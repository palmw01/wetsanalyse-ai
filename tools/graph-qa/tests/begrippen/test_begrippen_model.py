"""Het datamodel van de begrippenketen (ADR-004): identiteit, vorm en weigeringen."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.begrippen_pipeline.model import (
    Aandacht, Besluit, Beslissing, Betekenisgroep, Bewijs, Bron, Formulering, Hypothese,
    Kandidaat, Manifest, Polariteit, Relatie, Sterkte, groep_id, kandidaat_id,
)

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
IRI = "urn:bwb:BWBR0004770:artikel:9:lid:1"


def _bron(tekst: str = TEKST, iri: str = IRI) -> Bron:
    return Bron(bron_iri=iri, tekst=tekst, bron_hash="h" + str(len(tekst)))


def _form(element_id: str, tekst: str, *, bron: str = TEKST, iri: str = IRI,
          klasse: str = "Rechtsobject") -> Formulering:
    start = bron.index(tekst)
    return Formulering(element_id=element_id, bron_iri=iri, start=start, eind=start + len(tekst),
                       tekst=tekst, jas_klasse=klasse)


def _bewijs(code: str = "ZELFDE_KERN", pol: Polariteit = Polariteit.STEUN) -> Bewijs:
    return Bewijs(code=code, polariteit=pol, sterkte=Sterkte.ZWAK, regel="begrip.kern.lemma",
                  versie="1")


def test_manifest_id_is_inhoudelijk_en_volgorde_ongevoelig():
    a, b = _form("e1", "belastingaanslag"), _form("e2", "aanslagbiljet")
    m1 = Manifest(bronnen=(_bron(),), formuleringen=(a, b))
    m2 = Manifest(bronnen=(_bron(),), formuleringen=(b, a))
    assert m1.id == m2.id
    assert m1.id != Manifest(bronnen=(_bron(),), formuleringen=(a,)).id


def test_manifest_id_verandert_met_de_bronstand():
    a = _form("e1", "belastingaanslag")
    anders = Bron(bron_iri=IRI, tekst=TEKST, bron_hash="andere-hash")
    assert Manifest(bronnen=(_bron(),), formuleringen=(a,)).id != \
        Manifest(bronnen=(anders,), formuleringen=(a,)).id


@pytest.mark.parametrize("formuleringen, fout", [
    ((Formulering(element_id="e1", bron_iri=IRI, start=4, eind=20, tekst="iets anders",
                  jas_klasse="Rechtsobject"),), "letterlijk"),
    ((Formulering(element_id="e1", bron_iri="urn:elders", start=0, eind=3, tekst="Een",
                  jas_klasse="Rechtsobject"),), "buiten het manifest"),
])
def test_manifest_weigert_een_element_dat_niet_op_zijn_anker_staat(formuleringen, fout):
    with pytest.raises(ValidationError, match=fout):
        Manifest(bronnen=(_bron(),), formuleringen=formuleringen)


def test_manifest_weigert_dubbele_elementen():
    a = _form("e1", "belastingaanslag")
    with pytest.raises(ValidationError, match="dubbel"):
        Manifest(bronnen=(_bron(),), formuleringen=(a, a))


def test_symmetrische_kandidaat_negeert_de_volgorde():
    k1 = Kandidaat.maak(Hypothese.ZELFDE_BETEKENIS, "e2", "e1", [_bewijs()])
    k2 = Kandidaat.maak(Hypothese.ZELFDE_BETEKENIS, "e1", "e2", [_bewijs()])
    assert k1.id == k2.id and k1.leden == ("e1", "e2")


def test_gerichte_kandidaat_houdt_de_richting():
    boven = Kandidaat.maak(Hypothese.HIERARCHIE, "e1", "e2", [_bewijs("HEARST_ZOALS")])
    onder = Kandidaat.maak(Hypothese.HIERARCHIE, "e2", "e1", [_bewijs("HEARST_ZOALS")])
    assert boven.id != onder.id
    assert boven.id != kandidaat_id(Hypothese.KWALIFICATIE, "e1", "e2")


def test_kandidaat_weigert_zonder_bewijs_en_met_zichzelf():
    with pytest.raises(ValidationError, match="gok"):
        Kandidaat.maak(Hypothese.ZELFDE_BETEKENIS, "e1", "e2", [])
    with pytest.raises(ValidationError, match="twee verschillende"):
        Kandidaat.maak(Hypothese.ZELFDE_BETEKENIS, "e1", "e1", [_bewijs()])


def test_kandidaat_met_een_verzonnen_id_wordt_geweigerd():
    with pytest.raises(ValidationError, match="volgt niet"):
        Kandidaat(id="P000000000000", hypothese=Hypothese.ZELFDE_BETEKENIS, van="e1", naar="e2",
                  bewijs=(_bewijs(),))


def test_bewijs_toevoegen_ontdubbelt_en_houdt_de_volgorde():
    k = Kandidaat.maak(Hypothese.ZELFDE_BETEKENIS, "e1", "e2", [_bewijs()])
    tegen = _bewijs("ANDERE_DEFINITIE", Polariteit.TEGEN)
    k2 = k.met_bewijs([_bewijs(), tegen])
    assert [b.code for b in k2.bewijs] == ["ZELFDE_KERN", "ANDERE_DEFINITIE"]
    assert k.bewijs == (_bewijs(),)                     # het origineel is onveranderd


def test_groep_identiteit_en_vorm():
    g = Betekenisgroep.maak(["e3", "e1", "e2"], ["P2", "P1"])
    assert g.leden == ("e1", "e2", "e3") and g.id == groep_id(["e2", "e3", "e1"])
    assert g.kandidaten == ("P1", "P2")
    with pytest.raises(ValidationError, match="minstens twee"):
        Betekenisgroep.maak(["e1"], [])


def test_een_groep_met_conflict_kan_niet_groen_zijn():
    with pytest.raises(ValidationError, match="geel"):
        Betekenisgroep.maak(["e1", "e2"], ["P1"], conflicten=["P9"], aandacht=Aandacht.GROEN)
    assert Betekenisgroep.maak(["e1", "e2"], ["P1"], conflicten=["P9"],
                               aandacht=Aandacht.GEEL).conflicten == ("P9",)


def test_zelfde_betekenis_is_geen_relatie():
    with pytest.raises(ValidationError, match="groep"):
        Relatie(kandidaat_id="P1", hypothese=Hypothese.ZELFDE_BETEKENIS, van="e1", naar="e2",
                aandacht=Aandacht.GEEL)


def test_modellen_zijn_onveranderlijk_en_serialiseerbaar():
    k = Kandidaat.maak(Hypothese.KWALIFICATIE, "e1", "e2", [_bewijs("KWALIFICATIE")])
    with pytest.raises(ValidationError):
        k.van = "e9"
    assert Kandidaat.model_validate_json(k.model_dump_json()) == k
    b = Beslissing(kandidaat_id=k.id, besluit=Besluit.POSSIBLE_LINK, regel="B-ZWAK")
    assert Beslissing.model_validate(b.model_dump()) == b
