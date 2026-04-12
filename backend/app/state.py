from __future__ import annotations

"""
Shared in-memory state for the dump1090 polling loop.

The backend polls dump1090 in a background task and keeps the latest aircraft list in
memory. Endpoints read from this state under an asyncio.Lock to avoid partial updates.
"""

import asyncio
from dataclasses import dataclass, field

from .models import Aircraft


@dataclass
class Dump1090State:
    """Holds the latest dump1090 poll results and error status."""

    source_url: str
    poll_interval_s: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    aircraft: list[Aircraft] = field(default_factory=list)
    polled_at_unix_s: float | None = None
    error: str | None = None
