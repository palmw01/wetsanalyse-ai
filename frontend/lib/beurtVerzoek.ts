// Wat een beurt vraagt, als één waarde.
//
// `verstuur` had zeven positionele parameters, en elke knop telde `undefined`s af tot zijn plek. Een verzoek is nu een
// object: wat erin staat gaat mee, de rest niet. Omdat het een waarde is kan een beurt hem later ook opnieuw sturen.
// Hoe het verzoek de run-aanvraag wordt (`startOpties`) en wat het user-bericht draagt (`userVelden`) staat hier puur,
// zodat vitest het kan toetsen.

import type { startRun } from "./api";
import type { AgentDoelInvoer } from "./types";
import { antwoordOp, type IntakeActie } from "./vraagkaart";
import { actieVerzoek, verzoekVan, type Onderwerp, type VraagLexActie } from "./vraagLex";

/** De knop bij een voorstel van Lex (fase B en C): het werkgebied en wat de analist bevestigde. */
export interface WerkgebiedAnnoteren {
  werkgebiedId: string;
  bevestigd?: number;
  modus?: "werkgebied_annoteren" | "begrippen_verdiepen";
  /** Alleen de bronnen onder de deelvragen (met `deelvraagId`: onder die ene), uit de bevestiging. */
  bereik?: "deelvragen";
  deelvraagId?: string;
  /** Bij meedenken: de inhoud van de werkvoorraad uit de bevestiging (spoor M). */
  werkvoorraadId?: string;
}

export interface BeurtVerzoek {
  /** De vraag; zonder prompt geldt wat er in het invoerveld staat. */
  prompt?: string;
  /** De bepaling, als die al vaststaat (zie `startRun`). */
  doel?: AgentDoelInvoer;
  /** "opnieuw" = de jurist vraagt expliciet om een nieuwe ronde op een al geannoteerd artikel; zonder doel betekent dat
   *  niets (de agent weet dan nog niet welk). */
  hergebruik?: "opnieuw";
  /** Meerdere onderdelen van één artikel: één run, elk onderdeel een eigen laag. */
  doelen?: AgentDoelInvoer[];
  annoteren?: WerkgebiedAnnoteren;
  /** Een klik op een vraagkaartje (activiteit 1, de bronselectie). */
  intake?: IntakeActie;
  /** Een suggestie met een actie: een vaste route, zonder model. */
  actie?: VraagLexActie;
}

export type StartOpties = NonNullable<Parameters<typeof startRun>[2]>;

/** De run-aanvraag bij een verzoek. `onderwerp` is waar de vraag over gaat (de chip), `werkgebiedId` het werkgebied van
 *  het gesprek. */
export function startOpties(
  v: BeurtVerzoek,
  { werkgebiedId, onderwerp }: { werkgebiedId?: string | null; onderwerp?: Onderwerp },
): StartOpties | undefined {
  const { annoteren, intake, actie, doel, doelen, hergebruik } = v;
  // Het werkgebied annoteren (fase B) is een eigen opdracht: geen context, geen doel, het werkgebied uit de bevestiging
  // (een oud gesprek kan buiten de context van dat werkgebied staan).
  if (annoteren) {
    return { modus: annoteren.modus ?? "werkgebied_annoteren", werkgebied_id: annoteren.werkgebiedId,
      ...(annoteren.bevestigd !== undefined ? { bevestigd: annoteren.bevestigd } : {}),
      ...(annoteren.bereik ? { bereik: annoteren.bereik } : {}),
      ...(annoteren.deelvraagId ? { deelvraag_id: annoteren.deelvraagId } : {}),
      ...(annoteren.werkvoorraadId ? { werkvoorraad_id: annoteren.werkvoorraadId } : {}) };
  }
  // Een klik op een vraagkaartje: geen context en geen doel; het werkgebied van het gesprek mag mee.
  if (intake) return { intake_actie: intake, ...(werkgebiedId ? { werkgebied_id: werkgebiedId } : {}) };
  // Een suggestie met een actie: een vaste route op het werkgebied van het onderwerp, zonder model.
  if (actie && onderwerp && onderwerp.soort !== "markering") {
    return { ...actieVerzoek(onderwerp, actie), werkgebied_id: onderwerp.werkgebied_id };
  }
  // Een werkgebiedsuggestie: dezelfde vaste handeling, op het werkgebied van het gesprek.
  if (actie && werkgebiedId) return { actie, werkgebied_id: werkgebiedId };
  // Een vraag bij een markering gaat als advies, een ander object als `onderwerp` (`lib/vraagLex.ts`). Een vraag over
  // een onderwerp draagt nooit een doel: die route annoteert niet.
  const basis = onderwerp ? verzoekVan(onderwerp) : undefined;
  const extra = doelen?.length && !onderwerp
    // Meerdere onderdelen van één artikel: één run, elk onderdeel een eigen laag.
    ? { ...basis, doelen }
    : doel && !onderwerp ? { ...basis, doel, ...(hergebruik ? { hergebruik } : {}) } : basis;
  return werkgebiedId ? { ...extra, werkgebied_id: werkgebiedId } : extra;
}

/** Een knop bij een voorstel van Lex beantwoordt dat voorstel; daarna staat er geen knop meer. */
export function bevestigt(v: BeurtVerzoek): boolean {
  return v.annoteren?.bevestigd !== undefined;
}

/** Wat het user-bericht draagt. De chip is UI-state en reist niet mee naar de api, dus de contextregel staat in de
 *  tekst; zonder die regel leest een herladen gesprek als een losse vraag zonder onderwerp. */
export function userVelden(v: BeurtVerzoek, prompt: string, contextLabel: string): Record<string, unknown> {
  return { tekst: contextLabel ? `Bij ${contextLabel}: ${prompt}` : prompt,
    // Een klik op een vraagkaartje: zo staat het antwoord na herladen weer in de Vragen-kaart.
    ...(v.intake ? { intake_antwoord: antwoordOp(v.intake) } : {}),
    ...(bevestigt(v) ? { bevestiging_antwoord: { keuze: "gestart" } } : {}) };
}
