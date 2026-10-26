"""De complete graaf: alle regelingen samen, één keer opgehaald per toestand, gecomprimeerd geleverd."""
import hashlib

import pytest

from app import annotatie_v2_store as store
from app import db, graaf

IW, AWB = "urn:bwb:BWBR0004770", "urn:bwb:BWBR0005537"
H2, A9, L1, A10 = f"{IW}:hoofdstuk:II", f"{IW}:artikel:9", f"{IW}:artikel:9:lid:1", f"{IW}:artikel:10"
A4_94A = f"{AWB}:artikel:4%3A94a"
BUITEN = "urn:bwb:BWBR0002320:artikel:3"


def _knopen(bwb: str, rijen: list[tuple[str, str, str, str, str]]) -> dict:
    nodes = {}
    for i, (iri, ouder, soort, label, tekst) in enumerate(rijen):
        nodes[iri] = dict(bron_iri=iri, parent_iri=ouder, type=soort, label=label, nummer="", tekst=tekst,
                          bron_hash=hashlib.sha256(tekst.encode()).hexdigest(), volgorde=i, bwb_id=bwb)
    return nodes


BRONBOMEN = {
    "BWBR0004770": _knopen("BWBR0004770", [
        (IW, "", "Regeling", "Invorderingswet 1990", ""),
        (H2, IW, "Hoofdstuk", "Hoofdstuk", ""),
        (A9, H2, "Artikel", "Artikel 9", ""),
        (L1, A9, "Lid", "Lid 1", "De ontvanger vordert in."),
        (A10, H2, "Artikel", "Artikel 10", "Uitstel."),
    ]),
    "BWBR0005537": _knopen("BWBR0005537", [
        (AWB, "", "Regeling", "Algemene wet bestuursrecht", ""),
        (A4_94A, AWB, "Artikel", "Artikel 4:94a", "Kwijtschelding."),
    ]),
}
BRONBOMEN["BWBR0004770"][H2]["nummer"] = "II"


class Graafbron:
    """Fake GraphDB: toestanden, bronbomen en verwijzingen; telt wat er wordt opgehaald."""

    def __init__(self) -> None:
        self.toestand = {"BWBR0004770": "http://wetten.overheid.nl/id/BWBR0004770/2026-07-01/0",
                         "BWBR0005537": "http://wetten.overheid.nl/id/BWBR0005537/2026-08-15/0"}
        self.bronbomen: list[str] = []

    async def select(self, client, query: str) -> list[dict]:
        if "bwb:toestandUrl" in query:
            gekozen = [b for b in self.toestand if f'"{b}"' in query] or list(self.toestand)
            return [{"bwbId": b, "toestand": self.toestand[b], "citeertitel": BRONBOMEN[b][next(iter(BRONBOMEN[b]))]["label"]}
                    for b in sorted(gekozen)]
        if "urn:bwb:graph:BWBR0004770" in query:
            return [{"van": L1, "naar": A4_94A, "anker": "artikel 4:94a van de Awb", "label": "Artikel 4:94a"},
                    {"van": L1, "naar": BUITEN, "anker": "artikel 3", "stub": "Awr, artikel 3"}]
        return []

    async def bronrijen(self, bwb: str) -> list[dict]:
        self.bronbomen.append(bwb)
        return [bwb]                      # snapshot_uit hieronder leest alleen het id

    @staticmethod
    def snapshot(rijen, bwb, doel):
        nodes = BRONBOMEN[bwb]
        return {"snapshot_id": "s", "doel": nodes[next(iter(nodes))], "nodes": nodes, "citeertitel": ""}


@pytest.fixture
def bron(monkeypatch):
    b = Graafbron()
    monkeypatch.setattr(graaf, "_select", b.select)
    monkeypatch.setattr(graaf, "haal_bronrijen", b.bronrijen)
    monkeypatch.setattr(graaf, "snapshot_uit", b.snapshot)

    async def elementen(nodes):
        return [{"id": "e1", "klasse": "Rechtssubject", "tekst": "ontvanger", "lifecycle": "voorgesteld",
                 "eigenaar_iri": L1, "ankers": [{"bron_iri": L1}], "trace": {}}]
    monkeypatch.setattr(store, "actuele_elementen", elementen)
    graaf.leeg_cache()
    yield b
    graaf.leeg_cache()


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


async def test_alle_regelingen_in_een_graaf(bron):
    g = await graaf.graaf()
    ids = {k["id"]: k for k in g["knopen"]}
    assert [r["bwb_id"] for r in g["regelingen"]] == ["BWBR0004770", "BWBR0005537"]
    assert ids[IW]["label"] == "Invorderingswet 1990" and ids[H2]["label"] == "Hoofdstuk II"
    assert all(k["tekst"] == "" for k in g["knopen"] if k["id"].startswith("urn:bwb:")), "geen tekst: de graaf blijft licht"
    paren = {(r["soort"], r["bron"], r["doel"]) for r in g["relaties"]}
    assert {("bevat", IW, H2), ("bevat", H2, A9), ("bevat", A9, L1)} <= paren
    # Een verwijzing naar een andere geladen regeling is een gewone lijn; naar buiten een randknoop.
    assert ("verwijst_naar", L1, A4_94A) in paren and not ids[A4_94A]["rand"]
    assert ids[BUITEN]["rand"] and ids[BUITEN]["soort"] == "extern" and ids[BUITEN]["label"] == "Awr, artikel 3"
    assert ("markeert", "element:e1", L1) in paren and "klasse:Rechtssubject" in ids


async def test_de_bronboom_wordt_per_toestand_een_keer_opgehaald(bron):
    eerste = await graaf.graaf()
    await graaf.graaf()
    assert sorted(bron.bronbomen) == ["BWBR0004770", "BWBR0005537"], "de tweede keer uit de cache"
    bron.toestand["BWBR0004770"] = "http://wetten.overheid.nl/id/BWBR0004770/2027-01-01/0"
    nieuw = await graaf.graaf()
    assert sorted(bron.bronbomen) == ["BWBR0004770", "BWBR0004770", "BWBR0005537"], "een nieuwe toestand: opnieuw"
    assert nieuw["versie"] != eerste["versie"], "de werkplek cachet zijn layout op de versie"


async def test_een_keuze_van_regelingen_en_strikte_invoer(bron):
    g = await graaf.graaf(["BWBR0005537"])
    assert [r["bwb_id"] for r in g["regelingen"]] == ["BWBR0005537"]
    with pytest.raises(ValueError):
        await graaf.graaf(['BWBR1" } DROP'])


async def test_de_route_comprimeert(bron, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("graaf-route")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/annotatie/graaf", headers={"X-User-Id": "graaf-route", "Accept-Encoding": "gzip"})
        fout = await client.get("/v1/annotatie/graaf", params={"bwb_id": "nee"}, headers={"X-User-Id": "graaf-route"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
    assert len(r.json()["knopen"]) >= 8
    assert fout.status_code == 422
    get_settings.cache_clear()


# --- de plek van een bepaling (spoor H) ------------------------------------------------------------

async def test_plaatsen_geeft_het_pad_onder_de_regeling(bron):
    uit = await graaf.plaatsen([L1, A10, A4_94A])
    lid = uit[0]
    assert lid["regeling"] == {"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}
    # Het hoofdstuk krijgt zijn nummer erbij, zoals in de graaf; de regeling zelf staat er niet in.
    assert [(p["type"], p["label"]) for p in lid["pad"]] == [("Hoofdstuk", "Hoofdstuk II"), ("Artikel", "Artikel 9"), ("Lid", "Lid 1")]
    assert lid["volgorde"] < uit[1]["volgorde"]
    assert uit[2]["regeling"]["bwb_id"] == "BWBR0005537" and uit[2]["pad"][-1]["label"] == "Artikel 4:94a"


async def test_plaatsen_onbekende_bepaling_en_cache(bron):
    onbekend = "urn:bwb:BWBR0004770:artikel:999"
    uit = await graaf.plaatsen([onbekend, L1, L1])
    assert uit[0]["pad"] == [] and uit[0]["volgorde"] is None
    assert len(uit) == 2, "een dubbele IRI komt één keer terug"
    await graaf.plaatsen([A9])
    assert bron.bronbomen.count("BWBR0004770") == 1, "de structuur komt per toestand één keer uit de graaf"
    # De graaf deelt die structuur: geen tweede bronboom voor dezelfde toestand.
    await graaf.graaf(["BWBR0004770"])
    assert bron.bronbomen.count("BWBR0004770") == 1


async def test_plaatsen_weigert_wat_geen_bron_iri_is(bron):
    with pytest.raises(ValueError):
        await graaf.plaatsen(["https://example.org/x"])
    with pytest.raises(ValueError):
        await graaf.plaatsen([L1] * (graaf.MAX_PLAATSEN + 1))


async def test_de_route_plaatsen(bron, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("plaats-route")
    from app.main import app
    h = {"X-User-Id": "plaats-route"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/v1/annotatie/plaatsen", json={"bron_iris": [L1]}, headers=h)
        fout = await client.post("/v1/annotatie/plaatsen", json={"bron_iris": ["nee"]}, headers=h)
    assert r.status_code == 200 and r.json()["plaatsen"][0]["pad"][-1]["label"] == "Lid 1"
    assert fout.status_code == 422
    get_settings.cache_clear()
