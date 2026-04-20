# In Plane Sight

## Kurzbeschreibung

In diesem Projekt wollen wir ein ADS-B-basiertes Flugzeug-Tracking-System entwickeln, das nicht nur Positionsdaten empfängt und verarbeitet, sondern ein Flugzeug auch auf einem "Holo-Globe" anzeigt.

Die geplante Pipeline sieht so aus:

- Empfang von ADS-B-Signalen auf 1090 MHz
- Erfassung der Rohdaten über einen SDR-Empfänger
- Demodulation und Decoding der Datenpakete
- Decoding der ADS-B Frames und Bereitstellung der Live-Daten via `dump1090` (JSON-Endpoint)
- RasPi Backend pollt `dump1090` regelmäßig und normalisiert die wichtigsten Felder (Flight, Lat/Lon, Altitude, Speed)
- Touch-UI zeigt alle aktuell getrackten Flugzeuge an (kiosk-/touch-optimiert)
- Auswahl eines Flugzeugs auf dem Touchscreen (Tap) sendet die Selection an das Backend
- Backend leitet `lat/lon` (und Metadaten) über WLAN an den Holo-Globe-Controller weiter (modular: HTTP oder UDP)

Das Repository befindet sich aktuell noch in einer frühen Phase und dient zunächst dazu, die geplante Struktur, den technischen Ablauf und die nächsten Entwicklungsschritte festzuhalten.

## RasPi Control App (lokale Web-App)

Unter [backend/](backend/) liegt ein schlankes FastAPI-Backend, das:

- live Aircraft-Daten aus der lokalen Datei `/tmp/aircraft.json` (von `dump1090` geschrieben) liest
- die Daten als REST-API für das Touch-Frontend bereitstellt
- bei Auswahl eines Flugzeugs dessen `lat/lon` modular an den Holo Globe weiterleitet (HTTP oder UDP, per ENV konfigurierbar)
- bei Auswahl eines Flugzeugs Metadaten und ein Foto über die Planespotters API nachlädt (inkl. Cache & Placeholder)

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

Für einen einfachen Start inkl. Standard-Exports gibt es [start.sh](start.sh):

```bash
chmod +x start.sh
./start.sh
```

Overrides funktionieren inline:

```bash
DUMP1090_FILE_PATH=/tmp/aircraft.json GLOBE_UDP_HOST=10.42.0.1 GLOBE_UDP_PORT=5005 ./start.sh
```

Standardwerte in `start.sh`:

- `DUMP1090_FILE_PATH=/tmp/aircraft.json`
- `GLOBE_MODE=udp`
- `GLOBE_UDP_HOST=10.42.0.1`
- `GLOBE_UDP_PORT=5005`

### Tests

Tests laufen mit dem Python-Standardframework `unittest`:

```bash
python3 -m unittest discover -s backend/tests -p "test_*.py"
```

Hinweis: Einige Tests werden automatisch übersprungen, wenn Abhängigkeiten wie `fastapi/httpx/pydantic` in der aktuellen Umgebung nicht installiert sind.

### Aircraft-Metadaten (Planespotters)

Beim Tap auf ein Flugzeug ruft das Backend zusätzlich die Planespotters API anhand des `hex` Codes auf und liefert `type`, `airline`, `photographer` sowie eine Bild-URL zurück. Um Rate-Limits zu vermeiden, werden Ergebnisse pro `hex` im Backend gecacht; bei fehlendem Internet/keinen Fotos wird ein Placeholder-Bild genutzt.

Optionale Umgebungsvariablen:

- `PLANESPOTTERS_BASE_URL` (Default: `https://api.planespotters.net/pub/photos/hex`)
- `PLANESPOTTERS_TIMEOUT_S` (Default: `2.0`)

### Lokale Datenquelle (dump1090 File)

Das Backend verwendet als Quelle standardmäßig `/tmp/aircraft.json`.
Falls `dump1090` die Datei gerade schreibt oder sie noch nicht existiert, behandelt das Backend das robust und liefert vorübergehend eine leere Liste statt abzustürzen.

## 📁 Projektstruktur

Hier ist eine Übersicht über die wichtigsten Dateien und Ordner in diesem Projekt und deren Zweck:

- **`.github/workflows/ci.yml`**: Definition der GitHub Actions CI/CD-Pipeline, die bei jedem Push und Pull Request automatisch die Tests ausführt.
- **`backend/`**: Enthält den gesamten Backend- und Frontend-Code.
  - **`app/`**: Der FastAPI Python-Code.
    - **`main.py`**: Der Haupteinstiegspunkt der Anwendung. Definiert die REST-API-Endpunkte (`/api/aircraft`, `/api/select`) und startet den Hintergrund-Poller.
    - **`models.py`**: Pydantic-Datenmodelle (z.B. `Aircraft`, `AircraftMetadata`) für Validierung und Typensicherheit.
    - **`state.py`**: Speichert den globalen Zustand der Anwendung (In-Memory), wie z.B. Konfigurationen für das Auslesen der dump1090-Daten.
    - **`utils.py`**: Hilfsfunktionen, insbesondere für das sichere Auslesen von Umgebungsvariablen.
    - **`services/`**: Gekapselte Geschäftslogik und externe Schnittstellen.
      - **`dump1090.py`**: Logik zum Einlesen und Parsen der lokalen `aircraft.json`-Datei (oder History-Dateien) von dump1090.
      - **`globe.py`**: Behandelt die Kommunikation (UDP oder HTTP) mit dem Mikrocontroller des Holo Globes.
      - **`planespotters.py`**: Integration der Planespotters.net API zum Abrufen von Flugzeugbildern und Metadaten inkl. Caching-Logik.
  - **`static/`**: Statische Dateien für das Frontend (Kiosk-Touch-UI).
    - **`index.html`**: Das HTML-Grundgerüst der Benutzeroberfläche.
    - **`styles.css`**: Das Styling, optimiert für Touchscreens und dunkle Umgebungen (Dark Mode).
    - **`app.js`**: Die JavaScript-Logik des Frontends. Ruft Daten vom Backend ab und aktualisiert die UI.
    - **`aircraft-placeholder.svg`**: Ein Fallback-Bild (Platzhalter), falls für ein Flugzeug kein Foto über die Planespotters API gefunden wird.
  - **`tests/`**: Unit-Tests zur Überprüfung der Backend-Funktionalität.
    - **`json-beispiel-data/`**: Ordner mit beispielhaften `aircraft.json`- und `history.json`-Dateien, die für Tests und Simulationen verwendet werden.
  - **`requirements.txt`**: Liste aller benötigten Python-Abhängigkeiten (z.B. fastapi, uvicorn, httpx).
- **`architecture.mmd` / `architecture.md`**: Ein Mermaid.js-Diagramm, das die Systemarchitektur visuell darstellt.
- **`start.sh`**: Ein Shell-Skript, das den einfachen und schnellen Start der Anwendung mit den korrekten Umgebungsvariablen ermöglicht.
- **`README.md`**: Diese Dokumentation.
