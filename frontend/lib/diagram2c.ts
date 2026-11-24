/** Het 2c-diagram in de werkplek (Handleiding §3.4c): het model, de plaatsen en de lijnen zoals de api ze levert
 *  (`GET /v1/annotatie/diagrammen` per bepaling, `GET /v1/annotatie/diagram` rond één markering). De api rekent de
 *  plaatsen én de stukken en labels van de lijnen uit (`diagram.plaats`, `diagram_teken.lijnstukken`), dus de werkplek
 *  tekent hetzelfde plaatje als de PDF en meet zelf niets. Dit bestand is puur: geen React, geen fetch-logica buiten
 *  `haalDiagrammen`/`haalDiagram`. */
import { jasRandKleur, jasVlakKleur } from "@/lib/jas";

export interface DiagramKnoop {
  id: string;
  soort: "element" | "impliciet";
  nr: number;
  klasse: string;
  tekst: string;
  /** De vindplaats als de markering in een andere bepaling staat. */
  elders: string;
  lifecycle: string;
  begrip: string;
  zone: "boven" | "links" | "midden" | "rechts" | "onder";
  diepte: number;
}

export interface Diagram {
  centraal: string;
  klasse: string;
  nr: number;
  knopen: DiagramKnoop[];
  lijnen: { van: string; naar: string; code: string; leesvorm: string; volgorde: number | null; lifecycle: string }[];
  ontbreekt: string[];
}

export interface Geplaatst {
  knoop: DiagramKnoop;
  x: number; y: number; b: number; h: number;
  kop: string;
  regels: string[];
}

/** Een lijn zoals de tekenaar haar trekt: van rand tot rand, met het midden en de maat van haar label. */
export interface DiagramLijn {
  relatie_id: string;
  van: string;
  naar: string;
  code: string;
  lifecycle: string;
  label: string[];
  x1: number; y1: number; x2: number; y2: number;
  lx: number; ly: number; lb: number; lh: number;
}

/** Wat de methode bij de centrale klasse verwacht en nog niet is vastgelegd, met het type en de richting gezien vanuit
 *  de centrale formulering (`in`: de relatie wijst naar haar). */
export interface OntbrekendeRol {
  label: string;
  codes: string[];
  richting: "in" | "uit";
}

export interface DiagramData {
  diagram: Diagram;
  plaatsing: { breedte: number; hoogte: number; knopen: Geplaatst[] };
  lijnen: DiagramLijn[];
  ontbreekt_rollen: OntbrekendeRol[];
}

export interface DiagramSet {
  bron_iri: string;
  diagrammen: DiagramData[];
}

/** Het kader van wat er werkelijk getekend is: de knopen en de labels van de lijnen, met een rand. De plaatsing van de api
 *  rekent op de volle breedte van een pagina (drie kolommen); staat er maar één kolom, dan zou de tekening op een smal
 *  scherm onleesbaar klein worden. Leeg: het kader van de plaatsing. */
export function inhoudKader(data: Pick<DiagramData, "plaatsing" | "lijnen">, rand = 3): { x: number; y: number; b: number; h: number } {
  const xs: number[] = [], ys: number[] = [], xe: number[] = [], ye: number[] = [];
  for (const g of data.plaatsing.knopen) { xs.push(g.x); ys.push(g.y); xe.push(g.x + g.b); ye.push(g.y + g.h); }
  for (const l of data.lijnen) {
    xs.push(l.lx - l.lb / 2, Math.min(l.x1, l.x2)); xe.push(l.lx + l.lb / 2, Math.max(l.x1, l.x2));
    ys.push(l.ly - l.lh / 2, Math.min(l.y1, l.y2)); ye.push(l.ly + l.lh / 2, Math.max(l.y1, l.y2));
  }
  if (!xs.length) return { x: -rand, y: -rand, b: data.plaatsing.breedte + 2 * rand, h: data.plaatsing.hoogte + 2 * rand };
  const x = Math.min(...xs) - rand, y = Math.min(...ys) - rand;
  return { x, y, b: Math.max(...xe) + rand - x, h: Math.max(...ye) + rand - y };
}

/** De maten van de tekening (`api/app/diagram.py` en `diagram_teken.py`): in dezelfde eenheden als de plaatsen. */
export const MAAT = { kop: 11, regel: 9, marge: 5, tekst: 7.5, kopTekst: 6.5, label: 6, labelRegel: 7.5 } as const;
export const LIJNKLEUR = "#535353";
export const RAND_CENTRAAL = "#154273";

export const knoopSleutel = (k: Pick<DiagramKnoop, "soort" | "id">) => `${k.soort}:${k.id}`;

/** Vlak en rand van een knoop, uit dezelfde tabel als de badges (`lib/jas.ts`). */
export function knoopKleuren(klasse: string): { vlak: string; rand: string } {
  return { vlak: jasVlakKleur(klasse), rand: jasRandKleur(klasse) };
}

/** De punt van een lijn: een driehoek bij het eindpunt, zoals in de PDF. */
export function pijlpunt(l: Pick<DiagramLijn, "x1" | "y1" | "x2" | "y2">): string {
  const lengte = Math.hypot(l.x2 - l.x1, l.y2 - l.y1) || 1;
  const ux = (l.x2 - l.x1) / lengte;
  const uy = (l.y2 - l.y1) / lengte;
  const punten = [[l.x2, l.y2], [l.x2 - 5 * ux + 2.4 * uy, l.y2 - 5 * uy - 2.4 * ux], [l.x2 - 5 * ux - 2.4 * uy, l.y2 - 5 * uy + 2.4 * ux]];
  return punten.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
}

/** Hoe een lijn heet in een schermlezer en een tooltip: "X levert op Y". */
export function lijnNaam(l: DiagramLijn, knopen: readonly DiagramKnoop[]): string {
  const tekst = (id: string) => knopen.find((k) => k.id === id)?.tekst ?? "";
  const kort = (t: string) => (t.length > 40 ? `${t.slice(0, 37)}…` : t);
  return `“${kort(tekst(l.van))}” ${l.label.join(" ")} “${kort(tekst(l.naar))}”`;
}

async function haal<T>(pad: string): Promise<T> {
  const r = await fetch(`/api/annotatie/v2/${pad}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Het diagram kon niet worden geladen (${r.status}).`);
  return r.json() as Promise<T>;
}

/** Alle diagrammen van een bepaling (de tab *Diagram* van het annotatiepaneel). */
export function haalDiagrammen(bronIri: string): Promise<DiagramSet> {
  return haal(`diagrammen?${new URLSearchParams({ bron_iri: bronIri })}`);
}

/** Het diagram rond één markering van een centrale klasse (onder haar relaties op de reviewkaart). */
export function haalDiagram(elementId: string): Promise<DiagramData> {
  return haal(`diagram?${new URLSearchParams({ element_id: elementId })}`);
}
