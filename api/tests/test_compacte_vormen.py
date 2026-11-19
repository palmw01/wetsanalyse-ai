"""Compacte vormen voor agents en de acceptatie-MCP (B-1, verslag E2E Rekeningafspraken 16 nov 2026).

Bij één annotatie van twaalf bepalingen werden de antwoorden te groot voor een agent:
- een besluit in de bronselectie gaf de hele selectie van alle deelvragen terug, rond 15k tokens;
- `GET …/kandidaten?deelvraag_id=` filterde niet;
- de weergave van één lid was 105k tekens;
- een wijziging aan een begrip gaf de hele kaart terug.

Elke compacte vorm is opt-in. Zonder parameter blijft het antwoord zoals het was: de werkplek en graph-qa lezen dat.
"""
from __future__ import annotations

from app import annotatie_v2_store as store
from gedeelde_bron import ART, ONE, TWO, element, request, snapshot
from test_begrippen import DEFINITIE, _begrip, _url, _werkgebied
from test_bronselectie import _besluit, _dq, _kd, _kid, _met_kandidaten, _overzicht, _vier
from gedeelde_bron import ART2, client, database, graaf  # noqa: F401


async def test_een_besluit_met_vorm_deelvraag_geeft_alleen_die_deelvraag_volledig(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0], ids[2]])])
    ov = await _overzicht(client, wg)
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[0]}/kandidaten/{kid}",
                          params={"vorm": "deelvraag"},
                          json={"besluit": "opnemen", "verwachte_revisie": ov["revisie"], "rol": "analyseren"})
    assert r.status_code == 200, r.text
    kort = r.json()
    assert kort["vorm"] == "deelvraag"
    eerste = _dq(kort, ids[0])
    assert [b["bron_iri"] for b in eerste["bronnen"]] == [ART] and eerste["kandidaten"]
    # De andere deelvragen staan er met hun stand, zonder lijsten.
    for did in ids[1:]:
        dq = _dq(kort, did)
        assert "kandidaten" not in dq and "bronnen" not in dq
        assert {"status", "klaar", "telling", "revisie"} <= dq.keys()
    # Dezelfde stand als de volledige vorm, op die ene deelvraag na.
    vol = await _overzicht(client, wg, na=ids[0])
    assert _dq(vol, ids[0]) == eerste and kort["revisie"] == vol["revisie"] and kort["volgende"] == vol["volgende"]
    assert "vorm" not in vol                                                    # de standaard verandert niet


async def test_het_overzicht_en_de_status_kennen_dezelfde_vorm(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[1]])])
    kort = await _overzicht(client, wg, na=ids[1], vorm="deelvraag")
    assert "kandidaten" in _dq(kort, ids[1]) and "kandidaten" not in _dq(kort, ids[0])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[1]}/status",
                          params={"vorm": "deelvraag"}, json={"actie": "openen"})
    assert r.status_code == 200, r.text
    assert "kandidaten" in _dq(r.json(), ids[1]) and "kandidaten" not in _dq(r.json(), ids[2])
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/bronselectie", params={"vorm": "alles"})
    assert r.status_code == 422                                                 # een onbekende vorm raadt niets


async def test_kandidaten_filteren_echt_op_de_deelvraag(client):
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]]),
                                       _kd(ONE, "kern", deelvragen=[ids[1]])])
    url = f"/v1/werkgebieden/{wg['id']}/kandidaten"
    alle = (await client.get(url)).json()
    assert {k["bron_iri"] for k in alle["kandidaten"]} == {ART, ONE}
    r = await client.get(url, params={"deelvraag_id": ids[1]})
    assert r.status_code == 200, r.text
    assert [k["bron_iri"] for k in r.json()["kandidaten"]] == [ONE] and r.json()["deelvraag_id"] == ids[1]
    assert (await client.get(url, params={"deelvraag_id": "bestaat-niet"})).status_code == 404


async def test_de_weergave_als_lijst_draagt_wat_je_beoordeelt_en_geen_trace():
    snap = snapshot()
    await store.batch(request(snap, [element(snap, ONE), element(snap, TWO, 0, 4)]), snap, "lex")
    view = await store.weergave(snap)
    lijst = store.lijst_weergave(view)
    assert lijst["vorm"] == "lijst" and lijst["snapshot_id"] == view["snapshot_id"]
    assert {e["id"] for e in lijst["elementen"]} == {e["id"] for e in view["elementen"]}
    for e in lijst["elementen"]:
        assert {"id", "klasse", "tekst", "ankers", "lifecycle", "laag_id"} <= e.keys()
        assert "trace" not in e and "geproduceerd_door" not in e
        assert isinstance(e["beslissingen"], int)
    assert [laag["revisie"] for laag in lijst["lagen"]] == [laag["revisie"] for laag in view["lagen"]]
    assert "segmenten" not in lijst                                             # de tekst haal je los
    assert len(str(lijst)) < len(str(store.compacte_weergave(view)))


async def test_de_weergave_route_kent_de_lijstvorm(client, monkeypatch):
    from app import annotatie_v2

    async def resolve(doel):
        return snapshot(doel.get("bron_iri") or ART)
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    snap = snapshot()
    await store.batch(request(snap, [element(snap, ONE)]), snap, "lex")
    r = await client.get("/v1/annotatie/weergave", params={"bron_iri": ART, "vorm": "lijst"})
    assert r.status_code == 200, r.text
    assert r.json()["vorm"] == "lijst" and r.json()["elementen"]
    vol = (await client.get("/v1/annotatie/weergave", params={"bron_iri": ART})).json()
    assert "segmenten" in vol and "vorm" not in vol                             # de standaard verandert niet
    skelet = (await client.get("/v1/annotatie/weergave", params={"bron_iri": ART, "vorm": "skelet"})).json()
    assert skelet["vorm"] == "skelet" and skelet["regels"] == []                # geen afleidingsregel, geen skelet
    assert "segmenten" not in skelet and "elementen" not in skelet


async def test_een_wijziging_aan_een_begrip_met_vorm_stand_geeft_de_stand_zonder_koppelingen(client):
    wg = await _werkgebied(client)
    b = await _begrip(client, wg)
    r = await client.patch(_url(wg, b), params={"vorm": "stand"},
                           json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "Belastingschuldige", **DEFINITIE}})
    assert r.status_code == 200, r.text
    stand = r.json()
    assert stand["vorm"] == "stand" and stand["revisie"] == b["revisie"] + 1
    assert stand["inhoud"]["definitie"] == DEFINITIE["definitie"]
    assert isinstance(stand["koppelingen"], int) and "accorderen" in stand
    kaart = (await client.get(_url(wg, b))).json()
    assert kaart["revisie"] == stand["revisie"] and isinstance(kaart["koppelingen"], list)
