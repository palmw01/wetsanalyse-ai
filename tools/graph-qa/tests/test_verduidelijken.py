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


def test_een_keuzevraag_met_de_mogelijkheden_in_een_slotvraag_wordt_herkend():
    """Het antwoord van de centrale agent in de meting van 12 nov 2026 (gesprek v-artikel-zonder-wet, beurt 2): de
    keuzevraag, en daarna de voorbeelden in een eigen vraag. De herkenner keek alleen naar de laatste zin."""
    antwoord = ('De Awb gebruikt een bijzondere nummering voor artikelen, in de vorm van hoofdstuk:artikel (bijvoorbeeld 3:1, '
                '3:2). Er is geen artikel met alleen het nummer "3" in de Awb. Bedoel je een specifiek artikel uit een bepaald '
                'hoofdstuk of afdeling? Bijvoorbeeld artikel 3:1, 3:2 of een ander artikel uit hoofdstuk 3?')
    keuze = open_keuzevraag(antwoord)
    assert keuze.startswith("Bedoel je een specifiek artikel") and keuze.endswith("uit hoofdstuk 3?")
    tekst = doorvraag("En het tweede lid?", antwoord)
    assert tekst.startswith("Ik weet nog niet welk artikel je bedoelt") and "3:1, 3:2" in tekst
    # Wie een artikel noemt, heeft gekozen.
    assert doorvraag("Artikel 3:2, het tweede lid.", antwoord) == ""


def test_een_keuzevraag_midden_in_het_antwoord_telt_niet():
    """Alleen de vragen waarmee het antwoord eindigt: een vraag met een gewone zin erna is beantwoord of retorisch."""
    assert open_keuzevraag("Bedoel je artikel 3:1? Dat artikel regelt de zorgvuldigheid.") == ""
    assert open_keuzevraag("Welk artikel bedoel je? Ik ga uit van artikel 9. Klopt dat?") == ""
    assert open_keuzevraag("Het staat in de Awb. **Bedoel je artikel 3:1 of 3:2?**") == "Bedoel je artikel 3:1 of 3:2?"


# De vorm uit ronde 3 van de meting van ADR-016 (13 nov 2026, gesprek v-artikel-zonder-wet op de supervisorweg, beurt 2):
# de keuzevraag, "Bijvoorbeeld:" en dan een opsomming. De meting bewaart de tekst van het antwoord niet; dit is die vorm
# met de zin die het meetverslag citeert.
MET_LIJST = ("De Awb kent geen artikel 3 zonder hoofdstuk: de artikelen heten 3:1, 3:2 enzovoort.\n\n"
             "Kun je aangeven welk artikel 3 je precies bedoelt? Bijvoorbeeld:\n\n"
             "- **Artikel 3:1** – de toepasselijkheid van hoofdstuk 3\n"
             "- **Artikel 3:2** – zorgvuldige voorbereiding\n"
             "- **Artikel 3:4** – belangenafweging\n")


@pytest.mark.parametrize("antwoord", [
    MET_LIJST,
    MET_LIJST.replace("? Bijvoorbeeld:\n\n", "?\n\nBijvoorbeeld:\n"),          # het kopje op een eigen regel
    MET_LIJST.replace(" Bijvoorbeeld:", ""),                                        # de opsomming direct onder de vraag
    MET_LIJST.replace("- **", "1. **", 1).replace("- **", "2. **", 1).replace("- **", "3. **", 1),   # genummerd
    MET_LIJST.replace("Kun je aangeven", "**Kun je aangeven").replace("bedoelt?", "bedoelt?**"),      # de vraag vet
])
def test_een_keuzevraag_met_de_mogelijkheden_in_een_opsomming_eronder_wordt_herkend(antwoord):
    assert open_keuzevraag(antwoord) == "Kun je aangeven welk artikel 3 je precies bedoelt?"
    tekst = doorvraag("En het tweede lid?", antwoord)
    assert tekst.startswith("Ik weet nog niet welk artikel je bedoelt") and "Noem het artikel" in tekst
    # Wie het artikel noemt, heeft gekozen.
    assert doorvraag("Artikel 3:2, het tweede lid.", antwoord) == ""


@pytest.mark.parametrize("antwoord", [
    # Een opsomming zonder vraag ervoor: gewoon een antwoord.
    "Hoofdstuk 3 van de Awb bevat onder meer:\n- Artikel 3:1\n- Artikel 3:2\n",
    # Na de vraag komt nog een gewone zin: de vraag staat niet meer open.
    "Welk artikel bedoel je? Ik ga uit van artikel 3:2.\n- Lid 1 gaat over de voorbereiding\n- Lid 2 over de aanvrager\n",
    # Een lange opsomming of lange regels zijn inhoud, geen rijtje mogelijkheden.
    "Welk artikel bedoel je?\n" + "".join(f"- Artikel 3:{i}\n" for i in range(1, 15)),
    "Welk artikel bedoel je?\n- " + "Artikel 3:2 bepaalt dat het bestuursorgaan bij de voorbereiding van een besluit de nodige kennis vergaart. " * 2 + "\n",
    # Een vraag die geen keuze voorlegt.
    "Wil je meer weten? Bijvoorbeeld:\n- de voorbereiding\n- de motivering\n",
])
def test_een_opsomming_maakt_van_een_antwoord_geen_keuzevraag(antwoord):
    assert open_keuzevraag(antwoord) == ""
    assert doorvraag("En het tweede lid?", antwoord) == ""


def test_in_het_gesprek_vraagt_lex_ook_na_een_opsomming_door_zonder_model(monkeypatch):
    """De supervisorweg: het vervolg op een keuzevraag met een opsomming gaat niet naar het model."""
    from agent.nodes import supervisie
    from test_routering import _bouw
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    b = _bouw()  # een model dat faalt als het wordt aangeroepen
    state = {"question": "En het tweede lid?", "modus": "auto", "focus": {},
             "messages": [{"role": "user", "content": "Ik bedoel de Awb."},
                          {"role": "assistant", "content": MET_LIJST},
                          {"role": "user", "content": "En het tweede lid?"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "afwijzen" and "welk artikel" in upd["afwijs_melding"]
