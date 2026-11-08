"""Relaties tussen markeringen en impliciete partijen (ADR-011): leggen, toetsen, beoordelen, doorwerking, wissen."""
import hashlib

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app import db
from app import annotatie_v2_relaties as rel
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import Batch, Beslissing, ImplicietInvoer, RelatieBeslissing, RelatieInvoer

LAW = "urn:bwb:BWBR0004770"
ART = LAW + ":artikel:9"
ONE = ART + ":lid:1"
TWO = ART + ":lid:2"
TEKST_1 = "De ontvanger stelt de aanslag vast"
TEKST_2 = "indien de termijn is verstreken"
RB, RS, RO, VW = "Rechtsbetrekking", "Rechtssubject", "Rechtsobject", "Voorwaarde"


def snapshot(target=ONE):
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=ART, parent_iri=LAW, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst=TEKST_1),
             dict(bron_iri=TWO, parent_iri=ART, type="Lid", label="Lid 2", tekst=TEKST_2)]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    return dict(snapshot_id=store.digest(nodes), doel=next(n for n in nodes if n["bron_iri"] == target), nodes=nodes)


def element(snap, iri, start, end, id_, klasse):
    n = store.nodes_van(snap)[iri]
    return dict(id=id_, klasse=klasse, tekst=n["tekst"][start:end],
                ankers=[dict(bron_iri=iri, start=start, eind=end, tekst=n["tekst"][start:end], bron_hash=n["bron_hash"])])


def batch(snap, elements, batch_id, revisie=0):
    iri = snap["doel"]["bron_iri"]
    return Batch.model_validate(dict(batch_id=batch_id, doel={"bron_iri": iri}, snapshot_id=snap["snapshot_id"],
        elementen=elements, verwachte_revisies={iri: revisie} if revisie else {}, run={"modus": "nieuw"},
        dekking={"voltooid": True, "bereik": [iri]}))


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


@pytest.fixture
async def lagen():
    """Lid 1: een rechtsbetrekking (de zin), het rechtssubject en het rechtsobject, van Lex. Lid 2: een voorwaarde van
    de jurist zelf."""
    s1, s2 = snapshot(ONE), snapshot(TWO)
    await store.batch(batch(s1, [element(s1, ONE, 0, 34, "zin", RB), element(s1, ONE, 3, 12, "ontvanger", RS),
                                 element(s1, ONE, 19, 29, "aanslag", RO)], "lex-1"), s1, "lex")
    await store.batch(batch(s2, [element(s2, TWO, 0, 31, "termijn", VW)], "eigen-2"), s2, "jurist", mens=True)
    return s1, s2


async def _revisie(snap) -> int:
    return (await store.weergave(snap))["lagen"][0]["revisie"]


def leg(van, naar, type_, revisies, **extra):
    soort = lambda x: {"soort": "impliciet" if x.startswith("I") else "element", "id": x}
    return RelatieInvoer(van=soort(van), naar=soort(naar), type=type_, verwachte_revisies=revisies, **extra)


async def _audit(actie):
    async with db.get_engine().connect() as conn:
        return [dict(r) for r in (await conn.execute(select(db.annotatie_v2_audit).where(
            db.annotatie_v2_audit.c.actie == actie))).mappings().all()]


async def test_een_relatie_leggen_raakt_de_dragerlaag_en_staat_in_de_weergave(lagen):
    s1, _ = lagen
    r = (await rel.leg(leg("ontvanger", "zin", "plichthebbende", {ONE: 1}), "jurist"))["relatie"]
    assert r["id"].startswith("R") and r["lifecycle"] == "human_approved" and r["herkomst"] == "mens"
    assert r["leesvorm"] == "is plichthebbende van" and r["veranderd"] is False
    assert (r["van"]["klasse"], r["naar"]["klasse"]) == (RS, RB)
    view = await store.weergave(s1)
    assert [x["id"] for x in view["relaties"]] == [r["id"]]
    assert view["lagen"][0]["revisie"] == 2
    assert (await _audit("relatie-gelegd"))[0]["laag_id"] == view["lagen"][0]["id"]


@pytest.mark.parametrize("van, naar, type_, extra, fout", [
    ("zin", "ontvanger", "plichthebbende", {}, "klassen_passen_niet"),     # de richting telt
    ("ontvanger", "zin", "bestaat_niet", {}, "onbekend_type"),
    ("zin", "zin", "voorwerp", {}, "naar_zichzelf"),
    ("zin", "aanslag", "voorwerp", {"volgorde": 1}, "geen_volgorde"),
])
async def test_wat_niet_bij_de_catalogus_past_is_een_422(lagen, van, naar, type_, extra, fout):
    with pytest.raises(HTTPException) as exc:
        await rel.leg(leg(van, naar, type_, {ONE: 1}, **extra), "jurist")
    assert exc.value.status_code == 422 and exc.value.detail["fout"] == fout


async def test_dezelfde_relatie_twee_keer_en_een_oude_revisie(lagen):
    await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 1}), "jurist")
    with pytest.raises(HTTPException) as exc:
        await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 2}), "jurist")
    assert exc.value.status_code == 409 and exc.value.detail["fout"] == "al_vastgelegd"
    with pytest.raises(HTTPException) as exc:
        await rel.leg(leg("ontvanger", "zin", "plichthebbende", {ONE: 1}), "jurist")
    assert exc.value.status_code == 412


async def test_een_eindpunt_in_een_andere_laag_staat_in_beide_weergaven(lagen):
    s1, s2 = lagen
    r = (await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 1}), "jurist"))["relatie"]
    assert r["laag_id"] == (await store.weergave(s1))["lagen"][0]["id"]   # de drager is de rechtsbetrekking
    assert [x["id"] for x in (await store.weergave(s2))["relaties"]] == [r["id"]]
    assert await _revisie(s2) == 1                                        # de andere laag houdt haar revisie


async def test_een_veranderd_eindpunt_vraagt_een_nieuw_oordeel(lagen):
    s1, _ = lagen
    r = (await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 1}), "jurist"))["relatie"]
    # Een ander leest de toelichting bij: dat raakt de stand niet. Een klassewissel wel.
    await store.beslis("aanslag", Beslissing(type="edit", wijziging={"klasse": RS}, snapshot_id=s1["snapshot_id"],
                                             verwachte_revisies={ONE: 2}), s1, "jurist")
    [r2] = (await store.weergave(s1))["relaties"]
    assert r2["veranderd"] is True and r2["naar"]["klasse"] == RS
    # Goedkeuren kan dan niet meer: het paar past niet bij het type.
    with pytest.raises(HTTPException) as exc:
        await rel.beslis(r["id"], RelatieBeslissing(type="approve", verwachte_revisies={ONE: 3}), "jurist")
    assert exc.value.detail["fout"] == "klassen_passen_niet"
    await store.beslis("aanslag", Beslissing(type="edit", wijziging={"klasse": RO}, snapshot_id=s1["snapshot_id"],
                                             verwachte_revisies={ONE: 3}), s1, "jurist")
    # Terug naar dezelfde klasse is weer dezelfde stand.
    assert (await store.weergave(s1))["relaties"][0]["veranderd"] is False


async def test_afwijzen_heropenen_en_goedkeuren(lagen):
    r = (await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 1}), "jurist"))["relatie"]
    afgewezen = (await rel.beslis(r["id"], RelatieBeslissing(type="reject", comment="te ruim",
                                                             verwachte_revisies={ONE: 2}), "jurist"))["relatie"]
    assert afgewezen["lifecycle"] == "rejected"
    with pytest.raises(HTTPException) as exc:
        await rel.beslis(r["id"], RelatieBeslissing(type="approve", verwachte_revisies={ONE: 3}), "jurist")
    assert exc.value.status_code == 409
    await rel.beslis(r["id"], RelatieBeslissing(type="heropen", verwachte_revisies={ONE: 3}), "jurist")
    ok = (await rel.beslis(r["id"], RelatieBeslissing(type="approve", verwachte_revisies={ONE: 4}), "jurist"))["relatie"]
    assert ok["lifecycle"] == "human_approved"
    assert [b["type"] for b in ok["beslissingen"]] == ["markering", "reject", "heropen", "approve"]


async def test_volgorde_is_uniek_per_operator(lagen):
    s1, _ = lagen
    await store.batch(batch(s1, [element(s1, ONE, 13, 18, "stelt", "Operator")], "lex-op", 1), s1, "lex")
    await rel.leg(leg("ontvanger", "stelt", "operand", {ONE: 2}, volgorde=1), "jurist")
    with pytest.raises(HTTPException) as exc:
        await rel.leg(leg("aanslag", "stelt", "operand", {ONE: 3}, volgorde=1), "jurist")
    assert exc.value.detail["fout"] == "volgorde_bezet"
    r = (await rel.leg(leg("aanslag", "stelt", "operand", {ONE: 3}, volgorde=2), "jurist"))["relatie"]
    assert r["volgorde"] == 2


async def test_een_gewist_element_neemt_zijn_relaties_mee(lagen):
    s1, s2 = lagen
    r = (await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 1}), "jurist"))["relatie"]
    res = await store.verwijder("termijn", 1, "jurist")
    assert res["relaties"] == [r["id"]]
    assert (await store.weergave(s1))["relaties"] == []
    assert await _revisie(s1) == 3                    # de dragerlaag kreeg een revisie bij het wissen
    assert [a["detail"]["relatie"]["id"] for a in await _audit("relatie-gewist")] == [r["id"]]


async def test_de_bepaling_verwijderen_wist_ook_relaties_elders(lagen):
    s1, s2 = lagen
    await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 1}), "jurist")
    res = await store.verwijder_weergave(s2, {TWO: 1}, "iemand")
    assert res["verwijderd"]["relaties"] == 1
    assert (await store.weergave(s1))["relaties"] == []


async def test_een_impliciete_partij_is_een_rechtssubject_van_de_jurist(lagen):
    s1, _ = lagen
    with pytest.raises(ValidationError):
        ImplicietInvoer(doel={"bron_iri": ONE}, snapshot_id=s1["snapshot_id"], klasse=RO, label="x", toelichting="y")
    p = (await rel.maak_impliciet(ImplicietInvoer(doel={"bron_iri": ONE}, snapshot_id=s1["snapshot_id"],
                                                  label="de belastingschuldige", toelichting="volgt uit de aanslag",
                                                  verwachte_revisies={ONE: 1}), s1, "jurist"))["impliciet"]
    assert p["id"].startswith("I") and p["klasse"] == RS
    r = (await rel.leg(leg(p["id"], "zin", "rechthebbende", {ONE: 2}), "jurist"))["relatie"]
    view = await store.weergave(s1)
    assert [x["id"] for x in view["impliciet"]] == [p["id"]]
    assert view["relaties"][0]["van"]["tekst"] == "de belastingschuldige"
    # Geen markering: de elementen en hun aantal blijven gelijk.
    assert len(view["elementen"]) == 3
    gewist = await rel.wis_impliciet(p["id"], {ONE: 3}, "jurist")
    assert gewist["relaties"] == [r["id"]]
    assert (await store.weergave(s1))["impliciet"] == []


async def test_alleen_een_eigen_relatie_is_te_wissen(lagen):
    r = (await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 1}), "jurist"))["relatie"]
    with pytest.raises(HTTPException) as exc:
        await rel.wis(r["id"], {ONE: 2}, "iemand-anders")
    assert exc.value.status_code == 409
    await rel.wis(r["id"], {ONE: 2}, "jurist")
    assert (await store.weergave(snapshot(ONE)))["relaties"] == []


async def test_de_projectie_krijgt_de_relaties_van_de_dragerlaag(lagen):
    """Projectie en graafcontrole bouwen uit `laag_invoer`: de relatie en de impliciete partij zitten erin, alleen
    bij de laag die ze draagt."""
    from app import graaf_projectie_v2 as projectie
    s1, s2 = lagen
    p = (await rel.maak_impliciet(ImplicietInvoer(doel={"bron_iri": ONE}, snapshot_id=s1["snapshot_id"], label="x",
                                                  toelichting="y", verwachte_revisies={ONE: 1}), s1, "jurist"))["impliciet"]
    r = (await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 2}), "jurist"))["relatie"]
    lagen_ = {l["bron_iri"]: l for l in (await store.weergave(s1))["lagen"] + (await store.weergave(s2))["lagen"]}
    async with db.get_engine().connect() as conn:
        _e, _d, eigen = await projectie.laag_invoer(conn, lagen_[ONE])
        _e, _d, ander = await projectie.laag_invoer(conn, lagen_[TWO])
    assert [x["id"] for x in eigen["relaties"]] == [r["id"]] and [x["id"] for x in eigen["impliciet"]] == [p["id"]]
    assert ander == {"relaties": [], "impliciet": []}
    g = projectie.bouw_graaf(lagen_[ONE], _e, relaties=eigen)
    assert (projectie.relatie_iri(r["id"]), projectie.JAS.naar, projectie.element_iri("termijn")) in g
