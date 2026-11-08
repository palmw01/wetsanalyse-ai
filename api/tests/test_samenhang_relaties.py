"""Relaties tussen markeringen in de samenhangsgraaf en de complete graaf (ADR-011): alleen wat is vastgelegd."""
from app import annotatie_v2_relaties as rel
from app import annotatie_v2_store as store
from app import samenhang
from app.annotatie_v2_contracts import Beslissing, ImplicietInvoer, RelatieBeslissing
from test_annotatie_relaties import ONE, TWO, database, lagen, leg  # noqa: F401  (fixtures)


def _geen_verwijzingen(monkeypatch):
    async def haal(iris):
        return [], []
    monkeypatch.setattr(samenhang, "_verwijzingen", haal)


async def _partij(s1, revisie):
    return (await rel.maak_impliciet(ImplicietInvoer(doel={"bron_iri": ONE}, snapshot_id=s1["snapshot_id"],
                                                     label="de belastingschuldige", toelichting="volgt uit de aanslag",
                                                     verwachte_revisies={ONE: revisie}), s1, "jurist"))["impliciet"]


async def test_relaties_en_impliciete_partijen_staan_in_de_samenhang(lagen, monkeypatch):
    _geen_verwijzingen(monkeypatch)
    s1, _ = lagen
    p = await _partij(s1, 1)
    await rel.leg(leg("ontvanger", "zin", "plichthebbende", {ONE: 2}), "jurist")
    await rel.leg(leg(p["id"], "zin", "rechthebbende", {ONE: 3}), "jurist")
    await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 4}), "jurist")   # een eindpunt in lid 2

    g = await samenhang.samenhang(s1)
    ids = {k["id"]: k for k in g["knopen"]}
    partij = ids[f"impliciet:{p['id']}"]
    assert (partij["soort"], partij["klasse"], partij["label"]) == ("impliciet", "Rechtssubject", "de belastingschuldige")
    assert partij["toelichting"] == "volgt uit de aanslag"
    lijnen = {(r["bron"], r["type"], r["doel"]): r for r in g["relaties"] if r["soort"] == "jas_relatie"}
    assert set(lijnen) == {("element:ontvanger", "plichthebbende", "element:zin"),
                           (f"impliciet:{p['id']}", "rechthebbende", "element:zin"),
                           ("element:zin", "voorwaarde", "element:termijn")}
    r = lijnen[("element:ontvanger", "plichthebbende", "element:zin")]
    assert r["groep"] == "relaties" and r["lifecycle"] == "human_approved" and r["veranderd"] is False
    assert r["leesvorm"] == r["anker_tekst"] == "is plichthebbende van"
    assert g["relaties_weggelaten"] == 0


async def test_een_eindpunt_buiten_de_graaf_valt_weg_en_telt(lagen, monkeypatch):
    _geen_verwijzingen(monkeypatch)
    s1, s2 = lagen
    await rel.leg(leg("zin", "termijn", "voorwaarde", {ONE: 1}), "jurist")
    # Een verworpen eindpunt staat niet in de graaf; de relatie blijft (veranderd) bestaan, maar niet als lijn.
    await store.beslis("termijn", Beslissing(type="reject", snapshot_id=s2["snapshot_id"], verwachte_revisies={TWO: 1}),
                       s2, "jurist")
    g = await samenhang.samenhang(s1)
    assert not [r for r in g["relaties"] if r["soort"] == "jas_relatie"]
    assert g["relaties_weggelaten"] == 1


async def test_een_afgewezen_relatie_staat_er_niet_in(lagen, monkeypatch):
    _geen_verwijzingen(monkeypatch)
    s1, _ = lagen
    r = (await rel.leg(leg("zin", "aanslag", "voorwerp", {ONE: 1}), "jurist"))["relatie"]
    await rel.beslis(r["id"], RelatieBeslissing(type="reject", verwachte_revisies={ONE: 2}), "jurist")
    g = await samenhang.samenhang(s1)
    assert not [x for x in g["relaties"] if x["soort"] == "jas_relatie"] and g["relaties_weggelaten"] == 0


async def test_alle_relaties_in_een_lezing(lagen):
    s1, _ = lagen
    p = await _partij(s1, 1)
    r = (await rel.leg(leg(p["id"], "zin", "rechthebbende", {ONE: 2}), "jurist"))["relatie"]
    relaties, partijen = await rel.alle_relaties()
    assert [x["id"] for x in relaties] == [r["id"]] and relaties[0]["leesvorm"] == "is rechthebbende van"
    assert [(x["id"], x["bron_iri"]) for x in partijen] == [(p["id"], ONE)]
