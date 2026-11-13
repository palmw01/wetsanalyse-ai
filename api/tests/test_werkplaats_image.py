"""Wat er in het image zit (ADR-016 §B1, stap B1-2): graph-qa meldt het, de api leidt er de stand uit af.

De melding is van graph-qa alleen, idempotent op de hash van het pakket, en het enige wat het agent-token in de
werkplaats mag. Of een versie actief is, staat nergens opgeslagen: het volgt uit de hashes. Kent de api het image niet,
dan is het antwoord onbekend, nooit "niet actief".
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from bronmodel import werkplaats as wp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

AGENT = {"Authorization": "Bearer agent-token"}
B = {"Authorization": "Bearer webapp-token", "X-User-Id": "gebruiker-b"}

BRONPAKKET = json.loads((Path(__file__).resolve().parents[2] / "tools" / "graph-qa" / "agent" / "bronpakket.json")
                        .read_text(encoding="utf-8"))

PROFIEL = """---
name: jrm-scenario
description: Werkt een juridisch scenario uit.
methoderol: agent
tools: [get_artikel]
---

Werk het scenario stap voor stap uit.
"""
ANDERS = PROFIEL.replace("stap voor stap", "in drie stappen")


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_API_TOKENS", "graph-qa:agent-token,frontend:webapp-token")
    monkeypatch.setenv("WERKPLAATS", "true")
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
    await maak_testgebruikers("gebruiker-b")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    get_settings.cache_clear()
    await db.dispose_engine()


def _pakket(**profielen: str) -> dict:
    """Een melding met deze agentprofielen (naam → tekst), zoals graph-qa haar opbouwt."""
    onderdelen = {}
    for naam, tekst in profielen.items():
        bestanden = {f"{naam}.md": tekst.replace("jrm-scenario", naam)}
        onderdelen[f"agentprofiel/{naam}"] = {"soort": "agentprofiel", "naam": naam, "bestanden": bestanden,
                                              "hash": wp.hash_van(bestanden)}
    return {"pakket_hash": wp.pakkethash({k: o["hash"] for k, o in onderdelen.items()}), "revisie": "abc1234",
            "onderdelen": onderdelen}


async def _meld(client, pakket: dict, *, alleen_hash: bool = False, headers=AGENT):
    body = {k: v for k, v in pakket.items() if not (alleen_hash and k == "onderdelen")}
    return await client.put("/v1/werkplaats/image", json=body, headers=headers)


async def _stand(client) -> dict:
    return (await client.get("/v1/werkplaats/stand", headers=B)).json()["image"]


async def _bewerk(client, naam="jrm-scenario", soort="agentprofiel"):
    return await client.post("/v1/werkplaats/onderdelen", json={"soort": soort, "naam": naam, "uit_image": True}, headers=B)


async def _sla_op(client, oid: str, tekst: str, na: int):
    r = await client.post(f"/v1/werkplaats/onderdelen/{oid}/versies",
                          json={"bestanden": {"jrm-scenario.md": tekst}, "na_versie": na}, headers=B)
    assert r.status_code == 200, r.text
    return r.json()


async def _lees(client, oid: str) -> dict:
    return (await client.get(f"/v1/werkplaats/onderdelen/{oid}", headers=B)).json()


async def test_zonder_melding_is_de_stand_onbekend_en_nooit_niet_actief(client):
    assert await _stand(client) == {"bekend": False, "pakket_hash": "", "revisie": "", "gemeld_op": "", "onderdelen": 0}
    r = await client.post("/v1/werkplaats/onderdelen", json={"soort": "agentprofiel", "naam": "jrm-scenario"}, headers=B)
    o = await _lees(client, r.json()["id"])
    assert (o["image_bekend"], o["in_image"], o["actief_versie"], o["basis_verouderd"]) == (False, None, None, None)
    assert o["stand"] == "concept" and [v["actief"] for v in o["versielijst"]] == [None]
    # Bewerken vanuit het image kan pas als de api het image kent.
    r = await _bewerk(client, "ander-profiel")
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "image_onbekend"


async def test_de_melding_is_idempotent_op_de_hash_van_het_pakket(client):
    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    # Eerst alleen de hash: de api kent het pakket niet en vraagt om het geheel.
    r = await _meld(client, pakket, alleen_hash=True)
    assert r.status_code == 200 and r.json() == {"bekend": False, "pakket_hash": "", "geschreven": False}
    r = await _meld(client, pakket)
    assert r.status_code == 200 and r.json()["geschreven"] is True
    stand = await _stand(client)
    assert (stand["bekend"], stand["pakket_hash"], stand["revisie"], stand["onderdelen"]) == (True, pakket["pakket_hash"], "abc1234", 1)
    assert stand["gemeld_op"]
    # Een volgende start van hetzelfde image, met of zonder de inhoud: er wordt niets geschreven.
    for alleen_hash in (True, False):
        r = await _meld(client, pakket, alleen_hash=alleen_hash)
        assert r.json()["geschreven"] is False and r.json()["bekend"] is True
    assert (await _stand(client))["gemeld_op"] == stand["gemeld_op"]

    from app import db
    async with db.get_engine().connect() as conn:
        regels = (await conn.execute(select(db.werkplaats_audit).where(db.werkplaats_audit.c.actie == "image"))).mappings().all()
    assert len(regels) == 1 and regels[0]["door"] == "graph-qa"
    assert regels[0]["details"] == {"pakket_hash": pakket["pakket_hash"], "revisie": "abc1234", "onderdelen": 1, "was": ""}
    assert "stap voor stap" not in json.dumps(regels[0]["details"])


async def test_alleen_graph_qa_meldt_en_het_agent_token_mag_verder_niets_in_de_werkplaats(client):
    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    assert (await _meld(client, pakket, headers=B)).status_code == 403
    assert (await _stand(client))["bekend"] is False
    assert (await _meld(client, pakket)).status_code == 200
    for methode, pad, body in (("GET", "/v1/werkplaats/onderdelen", None), ("GET", "/v1/werkplaats/stand", None),
                               ("POST", "/v1/werkplaats/onderdelen", {"soort": "agentprofiel", "naam": "x"}),
                               ("POST", "/v1/werkplaats/toets", {"soort": "agentprofiel", "naam": "x", "bestanden": {}}),
                               ("DELETE", "/v1/werkplaats/image", None)):
        r = await client.request(methode, pad, json=body, headers={**AGENT, "X-User-Id": "gebruiker-b"})
        assert r.status_code in (403, 405), (methode, pad, r.status_code)


@pytest.mark.parametrize("breek", ["pakket_hash", "hash", "bestanden", "sleutel", "soort"])
async def test_een_melding_die_niet_met_zichzelf_klopt_wordt_niet_bewaard(client, breek):
    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    o = pakket["onderdelen"]["agentprofiel/jrm-scenario"]
    if breek == "pakket_hash":
        pakket["pakket_hash"] = "0" * 64
    elif breek == "hash":
        o["hash"] = "0" * 64
    elif breek == "bestanden":
        o["bestanden"] = {"../buiten.md": "x"}
    elif breek == "sleutel":
        pakket["onderdelen"] = {"agentprofiel/anders": o}
    else:
        pakket["onderdelen"] = {"mcp/jrm-scenario": {**o, "soort": "mcp"}}
    assert (await _meld(client, pakket)).status_code == 422
    assert (await _stand(client))["bekend"] is False


async def test_bewerken_begint_met_de_versie_uit_het_image(client):
    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    await _meld(client, pakket)
    imagehash = pakket["onderdelen"]["agentprofiel/jrm-scenario"]["hash"]
    r = await _bewerk(client)
    assert r.status_code == 201, r.text
    o = await _lees(client, r.json()["id"])
    v1 = (await client.get(f"/v1/werkplaats/onderdelen/{o['id']}/versies/1", headers=B)).json()
    assert v1["bestanden"] == {"jrm-scenario.md": PROFIEL} and (v1["hash"], v1["basis_hash"], v1["actief"]) == (imagehash, imagehash, True)
    assert (o["stand"], o["in_image"], o["actief_versie"], o["basis_verouderd"]) == ("actief", True, 1, False)
    # Wat niet in het image zit, is niet te bewerken; met eigen bestanden erbij is het geen Bewerken.
    r = await _bewerk(client, "bestaat-niet")
    assert r.status_code == 404 and r.json()["detail"]["fout"] == "niet_in_image"
    r = await client.post("/v1/werkplaats/onderdelen", headers=B,
                          json={"soort": "agentprofiel", "naam": "jrm-scenario", "uit_image": True, "bestanden": {}})
    assert r.status_code == 422


async def test_een_image_dat_ouder_is_dan_master_maakt_een_versie_niet_actief(client):
    """De wijziging staat op master, maar het image dat draait is nog het oude: de versie is een concept tot graph-qa
    met het nieuwe image start en zich meldt. Daarna is zij actief, zonder dat iemand iets opslaat."""
    oud, nieuw = _pakket(**{"jrm-scenario": PROFIEL}), _pakket(**{"jrm-scenario": ANDERS})
    await _meld(client, oud)
    oid = (await _bewerk(client)).json()["id"]
    await _sla_op(client, oid, ANDERS, 1)
    o = await _lees(client, oid)
    assert (o["stand"], o["actief_versie"], o["basis_verouderd"]) == ("concept", 1, False)
    assert [v["actief"] for v in o["versielijst"]] == [True, False]
    # Een oude replica die nog eens meldt, verandert niets.
    await _meld(client, oud, alleen_hash=True)
    assert (await _lees(client, oid))["stand"] == "concept"

    assert (await _meld(client, nieuw)).json()["geschreven"] is True
    o = await _lees(client, oid)
    assert (o["stand"], o["actief_versie"], o["basis_verouderd"]) == ("actief", 2, False)
    assert [v["actief"] for v in o["versielijst"]] == [False, True]


async def test_een_basis_die_niet_meer_in_het_image_zit_is_verouderd(client):
    """Master veranderde terwijl het concept openlag: de basis is niet meer wat er draait, en het concept ook niet."""
    await _meld(client, _pakket(**{"jrm-scenario": PROFIEL}))
    oid = (await _bewerk(client)).json()["id"]
    await _sla_op(client, oid, PROFIEL.replace("stap voor stap", "zorgvuldig"), 1)
    await _meld(client, _pakket(**{"jrm-scenario": ANDERS}))
    o = await _lees(client, oid)
    assert (o["stand"], o["in_image"], o["actief_versie"], o["basis_verouderd"]) == ("concept", True, None, True)
    # Verdwijnt het onderdeel uit het image, dan is het een eigen concept met een basis die er niet meer is.
    await _meld(client, _pakket(**{"ander-profiel": PROFIEL}))
    o = await _lees(client, oid)
    assert (o["in_image"], o["actief_versie"], o["basis_verouderd"]) == (False, None, True)


async def test_twee_replicas_die_tegelijk_melden_laten_een_rij_achter(client):
    from app import db

    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    antwoorden = await asyncio.gather(*(_meld(client, pakket) for _ in range(4)))
    assert [r.status_code for r in antwoorden] == [200] * 4
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(db.werkplaats_image))).scalar() == 1
    assert (await _stand(client))["pakket_hash"] == pakket["pakket_hash"]
    # Een oude en een nieuwe replica naast elkaar: één rij, en de stand zegt welke het laatst meldde.
    ander = _pakket(**{"jrm-scenario": ANDERS})
    antwoorden = await asyncio.gather(_meld(client, pakket), _meld(client, ander), _meld(client, pakket, alleen_hash=True))
    assert [r.status_code for r in antwoorden] == [200] * 3
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(db.werkplaats_image))).scalar() == 1
    assert (await _stand(client))["pakket_hash"] in {pakket["pakket_hash"], ander["pakket_hash"]}


async def test_het_echte_bronpakket_van_graph_qa_is_een_geldige_melding(client):
    melding = {"pakket_hash": BRONPAKKET["sha256"], "revisie": "", "onderdelen": BRONPAKKET["onderdelen"]}
    r = await client.put("/v1/werkplaats/image", json=melding, headers=AGENT)
    assert r.status_code == 200, r.text
    assert r.json()["onderdelen"] == len(BRONPAKKET["onderdelen"])
    # Elk onderdeel uit het image is te bewerken, en is dan meteen een geldige, actieve versie.
    for o in BRONPAKKET["onderdelen"].values():
        r = await _bewerk(client, o["naam"], o["soort"])
        assert r.status_code == 201, (o["naam"], r.text)
        gelezen = await _lees(client, r.json()["id"])
        assert gelezen["stand"] == "actief" and gelezen["laatste"]["geldig"] is True, o["naam"]


async def test_een_skill_wordt_ook_tegen_de_andere_skills_in_het_image_getoetst(client):
    """Een sectie-id en een broncode zijn van één skill. Dat is alleen over de skills heen te zien, dus pas met het image."""
    bron = BRONPAKKET["onderdelen"]["skill/wetsuitvoering"]["bestanden"]
    kopie = {pad: tekst.replace("name: wetsuitvoering", "name: jrm-proef") for pad, tekst in bron.items()}
    vraag = {"soort": "skill", "naam": "jrm-proef", "bestanden": kopie}
    # Zonder image toetst de skill alleen op zichzelf.
    alleen = (await client.post("/v1/werkplaats/toets", json=vraag, headers=B)).json()
    assert alleen["geldig"] is True, alleen
    await client.put("/v1/werkplaats/image", headers=AGENT,
                     json={"pakket_hash": BRONPAKKET["sha256"], "onderdelen": BRONPAKKET["onderdelen"]})
    samen = (await client.post("/v1/werkplaats/toets", json=vraag, headers=B)).json()
    assert samen["geldig"] is False and samen["bevindingen"]
    # Opslaan bewaart de versie, met dezelfde bevindingen: ongeldig, dus niet bruikbaar.
    r = await client.post("/v1/werkplaats/onderdelen", json=vraag, headers=B)
    assert r.status_code == 201
    laatste = (await _lees(client, r.json()["id"]))["laatste"]
    assert laatste["geldig"] is False
    # Een concept van de skill zelf vervangt haar eigen versie in het image en botst dus niet met zichzelf.
    r = await _bewerk(client, "wetsuitvoering", "skill")
    assert r.status_code == 201 and (await _lees(client, r.json()["id"]))["laatste"]["geldig"] is True


# --- een concept dat achterloopt (B2-4) --------------------------------------------------------------------------------

async def test_de_versie_die_draait_is_te_lezen_voor_een_gebruiker_en_niet_voor_de_agent(client):
    assert (await client.get("/v1/werkplaats/image/onderdelen/agentprofiel/jrm-scenario", headers=B)).json()["detail"]["fout"] == "image_onbekend"
    pakket = _pakket(**{"jrm-scenario": PROFIEL})
    await _meld(client, pakket)
    r = await client.get("/v1/werkplaats/image/onderdelen/agentprofiel/jrm-scenario", headers=B)
    assert r.status_code == 200
    d = r.json()
    assert d["bestanden"] == {"jrm-scenario.md": PROFIEL} and d["hash"] == wp.hash_van(d["bestanden"]) and d["revisie"] == "abc1234"
    r = await client.get("/v1/werkplaats/image/onderdelen/agentprofiel/bestaat-niet", headers=B)
    assert r.status_code == 404 and r.json()["detail"]["fout"] == "niet_in_image"
    assert (await client.get("/v1/werkplaats/image/onderdelen/regelset/x", headers=B)).status_code == 422
    # Het agent-token leest in de werkplaats niets.
    r = await client.get("/v1/werkplaats/image/onderdelen/agentprofiel/jrm-scenario", headers={**AGENT, "X-User-Id": "gebruiker-b"})
    assert r.status_code == 403


async def test_wie_verwerkt_wat_er_draait_bouwt_daarna_voort_op_die_versie(client):
    """Een concept loopt achter: master veranderde. De gebruiker verwerkt dat en slaat op met de hash van wat er nu
    draait als basis. Daarna loopt het concept niet meer achter, ook niet na een volgende wijziging."""
    await _meld(client, _pakket(**{"jrm-scenario": PROFIEL}))
    oid = (await _bewerk(client)).json()["id"]
    mijn = PROFIEL.replace("stap voor stap", "zorgvuldig")
    await _sla_op(client, oid, mijn, 1)
    nieuw = _pakket(**{"jrm-scenario": ANDERS})
    await _meld(client, nieuw)
    assert (await _lees(client, oid))["basis_verouderd"] is True
    nu = nieuw["onderdelen"]["agentprofiel/jrm-scenario"]["hash"]
    pad = f"/v1/werkplaats/onderdelen/{oid}/versies"
    # Een hash die niet (meer) in het image zit, is geen basis.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": mijn}, "na_versie": 2, "basis_hash": "0" * 64}, headers=B)
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "basis_niet_actueel"
    # Dezelfde inhoud met een nieuwe basis is een nieuwe versie: de basis is het nieuws.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": mijn}, "na_versie": 2, "basis_hash": nu,
                                     "toelichting": "verwerkt wat er draait"}, headers=B)
    assert r.status_code == 200 and (r.json()["nummer"], r.json()["basis_hash"]) == (3, nu)
    o = await _lees(client, oid)
    assert (o["stand"], o["basis_verouderd"]) == ("concept", False)
    # Een volgende wijziging erft de nieuwe basis.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": mijn + "\nNog een regel.\n"}, "na_versie": 3}, headers=B)
    assert r.json()["basis_hash"] == nu and (await _lees(client, oid))["basis_verouderd"] is False
    # Opnieuw beginnen vanaf wat er draait: de inhoud van het image met die basis is meteen de versie die draait.
    r = await client.post(pad, json={"bestanden": {"jrm-scenario.md": ANDERS}, "na_versie": 4, "basis_hash": nu}, headers=B)
    assert r.status_code == 200 and (await _lees(client, oid))["stand"] == "actief"
