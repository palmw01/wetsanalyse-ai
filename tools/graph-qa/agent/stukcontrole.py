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

Een tegenspraak telt pas na drie toetsen (A6 run 2 en 3: van de inhoudelijke meldingen was het merendeel vals): beide
kanten letterlijk aangewezen (`aangewezen`), beide met inhoud en niet alleen een verwijzing (`heeft_inhoud`), en een
tweede, strengere lezing van alleen die gevallen met de tekst rond de passage (`bevestig`: hetzelfde onderwerp én het
omgekeerde; bij twijfel niet). Die tweede aanroep komt er alleen als er een kandidaat is.
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
    kandidaten: list[dict[str, Any]] = []
    niet_aangewezen = zonder_inhoud = 0
    for o in uit.waarde or []:
        try:
            stuk, zin = stukken[int(o["stuk"]) - 1], int(o["zin"]) - 1
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if o.get("oordeel") != "spreekt_tegen" or not 0 <= zin < len(stuk["zinnen"]):
            continue
        tegen, deel = str(o.get("tegen") or ""), str(o.get("deel") or "")
        # Beide kanten letterlijk aangewezen: het zinsdeel in de zin en het stukje in de passages (A6 run 2, F01: bij
        # PHR:2025:435 een stukje van de slotsom dat hetzelfde zei als de zin, die alleen meer zei).
        if not (aangewezen(tegen, stuk["passages"]) and aangewezen(deel, stuk["zinnen"][zin])):
            niet_aangewezen += 1
            continue
        # Een verwijzing zegt niets wat iets tegenspreekt (A6 run 3, HR:2023:1371: "artikel 36, lid 4, tweede volzin, IW
        # 1990" als tegenspraak).
        if not (heeft_inhoud(tegen) and heeft_inhoud(deel)):
            zonder_inhoud += 1
            continue
        kandidaten.append({"stuk": stuk, "zin": stuk["zinnen"][zin], "deel": deel, "tegen": tegen})
    bevestigd = bevestig(llm, settings, kandidaten, meting) if kandidaten else []
    beweringen: dict[str, None] = {}
    for k in bevestigd:
        kort = " ".join(k["zin"].split())[:100]
        tegen = " ".join(k["tegen"].split())[:120]
        beweringen[f"duiding van {k['stuk']['id']} die de passages van dat stuk tegenspreekt: '{kort}' (de passage: "
                   f"'{tegen}')"] = None
    logger.info("stukcontrole", extra={"categorie": "functioneel", "stukken": len(stukken),
                                       "zinnen": sum(len(s["zinnen"]) for s in stukken),
                                       "tegengesproken": len(beweringen), "niet_aangewezen": niet_aangewezen,
                                       "zonder_inhoud": zonder_inhoud,
                                       "niet_bevestigd": len(kandidaten) - len(bevestigd)})
    return list(beweringen)


#: Woorden die een verwijzing maken, geen bewering: "artikel 36, lid 4, tweede volzin, IW 1990".
_VERWIJZING = frozenset({
    "artikel", "artikelen", "art", "lid", "leden", "volzin", "volzinnen", "onderdeel", "onderdelen", "aanhef", "sub",
    "eerste", "tweede", "derde", "vierde", "vijfde", "zesde", "zevende", "achtste", "negende", "tiende", "wet", "boek",
    "hoofdstuk", "afdeling", "paragraaf", "titel", "bepaling", "bepalingen", "r.o", "rov", "overweging"})
#: Hoeveel woorden met inhoud een aangewezen stuk minstens draagt, buiten verwijzingen en functiewoorden.
MIN_INHOUD = 2


def heeft_inhoud(fragment: str) -> bool:
    """Draagt het fragment een bewering, of is het alleen een verwijzing of een paar functiewoorden?"""
    woorden = [w for w in _WOORD.findall(fragment.casefold())
               if w not in _VERWIJZING and w not in _FUNCTIEWOORDEN]
    return len(woorden) >= MIN_INHOUD


#: Hoeveel tekst rond het aangewezen stukje de tweede lezing ziet: genoeg om het onderdeel te zien (welk beroep, welke
#: partij, welk jaar).
OMGEVING = 600

BEVESTIG_SYSTEEM = (
    "Je krijgt mogelijke tegenspraken tussen een zin uit een samenvatting en een passage uit het stuk dat ze samenvat, "
    "elk met de tekst rond de passage. Beoordeel per geval twee dingen, streng:\n"
    "- zelfde_onderwerp: gaan het zinsdeel en de passage over hetzelfde (dezelfde partij, hetzelfde beroep of "
    "middel, hetzelfde jaar, dezelfde bepaling)? Gaat de passage over een ander onderdeel van het stuk (het principale "
    "beroep tegenover het incidentele, een ander standpunt dan dat van de rechter), dan false.\n"
    "- omgekeerd: als de passage waar is, kan het zinsdeel dan niet waar zijn? Zegt de passage hetzelfde, iets ruimers "
    "of iets anders dat ermee samengaat, dan false.\n"
    "Bij twijfel is het antwoord false. Oordeel alleen op de tekst die je krijgt.")


def bevestig_schema() -> dict[str, Any]:
    return {"name": "bevestiging", "description": "Per geval of het een echte tegenspraak is.", "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False, "required": ["gevallen"], "properties": {
                "gevallen": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["geval", "zelfde_onderwerp", "omgekeerd"],
                    "properties": {"geval": {"type": "integer"}, "zelfde_onderwerp": {"type": "boolean"},
                                   "omgekeerd": {"type": "boolean"}}}}}}}


def omgeving(tegen: str, passages: str) -> str:
    """De tekst rond het aangewezen stukje in de passages, op woordgrenzen."""
    plat = " ".join(passages.split())
    plek = plat.casefold().find(" ".join(tegen.split()).casefold()[:40])
    if plek < 0:
        return plat[:2 * OMGEVING]
    begin, eind = max(0, plek - OMGEVING), min(len(plat), plek + len(tegen) + OMGEVING)
    return ("…" if begin else "") + plat[begin:eind] + ("…" if eind < len(plat) else "")


def bevestig_prompt(kandidaten: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"GEVAL {n} ({k['stuk']['id']})\nZin: {k['zin']}\nZinsdeel: {k['deel']}\nPassage: {k['tegen']}\n"
        f"Tekst rond de passage: {omgeving(k['tegen'], k['stuk']['passages'])}"
        for n, k in enumerate(kandidaten, 1)) + "\n\nGeef met de tool bevestiging per geval je oordeel."


def bevestig(llm: Any, settings: Any, kandidaten: list[dict[str, Any]], meting: dict[str, Any] | None = None
             ) -> list[dict[str, Any]]:
    """De tweede lezing: alleen de kandidaten die over hetzelfde gaan én het omgekeerde zeggen (A6 run 3: drie van de
    vier meldingen vals, bij HR:2026:586 het verkeerde beroep en bij kst-26728-3 een passage die Lex bevestigde). Een
    fout of een onbruikbaar antwoord bevestigt niets: liever geen melding dan een valse."""
    verzoek = dict(model=settings.model_voor("controle"), max_tokens=MAX_TOKENS, system=BEVESTIG_SYSTEEM,
                   tools=[bevestig_schema()], tool_choice={"type": "tool", "name": "bevestiging"},
                   messages=[{"role": "user", "content": bevestig_prompt(kandidaten)}])
    try:
        uit = vraag_tool(llm, Rol.STUKCONTROLE, verzoek=verzoek, pogingen=1, meting=meting,
                         haal=lambda invoer: invoer.get("gevallen") if isinstance(invoer.get("gevallen"), list) else None)
    except Exception:  # noqa: BLE001 – een tweede lezing die faalt, bevestigt niets
        logger.warning("stukcontrole: tweede lezing mislukt", exc_info=True, extra={"categorie": "technisch"})
        return []
    ja = set()
    for g in uit.waarde or []:
        try:
            if g.get("zelfde_onderwerp") is True and g.get("omgekeerd") is True:
                ja.add(int(g["geval"]) - 1)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return [k for n, k in enumerate(kandidaten) if n in ja]

