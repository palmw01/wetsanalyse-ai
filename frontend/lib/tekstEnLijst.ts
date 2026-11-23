/** Twee kolommen op de breedte van het blok (melding gebruiker 23 nov 2026): tekst en lijst (`components/ui/TekstEnLijst.tsx`)
 *  en een object met een zijkolom (`SplitDetail` in `components/ui/Pagina.tsx`), de CSS in `app/globals.css`. Voor tekst en
 *  lijst: wanneer ze naast elkaar staan, en
 *  hoe de verdeling te verslepen is. Puur, getest in `tekstEnLijst.test.ts`; die toetst ook dat de CSS dezelfde waarden
 *  gebruikt, want de CSS kan geen constante lezen. */

/** Vanaf deze breedte van het blok zelf (niet van het scherm) twee kolommen: een vergroot paneel en de pagina wel, een
 *  paneel naast het gesprek niet (hoogstens 60% van de werkplek), tenzij je het breed sleept. */
export const TEKST_EN_LIJST_BREED = "56rem";

/** Vanaf deze breedte van het blok staat een object in twee kolommen (`SplitDetail`: inhoud plus een zijkolom van 20rem).
 *  Lager dan `TEKST_EN_LIJST_BREED`: de zijkolom is smal en vast, de inhoud houdt dan nog 24rem. */
export const SPLIT_DETAIL_BREED = "44rem";

/** Smal staat de tekst bovenin, hoogstens zo hoog; de lijst krijgt de rest. */
export const TEKST_MAX_SMAL = "45%";

/** Het deel van de breedte voor de tekst (procent), standaard: de wettekst leest het meest, de kaartjes passen in de rest. */
export const AANDEEL_STANDAARD = 57;
/** Verslepen kan tussen deze grenzen: smaller wordt de tekst of de lijst onleesbaar. */
export const AANDEEL_MIN = 35;
export const AANDEEL_MAX = 75;
/** Eén pijltjesstap op de scheiding. */
export const AANDEEL_STAP = 2;

/** Per browser bewaard (`lib/opslag.ts`): één verdeling voor elke plek, want het is een leesvoorkeur. */
export const OPSLAG_AANDEEL = "lex.tekstEnLijst.aandeel";

export function begrensAandeel(aandeel: number): number {
  return Math.round(Math.min(AANDEEL_MAX, Math.max(AANDEEL_MIN, aandeel)));
}

/** Het aandeel van de tekst als de scheiding op `x` staat, in een blok van `links` tot `links + breedte`. */
export function aandeelUitPositie(x: number, links: number, breedte: number): number {
  if (breedte <= 0) return AANDEEL_STANDAARD;
  return begrensAandeel(((x - links) / breedte) * 100);
}

/** Het aandeel na een toets op de scheiding; `null` = geen toets voor de scheiding. De tekst staat links: → maakt hem breder. */
export function aandeelNaToets(huidig: number, toets: string): number | null {
  if (toets === "ArrowRight") return begrensAandeel(huidig + AANDEEL_STAP);
  if (toets === "ArrowLeft") return begrensAandeel(huidig - AANDEEL_STAP);
  if (toets === "Home") return AANDEEL_MIN;
  if (toets === "End") return AANDEEL_MAX;
  return null;
}

/** Een bewaard aandeel, of `undefined` als het geen geldig getal binnen de grenzen is. */
export function leesAandeel(ruw: unknown): number | undefined {
  return typeof ruw === "number" && Number.isFinite(ruw) && ruw >= AANDEEL_MIN && ruw <= AANDEEL_MAX ? ruw : undefined;
}
