"""De annotatie-werkvoorraad van een werkgebied (spoor D, fase B1): eenheden, stand, schatting."""
from __future__ import annotations

from app import annotatie_v2_store as store, db, verbruik
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import ART, ONE, TWO, element, request, snapshot
from test_werkgebieden import ART2, LAW2, _bron, _nieuw, client, database, graaf  # noqa: F401


async def _voorraad(client, wg) -> dict:
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/annotatie-werkvoorraad")
    assert r.status_code == 200, r.text
    return r.json()


async def test_per_lid_een_keer_en_zonder_context(client):
    snap = snapshot()
    await store.batch(request(snapshot(ONE), [element(snap)]), snapshot(ONE), "lex")    # lid 1: voorstel
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]                           # artikel → per lid
    wg = (await _bron(client, wg, bron_iri=ONE, bereik="node"))["werkgebied"]            # dubbel gedekt
    wg = (await _bron(client, wg, bron_iri=ART2, rol="context"))["werkgebied"]
    v = await _voorraad(client, wg)
    assert [e["bron_iri"] for e in v["eenheden"]] == [ONE, TWO]                         # elk één keer
    per = {e["bron_iri"]: e for e in v["eenheden"]}
    assert per[ONE]["stand"] == {"status": "te_beoordelen", "voorstellen": 1, "te_beoordelen": 1}
    assert len(per[ONE]["selecties"]) == 2
    assert (per[TWO]["stand"]["status"], per[TWO]["label"], per[TWO]["regeling"]) == ("nieuw", "Artikel 9, Lid 2", "Wet")
    assert v["te_annoteren"] == [TWO]
    assert v["context_niet_meegenomen"] == 1 and v["volledig"] is True
    sel = {s["bron_iri"]: s for s in v["selecties"]}
    assert sel[ART]["eenheden"] == 2 and sel[ART]["per_stand"] == {"te_beoordelen": 1, "nieuw": 1}
    assert ART2 not in sel


async def test_afgerond_beoordeeld_en_zonder_markeringen(client):
    een = snapshot(ONE)
    res = await store.batch(request(een, [element(een)]), een, "lex")
    eid, laag = res["elementen"][0]["id"], (await store.weergave(een))["lagen"][0]
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=een["snapshot_id"],
                                      verwachte_revisies={ONE: laag["revisie"]}), een, "jurist-a")
    twee = snapshot(TWO)                       # geannoteerd, niets gevonden: dekking zonder elementen
    await store.batch(request(twee, [], batch_id="leeg", dekking={"bereik": [TWO]}), twee, "lex")
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]

    v = await _voorraad(client, wg)
    assert {e["bron_iri"]: e["stand"]["status"] for e in v["eenheden"]} == {ONE: "beoordeeld", TWO: "zonder_markeringen"}
    assert v["te_annoteren"] == []

    laag = (await store.weergave(een))["lagen"][0]
    await store.zet_status(laag["id"], "geaccordeerd", laag["revisie"], "jurist-a", een)
    v = await _voorraad(client, wg)
    assert {e["bron_iri"]: e["stand"]["status"] for e in v["eenheden"]}[ONE] == "afgerond"


async def test_onbereikbare_bron_is_een_open_punt(client, graaf):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = (await _bron(client, wg, bron_iri=ART2))["werkgebied"]
    graaf.weg.add(LAW2)
    v = await _voorraad(client, wg)
    assert v["volledig"] is False and len(v["open_punten"]) == 1
    assert v["te_annoteren"] == [ONE, TWO]                    # de rest komt wel
    assert {s["bron_iri"]: bool(s["onbereikbaar"]) for s in v["selecties"]} == {ART: False, ART2: True}


async def _beurt(run_id: str, tokens: int, *, annotatie: bool, userid: str = "jurist-a"):
    inhoud = {"tekst": "x", "run_id": run_id}
    if annotatie:
        inhoud["artefact"] = {"soort": "annotatie", "ref": {"bron_iri": ONE}, "titel": "Lid 1"}
    async with db.get_engine().begin() as conn:
        await conn.execute(db.gesprek_berichten.insert().values(
            gesprek_id="g1", rol="assistant", inhoud=inhoud, run_id=run_id, created=db.utcnow()))
    await verbruik.boek(userid, bron="agent", invoer=tokens, run_id=run_id)


async def test_schatting_alleen_uit_eigen_annotatiebeurten(client):
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    v = await _voorraad(client, wg)
    assert v["schatting"] is None and "Nog geen annotatiebeurten" in v["schatting_toelichting"]
    assert v["budget"]["actief"] in (True, False) and "resterend" in v["budget"]

    await _beurt("r1", 100, annotatie=True)
    await _beurt("r2", 300, annotatie=True)
    await _beurt("r3", 200, annotatie=True)
    await _beurt("r4", 50_000, annotatie=False)              # een gewone vraag telt niet
    await _beurt("r5", 9_000, annotatie=True, userid="jurist-b")   # en een ander ook niet
    v = await _voorraad(client, wg)
    assert v["schatting"] == {"per_bepaling": 200, "basis": 3, "totaal": 400}
