"use client";

import { useSyncExternalStore } from "react";

/** Vanaf welke breedte het artefact naast de chat past in plaats van eroverheen.
 *
 *  Een half venster op een 1920-scherm is 960px: ook daar moet je het artefact en het gesprek tegelijk
 *  zien. Onder deze grens blijft er te weinig over voor twee leesbare kolommen en is de sheet beter.
 *  De kolom neemt een aandeel van de ruimte naast de sidebar, dus die telt vanzelf mee (zie `WerkplekClient`).
 *
 *  Geëxporteerd omdat de rondleiding op deze grens moet reageren: het artefact wisselt hier van
 *  `Dialog`-variant en wordt daarmee een nieuwe DOM-boom, dus de aangewezen elementen zijn andere
 *  knopen dan een tel eerder. Eén plek voor het getal – twee bestanden die het los opschrijven lopen
 *  vroeg of laat uit elkaar. */
export const BREED = "(min-width: 800px)";

function abonneer(opWijziging: () => void): () => void {
  const mq = window.matchMedia(BREED);
  mq.addEventListener("change", opWijziging);
  return () => mq.removeEventListener("change", opWijziging);
}

/** Is het scherm breed genoeg voor de kolom-indeling?
 *
 *  Via `useSyncExternalStore` en niet via `useState` + effect: `matchMedia` ís externe state, en zo
 *  leest React de waarde tijdens het renderen in plaats van er één frame achteraan te lopen. Op de
 *  server bestaat `matchMedia` niet – daar is het antwoord `false`. Dat is hier onschuldig: het
 *  artefact opent pas na een interactie, dus de eerste render toont het toch niet.
 */
export function useBreedScherm(): boolean {
  return useSyncExternalStore(
    abonneer,
    () => window.matchMedia(BREED).matches,
    () => false,
  );
}
