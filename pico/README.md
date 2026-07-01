# POV-Globe — Projekt- und Implementierungs-Spec

Diese README beschreibt den kompletten Aufbau des Spinning-LED-Globe und ist
zugleich die Umsetzungs-Anweisung für die Firmware. Ziel: ein rotierender
LED-Ring zeigt per Persistence-of-Vision eine Weltkarte, auf der ein roter
Punkt (Flugzeugposition, per MQTT) eingeblendet wird. Später sollen auch
andere Bilder (z. B. Gesichtsfotos vom Stand) darstellbar sein.

---

## 1. Das eine Prinzip, das alles trägt

**Der Pico zeigt immer nur EINEN Framebuffer an.** Ein Framebuffer ist eine
Tabelle `[Spalte][LED]` mit fertigen Farben. Ob die Tabelle eine Weltkarte,
ein Gesicht oder ein Logo enthält, ist dem Pico egal — er schiebt sie nur
synchron zur Drehung raus.

Daraus folgt die wichtigste Architektur-Entscheidung: Der aktive Framebuffer
ist **austauschbar**. Er kann aus zwei Quellen kommen:

1. **Jetzt:** beim Booten aus einer Datei im Flash (`framebuffer.bin`).
2. **Später:** live über eine Verbindung reingeschickt (Foto-Erweiterung).

Die Firmware muss deshalb von Anfang an eine saubere "Framebuffer
austauschen"-Schnittstelle haben (siehe §9 und §12), auch wenn jetzt nur die
Flash-Quelle implementiert wird. So ist die Foto-Funktion später kein Umbau,
sondern nur eine zweite Quelle.

---

## 2. Aufgabenteilung der Plattformen

| Plattform | Rolle | Aufgaben |
|-----------|-------|----------|
| Pico 2 W (RP2350) | Echtzeit-Treiber | Motor-PWM, Taster, Hall/RPM, LED-Ausgabe (PIO/DMA), WLAN+MQTT für den roten Punkt, Framebuffer halten & anzeigen |
| PC (jetzt) / RPi 5 (später) | "Gehirn" | Bilder in Framebuffer rendern (`render_worldmap.py`), später Kamera + Live-Rendern |

Der Pico kann das **Rendern nicht** sinnvoll selbst (zu langsam in MicroPython)
und ein Linux-Rechner kann die **POV-Ausgabe nicht** sinnvoll selbst (zu viel
Timing-Jitter). Deshalb diese Teilung. Die Weltkarte wird **offline am PC**
gerendert, weil sie sich nie ändert.

---

## 3. Sprache & Laufzeitmodell

- **MicroPython** auf dem Pico. WLAN/MQTT/JSON bleiben in MicroPython (läuft schon).
- Die LED-Ausgabe läuft über **PIO + DMA**, damit sie unabhängig vom Python-GC
  jitterfrei ist. Erststufe darf auch normale `SPI.write` sein (siehe §13).
- Kommunikation der Module untereinander = **gemeinsamer Zustand** (`state.py`),
  kein Message-Passing. `main.py` ist der Dirigent (kooperative Hauptschleife,
  jedes Modul bekommt pro Runde kurz das Wort).
- Erst zu C wechseln, wenn nach dem APA102-Umstieg messbar noch Probleme
  bleiben — dann nur die Display-Engine als User-C-Modul (nicht das ganze Projekt).

---

## 4. Hardware & Pins

LED-Streifen: **APA102** (2-Draht: Data + Clock). Beide Arme zu **einem**
durchgehenden 100-LED-Strang verkettet (Data-Out Arm A → Data-In Arm B,
gemeinsamer Clock). Vorschlag (an bestehende Verkabelung angelehnt):

| Funktion | Pin | Hinweis |
|----------|-----|---------|
| APA102 Clock | GP18 | = SPI0 SCK |
| APA102 Data  | GP19 | = SPI0 TX (MOSI) |
| Hall-Sensor  | GP2  | Open-Collector → **Pull-up Pflicht** |
| Motor-PWM    | GP0  | IRL2910 low-side; GP0 ist UART0-TX, nie `UART(0)` benutzen |
| Taster schneller | GP1 | Pull-up, Taster nach GND |
| Taster langsamer | GP3 | Pull-up, Taster nach GND |

Bei PIO statt Hardware-SPI sind die LED-Pins frei wählbar. Falls die Arme doch
getrennt bleiben (2 Datenleitungen), in §7/§8 die LED-Reihenfolge anpassen.

Motor/Hall/Taster-Logik aus der vorhandenen Datei `new_combine_test.py`
übernehmen (Sanftanlauf-Rampe, Auto-Repeat, EMA-geglättete Periode, `hard=True`
Hall-IRQ) — die ist bereits erprobt.

---

## 5. Dateistruktur

Ein File pro Aufgabe (= ein MicroPython-Modul); `main.py` bindet sie zusammen:

```
main.py            # Dirigent: initialisiert alles, Hauptschleife
config.py          # alle Pins, Konstanten, Kalibrierzahlen an EINEM Ort
state.py           # gemeinsamer Zustand ("Whiteboard")
netz.py            # WLAN + MQTT + JSON -> schreibt Punkte/Bildwahl in state
rpm.py             # Hall-IRQ -> schreibt Drehperiode/Phase in state
motor.py           # PWM + Taster -> Drehzahl
display.py         # POV-Engine: Framebuffer + Punkt -> Spalten via PIO/DMA
framebuffer.bin    # vorgerenderte Weltkarte (Daten, kein Code; ins Flash)
```

PC-seitig (separat, nicht auf dem Pico): `render_worldmap.py`.

---

## 6. Gemeinsamer Zustand (`state.py`)

Ein einfaches Objekt/Modul mit den geteilten Variablen. Schreiber/Leser:

| Variable | geschrieben von | gelesen von | Inhalt |
|----------|-----------------|-------------|--------|
| `period_us`, `last_pulse_us`, `seq` | rpm | display | Drehperiode & Phase |
| `points` | netz | display | Liste von Punkten `{lat, lon, color}` |
| `active_fb`, `fb_columns`, `fb_leds` | netz/boot | display | aktiver Framebuffer + Maße |
| `duty` | motor | (info) | aktuelle Motor-Drehzahl |

Regel: Leser dürfen halb geschriebene Daten nie sehen. Für `points` und den
Framebuffer-Tausch deshalb **atomar referenzieren** (neue Liste/neuen Buffer
fertig bauen, dann mit einer einzigen Zuweisung aktiv setzen).

---

## 7. Datenformat `framebuffer.bin`

Erzeugt vom PC-Skript, muss von der Firmware exakt so gelesen werden:

```
Header (16 Byte, little-endian):
  char[4] magic        = "POVG"
  uint8   version      = 1
  uint16  num_columns
  uint16  num_leds
  uint8   bytes_per_led = 4
  uint8   brightness    = 31
  uint8[5] reserviert
Danach: num_columns * num_leds * 4 Byte Pixeldaten.
Jede LED = 4 Byte APA102-Wire-Format: [0xE0|31] [Blau] [Grün] [Rot]
```

Die Helligkeit (0xE0|31 = 0xFF) und die Kanalreihenfolge sind bereits
eingebacken — die Firmware streamt die Spalten-Bytes unverändert. Eine Spalte
sind `num_leds * 4` aufeinanderfolgende Bytes; Spalte `c` beginnt bei
`16 + c * num_leds * 4`.

**Wichtig:** Global-Brightness bleibt immer 31. Dimmen/Schattieren passiert
ausschließlich über die RGB-Werte (sonst Banding durch die langsame interne PWM).

---

## 8. Geometrie / Kalibrierung

Der Ring ist ein Meridian um die senkrechte Achse:
- LED-Position am Ring → Breitengrad.
- Drehwinkel → Längengrad.
- Arm A und Arm B bemalen gleichzeitig zwei um 180° versetzte Meridiane.

Der Längengrad-Versatz von Arm B ist **bereits im Framebuffer eingebacken**
(siehe Render-Skript). Die Firmware muss die Geometrie also nicht mehr rechnen
— sie wählt nur pro Drehposition die Spalte und schiebt alle 100 LEDs raus.

Kalibrier-Konstanten leben in `config.py` (Firmware) **und** im Render-Skript
(PC) und müssen übereinstimmen: `NUM_COLUMNS`, `NUM_LEDS`, sowie am laufenden
Globe einzustellen: `LON_OFFSET` (Nullmeridian-Ausrichtung) und `LON_DIRECTION`
(Drehrichtung). Die LED→Breitengrad-Zuordnung steckt komplett im Render-Skript
(`build_led_table`); ändert sich die Verkabelung, ändert sich nur dort etwas.

---

## 9. Display-Engine (`display.py`) — das zeitkritische Herzstück

Schnittstelle (zukunftssicher):
```
set_framebuffer(buf, num_columns, num_leds)   # tauscht den aktiven Buffer atomar
service()                                      # pro Hauptschleifen-Runde / bzw. eigener Takt
```

Ablauf pro Drehposition:
1. Aus `state.period_us`/`last_pulse_us` den aktuellen Drehwinkel schätzen.
2. Spaltennummer `c = winkel/360 * num_columns` berechnen.
3. Spalte `c` aus dem aktiven Framebuffer holen (Byte-Slice, kein Rechnen).
4. **Roten Punkt einblenden** (siehe §10) in eine Kopie der Spalte.
5. APA102-Rahmen drumherum und per **DMA** rausschieben:
   - Startrahmen: 4 Byte `0x00`
   - Spaltendaten: `num_leds * 4` Byte
   - Endrahmen: `(num_leds // 16) + 1` Byte `0x00`
6. Ausgabe über PIO+DMA (Ziel) bzw. `SPI.write` (Erststufe). Beim PIO-Weg den
   Taktteiler einmal pro Umdrehung an die gemessene Periode anpassen.

GC-Disziplin (gegen die "weißen Glitches"): GC während der Drehung gezielt in
die Totzeit legen (`gc.collect()` nach beiden Arm-Ausgaben einer Umdrehung),
ggf. `@micropython.viper` auf die heiße Schleife. Beim APA102 sind die Glitches
durch die Taktleitung ohnehin weitgehend entschärft.

---

## 10. Roter Punkt (Flug-Overlay)

Der Punkt steckt **nicht** im Framebuffer, sondern wird live drübergemalt:
- Für jeden Punkt aus `state.points` einmal `(lat, lon)` → `(spalte, led)`
  umrechnen (gleiche Geometrie/Kalibrierung wie das Render-Skript).
- Wenn die gerade auszugebende Spalte zur Punkt-Spalte passt (mit kleiner
  Toleranz, optional `size` LEDs/Spalten breit), die betroffene(n) LED(s) in der
  Spalten-Kopie mit Rot überschreiben: Wire-Bytes `[0xFF, 0x00, 0x00, 0xFF]`
  (Helligkeit, B=0, G=0, R=255 bei COLOR_ORDER BGR).
- Mehrere Punkte gleichzeitig möglich (Liste).

---

## 11. MQTT-Protokoll (`netz.py`)

Bestehende `umqtt.simple`-Logik weiterverwenden. Nachrichten sind JSON mit einem
`type`-Feld. Koordinaten sind **Längengrad/Breitengrad in Dezimalgrad**
(NICHT X/Y), weil das dem Flugdatenformat entspricht und hardwareunabhängig ist.

```json
{ "type": "set_points",
  "points": [ { "id": "DLH123", "lat": 48.35, "lon": 11.78, "color": [255,0,0] } ] }
```
Konvention: `lat` -90..+90 (Süd→Nord), `lon` -180..+180 (West→Ost, positiv=Ost).
Optional pro Punkt: `size` (Breite in LEDs/Spalten, Default 1), `blink`.

Weitere Typen:
- `{ "type": "clear_points" }` — alle Punkte löschen.
- `{ "type": "change_all_to_color", "value": [r,g,b] }` — bestehend, ganze Anzeige.
- `{ "type": "set_image", "name": "..." }` — Vorbereitung für Bildwechsel (§12).

`netz.py` parst die Nachricht und aktualisiert nur `state` (Punkte/Bildwahl),
rechnet selbst nichts an der Anzeige.

---

## 12. Zukunftssicher: Live-Framebuffer-Quelle (Foto-Erweiterung)

Jetzt **nicht implementieren**, aber die Schnittstelle aus §9
(`set_framebuffer`) so bauen, dass ein zweiter "Lieferant" sie aufrufen kann:

- Quelle ist später ein RPi 5, der ein Foto mit demselben `render_worldmap.py`
  in das gleiche `framebuffer.bin`-Format rendert.
- Übertragung an den **laufenden** Pico: bevorzugt per Kabel (USB-Serial/UART
  oder SPI), weil ~100 KB über WLAN/MQTT am Stück viel sind. Über MQTT ginge es
  in Häppchen (z. B. zeilenweise) mit Reassembly auf dem Pico.
- Empfangenes Bild in einen **zweiten** Buffer schreiben, dann mit einer
  Zuweisung aktiv setzen (Double-Buffering, kein Tearing).

Damit ist "Besucher macht Foto → erscheint auf dem Globus" nur noch ein neuer
Sender für `set_framebuffer`. Die Weltkarte läuft dann genauso (sie ist der
Standard-Buffer beim Start).

Hinweis: Ein Gesicht über die ganze Kugel gewickelt wirkt an den Polen verzerrt;
meist will man es nur auf einen Spalten-Bereich (eine Seite) setzen. Das ist
reine Render-Skript-Sache, am Pico ändert sich nichts.

---

## 13. Implementierungs-Meilensteine (in dieser Reihenfolge)

1. **End-to-End, simpel:** `framebuffer.bin` beim Boot laden, mit
   blockierendem `SPI.write` bei moderater `NUM_COLUMNS` ausgeben. Ziel: Karte
   erscheint, dreht synchron, eine MQTT-Nachricht setzt sichtbar einen Punkt.
   Hier darf das Bild bei Nachrichten kurz ruckeln.
2. **Ausgabe auf PIO + DMA umstellen:** Hardware schiebt die Spalten, CPU setzt
   den Takt nur einmal pro Umdrehung. Bringt die hohe Spaltenzahl.
3. **Feintuning:** `LON_OFFSET`/`LON_DIRECTION` kalibrieren, roter Punkt,
   GC-Disziplin, Helligkeit (immer 31).
4. **(Später)** Live-Framebuffer-Quelle für Fotos.

---

## 14. Constraints & Fallstricke (unbedingt beachten)

- Global-Brightness **immer 31**; dimmen nur über RGB.
- Hall-Pin braucht **Pull-up**; Hall-IRQ mit `hard=True`, im Handler nichts
  allokieren (nur Integer-Arithmetik).
- GP0 ist UART0-TX → niemals `machine.UART(0)`.
- Display-Ausgabe muss DMA-getrieben sein, damit WLAN-/GC-Pausen sie nicht stören.
- Geteilte Daten (Punkte, Framebuffer) immer atomar tauschen.
- `NUM_COLUMNS`/`NUM_LEDS`/Geometrie müssen zwischen `config.py` (Pico) und
  `render_worldmap.py` (PC) identisch sein.
- Framebuffer-Größe bei 256×100×4 ≈ 100 KB (+16 Byte Header) — passt in
  Flash und RAM (RP2350: 520 KB SRAM).

---

## 15. PC-Render-Skript

`render_worldmap.py` (liegt bei) erzeugt `framebuffer.bin` aus einem
equirektangulären Bild. Es ist die **einzige** Render-Stelle für alle Bilder
(Karte, Gesicht, Logo). Aufruf z. B.:

```
pip install pillow numpy
python render_worldmap.py world_equirect.png -o framebuffer.bin --preview vorschau.png
python render_worldmap.py --demo --preview vorschau.png   # Test ohne eigene Karte
```

Danach `framebuffer.bin` mit Thonny oder `mpremote` auf den Pico kopieren.
Die Kalibrier-Konstanten oben im Skript müssen mit `config.py` übereinstimmen.
