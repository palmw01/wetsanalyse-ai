/** Zou een klik op deze link de pagina verlaten? Alleen dan staan niet-bewaarde wijzigingen op het
 *  spel bij een client-side navigatie. Niet bij: een andere origin (een volledige paginawissel, die
 *  `beforeunload` al vangt), dezelfde pagina (alleen een anker) en `/instellingen/*` – dat opent als
 *  dialoog óver de pagina (intercepting route), de kaart blijft staan. */
export function verlaatPagina(href: string, huidig: { origin: string; pathname: string; search: string }): boolean {
  let url: URL;
  try {
    url = new URL(href, huidig.origin + huidig.pathname + huidig.search);
  } catch {
    return false;
  }
  if (url.origin !== huidig.origin) return false;
  if (url.pathname === huidig.pathname && url.search === huidig.search) return false;
  return !url.pathname.startsWith("/instellingen");
}
