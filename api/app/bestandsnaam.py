"""De naam van een exportbestand: met datum en tijd, zodat elke download een eigen bestand is.

De tijd is die in Nederland, op de seconde; de vorm is gelijk aan `bestandsnaam` in `frontend/lib/artefactMarkdown.ts`.
Alleen ASCII: de naam gaat een header in, en een aanhalingsteken erin zou die breken.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import db

_ZONE = ZoneInfo("Europe/Amsterdam")


def met_tijd(stam: str, extensie: str, op: str | None = None) -> str:
    """`stam-20261107-143205.extensie`, op het ISO-tijdstip `op` of anders op dit moment."""
    moment = datetime.fromisoformat(op) if op else db.utcnow()
    return f"{stam}-{moment.astimezone(_ZONE):%Y%m%d-%H%M%S}.{extensie}"
