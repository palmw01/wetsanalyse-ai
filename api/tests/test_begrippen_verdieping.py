"""De verdieping van de voorstellen (spoor D, fase C): batches, werkvoorraad, garanties en de uitkomst.

graph-qa rekent; hier staat wat de api tegenhoudt en bewaart. De garanties toetst hij zelf tegen het
manifest: een fragment dat niet letterlijk in de bron staat, komt er niet in.
"""
from __future__ import annotations

from app.begrippen_verdieping import SCHEIDING, fragment_id
from test_annotatie_v2 import ONE, TWO
from test_begrippen_runs import _annoteer, _groep, _start, _uitkomst, _werkgebied
from test_werkgebieden import client, database, graaf  # noqa: F401

GA, GM = "Ga1a1a1", "Gb2b2b2"


def _frag(iri: str, start: int, eind: int, tekst: str) -> dict:
    return {"id": fragment_id(iri, start, eind), "bron_iri": iri, "start": start, "eind": eind, "tekst": tekst}


ALFA = _frag(ONE, 2, 11, "Alfa Alfa")
BETA = _frag(TWO, 0, 4, "Beta")


def _kaart(gid: str, **extra) -> dict:
    return {"groep_id": gid, "naam": "alfa", "context": "Komt voor in Lid 1.", "begripstype": "actor",
            "begripstype_door": "regel", "aandacht": "geel", **extra}


async def _klaar(client):
    """Een klare run met één groep zonder definitie, een twijfelvraag en een vraag die de wet al beslist."""
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, [_groep(GA, [ids["alfa1"], ids["alfa2"]])], vragen=[
        {"kandidaat_id": "P1", "van": ids["alfa1"], "naar": ids["beta"], "regel": "Z-ANDERS"},
        {"kandidaat_id": "P2", "van": ids["alfa2"], "naar": ids["beta"], "regel": "Z-RELATIE-GAAT-VOOR"}])
    assert r.status_code == 200, r.text
    return ids, wg, run


def _pad(wg, run, *rest) -> str:
    return "/".join([f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}", *rest])


def _vraagbatch(oordeel="zelfde_betekenis", **extra) -> dict:
    return {"soort": "vraag", "ids": ["P1"], "model": "m", "promptversie": "v", "tokens": 900,
            "oordelen": [{"kandidaat_id": "P1", "oordeel": oordeel, "motivatie": "Beide alfa."}], **extra}


async def test_de_werkvoorraad_telt_twijfelvragen_en_kaarten(client):
    _, wg, _ = await _klaar(client)
    wv = (await client.get(f"/v1/werkgebieden/{wg['id']}/verdieping")).json()
    # P2 noemt de wet al als relatie: die gaat niet naar het model.
    assert (wv["vragen"], wv["kaarten"], wv["aantal"]) == (["P1"], [GA], 2)
    assert wv["schatting"] is None and "Nog geen verdieping" in wv["schatting_toelichting"]
    assert wv["verdiept"] is False and wv["budget"] is not None


async def test_zonder_voorstellen_niets_te_verdiepen(client):
    wg = await _werkgebied(client)
    wv = (await client.get(f"/v1/werkgebieden/{wg['id']}/verdieping")).json()
    assert wv["run"] is None and wv["aantal"] == 0


async def test_een_batch_is_idempotent_en_telt_af(client):
    _, wg, run = await _klaar(client)
    assert (await client.put(_pad(wg, run, "batches", "B1"), json=_vraagbatch())).status_code == 200
    assert (await client.put(_pad(wg, run, "batches", "B1"), json=_vraagbatch())).status_code == 200
    r = await client.put(_pad(wg, run, "batches", "B1"), json=_vraagbatch("onbeslist"))
    assert r.status_code == 409
    wv = (await client.get(f"/v1/werkgebieden/{wg['id']}/verdieping")).json()
    assert (wv["vragen"], wv["aantal"]) == ([], 1)
    assert [b["id"] for b in wv["batches"]] == ["B1"]
    assert wv["schatting"] == {"per_item": 900, "basis": 1, "totaal": 900}


async def test_een_batch_noemt_alleen_eigen_twijfelvragen(client):
    _, wg, run = await _klaar(client)
    for kid in ("P9", "P2"):
        batch = _vraagbatch(ids=[kid], oordelen=[{"kandidaat_id": kid, "oordeel": "onbeslist"}])
        assert (await client.put(_pad(wg, run, "batches", f"B{kid}"), json=batch)).status_code == 422


async def test_een_kaart_met_niet_letterlijke_tekst_komt_er_niet_in(client):
    _, wg, run = await _klaar(client)
    nep = {**ALFA, "tekst": "Alfa Beta"}
    batch = {"soort": "kaart", "ids": [GA], "model": "m", "promptversie": "v",
             "kaarten": [_kaart(GA, definitie="Alfa Beta", herkomst="samengesteld", fragmenten=[nep])]}
    r = await client.put(_pad(wg, run, "batches", "BK"), json=batch)
    assert r.status_code == 422 and r.json()["detail"]["kaarten"] == {GA: ["FRAGMENT_NIET_LETTERLIJK"]}
    verschoven = {**ALFA, "id": fragment_id(ONE, 2, 12)}
    batch["kaarten"] = [_kaart(GA, definitie="Alfa Alfa", herkomst="samengesteld", fragmenten=[verschoven])]
    assert (await client.put(_pad(wg, run, "batches", "BK"), json=batch)).json()["detail"]["kaarten"] == \
        {GA: ["FRAGMENT_ONBEKEND"]}
    batch["kaarten"] = [_kaart(GA, definitie="Alfa, en meer", herkomst="samengesteld", fragmenten=[ALFA])]
    assert (await client.put(_pad(wg, run, "batches", "BK"), json=batch)).json()["detail"]["kaarten"] == \
        {GA: ["SAMENGESTELD_NIET_UIT_FRAGMENTEN"]}
    wv = (await client.get(f"/v1/werkgebieden/{wg['id']}/verdieping")).json()
    assert wv["batches"] == []


async def _verdiep(client, ids, wg, run, **extra):
    leden = sorted([ids["alfa1"], ids["alfa2"], ids["beta"]])
    groep = {**_groep(GM, leden, naam="alfa"), "aandacht": "geel", "door": "model"}
    kaart = _kaart(GM, definitie=SCHEIDING.join([ALFA["tekst"], BETA["tekst"]]), herkomst="samengesteld",
                   fragmenten=[ALFA, BETA], motivatie="Alfa en Beta samen.", alternatieve_termen=["beta"])
    body = {"manifest_id": run["manifest_id"], "groepen": [groep], "kaarten": [kaart], "model": "m",
            "oordelen": [{"kandidaat_id": "P1", "oordeel": "zelfde_betekenis", "motivatie": "Beide alfa."}],
            "vragen": ["P2"], **extra}
    return await client.put(_pad(wg, run, "verdieping"), json=body)


async def test_de_verdieping_vervangt_de_groepen_en_draagt_kaart_en_oordelen(client):
    ids, wg, run = await _klaar(client)
    r = await _verdiep(client, ids, wg, run)
    assert r.status_code == 200, r.text
    assert (await _verdiep(client, ids, wg, run)).status_code == 200             # idempotent
    assert (await _verdiep(client, ids, wg, run, vragen=[])).status_code == 409  # andere inhoud
    g = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()
    [groep] = g["groepen"]
    assert (groep["id"], groep["door"], groep["aandacht"]) == (GM, "model", "geel")
    assert groep["kaart"]["herkomst"] == "samengesteld"
    assert g["verdieping"]["vragen_open"] == ["P2"] and g["verdieping"]["oordelen"]["P1"]["oordeel"] == "zelfde_betekenis"
    wv = (await client.get(f"/v1/werkgebieden/{wg['id']}/verdieping")).json()
    assert wv["verdiept"] and wv["aantal"] == 0
    # Na de verdieping geen batches meer.
    assert (await client.put(_pad(wg, run, "batches", "B2"), json=_vraagbatch())).status_code == 409


async def test_de_verdieping_toetst_elementen_vragen_en_kaarten(client):
    ids, wg, run = await _klaar(client)
    assert (await _verdiep(client, ids, wg, run, vragen=["P9"])).status_code == 422
    assert (await _verdiep(client, ids, wg, run, manifest_id="Manders")).status_code == 422
    vreemd = {**_groep(GM, ["onbekend", ids["beta"]]), "door": "model"}
    assert (await _verdiep(client, ids, wg, run, groepen=[vreemd])).status_code == 422


async def test_een_besloten_groep_van_de_keten_blijft_zichtbaar(client):
    ids, wg, run = await _klaar(client)
    await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/{GA}/afwijzen", json={"reden": "nee"})
    await _verdiep(client, ids, wg, run)
    g = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()
    assert {x["id"]: x["besluit"] for x in g["groepen"]} == {GM: "open", GA: "afgewezen"}


async def test_overnemen_vult_het_begrip_uit_de_kaart(client):
    ids, wg, run = await _klaar(client)
    await _verdiep(client, ids, wg, run)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/overnemen", json={"groep_ids": [GM], "naam": "alfa"})
    assert r.status_code == 201, r.text
    inhoud = r.json()["inhoud"]
    assert inhoud["definitie"] == "Alfa Alfa … Beta" and inhoud["definitie_herkomst"] == "samengesteld"
    assert inhoud["begripstype"] == "actor" and inhoud["alternatieve_termen"] == ["beta"]
    assert inhoud["context"] == "Komt voor in Lid 1."
    assert "“Alfa Alfa” (Artikel 9 · Lid 1 – Wet)" in inhoud["onderbouwing"]
    assert "Toelichting van Lex: Alfa en Beta samen." in inhoud["onderbouwing"]
