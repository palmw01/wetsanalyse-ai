"""De gedeelde annotatielaag per artikel: één laag voor iedereen, hash per lid, verouderen i.p.v.
intrekken, en het vangnet onder het hergebruik van Lex."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

LAAG = "/v1/annotatie/lagen/BWBR0004770/9"
DOCS = "/v1/annotatie/documenten"


@pytest.fixture
async def app_(monkeypatch):
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "1")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")

    from app import db, ratelimit
    from app.config import get_settings
    from app.deps import get_annotatie_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("jurist-a", "jurist-b")

    from app.main import app
    yield app

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    await db.dispose_engine()


def _client(app, userid: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                       headers={"X-User-Id": userid})


@pytest.fixture
async def a(app_):
    async with _client(app_, "jurist-a") as c:
        yield c


@pytest.fixture
async def b(app_):
    async with _client(app_, "jurist-b") as c:
        yield c


def _el(tekst: str, lid: str = "1", klasse: str = "Rechtssubject", *, lid_hash: str = "h1",
        bron_hash: str = "art1", id: str | None = None) -> dict:
    el = {"klasse": klasse, "tekst": tekst, "lid": lid,
          "anker": {"lid": lid, "start": 0, "eind": len(tekst), "bron_hash": bron_hash,
                    "lid_hash": lid_hash}}
    if id:
        el["id"] = id
    return el


def _ronde(*elementen, leden=(("1", "h1"),), modus="auto", bron_hash="art1") -> dict:
    return {"elementen": list(elementen), "modus": modus, "bron_hash": bron_hash,
            "citeertitel": "Invorderingswet 1990",
            "leden": [{"lid": lid, "hash": h, "iri": f"urn:bwb:BWBR0004770:artikel:9:lid:{lid}"}
                      for lid, h in leden]}


async def test_een_laag_voor_iedereen(a, b):
    r = await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))
    assert r.status_code == 200
    laag = r.json()
    assert laag["laag_sleutel"] == "BWBR0004770:9" and laag["user_id"] == ""
    assert laag["leden"]["1"]["hash"] == "h1"

    # jurist-b ziet dezelfde laag en kan erop beslissen – via de gewone slug-routes.
    zelfde = (await b.get(LAAG)).json()
    assert zelfde["slug"] == laag["slug"]
    el_id = zelfde["elementen"][0]["id"]
    r = await b.post(f"{DOCS}/{laag['slug']}/elementen/{el_id}/beslissing", json={"type": "approve"})
    assert r.status_code == 200

    audit = (await a.get(f"{DOCS}/{laag['slug']}/audit")).json()
    actoren = {r["actor"] for r in audit}
    assert {"jurist-a", "jurist-b"} <= actoren
    assert audit[0]["actie"] == "laag-aangemaakt"

    # Een tweede artikelschrijfwijze komt in dezelfde laag terecht.
    r = await b.get("/v1/annotatie/lagen/bwbr0004770/9")
    assert r.json()["slug"] == laag["slug"]


async def test_onbekende_laag_is_404(a):
    assert (await a.get(LAAG)).status_code == 404
    assert (await a.post(f"{LAAG}/hergebruik", json={})).status_code == 404


async def test_laag_kan_niet_verwijderd_worden(a):
    slug = (await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))).json()["slug"]
    assert (await a.delete(f"{DOCS}/{slug}")).status_code == 403
    assert (await a.get(LAAG)).status_code == 200


async def test_vangnet_negeert_ongewijzigd_lid_in_auto(a):
    await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))
    r = await a.put(f"{LAAG}/elementen", json=_ronde(_el("de belastingschuldige")))
    assert r.status_code == 200
    assert r.headers["X-Hergebruikt-Leden"] == "1"
    assert [e["tekst"] for e in r.json()["elementen"]] == ["de ontvanger"]


async def test_opnieuw_voegt_alleen_toe(a):
    eerste = (await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger"), _el("kan uitstel verlenen", klasse="Rechtsbetrekking")))).json()
    slug = eerste["slug"]
    goedgekeurd = eerste["elementen"][0]["id"]
    await a.post(f"{DOCS}/{slug}/elementen/{goedgekeurd}/beslissing", json={"type": "approve"})

    # Een tweede run ziet het andere fragment niet meer en stelt iets nieuws voor: niets verdwijnt.
    r = await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger", klasse="Rechtsobject"), _el("de belastingschuldige"), modus="opnieuw"))
    assert r.status_code == 200 and "X-Hergebruikt-Leden" not in r.headers
    per_tekst = {e["tekst"]: e for e in r.json()["elementen"]}
    assert set(per_tekst) == {"de ontvanger", "kan uitstel verlenen", "de belastingschuldige"}
    # Het beoordeelde element is bevroren: de andere klasse van de agent verandert het niet.
    assert per_tekst["de ontvanger"]["klasse"] == "Rechtssubject"
    assert per_tekst["de ontvanger"]["lifecycle"] == "human_approved"
    audit = (await a.get(f"{DOCS}/{slug}/audit")).json()
    assert not any(r["actie"] == "element-ingetrokken" for r in audit)


async def test_bronwijziging_veroudert_per_lid_en_behoudt_oordeel(a):
    eerste = (await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger"), _el("de inspecteur", lid="2", lid_hash="h2"),
        leden=(("1", "h1"), ("2", "h2"))))).json()
    slug = eerste["slug"]
    ontvanger = next(e["id"] for e in eerste["elementen"] if e["tekst"] == "de ontvanger")
    await a.post(f"{DOCS}/{slug}/elementen/{ontvanger}/beslissing", json={"type": "approve"})

    # Alleen lid 1 veranderde; Lex annoteert alleen lid 1 opnieuw.
    r = await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger", lid_hash="h1b", bron_hash="art2"),
        leden=(("1", "h1b"),), bron_hash="art2"))
    assert r.status_code == 200
    laag = r.json()
    oud = next(e for e in laag["elementen"] if e["id"] == ontvanger)
    assert oud["verouderd"] is True and oud["lifecycle"] == "human_approved"
    nieuw = [e for e in laag["elementen"] if e["tekst"] == "de ontvanger" and not e["verouderd"]]
    assert len(nieuw) == 1 and nieuw[0]["id"] != ontvanger and nieuw[0]["lifecycle"] == "voorgesteld"
    # Lid 2 is niet aangeraakt.
    assert next(e for e in laag["elementen"] if e["tekst"] == "de inspecteur")["verouderd"] is False
    assert laag["leden"]["1"]["hash"] == "h1b" and laag["leden"]["2"]["hash"] == "h2"
    # Verouderd telt niet als bronversie en niet als werkvoorraad.
    # art1 is nog de versie van lid 2; de verouderde markering van lid 1 telt niet meer mee.
    assert laag["bronversies"] == ["art1", "art2"]
    samenvatting = (await a.get("/v1/annotatie/lagen")).json()[0]
    assert samenvatting["verouderd"] == 1

    # Een verouderd element is alleen-lezen, een kanttekening mag.
    r = await a.post(f"{DOCS}/{slug}/elementen/{ontvanger}/beslissing",
                     json={"type": "heropen"})
    assert r.status_code == 409
    r = await a.post(f"{DOCS}/{slug}/elementen/{ontvanger}/beslissing",
                     json={"type": "comment", "comment": "gold voor de oude tekst"})
    assert r.status_code == 200

    acties = [r["actie"] for r in (await a.get(f"{DOCS}/{slug}/audit")).json()]
    assert "element-verouderd" in acties


async def test_bronversies_negeren_verouderde_elementen(a):
    await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))
    r = await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger", lid_hash="h1b", bron_hash="art2"), leden=(("1", "h1b"),), bron_hash="art2"))
    assert r.json()["bronversies"] == ["art2"]


async def test_bronwijziging_heropent_afgeronde_laag(a):
    slug = (await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))).json()["slug"]
    await a.post(f"{DOCS}/{slug}/status", json={"status": "geaccordeerd"})

    # Ongewijzigd + auto: niets te doen, geen 409 – de laag was gewoon herbruikbaar.
    r = await a.put(f"{LAAG}/elementen", json=_ronde(_el("de belastingschuldige")))
    assert r.status_code == 200 and r.json()["status"] == "geaccordeerd"
    # Expliciet opnieuw op een afgeronde laag: eerst heropenen.
    r = await a.put(f"{LAAG}/elementen", json=_ronde(_el("de belastingschuldige"), modus="opnieuw"))
    assert r.status_code == 409

    r = await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger", lid_hash="h1b"), leden=(("1", "h1b"),)))
    assert r.status_code == 200 and r.json()["status"] == "in_review"
    acties = [x["actie"] for x in (await a.get(f"{DOCS}/{slug}/audit")).json()]
    assert "heropend-door-bronwijziging" in acties


async def test_oude_ankers_zonder_lid_hash_worden_op_bron_hash_getoetst(a):
    oud_actueel = _el("de ontvanger", lid_hash="", bron_hash="seg1")        # lid-scoped document
    oud_artikel = _el("de inspecteur", lid_hash="", bron_hash="art1")       # artikel-document
    oud_weg = _el("kan uitstel verlenen", klasse="Rechtsbetrekking", lid_hash="", bron_hash="oud")
    zonder_anker = {"klasse": "Rechtssubject", "tekst": "de minister", "lid": "1"}
    # Eerst zonder leden: zo komen ze binnen zoals de migratie ze straks aanlevert.
    await a.put(f"{LAAG}/elementen", json={
        "elementen": [oud_actueel, oud_artikel, oud_weg, zonder_anker], "modus": "opnieuw"})

    r = await a.put(f"{LAAG}/elementen", json=_ronde(leden=(("1", "seg1"),), bron_hash="art1"))
    verouderd = {e["tekst"]: e["verouderd"] for e in r.json()["elementen"]}
    assert verouderd == {"de ontvanger": False, "de inspecteur": False,
                         "kan uitstel verlenen": True, "de minister": False}


async def test_eigen_markering_krijgt_lidstand(a):
    slug = (await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))).json()["slug"]
    r = await a.post(f"{DOCS}/{slug}/elementen", json={
        "klasse": "Rechtsobject", "tekst": "uitstel", "lid": "1",
        "anker": {"lid": "1", "start": 0, "eind": 7, "bron_hash": "art1"}})
    assert r.status_code == 201
    eigen = next(e for e in r.json()["elementen"] if e["tekst"] == "uitstel")
    assert eigen["anker"]["lid_hash"] == "h1"


async def test_hergebruik_stempelt_ankers_en_legt_vast(a, b):
    eerste = (await a.put(f"{LAAG}/elementen", json=_ronde(
        _el("de ontvanger", lid_hash="", bron_hash="seg1")))).json()
    el_id = eerste["elementen"][0]["id"]
    await a.post(f"{DOCS}/{eerste['slug']}/status", json={"status": "geaccordeerd"})

    r = await b.post(f"{LAAG}/hergebruik", json={
        "leden": [{"lid": "1", "hash": "h1"}, {"lid": "2", "hash": "h2"}],
        "ankers": [
            {"element_id": el_id, "anker": {"lid": "1", "start": 40, "eind": 52,
                                           "bron_hash": "art9", "lid_hash": "h1"}},
            # verkeerde lengte → geen bijstempeling maar een wijziging, dus geweigerd
            {"element_id": el_id, "anker": {"lid": "1", "start": 40, "eind": 45}},
        ],
        "run": {"model": "m", "modus": "hergebruik", "leden": ["1", "2"]},
    })
    assert r.status_code == 200
    laag = r.json()
    assert laag["status"] == "geaccordeerd"      # hergebruik werkt ook op een afgeronde laag
    assert laag["elementen"][0]["anker"]["start"] == 40
    assert laag["elementen"][0]["anker"]["lid_hash"] == "h1"
    assert laag["leden"]["2"]["hash"] == "h2"
    assert laag["runs"][-1]["modus"] == "hergebruik"

    audit = (await a.get(f"{DOCS}/{laag['slug']}/audit")).json()
    regel = next(x for x in audit if x["actie"] == "laag-hergebruikt")
    assert regel["actor"] == "jurist-b"
    assert regel["detail"]["gestempeld"] == 1 and regel["detail"]["geweigerd"] == 1


async def test_hergebruik_slaat_gewijzigd_lid_over(a):
    await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))
    r = await a.post(f"{LAAG}/hergebruik", json={"leden": [{"lid": "1", "hash": "anders"}]})
    assert r.json()["leden"]["1"]["hash"] == "h1"


async def test_lijst_mijn_filtert_op_audit(a, b):
    await a.put(f"{LAAG}/elementen", json=_ronde(_el("de ontvanger")))
    await b.put("/v1/annotatie/lagen/BWBR0004770/10/elementen", json=_ronde(_el("de ontvanger")))
    assert len((await a.get("/v1/annotatie/lagen")).json()) == 2
    mijn = (await a.get("/v1/annotatie/lagen", params={"mijn": "true"})).json()
    assert [l["artikel"] for l in mijn] == ["9"]
    # Lagen horen niet in de per-gebruiker-documentenlijst.
    assert (await a.get(DOCS)).json() == []


async def test_haal_of_maak_verliest_race_netjes(app_, monkeypatch):
    """De unieke index beslist, niet de check vooraf: verliest deze aanroep de race, dan krijgt hij
    de laag van de winnaar in plaats van een 500.

    Bewust gesimuleerd en niet met twee gelijktijdige requests: de in-memory SQLite van de suite
    deelt één verbinding (`StaticPool`), dus de rollback van de verliezer draait daar ook de nog
    niet gecommitte insert van de winnaar terug. Dat toetst SQLite, niet deze code. Op Postgres
    wacht de tweede insert op de commit van de eerste en ziet de herlaadactie de rij gewoon."""
    from app.annotatie_store import AnnotatieStore

    store = AnnotatieStore()
    winnaar, nieuw = await store.haal_of_maak_laag("BWBR0004770", "9", "", "c")
    assert nieuw

    echte = store.laad_laag
    eerste = {"ja": True}

    async def laat_check_missen(sleutel):
        if eerste.pop("ja", False):
            return None          # de ander was net iets eerder dan onze check
        return await echte(sleutel)

    monkeypatch.setattr(store, "laad_laag", laat_check_missen)
    laag, nieuw = await store.haal_of_maak_laag("BWBR0004770", "9", "", "c")
    assert not nieuw and laag.slug == winnaar.slug
