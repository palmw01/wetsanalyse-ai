"""Welke agent welke taken kent, en hoe een taak zijn invoer krijgt.

De supervisor levert agent + taak (uit de `TAAK:`-regel, of zonder model uit een `actie`); de rest van de
invoer komt uit wat er al ligt: het werkgebied van het gesprek, het object waarop de analist *Vraag Lex*
koos (of dat de focus nog vasthoudt), en de getypte vraag – alleen voor wat code eruit kan lezen
("deelvraag 2", de term van een begrip). Nooit uit modeltekst.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from . import Context, Uitkomst, annotatie, begrippen, deelvragen

AGENTS = {"deelvragen": deelvragen, "begrippen": begrippen, "annotatie": annotatie}
#: Wat de werkplek en de statusregel zeggen.
NAAM = {"deelvragen": "deelvragen-agent", "begrippen": "begrippen-agent", "annotatie": "annotatie-agent"}

_DEELVRAAG_NR = re.compile(r"\bdeelvraag\s+(?:nummer\s+|nr\.?\s*)?(\d{1,2})\b", re.I)


def taken(agent: str) -> tuple[str, ...]:
    return tuple(t.value for t in AGENTS[agent].Taak)


def is_taak(agent: str, taak: str) -> bool:
    return agent in AGENTS and taak in taken(agent)


def model_taak(agent: str, taak: str) -> bool:
    """Kan deze taak een model aanroepen? (Voor de meting en de tests: de rest draait zonder.)"""
    return is_taak(agent, taak) and AGENTS[agent].Taak(taak) in AGENTS[agent].MODEL_TAKEN


def parameters(agent: str, taak: str, *, vraag: str = "", onderwerp: dict[str, Any] | None = None,
               werkgebied_id: str = "", actie: str = "", bevestigd: int | None = None) -> dict[str, Any]:
    """De invoer van een taak, behalve de taak zelf."""
    from ..kaart_beurt import termen_uit

    o = onderwerp or {}
    p: dict[str, Any] = {"werkgebied_id": werkgebied_id or o.get("werkgebied_id", "")}
    if agent == "deelvragen":
        if o.get("soort") == "deelvraag" and o.get("id"):
            p["deelvraag_id"] = o["id"]
        elif m := _DEELVRAAG_NR.search(vraag or ""):
            p["deelvraag_nr"] = int(m.group(1))
        if actie in ("deelvraag_herformuleren", "deelvraag_splitsen"):
            p["soort"] = "splits" if actie == "deelvraag_splitsen" else "herformuleer"
    elif agent == "begrippen":
        if o.get("soort") == "begrip" and o.get("id"):
            p["begrip_id"] = o["id"]
        if taak not in ("voorstellen", "meedenken"):
            p["termen"] = termen_uit(vraag, taak if taak in begrippen.KAARTACTIES else "brondefinitie")[:2]
        if taak == "meedenken" and bevestigd is not None:
            p["bevestigd"] = bevestigd
    return p


def invoer(agent: str, taak: str, parameters_: dict[str, Any]) -> BaseModel:
    """De getypte invoer; een onbekende agent of taak is een `ValueError`."""
    if not is_taak(agent, taak):
        raise ValueError(f"onbekende taak '{taak}' voor agent '{agent}'")
    return AGENTS[agent].Invoer.model_validate({"taak": taak, **parameters_})


async def voer_uit(agent: str, invoer_: BaseModel, ctx: Context) -> Uitkomst:
    return await AGENTS[agent].voer_uit(invoer_, ctx)
