/** Tekst aan de randen inkorten zonder reguliere expressie.
 *
 *  `s.replace(/x+$/, "")` en verwanten zijn kwadratisch op een lange reeks die niet aan het eind staat: de motor begint
 *  op elke positie opnieuw (SonarQube S8786). Deze functies lopen één keer over de tekst en geven precies hetzelfde
 *  resultaat als de expressie die ze vervangen. */

type Teken = string | ((c: string) => boolean);

function past(teken: Teken): (c: string) => boolean {
  return typeof teken === "string" ? (c) => teken.includes(c) : teken;
}

/** Als `s.replace(/[tekens]+$/, "")`. */
export function zonderAchteraan(s: string, teken: Teken): string {
  const p = past(teken);
  let eind = s.length;
  while (eind > 0 && p(s[eind - 1])) eind--;
  return s.slice(0, eind);
}

/** Als `s.replace(/^[tekens]+|[tekens]+$/g, "")`. */
export function zonderRand(s: string, teken: Teken): string {
  const p = past(teken);
  let begin = 0;
  while (begin < s.length && p(s[begin])) begin++;
  return begin === s.length ? "" : zonderAchteraan(s.slice(begin), p);
}

const SPATIE = (c: string) => /\s/.test(c);

/** Als `s.replace(/\s+\S*$/, "")`: het laatste (halve) woord en de witruimte ervoor weg; zonder witruimte blijft alles staan. */
export function zonderLaatsteWoord(s: string): string {
  let i = s.length;
  while (i > 0 && !SPATIE(s[i - 1])) i--;
  if (i === 0) return s;
  return zonderAchteraan(s.slice(0, i), SPATIE);
}

/** De volgorde van `sort()` zonder argument: op UTF-16-codepunt, niet `localeCompare`. Sleutels, hashes en cachesleutels
 *  blijven zo gelijk aan wat ze waren, en de vergelijking staat er expliciet (SonarQube S2871). */
export function opCodepunt(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
