from __future__ import annotations

"""
Pydantic models for the backend API.

These models define:
- the normalized aircraft data shape used by the UI
- request/response payloads for selecting and forwarding aircraft
"""

from typing import Any

from pydantic import BaseModel, Field


class Aircraft(BaseModel):
    """Normalized aircraft record extracted from dump1090."""

    hex: str = Field(..., description="ICAO address (hex)")
    flight: str | None = Field(default=None, description="Callsign / flight number")
    lat: float | None = Field(default=None, description="Latitude")
    lon: float | None = Field(default=None, description="Longitude")
    altitude: float | None = Field(default=None, description="Altitude (unit depends on dump1090 config; often feet)")
    speed: float | None = Field(default=None, description="Ground speed (often knots)")


class SystemPosition(BaseModel):
    """System's own position, used to compute distance to aircraft."""

    lat: float = Field(..., description="System latitude")
    lon: float = Field(..., description="System longitude")
    source: str = Field(..., description="Position source (e.g. env, gpsd)")


class AircraftListResponse(BaseModel):
    """Response payload for the UI poll endpoint."""

    ok: bool
    source_file_path: str
    polled_at_unix_s: float | None
    error: str | None
    aircraft: list[Aircraft]
    system_position: SystemPosition | None = None


class SelectRequest(BaseModel):
    """Request payload from the UI when a user selects an aircraft."""

    hex: str = Field(..., description="ICAO address (hex) of the aircraft to select")


class AircraftMetadata(BaseModel):
    """Metadata for an aircraft, enriched via external APIs (e.g. Planespotters)."""

    hex: str = Field(..., description="ICAO address (hex) this metadata refers to")
    type: str | None = Field(default=None, description="Aircraft model/type")
    airline: str | None = Field(default=None, description="Operating airline")
    photographer: str | None = Field(default=None, description="Photographer credit")
    image_url: str | None = Field(default=None, description="URL of aircraft image")
    from_cache: bool = Field(default=False, description="True if returned from in-memory cache")
    placeholder: bool = Field(default=False, description="True if using a generic placeholder image")


class GlobeForwardResult(BaseModel):
    """Result of forwarding the selected aircraft to the globe integration."""

    mode: str
    sent: bool
    detail: str | None = None
    response: Any | None = None


class SelectResponse(BaseModel):
    """Response payload for the selection endpoint."""

    ok: bool
    selected: Aircraft | None
    forward: GlobeForwardResult
    meta: AircraftMetadata | None = None
