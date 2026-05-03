from __future__ import annotations

"""
FastAPI entrypoint for the Raspberry Pi control application.

Responsibilities:
- Serve a touch-friendly local frontend from /static
- Poll dump1090's aircraft.json regularly and keep a cached in-memory view
- Expose the cached view via a small REST API for the frontend
- Accept a "selected aircraft" from the UI and forward its position to the globe module
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import AircraftListResponse, AircraftMetadata, SelectRequest, SelectResponse
from .services.dump1090 import Dump1090Client
from .services.globe import forward_to_globe
from .services.planespotters import get_aircraft_metadata
from .services.system_position import get_system_position
from .state import Dump1090State
from .utils import get_env, get_env_float


STATIC_DIR = (Path(__file__).resolve().parent.parent / "static").resolve()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Configuration is driven by environment variables:
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
        """Serve the single-page frontend."""
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="frontend not found")
        return FileResponse(str(index_path))

    async def _poll_dump1090_loop() -> None:
        """
        Background task that polls dump1090 and updates the shared cache.

        On failures the previous aircraft list is kept and the error string is updated.
        """
        client = Dump1090Client(file_path=dump1090_file_path)
        state: Dump1090State = app.state.dump1090
        consecutive_failures = 0
        sleep_s = poll_interval_s
        while True:
            try:
                aircraft, polled_at = await client.fetch_aircraft()
                async with state.lock:
                    state.aircraft = aircraft
                    state.polled_at_unix_s = polled_at
                    state.error = None
                consecutive_failures = 0
                sleep_s = poll_interval_s
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
        """Start the dump1090 polling loop."""
        if app.state.poll_task is None:
            app.state.poll_task = asyncio.create_task(_poll_dump1090_loop())

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        """Stop the polling task cleanly."""
        task: asyncio.Task | None = app.state.poll_task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Simple liveness probe for the backend."""
        return {"status": "ok"}

    @app.get("/api/aircraft", response_model=AircraftListResponse)
    async def list_aircraft() -> AircraftListResponse:
        """
        Return the latest cached aircraft list.

        The frontend calls this endpoint periodically; the backend does not hit dump1090
        on-demand to keep the UI responsive even when dump1090 is slow or offline.
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
        Select an aircraft by ICAO hex and forward it to the globe integration.

        If the aircraft is missing from the latest cache, a 404 is returned.
        If the aircraft has no lat/lon yet, forwarding is rejected by the globe module.
        """
        state: Dump1090State = app.state.dump1090
        async with state.lock:
            selected = next((a for a in state.aircraft if a.hex.lower() == request.hex.lower()), None)

        if selected is None:
            raise HTTPException(status_code=404, detail="aircraft not found")

        forward_result = await forward_to_globe(selected)
        meta = await get_aircraft_metadata(selected.hex)
        return SelectResponse(ok=forward_result.sent, selected=selected, forward=forward_result, meta=meta)

    @app.get("/api/aircraft/{hex_code}/metadata", response_model=AircraftMetadata)
    async def aircraft_metadata(hex_code: str) -> AircraftMetadata:
        """Return cached/enriched image metadata for one aircraft hex code."""
        return await get_aircraft_metadata(hex_code)

    return app


app = create_app()
