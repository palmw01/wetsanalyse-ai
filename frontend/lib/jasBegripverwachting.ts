// Gegenereerd uit .claude/skills/wetsanalyse/begripverwachting.json; niet handmatig bewerken.
// Draai tools/graph-qa/scripts/genereer_begripverwachting.py.

export type Verwachting = "begrip" | "omschrijving" | "definitie";

export const VERWACHTING_VERSIE = "fc06e86e0c68";

export const VERWACHTING: Record<string, Verwachting> = {
  "Rechtssubject": "begrip",
  "Rechtsobject": "begrip",
  "Rechtsbetrekking": "begrip",
  "Rechtsfeit": "begrip",
  "Voorwaarde": "omschrijving",
  "Afleidingsregel": "begrip",
  "Variabele en variabelewaarde": "begrip",
  "Parameter en parameterwaarde": "begrip",
  "Operator": "begrip",
  "Tijdsaanduiding": "begrip",
  "Plaatsaanduiding": "begrip",
  "Delegatiebevoegdheid en delegatie-invulling": "begrip",
  "Brondefinitie": "definitie"
};

export const UITLEG: Record<Verwachting, string> = {
  "begrip": "De formulering krijgt een begrip: een nieuw, of een bestaand met dezelfde betekenis.",
  "omschrijving": "De formulering krijgt geen eigen begrip, maar een omschrijving bij de rechtsbetrekking, het rechtsfeit of de afleidingsregel waar ze bij hoort.",
  "definitie": "De formulering is de wettelijke definitie van een begrip en hangt daar als definitie aan."
};

/** Wat de methode van een formulering van deze klasse verwacht; een onbekende klasse verwacht een begrip. */
export function verwacht(klasse: string): Verwachting {
  return VERWACHTING[klasse] ?? "begrip";
}
