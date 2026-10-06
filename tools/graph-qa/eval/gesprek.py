"""Gesprekseval: meet of Lex een vervolgvraag op de vorige beurt laat aansluiten.

De andere sets stellen één vraag per case. Daarmee is het geheugen nooit gemeten. Juist daar liep
het mis: doorvragen op een antwoord, na een annotatie vragen naar "andere annotaties", doorvragen op
een gemarkeerd element. Een case is hier een GESPREK: beurten in één `conversation_id`, met per
beurt wat er moet gebeuren.

Wat er per beurt getoetst wordt, komt uit de events die de werkplek ook krijgt. De route lezen we
uit de `status`-regels van de supervisor, de tools uit `tool_execution`. Er is geen apart
eval-kanaal in de agent: wat hier meetbaar is, ziet de jurist ook.

Verwachtingen per beurt (alle optioneel):
  route        : één van de gezien-routes (`annotaties_lezen`, `annotatie`, `advies`, `afgewezen`,
                 `definitie`, `duiding`, `algemeen`) die in deze beurt moet voorkomen
  niet_route   : routes die NIET mogen voorkomen
  tools_wel    : tools waarvan er minstens één moet zijn aangeroepen
  tools_niet   : tools die niet aangeroepen mogen worden
  max_tools    : bovengrens op het aantal tool-calls (de zoeklus van scenario B)
  bevat        : deelstrings die in het antwoord staan (hoofdletterongevoelig, allemaal)
  bevat_een    : minstens één van deze deelstrings staat in het antwoord
  verboden     : deelstrings die er niet in mogen staan
  niet_ongegrond: true → het grounding-niveau mag niet `ongegrond` zijn
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.agent import answer_stream
from agent.config import Settings

GOLDEN_GESPREK = Path(__file__).parent / "golden_gesprek.jsonl"

# Status-regel → route. De supervisor meldt zijn keuze altijd in één van deze vormen
# (agent/nodes/supervisie.py); een specialist meldt zich met "Specialist <naam> · …".
_ROUTE_REGELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Lex · raadpleegt bestaande annotaties"), "annotaties_lezen"),
    (re.compile(r"^Lex · annoteert de aangewezen bepaling"), "annotatie"),
    (re.compile(r"^Lex · advies bij een bestaande markering"), "advies"),
    (re.compile(r"^Lex · meer dan één artikel genoemd"), "afgewezen"),
    (re.compile(r"^Supervisor · buiten de wet"), "afgewezen"),
    (re.compile(r"^Supervisor · kiest de annotatie-worker"), "annotatie"),
    (re.compile(r"^Specialist (\w+) ·"), ""),  # groep 1 is de specialist
)


class GesprekAnnotaties:
    """Annotatie-leespoort voor de gesprekseval, zonder api.

    De eval-job draagt bewust geen api-toegang: een meting mag de werkvoorraad van juristen niet
    veranderen. Zonder poort kan Lex dan niet annoteren (de dekking is onleesbaar) en niets
    terugvinden. Deze poort onthoudt wat Lex in dít gesprek markeerde en kent daarnaast de
    `andere_annotaties` die de case zaait. Zo is "welke rechtssubjecten ken je nog meer" te meten.

    Wat hij NIET nabootst: de omvang en de verificatie van de echte api. Die gedragen zich anders;
    de unittests dekken ze.
    """

    def __init__(self, sparql, gezaaid: list[dict[str, Any]] | None = None):
        self._sparql = sparql
        self.elementen: list[dict[str, Any]] = [dict(e) for e in gezaaid or []]

    def _snapshot_id(self, doel: dict[str, Any]) -> str:
        from bronmodel import resolve

        from agent.bron_annotatie import doel_params
        return resolve(self._sparql, **doel_params(doel))["snapshot_id"]

    def onthoud(self, element: dict[str, Any]) -> None:
        self.elementen = [e for e in self.elementen if e.get("id") != element.get("id")] + [element]

    def dekking(self, doel):
        return {"status": "ok", "snapshot_id": self._snapshot_id(doel), "voltooid": False,
                "parent_context": False, "bereik": []}

    def weergave(self, doel):
        return {"schema_versie": 2, "snapshot_id": self._snapshot_id(doel), "elementen": [], "lagen": []}

    def element(self, element_id):
        for e in self.elementen:
            if e.get("id") == element_id:
                return {"status": "ok", "element": e}
        return {"status": "niet_gevonden", "volledig": True}

    def zoeken(self, filters):
        klassen = set(filters.get("jas_klassen") or ([filters["klasse"]] if filters.get("klasse") else []))
        bron = filters.get("bron_iri") or ""
        bwb = filters.get("bwb_id") or ""
        tekst = (filters.get("tekst") or "").lower()

        def past(e: dict[str, Any]) -> bool:
            iri = e.get("eigenaar_iri") or e.get("bron_iri") or ""
            return ((not klassen or e.get("klasse") in klassen)
                    and (not bron or iri == bron or iri.startswith(bron + ":"))
                    and (not bwb or f"urn:bwb:{bwb}" in iri)
                    and (not tekst or tekst in (e.get("tekst") or "").lower()))

        treffers = [e for e in self.elementen if past(e)]
        limit = int(filters.get("limit") or 25)
        return {"status": "ok", "volledig": True, "resultaten": treffers[:limit],
                "volgende_offset": limit if len(treffers) > limit else None}


_POORTGRAAF = None


def _poortgraaf(settings: Settings):
    global _POORTGRAAF
    if _POORTGRAAF is None:
        from agent.adapters.graphdb_graph import make_graph

        _POORTGRAAF = make_graph(settings)
        _POORTGRAAF.initialize()
    return _POORTGRAAF


def routes_uit_status(berichten: list[str]) -> list[str]:
    """De routes die in deze beurt voorbijkwamen, in volgorde en ontdubbeld."""
    gezien: list[str] = []
    for bericht in berichten:
        for patroon, route in _ROUTE_REGELS:
            m = patroon.match(bericht)
            if m:
                naam = route or m.group(1)
                if naam not in gezien:
                    gezien.append(naam)
                break
    return gezien


@dataclass
class Beurt:
    vraag: str
    antwoord: str
    routes: list[str]
    tools: list[str]
    niveau: str
    error: str | None
    fouten: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.fouten


@dataclass
class GesprekResult:
    id: str
    scenario: str
    beurten: list[Beurt]

    @property
    def passed(self) -> bool:
        return all(b.passed for b in self.beurten)


def score_beurt(verwacht: dict[str, Any], beurt: Beurt) -> list[str]:
    """Wat er aan deze beurt niet klopt, als leesbare regels. Leeg = geslaagd."""
    fouten: list[str] = []
    if beurt.error:
        fouten.append(f"fout: {beurt.error[:80]}")
    laag = beurt.antwoord.lower()
    if (r := verwacht.get("route")) and r not in beurt.routes:
        fouten.append(f"route {r} verwacht, kreeg {beurt.routes or ['?']}")
    for r in verwacht.get("niet_route") or []:
        if r in beurt.routes:
            fouten.append(f"route {r} hoort niet")
    if (wel := verwacht.get("tools_wel")) and not set(wel) & set(beurt.tools):
        fouten.append(f"geen van {wel} aangeroepen")
    for t in verwacht.get("tools_niet") or []:
        if t in beurt.tools:
            fouten.append(f"tool {t} hoort niet")
    if (mx := verwacht.get("max_tools")) is not None and len(beurt.tools) > mx:
        fouten.append(f"{len(beurt.tools)} tool-calls (max {mx})")
    for s in verwacht.get("bevat") or []:
        if s.lower() not in laag:
            fouten.append(f"mist '{s}'")
    if (een := verwacht.get("bevat_een")) and not any(s.lower() in laag for s in een):
        fouten.append(f"geen van {een} in het antwoord")
    for s in verwacht.get("verboden") or []:
        if s.lower() in laag:
            fouten.append(f"bevat '{s}'")
    if verwacht.get("niet_ongegrond") and beurt.niveau == "ongegrond":
        fouten.append("grounding ongegrond")
    return fouten


async def run_beurt(spec: dict[str, Any], conversation_id: str, *, settings: Settings,
                    llm=None, graph=None, annotaties=None, meter=None) -> Beurt:
    status: list[str] = []
    tools: list[str] = []
    tokens: list[str] = []
    niveau = ""
    error: str | None = None
    async for ev in answer_stream(
        spec["vraag"], conversation_id, settings=settings, llm=llm, graph=graph, meter=meter,
        modus=spec.get("modus", "auto"), context=spec.get("context"), doel=spec.get("doel"),
        annotaties=annotaties or getattr(graph, "annotaties", None),
    ):
        soort = ev.get("type")
        if soort == "status":
            status.append(ev.get("message", ""))
        elif soort == "tool_execution" and ev.get("phase") == "start":
            tools.append(ev.get("tool", ""))
        elif soort == "element" and hasattr(annotaties, "onthoud"):
            # Wat Lex markeerde is in de volgende beurt terug te vinden, zoals in de werkplek.
            annotaties.onthoud(ev["element"])
        elif soort == "token":
            tokens.append(ev.get("content", ""))
        elif soort == "grounding":
            niveau = ev.get("niveau", "")
        elif soort == "error":
            error = ev.get("message")
    beurt = Beurt(spec["vraag"], "".join(tokens), routes_uit_status(status), tools, niveau, error)
    beurt.fouten = score_beurt(spec.get("verwacht") or {}, beurt)
    return beurt


async def run_gesprek(case: dict[str, Any], *, settings: Settings, llm=None, graph=None,
                      annotaties=None, meter=None) -> GesprekResult:
    """Alle beurten in één thread. Elke run een vers id: een tweede run mag niet voortbouwen op het
    geheugen van de eerste."""
    gid = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    if annotaties is None:
        # Per gesprek een verse poort: wat het ene gesprek markeerde, hoort het volgende niet te zien.
        # `answer_stream` sluit zijn graaf na elke beurt; de poort leest dus via een eigen verbinding.
        annotaties = GesprekAnnotaties((graph or _poortgraaf(settings)).sparql, case.get("andere_annotaties"))
    beurten = []
    for spec in case["beurten"]:
        beurten.append(await run_beurt(spec, gid, settings=settings, llm=llm, graph=graph,
                                       annotaties=annotaties, meter=meter))
    return GesprekResult(case["id"], case.get("scenario", ""), beurten)


async def run_gesprek_suite(cases: list[dict[str, Any]], *, settings: Settings, stil: bool = False,
                            minuten: float = 15.0, **kw: Any) -> list[GesprekResult]:
    uit = []
    begin = time.monotonic()
    for i, case in enumerate(cases, 1):
        if (time.monotonic() - begin) / 60 >= minuten:
            # Zelfde vangrail als de annotatiesuite: liever een onvolledig rapport dan een job die
            # door zijn timeout wordt afgekapt. Overgeslagen gesprekken tellen nergens mee.
            if not stil:
                print(f"[{i}/{len(cases)}] tijdbudget bereikt – rest overgeslagen", flush=True)
            break
        t0 = time.monotonic()
        r = await run_gesprek(case, settings=settings, **kw)
        uit.append(r)
        if not stil:
            ok = sum(b.passed for b in r.beurten)
            print(f"[{i}/{len(cases)}] {r.id:28} {ok}/{len(r.beurten)} beurten ok · "
                  f"{time.monotonic() - t0:5.1f}s", flush=True)
    return uit


def print_gesprek_report(results: list[GesprekResult]) -> bool:
    print(f"\n{'gesprek':28} {'scen':4} beurt  routes / tools")
    print("-" * 100)
    for r in results:
        for n, b in enumerate(r.beurten, 1):
            vlag = "OK" if b.passed else "XX"
            print(f"{r.id if n == 1 else '':28} {r.scenario if n == 1 else '':4} {n}.{vlag}  "
                  f"{','.join(b.routes) or '-'} / {','.join(b.tools) or '-'}  «{b.vraag[:40]}»")
            for f in b.fouten:
                print(f"{'':40}! {f}")
    beurten = [b for r in results for b in r.beurten]
    vervolg = [b for r in results for b in r.beurten[1:]]
    print("-" * 100)
    print(f"{sum(r.passed for r in results)}/{len(results)} gesprekken geheel geslaagd · "
          f"{sum(b.passed for b in beurten)}/{len(beurten)} beurten · "
          f"vervolgbeurten {sum(b.passed for b in vervolg)}/{len(vervolg)}")
    per_scen: dict[str, list[bool]] = {}
    for r in results:
        per_scen.setdefault(r.scenario or "-", []).extend(b.passed for b in r.beurten[1:])
    for s, v in sorted(per_scen.items()):
        print(f"  scenario {s}: vervolgbeurten {sum(v)}/{len(v)}")
    return all(r.passed for r in results)
