from __future__ import annotations

"""main.py - FastAPI-Einstiegspunkt für die Raspberry Pi Control-App.

Aufgaben:
- Bereitstellung des touch-optimierten lokalen Frontends unter /static
- Regelmäßiges Auslesen von dump1090 (aircraft.json) in einen In-Memory-Cache
- Bereitstellung des Caches über eine kleine REST-API für das Frontend
- Entgegennahme eines "ausgewählten Flugzeugs" aus der UI und Weiterleitung der Position an den Globe
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import AircraftListResponse, AircraftMetadata, SelectRequest, SelectResponse, DisplayModeRequest, SetPointsRequest, ChangePwmRequest
from .services.dump1090 import Dump1090Client
from .services.globe import forward_to_globe, init_globe_transport, shutdown_globe_transport, publish_display_mode, publish_set_points, publish_change_pwm
from .services.planespotters import get_aircraft_metadata
from .services.system_position import get_system_position
from .state import Dump1090State
from .utils import get_env, get_env_float


STATIC_DIR = (Path(__file__).resolve().parent.parent / "static").resolve()


def _aircraft_signature(aircraft) -> tuple[float | None, float | None, float | None, float | None]:
    """Liefert die Felder, die für ein erneutes Senden an den Globe (Live-Update) relevant sind."""
    return (aircraft.lat, aircraft.lon, aircraft.altitude, aircraft.speed)


def _pick_selected_for_republish(state: Dump1090State, aircraft: list) -> tuple[object, tuple[float | None, float | None, float | None, float | None]] | None:
    """Gibt das ausgewählte Flugzeug zurück, wenn sich seine Position seit dem letzten Senden geändert hat."""
    if not state.selected_hex:
        return None
    selected = next((a for a in aircraft if a.hex.lower() == state.selected_hex), None)
    if selected is None:
        return None
    signature = _aircraft_signature(selected)
    if signature == state.last_forwarded_signature:
        return None
    return selected, signature


def create_app() -> FastAPI:
    """
    Erstellt und konfiguriert die FastAPI-Anwendung.

    Die Konfiguration erfolgt über Umgebungsvariablen:
    - DUMP1090_FILE_PATH
    - DUMP1090_POLL_INTERVAL_S
    """
    dump1090_file_path = get_env("DUMP1090_FILE_PATH", "/tmp/aircraft.json")
    poll_interval_s = get_env_float("DUMP1090_POLL_INTERVAL_S", 1.0)
    backoff_initial_s = get_env_float("DUMP1090_BACKOFF_INITIAL_S", poll_interval_s)
    backoff_max_s = get_env_float("DUMP1090_BACKOFF_MAX_S", 15.0)
    backoff_multiplier = get_env_float("DUMP1090_BACKOFF_MULTIPLIER", 2.0)

    app = FastAPI(title="In Plane Sight - RasPi Control App", version="0.1.0")

    logger = logging.getLogger("in-plane-sight.poller")

    app.state.dump1090 = Dump1090State(source_file_path=dump1090_file_path, poll_interval_s=poll_interval_s)
    app.state.poll_task = None

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        """Liefert das Single-Page Frontend aus."""
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="frontend not found")
        return FileResponse(str(index_path))

    async def _poll_dump1090_loop() -> None:
        """
        Hintergrund-Task, der dump1090 ausliest und den gemeinsamen Cache aktualisiert.

        Bei Fehlern wird die vorherige Flugzeugliste beibehalten und der Fehlertext aktualisiert.
        """
        client = Dump1090Client(file_path=dump1090_file_path)
        state: Dump1090State = app.state.dump1090
        consecutive_failures = 0
        sleep_s = poll_interval_s
        while True:
            try:
                aircraft, polled_at = await client.fetch_aircraft()
                republish_selected = None
                async with state.lock:
                    state.aircraft = aircraft
                    state.polled_at_unix_s = polled_at
                    state.error = None
                    republish_selected = _pick_selected_for_republish(state, aircraft)
                consecutive_failures = 0
                sleep_s = poll_interval_s
                if republish_selected is not None:
                    selected, signature = republish_selected
                    forward_result = await forward_to_globe(selected)
                    if forward_result.sent:
                        async with state.lock:
                            if state.selected_hex == selected.hex.lower():
                                current = next((a for a in state.aircraft if a.hex.lower() == state.selected_hex), None)
                                if current is not None and _aircraft_signature(current) == signature:
                                    state.last_forwarded_signature = signature
            except Exception as exc:
                consecutive_failures += 1
                logger.exception("dump1090 poll failed (consecutive=%s)", consecutive_failures)

                error_text = str(exc)
                async with state.lock:
                    if state.error != error_text:
                        state.error = error_text

                if consecutive_failures == 1:
                    sleep_s = max(backoff_initial_s, poll_interval_s)
                else:
                    sleep_s = min(backoff_max_s, max(backoff_initial_s, sleep_s * backoff_multiplier))

            await asyncio.sleep(sleep_s)

    @app.on_event("startup")
    async def _on_startup() -> None:
        """Startet die dump1090-Schleife und die dauerhaften Verbindungen (MQTT)."""


        try:
            init_globe_transport()
        except Exception:
            logger.exception("globe transport init failed; continuing without globe forwarding")
        if app.state.poll_task is None:
            app.state.poll_task = asyncio.create_task(_poll_dump1090_loop())

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """Beendet den Polling-Task und schließt Verbindungen sauber ab."""
        task: asyncio.Task | None = app.state.poll_task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        shutdown_globe_transport()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Einfacher Liveness-Probe-Endpunkt."""
        return {"status": "ok"}

    @app.get("/api/aircraft", response_model=AircraftListResponse)
    async def list_aircraft() -> AircraftListResponse:
        """
        Gibt die aktuell gecachte Flugzeugliste zurück.

        Das Frontend ruft diesen Endpunkt regelmäßig auf; das Backend blockiert nicht,
        um dump1090 synchron zu lesen. So bleibt die UI reaktionsschnell, auch wenn
        dump1090 langsam oder offline ist.
        """
        state: Dump1090State = app.state.dump1090
        system_position = get_system_position()
        async with state.lock:
            return AircraftListResponse(
                ok=state.error is None,
                source_file_path=state.source_file_path,
                polled_at_unix_s=state.polled_at_unix_s,
                error=state.error,
                aircraft=state.aircraft,
                system_position=system_position,
            )

    @app.post("/api/select", response_model=SelectResponse)
    async def select_aircraft(request: SelectRequest) -> SelectResponse:
        """
        Wählt ein Flugzeug über seine ICAO-Hex-Adresse aus und leitet es an den Globe weiter.

        Wenn das Flugzeug im aktuellen Cache fehlt, wird ein 404 zurückgegeben.
        Wenn das Flugzeug noch keine Lat/Lon-Daten hat, wird die Weiterleitung abgelehnt.
        """
        state: Dump1090State = app.state.dump1090
        async with state.lock:
            selected = next((a for a in state.aircraft if a.hex.lower() == request.hex.lower()), None)

        if selected is None:
            raise HTTPException(status_code=404, detail="aircraft not found")

        selected_hex = selected.hex.lower()
        async with state.lock:
            state.selected_hex = selected_hex
            state.last_forwarded_signature = None

        forward_result = await forward_to_globe(selected)
        if forward_result.sent:
            async with state.lock:
                if state.selected_hex == selected_hex:
                    state.last_forwarded_signature = _aircraft_signature(selected)
        meta = await get_aircraft_metadata(selected.hex)
        return SelectResponse(ok=forward_result.sent, selected=selected, forward=forward_result, meta=meta)

    @app.post("/api/unselect")
    async def unselect_aircraft() -> dict[str, bool]:
        """Entfernt die Auswahl des aktuell verfolgten Flugzeugs (stoppt Live-Updates)."""
        state: Dump1090State = app.state.dump1090
        async with state.lock:
            state.selected_hex = None
            state.last_forwarded_signature = None
        return {"ok": True}

    @app.post("/api/globe/mode")
    async def set_globe_mode(request: DisplayModeRequest) -> dict[str, bool]:
        """Ändert den Anzeigemodus des Globes."""
        result = await publish_display_mode(request.mode, request.color)
        if not result.sent:
            raise HTTPException(status_code=500, detail=result.detail or "failed to set mode")
        return {"ok": True}

    @app.post("/api/globe/points")
    async def set_globe_points(request: SetPointsRequest) -> dict[str, bool]:
        """Sendet eine Liste von Punkten (set_points), die auf dem Globe angezeigt werden sollen."""
        # Pydantic-Modelle in Dicts umwandeln, bevor sie an den Publisher gehen
        points_dicts = [p.model_dump() for p in request.points]
        result = await publish_set_points(points_dicts)
        if not result.sent:
            raise HTTPException(status_code=500, detail=result.detail or "failed to set points")
        return {"ok": True}

    @app.post("/api/globe/motor")
    async def set_globe_motor(request: ChangePwmRequest) -> dict[str, bool]:
        """Ändert die Motor-PWM (RPM) des Globes."""
        result = await publish_change_pwm(request.mode, request.rpm)
        if not result.sent:
            raise HTTPException(status_code=500, detail=result.detail or "failed to set motor")
        return {"ok": True}

    @app.get("/api/aircraft/{hex_code}/metadata", response_model=AircraftMetadata)
    async def aircraft_metadata(hex_code: str) -> AircraftMetadata:
        """Gibt gecachte oder neu abgerufene Metadaten (Bild, Typ, Airline) für einen Hex-Code zurück."""
        return await get_aircraft_metadata(hex_code)

    return app


app = create_app()
