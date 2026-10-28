// Het overzicht van de werkgebieden, in de lijn van de annotaties (`components/ui/OverzichtBalk`): een
// statusfilter met tellers, *Door mij bewerkt* (de api, `mijn`) en zoeken. De lijst is klein; filteren
// en zoeken gebeurt hier.
import type { WerkgebiedSamenvatting, WerkgebiedStatus } from "./types";

export type StatusFilter = "alle" | WerkgebiedStatus;
export const STATUS_FILTERS: StatusFilter[] = ["alle", "in_voorbereiding", "actief", "afgerond"];

/** De status uit de URL (`?status=actief`); wat niet klopt, is "alle". */
export function statusUitParam(p: string | null | undefined): StatusFilter {
  return (STATUS_FILTERS as string[]).includes(p ?? "") ? (p as StatusFilter) : "alle";
}

const normaal = (t: string) => t.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();

/** Elk woord moet ergens staan: naam, analysevraag, afbakening of context; zonder hoofdletters en
 *  diakrieten. */
export function zoek(lijst: WerkgebiedSamenvatting[], term: string): WerkgebiedSamenvatting[] {
  const woorden = normaal(term).split(/\s+/).filter(Boolean);
  if (!woorden.length) return lijst;
  return lijst.filter((w) => {
    const hooiberg = normaal([w.naam, w.analysevraag, w.afbakening, w.context ?? ""].join(" "));
    return woorden.every((x) => hooiberg.includes(x));
  });
}

/** De tellers bij de knoppen. */
export function perStatus(lijst: WerkgebiedSamenvatting[]): Record<StatusFilter, number> {
  const uit: Record<StatusFilter, number> = { alle: lijst.length, in_voorbereiding: 0, actief: 0, afgerond: 0 };
  for (const w of lijst) uit[w.status] += 1;
  return uit;
}

export const metStatus = (lijst: WerkgebiedSamenvatting[], s: StatusFilter) =>
  s === "alle" ? lijst : lijst.filter((w) => w.status === s);
