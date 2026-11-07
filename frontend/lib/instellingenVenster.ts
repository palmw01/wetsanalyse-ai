"use client";

import { INSTELLINGEN_PARAM, type TabKey } from "./instellingen";

/** Openen, van tab wisselen en sluiten van het instellingenvenster, met de History API.
 *
 *  Geen navigatie: Next houdt `useSearchParams` bij `pushState`/`replaceState` bij zonder iets bij de server te halen, dus
 *  de pagina eronder blijft precies staan. Openen zet een stap in de geschiedenis, zodat de terugknop het venster sluit;
 *  een tabwissel vervangt die stap, zodat terug niet langs elke tab loopt. */

const GEOPEND = "instellingenGeopend";

function urlMet(key: TabKey | null): string {
  const url = new URL(window.location.href);
  if (key) url.searchParams.set(INSTELLINGEN_PARAM, key);
  else url.searchParams.delete(INSTELLINGEN_PARAM);
  return url.pathname + url.search + url.hash;
}

/** Alleen onze eigen markering in de state. Kopieer je de state van Next mee (`{...history.state}`), dan houdt Next de
 *  stap voor een eigen navigatie en volgt `useSearchParams` hem niet: het venster bleef dan dicht. */
function stand(geopend: boolean) {
  return geopend ? { [GEOPEND]: true } : {};
}

function isGeopend(): boolean {
  return Boolean(window.history.state?.[GEOPEND]);
}

export function openInstellingen(key: TabKey) {
  window.history.pushState(stand(true), "", urlMet(key));
}

export function kiesInstellingenTab(key: TabKey) {
  window.history.replaceState(stand(isGeopend()), "", urlMet(key));
}

/** Sluiten: terug naar de stap van vóór het openen, als die er is. Kwam je binnen met de parameter al in de URL (een link
 *  of een doorverwijzing), dan valt alleen de parameter weg en blijf je op de pagina. */
export function sluitInstellingen() {
  if (isGeopend()) window.history.back();
  else window.history.replaceState(stand(false), "", urlMet(null));
}
