import { jasStyle } from "./jas";
import { nodeRequest, type NodeDoel } from "./annotatieNode";

/** Het antwoord van `GET /v1/annotatie/samenhang` (api/app/samenhang.py). */
export type KnoopSoort = "regeling" | "deel" | "artikel" | "lid" | "onderdeel" | "markering" | "klasse" | "extern";
export type RelatieGroep = "structuur" | "verwijzingen" | "annotaties";
export interface SamenhangKnoop {
  id: string; soort: KnoopSoort; label: string; tekst: string; klasse: string; lifecycle: string;
  element_id: string; bwb_id: string; artikel: string; lid: string; rand: boolean;
}
export interface SamenhangRelatie {
  bron: string; doel: string; soort: "bevat" | "verwijst_naar" | "markeert" | "heeft_klasse";
  groep: RelatieGroep; anker_tekst: string;
}
export interface Samenhang {
  schema_versie: 1; doel: NodeDoel; snapshot_id: string; artikel_iri: string;
  knopen: SamenhangKnoop[]; relaties: SamenhangRelatie[]; verwijzingen_beschikbaar: boolean; afgekapt: boolean;
}

/** Wat de canvas tekent: vaste posities, zodat de kaart herkenbaar blijft tussen renders. */
export interface GraafKnoop extends SamenhangKnoop {
  kort: string; kleur: string; x: number; y: number; z: number; fx: number; fy: number; fz: number;
}
export interface GraafRelatie { id: string; source: string; target: string; label: string; groep: RelatieGroep; anker_tekst: string }
export interface GraafData { nodes: GraafKnoop[]; links: GraafRelatie[] }

export const SOORT_LABEL: Record<KnoopSoort, string> = {
  regeling: "Regeling", deel: "Structuur", artikel: "Artikel", lid: "Lid", onderdeel: "Onderdeel",
  markering: "Markering", klasse: "JAS-klasse", extern: "Niet-geïmporteerde bepaling",
};
const RELATIE_LABEL: Record<SamenhangRelatie["soort"], string> = {
  bevat: "bevat", verwijst_naar: "verwijst naar", markeert: "markeert", heeft_klasse: "heeft klasse",
};
const BRONKLEUR: Partial<Record<KnoopSoort, string>> = {
  regeling: "#154273", deel: "#2b5f8f", artikel: "#007bc7", lid: "#398ab8", onderdeel: "#6aa6cf", extern: "#94a3b8",
};
const RANDKLEUR = "#a7bfd3";

export function klasseKleur(klasse: string): string {
  return jasStyle(klasse).match(/bg-\[(#[a-f0-9]+)\]/)?.[1] ?? "#cbd5e1";
}

export async function haalSamenhang(doel: Pick<NodeDoel, "bron_iri">): Promise<Samenhang> {
  return nodeRequest(`samenhang?${new URLSearchParams({ bron_iri: doel.bron_iri })}`);
}

let capabilities: Promise<boolean> | undefined;
/** Heeft de API het samenhang-endpoint? Eén keer per pagina gevraagd; een fout betekent: nee. */
export function samenhangBeschikbaar(): Promise<boolean> {
  capabilities ??= nodeRequest<{ samenhang?: boolean }>("capabilities")
    .then((c) => Boolean(c.samenhang)).catch(() => false);
  return capabilities;
}

const BWB = /^BWB[RV]\d+$/;
/** Een bron onder een antwoord (graaf-IRI of jci) als bronnode; de spiegel van `uitGraafIri` in
 *  `lib/url.ts`. Alleen een bepaling ónder een regeling telt: bij een hele wet is er geen artikel. */
export function bronDoel(uri: string): NodeDoel | undefined {
  const ref = uri.trim();
  let bwb = "", paren: [string, string][] = [];
  if (ref.startsWith("urn:bwb:")) {
    const [id, ...rest] = ref.slice("urn:bwb:".length).split(":").map(decodeURIComponent);
    if (rest.length % 2) return undefined;
    bwb = id;
    for (let i = 0; i < rest.length; i += 2) paren.push([rest[i], rest[i + 1]]);
  } else if (/^jci/i.test(ref)) {
    const m = ref.match(/^jci[\d.]+:c:(BWB[RV]\d+)(.*)$/i);
    if (!m) return undefined;
    bwb = m[1].toUpperCase();
    paren = [...new URLSearchParams(m[2].replace(/^&?/, ""))].filter(([k]) => !["g", "z"].includes(k));
  }
  if (!BWB.test(bwb) || !paren.length || paren.some(([k, v]) => !k || !v || k === "id")) return undefined;
  const waarde = Object.fromEntries(paren);
  return {
    bron_iri: `urn:bwb:${bwb}:` + paren.map(([k, v]) => `${k}:${v}`).join(":"),
    bwb_id: bwb, artikel: waarde.artikel, lid: waarde.lid,
    label: [waarde.artikel && `Artikel ${waarde.artikel}`, waarde.lid && `lid ${waarde.lid}`].filter(Boolean).join(", ") || undefined,
  };
}

/** Samenhang-antwoorden samenvoegen (uitgeklapte randknopen). Een knoop is pas rand als hij dat in
 *  élk antwoord is; relaties ontdubbeld op bron, doel en soort. Idempotent. */
export function voegSamen(delen: Samenhang[]): { knopen: SamenhangKnoop[]; relaties: SamenhangRelatie[] } {
  const knopen = new Map<string, SamenhangKnoop>();
  const relaties = new Map<string, SamenhangRelatie>();
  for (const deel of delen) {
    for (const k of deel.knopen) {
      const oud = knopen.get(k.id);
      knopen.set(k.id, oud ? { ...oud, ...(oud.rand && !k.rand ? k : {}), rand: oud.rand && k.rand } : k);
    }
    for (const r of deel.relaties) relaties.set(`${r.bron}|${r.soort}|${r.doel}`, r);
  }
  return { knopen: [...knopen.values()], relaties: [...relaties.values()] };
}

const kort = (tekst: string) => tekst.length > 27 ? tekst.slice(0, 25) + "…" : tekst;

/** Vaste 3D-posities per artikelcluster: structuur links, leden in het midden, markeringen in een
 *  ring rond hun lid, klassen rechts, randknopen erachter. Afstand en positie betekenen juridisch
 *  niets; ze houden de kaart alleen herkenbaar. Elk uitgeklapt artikel krijgt een eigen cluster. */
export function bouwGraaf(delen: Samenhang[]): GraafData {
  const { knopen, relaties } = voegSamen(delen);
  const per = new Map(knopen.map((k) => [k.id, k]));
  const pos = new Map<string, [number, number, number]>();
  const zet = (id: string, p: [number, number, number]) => { if (!pos.has(id)) pos.set(id, p); };
  const kinderen = (id: string) => relaties.filter((r) => r.soort === "bevat" && r.bron === id).map((r) => r.doel);
  let klasseRij = 0;
  delen.forEach((deel, cluster) => {
    const dx = cluster * 380;
    // Structuur boven het artikel: een diagonaal naar links boven.
    const keten: string[] = [];
    for (let id: string | undefined = deel.artikel_iri; id; id = relaties.find((r) => r.soort === "bevat" && r.doel === id)?.bron)
      keten.unshift(id);
    keten.forEach((id, i) => zet(id, [dx - 40 - (keten.length - 1 - i) * 55, 20 + (keten.length - 1 - i) * 40, (i % 2 ? 1 : -1) * 25]));
    // Leden en onderdelen onder het artikel, op volgorde.
    const binnen: string[] = [];
    const loop = (id: string) => { for (const k of kinderen(id)) { binnen.push(k); loop(k); } };
    loop(deel.artikel_iri);
    binnen.forEach((id, i) => zet(id, [dx + 30 + (per.get(id)?.soort === "onderdeel" ? 30 : 0),
      ((binnen.length - 1) / 2 - i) * 70, (i % 2 ? 1 : -1) * 30]));
    // Markeringen in een ring rond het eerste fragment dat ze markeren.
    const markeringen = deel.knopen.filter((k) => k.soort === "markering");
    const perAnker = new Map<string, string[]>();
    for (const m of markeringen) {
      const anker = relaties.find((r) => r.bron === m.id && r.soort === "markeert")?.doel ?? deel.artikel_iri;
      perAnker.set(anker, [...(perAnker.get(anker) ?? []), m.id]);
    }
    for (const [anker, ids] of perAnker) {
      const [ax, ay] = pos.get(anker) ?? [dx + 30, 0, 0];
      ids.forEach((id, i) => {
        const hoek = (i / ids.length) * Math.PI * 2;
        zet(id, [ax + 75 + Math.cos(hoek) * 40, ay + Math.sin(hoek) * 45, ((i % 3) - 1) * 50]);
      });
    }
    for (const k of deel.knopen.filter((k) => k.soort === "klasse"))
      if (!pos.has(k.id)) { zet(k.id, [dx + 230, 110 - klasseRij * 50, klasseRij % 2 ? -35 : 40]); klasseRij++; }
    // Randknopen: een boog achter het cluster, in vaste volgorde.
    const rand = deel.knopen.filter((k) => k.rand && !pos.has(k.id)).sort((a, b) => a.id.localeCompare(b.id));
    rand.forEach((k, i) => {
      const hoek = rand.length > 1 ? -Math.PI / 3 + (i / (rand.length - 1)) * (2 * Math.PI / 3) : 0;
      zet(k.id, [dx - 20 + Math.sin(hoek) * 170, Math.cos(hoek) * 40 - 140, -170]);
    });
  });
  const nodes = knopen.map((k): GraafKnoop => {
    const [x, y, z] = pos.get(k.id) ?? [0, 0, 0];
    const kleur = k.klasse ? klasseKleur(k.klasse) : k.rand ? (k.soort === "extern" ? BRONKLEUR.extern! : RANDKLEUR) : BRONKLEUR[k.soort] ?? "#398ab8";
    const label = k.soort === "lid" && k.lid && k.artikel ? `Artikel ${k.artikel} · lid ${k.lid}` : k.label;
    return { ...k, label, kort: kort(k.soort === "lid" && k.lid ? `Lid ${k.lid}` : label), kleur, x, y, z, fx: x, fy: y, fz: z };
  });
  const links = relaties.filter((r) => per.has(r.bron) && per.has(r.doel)).map((r) => ({
    id: `${r.bron}|${r.soort}|${r.doel}`, source: r.bron, target: r.doel, label: RELATIE_LABEL[r.soort],
    groep: r.groep, anker_tekst: r.anker_tekst,
  }));
  return { nodes, links };
}

/** Filters veranderen alleen zichtbaarheid. Altijd zichtbaar: de bronstructuur van de geopende
 *  artikelen. Uitgeklapte knopen tonen daarnaast hun directe buren. */
export function zichtbareGraaf(data: GraafData, uitgebreid: string[], filters: Record<RelatieGroep, boolean>): GraafData {
  const zichtbaar = new Set(data.nodes.filter((n) => !n.rand && !["markering", "klasse"].includes(n.soort)).map((n) => n.id));
  for (const id of uitgebreid) {
    zichtbaar.add(id);
    for (const edge of data.links) {
      if (!filters[edge.groep]) continue;
      if (edge.source === id) zichtbaar.add(edge.target);
      if (edge.target === id) zichtbaar.add(edge.source);
    }
  }
  const nodes = data.nodes.filter((n) => zichtbaar.has(n.id)
    && (filters.annotaties || !["klasse", "markering"].includes(n.soort))
    && (filters.verwijzingen || !n.rand));
  const ids = new Set(nodes.map((n) => n.id));
  return { nodes, links: data.links.filter((e) => filters[e.groep] && ids.has(e.source) && ids.has(e.target)) };
}

/** Kan deze knoop als eigen artikel worden bijgeladen? Alleen een geïmporteerde randbepaling. */
export function uitklapbaar(knoop: Pick<SamenhangKnoop, "rand" | "soort" | "bwb_id">): boolean {
  return knoop.rand && knoop.soort !== "extern" && Boolean(knoop.bwb_id);
}
