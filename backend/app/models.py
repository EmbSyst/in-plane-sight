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


class AircraftListResponse(BaseModel):
    """Response payload for the UI poll endpoint."""

    ok: bool
    source_url: str
    polled_at_unix_s: float | None
    error: str | None
    aircraft: list[Aircraft]


class SelectRequest(BaseModel):
    """Request payload from the UI when a user selects an aircraft."""

    hex: str = Field(..., description="ICAO address (hex) of the aircraft to select")


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
