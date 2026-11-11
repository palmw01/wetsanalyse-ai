"""Tekst ná een opsomming blijft op zijn plek.

De bron zet een `<al>` achter een `<lijst>` in hetzelfde element. Voegde de importer alle alinea's
samen, dan stond die tekst vóór de lijst: "van een derde die: voor zover de uitbetaling …", gevolgd
door 1° en 2°. De fixtures zijn echte bepalingen, uit de bron geknipt, uit drie wetsfamilies.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from bronmodel.bwb.models import Onderdeel, Wet
from bronmodel.bwb.parser import ToestandParser
from rdflib import Dataset, URIRef

from app.collect import collect
from app.dekking import bron_tekens
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BRONMODEL = Path(__file__).resolve().parents[3] / "packages" / "bronmodel"


def _wet(naam: str) -> Wet:
    return ToestandParser().parse(FIXTURES / f"{naam}.xml")


def _artikelen(wet: Wet) -> dict:
    gevonden = {a.nummer: a for a in wet.losse_artikelen}

    def loop(delen) -> None:
        for deel in delen:
            gevonden.update({a.nummer: a for a in deel.artikelen})
            loop(deel.subdelen)

    loop(wet.structuurdelen)
    return gevonden


def _lid(wet: Wet, artikel: str, lid: str):
    return next(x for x in _artikelen(wet)[artikel].leden if x.nummer == lid)


def _onderdeel(onderdelen: list[Onderdeel], nummer: str) -> Onderdeel:
    return next(o for o in onderdelen if o.nummer == nummer)


def test_onderdeel_ur_awir_artikel_6_lid_2_c() -> None:
    c = _onderdeel(_lid(_wet("slottekst_ur_awir"), "6", "2").onderdelen, "c.")

    assert c.tekst == "van een derde die:"
    assert [s.nummer for s in c.subonderdelen] == ["1°.", "2°.", ""]
    slot = c.subonderdelen[-1]
    assert slot.slottekst
    assert slot.tekst.startswith("voor zover de uitbetaling plaatsvindt")
    assert slot.id == "BWBR0019237/Artikel6/Lid2/Onderdeelc/Slottekst1"


def test_lid_awir_artikel_45_lid_1() -> None:
    lid = _lid(_wet("slottekst_awir"), "45", "1")

    assert lid.tekst.endswith(":")
    assert lid.onderdelen[-1].slottekst
    assert not any(o.slottekst for o in lid.onderdelen[:-1])


def test_lid_iw_artikel_24_lid_1() -> None:
    lid = _lid(_wet("slottekst_iw1990"), "24", "1")

    assert lid.tekst.endswith(":")
    assert lid.onderdelen[-1].slottekst
    assert lid.onderdelen[-1].tekst not in lid.tekst


def test_onderdeel_iw_artikel_25_lid_8_b() -> None:
    b = _onderdeel(_lid(_wet("slottekst_iw1990"), "25", "8").onderdelen, "b.")

    assert b.tekst.endswith("vermenigvuldigd met:")
    assert b.subonderdelen[-1].tekst.startswith("verminderd met de over die uitgedeelde reserves")


def test_lid_awr_artikel_21d_lid_1() -> None:
    lid = _lid(_wet("slottekst_awr"), "21d", "1")

    assert lid.onderdelen[-1].slottekst
    assert lid.onderdelen[-1].tekst not in lid.tekst


def test_lijst_en_tekst_wisselen_af_iw_artikel_25_lid_14() -> None:
    lid = _lid(_wet("slottekst_iw1990"), "25", "14")

    assert [o.nummer for o in lid.onderdelen] == ["a.", "b.", "c.", "", "1°.", "2°.", "3°."]
    assert lid.onderdelen[3].tekst == "Het uitstel wordt beëindigd:"
    assert "Het uitstel wordt beëindigd:" not in lid.tekst


def test_divisie_leidraad() -> None:
    wet = _wet("slottekst_leidraad")
    divisie = wet.divisies[0]

    alles = [divisie, *divisie.subdivisies]
    onderdelen = [o for d in alles for o in d.onderdelen]
    tweede = next(o for o in onderdelen if o.nummer.startswith("2"))
    assert any(s.slottekst for s in tweede.subonderdelen)
    assert sum(1 for s in tweede.subonderdelen if not s.slottekst) >= 2


@pytest.mark.parametrize(
    "fixture",
    ["slottekst_ur_awir", "slottekst_awir", "slottekst_iw1990", "slottekst_awr", "slottekst_leidraad"],
)
def test_geen_tekst_verloren_en_elke_node_uniek(fixture: str) -> None:
    pad = FIXTURES / f"{fixture}.xml"
    wet = ToestandParser().parse(pad)
    vocab = Vocab()
    graaf, _ = GraphDbWriter(url="offline", repository="offline", vocab=vocab).build_graph(wet)
    batch, _ = collect(wet)

    ids = [r["id"] for rijen in batch.nodes.values() for r in rijen]
    assert len(ids) == len(set(ids))
    # Elk teken uit de bron staat één keer in de graaf: niet weg, en niet dubbel.
    assert abs(sum(len(str(o)) for o in graaf.objects(None, vocab.ns.tekst)) - bron_tekens(pad)) < 20


def test_slottekst_draagt_zijn_eigen_verwijzingen() -> None:
    """Een verwijzing in de slottekst hoort niet meer bij de aanhef: die verwijst er niet naar."""
    for wet, artikel, lid in (("slottekst_iw1990", "24", "1"), ("slottekst_awir", "45", "1")):
        gevonden = _lid(_wet(wet), artikel, lid)
        slot = gevonden.onderdelen[-1]
        assert {v.doc for v in gevonden.verwijzingen}.isdisjoint({v.doc for v in slot.verwijzingen})


def test_collect_noemt_de_slottekst_op_zijn_plek() -> None:
    batch, _ = collect(_wet("slottekst_ur_awir"))
    rijen = {r["id"]: r for r in batch.nodes["Onderdeel"]}
    slot = rijen["BWBR0019237/Artikel6/Lid2/Onderdeelc/Slottekst1"]

    assert slot["label"] == "Slottekst"
    assert slot["vindplaats"] == "Artikel 6, lid 2, onderdeel c"
    assert slot["ref_key"] is None  # een jci die niet bestaat zou op wetten.overheid.nl niets vinden
    twee = rijen["BWBR0019237/Artikel6/Lid2/Onderdeelc/Onderdeel2"]
    assert {"from": slot["id"], "to": twee["id"]} in batch.rels[("Onderdeel", "VOLGT_OP", "Onderdeel")]
    assert twee["volgnummer"] < slot["volgnummer"]


def test_alleen_onderdelen_met_een_slottekst_krijgen_een_keten() -> None:
    """De rest van de regeling blijft gelijk, en dus ook haar snapshot-id."""
    batch, _ = collect(_wet("slottekst_ur_awir"))
    ketens = batch.rels[("Onderdeel", "VOLGT_OP", "Onderdeel")]

    assert {r["from"].rsplit("/", 1)[0] for r in ketens} == {
        "BWBR0019237/Artikel6/Lid2/Onderdeelc"
    }


def _snapshot(fixture: str, bwb: str) -> dict:
    """Wat api en graph-qa zien: de eigen `bron_query` van `bronmodel` op de geschreven graaf."""
    if not BRONMODEL.exists():
        pytest.skip("bronmodel staat niet in deze kopie")
    sys.path.insert(0, str(BRONMODEL))
    try:
        import bronmodel
    finally:
        sys.path.pop(0)

    wet = _wet(fixture)
    vocab = Vocab()
    graaf, _ = GraphDbWriter(url="offline", repository="offline", vocab=vocab).build_graph(wet)
    data = Dataset()
    benoemd = data.graph(URIRef(f"urn:bwb:graph:{bwb}"))
    for triple in graaf:
        benoemd.add(triple)
    rijen = [
        {str(k): str(v) for k, v in rij.asdict().items()}
        for rij in data.query(bronmodel.bron_query(bwb))
    ]
    return bronmodel.bouw_snapshot(rijen, bwb_id=bwb)


def test_bronmodel_leest_de_bronvolgorde_ur_awir() -> None:
    nodes = _snapshot("slottekst_ur_awir", "BWBR0019237")["nodes"]
    teksten = [n["tekst"] for n in nodes if n["tekst"]]

    i = teksten.index("van een derde die:")
    assert teksten[i + 1].startswith("een subsidiebeschikking heeft ontvangen")
    assert teksten[i + 2] == "voldoet aan de norm NEN-ISO 9001;"
    assert teksten[i + 3].startswith("voor zover de uitbetaling plaatsvindt")
    # Niet twee keer gelezen: de aanhef staat er één keer, de slottekst ook.
    assert teksten.count("van een derde die:") == 1
    assert teksten.count(teksten[i + 3]) == 1


def test_bronmodel_leest_de_bronvolgorde_bij_afwisseling_iw() -> None:
    nodes = _snapshot("slottekst_iw1990", "BWBR0004770")["nodes"]
    lid14 = next(n for n in nodes if n["bron_iri"].endswith(":artikel:25:lid:14"))
    onder = [n for n in nodes if n["parent_iri"] == lid14["bron_iri"]]

    assert [n["nummer"] for n in onder] == ["a.", "b.", "c.", "", "1°.", "2°.", "3°."]
    assert onder[3]["label"] == "Slottekst"
    assert onder[3]["vindplaats"] == "Artikel 25, lid 14"
    assert onder[3]["bron_hash"]


def test_bronmodel_slottekst_is_een_eigen_ankerbron() -> None:
    """Een anker rekent in de eigen tekst van de node, dus ook hier begint de tekst op 0."""
    snapshot = _snapshot("slottekst_ur_awir", "BWBR0019237")
    slot = next(n for n in snapshot["nodes"] if n["label"] == "Slottekst")

    assert slot["tekst"].startswith("voor zover")
    assert slot["parent_iri"].endswith(":o:c")
    assert slot["bepaling"].endswith(":artikel:6:lid:2")
