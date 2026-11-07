"""Eén foute laag houdt de projectieronde niet op; een storing wel, anders wacht elke laag een time-out af (D6)."""
import httpx
import pytest
from sqlalchemy import insert
from sqlalchemy.exc import OperationalError

from app import begrip_projectie as bp, db, graaf_projectie_v2 as gp


def _status(code: int) -> httpx.HTTPStatusError:
    verzoek = httpx.Request("PUT", "http://graaf/x")
    return httpx.HTTPStatusError("x", request=verzoek, response=httpx.Response(code, request=verzoek))


@pytest.mark.parametrize("fout, storing", [
    (httpx.ConnectError("weg"), True), (httpx.ReadTimeout("traag"), True), (_status(503), True),
    (OperationalError("x", {}, Exception()), True), (_status(400), False), (ValueError("x"), False),
    (KeyError("veld"), False),
])
def test_storing_of_inhoud(fout, storing):
    assert gp.is_verbindingsfout(fout) is storing


@pytest.fixture
async def twee_lagen(monkeypatch):
    db.init_engine("sqlite+aiosqlite:///:memory:")
    await db.create_all()
    async with db.get_engine().begin() as conn:
        for i in ("a", "b"):
            await conn.execute(insert(db.annotatie_v2_lagen).values(
                id=i, bron_iri=f"urn:{i}", revisie=1, status="in_review", snapshot_id="s", geprojecteerd_revisie=0,
                updated=db.utcnow()))

    async def niets(*_a, **_k):
        return {"manifest": {}} if _k or _a else None

    monkeypatch.setattr(gp, "zoek_kandidaten", niets)
    monkeypatch.setattr(gp, "verwijder_verweesde_projecties", niets)
    monkeypatch.setattr(gp, "zorg_voor_vocabulaire", niets)
    yield
    await db.dispose_engine()


async def test_een_foute_laag_slaat_alleen_die_laag_over(twee_lagen, monkeypatch):
    async def projecteer(laag_id):
        if laag_id == "a":
            raise ValueError("kapotte inhoud")
        return True

    monkeypatch.setattr(gp, "projecteer", projecteer)
    assert await gp.reconcile() == 1


async def test_een_storing_stopt_de_ronde(twee_lagen, monkeypatch):
    geprobeerd = []

    async def projecteer(laag_id):
        geprobeerd.append(laag_id)
        raise httpx.ConnectError("weg")

    monkeypatch.setattr(gp, "projecteer", projecteer)
    with pytest.raises(httpx.ConnectError):
        await gp.reconcile()
    assert len(geprobeerd) == 1


@pytest.mark.parametrize("fout, verwacht", [(ValueError("x"), 1), (httpx.ConnectError("weg"), None)])
async def test_begrippen_volgen_dezelfde_regel(monkeypatch, fout, verwacht):
    async def stand():
        return {"a": {}, "b": {}}

    async def register():
        return {}

    async def graphs(*_a):
        return []

    async def projecteer(wid, zeker=False):
        if wid == "a":
            raise fout
        return "geschreven"

    monkeypatch.setattr(bp, "postgres_stand", stand)
    monkeypatch.setattr(bp, "register", register)
    monkeypatch.setattr(bp, "sparql_select", graphs)
    monkeypatch.setattr(bp, "invoer_hash", lambda _inv: "h")
    monkeypatch.setattr(bp, "projecteer", projecteer)
    if verwacht is None:
        with pytest.raises(httpx.ConnectError):
            await bp.reconcile()
    else:
        assert await bp.reconcile() == verwacht
