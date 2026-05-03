# In Plane Sight

## Kurzbeschreibung

In diesem Projekt wollen wir ein ADS-B-basiertes Flugzeug-Tracking-System entwickeln, das nicht nur Positionsdaten empfängt und verarbeitet, sondern ein Flugzeug auch auf einem "Holo-Globe" anzeigt.

Die geplante Pipeline sieht so aus:

* Empfang von ADS-B-Signalen auf 1090 MHz
* Erfassung der Rohdaten über einen SDR-Empfänger
* Demodulation und Decoding der Datenpakete
* Decoding der ADS-B Frames und Bereitstellung der Live-Daten via `dump1090-fa` (lokales JSON-Snapshot-File)
* RasPi Backend liest `/tmp/aircraft.json` regelmäßig (z.B. alle 1s) und normalisiert die wichtigsten Felder (Flight, Lat/Lon, Altitude, Speed)
* Touch-UI zeigt alle aktuell getrackten Flugzeuge an (kiosk-/touch-optimiert)
* Auswahl eines Flugzeugs auf dem Touchscreen (Tap) sendet die Selection an das Backend
* Backend leitet `lat/lon` (und Metadaten) über WLAN an den Holo-Globe-Controller weiter (modular: HTTP oder UDP)

Das Repository befindet sich aktuell noch in einer frühen Phase und dient zunächst dazu, die geplante Struktur, den technischen Ablauf und die nächsten Entwicklungsschritte festzuhalten.

---

## RasPi Control App (lokale Web-App)

Unter `backend/` liegt ein schlankes FastAPI-Backend, das:

* live Aircraft-Daten aus der lokalen Datei `/tmp/aircraft.json` (von `dump1090-fa` geschrieben) liest
* die Daten als REST-API für das Touch-Frontend bereitstellt
* bei Auswahl eines Flugzeugs dessen `lat/lon` modular an den Holo Globe weiterleitet (HTTP oder UDP, per ENV konfigurierbar)
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
DUMP1090_FILE_PATH=/tmp/aircraft.json GLOBE_UDP_HOST=10.42.0.1 GLOBE_UDP_PORT=5005 ./start.sh

# Systemposition (für Distanzberechnung in der UI):
SYSTEM_LAT=49.121479 SYSTEM_LON=9.211960 ./start.sh
```

Standardwerte in `start.sh`:
* `DUMP1090_FILE_PATH=/tmp/aircraft.json`
* `GLOBE_MODE=udp`
* `GLOBE_UDP_HOST=10.42.0.1`
* `GLOBE_UDP_PORT=5005`

### Autostart (Boot-Konfiguration)

Um das System auf dem Raspberry Pi (Ubuntu 24.04) vollautomatisch beim Hochfahren zu starten, sind zwei Komponenten eingerichtet: ein Hintergrunddienst für das Backend und ein Desktop-Autostart für das Kiosk-Frontend.

**1. Hintergrunddienste (Systemd)**
Ein zentrales Skript startet `dump1090` und das FastAPI-Backend im Hintergrund. 
* **Startup-Skript:** `/usr/local/bin/startup.sh`
* **Systemd-Service:** `/etc/systemd/system/backend.service`

Steuern lässt sich der Dienst via Terminal:
* Status prüfen: `sudo systemctl status backend.service`
* Neu starten: `sudo systemctl restart backend.service`

**2. Kiosk-Frontend (Desktop Autostart)**
Sobald die grafische Oberfläche geladen ist, wird der Chromium-Browser automatisch im Vollbildmodus gestartet.
* **Autostart-Datei:** `/home/pi/.config/autostart/kiosk.desktop`

> **Hinweis:** Der Kiosk-Autostart wartet initial einige Sekunden, um sicherzustellen, dass das Backend unter `localhost:8000` vollständig erreichbar ist, bevor die Seite aufgerufen wird.

### Tests

Tests laufen mit dem Python-Standardframework `unittest`:

```bash
python3 -m unittest discover -s backend/tests -p "test_*.py"
```

> **Hinweis:** Einige Tests werden automatisch übersprungen, wenn Abhängigkeiten wie `fastapi/httpx/pydantic` in der aktuellen Umgebung nicht installiert sind.

### Aircraft-Metadaten (Planespotters)

Beim Tap auf ein Flugzeug ruft das Backend zusätzlich die Planespotters API anhand des `hex` Codes auf und liefert eine Bild-URL sowie (best-effort) `type` und `airline` zurück. Um Rate-Limits zu vermeiden, werden Ergebnisse pro `hex` im Backend gecacht; bei fehlendem Internet/keinen Fotos wird ein Placeholder-Bild genutzt.

Optionale Umgebungsvariablen:
* `PLANESPOTTERS_BASE_URL` (Default: `[https://api.planespotters.net/pub/photos/hex](https://api.planespotters.net/pub/photos/hex)`)
* `PLANESPOTTERS_TIMEOUT_S` (Default: `2.0`)

### Lokale Datenquelle (dump1090 File)

Das Backend verwendet als Quelle standardmäßig `/tmp/aircraft.json`.
Falls `dump1090` die Datei gerade schreibt oder sie noch nicht existiert, behandelt das Backend das robust und liefert vorübergehend eine leere Liste statt abzustürzen.

---

## 📁 Projektstruktur

Hier ist eine Übersicht über die wichtigsten Dateien und Ordner in diesem Projekt und deren Zweck:

* **`.github/workflows/ci.yml`**: Definition der GitHub Actions CI/CD-Pipeline, die bei jedem Push und Pull Request automatisch die Tests ausführt.
* **`backend/`**: Enthält den gesamten Backend- und Frontend-Code.
* **`backend/app/main.py`**: Der Haupteinstiegspunkt der Anwendung. Definiert die REST-API-Endpunkte (`/api/aircraft`, `/api/select`) und startet den Hintergrund-Poller.
* **`backend/app/models.py`**: Pydantic-Datenmodelle (z.B. `Aircraft`, `AircraftMetadata`) für Validierung und Typensicherheit.
* **`backend/app/state.py`**: Speichert den globalen Zustand der Anwendung (In-Memory), wie z.B. Konfigurationen für das Auslesen der dump1090-Daten.
* **`backend/app/utils.py`**: Hilfsfunktionen, insbesondere für das sichere Auslesen von Umgebungsvariablen.
* **`backend/app/services/dump1090.py`**: Logik zum Einlesen und Parsen der lokalen `aircraft.json`-Datei von dump1090.
* **`backend/app/services/globe.py`**: Behandelt die Kommunikation (UDP oder HTTP) mit dem Mikrocontroller des Holo Globes.
* **`backend/app/services/planespotters.py`**: Integration der Planespotters.net API zum Abrufen von Flugzeugbildern und Metadaten inkl. Caching-Logik.
* **`backend/static/index.html`**: Das HTML-Grundgerüst der Benutzeroberfläche.
* **`backend/static/styles.css`**: Das Styling, optimiert für Touchscreens und dunkle Umgebungen (Dark Mode).
* **`backend/static/app.js`**: Die JavaScript-Logik des Frontends. Ruft Daten vom Backend ab und aktualisiert die UI.
* **`backend/static/aircraft-placeholder.svg`**: Ein Fallback-Bild (Platzhalter), falls für ein Flugzeug kein Foto über die Planespotters API gefunden wird.
* **`backend/tests/test_*.py`**: Backend-Tests (API-Endpunkte, ENV-Parsing, Globe-Forwarding, Planespotters-Parsing/Cache).
* **`backend/requirements.txt`**: Liste aller benötigten Python-Abhängigkeiten (z.B. fastapi, uvicorn, httpx).
* **`architecture.md`**: Ein Mermaid.js-Diagramm, das die Systemarchitektur visuell darstellt.
* **`start.sh`**: Ein Shell-Skript, das den einfachen und schnellen Start der Anwendung mit den korrekten Umgebungsvariablen ermöglicht.
* **`README.md`**: Diese Dokumentation.