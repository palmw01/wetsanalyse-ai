"""Guard: de juiste rol krijgt de juiste tool, en elke tool legt uit wat hij teruggeeft.

Twee faalmodi die geen enkele bestaande test ving, allebei stil:

1. **De weestool.** Een tool kan perfect werken, getest zijn en in `TOOLS` staan – en tóch nooit
   worden aangeroepen, omdat geen enkele specialist hem in zijn set heeft. `algemeen` ziet alles
   (`tools=None`), dus de fout valt niet op zolang de router daar toevallig heen routeert. Bij het
   uitbreiden van de toollaag van 13 naar 19 tools is dat het waarschijnlijkste ongeluk.
2. **De tool zonder gebruiksaanwijzing.** Het model kiest op de beschrijving. Staat daar niet wat er
   terugkomt, dan moet het gokken wat het krijgt – en kiest het bij twijfel de tool die het al kent.

De derde controle is de spiegel: een naam in een specialist-set die niet (meer) bestaat wordt
stilzwijgend genegeerd door `anthropic_schemas(only=...)`. Zo verdwijnt een tool uit een rol door een
hernoeming, zonder dat iets rood wordt.
"""
from __future__ import annotations

import pytest

from agent import specialists, tools

# Tools die bewust alleen via `algemeen` beschikbaar zijn. Elke uitzondering hoort een reden te
# hebben; een lege verzameling is prima, een ongemotiveerde toevoeging niet.
ALLEEN_ALGEMEEN: set[str] = set()

# Ondergrens voor een bruikbare beschrijving. Bewust ruim: hij vangt "leeg" en "één zin zonder
# retourvorm", niet een bewust bondige tekst.
MIN_BESCHRIJVING = 80


def _alle_rolsets() -> dict[str, frozenset[str]]:
    return {
        naam: spec.tools
        for naam, spec in specialists.SPECIALISTS.items()
        if spec.tools is not None
    }


def test_geen_weestools():
    toegewezen: set[str] = set()
    for namen in _alle_rolsets().values():
        toegewezen |= set(namen)
    wees = {t["name"] for t in tools.TOOLS} - toegewezen - ALLEEN_ALGEMEEN
    assert not wees, (
        f"deze tools zitten in geen enkele specialist-set: {sorted(wees)}. "
        "Ze zijn dan alleen bereikbaar als de router toevallig 'algemeen' kiest. "
        "Wijs ze toe in agent/specialists.py of zet ze met reden in ALLEEN_ALGEMEEN."
    )


def test_elke_naam_in_een_rolset_bestaat():
    bekend = {t["name"] for t in tools.TOOLS} | set(tools.JAS_TOOL_NAMEN)
    for rol, namen in _alle_rolsets().items():
        onbekend = set(namen) - bekend
        assert not onbekend, (
            f"specialist {rol!r} noemt tools die niet bestaan: {sorted(onbekend)}. "
            "anthropic_schemas() negeert zo'n naam stil, dus de rol mist die tool zonder melding."
        )


def test_elke_beschrijving_zegt_wat_de_tool_teruggeeft():
    for t in tools.TOOLS:
        assert len(t["description"]) >= MIN_BESCHRIJVING, (
            f"beschrijving van {t['name']!r} is te kort om op te kiezen: {t['description']!r}"
        )


@pytest.mark.parametrize(
    ("rol", "moet_hebben"),
    [
        ("definitie", {"zoek_definitie", "resolve_begrip"}),
        ("duiding", {"get_context", "verwijst_naar_deze", "grondslagen", "geldigheid", "inhoudsopgave"}),
        ("retrieval", {"get_bepaling", "inhoudsopgave", "search_wetgeving"}),
    ],
)
def test_de_kerntools_per_rol(rol: str, moet_hebben: set[str]):
    """De toewijzing uit het ontwerp, vastgelegd zodat een refactor hem niet stil terugdraait."""
    assert moet_hebben <= set(specialists.SPECIALISTS[rol].tools)


def test_de_ophaalrol_duidt_niet():
    """`retrieval` haalt een bepaling op en levert een doel-JSON; duiden doet een andere rol.

    Toolbereik is hier gedragssturing en geen opruiming: geef je deze rol `grondslagen` en
    `geldigheid`, dan gaat hij analyseren in een stap die alleen hoort aan te wijzen.
    """
    namen = set(specialists.SPECIALISTS["retrieval"].tools)
    assert not ({"grondslagen", "geldigheid", "raw_sparql"} & namen)


def test_elke_graaftool_zit_in_de_retrieval_smoke():
    """Een nieuwe tool zonder smoke-controle is een nieuwe kans op stille onvolledigheid.

    De unit-tests draaien tegen een FakeGraph en bewijzen dus alleen dat de bouwer wordt aangeroepen,
    niet dat de query in de échte graaf iets matcht. Dat gat is precies waar `bwb:bevat` in viel.
    """
    from eval.retrieval_smoke import CONTROLES

    gedekt = {c.tool for c in CONTROLES}
    # `semantic_search` hangt aan een similarity-index die na elke herstart van de niet-persistente
    # graaf ontbreekt; `raw_sparql` heeft geen vaste vorm om op te toetsen.
    buiten = {"semantic_search", "raw_sparql"}
    ongedekt = {t["name"] for t in tools.TOOLS} - gedekt - buiten
    assert not ongedekt, (
        f"deze tools worden nergens tegen de echte graaf geraakt: {sorted(ongedekt)}. "
        "Voeg een Controle toe in eval/retrieval_smoke.py."
    )
