"""De dertien JAS-klassen – de canonieke bron voor het annotatiedomein.

Deze lijst stond eerder in een script in de wetsanalyse-skill, dat `validation.py` op import-tijd
inlaadde. Dat betekende dat het productie-image een Claude-skill
moest meedragen om te kunnen starten. Toen de standalone analyse-werkstroom (de reviewlus en de
rapportviewer) verdween, is deze kennis hierheen verhuisd: de api hangt nu nergens buiten `api/`
meer aan vast.

Twee andere plekken dragen dezelfde waarden en worden door tests bewaakt:
`frontend/lib/jas.ts` (een browser kan dit bestand niet lezen) via `tests/test_jas_kleuren_drift.py`,
en `tools/graph-qa/agent/jas_klassen.py` met een eigen drift-test. Wijzig je hier iets, wijzig het
daar mee – de tests wijzen je erop.
"""

from __future__ import annotations

# De canonieke weergave-volgorde van de dertien JAS-klassen (docs/wetsanalyse/wa-table.png).
# Alle resultaatweergaves (exports, frontend) sorteren hierop.
JAS_KLASSEN_VOLGORDE: tuple[str, ...] = (
    "Rechtssubject",
    "Rechtsobject",
    "Rechtsbetrekking",
    "Rechtsfeit",
    "Voorwaarde",
    "Afleidingsregel",
    "Variabele en variabelewaarde",
    "Parameter en parameterwaarde",
    "Operator",
    "Tijdsaanduiding",
    "Plaatsaanduiding",
    "Delegatiebevoegdheid en delegatie-invulling",
    "Brondefinitie",
)

GELDIGE_JAS_KLASSEN: set[str] = set(JAS_KLASSEN_VOLGORDE)


def jas_sorteersleutel(klasse: str) -> int:
    """Sorteersleutel voor presentatie: klasse-index in de wa-table-volgorde;
    onbekende klassen achteraan. Gebruik met een stabiele sort zodat de onderlinge
    (document)volgorde binnen een klasse behouden blijft."""
    try:
        return JAS_KLASSEN_VOLGORDE.index(klasse)
    except ValueError:
        return len(JAS_KLASSEN_VOLGORDE)


# De labelkleuren per JAS-klasse uit de officiële JAS-tabel (docs/wetsanalyse/wa-table.png),
# per pixel gesampled: (achtergrond, rand). De rand is dezelfde kleur ~22% donkerder; de tekst is
# altijd #1A1A1A (≥ 5,4:1 op elke tint). Samengevoegde klassen nemen de hoofdkleur uit de tabel
# (Variabele / Parameter / Delegatiebevoegdheid).
JAS_KLASSE_KLEUREN: dict[str, tuple[str, str]] = {
    "Rechtssubject": ("#d8eaf7", "#a8b6c0"),
    "Rechtsobject": ("#b2c3e3", "#8a98b1"),
    "Rechtsbetrekking": ("#90a2d0", "#707ea2"),
    "Rechtsfeit": ("#bad8f1", "#91a8bb"),
    "Voorwaarde": ("#b7d8cd", "#8ea89f"),
    "Afleidingsregel": ("#d47479", "#a55a5e"),
    "Variabele en variabelewaarde": ("#f5dc5e", "#bfab49"),
    "Parameter en parameterwaarde": ("#e6b8bb", "#b38f91"),
    "Operator": ("#d7e8e2", "#a7b4b0"),
    "Tijdsaanduiding": ("#cbb8d6", "#9e8fa6"),
    "Plaatsaanduiding": ("#e6d3e5", "#b3a4b2"),
    "Delegatiebevoegdheid en delegatie-invulling": ("#b0b1b2", "#898a8a"),
    "Brondefinitie": ("#edefef", "#b8baba"),
}

JAS_TEKSTKLEUR = "#1A1A1A"
