"""De nieuwe retrieval-tools: geven ze een RESULTAAT terug, en op de juiste bepaling?

Bewust op het resultaat en niet op de querytekst. Dat onderscheid is in dit project duur betaald:
`test_queries.py` toetste jarenlang `"bwb:bevat" in sparql` en bevestigde daarmee een tool die
nooit één rij opleverde. Een FakeGraph bewijst niet dat de graaf data heeft — daarvoor is
`eval/retrieval_smoke.py` — maar wél dat de handler zijn bouwer aanroept, de argumenten doorgeeft en
het antwoord ongeschonden teruglevert. De vorm van de query toetsen we alleen waar hij een
BESLISSING draagt: welke node wordt aangewezen.
"""
from __future__ import annotations

import pytest

from agent import tools
from fakes import FakeGraph

IW = "BWBR0004770"
LEIDRAAD = "BWBR0024096"

NIEUW = [
    ("verwijst_naar_deze", {"bwb_id": IW, "artikel": "36"}),
    ("inhoudsopgave", {"bwb_id": IW}),
    ("zoek_definitie", {"term": "bestuurder"}),
    ("grondslagen", {"bwb_id": LEIDRAAD}),
    ("geldigheid", {"bwb_id": IW, "artikel": "36"}),
    ("bijlagen", {"bwb_id": IW}),
]


@pytest.mark.parametrize(("naam", "args"), NIEUW, ids=[n for n, _ in NIEUW])
def test_tool_levert_het_graafantwoord_terug(naam: str, args: dict):
    g = FakeGraph(result="RIJEN")
    assert tools.dispatch(naam, g, args) == "RIJEN"
    assert len(g.queries) == 1, "één tool-aanroep hoort één graafquery te zijn"


# --- het bepaling-pad: artikelnummer én decimaal nummer wijzen dezelfde soort node aan ---

@pytest.mark.parametrize(
    "naam", ["follow_verwijzingen", "verwijst_naar_deze", "referenced_by", "get_context"]
)
def test_artikelnummer_wordt_een_directe_iri(naam: str):
    g = FakeGraph(result="x")
    tools.dispatch(naam, g, {"bwb_id": IW, "artikel": "36"})
    assert f"BIND(<urn:bwb:{IW}:artikel:36> AS ?node)" in g.queries[0]


@pytest.mark.parametrize(
    "naam", ["follow_verwijzingen", "verwijst_naar_deze", "referenced_by", "get_context"]
)
def test_decimaal_nummer_werkt_ook(naam: str):
    """Vóór 4 sep 2026 gaf elk van deze tools een 400 op een Leidraad-bepaling.

    Ze bouwden op `artikel_iri`, en die weigert een punt. De ~800 divisies van de Leidraad
    Invordering 2008 waren daarmee onbereikbaar voor élke verwijzings- en contextvraag, terwijl het
    corpus-pad ze gewoon opleverde. Een jurist die zo'n bepaling opende kreeg een half platform.
    """
    g = FakeGraph(result="x")
    out = tools.dispatch(naam, g, {"bwb_id": LEIDRAAD, "nummer": "25.1"})
    assert not out.startswith("Fout bij tool"), out
    assert 'bwb:nummer "25.1"' in g.queries[0]
    assert f'STRSTARTS(STR(?node), "urn:bwb:{LEIDRAAD}")' in g.queries[0]


def test_zonder_aanduiding_een_duidelijke_fout():
    """Geen stille lege query: een tool-foutmelding kan het model herstellen."""
    out = tools.dispatch("follow_verwijzingen", FakeGraph(), {"bwb_id": IW})
    assert "artikel" in out and "nummer" in out


# --- afbakening en validatie ---

def test_zoeken_op_een_onbekend_veld_geeft_een_leesbare_fout():
    out = tools.dispatch("search_wetgeving", FakeGraph(), {"query": "x", "veld": "bestaat_niet"})
    assert "Onbekend zoekveld" in out


def test_zoeken_binnen_een_regeling_scopet_op_de_iri():
    g = FakeGraph(result="x")
    tools.dispatch("search_wetgeving", g, {"query": "aansprakelijk", "bwb_id": IW})
    assert f'STRSTARTS(STR(?node), "urn:bwb:{IW}")' in g.queries[0]


def test_zoekresultaat_draagt_de_vindplaats():
    """Een treffer zonder jci/BWB-id/citeertitel dwingt tot een tweede call om te kunnen citeren."""
    g = FakeGraph(result="x")
    tools.dispatch("search_wetgeving", g, {"query": "aansprakelijk"})
    for veld in ("?jci", "?bwbId", "?citeertitel", "?soort"):
        assert veld in g.queries[0]


def test_bijlage_zonder_nummer_geeft_de_lijst_en_met_nummer_de_inhoud():
    g = FakeGraph(result="x")
    tools.dispatch("bijlagen", g, {"bwb_id": IW})
    tools.dispatch("bijlagen", g, {"bwb_id": IW, "nummer": "1"})
    assert "heeftBijlage ?bijlage" in g.queries[0]
    assert "heeftBijlage ?node" in g.queries[1] and "?deel" in g.queries[1]


def test_grondslagen_dekt_beide_richtingen():
    """Delegatie is een vraag met twee kanten; ze in twee tools splitsen laat het model raden."""
    g = FakeGraph(result="x")
    tools.dispatch("grondslagen", g, {"bwb_id": LEIDRAAD})
    for relatie in ("berust-op", "grondslag-voor", "bevoegdheid-voor", "in-familie", "berust-op-mij"):
        assert relatie in g.queries[0]


# --- afkapping ---

def test_afkapping_zegt_hoeveel_er_wegviel():
    """"Ingekort op 8000 tekens" zegt niet of je een regel of een derde van de bepaling mist."""
    from agent.agent_common import kap_toolresultaat

    uit = kap_toolresultaat("x" * 9000, 8000)
    assert "1000 van 9000 tekens niet getoond" in uit
    assert "offset" in uit, "het model moet weten dát er een uitweg is"
    assert kap_toolresultaat("kort", 8000) == "kort"


@pytest.mark.parametrize("naam", ["grondslagen", "geldigheid"])
def test_ook_deze_tools_kennen_het_decimale_pad(naam: str):
    """Het schema biedt 'nummer' aan, dus de handler moet hem ook lezen – anders vraagt het model
    naar bepaling 25.1 en krijgt hij het antwoord over de hele regeling, zonder dat iets dat meldt."""
    g = FakeGraph(result="x")
    tools.dispatch(naam, g, {"bwb_id": LEIDRAAD, "nummer": "25.1"})
    assert 'bwb:nummer "25.1"' in g.queries[0]
