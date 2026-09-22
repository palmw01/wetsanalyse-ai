"""Projectie van de gedeelde annotatielagen naar de kennisgraaf (GraphDB).

**Postgres is de waarheid, de graaf is een projectie.** GraphDB draait op Azure niet-persistent: een
herstart wist alle named graphs, en de graafwacht zet alleen de wetten terug. Daarom kan elke laag op
elk moment opnieuw uit Postgres worden opgebouwd, en doet deze module dat ook vanzelf:

* **Na elke mutatie** van een laag (`na_mutatie`, aangeroepen vanuit `AnnotatieStore`) wordt zijn named
  graph best-effort vervangen – een Graph Store `PUT`, dus idempotent.
* **De reconcile-lus** vangt de rest. De kolom `geprojecteerd_tot` is de outbox: kleiner dan `updated`
  betekent achterstand. Ontbreekt het register (`urn:jas:graph:register`), dan is de graaf gewist:
  eerst de ontologie, dan alle lagen, het register **als laatste**, zodat een half herstel opnieuw
  wordt opgepakt.

Ontbreekt de repository `inning` zelf, dan wacht de lus: de importer is eigenaar van die repository
(met zijn FTS-connector en similarity-index), en de graafwacht zet hem terug.

**De api is de enige schrijver naar `urn:jas:`.** graph-qa blijft read-only. Geen enkele triple krijgt
een subject onder `urn:bwb:` en `urn:bwb-ns:tekst` wordt nergens gebruikt – anders belandt een
annotatie in de similarity-index, de union-queries van Lex en de bronnencontrole als "wettekst".
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS, XSD

from .annotatie_contracts import AgentRun, AnnotatieDocument, AnnotatieElement
from .jas_ontologie import JAS, JASK, OA, ONTOLOGIE_GRAAF, bouw_ontologie, klasse_iri, waarde_iri

if TYPE_CHECKING:
    from .annotatie_store import AnnotatieStore

logger = logging.getLogger("wetsanalyse.graaf_projectie")

REGISTER_GRAAF = URIRef("urn:jas:graph:register")
REGISTER = URIRef("urn:jas:register")


class RepositoryOntbreekt(Exception):
    """GraphDB antwoordt, maar de repository bestaat (nog) niet – wachten op de importer."""


def _q(s: str) -> str:
    # Zelfde codering als bwb-import (`rdf_vocab._iri`): een `:` in een waarde moet geëscaped, anders
    # leest hij als een extra segment.
    return quote(s, safe="")


def _pad(doc: AnnotatieDocument) -> str:
    return f"{_q(doc.bwbId)}:artikel:{_q(doc.artikel)}"


def laag_graaf_iri(doc: AnnotatieDocument) -> URIRef:
    return URIRef(f"urn:jas:graph:{_pad(doc)}")


def laag_iri(doc: AnnotatieDocument) -> URIRef:
    return URIRef(f"urn:jas:laag:{_pad(doc)}")


def artikel_iri(doc: AnnotatieDocument) -> URIRef:
    return URIRef(f"urn:bwb:{_q(doc.bwbId)}:artikel:{_q(doc.artikel)}")


def lid_iri(doc: AnnotatieDocument, lid: str) -> URIRef:
    """De lid-node in de BWB-graaf. Liefst zoals graph-qa hem uit de graaf las: een lid zonder eigen
    jci heeft in de graaf een `…:id:<xml-id>`-vorm die hier niet te reconstrueren is."""
    if not lid:
        return artikel_iri(doc)
    stand = doc.leden.get(lid)
    if stand is not None and stand.iri:
        return URIRef(stand.iri)
    return URIRef(f"{artikel_iri(doc)}:lid:{_q(lid)}")


def _lex(run: AgentRun) -> URIRef:
    return URIRef(f"urn:jas:agent:lex:{_q(run.agent_versie or 'onbekend')}")


def _model(run: AgentRun) -> URIRef:
    return URIRef(f"urn:jas:agent:model:{_q(run.model)}")


def _mens(user_id: str) -> URIRef:
    # Alleen de opaque userid, nooit naam of e-mail: de graaf heeft geen authenticatie.
    return URIRef(f"urn:jas:agent:mens:{_q(user_id or 'onbekend')}")


def _tijd(dt: datetime | None) -> Literal | None:
    return Literal(dt.isoformat(), datatype=XSD.dateTime) if dt else None


def _voeg(g: Graph, s, p, o) -> None:
    """Voeg alleen toe als er een waarde is: een lege string is geen feit."""
    if o is None or (isinstance(o, str) and o == ""):
        return
    g.add((s, p, o if isinstance(o, (URIRef, Literal, BNode)) else Literal(o)))


def _run_sleutel(run: AgentRun) -> tuple[str, str, str]:
    return (run.tijd.isoformat(), run.model, run.agent_versie)


def _bouw_run(g: Graph, iri: URIRef, run: AgentRun) -> None:
    g.add((iri, RDF.type, JAS.AgentRun))
    g.add((iri, RDF.type, PROV.Activity))
    g.add((iri, PROV.wasAssociatedWith, _lex(run)))
    g.add((_lex(run), RDF.type, PROV.SoftwareAgent))
    g.add((_lex(run), RDFS.label, Literal(f"Lex {run.agent_versie}".strip())))
    if run.model:
        g.add((iri, PROV.wasAssociatedWith, _model(run)))
        g.add((_model(run), RDF.type, PROV.SoftwareAgent))
        g.add((_model(run), RDFS.label, Literal(run.model)))
    _voeg(g, iri, PROV.startedAtTime, _tijd(run.tijd))
    _voeg(g, iri, JAS.ronde, Literal(run.ronde))
    _voeg(g, iri, JAS.modus, run.modus)
    _voeg(g, iri, JAS.criticRondes, Literal(run.critic_rondes))
    _voeg(g, iri, JAS.stopReden, run.stop_reden)
    _voeg(g, iri, JAS.promptHash, run.prompt_hash)
    _voeg(g, iri, JAS.methodeVersie, run.methode_versie)
    for lid in run.leden:
        g.add((iri, JAS.lid, Literal(lid)))


def _bouw_element(
    g: Graph, doc: AnnotatieDocument, laag: URIRef, el: AnnotatieElement, runs: dict,
) -> None:
    a = URIRef(f"urn:jas:annotatie:{_pad(doc)}:{_q(el.id)}")
    g.add((a, RDF.type, OA.Annotation))
    g.add((a, RDF.type, JAS.Markering))
    g.add((a, OA.motivatedBy, OA.classifying))
    g.add((a, OA.hasBody, klasse_iri(el.klasse)))
    g.add((a, JAS.klasse, klasse_iri(el.klasse)))
    g.add((a, JAS.inLaag, laag))
    g.add((a, JAS.elementId, Literal(el.id)))
    _voeg(g, a, JAS.lid, el.lid)
    _voeg(g, a, JAS.vindplaats, el.vindplaats)
    g.add((a, JAS.lifecycle, waarde_iri("lifecycle", el.lifecycle.value)))
    if el.aandacht is not None:
        g.add((a, JAS.aandacht, waarde_iri("aandacht", el.aandacht.value)))
    g.add((a, JAS.herkomst, Literal(el.herkomst)))
    _voeg(g, a, JAS.gewijzigdDoor, el.gewijzigd_door)
    g.add((a, JAS.verouderd, Literal(el.verouderd)))
    _voeg(g, a, PROV.invalidatedAtTime, _tijd(el.verouderd_op))

    if el.toelichting:
        body = URIRef(f"{a}:toelichting")
        g.add((a, OA.hasBody, body))
        g.add((body, RDF.type, OA.TextualBody))
        g.add((body, OA.purpose, OA.describing))
        g.add((body, RDF.value, Literal(el.toelichting, lang="nl")))

    # Het doel: welk stuk van welke wet. Het citaat staat in `oa:exact` – bewust niet in
    # `urn:bwb-ns:tekst`, want dan telt de similarity-index het als wettekst.
    doel = URIRef(f"{a}:doel")
    g.add((a, OA.hasTarget, doel))
    g.add((doel, RDF.type, OA.SpecificResource))
    g.add((doel, OA.hasSource, lid_iri(doc, el.lid)))
    quote_sel = URIRef(f"{a}:quote")
    g.add((doel, OA.hasSelector, quote_sel))
    g.add((quote_sel, RDF.type, OA.TextQuoteSelector))
    g.add((quote_sel, OA.exact, Literal(el.tekst)))
    if el.anker is not None:
        _voeg(g, quote_sel, OA.prefix, el.anker.voor)
        _voeg(g, quote_sel, OA.suffix, el.anker.na)
        positie = URIRef(f"{a}:positie")
        g.add((doel, OA.hasSelector, positie))
        g.add((positie, RDF.type, OA.TextPositionSelector))
        g.add((positie, OA.start, Literal(el.anker.start, datatype=XSD.nonNegativeInteger)))
        g.add((positie, OA.end, Literal(el.anker.eind, datatype=XSD.nonNegativeInteger)))
        _voeg(g, positie, JAS.bronHash, el.anker.bron_hash)
        _voeg(g, positie, JAS.lidHash, el.anker.lid_hash)

    for i, alt in enumerate(el.alternatieven, start=1):
        n = URIRef(f"{a}:alt:{i}")
        g.add((a, JAS.heeftAlternatief, n))
        g.add((n, RDF.type, JAS.Alternatief))
        g.add((n, JAS.klasse, klasse_iri(alt.klasse)))
        _voeg(g, n, JAS.motivatie, Literal(alt.motivatie, lang="nl") if alt.motivatie else None)

    run = el.geproduceerd_door
    run_iri = runs.get(_run_sleutel(run)) if run is not None else None
    if run_iri is not None:
        g.add((a, PROV.wasGeneratedBy, run_iri))
    if run is not None:
        g.add((a, PROV.wasAttributedTo, _lex(run)))

    for ronde in el.critic_rondes:
        n = URIRef(f"{a}:critic:{ronde.ronde}")
        g.add((a, JAS.heeftCriticRonde, n))
        g.add((n, RDF.type, JAS.CriticRonde))
        g.add((n, RDF.type, PROV.Activity))
        g.add((n, PROV.used, a))
        if run is not None:
            g.add((n, PROV.wasAssociatedWith, _lex(run)))
        g.add((n, JAS.ronde, Literal(ronde.ronde)))
        if ronde.aandacht is not None:
            g.add((n, JAS.aandacht, waarde_iri("aandacht", ronde.aandacht.value)))
        _voeg(g, n, JAS.motivatie, Literal(ronde.motivatie, lang="nl") if ronde.motivatie else None)
        _voeg(g, n, JAS.actie, ronde.actie)
        g.add((n, JAS.toegepast, Literal(ronde.toegepast)))
        if ronde.voorstel_klasse:
            g.add((n, JAS.voorstelKlasse, klasse_iri(ronde.voorstel_klasse)))
        _voeg(g, n, JAS.voorstelTekst, ronde.voorstel_tekst)
        _voeg(g, n, PROV.endedAtTime, _tijd(ronde.tijd))

    for i, b in enumerate(el.beslissingen, start=1):
        n = URIRef(f"{a}:beslissing:{i}")
        g.add((a, JAS.heeftBeslissing, n))
        g.add((n, RDF.type, JAS.Beslissing))
        g.add((n, RDF.type, PROV.Activity))
        g.add((n, PROV.used, a))
        g.add((n, PROV.wasAssociatedWith, _mens(b.actor)))
        g.add((_mens(b.actor), RDF.type, PROV.Person))
        g.add((n, JAS.beslissingType, waarde_iri("beslissing", b.type.value)))
        if b.review_reason is not None:
            g.add((n, JAS.reviewReden, waarde_iri("reden", b.review_reason.value)))
        _voeg(g, n, JAS.opmerking, Literal(b.comment, lang="nl") if b.comment else None)
        if b.wijziging:
            g.add((n, JAS.wijziging, Literal(json.dumps(b.wijziging, ensure_ascii=False, sort_keys=True))))
        _voeg(g, n, PROV.endedAtTime, _tijd(b.tijd))


def bouw_laaggraaf(doc: AnnotatieDocument) -> Graph:
    """De named graph van één laag. Puur en deterministisch: dezelfde laag geeft dezelfde triples."""
    g = Graph()
    for prefix, ns in (("jas", JAS), ("jask", JASK), ("oa", OA), ("prov", PROV), ("dcterms", DCTERMS)):
        g.bind(prefix, ns)

    laag = laag_iri(doc)
    g.add((laag, RDF.type, JAS.AnnotatieLaag))
    g.add((laag, JAS.bwbId, Literal(doc.bwbId)))
    g.add((laag, JAS.artikel, Literal(doc.artikel)))
    g.add((laag, JAS.slug, Literal(doc.slug)))
    g.add((laag, JAS.bepaling, artikel_iri(doc)))
    g.add((laag, JAS.status, waarde_iri("status", doc.status.value)))
    _voeg(g, laag, DCTERMS.title, doc.citeertitel)
    _voeg(g, laag, DCTERMS.modified, _tijd(doc.updated))

    for lid, stand in sorted(doc.leden.items()):
        ls = URIRef(f"{laag}:lid:{_q(lid)}")
        g.add((laag, JAS.heeftLidstand, ls))
        g.add((ls, RDF.type, JAS.Lidstand))
        g.add((ls, JAS.lid, Literal(lid)))
        g.add((ls, JAS.lidHash, Literal(stand.hash)))
        g.add((ls, JAS.bepaling, lid_iri(doc, lid)))
        _voeg(g, ls, PROV.generatedAtTime, _tijd(stand.bijgewerkt))

    # `runs` is append-only, dus de index is een stabiele naam.
    runs: dict[tuple, URIRef] = {}
    for i, run in enumerate(doc.runs):
        iri = URIRef(f"{laag}:run:{i}")
        runs.setdefault(_run_sleutel(run), iri)
        _bouw_run(g, iri, run)

    for el in doc.elementen:
        _bouw_element(g, doc, laag, el, runs)
    return g


def bouw_register(lagen: list[AnnotatieDocument]) -> Graph:
    """Welke lagen er in de graaf staan. Zijn bestaan is ook het teken dat de projectie de laatste
    GraphDB-herstart heeft overleefd: ontbreekt hij, dan is alles weg."""
    g = Graph()
    g.bind("jas", JAS)
    g.add((REGISTER, RDF.type, JAS.Register))
    for doc in lagen:
        laag = laag_iri(doc)
        g.add((REGISTER, JAS.inLaag, laag))
        g.add((laag, JAS.inGraaf, laag_graaf_iri(doc)))
        _voeg(g, laag, JAS.versie, _tijd(doc.updated))
    return g


# --- schrijven ---------------------------------------------------------------------------------------


class GraafProjector:
    """Schrijft lagen naar GraphDB. Eén per proces; de lock per laag houdt projecties van dezelfde
    laag op volgorde – anders kan een oudere PUT ná een nieuwere landen terwijl de outbox de nieuwere
    als geprojecteerd boekt, en dan toont de graaf oude inhoud zonder dat iemand het merkt."""

    def __init__(self, url: str, repository: str, client: httpx.AsyncClient | None = None,
                 timeout: float = 10.0) -> None:
        self._repo_url = f"{url.rstrip('/')}/repositories/{repository}"
        self._http = client or httpx.AsyncClient(timeout=timeout)
        self._eigen_client = client is None
        self._locks: dict[str, asyncio.Lock] = {}
        self._taken: set[asyncio.Task] = set()
        self.status: dict = {"laatste_reconcile": None, "laatste_fout": "", "wacht_op_repository": False}

    async def close(self) -> None:
        for taak in list(self._taken):
            taak.cancel()
        if self._eigen_client:
            await self._http.aclose()

    async def put_graph(self, graaf: URIRef, g: Graph) -> None:
        r = await self._http.put(
            f"{self._repo_url}/rdf-graphs/service", params={"graph": str(graaf)},
            content=g.serialize(format="turtle").encode("utf-8"),
            headers={"Content-Type": "text/turtle"},
        )
        if r.status_code == 404:
            raise RepositoryOntbreekt(self._repo_url)
        r.raise_for_status()

    async def register_bestaat(self) -> bool:
        r = await self._http.post(
            self._repo_url,
            data={"query": f"ASK {{ GRAPH <{REGISTER_GRAAF}> {{ <{REGISTER}> ?p ?o }} }}"},
            headers={"Accept": "application/sparql-results+json"},
        )
        if r.status_code == 404:
            raise RepositoryOntbreekt(self._repo_url)
        r.raise_for_status()
        return bool(r.json().get("boolean"))

    async def projecteer(self, store: "AnnotatieStore", slug: str) -> bool:
        """Vervang de graaf van één laag. `False` = geen laag (meer)."""
        async with self._locks.setdefault(slug, asyncio.Lock()):
            doc = await store.laad_document(slug)
            if doc is None or not doc.laag_sleutel:
                return False
            await self.put_graph(laag_graaf_iri(doc), bouw_laaggraaf(doc))
            # De stand die hier gelezen is, niet "nu": is er intussen weer gemuteerd, dan blijft de
            # laag vuil en neemt de lus hem mee.
            await store.markeer_geprojecteerd(slug, doc.updated)
            return True

    def na_mutatie(self, store: "AnnotatieStore", slug: str) -> None:
        """Best-effort, op de achtergrond: een GraphDB die hapert mag geen beslissing van een jurist
        laten falen. Mislukt het, dan blijft de laag vuil en pakt de lus hem op."""
        async def _doe():
            try:
                await self.projecteer(store, slug)
            except Exception as e:  # noqa: BLE001
                logger.warning("jas_projectie_uitgesteld", extra={"slug": slug, "fout": str(e)[:200]})

        taak = asyncio.get_running_loop().create_task(_doe())
        self._taken.add(taak)
        taak.add_done_callback(self._taken.discard)

    async def reconcile(self, store: "AnnotatieStore", batch: int = 50) -> dict:
        """Eén ronde bijwerken. Geeft terug wat er gebeurde (voor log en admin-status)."""
        volledig = not await self.register_bestaat()
        if volledig:
            logger.info("jas_projectie_herstel", extra={"reden": "register ontbreekt"})
            await self.put_graph(ONTOLOGIE_GRAAF, bouw_ontologie())
            await store.maak_lagen_vuil()

        geprojecteerd = 0
        gezien: set[str] = set()
        while True:
            vuil = [s for s in await store.vuile_lagen(batch) if s not in gezien]
            if not vuil:
                break
            for slug in vuil:
                gezien.add(slug)
                if await self.projecteer(store, slug):
                    geprojecteerd += 1

        if volledig or geprojecteerd:
            # Als laatste: pas als alles erin staat mag de volgende ronde denken dat het af is.
            await self.put_graph(REGISTER_GRAAF, bouw_register(await store.geprojecteerde_lagen()))
        return {"volledig": volledig, "geprojecteerd": geprojecteerd}

    async def lus(self, store: "AnnotatieStore", interval_s: float) -> None:
        while True:
            try:
                uitkomst = await self.reconcile(store)
                self.status.update(laatste_reconcile=datetime.now().astimezone().isoformat(),
                                   laatste_fout="", wacht_op_repository=False)
                if uitkomst["geprojecteerd"]:
                    logger.info("jas_projectie", extra=uitkomst)
            except RepositoryOntbreekt:
                if not self.status["wacht_op_repository"]:
                    logger.warning("jas_projectie_wacht", extra={"reden": "repository ontbreekt"})
                self.status["wacht_op_repository"] = True
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 – de lus mag nooit sterven
                self.status["laatste_fout"] = str(e)[:300]
                logger.warning("jas_projectie_fout", extra={"fout": str(e)[:300]})
            await asyncio.sleep(interval_s)


# De projector van dit proces; None = projectie uit (geen GRAPHDB_URL).
_projector: GraafProjector | None = None


def zet_projector(p: GraafProjector | None) -> None:
    global _projector
    _projector = p


def projector() -> GraafProjector | None:
    return _projector


def na_mutatie(store: "AnnotatieStore", doc: AnnotatieDocument) -> None:
    if _projector is not None and doc.laag_sleutel:
        _projector.na_mutatie(store, doc.slug)
