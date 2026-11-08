"""De bronstand van een beurt (ADR-013): per connector of hij aanstaat, en zo niet, waarom.

`State.bronnen` zegt alleen wélke connectors aanstaan; daar filtert de toollaag op. Voor een eerlijk antwoord is meer
nodig: staat Kamerstukken uit, dan moet Lex kunnen zeggen wie hem aanzet. De reden volgt een vaste rangorde:

- `straat`: deze omgeving biedt de connector niet aan (`CONNECTOR_<NAAM>` staat uit); niemand in de werkplek kan dat
  veranderen;
- `gesprek` of `werkgebied`: de beurt vraagt hem niet, omdat de jurist (of de standaard van het werkgebied) hem
  uitzette; de werkplek geeft de herkomst mee (`ChatRequest.bronnen_herkomst`);
- `register_onleesbaar`: het register van de beheerder kon niet worden gelezen, dus staat alles uit;
- `beheerder`: de beheerder zette hem uit in het register;
- `aan`.

Het register wordt alleen gelezen als er iets aan te zetten valt. Een connector die het gesprek uitzette en die ook de
beheerder uitzette, heet daarom `gesprek`: zet de jurist hem aan, dan zegt de volgende beurt `beheerder`.

Alles komt uit de beschrijving (`bronmodel.connectors`); er staat hier geen connector met naam.
"""
from __future__ import annotations

from typing import Any, Literal

from bronmodel.connectors import CONNECTORS

Reden = Literal["aan", "straat", "register_onleesbaar", "beheerder", "gesprek", "werkgebied"]
Herkomst = Literal["gesprek", "werkgebied", "standaard"]

#: Wie een uitgezette connector weer aanzet, in de woorden van de jurist.
WIE_ZET_AAN: dict[str, str] = {
    "straat": "Deze bron is op deze omgeving niet beschikbaar; dat regelt de beheerder van de omgeving.",
    "register_onleesbaar": "De lijst met bronnen kon niet worden gelezen. Probeer het straks opnieuw.",
    "beheerder": "De beheerder heeft deze bron uitgezet.",
    "gesprek": "Je kunt hem aanzetten bij *Bronnen en tools* boven het invoerveld.",
    "werkgebied": "Hij staat uit in de standaard van dit werkgebied. Je kunt hem aanzetten bij *Bronnen en tools* "
                  "boven het invoerveld.",
}


def bepaal(settings: Any, bronnen: list[str] | None, herkomst: str | None = None, *,
           register: set[str] | None = None, register_fout: bool = False) -> dict[str, dict[str, Any]]:
    """Per connector `{naam, label, aan, reden}`, in de volgorde van de beschrijvingen.

    `bronnen` is wat de beurt vraagt (None = alles wat de straat aanbiedt), `register` wat de beheerder aanzette
    (None = niet gelezen: dan beperkt het niet), `herkomst` waar de vraag van de beurt vandaan komt."""
    uit_door = "werkgebied" if herkomst == "werkgebied" else "gesprek"
    stand: dict[str, dict[str, Any]] = {}
    for naam, c in CONNECTORS.items():
        if not getattr(settings, f"connector_{naam}", False):
            reden: Reden = "straat"
        elif bronnen is not None and naam not in bronnen:
            reden = uit_door
        elif register_fout:
            reden = "register_onleesbaar"
        elif register is not None and naam not in register:
            reden = "beheerder"
        else:
            reden = "aan"
        stand[naam] = {"naam": naam, "label": c.label, "aan": reden == "aan", "reden": reden}
    return stand


def actief(stand: dict[str, dict[str, Any]]) -> list[str]:
    return [n for n, s in stand.items() if s["aan"]]


def als_tekst(stand: dict[str, dict[str, Any]]) -> str:
    """Voor de logregel `beurt_meting`: `kamerstukken:aan`, `kamerstukken:straat`; leeg zonder connectors."""
    return ",".join(f"{n}:{s['reden']}" for n, s in stand.items())


def event(stand: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Het `bronstand`-event aan het begin van de beurt: de werkplek toont er een hint mee, de meting leest het.
    Alleen als de straat minstens één connector aanbiedt (`agent.answer_stream`)."""
    return {"type": "bronstand", "bronnen": list(stand.values())}
