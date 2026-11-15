"""De controle per stuk (ADR-016 §A4): klopt wat het antwoord over een stuk zegt met de passages die het rapport eruit citeert?

De toetsen in `gelezen.py` kijken naar woorden: rust een duiding op een gelezen stuk, staan haar woorden in zijn passages.
Een omgedraaide bewering in de woorden van de passage zien ze niet (meting bundel 119, D01: bij HR:2023:181/184 stond de
bewijslast van lid 3 omgedraaid, met de woorden van de uitspraak; `tests/test_d01_samenvatting_per_stuk.py`). Daarvoor is
een lezer nodig: één modelaanroep per beurt, met per stuk de geciteerde passages en de zinnen van het antwoord die het
stuk duiden, en per zin één oordeel uit drie (`steunt`, `spreekt_tegen`, `niet_te_zien`). Alleen `spreekt_tegen` wordt een
bewering: dan volgt de correctieronde, zoals bij de andere toetsen. `niet_te_zien` zegt `zonder_steun` al waar het kan.

De grens: alleen na een rapport van een subagent (er zijn passages, `rapport_steun`), alleen in het antwoord van de
centrale agent (wat de jurist leest), en alleen voor zinnen die een stuk duiden (meer dan `MAX_EIGEN_WOORDEN` eigen
woorden). Begrensd in stukken, zinnen en passagetekst; een fout of een onbruikbaar antwoord van het model is geen
bewering (de andere toetsen blijven staan). De kosten: één verzoek met de passages en de zinnen, zonder historie of tools
(~2–3k invoertokens per stuk, en een kort antwoord).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from .gelezen import MAX_EIGEN_WOORDEN, _FUNCTIEWOORDEN, _WOORD, _context, _rijwoorden, per_stuk
from .llm_stap import Rol, vraag_tool

logger = logging.getLogger("graph_qa.stukcontrole")

#: Hoeveel stukken, zinnen per stuk en tekens passage per stuk de controle hoogstens meestuurt.
MAX_STUKKEN = 8
MAX_ZINNEN = 8
MAX_PASSAGE = 4000
#: De uitvoer: per zin één oordeel van een paar woorden.
MAX_TOKENS = 1200

OORDELEN = ("steunt", "spreekt_tegen", "niet_te_zien")

SYSTEEM = (
    "Je controleert een samenvatting van rechtspraak of andere stukken tegen de passages eruit. Per stuk krijg je de "
    "passages die geciteerd zijn en de zinnen die er iets over zeggen. Geef per zin één oordeel:\n"
    "- steunt: de passages zeggen dit, ook als het anders geformuleerd is;\n"
    "- spreekt_tegen: een passage zegt iets anders of het omgekeerde (een andere partij, een andere richting van de "
    "bewijslast, een andere uitkomst, ontkenning tegenover bevestiging);\n"
    "- niet_te_zien: de passages zeggen er niets over.\n"
    "Zegt een zin méér dan de passages (een punt, een aantal of een reden die ze niet noemen), dan is dat niet_te_zien, "
    "niet spreekt_tegen: spreekt_tegen is alleen een passage die het omgekeerde zegt van wat de zin zegt.\n"
    "Bij spreekt_tegen geef je in `deel` letterlijk het stuk van de zin dat niet klopt, en in `tegen` letterlijk het "
    "stukje passage dat er het tegendeel van zegt (elk een paar woorden tot een zin, exact overgenomen); bij de andere "
    "oordelen laat je beide leeg. Kun je ze niet aanwijzen, of zeggen ze hetzelfde, dan is het niet_te_zien. Een zin die een standpunt weergeeft dat het stuk noemt en zelf verwerpt, spreekt het niet tegen zolang "
    "ze die verwerping niet omdraait; een zin met meer punten beoordeel je op elk punt.\n"
    "Oordeel alleen op de passages, niet op wat je zelf over het recht weet. Bij twijfel: niet_te_zien.")

#: Hoeveel woorden het aangewezen stukje passage minstens telt: één woord ("niet") wijst niets aan.
MIN_TEGEN_WOORDEN = 3


def schema() -> dict[str, Any]:
    return {"name": "oordelen", "description": "Het oordeel per zin.", "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False, "required": ["oordelen"], "properties": {
                "oordelen": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["stuk", "zin", "deel", "tegen", "oordeel"],
                    "properties": {"stuk": {"type": "integer"}, "zin": {"type": "integer"},
                                   "deel": {"type": "string"}, "tegen": {"type": "string"},
                                   "oordeel": {"type": "string", "enum": list(OORDELEN)}}}}}}}


def _plat(tekst: str) -> str:
    """Tekst om letterlijk te vergelijken: kleine letters, één soort aanhalingstekens en streepjes, enkele spaties."""
    tekst = tekst.casefold().translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return " ".join(tekst.split()).strip(" .,;:'\"")


def aangewezen(fragment: str, passages: str) -> bool:
    """Staat het stukje dat het model als tegenspraak aanwijst letterlijk in de passages van het stuk (A6 run 1, S01: bij
    PHR:2025:435 en HR:2020:1502 een tegenspraak die geen passage droeg)? Zonder zo'n stukje is het oordeel geen
    bewering."""
    frag = _plat(fragment)
    return len(frag.split()) >= MIN_TEGEN_WOORDEN and frag in _plat(passages)


def te_controleren(tekst: str, steun: dict[str, str], trace: Iterable[Any]) -> list[dict[str, Any]]:
    """Per stuk met passages de zinnen die het duiden, in volgorde, begrensd: `[{id, passages, zinnen}]`."""
    items = [(str(x[0]), str(x[1])) for x in trace]
    per: dict[str, list[str]] = {}
    for segment, ids in per_stuk(tekst, *_context(items)):
        ids = [i for i in ids if (steun.get(i) or "").strip()]
        if not ids:
            continue
        bekend = set().union(*(_rijwoorden(items, i) for i in ids))
        eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
        if len(eigen) <= MAX_EIGEN_WOORDEN:
            continue
        for i in ids:
            zinnen = per.setdefault(i, [])
            if segment.strip() not in zinnen and len(zinnen) < MAX_ZINNEN:
                zinnen.append(segment.strip())
    return [{"id": i, "passages": steun[i][:MAX_PASSAGE], "zinnen": z} for i, z in list(per.items())[:MAX_STUKKEN]]


def prompt(stukken: list[dict[str, Any]]) -> str:
    delen = []
    for s, stuk in enumerate(stukken, 1):
        zinnen = "\n".join(f"  zin {z}: {zin}" for z, zin in enumerate(stuk["zinnen"], 1))
        delen.append(f"STUK {s} ({stuk['id']})\nPassages:\n{stuk['passages']}\nZinnen:\n{zinnen}")
    return "\n\n".join(delen) + "\n\nGeef met de tool oordelen per stuk en zin één oordeel."


def controleer(llm: Any, settings: Any, tekst: str, steun: dict[str, str] | None, trace: Iterable[Any],
               meting: dict[str, Any] | None = None) -> list[str]:
    """De beweringen van de controle per stuk: elke zin die de passages van zijn stuk tegenspreekt. Leeg zonder steun,
    zonder zinnen om te toetsen, of als het model geen bruikbaar oordeel gaf."""
    if not steun or llm is None:
        return []
    stukken = te_controleren(tekst, steun, trace)
    if not stukken:
        return []
    verzoek = dict(model=settings.model_voor("controle"), max_tokens=MAX_TOKENS, system=SYSTEEM, tools=[schema()],
                   tool_choice={"type": "tool", "name": "oordelen"},
                   messages=[{"role": "user", "content": prompt(stukken)}])
    try:
        uit = vraag_tool(llm, Rol.STUKCONTROLE, verzoek=verzoek, pogingen=1, meting=meting,
                         haal=lambda invoer: invoer.get("oordelen") if isinstance(invoer.get("oordelen"), list) else None)
    except Exception:  # noqa: BLE001 – een controle die faalt, is geen bewering; de andere toetsen blijven staan
        logger.warning("stukcontrole mislukt", exc_info=True, extra={"categorie": "technisch"})
        return []
    beweringen: dict[str, None] = {}
    niet_aangewezen = 0
    for o in uit.waarde or []:
        try:
            stuk, zin = stukken[int(o["stuk"]) - 1], int(o["zin"]) - 1
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if o.get("oordeel") != "spreekt_tegen" or not 0 <= zin < len(stuk["zinnen"]):
            continue
        # Beide kanten letterlijk aangewezen: het zinsdeel in de zin en het stukje in de passages (A6 run 2, F01: bij
        # PHR:2025:435 een stukje van de slotsom dat hetzelfde zei als de zin, die alleen meer zei).
        if not (aangewezen(str(o.get("tegen") or ""), stuk["passages"])
                and aangewezen(str(o.get("deel") or ""), stuk["zinnen"][zin])):
            niet_aangewezen += 1
            continue
        kort = " ".join(stuk["zinnen"][zin].split())[:100]
        tegen = " ".join(str(o["tegen"]).split())[:120]
        beweringen[f"duiding van {stuk['id']} die de passages van dat stuk tegenspreekt: '{kort}' (de passage: "
                   f"'{tegen}')"] = None
    logger.info("stukcontrole", extra={"categorie": "functioneel", "stukken": len(stukken),
                                       "zinnen": sum(len(s["zinnen"]) for s in stukken),
                                       "tegengesproken": len(beweringen), "niet_aangewezen": niet_aangewezen})
    return list(beweringen)

