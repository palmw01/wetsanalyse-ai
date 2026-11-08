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

#: Waarom een connector uit staat en wie hem aanzet, in de woorden van de jurist (`{label}` wordt ingevuld).
WIE_ZET_AAN: dict[str, str] = {
    "straat": "{label} is op deze omgeving niet beschikbaar. Dat regelt de beheerder van de omgeving.",
    "register_onleesbaar": "Ik kon niet nagaan of {label} aanstaat, omdat de lijst met bronnen niet te lezen was. "
                           "Probeer het straks opnieuw.",
    "beheerder": "{label} staat uit: de beheerder heeft deze bron uitgezet.",
    "gesprek": "{label} staat uit in dit gesprek. Je kunt de bron aanzetten bij *Bronnen en tools* boven het "
               "invoerveld.",
    "werkgebied": "{label} staat uit in de standaard van dit werkgebied. Je kunt de bron aanzetten bij *Bronnen en "
                  "tools* boven het invoerveld.",
}

#: Achter de melding: wat Lex dan wél doet, en dat hij niets invult.
NIET_VERZINNEN = ("Uit mijn eigen kennis vul ik niet in wat daar staat. Over de wet- en regelgeving zelf kan ik je wel "
                  "helpen.")


def uit_zin(stand: dict[str, dict[str, Any]], naam: str) -> str:
    """De zin over één uitgezette connector; een onbekende stand telt als niet aangeboden door de straat."""
    s = stand.get(naam) or {"reden": "straat", "label": CONNECTORS[naam].label}
    return WIE_ZET_AAN[s["reden"]].format(label=s.get("label") or CONNECTORS[naam].label)


def melding_uit(stand: dict[str, dict[str, Any]], namen: list[str] | tuple[str, ...]) -> str:
    """De melding als een vraag alleen over uitgezette bronnen gaat: per bron waarom, en wat Lex dan doet."""
    return " ".join([*(uit_zin(stand, n) for n in namen), NIET_VERZINNEN])


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


def prompt_blok(stand: dict[str, dict[str, Any]], vraag: str = "") -> str:
    """BRONNEN IN DEZE BEURT, voor het variabele deel van de prompt (ná het cachepunt). Per connector uit de
    beschrijving: aan (wat hij dekt, waarvoor hij staat, zijn grenzen, de vorm van zijn id) of uit (waarom, en wie
    hem aanzet). Leeg als de straat niets aanbiedt en de vraag geen bron naast de wet noemt: dan is de prompt gelijk
    aan een straat zonder connectors."""
    from bronmodel.connectors import herkende

    genoemd = set(herkende(vraag))
    if not any(s["reden"] != "straat" for s in stand.values()) and not genoemd:
        return ""
    regels = ["BRONNEN IN DEZE BEURT – de wet- en regelgeving (de kennisgraaf) staat altijd aan."]
    for naam, s in stand.items():
        c = CONNECTORS[naam]
        if s["aan"]:
            regels.append(f"- {c.label}: aan. Dekt {c.dekt}. Rol: {c.rol_in_antwoord}. Grenzen: {c.grenzen}. Noem een "
                          f"stuk met zijn id ({' of '.join(p + '…' for p in c.id_prefixen)}).")
        elif s["reden"] != "straat" or naam in genoemd:
            regels.append(f"- {c.label}: uit. {uit_zin(stand, naam)} Zoek er niet in en vul niet uit eigen kennis "
                          "in wat erin staat.")
    return "\n\n" + "\n".join(regels)


def actief(stand: dict[str, dict[str, Any]]) -> list[str]:
    return [n for n, s in stand.items() if s["aan"]]


def als_tekst(stand: dict[str, dict[str, Any]]) -> str:
    """Voor de logregel `beurt_meting`: `kamerstukken:aan`, `kamerstukken:straat`; leeg zonder connectors."""
    return ",".join(f"{n}:{s['reden']}" for n, s in stand.items())


def event(stand: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Het `bronstand`-event aan het begin van de beurt: de werkplek toont er een hint mee, de meting leest het.
    Alleen als de straat minstens één connector aanbiedt (`agent.answer_stream`)."""
    return {"type": "bronstand", "bronnen": list(stand.values())}
