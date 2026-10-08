/** De layout van de graaf: deterministisch, in twee lagen.
 *
 *  1. **De wettekst** (regelingen, delen, artikelen, leden, onderdelen, randbepalingen) krijgt een
 *     krachtlayout: eerst een radiale boom per regeling als startpunt (de opbouw van de wet blijft zo
 *     herkenbaar), dan ForceAtlas2 met de verwijzingen als zwakke veren, en tot slot een fase met
 *     `adjustSizes` die overlap wegduwt. ForceAtlas2 kent geen willekeur, dus dezelfde structuur geeft
 *     dezelfde kaart. Dit is het dure deel; het draait in een worker (`layout.worker.ts`) en de
 *     uitkomst wordt bewaard (`cache.ts`).
 *  2. **De annotaties** (markeringen en JAS-klassen) worden afgeleid, niet gesimuleerd
 *     (`plaatsAnnotaties`): een markering bij haar anker, de klassen op een ring om de kaart. Een
 *     beoordeling of een nieuwe markering verschuift daardoor niets en vraagt geen nieuwe layout.
 *
 *  Afstand en positie betekenen juridisch niets; ze houden de kaart herkenbaar en leesbaar. */
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { jasVolgorde, JAS_KLASSEN } from "@/lib/jas";
import { ankerVan, isBron, type GraafModel, type KnoopSoort, type RelatieData } from "./model";

/** Verhoog bij elke wijziging die de uitkomst verandert: de cache onder de oude sleutel vervalt dan. */
export const LAYOUT_VERSIE = 1;

export type Punt = [number, number];
export type Posities = Map<string, Punt>;

/** Wat de layout nodig heeft: de bronknopen en de relaties ertussen. Platte data, zodat het zonder
 *  omzetting naar een worker kan. */
export interface Structuur {
  knopen: { id: string; soort: KnoopSoort }[];
  relaties: { bron: string; doel: string; soort: RelatieData["soort"] }[];
}

export function structuurVan(g: GraafModel): Structuur {
  const knopen = g.filterNodes((_, a) => isBron(a)).map((id) => ({ id, soort: g.getNodeAttribute(id, "soort") }));
  const ids = new Set(knopen.map((k) => k.id));
  const relaties = g.filterEdges((_e, _a, bron, doel) => ids.has(bron) && ids.has(doel) && bron !== doel)
    .map((e) => ({ bron: g.source(e), doel: g.target(e), soort: g.getEdgeAttribute(e, "soort") }));
  return { knopen, relaties };
}

// ── Startposities: een radiale boom per regeling ────────────────────────────────────────────────

/** Afstand tussen twee ringen van de boom, in layout-eenheden. Op de schaal van ForceAtlas2 (een
 *  rustafstand van enkele eenheden), zodat de simulatie de boom niet eerst hoeft op te blazen of te
 *  laten krimpen. */
const RING = 6;
const TUSSENRUIMTE = 3 * RING;

const natuurlijk = (a: string, b: string) => a.localeCompare(b, "nl", { numeric: true });

/** Een deterministisch getal in [0, 1) uit een id (FNV-1a); `zaad` geeft per gebruik een eigen reeks. */
export function hash01(id: string, zaad = 0): number {
  let h = 2166136261 ^ zaad;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296;
}

const pool = (r: number, hoek: number): Punt => [r * Math.cos(hoek), r * Math.sin(hoek)];

export function startposities(s: Structuur, vast: Posities = new Map()): Posities {
  const kinderen = new Map<string, string[]>();
  const ouder = new Map<string, string>();
  for (const r of s.relaties) {
    if (r.soort !== "bevat" || ouder.has(r.doel)) continue;
    ouder.set(r.doel, r.bron);
    kinderen.set(r.bron, [...(kinderen.get(r.bron) ?? []), r.doel]);
  }
  for (const lijst of kinderen.values()) lijst.sort(natuurlijk);
  const bladen = new Map<string, number>();
  const telBladen = (id: string): number => {
    let n = bladen.get(id);
    if (n === undefined) {
      const k = kinderen.get(id);
      n = k ? k.reduce((som, c) => som + telBladen(c), 0) : 1;
      bladen.set(id, n);
    }
    return n;
  };
  const diepte = (id: string): number => Math.max(0, ...(kinderen.get(id) ?? []).map((c) => 1 + diepte(c)));

  // Bomen: elke wortel met kinderen (een regeling, of een los deel). De rest – randbepalingen en
  // knopen zonder plaats in een boom – komt straks naast een buur.
  const wortels = s.knopen.filter((k) => !ouder.has(k.id) && kinderen.has(k.id)).map((k) => k.id)
    .sort((a, b) => telBladen(b) - telBladen(a) || natuurlijk(a, b));
  const boom = new Map<string, Punt>();
  const bomen = wortels.map((w) => {
    const lokaal = new Map<string, Punt>();
    const maxDiepte = Math.max(1, diepte(w));
    // De straal groeit met de wortel van het aantal bladen: de buitenste ring houdt dan per blad
    // ongeveer dezelfde ruimte, of de regeling nu 50 of 2.000 bepalingen heeft.
    const straal = Math.max(RING, RING * Math.sqrt(telBladen(w)) / 1.6);
    const leg = (id: string, van: number, tot: number, d: number) => {
      lokaal.set(id, pool((straal * d) / maxDiepte, (van + tot) / 2));
      let hoek = van;
      for (const c of kinderen.get(id) ?? []) {
        const breedte = ((tot - van) * telBladen(c)) / telBladen(id);
        leg(c, hoek, hoek + breedte, d + 1);
        hoek += breedte;
      }
    };
    leg(w, 0, 2 * Math.PI, 0);
    return { lokaal, straal };
  });
  // De grootste boom in het midden, de andere op een ring eromheen, elk met een hoek naar zijn breedte.
  if (bomen.length) {
    const [eerste, ...rest] = bomen;
    for (const [id, p] of eerste.lokaal) boom.set(id, p);
    const omtrek = rest.reduce((som, b) => som + 2 * b.straal + TUSSENRUIMTE, 0);
    const ring = Math.max(eerste.straal + TUSSENRUIMTE + Math.max(0, ...rest.map((b) => b.straal)), omtrek / (2 * Math.PI));
    let hoek = 0;
    for (const b of rest) {
      const breedte = ((2 * b.straal + TUSSENRUIMTE) / omtrek) * 2 * Math.PI;
      const [mx, my] = pool(ring, hoek + breedte / 2);
      for (const [id, [x, y]] of b.lokaal) boom.set(id, [x + mx, y + my]);
      hoek += breedte;
    }
  }

  // Met een vorige stand: wat daarin stond blijft staan; nieuwe bomen komen er rechts naast.
  const pos: Posities = new Map();
  for (const k of s.knopen) {
    const p = vast.get(k.id);
    if (p) pos.set(k.id, p);
  }
  if (pos.size) {
    const nieuw = [...boom.keys()].filter((id) => !pos.has(id));
    const rechts = Math.max(...[...pos.values()].map(([x]) => x));
    const links = Math.min(...nieuw.map((id) => boom.get(id)![0]));
    for (const id of nieuw) {
      const [x, y] = boom.get(id)!;
      pos.set(id, [x - links + rechts + TUSSENRUIMTE, y]);
    }
  } else for (const [id, p] of boom) pos.set(id, p);

  // Losse knopen naast hun eerste geplaatste buur (in vaste volgorde), anders op een ring buitenom.
  const buren = new Map<string, string[]>();
  for (const r of s.relaties) {
    buren.set(r.bron, [...(buren.get(r.bron) ?? []), r.doel]);
    buren.set(r.doel, [...(buren.get(r.doel) ?? []), r.bron]);
  }
  const los = s.knopen.map((k) => k.id).filter((id) => !pos.has(id)).sort(natuurlijk);
  const buiten = Math.max(RING, ...[...pos.values()].map(([x, y]) => Math.hypot(x, y))) + TUSSENRUIMTE;
  for (const id of los) {
    const buur = (buren.get(id) ?? []).filter((b) => pos.has(b)).sort(natuurlijk)[0];
    const [bx, by] = buur ? pos.get(buur)! : [0, 0];
    const [dx, dy] = pool(buur ? RING * (1 + hash01(id, 7)) : buiten, 2 * Math.PI * hash01(id, 3));
    pos.set(id, [bx + dx, by + dy]);
  }
  return pos;
}

// ── De krachtlayout ──────────────────────────────────────────────────────────────────────────────

/** Welke relaties de layout vormen. De plek van een bepaling volgt uit de opbouw van de wet
 *  (`bevat`): elke regeling wordt een eigen gebied, met haar hoofdstukken als deelgebieden. Een
 *  verwijzing trekt níét – de ~3.500 verwijzingen zouden alle regelingen tot één kluwen trekken – en
 *  loopt als lijn over de kaart. Alleen een knoop zonder plek in een boom (een randbepaling buiten wat
 *  geladen is) hangt aan zijn verwijzing, anders drijft hij weg. */
function vormend(r: Structuur["relaties"][number], inBoom: ReadonlySet<string>): number {
  if (r.soort === "bevat") return 1;
  if (r.soort === "verwijst_naar" && (!inBoom.has(r.bron) || !inBoom.has(r.doel))) return 0.5;
  return 0;
}

/** De ruimte die een knoop in de layout inneemt (voor `adjustSizes`), in layout-eenheden. */
const RUIMTE: Record<KnoopSoort, number> = {
  regeling: 3, deel: 1.6, artikel: 0.9, lid: 0.6, onderdeel: 0.45, extern: 0.45, markering: 0.4, klasse: 1,
};

/** Hoeveel iteraties, naar grootte: genoeg om uit te kristalliseren, begrensd zodat de hele
 *  kennisgraaf (~6.500 knopen) binnen enkele seconden ligt. Vast per grootte, dus deterministisch. */
export function iteraties(order: number): { krachten: number; overlap: number } {
  return { krachten: order <= 1000 ? 200 : order <= 4000 ? 120 : 80, overlap: 20 };
}

const PER_STAP = 10;

export interface LayoutOpties {
  /** Posities uit een vorige stand. Die knopen liggen vast; alleen wat nieuw is, wordt geplaatst. */
  vast?: Posities;
  /** Voortgang in [0, 1], na elke stap van tien iteraties. */
  opVoortgang?: (fractie: number) => void;
}

export function berekenLayout(s: Structuur, opties: LayoutOpties = {}): Posities {
  const vast = opties.vast ?? new Map();
  const start = startposities(s, vast);
  const g = new Graph({ type: "directed", multi: true, allowSelfLoops: false });
  for (const k of s.knopen) {
    const [x, y] = start.get(k.id)!;
    g.addNode(k.id, { x, y, size: RUIMTE[k.soort], fixed: vast.has(k.id) });
  }
  const inBoom = new Set(s.relaties.filter((r) => r.soort === "bevat").flatMap((r) => [r.bron, r.doel]));
  for (const r of s.relaties) {
    const gewicht = vormend(r, inBoom);
    if (gewicht && r.bron !== r.doel && g.hasNode(r.bron) && g.hasNode(r.doel)) g.addDirectedEdge(r.bron, r.doel, { gewicht });
  }
  const nieuw = g.filterNodes((_, a) => !a.fixed).length;
  if (nieuw && g.size) {
    const { krachten, overlap } = iteraties(g.order);
    const basis = { ...forceAtlas2.inferSettings(g), edgeWeightInfluence: 1 };
    const totaal = krachten + overlap;
    for (let gedaan = 0; gedaan < totaal; gedaan += PER_STAP) {
      const settings = gedaan < krachten ? basis : { ...basis, adjustSizes: true };
      forceAtlas2.assign(g, { iterations: Math.min(PER_STAP, totaal - gedaan), settings, getEdgeWeight: "gewicht" });
      opties.opVoortgang?.(Math.min(1, (gedaan + PER_STAP) / totaal));
    }
  } else opties.opVoortgang?.(1);
  const uit: Posities = new Map();
  g.forEachNode((id, a) => uit.set(id, vast.get(id) ?? [a.x, a.y]));
  return uit;
}

// ── Annotaties: afgeleid van hun anker ──────────────────────────────────────────────────────────

const mediaan = (getallen: number[]) => {
  if (!getallen.length) return RING;
  const s = [...getallen].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)] || RING;
};

/** De posities van markeringen en klassen, bij de posities van de wettekst.
 *
 *  - Een markering staat in een kleine kring om haar anker (het lid of onderdeel dat ze markeert), op
 *    een plek die alleen van haar eigen id afhangt: komt er een bij, dan schuift er niets.
 *  - De dertien JAS-klassen staan in de tabelvolgorde op een ring om de hele kaart: ze verbinden
 *    markeringen uit alle regelingen, dus elke plek binnen de kaart zou ergens anders scheef trekken.
 *
 *  De maat is de mediane lengte van een `bevat`-lijn, zodat de kring meeschaalt met de kaart. */
export function plaatsAnnotaties(g: GraafModel, bron: Posities): Posities {
  const pos: Posities = new Map(bron);
  const lengtes: number[] = [];
  g.forEachEdge((_, a, van, naar) => {
    const p = bron.get(van), q = bron.get(naar);
    if (a.soort === "bevat" && p && q) lengtes.push(Math.hypot(p[0] - q[0], p[1] - q[1]));
  });
  const maat = mediaan(lengtes);

  const perAnker = new Map<string, string[]>();
  const zonderAnker: string[] = [];
  g.forEachNode((id, a) => {
    if (a.soort !== "markering") return;
    const anker = ankerVan(g, id);
    if (anker && bron.has(anker)) perAnker.set(anker, [...(perAnker.get(anker) ?? []), id]);
    else zonderAnker.push(id);
  });
  for (const [anker, ids] of perAnker) {
    const [ax, ay] = bron.get(anker)!;
    for (const id of ids) {
      const [dx, dy] = pool(maat * (0.4 + 0.25 * hash01(id, 13)), 2 * Math.PI * hash01(id, 5));
      pos.set(id, [ax + dx, ay + dy]);
    }
  }

  const punten = [...bron.values()];
  const midden: Punt = punten.length
    ? [punten.reduce((s, p) => s + p[0], 0) / punten.length, punten.reduce((s, p) => s + p[1], 0) / punten.length]
    : [0, 0];
  const straal = Math.max(maat * 3, ...punten.map(([x, y]) => Math.hypot(x - midden[0], y - midden[1]))) + maat * 4;
  const plekken = JAS_KLASSEN.length + 1;
  g.forEachNode((id, a) => {
    if (a.soort !== "klasse") return;
    const [dx, dy] = pool(straal, -Math.PI / 2 + (2 * Math.PI * jasVolgorde(a.klasse || a.label)) / plekken);
    pos.set(id, [midden[0] + dx, midden[1] + dy]);
  });
  // Een markering zonder geladen anker (komt uit de api niet voor) staat bij haar klasse.
  for (const id of zonderAnker.sort(natuurlijk)) {
    const klasse = g.outNeighbors(id).find((n) => g.getNodeAttribute(n, "soort") === "klasse");
    const [kx, ky] = (klasse && pos.get(klasse)) || midden;
    const [dx, dy] = pool(maat, 2 * Math.PI * hash01(id, 9));
    pos.set(id, [kx + dx, ky + dy]);
  }
  return pos;
}
