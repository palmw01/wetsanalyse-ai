// Wat er in de chatthread van de werkplek kan staan.
//
// Dit type stond in `WerkplekClient` zelf. Het staat nu hier omdat de rondleiding een voorbeeldbeurt
// moet kunnen opbouwen (`lib/rondleidingDemo.ts`) zonder dat `lib/` een component hoeft te
// importeren – dezelfde reden waarom de rest van de rekenkern in `lib/` woont.

import type { AgentGrounding, AgentKandidaat, Bron, OntbrekendItem } from "./types";

export type ThreadItem =
  | { id: string; type: "user"; tekst: string; over?: string }
  | { id: string; type: "antwoord"; tekst: string; denk?: string; bronnen?: Bron[];
      // De brongetrouwheidstoets van déze beurt. Live; hij reist niet mee in het berichtcontract,
      // maar de statusregel ervan staat wél in `denk` en blijft dus na herladen terug te vinden.
      grounding?: AgentGrounding }
  // `denk` = de tijdlijn van het samenspel (supervisor → ophaal → annoteerder ⇄ Critic). Die werd
  // eerder weggegooid zodra de beurt een annotatie bleek; juist bij een annotatie wil je achteraf
  // kunnen zien hoe hij tot stand kwam.
  // `titel` komt uit het bericht zelf (`annotatie_titel`), niet uit het document: er is geen foreign
  // key, dus na het verwijderen van het document is dit het enige dat de kaart nog kan benoemen.
  | { id: string; type: "annotatie"; slug: string; titel?: string; ontbrekend?: OntbrekendItem[]; denk?: string }
  // De vraag noemde een onderwerp: de agent vond bepalingen, de jurist kiest er één.
  | { id: string; type: "kandidaten"; tekst: string; kandidaten: AgentKandidaat[] };
