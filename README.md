# In Plane Sight

## Kurzbeschreibung

In diesem Projekt wollen wir ein ADS-B-basiertes Flugzeug-Tracking-System entwickeln, das nicht nur Positionsdaten empfängt und verarbeitet, sondern ein Flugzeug auch auf einem "Holo-Globe" anzeigt.

Die geplante Pipeline sieht so aus:

* Empfang von ADS-B-Signalen auf 1090 MHz
* Erfassung der Rohdaten über einen SDR-Empfänger
* Demodulation und Decoding der Datenpakete
* Decoding der ADS-B Frames und Bereitstellung der Live-Daten via `dump1090-fa` (lokales JSON-Snapshot-File)
* RasPi Backend liest `/tmp/aircraft.json` regelmäßig und normalisiert die wichtigsten Felder (Flight, Lat/Lon, Altitude, Speed)
* Touch-UI zeigt alle aktuell getrackten Flugzeuge an (kiosk-/touch-optimiert)
* Auswahl eines Flugzeugs auf dem Touchscreen (Tap) sendet die Selection an das Backend
* Backend publiziert die relevanten Holo-Globe-Daten per MQTT an einen öffentlichen Broker; der Pico empfängt diese Nachrichten als Subscriber

---

## RasPi Control App (lokale Web-App)

Unter `backend/` liegt ein schlankes FastAPI-Backend, das:

* live Aircraft-Daten aus der lokalen Datei `/tmp/aircraft.json` (von `dump1090-fa` geschrieben) liest
* die Daten als REST-API für das Touch-Frontend bereitstellt
* bei Auswahl eines Flugzeugs die relevanten Daten in MQTT-Nachrichten für den Holo Globe übersetzt und publiziert
* bei Auswahl eines Flugzeugs Metadaten und ein Foto über die Planespotters API nachlädt (inkl. Cache & Placeholder)

**Touch-UI (Kiosk):**

* Pollt `/api/aircraft` alle 1s und zeigt Altitude/Speed pro Flugzeug
* „Select on Globe“ öffnet eine Detailansicht mit Bild, Type, Airline und Position
* Die Position (`lat/lon`) in der Detailansicht aktualisiert sich ebenfalls mit jedem Poll (ohne erneuten Planespotters-Call)
* Wenn `SYSTEM_LAT`/`SYSTEM_LON` gesetzt sind, wird in der Detailansicht zusätzlich die Distanz zum ausgewählten Flugzeug in km angezeigt (im Frontend berechnet)
* Ein `×` Button schließt die Detailansicht (Unselect)

Architekturdiagramm (Mermaid): [architecture.md](architecture.md)

### Start (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
DUMP1090_FILE_PATH=/tmp/aircraft.json uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Danach im Browser öffnen: `http://<raspi-ip>:8000/`

### Start (mit Startskript)

Für einen einfachen Start inkl. Standard-Exports gibt es `start.sh`:

```bash
chmod +x start.sh
./start.sh
```

Overrides funktionieren inline:

```bash
DUMP1090_FILE_PATH=/tmp/aircraft.json ./start.sh

# Systemposition (für Distanzberechnung in der UI):
SYSTEM_LAT=49.121479 SYSTEM_LON=9.211960 ./start.sh
```

Standardwerte in `start.sh`:
* `DUMP1090_FILE_PATH=/tmp/aircraft.json`
* `SYSTEM_LAT` / `SYSTEM_LON` für die Distanzberechnung im Frontend

### MQTT-Übertragung zum Pico

Die Kommunikation vom Raspberry Pi zum Pico ist aktuell MQTT-basiert und verwendet einen öffentlichen Broker:

* **Broker:** `test.mosquitto.org`
* **Port:** `1883`
* **Topic:** `in-plane-sight`

Die in `messages/message-list.txt` dokumentierten Nachrichtentypen sind:

**1. Anzeige-Modus des Globe**

```json
{
  "type": "change_display_mode",
  "mode": 0,
  "color": [255, 255, 255]
}
```

* `mode = 0`: LEDs aus
* `mode = 1`: gesamten Globe mit `color` füllen
* `mode = 2`: Weltkarte (Framebuffer) anzeigen
* `mode = 3`: RGB-Regenbogenmodus

**2. Motorsteuerung per PWM**

```json
{
  "type": "change_PWM",
  "mode": 0,
  "rpm": []
}
```

* `mode = 0`: Motor aus
* `mode = 1`: PWM-Werte aus der gewünschten Drehzahl ableiten

**3. Flugzeugpositionen setzen (set_points)**

```json
{
  "type": "set_points",
  "points": [
    { "id": "DLH123", "lat": 48.35, "lon": 11.78, "color": [255, 255, 255] }
  ]
}
```

* Der Raspberry Pi extrahiert Längen- und Breitengrad sowie die Flugnummer aus den ADS-B Daten und sendet diese an den Pico. Der Pico kümmert sich um die Umrechnung auf den Framebuffer.

### Autostart (Boot-Konfiguration)

Um das System auf dem Raspberry Pi vollautomatisch beim Hochfahren zu starten, sind zwei Komponenten eingerichtet: ein Hintergrunddienst für das Backend und ein isolierter Kiosk-Start für das Frontend.

**1. Hintergrunddienste (Systemd)**

Ein zentrales Skript startet das FastAPI-Backend im Hintergrund, völlig unabhängig von der Bildschirmausgabe.
* **Startup-Skript:** `/usr/local/bin/startup.sh`
* **Systemd-Service:** `/etc/systemd/system/backend.service`

Steuern lässt sich der Dienst via Terminal:
* MQTT-Broker Status prüfen: `sudo systemctl status mosquitto`
* MQTT-Broker neu starten: `sudo systemctl restart mosquitto`
* Backend Status prüfen: `sudo systemctl status backend.service`
* Backend neu starten: `sudo systemctl restart backend.service`

> **Hinweis:** `dump1090-fa` liefert weiterhin separat die Datei `/tmp/aircraft.json`; das Startskript dieser Web-App startet `dump1090` nicht automatisch.

**2. Kiosk-Frontend (Sway Wayland Compositor)**

Um das System unter Ubuntu 24.04 ressourcenschonend und "ausbruchsicher" (keine Taskleiste, keine Wischgesten) zu betreiben – und gleichzeitig unser Hardware-Display korrekt zu drehen – verzichten wir auf einen kompletten Desktop. Stattdessen bootet der Raspberry Pi in die Textkonsole, loggt sich automatisch ein und startet den Browser isoliert über den Wayland-Fenstermanager **Sway**.

* **Autologin:** Konfiguriert über einen Getty-Override unter `/etc/systemd/system/getty@tty1.service.d/override.conf`
* **Sway-Konfiguration:** Liegt unter `~/.config/sway/config`. Hier wird das Bild gedreht, der Touchscreen kalibriert und der Browser (Chromium als Snap-Paket) mit Wayland-Flags gestartet:
  ```text
  # Bildschirm und Touch-Matrix um 180 Grad drehen
  output * transform 180
  input type:touch {
      calibration_matrix -1 0 1 0 -1 1
  }
  
  # Hintergrund (blau) und Kiosk-Optik (keine Ränder)
  output * bg #0000AA solid_color
  default_border none
  hide_edge_borders both
  
  # Start des Frontends
  exec bash -c "sleep 10 && /snap/bin/chromium --enable-features=UseOzonePlatform --ozone-platform=wayland --kiosk --noerrdialogs --disable-infobars http://localhost:8000"
  ```
* **Startbefehl:** Liegt in der Datei `~/.bash_profile` des Benutzers und ruft Sway direkt nach dem Login auf:
  ```bash
  if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
      exec sway
  fi
  ```

> **Hinweis:** Der `sleep 10` Befehl in der Sway-Konfiguration stellt sicher, dass der Backend-Dienst im Hintergrund vollständig hochgefahren und erreichbar ist, bevor der Browser die URL aufruft.

**Zurück zum normalen Desktop wechseln (Wartungsmodus):**
Falls für Anpassungen wieder die normale grafische Benutzeroberfläche (Desktop) benötigt wird, kann das System einfach per SSH oder Tastatur wieder umgestellt werden:
1. Standard-Bootmodus auf "Desktop" setzen:
   ```bash
   sudo systemctl set-default graphical.target
   ```
2. Raspberry Pi neu starten:
   ```bash
   sudo reboot
   ```
*(Um nach der Wartung wieder in den Kiosk-Modus zurückzukehren, lautet der Befehl: `sudo systemctl set-default multi-user.target`)*

### Tests

Tests laufen mit dem Python-Standardframework `unittest`:

```bash
python3 -m unittest discover -s backend/tests -p "test_*.py"
```

> **Hinweis:** Einige Tests werden automatisch übersprungen, wenn Abhängigkeiten wie `fastapi/httpx/pydantic` in der aktuellen Umgebung nicht installiert sind.

### Aircraft-Metadaten (Planespotters)

Beim Tap auf ein Flugzeug ruft das Backend zusätzlich die Planespotters API anhand des `hex` Codes auf und liefert eine Bild-URL sowie (best-effort) `type` und `airline` zurück. Um Rate-Limits zu vermeiden, werden Ergebnisse pro `hex` im Backend gecacht; bei fehlendem Internet/keinen Fotos wird ein Placeholder-Bild genutzt.

Optionale Umgebungsvariablen:
* `PLANESPOTTERS_BASE_URL` (Default: `https://api.planespotters.net/pub/photos/hex`)
* `PLANESPOTTERS_TIMEOUT_S` (Default: `2.0`)

### Lokale Datenquelle (dump1090 File)

Das Backend verwendet als Quelle standardmäßig `/tmp/aircraft.json`.
Falls `dump1090` die Datei gerade schreibt oder sie noch nicht existiert, behandelt das Backend das robust und liefert vorübergehend eine leere Liste statt abzustürzen.

---

## 📁 Projektstruktur

Hier ist eine Übersicht über die wichtigsten Dateien und Ordner in diesem Projekt und deren Zweck:

* **`.github/workflows/ci.yml`**: Definition der GitHub Actions CI/CD-Pipeline, die bei jedem Push und Pull Request automatisch die Tests ausführt.
* **`backend/`**: Enthält den gesamten Backend- und Frontend-Code.
* **`backend/app/main.py`**: Der Haupteinstiegspunkt der Anwendung. Definiert die REST-API-Endpunkte (`/api/aircraft`, `/api/select`, `/api/globe/mode`, `/api/globe/points`) und startet den Hintergrund-Poller.
* **`backend/app/models.py`**: Pydantic-Datenmodelle für Validierung und Typensicherheit (z.B. `Aircraft`, `SetPointsRequest`, `DisplayModeRequest`).
* **`backend/app/state.py`**: Speichert den globalen Zustand der Anwendung (In-Memory).
* **`backend/app/utils.py`**: Hilfsfunktionen, insbesondere für das sichere Auslesen von Umgebungsvariablen.
* **`backend/app/services/dump1090.py`**: Logik zum Einlesen und Parsen der lokalen `aircraft.json`-Datei.
* **`backend/app/services/globe.py`**: Behandelt die Weitergabe der Holo-Globe-Daten per MQTT (Display Modes und Set Points).
* **`backend/app/services/planespotters.py`**: Integration der Planespotters.net API zum Abrufen von Flugzeugbildern.
* **`backend/static/`**: Die Dateien der Benutzeroberfläche (`index.html`, `styles.css`, `app.js`). Beinhaltet jetzt zwei Tabs ("Aircrafts" und "Globe Control").
* **`backend/tests/test_*.py`**: Backend-Tests.
* **`backend/requirements.txt`**: Liste aller benötigten Python-Abhängigkeiten.
* **`architecture.md`**: Ein Mermaid.js-Diagramm, das die Systemarchitektur visuell darstellt.
* **`messages/`**: Spezifikationen für die Kommunikation mit dem Pico.
  * **`message-list.txt`**: Dokumentation der MQTT-Nachrichtentypen (`change_display_mode`, `change_PWM`, `set_points`).
* **`pico/`**: Enthält die Firmware und Render-Skripte für den Raspberry Pi Pico W.
  * **`main.py`**: MicroPython-Einstiegspunkt für den Pico. Verbindet WLAN und MQTT, verarbeitet die `set_points` Nachrichten.
  * **`render_worldmap.py`**: PC-seitiges Skript zum Rendern einer equirektangulären Karte in einen Binär-Framebuffer (`framebuffer.bin`) für den Pico.
  * **`display.py`, `motor.py`, `rpm.py`, `netz.py`**: Modulare Bestandteile der Firmware für Hardware-Steuerung und Netzwerk.
  * **`state.py`**, **`config.py`**: Geteilter Status und Hardware-Konfigurationen für die Pico-Firmware.
  * **`README.md`**: Detaillierte Spezifikation der POV-Globe Architektur und des Framebuffer-Konzepts.
* **`start.sh`**: Ein Shell-Skript, das den einfachen und schnellen Start der Anwendung mit den korrekten Umgebungsvariablen ermöglicht.
* **`presentation_outline.md`**: Leitfaden für eine Projektpräsentation (Frontend & Daten-Pipeline).
* **`README.md`**: Diese Dokumentation.
* **`SETUP.md`**: Setup-Guide für die Inbetriebnahme des Holo-Globes.
