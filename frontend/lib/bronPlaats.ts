// Bepalingen gegroepeerd zoals een jurist ze leest (spoor H): regeling › hoofdstuk/afdeling/paragraaf of
// divisie › artikel › lid/onderdeel, in de volgorde van het document. De plek komt van de api
// (`POST /v1/annotatie/plaatsen`, uit de bronboom); zonder plek valt de boom terug op wat de IRI zelf zegt
// (`vindplaatsVan`). Zuiver, zodat vitest het zonder DOM toetst.

import { vindplaatsVan } from "./samenhang";

export interface PlaatsStap { iri: string; type: string; nummer: string; label: string }
export interface Plaats {
  bron_iri: string;
  regeling: { bwb_id: string; citeertitel: string };
  pad: PlaatsStap[];
  volgorde: number | null;
}

/** Actuele bronnaam uit de graaf, ook voor selecties met een ouder opgeslagen label. */
export function labelVanPlaats(plaats: Plaats | undefined): string | undefined {
  if (!plaats?.pad.length) return undefined;
  const begin = plaats.pad.findIndex((p) => p.type === "Artikel" || p.type === "Divisie");
  const pad = plaats.pad.slice(Math.max(0, begin)).map((p) => p.label).filter(Boolean).join(", ");
  if (!pad) return undefined;
  return plaats.regeling.citeertitel ? `${plaats.regeling.citeertitel} – ${pad}` : pad;
}

export interface Blad<T> {
  sleutel: string;
  bron_iri: string;
  /** Wat er onder het artikel nog staat ("Lid 2, onderdeel a"), of "Hele artikel" voor het artikel zelf. */
  label: string;
  data: T;
}

export interface BoomKnoop<T> {
  sleutel: string;
  soort: "regeling" | "deel" | "artikel";
  label: string;
  kinderen: BoomKnoop<T>[];
  bladeren: Blad<T>[];
}

/** De soorten die een artikel groeperen (een "deel"); een divisie van een beleidsregel ook, tenzij ze
 *  zelf de bepaling is (dan staat ze op de plek van het artikel). */
const DELEN = new Set(["Hoofdstuk", "Titeldeel", "Titel", "Afdeling", "Paragraaf", "Subparagraaf", "Boek", "Deel", "Divisie"]);
const DEEL_SLEUTELS: Record<string, string> = { hoofdstuk: "Hoofdstuk", titeldeel: "Titeldeel", afdeling: "Afdeling", paragraaf: "Paragraaf" };

/** De laatste index waarvoor `test` klopt (`findLastIndex` zit niet in de ES2022-lib van dit project). */
function laatste<T>(lijst: readonly T[], test: (x: T) => boolean): number {
  for (let i = lijst.length - 1; i >= 0; i--) if (test(lijst[i])) return i;
  return -1;
}

function hoofdletter(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Het pad van één bepaling: delen, het artikel (of de bepaling op die plek) en wat eronder staat. */
function stappen(iri: string, plaats: Plaats | undefined): { delen: { sleutel: string; label: string }[]; artikel?: { sleutel: string; label: string }; rest: string } {
  if (plaats?.pad.length) {
    const pad = plaats.pad;
    let a = laatste(pad, (p) => p.type === "Artikel");
    if (a < 0) a = laatste(pad, (p) => DELEN.has(p.type));
    if (a < 0) a = pad.length - 1;
    const delen = pad.slice(0, a).map((p) => ({ sleutel: p.iri, label: p.label || hoofdletter(p.type) }));
    const rest = pad.slice(a + 1).map((p) => p.label || hoofdletter(p.type)).join(", ");
    return { delen, artikel: { sleutel: pad[a].iri, label: pad[a].label || hoofdletter(pad[a].type) }, rest };
  }
  const vp = vindplaatsVan(iri);
  if (!vp || !vp.pad.length || vp.soort === "node") return { delen: [], rest: "" };
  const delen: { sleutel: string; label: string }[] = [];
  let artikel: { sleutel: string; label: string } | undefined;
  const rest: string[] = [];
  let pad = `urn:bwb:${vp.bwb_id}`;
  for (const [k, v] of vp.pad) {
    pad += `:${k}:${v}`;
    if (DEEL_SLEUTELS[k] && !artikel) delen.push({ sleutel: pad, label: `${DEEL_SLEUTELS[k]} ${v}` });
    else if (k === "artikel") artikel = { sleutel: pad, label: `Artikel ${v}` };
    else if (k === "lid") rest.push(`Lid ${v}`);
    else if (k === "o") rest.push(`Onderdeel ${v}`);
  }
  // Een hoofdstuk zonder artikel eronder: de laatste stap is de bepaling zelf.
  if (!artikel && delen.length) artikel = delen.pop();
  return { delen, artikel, rest: rest.join(", ") };
}

/** De boom van een lijst bepalingen. `items` mogen in elke volgorde komen; de boom volgt de wet. Een
 *  bepaling zonder herkenbare plek staat direct onder haar regeling, met haar eigen naam (`naam`). */
export function bouwBoom<T>(items: readonly T[], opties: {
  iri: (item: T) => string;
  /** Hoe het blad heet als er geen plek is (meestal het label van de bron). */
  naam: (item: T) => string;
  /** De sleutel van een blad, als er meer items op één bepaling staan (passages); standaard de IRI. */
  sleutel?: (item: T) => string;
  plaatsen?: ReadonlyMap<string, Plaats> | null;
  /** De naam van een regeling als de api hem niet gaf (bv. uit het label "… – Invorderingswet 1990"). */
  regelingNaam?: (item: T, bwbId: string) => string | undefined;
}): BoomKnoop<T>[] {
  const plaatsen = opties.plaatsen ?? new Map<string, Plaats>();
  const gesorteerd = items.map((item, i) => ({ item, i, iri: opties.iri(item), plaats: plaatsen.get(opties.iri(item)) }))
    .sort((a, b) => {
      const va = a.plaats?.volgorde, vb = b.plaats?.volgorde;
      if (va != null && vb != null && a.plaats!.regeling.bwb_id === b.plaats!.regeling.bwb_id) return va - vb;
      return a.iri.localeCompare(b.iri, "nl", { numeric: true }) || a.i - b.i;
    });
  const regelingen = new Map<string, BoomKnoop<T>>();
  const kind = (ouder: BoomKnoop<T>, sleutel: string, soort: BoomKnoop<T>["soort"], label: string) => {
    let k = ouder.kinderen.find((x) => x.sleutel === sleutel);
    if (!k) { k = { sleutel, soort, label, kinderen: [], bladeren: [] }; ouder.kinderen.push(k); }
    return k;
  };
  for (const { item, iri, plaats } of gesorteerd) {
    const bwb = plaats?.regeling.bwb_id || vindplaatsVan(iri)?.bwb_id || iri.match(/^urn:bwb:(BWB[A-Z]\d+)/)?.[1] || "onbekend";
    let reg = regelingen.get(bwb);
    if (!reg) {
      const label = plaats?.regeling.citeertitel || opties.regelingNaam?.(item, bwb) || bwb;
      reg = { sleutel: `urn:bwb:${bwb}`, soort: "regeling", label, kinderen: [], bladeren: [] };
      regelingen.set(bwb, reg);
    }
    const { delen, artikel, rest } = stappen(iri, plaats);
    let ouder = reg;
    for (const d of delen) ouder = kind(ouder, d.sleutel, "deel", d.label);
    if (artikel) {
      const a = kind(ouder, artikel.sleutel, "artikel", artikel.label);
      a.bladeren.push({ sleutel: opties.sleutel?.(item) ?? iri, bron_iri: iri, label: rest || "Hele bepaling", data: item });
    } else {
      ouder.bladeren.push({ sleutel: opties.sleutel?.(item) ?? iri, bron_iri: iri, label: opties.naam(item), data: item });
    }
  }
  return [...regelingen.values()];
}

/** Alle bladeren onder een knoop, in volgorde. */
export function bladerenVan<T>(k: BoomKnoop<T>): Blad<T>[] {
  return [...k.bladeren, ...k.kinderen.flatMap(bladerenVan)];
}

/** De boom plat per regeling (spoor K): elke bepaling één rij met haar plek ("Artikel 9 · Lid 2"), in de volgorde
 *  van de wet, zonder in te klappen niveaus. Voor lezen; kiezen met vinkjes per hoofdstuk blijft de boom. */
export function rijenPerRegeling<T>(boom: readonly BoomKnoop<T>[]): { sleutel: string; regeling: string; rijen: { blad: Blad<T>; plek: string }[] }[] {
  const plat = (k: BoomKnoop<T>, artikel?: string): { blad: Blad<T>; plek: string }[] => [
    ...k.bladeren.map((blad) => ({ blad, plek: k.soort === "artikel"
      ? (blad.label === "Hele bepaling" ? k.label : `${k.label} · ${blad.label}`) : blad.label })),
    ...k.kinderen.flatMap((c) => plat(c, c.soort === "artikel" ? c.label : artikel)),
  ];
  return boom.map((r) => ({ sleutel: r.sleutel, regeling: r.label, rijen: plat(r) }));
}

/** "18 bepalingen in 4 regelingen": de omvang van een boom in één regel. */
export function omvangZin<T>(boom: readonly BoomKnoop<T>[]): string {
  const n = boom.reduce((s, r) => s + bladerenVan(r).length, 0);
  if (!n) return "geen bepalingen";
  const b = `${n} ${n === 1 ? "bepaling" : "bepalingen"}`;
  return boom.length > 1 ? `${b} in ${boom.length} regelingen` : b;
}

/** De regelingnaam uit een label in de vorm "Artikel 9, lid 1 – Invorderingswet 1990". */
export function regelingUitLabel(label: string): string | undefined {
  const i = label.lastIndexOf(" – ");
  return i > 0 ? label.slice(i + 3).trim() || undefined : undefined;
}
