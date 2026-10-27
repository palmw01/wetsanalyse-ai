"""Lex naast de kaart (spoor D, fase E): voorstellen per veld. Acceptatie: niets wordt stil
overschreven; herkomst gaat mee."""
from __future__ import annotations

import csv
import io

from app.begrippen_verdieping import fragment_id
from test_annotatie_v2 import ART, ONE
from test_begrippen_akkoord import LID1, _akkoord, _alfa, _keur_goed, _voorstel
from test_begrippen_runs import _annoteer, _werkgebied
from test_werkgebieden import ART2, _bron, _nieuw, client, database, graaf, snapshot2  # noqa: F401


def _fragment(start=2, eind=6, tekst="Alfa", bron=ONE) -> dict:
    return {"id": fragment_id(bron, start, eind), "bron_iri": bron, "start": start, "eind": eind, "tekst": tekst}


def _geformuleerd(tekst="iemand die als eerste genoemd wordt", **extra) -> dict:
    return {"veld": "definitie", "definitie": {"definitie": tekst, "herkomst": "geformuleerd",
                                               "fragmenten": [_fragment()]},
            "motivatie": "Uit lid 1.", "aandacht": "geel", "aandachtspunten": ["DOOR_LEX_GEFORMULEERD"], **extra}


async def _begrip(client, wg, naam="Alfa", **inhoud) -> dict:
    ids = await _annoteer()
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": naam, **inhoud}, "element_ids": [ids["alfa1"], ids["alfa2"]]})
    assert r.status_code == 201, r.text
    return r.json()


def _pad(wg, b) -> str:
    return f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}"


async def _run(client, wg, b, actie="scherper", status=None, **body) -> dict:
    r = await client.post(f"{_pad(wg, b)}/kaart-runs", json={"actie": actie, **body})
    if status:
        assert r.status_code == status, r.text
    return r.json()


async def _uitkomst(client, wg, b, run, voorstellen, **extra):
    return await client.put(f"{_pad(wg, b)}/kaart-runs/{run['id']}/uitkomst",
                            json={"invoer_id": run["invoer_id"], "voorstellen": voorstellen, "model": "m",
                                  "promptversie": "p1", "tokens": 1200, **extra})


async def _met_voorstel(client, voorstellen=None, actie="scherper", **inhoud):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, **inhoud)
    run = await _run(client, wg, b, actie, 201)
    r = await _uitkomst(client, wg, b, run, voorstellen if voorstellen is not None else [_geformuleerd()])
    assert r.status_code == 200, r.text
    return wg, b, run, r.json()["voorstellen"]


async def _neem_over(client, wg, b, v, revisie=None, **body):
    return await client.post(f"{_pad(wg, b)}/voorstellen/{v['id']}/overnemen",
                             json={"verwachte_revisie": revisie or b["revisie"], **body})


async def test_de_invoer_draagt_het_begrip_de_passages_en_het_manifest(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    run = await _run(client, wg, b, status=201)
    assert (run["status"], run["basis_revisie"], run["nieuw"]) == ("wacht", 1, True)
    tweede = await _run(client, wg, b, status=200)
    assert tweede["id"] == run["id"]
    invoer = (await client.get(f"{_pad(wg, b)}/kaart-runs/{run['id']}", params={"invoer": True})).json()["invoer"]
    assert set(invoer["leden"]) == {k["element_id"] for k in b["koppelingen"]}
    assert invoer["begrip"]["inhoud"]["naam"] == "Alfa" and invoer["ander"] is None
    assert {x["rol"] for x in invoer["selecties"]} == {"analyseren", "context"}
    assert any(x["bron_iri"] == ONE for x in invoer["manifest"]["bronnen"])


async def test_overnemen_zet_definitie_herkomst_en_revisie(client):
    wg, b, run, [v] = await _met_voorstel(client)
    assert (v["status"], v["veld"], v["verouderd"], v["door"]["bron"]) == ("open", "definitie", False, "model")
    r = await _neem_over(client, wg, b, v)
    assert r.status_code == 200, r.text
    nb = r.json()
    i = nb["inhoud"]
    assert (i["definitie"], i["definitie_herkomst"], i["definitie_door"]) == (
        "iemand die als eerste genoemd wordt", "geformuleerd", "lex")
    assert "onderbouwing" not in i
    assert nb["revisie"] == 2
    [laatste, *_] = (await client.get(f"{_pad(wg, b)}/revisies")).json()["revisies"]
    assert (laatste["actie"], laatste["detail"]["voorstel_id"], laatste["detail"]["door"]["model"]) == (
        "voorstel-overgenomen", v["id"], "m")
    [v2] = (await client.get(f"{_pad(wg, b)}/voorstellen")).json()["voorstellen"]
    assert (v2["status"], v2["besloten_door"], v2["begrip_revisie"]) == ("overgenomen", "jurist-a", 2)
    # Een tweede keer overnemen: het besluit staat al.
    r = await _neem_over(client, wg, b, v, revisie=2)
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "al_besloten"


async def test_een_veranderde_definitie_wordt_niet_stil_overschreven(client):
    wg, b, run, [v] = await _met_voorstel(client)
    r = await client.patch(_pad(wg, b), json={"verwachte_revisie": 1, "inhoud": {
        "naam": "Alfa", "definitie": "eigen tekst", "definitie_herkomst": "geformuleerd"}})
    assert r.status_code == 200, r.text
    assert r.json()["inhoud"]["definitie_door"] == "analist"
    [v] = (await client.get(f"{_pad(wg, b)}/voorstellen")).json()["voorstellen"]
    assert v["verouderd"] is True and v["nu"]["definitie"] == "eigen tekst"
    r = await _neem_over(client, wg, b, v, revisie=2)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert (d["fout"], d["toen"]["definitie"], d["nu"]["definitie"], d["voorstel"]["definitie"]) == (
        "voorstel_verouderd", "", "eigen tekst", "iemand die als eerste genoemd wordt")
    nu = (await client.get(_pad(wg, b))).json()
    assert (nu["revisie"], nu["inhoud"]["definitie"]) == (2, "eigen tekst")
    # Vervangen kan alleen bewust: met de definitie die de analist naast het voorstel zag.
    r = await _neem_over(client, wg, b, v, revisie=2, nu_gezien="andere tekst")
    assert r.status_code == 409
    r = await _neem_over(client, wg, b, v, revisie=2, nu_gezien="eigen tekst")
    assert r.status_code == 200 and r.json()["inhoud"]["definitie"] == "iemand die als eerste genoemd wordt"


async def test_een_412_als_de_kaart_een_oude_revisie_had(client):
    wg, b, run, [v] = await _met_voorstel(client)
    await client.patch(_pad(wg, b), json={"verwachte_revisie": 1, "inhoud": {"naam": "Alfa", "context": "Ergens"}})
    r = await _neem_over(client, wg, b, v, revisie=1)
    assert r.status_code == 412
    # Met de nieuwe revisie mag het wel: de context raakt de definitie niet.
    r = await _neem_over(client, wg, b, v, revisie=2)
    assert r.status_code == 200 and r.json()["inhoud"]["context"] == "Ergens"


async def test_aanpassen_maakt_de_definitie_van_de_analist(client):
    wg, b, run, [v] = await _met_voorstel(client)
    r = await _neem_over(client, wg, b, v, aanpassing="de eerste persoon in lid 1")
    i = r.json()["inhoud"]
    assert (i["definitie"], i["definitie_herkomst"], i["definitie_door"]) == (
        "de eerste persoon in lid 1", "geformuleerd", "analist")
    [v] = (await client.get(f"{_pad(wg, b)}/voorstellen")).json()["voorstellen"]
    assert v["status"] == "aangepast"


async def test_herkomst_blijft_lex_tot_de_analist_de_tekst_raakt(client):
    wg, b, run, [v] = await _met_voorstel(client)
    nb = (await _neem_over(client, wg, b, v)).json()
    inhoud = {**nb["inhoud"], "context": "Elders", "definitie_door": "analist"}   # wat de client zegt telt niet
    nb = (await client.patch(_pad(wg, b), json={"verwachte_revisie": 2, "inhoud": inhoud})).json()
    assert nb["inhoud"]["definitie_door"] == "lex"
    inhoud = {**nb["inhoud"], "definitie": "anders"}
    nb = (await client.patch(_pad(wg, b), json={"verwachte_revisie": 3, "inhoud": inhoud})).json()
    assert nb["inhoud"]["definitie_door"] == "analist"
    inhoud = {**nb["inhoud"], "definitie": "", "definitie_herkomst": None}
    nb = (await client.patch(_pad(wg, b), json={"verwachte_revisie": 4, "inhoud": inhoud})).json()
    assert nb["inhoud"]["definitie_door"] == ""


async def test_zelf_maken_met_definitie_is_van_de_analist(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, definitie="zelf", definitie_herkomst="geformuleerd", definitie_door="lex")
    assert b["inhoud"]["definitie_door"] == "analist"


async def test_de_garanties_toetst_de_api_zelf(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    run = await _run(client, wg, b, status=201)
    nep = {**_fragment(), "tekst": "Beta"}
    r = await _uitkomst(client, wg, b, run, [_geformuleerd(definitie={
        "definitie": "x", "herkomst": "geformuleerd", "fragmenten": [nep]})])
    assert r.status_code == 422 and r.json()["detail"]["voorstellen"] == {"0": ["FRAGMENT_NIET_LETTERLIJK"]}
    r = await _uitkomst(client, wg, b, run, [{"veld": "uitleg", "tekst": "Iets"}])
    assert r.status_code == 422 and r.json()["detail"]["voorstellen"] == {"0": ["VELD_HOORT_NIET_BIJ_ACTIE"]}
    r = await _uitkomst(client, wg, b, run, [_geformuleerd(aandacht="groen")])
    assert r.status_code == 422                                     # geformuleerd is nooit groen
    r = await _uitkomst(client, wg, b, run, [{"veld": "definitie", "definitie": {
        "definitie": "Alfa … Alfa", "herkomst": "samengesteld", "fragmenten": [_fragment()]}}])
    assert r.status_code == 422 and r.json()["detail"]["voorstellen"] == {"0": ["SAMENGESTELD_NIET_UIT_FRAGMENTEN"]}
    r = await _uitkomst(client, wg, b, {**run, "invoer_id": "ander"}, [])
    assert r.status_code == 422
    # Niets bewaard, de run kan nog.
    assert (await client.get(f"{_pad(wg, b)}/voorstellen")).json()["voorstellen"] == []


async def test_dezelfde_uitkomst_nog_eens_is_idempotent(client):
    wg, b, run, _ = await _met_voorstel(client)
    r = await _uitkomst(client, wg, b, run, [_geformuleerd()])
    assert r.status_code == 200 and len(r.json()["voorstellen"]) == 1
    r = await _uitkomst(client, wg, b, run, [_geformuleerd("iets anders")])
    assert r.status_code == 409


async def test_een_brondefinitie_buiten_het_werkgebied_toetst_de_api_tegen_de_graaf(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    b = await _begrip(client, wg)
    run = await _run(client, wg, b, "brondefinitie", 201)

    def bron(tekst):
        return {"veld": "definitie", "aandacht": "groen", "definitie": {
            "definitie": tekst, "herkomst": "letterlijk", "definitie_bron_iri": ART2,
            "definitie_vindplaats": "Artikel 2 – AWR", "vindplaats_soort": "definitieverwijzing"}}
    r = await _uitkomst(client, wg, b, run, [bron("Die wet")])
    assert r.status_code == 422 and r.json()["detail"]["voorstellen"] == {"0": ["LETTERLIJK_NIET_IN_BRON"]}
    r = await _uitkomst(client, wg, b, run, [bron("Deze wet")])
    assert r.status_code == 200, r.text
    [v] = r.json()["voorstellen"]
    assert v["door"]["bron"] == "graaf"
    i = (await _neem_over(client, wg, b, v)).json()["inhoud"]
    assert (i["definitie"], i["definitie_herkomst"], i["definitie_door"]) == ("Deze wet", "letterlijk", "lex")


async def test_een_lege_uitkomst_draagt_haar_melding(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    run = await _run(client, wg, b, "brondefinitie", 201)
    r = await _uitkomst(client, wg, b, run, [], melding="Geen brondefinitie gevonden.")
    assert r.status_code == 200
    stand = r.json()
    assert stand["voorstellen"] == []
    assert (stand["runs"]["brondefinitie"]["status"], stand["runs"]["brondefinitie"]["melding"]) == (
        "klaar", "Geen brondefinitie gevonden.")
    # Zonder open voorstellen start een nieuwe klik een nieuwe run.
    assert (await _run(client, wg, b, "brondefinitie", 201))["id"] != run["id"]


async def test_voorbeelden_worden_toegevoegd_nooit_vervangen(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    r = await client.post(f"{_pad(wg, b)}/kaart-runs", json={"actie": "voorbeelden"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "geen_definitie"
    b = (await client.patch(_pad(wg, b), json={"verwachte_revisie": 1, "inhoud": {
        "naam": "Alfa", "definitie": "de eerste", "definitie_herkomst": "geformuleerd",
        "voorbeelden": [{"tekst": "eigen", "oordeel": "wel"}]}})).json()
    run = await _run(client, wg, b, "voorbeelden", 201)
    vbs = [{"veld": "voorbeelden", "tekst": "A is de eerste", "oordeel": "wel", "toelichting": "past"},
           {"veld": "voorbeelden", "tekst": "B komt later", "oordeel": "niet"}]
    v1, v2 = (await _uitkomst(client, wg, b, run, vbs)).json()["voorstellen"]
    assert "verouderd" not in v1
    b = (await _neem_over(client, wg, b, v1)).json()
    b = (await _neem_over(client, wg, b, v2, oordeel="onzeker")).json()
    assert [(x["tekst"], x["oordeel"]) for x in b["inhoud"]["voorbeelden"]] == [
        ("eigen", "wel"), ("A is de eerste", "wel"), ("B komt later", "onzeker")]
    statussen = {x["id"]: x["status"] for x in (await client.get(f"{_pad(wg, b)}/voorstellen")).json()["voorstellen"]}
    assert (statussen[v1["id"]], statussen[v2["id"]]) == ("overgenomen", "aangepast")


async def test_betekenisverschil_met_een_ander_begrip(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    beta = (await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen", json={"inhoud": {"naam": "Beta"}})).json()
    assert (await client.post(f"{_pad(wg, b)}/kaart-runs", json={"actie": "betekenisverschil"})).status_code == 422
    assert (await client.post(f"{_pad(wg, b)}/kaart-runs", json={
        "actie": "betekenisverschil", "ander_begrip_id": b["id"]})).status_code == 422
    run = await _run(client, wg, b, "betekenisverschil", 201, ander_begrip_id=beta["id"])
    assert run["ander_begrip_id"] == beta["id"]
    uit, vraag = (await _uitkomst(client, wg, b, run, [
        {"veld": "uitleg", "tekst": "Alfa is iets anders dan Beta.", "vergelijking": "verschil", "fragmenten": [_fragment()]},
        {"veld": "context", "tekst": "Beta valt er niet onder."}])).json()["voorstellen"]
    assert uit["waarde"]["vergelijking"] == "verschil"
    b = (await _neem_over(client, wg, b, uit)).json()
    b = (await _neem_over(client, wg, b, vraag)).json()
    assert (b["inhoud"]["uitleg"], b["inhoud"]["context"]) == ("Alfa is iets anders dan Beta.", "Beta valt er niet onder.")


async def test_afwijzen_laat_het_begrip_staan(client):
    wg, b, run, [v] = await _met_voorstel(client)
    r = await client.post(f"{_pad(wg, b)}/voorstellen/{v['id']}/afwijzen", json={"reden": "te ruim"})
    [v] = r.json()["voorstellen"]
    assert (v["status"], v["reden"]) == ("afgewezen", "te ruim")
    assert (await client.get(_pad(wg, b))).json()["revisie"] == 1
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
    assert any(x["actie"] == "voorstel-afgewezen" and x["detail"]["reden"] == "te ruim" for x in audit)


async def test_overnemen_maakt_een_geaccordeerd_begrip_weer_concept(client):
    ids, wg, _ = await _voorstel(client, lambda ids: _alfa(ids, definitie="Alfa Alfa", definitie_vindplaats=LID1))
    await _keur_goed(ids["alfa1"], ids["alfa2"])
    b = (await _akkoord(client, wg, groep_ids=["Gaaa111"])).json()["begrip"]
    # Het akkoord op een voorstel van Lex legt ook vast dat de definitie van Lex komt.
    assert (b["status"], b["inhoud"]["definitie_door"]) == ("geaccordeerd", "lex")
    run = await _run(client, wg, b, status=201)
    [v] = (await _uitkomst(client, wg, b, run, [_geformuleerd()])).json()["voorstellen"]
    assert v["basis"]["definitie"] == "Alfa Alfa"
    nb = (await _neem_over(client, wg, b, v)).json()
    assert (nb["status"], nb["inhoud"]["definitie"]) == ("concept", "iemand die als eerste genoemd wordt")


async def test_loopt_en_mislukt(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    run = await _run(client, wg, b, status=201)
    assert (await client.post(f"{_pad(wg, b)}/kaart-runs/{run['id']}/loopt")).json()["status"] == "loopt"
    r = await client.post(f"{_pad(wg, b)}/kaart-runs/{run['id']}/mislukt", json={"reden": "model weg"})
    assert (r.json()["status"], r.json()["reden"]) == ("mislukt", "model weg")
    assert (await _run(client, wg, b, status=201))["id"] != run["id"]


async def test_schatting_en_budget_bij_de_voorstellen(client):
    wg, b, _, _ = await _met_voorstel(client)
    stand = (await client.get(f"{_pad(wg, b)}/voorstellen")).json()
    assert stand["schatting"] == {"scherper": {"tokens": 1200, "basis": 1}}
    assert set(stand["budget"]) == {"resterend", "budget", "actief", "geblokkeerd"}


async def test_de_export_noemt_wie_de_definitie_voorstelde(client):
    wg, b, run, [v] = await _met_voorstel(client)
    await _neem_over(client, wg, b, v)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "csv"})
    rijen = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert {x["definitie_door"] for x in rijen} == {"lex"}
