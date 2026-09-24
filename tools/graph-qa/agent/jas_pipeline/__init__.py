"""De hybride JAS-pijplijn (ADR-001, `docs/architectuur/adr-001-hybride-jas-pijplijn.md`).

Pure functies en datatypes, zonder LangGraph: bronstructuur → taalanalyse → detectoren →
kandidaten → classificatie → validatie. De orchestrator roept dit aan vanuit zijn nodes, achter
de vlag `ANNOTATION_PIPELINE`; zolang die op `legacy` staat, raakt niets hiervan een beurt.
"""
