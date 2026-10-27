"""De onderzoeksstand van de begrippenketen (spoor M): welke context er naast het manifest komt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import begrip_onderzoek
from app.begrip_manifest import manifest_id

CASUS = json.loads((Path(__file__).resolve().parents[2] / "tools" / "graph-qa" / "eval"
                    / "betekenisonderzoek_casus.json").read_text())
A = "urn:bwb:BWBR0002320:artikel:30fb"
B = "urn:bwb:BWBR0002320:artikel:30fc"


def _snapshot(nodes=None) -> dict:
    nodes = nodes or CASUS["nodes"]
    return {"doel": {"citeertitel": "AWR"}, "nodes": nodes}


def _manifest(casus: str, nodes=None) -> tuple[dict, str]:
    per_iri = {n["bron_iri"]: n for n in (nodes or CASUS["nodes"])}
    fs = [{**f, "element_id": f"e{i}", "jas_subtype": "", "review_status": "voorgesteld"}
          for i, f in enumerate(CASUS["casus"][casus]["formuleringen"])]
    bronnen = [{"bron_iri": i, "tekst": per_iri[i]["tekst"], "bron_hash": per_iri[i]["bron_hash"], "label": i,
                "aanhef": "", "regeling": "BWBR0002320"} for i in sorted({f["bron_iri"] for f in fs})]
    m = {"bronnen": bronnen, "formuleringen": fs}
    return m, manifest_id(bronnen, fs)


def _werkgebied(casus: str, extra: list[dict] | None = None) -> dict:
    sel = [{**s, "bwb_id": "BWBR0002320"} for s in CASUS["casus"][casus]["selecties"]] + (extra or [])
    return {"id": "wg", "bronnen": sel}


async def _geen_verwijzingen(iris):
    return []


async def _resolve_niets(doel):
    from fastapi import HTTPException
    raise HTTPException(503, "weg")


async def _bouw(casus="A", werkgebied=None, nodes=None, verwijzingen=_geen_verwijzingen, resolve=_resolve_niets,
                begrippen=None):
    m, mid = _manifest(casus, nodes)
    return await begrip_onderzoek.bouw(werkgebied or _werkgebied(casus), m, mid, {"BWBR0002320": _snapshot(nodes)},
                                       resolve, verwijzingen=verwijzingen, begrippen=begrippen or [])


async def test_casus_a_onderzoekt_de_andere_leden_van_het_artikel():
    uit = await _bouw("A")
    bronnen = uit["onderzoek"]["bronnen"]
    leden = [b["bron_iri"] for b in bronnen if b["reden"] == "zelfde_artikel"]
    # Leden 1–3 en 5–8, in documentvolgorde; lid 4 is een manifestbron en komt er nooit in.
    assert leden == [f"{A}:lid:{n}" for n in (1, 2, 3, 5, 6, 7, 8)]
    assert all(b["rol"] == "onderzoek" and b["voor"] == ["e0", "e1"] for b in bronnen)
    assert all(b["label"].startswith("Artikel 30fb · Lid") for b in bronnen)
    assert uit["onderzoek"]["ontbrekend"] == []


async def test_casus_b_vindt_de_kwalificatie_in_lid_7():
    uit = await _bouw("B")
    per_iri = {b["bron_iri"]: b for b in uit["onderzoek"]["bronnen"]}
    # Lid 7 komt als lid van hetzelfde artikel binnen (de eerste reden wint); dat het ook een
    # kwalificatie is, leest de keten zelf uit de tekst.
    assert per_iri[f"{B}:lid:7"]["reden"] == "zelfde_artikel"
    assert {f"{B}:lid:7:o:a", f"{B}:lid:7:o:b", f"{B}:lid:7:o:c"} <= set(per_iri)
    assert f"{B}:lid:1" not in per_iri and f"{B}:lid:2" not in per_iri


async def test_een_definitie_elders_in_de_regeling_komt_mee_als_ze_de_formulering_bevat():
    # Casus A met alleen lid 4: de kwalificatie in 30fc lid 7 bevat "belastingrente" niet, maar een
    # ingevoegde definitie met "herziening" wel.
    nodes = [*CASUS["nodes"], {"bron_iri": "urn:bwb:BWBR0002320:artikel:1", "parent_iri": "urn:bwb:BWBR0002320",
                               "type": "Artikel", "label": "Artikel 1", "volgorde": 99, "bwb_id": "BWBR0002320",
                               "tekst": "In deze wet wordt verstaan onder herziening: de wijziging van een aanslag.",
                               "bron_hash": "h1"}]
    uit = await _bouw("A", nodes=nodes)
    definitie = [b for b in uit["onderzoek"]["bronnen"] if b["reden"] == "definitie_in_regeling"]
    assert [b["bron_iri"] for b in definitie] == ["urn:bwb:BWBR0002320:artikel:1"]
    assert definitie[0]["voor"] == ["e0"]


async def test_verwijzingen_buiten_de_graaf_staan_als_ontbrekend():
    async def verwijzingen(iris):
        assert iris == [f"{A}:lid:4"]
        return [(f"{A}:lid:4", "urn:bwb:BWBR0004770:artikel:9")]

    uit = await _bouw("A", verwijzingen=verwijzingen)
    assert {"wat": "urn:bwb:BWBR0004770:artikel:9", "reden": "niet_in_graaf"} in uit["onderzoek"]["ontbrekend"]


async def test_een_verwijzing_naar_een_andere_regeling_haalt_die_regeling_erbij():
    iw = "urn:bwb:BWBR0004770"
    nodes = [{"bron_iri": iw, "parent_iri": "", "type": "Regeling", "label": "IW", "tekst": ""},
             {"bron_iri": iw + ":artikel:9", "parent_iri": iw, "type": "Artikel", "label": "Artikel 9", "tekst": ""},
             {"bron_iri": iw + ":artikel:9:lid:1", "parent_iri": iw + ":artikel:9", "type": "Lid", "label": "Lid 1",
              "tekst": "Een belastingaanslag is invorderbaar twee maanden na dagtekening."}]
    for i, n in enumerate(nodes):
        n.update(bron_hash=f"h{i}", volgorde=i, bwb_id="BWBR0004770")

    async def resolve(doel):
        assert doel["bron_iri"] == iw + ":artikel:9"
        return {"doel": {"citeertitel": "IW 1990"}, "nodes": nodes}

    async def verwijzingen(iris):
        return [(f"{A}:lid:4", iw + ":artikel:9")]

    uit = await _bouw("A", verwijzingen=verwijzingen, resolve=resolve)
    via = [b for b in uit["onderzoek"]["bronnen"] if b["reden"] == "verwijzing"]
    assert [b["bron_iri"] for b in via] == [iw + ":artikel:9:lid:1"]
    assert via[0]["regeling"] == "BWBR0004770" and via[0]["label"] == "Artikel 9 · Lid 1 – IW 1990"


async def test_een_onbereikbare_graaf_is_geen_fout_maar_staat_als_ontbrekend():
    async def weg(iris):
        return None

    uit = await _bouw("A", verwijzingen=weg)
    assert {"wat": "verwijzingen vanaf de passages", "reden": "onbereikbaar"} in uit["onderzoek"]["ontbrekend"]
    assert uit["onderzoek"]["bronnen"]                        # de rest is er gewoon


async def test_een_contextselectie_zonder_annotaties_komt_mee_met_haar_rol():
    wg = _werkgebied("A", [{"bron_iri": B, "rol": "context", "bereik": "onderliggend", "bwb_id": "BWBR0002320"}])
    uit = await _bouw("A", werkgebied=wg)
    context = [b for b in uit["onderzoek"]["bronnen"] if b["reden"] == "contextselectie"]
    assert context and all(b["rol"] == "context" and b["bron_iri"].startswith(B) for b in context)
    assert len(context) == begrip_onderzoek.MAX_CONTEXTSELECTIE
    # De rest van de selectie past niet in het budget: niet stil weg, maar `budget`.
    assert any(o["reden"] == "budget" and o["wat"].startswith(B) for o in uit["onderzoek"]["ontbrekend"])


async def test_het_budget_per_reden_en_in_totaal(monkeypatch):
    monkeypatch.setattr(begrip_onderzoek, "MAX_ZELFDE_ARTIKEL", 3)
    monkeypatch.setitem(begrip_onderzoek._PER_REDEN, "zelfde_artikel", 3)
    uit = await _bouw("A")
    assert [b["bron_iri"] for b in uit["onderzoek"]["bronnen"]] == [f"{A}:lid:{n}" for n in (1, 2, 3)]
    assert [o["wat"] for o in uit["onderzoek"]["ontbrekend"]] == [f"{A}:lid:{n}" for n in (5, 6, 7, 8)]
    monkeypatch.setattr(begrip_onderzoek, "MAX_TEKENS", 1000)
    uit = await _bouw("A")
    assert sum(len(b["tekst"]) for b in uit["onderzoek"]["bronnen"]) <= 1000


async def test_het_id_volgt_uit_de_inhoud():
    een, twee = await _bouw("A"), await _bouw("A")
    assert een == twee and een["onderzoek_id"].startswith("O")
    # Een ander lid ernaast (nieuwe wettekst) geeft een ander id; het manifest blijft gelijk.
    nodes = [dict(n) for n in CASUS["nodes"]]
    lid5 = next(n for n in nodes if n["bron_iri"] == f"{A}:lid:5")
    lid5.update(tekst=lid5["tekst"] + " Nieuw.", bron_hash="anders")
    drie = await _bouw("A", nodes=nodes)
    assert drie["onderzoek"]["manifest_id"] == een["onderzoek"]["manifest_id"]
    assert drie["onderzoek_id"] != een["onderzoek_id"]
    # Een vergelijkingsbegrip telt mee: het komt in de prompt.
    vier = await _bouw("A", begrippen=[{"id": "b1", "naam": "herziening", "definitie": "x", "status": "concept",
                                        "werkgebied_id": "wg", "eigen": True}])
    assert vier["onderzoek_id"] != een["onderzoek_id"]


@pytest.mark.parametrize("veld", ["bron_iri", "tekst", "bron_hash", "label", "aanhef", "regeling", "rol", "reden", "voor"])
async def test_een_contextbron_draagt_de_velden_van_het_model(veld):
    uit = await _bouw("A")
    assert all(veld in b for b in uit["onderzoek"]["bronnen"])


ONDERZOEK = json.loads((Path(__file__).resolve().parents[2] / "docs" / "wetsanalyse" / "referentieset-begrippen"
                        / "onderzoek-id.vectoren.json").read_text())


@pytest.mark.parametrize("vector", ONDERZOEK["vectoren"], ids=lambda v: v["naam"])
def test_het_onderzoek_id_rekent_zoals_de_keten(vector):
    o = vector["onderzoek"]
    assert begrip_onderzoek.onderzoek_id(o["manifest_id"], o["bronnen"], o["begrippen"]) == vector["onderzoek_id"]


async def test_de_vorm_van_het_onderzoek_is_die_van_de_keten():
    uit = (await _bouw("A", begrippen=[{"id": "b1", "naam": "x", "definitie": "", "status": "concept",
                                        "werkgebied_id": "wg", "eigen": True}]))["onderzoek"]
    assert sorted(uit) == ONDERZOEK["velden"]["onderzoek"]
    assert all(sorted(b) == ONDERZOEK["velden"]["contextbron"] for b in uit["bronnen"])
    assert all(sorted(b) == ONDERZOEK["velden"]["begrip"] for b in uit["begrippen"])


# --- de garanties en de duiding (M2) --------------------------------------------------------------

def test_een_fragment_uit_een_contextbron_doorstaat_de_garanties():
    from app.begrippen_run_contracts import KaartFragment
    from app.begrippen_verdieping import fragment_fouten, fragment_id, fragmentruimte
    m, mid = _manifest("A")
    lid1 = next(n for n in CASUS["nodes"] if n["bron_iri"] == f"{A}:lid:1")
    tekst = "Bij herziening van een voorlopige aanslag"
    fid = fragment_id(lid1["bron_iri"], 0, len(tekst))
    fr = KaartFragment(id=fid, bron_iri=lid1["bron_iri"], start=0, eind=len(tekst), tekst=tekst)
    assert fragment_fouten(m, [fr]) == ["FRAGMENT_ONBEKEND"]
    onderzoek = {"bronnen": [{"bron_iri": lid1["bron_iri"], "tekst": lid1["tekst"]}]}
    assert fragment_fouten(fragmentruimte(m, onderzoek), [fr]) == []
    assert fragmentruimte(m, None) is m


def test_een_definitievoorstel_draagt_zijn_duiding():
    from app.begrip_voorstel_contracts import VoorstelInvoer
    from app.begrip_voorstel_store import _waarde
    v = VoorstelInvoer.model_validate({
        "veld": "definitie", "aandacht": "geel",
        "definitie": {"definitie": "x", "herkomst": "letterlijk", "definitie_bron_iri": "urn:bwb:BWBR1:artikel:1"},
        "duiding": {"soort": "toepassingsgeval", "bereik": "specifiek", "voorkeursterm": "herziening naar positief"}})
    assert _waarde(v)["duiding"] == {"soort": "toepassingsgeval", "bereik": "specifiek",
                                     "voorkeursterm": "herziening naar positief", "ontbreekt": ""}
    with pytest.raises(ValueError):
        VoorstelInvoer.model_validate({"veld": "definitie", "definitie": {"definitie": "x", "herkomst": "letterlijk",
                                       "definitie_bron_iri": "u"}, "duiding": {"soort": "verzonnen"}})
