"""Samenhangsgraaf: structuur, annotaties en letterlijke verwijzingen, zonder afgeleide relaties."""
import pytest

from app import annotatie_v2_store as store
from app import db, samenhang
from test_annotatie_v2 import ART, LAW, ONE, TWO, element, request, snapshot

ANDER = "urn:bwb:BWBR0004770:artikel:10"
STUB = "urn:bwb:BWBR0002320:artikel:3"


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


def rijen(uit=None, inn=None):
    async def haal(iris):
        return uit or [], inn or []
    return haal


async def test_lid_toont_hele_artikel_met_structuur_annotaties_en_verwijzingen(monkeypatch):
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen(
        uit=[{"van": TWO, "naar": ONE, "anker": "het eerste lid"},
             {"van": ONE, "naar": ANDER, "anker": "artikel 10", "label": "Artikel 10"},
             {"van": ONE, "naar": STUB, "stub": "Awb, artikel 3"}],
        inn=[{"van": "urn:bwb:BWBR0004770:artikel:20:lid:1", "naar": ART, "label": "Artikel 20, lid 1"}]))
    g = await samenhang.samenhang(snapshot(ONE))
    ids = {k["id"]: k for k in g["knopen"]}
    assert g["artikel_iri"] == ART and g["verwijzingen_beschikbaar"]
    assert {LAW, ART, ONE, TWO} <= ids.keys()
    assert ("bevat", LAW, ART) in {(r["soort"], r["bron"], r["doel"]) for r in g["relaties"]}
    # binnen het artikel: gewone kant, geen randknoop
    assert any(r["bron"] == TWO and r["doel"] == ONE and r["groep"] == "verwijzingen" for r in g["relaties"])
    assert not ids[ONE]["rand"]
    assert ids[ANDER]["rand"] and ids[ANDER]["soort"] == "artikel" and ids[ANDER]["artikel"] == "10"
    assert ids[STUB]["soort"] == "extern" and ids[STUB]["label"] == "Awb, artikel 3"
    assert ids["urn:bwb:BWBR0004770:artikel:20:lid:1"]["lid"] == "1"
    markeringen = [k for k in g["knopen"] if k["soort"] == "markering"]
    assert len(markeringen) == 2 and "klasse:Rechtssubject" in ids
    assert all(k["element_id"] for k in markeringen)


async def test_afgewezen_en_verouderde_markeringen_blijven_weg(monkeypatch):
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    # Andere tekst in lid 2 maakt het element daar verouderd.
    g = await samenhang.samenhang(snapshot(second="Gamma"))
    assert [k["tekst"] for k in g["knopen"] if k["soort"] == "markering"] == ["Alfa"]


async def test_verwijzingen_onbeschikbaar_geeft_toch_structuur(monkeypatch):
    async def faalt(iris):
        return None
    monkeypatch.setattr(samenhang, "_verwijzingen", faalt)
    g = await samenhang.samenhang(snapshot())
    assert not g["verwijzingen_beschikbaar"]
    assert not any(r["groep"] == "verwijzingen" for r in g["relaties"])
    assert {k["id"] for k in g["knopen"]} >= {LAW, ART, ONE, TWO}


async def test_afkapping_en_ontdubbeling(monkeypatch):
    veel = [{"van": ONE, "naar": f"urn:bwb:BWBR0004770:artikel:{i}"} for i in range(100, 100 + samenhang.MAX_VERWIJZINGEN + 1)]
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen(uit=veel + veel[:3]))
    g = await samenhang.samenhang(snapshot())
    assert g["afgekapt"]
    assert sum(r["groep"] == "verwijzingen" for r in g["relaties"]) == samenhang.MAX_VERWIJZINGEN


async def test_zonder_graaf_geen_fout_bij_verwijzingen(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GRAPHDB_URL", "")
    get_settings.cache_clear()
    assert await samenhang._verwijzingen([ONE]) is None
    get_settings.cache_clear()


def test_queries_beperken_zich_tot_de_scope():
    q = samenhang._uitgaand([ONE, TWO])
    assert f"<{ONE}>" in q and f"<{TWO}>" in q and "VALUES ?van" in q
    assert f"LIMIT {samenhang.MAX_VERWIJZINGEN + 1}" in samenhang._inkomend([ONE])


async def test_endpoint_vereist_gebruiker_en_meldt_capability(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-samenhang")
    from app.main import app

    async def resolve(goal):
        return snapshot(goal.get("bron_iri", ART))
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/annotatie/samenhang", params={"bron_iri": ONE})).status_code == 401
        headers = {"X-User-Id": "v2-samenhang"}
        r = await client.get("/v1/annotatie/samenhang", params={"bron_iri": ONE}, headers=headers)
        assert r.status_code == 200 and r.json()["artikel_iri"] == ART
        assert (await client.get("/v1/annotatie/capabilities", headers=headers)).json()["samenhang"]
    get_settings.cache_clear()


async def test_markeringen_dragen_herkomst_aandacht_en_spoor(monkeypatch):
    snap = snapshot()
    spoor = {"beslissing": {"door": "model"}, "twijfel": [{"reden": "DETECTOR_CONFLICT"}]}
    await store.batch(request(snap, [element(snap, trace=spoor, aandacht="geel", jas_subtype="parameter")]), snap, "a")
    await store.batch(request(snap, [element(snap, TWO, 0, 4)], batch_id="mens", revisions={TWO: 0}), snap, "jan", mens=True)
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    g = await samenhang.samenhang(snapshot())
    per_tekst = {k["tekst"]: k for k in g["knopen"] if k["soort"] == "markering"}
    agent, mens = per_tekst["Alfa"], per_tekst["Beta"]
    assert (agent["herkomst"], agent["aandacht"], agent["subtype"], agent["beslist_door"], agent["twijfel"]) == \
        ("agent", "geel", "parameter", "model", True)
    assert (mens["herkomst"], mens["aandacht"], mens["beslist_door"], mens["twijfel"]) == ("mens", "", "", False)
    # Structuurknopen houden de lege standaardwaarden.
    assert all(k["herkomst"] == "" for k in g["knopen"] if k["soort"] != "markering")


async def test_een_terugval_markeert_wel_maar_krijgt_geen_klasseknoop(monkeypatch):
    from test_annotatie_v2 import TERUGVAL
    snap = snapshot(ONE)
    await store.batch(request(snap, [{**element(snap), **TERUGVAL}]), snap, "lex")
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    g = await samenhang.samenhang(snap)
    [m] = [k for k in g["knopen"] if k["soort"] == "markering"]
    assert m["klasse"] == "" and m["beslist_door"] == "terugval"
    assert not any(k["soort"] == "klasse" for k in g["knopen"])
    assert not any(r["soort"] == "heeft_klasse" for r in g["relaties"])


async def test_structuurdeel_toont_zijn_artikelen_zonder_leden(monkeypatch):
    """Een overzichtsantwoord noemt hoofdstukken; de samenhang daarvan is het deel met zijn artikelen.
    Leden, markeringen en verwijzingen horen bij een geopend artikel."""
    import hashlib

    hfd = LAW + ":hoofdstuk:II"
    # Zoals de bronboom hem levert: `bwb:label` is alleen het woord, het nummer staat apart.
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=hfd, parent_iri=LAW, type="Hoofdstuk", label="Hoofdstuk", nummer="II", tekst=""),
             dict(bron_iri=ART, parent_iri=hfd, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst="Alfa"),
             dict(bron_iri=ANDER, parent_iri=hfd, type="Artikel", label="Artikel 10", tekst="")]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    snap = dict(snapshot_id=store.digest(nodes), doel=nodes[1], nodes=nodes)

    async def niet_vragen(iris):
        raise AssertionError("geen verwijzingsquery voor een structuurdeel")
    monkeypatch.setattr(samenhang, "_verwijzingen", niet_vragen)
    g = await samenhang.samenhang(snap)
    ids = {k["id"]: k for k in g["knopen"]}
    assert g["artikel_iri"] == hfd and g["verwijzingen_beschikbaar"]
    assert set(ids) == {LAW, hfd, ART, ANDER}
    assert ids[hfd]["soort"] == "deel" and ids[ART]["soort"] == "artikel" and not ids[ART]["rand"]
    assert ids[hfd]["label"] == "Hoofdstuk II", "het nummer hoort bij het label"
    assert {(r["bron"], r["doel"]) for r in g["relaties"]} == {(LAW, hfd), (hfd, ART), (hfd, ANDER)}


async def test_meer_doelen_in_een_regeling_halen_de_bronboom_een_keer_op(monkeypatch):
    """Een overzicht opent zijn delen in één verzoek. Per deel een verzoek haalde per deel de hele
    bronboom van de regeling op (de Leidraad: 1601 knopen, 8×); nu één keer per regeling."""
    import hashlib

    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-samenhang-meer")
    from app.main import app

    h2, h5 = LAW + ":hoofdstuk:II", LAW + ":hoofdstuk:V"
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=h2, parent_iri=LAW, type="Hoofdstuk", label="Hoofdstuk", nummer="II", tekst=""),
             dict(bron_iri=ART, parent_iri=h2, type="Artikel", label="Artikel 9", tekst="Alfa"),
             dict(bron_iri=h5, parent_iri=LAW, type="Hoofdstuk", label="Hoofdstuk", nummer="V", tekst=""),
             dict(bron_iri=ANDER, parent_iri=h5, type="Artikel", label="Artikel 10", tekst="Beta")]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    opgehaald: list[str] = []

    async def haal(bwb):
        opgehaald.append(bwb)
        return nodes

    def snapshot_uit(rijen, bwb, doel):
        if doel["bron_iri"] not in {n["bron_iri"] for n in rijen}:
            from bronmodel import BronFout
            raise BronFout("Bronnode bestaat niet")
        return dict(snapshot_id=store.digest(rijen), doel=next(n for n in rijen if n["bron_iri"] == doel["bron_iri"]), nodes=rijen)

    monkeypatch.setattr(annotatie_v2, "haal_bronrijen", haal)
    monkeypatch.setattr(annotatie_v2, "snapshot_uit", snapshot_uit)
    onbekend = LAW + ":hoofdstuk:XX"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/annotatie/samenhang/meer", params=[("bron_iri", h5), ("bron_iri", h2), ("bron_iri", onbekend)],
                             headers={"X-User-Id": "v2-samenhang-meer"})
    assert r.status_code == 200
    data = r.json()
    assert opgehaald == ["BWBR0004770"], "één bronboom voor twee delen in dezelfde regeling"
    assert [s["artikel_iri"] for s in data["resultaten"]] == [h5, h2], "in de volgorde van het verzoek"
    assert [f["bron_iri"] for f in data["fouten"]] == [onbekend]
    assert {k["id"]: k["label"] for k in data["resultaten"][0]["knopen"]}[h5] == "Hoofdstuk V"
    get_settings.cache_clear()
