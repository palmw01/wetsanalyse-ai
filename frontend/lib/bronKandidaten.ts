// Rekenkern van "Bronnen vinden met Lex" (spoor D, fase A): de woorden waarmee de werkplek een
// kandidaat en zijn bewijs noemt, de filters en de standaardrol bij opnemen. Puur, voor vitest.

import { vindplaatsVan } from "./samenhang";
import type { BronKandidaat, BronMethode, BronRol, KandidaatBewijs, KandidaatRol, KandidaatStatus } from "./types";

export const KANDIDAAT_ROL_LABEL: Record<KandidaatRol, string> = {
  kern: "kern",
  afhankelijkheid: "afhankelijkheid",
  aanverwant: "aanverwant",
};

/** Wat een rol betekent – staat als toelichting bij de badge. */
export const KANDIDAAT_ROL_UITLEG: Record<KandidaatRol, string> = {
  kern: "regelt het onderwerp zelf",
  afhankelijkheid: "nodig om de kern te begrijpen of toe te passen",
  aanverwant: "mogelijk relevant, noodzaak niet aangetoond",
};

export const METHODE_LABEL: Record<BronMethode, string> = {
  overzicht: "overzicht op de analysevraag",
  verwijzing_uit: "verwijzingen vanuit de kern",
  verwijzing_in: "verwijzingen naar de kern",
  definitie: "definities van termen",
  opbouw: "opbouw van de wet",
  gelijkenis: "tekstuele gelijkenis",
};

export const FUNCTIE_LABEL: Record<string, string> = {
  definitie: "definitie",
  uitzondering: "uitzondering",
  delegatie: "delegatie",
  toepassing: "toepassing",
  onbekend: "functie onbekend",
};

export type KandidaatFilter = "open" | "later" | "uitgesloten" | "opgenomen";

export const FILTER_LABEL: Record<KandidaatFilter, string> = {
  open: "Open", later: "Later", uitgesloten: "Uitgesloten", opgenomen: "Opgenomen",
};

/** In welk filter een kandidaat valt. Intussen met de hand opgenomen telt als opgenomen: dat is geen
 *  open voorstel meer, ook al staat zijn status nog op voorgesteld. */
export function filterVan(k: Pick<BronKandidaat, "status" | "in_selectie">): KandidaatFilter {
  if (k.status === "opgenomen" || k.in_selectie) return "opgenomen";
  return k.status === "voorgesteld" ? "open" : (k.status satisfies Exclude<KandidaatStatus, "voorgesteld" | "opgenomen">);
}

export function telPerFilter(lijst: BronKandidaat[]): Record<KandidaatFilter, number> {
  const uit: Record<KandidaatFilter, number> = { open: 0, later: 0, uitgesloten: 0, opgenomen: 0 };
  for (const k of lijst) uit[filterVan(k)] += 1;
  return uit;
}

/** De rol bij opnemen: analyseren bij een kernbepaling, anders context – dezelfde regel als de api. */
export function standaardRol(k: Pick<BronKandidaat, "rol">): BronRol {
  return k.rol === "kern" ? "analyseren" : "context";
}

/** Een bron-IRI als vindplaats ("Artikel 9, lid 1"); onbekend → wat er na de regeling staat. */
export function plekNaam(iri: string, labels: Map<string, string> = new Map()): string {
  if (!iri) return "";
  if (labels.has(iri)) return labels.get(iri)!;
  const vp = vindplaatsVan(iri);
  return vp?.label || iri.replace(/^urn:bwb:BWB[A-Z]\d+:?/, "") || iri;
}

/** Het bewijs van één methode in gewone woorden. `labels`: bron-IRI → naam (de selecties). */
export function bewijsZin(b: KandidaatBewijs, labels: Map<string, string> = new Map()): string {
  const vanuit = plekNaam(b.vanuit, labels);
  const d = b.detail ?? {};
  switch (b.methode) {
    case "overzicht":
      return d.onderwerp ? `in het overzicht op “${d.onderwerp}”` : "in het overzicht op de analysevraag";
    case "verwijzing_uit":
      return `verwezen vanuit ${vanuit || "de kern"}${d.anker ? ` (“${d.anker}”)` : ""} – ${FUNCTIE_LABEL[d.functie ?? "onbekend"] ?? d.functie}`;
    case "verwijzing_in":
      return `verwijst naar ${vanuit || "de kern"}${d.anker ? ` (“${d.anker}”)` : ""}`;
    case "definitie":
      return `definieert “${d.begrip ?? "?"}”${vanuit ? `, dat in ${vanuit} staat` : ""}`;
    case "opbouw":
      return `staat in hetzelfde deel als ${vanuit || "de kern"}`;
    case "gelijkenis":
      return `lijkt qua tekst op ${vanuit || "de kern"} (zwak signaal)`;
    default:
      return b.methode;
  }
}

/** Open voorstellen eerst, dan sterkste rol, dan meeste bewijs – zoals de api ze geeft, maar stabiel
 *  na een besluit. */
const ROL_VOLGORDE: Record<KandidaatRol, number> = { kern: 0, afhankelijkheid: 1, aanverwant: 2 };
export function sorteerKandidaten(lijst: BronKandidaat[]): BronKandidaat[] {
  return [...lijst].sort((a, b) => ROL_VOLGORDE[a.rol] - ROL_VOLGORDE[b.rol] || b.bewijs.length - a.bewijs.length
    || a.label.localeCompare(b.label, "nl", { numeric: true }) || a.bron_iri.localeCompare(b.bron_iri));
}

/** "Lex · Verwijzingen vanuit de kern: 3 (12 ms)" → "Verwijzingen vanuit de kern: 3 (12 ms)". */
export function voortgangsregel(bericht: string): string {
  return bericht.replace(/^Lex · /, "");
}
