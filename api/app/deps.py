"""Dependency-wiring: de gesprekkenstore. De annotatie-store (`annotatie_v2_store`) is een module
met functies en heeft geen wiring nodig."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gesprek_store import GesprekStore

logger = logging.getLogger(__name__)


@lru_cache
def get_gesprek_store() -> "GesprekStore":
    from .gesprek_store import GesprekStore

    return GesprekStore()
