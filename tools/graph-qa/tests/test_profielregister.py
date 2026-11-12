"""Het profielregister (ADR-016 §A2, stap A1): de specialisten zijn profielen, en hun gedrag is hetzelfde gebleven.

Een profiel is configuratie die een Python-agent laadt. De bestanden staan in `.claude/lex-agents/`, de generator
bundelt ze in `agent/agentprofielen.py`, en `agent/profielen.py` laadt en toetst ze. Deze tests bewaken drie dingen:

1. **Bitgelijk.** De instructie, de tools, de sjablonen en de methoderol per specialist zijn die van vóór het register
   (de hashes hieronder komen uit de code van toen), en de supervisor kiest uit dezelfde drie.
2. **Eén register.** `SPECIALISTS` en de keuze van de supervisor zijn afgeleid; het gebundelde bestand loopt niet uit de
   pas met de map.
3. **De grenzen.** Een profiel dat iets noemt wat niet bestaat, laadt niet.

Wijzig je een profiel, dan verandert het gedrag van Lex: dat vraagt een meting (ADR-016 §B2, poort 3). Werk daarna de
hash hier bij.
"""
from __future__ import annotations

import hashlib
import json

import pytest
from bronmodel.agentprofiel import Agentprofiel
from bronmodel.connectors import CONNECTORS
from bronmodel.validatie import ValidatieFout

from agent import profielen, specialists, supervisor
from agent.methode import instructies
from scripts.genereer_agentprofielen import DOEL, PROFIELEN as MAP, compileer, genereer


def _hash(waarde) -> str:
    return hashlib.sha256(json.dumps(waarde, ensure_ascii=False).encode()).hexdigest()[:16]


#: Per specialist: de hash van de instructie, de hash van de gesorteerde tools (None = alle tools) met hun aantal, de
#: sjablonen en de methoderol. Vastgelegd op de code van vóór het register (`agent/specialists.py`, 12 nov 2026).
VOORHEEN = {
    "algemeen": ("2fe1af2e427495d0", None, None, ["antwoord_bepaling"], "algemeen"),
    "annotaties_lezen": ("fe3c7e28bcb0084f", "1b8f0319fc539a5a", 9, ["antwoord_annotaties"], "algemeen"),
    "begrippen_lezen": ("45284dc016d47e95", "241067cb93dfea3f", 7, ["antwoord_begrip"], "algemeen"),
    "definitie": ("9aee233723c7f727", "13b1588ec3911be8", 20, ["antwoord_begrip"], "definitie"),
    "duiding": ("a188d65b51c9ff01", "2e7a2ae68e2d4166", 30, ["antwoord_bepaling", "antwoord_duiding"], "duiding"),
    "retrieval": ("0251938f3a1be130", "921d3ac2de6f1b11", 13, [], "retrieval"),
}
#: De specialisten die de supervisor mocht kiezen (`_QA_SPECIALISTS`), en de connectors die hun rol bedienden.
KOOS = {"definitie", "duiding", "algemeen"}
#: Profielen die er na het register bij kwamen. Ze raken de specialisten van voorheen niet: `centraal` draait alleen
#: achter de vlag `CENTRALE_AGENT` (`tests/test_centrale_agent.py`).
NIEUW = {"centraal"}


# --- bitgelijk ---------------------------------------------------------------------------------------------------

def test_dezelfde_specialisten():
    assert set(specialists.SPECIALISTS) == set(VOORHEEN) | NIEUW == set(profielen.PROFIELEN)


@pytest.mark.parametrize("naam", sorted(VOORHEEN))
def test_dezelfde_instructie_tools_sjablonen_en_methoderol(naam: str):
    instructie, tools, aantal, sjablonen, rol = VOORHEEN[naam]
    spec = specialists.SPECIALISTS[naam]
    assert _hash(spec.system) == instructie, "de instructie is gewijzigd"
    assert (None if spec.tools is None else _hash(sorted(spec.tools))) == tools, "de tools zijn gewijzigd"
    assert (None if spec.tools is None else len(spec.tools)) == aantal
    assert sorted(spec.sjablonen) == sjablonen
    assert specialists.methoderol(naam) == rol


@pytest.mark.parametrize("naam", sorted(VOORHEEN))
def test_de_systeemtekst_is_de_methodetekst_van_de_rol_plus_de_instructie(naam: str):
    """Zo bouwde `specialists.get` hem altijd op; de methodetekst zelf bewaakt `test_methodepakket.py`."""
    assert specialists.get(naam).system == instructies(VOORHEEN[naam][4]) + "\n\n" + profielen.PROFIELEN[naam].instructie


def test_dezelfde_routering():
    assert set(supervisor._QA_SPECIALISTS) == KOOS == {n for n, p in profielen.PROFIELEN.items() if p.kiesbaar}
    assert supervisor.parse_supervisor("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: x")[0] == ["duiding"]
    # Een profiel dat een stap van een route is, kiest het model niet: de keuze valt terug op algemeen.
    assert supervisor.parse_supervisor("WORKERS: antwoord\nSPECIALIST: retrieval\nPLAN: x")[0] == ["algemeen"]
    assert specialists.get("bestaat_niet") == specialists.get("algemeen") == specialists.get(None)
    assert specialists.methoderol("bestaat_niet") == "algemeen"


def test_dezelfde_profielen_bedienen_een_connector():
    """Vóór het register noemde elke connector de rollen definitie, duiding en algemeen."""
    for connector in CONNECTORS:
        assert {n for n in profielen.PROFIELEN if profielen.bedient(n, connector)} - NIEUW == KOOS
    assert not profielen.bedient("bestaat_niet", "kamerstukken")


# --- één register ------------------------------------------------------------------------------------------------

def test_het_gebundelde_bestand_past_bij_de_map():
    assert DOEL.read_text(encoding="utf-8") == genereer()
    assert {p.stem for p in MAP.glob("*.md")} == set(profielen.PROFIELEN)
    register = compileer()
    assert profielen.laad(register) == profielen.PROFIELEN


def test_specialists_is_afgeleid_en_draagt_geen_eigen_tekst():
    for naam, p in profielen.PROFIELEN.items():
        spec = specialists.SPECIALISTS[naam]
        assert (spec.system, spec.doel, spec.sjablonen) == (p.instructie, p.beschrijving, frozenset(p.sjablonen))
        assert spec.tools == profielen.tools_van(p)


# --- de grenzen --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("veld", "waarde"), [
    ("tools", ("bestaat_niet",)),
    ("tools", ("subagent",)),
    ("tools", (next(iter(sorted(next(iter(CONNECTORS.values())).tools))),)),   # een connectortool met de hand
    ("skills", ("onbekende-skill",)),
    ("connectors", ("onbekend",)),
    ("sjablonen", ("antwoord_vrij",)),
    ("methoderol", "bestaat_niet"),
])
def test_een_profiel_buiten_de_grenzen_laadt_niet(veld: str, waarde):
    register = compileer()
    register["profielen"]["duiding"] = register["profielen"]["duiding"] | {veld: waarde}
    with pytest.raises(ValidatieFout) as fout:
        profielen.laad(register)
    assert {b.code for b in fout.value.bevindingen} == {veld}


def test_elk_profiel_is_een_getypeerd_object_binnen_de_grenzen():
    g = profielen.grenzen()
    assert g.skills and g.methoderollen and g.sjablonen
    for p in profielen.PROFIELEN.values():
        assert isinstance(p, Agentprofiel)
