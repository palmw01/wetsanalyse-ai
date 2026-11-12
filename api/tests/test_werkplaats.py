"""De werkplaats (ADR-016 deel B, stap B1): het register van wat een gebruiker zelf maakt.

Eén levenscyclus voor elke soort: een onderdeel met een eigenaar, versies die alleen aangroeien, een toets bij elke
opslag (de validatoren van `bronmodel`), een audit zonder inhoud, de rechten van §B4 en de vlag `WERKPLAATS`.
"""
from __future__ import annotations

import pytest
from bronmodel import werkplaats as wp
from httpx import ASGITransport, AsyncClient

_ADMIN = {"Authorization": "Bearer admin-token"}
# gebruiker-a is de beheerder (met 2FA), b en c zijn analisten, d is een beheerder zonder 2FA.
A, B, C, D = ({"X-User-Id": f"gebruiker-{x}"} for x in "abcd")

PROFIEL = """---
name: jrm-scenario
description: Werkt een juridisch scenario uit.
methoderol: agent
tools: [get_artikel]
---

Werk het scenario stap voor stap uit.
"""


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("WERKPLAATS", "true")
    from sqlalchemy import update

    from app import db, ratelimit
    from app.config import get_settings
    from app.routers.auth import vergeet_actief
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    ratelimit.reset()
    vergeet_actief()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await db.reconcile_schema()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b", "gebruiker-c", "gebruiker-d")
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.users).where(db.users.c.userid == "gebruiker-a").values(totp_enabled=True))
        await conn.execute(update(db.users).where(db.users.c.userid == "gebruiker-d").values(role="beheerder"))
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    get_settings.cache_clear()
    await db.dispose_engine()


async def _maak(client, wie=B, soort="agentprofiel", naam="jrm-scenario", bestanden=None, **extra):
    body = {"soort": soort, "naam": naam, **extra}
    if bestanden is not None:
        body["bestanden"] = bestanden
    return await client.post("/v1/werkplaats/onderdelen", json=body, headers=wie)


# --- de levenscyclus -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("soort, naam", [("skill", "jrm-proef"), ("agentprofiel", "jrm-scenario")])
async def test_nieuw_begint_met_een_geldige_versie_1(client, soort, naam):
    r = await _maak(client, soort=soort, naam=naam)
    assert r.status_code == 201, r.text
    o = r.json()
    assert (o["soort"], o["naam"], o["eigenaar"], o["stand"], o["versies"]) == (soort, naam, "gebruiker-b", "concept", 1)
    assert o["laatste"]["nummer"] == 1 and o["laatste"]["geldig"] is True and o["laatste"]["bevindingen"] == []
    v = (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/1", headers=B)).json()
    assert v["bestanden"] == wp.begin(soort, naam) and v["hash"] == wp.hash_van(v["bestanden"]) and v["bruikbaar"]


async def test_opslaan_vult_aan_en_dezelfde_inhoud_geeft_geen_versie(client):
    o = (await _maak(client)).json()
    pad = f"/v1/werkplaats/onderdelen/{o['id']}/versies"
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL}, "na_versie": 1, "toelichting": "eerste"}, headers=B)
    assert r.status_code == 200 and (r.json()["nummer"], r.json()["geldig"]) == (2, True)
    # Dezelfde inhoud nog eens: de laatste versie komt terug, er komt geen derde.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL}, "na_versie": 2}, headers=B)
    assert r.status_code == 200 and r.json()["nummer"] == 2
    # Voortbouwen op een verouderde versie weigert het register.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL + "Meer.\n"}, "na_versie": 1}, headers=B)
    assert r.status_code == 409 and "versie 2" in r.json()["detail"]["melding"]
    volledig = (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}", headers=B)).json()
    assert [v["nummer"] for v in volledig["versielijst"]] == [1, 2] and volledig["versies"] == 2
    # Versie 1 is niet gewijzigd.
    v1 = (await client.get(f"{pad}/1", headers=B)).json()
    assert v1["bestanden"] == wp.begin("agentprofiel", "jrm-scenario")


async def test_een_ongeldige_versie_wordt_bewaard_maar_is_niet_bruikbaar(client):
    """Wie halverwege opslaat, verliest niets. Naar de proef of een PR kan alleen een geldige versie."""
    o = (await _maak(client)).json()
    kapot = {"jrm-scenario.md": PROFIEL.replace("name: jrm-scenario", "name: anders")}
    r = await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/versies", json={"bestanden": kapot, "na_versie": 1}, headers=B)
    assert r.status_code == 200 and r.json()["geldig"] is False
    assert {b["code"] for b in r.json()["bevindingen"]} == {"naam"}
    v = (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/2", headers=B)).json()
    assert v["bestanden"] == kapot and v["bruikbaar"] is False
    assert (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/1", headers=B)).json()["bruikbaar"] is True


async def test_de_toets_is_die_van_bronmodel_en_slaat_niets_op(client):
    r = await client.post("/v1/werkplaats/toets", json={"soort": "skill", "naam": "jrm-proef", "bestanden": {"SKILL.md": "x"}}, headers=B)
    assert r.status_code == 200 and r.json()["geldig"] is False
    assert {b["code"] for b in r.json()["bevindingen"]} == {b.code for b in wp.toets("skill", "jrm-proef", {"SKILL.md": "x"})}
    goed = wp.begin("skill", "jrm-proef")
    r = await client.post("/v1/werkplaats/toets", json={"soort": "skill", "naam": "jrm-proef", "bestanden": goed}, headers=B)
    assert r.json() == {"geldig": True, "bevindingen": [], "hash": wp.hash_van(goed)}
    assert (await client.get("/v1/werkplaats/onderdelen", headers=B)).json() == []


@pytest.mark.parametrize("body, code", [
    ({"soort": "mcp", "naam": "server"}, None),                                   # de soort wacht op ADR-007
    ({"soort": "regelset", "naam": "x"}, None),
    ({"soort": "skill", "naam": "Geen_Skillnaam"}, None),
    ({"soort": "skill", "naam": "jrm-proef", "bestanden": {}}, "leeg"),
    ({"soort": "skill", "naam": "jrm-proef", "bestanden": {"../buiten.md": "x"}}, "pad"),
    ({"soort": "skill", "naam": "jrm-proef", "bestanden": {"/etc/passwd": "x"}}, "pad"),
    ({"soort": "skill", "naam": "jrm-proef", "bestanden": {"groot.md": "x" * (wp.MAX_TEKENS_BESTAND + 1)}}, "omvang"),
    ({"soort": "skill", "naam": "jrm-proef", "bestanden": {f"r/{i}.md": "x" for i in range(wp.MAX_BESTANDEN + 1)}}, "omvang"),
])
async def test_wat_het_register_nooit_bewaart(client, body, code):
    r = await client.post("/v1/werkplaats/onderdelen", json=body, headers=B)
    assert r.status_code == 422, r.text
    if code:
        assert code in {b["code"] for b in r.json()["detail"]["bevindingen"]}
    assert (await client.get("/v1/werkplaats/onderdelen", headers=B)).json() == []


async def test_het_aantal_versies_en_onderdelen_is_begrensd(client, monkeypatch):
    monkeypatch.setattr(wp, "MAX_VERSIES", 2)
    monkeypatch.setattr(wp, "MAX_ONDERDELEN", 2)
    o = (await _maak(client)).json()
    pad = f"/v1/werkplaats/onderdelen/{o['id']}/versies"
    assert (await client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL}, "na_versie": 1}, headers=B)).status_code == 200
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL + "x\n"}, "na_versie": 2}, headers=B)
    assert r.status_code == 409 and "maximum" in r.json()["detail"]["melding"]
    assert (await _maak(client, naam="tweede")).status_code == 201
    r = await _maak(client, naam="derde")
    assert r.status_code == 409 and "maximum" in r.json()["detail"]["melding"]


# --- een eigenaar, en meer concepten van dezelfde naam ---------------------------------------------------------

async def test_de_naam_is_uniek_per_soort_en_eigenaar(client):
    assert (await _maak(client, B)).status_code == 201
    assert (await _maak(client, B)).status_code == 409
    # Dezelfde naam als een andere soort, of van een andere eigenaar, mag.
    assert (await _maak(client, B, soort="skill")).status_code == 201
    andere = await _maak(client, C)
    assert andere.status_code == 201
    # De lijst en het onderdeel zeggen dat er nog een concept van dezelfde naam is.
    eigen = [o for o in (await client.get("/v1/werkplaats/onderdelen?soort=agentprofiel", headers=B)).json()]
    assert [(o["naam"], o["zelfde_naam"]) for o in eigen] == [("jrm-scenario", 1)]
    assert andere.json()["zelfde_naam"] == 1


async def test_na_intrekken_is_de_naam_weer_vrij_en_de_historie_blijft(client):
    o = (await _maak(client)).json()
    r = await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/intrekken", headers=B)
    assert r.status_code == 200 and (r.json()["stand"], r.json()["ingetrokken_door"]) == ("ingetrokken", "gebruiker-b")
    assert (await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/versies",
                              json={"bestanden": {"jrm-scenario.md": PROFIEL}, "na_versie": 1}, headers=B)).status_code == 409
    v = (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/1", headers=B)).json()
    assert v["bestanden"] and v["bruikbaar"] is False, "een ingetrokken onderdeel gaat niet naar de proef"
    assert (await _maak(client)).status_code == 201


# --- rechten (§B4) ---------------------------------------------------------------------------------------------

async def test_een_concept_is_van_zijn_eigenaar(client):
    o = (await _maak(client, B)).json()
    pad = f"/v1/werkplaats/onderdelen/{o['id']}"
    # Een andere analist ziet het niet, en een beheerder zonder 2FA ook niet.
    for wie in (C, D):
        assert (await client.get(pad, headers=wie)).status_code == 404
        assert (await client.get(f"{pad}/versies/1", headers=wie)).status_code == 404
        assert (await client.get(f"{pad}/audit", headers=wie)).status_code == 404
        assert (await client.get("/v1/werkplaats/onderdelen", headers=wie)).json() == []
    # Een beheerder met 2FA ziet alles, maar wijzigt andermans concept niet.
    assert (await client.get(pad, headers=A)).status_code == 200
    assert [x["id"] for x in (await client.get("/v1/werkplaats/onderdelen", headers=A)).json()] == [o["id"]]
    r = await client.post(f"{pad}/versies", json={"bestanden": {"jrm-scenario.md": PROFIEL}, "na_versie": 1}, headers=A)
    assert r.status_code == 403
    assert (await client.post(f"{pad}/intrekken", headers=A)).status_code == 403


async def test_delen_en_andermans_concept_intrekken_kan_alleen_een_beheerder_met_2fa(client):
    o = (await _maak(client, B)).json()
    delen = f"/v1/admin/werkplaats/onderdelen/{o['id']}/delen"
    assert (await client.put(delen, json={"gedeeld": True}, headers=B)).status_code == 401          # geen admin-token
    assert (await client.put(delen, json={"gedeeld": True}, headers={**_ADMIN, **D})).status_code == 403   # geen 2FA
    assert (await client.put(delen, json={"gedeeld": True}, headers={**_ADMIN, **B})).status_code == 403   # geen beheerder
    r = await client.put(delen, json={"gedeeld": True}, headers={**_ADMIN, **A})
    assert r.status_code == 200 and r.json()["gedeeld"] is True
    # Gedeeld: een andere analist leest het, maar wijzigt het niet.
    assert (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/1", headers=C)).status_code == 200
    assert [x["id"] for x in (await client.get("/v1/werkplaats/onderdelen", headers=C)).json()] == [o["id"]]
    assert (await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/intrekken", headers=C)).status_code == 403
    r = await client.post(f"/v1/admin/werkplaats/onderdelen/{o['id']}/intrekken", headers={**_ADMIN, **A})
    assert r.status_code == 200 and (r.json()["stand"], r.json()["gedeeld"]) == ("ingetrokken", False)
    assert (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}", headers=C)).status_code == 404


async def test_het_beleid_bepaalt_of_een_analist_mag_maken(client):
    s = (await client.get("/v1/werkplaats/stand", headers=B)).json()
    assert s["aan"] and s["mag_maken"] and not s["beheerder"] and s["beleid"]["analist_mag_maken"] is True
    assert [(x["naam"], x["open"]) for x in s["soorten"]] == [("skill", True), ("agentprofiel", True), ("mcp", False)]
    assert (await client.put("/v1/admin/werkplaats/beleid", json={"analist_mag_maken": False}, headers={**_ADMIN, **B})).status_code == 403
    r = await client.put("/v1/admin/werkplaats/beleid", json={"analist_mag_maken": False}, headers={**_ADMIN, **A})
    assert r.status_code == 200 and (r.json()["analist_mag_maken"], r.json()["door"]) == (False, "gebruiker-a")
    assert (await _maak(client, B)).status_code == 403
    assert (await client.get("/v1/werkplaats/stand", headers=B)).json()["mag_maken"] is False
    # De beheerder met 2FA mag altijd; een beheerder zonder 2FA werkt als analist.
    assert (await _maak(client, A)).status_code == 201
    assert (await _maak(client, D)).status_code == 403


# --- de audit --------------------------------------------------------------------------------------------------

async def test_elke_handeling_staat_in_de_audit_zonder_inhoud(client):
    o = (await _maak(client, B)).json()
    geheim = PROFIEL + "GEHEIME-TEKST-UIT-EEN-READER\n"
    await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/versies", json={"bestanden": {"jrm-scenario.md": geheim}, "na_versie": 1}, headers=B)
    await client.put(f"/v1/admin/werkplaats/onderdelen/{o['id']}/delen", json={"gedeeld": True}, headers={**_ADMIN, **A})
    await client.put(f"/v1/admin/werkplaats/onderdelen/{o['id']}/delen", json={"gedeeld": True}, headers={**_ADMIN, **A})
    await client.post(f"/v1/werkplaats/onderdelen/{o['id']}/intrekken", headers=B)
    r = await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/audit", headers=B)
    regels = list(reversed(r.json()))
    assert [(x["actie"], x["door"]) for x in regels] == [
        ("aangemaakt", "gebruiker-b"), ("versie", "gebruiker-b"), ("versie", "gebruiker-b"),
        ("gedeeld", "gebruiker-a"), ("ingetrokken", "gebruiker-b")]
    assert regels[2]["details"]["nummer"] == 2 and regels[2]["details"]["hash"] == wp.hash_van({"jrm-scenario.md": geheim})
    assert "GEHEIME-TEKST" not in r.text and "Werk het scenario" not in r.text


async def test_de_logregels_dragen_geen_inhoud_en_geen_naam(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="wetsanalyse.werkplaats"):
        await _maak(client, B, naam="geheime-naam", bestanden={"geheime-naam.md": PROFIEL.replace("jrm-scenario", "geheime-naam")})
    regels = [r for r in caplog.records if r.name == "wetsanalyse.werkplaats"]
    assert regels and all("geheime-naam" not in str(r.__dict__) and "Werk het scenario" not in str(r.__dict__) for r in regels)


# --- de vlag ---------------------------------------------------------------------------------------------------

async def test_zonder_de_vlag_bestaat_de_werkplaats_niet(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.delenv("WERKPLAATS")
    get_settings.cache_clear()
    assert get_settings().werkplaats is False
    assert (await client.get("/v1/werkplaats/stand", headers=B)).json() == {"aan": False}
    assert (await _maak(client, B)).status_code == 404
    assert (await client.get("/v1/werkplaats/onderdelen", headers=B)).status_code == 404
    assert (await client.post("/v1/werkplaats/toets", json={"soort": "skill", "naam": "x", "bestanden": {"a": "b"}}, headers=B)).status_code == 404
    assert (await client.put("/v1/admin/werkplaats/beleid", json={"analist_mag_maken": False}, headers={**_ADMIN, **A})).status_code == 404


# --- het register van de soorten -------------------------------------------------------------------------------

def test_de_hash_hangt_niet_van_de_volgorde_af():
    a = {"SKILL.md": "x", "references/a.md": "y"}
    assert wp.hash_van(a) == wp.hash_van(dict(reversed(a.items()))) != wp.hash_van({**a, "references/a.md": "z"})
    assert wp.hash_van({"a": "bc"}) != wp.hash_van({"ab": "c"}), "pad en tekst lopen niet in elkaar over"


def test_elke_open_soort_heeft_een_begin_dat_de_toets_haalt():
    for soort in wp.REGISTER:
        assert wp.toets(soort, "nieuw-onderdeel", wp.begin(soort, "nieuw-onderdeel")) == []
    assert set(wp.REGISTER) < set(wp.SOORTEN) and wp.naam_fout("mcp", "server")
