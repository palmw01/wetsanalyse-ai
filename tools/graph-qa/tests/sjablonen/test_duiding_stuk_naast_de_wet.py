"""Een stuk naast de wet in 'onderbouwing' van de duiding (meting 19 nov 2026, acceptatie): de weigering zei "haal de
bepaling op met get_artikel", ook bij een link naar een Kamerstuk of het Staatsblad en bij een artikel van overheid.nl
dat niet gelezen was. Dat kan bij zo'n stuk niet; het model las opnieuw of gaf het op. Nu wijst de weigering naar
'extern' (gelezen) of naar de leestool van de bron (niet gelezen)."""
import json

import pytest

from agent import sjablonen
from agent.sjablonen import Onvulbaar

KORT = "De verrekening is ook mogelijk vóór het verstrijken van de betalingstermijn."


def _vul(bepaling: str, trace: list[tuple[str, str]]) -> str:
    with pytest.raises(Onvulbaar) as fout:
        sjablonen.vul("antwoord_duiding", {"kort_antwoord": KORT, "twijfel": [], "extern": [], "stukken": [],
                                          "onderbouwing": [{"bepaling": bepaling, "van": "", "tot": "", "waarom": "x"}]},
                      trace)
    return str(fout.value)


def _kamerstuk(ident: str) -> tuple[str, str]:
    return ("get_kamerstuk", json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                                         "stuk": {"id": ident, "label": "Kamerstukken 30322, nr. 3"},
                                         "resultaten": [{"nr": 1, "tekst": "Memorie van toelichting."}]}))


def test_een_gelezen_kamerstuk_hoort_in_extern():
    melding = _vul("https://zoek.officielebekendmakingen.nl/kst-30322-3", [_kamerstuk("kst-30322-3")])
    assert "'extern'" in melding and "kst-30322-3" in melding and "get_artikel" not in melding
    assert "Lees het niet opnieuw" in melding


def test_een_ongelezen_stuk_noemt_de_leestool_van_zijn_bron():
    melding = _vul("https://zoek.officielebekendmakingen.nl/stb-2010-176", [_kamerstuk("kst-30322-3")])
    assert "niet gelezen" in melding and "get_bekendmaking" in melding and "get_artikel" not in melding
    melding = _vul("bwbt:BWBR0011353:2026-02-21_0:artikel:2.3", [])
    assert "get_wettekst" in melding and "get_artikel" not in melding
    melding = _vul("ECLI:NL:HR:2023:563", [])
    assert "get_uitspraak" in melding


def test_wettekst_uit_de_graaf_houdt_de_oude_weigering():
    melding = _vul("urn:bwb:BWBR0004770:artikel:9:lid:1", [])
    assert "get_artikel" in melding
