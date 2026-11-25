// Plugins van Lex (plan docs/architectuur/plan-contenttoets.md): de spiegel van `packages/bronmodel/bronmodel/plugins.py`.
// `plugins.test.ts` leest die bron. Een plugin is een methode naast de wetsanalyse die je per gesprek aan of uit zet; in de
// werkplek is hij een commando met tekst erachter (`/contenttoets <tekst>`), dat graph-qa zonder model herkent.

export interface Plugin {
  naam: string; label: string; beschrijving: string; skill: string; profiel: string; sjabloon: string; actie: string;
  commando: string;
  /** Wat het commando in het menu zegt. */
  hulp: string;
}

export const PLUGINS: readonly Plugin[] = [
  {
    naam: "contenttoets", label: "Contenttoets",
    beschrijving: "Toetst content, zoals een webtekst, op juistheid en volledigheid tegen de wet- en regelgeving.",
    skill: "contenttoets", profiel: "contenttoets", sjabloon: "antwoord_contenttoets", actie: "contenttoets",
    commando: "contenttoets",
    hulp: "Toets een tekst op juistheid en volledigheid tegen de wet: plak de tekst erachter",
  },
];

/** Een plugin die de beheerder aanbiedt (`GET /api/plugins`, het register bij de api). */
export interface AangebodenPlugin { naam: string; label: string; beschrijving: string; commando: string }

/** De plugins van dit gesprek: wat de beheerder aanbiedt, en de eigen keuze van het gesprek (`Gesprek.plugins`;
 *  `null` = alles wat aangeboden is staat aan). */
export interface PluginStand { aangeboden: readonly AangebodenPlugin[]; gesprek: readonly string[] | null }

export const LEGE_PLUGINS: PluginStand = { aangeboden: [], gesprek: null };

/** De namen die in dit gesprek aanstaan: alleen wat de beheerder aanbiedt. */
export function actievePlugins({ aangeboden, gesprek }: PluginStand): string[] {
  const gekozen = gesprek ?? aangeboden.map((p) => p.naam);
  return aangeboden.filter((p) => gekozen.includes(p.naam)).map((p) => p.naam);
}

/** Eén plugin om: de nieuwe eigen stand van het gesprek. */
export function wisselPlugin(stand: PluginStand, naam: string): string[] {
  const nu = actievePlugins(stand);
  if (!stand.aangeboden.some((p) => p.naam === naam)) return nu;
  return nu.includes(naam) ? nu.filter((n) => n !== naam) : [...nu, naam];
}

/** Wat een beurt meestuurt: niets zonder aangeboden plugin (graph-qa beslist dan met zijn proefvlag), anders de stand. */
export function beurtPlugins(stand: PluginStand): { plugins?: string[] } {
  return stand.aangeboden.length ? { plugins: actievePlugins(stand) } : {};
}

/** De commando's van de plugins die in dit gesprek aanstaan. */
export function pluginCommandos(actief: readonly string[]): Plugin[] {
  return PLUGINS.filter((p) => actief.includes(p.naam));
}

/** Streng: wat de BFF teruggaf, of een lege lijst. Een storing kost de plugins, niet de werkplek. */
export function parsePlugins(v: unknown): AangebodenPlugin[] {
  const lijst = (v as { plugins?: unknown } | null)?.plugins;
  if (!Array.isArray(lijst)) return [];
  return lijst.filter((p): p is AangebodenPlugin => !!p && typeof p === "object" && typeof p.naam === "string" &&
    typeof p.label === "string" && PLUGINS.some((x) => x.naam === p.naam))
    .map((p) => ({ naam: p.naam, label: p.label, beschrijving: String(p.beschrijving ?? ""), commando: String(p.commando ?? p.naam) }));
}
