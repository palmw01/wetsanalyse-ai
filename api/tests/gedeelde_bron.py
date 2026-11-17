"""De bron en het werkgebied die veel api-tests delen (testplan api V7).

Stonden in `test_annotatie_v2.py` en `test_werkgebieden.py`, en een kleine veertig testbestanden lazen ze daar uit. Een
testbestand hoort geen bibliotheek te zijn: verplaats je een test, dan breekt een ander bestand. Hier staan ze letterlijk,
ongewijzigd.

Alleen wie importeert, krijgt ze. Dat geldt ook voor de fixtures: `database` is autouse in een module die hem
importeert, en `client` en `graaf` gelden alleen waar ze geïmporteerd zijn. Daarom staan ze niet in `conftest.py`, waar
ze voor de hele suite zouden gelden.
"""
from __future__ import annotations

import hashlib

import pytest

from app import annotatie_v2_store as store, db, werkgebieden
from app.annotatie_v2_contracts import Batch

LAW = "urn:bwb:BWBR0004770"
ART = LAW + ":artikel:9"
ONE = ART + ":lid:1"
TWO = ART + ":lid:2"


def snapshot(target=ART, second="Beta"):
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=ART, parent_iri=LAW, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst="😀 Alfa Alfa"),
             dict(bron_iri=TWO, parent_iri=ART, type="Lid", label="Lid 2", tekst=second)]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    return dict(snapshot_id=store.digest(nodes), doel=next(n for n in nodes if n["bron_iri"] == target), nodes=nodes)


def element(snap, iri=ONE, start=2, end=6, **extra):
    n = store.nodes_van(snap)[iri]
    return dict(klasse="Rechtssubject", tekst=n["tekst"][start:end],
                ankers=[dict(bron_iri=iri, start=start, eind=end, tekst=n["tekst"][start:end], bron_hash=n["bron_hash"])], **extra)


def request(snap, elements=None, batch_id="test", revisions=None, **extra):
    return Batch.model_validate(dict(batch_id=batch_id, doel={"bron_iri": snap["doel"]["bron_iri"]},
        snapshot_id=snap["snapshot_id"], elementen=elements or [], verwachte_revisies=revisions or {}, **extra))


TERUGVAL = dict(klasse="", alternatieven=[{"klasse": "Rechtsbetrekking", "motivatie": ""},
                                          {"klasse": "Rechtsfeit", "motivatie": ""}],
                trace={"beslissing": {"door": "terugval", "status": "HUMAN_REVIEW"}})


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


LAW2 = "urn:bwb:BWBR0002320"
ART2 = LAW2 + ":artikel:2"


def snapshot2():
    nodes = [dict(bron_iri=LAW2, parent_iri="", type="Wet", label="AWR", tekst=""),
             dict(bron_iri=ART2, parent_iri=LAW2, type="Artikel", label="Artikel 2", tekst="Deze wet")]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0002320")
    return dict(snapshot_id=store.digest(nodes), doel=nodes[1], nodes=nodes)


class Graaf:
    """Nep-resolver: welke bronstand er 'nu' is, en of een regeling onbereikbaar is."""

    def __init__(self):
        self.tweede_lid = "Beta"
        self.weg: set[str] = set()

    async def resolve(self, doel):
        iri = doel.get("bron_iri") or (ART if doel.get("artikel") == "9" else "")
        if not iri:
            from bronmodel import BronFout
            raise BronFout("Onbekende bepaling.")
        if iri.startswith(LAW2):
            if LAW2 in self.weg:
                raise ConnectionError("graaf weg")
            return snapshot2()
        return snapshot(iri, second=self.tweede_lid)


@pytest.fixture
def graaf(monkeypatch):
    g = Graaf()
    monkeypatch.setattr(werkgebieden, "_resolve_bron", g.resolve)
    monkeypatch.setattr(werkgebieden, "_lees_bron", g.resolve)
    return g


@pytest.fixture
async def client(monkeypatch, graaf):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("jurist-a", "jurist-b")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"X-User-Id": "jurist-a"}) as c:
        yield c
    get_settings.cache_clear()


async def _nieuw(client, naam="Invorderbaarheid") -> dict:
    r = await client.post("/v1/werkgebieden", json={"naam": naam, "analysevraag": "Wanneer?"})
    assert r.status_code == 201, r.text
    return r.json()


async def _bron(client, wg: dict, **velden) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen",
                          json={"verwachte_revisie": wg["revisie"], **velden})
    assert r.status_code in (200, 201), r.text
    return r.json()
