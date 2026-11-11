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
