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

import pytest

from agent.graph import queries as q

rdflib = pytest.importorskip("rdflib", reason="rdflib is een dev-only parser-afhankelijkheid")
from rdflib.plugins.sparql import prepareQuery  # noqa: E402

IW = "BWBR0004770"
LEIDRAAD = "BWBR0024096"

# (naam, sparql) – elke publieke bouwer minstens één keer, en de takken die van een parameter
# afhangen apart. Een bouwer die hier niet in staat wordt nergens op syntaxis getoetst.
GEVALLEN: list[tuple[str, str]] = [
    ("fts", q.fts("aansprakelijk")),
    ("fts+veld+scope", q.fts("bestuurder", 5, veld="definieertBegrip", bwb_id=IW, soort="Onderdeel", offset=10)),
    ("list_regelingen", q.list_regelingen()),
    ("get_artikel", q.get_artikel(IW, "36")),
    ("get_artikel_corpus", q.get_artikel_corpus(IW, "36")),
    ("get_lid", q.get_lid(IW, "2", "1")),
    ("get_bepaling", q.get_bepaling(LEIDRAAD, "25.1")),
    ("get_bepaling_corpus", q.get_bepaling_corpus(LEIDRAAD, "25.1")),
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
]


@pytest.mark.parametrize(("naam", "sparql"), GEVALLEN, ids=[g[0] for g in GEVALLEN])
def test_query_is_geldige_sparql(naam: str, sparql: str):
    try:
        prepareQuery(sparql)
    except Exception as exc:  # noqa: BLE001 – rdflib gooit van alles; we willen de tekst zien
        pytest.fail(f"{naam} levert ongeldige SPARQL op: {exc}\n\n{sparql}")


def test_elke_publieke_bouwer_wordt_getoetst():
    """Een nieuwe bouwer zonder syntaxis-controle glipt er anders zo doorheen."""
    getoetst = {naam.split("+")[0] for naam, _ in GEVALLEN}
    publiek = {
        naam for naam in dir(q)
        if not naam.startswith("_") and callable(getattr(q, naam)) and getattr(q, naam).__module__ == q.__name__
    }
    # Helpers die geen complete query opleveren.
    helpers = {"regeling_iri", "artikel_iri", "lid_iri", "node_patroon", "is_artikelnummer"}
    ontbreekt = publiek - getoetst - helpers
    assert not ontbreekt, f"deze query-bouwers staan niet in GEVALLEN: {sorted(ontbreekt)}"
