/** De rekenkern van het zijpaneel naast het gesprek (het bronvenster, PR 3a): hoe breed het mag zijn, en wat de
 *  pijltjestoetsen op de scheiding doen. Puur, getest in `zijpaneel.test.ts`. */

/** Smaller wordt een wettekst onleesbaar. */
export const MIN_BREEDTE = 320;
/** Het paneel neemt hoogstens dit deel van de werkplek. */
export const MAX_FRACTIE = 0.6;
/** Het gesprek ernaast houdt minstens zoveel ruimte (`test-contextpaneel` toetst 300 px). */
export const CHAT_MIN = 300;
/** Eén pijltjesstap op de scheiding. */
export const STAP = 16;

export const OPSLAG_BREEDTE = "lex.paneel.breedte";
export const OPSLAG_INGEKLAPT = "lex.paneel.ingeklapt";

/** De grenzen voor een werkplek van `container` px breed. Op een smalle werkplek wint de ondergrens van het gesprek. */
export function grenzen(container: number): { min: number; max: number } {
  const max = Math.max(MIN_BREEDTE, Math.min(Math.floor(container * MAX_FRACTIE), container - CHAT_MIN));
  return { min: Math.min(MIN_BREEDTE, max), max };
}

/** Een gewenste breedte binnen de grenzen, afgerond op hele pixels. */
export function begrens(gewenst: number, container: number): number {
  const { min, max } = grenzen(container);
  return Math.round(Math.min(max, Math.max(min, gewenst)));
}

/** De breedte na een toets op de scheiding. Het paneel staat rechts: ← maakt het breder, → smaller. `null` = geen
 *  toets voor de scheiding (dan doet hij niets en gaat de toets door). */
export function naToets(huidig: number, toets: string, container: number): number | null {
  const { min, max } = grenzen(container);
  if (toets === "ArrowLeft") return begrens(huidig + STAP, container);
  if (toets === "ArrowRight") return begrens(huidig - STAP, container);
  if (toets === "Home") return min;
  if (toets === "End") return max;
  return null;
}

/** Een bewaarde breedte, alleen als het een getal is dat ergens op slaat. */
export function leesBreedte(ruw: unknown): number | undefined {
  return typeof ruw === "number" && Number.isFinite(ruw) && ruw >= MIN_BREEDTE && ruw < 10000 ? Math.round(ruw) : undefined;
}
