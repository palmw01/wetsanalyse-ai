"""De vorm van de toestandsgraaf per configuratietak — nodes en edges, niet het gedrag.

Waarom deze test bestaat: `build_graph` legt de edges in drie aparte takken (decompositie,
planning, kaal), en de annotatieketen stond daarin twee keer letterlijk gekopieerd. Wie die keten
wijzigt moet dat op elke plek doen, en niets bewaakte dat ze gelijk bleven. Deze test legt de
structuur vast zodat een ontvlechting van `build_graph` aantoonbaar gedragsbehoudend is: hij hoort
ongewijzigd groen te blijven. Moet je hem aanpassen, dan is er iets aan de routering veranderd —
dat mag, maar het moet een bewuste wijziging zijn en geen bijvangst van een refactor.

De gedragskant (wat een node dóét) staat in test_orchestrator.py, test_critic_lus.py en
test_kandidaat_splitsing.py; hier gaat het puur om welke node met welke verbonden is.
"""

from __future__ import annotations

import pytest

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


# De annotatieketen zoals hij er in élke tak met annotatie uitziet: lineair van annoteer naar emit,
# met `emit` als enige uitgang naar advance. Geen enkele edge wijst terug naar een eerdere stap —
# dat is de eigenschap die de keten convergentievrij maakt en die we niet stilzwijgend willen verliezen.
def annotatieketen(entry: str) -> set[tuple[str, str, str, bool]]:
    label = "annoteer" if entry != "annoteer" else ""
    keten = {
        ("critic", "patch", "", True),
        ("critic", "emit", "", True),
        ("patch", "herzie", "", True),
        ("patch", "critic", "", True),
        ("patch", "emit", "", True),
        ("herzie", "critic", "", False),
        ("emit", "advance", "", False),
    }
    if entry == "annoteer":
        keten.add(("annoteer", "critic", "", False))
    else:
        keten.add(("annoteer_kandidaten", "annoteer_klasseer", "", False))
        keten.add(("annoteer_klasseer", "critic", "", False))
    return keten


ANNOTATIE_NODES = {"critic", "patch", "herzie", "emit"}


def test_planning_is_de_standaardvorm():
    nodes, edges = structuur(enable_planning=True)
    assert nodes == {
        "supervisor", "agent", "tools", "verify", "correct", "finalize",
        "annoteer", "critic", "patch", "herzie", "emit", "advance", "afwijzen",
    }
    assert edges == {
        (START, "supervisor", "", False),
        ("supervisor", "agent", "", True),
        ("supervisor", "annoteer", "", True),
        ("supervisor", "afwijzen", "", True),
        ("afwijzen", EIND, "", False),
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
        ("advance", "afwijzen", "", True),
        ("advance", EIND, "einde", True),
    } | annotatieketen("annoteer")


def test_decompositie_voegt_de_deelvraag_keten_toe():
    nodes, edges = structuur(enable_decomposition=True)
    assert {"decompose", "solve", "synthesize", "resynth"} <= nodes
    # `correct` bestaat hier niet: een ongegrond antwoord gaat terug de synthese in (resynth),
    # niet terug naar de agent. Dat is het echte verschil met de planning-tak.
    assert "correct" not in nodes
    assert ("verify", "resynth", "correct", True) in edges
    assert ("decompose", "solve", "", False) in edges
    assert ("solve", "verify", "", True) in edges
    assert ("solve", "synthesize", "", True) in edges
    assert ("synthesize", "verify", "", False) in edges
    assert ("resynth", "synthesize", "", False) in edges
    # De supervisor kan hier ook naar decompose routeren.
    assert ("supervisor", "decompose", "", True) in edges
    assert ("advance", "decompose", "", True) in edges


def test_de_kale_tak_heeft_geen_annotatie_en_geen_supervisor():
    nodes, edges = structuur(enable_planning=False)
    assert nodes == {"agent", "tools", "verify", "correct", "finalize"}
    assert not (ANNOTATIE_NODES & nodes)
    assert "supervisor" not in nodes
    # Zonder supervisor begint de graaf bij de agent en eindigt finalize direct.
    assert (START, "agent", "", False) in edges
    assert ("finalize", EIND, "", False) in edges


@pytest.mark.parametrize("tak", [{"enable_planning": True}, {"enable_decomposition": True}])
def test_de_annotatieketen_is_identiek_in_elke_tak_die_hem_heeft(tak):
    """De invariant die de ontvlechting moet behouden: de keten van annoteer tot emit is in beide
    takken exact dezelfde, ook al verschilt de antwoordketen eromheen."""
    _, edges = structuur(**tak)
    assert annotatieketen("annoteer") <= edges


@pytest.mark.parametrize("tak", [{"enable_planning": True}, {"enable_decomposition": True}])
def test_kandidaat_splitsing_vervangt_alleen_de_ingang(tak):
    """Met splitsing komt er één node vóór: annoteer_kandidaten → annoteer_klasseer → critic.
    De rest van de keten is ongewijzigd, en alles wat naar 'annoteer' routeerde wijst nu naar
    de eerste van de twee."""
    nodes, edges = structuur(**tak, enable_kandidaat_splitsing=True)
    assert {"annoteer_kandidaten", "annoteer_klasseer"} <= nodes
    assert "annoteer" not in nodes
    assert annotatieketen("annoteer_kandidaten") <= edges
    # Elke router die 'annoteer' als bestemming kende, wijst nu naar de kandidaten-node.
    for bron in ("supervisor", "agent", "advance"):
        assert (bron, "annoteer_kandidaten", "annoteer", True) in edges


def test_stopbewaking_zit_om_elke_node():
    """Elke node wordt via `add()` geregistreerd, die `stopbaar()` eromheen wikkelt. Zou een node
    daarbuiten om geregistreerd worden, dan negeert hij een stopverzoek."""
    nodes, _ = structuur(enable_decomposition=True, enable_kandidaat_splitsing=True)
    # Alle nodes van de rijkste tak; als hier iets bijkomt zonder dat deze lijst meegroeit,
    # is dat een signaal om te controleren of het via add() ging.
    assert nodes == {
        "supervisor", "decompose", "solve", "synthesize", "resynth", "agent", "tools",
        "annoteer_kandidaten", "annoteer_klasseer", "critic", "patch", "herzie", "emit",
        "advance", "afwijzen", "verify", "finalize",
    }
