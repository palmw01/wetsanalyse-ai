"""De index van de kennisgroepstandpunten in de graaf (`--kennisgroepen`; plan-connector-kennisgroepen.md stap 3).

Haalt alle publicaties en nieuwsberichten op bij de openbare REST API van de Belastingdienst (CC0), leest ze met de
gedeelde lezer (`bronmodel.kennisgroepen`, dezelfde als de leestool van graph-qa) en schrijft één eigen named graph,
`urn:wa:graph:kennisgroepen`, met een eigen vocabulaire. Waarom in de graaf: de bron kan niet per wetsartikel zoeken, en
de hele set is klein (1180 publicaties, 12 verzoeken). De graaf weet *dat* en *waar*, de leestool haalt *wat*.

Regels die je niet mag breken:

- **Idempotent per named graph.** Eén PUT vervangt de hele index; herhalen geeft dezelfde graaf.
- **Nooit minder.** De index wordt alleen geschreven als alles binnen is (het aantal is `X-WP-Total`) en als hij niet
  meer dan `MAX_KRIMP` kleiner wordt dan wat er staat (`poortbesluit`). Anders blijft de oude staan en eindigt de run
  met exitcode 2, net als de importpoort van de wet.
- **Gescheiden van de wet.** Geen subject onder `urn:bwb:`, geen `bwb:`-type of -predicaat: de FTS-connector, de
  similarity-index, de provenance en de graafwacht van de wet zien de index niet. De graafwacht peilt hem apart
  (`index_is_compleet`), zodat een lege index nooit als verlies van de wetgraaf telt en andersom.
- **Beleefd.** Hoogstens één verzoek per `PAUZE_S`, een eigen User-Agent, en alleen de host van de Belastingdienst.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests
from bronmodel import kennisgroepen as kg
from rdflib import XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

logger = logging.getLogger(__name__)

KGO = Namespace(kg.NS)
GRAAF = URIRef(kg.GRAAF)
USER_AGENT = "wetsanalyse-bwb-import (kennisgroepen-index; https://github.com/palmw01/wetsanalyse-ai)"
PAUZE_S = 1.0
#: Hoeveel kleiner de index mag worden dan wat er staat (een ingetrokken standpunt blijft bij de bron staan, dus de
#: verzameling krimpt normaal niet).
MAX_KRIMP = 0.05
#: Een vangnet tegen een eindeloze paginering.
MAX_PAGINAS = 100


class KennisgroepenFout(RuntimeError):
    """De bron gaf niet alles: dan schrijven we niets."""


@dataclass
class Opgehaald:
    items: list[dict[str, Any]]
    totaal: int


@dataclass
class Uitkomst:
    standpunten: int = 0
    berichten: int = 0
    bepalingen: int = 0
    geschreven: bool = False
    reden: str = ""
    duur_s: float = 0.0
    per_status: dict[str, int] = field(default_factory=dict)


def haal_alles(sessie: requests.Session, soort: str = "wt_publication", *,
               slaap: Callable[[float], None] = time.sleep, timeout: float = 60.0) -> Opgehaald:
    """Alle items van een soort, pagina voor pagina, op id (stabiel). Volledig of een `KennisgroepenFout`."""
    items: list[dict[str, Any]] = []
    totaal = paginas = None
    pagina = 1
    while paginas is None or pagina <= paginas:
        if pagina > MAX_PAGINAS:
            raise KennisgroepenFout(f"{soort}: meer dan {MAX_PAGINAS} pagina's")
        if pagina > 1:
            slaap(PAUZE_S)
        r = sessie.get(kg.lijst_url(pagina, soort=soort), headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        if totaal is None:
            totaal = int(r.headers.get("X-WP-Total", "-1"))
            paginas = int(r.headers.get("X-WP-TotalPages", "0"))
            if totaal < 0:
                raise KennisgroepenFout(f"{soort}: de bron noemt geen totaal (X-WP-Total)")
        data = r.json()
        if not isinstance(data, list):
            raise KennisgroepenFout(f"{soort}: pagina {pagina} is geen lijst")
        items.extend(data)
        pagina += 1
    ids = {i.get("id") for i in items}
    if len(ids) != totaal:
        raise KennisgroepenFout(f"{soort}: {len(ids)} unieke items, de bron noemt er {totaal}")
    return Opgehaald(items, totaal or 0)


def _lit(waarde: str) -> Literal:
    return Literal(waarde)


def _datum(waarde: str) -> Literal | None:
    return Literal(waarde, datatype=XSD.date) if waarde else None


def bouw_graph(publicaties: list[dict[str, Any]], berichten: list[dict[str, Any]]) -> tuple[Graph, Uitkomst]:
    """De index als graaf. Per publicatie alle velden en verwijzingen uit de lezer (§2.6 van het plan), de tekst per
    rij, de intrekkingen in beide richtingen, en de nieuwsberichten als gebeurtenissen bij de publicatie die ze noemen."""
    g = Graph()
    g.bind("kgo", KGO)
    uit = Uitkomst()
    standpunten = [kg.lees_publicatie(p) for p in publicaties]
    op_id = {s.id: s for s in standpunten if s.id}
    op_slug = {s.slug: s for s in standpunten if s.slug}
    door: dict[str, list[str]] = {}
    for s in standpunten:
        for oud in s.vervangt:
            door.setdefault(oud, []).append(s.id or "")

    for s in standpunten:
        iri = URIRef(kg.subject_iri(s.wp_id))
        m = s.metadata
        bron = m["bron"]
        g.add((iri, RDF.type, KGO.Publicatie))
        if s.is_standpunt:
            g.add((iri, RDF.type, KGO.Standpunt))
            uit.standpunten += 1
        uit.per_status[s.status] = uit.per_status.get(s.status, 0) + 1
        for p, o in (
            (KGO.id, s.id), (KGO.kenmerk, s.kenmerk), (KGO.titel, s.titel), (KGO.titelBron, bron["titel_bron"]),
            (KGO.status, s.status), (KGO.link, s.link), (KGO.slug, s.slug), (KGO.gewijzigdBron, s.gewijzigd_bron),
            (KGO.bronHash, s.bron_hash), (KGO.soort, m.get("soort")), (KGO.nummer, m.get("nummer")),
            (KGO.jaar, m.get("jaar")),
        ):
            if o:
                g.add((iri, p, _lit(str(o))))
        g.add((iri, KGO.wpId, Literal(s.wp_id)))
        g.add((iri, RDFS.label, _lit(s.label)))
        for p, sleutel in ((KGO.datum, "datum"), (KGO.gepubliceerd, "gepubliceerd"), (KGO.gewijzigd, "gewijzigd"),
                           (KGO.vastgesteld, "vastgesteld")):
            if d := _datum(m.get(sleutel, "")):
                g.add((iri, p, d))
        for p, waarden in ((KGO.kennisgroep, bron["kennisgroepen"]), (KGO.middel, bron["middelen"]),
                           (KGO.belastingsoort, bron["belastingsoorten"]), (KGO.rubriek, bron["rubrieken"]),
                           (KGO.subrubriek, bron["subrubrieken"]), (KGO.berichtsoort, bron["soorten"]),
                           (KGO.klasse, bron["class_list"]), (KGO.bijlage, m["bijlagen"])):
            for w in waarden:
                g.add((iri, p, _lit(str(w))))
        for p, waarden in ((KGO.kennisgroepId, bron["kennisgroep_ids"]), (KGO.middelId, bron["middel_ids"])):
            for w in waarden:
                g.add((iri, p, Literal(int(w))))
        for oud in s.vervangt:
            g.add((iri, KGO.vervangtId, _lit(oud)))
            if oud in op_id:
                g.add((iri, KGO.vervangt, URIRef(kg.subject_iri(op_id[oud].wp_id))))
        for nieuw in door.get(s.id or "", []):
            if nieuw:
                g.add((iri, KGO.vervangenDoorId, _lit(nieuw)))
        # De tekst per rij, voor zoeken op woorden (in de eigen graaf, nooit in de wet-FTS).
        for r in s.rijen:
            rij = URIRef(f"{iri}/rij/{r.nr}")
            g.add((iri, KGO.rij, rij))
            g.add((rij, KGO.nr, Literal(r.nr)))
            g.add((rij, KGO.tekst, _lit(r.tekst)))
            if r.kop:
                g.add((rij, KGO.kop, _lit(r.kop)))
            g.add((rij, KGO.rijsoort, _lit(r.soort)))
        # Wat het standpunt noemt, met herkomst en de rij waar het staat.
        for n, v in enumerate(s.verwijzingen, start=1):
            if v.soort == "bijlage":
                continue
            ref = URIRef(f"{iri}/noemt/{n}")
            g.add((iri, KGO.noemt, ref))
            g.add((ref, KGO.doelsoort, _lit(v.soort)))
            g.add((ref, KGO.doel, _lit(v.doel)))
            g.add((ref, KGO.herkomst, _lit(v.herkomst)))
            g.add((ref, KGO.inRij, Literal(v.rij)))
            if v.bwb_id:
                g.add((ref, KGO.bwbId, _lit(v.bwb_id)))
            delen = dict(v.delen)
            if delen.get("artikel"):
                g.add((ref, KGO.artikel, _lit(delen["artikel"])))
            if delen.get("lid"):
                g.add((ref, KGO.lid, _lit(delen["lid"])))
            if v.soort == "bepaling":
                uit.bepalingen += 1
            if v.soort == "publicatie" and v.doel in op_slug:
                g.add((ref, KGO.publicatie, URIRef(kg.subject_iri(op_slug[v.doel].wp_id))))

    for b in berichten:
        geb = kg.lees_bericht(b)
        uit.berichten += 1
        doelen = {op_slug[x].wp_id for x in geb.publicaties if x in op_slug}
        if not doelen:
            continue
        for wp_id in doelen:
            iri = URIRef(kg.subject_iri(wp_id))
            ref = URIRef(f"{iri}/gebeurtenis/{int(b.get('id') or 0)}")
            g.add((iri, KGO.gebeurtenis, ref))
            g.add((ref, KGO.gebeurtenissoort, _lit(geb.soort)))
            if d := _datum(geb.datum):
                g.add((ref, KGO.datum, d))
            g.add((ref, KGO.link, _lit(geb.link)))
            g.add((ref, KGO.titel, _lit(geb.titel)))
    return g, uit


def poortbesluit(nieuw: int, bestaand: int) -> str:
    """Leeg als de index geschreven mag worden; anders de reden waarom de oude blijft staan."""
    if nieuw <= 0:
        return "de bron leverde geen standpunten"
    if bestaand and nieuw < bestaand * (1 - MAX_KRIMP):
        return f"de index zou krimpen van {bestaand} naar {nieuw} standpunten"
    return ""


class IndexSchrijver:
    """De graafkant: tellen wat er staat en de named graph vervangen (RDF4J Graph Store, zoals de wetten)."""

    def __init__(self, *, url: str, repository: str, user: str | None = None, password: str | None = None,
                 sessie: requests.Session | None = None, timeout: float = 120.0) -> None:
        self._url = url.rstrip("/")
        self._repo = repository
        self._auth = (user, password) if user else None
        self._http = sessie or requests.Session()
        self._timeout = timeout

    def aantal(self) -> int:
        """Hoeveel standpunten de index nu draagt. Een fout gaat naar de aanroeper."""
        q = f"SELECT (COUNT(?s) AS ?n) WHERE {{ GRAPH <{kg.GRAAF}> {{ ?s a <{KGO.Standpunt}> }} }}"
        r = self._http.post(f"{self._url}/repositories/{self._repo}", data={"query": q},
                            headers={"Accept": "application/sparql-results+json"}, auth=self._auth,
                            timeout=self._timeout)
        r.raise_for_status()
        rijen = r.json().get("results", {}).get("bindings", [])
        return int(rijen[0]["n"]["value"]) if rijen else 0

    def vervang(self, graph: Graph) -> None:
        r = self._http.put(f"{self._url}/repositories/{self._repo}/rdf-graphs/service", params={"graph": kg.GRAAF},
                           # N-Triples: de index is ~17 MB, en Turtle serialiseren kost daar ~40 s.
                           data=graph.serialize(format="nt").encode("utf-8"),
                           headers={"Content-Type": "application/n-triples"}, auth=self._auth, timeout=self._timeout)
        r.raise_for_status()


def index_is_compleet(schrijver: IndexSchrijver) -> bool:
    """De peiling van de graafwacht: staat er een index? Een fout telt als "niet compleet" (zoals bij de wet)."""
    try:
        n = schrijver.aantal()
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("kennisgroepen: peiling mislukt (%s); de index geldt als incompleet", exc)
        return False
    logger.info("kennisgroepen: index draagt %d standpunten", n)
    return n > 0


def ververs(schrijver: IndexSchrijver, sessie: requests.Session | None = None, *,
            slaap: Callable[[float], None] = time.sleep) -> Uitkomst:
    """Haal alles op, bouw de index en schrijf hem als de poort het toestaat. Een fout van de bron of een poort die
    aanslaat laat de bestaande index staan."""
    begin = time.monotonic()
    sessie = sessie or requests.Session()
    publicaties = haal_alles(sessie, "wt_publication", slaap=slaap)
    berichten = haal_alles(sessie, "posts", slaap=slaap)
    graph, uit = bouw_graph(publicaties.items, berichten.items)
    uit.reden = poortbesluit(uit.standpunten, schrijver.aantal())
    if not uit.reden:
        schrijver.vervang(graph)
        uit.geschreven = True
    uit.duur_s = round(time.monotonic() - begin, 1)
    logger.info("kennisgroepen_index", extra={"standpunten": uit.standpunten, "berichten": uit.berichten,
                                              "bepalingen": uit.bepalingen, "geschreven": uit.geschreven,
                                              "reden": uit.reden, "duur_s": uit.duur_s, "triples": len(graph)})
    return uit
