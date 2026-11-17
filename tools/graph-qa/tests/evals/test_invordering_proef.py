"""De modelproef mag bron- of variantwisselingen niet als verbetering tellen."""
import copy
import json

import pytest

from eval.invordering_proef import MEETMAP, VARIANTEN, controleer_cases, prepare, sha, onderzoekssnapshot
from bronmodel import valideer_ankers


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


def test_alle_graafcasussen_valideren_ook_voor_de_eerste_modelaanvraag():
    p = json.loads((MEETMAP / "proef-bronnen.json").read_text())
    origineel = copy.deepcopy(p)
    for c in p["casussen"]:
        s = onderzoekssnapshot(c["snapshot"])
        assert s["segmenten"] == c["snapshot"]["segmenten"]
        assert [(n["bron_iri"], n["tekst"], n.get("bron_hash")) for n in s["nodes"]] == [
            (n["bron_iri"], n["tekst"], n.get("bron_hash")) for n in c["snapshot"]["nodes"]]
        for n in s["segmenten"]:
            assert valideer_ankers(s, [{"bron_iri": n["bron_iri"], "bron_hash": n["bron_hash"],
                "start": 0, "eind": len(n["tekst"]), "tekst": n["tekst"]}]) == n["bron_iri"]
        if s.get("afbakening"):
            top = next(n for n in s["nodes"] if n["bron_iri"] == s["afbakening"]["lokale_wortel"])
            assert top["parent_iri"] == ""
            assert top["graaf_parent_iri"] == s["afbakening"]["graafouder_buiten_selectie"]
    assert p == origineel


def test_onvolledige_productiesnapshot_wordt_niet_stil_hersteld():
    p = json.loads((MEETMAP / "proef-bronnen.json").read_text())
    s = copy.deepcopy(p["casussen"][-1]["snapshot"])
    s.pop("snapshot_soort")
    with pytest.raises(ValueError, match="gerichte onderzoekssnapshot"):
        onderzoekssnapshot(s)
