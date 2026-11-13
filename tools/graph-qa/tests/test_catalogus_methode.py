"""Elk onderdeel van de catalogus is van één methode, of uitdrukkelijk neutraal (plan methodes scheiden, S2, test 3).

De annotatieketen, de annotatie-UI en de JAS-tools zijn van wetsanalyse. De vaste lijst hieronder staat los van de
tabel in `agent/catalogus.py`: verdwijnt een onderdeel van de annotatieketen daar uit de tabel, dan wordt het hier rood
en niet stil neutraal.
"""
from __future__ import annotations

import pytest
from bronmodel.catalogus import NEUTRAAL

from agent import catalogus
from agent.methodepakket import PAKKET
from agent.tools import JAS_TOOL_NAMEN
from agent.tools.annotatie_tools import ANNOTATIE_TOOLS

ONDERDELEN = {o.id: o for o in catalogus.catalogus()}

#: Wat van wetsanalyse moet zijn, uit het plan (§5), onafhankelijk van de tabel in de code.
VAN_WETSANALYSE = [
    "methode/wetsanalyse",
    "workflow/annotatieketen", "agent/annotatie", "route/annotatie_doel", "route/annotaties_lezen",
    "route/meerdere_artikelen", "agentprofiel/annotaties_lezen", "sjabloon/antwoord_annotaties",
    "tool/search_annotaties", "tool/get_annotatie", "tool/overzicht_annotaties", "tool/get_annotatiedekking",
    "tool/jas_klasse_opvragen", "regelset/jas.profielen", "regelset/jas.verklaringen",
    "workflow/begrippenketen", "agent/begrippen", "route/begrippen_lezen", "agentprofiel/begrippen_lezen",
    "sjabloon/antwoord_begrip", "tool/search_begrippen", "tool/get_begrip",
    "workflow/werkgebied_intake", "workflow/bronselectie", "workflow/bronnen_vinden", "agent/deelvragen",
    "route/werkgebied_samenstellen", "route/bronselectie", "route/dekking",
    "agentprofiel/definitie", "agentprofiel/duiding", "agentprofiel/algemeen", "agentprofiel/centraal",
    "agentprofiel/centraal_breed", "agentprofiel/retrieval",
]
#: Wat neutraal moet blijven: de graaf, de bronnen naast de wet, de controles en de vaste routes daarop.
NEUTRAAL_VERWACHT = [
    "tool/get_artikel", "tool/search_wetgeving", "tool/zoek_definitie", "tool/resolve_begrip", "tool/geldigheid",
    "connector/kamerstukken", "connector/rechtspraak", "controle/brongetrouwheid", "controle/id_herkomst",
    "workflow/overzicht", "workflow/bepaling", "workflow/bron_lezen", "workflow/vaste_melding", "workflow/regie",
    "route/overzicht", "route/bepaling", "route/genoemd_stuk", "route/doorvraag", "sjabloon/antwoord_bepaling",
    "sjabloon/antwoord_duiding", "sjabloon/antwoord_extern",
]


def test_elk_onderdeel_heeft_een_methode_skill_of_is_neutraal():
    toegestaan = set(PAKKET["skills"]) | {NEUTRAAL}
    fout = {o.id: o.methode for o in ONDERDELEN.values() if o.methode not in toegestaan}
    assert fout == {}


@pytest.mark.parametrize("id_", VAN_WETSANALYSE)
def test_de_annotatieketen_de_begrippen_en_het_werkgebied_zijn_van_wetsanalyse(id_):
    assert ONDERDELEN[id_].methode == "wetsanalyse"


@pytest.mark.parametrize("id_", NEUTRAAL_VERWACHT)
def test_de_graaf_de_bronnen_en_de_controles_zijn_neutraal(id_):
    assert ONDERDELEN[id_].methode == NEUTRAAL


def test_elke_annotatieleestool_en_elke_jas_tool_is_van_wetsanalyse():
    """Uit de registers zelf: een nieuwe annotatieleestool of JAS-tool kan niet stil neutraal zijn."""
    namen = {t["name"] for t in ANNOTATIE_TOOLS} | set(JAS_TOOL_NAMEN)
    assert namen and {n: ONDERDELEN[f"tool/{n}"].methode for n in namen} == {n: "wetsanalyse" for n in namen}


def test_elke_regelset_van_de_twee_ketens_is_van_wetsanalyse():
    regelsets = [o for o in ONDERDELEN.values() if o.soort == "regelset" and o.naam.startswith(("jas.", "begrippen."))]
    assert regelsets and all(o.methode == "wetsanalyse" for o in regelsets)


def test_een_methode_is_van_zichzelf_en_een_rol_van_zijn_skill():
    assert ONDERDELEN["methode/wetsuitvoering"].methode == "wetsuitvoering"
    assert all(o.methode == o.deel_van.split("/", 1)[1] for o in ONDERDELEN.values() if o.soort == "rol")


def test_de_tabel_noemt_alleen_onderdelen_die_bestaan():
    assert catalogus.VAN_WETSANALYSE <= set(ONDERDELEN)


def test_de_methode_reist_mee_naar_de_werkplek():
    assert ONDERDELEN["workflow/annotatieketen"].als_dict()["methode"] == "wetsanalyse"
