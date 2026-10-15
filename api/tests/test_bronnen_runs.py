"""Bronnen vinden met Lex (spoor D, fase A): runs, de uitkomst van graph-qa en de besluiten over
kandidaatbepalingen. De acceptatie van levering 1 staat hier: een uitgesloten kandidaat komt niet terug."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import update

from app import bronnen_run_store, db
from app.gesprek_contracts import Artefact
from test_annotatie_v2 import ART, ONE
from test_werkgebieden import ART2, _bron, _nieuw, client, database, graaf  # noqa: F401

LID3 = ART + ":lid:3"


async def _start(client, wg, status=None) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen-runs")
    if status:
        assert r.status_code == status, r.text
    return r.json()


def _k(iri: str, rol: str, *bewijs: tuple[str, str], label: str = "") -> dict:
    return {"bron_iri": iri, "label": label or iri.rsplit(":", 2)[-2] + " " + iri.rsplit(":", 1)[-1], "rol": rol,
            "bwb_id": iri.split(":")[2] if iri.startswith("urn:bwb:") else "", "bewijs": [{"methode": m, "vanuit": v, "detail": {}} for m, v in bewijs]}


async def _uitkomst(client, wg, run, kandidaten, **extra):
    return await client.put(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run['id']}/uitkomst",
                            json={"invoer_id": run["invoer_id"], "kandidaten": kandidaten, **extra})


async def _lijst(client, wg) -> dict:
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")
    assert r.status_code == 200, r.text
    return {k["bron_iri"]: k for k in r.json()["kandidaten"]}


async def _haal(client, wg) -> dict:
    return (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()


# --- runs ------------------------------------------------------------------------------------------

async def test_de_invoer_is_de_selectie_en_de_analysevraag(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = (await _bron(client, wg, bron_iri=ART2, rol="context"))["werkgebied"]
    run = await _start(client, wg, 201)
    run = (await client.get(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run['id']}", params={"invoer": True})).json()
    assert [b["bron_iri"] for b in run["invoer"]["kern"]] == [ART]
    assert [b["bron_iri"] for b in run["invoer"]["context"]] == [ART2]
    assert run["invoer"]["analysevraag"] == "Wanneer?" and run["status"] == "wacht"


async def test_zonder_vertrekpunt_geen_run(client):
    r = await client.post("/v1/werkgebieden", json={"naam": "Leeg"})
    wg = r.json()
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen-runs")
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "geen_vertrekpunt"


async def test_dezelfde_selectie_dezelfde_run_een_andere_selectie_een_nieuwe(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    a = await _start(client, wg, 201)
    b = await _start(client, wg, 200)
    assert (a["id"], b["nieuw"]) == (b["id"], False)
    laatste = (await client.get(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/laatste")).json()["run"]
    assert laatste["id"] == a["id"] and laatste["verouderd"] is False
    wg = (await _bron(client, wg, bron_iri=ART2, rol="context"))["werkgebied"]
    laatste = (await client.get(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/laatste")).json()["run"]
    assert laatste["verouderd"] is True
    assert (await _start(client, wg, 201))["id"] != a["id"]
    # Een vastgelopen run mag opnieuw.
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.bronnen_runs).values(gewijzigd=db.utcnow() - timedelta(minutes=10)))
    assert (await _start(client, wg, 201))["nieuw"] is True


# --- de uitkomst ------------------------------------------------------------------------------------

async def test_meer_methoden_een_kandidaat_met_de_sterkste_rol(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    run = await _start(client, wg)
    r = await _uitkomst(client, wg, run, [
        _k(ART2, "aanverwant", ("opbouw", ART)),
        _k(ART2, "afhankelijkheid", ("verwijzing_uit", ONE)),
        _k(ART, "kern", ("overzicht", "")),                       # staat al in de selectie: geen kandidaat
    ], meting={"opbouw": {"aantal": 1}, "verwijzing_uit": {"aantal": 1, "volledig": False}})
    assert r.status_code == 200 and r.json()["status"] == "klaar", r.text
    assert r.json()["meting"]["verwijzing_uit"]["volledig"] is False
    lijst = await _lijst(client, wg)
    assert set(lijst) == {ART2}
    k = lijst[ART2]
    assert k["rol"] == "afhankelijkheid" and k["status"] == "voorgesteld" and k["in_laatste_run"]
    assert [b["methode"] for b in k["bewijs"]] == ["opbouw", "verwijzing_uit"]
    assert k["id"] == bronnen_run_store.kandidaat_id(ART2)


async def test_de_uitkomst_wordt_getoetst_en_is_idempotent(client):
    wg = await _nieuw(client)
    run = await _start(client, wg)
    goed = [_k(ART2, "kern", ("overzicht", ""))]
    r = await client.put(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run['id']}/uitkomst",
                         json={"invoer_id": "Ianders", "kandidaten": goed})
    assert r.status_code == 422
    assert (await _uitkomst(client, wg, run, [_k("https://elders.example/x", "kern", ("overzicht", ""))])).status_code == 422
    assert (await _uitkomst(client, wg, run, [{**goed[0], "bewijs": [{"methode": "gok"}]}])).status_code == 422
    assert (await _uitkomst(client, wg, run, goed)).status_code == 200
    assert (await _uitkomst(client, wg, run, goed)).status_code == 200            # nog eens: hetzelfde
    assert (await _uitkomst(client, wg, run, [_k(LID3, "kern", ("overzicht", ""))])).status_code == 409


# --- besluiten ----------------------------------------------------------------------------------

async def _met_kandidaten(client):
    wg = await _nieuw(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_k(ART2, "afhankelijkheid", ("definitie", "")),
                                      _k(ART, "kern", ("overzicht", "")),
                                      _k(LID3, "aanverwant", ("gelijkenis", ""))])
    return wg, await _lijst(client, wg)


async def test_een_uitgesloten_kandidaat_komt_niet_terug(client):
    wg, lijst = await _met_kandidaten(client)
    pad = f"/v1/werkgebieden/{wg['id']}/kandidaten/{lijst[ART2]['id']}"
    assert (await client.post(f"{pad}/uitsluiten", json={"reden": ""})).status_code == 422
    r = await client.post(f"{pad}/uitsluiten", json={"reden": "Buiten de analysevraag"})
    assert r.status_code == 200 and r.json()["status"] == "uitgesloten" and r.json()["besloten_door"] == "jurist-a"
    # Een nieuwe run (andere analysevraag) vindt hem opnieuw, met nieuw bewijs: het besluit blijft staan.
    await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": wg["revisie"], "analysevraag": "Hoe?"})
    run = await _start(client, await _haal(client, wg), 201)
    await _uitkomst(client, wg, run, [_k(ART2, "kern", ("overzicht", ""), ("verwijzing_in", ONE))])
    k = (await _lijst(client, wg))[ART2]
    assert k["status"] == "uitgesloten" and k["reden"] == "Buiten de analysevraag"
    assert k["in_laatste_run"] and k["rol"] == "kern" and len(k["bewijs"]) == 2
    # Heropenen kan; dan is hij weer een voorstel.
    assert (await client.post(f"{pad}/heropenen")).json()["status"] == "voorgesteld"


async def test_later_en_heropenen(client):
    wg, lijst = await _met_kandidaten(client)
    pad = f"/v1/werkgebieden/{wg['id']}/kandidaten/{lijst[LID3]['id']}"
    assert (await client.post(f"{pad}/later")).json()["status"] == "later"
    assert (await client.post(f"{pad}/later")).status_code == 409
    assert (await client.post(f"{pad}/heropenen")).json()["status"] == "voorgesteld"
    assert (await client.post(f"{pad}/heropenen")).status_code == 409
    assert (await client.post(f"/v1/werkgebieden/{wg['id']}/kandidaten/Konbekend/later")).status_code == 404


async def test_opnemen_maakt_een_bronselectie_met_de_rol_van_de_kandidaat(client):
    wg, lijst = await _met_kandidaten(client)
    wg = await _haal(client, wg)
    pad = f"/v1/werkgebieden/{wg['id']}/kandidaten"
    # Een verouderde revisie: 412, en er gebeurt niets.
    r = await client.post(f"{pad}/{lijst[ART2]['id']}/opnemen", json={"verwachte_revisie": wg["revisie"] + 5})
    assert r.status_code == 412
    assert (await _lijst(client, wg))[ART2]["status"] == "voorgesteld"
    # Afhankelijkheid → context.
    r = await client.post(f"{pad}/{lijst[ART2]['id']}/opnemen", json={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    uit = r.json()
    assert uit["kandidaat"]["status"] == "opgenomen" and uit["selectie"]["rol"] == "context"
    assert uit["selectie"]["reden"] == "Voorgesteld door Lex (afhankelijkheid)."
    assert [b["bron_iri"] for b in uit["werkgebied"]["bronnen"]] == [ART2]
    # Kern → analyseren; de analist mag de rol overschrijven.
    r = await client.post(f"{pad}/{lijst[ART]['id']}/opnemen",
                          json={"verwachte_revisie": uit["werkgebied"]["revisie"], "rol": "context"})
    assert r.json()["selectie"]["rol"] == "context"
    # Opgenomen is geen open voorstel: niet heropenen, niet uitsluiten.
    assert (await client.post(f"{pad}/{lijst[ART2]['id']}/heropenen")).status_code == 409
    assert (await client.post(f"{pad}/{lijst[ART2]['id']}/uitsluiten", json={"reden": "x"})).status_code == 409
    acties = [a["actie"] for a in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert acties.count("kandidaat-opgenomen") == 2 and "bronnen-voorgesteld" in acties


async def test_uit_de_selectie_gehaald_wordt_weer_een_voorstel(client):
    wg, lijst = await _met_kandidaten(client)
    wg = await _haal(client, wg)
    uit = (await client.post(f"/v1/werkgebieden/{wg['id']}/kandidaten/{lijst[ART2]['id']}/opnemen",
                             json={"verwachte_revisie": wg["revisie"]})).json()
    # Zolang hij in de selectie staat, laat een nieuwe run hem opgenomen.
    run = await _start(client, uit["werkgebied"], 201)
    await _uitkomst(client, wg, run, [_k(ART2, "afhankelijkheid", ("definitie", ""))])
    assert (await _lijst(client, wg))[ART2]["status"] == "opgenomen"
    # Weggehaald: meteen weer een voorstel, met zijn bewijs – zonder nieuwe run.
    wg = await _haal(client, wg)
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}/bronnen/{uit['selectie']['id']}",
                            params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200
    k = (await _lijst(client, wg))[ART2]
    assert k["status"] == "voorgesteld" and k["besloten_door"] is None and k["bewijs"]


async def test_met_de_hand_opgenomen_staat_als_in_selectie(client):
    wg, lijst = await _met_kandidaten(client)
    await _bron(client, await _haal(client, wg), bron_iri=ART2, rol="context")
    assert (await _lijst(client, wg))[ART2]["in_selectie"] is True


def test_het_bronnenartefact_vraagt_werkgebied_en_run():
    a = Artefact(soort="bronnen", ref={"werkgebied_id": "w", "run_id": "r"}, titel="Invordering")
    assert a.soort == "bronnen"
    with pytest.raises(ValueError):
        Artefact(soort="bronnen", ref={"werkgebied_id": "w"})
