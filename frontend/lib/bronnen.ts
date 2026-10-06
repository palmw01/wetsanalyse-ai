// De bronnen onder een antwoord: ontdubbeld per bronnode en gegroepeerd per regeling.
//
// graph-qa levert sinds de canonieke bronnen (`bronmodel.vindplaats`) al één bron per bepaling, met
// `bron_iri` en `regeling`. Oudere, bewaarde berichten dragen alleen `label` + `uri`, waarin dezelfde
// bepaling als graaf-IRI én als jci kan staan. Daarom normaliseert de werkplek zelf ook, met dezelfde
// regels (`vindplaatsVan`, de spiegel van bronmodel): één weergave voor oud en nieuw.

import type { NodeDoel } from "./annotatieNode";
import { koppelBron, vindVermeldingen } from "./citaties";
import { bronHref } from "./url";
import { bronDoel, iriSegment, vindplaatsVan } from "./samenhang";
import type { Bron } from "./types";

export interface BronItem {
  sleutel: string;
  label: string;
  soort: string;
  href?: string;
}

export interface BronGroep {
  bwb_id: string;
  naam: string;
  /** De link van de regeling zelf, als die als bron voorkwam. */
  href?: string;
  items: BronItem[];
}

export interface Bronnenlijst {
  groepen: BronGroep[];
  /** Verwijzingen zonder herkenbare bronnode, ongewijzigd. */
  overig: BronItem[];
  aantal: number;
}

const STRUCTUUR = ["hoofdstuk", "titeldeel", "afdeling", "paragraaf"];
const nummers = new Intl.Collator("nl", { numeric: true, sensitivity: "base" });

/** "VIIa" → [7, "a"]; geen Romeins getal → [Infinity, waarde]. Hoofdstukken heten I, II … X, VIIa, VIIbis. */
function romeins(waarde: string): [number, string] {
  const m = waarde.match(/^([IVXLC]+)(.*)$/);
  if (!m) return [Infinity, waarde];
  const w: Record<string, number> = { I: 1, V: 5, X: 10, L: 50, C: 100 };
  let som = 0;
  for (let i = 0; i < m[1].length; i++) {
    const nu = w[m[1][i]], volgende = w[m[1][i + 1]] ?? 0;
    som += nu < volgende ? -nu : nu;
  }
  return [som, m[2]];
}

function vergelijkPad(a: [string, string][], b: [string, string][]): number {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (!a[i] || !b[i]) return a.length - b.length;
    const [ka, va] = a[i], [kb, vb] = b[i];
    if (ka !== kb) return rang(ka) - rang(kb);
    if (va === vb) continue;
    if (ka === "hoofdstuk") {
      const [na, ra] = romeins(va), [nb, rb] = romeins(vb);
      if (na !== nb) return na - nb;
      return nummers.compare(ra, rb);
    }
    return nummers.compare(va, vb);
  }
  return 0;
}

/** Structuur vóór artikelen, binnen de structuur in de volgorde van de boom. */
function rang(sleutel: string): number {
  const i = STRUCTUUR.indexOf(sleutel);
  return i >= 0 ? i : STRUCTUUR.length;
}

export function normaliseerBronnen(bronnen: readonly Bron[]): Bronnenlijst {
  const groepen = new Map<string, BronGroep & { paden: Map<string, [string, string][]> }>();
  const overig: BronItem[] = [];
  const gezien = new Set<string>();
  for (const b of bronnen) {
    const vp = vindplaatsVan(b.bron_iri || b.uri) ?? vindplaatsVan(b.uri);
    const href = bronHref(b.jci || b.uri) ?? bronHref(b.uri);
    if (!vp) {
      if (gezien.has(b.uri)) continue;
      gezien.add(b.uri);
      overig.push({ sleutel: b.uri, label: b.label || b.uri, soort: "", href });
      continue;
    }
    let groep = groepen.get(vp.bwb_id);
    if (!groep) {
      groep = { bwb_id: vp.bwb_id, naam: vp.bwb_id, items: [], paden: new Map() };
      groepen.set(vp.bwb_id, groep);
    }
    if (b.regeling && groep.naam === vp.bwb_id) groep.naam = b.regeling;
    if (gezien.has(vp.bron_iri)) {
      // Dezelfde bepaling als IRI én als jci (een ouder bericht): de jci geeft de preciezere link.
      const item = groep.items.find((i) => i.sleutel === vp.bron_iri);
      if (item && b.jci && href) item.href = href;
      continue;
    }
    gezien.add(vp.bron_iri);
    if (vp.soort === "regeling") {
      groep.href ??= href;
      continue;
    }
    groep.items.push({ sleutel: vp.bron_iri, label: vp.label || b.label || vp.bron_iri, soort: vp.soort, href });
    groep.paden.set(vp.bron_iri, vp.pad);
  }
  const uit: BronGroep[] = [];
  for (const { paden, ...groep } of groepen.values()) {
    groep.items.sort((a, b) => vergelijkPad(paden.get(a.sleutel) ?? [], paden.get(b.sleutel) ?? []));
    uit.push(groep);
  }
  return { groepen: uit, overig, aantal: gezien.size };
}

/** Hoeveel artikelen de 3D-graaf hoogstens tegelijk opent vanuit één antwoord. Meer wordt een
 *  kaart van eilandjes, en elk artikel is een eigen request. */
export const MAX_SAMENHANG_DOELEN = 8;

/** De artikelen die het antwoord zelf noemt, in de volgorde van de tekst, als doelen voor de
 *  3D-graaf. Alleen een éénduidige koppeling telt (`koppelBron`, dezelfde regel als de
 *  citatie-chips). Eén doel per artikel, maar wel zo precies als de eerste vermelding: een genoemd lid
 *  opent zijn artikel met dát lid gekozen. Noemt de tekst niets te koppelen, dan de eerste bepaling
 *  uit de bronnen – het oude gedrag. */
export function samenhangDoelen(tekst: string, bronnen: readonly Bron[], max = MAX_SAMENHANG_DOELEN): { doelen: NodeDoel[]; totaal: number } {
  const gezien = new Map<string, NodeDoel>();
  const voegToe = (b: Bron) => {
    const doel = bronDoel(b.bron_iri || b.uri);
    if (!doel?.artikel) return;
    const artikel = `urn:bwb:${doel.bwb_id}:artikel:${iriSegment(doel.artikel)}`;
    if (gezien.has(artikel)) return;
    gezien.set(artikel, { ...doel, ...(b.regeling ? { citeertitel: b.regeling } : {}) });
  };
  for (const v of vindVermeldingen(tekst)) {
    const i = koppelBron(v, bronnen);
    if (i >= 0) voegToe(bronnen[i]);
  }
  if (!gezien.size) {
    const eerste = bronnen.find((b) => bronDoel(b.bron_iri || b.uri)?.artikel);
    if (eerste) voegToe(eerste);
  }
  const alle = [...gezien.values()];
  return { doelen: alle.slice(0, max), totaal: alle.length };
}

/** De tekst op de knop: wat hij opent, niet alleen dát hij iets opent. */
export function samenhangKnopTekst({ doelen, totaal }: { doelen: NodeDoel[]; totaal: number }): string {
  if (doelen.length === 1) {
    const d = doelen[0];
    return `Bekijk samenhang van ${d.label ?? "de bepaling"}${d.citeertitel ? ` ${d.citeertitel}` : ""}`;
  }
  return `Bekijk samenhang van de ${totaal} genoemde artikelen${totaal > doelen.length ? ` (${doelen.length} getoond)` : ""}`;
}
