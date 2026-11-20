"""De statusregels die de werkplek live toont: één idioom `Actor · wat er gebeurde`.

Pure functies, bewust los van de nodes die ze aanroepen — zo zijn ze zonder graaf te testen, en
kunnen meerdere node-modules ze delen zonder elkaar te importeren.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

#: In de testsuite (`tests/conftest.py`) is een regel met een lege plek een fout; in de dienst haalt `_stap` de lege plek
#: weg en logt hij het, want een denkproces is geen reden om een beurt te laten vallen.
STRIKT = False

#: Wat een regel met een gat verraadt: lege haakjes ("(art. )", "( )"), een leeg veld ("None", "{zoekterm}"), een
#: dubbele spatie, een leesteken met niets ervoor of erachter (" , ", ": ;"), een regel die op een scheiding eindigt.
#: E2E Rekeningafspraken 16 nov 2026, D-1: twaalf keer "Lex · annoteert de aangewezen bepaling (art. )".
_LEGE_PLEK = re.compile(
    r"\(\s*(?:art\.?|artikel|lid|bepaling|onderdeel)?\s*[,;:]?\s*\)"   # lege haakjes, ook met alleen een soortwoord
    r"|\b(?:None|null|undefined|nan)\b"                                  # een veld zonder waarde
    r"|\{\w*\}"                                                         # een vorm zonder invulling
    r"|\S {2,}\S"                                                        # een dubbele spatie: een leeg deel ertussen
    r"|\s[,;:.](?=\s|$)"                                                # een leesteken zonder woord ervoor
    r"|[,;:·–]\s*$"                                                     # een regel die op een scheiding eindigt
    r"|^\s*$")                                                          # een lege regel


def lege_plekken(regel: str) -> list[str]:
    """De gaten in één regel van het denkproces (`_LEGE_PLEK`); leeg als de regel heel is."""
    return [m.group(0) for m in _LEGE_PLEK.finditer(regel or "")] or ([""] if not (regel or "").strip() else [])


def _zonder_lege_plekken(regel: str) -> str:
    regel = re.sub(r"\s*\(\s*(?:art\.?|artikel|lid|bepaling|onderdeel)?\s*[,;:]?\s*\)", "", regel)
    regel = re.sub(r"\s+([,;:.])(?=\s|$)", r"\1", " ".join(regel.split()))
    return re.sub(r"[,;:·–]\s*$", "", regel).strip()


def _duur(ms: int) -> str:
    """`0,4 s` / `12 s` – Nederlandse notatie, zoals de werkplek hem toont."""
    return f"{ms / 1000:.1f} s".replace(".", ",") if ms < 10_000 else f"{round(ms / 1000)} s"


def _stap(writer: Any, actor: str, bericht: str, duur_ms: int | None = None, route: str = "", bron: str = "") -> None:
    """Meld één stap in de keten: `Actor · wat er gebeurde`.

    Bestaat om het idioom af te dwingen. Zonder deze helper verzint elke node zijn eigen vorm – zo
    stonden er "Opgesplitst in 3 deelvragen." en "Annoteerder · 4 gegrond" naast elkaar, en waren er
    twee verschillende teksten voor dezelfde graafbevraging.

    Met `duur_ms` staat de duur achter de regel (`… (0,4 s)`) én als eigen veld op het event: de
    tekst reist als `denk` mee naar het chatbericht, dus zo blijft de duur na herladen bewaard.

    `route` zegt welke weg de beurt neemt, als eigen veld: de tekst is voor de jurist en mag veranderen, de eval leest
    de route (G2b). Eerst las de eval hem uit de tekst, dus "Supervisor · kiest de duiding-worker" kon niet weg.

    `bron` zegt bij een regel over een opgehaald resultaat welke spoorbron het was (`agent/spoorbronnen.py`), om dezelfde
    reden: de tekst is voor de jurist, het veld voor wie hem leest zonder tekst te ontleden.
    """
    if gaten := lege_plekken(f"{actor} · {bericht}"):
        if STRIKT:
            raise AssertionError(f"denkproces: lege plek {gaten!r} in {actor} · {bericht!r}")
        logger.warning("denkproces: lege plek", extra={"categorie": "functioneel", "actor": actor, "route": route})
        actor, bericht = _zonder_lege_plekken(actor) or "Lex", _zonder_lege_plekken(bericht) or "werkt verder"
    event: dict[str, Any] = {"type": "status", "message": f"{actor} · {bericht}"}
    if route:
        event["route"] = route
    if bron:
        event["bron"] = bron
    if duur_ms is not None:
        event["message"] += f" ({_duur(duur_ms)})"
        event["duur_ms"] = duur_ms
    writer(event)


def doel_in_woorden(doel: dict[str, Any]) -> str:
    """De aangewezen bepaling van een annotatiedoel in woorden: "artikel 7a, lid 1 (Wet X)", of het label van zijn
    `bron_iri` als het doel alleen die draagt ("Artikel 7a, lid 1"). Leeg als het doel niets aanwijst. Eerst stond er
    "(art. )" bij elk doel met alleen een `bron_iri` (E2E Rekeningafspraken 16 nov 2026, D-1)."""
    from bronmodel import vindplaats

    nummer = str(doel.get("artikel") or doel.get("nummer") or "").strip()
    lid = str(doel.get("lid") or "").strip()
    titel = str(doel.get("citeertitel") or "").strip()
    vp = vindplaats.vindplaats(str(doel.get("bron_iri") or ""))
    if not titel and (bwb := str(doel.get("bwbId") or doel.get("bwb_id") or (vp.bwb_id if vp else "")).strip()):
        from .spoorbronnen import _regeling
        titel = _regeling(bwb)
    if nummer:
        tekst = f"artikel {nummer}" + (f", lid {lid}" if lid else "")
    elif vp is not None and vp.label:
        tekst = vp.label[:1].lower() + vp.label[1:]
    else:
        tekst = ""
    return (tekst + (f" ({titel})" if titel else "")).strip() if tekst else titel


#: Hoe een subagent afliep (`subagent.Afloop.uitkomst`), voor de kindregel.
KIND_UITKOMST: dict[str, str] = {
    "klaar": "klaar, met een rapport",
    "vraag": "heeft een vraag voor je",
    "niet_gelukt": "rondde af zonder het gevraagde",
    "afgesloten": "afgesloten door de code (rondegrens of tokenplafond), zonder rapport",
    "gestopt": "gestopt",
    "mislukt": "liep vast door een storing",
    "budget_op": "niet gestart: het tokenbudget is op",
    "niet_gestart": "niet gestart",
}


def kindregel(uitkomst: str, kind: dict[str, Any]) -> str:
    """Wat een subagent opleverde, als regel in het denkproces van de beurt die hem startte: "klaar, met een rapport ·
    9 aanroepen, 5 gelezen (3 deels), 12 alleen gevonden". De stappen van het kind staan in zijn deelgesprek;
    hier stond alleen dat hij begon, en niet wat hij deed of opleverde (E2E Rekeningafspraken 16 nov 2026). Uit code: de
    trace en het rapport van het kind, voor elk profiel en elke bron."""
    from .gelezen import deels_gelezen, gelezen_en_gevonden

    trace = kind.get("source_trace") or []
    gelezen, gevonden = gelezen_en_gevonden(trace)
    deels = deels_gelezen(trace)
    delen = [f"{len(trace)} {'aanroep' if len(trace) == 1 else 'aanroepen'}"] if trace else []
    if gelezen:
        n_deels = sum(1 for i, _ in gelezen if i in deels)
        delen.append(f"{len(gelezen)} gelezen" + (f" ({n_deels} deels)" if n_deels else ""))
    if gevonden:
        delen.append(f"{len(gevonden)} alleen gevonden")
    rapport = kind.get("rapport") or {}
    if punten := list(dict.fromkeys([*(kind.get("niet_onderbouwd") or []), *(kind.get("onbevestigd") or [])])):
        # Wat de controle van het kind niet terugvond, gaat met het rapport mee (`subagent.controle_tekst`): ook hier.
        delen.append(f"{len(punten)} {'punt' if len(punten) == 1 else 'punten'} niet teruggevonden door de controle")
    if (n := len(rapport.get("vragen") or [])) and uitkomst == "vraag":
        delen.append(f"{n} {'vraag' if n == 1 else 'vragen'}")
    tekst = KIND_UITKOMST.get(uitkomst, uitkomst or "klaar")
    return tekst + (": " + ", ".join(delen) if delen else "")


def met_regelgrens(denk: str, inhoud: str) -> str:
    """`inhoud` van een `reason`-event, met een regelgrens als het denkproces op een statusregel eindigt. De eerste ronde
    draagt geen alinea-scheiding (`ronde_in_denk`), dus plakte "· Lex · zoekt in de kennisgraaf" aan "Ik zoek …"
    (acceptatie 7 nov 2026). `frontend/lib/beurtStroom.ts` doet hetzelfde voor wie meekijkt."""
    laatste = denk.rsplit("\n", 1)[-1]
    return "\n" + inhoud if inhoud and laatste.startswith("· ") and not inhoud.startswith("\n") else inhoud


def ronde_in_denk(writer: Any, tool_uses: list[Any], tekst: list[str], ronde: int,
                  afronden: frozenset[str] | set[str] = frozenset()) -> None:
    """Zet de tekst van een afgelopen modelronde in het denkproces (`reason`), als het narratie is.

    Een ronde zonder tool-aanroepen is een eindantwoord, en dat hoort daar niet: `verify` kan het nog
    afkeuren, en het denkproces staat tijdens de beurt open (besluit 2, 6 nov 2026). Vandaar ná de
    ronde en niet per delta: tijdens het streamen is nog niet bekend welke van de twee het is.

    Een ronde met een tool uit `afronden` (de sjablonen) is óók het antwoord: wat het model ernaast schreef, staat daarna
    in het sjabloon, dus in het denkproces stond het antwoord twee keer (acceptatie 12 nov 2026, K17).

    Op een rondegrens een alinea-scheiding, anders plakt "…tegelijkertijd." aan "De thesaurus…".
    Een ronde zonder tekst geeft niets, dus ook geen loshangende witregel.
    """
    inhoud = "".join(tekst)
    if not tool_uses or not inhoud.strip() or any(_naam(t) in afronden for t in tool_uses):
        return
    writer({"type": "reason", "content": ("\n\n" if ronde > 0 else "") + inhoud})


def _naam(tool_use: Any) -> str:
    return str(tool_use.get("name", "") if isinstance(tool_use, dict) else getattr(tool_use, "name", ""))


#: Wat er in het denkproces staat vóór een statusregel: `· Actor · bericht`.
STATUSTEKEN = "· "


def denk_bij(denk: str, event: dict[str, Any]) -> str:
    """Het denkproces na één event: de enige plek in graph-qa die het opbouwt, voor het bewaarde bericht
    (`beurt.BeurtSchrijver`). Een `status` wordt een eigen regel, een `reason` loopt door (met `met_regelgrens`); elk ander
    event, ook `token`, laat het staan. `frontend/lib/denkproces.ts` (`denkBij`) doet hetzelfde voor wie meekijkt, en
    `tests/poort/denkproces-vectoren.json` houdt de twee gelijk."""
    soort = event.get("type")
    if soort == "status":
        return denk + ("\n" if denk else "") + STATUSTEKEN + str(event.get("message", ""))
    if soort == "reason":
        return denk + met_regelgrens(denk, str(event.get("content", "")))
    return denk


def _toolregel(call: dict[str, Any]) -> str:
    """"leest artikel 9, lid 1 (Invorderingswet 1990)": het werkwoord komt uit het register van spoorbronnen
    (`agent/spoorbronnen.py`), voor de graaf en elke connector langs dezelfde weg."""
    from .spoorbronnen import toolregel
    return toolregel(call)


def _grounding_melding(report: Any) -> str:
    """Wat de brongetrouwheidstoets opleverde – inclusief het geval dat er niets te toetsen viel.

    De controle kijkt naar twee dingen die los van elkaar staan: **vindplaatsen** (BWB-id's en IRI's
    in het antwoord) en **citaten** (tekst tussen aanhalingstekens). De melding hoort te zeggen wat
    er daadwerkelijk is nagelopen.

    Dat ging mis bij een antwoord dat artikelen in gewone taal noemt – "artikel 2 lid 1 onderdeel m"
    zonder BWB-id. Nul vindplaatsen dus, maar wél twee citaten, en die klopten allebei. De tijdlijn
    meldde toen "0 verwijzingen onderbouwd": precies de misleidende regel die de "niets te
    controleren"-tak hierboven had moeten voorkomen, maar die vangt alleen het geval waarin er
    helemaal niets was.
    """
    onbevestigd = getattr(report, "onbevestigd", None)
    if report.niveau == "onbepaald" and onbevestigd:
        return f"brongetrouwheid: {len(onbevestigd)} vermelding(en) niet teruggevonden in wat is opgehaald"
    vermeld = getattr(report, "vermeld", None) or []
    if report.niveau == "onbepaald" and vermeld and not report.cited and not getattr(report, "citaten", 0):
        # Een artikel in gewone taal is nagelopen, dus "niets te controleren" klopt niet; hard getoetst is het ook niet.
        n = len(vermeld)
        return (f"brongetrouwheid: {n} {'vermelding' if n == 1 else 'vermeldingen'} teruggevonden in wat is opgehaald, "
                "geen vindplaats of citaat om letterlijk te toetsen")
    if report.niveau == "onbepaald":
        return "brongetrouwheid: geen vindplaats of citaat genoemd – niets te controleren"

    delen: list[str] = []
    if report.unsupported:
        delen.append(f"{len(report.unsupported)} verwijzing(en) niet uit de graaf")
    if report.niet_letterlijk:
        delen.append(f"{len(report.niet_letterlijk)} citaat(en) niet letterlijk teruggevonden")
    if delen:
        return "brongetrouwheid: " + ", ".join(delen)

    # Alles klopte. Zeg dan wát er klopte, en tel alleen mee wat er ook echt was.
    aantal_citaten = int(getattr(report, "citaten", 0) or 0)
    goed: list[str] = []
    if report.cited:
        goed.append(f"{len(report.cited)} " + ("verwijzingen" if len(report.cited) > 1 else "verwijzing"))
    if aantal_citaten:
        goed.append(f"{aantal_citaten} " + ("citaten" if aantal_citaten > 1 else "citaat"))
    if not goed:  # een vaste tekst van de code (de bepalingsroute): niets aangehaald, dus ook niets geteld
        return "brongetrouwheid: gecontroleerd, niets aangehaald"
    return f"brongetrouwheid: {' en '.join(goed)} gecontroleerd"


#: Procestaal van het model vóór een scheidingslijn: "Nu heb ik de letterlijke tekst van alinea 148. Ik kan het antwoord nu
#: opbouwen.\n\n---\n\n**Twee lagen …**" (nameting #1274, K07: na twee weigeringen van een sjabloon schreef het model zijn
#: antwoord in tekst, met zijn eigen aanloop erboven). Alleen een korte aanloop in de eerste persoon over het werk zelf.
_AANLOOP_RE = re.compile(r"\A\s*(?P<kop>[^\n]{1,300}?)\s*\n\s*(?:-{3,}|\*{3,}|_{3,})\s*\n(?P<rest>.+)\Z", re.S)
_PROCES_RE = re.compile(r"\b(?:ik\s+(?:heb|kan|ga|zal|wil|moet)|nu\s+(?:heb|kan|ga)\s+ik|laat\s+me|eerst\s+(?:lees|zoek|haal))\b",
                        re.IGNORECASE)


#: Een eerste alinea die alleen het antwoord aankondigt, zonder scheidingslijn ("Hieronder volgt het volledige antwoord
#: op basis van de opgehaalde regels."; herhaalmeting na #1796). Kort, en alleen deze vaste vorm: een alinea met inhoud
#: begint niet zo.
_AANKONDIGING_RE = re.compile(r"\A\s*(?P<kop>(?:hieronder|hier)\s+(?:volgt|staat|vind\s+je|is|lees\s+je)\b[^\n]{0,160}?"
                              r"\b(?:antwoord|overzicht|uitleg|samenvatting)\b[^\n]{0,80}?[.:])\s*\n\s*\n(?P<rest>.+)\Z",
                              re.S | re.IGNORECASE)


def zonder_aanloop(tekst: str) -> tuple[str, str]:
    """(het antwoord, de aanloop die eraf ging). De aanloop gaat naar het denkproces, niet naar de jurist; geen
    aanloop of een kop die geen procestaal is (een titel, een citaat): de tekst blijft zoals hij was."""
    if (a := _AANKONDIGING_RE.match(tekst or "")) and not any(t in a.group("kop") for t in ('"', "„", "“", "#", "**")):
        return a.group("rest").lstrip("\n"), a.group("kop").strip()
    m = _AANLOOP_RE.match(tekst or "")
    if not m or not _PROCES_RE.search(m.group("kop")) or any(t in m.group("kop") for t in ('"', "„", "“", "#", "**")):
        return tekst, ""
    return m.group("rest").lstrip("\n"), m.group("kop").strip()

