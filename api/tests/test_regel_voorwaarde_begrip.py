"""V6 (plan lessen Termijnen-bibliotheek): een voorwaarde die geen invoerbegrip noemt, en dezelfde voorwaarde in meer
regels. Twee gaten uit de skill (`regelgaten.json`), uitgerekend door `regel_store`; een signaal, geen poort."""
from __future__ import annotations

from app.regel_store import dragen_gaten, keten


def _inhoud(voorwaarde: dict, invoer=("in",), onderwerp="") -> dict:
    return {"soort": "beslisregel", "regelbegrip_id": "rb", "uitvoer_begrip_id": "uit", "onderwerp_begrip_id": onderwerp,
            "invoer": [{"begrip_id": i, "rol": "invoer"} for i in invoer],
            "gevallen": [{"label": "", "voorwaarden": {"verband": "alle", "delen": [voorwaarde]},
                          "uitkomst": [{"soort": "tekst", "tekst": "waar"}], "voorrang": 0}]}


def _codes(gaten: list[dict]) -> list[str]:
    return [g["code"] for g in gaten]


def test_een_voorwaarde_zonder_invoerbegrip_is_een_gat():
    v = {"tekst": "de aanslag is een voorlopige aanslag in de inkomstenbelasting", "element_ids": ["e1"]}
    # e1 draagt een begrip dat geen invoer is: de voorwaarde toetst iets wat een eigen begrip en regel hoort te zijn.
    gaten = dragen_gaten(_inhoud(v), {}, {}, {"e1": {"ander"}})
    assert _codes(gaten) == ["voorwaarde_zonder_begrip"]
    assert "voorlopige aanslag in de inkomstenbelasting" in gaten[0]["tekst"]
    # e1 draagt geen begrip: ook een gat.
    assert _codes(dragen_gaten(_inhoud(v), {}, {}, {})) == ["voorwaarde_zonder_begrip"]


def test_een_voorwaarde_op_een_invoer_of_het_onderwerp_is_geen_gat():
    v = {"tekst": "het bedrag is negatief", "element_ids": ["e1", "e2"]}
    assert dragen_gaten(_inhoud(v), {}, {}, {"e2": {"in"}}) == []
    assert dragen_gaten(_inhoud(v, invoer=(), onderwerp="ond"), {}, {}, {"e1": {"ond"}}) == []


def test_zonder_koppelgegevens_blijft_het_zoals_het_was():
    """Een aanroeper zonder `begrip_van` (oudere vorm) krijgt het nieuwe gat niet."""
    v = {"tekst": "x", "element_ids": ["e1"]}
    assert dragen_gaten(_inhoud(v), {}, {}) == []


def test_een_verwijzing_naar_een_geval_valt_erbuiten():
    v = {"tekst": "het aantal is bepaald volgens geval 1", "element_ids": ["e1"], "geval_van": {"regel_id": "r9", "geval": ""}}
    gaten = dragen_gaten(_inhoud(v), {}, {"r9": {"status": "concept", "uitvoer": "in", "labels": [""], "naam": "r"}}, {})
    assert "voorwaarde_zonder_begrip" not in _codes(gaten)


def _regel(rid: str, uitvoer: str, voorwaarde: dict) -> dict:
    inhoud = _inhoud(voorwaarde)
    inhoud.update({"uitvoer_begrip_id": uitvoer, "regelbegrip_id": f"rb-{rid}"})
    return {"id": rid, "naam": rid, "uitvoer": uitvoer, "status": "concept", "inhoud": inhoud, "begrippen": {}}


def test_dezelfde_voorwaarde_in_meer_regels_is_een_ketensignaal():
    v = {"tekst": "de dagtekening ligt in het jaar", "element_ids": ["e2", "e1"]}
    w = {"tekst": "dagtekening in het jaar", "element_ids": ["e1", "e2"]}
    sig = keten([_regel("r1", "a", v), _regel("r2", "b", w), _regel("r3", "c", {"tekst": "x", "element_ids": ["e3"]})])["signalen"]
    herhaald = [s for s in sig if s["soort"] == "voorwaarde_herhaald"]
    assert len(herhaald) == 1
    assert herhaald[0]["regel_ids"] == ["r1", "r2"] and herhaald[0]["element_ids"] == ["e1", "e2"]
    assert herhaald[0]["code"] == "voorwaarde_herhaald"
