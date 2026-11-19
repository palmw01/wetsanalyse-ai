"""Het regelskelet: één berekening voor het rapport en de weergave, en de gaten met hun code uit de skill."""
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


def _codes(gaten):
    return [g["code"] for g in gaten]


def test_de_gaten_zeggen_wat_ontbreekt():
    alleen_object = [_rel("r1", "invoer", "aanslagbiljet", "regel", "Rechtsobject", AR)]
    gaten = regelskelet.gaten("regel", alleen_object)
    assert _codes(gaten) == ["uitvoer_ontbreekt", "rechtsobject_als_invoer"]
    assert gaten[0] == {"code": "uitvoer_ontbreekt", "plek": "skelet",
                        "tekst": "Er is geen uitvoer: welk begrip leidt deze regel af?"}
    twee = [_rel("u1", "uitvoer", "regel", "a", AR, "Variabele en variabelewaarde"),
            _rel("u2", "uitvoer", "regel", "b", AR, "Variabele en variabelewaarde"),
            _rel("i1", "invoer", "x", "regel", "Variabele en variabelewaarde", AR, volgorde=1),
            _rel("i2", "invoer", "y", "regel", "Variabele en variabelewaarde", AR)]
    gaten = regelskelet.gaten("regel", twee)
    assert _codes(gaten) == ["meer_uitvoeren", "invoer_zonder_volgorde"]
    assert gaten[1]["tekst"] == "1 van de 2 invoeren hebben geen volgorde."


def test_een_voorwaarde_bij_de_rechtsbetrekking_en_een_afwijking_zonder_uitzondering():
    """Termijnen, lid 5: de voorwaarde hing alleen aan de rechtsbetrekking, en "In afwijking van het eerste lid" had geen
    uitzondering_op. Een voorwaarde aan een andere regel is geen signaal; een uitzondering_op sluit het tweede gat."""
    basis = [_rel("u", "uitvoer", "regel", "a", AR, "Variabele en variabelewaarde"),
             _rel("i", "invoer", "x", "regel", "Variabele en variabelewaarde", AR, volgorde=1)]
    tekst = "In afwijking van het eerste lid is een voorlopige aanslag invorderbaar in zoveel termijnen als …"
    bij_rb = [*basis, _rel("v", "voorwaarde", "rb", "vw", "Rechtsbetrekking", "Voorwaarde")]
    assert _codes(regelskelet.gaten("regel", bij_rb, tekst)) == ["voorwaarde_bij_andere_drager",
                                                                 "afwijking_zonder_uitzondering"]
    bij_ar = [*basis, _rel("v", "voorwaarde", "andere", "vw", AR, "Voorwaarde"),
              _rel("x", "uitzondering_op", "regel", "lid1", AR, "Afleidingsregel")]
    assert regelskelet.gaten("regel", bij_ar, tekst) == []
    assert regelskelet.gaten("regel", basis, "Een aanslag is invorderbaar.") == []


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
    assert [g["code"] for g in r["gaten"]] == ["invoer_ontbreekt"]
