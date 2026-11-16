"""De route `subagent_route`: een opdracht die een reeks moet doorlopen, of die uit delen bestaat die los van elkaar
kunnen, gaat in code naar subagents (ADR-016 §A5; meting 14 nov 2026 en A6 run 1, 15 nov 2026).

S01 en D01 ("vat per uitspraak samen wat de rechter zegt") deed de centrale agent zelf, ook met een scherpere regel in
zijn profiel: 18 keer `get_uitspraak` in 13 rondes, 659k tokens. In A6 run 1 deed hij hetzelfde bij S03–S05, M01 en
M06, met dezelfde regel in zijn instructie en in de beschrijving van `subagent`: S04 kostte zo 400k in één context, en
M01 en M06 begonnen zonder bevestiging. De vorm van zulke opdrachten ligt vast, dus de code herkent haar (`plan`) en
start de subagents zonder modelronde, met de vraag van de jurist als doel: die is de volledige opdracht.

- **Eén subagent**: een reeks die doorlopen moet worden. Per uitspraak, Kamerstuk of publicatie iets samenvatten, of
  wat een bron naast de wet zegt per deelvraag van het werkgebied (V03), met het taakprofiel van die bron
  (`PROFIEL_VAN`), of per artikel of onderdeel van een hoofdstuk of een beleidsregel (de graaf, `bepalingen_duiden`). Daarna gaat de beurt naar de centrale agent, met het rapport als gegeven in de context van de
  beurt (`State.rapporten`, zoals na een klik op een vraagkaart), en die vat het samen. Heeft de subagent een vraag,
  dan sluit `finalize_node` af met de kaart.
- **Twee of drie**: delen die naast elkaar kunnen. Per bron naast de wet (de rechtspraak, de Kamerstukken en het
  Staatsblad, elk apart samengevat), of een vergelijking van twee of drie regelingen zonder genoemd artikel. Die legt
  de code eerst aan de jurist voor (`subagent_plan`, dezelfde kaart als wanneer de centrale agent ze zelf opstelt).

Alleen voor de centrale agent. Een vraag met een artikel zonder regeling niet (V01: "artikel 30"): die vraagt eerst
welke regeling, en dat doet de centrale agent. Een verzoek om te annoteren ook niet. Kan de subagent niet starten (er
loopt al werk van de gebruiker), dan beantwoordt de centrale agent de vraag zelf.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langgraph.config import get_stream_writer

from bronmodel.connectors import herkende

from .. import subagent as sub
from ..agents.uitvoering import draai
from ..agentvorm import CENTRAAL
from ..models import SubagentOpdracht
from ..narratie import _stap
from ..state import State
from .context import Bouw

#: Het brede profiel: voor een bron zonder taakprofiel, of een reeks die over meer soorten bronnen gaat.
PROFIEL = "algemeen"
#: Het profiel voor een reeks bepalingen in de graaf (plan docs/architectuur/plan-agentprofielen.md).
DUIDING = "bepalingen_duiden"
RECHTSPRAAK, WETSGESCHIEDENIS = "rechtspraak_lezen", "wetsgeschiedenis_lezen"
#: Per connector het taakprofiel dat hem leest. Een connector die hier niet staat, leest `algemeen`.
PROFIEL_VAN = {"rechtspraak": RECHTSPRAAK, "kamerstukken": WETSGESCHIEDENIS, "bekendmakingen": WETSGESCHIEDENIS}
#: Zonder herkende bron zegt het soort stuk in de vraag welk taakprofiel het is ("vat per uitspraak samen", S01).
_SOORT_STUK = ((re.compile(r"\b(?:uitspra\w*|arrest\w*|vonnis\w*|conclusie\w*)\b", re.I), RECHTSPRAAK),
               (re.compile(r"\b(?:kamerstuk\w*|memorie\w*|bekendmaking\w*|staatsblad|staatscourant)\b", re.I),
                WETSGESCHIEDENIS))

_STUK = r"(?:uitspraak|uitspraken|arrest|arresten|vonnis|vonnissen|kamerstuk|kamerstukken|stuk|stukken|publicatie|" \
        r"publicaties|bekendmaking|bekendmakingen)"
_PER_STUK = re.compile(rf"\b(?:per|elke|iedere)\s+{_STUK}\b", re.I)
_SAMENVATTEN = re.compile(r"\b(?:vat\w*|samen\s*te\s*vatten|samenvat\w*|samenvatting\w*|de\s+kern|op\s+een\s+rij)\b", re.I)
#: "Welke publicaties … hebben artikel 36 gewijzigd, en wat veranderde elk?" (S05): de reeks staat vooraan, "elk" achteraan.
_STUKKEN = re.compile(r"\b(?:uitspraken|arresten|vonnissen|kamerstukken|stukken|publicaties|bekendmakingen)\b", re.I)
_ELK = re.compile(r"\b(?:elk|ieder)\b\s*[?.!]?\s*$|\bvan\s+(?:elk|ieder)\b", re.I)
_WAT_ELK = re.compile(r"\bwat\s+(?:veranderde|verandert|wijzigde|wijzigt|zegt|zei|regelde|regelt)\b", re.I)

#: "Loop het hoofdstuk … door en geef per artikel …" (S03), "geef per onderdeel van de Leidraad de kern" (S04).
_PER_DEEL = re.compile(r"\b(?:per|elk|ieder)e?\s+(?:artikel|onderdeel|bepaling)\b", re.I)
_REEKS_GRAAF = re.compile(r"\b(?:hoofdstuk|afdeling|paragraaf|titel|leidraad|beleidsregel|onderdelen|artikelen)\b", re.I)

#: "Zoek uit wat de memorie van toelichting zegt over de bepalingen van dit werkgebied en vat dat per deelvraag samen"
#: (V03, A6 run 2: de centrale agent deed het zelf, 17 keer `get_kamerstuk`, 690k).
_PER_DEELVRAAG = re.compile(r"\b(?:per|elke|iedere)\s+deelvraag\b", re.I)

#: "… de rechtspraak en de Kamerstukken, en vat ze per bron apart samen" (P01, P02, M06).
_PER_BRON = re.compile(r"\b(?:per|elke|iedere)\s+bron\b|\bapart\b|\bafzonderlijk\b", re.I)
#: "Vergelijk de regels over aanmaning en dwangbevel in de Iw 1990, de Awb en de Leidraad" (M01, P03).
_VERGELIJK = re.compile(r"\b(?:vergelijk\w*|verhoud\w*|verschil\w*|naast\s+elkaar)\b", re.I)

_ARTIKEL = re.compile(r"\bart(?:ikel|\.)\s*\d", re.I)
_ANNOTEER = re.compile(r"\b(?:annote(?:er|ren)|markeer|markeren|classificeer)\b", re.I)

#: De regelingen die een vraag bij naam noemt, als (bwb-id, citeertitel), in de volgorde van de vraag.
Regelingen = Callable[[str], list[tuple[str, str]]]

Plan = list[tuple[str, SubagentOpdracht]]


def _deel(vraag: str, wat: str, anderen: list[str], *, oplevering: str, bronnen: str = "") -> SubagentOpdracht:
    return SubagentOpdracht(
        doel=f"Jouw deel van deze vraag: alleen {wat}. De vraag van de gebruiker: {vraag}",
        onderwerp=wat, oplevering=oplevering, bronnen=bronnen,
        buiten=("Dit doen andere subagents: " + ", ".join(anderen) + ".") if anderen else "")


def profiel_voor(vraag: str, aan: list[str]) -> str:
    """Het taakprofiel voor één reeks: dat van de bronnen die de vraag noemt als ze er één delen, anders dat van het
    soort stuk dat de vraag noemt, anders het brede profiel."""
    if aan:
        profielen = {PROFIEL_VAN.get(n, PROFIEL) for n in aan}
        return profielen.pop() if len(profielen) == 1 else PROFIEL
    soorten = {p for patroon, p in _SOORT_STUK if patroon.search(vraag)}
    return soorten.pop() if len(soorten) == 1 else PROFIEL


def _per_bron(vraag: str, aan: list[str], bronstand: dict[str, Any]) -> Plan:
    label = {n: (bronstand.get(n) or {}).get("label") or n for n in aan}
    return [(PROFIEL_VAN.get(n, PROFIEL), _deel(vraag, f"de bron {label[n]}", [label[m] for m in aan if m != n], bronnen=label[n],
                            oplevering="Per gelezen stuk (met zijn id) de kern, met de passages die haar dragen."))
            for n in aan]


def _per_regeling(vraag: str, genoemd: list[tuple[str, str]]) -> Plan:
    titels = [t for _, t in genoemd]
    return [(DUIDING, _deel(vraag, f"de {t}", [f"de {x}" for x in titels if x != t],
                            oplevering=f"De bepalingen van de {t} die de vraag dragen, elk gelezen, met hun kern en een "
                                       "letterlijke passage."))
            for t in titels]


def plan(vraag: str, bronstand: dict[str, Any] | None, regelingen: Regelingen | None = None) -> Plan:
    """De subagents die deze opdracht vraagt, of leeg als de centrale agent haar zelf beantwoordt."""
    vraag = " ".join((vraag or "").split())
    if not vraag or _ANNOTEER.search(vraag):
        return []
    from ..binnen_scope import genoemde_regelingen

    stand = bronstand or {}
    # Een regeling alleen bij afkorting telt hier niet als genoemd: liever de centrale agent dan een gok.
    if _ARTIKEL.search(vraag) and not genoemde_regelingen(vraag):
        return []
    aan = [n for n in herkende(vraag) if (stand.get(n) or {}).get("aan")]

    # Meer delen naast elkaar: een plan dat de jurist eerst bevestigt.
    if len(aan) >= 2 and _PER_BRON.search(vraag):
        return _per_bron(vraag, aan[:sub.MAX_SUBAGENTS], stand)
    # De namen uit de graaf alleen bij een vergelijking zonder artikel: geen query bij elke vraag.
    if regelingen and _VERGELIJK.search(vraag) and not _ARTIKEL.search(vraag) \
            and 2 <= len(genoemd := regelingen(vraag)) <= sub.MAX_SUBAGENTS:
        return _per_regeling(vraag, genoemd)

    # Eén reeks.
    een = SubagentOpdracht(doel=vraag, oplevering="Per stuk de kern, met de passages die haar dragen.")
    bron_aan = any((s or {}).get("aan") for s in stand.values())
    if bron_aan and _PER_STUK.search(vraag) and _SAMENVATTEN.search(vraag):
        return [(profiel_voor(vraag, aan), een)]
    if aan and _STUKKEN.search(vraag) and _ELK.search(vraag) and _WAT_ELK.search(vraag):
        return [(profiel_voor(vraag, aan), een)]
    if aan and _PER_DEELVRAAG.search(vraag) and _SAMENVATTEN.search(vraag):
        # De subagent krijgt het werkgebied van de beurt mee (`subagent.voer_uit`): de deelvragen en het zoekbereik.
        return [(profiel_voor(vraag, aan), SubagentOpdracht(
            doel=vraag, oplevering="Per deelvraag van het werkgebied de kern uit de gelezen stukken, elk met zijn id en "
                                   "de passages die haar dragen; noem een deelvraag waarvoor je niets vond."))]
    if _PER_DEEL.search(vraag) and _REEKS_GRAAF.search(vraag) and not aan:
        return [(DUIDING, SubagentOpdracht(
            doel=vraag, oplevering="Per artikel of onderdeel van de reeks, elk gelezen, de kern met de vindplaats en een "
                                   "letterlijke passage; sla er geen over."))]
    return []


#: Een antwoord dat alleen een regeling noemt ("De Invorderingswet 1990."): hoogstens zoveel woorden.
MAX_WOORDEN_ANTWOORD = 8
_EERSTE_ARTIKEL = re.compile(r"\b(art(?:ikel|\.)\s*\d+[a-z]*(?::\d+[a-z]*)?)", re.I)


def aangevuld(vraag: str, vorige: str, regelingen: Regelingen | None) -> str:
    """De vorige opdracht met de regeling uit dit antwoord, of leeg (agentset F02, A6: op "artikel 30?" antwoordde de
    jurist "De Invorderingswet 1990.", en de centrale agent zocht en stelde opnieuw een keuzevraag). Alleen als de vorige
    opdracht een artikel noemde zonder regeling en dit antwoord niets anders noemt dan één regeling: dan is de opdracht
    van de jurist samen te stellen, en gaat ze langs dezelfde route als wanneer hij haar meteen volledig had gesteld."""
    from ..binnen_scope import genoemde_regelingen

    vraag, vorige = " ".join((vraag or "").split()), " ".join((vorige or "").split())
    if not (vraag and vorige and regelingen) or len(vraag.split()) > MAX_WOORDEN_ANTWOORD or _ARTIKEL.search(vraag):
        return ""
    if not _ARTIKEL.search(vorige) or genoemde_regelingen(vorige):
        return ""
    genoemd = regelingen(vraag)
    if len(genoemd) != 1:
        return ""
    return _EERSTE_ARTIKEL.sub(lambda m: f"{m.group(1)} van de {genoemd[0][1]}", vorige, count=1)


def past(vraag: str, bronstand: dict[str, Any] | None, regelingen: Regelingen | None = None) -> bool:
    """Vraagt deze opdracht om een of meer subagents (`plan`)?"""
    return bool(plan(vraag, bronstand, regelingen))


def als_state(p: Plan) -> list[dict[str, Any]]:
    """Het plan in de vorm van `State.subagent_plan` (dezelfde als de overdracht `subagent` zet)."""
    return [{"profiel": profiel, "opdracht": o.model_dump()} for profiel, o in p]


def subagent_route_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    vraag = " ".join((state.get("question") or "").split())
    if b.kinderen is None or not state.get("gesprek_id") or not getattr(b.settings, "legt_zelf_vast", False):
        # De ingang zei al dat een subagent het werk doet: zeg dan ook dat het niet zo liep.
        _stap(writer, "Lex", "kan hier geen subagent starten en beantwoordt de vraag zelf", route=CENTRAAL)
        return {"specialist": CENTRAAL, "subagent_plan": []}
    [eerste, *_] = state.get("subagent_plan") or als_state(
        [(PROFIEL, SubagentOpdracht(doel=vraag, oplevering="Per stuk de kern, met de passages die haar dragen."))])
    profiel, opdracht = eerste["profiel"], SubagentOpdracht(**eerste["opdracht"])
    afloop, kind, weigering = draai(
        lambda stuur: sub.voer_uit(state, profiel, opdracht, stuur, settings=b.settings, kinderen=b.kinderen,
                                   gestopt=lambda: bool(b.stop_check and b.stop_check())),
        loop=b.loop, schrijf=writer)
    if weigering:
        _stap(writer, "Lex", "kon geen subagent starten en beantwoordt de vraag zelf", route=CENTRAAL)
        return {"specialist": CENTRAAL, "subagent_plan": []}
    trace = list(state.get("source_trace") or []) + [tuple(x) for x in kind.get("source_trace") or []]
    rapport = sub.als_toolresultaat(profiel, afloop.uitkomst, sub.rapport_tekst(afloop, kind))
    return {"specialist": CENTRAAL, "source_trace": trace, "subagenten": [afloop.als_dict()], "subagent_plan": [],
            "rapport_steun": sub.steun_van([kind]), "rapport_citaten": sub.citaten_van([kind]),
            "rapporten": ("RAPPORT VAN EEN SUBAGENT (de code gaf hem de vraag van de gebruiker; vat het rapport samen voor "
                          "de gebruiker):\n" + rapport + "\n\n")}
