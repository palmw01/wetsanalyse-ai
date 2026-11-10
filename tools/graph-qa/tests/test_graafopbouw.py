"""De vorm van de toestandsgraaf per configuratietak — nodes en edges, niet het gedrag.

Waarom deze test bestaat: `build_graph` legde de edges in drie aparte takken (decompositie,
planning, kaal; de decompositie is in november 2026 weggehaald), en de annotatieketen stond daarin
twee keer letterlijk gekopieerd. Wie die keten
wijzigt moet dat op elke plek doen, en niets bewaakte dat ze gelijk bleven. Deze test legt de
structuur vast zodat een ontvlechting van `build_graph` aantoonbaar gedragsbehoudend is: hij hoort
ongewijzigd groen te blijven. Moet je hem aanpassen, dan is er iets aan de routering veranderd —
dat mag, maar het moet een bewuste wijziging zijn en geen bijvangst van een refactor.

De gedragskant (wat een node dóét) staat in test_orchestrator.py en test_hybride_keten.py; hier
gaat het puur om welke node met welke verbonden is.
"""

from __future__ import annotations

from agent.orchestrator import build_graph

from tests.fakes import FakeGraph, FakeLLM, make_settings

START, EIND = "__start__", "__end__"


def structuur(**kw) -> tuple[set[str], set[tuple[str, str, str, bool]]]:
    """(nodes, edges) van een gebouwde graaf. Een edge is (bron, doel, label, conditioneel);
    het label is niet-leeg als de routernaam afwijkt van de doelnode."""
    g = build_graph(make_settings(**kw), FakeLLM([]), FakeGraph())
    getekend = g.compile().get_graph()
    edges = {(e.source, e.target, e.data or "", e.conditional) for e in getekend.edges}
    return set(g.nodes), edges


# De annotatieketen zoals hij er in élke tak met annotatie uitziet (ADR-001): de hybride
# analyse en daarna emit, als enige uitgang naar advance. Geen review-lus, geen terugwaartse edge.
ANNOTATIEKETEN = {("annoteer", "emit", "", False), ("emit", "advance", "", False)}
ANNOTATIE_NODES = {"annoteer", "emit"}


def test_planning_is_de_standaardvorm():
    nodes, edges = structuur(enable_planning=True)
    assert nodes == {
        "supervisor", "agent", "tools", "sjabloon", "verify", "correct", "finalize", "annotaties_zoeken", "bron_lezen",
        "bron_lijst", "begrippen_zoeken", "overzicht_bouwen", "bepaling_lezen", "annoteer", "emit", "advance", "afwijzen",
        "werkgebied_intake", "bronselectie", "agent_taak",
    }
    assert edges == {
        ("agent", "sjabloon", "", True),
        ("sjabloon", "verify", "", True),
        ("sjabloon", "agent", "", True),
        (START, "supervisor", "", False),
        ("supervisor", "agent", "", True),
        ("supervisor", "annoteer", "", True),
        ("supervisor", "afwijzen", "", True),
        # De leesroute zoekt eerst zelf; pas daarna formuleert de agent (zie nodes/annotatie_lezen.py).
        ("supervisor", "annotaties_zoeken", "", True),
        ("annotaties_zoeken", "agent", "", False),
        # Een stuk dat de vraag bij id noemt (ADR-013): eerst lezen in code (nodes/bron_lezen.py), dan formuleren.
        ("supervisor", "bron_lezen", "", True),
        ("bron_lezen", "agent", "", True),
        # Een stuk zonder tekst bij de bron: de melding uit code, zonder model (nameting 10 nov 2026).
        ("bron_lezen", "verify", "", True),
        # Een lijstvraag over een bron naast de wet: de zoektool in code en het blok `stukken`, dan de controle; na een
        # fout de agent (nodes/bron_lijst.py).
        ("supervisor", "bron_lijst", "", True),
        ("bron_lijst", "verify", "", True),
        ("bron_lijst", "agent", "", True),
        # Idem voor vastgelegde begrippen (nodes/begrippen_lezen.py, fase F4).
        ("supervisor", "begrippen_zoeken", "", True),
        ("begrippen_zoeken", "agent", "", False),
        # Een overzichtsvraag: het overzicht en zijn tekst komen uit de graaf, zonder model; alleen als
        # het bouwen faalt neemt de agent het over (nodes/overzicht.py).
        ("supervisor", "overzicht_bouwen", "", True),
        ("overzicht_bouwen", "verify", "", True),
        ("overzicht_bouwen", "agent", "", True),
        # De tekst van een bepaling (ADR-010, D1): ophalen en vullen in code, dan de controle; lukt het niet, de agent.
        ("supervisor", "bepaling_lezen", "", True),
        ("bepaling_lezen", "verify", "", True),
        ("bepaling_lezen", "agent", "", True),
        ("afwijzen", EIND, "", False),
        # Een werkgebied samenstellen (activiteit 1): één stap van de intake per beurt, zonder
        # verify/finalize – er wordt niets over wetgeving beweerd (nodes/werkgebied.py).
        ("supervisor", "werkgebied_intake", "", True),
        ("werkgebied_intake", EIND, "", False),
        # De bronselectie per deelvraag (spoor J): één stap per beurt, de stand staat bij de api
        # (nodes/bronselectie.py).
        ("supervisor", "bronselectie", "", True),
        ("bronselectie", EIND, "", False),
        # Een taak van een agent op het werkgebied (F3c): deelvragen, begrippen, het werkgebied
        # annoteren. Eén taak per beurt, zonder verify/finalize (nodes/agent_taak.py).
        ("supervisor", "agent_taak", "", True),
        ("agent_taak", EIND, "", False),
        ("agent", "tools", "", True),
        ("agent", "verify", "", True),
        ("agent", "annoteer", "", True),
        ("tools", "agent", "", False),
        ("verify", "correct", "", True),
        ("verify", "finalize", "", True),
        ("correct", "agent", "", False),
        ("finalize", "advance", "", False),
        ("advance", "agent", "", True),
        ("advance", "annoteer", "", True),
        ("advance", "annotaties_zoeken", "", True),
        ("advance", "bron_lezen", "", True),
        ("advance", "bron_lijst", "", True),
        ("advance", "begrippen_zoeken", "", True),
        ("advance", "overzicht_bouwen", "", True),
        ("advance", "bepaling_lezen", "", True),
        ("advance", "afwijzen", "", True),
        ("advance", "werkgebied_intake", "", True),
        ("advance", "bronselectie", "", True),
        ("advance", "agent_taak", "", True),
        ("advance", EIND, "einde", True),
    } | ANNOTATIEKETEN


def test_de_kale_tak_heeft_geen_annotatie_en_geen_supervisor():
    nodes, edges = structuur(enable_planning=False)
    assert nodes == {"agent", "tools", "sjabloon", "verify", "correct", "finalize"}
    assert not (ANNOTATIE_NODES & nodes)
    assert "supervisor" not in nodes
    # Zonder supervisor begint de graaf bij de agent en eindigt finalize direct.
    assert (START, "agent", "", False) in edges
    assert ("finalize", EIND, "", False) in edges


def test_stopbewaking_zit_om_elke_node():
    """Elke node wordt via `add()` geregistreerd, die `stopbaar()` eromheen wikkelt. Zou een node
    daarbuiten om geregistreerd worden, dan negeert hij een stopverzoek."""
    nodes, _ = structuur()
    # Alle nodes van de rijkste tak; als hier iets bijkomt zonder dat deze lijst meegroeit,
    # is dat een signaal om te controleren of het via add() ging.
    assert nodes == {
        "supervisor", "agent", "tools", "sjabloon", "correct",
        "annoteer", "emit", "advance", "afwijzen", "verify", "finalize", "annotaties_zoeken", "bron_lezen", "bron_lijst",
        "begrippen_zoeken", "overzicht_bouwen", "bepaling_lezen", "werkgebied_intake", "bronselectie", "agent_taak",
    }
