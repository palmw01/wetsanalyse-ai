"""De ketting bij een antwoord: de keten tot de relevante diepte, met begrippen die daar gelden."""
import hashlib
from datetime import UTC, datetime

import httpx
import pytest
from bronmodel.definities import geldigheid_uit, losse_termen, term_vindplaats

from app import annotatie_v2_store as store
from app import begrip_store, db, graaf, samenhang_antwoord
from test_annotatie_v2 import element, request

LAW = "urn:bwb:BWBR0004770"
H1 = f"{LAW}:hoofdstuk:I"
H2 = f"{LAW}:hoofdstuk:II"
A2 = f"{H1}:artikel:2"
A2L1 = f"{A2}:lid:1"
A2M = f"{A2L1}:o:m"
A2K = f"{A2L1}:o:k"
A2R = f"{A2L1}:o:r"
A9 = f"{H2}:artikel:9"
L1 = f"{A9}:lid:1"
L2 = f"{A9}:lid:2"
A33 = f"{H2}:artikel:33a"
A33L3 = f"{A33}:lid:3"
A33X = f"{A33L3}:o:a"
A40 = f"{H2}:artikel:40"
A40L1 = f"{A40}:lid:1"


def boom(*rijen):
    nodes = []
    for i, (iri, ouder, soort, tekst) in enumerate(rijen):
        nodes.append(dict(bron_iri=iri, parent_iri=ouder, type=soort, label=iri.rsplit(":", 2)[-2:][-1], tekst=tekst, volgorde=i,
                          bwb_id="BWBR0004770", vindplaats=iri.removeprefix(LAW), nummer="",
                          bron_hash=hashlib.sha256(tekst.encode()).hexdigest()))
    return dict(snapshot_id=store.digest(nodes), doel=nodes[0], nodes=nodes, citeertitel="Invorderingswet 1990")


def standaard():
    return boom(
        (LAW, "", "Regeling", ""),
        (H1, LAW, "Hoofdstuk", ""),
        (A2, H1, "Artikel", ""),
        (A2L1, A2, "Lid", "In deze wet wordt verstaan onder:"),
        (A2M, A2L1, "Onderdeel", "belastingaanslag: de aanslag;"),
        (A2K, A2L1, "Onderdeel", "aanslagbiljet: de kennisgeving;"),
        (A2R, A2L1, "Onderdeel", "Rijk: het land;"),
        (H2, LAW, "Hoofdstuk", "Dit hoofdstuk regelt de invordering."),
        (A9, H2, "Artikel", ""),
        (L1, A9, "Lid", "Een belastingaanslag is invorderbaar zes weken na het aanslagbiljet. Het rijk zwijgt. Een lichaam ook."),
        (L2, A9, "Lid", "Broer van lid 1 met belastingaanslagen."),
        (A33, H2, "Artikel", ""),
        (A33L3, A33, "Lid", "Voor de toepassing van dit artikel wordt verstaan onder:"),
        (A33X, A33L3, "Onderdeel", "lichaam: een vennootschap;"),
        (A40, H2, "Artikel", ""),
        (A40L1, A40, "Lid", "In dit hoofdstuk wordt onder zwijgen verstaan: stil zijn."),
    )


DEFINITIES = [{"node": A2M, "begrip": "belastingaanslag"}, {"node": A2K, "begrip": "aanslagbiljet"},
              {"node": A2R, "begrip": "Rijk"}, {"node": A33X, "begrip": "lichaam"}]


@pytest.fixture(autouse=True)
async def database(monkeypatch):
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    samenhang_antwoord._DEFINITIES.clear()
    snap = standaard()

    async def lees_bron(doel):
        return snap

    async def geen_verwijzingen(client, query):
        return []

    async def definities(bwb, snapshot_id):
        return DEFINITIES

    monkeypatch.setattr(graaf, "lees_bron", lees_bron)
    monkeypatch.setattr(samenhang_antwoord, "_select", geen_verwijzingen)
    monkeypatch.setattr(samenhang_antwoord, "_definities", definities)
    yield snap
    await db.dispose_engine()


def ids(g, soort=None):
    return {k["id"] for k in g["knopen"] if soort is None or k["soort"] == soort}


async def test_de_keten_gaat_van_regeling_naar_doel_zonder_broers():
    g = await samenhang_antwoord.antwoord([L1])
    assert {LAW, H2, A9, L1} <= ids(g)
    assert L2 not in ids(g) and A33 not in ids(g)
    assert g["doelen"] == [L1] and g["keten"] is True
    assert next(k for k in g["knopen"] if k["id"] == LAW)["label"] == "Invorderingswet 1990"


async def test_begrip_uit_de_wet_met_definitie_en_fragment():
    g = await samenhang_antwoord.antwoord([L1])
    b = next(k for k in g["knopen"] if k["id"] == "term:BWBR0004770:belastingaanslag")
    assert b["soort"] == "begrip" and b["begrip_bron"] == "wet"
    assert b["definities"][0]["bron_iri"] == A2M and b["definities"][0]["bereik"] == "regeling"
    assert "In deze wet" in b["definities"][0]["aanhef"]
    assert A2M in ids(g) and next(k for k in g["knopen"] if k["id"] == A2M)["rand"]
    assert ("definieert", A2M, b["id"]) in {(r["soort"], r["bron"], r["doel"]) for r in g["relaties"]}
    assert any(r["soort"] == "komt_voor_in" and r["doel"] == L1 and r["anker_tekst"] == "belastingaanslag" for r in g["relaties"])


async def test_definitie_buiten_haar_bereik_telt_niet():
    g = await samenhang_antwoord.antwoord([L1])
    assert "term:BWBR0004770:lichaam" not in ids(g)


async def test_binnen_het_bereik_telt_de_definitie_wel(database):
    nodes = store.nodes_van(database)
    nodes[A33L3]["tekst"] = "Voor de toepassing van dit artikel wordt verstaan onder: een lichaam ook."
    g = await samenhang_antwoord.antwoord([A33L3])
    assert "term:BWBR0004770:lichaam" in ids(g)


async def test_dit_hoofdstuk_wordt_via_de_boom_opgelost(database):
    nodes = store.nodes_van(database)
    g = geldigheid_uit("In dit hoofdstuk")
    assert samenhang_antwoord._geldt_voor(nodes, A40L1, g, L1)
    assert not samenhang_antwoord._geldt_voor(nodes, A40L1, g, A2L1)


async def test_lid_en_artikel_n_als_bereik(database):
    nodes = store.nodes_van(database)
    assert samenhang_antwoord._geldt_voor(nodes, A2M, geldigheid_uit("In dit lid"), A2K)
    assert not samenhang_antwoord._geldt_voor(nodes, A2M, geldigheid_uit("In dit lid"), L1)
    assert samenhang_antwoord._geldt_voor(nodes, A33X, geldigheid_uit("Voor de toepassing van artikel 33a"), A33L3)


async def test_twee_definities_zijn_een_begrip(monkeypatch):
    async def twee(bwb, snapshot_id):
        return [{"node": A2M, "begrip": "belastingaanslag"}, {"node": A2K, "begrip": "belastingaanslag"}]
    monkeypatch.setattr(samenhang_antwoord, "_definities", twee)
    g = await samenhang_antwoord.antwoord([L1])
    b = [k for k in g["knopen"] if k["soort"] == "begrip"]
    assert len(b) == 1 and {d["bron_iri"] for d in b[0]["definities"]} == {A2M, A2K}


async def test_een_naam_is_hoofdlettergevoelig():
    g = await samenhang_antwoord.antwoord([L1])
    assert "term:BWBR0004770:rijk" not in ids(g)


async def test_meervoud_telt_mee_met_het_fragment():
    g = await samenhang_antwoord.antwoord([L2])
    assert any(r["soort"] == "komt_voor_in" and r["anker_tekst"] == "belastingaanslagen" for r in g["relaties"])


async def test_doel_dat_zelf_definieert_draagt_het_begrip():
    g = await samenhang_antwoord.antwoord([A2M])
    assert "term:BWBR0004770:belastingaanslag" in ids(g)


async def test_kinderen_een_niveau_eronder():
    g = await samenhang_antwoord.antwoord([A9])
    assert {L1, L2} <= ids(g) and A33 not in ids(g)


async def test_doel_dat_niet_bestaat_valt_terug_op_de_ouder():
    g = await samenhang_antwoord.antwoord([f"{A9}:lid:14"])
    assert g["doelen"] == [A9] and g["fouten"][0]["bron_iri"].endswith(":lid:14")


async def test_ontdubbelt_over_doelen():
    g = await samenhang_antwoord.antwoord([L1, L2])
    alle = [k["id"] for k in g["knopen"]]
    assert len(alle) == len(set(alle)) and alle.count(A9) == 1
    assert g["doelen"] == [L1, L2]


async def test_haperende_graaf_zegt_niet_dat_er_geen_begrippen_zijn(monkeypatch):
    async def stuk(bwb, snapshot_id):
        raise httpx.ConnectError("weg")
    monkeypatch.setattr(samenhang_antwoord, "_definities", stuk)
    g = await samenhang_antwoord.antwoord([L1])
    assert g["begrippen_beschikbaar"] is False and not ids(g, "begrip")


async def test_markeringen_alleen_op_het_doel_en_wijst_naar_de_kortste(database):
    snap = {**database, "doel": store.nodes_van(database)[L1]}
    tekst = store.nodes_van(database)[L1]["tekst"]
    start = tekst.index("belastingaanslag")
    await store.batch(request(snap, [element(snap, L1, start, start + 16), element(snap, L1, 0, len(tekst) - 1),
                                     ]), snap, "a")
    snap2 = {**database, "doel": store.nodes_van(database)[L2]}
    await store.batch(request(snap2, [element(snap2, L2, 0, 5)], batch_id="b"), snap2, "a")
    g = await samenhang_antwoord.antwoord([L1])
    markeringen = [k for k in g["knopen"] if k["soort"] == "markering"]
    assert len(markeringen) == 2 and all(k["lid"] != "2" for k in markeringen)
    assert not any(k["id"].startswith("klasse:") for k in g["knopen"])
    kort = next(k for k in markeringen if k["tekst"] == "belastingaanslag")
    assert any(r["soort"] == "komt_voor_in" and r["doel"] == kort["id"] for r in g["relaties"])


async def test_boven_de_grens_geen_enkele_markering(monkeypatch, database):
    monkeypatch.setattr(samenhang_antwoord, "MAX_MARKERINGEN", 0)
    snap = {**database, "doel": store.nodes_van(database)[L1]}
    await store.batch(request(snap, [element(snap, L1, 0, 5)]), snap, "a")
    g = await samenhang_antwoord.antwoord([L1])
    assert not ids(g, "markering") and g["ingekort"]["markeringen"] == {L1: 1}


async def test_los_gesprek_alleen_geaccordeerde_generieke_begrippen(monkeypatch, database):
    gevraagd = []

    async def generiek(element_ids):
        gevraagd.append(element_ids)
        return []

    async def werkgebied(werkgebied_id):
        raise AssertionError("een los gesprek leest geen werkgebied")

    monkeypatch.setattr(begrip_store, "generiek_bij_elementen", generiek)
    monkeypatch.setattr(begrip_store, "samenhang", werkgebied)
    snap = {**database, "doel": store.nodes_van(database)[L1]}
    await store.batch(request(snap, [element(snap, L1, 0, 5)]), snap, "a")
    await samenhang_antwoord.antwoord([L1])
    assert gevraagd


async def test_onzekere_verwijzing_is_een_telling(monkeypatch):
    async def rijen(client, query):
        return [{"van": L1, "naar": f"{LAW}:artikel:167", "anker": "artikel 167", "betrouwbaarheid": "laag"},
                {"van": L1, "naar": "urn:bwb:BWBR0002448", "anker": "Algemene termijnenwet", "stub": "BWBR0002448"}]
    monkeypatch.setattr(samenhang_antwoord, "_select", rijen)
    g = await samenhang_antwoord.antwoord([L1])
    assert g["ingekort"]["onzekere_verwijzingen"] == 1
    assert f"{LAW}:artikel:167" not in ids(g)
    assert next(k for k in g["knopen"] if k["id"] == "urn:bwb:BWBR0002448")["label"] == "Algemene termijnenwet"


async def test_begrip_uit_het_werkgebied_hangt_aan_een_getoonde_markering(monkeypatch, database):
    async def werkgebied(werkgebied_id):
        return {"begrippen": [{"id": "b1", "naam": "aanslag", "status": "concept", "definitie": "d"},
                              {"id": "b2", "naam": "elders", "status": "concept", "definitie": "d"}],
                "koppelingen": []}
    monkeypatch.setattr(begrip_store, "samenhang", werkgebied)
    snap = {**database, "doel": store.nodes_van(database)[L1]}
    (await store.batch(request(snap, [element(snap, L1, 0, 5)]), snap, "a"))
    element_id = next(iter(await store.actuele_elementen(store.nodes_van(database))))["id"]

    async def met_koppeling(werkgebied_id):
        data = await werkgebied(werkgebied_id)
        return {**data, "koppelingen": [
            {"begrip_id": "b1", "element_id": element_id, "rol": "duiding", "beoordeling": "open"},
            {"begrip_id": "b2", "element_id": element_id, "rol": "duiding", "beoordeling": "afgewezen"}]}
    monkeypatch.setattr(begrip_store, "samenhang", met_koppeling)
    g = await samenhang_antwoord.antwoord([L1], "w1")
    b = next(k for k in g["knopen"] if k["id"] == "begrip:b1")
    assert b["begrip_bron"] == "werkgebied" and b["werkgebied_id"] == "w1"
    assert "begrip:b2" not in ids(g)
    assert any(r["soort"] == "duidt" and r["bron"] == "begrip:b1" and r["doel"] == f"element:{element_id}" for r in g["relaties"])


async def test_generiek_bij_elementen_leest_alleen_geaccordeerd_en_niet_afgewezen():
    nu = datetime.now(UTC)
    async with db.get_engine().begin() as conn:
        for id_, werkgebied, status in [("g1", None, "geaccordeerd"), ("g2", None, "concept"), ("w1", "w", "geaccordeerd"),
                                        ("g3", None, "geaccordeerd")]:
            await conn.execute(db.begrippen.insert().values(
                id=id_, werkgebied_id=werkgebied, status=status, revisie=1, inhoud={"naam": id_, "definitie": "d"},
                aangemaakt_door="a", aangemaakt=nu, gewijzigd=nu))
            await conn.execute(db.begrip_koppelingen.insert().values(
                id=f"k{id_}", begrip_id=id_, werkgebied_id="w", element_id="e1", rol="duiding", motivatie="", bewijs={},
                beoordeling="afgewezen" if id_ == "g3" else "open", toegevoegd_door="a", toegevoegd=nu))
    rijen = await begrip_store.generiek_bij_elementen({"e1"})
    assert [r["id"] for r in rijen] == ["g1"]


def test_term_op_woordgrens():
    assert term_vindplaats("aanslag", "de aanslagen") == "aanslagen"
    assert term_vindplaats("aanslag", "De voorlopige aanslag.") == "aanslag"
    assert term_vindplaats("aanslag", "Aanslag vervalt") == "Aanslag"
    assert term_vindplaats("aanslag", "de belastingaanslag") == ""
    assert term_vindplaats("kat", "de katten") == "katten"
    assert term_vindplaats("lichaam", "de lichamen") == ""     # liever gemist dan verkeerd
    assert term_vindplaats("Rijk", "het rijk") == ""
    assert term_vindplaats("", "tekst") == ""


def test_losse_termen_houden_hun_hoofdletters():
    assert losse_termen("directeur, inspecteur of  ontvanger") == ["directeur", "inspecteur", "ontvanger"]
    assert losse_termen("Rijk") == ["Rijk"]
