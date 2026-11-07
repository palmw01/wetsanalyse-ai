// De bronnen onder een antwoord: ontdubbeld per bronnode en gegroepeerd per regeling.
//
// graph-qa levert sinds de canonieke bronnen (`bronmodel.vindplaats`) al één bron per bepaling, met
// `bron_iri` en `regeling`. Oudere, bewaarde berichten dragen alleen `label` + `uri`, waarin dezelfde
// bepaling als graaf-IRI én als jci kan staan. Daarom normaliseert de werkplek zelf ook, met dezelfde
// regels (`vindplaatsVan`, de spiegel van bronmodel): één weergave voor oud en nieuw.

import type { Antwoord } from "./antwoord";
import type { NodeDoel } from "./annotatieNode";
import { koppelVermelding, vindVermeldingen } from "./citaties";
import { bronHref } from "./url";
import { bronDoel, vindplaatsVan } from "./samenhang";
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

/** De naam van de groep per brontype (ADR-013), in de volgorde van `bronmodel.extern.BRONTYPEN`. */
export const BRONTYPE_NAAM: Record<string, string> = {
  kamerstuk: "Parlementaire stukken", bekendmaking: "Staatsblad en Staatscourant", uitspraak: "Uitspraken",
  eu: "EU-recht",
};
const BRONTYPE_VOLGORDE = ["kamerstuk", "bekendmaking", "uitspraak", "eu"];

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
  const extern = new Map<string, BronGroep>();
  for (const b of bronnen) {
    // Een externe bron (ADR-013) staat in een eigen groep per brontype, onder de regelingen.
    if (b.brontype && b.brontype !== "wettekst") {
      if (gezien.has(b.uri)) continue;
      gezien.add(b.uri);
      let groep = extern.get(b.brontype);
      if (!groep) {
        groep = { bwb_id: `extern:${b.brontype}`, naam: BRONTYPE_NAAM[b.brontype] ?? b.brontype, items: [] };
        extern.set(b.brontype, groep);
      }
      groep.items.push({ sleutel: b.uri, label: b.label || b.uri, soort: b.brontype, href: bronHref(b.link) });
      continue;
    }
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
  for (const b of BRONTYPE_VOLGORDE) if (extern.has(b)) uit.push(extern.get(b)!);
  for (const [b, groep] of extern) if (!BRONTYPE_VOLGORDE.includes(b)) uit.push(groep);
  return { groepen: uit, overig, aantal: gezien.size };
}

/** Hoeveel artikelen de graaf hoogstens tegelijk opent vanuit één antwoord. Meer wordt een
 *  kaart van eilandjes, en elk artikel is een eigen request. */
export const MAX_SAMENHANG_DOELEN = 8;

/** Waar een doel vandaan komt, zodat de graaf eerlijk kan zeggen wat hij toont: het bericht wijst de
 *  bepaling zelf aan, of de tekst noemde niets te koppelen en het is de eerste bepaling uit de bronnen.
 *  `bronnen` is alles wat de tools teruggaven, niet waar het antwoord op rust. */
export type DoelHerkomst = "vermelding" | "eerste_bron";
export type AntwoordDoel = NodeDoel & { herkomst: DoelHerkomst };

/** Waar `antwoordDoelen` uit leest: een antwoord (`ThreadItem`), een annotatie of een citatie-chip. */
export type AntwoordBron =
  | { type: "antwoord"; tekst: string; bronnen?: readonly Bron[]; antwoord?: Antwoord }
  | { type: "annotatie"; annotatie_doel?: NodeDoel }
  | { type: "citatie"; doel: NodeDoel };

function doelenVan(item: AntwoordBron): AntwoordDoel[] {
  if (item.type === "citatie") return [{ ...item.doel, herkomst: "vermelding" }];
  if (item.type === "annotatie") return item.annotatie_doel ? [{ ...item.annotatie_doel, herkomst: "vermelding" }] : [];
  // Een sjabloon draagt zijn doelen zelf (ADR-008): dan valt er niets uit de tekst te halen.
  if (item.antwoord) return item.antwoord.doelen.flatMap((v) => {
    const doel = bronDoel(v.iri);
    return doel ? [{ ...doel, label: v.label, ...(v.regeling ? { citeertitel: v.regeling } : {}), herkomst: "vermelding" as const }] : [];
  });
  const bronnen = item.bronnen ?? [];
  const gezien = new Map<string, AntwoordDoel>();
  for (const v of vindVermeldingen(item.tekst)) {
    const k = koppelVermelding(v, bronnen);
    if (!k?.doel.artikel || gezien.has(k.doel.bron_iri)) continue;
    const regeling = bronnen[k.index].regeling;
    gezien.set(k.doel.bron_iri, { ...k.doel, ...(regeling ? { citeertitel: regeling } : {}), herkomst: "vermelding" });
  }
  const genoemd = [...gezien.values()];
  if (genoemd.length) return genoemd.filter((d) => !genoemd.some((x) => x.bron_iri.startsWith(`${d.bron_iri}:`)));
  const eerste = bronnen.find((b) => bronDoel(b.bron_iri || b.uri)?.artikel);
  const doel = eerste && bronDoel(eerste.bron_iri || eerste.uri);
  return doel ? [{ ...doel, ...(eerste.regeling ? { citeertitel: eerste.regeling } : {}), herkomst: "eerste_bron" }] : [];
}

/** De doelen van de graaf bij een antwoord: per bepaling één doel, zo diep als het bericht aanwijst, in
 *  de volgorde van de tekst. Een ouder valt weg als een kind ook genoemd is (de keten toont hem toch).
 *  De tekst selecteert alleen uit de bronnen en voegt niets toe (`koppelVermelding`), dezelfde regel als
 *  de citatie-chips. Noemt de tekst niets te koppelen, dan de eerste bepaling uit de bronnen, met
 *  `herkomst: "eerste_bron"`. Een annotatie, een chip en een sjabloon dragen hun doel zelf.
 *
 *  Een overzichtsantwoord gaat hier niet langs. */
export function antwoordDoelen(item: AntwoordBron, max = MAX_SAMENHANG_DOELEN): { doelen: AntwoordDoel[]; totaal: number } {
  const alle = doelenVan(item);
  return { doelen: alle.slice(0, max), totaal: alle.length };
}

function knopTekst({ doelen, totaal }: { doelen: NodeDoel[]; totaal: number }, meervoud: string): string {
  if (doelen.length === 1) {
    const d = doelen[0];
    return `Bekijk samenhang van ${d.label ?? "de bepaling"}${d.citeertitel ? ` ${d.citeertitel}` : ""}`;
  }
  return `Bekijk samenhang van de ${totaal} genoemde ${meervoud}${totaal > doelen.length ? ` (${doelen.length} getoond)` : ""}`;
}

/** De tekst op de knop: wat hij opent, niet alleen dát hij iets opent. Een doel is een bepaling, geen artikel. */
export const antwoordKnopTekst = (keuze: { doelen: NodeDoel[]; totaal: number }) => knopTekst(keuze, "bepalingen");
