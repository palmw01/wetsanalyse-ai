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
