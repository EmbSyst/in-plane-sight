"""display.py - POV-Engine fuer SK6812-RGBW ueber PIO + DMA (zwei Arme).

Ausgabe laeuft NICHT mehr ueber neopixel (Bit-Banging, das die Interrupts sperrt
und dadurch Hall-Pulse verschluckt), sondern ueber zwei PIO-State-Machines, die
per DMA im Hintergrund gefuettert werden:
  - SM0 -> DATA_PIN_A, SM1 -> DATA_PIN_B  (PIO0)
  - je ein DMA-Kanal schiebt die Arm-Bytes in die TX-FIFO der SM
  - bswap dreht die GRBW-Bytes in die MSB-first-Reihenfolge der PIO
    -> der Framebuffer bleibt unveraendert GRBW, kein CPU-Umsortieren.

Die CPU loest die DMA nur an (~us) und ist sofort wieder frei -> Interrupts
bleiben offen (Hall sauber), und es bleibt Zeit fuer mehr Spalten.

Schnittstelle unveraendert: set_framebuffer(buf, num_columns, num_leds), service().
Zusaetzlich aus state (von netz.py): Punkt-Overlay (set_points) und Anzeige-Modi
(change_display_mode: 0=AUS, 1=EINE_FARBE, 3=REGENBOGEN, sonst=Bild).
"""

import time
import rp2
from machine import Pin

import config
import state

# --- PIO0-Register (RP2040/RP2350 identisch) -------------------------------
_PIO0_BASE = 0x50200000
_TXF0 = _PIO0_BASE + 0x10          # TX-FIFO von SM0
_TXF1 = _PIO0_BASE + 0x14          # TX-FIFO von SM1
_DREQ_PIO0_TX0 = 0                 # DMA-Pacing: PIO0 SM0 TX
_DREQ_PIO0_TX1 = 1                 # DMA-Pacing: PIO0 SM1 TX

_PIO_FREQ = 8_000_000              # 10 Zyklen/Bit -> 800 kHz WS2812/SK6812-Timing


@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT,
             autopull=True, pull_thresh=32)            # 32 bit/LED = RGBW
def _sk6812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]
    label("do_zero")
    nop()                   .side(0)    [T2 - 1]
    wrap()


def _encode(rgb):
    """RGB-Liste -> Bytes in config.COLOR_ORDER (mit W-Ableitung bei RGBW)."""
    r = min(255, max(0, int(rgb[0])))
    g = min(255, max(0, int(rgb[1])))
    b = min(255, max(0, int(rgb[2])))
    w = 0
    if "W" in config.COLOR_ORDER:
        w = min(r, g, b)
        r -= w
        g -= w
        b -= w
    chan = {"R": r, "G": g, "B": b, "W": w}
    return bytes([chan[ch] for ch in config.COLOR_ORDER])


class Display:
    def __init__(self):
        if config.BYTES_PER_LED != 4:
            raise ValueError("PIO+DMA-Pfad ist fuer RGBW (BYTES_PER_LED=4) gebaut")

        nper = config.LEDS_PER_ARM
        # Zwei State-Machines auf PIO0 (SM0/SM1), je ein Daten-Pin.
        self._sm_a = rp2.StateMachine(0, _sk6812, freq=_PIO_FREQ,
                                      sideset_base=Pin(config.DATA_PIN_A))
        self._sm_b = rp2.StateMachine(1, _sk6812, freq=_PIO_FREQ,
                                      sideset_base=Pin(config.DATA_PIN_B))
        self._sm_a.active(1)
        self._sm_b.active(1)

        # Zwei DMA-Kanaele; bswap dreht GRBW -> MSB-first fuer die PIO.
        self._dma_a = rp2.DMA()
        self._dma_b = rp2.DMA()
        self._ctrl_a = self._dma_a.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                             treq_sel=_DREQ_PIO0_TX0, bswap=True)
        self._ctrl_b = self._dma_b.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                             treq_sel=_DREQ_PIO0_TX1, bswap=True)

        # Arbeitspuffer pro Arm (werden pro Spalte gefuellt, dann per DMA gestreamt)
        self.buf_a = bytearray(nper * 4)
        self.buf_b = bytearray(nper * 4)

        self.fb = None
        self.num_columns = config.NUM_COLUMNS
        self.stride = config.NUM_LEDS * 4
        self.arm_bytes = nper * 4
        self.last_col = -1

        self._lat = self._build_lat_table()       # Breitengrad pro LED-Index

        # Caches fuer Overlay und Modus
        self._points_ref = None
        self._overlay = {}              # Spalte -> [(is_b, byte_offset, color_bytes)]
        self._mode = "?"
        self._mode_color_ref = None
        self._solid = None              # vorgefertigte Arm-Bytes fuer AUS / EINE_FARBE

    # ----- Geometrie -------------------------------------------------------
    def _build_lat_table(self):
        """Gleiche Formel wie render_worldmap.build_led_table (nur Breitengrad)."""
        step = config.ARM_SPAN_DEG / (config.LEDS_PER_ARM - 1)
        tab = []
        for i in range(config.LEDS_PER_ARM):
            k = (config.LEDS_PER_ARM - 1 - i) if config.A_REVERSED else i
            tab.append(config.A_START_DEG + k * step - 90.0)
        for i in range(config.LEDS_PER_ARM):
            j = (config.LEDS_PER_ARM - 1 - i) if config.B_REVERSED else i
            tab.append(270.0 - (config.B_START_DEG + j * step))
        return tab

    def _nearest_led(self, lat, lo, hi):
        best, bd = lo, 1e9
        for i in range(lo, hi):
            d = self._lat[i] - lat
            if d < 0:
                d = -d
            if d < bd:
                bd, best = d, i
        return best

    # ----- Framebuffer -----------------------------------------------------
    def set_framebuffer(self, buf, num_columns, num_leds):
        """Tauscht den aktiven Buffer mit EINER Zuweisung (kein Tearing)."""
        self.num_columns = num_columns
        self.stride = num_leds * 4
        self.last_col = -1
        self.fb = buf

    # ----- Overlay (set_points) -------------------------------------------
    def _rebuild_overlay(self, pts):
        """Aus state.points eine Spalten->LED-Tabelle bauen (nur bei Aenderung)."""
        ov = {}
        ncol = self.num_columns
        nper = config.LEDS_PER_ARM
        nled = config.NUM_LEDS
        for p in pts:
            try:
                lat = float(p["lat"])
                lon = float(p["lon"]) % 360.0
                col = _encode(p.get("color", [255, 0, 0]))
                size = int(p.get("size", 1))
            except Exception as e:
                print("display: Punkt fehlerhaft:", e)
                continue
            # Arm A zeigt lon, Arm B den um 180 Grad versetzten Meridian
            cA = int(round(lon / 360.0 * ncol)) % ncol
            cB = int(round(((lon - 180.0) % 360.0) / 360.0 * ncol)) % ncol
            ledA = self._nearest_led(lat, 0, nper)
            ledB = self._nearest_led(lat, nper, nled)
            self._add_blob(ov, cA, ledA, col, size, 0, nper - 1)
            self._add_blob(ov, cB, ledB, col, size, nper, nled - 1)
        self._overlay = ov
        self.last_col = -1

    def _add_blob(self, ov, c, gled, col, size, lo, hi):
        """Punkt (optional size x size) in die Overlay-Tabelle eintragen."""
        ncol = self.num_columns
        nper = config.LEDS_PER_ARM
        half = size // 2
        for dc in range(-half, half + 1):
            cc = (c + dc) % ncol
            lst = ov.get(cc)
            if lst is None:
                lst = []
                ov[cc] = lst
            for dl in range(-half, half + 1):
                gl = gled + dl
                if gl < lo or gl > hi:          # im selben Arm bleiben
                    continue
                is_b = gl >= nper
                off = (gl - nper if is_b else gl) * 4
                lst.append((is_b, off, col))

    # ----- Modi (change_display_mode) -------------------------------------
    def _rebuild_mode(self):
        nper = config.LEDS_PER_ARM
        m = self._mode
        if m == 0:                              # AUS
            self._solid = bytes(nper * 4)
        elif m == 1:                            # EINE_FARBE
            self._solid = _encode(state.mode_color or [255, 255, 255]) * nper
        else:                                   # Bild / Regenbogen -> kein Solid
            self._solid = None
        self.last_col = -1

    def _rainbow(self, c):
        """Einfacher Farbkreis ueber die Spalten -> Arm-Bytes."""
        h = (c % self.num_columns) * 6.0 / self.num_columns
        x = int((1 - abs(h % 2 - 1)) * 255)
        i = int(h)
        if i == 0:
            rgb = (255, x, 0)
        elif i == 1:
            rgb = (x, 255, 0)
        elif i == 2:
            rgb = (0, 255, x)
        elif i == 3:
            rgb = (0, x, 255)
        elif i == 4:
            rgb = (x, 0, 255)
        else:
            rgb = (255, 0, x)
        return _encode(rgb) * config.LEDS_PER_ARM

    # ----- Hauptarbeit -----------------------------------------------------
    def _current_column(self):
        period = state.period_us
        if period <= 0:
            return 0
        dt = time.ticks_diff(time.ticks_us(), state.last_pulse_us)
        frac = (dt % period) / period
        c = int(frac * self.num_columns) * config.LON_DIRECTION + config.COLUMN_OFFSET
        return c % self.num_columns

    def service(self):
        # Aenderungen aus state uebernehmen (atomar referenziert)
        pts = state.points
        if pts is not self._points_ref:
            self._points_ref = pts
            self._rebuild_overlay(pts)
        if (state.display_mode != self._mode
                or state.mode_color is not self._mode_color_ref):
            self._mode = state.display_mode
            self._mode_color_ref = state.mode_color
            self._rebuild_mode()

        c = self._current_column()
        if c == self.last_col:
            return
        # Puffer erst neu fuellen, wenn die letzte DMA durch ist (sonst Tearing)
        if self._dma_a.active() or self._dma_b.active():
            return
        self.last_col = c

        buf_a = self.buf_a
        buf_b = self.buf_b

        # 1) Grundbild der Spalte in beide Arm-Puffer schreiben
        if self._solid is not None:             # AUS oder EINE_FARBE
            buf_a[:] = self._solid
            buf_b[:] = self._solid
        elif self._mode == 3:                   # REGENBOGEN
            rb = self._rainbow(c)
            buf_a[:] = rb
            buf_b[:] = rb
        elif self.fb is not None:               # Bild (Framebuffer)
            base = c * self.stride
            buf_a[:] = self.fb[base : base + self.arm_bytes]
            buf_b[:] = self.fb[base + self.arm_bytes : base + self.stride]
        else:
            return                              # nichts zu zeigen

        # 2) Punkt-Overlay drueberblenden
        entries = self._overlay.get(c)
        if entries:
            for is_b, off, col in entries:
                if is_b:
                    buf_b[off:off + 4] = col
                else:
                    buf_a[off:off + 4] = col

        # 3) DMA anstossen -> PIO schiebt im Hintergrund raus, CPU ist frei
        self._dma_a.config(read=buf_a, write=_TXF0, count=config.LEDS_PER_ARM,
                           ctrl=self._ctrl_a, trigger=True)
        self._dma_b.config(read=buf_b, write=_TXF1, count=config.LEDS_PER_ARM,
                           ctrl=self._ctrl_b, trigger=True)
