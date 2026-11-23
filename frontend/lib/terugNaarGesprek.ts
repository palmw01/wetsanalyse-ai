/** De weg terug van een volle pagina naar het gesprek waaruit je hem opende (melding gebruiker 23 nov 2026: na de pagina
 *  vanuit het zijpaneel was het paneel weg en kon je niet meer terug naar gesprek plus paneel).
 *
 *  Eén patroon voor elk paneel: `PaneelKop` zet het gesprek als `?vanuit=` op *Openen als pagina* (in ⋯), en de strook
 *  `TerugNaarGesprek` (in de root-layout, net als `?instellingen=`) toont op elke pagina *Terug naar het gesprek*. Het
 *  gesprek opent dan met zijn tabs: die bewaart de werkplek per gesprek (`lex.paneel.tabs.<gesprek>`), met de tab
 *  die actief was. Omdat het in de url staat, overleeft het herladen, en de terugknop van de browser werkt gewoon. */

export const VANUIT_PARAM = "vanuit";

/** Een gesprek-id zoals de api ze maakt (hex), zonder iets wat in een url of pad iets anders zou betekenen. */
const GESPREK_ID = /^[A-Za-z0-9_-]{1,64}$/;

/** De link naar een volle pagina, met het gesprek erbij als dat er is. De rest van de link blijft letterlijk staan
 *  (geen herschrijving van de query); het id is gecontroleerd, dus het hoeft niet gecodeerd. */
export function metVanuit(href: string, gesprekId: string | null | undefined): string {
  if (!gesprekId || !GESPREK_ID.test(gesprekId)) return href;
  const i = href.indexOf("#");
  const [pad, hash] = i === -1 ? [zonderVanuit(href), ""] : [zonderVanuit(href.slice(0, i)), href.slice(i)];
  return `${pad}${pad.includes("?") ? "&" : "?"}${VANUIT_PARAM}=${gesprekId}${hash}`;
}

/** Een link zonder `vanuit` (het omgekeerde van `metVanuit`, voor een link die het al had). */
export function zonderVanuit(href: string): string {
  return href.replace(new RegExp(`([?&])${VANUIT_PARAM}=[^&#]*&?`), "$1").replace(/[?&](#|$)/, "$1");
}

/** Het gesprek waar de pagina vandaan kwam, of `null`: alleen een geldig id, en nooit op de werkplek zelf. */
export function vanuitGesprek(pathname: string | null, params: { get(naam: string): string | null } | null): string | null {
  if (!pathname || pathname.startsWith("/workbench")) return null;
  const id = params?.get(VANUIT_PARAM) ?? "";
  return GESPREK_ID.test(id) ? id : null;
}

/** Terug in de werkplek, op dat gesprek. */
export function gesprekHref(gesprekId: string): string {
  return `/workbench?gesprek=${encodeURIComponent(gesprekId)}`;
}
