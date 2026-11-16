"""Races op echte PostgreSQL voor de domeinen met een slot of een unieke index maar zonder race-test (Lex Bench §20.5
stap 3, risico R07; testplan api V4): de bronselectie per deelvraag, de deelvragen en de delegaties. Twee gelijktijdige
aanroepen: precies één wint, de ander krijgt een 409 of 412 (nooit een 500), en de stand klopt daarna. SQLite serialiseert
alles en bewijst zo'n slot niet; vandaar Postgres, zoals `test_werkgebieden_postgres.py`.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from app import db
from conftest import postgres_schema, vereis_postgres
from test_annotatie_v2 import ART
from test_bronselectie import _dq, _kd, _kid, _met_kandidaten, _overzicht, _status, _vier
from test_delegaties import B, D, _gesprek, _start, _subagent
from test_werkgebied_deelvragen import _dv
from test_werkgebieden import _nieuw, client, graaf  # noqa: F401

pytestmark = [vereis_postgres(), pytest.mark.risico("R07")]


@pytest.fixture(autouse=True)
async def database():
    async for _ in postgres_schema("races"):
        yield


def _codes(*antwoorden) -> list[int]:
    return sorted(a.status_code for a in antwoorden)


async def _tel(tabel, **waar) -> int:
    async with db.get_engine().begin() as conn:
        q = select(func.count()).select_from(tabel).where(*(getattr(tabel.c, k) == v for k, v in waar.items()))
        return (await conn.execute(q)).scalar_one()


# --- de bronselectie per deelvraag ------------------------------------------------------------------------------

async def test_twee_keer_tegelijk_openen_geeft_een_voortgang(client):
    wg, ids = await _vier(client)
    pad = f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[0]}/status"
    a, b = await asyncio.gather(client.post(pad, json={"actie": "openen"}), client.post(pad, json={"actie": "openen"}))
    assert _codes(a, b) == [200, 200], (a.text, b.text)
    assert await _tel(db.bronselectie_voortgang, werkgebied_id=wg["id"], deelvraag_id=ids[0]) == 1


async def _dubbele_stand(wg_id: str, did: str, iri: str) -> bool:
    """Of de kandidaat bij deze deelvraag tegelijk opgenomen (een gekoppelde selectie) en uitgesloten (een besluit) is."""
    s, kp, bd = db.werkgebied_bronselecties, db.werkgebied_deelvraag_koppelingen, db.bron_kandidaat_deelvragen
    async with db.get_engine().begin() as conn:
        gekoppeld = (await conn.execute(select(func.count()).select_from(kp.join(s, kp.c.doel_id == s.c.id)).where(
            kp.c.deelvraag_id == did, kp.c.soort == "bron", s.c.bron_iri == iri, s.c.verwijderd.is_(None)))).scalar_one()
        uitgesloten = (await conn.execute(select(func.count()).select_from(bd).where(
            bd.c.werkgebied_id == wg_id, bd.c.deelvraag_id == did, bd.c.status == "uitgesloten"))).scalar_one()
    return bool(gekoppeld and uitgesloten)


@pytest.mark.parametrize("ronde", range(4))
async def test_tegengestelde_besluiten_over_een_kandidaat_geven_nooit_een_dubbele_stand(client, ronde):
    """Opnemen en uitsluiten tegelijk. Wint uitsluiten eerst, dan vervangt opnemen dat besluit (zoals na elkaar: een besluit
    bij een deelvraag hoogt de revisie niet op). Wint opnemen eerst, dan weigert uitsluiten met 409. Wat nooit mag: een
    kandidaat die bij dezelfde deelvraag opgenomen én uitgesloten is (zonder de toets onder het slot gebeurde dat)."""
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    pad = f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[0]}/kandidaten/{kid}"
    opnemen = client.post(pad, json={"besluit": "opnemen", "verwachte_revisie": ov["revisie"]})
    uitsluiten = client.post(pad, json={"besluit": "uitsluiten", "reden": "hoort er niet bij",
                                        "verwachte_revisie": ov["revisie"]}, headers=B)
    a, b = await asyncio.gather(*((opnemen, uitsluiten) if ronde % 2 else (uitsluiten, opnemen)))
    assert {a.status_code, b.status_code} <= {200, 409, 412}, (a.text, b.text)
    assert not await _dubbele_stand(wg["id"], ids[0], ART), "opgenomen én uitgesloten bij dezelfde deelvraag"
    assert _kid(_dq(await _overzicht(client, wg), ids[0]), ART)["stand"] in ("opgenomen", "uitgesloten")


async def test_uitsluiten_dat_zijn_toets_las_voor_een_opnemen_weigert_onder_het_slot(client, monkeypatch):
    """De volgorde die de race gevaarlijk maakt, afgedwongen: uitsluiten leest dat de kandidaat niet is opgenomen, wacht
    vóór het werkgebiedslot tot een opnemen klaar is, en gaat dan verder. Zonder de toets onder het slot was de kandidaat
    daarna opgenomen én uitgesloten; nu weigert uitsluiten met 409."""
    from app import bronselectie
    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [_kd(ART, "kern", deelvragen=[ids[0]])])
    ov = await _status(client, wg, ids[0], "openen")
    kid = _kid(_dq(ov, ids[0]), ART)["id"]
    pad = f"/v1/werkgebieden/{wg['id']}/bronselectie/{ids[0]}/kandidaten/{kid}"

    echt, wacht, klaar = bronselectie._slot, {"nog": True}, asyncio.Event()

    async def slot(conn, werkgebied_id):
        if wacht["nog"]:
            wacht["nog"] = False
            await klaar.wait()
        return await echt(conn, werkgebied_id)

    monkeypatch.setattr(bronselectie, "_slot", slot)
    uitsluiten = asyncio.create_task(client.post(pad, json={"besluit": "uitsluiten", "reden": "hoort er niet bij",
                                                            "verwachte_revisie": ov["revisie"]}, headers=B))
    for _ in range(200):
        if not wacht["nog"]:
            break
        await asyncio.sleep(0.01)
    assert not wacht["nog"], "uitsluiten kwam niet bij het slot"
    opnemen = await client.post(pad, json={"besluit": "opnemen", "verwachte_revisie": ov["revisie"]})
    assert opnemen.status_code == 200, opnemen.text
    klaar.set()
    r = await uitsluiten
    assert r.status_code == 409 and r.json()["detail"]["status"] == "opgenomen", r.text
    assert not await _dubbele_stand(wg["id"], ids[0], ART)
    assert _kid(_dq(await _overzicht(client, wg), ids[0]), ART)["stand"] == "opgenomen"


# --- de deelvragen --------------------------------------------------------------------------------------------

async def test_twee_keer_tegelijk_een_deelvraag_erbij_een_412(client):
    wg = await _nieuw(client)
    pad = f"/v1/werkgebieden/{wg['id']}/deelvragen/samen"
    a, b = await asyncio.gather(
        client.post(pad, json={"verwachte_revisie": wg["revisie"], "nieuw": ["Wie betaalt?"]}),
        client.post(pad, json={"verwachte_revisie": wg["revisie"], "nieuw": ["Wanneer?"]}, headers=B))
    assert _codes(a, b) == [200, 412], (a.text, b.text)
    stand = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert len([d for d in stand["deelvragen"] if d.get("status") != "vervangen"]) == 1


async def test_een_deelvraag_daarna_nog_bijzetten_kan_op_de_nieuwe_revisie(client):
    """De tegenproef: de 412 hierboven is een revisietoets, geen slot dat blijft hangen."""
    wg = await _nieuw(client)
    wg = await _dv(client, wg, "Wie betaalt?")
    wg = await _dv(client, wg, "Wanneer?")
    assert len(wg["deelvragen"]) == 2


# --- de delegaties ----------------------------------------------------------------------------------------------

async def test_een_gebruiker_start_tegelijk_twee_subagents_een_409(client):
    g1, g2 = await _gesprek(client), await _gesprek(client)
    a, b = await asyncio.gather(_subagent(client, g1), _subagent(client, g2))
    assert _codes(a, b) == [201, 409], (a.text, b.text)
    fout = (a if a.status_code == 409 else b).json()["detail"]
    assert fout["fout"] == "delegatie_loopt_al"
    assert await _tel(db.delegaties, user_id="jurist-a", status="loopt") == 1


async def test_twee_juristen_starten_tegelijk_een_regie_in_een_werkgebied_een_409(client):
    wg = await _nieuw(client)
    ga = await _gesprek(client, werkgebied_id=wg["id"])
    gb = await _gesprek(client, headers=B, werkgebied_id=wg["id"])
    a, b = await asyncio.gather(_start(client, wg, ga), _start(client, wg, gb, headers=B))
    assert _codes(a, b) == [201, 409], (a.text, b.text)
    assert await _tel(db.delegaties, werkgebied_id=wg["id"], status="loopt") == 1
    assert D
