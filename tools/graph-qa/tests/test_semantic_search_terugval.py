"""semantic_search als de similarity-index er niet is.

De GraphDB-opslag op Azure is niet-persistent. Na een herstart vult de import-job de graaf terug,
maar de similarity-index komt niet mee: die staat dan wél geconfigureerd en bestaat níét. Dat is
geen storing waar de beurt op hoort te stranden — tekstueel zoeken werkt gewoon — maar het mag ook
niet stil gebeuren, want dan zoekt Lex weken semantisch zonder dat iemand het merkt.
"""

from __future__ import annotations

import logging

from agent.mcp_client import MCPError
from agent.tools import dispatch

from tests.fakes import FakeGraph, make_settings


class GeenIndex(FakeGraph):
    """Een graaf waarin de similarity-index niet bestaat."""

    def semantic_search(self, query: str, limit: int = 10) -> str:
        raise MCPError("no such similarity index: bwb_similarity")


def test_zonder_geconfigureerde_index_wijst_hij_naar_tekstueel_zoeken():
    uit = dispatch("semantic_search", FakeGraph(), {"query": "bestuurdersaansprakelijkheid"},
                   make_settings(similarity_index=""))
    assert "search_wetgeving" in uit


def test_een_ontbrekende_index_valt_terug_in_plaats_van_te_falen(caplog):
    """Het model krijgt een bruikbare aanwijzing, geen rauwe toolfout."""
    with caplog.at_level(logging.WARNING):
        uit = dispatch("semantic_search", GeenIndex(), {"query": "aansprakelijkheid"},
                       make_settings(similarity_index="bwb_similarity"))

    # Dezelfde melding als bij een niet-geconfigureerde index: het model hoeft het verschil niet
    # te kennen, het moet alleen weten dat tekstueel zoeken de weg is.
    assert "search_wetgeving" in uit
    assert "Fout bij tool" not in uit

    # Maar een beheerder moet het wél kunnen zien.
    waarschuwingen = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert waarschuwingen, "een ontbrekende index hoort een waarschuwing te loggen"
    assert "similarity-index" in waarschuwingen[0].getMessage()


def test_een_werkende_index_blijft_gewoon_zoeken():
    uit = dispatch("semantic_search", FakeGraph(), {"query": "aansprakelijkheid"},
                   make_settings(similarity_index="bwb_similarity"))
    assert "search_wetgeving" not in uit
