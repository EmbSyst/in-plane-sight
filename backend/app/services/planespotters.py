from __future__ import annotations

"""
Planespotters metadata integration.

The Planespotters API can enrich dump1090 aircraft with:
- a representative photo (thumbnail_large.src)
- aircraft type/model
- airline
- photographer credit

To avoid rate limiting, results are cached in-memory by ICAO hex. Negative results
(no photos / offline) are cached as placeholder metadata as well.
"""

import logging
from typing import Any

import httpx

from ..models import AircraftMetadata
from ..utils import get_env, get_env_float


logger = logging.getLogger("in-plane-sight.planespotters")

_CACHE: dict[str, AircraftMetadata] = {}
_CACHE_MAX_SIZE = 2048
_TYPE_MANUFACTURER_TOKENS = {
    "airbus",
    "boeing",
    "embraer",
    "bombardier",
    "atr",
    "cessna",
    "beechcraft",
    "gulfstream",
    "dassault",
    "pilatus",
    "tupolev",
    "ilyushin",
    "antonov",
    "sukhoi",
    "comac",
    "lockheed",
    "mcdonnell",
    "fokker",
}


def _copy_model(model: Any, update: dict[str, Any]) -> Any:
    """
    Return a shallow copy of a Pydantic model with updated fields.

    Supports both Pydantic v2 (`model_copy`) and v1 (`copy`) to avoid runtime errors
    on environments that still ship Pydantic v1.
    """
    model_copy = getattr(model, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=update)
    model_copy_v1 = getattr(model, "copy", None)
    if callable(model_copy_v1):
        return model_copy_v1(update=update)
    raise TypeError("Unsupported model type for copying")


def _placeholder(hex_code: str) -> AircraftMetadata:
    return AircraftMetadata(
        hex=hex_code,
        type=None,
        airline=None,
        photographer=None,
        image_url="/static/aircraft-placeholder.svg",
        from_cache=False,
        placeholder=True,
    )


def _normalize_hex(hex_code: str) -> str:
    return hex_code.strip().lower()


def _get_nested_str(obj: Any, path: list[str]) -> str | None:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if cur is None:
        return None
    if isinstance(cur, str):
        value = cur.strip()
        return value or None
    return None


def _format_slug_token(token: str) -> str:
    token = token.strip()
    if not token:
        return ""
    return "".join((ch.upper() if ch.isalpha() else ch) for ch in token)


def _parse_type_and_airline_from_link(link: str) -> tuple[str | None, str | None]:
    """
    Best-effort fallback for Planespotters responses that only contain a photo link.

    In practice, the /pub/photos/hex/{hex} endpoint often returns:
    - photographer
    - thumbnail URLs
    - a canonical photo link that embeds registration, airline slug and type slug
    """
    try:
        path = link.split("?", 1)[0]
        last = path.rstrip("/").split("/")[-1]
        tokens = [t for t in last.split("-") if t]
        if len(tokens) < 2:
            return None, None

        manufacturer_index: int | None = None
        for idx, t in enumerate(tokens):
            if t.lower() in _TYPE_MANUFACTURER_TOKENS:
                manufacturer_index = idx
                break
        if manufacturer_index is None:
            return None, None

        reg_len = 1
        if manufacturer_index >= 3 and len(tokens[0]) <= 3 and len(tokens[1]) <= 5:
            reg_len = 2

        airline_tokens = tokens[reg_len:manufacturer_index]
        airline = " ".join(w.capitalize() for w in airline_tokens).strip() or None

        manufacturer = tokens[manufacturer_index].capitalize()
        rest_tokens = tokens[manufacturer_index + 1 :]
        if rest_tokens:
            rest = "-".join(_format_slug_token(t) for t in rest_tokens if t).strip("-")
            aircraft_type = f"{manufacturer} {rest}".strip()
        else:
            aircraft_type = manufacturer

        return aircraft_type or None, airline
    except Exception:
        return None, None


def _parse_payload(hex_code: str, payload: Any) -> AircraftMetadata:
    photos = payload.get("photos") if isinstance(payload, dict) else None
    if not isinstance(photos, list) or len(photos) == 0:
        return _placeholder(hex_code)

    first = photos[0]
    if not isinstance(first, dict):
        return _placeholder(hex_code)

    photographer: str | None
    raw_photographer = first.get("photographer")
    if isinstance(raw_photographer, str):
        photographer = raw_photographer.strip() or None
    elif isinstance(raw_photographer, dict):
        photographer = _get_nested_str(raw_photographer, ["name"])
    else:
        photographer = None

    aircraft_type = _get_nested_str(first, ["aircraft", "type"]) or _get_nested_str(first, ["aircraft", "model"])
    airline = _get_nested_str(first, ["airline", "name"]) or _get_nested_str(first, ["airline", "iata"]) or _get_nested_str(first, ["airline", "icao"])
    image_url = _get_nested_str(first, ["thumbnail_large", "src"]) or _get_nested_str(first, ["thumbnail", "src"])
    link = _get_nested_str(first, ["link"])

    if (aircraft_type is None or airline is None) and link:
        type_from_link, airline_from_link = _parse_type_and_airline_from_link(link)
        aircraft_type = aircraft_type or type_from_link
        airline = airline or airline_from_link

    if not image_url:
        return _placeholder(hex_code)

    return AircraftMetadata(
        hex=hex_code,
        type=aircraft_type,
        airline=airline,
        photographer=photographer,
        image_url=image_url,
        from_cache=False,
        placeholder=False,
    )


async def get_aircraft_metadata(hex_code: str) -> AircraftMetadata:
    """
    Fetch aircraft metadata by ICAO hex via Planespotters (with caching).

    Environment variables:
    - PLANESPOTTERS_BASE_URL (default: https://api.planespotters.net/pub/photos/hex)
    - PLANESPOTTERS_TIMEOUT_S (default: 2.0)
    """
    normalized = _normalize_hex(hex_code)
    if not normalized:
        return _placeholder(hex_code)

    cached = _CACHE.get(normalized)
    if cached is not None:
        return _copy_model(cached, {"from_cache": True})

    base_url = get_env("PLANESPOTTERS_BASE_URL", "https://api.planespotters.net/pub/photos/hex").rstrip("/")
    timeout_s = get_env_float("PLANESPOTTERS_TIMEOUT_S", 2.0)
    url = f"{base_url}/{normalized}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
            response = await client.get(url)
            if response.status_code == 404:
                meta = _placeholder(normalized)
            else:
                response.raise_for_status()
                meta = _parse_payload(normalized, response.json())
    except Exception as exc:
        logger.warning("Planespotters lookup failed for %s: %s", normalized, exc)
        meta = _placeholder(normalized)

    if len(_CACHE) >= _CACHE_MAX_SIZE:
        _CACHE.clear()
    _CACHE[normalized] = _copy_model(meta, {"from_cache": False})
    return meta
