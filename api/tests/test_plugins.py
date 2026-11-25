"""Het register van de plugins (plan contenttoets, C4): hetzelfde patroon als de bronconnectors.

Welke plugins er bestaan, staat in de code (`bronmodel.plugins`); het register zegt alleen aan of uit, per beheerder
mét 2FA, en elke wijziging is een auditregel. De werkplek en graph-qa lezen `GET /v1/plugins`; per gesprek zet de
jurist een aangeboden plugin aan of uit (`gesprekken.plugins`).
"""
from __future__ import annotations

import pytest

from conftest import api_client

_ADMIN = {"Authorization": "Bearer admin-token"}
_BEHEERDER = {**_ADMIN, "X-User-Id": "gebruiker-a"}
_ZONDER_2FA = {**_ADMIN, "X-User-Id": "gebruiker-b"}
_A = {"X-User-Id": "gebruiker-a"}


@pytest.fixture
async def client(monkeypatch):
    async with api_client(monkeypatch, env={"WETSANALYSE_AUTH_REQUIRED": "0", "WETSANALYSE_ADMIN_TOKENS": "adm:admin-token"},
                          reconcile=True, gebruikers=("gebruiker-a", "gebruiker-b"), met_2fa=("gebruiker-a",)) as ac:
        yield ac


async def test_de_contenttoets_staat_uit_tot_de_beheerder_hem_aanbiedt(client):
    r = await client.get("/v1/admin/plugins", headers=_ADMIN)
    assert [(p["naam"], p["commando"], p["aan"]) for p in r.json()] == [("contenttoets", "contenttoets", False)]
    assert (await client.get("/v1/plugins")).json() == {"aan": [], "plugins": []}
    r = await client.put("/v1/admin/plugins/contenttoets", json={"aan": True}, headers=_BEHEERDER)
    assert r.status_code == 200 and r.json()["aan"] and r.json()["door"] == "gebruiker-a"
    aan = (await client.get("/v1/plugins")).json()
    assert aan["aan"] == ["contenttoets"] and aan["plugins"][0]["label"] == "Contenttoets"


async def test_elke_wijziging_is_een_auditregel(client):
    for aan in (True, True, False):
        await client.put("/v1/admin/plugins/contenttoets", json={"aan": aan}, headers=_BEHEERDER)
    regels = (await client.get("/v1/admin/plugins/contenttoets/audit", headers=_ADMIN)).json()
    assert [(r["actie"], r["door"]) for r in regels] == [("uit", "gebruiker-a"), ("aan", "gebruiker-a")]


async def test_zonder_2fa_of_een_onbekende_plugin_geen_wijziging(client):
    assert (await client.put("/v1/admin/plugins/contenttoets", json={"aan": True}, headers=_ZONDER_2FA)).status_code == 403
    assert (await client.put("/v1/admin/plugins/onbekend", json={"aan": True}, headers=_BEHEERDER)).status_code == 404
    assert (await client.get("/v1/plugins")).json()["aan"] == []


async def test_de_stand_van_een_gesprek_en_terug_naar_de_standaard(client):
    g = (await client.post("/v1/gesprekken", headers=_A, json={"titel": "t"})).json()
    assert g["plugins"] is None
    r = await client.patch(f"/v1/gesprekken/{g['id']}", headers=_A, json={"plugins": []})
    assert r.status_code == 200 and r.json()["plugins"] == []
    r = await client.patch(f"/v1/gesprekken/{g['id']}", headers=_A, json={"titel": "u"})
    assert r.json()["plugins"] == [], "weggelaten is ongewijzigd"
    r = await client.patch(f"/v1/gesprekken/{g['id']}", headers=_A, json={"plugins": ["contenttoets", "contenttoets"]})
    assert r.json()["plugins"] == ["contenttoets"]
    r = await client.patch(f"/v1/gesprekken/{g['id']}", headers=_A, json={"plugins": None})
    assert r.json()["plugins"] is None
    assert (await client.patch(f"/v1/gesprekken/{g['id']}", headers=_A, json={"plugins": ["onbekend"]})).status_code == 422
