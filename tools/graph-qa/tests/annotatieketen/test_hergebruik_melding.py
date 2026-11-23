"""De hergebruikmelding in het denkproces noemt een ongenummerd onderdeel niet bij zijn streepje."""
from agent.nodes.annotatie import _hergebruik_melding

TELLING = {"markeringen": 33, "beoordeeld": 27, "te_beoordelen": 0}


def _melding(*leden: str) -> str:
    return _hergebruik_melding({"leden": [{"lid": ld} for ld in leden], "telling": TELLING})


def test_genummerde_leden_bij_nummer():
    assert _melding("2").startswith("lid 2 ongewijzigd")
    assert _melding("1", "3").startswith("leden 1, 3 ongewijzigd")
    assert _melding("").startswith("het artikel ongewijzigd")


def test_ongenummerde_onderdelen_geteld_niet_opgesomd():
    assert _melding(*["–"] * 17).startswith("17 onderdelen ongewijzigd")
    assert _melding("•").startswith("het onderdeel ongewijzigd")
    assert _melding("1", "–", "–").startswith("lid 1 en 2 ongenummerde onderdelen ongewijzigd")
    assert "–" not in _melding(*["–"] * 17)
