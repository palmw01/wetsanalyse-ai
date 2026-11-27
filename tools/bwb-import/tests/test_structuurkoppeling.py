"""Structuurverwijzingen die pas met het boek of de ankertekst op hun node uitkomen (Rv en het BW).

Twee gaten uit de civiele import (27 nov 2026): de interne verwijzingen van Rv noemen in de jci het boek
(`&boek=Vierde&titeldeel=Eerste&afdeling=Derde`) terwijl de sleutel het wegliet, en een verwijzing naar een ander
BW-boek noemt in de jci alleen het laatste segment (`&afdeling=2`), dat in dat boek vaak voorkomt. De ankertekst
("afdeling 2 van titel 1 van Boek 3") wijst er dan één aan. Wat daarna nog dubbelzinnig is, blijft open.
"""

from __future__ import annotations

from app.collect import Batch, _met_boek, koppel_structuurverwijzingen, structuurindex

RV = "BWBR0001827"
BW3 = "BWBR0005291"


def _structuur(*sleutels: str) -> Batch:
    batch = Batch()
    for sleutel in sleutels:
        soort, _, nummer = sleutel.rpartition("#")[2].partition("=")
        entiteit = {"hoofdstuk": "Hoofdstuk", "titeldeel": "Titeldeel", "afdeling": "Afdeling", "paragraaf": "Paragraaf"}[soort]
        batch.nodes.setdefault(entiteit, []).append(
            {"id": sleutel, "ref_key": sleutel, "nummer": nummer, "soort": soort}
        )
    return batch


def _verwijzing(naar: str, soort: str, anker: str) -> dict:
    return {"from": f"{RV}#artikel=1", "to": naar, "doel_soort": soort, "anker_tekst": anker}


def test_het_boek_uit_de_jci_komt_in_de_sleutel() -> None:
    doc = f"jci1.3:c:{RV}&boek=Vierde&titeldeel=Eerste&afdeling=Derde&z=2026-07-14"
    assert _met_boek(f"{RV}#titeldeel=Eerste#afdeling=Derde", "afdeling", doc) == (
        f"{RV}#boek=Vierde#titeldeel=Eerste#afdeling=Derde"
    )
    # Een artikel houdt zijn sleutel: die is zonder boek al uniek.
    assert _met_boek(f"{RV}#artikel=3", "artikel", doc) == f"{RV}#artikel=3"


def test_het_boek_valt_weg_als_de_doelregeling_geen_boeken_kent() -> None:
    doel = _structuur(f"{BW3}#titeldeel=1#afdeling=2")
    bron = Batch(verwijzingen=[_verwijzing(f"{BW3}#boek=3#titeldeel=1#afdeling=2", "afdeling", "afdeling 2")])
    assert koppel_structuurverwijzingen(bron, structuurindex([doel, bron])) == 1
    assert bron.verwijzingen[0]["to"] == f"{BW3}#titeldeel=1#afdeling=2"


def test_de_ankertekst_kiest_tussen_gelijknamige_afdelingen() -> None:
    doel = _structuur(f"{BW3}#titeldeel=1#afdeling=2", f"{BW3}#titeldeel=7#afdeling=2")
    een = _verwijzing(f"{BW3}#afdeling=2", "afdeling", "afdeling 2 van titel 1 van Boek 3 van het Burgerlijk Wetboek")
    zeven = _verwijzing(f"{BW3}#afdeling=2", "afdeling", "afdeling 2 van titel 7 van Boek 3")
    bron = Batch(verwijzingen=[een, zeven])
    assert koppel_structuurverwijzingen(bron, structuurindex([doel, bron])) == 2
    assert [r["to"] for r in bron.verwijzingen] == [f"{BW3}#titeldeel=1#afdeling=2", f"{BW3}#titeldeel=7#afdeling=2"]


def test_rangtelwoorden_en_titel_met_punt() -> None:
    doel = _structuur(
        f"{RV}#boek=Eerste#titeldeel=Derde#afdeling=Tweede", f"{RV}#boek=Tweede#titeldeel=Derde#afdeling=Tweede",
        f"{BW3}#titeldeel=5#afdeling=3", f"{BW3}#titeldeel=6#afdeling=3",
    )
    rv = _verwijzing(f"{RV}#afdeling=Tweede", "afdeling",
                     "tweede afdeling van de derde titel van het eerste boek van het Wetboek van Burgerlijke Rechtsvordering")
    punt = _verwijzing(f"{BW3}#afdeling=3", "afdeling", "titel 5.3 van Boek 3 van het Burgerlijk Wetboek")
    bron = Batch(verwijzingen=[rv, punt])
    koppel_structuurverwijzingen(bron, structuurindex([doel, bron]))
    assert [r["to"] for r in bron.verwijzingen] == [
        f"{RV}#boek=Eerste#titeldeel=Derde#afdeling=Tweede", f"{BW3}#titeldeel=5#afdeling=3",
    ]


def test_wat_de_ankertekst_niet_beslist_blijft_open() -> None:
    doel = _structuur(f"{BW3}#titeldeel=1#afdeling=2", f"{BW3}#titeldeel=7#afdeling=2")
    kaal = _verwijzing(f"{BW3}#afdeling=2", "afdeling", "afdeling 2")
    bron = Batch(verwijzingen=[kaal])
    assert koppel_structuurverwijzingen(bron, structuurindex([doel, bron])) == 0
    assert bron.verwijzingen[0]["to"] == f"{BW3}#afdeling=2"


def test_romeins_hoofdstuk_met_letter() -> None:
    awr = "BWBR0002320"
    doel = _structuur(f"{awr}#hoofdstuk=VIIIA#afdeling=2", f"{awr}#hoofdstuk=II#afdeling=2")
    bron = Batch(verwijzingen=[_verwijzing(f"{awr}#afdeling=2", "afdeling",
                                           "hoofdstuk VIIIA, afdeling 2, van de Algemene wet inzake rijksbelastingen")])
    koppel_structuurverwijzingen(bron, structuurindex([doel, bron]))
    assert bron.verwijzingen[0]["to"] == f"{awr}#hoofdstuk=VIIIA#afdeling=2"
