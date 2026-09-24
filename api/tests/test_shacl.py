"""SHACL op de v2-projectie (ADR-001 PR 14): conform, en elke mutatie op het juiste niveau."""
from __future__ import annotations

import re

import pytest
from rdflib import Literal, URIRef

from app.annotatie_contracts import Lifecycle
from app.graaf_projectie_v2 import JAS, OA, bouw_graaf, element_iri
from app.jas_klassen import JAS_KLASSEN_VOLGORDE
from app.shacl import SHAPES, valideer

pytest.importorskip("pyshacl")

BRON = "urn:bwb:BWBR0004770:artikel:9:lid:1"
LAAG = {"id": "laag-1", "revisie": 3, "status": "in_review", "bron_iri": BRON}
ANKER = {"bron_iri": BRON, "start": 37, "eind": 46, "tekst": "zes weken", "bron_hash": "a" * 64}
ELEMENT = {"id": "e1", "klasse": "Tijdsaanduiding", "lifecycle": "voorgesteld", "verouderd": False,
           "tekst": "zes weken", "toelichting": "termijn", "snapshot_id": "s", "ankers": [ANKER]}


def _graaf(**wijziging):
    anker = {**ANKER, **wijziging.pop("anker", {})}
    return bouw_graaf({**LAAG, **wijziging.pop("laag", {})}, [{**ELEMENT, "ankers": [anker], **wijziging}])


def test_een_geldige_projectie_is_conform():
    r = valideer(_graaf())
    assert r == {"beschikbaar": True, "conform": True, "rdf": [], "jas_model": []}


@pytest.mark.parametrize("graaf_kw,niveau", [
    ({"klasse": "Termijn"}, "jas_model"),
    ({"lifecycle": "goedgekeurd"}, "jas_model"),
    ({"anker": {"bron_iri": "https://example.org/wet"}}, "jas_model"),
    ({"anker": {"bron_hash": "fnv1a32"}}, "jas_model"),
    ({"laag": {"status": "klaar"}}, "jas_model"),
    ({"anker": {"start": 46, "eind": 37}}, "rdf"),
    ({"tekst": ""}, "rdf"),
])
def test_elke_mutatie_landt_op_het_juiste_niveau(graaf_kw, niveau):
    r = valideer(_graaf(**graaf_kw))
    assert r["conform"] is False and r[niveau], r


def test_een_subject_onder_urn_bwb_is_een_jas_modelfout():
    g = _graaf()
    g.add((URIRef(BRON), JAS.tekst, Literal("vervuilde wettekst")))
    r = valideer(g)
    assert r["conform"] is False and any("urn:bwb" in f["melding"] for f in r["jas_model"])


def test_een_markering_zonder_anker_is_een_rdf_fout():
    g = _graaf()
    for doel in list(g.objects(element_iri("e1"), OA.hasTarget)):
        g.remove((element_iri("e1"), OA.hasTarget, doel))
    r = valideer(g)
    assert r["conform"] is False and r["rdf"]


def test_de_klassenlijst_in_de_shapes_loopt_mee_met_de_api():
    tekst = SHAPES.read_text(encoding="utf-8")
    blok = re.search(r"sh:path jas:klasseNaam.*?sh:in \((.*?)\)", tekst, re.S).group(1)
    assert re.findall(r'"([^"]+)"', blok) == list(JAS_KLASSEN_VOLGORDE)
    blok = re.search(r"sh:path jas:lifecycle.*?sh:in \((.*?)\)", tekst, re.S).group(1)
    assert set(re.findall(r'"([^"]+)"', blok)) == {l.value for l in Lifecycle}


def test_zonder_pyshacl_valt_de_diagnose_niet_om(monkeypatch):
    import builtins
    echte = builtins.__import__

    def geen_pyshacl(naam, *a, **kw):
        if naam == "pyshacl":
            raise ImportError
        return echte(naam, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", geen_pyshacl)
    assert valideer(_graaf())["beschikbaar"] is False
