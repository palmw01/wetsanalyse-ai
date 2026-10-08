/** De weergavestand: de énige plek waar staat wat er in beeld is en wat nadruk krijgt. De tekenaar
 *  vraagt per knoop en per lijn het beeld op (`knoopBeeld`, `lijnBeeld`) en houdt zelf geen stand bij.
 *
 *  Twee begrippen, strikt gescheiden:
 *
 *  - **Zichtbaar** = wat geladen is, binnen de lagen (*Leden en onderdelen*, *Verwijzingen*,
 *    *Annotaties*) en het markeringsfilter. Alleen de lagen en het filter veranderen dat; **een klik
 *    nooit**.
 *  - **Nadruk**, in deze volgorde: (1) de gekozen knoop met zijn directe buren; anders (2) de focus,
 *    de delen en bepalingen die het antwoord noemt; anders (3) alles. Wat geen nadruk heeft, is
 *    gedimd: het blijft als kaart staan, zonder label. Op de achtergrond klikken heft de keuze op en
 *    brengt de focus terug. */
import { pastBijMarkeringFilter, type MarkeringFilter } from "@/lib/samenhang";
import { ankerVan, type GraafModel, type KnoopData, type RelatieData } from "./model";
import {
  BRONKLEUR, DEKKINGSKLEUR, GEDIMD, GEDIMDE_LIJN, GEKOZEN_FACTOR, GROOTTE, klasseKleur, LIJNDIKTE, LIJNKLEUR,
  NADRUK_LIJN, RAND_VULLING, RANDKLEUR,
} from "./stijl";

export interface Lagen {
  /** Leden en onderdelen; uit = de kaart tot op artikelniveau. */
  leden: boolean;
  /** Verwijzingen en de bepalingen buiten wat geladen is. */
  verwijzingen: boolean;
  /** Markeringen met hun JAS-klasse. */
  annotaties: boolean;
  /** Een okeromtrek om leden en onderdelen met zinsdelen zonder detectortreffer. */
  dekking: boolean;
}
export const STANDAARD_LAGEN: Lagen = { leden: true, verwijzingen: true, annotaties: true, dekking: false };

/** Wat het antwoord noemt: de `doelen` zelf (krijgen altijd een label) en hun `bereik` (de doelen met
 *  wat ze bevatten, plus de markeringen daarop). */
export interface Focus {
  doelen: ReadonlySet<string>;
  bereik: ReadonlySet<string>;
}

export interface WeergaveStand {
  lagen: Lagen;
  markering: MarkeringFilter;
  selectie: string | null;
  focus: Focus | null;
  /** Bron-IRI's met zinsdelen zonder detectortreffer (de laag Dekking). */
  ongedekt: ReadonlySet<string>;
}

/** De focus voor een reeks doelen: de doelen, alles wat ze bevatten, en de markeringen daarop met hun
 *  klasse. Doelen die niet in het model staan, vallen weg. */
export function focusVan(g: GraafModel, doelen: Iterable<string>): Focus {
  const eigen = new Set([...doelen].filter((id) => g.hasNode(id)));
  const bereik = new Set<string>();
  const stapel = [...eigen];
  while (stapel.length) {
    const id = stapel.pop()!;
    if (bereik.has(id)) continue;
    bereik.add(id);
    for (const e of g.outEdges(id)) if (g.getEdgeAttribute(e, "soort") === "bevat") stapel.push(g.target(e));
  }
  for (const e of g.edges()) {
    if (g.getEdgeAttribute(e, "soort") !== "markeert" || !bereik.has(g.target(e))) continue;
    const m = g.source(e);
    bereik.add(m);
    for (const k of g.outNeighbors(m)) if (g.getNodeAttribute(k, "soort") === "klasse") bereik.add(k);
  }
  return { doelen: eigen, bereik };
}

/** De knopen die buiten de lagen of het markeringsfilter vallen. */
export function verborgenKnopen(g: GraafModel, lagen: Lagen, markering: MarkeringFilter): Set<string> {
  const weg = new Set<string>();
  g.forEachNode((id, a) => {
    if (!lagen.annotaties && (a.soort === "markering" || a.soort === "klasse")) weg.add(id);
    else if (!lagen.leden && (a.soort === "lid" || a.soort === "onderdeel")) weg.add(id);
    else if (!lagen.verwijzingen && (a.rand || a.soort === "extern")) weg.add(id);
  });
  // Een markering verdwijnt met haar anker of door het filter; een klasse als ze niets meer markeert.
  const klasseInGebruik = new Set<string>();
  g.forEachNode((id, a) => {
    if (a.soort !== "markering" || weg.has(id)) return;
    const anker = ankerVan(g, id);
    if ((anker && weg.has(anker)) || !pastBijMarkeringFilter(a, markering)) weg.add(id);
    else for (const k of g.outNeighbors(id)) klasseInGebruik.add(k);
  });
  g.forEachNode((id, a) => {
    if (a.soort === "klasse" && !klasseInGebruik.has(id)) weg.add(id);
  });
  return weg;
}

export interface WeergaveContext {
  stand: WeergaveStand;
  verborgen: ReadonlySet<string>;
  /** Wat nadruk heeft; `null` = alles (geen keuze en geen focus). */
  nadruk: ReadonlySet<string> | null;
}

export function weergaveContext(g: GraafModel, stand: WeergaveStand): WeergaveContext {
  const verborgen = verborgenKnopen(g, stand.lagen, stand.markering);
  let nadruk: Set<string> | null = null;
  const sel = stand.selectie;
  if (sel && g.hasNode(sel) && !verborgen.has(sel)) {
    nadruk = new Set([sel, ...g.neighbors(sel).filter((n) => !verborgen.has(n))]);
  } else if (stand.focus) {
    const zichtbaar = [...stand.focus.bereik].filter((id) => g.hasNode(id) && !verborgen.has(id));
    if (zichtbaar.length) nadruk = new Set(zichtbaar);
  }
  return { stand, verborgen, nadruk };
}

export interface KnoopBeeld {
  verborgen: boolean;
  kleur: string;
  /** Omtrekkleur (een bepaling buiten wat geladen is, of de laag Dekking), anders `null`. */
  omtrek: string | null;
  grootte: number;
  /** `null` = geen label (gedimd). Of het getoond wordt, beslist de tekenaar naar ruimte. */
  label: string | null;
  /** Altijd een label, ook als het ruimte kost: de keuze en de doelen van de focus. */
  altijdLabel: boolean;
  gedimd: boolean;
  gekozen: boolean;
  /** Tekenvolgorde: gedimd 0, gewoon 1, nadruk 2, gekozen 3. */
  niveau: number;
}

export function knoopBeeld(id: string, a: KnoopData, ctx: WeergaveContext): KnoopBeeld {
  const { stand, nadruk } = ctx;
  const verborgen = ctx.verborgen.has(id);
  const gekozen = stand.selectie === id;
  const gedimd = !!nadruk && !nadruk.has(id);
  const eigen = a.soort === "markering" || a.soort === "klasse" ? klasseKleur(a.klasse || a.label) : a.rand ? RAND_VULLING : BRONKLEUR[a.soort];
  const dekking = stand.lagen.dekking && stand.ongedekt.has(id);
  const doel = !stand.selectie && !!stand.focus?.doelen.has(id);
  return {
    verborgen,
    kleur: gedimd ? GEDIMD : eigen,
    omtrek: gedimd ? null : dekking ? DEKKINGSKLEUR : a.rand ? RANDKLEUR : null,
    grootte: GROOTTE[a.soort] * (gekozen ? GEKOZEN_FACTOR : 1),
    label: gedimd ? null : a.kort,
    altijdLabel: gekozen || doel,
    gedimd,
    gekozen,
    niveau: gekozen ? 3 : gedimd ? 0 : nadruk ? 2 : 1,
  };
}

export interface LijnBeeld {
  verborgen: boolean;
  kleur: string;
  dikte: number;
  /** Een verwijzing heeft een richting; de opbouw en de annotaties lezen zonder pijl. */
  pijl: boolean;
  niveau: number;
}

export function lijnBeeld(a: RelatieData, bron: string, doel: string, ctx: WeergaveContext): LijnBeeld {
  const { stand, nadruk, verborgen } = ctx;
  const sel = stand.selectie;
  const raaktKeuze = !!sel && (bron === sel || doel === sel);
  const laagUit = (a.groep === "verwijzingen" && !stand.lagen.verwijzingen) || (a.groep === "annotaties" && !stand.lagen.annotaties);
  // Lijnen naar een klasse alleen bij een gekozen markering of klasse: dertien knopen met elk honderden
  // lijnen dekken anders de hele kaart af.
  const klasselijn = a.soort === "heeft_klasse" && !raaktKeuze;
  const pijl = a.soort === "verwijst_naar";
  if (laagUit || klasselijn || verborgen.has(bron) || verborgen.has(doel)) {
    return { verborgen: true, kleur: GEDIMDE_LIJN, dikte: 0, pijl, niveau: 0 };
  }
  if (raaktKeuze) return { verborgen: false, kleur: NADRUK_LIJN, dikte: LIJNDIKTE[a.soort] * 2, pijl, niveau: 2 };
  const gedimd = !!nadruk && !(nadruk.has(bron) && nadruk.has(doel));
  return { verborgen: false, kleur: gedimd ? GEDIMDE_LIJN : LIJNKLEUR[a.soort], dikte: LIJNDIKTE[a.soort], pijl, niveau: gedimd ? 0 : 1 };
}
