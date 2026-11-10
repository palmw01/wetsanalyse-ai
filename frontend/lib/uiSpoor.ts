// Het spoor van een handeling in de UI: is de klik aangekomen, wat kwam eruit, en hoe lang duurde
// het. Geen analytics — een diagnosemiddel voor precies één klacht: "ik klik en er gebeurt niets".
//
// Zonder dit is die klacht niet te onderzoeken. De BFF logt wél elke upstream-call
// (`app/api/_lib/proxy.ts`), maar juist het geval dat we zoeken laat daar niets achter: een klik die
// nooit een request werd, of een request die nog liep toen de gebruiker het opgaf. Daarom meldt de
// client zélf dat hij begon, en later wat de uitkomst was.
//
// Wat er NIET in mag: inhoud, titels, id's, vrije tekst. Alleen een actienaam uit de lijst hieronder,
// een uitkomst, een duur en een http-status. De route weigert al het andere (`app/api/ui-spoor`),
// zodat de logregel niet kan uitgroeien tot een gegevensstroom die niemand heeft afgesproken.

/** De handelingen die een spoor achterlaten. Bewust een gesloten lijst: een vrije naam zou hier
 *  ongemerkt gebruikersinhoud binnenlaten (een gesprekstitel in een actienaam is zo gebeurd). */
export const UI_ACTIES = [
  "gesprek_verwijderen",
  "gesprek_hernoemen",
  "gesprek_archiveren",
  "gesprek_verplaatsen",
  "gesprekken_verwijderen",
  "gesprekken_archiveren",
  "annotatie_verwijderen",
  "werkgebied_verwijderen",
  "begrip_verwijderen",
  "review_beslissing",
] as const;
export type UiActie = (typeof UI_ACTIES)[number];

/** `gestart` gaat weg bij de klik, de rest als het antwoord er is. Het ontbreken van een tweede
 *  regel na een `gestart` is zelf het signaal: dan is de handeling blijven hangen. */
export const UI_UITKOMSTEN = ["gestart", "gelukt", "mislukt", "afgebroken"] as const;
export type UiUitkomst = (typeof UI_UITKOMSTEN)[number];

export interface UiSpoor {
  actie: UiActie;
  uitkomst: UiUitkomst;
  /** Hoe lang de handeling duurde. Ontbreekt bij `gestart`. */
  duur_ms?: number;
  /** De http-status van de mislukte call, als die er was. */
  status?: number;
}

/** Bovengrens op de duur die we accepteren (24 uur). Een tabblad dat een week open stond en dan pas
 *  zijn beacon kwijt kan, hoort de statistiek niet te vervuilen. */
const MAX_DUUR_MS = 86_400_000;

/** Lees een binnengekomen melding en geef hem terug in de vorm die gelogd mag worden, of `null`.
 *
 *  Staat hier en niet in de route omdat dit de enige logica is die te testen valt: vitest draait
 *  node-env zonder DOM, dus `sendBeacon` niet — de validatie wél. */
export function leesSpoor(ruw: unknown): UiSpoor | null {
  if (typeof ruw !== "object" || ruw === null) return null;
  const o = ruw as Record<string, unknown>;
  const actie = o.actie;
  const uitkomst = o.uitkomst;
  if (!UI_ACTIES.includes(actie as UiActie)) return null;
  if (!UI_UITKOMSTEN.includes(uitkomst as UiUitkomst)) return null;

  const spoor: UiSpoor = { actie: actie as UiActie, uitkomst: uitkomst as UiUitkomst };
  if (typeof o.duur_ms === "number" && Number.isFinite(o.duur_ms) && o.duur_ms >= 0) {
    spoor.duur_ms = Math.min(Math.round(o.duur_ms), MAX_DUUR_MS);
  }
  if (typeof o.status === "number" && Number.isInteger(o.status) && o.status >= 100 && o.status <= 599) {
    spoor.status = o.status;
  }
  return spoor;
}

/** Stuur één melding weg. Faalt stil en houdt niets tegen: dit is een waarneming, geen handeling.
 *
 *  `sendBeacon` en niet `fetch`: de melding moet ook aankomen als de gebruiker het tabblad sluit
 *  omdat er "niets gebeurt" — precies het geval dat we willen zien. Valt hij weg (te groot, geen
 *  ondersteuning), dan proberen we het niet nog eens. */
export function meldSpoor(spoor: UiSpoor): void {
  if (typeof navigator === "undefined" || typeof navigator.sendBeacon !== "function") return;
  try {
    navigator.sendBeacon("/api/ui-spoor", new Blob([JSON.stringify(spoor)], { type: "application/json" }));
  } catch {
    /* een waarneming mag nooit de handeling breken */
  }
}

/** Waar een browserfout vandaan kwam. Een gesloten lijst, net als de actienamen. */
export const FOUT_PLEKKEN = ["route", "globaal", "script", "belofte"] as const;
export type FoutPlek = (typeof FOUT_PLEKKEN)[number];

/** Een crash in de browser, voor de logs. Bewust geen melding en geen stack: daar kan tekst van de
 *  gebruiker in staan. De naam van de fout en de `digest` van Next zijn genoeg om hem terug te vinden. */
export interface Browserfout {
  plek: FoutPlek;
  naam?: string;
  digest?: string;
}

const FOUT_NAAM = /^[A-Za-z]{1,40}$/;
const FOUT_DIGEST = /^[A-Za-z0-9-]{1,40}$/;

/** Lees een binnengekomen browserfout en geef hem terug in de vorm die gelogd mag worden, of `null`. */
export function leesBrowserfout(ruw: unknown): Browserfout | null {
  if (typeof ruw !== "object" || ruw === null) return null;
  const o = ruw as Record<string, unknown>;
  if (!FOUT_PLEKKEN.includes(o.plek as FoutPlek)) return null;
  const fout: Browserfout = { plek: o.plek as FoutPlek };
  if (typeof o.naam === "string" && FOUT_NAAM.test(o.naam)) fout.naam = o.naam;
  if (typeof o.digest === "string" && FOUT_DIGEST.test(o.digest)) fout.digest = o.digest;
  return fout;
}

/** Een afgebroken verzoek is geen crash: elke wissel van gesprek breekt er een af. */
export function isRuisfout(fout: unknown): boolean {
  return (fout as { name?: unknown } | null)?.name === "AbortError";
}

/** Meld een browserfout. Faalt stil, net als `meldSpoor`. */
export function meldBrowserfout(plek: FoutPlek, fout?: unknown): void {
  if (isRuisfout(fout) || typeof navigator === "undefined" || typeof navigator.sendBeacon !== "function") return;
  const { name, digest } = (fout ?? {}) as { name?: unknown; digest?: unknown };
  try {
    navigator.sendBeacon("/api/ui-spoor", new Blob([JSON.stringify({ soort: "fout", plek, naam: name, digest })],
      { type: "application/json" }));
  } catch {
    /* een waarneming mag nooit iets breken */
  }
}

/** Voer een handeling uit met een spoor eromheen: `gestart` vooraf, de uitkomst achteraf.
 *
 *  De fout gaat gewoon door naar de aanroeper — dit meet, het vangt niet af. */
export async function metSpoor<T>(actie: UiActie, handeling: () => Promise<T>): Promise<T> {
  const begin = Date.now();
  meldSpoor({ actie, uitkomst: "gestart" });
  try {
    const uitkomst = await handeling();
    meldSpoor({ actie, uitkomst: "gelukt", duur_ms: Date.now() - begin });
    return uitkomst;
  } catch (err) {
    const status = (err as { status?: unknown })?.status;
    meldSpoor({
      actie,
      uitkomst: "mislukt",
      duur_ms: Date.now() - begin,
      status: typeof status === "number" ? status : undefined,
    });
    throw err;
  }
}
