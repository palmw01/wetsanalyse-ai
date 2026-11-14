// Wat er in de chatthread van de werkplek kan staan.
//
// Dit type stond in `WerkplekClient` zelf. Het staat nu hier omdat de rondleiding een voorbeeldbeurt
// moet kunnen opbouwen (`lib/rondleidingDemo.ts`) zonder dat `lib/` een component hoeft te
// importeren – dezelfde reden waarom de rest van de rekenkern in `lib/` woont.

import type { DelegatieWeergave } from "./delegatie";
import type { Reeks } from "./reeks";
import type {
  AgentGrounding, AgentHergebruik, AgentKandidaat, AgentKeuze, Bron, Overzicht,
} from "./types";

export type ThreadItem = (
  // `nietVerstuurd`: de vraag is bewaard maar niet aangenomen (er liep al een beurt). Hij blijft in
  // beeld omdat hij na herladen tóch terugkomt – wat je ziet moet kloppen met wat er bewaard is.
  | { id: string; type: "user"; tekst: string; over?: string; nietVerstuurd?: boolean;
      // Een klik op een vraagkaartje (activiteit 1): geen bubbel, het antwoord staat in de Vragen-kaart.
      antwoordOp?: import("./vraagkaart").AntwoordOp;
      // Het antwoord op een bevestiging erboven (de knop of *Annuleren*): het voorstel is afgehandeld.
      bevestigingKeuze?: import("./werkgebiedAnnoteren").BevestigingKeuze;
      // Door de code doorgegeven in een deelgesprek (de opdracht, of de antwoorden van de jurist), van elke rol: geen bubbel
      // van de jurist maar een blok van Lex (`ThreadRij`).
      doorgegeven?: "opdracht" | "antwoorden" }
  | { id: string; type: "antwoord"; tekst: string; denk?: string; bronnen?: Bron[];
      // De brongetrouwheidstoets van déze beurt: live uit de stroom, na herladen van het bericht.
      grounding?: AgentGrounding;
      // Het overzicht van een onderwerp, uit de graaf (graph-qa `agent/overzicht.py`): de werkplek
      // toont het als blok onder de duiding, en de graafknop opent er de delen van.
      overzicht?: Overzicht;
      // Het antwoord als sjabloon (ADR-008): vaste blokken; `tekst` blijft het hele antwoord.
      antwoord?: import("./antwoord").Antwoord;
      // Lex stelt voor het werkgebied te annoteren (fase B): de knop eronder start de run.
      bevestiging?: import("./types").Bevestiging;
      // Een vraag van Lex bij het samenstellen van een werkgebied (activiteit 1): het kaartje eronder.
      vraagkaart?: import("./vraagkaart").Vraagkaart;
      // Hoe de beurt afliep: live uit de stroom, na herladen van het bericht, met dezelfde melding.
      uitkomst?: import("./types").BeurtUitkomst;
      // Wat de subagents of de regie van deze beurt doen (ADR-016 §A5): live uit de stroom, daarna van de api.
      delegatie?: DelegatieWeergave }
  // `denk` = de tijdlijn van het samenspel (supervisor → ophaal → annoteer → emit). Die blijft ook
  // bewaard als de beurt een annotatie blijkt; juist bij een annotatie wil je achteraf kunnen zien
  // hoe hij tot stand kwam.
  // `titel` komt uit het bericht zelf (de titel van het artefact), niet uit het document: er is geen foreign
  // key, dus na het verwijderen van het document is dit het enige dat de kaart nog kan benoemen.
  | {
      id: string; type: "annotatie"; slug: string; titel?: string;
      /** Wat Lex over de annotatie zegt: hoogstens vier zinnen, door graph-qa uit de data opgebouwd. */
      tekst?: string;
      denk?: string;
      /** Lex hergebruikte de laag (deels) in plaats van opnieuw te annoteren. */
      hergebruik?: AgentHergebruik;
      annotatie_doel?: import("./annotatieNode").NodeDoel;
      /** De meting van deze ronde: live uit het `run`-event, na herladen uit `Bericht.dekking`. */
      meting?: import("./types").BeurtMeting;
    }
  // Een ander artefact dan een annotatie (begripsvoorstellen, later afleidingsregels): een beurt van
  // Lex met een chip die het artefactpaneel van die soort opent (`lib/artefact.ts`). Een annotatie
  // blijft hierboven, met haar eigen hergebruik, opnieuw-knop en meting.
  | { id: string; type: "artefact"; artefact: import("./artefact").Artefact; tekst?: string; denk?: string;
      delegatie?: DelegatieWeergave;
      // De bundel van een regie met de knop voor de volgende fase (graph-qa #1521).
      bevestiging?: import("./types").Bevestiging }
  // De vraag noemde een onderwerp: de agent vond bepalingen, de jurist kiest er één.
  // `keuze` gezet: de onderdelen van één bepaling (leden, subbepalingen) of een dubbelzinnig nummer.
  | { id: string; type: "kandidaten"; tekst: string; kandidaten: AgentKandidaat[]; keuze?: AgentKeuze }
  // Meerdere onderdelen van één artikel in één run: per onderdeel een regel met zijn eigen spoor.
  | { id: string; type: "reeks"; reeks: Reeks; tekst?: string; uitkomst?: import("./types").BeurtUitkomst });
