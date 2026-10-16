// Onderhoud van begrippen (spoor D, fase F1): herbeoordelen en dekking. Puur, voor vitest.
//
// De api rekent wat er veranderde (toen, nu, bronsignalen, opvolgers); hier staat alleen hoe de werkplek
// dat noemt en ordent. Een signaal heeft een richting en wordt nooit tot een score opgeteld.

import type { Dekking, DekkingStand, GeraakteKoppeling, Herbeoordelingen, Richting } from "./types";

/** Is dit een herbeoordelingsantwoord? Een ander antwoord (een oudere api, een storing) mag de tab
 *  niet breken: zonder herbeoordeling staan de begrippen er gewoon. */
export function isHerbeoordelingen(x: unknown): x is Herbeoordelingen {
  return !!x && typeof x === "object" && Array.isArray((x as Herbeoordelingen).begrippen);
}

export function isDekking(x: unknown): x is Dekking {
  const d = x as Dekking;
  return !!d && typeof d === "object" && Array.isArray(d.elementen) && !!d.totalen && typeof d.totalen === "object";
}

export const DEKKING_LABEL: Record<DekkingStand, string> = {
  te_verwerken: "te verwerken",
  voorstel: "voorstel",
  gekoppeld: "gekoppeld aan een geaccordeerd begrip",
  buiten_behandeling: "bewust buiten behandeling",
};

export const DEKKING_VOLGORDE: DekkingStand[] = ["te_verwerken", "voorstel", "gekoppeld", "buiten_behandeling"];

export const RICHTING_LABEL: Record<Richting, string> = { steun: "steun", tegen: "tegen", onbeslist: "onbeslist" };
export const RICHTING_TEKEN: Record<Richting, string> = { steun: "+", tegen: "−", onbeslist: "?" };

/** De geraakte koppelingen van één begrip, op koppeling-id. */
export function geraaktPerKoppeling(h: Herbeoordelingen | null, begripId: string): Map<string, GeraakteKoppeling> {
  const b = h?.begrippen.find((x) => x.begrip_id === begripId);
  return new Map((b?.koppelingen ?? []).map((k) => [k.koppeling_id, k]));
}

/** Per begrip het aantal geraakte passages – voor de lijst links. */
export function geraakteBegrippen(h: Herbeoordelingen | null): Map<string, number> {
  return new Map((h?.begrippen ?? []).map((b) => [b.begrip_id, b.koppelingen.length]));
}

export function herbeoordelingZin(n: number): string {
  return n === 1 ? "1 passage veranderde" : `${n} passages veranderden`;
}

/** De kop boven de strook: hoeveel begrippen, hoeveel passages. */
export function strookKop(h: Herbeoordelingen): string {
  const passages = h.begrippen.reduce((n, b) => n + b.koppelingen.length, 0);
  const begrippen = h.begrippen.length === 1 ? "1 begrip" : `${h.begrippen.length} begrippen`;
  return `${begrippen} herbeoordelen · ${herbeoordelingZin(passages)}`;
}

/** Wat de analist kan, als knoptekst. Volgorde zoals de api ze geeft. */
export const ACTIE_LABEL: Record<GeraakteKoppeling["acties"][number], string> = {
  herkoppelen: "Herkoppelen",
  bevestigen: "Begrip klopt nog",
  loskoppelen: "Losmaken",
};

/** Een fragment in de huidige tekst aanwijzen: [ervoor, fragment, erna] als het fragment er (nog)
 *  in staat, anders null. Voor de weergave van *nu* naast *toen*. */
export function markeer(tekst: string, fragment: string): [string, string, string] | null {
  if (!fragment) return null;
  const i = tekst.indexOf(fragment);
  return i < 0 ? null : [tekst.slice(0, i), fragment, tekst.slice(i + fragment.length)];
}
