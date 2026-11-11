"""`bronmodel.bwb.boom.model_tekens` is de graafkant van de dekking voor de connector `wetgeving_live`: hij moet
precies tellen wat de importer als `bwb:tekst` schrijft. Anders weigert de connector een volledige tekst, of laat hij
een onvolledige door."""
from __future__ import annotations

from pathlib import Path

import pytest
from bronmodel.bwb.boom import artikelen, model_tekens
from bronmodel.bwb.parser import ToestandParser

from app.dekking import meet

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.xml"))
TOESTANDEN = [p for p in FIXTURES if b"<toestand" in p.read_bytes()[:2000]]


@pytest.mark.parametrize("pad", TOESTANDEN, ids=lambda p: p.name)
def test_model_tekens_is_wat_de_importer_schrijft(pad: Path) -> None:
    wet = ToestandParser().parse(pad)
    assert model_tekens(wet) == meet(pad).graaf_tekens


@pytest.mark.parametrize("pad", TOESTANDEN, ids=lambda p: p.name)
def test_bytes_en_pad_lezen_hetzelfde(pad: Path) -> None:
    assert ToestandParser().parse(pad.read_bytes()) == ToestandParser().parse(pad)


def test_artikelen_in_documentvolgorde_met_plek() -> None:
    pad = next(p for p in TOESTANDEN if p.name == "sample_toestand.xml")
    rijen = list(artikelen(ToestandParser().parse(pad)))
    assert rijen, "geen artikelen gelezen"
    assert len({id(a) for _, a in rijen}) == len(rijen)


def test_een_boek_van_het_bw_is_de_regeling_zelf():
    """Boek 7 BW (BWBR0005290) heeft als wettekst precies één `<boek>`. De lezer leest erdoorheen: dezelfde artikelen en
    tekst als zonder die omhulling, niets overgeslagen, en de IRI's veranderen niet."""
    pad = next(p for p in TOESTANDEN if p.name == "sample_toestand.xml")
    xml = pad.read_text(encoding="utf-8")
    kop, staart = xml.split("<wettekst", 1)
    open_tag, rest = staart.split(">", 1)
    inhoud, slot = rest.rsplit("</wettekst>", 1)
    met_boek = (f"{kop}<wettekst{open_tag}><boek><kop><label>Boek</label><nr>7</nr><titel>Test</titel></kop>"
                f"{inhoud}</boek></wettekst>{slot}").encode("utf-8")
    zonder, met = ToestandParser().parse(pad), ToestandParser().parse(met_boek)
    assert not met.overgeslagen
    assert [a.nummer for _, a in artikelen(met)] == [a.nummer for _, a in artikelen(zonder)]
    assert model_tekens(met) == model_tekens(zonder)
