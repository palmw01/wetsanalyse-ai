"""De hybride JAS-pijplijn (ADR-001, `docs/architectuur/adr-001-hybride-jas-pijplijn.md`).

Pure functies en datatypes, zonder LangGraph: bronstructuur → taalanalyse → detectoren →
kandidaten → classificatie → validatie. `nodes/annotatie.annoteer_node` roept `keten.analyseer`
aan; dit is de enige annotatieroute.
"""
