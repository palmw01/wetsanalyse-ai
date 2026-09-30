// Wat er in de chatthread van de werkplek kan staan.
//
// Dit type stond in `WerkplekClient` zelf. Het staat nu hier omdat de rondleiding een voorbeeldbeurt
// moet kunnen opbouwen (`lib/rondleidingDemo.ts`) zonder dat `lib/` een component hoeft te
// importeren – dezelfde reden waarom de rest van de rekenkern in `lib/` woont.

import type { Reeks } from "./reeks";
import type {
  AgentDoelInvoer, AgentGrounding, AgentHergebruik, AgentKandidaat, AgentKeuze, Bron,
} from "./types";

export type ThreadItem = { tool_executions?: import("./annotatieNode").ToolExecution[] } & (
  // `nietVerstuurd`: de vraag is bewaard maar niet aangenomen (er liep al een beurt). Hij blijft in
  // beeld omdat hij na herladen tóch terugkomt – wat je ziet moet kloppen met wat er bewaard is.
  | { id: string; type: "user"; tekst: string; over?: string; nietVerstuurd?: boolean }
  | { id: string; type: "antwoord"; tekst: string; denk?: string; bronnen?: Bron[];
      // De brongetrouwheidstoets van déze beurt. Live; hij reist niet mee in het berichtcontract,
      // maar de statusregel ervan staat wél in `denk` en blijft dus na herladen terug te vinden.
      grounding?: AgentGrounding }
  // `denk` = de tijdlijn van het samenspel (supervisor → ophaal → annoteer → emit). Die blijft ook
  // bewaard als de beurt een annotatie blijkt; juist bij een annotatie wil je achteraf kunnen zien
  // hoe hij tot stand kwam.
  // `titel` komt uit het bericht zelf (`annotatie_titel`), niet uit het document: er is geen foreign
  // key, dus na het verwijderen van het document is dit het enige dat de kaart nog kan benoemen.
  | {
      id: string; type: "annotatie"; slug: string; titel?: string;
      denk?: string;
      /** Lex hergebruikte de laag (deels) in plaats van opnieuw te annoteren. */
      hergebruik?: AgentHergebruik;
      /** De bepaling, zodat "Lex opnieuw laten annoteren" hem kan meegeven. */
      doel?: AgentDoelInvoer;
      annotatie_doel?: import("./annotatieNode").NodeDoel;
    }
  // De vraag noemde een onderwerp: de agent vond bepalingen, de jurist kiest er één.
  // `keuze` gezet: de onderdelen van één bepaling (leden, subbepalingen) of een dubbelzinnig nummer.
  | { id: string; type: "kandidaten"; tekst: string; kandidaten: AgentKandidaat[]; keuze?: AgentKeuze }
  // Meerdere onderdelen van één artikel in één run: per onderdeel een regel met zijn eigen spoor.
  | { id: string; type: "reeks"; reeks: Reeks; tekst?: string });
