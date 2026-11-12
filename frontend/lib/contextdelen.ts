/** De categorieën waarin een modelverzoek uiteenvalt, voor de contextweergave (plan contextweergave, ADR-015).
 *
 *  Eén register: id, label, kleur en volgorde staan hier en nergens anders. De id's en hun volgorde zijn die van
 *  graph-qa (`tools/graph-qa/agent/contextdelen.py`); `contextdelen.test.ts` houdt beide gelijk, zoals bij `jas.ts`.
 *  De kleuren zijn tokens van de app: blauw in stappen voor het vaste deel (tools en systeem), warme en neutrale kleuren
 *  voor wat per beurt verandert. Kleur draagt nooit alleen: de legenda noemt elke categorie met haar omvang. */

export interface Contextdeel {
  id: string;
  /** In gewone taal, voor de legenda. */
  label: string;
  /** Wat erin zit, als uitleg bij de regel. */
  uitleg: string;
  /** De vulkleur van een vakje in het raster en van de stip in de legenda. */
  kleur: string;
  /** Staat vóór het cachepunt op de systeemprompt (tools en systeem): het vaste deel dat een uur in de cache blijft. */
  voorvoegsel: boolean;
}

export const CONTEXTDELEN: readonly Contextdeel[] = [
  { id: "systeem", label: "Vaste instructies", uitleg: "Wie Lex is en hoe Lex werkt.", kleur: "bg-lint", voorvoegsel: true },
  { id: "methode", label: "Methode", uitleg: "De methode Wetsanalyse voor dit soort vraag.", kleur: "bg-lint/50", voorvoegsel: true },
  { id: "graaftools", label: "Wettools", uitleg: "Waarmee Lex in de wetgeving zoekt en leest.", kleur: "bg-link", voorvoegsel: true },
  { id: "connectortools", label: "Bronnen naast de wet", uitleg: "De tools van de bronnen die aanstaan.", kleur: "bg-info", voorvoegsel: true },
  { id: "agenttools", label: "Eigen tools van de agent", uitleg: "Waarmee de agent het werk overdraagt aan een vaste route of aan een breder profiel.", kleur: "bg-info/70", voorvoegsel: true },
  { id: "sjablonen", label: "Antwoordvormen", uitleg: "De vaste vormen waarin Lex een antwoord opbouwt.", kleur: "bg-info/40", voorvoegsel: true },
  { id: "beurtcontext", label: "Plan en gesprekscontext", uitleg: "Het plan, het werkgebied of dossier en welke bronnen aanstaan.", kleur: "bg-gold", voorvoegsel: false },
  { id: "opdracht", label: "Opdracht", uitleg: "De opdracht die deze agent kreeg.", kleur: "bg-waarschuwing", voorvoegsel: false },
  { id: "historie", label: "Eerdere beurten", uitleg: "Wat er eerder in dit gesprek is gevraagd en geantwoord.", kleur: "bg-muted", voorvoegsel: false },
  { id: "beurt", label: "Vraag en stappen", uitleg: "Je vraag en wat Lex in deze beurt zelf schreef.", kleur: "bg-succes", voorvoegsel: false },
  { id: "toolresultaten", label: "Opgehaalde tekst", uitleg: "Wat de tools in deze beurt teruggaven.", kleur: "bg-ink", voorvoegsel: false },
  { id: "overig", label: "Overig", uitleg: "Wat niet in te delen is.", kleur: "bg-faint", voorvoegsel: false },
];

const PER_ID = new Map(CONTEXTDELEN.map((d) => [d.id, d]));
const OVERIG = CONTEXTDELEN[CONTEXTDELEN.length - 1];

/** Het deel bij een id. Een id dat de werkplek nog niet kent (een nieuwere graph-qa) telt als *Overig*, zodat de som
 *  blijft kloppen. */
export function contextdeel(id: string): Contextdeel {
  return PER_ID.get(id) ?? OVERIG;
}
