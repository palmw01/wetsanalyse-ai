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
    // graph-qa geeft een structuurdeel zijn titel mee ("Hoofdstuk II – Invordering in eerste aanleg");
    // die wint van het kale vindplaatslabel, dat er het begin van is.
    const label = vp.label && b.label?.startsWith(`${vp.label} – `) ? b.label : vp.label || b.label || vp.bron_iri;
    groep.items.push({ sleutel: vp.bron_iri, label, soort: vp.soort, href });
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

const DEELSOORTEN = new Set(["hoofdstuk", "titeldeel", "afdeling", "paragraaf"]);

/** De titel van een structuurbron: "Invordering in eerste aanleg" uit
 *  "Hoofdstuk II – Invordering in eerste aanleg" (graph-qa zet die erbij); leeg zonder titel. */
function deelTitel(b: Bron): string {
  const [, titel = ""] = (b.label ?? "").split(" – ", 2);
  return titel.trim();
}

/** Wat het antwoord zelf noemt, als doelen voor de 3D-graaf.
 *
 *  - **Structuurdelen** (hoofdstuk, titeldeel, afdeling, paragraaf) waarvan de titel in de tekst staat –
 *    de kern van een overzichtsantwoord. De api toont zo'n deel met zijn artikelen. Een deel binnen een
 *    ander gekozen deel (paragraaf 4.4.4.2 in afdeling 4.4.4) valt weg.
 *  - **Artikelen** die de tekst noemt, in tekstvolgorde. Alleen een éénduidige koppeling telt
 *    (`koppelBron`, dezelfde regel als de citatie-chips); één doel per artikel, wel zo precies als de
 *    eerste vermelding: een genoemd lid opent zijn artikel met dát lid gekozen.
 *
 *  Het eerste doel opent ook in het paneel (tekst en annotatie); daarom gaat een artikel voor als er
 *  een is. Noemt de tekst niets te koppelen, dan de eerste bepaling uit de bronnen – het oude gedrag. */
export function samenhangDoelen(tekst: string, bronnen: readonly Bron[], max = MAX_SAMENHANG_DOELEN): { doelen: NodeDoel[]; totaal: number } {
  const laag = tekst.toLowerCase();
  const delen: NodeDoel[] = [];
  const posities = new Map<string, number>();
  for (const b of bronnen) {
    const vp = vindplaatsVan(b.bron_iri || b.uri);
    const titel = deelTitel(b);
    if (!vp || !DEELSOORTEN.has(vp.soort) || titel.length < 4) continue;
    const plek = laag.indexOf(titel.toLowerCase());
    if (plek < 0 || posities.has(vp.bron_iri)) continue;
    posities.set(vp.bron_iri, plek);
    delen.push({ bron_iri: vp.bron_iri, bwb_id: vp.bwb_id, label: b.label, ...(b.regeling ? { citeertitel: b.regeling } : {}) });
  }
  const binnen = (iri: string, ouder: string) => iri.startsWith(`${ouder}:`);
  const kern = delen.filter((d) => !delen.some((o) => o !== d && binnen(d.bron_iri, o.bron_iri)))
    .sort((a, b) => posities.get(a.bron_iri)! - posities.get(b.bron_iri)!);

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
  if (!gezien.size && !kern.length) {
    const eerste = bronnen.find((b) => bronDoel(b.bron_iri || b.uri)?.artikel);
    if (eerste) voegToe(eerste);
  }
  const artikelen = [...gezien.values()];
  // Kern eerst, maar het paneel krijgt een artikel: het eerste genoemde artikel gaat vooraan.
  const alle = artikelen.length && kern.length ? [artikelen[0], ...kern, ...artikelen.slice(1)] : [...kern, ...artikelen];
  return { doelen: alle.slice(0, max), totaal: alle.length };
}

/** De tekst op de knop: wat hij opent, niet alleen dát hij iets opent. */
export function samenhangKnopTekst({ doelen, totaal }: { doelen: NodeDoel[]; totaal: number }): string {
  if (doelen.length === 1) {
    const d = doelen[0];
    return `Bekijk samenhang van ${d.label ?? "de bepaling"}${d.citeertitel ? ` ${d.citeertitel}` : ""}`;
  }
  const getoond = totaal > doelen.length ? ` (${doelen.length} getoond)` : "";
  const delen = doelen.filter((d) => !d.artikel).length;
  if (!delen) return `Bekijk samenhang van de ${totaal} genoemde artikelen${getoond}`;
  const artikelen = doelen.length - delen;
  const stuk = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;
  return `Bekijk samenhang van ${stuk(delen, "deel", "delen")}${artikelen ? ` en ${stuk(artikelen, "artikel", "artikelen")}` : ""}${getoond}`;
}
