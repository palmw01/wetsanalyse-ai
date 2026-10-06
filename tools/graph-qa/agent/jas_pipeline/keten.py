"""De hybride annotatieketen als één pure functie (ADR-001).

    bronsegmenten → taalanalyse → detectoren → fusie + specificiteit
                  → deterministische besluiten → classifier op labels → voorstellen

Uitvoer is een lijst `AnnotatieVoorstel`-dicts (met `ankers` per bronnode en `anker` op het
corpus), in de vorm die `emit`, de api en de werkplek verwachten.

Een voorstel komt er alleen voor een geaccepteerde beslissing. Afgewezen en onzekere kandidaten
verdwijnen niet: ze staan in `Uitkomst.beslissingen` en gaan mee naar de provenance en de
dekkingsboekhouding (`dekking`). Er valt hier nooit iets terug naar een volledige LLM-annotatie.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from bronmodel import CorpusMap, Span

from . import uitleg
from ..annotatie import _maak_anker
from ..models import AnnotatieAlternatief, AnnotatieVoorstel
from .besluit import Beslissing, deterministisch, ontdubbel_tijd
from .broncontext import BronContext
from .classificatie import batches, classificeer, kandidaatregel, optie_ids, promptversie, toolschema
from .dekking import controleer_a, structureel
from .onzekerheid import REVIEWBAAR, signaleer
from .subtype import bepaal as bepaal_subtype
from .resolver import los_op
from .reviewload import splits
from .review import beoordeel
from .validatie import valideer
from .detectoren import BronTekst, detecteer_alles
from .fusie import Fusie, fuseer, VERSIE as FUSIE_VERSIE
from .kandidaten import Candidate, CandidateStatus
from .taal import maak_provider
from .taal.grenzen import VERSIE as GRENS_VERSIE
from .taal.structuur import VERSIE as STRUCTUUR_VERSIE
from .taal.verwijzingen import VERSIE as VERWIJZING_VERSIE


# De JAS-versie waarop profielen en regels berusten (ADR-001 §1.1; minbzk/wetsanalyse 5ae93cc).
JAS_VERSIE = "1.0.10"


@cache
def _provider(spec: str):
    return maak_provider(spec)


def warm_taalmodel_op(spec: str) -> None:
    """Laad het taalmodel van deze configuratie alvast. Voor de opstartfase van de dienst: het laden
    duurt seconden, en na een koude start (`minReplicas: 0`) betaalde de eerste beurt dat. Een
    provider zonder zwaar model (`null`) heeft niets op te warmen; een laadfout blijft het gewone,
    zichtbaar gedegradeerde pad."""
    opwarmen = getattr(_provider(spec), "warm_op", None)
    if opwarmen is not None:
        opwarmen()


@dataclass
class Uitkomst:
    voorstellen: list[dict[str, Any]]
    fusie: Fusie
    beslissingen: list[Beslissing]
    meting: dict[str, Any] = field(default_factory=dict)


def _classificeer_batches(alle_batches: list[list[Candidate]], llm: Any, model: str, corpus: str,
                          settings: Any, meting: dict[str, Any], contextblok: str) -> list[Beslissing]:
    """Alle classificatiebatches, tegelijk waar dat mag, met het resultaat in batchvolgorde.

    De batches zijn onafhankelijk: elk heeft zijn eigen klasseverzameling, prompt en toolschema, en
    geen batch leest de uitkomst van een andere. Na elkaar kostte dat per batch een volle modelronde –
    vier batches van ~15 s maakten een beurt van een minuut. Parallel verandert de uitkomst niet:
    elke batch krijgt precies hetzelfde verzoek, en de beslissingen komen in dezelfde volgorde terug.

    Elke batch telt in een eigen `meting`-dict (een gedeelde dict tussen threads zou tellingen
    verliezen); de tellers gaan daarna bij elkaar. `copy_context` houdt de OTel-span van de beurt
    als ouder van de modelaanroepen in de worker-threads.
    """
    parallel = max(1, min(int(getattr(settings, "classifier_parallel", 1) or 1), len(alle_batches)))

    def een(batch: list[Candidate]) -> tuple[list[Beslissing], dict[str, int]]:
        eigen: dict[str, int] = {}
        uit = classificeer(llm, model, batch, corpus, settings.classifier_temperature, eigen,
                           spankeuze=settings.classifier_spankeuze, context=contextblok)
        return uit, eigen

    if parallel == 1:
        uitkomsten = [een(b) for b in alle_batches]
    else:
        with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="classifier") as pool:
            futures = [pool.submit(contextvars.copy_context().run, een, b) for b in alle_batches]
            uitkomsten = [f.result() for f in futures]
    beslissingen: list[Beslissing] = []
    for uit, eigen in uitkomsten:
        beslissingen += uit
        for sleutel, waarde in eigen.items():
            meting[sleutel] = meting.get(sleutel, 0) + waarde
    meting["classifier_parallel"] = parallel
    return beslissingen


def _bronteksten(segmenten: list[dict[str, Any]], nodes: list[dict[str, Any]], taal: str) -> list[BronTekst]:
    """Per niet-leeg segment een BronTekst, met de tekst van de ouder als context (aanhef)."""
    per_iri = {n["bron_iri"]: n for n in nodes}
    provider = _provider(taal)
    uit = []
    for s in segmenten:
        if not s["tekst"].strip():
            continue
        ouder = per_iri.get(s.get("parent_iri", ""), {})
        uit.append(BronTekst(s["bron_iri"], s["tekst"], s["bron_hash"], analyse=provider.analyseer(s["tekst"]),
                             context=ouder.get("tekst", "")))
    return uit


def _grens(k: Candidate, optie: str) -> tuple[int, int]:
    return optie_ids(k)[optie] if optie else (k.span.start, k.span.eind)


def _toelichting(k: Candidate, b: Beslissing, bijdragen=()) -> str:
    """Criterium en toepassing op dit fragment (`uitleg.toelichting`); geen modeltekst."""
    return uitleg.toelichting(k, b.klasse, b.door, bijdragen)


def _voorstel(k: Candidate, b: Beslissing, kaart: CorpusMap, corpus: str, lid: str, vindplaats: str,
              spankeuze: bool = False, bijdragen=()) -> dict[str, Any]:
    start, eind = _grens(k, b.optie)
    seg = kaart.segment(k.span.bron_iri)
    span = Span(k.span.bron_iri, start, eind, seg.tekst[start:eind], seg.bron_hash)
    c_start, c_eind = kaart.naar_corpus(span)
    anker = _maak_anker(corpus, c_start, c_eind, lid)
    # Per alternatief de reden uit het bewijs van de detectoren die déze klasse aandroegen.
    alternatieven = [AnnotatieAlternatief(klasse=c, motivatie=uitleg.reden_alternatief(c, b.klasse, bijdragen))
                     for c in k.possible_classes if c != b.klasse] if (b.door == "model" or len(k.possible_classes) > 1) else []
    return AnnotatieVoorstel(
        # Deterministisch: dezelfde span met dezelfde klasse krijgt in elke run hetzelfde id, dus de
        # api herkent het element bij een volgende ronde en de stabiliteitsmeting kan vergelijken.
        id=hashlib.sha256(f"{k.id}\x1f{b.klasse}\x1f{start}:{eind}".encode()).hexdigest()[:12],
        klasse=b.klasse, tekst=span.tekst, lid=lid, toelichting=_toelichting(k, b, bijdragen),
        alternatieven=alternatieven, grounded=True, vindplaats=vindplaats,
        anker=anker, ankers=[span.anker()],
        jas_subtype=bepaal_subtype(b.klasse, (e.code for e in k.evidence)),
        trace=_spoor(k, b, spankeuze),
    ).model_dump()


def _spoor(k: Candidate, b: Beslissing, spankeuze: bool = False) -> dict[str, Any]:
    """Het herkomstspoor van één element (opdracht §27, §40). Wat de hele beurt deelt – taalmodel,
    detectorversies, methode- en promptversie, model – staat in de `run`; hier alleen wat per
    element verschilt. `vervolledig` voegt validatie, twijfel en resolutie toe."""
    return {
        "pijplijn": "hybrid_v1", "jas_versie": JAS_VERSIE,
        "kandidaat": {"id": k.id, "label": k.label, "span": k.span.model_dump(),
                      "mogelijke_klassen": list(k.possible_classes), "gedegradeerd": k.gedegradeerd,
                      "bewijs": [e.model_dump() for e in k.evidence],
                      "spanopties": [{"soort": o.soort, "start": o.span.start, "eind": o.span.eind}
                                     for o in k.span_options]},
        "beslissing": b.model_dump(mode="json"),
        # Alleen als er een model aan te pas kwam: de exacte regel die het over deze kandidaat zag.
        "vraag": kandidaatregel(k, spankeuze) if b.door in {"model", "terugval"} else "",
    }


def _vervolledig(voorstellen: list[dict[str, Any]], beslissingen: list[Beslissing], bevindingen, twijfels,
                 transities) -> None:
    per_b = {b.label: b for b in beslissingen}
    for v in voorstellen:
        spoor = v.get("trace") or {}
        label = spoor.get("kandidaat", {}).get("label", "")
        spoor["beslissing"] = per_b[label].model_dump(mode="json") if label in per_b else spoor.get("beslissing")
        spoor["validatie"] = [x.model_dump() for x in bevindingen if x.label == label]
        spoor["twijfel"] = [t.model_dump() for t in twijfels if t.label == label]
        spoor["resolutie"] = [t.model_dump() for t in transities if t.label == label]
        v["trace"] = spoor


def _verwerp(beslissingen: list[Beslissing], bevindingen) -> list[Beslissing]:
    fout = {x.label: x for x in bevindingen if x.ernst == "fout"}
    return [b.model_copy(update={"status": CandidateStatus.REJECTED, "reden": f"VALIDATION_ERROR:{fout[b.label].code}"})
            if b.label in fout else b for b in beslissingen]


class _Fasen:
    """Meet de duur per fase en meldt hem – als statusregel (via `melding`) én in de meting."""

    def __init__(self, melding: Callable[[str, str, int], None] | None) -> None:
        self.melding, self.lijst, self.t = melding, [], time.perf_counter()

    def klaar(self, fase: str, samenvatting: str) -> None:
        nu = time.perf_counter()
        ms = round((nu - self.t) * 1000)
        self.t = nu
        self.lijst.append({"fase": fase, "samenvatting": samenvatting, "ms": ms})
        if self.melding is not None:
            self.melding(fase, samenvatting, ms)


def analyseer(*, snapshot: dict[str, Any], corpus_segmenten: list[dict[str, Any]], corpus: str,
              llm: Any, model: str, settings: Any, lid: str = "", vindplaats: str = "",
              hergebruikte_nodes: set[str] | frozenset[str] = frozenset(),
              context: BronContext | None = None,
              melding: Callable[[str, str, int], None] | None = None) -> Uitkomst:
    """De hele keten. `melding(fase, samenvatting, ms)` wordt per afgeronde fase aangeroepen, zodat de
    beurt zich per stap meldt in plaats van één regel na afloop."""
    fasen = _Fasen(melding)
    context = context or BronContext()
    contextblok = context.blok()
    teksten = [t for t in _bronteksten(snapshot["segmenten"], snapshot["nodes"], settings.taal_provider)
               if t.bron_iri not in hergebruikte_nodes]
    gedegradeerd = sorted({t.bron_iri for t in teksten if t.analyse and t.analyse.gedegradeerd})
    taal_model = next((t.analyse.model for t in teksten if t.analyse), "")
    zinnen = sum(len(t.analyse.zinnen) for t in teksten if t.analyse)
    fasen.klaar("Taalanalyse", (f"{taal_model or 'geen parser'}, {zinnen} zin(nen)" if not gedegradeerd
                                else f"gedegradeerd voor {len(gedegradeerd)} bronnode(s): alleen lexicale detectoren"))
    resultaten = [r for t in teksten for r in detecteer_alles(t)]
    fusie = fuseer(resultaten)
    detectoren = len({r.detector for r in resultaten})
    fasen.klaar("Detectie", f"{len(fusie.kandidaten)} kandidaten uit {detectoren} detectoren")
    meting: dict[str, Any] = {"llm_calls": 0, "kandidaten": len(fusie.kandidaten),
                              "gedegradeerd": gedegradeerd, "taal_model": taal_model,
                              "tekstgrenzen_versie": GRENS_VERSIE,
                              "tekststructuur_versie": STRUCTUUR_VERSIE,
                              "verwijzingen_versie": VERWIJZING_VERSIE,
                              "fusie_versie": FUSIE_VERSIE, "broncontext": context.meting(),
                              "detectorresultaten": [{"detector": r.detector, "versie": r.versie,
                                  "bron_iri": r.bron_iri, "kandidaten": len(r.kandidaten),
                                  "overgeslagen": r.overgeslagen, "reden": r.reden} for r in resultaten],
                              "classifier_prompt": promptversie(settings.classifier_spankeuze)}

    beslissingen: list[Beslissing] = []
    naar_model: list[Candidate] = []
    for k in fusie.kandidaten:
        b = deterministisch(k) if (settings.deterministisch_accepteren or k.status is CandidateStatus.REJECTED) else None
        if b is None:
            naar_model.append(k)
        else:
            beslissingen.append(b)
    fasen.klaar("Besluit", f"{len(beslissingen)} op vaste regels, {len(naar_model)} naar het model")
    alle_batches = batches(naar_model, settings.classifier_granulariteit)
    for batch in alle_batches:
        schema = toolschema(batch, settings.classifier_spankeuze)
        meting.setdefault("classifier_batches", []).append({"labels": [k.label for k in batch],
            "schema_sha256": hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest(),
            "beslissingen": schema["input_schema"]["properties"]["beslissingen"]["items"]["properties"]["beslissing"]["enum"]})
    beslissingen += _classificeer_batches(alle_batches, llm, model, corpus, settings, meting, contextblok)
    meting["oorspronkelijke_beslissingen"] = [b.model_dump(mode="json") for b in beslissingen]
    if naar_model:
        afgewezen = sum(b.status is CandidateStatus.REJECTED and b.door == "model" for b in beslissingen)
        fasen.klaar("Classificatie", f"{len(naar_model)} kandidaten in {meting['llm_calls']} modelaanroep(en), "
                                     f"{afgewezen} afgewezen")

    kaart = CorpusMap(corpus_segmenten)
    per_id = fusie.per_id()
    # Per kandidaat wat elke detector aanbood – de bron van de uitleg per alternatief.
    bijdragen: dict[str, list] = {}
    for bijdrage in fusie.bijdragen:
        bijdragen.setdefault(bijdrage.kandidaat_id, []).append(bijdrage)
    paren, gezien = [], set()
    for b in sorted(beslissingen, key=lambda b: b.label):
        if b.status is not CandidateStatus.ACCEPTED:
            continue
        v = _voorstel(per_id[b.kandidaat_id], b, kaart, corpus, lid, vindplaats, settings.classifier_spankeuze,
                      bijdragen.get(b.kandidaat_id, ()))
        sleutel = (v["ankers"][0]["bron_iri"], v["ankers"][0]["start"], v["ankers"][0]["eind"], v["klasse"])
        if sleutel not in gezien:                 # twee kandidaten die op dezelfde optie uitkomen
            gezien.add(sleutel)
            paren.append((v, b))

    # Validatie vóór de uitgang: een structurele fout haalt het voorstel eruit en maakt
    # de beslissing REJECTED met de foutcode – zichtbaar in de meting, niet stil.
    prov = {"model": model, **meting}
    voorstellen, bevindingen = valideer(paren, per_id, snapshot, prov)
    beslissingen = _verwerp(beslissingen, bevindingen)

    # Twijfel → gerichte review → resolver. De reviewer ziet alleen twijfelgevallen;
    # de resolver voert een vaste tabel uit en schrijft elke transitie weg.
    per_label = {k.label: k for k in fusie.kandidaten}
    label_van = {v["id"]: b.label for v, b in paren}
    twijfels = signaleer(per_id, beslissingen, bevindingen, set(meting["gedegradeerd"]))
    if context.ontbreekt:
        twijfels = [t.model_copy(update={"detail": t.detail + "; ontbrekende aangevraagde context: "
                                        + ", ".join(context.ontbreekt)})
                    if t.reden == "CENTRALE_NORM_AFGEWEZEN" else t for t in twijfels]
    te_reviewen = [t for t in twijfels if t.reden in REVIEWBAAR
                  and not (t.reden == "CENTRALE_NORM_AFGEWEZEN" and context.ontbreekt)]
    oordelen = (beoordeel(llm, model, te_reviewen, per_label, corpus, meting,
                          gegroepeerd=settings.classifier_granulariteit == "klasseverzameling", context=contextblok)
                if te_reviewen and settings.gerichte_review else [])
    if twijfels:
        fasen.klaar("Review", f"{len(twijfels)} twijfelgeval(len), {len(te_reviewen)} naar de reviewer")
    voorstellen, beslissingen, transities = los_op(
        [{**v, "_label": label_van[v["id"]]} for v in voorstellen], beslissingen, twijfels, oordelen, per_label,
        lambda k, b: _voorstel(k, b, kaart, corpus, lid, vindplaats, settings.classifier_spankeuze,
                               bijdragen.get(k.id, ())))
    # Wat de resolver maakte of wijzigde, gaat opnieuw door dezelfde controles.
    per_b = {b.label: b for b in beslissingen}
    voorstellen, na = valideer([({k: x for k, x in v.items() if k != "_label"}, per_b[v["_label"]])
                                for v in voorstellen], per_id, snapshot, prov)
    beslissingen = _verwerp(beslissingen, na)
    voorstellen, beslissingen, alternatieven = ontdubbel_tijd(voorstellen, beslissingen, per_id)
    meting["alternatieve_tijdgrenzen"] = alternatieven
    meting["validatie"] = [x.model_dump() for x in (*bevindingen, *(x for x in na if x.ernst == "fout"))]
    _vervolledig(voorstellen, beslissingen, (*bevindingen, *na), twijfels, transities)
    oorspronkelijk = {b["label"]: b for b in meting["oorspronkelijke_beslissingen"]}
    for v in voorstellen:
        v["trace"]["oorspronkelijke_beslissing"] = oorspronkelijk.get(v["trace"]["kandidaat"]["label"])
    meting["twijfels"] = [t.model_dump() for t in twijfels]
    meting["resolutie"] = [t.model_dump() for t in transities]
    # Juridisch tegenover technisch (V5, onderzoek §6): alleen rapportage, afgeleid uit het spoor.
    meting["reviewload"] = splits(beslissingen, twijfels, transities)
    meting["deterministisch"] = sum(b.door in {"regel", "specificiteit"} for b in beslissingen)
    # Dekking A: gooit als een kandidaat zonder beslissing bleef – dat is een fout in de keten,
    # geen uitkomst om te rapporteren.
    meting["per_status"] = controleer_a(fusie, beslissingen)
    gedraaid: dict[str, set[str]] = {}
    for r in resultaten:
        gedraaid.setdefault(r.bron_iri, set()).add(r.detector)
    meting["dekking"] = structureel(fusie, teksten, gedraaid)
    ongedekt = sum(len(b["ongedekt"]) for b in meting["dekking"].values())
    ter_keuze = meting["per_status"].get("HUMAN_REVIEW", 0)
    fasen.klaar("Resultaat", f"{len(voorstellen)} voorgesteld" + (f", {ter_keuze} ter keuze aan de jurist" if ter_keuze else "")
                + (f", {ongedekt} zinsdeel/-delen zonder kandidaat" if ongedekt else ""))
    meting["fasen"] = fasen.lijst
    return Uitkomst(voorstellen, fusie, beslissingen, meting)
