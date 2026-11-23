"""`inhoudsopgave(vanaf=…)` op een bepaling: een antwoord, geen fout.

Acceptatie 23 nov 2026, "annoteer leidraad artikel 1.1.2": het denkproces toonde "bekijkt de opbouw van Leidraad
Invordering 2008 · Wetgeving · gaf een fout", en Lex zocht daarna gewoon verder. De inhoudsopgave volgt alleen
containerniveaus; onder divisie 1.1.2 (geneste nummering Artikel 1 → 1.1 → 1.1.2) hangen alleen onderdelen, dus nul rijen,
en dat was een `ValueError`. Hetzelfde gold voor elk artikel van een wet. De rijen hieronder zijn wat de graaf van
acceptatie die dag gaf.
"""
from __future__ import annotations

import json

from agent import tools
from agent.resultaat import is_fout
from agent.spoorbronnen import uitkomstregel
from fakes import FakeGraph

LEIDRAAD = "BWBR0024096"
IW = "BWBR0004770"
_DIV = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie1%2FCirculaire.divisie1.1"
_LEEG = "?niveau\t?ouder\t?deel\t?soort\t?nummer\t?titel\t?volgtOp\n"
_KOP = "?node\t?soort\t?nummer\t?titel\t?ouder\t?oudersoort\t?oudernummer\n"


def _graaf(deel: str) -> FakeGraph:
    """Lege inhoudsopgave; de vraag naar het deel zelf geeft `deel`."""
    return FakeGraph(results=lambda q: _KOP + deel if "?oudersoort" in q else _LEEG)


def _eind(uit: str) -> dict:
    data = json.loads(uit)
    return {"status": data["status"], "aantal": data.get("aantal"), "has_more": not data.get("volledig", True),
            "foutcode": data.get("reden", "")}


def test_een_divisie_met_geneste_nummering_is_een_antwoord_met_de_weg_naar_de_tekst():
    g = _graaf(f'<{_DIV}%2FCirculaire.divisie1.1.2>\t"Divisie"\t"1.1.2"\t"Definities"@nl\t"{_DIV}"\t"Divisie"\t"1.1"\n')
    uit = tools.dispatch("inhoudsopgave", g, {"bwb_id": LEIDRAAD, "vanaf": "1.1.2"})
    assert not is_fout(uit), uit
    data = json.loads(uit)
    assert data["status"] == "ok" and data["volledig"] is True
    (deel,) = data["resultaten"]
    assert deel["soort"] == "Divisie" and deel["nummer"] == "1.1.2" and deel["onderdelen"] == 0
    assert deel["lezen"] == {"tool": "get_bepaling", "args": {"bwb_id": LEIDRAAD, "nummer": "1.1.2"}}
    assert deel["ouder"]["nummer"] == "1.1"
    assert deel["ouder"]["openen"] == {"tool": "inhoudsopgave", "args": {"bwb_id": LEIDRAAD, "vanaf": _DIV}}
    assert f"{_DIV}%2FCirculaire.divisie1.1.2" in uit, "de vindplaats staat in het resultaat (bronnen, grounding)"
    # Het denkproces zegt wat er is, niet "gaf een fout".
    regel = uitkomstregel("inhoudsopgave", {"bwb_id": LEIDRAAD, "vanaf": "1.1.2"}, _eind(uit), data)
    assert regel == "divisie 1.1.2 heeft geen onderliggende delen"


def test_een_artikel_van_een_wet_wijst_naar_get_artikel():
    g = _graaf(f'<urn:bwb:{IW}:artikel:9>\t"Artikel"\t"9"\t""\t"urn:bwb:{IW}:hoofdstuk:II"\t"Hoofdstuk"\t"II"\n')
    data = json.loads(tools.dispatch("inhoudsopgave", g, {"bwb_id": IW, "vanaf": "9"}))
    assert data["status"] == "ok"
    assert data["resultaten"][0]["lezen"] == {"tool": "get_artikel", "args": {"bwb_id": IW, "artikel": "9"}}


def test_een_deel_direct_onder_de_regeling_heeft_geen_ouder_om_te_openen():
    g = _graaf(f'<urn:bwb:{IW}:artikel:1>\t"Artikel"\t"1"\t""\t"urn:bwb:{IW}"\t"Regeling"\t""\n')
    data = json.loads(tools.dispatch("inhoudsopgave", g, {"bwb_id": IW, "vanaf": "1"}))
    assert "ouder" not in data["resultaten"][0]


def test_een_deel_dat_er_niet_is_heeft_een_reden_in_woorden():
    uit = tools.dispatch("inhoudsopgave", _graaf(""), {"bwb_id": LEIDRAAD, "vanaf": "99.9"})
    assert is_fout(uit)
    data = json.loads(uit)
    assert data["reden"] == "deel_niet_gevonden"
    assert data["alternatief"] == {"tool": "inhoudsopgave", "args": {"bwb_id": LEIDRAAD}}
    assert uitkomstregel("inhoudsopgave", {"bwb_id": LEIDRAAD}, _eind(uit), data) == "dat deel staat niet in de regeling"


def test_een_iri_van_een_andere_regeling_is_geen_deel():
    uit = tools.dispatch("inhoudsopgave", _graaf(""), {"bwb_id": LEIDRAAD, "vanaf": f"urn:bwb:{IW}:artikel:9"})
    assert json.loads(uit)["reden"] == "deel_niet_gevonden"
