"""De modelproef mag bron- of variantwisselingen niet als verbetering tellen."""
import copy
import json

import pytest

from eval.invordering_proef import MEETMAP, VARIANTEN, controleer_cases, prepare, sha


def test_proef_heeft_acht_graafcasussen_en_72_pogingen():
    p = json.loads((MEETMAP / "proef-bronnen.json").read_text())
    controleer_cases(p)
    assert len(p["casussen"]) * len(VARIANTEN) * p["herhalingen"] == 72
    assert p["vervanging"] == {"WZT01": "AWB-4:17-1", "RVV03": "IW04"}
    assert prepare() == p


@pytest.mark.parametrize("fout", ["tekst", "context", "herkomst", "hash"])
def test_gewijzigd_of_verkeerd_bronpakket_faalt(fout):
    p = copy.deepcopy(json.loads((MEETMAP / "proef-bronnen.json").read_text()))
    if fout == "tekst":
        p["casussen"][0]["snapshot"]["segmenten"][0]["tekst"] += " Nieuw."
    elif fout == "context":
        p["casussen"][0]["context"][0]["herkomst"] = "web"
    elif fout == "herkomst":
        p["casussen"][0]["herkomst"] = "xml"
    else:
        p["casussen_sha256"] = "ongeldig"
    if fout != "hash":
        p["casussen_sha256"] = sha(p["casussen"])
    with pytest.raises(ValueError):
        controleer_cases(p)
