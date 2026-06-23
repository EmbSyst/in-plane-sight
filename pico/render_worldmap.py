#!/usr/bin/env python3
"""
render_worldmap.py - POV-Globe Framebuffer-Renderer
====================================================

Wandelt ein equirektanguläres Bild (Weltkarte, Smiley, Gesicht, Logo, ...) in
eine `framebuffer.bin` für den POV-Globe um. Diese Datei wird auf den Pico
kopiert und dort beim Booten in ein bytearray geladen.

WICHTIGES PRINZIP
-----------------
Der Pico zeigt immer nur EINEN Framebuffer an - egal ob Weltkarte oder Foto.
Dieses Skript ist daher die einzige Render-Stelle fuer ALLE Bilder. Ein Smiley
durchlaeuft genau denselben Code wie die Weltkarte; nur die Eingabedatei
(und evtl. der Laengen-Bereich) aendert sich.

LED-TREIBER (NEU)
-----------------
Das Wire-Format haengt vom LED-Typ ab und wird ueber DRIVER (bzw. --driver)
gewaehlt. Der Pico streamt die Bytes danach UNVERAENDERT raus:

  DRIVER = "APA102"   -> 2-Draht (Data+Clock), 4 Byte/LED: [0xE0|bright][B][G][R]
  DRIVER = "SK6812"   -> 1-Draht (nur Data),   3 Byte/LED: [G][R][B]      (RGB)
  DRIVER = "SK6812W"  -> 1-Draht (nur Data),   4 Byte/LED: [G][R][B][W]   (RGBW)

GEOMETRIE
---------
Der LED-Ring ist ein Meridian, der um die senkrechte Achse dreht.
  - Position einer LED am Ring  -> Breitengrad (Latitude)
  - Drehwinkel                  -> Laengengrad (Longitude)
  - Arm A und Arm B bemalen gleichzeitig zwei um 180 Grad versetzte Meridiane.
Der Versatz von Arm B ist hier bereits in den Framebuffer eingebacken.

FORMAT von framebuffer.bin
--------------------------
  Header (16 Byte, little-endian):
    char[4] magic       = "POVG"
    uint8   version     = 1
    uint16  num_columns
    uint16  num_leds
    uint8   bytes_per_led   (4 = APA102 oder SK6812-RGBW, 3 = SK6812-RGB)
    uint8   brightness      (APA102: 0..31; SK6812: informativ, unbenutzt)
    uint8[5] reserviert (0)
  Danach: num_columns * num_leds * bytes_per_led Byte Pixeldaten in der
  Reihenfolge COLOR_ORDER (APA102: BGR + Helligkeits-Byte; SK6812: GRB / GRBW).

Abhaengigkeiten:  pip install pillow numpy
Beispiele:
  python render_worldmap.py --smiley --fit-latitude -o framebuffer.bin --preview vorschau_smiley.png
  python render_worldmap.py world_equirect.png --driver apa102 -o framebuffer.bin --preview vorschau.png
  python render_worldmap.py --demo --preview vorschau.png
"""

import argparse
import math
import struct

import numpy as np
from PIL import Image, ImageDraw

# ============================================================================
# AKTIVE HARDWARE  (muss mit config.py auf dem Pico uebereinstimmen!)
# ============================================================================
DRIVER = "SK6812W"         # "SK6812" (RGB), "SK6812W" (RGBW, euer Streifen), "APA102"

# >>> AN EURE LED-ZAHL ANPASSEN <<<  (danach neu rendern; gleiche Werte in config.py)
NUM_LEDS     = 100          # LEDs gesamt (beide Arme)  = 2 * LEDS_PER_ARM
LEDS_PER_ARM = 50          # LEDs pro Arm/Streifen
NUM_COLUMNS  = 64          # Drehpositionen pro Umdrehung (klein wg. 1-Draht-Tempo)

# Ring-Winkel (von unten = Suedpol gemessen), aus der Ring-Zeichnung:
ARM_SPAN_DEG = 155.0       # Winkel, den ein Arm ueberstreicht
A_START_DEG  = 20.0        # Ring-Winkel der ersten LED von Arm A
B_START_DEG  = 185.0       # Ring-Winkel der ersten LED von Arm B
A_REVERSED   = False       # True, falls LED 0 von Arm A am oberen Ende sitzt
B_REVERSED   = False       # True, falls LED 0 von Arm B am 340-Grad-Ende sitzt

# Laengengrad-Kalibrierung: im Test BEWUSST neutral lassen und stattdessen
# am laufenden Globe ueber COLUMN_OFFSET/LON_DIRECTION in config.py kalibrieren.
B_LON_OFFSET  = 180.0      # Arm B malt den gegenueberliegenden Meridian
LON_OFFSET    = 0.0        # 0 lassen -> Ausrichtung in der Firmware
LON_DIRECTION = +1         # +1 lassen -> Drehrichtung in der Firmware

# Breitengrad-Behandlung:
#   False = geografisch korrekt; Polkappen (>+85 / <-70 Grad) fehlen.
#   True  = das abgedeckte Band wird auf die volle Bildhoehe gestreckt
#           (nichts geht verloren, leichte Verzerrung). Fuer Smiley sinnvoll.
FIT_FULL_LATITUDE = False

# ============================================================================
# WIRE-FORMAT  (aus DRIVER abgeleitet)
# ============================================================================
BRIGHTNESS = 31            # APA102: IMMER 31 (Dimmen ueber RGB). SK6812: unbenutzt.
MAX_LEVEL  = 255           # RGB-Skalierung 0..255 (SK6812 ggf. senken, Strom!)
WHITE_MODE = "min"         # nur RGBW: "min" = Weiss-LED uebernimmt Grau-/Weissanteil
                           #           "none" = Weiss-LED bleibt aus (W=0)
MAGIC      = b"POVG"
VERSION    = 1

# werden von apply_driver() gesetzt:
COLOR_ORDER        = "GRB"
BYTES_PER_LED      = 3
USE_BRIGHTNESS_BYTE = False


def apply_driver(name):
    """Setzt COLOR_ORDER / BYTES_PER_LED / Helligkeits-Byte je nach LED-Typ."""
    global COLOR_ORDER, BYTES_PER_LED, USE_BRIGHTNESS_BYTE
    name = name.upper()
    if name == "APA102":
        COLOR_ORDER, BYTES_PER_LED, USE_BRIGHTNESS_BYTE = "BGR", 4, True
    elif name == "SK6812":
        COLOR_ORDER, BYTES_PER_LED, USE_BRIGHTNESS_BYTE = "GRB", 3, False
    elif name in ("SK6812W", "SK6812RGBW", "SK6812_RGBW"):
        COLOR_ORDER, BYTES_PER_LED, USE_BRIGHTNESS_BYTE = "GRBW", 4, False
    else:
        raise SystemExit(
            "unbekannter Treiber: %s (erlaubt: APA102, SK6812, SK6812W)" % name)


apply_driver(DRIVER)


# ----------------------------------------------------------------------------
def build_led_table():
    """Pro globalem LED-Index (0..NUM_LEDS-1) -> (latitude_deg, lon_offset_deg).
    Hier steckt die gesamte Ring-Geometrie. Wer die Verkabelung aendert,
    aendert nur diese Funktion."""
    assert NUM_LEDS == 2 * LEDS_PER_ARM, "NUM_LEDS muss 2 * LEDS_PER_ARM sein"
    step = ARM_SPAN_DEG / (LEDS_PER_ARM - 1)
    table = []
    # Arm A: globale Indizes 0..k-1  -> Breite = theta - 90
    for i in range(LEDS_PER_ARM):
        k = (LEDS_PER_ARM - 1 - i) if A_REVERSED else i
        theta = A_START_DEG + k * step
        table.append((theta - 90.0, 0.0))
    # Arm B: globale Indizes k..2k-1 -> Breite = 270 - theta (gespiegelt)
    for i in range(LEDS_PER_ARM):
        j = (LEDS_PER_ARM - 1 - i) if B_REVERSED else i
        theta = B_START_DEG + j * step
        table.append((270.0 - theta, B_LON_OFFSET))
    return table


def column_longitude(c):
    """Drehposition (Spalte) -> Laengengrad in Grad (0..360)."""
    return (c / NUM_COLUMNS) * 360.0


def sample_bilinear(arr, xf, yf):
    """Bilineares Sampling. xf wraplaeuft (Laenge), yf wird geklemmt (Breite).
    xf, yf in 0..1; yf=0 ist oben (+90 Grad)."""
    h, w = arr.shape[0], arr.shape[1]
    x = (xf % 1.0) * w
    y = min(max(yf, 0.0), 1.0) * (h - 1)
    x0 = int(math.floor(x)) % w
    x1 = (x0 + 1) % w
    y0 = int(math.floor(y))
    y1 = min(y0 + 1, h - 1)
    dx = x - math.floor(x)
    dy = y - y0
    top = arr[y0, x0] * (1 - dx) + arr[y0, x1] * dx
    bot = arr[y1, x0] * (1 - dx) + arr[y1, x1] * dx
    return top * (1 - dy) + bot * dy


def render(img):
    """Erzeugt das Farb-Gitter [NUM_COLUMNS][NUM_LEDS][3] (float 0..255)."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    table = build_led_table()
    lats = [lat for lat, _ in table]
    lat_min, lat_max = min(lats), max(lats)

    yfs = []
    for lat, _ in table:
        if FIT_FULL_LATITUDE:
            norm = (lat - lat_min) / (lat_max - lat_min)   # 0..1 ueber das Band
            lat_eff = -90.0 + norm * 180.0
        else:
            lat_eff = lat
        yfs.append((90.0 - lat_eff) / 180.0)

    grid = np.zeros((NUM_COLUMNS, NUM_LEDS, 3), dtype=np.float32)
    for c in range(NUM_COLUMNS):
        base_lon = LON_DIRECTION * column_longitude(c) + LON_OFFSET
        for led in range(NUM_LEDS):
            lon = base_lon + table[led][1]
            grid[c, led] = sample_bilinear(arr, (lon % 360.0) / 360.0, yfs[led])
    return grid


def pack(grid):
    """Gitter -> Bytes (Header + Wire-Format des aktiven Treibers)."""
    header = struct.pack("<4sBHHBB", MAGIC, VERSION,
                         NUM_COLUMNS, NUM_LEDS, BYTES_PER_LED, BRIGHTNESS)
    header += b"\x00" * (16 - len(header))
    out = bytearray(header)
    bright_byte = 0xE0 | (BRIGHTNESS & 0x1F)
    scale = MAX_LEVEL / 255.0
    for c in range(NUM_COLUMNS):
        for led in range(NUM_LEDS):
            r, g, b = (int(round(min(max(v, 0), 255) * scale)) for v in grid[c, led])
            chan = {"R": r, "G": g, "B": b}
            if "W" in COLOR_ORDER:                       # RGBW: Weiss-Kanal ableiten
                w = min(r, g, b) if WHITE_MODE == "min" else 0
                chan["R"] = r - w
                chan["G"] = g - w
                chan["B"] = b - w
                chan["W"] = w
            if USE_BRIGHTNESS_BYTE:
                out.append(bright_byte)
            for ch in COLOR_ORDER:
                out.append(chan[ch])
    return bytes(out)


def save_preview(grid, path):
    """Speichert das 'abgewickelte' Bild zur Sichtpruefung
    (Breite = Spalten/Laenge, Hoehe = LEDs/Breite)."""
    rgb = np.clip(grid.transpose(1, 0, 2), 0, 255).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB").resize((NUM_COLUMNS * 8, NUM_LEDS * 8),
                                             Image.NEAREST)
    img.save(path)


def make_demo_image(w=1024, h=512):
    """Test-Karte, um die Pipeline ohne echte Weltkarte zu pruefen."""
    img = Image.new("RGB", (w, h), (12, 40, 110))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, h // 2], fill=(20, 70, 150))
    d.ellipse([w * 0.35, h * 0.30, w * 0.65, h * 0.70], fill=(40, 140, 60))
    d.ellipse([w * 0.10, h * 0.45, w * 0.25, h * 0.62], fill=(40, 140, 60))
    for lon in range(0, w, max(1, w // 12)):
        d.line([(lon, 0), (lon, h)], fill=(180, 180, 180), width=1)
    for lat in range(0, h, max(1, h // 6)):
        d.line([(0, lat), (w, lat)], fill=(180, 180, 180), width=1)
    d.ellipse([w // 2 - 8, h // 2 - 8, w // 2 + 8, h // 2 + 8], fill=(230, 30, 30))
    return img


def make_smiley_image(w=512, h=512):
    """Einfacher Smiley als Testbild fuer den SK6812-Aufbau.
    Schwarzer Hintergrund = LEDs aus, gelbes Gesicht = LEDs an."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(w * 0.06)
    d.ellipse([pad, pad, w - pad, h - pad], fill=(255, 200, 0))          # Gesicht
    eye_w, eye_h = w * 0.10, h * 0.16
    ey = h * 0.36
    for ex in (w * 0.34, w * 0.66):                                      # Augen
        d.ellipse([ex - eye_w / 2, ey - eye_h / 2, ex + eye_w / 2, ey + eye_h / 2],
                  fill=(20, 20, 20))
    d.arc([w * 0.30, h * 0.38, w * 0.70, h * 0.80],                      # Laecheln
          start=20, end=160, fill=(20, 20, 20), width=int(h * 0.06))
    return img


def main():
    ap = argparse.ArgumentParser(description="POV-Globe Framebuffer-Renderer")
    ap.add_argument("image", nargs="?", help="equirektangulaeres Eingabebild")
    ap.add_argument("-o", "--out", default="framebuffer.bin")
    ap.add_argument("--preview", default=None, help="optional: Vorschau-PNG")
    ap.add_argument("--demo", action="store_true", help="Test-Karte erzeugen")
    ap.add_argument("--smiley", action="store_true", help="Smiley-Testbild erzeugen")
    ap.add_argument("--driver", default=None,
                    choices=["apa102", "sk6812", "sk6812w",
                             "APA102", "SK6812", "SK6812W"],
                    help="LED-Typ ueberschreiben (Default: DRIVER im Skript)")
    ap.add_argument("--white", default=None, choices=["min", "none"],
                    help="RGBW: Weiss-Kanal ableiten (min) oder aus (none)")
    ap.add_argument("--fit-latitude", action="store_true",
                    help="abgedecktes Breitenband auf volle Bildhoehe strecken")
    args = ap.parse_args()

    if args.driver:
        apply_driver(args.driver)
    if args.white:
        global WHITE_MODE
        WHITE_MODE = args.white
    if args.fit_latitude:
        global FIT_FULL_LATITUDE
        FIT_FULL_LATITUDE = True

    if args.smiley:
        img = make_smiley_image()
    elif args.demo or not args.image:
        if not args.demo:
            print("Kein Bild angegeben -> erzeuge Demo-Karte.")
        img = make_demo_image()
    else:
        img = Image.open(args.image)

    grid = render(img)
    data = pack(grid)
    with open(args.out, "wb") as f:
        f.write(data)
    print("geschrieben: %s  (%d Byte, Treiber %s, %d Spalten x %d LEDs x %d B, "
          "COLOR_ORDER %s)"
          % (args.out, len(data), DRIVER if not args.driver else args.driver.upper(),
             NUM_COLUMNS, NUM_LEDS, BYTES_PER_LED, COLOR_ORDER))

    if args.preview:
        save_preview(grid, args.preview)
        print("Vorschau:    %s" % args.preview)


if __name__ == "__main__":
    main()
