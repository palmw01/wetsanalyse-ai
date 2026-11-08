"""Relatievoorstellen van de keten in de batch (ADR-011, 4C): omzetten, overslaan, catalogus, opnieuw, de jurist."""
import hashlib

import pytest
from sqlalchemy import select

from app import db
from app import annotatie_v2_relaties as rel
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import Batch, RelatieBeslissing, RelatieInvoer

LAW = "urn:bwb:BWBR0004770"
ART = LAW + ":artikel:9"
ONE = ART + ":lid:1"
TEKST = "De ontvanger stelt de aanslag vast"
RB, RS, RO = "Rechtsbetrekking", "Rechtssubject", "Rechtsobject"
ZIN, ONTVANGER, AANSLAG = (0, 34), (3, 12), (19, 29)


def snapshot():
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=ART, parent_iri=LAW, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst=TEKST)]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    return dict(snapshot_id=store.digest(nodes), doel=nodes[2], nodes=nodes)


SNAP = snapshot()
HASH = SNAP["doel"]["bron_hash"]


def anker(se):
    return [dict(bron_iri=ONE, start=se[0], eind=se[1], tekst=TEKST[se[0]:se[1]], bron_hash=HASH)]


def element(se, klasse, id_):
    return dict(id=id_, klasse=klasse, tekst=TEKST[se[0]:se[1]], ankers=anker(se))


def voorstel(van, naar, type_, volgorde=None):
    return dict(van_ankers=anker(van), naar_ankers=anker(naar), type=type_, volgorde=volgorde,
                spoor={"door": "regel", "regel": "TEST"})


ELEMENTEN = [element(ZIN, RB, "zin"), element(ONTVANGER, RS, "ontvanger"), element(AANSLAG, RO, "aanslag")]


def batch(batch_id, relaties, *, elementen=ELEMENTEN, modus="nieuw", revisie=0, voltooid=True):
    return Batch.model_validate(dict(batch_id=batch_id, doel={"bron_iri": ONE}, snapshot_id=SNAP["snapshot_id"],
        elementen=elementen, verwachte_revisies={ONE: revisie} if revisie else {}, run={"modus": modus, "ronde": batch_id},
        dekking={"voltooid": voltooid, "bereik": [ONE]}, relaties=relaties))


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


async def _relaties():
    async with db.get_engine().connect() as conn:
        return {r["id"]: dict(r["inhoud"]) for r in (await conn.execute(select(db.annotatie_v2_relaties))).mappings()}


async def _revisie():
    return (await store.weergave(SNAP))["lagen"][0]["revisie"]


async def test_een_voorstel_wordt_omgezet_naar_de_elementen_en_vastgelegd_als_agentvoorstel():
    uit = await store.batch(batch("b1", [voorstel(ZIN, AANSLAG, "voorwerp"), voorstel(ONTVANGER, ZIN, "plichthebbende")]),
                            SNAP, "lex")
    assert len(uit["relaties"]) == 2 and uit["relaties_overgeslagen"] == []
    rels = await _relaties()
    r = rels[rel.relatie_id({"soort": "element", "id": "zin"}, {"soort": "element", "id": "aanslag"}, "voorwerp", None)]
    assert (r["herkomst"], r["lifecycle"], r["aandacht"]) == ("agent", "voorgesteld", "groen")
    assert r["spoor"] == {"door": "regel", "regel": "TEST"} and r["beslissingen"] == []
    view = await store.weergave(SNAP)
    assert {x["id"] for x in view["relaties"]} == set(uit["relaties"])
    assert all(not x["veranderd"] for x in view["relaties"])
    assert view["lagen"][0]["revisie"] == 1                  # één revisie voor de hele batch


async def test_wat_niet_op_te_lossen_is_wordt_overgeslagen_en_gemeld():
    uit = await store.batch(batch("b1", [
        voorstel(ZIN, (4, 12), "voorwerp"),                  # geen element met die ankers
        voorstel(AANSLAG, ZIN, "voorwerp"),                  # verkeerde richting: catalogus
        voorstel(ZIN, AANSLAG, "voorwerp", volgorde=1),      # voorwerp kent geen volgorde
        voorstel(ZIN, AANSLAG, "bestaat_niet"),
        voorstel(ZIN, AANSLAG, "voorwerp"),                  # deze wel
    ]), SNAP, "lex")
    assert [(x["index"], x["reden"]) for x in uit["relaties_overgeslagen"]] == [
        (0, "eindpunt_onbekend:naar"), (1, "klassen_passen_niet"), (2, "geen_volgorde"), (3, "onbekend_type")]
    assert len(uit["relaties"]) == 1 and len(await _relaties()) == 1


async def test_twee_klassen_op_dezelfde_ankers_beslist_de_catalogus_of_niemand():
    elementen = [*ELEMENTEN, element(AANSLAG, "Variabele en variabelewaarde", "aanslag-var")]
    uit = await store.batch(batch("b1", [voorstel(ZIN, AANSLAG, "voorwerp")], elementen=elementen), SNAP, "lex")
    r, = (await _relaties()).values()
    assert r["naar"]["id"] == "aanslag" and not uit["relaties_overgeslagen"]   # alleen Rechtsobject past bij voorwerp
    elementen = [*ELEMENTEN, element(AANSLAG, "Rechtsfeit", "aanslag-feit")]
    uit = await store.batch(batch("b2", [voorstel(ONTVANGER, AANSLAG, "voorwaarde")], elementen=elementen,
                                  revisie=await _revisie()), SNAP, "lex")
    assert uit["relaties_overgeslagen"][0]["reden"] == "klassen_passen_niet"


async def test_een_gelijk_voorstel_blijft_gelijk_en_een_afgewezen_komt_niet_terug():
    uit = await store.batch(batch("b1", [voorstel(ZIN, AANSLAG, "voorwerp")]), SNAP, "lex")
    rid, = uit["relaties"]
    await rel.beslis(rid, RelatieBeslissing(type="reject", verwachte_revisies={ONE: await _revisie()}), "jurist")
    voor = await _relaties()
    revisie = await _revisie()
    uit = await store.batch(batch("b2", [voorstel(ZIN, AANSLAG, "voorwerp")], revisie=revisie), SNAP, "lex")
    assert uit["relaties"] == [rid] and await _relaties() == voor
    assert await _revisie() == revisie                       # niets veranderd, geen revisie


async def test_opnieuw_vervangt_oude_voorstellen_maar_nooit_een_relatie_van_de_jurist_of_met_oordeel():
    uit = await store.batch(batch("b1", [voorstel(ZIN, AANSLAG, "voorwerp"), voorstel(ONTVANGER, ZIN, "rechthebbende")]),
                            SNAP, "lex")
    rels = await _relaties()
    voorwerp = next(i for i, r in rels.items() if r["type"] == "voorwerp")
    rechthebbende = next(i for i, r in rels.items() if r["type"] == "rechthebbende")
    await rel.beslis(rechthebbende, RelatieBeslissing(type="comment", comment="kijk ik nog naar",
                                                      verwachte_revisies={ONE: await _revisie()}), "jurist")
    eigen = (await rel.leg(RelatieInvoer(van={"soort": "element", "id": "ontvanger"}, naar={"soort": "element", "id": "zin"},
                                         type="plichthebbende", verwachte_revisies={ONE: await _revisie()}), "jurist"))["relatie"]
    # Een ronde opnieuw zonder voorstellen: alleen het onbeoordeelde voorstel van Lex gaat weg.
    uit = await store.batch(batch("b2", [], modus="opnieuw", revisie=await _revisie()), SNAP, "lex")
    assert uit["relaties_vervangen"] == [voorwerp]
    rels = await _relaties()
    assert rels[voorwerp]["lifecycle"] == "vervangen" and rels[voorwerp]["vervangen_in"]["batch_id"] == "b2"
    assert rels[rechthebbende]["lifecycle"] == "voorgesteld" and rels[eigen["id"]]["lifecycle"] == "human_approved"
    assert voorwerp not in {x["id"] for x in (await store.weergave(SNAP))["relaties"]}
    # Komt hetzelfde voorstel terug, dan leeft het op.
    uit = await store.batch(batch("b3", [voorstel(ZIN, AANSLAG, "voorwerp")], revisie=await _revisie()), SNAP, "lex")
    assert uit["relaties"] == [voorwerp] and (await _relaties())[voorwerp]["lifecycle"] == "voorgesteld"


async def test_een_gewone_of_onvoltooide_ronde_vervangt_niets():
    await store.batch(batch("b1", [voorstel(ZIN, AANSLAG, "voorwerp")]), SNAP, "lex")
    uit = await store.batch(batch("b2", [], revisie=await _revisie()), SNAP, "lex")
    assert uit["relaties_vervangen"] == []
    uit = await store.batch(batch("b3", [], modus="opnieuw", voltooid=False, revisie=await _revisie()), SNAP, "lex")
    assert uit["relaties_vervangen"] == []
    assert {r["lifecycle"] for r in (await _relaties()).values()} == {"voorgesteld"}


async def test_een_bezette_volgorde_wordt_gemeld():
    elementen = [*ELEMENTEN, element((13, 18), "Operator", "stelt")]
    uit = await store.batch(batch("b1", [voorstel(ONTVANGER, (13, 18), "operand", volgorde=1),
                                         voorstel(AANSLAG, (13, 18), "operand", volgorde=1),
                                         voorstel(AANSLAG, (13, 18), "operand", volgorde=2)], elementen=elementen),
                            SNAP, "lex")
    assert [(x["index"], x["reden"]) for x in uit["relaties_overgeslagen"]] == [(1, "volgorde_bezet")]
    assert len(uit["relaties"]) == 2


async def test_zonder_relaties_is_de_batch_idempotent_zoals_voorheen():
    eerst = await store.batch(batch("b1", []), SNAP, "lex")
    assert await store.batch(batch("b1", []), SNAP, "lex") == eerst
    assert "relaties" not in Batch.model_validate(batch("x", []).model_dump()).model_dump(
        mode="json", exclude={"relaties"})
