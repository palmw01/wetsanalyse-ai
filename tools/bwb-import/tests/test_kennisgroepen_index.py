"""De index van de kennisgroepstandpunten (`app/kennisgroepen.py`, `--kennisgroepen`).

Drie eisen uit het besluit van 13 nov 2026 (plan-connector-kennisgroepen.md §8): de import blijft idempotent per named
graph, de graafwacht leest de index niet als verlies van de wetgraaf, en de index staat los van de wet (geen
`urn:bwb:`-subject, geen `bwb:`-term, dus buiten de FTS en de similarity-index). Fixtures: echte publicaties (CC0).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from bronmodel import kennisgroepen as kg
from rdflib import URIRef

import app.kennisgroepen as kgi
import app.main as main_module
from app.graphdb_writer import inhoud_hash
from app.rdf_vocab import DEFAULT_BASE_IRI, DEFAULT_ONTOLOGY_IRI

DATA = Path(__file__).parent / "fixtures" / "kennisgroepen"


def _laad(naam: str) -> dict:
    return json.loads((DATA / f"{naam}.json").read_text(encoding="utf-8"))


PUBLICATIES = [_laad(n) for n in ("wp-22819", "wp-4785", "wp-586", "wp-8488")]
BERICHTEN = [_laad("bericht-22821")]


class _Antwoord:
    def __init__(self, data, totaal: int, paginas: int):
        self._data = data
        self.headers = {"X-WP-Total": str(totaal), "X-WP-TotalPages": str(paginas)}

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._data


class _Sessie:
    """Een nepbron: per soort een lijst items, in pagina's van `per`."""

    def __init__(self, soorten: dict[str, list[dict]], per: int = 2, totaal: dict[str, int] | None = None):
        self.soorten, self.per, self.totaal, self.urls = soorten, per, totaal or {}, []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        assert headers and "wetsanalyse" in headers["User-Agent"]
        assert url.startswith(kg.API)
        soort = url.split("/wp/v2/", 1)[1].split("?", 1)[0]
        from urllib.parse import parse_qs, urlsplit
        pagina = int(parse_qs(urlsplit(url).query)["page"][0])
        items = self.soorten[soort]
        paginas = max(1, -(-len(items) // self.per))
        return _Antwoord(items[(pagina - 1) * self.per: pagina * self.per], self.totaal.get(soort, len(items)), paginas)


def test_alles_ophalen_over_paginas_met_een_pauze():
    sessie, pauzes = _Sessie({"wt_publication": PUBLICATIES}), []
    opgehaald = kgi.haal_alles(sessie, slaap=pauzes.append)
    assert [p["id"] for p in opgehaald.items] == [p["id"] for p in PUBLICATIES] and opgehaald.totaal == 4
    assert len(sessie.urls) == 2 and pauzes == [kgi.PAUZE_S]


def test_onvolledig_is_een_fout_en_geen_lege_index():
    sessie = _Sessie({"wt_publication": PUBLICATIES}, totaal={"wt_publication": 5})
    with pytest.raises(kgi.KennisgroepenFout, match="de bron noemt er 5"):
        kgi.haal_alles(sessie, slaap=lambda _: None)


def test_de_index_staat_los_van_de_wet():
    g, uit = kgi.bouw_graph(PUBLICATIES, BERICHTEN)
    assert (uit.standpunten, uit.berichten) == (4, 1) and uit.per_status == {"geldend": 2, "ingetrokken": 1, "vervallen": 1}
    for s, p, o in g:
        assert not str(s).startswith(DEFAULT_BASE_IRI), s
        assert not str(p).startswith(DEFAULT_ONTOLOGY_IRI), p
        assert not (isinstance(o, URIRef) and str(o).startswith((DEFAULT_BASE_IRI, DEFAULT_ONTOLOGY_IRI))), o
    # Een subject draagt geen kenmerk, anders herkent `bronmodel.extern` de IRI als een standpunt.
    from bronmodel.extern import externe_verwijzingen
    assert not any(externe_verwijzingen(str(s)) for s in g.subjects())


def test_idempotent():
    assert inhoud_hash(kgi.bouw_graph(PUBLICATIES, BERICHTEN)[0]) == inhoud_hash(kgi.bouw_graph(PUBLICATIES, BERICHTEN)[0])


def _waarden(g, s, p) -> set[str]:
    return {str(o) for o in g.objects(URIRef(s), kgi.KGO[p])}


def test_alle_metadata_staat_in_de_index():
    g, _ = kgi.bouw_graph(PUBLICATIES, BERICHTEN)
    s = kg.subject_iri(22819)
    assert _waarden(g, s, "id") == {"kg:013:2026:4"} and _waarden(g, s, "status") == {"geldend"}
    assert _waarden(g, s, "kennisgroep") == {"KG Auto (A)"} and _waarden(g, s, "kennisgroepId") == {"155"}
    assert _waarden(g, s, "middel") == {"Autobelastingen"} and _waarden(g, s, "subrubriek") == {"Waarde"}
    assert _waarden(g, s, "datum") == {"2026-11-12"} and _waarden(g, s, "bronHash")
    assert _waarden(g, s, "vervangtId") == {"kg:013:2018:173"}
    assert len(_waarden(g, s, "rij")) == len(kg.lees_publicatie(PUBLICATIES[0]).rijen)
    # Het nieuwsbericht is een gebeurtenis bij de publicatie die het noemt.
    geb = next(iter(g.objects(URIRef(s), kgi.KGO.gebeurtenis)))
    assert str(next(g.objects(geb, kgi.KGO.gebeurtenissoort))) == "geactualiseerd"


def test_bepalingen_met_herkomst():
    g, uit = kgi.bouw_graph(PUBLICATIES, BERICHTEN)
    s = URIRef(kg.subject_iri(22819))
    rijen = {(str(g.value(n, kgi.KGO.bwbId)), str(g.value(n, kgi.KGO.artikel)), str(g.value(n, kgi.KGO.lid) or ""),
              str(g.value(n, kgi.KGO.herkomst)))
             for n in g.objects(s, kgi.KGO.noemt) if str(g.value(n, kgi.KGO.doelsoort)) == "bepaling"}
    # "artikel 10, eerste lid, Wet op de belasting van personenauto's en motorrijwielen 1992" staat alleen in de tekst.
    assert ("BWBR0005806", "10", "1", "tekst") in rijen
    assert uit.bepalingen >= len(rijen)
    s2 = URIRef(kg.subject_iri(8488))
    links = {(str(g.value(n, kgi.KGO.bwbId)), str(g.value(n, kgi.KGO.artikel)))
             for n in g.objects(s2, kgi.KGO.noemt) if str(g.value(n, kgi.KGO.herkomst)) == "link"
             and str(g.value(n, kgi.KGO.doelsoort)) == "bepaling"}
    assert ("BWBR0002471", "13") in links


@pytest.mark.parametrize("nieuw,bestaand,reden", [
    (1180, 0, ""), (1180, 1180, ""), (1150, 1180, ""), (1000, 1180, "zou krimpen"), (0, 0, "geen standpunten"),
])
def test_poortbesluit(nieuw, bestaand, reden):
    assert (reden in kgi.poortbesluit(nieuw, bestaand)) if reden else kgi.poortbesluit(nieuw, bestaand) == ""


class _Schrijver:
    def __init__(self, aantal: int = 0, fout: Exception | None = None):
        self._aantal, self._fout, self.geschreven = aantal, fout, []

    def aantal(self) -> int:
        if self._fout:
            raise self._fout
        return self._aantal

    def vervang(self, graph) -> None:
        self.geschreven.append(len(graph))


def test_verversen_schrijft_alleen_door_de_poort():
    bron = _Sessie({"wt_publication": PUBLICATIES, "posts": BERICHTEN})
    goed = _Schrijver(aantal=4)
    assert kgi.ververs(goed, bron, slaap=lambda _: None).geschreven and goed.geschreven
    krimp = _Schrijver(aantal=100)
    uit = kgi.ververs(krimp, _Sessie({"wt_publication": PUBLICATIES, "posts": BERICHTEN}), slaap=lambda _: None)
    assert not uit.geschreven and not krimp.geschreven and "krimpen" in uit.reden


def test_peiling_van_de_graafwacht():
    import requests
    assert kgi.index_is_compleet(_Schrijver(aantal=1180))
    assert not kgi.index_is_compleet(_Schrijver(aantal=0))
    assert not kgi.index_is_compleet(_Schrijver(fout=requests.ConnectionError("weg")))


@pytest.fixture
def nep_main(monkeypatch):
    stand = SimpleNamespace(wet_compleet=True, index=0, wetten=0, gepeild=[])

    def writer(settings):
        return SimpleNamespace(graaf_is_compleet=lambda ids: stand.gepeild.append(tuple(ids)) or stand.wet_compleet)

    monkeypatch.setattr(main_module, "maak_writer", writer)
    monkeypatch.setattr(main_module, "_wetten", lambda ids, settings: setattr(stand, "wetten", stand.wetten + 1) or 0)
    monkeypatch.setattr(main_module, "_kennisgroepen", lambda settings, verlies: stand.index)
    return stand


def test_de_graafwacht_peilt_alleen_de_wetten(nep_main):
    assert main_module.main(["BWBR0004770", "--alleen-bij-verlies", "--kennisgroepen"]) == 0
    assert nep_main.gepeild == [("BWBR0004770",)] and nep_main.wetten == 0


def test_de_index_houdt_de_wet_niet_tegen(nep_main):
    nep_main.wet_compleet, nep_main.index = False, 2
    assert main_module.main(["BWBR0004770", "--alleen-bij-verlies", "--kennisgroepen"]) == 2
    assert nep_main.wetten == 1
    nep_main.index = 1
    assert main_module.main(["BWBR0004770", "--kennisgroepen"]) == 1


def test_zonder_vlag_geen_index(nep_main, monkeypatch):
    monkeypatch.setattr(main_module, "_kennisgroepen", lambda *_: pytest.fail("index zonder --kennisgroepen"))
    nep_main.wet_compleet = False
    assert main_module.main(["BWBR0004770"]) == 0
