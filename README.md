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

- live Aircraft-Daten von `dump1090` pollt (`http://127.0.0.1:8080/data/aircraft.json`)
- die Daten als REST-API für das Touch-Frontend bereitstellt
- bei Auswahl eines Flugzeugs dessen `lat/lon` modular an den Holo Globe weiterleitet (HTTP oder UDP, per ENV konfigurierbar)

Architekturdiagramm (Mermaid): [architecture.md](architecture.md)

### Start (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Danach im Browser öffnen: `http://<raspi-ip>:8000/`

### Start (mit Startskript)

Für einen einfachen Start inkl. Standard-Exports gibt es [start.sh](file:///Users/noakaehling/Documents/Hochschule/Semester6/EmbeddedSystems/in-plane-sight/start.sh):

```bash
chmod +x start.sh
./start.sh
```

Overrides funktionieren inline:

```bash
GLOBE_MODE=udp GLOBE_UDP_HOST=192.168.4.1 GLOBE_UDP_PORT=4210 ./start.sh
```

### Wo werden Umgebungsvariablen gesetzt?

Die Variablen müssen im Environment des Prozesses vorhanden sein, der `uvicorn` startet.

- Development: `export ...` im Shell oder via `VAR=... ./start.sh`
- RasPi Autostart: systemd Service mit `Environment=...` oder `EnvironmentFile=...`
- `.env` Datei: wird aktuell nicht automatisch geladen (nur wenn du sie bewusst sourcest oder später eine .env-Library ergänzt)


### Tests

Tests laufen mit dem Python-Standardframework `unittest`:

```bash
python3 -m unittest discover -s backend/tests -p "test_*.py"
```

Hinweis: Einige Tests werden automatisch übersprungen, wenn Abhängigkeiten wie `fastapi/httpx/pydantic` in der aktuellen Umgebung nicht installiert sind.
