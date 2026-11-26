"""De naam van een exportbestand: met datum en tijd, zodat elke download een eigen bestand is.

De tijd is die in Nederland, op de seconde; de vorm is gelijk aan `bestandsnaam` in `frontend/lib/artefactMarkdown.ts`.
Alleen ASCII: de naam gaat een header in, en een aanhalingsteken erin zou die breken.

`download` is het antwoord van elke export. De inhoud komt letterlijk terug – ook een begripsnaam met `<script>` –, dus
de browser mag hem nooit als pagina lezen: een bijlage met een eigen MIME-type, zonder sniffen, en met een CSP die elk
script en elke bron blokkeert, ook als iemand de url rechtstreeks opent (SonarQube S5131).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Response

from . import db

_ZONE = ZoneInfo("Europe/Amsterdam")


def met_tijd(stam: str, extensie: str, op: str | None = None) -> str:
    """`stam-20261107-143205.extensie`, op het ISO-tijdstip `op` of anders op dit moment."""
    moment = datetime.fromisoformat(op) if op else db.utcnow()
    return f"{stam}-{moment.astimezone(_ZONE):%Y%m%d-%H%M%S}.{extensie}"


#: De headers die een download inert maken; `download` zet ze, de test leest ze hier.
DOWNLOAD_HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox"}


def download(body: bytes | str, media_type: str, naam: str) -> Response:
    """Een exportbestand als bijlage met de naam `naam` (uit `met_tijd` of een eigen ASCII-naam)."""
    if media_type.split(";")[0].strip().lower() in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"een download is nooit HTML: {media_type}")
    return Response(body, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{naam}"', **DOWNLOAD_HEADERS})
