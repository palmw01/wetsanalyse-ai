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
from agent.resultaat import is_contract
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


# Een rij zoals de graaf hem levert (SPARQL-TSV), met de kolommen die elke tool leest.
_RIJ = ("?niveau\t?ouder\t?deel\t?soort\t?nummer\t?bron\t?node\n"
        f'"1"\t"urn:bwb:{IW}"\t<urn:bwb:{IW}:hoofdstuk:VI>\t"Hoofdstuk"\t"VI"\t<urn:bwb:{IW}:artikel:2>\t<urn:bwb:{IW}:artikel:3>\n')


@pytest.mark.parametrize(("naam", "args"), NIEUW, ids=[n for n, _ in NIEUW])
def test_tool_levert_het_graafantwoord_terug(naam: str, args: dict):
    g = FakeGraph(result=_RIJ)
    uit = tools.dispatch(naam, g, args)
    assert len(g.queries) == 1, "één tool-aanroep hoort één graafquery te zijn"
    data = is_contract(uit)
    assert data is not None, uit[:200]
    assert data["status"] == "ok" and data["resultaten"], uit
    assert f"urn:bwb:{IW}" in uit, "de vindplaats moet in het resultaat staan (bronnen, grounding)"


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
    """Elk van deze tools moet een Leidraad-bepaling aankunnen, niet een 400 geven.

    `artikel_iri` weigert een punt. Bouwen ze daarop, dan zijn de ~800 divisies van de Leidraad
    Invordering 2008 onbereikbaar voor élke verwijzings- en contextvraag, terwijl het corpus-pad ze
    gewoon oplevert. Een jurist die zo'n bepaling opent krijgt dan een half platform.
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

@pytest.mark.parametrize("naam", ["grondslagen", "geldigheid"])
def test_ook_deze_tools_kennen_het_decimale_pad(naam: str):
    """Het schema biedt 'nummer' aan, dus de handler moet hem ook lezen – anders vraagt het model
    naar bepaling 25.1 en krijgt hij het antwoord over de hele regeling, zonder dat iets dat meldt."""
    g = FakeGraph(result="x")
    tools.dispatch(naam, g, {"bwb_id": LEIDRAAD, "nummer": "25.1"})
    assert 'bwb:nummer "25.1"' in g.queries[0]


# --- zoek_opbouw: het onderwerp in de opschriften ---------------------------------------------------

def test_opbouw_lucene_vindt_stam_en_samenstelling():
    """De index bevat stammen en een wildcardterm wordt niet geanalyseerd: `invordering*` mist
    "Invordering in eerste aanleg" (geïndexeerd als `invorder`) en "Dwanginvordering". Gemeten op
    acceptatie, 7 okt 2026."""
    from agent.graph.queries import opbouw_lucene

    assert opbouw_lucene("invordering") == "titel:((invordering OR *invorder*))"
    assert opbouw_lucene("Welke artikelen gaan over uitstel van betaling?") == \
        "titel:((uitstel OR *uitstel*) AND (betaling OR *betal*))"
    # Een kort woord krijgt geen samenstellingswildcard: `*btw*` zou te veel vangen en kort is al precies.
    assert opbouw_lucene("btw") == "titel:(btw)"


def test_opbouw_lucene_laat_geen_lucene_of_sparql_syntax_door():
    from agent.graph.queries import opbouw_lucene

    q = opbouw_lucene('invordering") } ; DROP * OR titel:x')
    assert '"' not in q and "}" not in q and ";" not in q
    with pytest.raises(ValueError):
        opbouw_lucene("de van het")


def test_zoek_opbouw_noemt_de_bepalingen_en_verdiept_een_groot_deel():
    from agent.resultaat import is_contract

    tsv = ("?node\t?score\t?soort\t?label\t?jci\t?bwbId\t?citeertitel\t?aantal\t?nummers\n"
           '<urn:bwb:BWBR0004770:hoofdstuk:II>\t"1.5"\t"Hoofdstuk"\t"Hoofdstuk II – Invordering in eerste aanleg"'
           '\t""\t"BWBR0004770"\t"Invorderingswet 1990"\t"3"\t"10|8|9"\n'
           '<urn:bwb:BWBR0005537:hoofdstuk:4:titeldeel:4.4>\t"1.1"\t"Titeldeel"\t"Titeldeel 4.4"'
           '\t""\t"BWBR0005537"\t"Awb"\t"40"\t"' + "|".join(f"4:{i}" for i in range(85, 125)) + '"\n')
    g = FakeGraph(result=tsv)
    data = is_contract(tools.dispatch("zoek_opbouw", g, {"onderwerp": "invordering"}))
    assert data and data["volledig"]
    hoofdstuk, titeldeel = data["resultaten"]
    assert hoofdstuk["bepalingen"] == "8, 9, 10", "in natuurlijke volgorde"
    assert "bepalingen" not in titeldeel
    assert titeldeel["openen"] == {"tool": "inhoudsopgave", "args": {
        "bwb_id": "BWBR0005537", "vanaf": "urn:bwb:BWBR0005537:hoofdstuk:4:titeldeel:4.4"}}
