"""
config.py - alle Pins, Konstanten und Kalibrierzahlen an EINEM Ort.

ACHTUNG: NUM_COLUMNS, NUM_LEDS, LEDS_PER_ARM, COLOR_ORDER und BYTES_PER_LED
MUESSEN exakt mit render_worldmap.py uebereinstimmen, sonst passt der
Framebuffer nicht zum Streifen (main.py prueft das beim Laden).

TEST-AUFBAU: alter SK6812-RGB-Streifen, 1-Draht. ZWEI getrennte Streifen
(Arm A und Arm B) an je EINEM eigenen Daten-Pin. Kein MQTT.
"""

# --- LED-Typ (== render_worldmap.py) ---------------------------------------
LED_TYPE      = "SK6812W"  # 1-Draht (WS2812-Familie), RGBW
COLOR_ORDER   = "GRBW"     # SK6812-RGBW -> GRBW
BYTES_PER_LED = 4          # 4 Byte pro LED (G,R,B,W; kein Helligkeits-Byte)

# --- Geometrie / Aufloesung (== render_worldmap.py) ------------------------
# >>> AN EURE LED-ZAHL ANPASSEN <<<  (danach framebuffer.bin neu rendern!)
LEDS_PER_ARM  = 50         # LEDs pro Streifen/Arm
NUM_LEDS      = 100         # = 2 * LEDS_PER_ARM (beide Arme zusammen)
NUM_COLUMNS   = 64         # Drehpositionen pro Umdrehung (klein wg. 1-Draht-Tempo)

# Ring-Geometrie (== render_worldmap.py) - fuer das Punkt-Overlay (lat/lon -> LED):
ARM_SPAN_DEG  = 155.0      # Winkel, den ein Arm ueberstreicht
A_START_DEG   = 20.0       # Ring-Winkel der ersten LED von Arm A
B_START_DEG   = 185.0      # Ring-Winkel der ersten LED von Arm B
A_REVERSED    = False
B_REVERSED    = False

# --- Pins  (>>> EURE BELEGUNG EINTRAGEN <<<) -------------------------------
DATA_PIN_A    = 13         # Signal Arm A  (eine 180-Grad-Seite)
DATA_PIN_B    = 14         # Signal Arm B  (gegenueberliegende Seite)
HALL_PIN      = 16          # Open-Collector -> PULL_UP Pflicht
MOTOR_PIN     = 10          # IRL2910 low-side (GP0 = UART0-TX, nie UART(0)!)
BTN_FASTER    = 18          # Taster nach GND, PULL_UP
BTN_SLOWER    = 20          # Taster nach GND, PULL_UP

# --- Laengengrad-Kalibrierung (am laufenden Globe einstellen) --------------
# Im Render-Skript bleibt LON_OFFSET = 0 -> hier kalibrieren, ohne neu zu rendern.
COLUMN_OFFSET = 20          # Spalten-Versatz: dreht die ganze Anzeige (Karte UND Punkte)
LON_DIRECTION = +1         # +1 / -1 je nach Drehrichtung
# Nur den Punkt (Overlay) RELATIV zur Karte schieben - COLUMN_OFFSET bewegt beide
# zusammen, hiermit den Punkt allein verschieben. Einheit = Spalten (1 ~ 5.6 Grad).
# "etwas weiter rechts": +1/+2 probieren; geht's falsch herum, Vorzeichen drehen.
POINT_COLUMN_OFFSET = 2

# --- Anzeige-Stabilisierung (Hall-Periode) ---------------------------------
# Median-Filter ueber die letzten N akzeptierten Hall-Perioden gegen Mess-Spikes
# (z.B. 350->900->150 rpm), damit das POV-Bild nicht springt. Groesser = ruhiger,
# aber traeger bei echten Drehzahlwechseln (N=5 toleriert bis zu 2 Spikes in Folge).
PERIOD_MEDIAN_N = 5

# --- Motor / Hall / Taster -------------------------------------------------
MOTOR_FREQ    = 3906       # PWM-Frequenz (Hz) - wie im funktionierenden Test
SPEED_STEP    = 256        # duty_u16-Schritt pro Tastendruck (= STEP im alten Code)
RAMP_STEP     = 400        # Sanftanlauf: max. duty-Aenderung pro service()
REPEAT_MS     = 100        # Auto-Repeat-Intervall (= DEBOUNCE_MS im alten Code)
MIN_PERIOD_US = 10000      # Hall-Entprellung (~10ms wie ENTPRELL_MS; kuerzere Pulse weg)
HALL_MAX_SKIP = 3          # Ausreisser-Schutz: hoechstens so viele unplausible Pulse
                           #   am Stueck verwerfen, dann annehmen (kein Festklemmen)

# --- change_PWM (MQTT, Web-UI): feste rpm -> PWM-Umrechnung -----------------
# Gilt NUR fuer den MQTT-Pfad. Direkte (offene) Umrechnung rpm -> duty_u16:
# KEIN Hochregeln, KEINE Hall-Rueckkopplung. Auf RPM_DUTY_CAP begrenzt.
# Die zwei Hardware-Taster bleiben unveraendert (manuelle Duty-Steuerung).
# Faktor aus Referenz 13% duty ~= 350 rpm  ->  0.13*65535/350 ~= 24.3 duty/rpm.
# Feste Werte:  200->4860   400->9720   600->14580   (alle <= CAP)
#               800->19440, 1000->24300  -> am CAP (16384) gedeckelt
RPM_DUTY_PER_RPM = 24.3       # duty_u16 je rpm (am Hall-Log auf dem Aufbau kalibrieren)
RPM_DUTY_CAP     = 16384      # Failsafe: max. Duty (~25% von 65535; ~knapp ueber 600 rpm)

# --- WLAN / MQTT (netz.py) -------------------------------------------------
# Echte Zugangsdaten NICHT ins git committen.
# Netzwerke in Prioritaetsreihenfolge: erst Haupt-AP, dann Fallback(s).
# Wird der Haupt-AP nicht gefunden, schaltet netz.py automatisch aufs naechste.
WIFI_NETWORKS = [
    ("embedded", "c384c8c3"),
    ("in-plane-sight", "planespotter"),
]
WIFI_TIMEOUT_S   = 30          # Boot: max. Gesamt-Wartezeit auf WLAN (auf die Netze aufgeteilt)

MQTT_BROKER      = "test.mosquitto.org"
MQTT_PORT        = 1883
MQTT_CLIENT_ID   = b"in-plane-sight-pico"
MQTT_TOPIC       = b"in-plane-sight"
MQTT_KEEPALIVE_S = 60
MQTT_CHECK_MS    = 50          # Intervall fuer check_msg() (nicht-blockierend)
MQTT_PING_MS     = 30000       # Keepalive-Ping (< MQTT_KEEPALIVE_S*1000)
MQTT_RETRY_MS    = 5000        # Reconnect-Versuch-Intervall

# --- Datei -----------------------------------------------------------------
FRAMEBUFFER_FILE = "framebuffer.bin"
