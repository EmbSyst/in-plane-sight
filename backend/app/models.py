from __future__ import annotations

"""
Pydantic models for the backend API.

These models define:
- the normalized aircraft data shape used by the UI
- request/response payloads for selecting and forwarding aircraft
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    source: str = Field(..., description="Position source (e.g. env)")


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


class DisplayModeRequest(BaseModel):
    """Request payload for changing the globe display mode."""

    mode: int = Field(..., description="Display mode (0=off, 1=solid color, 3=rainbow)")
    color: list[int] | None = Field(default=None, description="RGB color array (e.g. [255, 255, 255])")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: int) -> int:
        if v not in (0, 1, 3):
            raise ValueError("mode must be one of [0, 1, 3]")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            if len(v) != 3:
                raise ValueError("color must be a 3-element array")
            for channel in v:
                if not (0 <= channel <= 255):
                    raise ValueError("color channels must be between 0 and 255")
        return v

class Point(BaseModel):
    id: str
    lat: float
    lon: float
    color: list[int]

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: list[int]) -> list[int]:
        if len(v) != 3:
            raise ValueError("color must be a 3-element array")
        for channel in v:
            if not (0 <= channel <= 255):
                raise ValueError("color channels must be between 0 and 255")
        return v

class SetPointsRequest(BaseModel):
    points: list[Point]


class ChangePwmRequest(BaseModel):
    """Request payload for motor PWM control (forwarded to the pico as 'change_PWM')."""

    mode: int = Field(..., description="Motor mode (0=off, 1=run at rpm)")
    rpm: int | None = Field(default=None, ge=0, description="Target RPM when mode=1")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("mode must be one of [0, 1]")
        return v
