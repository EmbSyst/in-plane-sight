# In Plane Sight

## Kurzbeschreibung

In diesem Projekt wollen wir ein ADS-B-basiertes Flugzeug-Tracking-System entwickeln, das nicht nur Positionsdaten empfängt und verarbeitet, sondern ein Flugzeug auch physisch über eine Pan/Tilt-Mechanik „anzeigt“.

Die geplante Pipeline sieht so aus:

- Empfang von ADS-B-Signalen auf 1090 MHz
- Erfassung der Rohdaten über einen SDR-Empfänger
- Demodulation und Decoding der Datenpakete
- Extraktion von Position und Höhe des Flugzeugs
- Berechnung von Azimut und Elevation relativ zur eigenen Basisstation
- Umwandlung dieser Werte in PWM-Steuersignale
- Ansteuerung von zwei Servos für Pan und Tilt
- Physischer Zeiger richtet sich auf das Flugzeug aus

Das Repository befindet sich aktuell noch in einer frühen Phase und dient zunächst dazu, die geplante Struktur, den technischen Ablauf und die nächsten Entwicklungsschritte festzuhalten.

## RasPi Control App (lokale Web-App)

Unter [backend/](file:///Users/noakaehling/Documents/Hochschule/Semester6/EmbeddedSystems/in-plane-sight/backend) liegt ein schlankes FastAPI-Backend, das:

- live Aircraft-Daten von `dump1090` pollt (`http://127.0.0.1:8080/data/aircraft.json`)
- die Daten als REST-API für das Touch-Frontend bereitstellt
- bei Auswahl eines Flugzeugs dessen `lat/lon` modular an den Holo Globe weiterleitet (HTTP oder UDP, per ENV konfigurierbar)

### Start (Development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Danach im Browser öffnen: `http://<raspi-ip>:8000/`

### Wichtige Umgebungsvariablen

- `DUMP1090_URL` (Default: `http://127.0.0.1:8080/data/aircraft.json`)
- `DUMP1090_POLL_INTERVAL_S` (Default: `1.0`)
- `GLOBE_MODE` (`disabled` | `http` | `udp`, Default: `disabled`)
- `GLOBE_HTTP_URL` (Default: `http://192.168.4.1/aircraft`)
- `GLOBE_UDP_HOST` (Default: `192.168.4.1`), `GLOBE_UDP_PORT` (Default: `4210`)
