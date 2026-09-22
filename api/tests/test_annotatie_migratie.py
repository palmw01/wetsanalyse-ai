"""Migratie van per-gebruiker-documenten naar de gedeelde laag per artikel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.annotatie_contracts import (
    AgentRun, AnnotatieDocument, AnnotatieElement, Beslissing, BeslissingType, DocumentStatus,
    Lifecycle,
)
from app.annotatie_migratie import plan_samenvoeging

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
ADMIN = {"Authorization": "Bearer geheim"}
MIGREER = "/v1/admin/annotatie/migreer-naar-lagen"


def _el(id, tekst="de ontvanger", klasse="Rechtssubject", lid="1", *, herkomst="agent",
        besloten: datetime | None = None, type_=BeslissingType.approve) -> AnnotatieElement:
    beslissingen = [Beslissing(type=type_, actor="x", tijd=besloten)] if besloten else []
    lifecycle = {BeslissingType.approve: Lifecycle.human_approved,
                 BeslissingType.reject: Lifecycle.rejected}.get(type_) if besloten else Lifecycle.voorgesteld
    return AnnotatieElement(id=id, klasse=klasse, tekst=tekst, lid=lid, herkomst=herkomst,
                            lifecycle=lifecycle, beslissingen=beslissingen)


def _doc(slug, *elementen, uur=0, artikel="9", lid="", status=DocumentStatus.in_review,
         runs=()) -> AnnotatieDocument:
    return AnnotatieDocument(slug=slug, user_id=f"u-{slug}", bwbId="BWBR0004770", artikel=artikel,
                             lid=lid, status=status, elementen=list(elementen), runs=list(runs),
                             updated=T0 + timedelta(hours=uur))


# --- de regels (puur) -----------------------------------------------------------------------------

def test_groepeert_per_artikel_en_recentste_wordt_de_laag():
    plannen = plan_samenvoeging([
        _doc("oud", _el("a"), uur=1), _doc("nieuw", _el("b", "de inspecteur"), uur=2),
        _doc("lid2", _el("c", "uitstel", lid="2"), uur=0, lid="2"),   # lid-document → artikellaag
        _doc("ander", _el("d"), artikel="10"),
    ], {})
    assert [p.sleutel for p in plannen] == ["BWBR0004770:10", "BWBR0004770:9"]
    p = plannen[1]
    assert p.doel_slug == "nieuw" and p.bronnen == ["oud", "lid2"]
    assert sorted(e.tekst for e in p.elementen) == ["de inspecteur", "de ontvanger", "uitstel"]
    assert p.elementen_voor == 3 and p.dubbel == 0


def test_beoordeeld_wint_van_onbeoordeeld():
    p, = plan_samenvoeging([
        _doc("recent", _el("a", klasse="Rechtsobject"), uur=5),
        _doc("oud", _el("b", besloten=T0), uur=1),
    ], {})
    el, = p.elementen
    assert el.id == "b" and el.lifecycle is Lifecycle.human_approved
    assert [a.klasse for a in el.alternatieven] == ["Rechtsobject"]
    assert p.conflicten == []


def test_twee_oordelen_laatste_beslissing_wint_en_verliezer_in_conflict():
    p, = plan_samenvoeging([
        # Het recentste document, maar met de OUDSTE beslissing.
        _doc("recent", _el("a", besloten=T0 + timedelta(hours=1)), uur=9),
        _doc("oud", _el("b", besloten=T0 + timedelta(hours=3), type_=BeslissingType.reject), uur=4),
    ], {})
    el, = p.elementen
    assert el.id == "b" and el.lifecycle is Lifecycle.rejected
    conflict, = p.conflicten
    assert conflict["verliezer"]["id"] == "a" and conflict["verliezer_uit"] == "recent"
    assert conflict["verliezer"]["lifecycle"] == "human_approved"


def test_twee_onbeoordeeld_recentste_wint_andere_klasse_wordt_alternatief():
    p, = plan_samenvoeging([
        _doc("oud", _el("b", klasse="Rechtsobject"), uur=1),
        _doc("recent", _el("a"), uur=2),
    ], {})
    el, = p.elementen
    assert el.id == "a" and [a.klasse for a in el.alternatieven] == ["Rechtsobject"]
    assert p.dubbel == 1


def test_eigen_markering_krijgt_geen_alternatief():
    p, = plan_samenvoeging([
        _doc("recent", _el("a", klasse="Rechtsobject"), uur=5),
        _doc("oud", _el("b", herkomst="mens"), uur=1),
    ], {})
    el, = p.elementen
    assert el.id == "b" and el.alternatieven == []


def test_botsend_id_wordt_hernummerd():
    p, = plan_samenvoeging([
        _doc("recent", _el("zelfde"), uur=2),
        _doc("oud", _el("zelfde", "de inspecteur"), uur=1),
    ], {})
    assert len({e.id for e in p.elementen}) == 2
    nieuw = p.id_hernoemd["oud"]["zelfde"]
    assert any(e.id == nieuw and e.tekst == "de inspecteur" for e in p.elementen)


def test_bestaande_laag_is_het_doel_en_status_volgt_het_werk():
    laag = _doc("laag", _el("a"), uur=0, status=DocumentStatus.geaccordeerd)
    laag.laag_sleutel = "BWBR0004770:9"
    p, = plan_samenvoeging([_doc("doc", _el("b", "de inspecteur"), uur=5)], {"BWBR0004770:9": laag})
    assert p.doel_slug == "laag" and p.doel_was_laag and p.bronnen == ["doc"]
    assert p.status is DocumentStatus.in_review

    p, = plan_samenvoeging([_doc("x", _el("b"), status=DocumentStatus.geaccordeerd)], {})
    assert p.status is DocumentStatus.geaccordeerd


def test_runs_samengevoegd_op_tijd():
    r1, r2 = AgentRun(model="een", tijd=T0), AgentRun(model="twee", tijd=T0 + timedelta(hours=1))
    p, = plan_samenvoeging([_doc("recent", uur=2, runs=[r2]), _doc("oud", uur=1, runs=[r1])], {})
    assert [r.model for r in p.runs] == ["een", "twee"]


# --- het endpoint -----------------------------------------------------------------------------------

@pytest.fixture
async def omgeving(monkeypatch):
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "1")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "beheer:geheim")
    from app import db, ratelimit
    from app.annotatie_store import AnnotatieStore
    from app.config import get_settings
    from app.deps import get_annotatie_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("u-oud", "u-nieuw")

    store = AnnotatieStore()
    await store.maak_document(_doc("oud", _el("a", besloten=T0), _el("x", "de inspecteur")))
    await store.schrijf_audit("oud", "c", "u-oud", "beslissing-approve", element_id="a")
    await store.maak_document(_doc("nieuw", _el("b"), _el("x", "de minister")))
    # `maak_document` stempelt de tijd zelf; zet de volgorde vast zodat "nieuw" de recentste is.
    from sqlalchemy import update
    async with db.get_engine().begin() as conn:
        for slug, uur in (("oud", 1), ("nieuw", 2)):
            await conn.execute(update(db.annotatie_documenten)
                               .where(db.annotatie_documenten.c.slug == slug)
                               .values(updated=T0 + timedelta(hours=uur)))

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, store

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    await db.dispose_engine()


async def test_dry_run_schrijft_niets(omgeving):
    ac, store = omgeving
    r = await ac.post(MIGREER, headers=ADMIN)
    assert r.status_code == 200
    rapport = r.json()
    assert rapport["dry_run"] and rapport["documenten"] == 2 and rapport["uitgevoerd"] == []
    laag, = rapport["lagen"]
    # "de ontvanger" staat in beide; het goedgekeurde exemplaar uit "oud" verdringt het voorstel.
    assert laag["doel_slug"] == "nieuw" and laag["elementen_voor"] == 4 and laag["elementen_na"] == 3
    assert laag["dubbel"] == 0 and laag["conflicten"] == 0
    assert laag["id_hernoemd"] == {"oud": {"x": laag["id_hernoemd"]["oud"]["x"]}}
    assert (await store.laad_document("nieuw")).laag_sleutel == ""


async def test_migratie_is_idempotent_en_oude_slug_opent_de_laag(omgeving):
    ac, store = omgeving
    r = await ac.post(MIGREER, params={"dry_run": "false"}, headers=ADMIN)
    assert r.json()["uitgevoerd"] == ["BWBR0004770:9"]

    laag = await store.laad_laag("BWBR0004770:9")
    assert laag.slug == "nieuw" and laag.user_id == ""
    per_tekst = {e.tekst: e for e in laag.elementen}
    assert set(per_tekst) == {"de ontvanger", "de minister", "de inspecteur"}
    assert per_tekst["de ontvanger"].id == "a"
    assert per_tekst["de ontvanger"].lifecycle is Lifecycle.human_approved
    assert per_tekst["de minister"].id == "x" and per_tekst["de inspecteur"].id != "x"
    assert (await store.laad_document("oud")).samengevoegd_in == "nieuw"

    # Tweede run: niets meer te doen, laag ongewijzigd.
    r = await ac.post(MIGREER, params={"dry_run": "false"}, headers=ADMIN)
    assert r.json()["documenten"] == 0 and r.json()["lagen"] == []
    assert (await store.laad_laag("BWBR0004770:9")).elementen == laag.elementen

    # De oude slug (uit een chatbericht) leidt naar de laag, voor lezen én voor de audit.
    gebruiker = {"X-User-Id": "u-oud"}
    doc = (await ac.get("/v1/annotatie/documenten/oud", headers=gebruiker)).json()
    assert doc["slug"] == "nieuw"
    audit = (await ac.get("/v1/annotatie/documenten/oud/audit", headers=gebruiker)).json()
    acties = [a["actie"] for a in audit]
    assert "beslissing-approve" in acties and "laag-gemigreerd" in acties
    assert "samengevoegd-in-laag" in acties

    # Een beslissing via de oude slug landt in de laag.
    r = await ac.post("/v1/annotatie/documenten/oud/elementen/x/beslissing",
                      json={"type": "approve"}, headers=gebruiker)
    assert r.status_code == 200 and r.json()["slug"] == "nieuw"

    # Het samengevoegde document verdwijnt uit de eigen lijst en uit de statistiek.
    assert (await ac.get("/v1/annotatie/documenten", headers=gebruiker)).json() == []
    stat = (await ac.get("/v1/admin/annotatie-statistiek", headers=ADMIN)).json()
    assert stat["documenten"] == 1


async def test_gewijzigd_doel_wordt_overgeslagen(omgeving, monkeypatch):
    ac, store = omgeving
    echte = store.pas_samenvoeging_toe
    from app import annotatie_store

    async def eerst_wijzigen(self, plan):
        # Een Lex-run of beslissing tussen plannen en schrijven.
        await store.muteer_document("nieuw", "u-nieuw", lambda d: None)
        return await echte(plan)

    monkeypatch.setattr(annotatie_store.AnnotatieStore, "pas_samenvoeging_toe", eerst_wijzigen)
    r = await ac.post(MIGREER, params={"dry_run": "false"}, headers=ADMIN)
    assert r.json()["overgeslagen"] == ["BWBR0004770:9"] and r.json()["uitgevoerd"] == []
    assert (await store.laad_document("nieuw")).laag_sleutel == ""
