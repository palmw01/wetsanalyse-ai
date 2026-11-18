# Gegenereerd uit .claude/skills/wetsanalyse/begripverwachting.json; niet handmatig bewerken.
# Draai tools/graph-qa/scripts/genereer_begripverwachting.py.
"""Wat de methode per JAS-klasse verwacht in activiteit 3a: een begrip, een omschrijving of een definitie."""
from __future__ import annotations

#: De eerste twaalf tekens van de sha256 van de bron.
VERWACHTING_VERSIE = 'fc06e86e0c68'

#: De drie verwachtingen.
VERWACHTINGEN = ('begrip', 'omschrijving', 'definitie')

#: klasse → verwachting.
VERWACHTING = {'Rechtssubject': 'begrip',
 'Rechtsobject': 'begrip',
 'Rechtsbetrekking': 'begrip',
 'Rechtsfeit': 'begrip',
 'Voorwaarde': 'omschrijving',
 'Afleidingsregel': 'begrip',
 'Variabele en variabelewaarde': 'begrip',
 'Parameter en parameterwaarde': 'begrip',
 'Operator': 'begrip',
 'Tijdsaanduiding': 'begrip',
 'Plaatsaanduiding': 'begrip',
 'Delegatiebevoegdheid en delegatie-invulling': 'begrip',
 'Brondefinitie': 'definitie'}

#: verwachting → wat ze betekent.
UITLEG = {'begrip': 'De formulering krijgt een begrip: een nieuw, of een bestaand met dezelfde betekenis.',
 'omschrijving': 'De formulering krijgt geen eigen begrip, maar een omschrijving bij de rechtsbetrekking, '
                 'het rechtsfeit of de afleidingsregel waar ze bij hoort.',
 'definitie': 'De formulering is de wettelijke definitie van een begrip en hangt daar als definitie aan.'}


def verwacht(klasse: str) -> str:
    """Wat de methode van een formulering van deze klasse verwacht; een onbekende klasse verwacht een begrip."""
    return VERWACHTING.get(klasse, "begrip")
