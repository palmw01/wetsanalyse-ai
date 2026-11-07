"""R3: een open keuzevraag van Lex beantwoordt Lex niet zelf."""
from __future__ import annotations

import pytest

from agent.verduidelijken import doorvraag, open_keuzevraag

VORIG = ("De Awb nummert per hoofdstuk: artikel 3:1, 3:2 enzovoort. "
         "Bedoel je artikel 3:1, 3:2, of een ander artikel uit hoofdstuk 3?")


def test_de_keuzevraag_aan_het_eind_wordt_herkend():
    assert open_keuzevraag(VORIG).startswith("Bedoel je artikel 3:1")
    assert open_keuzevraag("Artikel 9 regelt de invorderbaarheid.") == ""
    assert open_keuzevraag("Wat vind jij ervan?") == ""


@pytest.mark.parametrize("vraag", ["En het tweede lid?", "Wat staat er in lid 2 daarvan?", "En onderdeel b?"])
def test_een_verwijzing_zonder_artikel_wordt_een_doorvraag(vraag):
    tekst = doorvraag(vraag, VORIG)
    assert "welk artikel" in tekst and "Bedoel je artikel 3:1" in tekst


@pytest.mark.parametrize("vraag", ["Artikel 3:2, het tweede lid.", "Wat is een besluit?", "Ik bedoel de Awb."])
def test_een_keuze_of_een_nieuwe_vraag_gaat_door(vraag):
    assert doorvraag(vraag, VORIG) == ""


def test_zonder_open_keuzevraag_geen_doorvraag():
    assert doorvraag("En het tweede lid?", "Artikel 9 regelt de invorderbaarheid.") == ""


def test_in_het_gesprek_vraagt_lex_door_zonder_model(monkeypatch):
    from agent.nodes import supervisie
    from test_routering import _bouw
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    b = _bouw()  # een model dat faalt als het wordt aangeroepen
    state = {"question": "En het tweede lid?", "modus": "auto", "focus": {},
             "messages": [{"role": "user", "content": "Wat zegt artikel 3? Ik bedoel de Awb."},
                          {"role": "assistant", "content": VORIG},
                          {"role": "user", "content": "En het tweede lid?"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "afwijzen" and "welk artikel" in upd["afwijs_melding"]


def test_een_vage_keuzevraag_staat_er_niet_twee_keer():
    """Acceptatie 7 nov 2026: "Kun je aangeven welk artikel je precies bedoelt?" en daarna nog eens "Noem het artikel"."""
    tekst = doorvraag("En het tweede lid?", "Kun je aangeven welk artikel je precies bedoelt, zodat ik het kan ophalen?")
    assert "Kun je aangeven" not in tekst and "Noem het artikel" in tekst
