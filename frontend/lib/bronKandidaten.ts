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
  deelvraag: "overzicht per deelvraag",
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
  if (vp?.label) return vp.label;
  const rest = iri.replace(/^urn:bwb:BWB[A-Z]\d+:?/, "");
  // Een wet-lokale divisie (`id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1`): het laatste
  // stuk van het pad, gedecodeerd ("divisie 9.1"), in plaats van de hele IRI die de rij uit beeld duwt.
  const id = rest.match(/^id:(.+)$/);
  if (id) {
    let pad = id[1];
    try { pad = decodeURIComponent(pad); } catch { /* laat staan */ }
    const laatste = pad.split("/").pop() ?? pad;
    const divisie = laatste.match(/divisie([\d.]+[a-z]?)$/i);
    return divisie ? `divisie ${divisie[1]}` : laatste;
  }
  return rest || iri;
}

/** Het bewijs van één methode in gewone woorden. `labels`: bron-IRI → naam (de selecties). */
export function bewijsZin(b: KandidaatBewijs, labels: Map<string, string> = new Map()): string {
  const vanuit = plekNaam(b.vanuit, labels);
  const d = b.detail ?? {};
  switch (b.methode) {
    case "overzicht":
      return d.onderwerp ? `in het overzicht op “${d.onderwerp}”` : "in het overzicht op de analysevraag";
    case "deelvraag":
      return d.vraag ? `gevonden bij de deelvraag “${d.vraag}”` : "gevonden bij een deelvraag";
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

/** Vond Lex deze kandidaat bij die deelvraag? (Het bewijs van de methode `deelvraag` noemt haar.) */
export function bijDeelvraag(k: Pick<BronKandidaat, "bewijs">, deelvraagId: string): boolean {
  return k.bewijs.some((b) => b.detail?.deelvraag_id === deelvraagId);
}

/** Het bewijs van een kandidaat in één regel (spoor H): per methode één stuk, herhalingen geteld –
 *  "8× verwezen vanuit de kern · definieert “rijksbelastingen”". Het volledige bewijs (`bewijsZin` per
 *  regel) staat uitklapbaar; hier gaat het om in één oogopslag waarom Lex de bepaling noemt. */
export function bewijsSamenvatting(bewijs: readonly KandidaatBewijs[], labels: Map<string, string> = new Map()): string {
  const per = new Map<BronMethode, KandidaatBewijs[]>();
  for (const b of bewijs) per.set(b.methode, [...(per.get(b.methode) ?? []), b]);
  const stukken: string[] = [];
  for (const [m, lijst] of per) {
    if (lijst.length === 1) { stukken.push(bewijsZin(lijst[0], labels)); continue; }
    const n = lijst.length;
    switch (m) {
      case "verwijzing_uit": stukken.push(`${n}× verwezen vanuit de kern`); break;
      case "verwijzing_in": stukken.push(`verwijst ${n}× naar de kern`); break;
      case "definitie": stukken.push(`definieert ${[...new Set(lijst.map((b) => `“${b.detail?.begrip ?? "?"}”`))].join(", ")}`); break;
      case "deelvraag": stukken.push(`gevonden bij ${new Set(lijst.map((b) => b.detail?.deelvraag_id)).size} deelvragen`); break;
      case "opbouw": stukken.push(`staat in hetzelfde deel als ${n} bepalingen van de kern`); break;
      default: stukken.push(`${METHODE_LABEL[m]} (${n}×)`);
    }
  }
  return stukken.join(" · ");
}

/** Vrije tekst met ruwe bron-IRI's leesbaar (spoor H): elke `urn:bwb:…` wordt haar plek ("divisie 26.3.9",
 *  "Artikel 9, lid 1"). Voor oudere afbakeningen waar de intake de IRI van een divisie in schreef; de tekst
 *  zelf blijft zoals hij is opgeslagen. */
export function metLeesbareBronnen(tekst: string): string {
  return tekst.replace(/urn:bwb:BWB[A-Z]\d+(?::[^\s,;)]+)?/g, (gevonden) => {
    // Een punt aan het eind hoort bij de zin, niet bij de IRI.
    const [, iri, punt] = gevonden.match(/^(.*?)(\.*)$/)!;
    return (plekNaam(iri) || iri) + punt;
  });
}
