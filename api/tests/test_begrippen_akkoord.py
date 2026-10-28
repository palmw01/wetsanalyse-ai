"""Akkoord op een voorstel van Lex (spoor D, fase D): uit een voorstel in één handeling een begrip met
beoordeelde koppelingen, geaccordeerd als de poort het toelaat – zonder leeg formulier."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import annotatie_v2_store as store, begrip_projectie, begrip_store, begrippen_run_store, db
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import ART, ONE, snapshot
from test_begrippen_runs import _annoteer, _groep, _start, _uitkomst, _werkgebied
from test_werkgebieden import client, database, graaf, snapshot2  # noqa: F401

LID1 = "Artikel 9 · Lid 1 – Wet"


async def _keur_goed(*element_ids: str) -> None:
    """Een jurist keurt de annotaties goed (de poort vraagt dat voor dragende passages)."""
    for eid in element_ids:
        d = await store.detail(eid)
        iri = d["element"]["eigenaar_iri"]
        snap = snapshot() if iri.startswith(ART) else snapshot2()
        await store.beslis(eid, Beslissing(type="approve", snapshot_id=d["snapshot_id"],
                                           verwachte_revisies={iri: d["laag"]["revisie"]}), snap, "jurist")


async def _voorstel(client, groepen, **extra):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    r = await _uitkomst(client, wg, run, groepen(ids), **extra)
    assert r.status_code == 200, r.text
    return ids, wg, run


def _alfa(ids, **extra):
    return [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]], **extra)]


async def _akkoord(client, wg, **body):
    return await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/akkoord", json={"naam": "Alfa", **body})


async def _groepen(client, wg) -> dict:
    return {g["id"]: g for g in (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"]}


async def test_akkoord_accordeert_meteen_als_de_poort_het_toelaat(client):
    ids, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1))
    await _keur_goed(ids["alfa1"], ids["alfa2"])
    g = (await _groepen(client, wg))["Gaaa111"]
    assert g["poort_vooraf"] == {"mag": True, "redenen": []}
    assert all(x["annotatie_beoordeeld"] for x in g["leden"])

    r = await _akkoord(client, wg, groep_ids=["Gaaa111"])
    assert r.status_code == 201, r.text
    uit = r.json()
    b = uit["begrip"]
    assert (uit["geaccordeerd"], b["status"], b["revisie"]) == (True, "geaccordeerd", 2)
    assert b["inhoud"]["definitie_herkomst"] == "letterlijk"
    # Zonder kaart: de context komt uit de vindplaatsen, zoals de concept-kaart hem zou schrijven.
    assert b["inhoud"]["context"] == f"Komt voor in {LID1}. Wettelijke definitie in {LID1}."
    assert {k["beoordeling"] for k in b["koppelingen"]} == {"akkoord"}
    assert all(k["beoordeeld_door"] == b["aangemaakt_door"] for k in b["koppelingen"])
    g = (await _groepen(client, wg))["Gaaa111"]
    assert (g["besluit"], g["begrip_id"], g["poort_vooraf"]) == ("overgenomen", b["id"], None)
    regels = [x for x in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
              if x["actie"] == "groep-akkoord"]
    assert len(regels) == 1 and regels[0]["detail"]["geaccordeerd"] is True


async def test_de_letterlijke_definitie_van_een_groep_houdt_haar_onderbouwing(client):
    """Spoor M: ook langs het akkoord op een groep blijft zichtbaar waarop de definitie rust, en de
    projectie maakt de bron een `dct:source` met de rol definitieonderbouwing."""
    ids, wg, run = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1,
                                                              definitie_bron_iri=ONE))
    await _keur_goed(ids["alfa1"], ids["alfa2"])
    b = (await _akkoord(client, wg, groep_ids=["Gaaa111"])).json()["begrip"]
    assert b["status"] == "geaccordeerd"                     # accorderen raakt de definitie niet
    o = b["definitie_onderbouwing"]
    assert (o["groep_id"], o["run_id"], o["herkomst"]) == ("Gaaa111", run["id"], "letterlijk")
    assert (o["definitie_bron_iri"], o["definitie_vindplaats"], o["fragmenten"]) == (ONE, LID1, [])
    async with db.get_engine().connect() as conn:
        inv = await begrip_projectie.invoer(conn, wg["id"])
    assert next(x for x in inv["begrippen"] if x["id"] == b["id"])["onderbouwing"] == [ONE]


async def test_een_aangepaste_definitie_heeft_geen_onderbouwing_van_lex(client):
    _, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1,
                                                          definitie_bron_iri=ONE))
    b = (await _akkoord(client, wg, groep_ids=["Gaaa111"], aanpassing={"definitie": "Een eigen definitie."})).json()
    assert b["begrip"]["definitie_onderbouwing"] is None
    # Een andere aanpassing laat de definitie, en dus haar onderbouwing, staan.
    _, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1,
                                                          definitie_bron_iri=ONE))
    b = (await _akkoord(client, wg, groep_ids=["Gaaa111"], aanpassing={"context": "Eigen toelichting."})).json()
    assert b["begrip"]["definitie_onderbouwing"]["definitie_bron_iri"] == ONE


async def test_onbeoordeelde_annotaties_laten_een_concept_achter_dat_later_kan(client):
    ids, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1))
    g = (await _groepen(client, wg))["Gaaa111"]
    assert g["poort_vooraf"]["mag"] is False
    assert g["poort_vooraf"]["redenen"] == ["2 dragende annotaties zijn nog niet door een jurist beoordeeld."]

    uit = (await _akkoord(client, wg, groep_ids=["Gaaa111"])).json()
    assert (uit["geaccordeerd"], uit["begrip"]["status"]) == (False, "concept")
    assert uit["poort"]["redenen"] == g["poort_vooraf"]["redenen"]
    # De jurist keurt de annotaties goed ("Annotatie akkoord"), daarna lukt accorderen.
    await _keur_goed(ids["alfa1"], ids["alfa2"])
    b = uit["begrip"]
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}/accorderen",
                          json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "geaccordeerd"


async def test_zonder_definitie_een_concept_en_met_eigen_definitie_geformuleerd(client):
    ids, wg, _ = await _voorstel(client, _alfa)
    await _keur_goed(ids["alfa1"], ids["alfa2"])
    assert (await _groepen(client, wg))["Gaaa111"]["poort_vooraf"]["redenen"][:1] == ["Er is nog geen definitie."]
    uit = (await _akkoord(client, wg, groep_ids=["Gaaa111"], element_ids=[ids["alfa1"]],
                          aanpassing={"definitie": "de eerste van twee"})).json()
    b = uit["begrip"]
    assert uit["geaccordeerd"] is True
    assert (b["inhoud"]["definitie"], b["inhoud"]["definitie_herkomst"]) == ("de eerste van twee", "geformuleerd")
    # Splitsen: de andere passage blijft als voorstel staan.
    g = (await _groepen(client, wg))["Gaaa111"]
    assert (g["besluit"], [x["element_id"] for x in g["leden"]], g["afgehandeld"]) == ("open", [ids["alfa2"]], 1)


async def test_een_aangepaste_letterlijke_definitie_is_niet_meer_letterlijk(client):
    _, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1))
    # Letterlijk kiezen bestaat niet meer (spoor I1): wat de client meestuurt, telt niet.
    r = await _akkoord(client, wg, groep_ids=["Gaaa111"], aanpassing={
        "definitie": "Alfa en meer", "definitie_herkomst": "letterlijk", "context": "Eigen"})
    assert r.status_code == 201, r.text
    inhoud = r.json()["begrip"]["inhoud"]
    assert (inhoud["definitie_herkomst"], inhoud["definitie_door"], inhoud["context"]) == (
        "geformuleerd", "analist", "Eigen")
    assert "onderbouwing" not in inhoud


async def test_een_ongewijzigde_brondefinitie_blijft_letterlijk(client):
    _, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1))
    r = await _akkoord(client, wg, groep_ids=["Gaaa111"], aanpassing={"definitie": "Alfa Alfa"})
    assert r.status_code == 201, r.text
    assert r.json()["begrip"]["inhoud"]["definitie_herkomst"] == "letterlijk"


async def test_een_tweede_akkoord_noemt_het_begrip(client):
    _, wg, _ = await _voorstel(client, _alfa)
    eerste = (await _akkoord(client, wg, groep_ids=["Gaaa111"])).json()["begrip"]
    r = await _akkoord(client, wg, groep_ids=["Gaaa111"])
    assert r.status_code == 409
    assert r.json()["detail"]["begrippen"] == {"Gaaa111": eerste["id"]}


async def test_combineren_met_de_definitie_van_een_gekozen_groep(client):
    ids, wg, _ = await _voorstel(client, lambda ids: [
        _groep("Gaaa111", [ids["alfa1"], ids["alfa2"]], definitie="Alfa Alfa", definitie_vindplaats=LID1),
        _groep("Gbbb222", [ids["beta"], ids["awr"]], naam="beta", definitie="Beta", definitie_vindplaats="Lid 2")])
    base = {"groep_ids": ["Gaaa111", "Gbbb222"], "naam": "Samen"}
    assert (await _akkoord(client, wg, **base, definitie_van="Gccc333")).status_code == 422
    # Twee definities en geen keuze: er gaat er geen mee.
    r = await _akkoord(client, wg, **base, element_ids=[ids["alfa1"], ids["beta"]])
    assert r.json()["begrip"]["inhoud"].get("definitie", "") == ""
    r = await _akkoord(client, wg, **base, element_ids=[ids["alfa2"], ids["awr"]], definitie_van="Gbbb222")
    assert r.status_code == 201, r.text
    assert r.json()["begrip"]["inhoud"]["definitie"] == "Beta"
    assert {g["besluit"] for g in (await _groepen(client, wg)).values()} == {"overgenomen"}


async def test_samen_bij_een_twijfelvraag_beantwoordt_de_vraag(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, _alfa(ids), vragen=[{"kandidaat_id": "P1", "van": ids["alfa1"], "naar": ids["beta"]}])
    body = {"groep_ids": ["Gaaa111"], "element_ids": [ids["alfa1"], ids["alfa2"], ids["beta"]]}
    assert (await _akkoord(client, wg, **body, kandidaat_id="P9")).status_code == 404
    r = await _akkoord(client, wg, **body, kandidaat_id="P1")
    assert r.status_code == 201, r.text
    run = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}")).json()
    assert run["vragen_besluiten"]["P1"]["antwoord"] == "samen"


async def test_een_begrip_van_een_term_beantwoordt_al_zijn_vragen(client):
    """Spoor H4, de termpagina: één akkoord over de gekozen groepen zet elke twijfelvraag ertussen op
    *samen*; een vraag naar een passage buiten de keuze kan niet mee."""
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, _alfa(ids), vragen=[
        {"kandidaat_id": "P1", "van": ids["alfa1"], "naar": ids["beta"]},
        {"kandidaat_id": "P2", "van": ids["alfa2"], "naar": ids["beta"]},
        {"kandidaat_id": "P3", "van": ids["alfa1"], "naar": ids["awr"]}])
    body = {"groep_ids": ["Gaaa111"], "element_ids": [ids["alfa1"], ids["alfa2"], ids["beta"]]}
    r = await _akkoord(client, wg, **body, kandidaat_ids=["P1", "P3"])
    assert r.status_code == 422 and r.json()["detail"]["vragen"] == ["P3"]
    assert (await _akkoord(client, wg, **body, kandidaat_ids=["P9"])).status_code == 404
    r = await _akkoord(client, wg, **body, kandidaat_ids=["P1", "P2"])
    assert r.status_code == 201, r.text
    run = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}")).json()
    assert {k: v["antwoord"] for k, v in run["vragen_besluiten"].items()} == {"P1": "samen", "P2": "samen"}


async def test_een_fout_halverwege_laat_niets_achter(client, monkeypatch):
    _, wg, _ = await _voorstel(client, _alfa)

    async def stuk(*args, **kwargs):
        raise RuntimeError("stroomstoring")
    monkeypatch.setattr(begrip_store, "accordeer_in", stuk)
    with pytest.raises(RuntimeError):
        await _akkoord(client, wg, groep_ids=["Gaaa111"])
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()["begrippen"] == []
    g = (await _groepen(client, wg))["Gaaa111"]
    assert (g["besluit"], g["afgehandeld"]) == ("open", 0)


async def test_koppelen_vanuit_de_review_houdt_een_begrip_geaccordeerd(client):
    ids, wg, _ = await _voorstel(client, lambda ids: [
        _groep("Gaaa111", [ids["alfa1"], ids["alfa2"]], definitie="Alfa Alfa", definitie_vindplaats=LID1),
        _groep("Gbbb222", [ids["beta"], ids["awr"]], naam="beta")])
    await _keur_goed(ids["alfa1"], ids["alfa2"], ids["beta"])
    b = (await _akkoord(client, wg, groep_ids=["Gaaa111"])).json()["begrip"]
    assert b["status"] == "geaccordeerd"
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/Gbbb222/koppelen",
                          json={"begrip_id": b["id"], "element_ids": [ids["beta"]], "akkoord": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "geaccordeerd"
    assert {k["beoordeling"] for k in r.json()["koppelingen"]} == {"akkoord"}
    g = (await _groepen(client, wg))["Gbbb222"]
    assert (g["besluit"], [x["element_id"] for x in g["leden"]]) == ("open", [ids["awr"]])


def test_de_context_volgt_de_concept_kaart_van_graph_qa():
    """`context_uit` is de tweeling van graph-qa `kaart._context`: dezelfde zin, met of zonder kaart."""
    bron = (Path(__file__).resolve().parents[2] / "tools" / "graph-qa" / "agent" / "begrippen_pipeline"
            / "kaart.py").read_text()
    assert 'zin = "Komt voor in " + "; ".join(plekken) + "."' in bron
    assert re.search(r'zin \+= f" Wettelijke definitie in \{definitie_vindplaats\}\."', bron)
    manifest = {"formuleringen": [{"element_id": "a", "bron_iri": "x"}, {"element_id": "b", "bron_iri": "y"},
                                  {"element_id": "c", "bron_iri": "x"}],
                "bronnen": [{"bron_iri": "x", "label": "Lid 1"}, {"bron_iri": "y", "label": ""}]}
    assert begrippen_run_store.context_uit(manifest, ["a", "b", "c"], "Lid 3") == \
        "Komt voor in Lid 1; y. Wettelijke definitie in Lid 3."
