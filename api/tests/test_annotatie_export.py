"""De export in vier vormen: dezelfde herkomst in dezelfde woorden, en niets kwijt van wat er al was."""
from __future__ import annotations

import csv
import io
import json
import re

import jsonschema
import pytest
from rdflib import Dataset
from rdflib.compare import isomorphic

from app import annotatie_export as export
from app import annotatie_v2_store as store
from app import db
from app.config import PROJECT_ROOT
from app.graaf_projectie_v2 import bouw_graaf, graph_iri, laag_invoer, verklaringen
from test_annotatie_v2 import ONE, TWO, element, request, snapshot

V = {
    "besluit": {"regel": {"naam": "vaste regel"}, "model": {"naam": "model"}, "specificiteit": {"naam": "specificiteit"}},
    "regels": {"jas.tijd.duur": {"naam": "Termijn"}, "JAS-PRIORITY-001": {"naam": "JAS-PRIORITY-001"}},
    "detectie": {"TEMPORAL_DURATION": {"naam": "Tijdsduur"}},
    "twijfel": {"DETECTOR_CONFLICT": {"naam": "Detectoren spreken elkaar tegen"}},
    "resolutie": {"R-CONFLICT-KEEP": {"naam": "Klasse behouden"}},
    "validatie": {"V_ANKER": {"naam": "Anker klopt niet"}},
}

SPOOR = {
    "pijplijn": "hybrid_v1", "jas_versie": "1.0",
    "kandidaat": {"id": "k1", "label": "k1", "mogelijke_klassen": ["Tijdsaanduiding", "Variabele en variabelewaarde"],
                  "gedegradeerd": True,
                  "bewijs": [{"detector": "temporeel", "code": "TEMPORAL_DURATION", "regel": "jas.tijd.duur"},
                             {"detector": "lexicaal", "code": "TEMPORAL_DURATION", "regel": "jas.tijd.duur"},
                             {"detector": "np", "code": "ONBEKEND"},
                             {"detector": "-", "code": "PRIORITY_APPLIED"}]},
    "beslissing": {"status": "ACCEPTED", "klasse": "Tijdsaanduiding", "door": "model"},
    "vraag": "k1 | binnen zes weken | Tijdsaanduiding, Variabele",
    "twijfel": [{"reden": "DETECTOR_CONFLICT", "alternatieven": ["Variabele en variabelewaarde"]}],
    "resolutie": [{"regel": "R-CONFLICT-KEEP"}],
    "validatie": [],
}
RUN = {"ronde": 1, "model": "claude-x", "provider": "p", "agent_versie": "a", "stop_reden": "", "tijd": "2026-10-05T10:00:00+00:00",
       "instellingen": {"meting": {"fasen": [{"fase": "Detectie", "samenvatting": "3 kandidaten", "ms": 1200},
                                             {"fase": "Resultaat", "samenvatting": "1 voorgesteld", "ms": 300}],
                                   "gedegradeerd": ["urn:x"]}}}


def _element(**extra) -> dict:
    basis = {"id": "e1", "eigenaar_iri": ONE, "laag_id": "l1", "klasse": "Tijdsaanduiding", "tekst": "binnen zes weken",
             "toelichting": "", "lifecycle": "voorgesteld", "herkomst": "agent", "snapshot_id": "s",
             "ankers": [{"bron_iri": ONE, "start": 0, "eind": 4, "tekst": "Alfa", "bron_hash": "h"}],
             "beslissingen": [{"type": "approve", "actor": "jan", "tijd": "2026-10-05T11:00:00", "comment": "", "wijziging": {}}],
             "trace": SPOOR, "jas_subtype": "", "aandacht": "groen", "geproduceerd_door": RUN}
    return {**basis, **extra}


def _view(elementen) -> dict:
    return {"schema_versie": 2, "doel": {"bron_iri": ONE, "label": "Lid 1"}, "snapshot_id": "s",
            "segmenten": [{"bron_iri": ONE, "tekst": "Alfa", "bron_hash": "h"}],
            "lagen": [{"id": "l1", "bron_iri": ONE, "revisie": 2, "status": "in_review"}],
            "elementen": elementen, "verwijzingen": [],
            "dekking": {"structureel": {ONE: {"dimensies": {"tijd": "uitgevoerd", "plaats": "overgeslagen"},
                                              "ongedekt": [{"tekst": "Alfa", "start": 0, "eind": 4}]}}},
            "audit": [{"id": 1, "actie": "batch", "actor": "lex", "tijdstip": "2026-10-05T10:00:00+00:00", "detail": {}}],
            "export": {"versie": 3, "actor": "jan", "op": "2026-10-05T12:00:00+00:00"}}


def test_herkomst_regels_in_leesbare_woorden():
    r = export.herkomst_regels(_element(), V)
    assert r["besloten_door"] == "model"
    # Twee detectoren met dezelfde regel: één keer; administratief bewijs valt weg; onbekend = de code.
    assert r["regels"] == ["Termijn", "ONBEKEND"]
    assert r["detectoren"] == ["temporeel", "lexicaal", "np"]
    assert r["twijfel"] == ["Detectoren spreken elkaar tegen"]
    assert r["resolutieregel"] == ["Klasse behouden"]
    assert r["gedegradeerd"] is True
    assert r["jurist"].startswith("akkoord bevonden door jan op ")


def test_herkomst_bij_specificiteit_en_zonder_spoor():
    spec = _element(trace={"beslissing": {"door": "specificiteit", "reden": "JAS-PRIORITY-001"}})
    assert export.herkomst_regels(spec, V)["besloten_door"] == "specificiteit (JAS-PRIORITY-001)"
    eigen = export.herkomst_regels(_element(trace=None, herkomst="mens", beslissingen=[], jas_subtype="parameter"), V)
    assert eigen["besloten_door"] == "" and eigen["regels"] == [] and eigen["subtype"] == "parameter"
    assert export.herkomst_zin(eigen).startswith("door een jurist zelf gemarkeerd")


def test_csv_houdt_de_oude_kolommen_voorop_en_maakt_formules_onschadelijk():
    view = _view([_element(), _element(id="e2", tekst="=SOM(A1)", trace=None, herkomst="mens")])
    rijen = list(csv.reader(io.StringIO(export.csv_export(view, V, lambda e: {}).decode("utf-8-sig"))))
    kop = rijen[0]
    assert kop[:12] == ["soort", "id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id", "ankers",
                        "beslissingen", "herkomst", "provenance", "laagstatus"]
    rij = dict(zip(kop, rijen[1]))
    assert rij["besloten_door"] == "model" and rij["regels"] == "Termijn; ONBEKEND"
    assert rij["gedegradeerd"] == "ja" and rij["aandacht"] == "groen"
    assert dict(zip(kop, rijen[2]))["tekst"] == "'=SOM(A1)"
    assert all(len(r) == len(kop) for r in rijen)


def test_json_v3_valideert_tegen_het_schema_en_ontdubbelt_de_runs():
    view = _view([_element(), _element(id="e2")])
    uit = json.loads(export.json_export(view, V))
    jsonschema.validate(uit, json.loads(export.SCHEMA_PAD.read_text(encoding="utf-8")))
    assert uit["export"]["versie"] == 3 and len(uit["runs"]) == 1
    assert uit["elementen"][0]["trace"]["vraag"].startswith("k1 |")
    assert uit["elementen"][0]["herkomst_regels"]["besloten_door"] == "model"


def test_pdf_draagt_herkomst_beurtmeting_en_dekking():
    view = _view([_element()])
    teksten = [t for _s, t in export.pdf_regels(view, V)]
    assert any(t.startswith("Herkomst: besloten door model; bewijs: Termijn, ONBEKEND") for t in teksten)
    assert any(t.startswith("Modelvraag: k1 |") for t in teksten)
    assert "Totaal: 1,5 s" in teksten
    assert any("1 van 2 dimensies volledig bekeken (plaats overgeslagen)" in t for t in teksten)
    # De beurtmeting staat er leesbaar in, niet meer als JSON-dump bij elk element.
    assert not any('"instellingen"' in t for t in teksten if t.startswith("Herkomst"))
    assert export.pdf_export(view, V).startswith(b"%PDF")


def test_de_export_leest_geen_sectie_die_de_werkplek_niet_ook_leest():
    v = verklaringen()
    assert all(isinstance(v.get(s), dict) and v[s] for s in export.GEBRUIKTE_SECTIES)
    ts = PROJECT_ROOT / "frontend" / "lib" / "verklaringen.ts"
    if not ts.exists():
        pytest.skip("frontend niet aanwezig")
    m = re.search(r"GEBRUIKTE_SECTIES[^=]*=\s*\[([^\]]*)\]", ts.read_text(encoding="utf-8"))
    assert set(export.GEBRUIKTE_SECTIES) == set(re.findall(r'"([a-z_]+)"', m.group(1)))


@pytest.fixture
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


async def test_trig_is_per_laag_wat_de_projectie_bouwt(database):
    from app.annotatie_v2 import _laaggrafen
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "lex")
    view = await store.weergave(snap)
    lagen = await _laaggrafen(view)
    ds = Dataset()
    ds.parse(data=export.trig_export(lagen).decode(), format="trig")
    assert {str(g.identifier) for g in ds.graphs() if len(g)} == {str(graph_iri(l["id"])) for l in view["lagen"]}
    async with store.leestransactie() as conn:
        for laag in view["lagen"]:
            rij = await store.laag_detail(laag["id"])
            elementen, dekking = await laag_invoer(conn, rij)
            assert isomorphic(ds.graph(graph_iri(laag["id"])), bouw_graaf(rij, elementen, dekking=dekking))
    assert not any(str(s).startswith("urn:bwb:") for g in ds.graphs() for s in g.subjects())


def test_een_terugval_heet_geen_besluit_van_het_model():
    el = _element(trace={**SPOOR, "beslissing": {"door": "terugval"}})
    v = {**V, "besluit": {**V["besluit"], "terugval": {"naam": "nog geen klasse gekozen"}}}
    r = export.herkomst_regels(el, v)
    assert r["terugval"] is True and r["besloten_door"] == "nog geen klasse gekozen"
    assert export.herkomst_zin(r).startswith("nog geen klasse gekozen – de jurist kiest uit de mogelijke klassen")
    # Geen klasse in de kop: de keuze staat erbij.
    pdf = [t for _s, t in export.pdf_regels(_view([_element(klasse="", trace={**SPOOR, "beslissing": {"door": "terugval"}},
                                                         alternatieven=[{"klasse": "Rechtsfeit"}, {"klasse": "Voorwaarde"}])]), v)]
    assert "Nog geen klasse (Rechtsfeit, Voorwaarde): binnen zes weken (voorgesteld)" in pdf
