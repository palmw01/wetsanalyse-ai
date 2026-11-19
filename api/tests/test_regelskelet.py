"""Het regelskelet: één berekening voor het rapport en de weergave, en de gaten in woorden."""
from __future__ import annotations

from app import regelskelet


def _rel(id_, type_, van, naar, klasse_van="", klasse_naar="", volgorde=None, lifecycle="human_approved"):
    return {"id": id_, "type": type_, "volgorde": volgorde, "lifecycle": lifecycle,
            "van": {"soort": "element", "id": van, "klasse": klasse_van, "tekst": van},
            "naar": {"soort": "element", "id": naar, "klasse": klasse_naar, "tekst": naar}}


AR = "Afleidingsregel"


def test_een_compleet_skelet_heeft_geen_gaten_en_de_invoer_op_volgorde():
    rel = [_rel("r1", "uitvoer", "regel", "aantal", AR, "Variabele en variabelewaarde"),
           _rel("r3", "invoer", "dagtekening", "regel", "Tijdsaanduiding", AR, volgorde=2),
           _rel("r2", "invoer", "jaar", "regel", "Tijdsaanduiding", AR, volgorde=1)]
    k = regelskelet.opbouw("regel", rel, regelskelet._kort)
    assert [d["id"] for d in k["invoer"]] == ["jaar", "dagtekening"]
    assert [d["id"] for d in k["uitvoer"]] == ["aantal"]
    assert regelskelet.gaten("regel", rel) == []


def test_de_gaten_zeggen_wat_ontbreekt():
    alleen_object = [_rel("r1", "invoer", "aanslagbiljet", "regel", "Rechtsobject", AR)]
    assert regelskelet.gaten("regel", alleen_object) == [
        "Er is geen uitvoer: welk begrip leidt deze regel af?",
        "De invoer is alleen een rechtsobject; een regel rekent met een waarde ervan (een variabele, parameter of "
        "tijdsaanduiding, met een relatie kenmerk naar het object)."]
    twee = [_rel("u1", "uitvoer", "regel", "a", AR, "Variabele en variabelewaarde"),
            _rel("u2", "uitvoer", "regel", "b", AR, "Variabele en variabelewaarde"),
            _rel("i1", "invoer", "x", "regel", "Variabele en variabelewaarde", AR, volgorde=1),
            _rel("i2", "invoer", "y", "regel", "Variabele en variabelewaarde", AR)]
    assert regelskelet.gaten("regel", twee) == ["Er zijn 2 uitvoeren; een afleidingsregel heeft er precies één.",
                                                 "1 van de 2 invoeren hebben geen volgorde."]


def test_de_weergave_laat_afgewezen_relaties_weg():
    view = {"schema_versie": 2, "doel": {"bron_iri": "b"}, "snapshot_id": "s",
            "lagen": [{"id": "L", "bron_iri": "b", "revisie": 3, "status": "in_review", "updated": "x"}],
            "elementen": [{"id": "regel", "klasse": AR, "tekst": "zoveel termijnen als", "lifecycle": "human_approved",
                           "laag_id": "L"},
                          {"id": "aantal", "klasse": "Variabele en variabelewaarde", "tekst": "termijnen",
                           "lifecycle": "human_approved", "laag_id": "L"}],
            "relaties": [_rel("r1", "uitvoer", "regel", "aantal", AR, "Variabele en variabelewaarde"),
                         _rel("r2", "invoer", "aanslagbiljet", "regel", "Rechtsobject", AR, lifecycle="rejected")]}
    w = regelskelet.weergave(view)
    assert w["vorm"] == "skelet" and w["lagen"] == [{"id": "L", "bron_iri": "b", "revisie": 3, "status": "in_review"}]
    [r] = w["regels"]
    assert [d["id"] for d in r["uitvoer"]] == ["aantal"] and r["invoer"] == []
    assert r["gaten"] == ["Er is geen invoer."]
