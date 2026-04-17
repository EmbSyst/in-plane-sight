```mermaid
%% Application architecture (render with Mermaid / mermaid.js)
flowchart LR
  subgraph RasPi["Raspberry Pi 5 (Kiosk Touchscreen)"]
    Browser["Chromium (Kiosk Mode)"]
    UI["Touch UI (HTML/CSS/JS)\n/backend/static/*"]
    API["FastAPI Backend\n/backend/app/main.py"]
    Poller["Background Poller\npolls dump1090 every 1s"]
    Cache["In-memory Cache\nDump1090State"]
    DumpClient["Dump1090Client\nHTTP GET aircraft.json"]
    MetaSvc["Planespotters Metadata\n(in-memory cache by hex)"]
    GlobeSvc["Globe Forwarding Service\nHTTP or UDP (ENV)"]
  end

  subgraph SDR["SDR Receiver Stack"]
    Dump1090["dump1090\nhttp://127.0.0.1:8080/data/aircraft.json"]
  end

  subgraph Internet["Internet (optional)"]
    Planespotters["Planespotters API\n/photos/hex/{hex}"]
  end

  subgraph Globe["Holo Globe Microcontroller"]
    MCU["Microcontroller\n(HTTP endpoint or UDP listener)"]
  end

  Browser --> UI
  UI -->|"GET /api/aircraft (1s)"| API
  UI -->|"POST /api/select {hex}"| API

  API --> Poller
  Poller --> Cache
  Poller --> DumpClient
  DumpClient -->|"HTTP GET"| Dump1090

  API -->|"on selection\n(fetch meta + cache)"| MetaSvc
  MetaSvc -->|"HTTP GET (cached)"| Planespotters

  API -->|"on selection"| GlobeSvc
  GlobeSvc -->|"HTTP POST or UDP JSON\n{hex,flight,lat,lon,altitude,speed}"| MCU
```
