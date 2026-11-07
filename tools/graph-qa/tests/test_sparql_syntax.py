"""Guard: elke query-bouwer levert SPARQL op die een parser accepteert.

De bouwers in `agent/graph/queries.py` zetten SPARQL in elkaar met f-strings, en dat is de goedkope
oplossing met één bekende prijs: een tikfout — een haakje, een puntkomma, een variabele die alleen
in de ORDER BY bestaat — komt er pas uit als de graaf hem afwijst. In productie is dat een
tool-foutmelding midden in een beurt van een jurist; hier is het een rode test in een seconde.

Dit is de derde laag onder de retrieval-guards, en de drie dekken elk iets anders af:
- **hier**: is het geldige SPARQL? (syntaxis)
- `tests/test_predicaat_dekking.py`: bestaan de gebruikte termen? (vocabulaire)
- `eval/retrieval_smoke.py`: komt er in de échte graaf iets uit? (data)

rdflib parseert alleen; er gaat geen enkele call naar buiten. De Lucene-predicaten (`luc:`, `inst:`)
zijn voor de parser gewone prefixed names, dus die hoeven niet te bestaan.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import agent
from agent import begrip_kaart, bronnen_vinden, plekken, regelingnamen, zoekvragen
from agent.graph import queries as q
from agent.tools import begrip_tools

rdflib = pytest.importorskip("rdflib", reason="rdflib is een dev-only parser-afhankelijkheid")
from rdflib.plugins.sparql import prepareQuery  # noqa: E402

IW = "BWBR0004770"
LEIDRAAD = "BWBR0024096"

# (naam, sparql) – elke publieke bouwer minstens één keer, en de takken die van een parameter
# afhangen apart. Een bouwer die hier niet in staat wordt nergens op syntaxis getoetst.
GEVALLEN: list[tuple[str, str]] = [
    ("fts", q.fts("aansprakelijk")),
    ("fts+veld+scope", q.fts("bestuurder", 5, veld="definieertBegrip", bwb_id=IW, soort="Onderdeel", offset=10)),
    ("zoek_opbouw", q.zoek_opbouw("invordering")),
    ("zoek_opbouw+scope", q.zoek_opbouw("uitstel van betaling", IW, 10, offset=10, meer=True)),
    ("plaats_in_opbouw", q.plaats_in_opbouw([f"urn:bwb:{IW}:artikel:4", "urn:bwb:BWBR0005537:artikel:4%3A94a"])),
    ("bepalingen_in_delen", q.bepalingen_in_delen([f"urn:bwb:{IW}:hoofdstuk:II", f"urn:bwb:{LEIDRAAD}:artikel:28"])),
    ("bepalingen_met_onderwerp", q.bepalingen_met_onderwerp("invordering")),
    ("definities_van", q.definities_van("invordering")),
    ("trefwoord_regelingen", q.trefwoord_regelingen("invordering")),
    ("list_regelingen", q.list_regelingen()),
    ("soort_van_regelingen", q.soort_van_regelingen(["BWBR0004770", "BWBR0024096"])),
    ("get_artikel", q.get_artikel(IW, "36")),
    ("get_lid", q.get_lid(IW, "2", "1")),
    ("get_bepaling", q.get_bepaling(LEIDRAAD, "25.1")),
    ("get_regeling_info", q.get_regeling_info(IW)),
    ("follow_verwijzingen", q.follow_verwijzingen(IW, "36")),
    ("follow_verwijzingen+lid", q.follow_verwijzingen(IW, "36", "1")),
    ("follow_verwijzingen+divisie", q.follow_verwijzingen(LEIDRAAD, "25.1")),
    ("verwijst_naar_deze", q.verwijst_naar_deze(IW, "36")),
    ("verwijst_naar_deze+divisie", q.verwijst_naar_deze(LEIDRAAD, "25.1")),
    ("referenced_by", q.referenced_by(IW, "36")),
    ("referenced_by+divisie", q.referenced_by(LEIDRAAD, "25.1")),
    ("context", q.context(IW, "36")),
    ("context+lid", q.context(IW, "36", "1")),
    ("context+divisie", q.context(LEIDRAAD, "25.1")),
    ("resolve_begrip", q.resolve_begrip("invordering")),
    ("count_by_type", q.count_by_type()),
    ("inhoudsopgave", q.inhoudsopgave(IW)),
    ("inhoudsopgave+vanaf+diep", q.inhoudsopgave(IW, "6", diepte=4)),
    ("inhoudsopgave+divisie", q.inhoudsopgave(LEIDRAAD, "25", diepte=1)),
    ("zoek_definitie", q.zoek_definitie("bestuurder")),
    ("zoek_definitie+scope", q.zoek_definitie("bestuurder", IW)),
    ("grondslagen", q.grondslagen(LEIDRAAD)),
    ("grondslagen+artikel", q.grondslagen(IW, "36")),
    ("grondslagen+divisie", q.grondslagen(LEIDRAAD, "25.1")),
    ("geldigheid", q.geldigheid(IW)),
    ("geldigheid+lid", q.geldigheid(IW, "36", "1")),
    ("geldigheid+divisie", q.geldigheid(LEIDRAAD, "25.1")),
    ("bijlagen", q.bijlagen(IW)),
    ("bijlagen+nummer", q.bijlagen(IW, "1")),
    ("ontologie", q.ontologie()),
    # De bouwers buiten `queries.py` horen bij hun domein; `test_elke_bouwer_buiten_queries_wordt_getoetst`
    # ontdekt ze zelf.
    ("begrip_kaart.q_brondefinities", begrip_kaart.q_brondefinities(["bestuurder"])),
    ("begrip_kaart.q_onder", begrip_kaart.q_onder(["bestuurder"])),
    ("begrip_kaart.q_verwijzingen", begrip_kaart.q_verwijzingen(f"urn:bwb:{IW}:artikel:4")),
    ("begrip_kaart.q_teksten", begrip_kaart.q_teksten([f"urn:bwb:{IW}:artikel:4"])),
    ("begrip_kaart.q_verwezen", begrip_kaart.q_verwezen([IW])),
    ("bronnen_vinden.q_uitgaand", bronnen_vinden.q_uitgaand([f"urn:bwb:{IW}:artikel:4"], 10)),
    ("bronnen_vinden.q_inkomend", bronnen_vinden.q_inkomend([f"urn:bwb:{IW}:artikel:4"], 10)),
    ("bronnen_vinden.q_teksten", bronnen_vinden.q_teksten([f"urn:bwb:{IW}:artikel:4"])),
    ("bronnen_vinden.q_definities", bronnen_vinden.q_definities([IW], 10)),
    ("bronnen_vinden.q_opbouw", bronnen_vinden.q_opbouw([f"urn:bwb:{IW}:artikel:4"])),
    ("plekken.q_plekken", plekken.q_plekken([f"urn:bwb:{IW}:artikel:4"])),
    ("regelingnamen._query", regelingnamen._query([IW])),
    ("zoekvragen.q_subdivisies", zoekvragen.q_subdivisies([f"urn:bwb:{IW}:artikel:4"], 10)),
    ("tools.begrip_tools.q_begrippen", begrip_tools.q_begrippen("bestuurder", ["onderzocht"], "wg", 10)),
]


@pytest.mark.parametrize(("naam", "sparql"), GEVALLEN, ids=[g[0] for g in GEVALLEN])
def test_query_is_geldige_sparql(naam: str, sparql: str):
    try:
        prepareQuery(sparql)
    except Exception as exc:  # noqa: BLE001 – rdflib gooit van alles; we willen de tekst zien
        pytest.fail(f"{naam} levert ongeldige SPARQL op: {exc}\n\n{sparql}")


# Functies met een query in de eigen tekst, zonder aparte bouwer. Ze hebben een eigen test tegen fakes.
INLINE: set[str] = set()


def _sparql_bouwers() -> set[str]:
    """Alle functies in `agent/` buiten `queries.py` die SPARQL opbouwen, gevonden op wat er in staat."""
    wortel = Path(agent.__file__).parent
    uit = set()
    for pad in wortel.rglob("*.py"):
        if pad.name == "queries.py" or "runstore" in pad.parts:
            continue
        module = ".".join(pad.relative_to(wortel).with_suffix("").parts)
        for fn in ast.walk(ast.parse(pad.read_text(encoding="utf-8"))):
            if not isinstance(fn, ast.FunctionDef):
                continue
            teksten = (n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str))
            if any(re.search(r"\bSELECT\b[^\n]*\?\w", t) for t in teksten):
                uit.add(f"{module}.{fn.name}")
    return uit


def test_elke_bouwer_buiten_queries_wordt_getoetst():
    """Staat een bouwer niet in GEVALLEN, dan ziet alleen de live graaf een tikfout, als stil minder resultaat."""
    getoetst = {naam for naam, _ in GEVALLEN}
    ontbreekt = _sparql_bouwers() - getoetst - INLINE
    assert not ontbreekt, f"deze SPARQL-bouwers staan niet in GEVALLEN: {sorted(ontbreekt)}"


def test_elke_publieke_bouwer_wordt_getoetst():
    """Een nieuwe bouwer zonder syntaxis-controle glipt er anders zo doorheen."""
    getoetst = {naam.split("+")[0] for naam, _ in GEVALLEN}
    publiek = {
        naam for naam in dir(q)
        if not naam.startswith("_") and callable(getattr(q, naam)) and getattr(q, naam).__module__ == q.__name__
    }
    # Helpers die geen complete query opleveren.
    helpers = {"regeling_iri", "artikel_iri", "lid_iri", "node_patroon", "is_artikelnummer", "opbouw_lucene", "onderwerpwoorden", "is_bron_iri"}
    ontbreekt = publiek - getoetst - helpers
    assert not ontbreekt, f"deze query-bouwers staan niet in GEVALLEN: {sorted(ontbreekt)}"
