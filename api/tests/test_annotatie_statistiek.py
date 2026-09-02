"""Wat juristen met de voorstellen van de agent deden, geaggregeerd.

De data hiervoor werd al vastgelegd — `Beslissing` met de server-afgeleide `review_reason`,
`geproduceerd_door` per element, `critic_rondes` — maar er was tot 2 sep 2026 geen consument. Deze
tests leggen vast hoe de aggregatie telt, en vooral wat ze bewust *niet* meetelt.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.annotatie_contracts import (
    AgentRun,
    AnnotatieDocument,
    AnnotatieElement,
    Beslissing,
    BeslissingType,
    CriticRonde,
    Lifecycle,
    ReviewReason,
)
from app.annotatie_statistiek import rapport

BASIS = "/v1/annotatie/documenten"


def _el(klasse="Voorwaarde", herkomst="agent", beslissingen=None, run=None, aandacht=None, **kw):
    return AnnotatieElement(
        id=kw.pop("id", "x"), klasse=klasse, tekst=kw.pop("tekst", "een fragment"),
        herkomst=herkomst, beslissingen=beslissingen or [],
        geproduceerd_door=run,
        critic_rondes=[CriticRonde(ronde=1, aandacht=aandacht)] if aandacht else [],
        **kw,
    )


def _besluit(type_, **kw):
    return Beslissing(type=type_, actor="jurist", **kw)


def _doc(elementen):
    return AnnotatieDocument(slug="s", bwbId="BWBR0004770", artikel="9", elementen=elementen)


# --- de kern van de telling -------------------------------------------------------------------------

def test_de_drie_uitkomsten_en_wat_nog_open_staat():
    st = rapport([_doc([
        _el(id="a", beslissingen=[_besluit(BeslissingType.approve)]),
        _el(id="b", beslissingen=[_besluit(BeslissingType.edit,
                                           wijziging={"klasse": {"voor": "Voorwaarde", "na": "Rechtsfeit"}},
                                           review_reason=ReviewReason.verkeerde_klasse)]),
        _el(id="c", beslissingen=[_besluit(BeslissingType.reject, review_reason=ReviewReason.bron_gemist)]),
        _el(id="d"),
    ])])
    assert (st.goedgekeurd, st.aangepast, st.afgewezen, st.open) == (1, 1, 1, 1)
    assert st.documenten == 1 and st.elementen == 4 and st.van_agent == 4


def test_een_eigen_markering_van_de_jurist_telt_niet_als_goedgekeurd_voorstel():
    """Die staat bij het aanmaken al op `human_approved`: gemaakt, niet beoordeeld.

    Meetellen zou het goedkeuringspercentage optillen zonder dat er iets is beoordeeld — precies de
    schijnzekerheid die dit rapport moet helpen voorkomen.

    Let op de vorm van de fixture: een eigen markering heeft géén beslissingen (je keurt je eigen
    markering niet goed). Geef je hem er toch een, dan repareert `_herstel_herkomst` hem naar
    agent-gemaakt-en-mens-gewijzigd — bestaand gedrag voor rijen van vóór die scheiding.
    """
    st = rapport([_doc([
        _el(id="mens", herkomst="mens", lifecycle=Lifecycle.human_approved),
        _el(id="agent", beslissingen=[_besluit(BeslissingType.approve)]),
    ])])
    assert (st.van_jurist, st.van_agent) == (1, 1)
    assert st.goedgekeurd == 1     # alleen het agent-voorstel


def test_de_zwaarste_uitkomst_wint_bij_meerdere_beslissingen():
    """"Is dit voorstel geaccepteerd" is één vraag per element, ook als er drie klikken op staan.

    De reject staat hier BEWUST niet achteraan: met de laatste beslissing als uitkomst zou een
    afronde `comment` ("toch even kijken") het element op `open` zetten, en dan telt een verworpen
    voorstel als onbeoordeeld.
    """
    st = rapport([_doc([_el(id="a", beslissingen=[
        _besluit(BeslissingType.approve),
        _besluit(BeslissingType.reject, review_reason=ReviewReason.interpretatie),
        _besluit(BeslissingType.comment, comment="toch even kijken"),
    ])])])
    assert (st.afgewezen, st.goedgekeurd, st.open) == (1, 0, 0)


def test_klasse_verschuivingen_komen_uit_de_diff():
    """Niet uit wat iemand claimde, maar uit wat de router feitelijk zag veranderen."""
    st = rapport([_doc([
        _el(id="a", beslissingen=[_besluit(BeslissingType.edit,
            wijziging={"klasse": {"voor": "Voorwaarde", "na": "Rechtsfeit"}})]),
        _el(id="b", beslissingen=[_besluit(BeslissingType.edit,
            wijziging={"klasse": {"voor": "Voorwaarde", "na": "Rechtsfeit"}})]),
        # Alleen de tekst gewijzigd: geen klasse-verschuiving.
        _el(id="c", beslissingen=[_besluit(BeslissingType.edit,
            wijziging={"tekst": {"voor": "aa", "na": "bb"}})]),
    ])])
    assert st.klasse_verschuivingen == {"Voorwaarde → Rechtsfeit": 2}


def test_per_model_maakt_twee_agentversies_vergelijkbaar():
    oud = AgentRun(model="claude-sonnet-4-6", agent_versie="1.0.0")
    nieuw = AgentRun(model="claude-sonnet-4-6", agent_versie="1.1.0")
    st = rapport([_doc([
        _el(id="a", run=oud, beslissingen=[_besluit(BeslissingType.reject,
                                                    review_reason=ReviewReason.anders)]),
        _el(id="b", run=nieuw, beslissingen=[_besluit(BeslissingType.approve)]),
        _el(id="c"),   # geen run: van vóór de registratie
    ])])
    assert st.per_model["claude-sonnet-4-6 · 1.0.0"]["afgewezen"] == 1
    assert st.per_model["claude-sonnet-4-6 · 1.1.0"]["goedgekeurd"] == 1
    assert st.per_model["onbekend"]["open"] == 1


def test_het_critic_oordeel_naast_wat_de_jurist_deed():
    """De eerste keer dat te zien is of de Critic ergens goed voor is.

    Alleen elementen die de jurist ook echt bekeek tellen mee: bij `open` weten we niet of het
    oordeel klopte, en dat als "niet gecorrigeerd" boeken zou rood kunstmatig goed laten lijken.
    """
    st = rapport([_doc([
        _el(id="a", aandacht="rood", beslissingen=[_besluit(BeslissingType.edit,
            wijziging={"klasse": {"voor": "Voorwaarde", "na": "Rechtsfeit"}})]),
        _el(id="b", aandacht="rood", beslissingen=[_besluit(BeslissingType.approve)]),
        _el(id="c", aandacht="groen", beslissingen=[_besluit(BeslissingType.approve)]),
        _el(id="d", aandacht="rood"),                       # nog niet beoordeeld → telt niet
    ])])
    assert st.critic["rood"] == {"beoordeeld": 2, "gecorrigeerd": 1}
    assert st.critic["groen"] == {"beoordeeld": 1, "gecorrigeerd": 0}


def test_zonder_critic_rondes_telt_het_aandacht_veld():
    """`critic_rondes` is pas sinds kort gevuld en de Critic kan uit staan (CRITIC_MAX_RONDES=0).

    Zonder deze terugval valt de hele Critic-doorsnede weg op precies de documenten die er al zijn.
    """
    from app.annotatie_contracts import Aandacht
    st = rapport([_doc([
        AnnotatieElement(id="a", klasse="Voorwaarde", tekst="x", aandacht=Aandacht.rood,
                         beslissingen=[_besluit(BeslissingType.reject,
                                                review_reason=ReviewReason.anders)]),
    ])])
    assert st.critic["rood"] == {"beoordeeld": 1, "gecorrigeerd": 1}


def test_niets_levert_nullen_op_en_geen_deling_door_nul():
    st = rapport([])
    assert (st.documenten, st.elementen, st.van_agent) == (0, 0, 0)
    assert st.per_klasse == {} and st.critic == {}


# --- de twee ingangen -------------------------------------------------------------------------------

@pytest.fixture
async def admin_client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "beheer:geheim")
    from app import db, ratelimit
    from app.config import get_settings
    from app.deps import get_annotatie_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_de_statistiek_kijkt_over_gebruikers_heen(admin_client):
    """Dat is waaróm hij achter het admin-token zit: per gebruiker zou het niets meten."""
    from app.annotatie_contracts import AnnotatieDocument as Doc
    from app.annotatie_store import AnnotatieStore

    store = AnnotatieStore()
    for user in ("gebruiker-a", "gebruiker-b"):
        await store.maak_document(Doc(
            slug=f"doc-{user}", user_id=user, bwbId="BWBR0004770", artikel="9",
            elementen=[_el(id=f"e-{user}", beslissingen=[_besluit(BeslissingType.approve)])],
        ))

    r = await admin_client.get("/v1/admin/annotatie-statistiek",
                               headers={"Authorization": "Bearer geheim"})
    assert r.status_code == 200
    assert r.json()["documenten"] == 2 and r.json()["goedgekeurd"] == 2


async def test_zonder_admin_token_geen_statistiek(admin_client):
    r = await admin_client.get("/v1/admin/annotatie-statistiek")
    assert r.status_code == 401


async def test_het_script_draait_over_een_echte_export(tmp_path):
    """Dezelfde aggregatie langs de andere ingang – die moet werken zónder database."""
    export = {
        "document": {"slug": "s", "bwbId": "BWBR0004770", "artikel": "9"},
        "elementen": [
            {"id": "a", "klasse": "Voorwaarde", "tekst": "indien hij verzoekt", "herkomst": "agent",
             "aandacht": "", "status": "Goedgekeurd",
             "beslissingen": [{"type": "approve", "actor": "jurist", "tijd": "2026-09-01T10:00:00Z"}]},
            {"id": "b", "klasse": "Rechtssubject", "tekst": "de ontvanger", "herkomst": "agent",
             "aandacht": "rood", "status": "Aangepast",
             "beslissingen": [{"type": "edit", "actor": "jurist", "tijd": "2026-09-01T10:01:00Z",
                               "review_reason": "verkeerde_klasse",
                               "wijziging": {"klasse": {"voor": "Rechtssubject", "na": "Rechtsobject"}}}]},
        ],
    }
    pad = tmp_path / "export.json"
    pad.write_text(json.dumps(export), encoding="utf-8")

    script = Path(__file__).resolve().parent.parent / "scripts" / "statistiek.py"
    uit = subprocess.run([sys.executable, str(script), str(pad)],
                         capture_output=True, text=True, check=True).stdout
    assert "2 elementen" in uit
    assert "Rechtssubject → Rechtsobject" in uit
    assert "verkeerde_klasse" in uit
