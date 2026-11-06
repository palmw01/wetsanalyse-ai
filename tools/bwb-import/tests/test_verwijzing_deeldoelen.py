"""Een verwijzing volgt haar hele tekst: "artikel 25, derde lid" wijst naar lid 3.

De `doc` van een `<intref>`/`<extref>` stopt in de BWB bij het artikel; lid en onderdeel staan alleen
in de tekst. De voorbeelden hieronder zijn letterlijke ankers uit Awir, AWR, IW 1990 en de Awb.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.collect import (
    Batch,
    bepalingsindex,
    collect,
    koppel_deelverwijzingen,
)
from app.graphdb_writer import GraphDbWriter
from app.models import Artikel, Lid, Onderdeel, Verwijzing, VerwijzingSoort, Wet
from app.parser import ToestandParser
from app.rdf_vocab import Vocab
from app.references import Deeldoel, deeldoelen

AWR = "BWBR0002320"
AWIR = "BWBR0018472"
IW = "BWBR0004770"
UR_AWIR = "BWBR0019237"


@pytest.mark.parametrize(
    ("anker", "artikel", "verwacht"),
    [
        ("artikel 25, derde lid", "25", [("3", ())]),
        ("Artikel 2, zesde lid, van de Algemene wet inzake rijksbelastingen", "2", [("6", ())]),
        ("137d, eerste lid", "137d", [("1", ())]),
        ("tweede lid van artikel 36", "36", [("2", ())]),
        ("artikel 14, eerste lid, van Boek 4 van het Burgerlijk Wetboek", "14", [("1", ())]),
        ("artikel 700, derde lid, Rv", "700", [("3", ())]),
        ("artikel 19, negende lid, eerste volzin", "19", [("9", ())]),
        ("artikel 8:113, tweede lid", "8:113", [("2", ())]),
        ("artikel 3 lid 1", "3", [("1", ())]),
        # meer leden
        ("artikel 1:1, eerste en tweede lid, van de Algemene douanewet", "1:1", [("1", ()), ("2", ())]),
        ("artikelen 18.16a, eerste, tweede of vijfde lid", "18.16a", [("1", ()), ("2", ()), ("5", ())]),
        ("Artikel 66a, tweede tot en met vierde lid", "66a", [("2", ()), ("3", ()), ("4", ())]),
        (
            "artikel 5a, eerste lid en derde tot en met vijfde lid, van de Algemene wet",
            "5a",
            [("1", ()), ("3", ()), ("4", ()), ("5", ())],
        ),
        # onderdelen
        ("artikel 2, derde lid, onderdeel b", "2", [("3", ("b",))]),
        ("artikel 6:5, eerste lid, onderdeel d, van de Algemene wet bestuursrecht", "6:5", [("1", ("d",))]),
        ("artikel 2:16, eerste lid, onder a", "2:16", [("1", ("a",))]),
        ("artikel 8:72, derde lid, aanhef en onder b", "8:72", [("3", ("b",))]),
        ("artikel 1, onderdeel b, van de Wet algemene bepalingen", "1", [(None, ("b",))]),
        ("artikel 21, onderdeel e, onder 1°", "21", [(None, ("e", "1"))]),
        ("artikel 4.6, onderdelen a of d, van de Wet inkomstenbelasting 2001", "4.6",
         [(None, ("a",)), (None, ("d",))]),
        ("artikel 9.4a, eerste lid, onderdelen a en b, van de Wet", "9.4a",
         [("1", ("a",)), ("1", ("b",))]),
    ],
)
def test_de_tekst_wijst_het_deel_aan(anker: str, artikel: str, verwacht: list) -> None:
    assert deeldoelen(anker, artikel) == [Deeldoel(lid, o) for lid, o in verwacht]


@pytest.mark.parametrize(
    ("anker", "artikel"),
    [
        ("artikel 1", "1"),
        ("artikel 266 van het Wetboek van Strafrecht", "266"),
        ("artikelen 3 en 4, eerste lid", "3"),  # van welk artikel?
        ("artikelen 8:74 tot en met 8:75a", "8:74"),
        ("artikel 5 onder de voorwaarde", "5"),
        ("artikel 7, derde lid", "8"),  # tekst en jci spreken elkaar tegen
        ("", "1"),
    ],
)
def test_bij_twijfel_blijft_het_artikel(anker: str, artikel: str) -> None:
    assert deeldoelen(anker, artikel) == []


def test_meer_leden_met_een_onderdeel_noemen_alleen_de_leden() -> None:
    """Van welk lid is onderdeel a? Dat staat er niet."""
    assert deeldoelen("artikel 2, eerste en tweede lid, onderdeel a", "2") == [
        Deeldoel("1"), Deeldoel("2")
    ]


def _verwijzing(anker: str, doc: str) -> Verwijzing:
    return Verwijzing(soort=VerwijzingSoort.EXTERN, tekst=anker, doc=doc)


def _wet_die_verwijst(*refs: Verwijzing) -> Wet:
    return Wet(
        bwb_id=AWIR, citeertitel="Awir", opschrift="", soort="wet", geldig_vanaf="2026-01-01",
        geldig_tot=None,
        losse_artikelen=[Artikel(id=f"{AWIR}/A1", nummer="1", label="Artikel 1", tekst="",
                                 jci=f"jci1.3:c:{AWIR}&artikel=1", verwijzingen=list(refs))],
    )


def _doelwet() -> Wet:
    """AWR-achtig doel: artikel 2 met lid 3 en daaronder onderdeel b, en artikel 7 zonder leden."""
    lid = Lid(id=f"{AWR}/A2/L3", nummer="3", tekst="", jci=f"jci1.3:c:{AWR}&artikel=2&lid=3",
              onderdelen=[Onderdeel(id=f"{AWR}/A2/L3/b", nummer="b.", tekst="",
                                    jci=f"jci1.3:c:{AWR}&artikel=2&lid=3&o=b")])
    return Wet(
        bwb_id=AWR, citeertitel="AWR", opschrift="", soort="wet", geldig_vanaf="2026-01-01",
        geldig_tot=None,
        losse_artikelen=[
            Artikel(id=f"{AWR}/A2", nummer="2", label="Artikel 2", tekst="",
                    jci=f"jci1.3:c:{AWR}&artikel=2", leden=[lid]),
            Artikel(id=f"{AWR}/A7", nummer="7", label="Artikel 7", tekst="kort",
                    jci=f"jci1.3:c:{AWR}&artikel=7"),
        ],
    )


def _gekoppeld(*refs: Verwijzing) -> list[dict]:
    bron, _ = collect(_wet_die_verwijst(*refs), tekstuele_refs=False)
    doel, _ = collect(_doelwet(), tekstuele_refs=False)
    koppel_deelverwijzingen(bron, bepalingsindex([bron, doel]))
    return bron.verwijzingen


def test_verwijzing_landt_op_het_lid() -> None:
    rij = _gekoppeld(_verwijzing("artikel 2, derde lid, van de AWR", f"jci1.3:c:{AWR}&artikel=2"))[0]

    assert rij["to"] == f"{AWR}#artikel=2#lid=3"
    assert (rij["doel_soort"], rij["doel_lid"]) == ("lid", "3")
    assert rij["anker_tekst"] == "artikel 2, derde lid, van de AWR"


def test_verwijzing_landt_op_het_onderdeel() -> None:
    rij = _gekoppeld(_verwijzing("artikel 2, derde lid, onderdeel b", f"jci1.3:c:{AWR}&artikel=2"))[0]

    assert rij["to"] == f"{AWR}#artikel=2#lid=3#o=b"
    assert rij["doel_soort"] == "onderdeel"


def test_onderdeel_dat_niet_bestaat_valt_terug_op_het_lid() -> None:
    rij = _gekoppeld(_verwijzing("artikel 2, derde lid, onderdeel z", f"jci1.3:c:{AWR}&artikel=2"))[0]

    assert rij["to"] == f"{AWR}#artikel=2#lid=3"


def test_lid_dat_niet_bestaat_valt_terug_op_het_artikel_en_bewaart_wat_er_stond() -> None:
    rij = _gekoppeld(_verwijzing("artikel 7, tweede lid", f"jci1.3:c:{AWR}&artikel=7"))[0]

    assert rij["to"] == f"{AWR}#artikel=7"
    assert (rij["doel_soort"], rij["doel_lid"]) == ("artikel", "2")


def test_wet_buiten_de_run_valt_terug_op_het_artikel() -> None:
    bron, _ = collect(
        _wet_die_verwijst(_verwijzing("artikel 2, derde lid", f"jci1.3:c:{AWR}&artikel=2")),
        tekstuele_refs=False,
    )
    koppel_deelverwijzingen(bron, bepalingsindex([bron]))

    assert bron.verwijzingen[0]["to"] == f"{AWR}#artikel=2"
    assert bron.verwijzingen[0]["doel_lid"] == "3"


def test_twee_leden_geven_twee_doelen_en_verwijzingen_in_een_bron_blijven_apart() -> None:
    rijen = _gekoppeld(
        _verwijzing("artikel 2, derde lid", f"jci1.3:c:{AWR}&artikel=2"),
        _verwijzing("artikel 2, derde lid, onderdeel b", f"jci1.3:c:{AWR}&artikel=2"),
    )

    assert sorted(r["to"] for r in rijen) == [f"{AWR}#artikel=2#lid=3", f"{AWR}#artikel=2#lid=3#o=b"]


def test_koppelen_is_idempotent() -> None:
    bron, _ = collect(
        _wet_die_verwijst(_verwijzing("artikel 2, derde lid", f"jci1.3:c:{AWR}&artikel=2")),
        tekstuele_refs=False,
    )
    bekend = {f"{AWR}#artikel=2#lid=3"}

    assert koppel_deelverwijzingen(bron, bekend) == 1
    assert koppel_deelverwijzingen(bron, bekend) == 0
    assert [r["to"] for r in bron.verwijzingen] == [f"{AWR}#artikel=2#lid=3"]


def test_de_graaf_wijst_naar_het_lid() -> None:
    vocab = Vocab()
    writer = GraphDbWriter(url="offline", repository="offline", vocab=vocab)
    wet = _wet_die_verwijst(_verwijzing("artikel 2, derde lid", f"jci1.3:c:{AWR}&artikel=2"))
    batch: tuple[Batch, object] = collect(wet, tekstuele_refs=False)
    graaf, _ = writer.build_graph(
        wet, verzameld=batch, bepalingsindex={f"{AWR}#artikel=2#lid=3"}
    )

    doelen = {str(o) for o in graaf.objects(None, vocab.ns.verwijstNaar)}
    assert doelen == {f"urn:bwb:{AWR}:artikel:2:lid:3"}


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _batches(*namen: str) -> dict[str, Batch]:
    uit = {}
    for naam in namen:
        wet = ToestandParser().parse(FIXTURES / f"{naam}.xml")
        uit[wet.bwb_id], _ = collect(wet, tekstuele_refs=False)
    return uit


def test_echte_bepaling_binnen_een_wet_iw_artikel_5() -> None:
    """"artikel 2, eerste lid, onderdeel i" wijst naar dat onderdeel, niet naar het hele artikel 2."""
    batches = _batches("verwijzing_iw1990")
    koppel_deelverwijzingen(batches[IW], bepalingsindex(batches.values()))

    doelen = {r["to"] for r in batches[IW].verwijzingen if r["from"] == f"{IW}#artikel=5#lid=2"}
    assert f"{IW}#artikel=2#lid=1#o=i" in doelen
    assert f"{IW}#artikel=2" not in doelen


def test_echte_bepaling_over_wetten_heen_ur_awir_naar_awir() -> None:
    batches = _batches("verwijzing_ur_awir", "verwijzing_awir")
    koppel_deelverwijzingen(batches[UR_AWIR], bepalingsindex(batches.values()))

    rij = next(r for r in batches[UR_AWIR].verwijzingen
               if r["anker_tekst"] == "artikel 9, tweede lid, van de wet")
    assert rij["from"] == f"{UR_AWIR}#artikel=3#lid=2#o=a"
    assert rij["to"] == f"{AWIR}#artikel=9#lid=2"


def test_echte_bepaling_zonder_de_doelwet_blijft_op_het_artikel() -> None:
    batches = _batches("verwijzing_ur_awir")
    koppel_deelverwijzingen(batches[UR_AWIR], bepalingsindex(batches.values()))

    rij = next(r for r in batches[UR_AWIR].verwijzingen
               if r["anker_tekst"] == "artikel 9, tweede lid, van de wet")
    assert rij["to"] == f"{AWIR}#artikel=9"
    assert rij["doel_lid"] == "2"
