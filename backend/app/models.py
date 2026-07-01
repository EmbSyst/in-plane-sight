from __future__ import annotations

"""models.py - Pydantic-Datenmodelle für Typensicherheit und Validierung."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class Aircraft(BaseModel):
    """Repräsentiert ein einzelnes Flugzeug, das von dump1090 geparst wurde."""

    hex: str = Field(..., description="ICAO address (hex)")
    flight: str | None = Field(default=None, description="Callsign / flight number")
    lat: float | None = Field(default=None, description="Latitude")
    lon: float | None = Field(default=None, description="Longitude")
    altitude: float | None = Field(default=None, description="Altitude (unit depends on dump1090 config; often feet)")
    speed: float | None = Field(default=None, description="Ground speed (often knots)")


class SystemPosition(BaseModel):
    """Eigene Position des Systems, verwendet zur Berechnung der Distanz zu Flugzeugen."""

    lat: float = Field(..., description="System-Breitengrad")
    lon: float = Field(..., description="System-Längengrad")
    source: str = Field(..., description="Positionsquelle (z.B. env)")


class AircraftListResponse(BaseModel):
    """Antwort-Payload für den UI-Poll-Endpunkt."""

    ok: bool
    source_file_path: str
    polled_at_unix_s: float | None
    error: str | None
    aircraft: list[Aircraft]
    system_position: SystemPosition | None = None


class SelectRequest(BaseModel):
    """Anfrage-Payload von der UI, wenn ein Benutzer ein Flugzeug auswählt."""

    hex: str = Field(..., description="ICAO-Adresse (hex) des auszuwälenden Flugzeugs")


class AircraftMetadata(BaseModel):
    """Metadaten für ein Flugzeug, angereichert durch externe APIs."""

    hex: str = Field(..., description="ICAO-Adresse (hex), auf die sich diese Metadaten beziehen")
    type: str | None = Field(default=None, description="Flugzeugmodell/-typ")
    airline: str | None = Field(default=None, description="Betreibende Fluggesellschaft")
    photographer: str | None = Field(default=None, description="Fotografen-Credit")
    image_url: str | None = Field(default=None, description="URL des Flugzeugbildes")
    from_cache: bool = Field(default=False, description="Wahr, wenn aus dem In-Memory-Cache zurückgegeben")
    placeholder: bool = Field(default=False, description="Wahr, wenn ein generisches Platzhalterbild verwendet wird")


class GlobeForwardResult(BaseModel):
    """Ergebnis der Weiterleitung des ausgewählten Flugzeugs an die Globe-Integration."""

    mode: str
    sent: bool
    detail: str | None = None
    response: Any | None = None


class SelectResponse(BaseModel):
    """Antwort-Payload für den Auswahl-Endpunkt."""

    ok: bool
    selected: Aircraft | None
    forward: GlobeForwardResult
    meta: AircraftMetadata | None = None


class DisplayModeRequest(BaseModel):
    """Anfrage-Payload zum Ändern des Globe-Anzeigemodus."""

    mode: int = Field(..., description="Anzeigemodus (0=aus, 1=Volltonfarbe, 2=Weltkarte, 3=Regenbogen)")
    color: list[int] | None = Field(default=None, description="RGB-Farb-Array (z.B. [255, 255, 255])")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: int) -> int:
        if v not in (0, 1, 2, 3):
            raise ValueError("mode must be one of [0, 1, 2, 3]")
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
    """Anfrage-Payload zur Steuerung der Motor-PWM (weitergeleitet an den Pico als 'change_PWM')."""

    mode: int = Field(..., description="Motormodus (0=aus, 1=mit RPM laufen)")
    rpm: int | None = Field(default=None, ge=0, description="Ziel-RPM, wenn mode=1")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("mode must be one of [0, 1]")
        return v
