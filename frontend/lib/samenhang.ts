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

/** Vaste 3D-posities per artikelcluster, radiaal: het artikel in het midden, leden in een ring en
 *  onderdelen verder naar buiten in het verlengde van hun lid (elk blad een eigen hoeksector naar
 *  gewicht), markeringen net buiten hun fragment, klassen in een kolom rechts. De structuur erboven
 *  (regeling, hoofdstuk) staat boven-achter het artikel; daarvoor blijft bovenin de ring een opening.
 *  Verwijzingen van of naar een lid staan buiten dat lid; verwijzingen naar het artikel als geheel
 *  – vaak de grootste groep – op een eigen ring áchter het artikel, zodat ze de leden niet bedekken.
 *  Afstand en positie betekenen juridisch niets; ze houden de kaart herkenbaar en leesbaar. */
export function bouwGraaf(delen: Samenhang[]): GraafData {
  const { knopen, relaties } = voegSamen(delen);
  const per = new Map(knopen.map((k) => [k.id, k]));
  const pos = new Map<string, [number, number, number]>();
  const zet = (id: string, p: [number, number, number]) => { if (!pos.has(id)) pos.set(id, p); };
  const bevat = relaties.filter((r) => r.soort === "bevat");
  const kinderen = (id: string) => bevat.filter((r) => r.bron === id).map((r) => r.doel);
  const ouder = (id: string) => bevat.find((r) => r.doel === id)?.bron;
  const OPENING = Math.PI / 6;                   // halve opening bovenin de ring, voor de structuur
  const STRAAL = [0, 150, 230, 290, 340];
  const straal = (diepte: number) => STRAAL[Math.min(diepte, STRAAL.length - 1)];
  const punt = (r: number, hoek: number, z = 0): [number, number, number] => [r * Math.sin(hoek), r * Math.cos(hoek), z];
  let klasseRij = 0;
  const klasseKolom: string[] = [];

  delen.forEach((deel, cluster) => {
    const dx = cluster * 760;
    const verschuif = ([x, y, z]: [number, number, number]): [number, number, number] => [x + dx, y, z];
    const art = deel.artikel_iri;
    const eigen = new Set(deel.knopen.map((k) => k.id));
    // Structuur boven het artikel: links naast de ring, op middenhoogte en oplopend. Daar ligt
    // geen sector van leden, onderdelen of markeringen – welk lid ook onderdelen heeft. Het canvas is
    // breed; breedte kost minder schaal dan hoogte.
    let stap = 0;
    for (let id = ouder(art); id; id = ouder(id)) { stap++; zet(id, verschuif([-440 - 30 * stap, 55 * (stap - 1), -30 * stap])); }
    zet(art, verschuif([0, 0, 0]));

    // Wat aan een fragment hangt (markeringen, verwijzingen) telt mee in het gewicht van zijn sector.
    const markeringen = deel.knopen.filter((k) => k.soort === "markering");
    const ankerVan = (m: string) => relaties.find((r) => r.bron === m && r.soort === "markeert")?.doel ?? art;
    const rand = deel.knopen.filter((k) => k.rand);
    const randAnker = (k: string) => {
      const r = relaties.find((r) => r.soort === "verwijst_naar" && (r.bron === k || r.doel === k));
      const ander = r ? (r.bron === k ? r.doel : r.bron) : art;
      return eigen.has(ander) && !per.get(ander)?.rand ? ander : art;
    };
    const gewicht = new Map<string, number>();
    const tel = (id: string, w: number) => gewicht.set(id, (gewicht.get(id) ?? 0) + w);
    for (const m of markeringen) tel(ankerVan(m.id), 0.5);
    for (const k of rand) if (randAnker(k.id) !== art) tel(randAnker(k.id), 0.5);

    // Hoeksectoren: bladeren naar gewicht, een tak om het midden van zijn bladeren.
    const sector = new Map<string, [number, number]>();
    const bladgewicht = (id: string): number => {
      const k = kinderen(id);
      return (k.length ? k.reduce((s, c) => s + bladgewicht(c), 0) : 1) + (gewicht.get(id) ?? 0);
    };
    const verdeel = (id: string, van: number, tot: number, diepte: number) => {
      sector.set(id, [van, tot]);
      if (id !== art) zet(id, verschuif(punt(straal(diepte), (van + tot) / 2, diepte % 2 ? 0 : 18)));
      const k = kinderen(id);
      const totaal = k.reduce((s, c) => s + bladgewicht(c), 0) || 1;
      let hoek = van;
      for (const c of k) {
        const breedte = (tot - van) * bladgewicht(c) / totaal;
        verdeel(c, hoek, hoek + breedte, diepte + 1);
        hoek += breedte;
      }
    };
    verdeel(art, OPENING, 2 * Math.PI - OPENING, 0);
    const diepte = (id: string) => { let d = 0; for (let x = id; x && x !== art; x = ouder(x) ?? "") d++; return d; };

    // Buiten een fragment: markeringen op de eerste schil, verwijzingen op de tweede.
    const waaier = (ids: string[], anker: string, extra: number, z: number) => {
      const [van, tot] = sector.get(anker) ?? [0, 2 * Math.PI];
      const r = straal(diepte(anker)) + extra;
      ids.forEach((id, i) => zet(id, verschuif(punt(r + (i % 2) * 22, van + (tot - van) * (i + 1) / (ids.length + 1),
        z + ((i % 3) - 1) * 18))));
    };
    const perAnker = new Map<string, string[]>();
    for (const m of markeringen) perAnker.set(ankerVan(m.id), [...(perAnker.get(ankerVan(m.id)) ?? []), m.id]);
    for (const [anker, ids] of perAnker) {
      if (anker === art) waaier(ids, art, 70, 60);
      else waaier(ids, anker, 65, 25);
    }
    const randPerAnker = new Map<string, string[]>();
    for (const k of [...rand].sort((a, b) => a.id.localeCompare(b.id))) {
      const a = randAnker(k.id);
      randPerAnker.set(a, [...(randPerAnker.get(a) ?? []), k.id]);
    }
    for (const [anker, ids] of randPerAnker) {
      if (anker !== art) { waaier(ids, anker, 130, -30); continue; }
      // Naar of van het artikel als geheel: een ring áchter het artikel, per regeling bij elkaar.
      ids.forEach((id, i) => zet(id, verschuif(punt(270 + (i % 2) * 30, (2 * Math.PI * (i + 0.5)) / ids.length, -220))));
    }
    for (const k of deel.knopen.filter((k) => k.soort === "klasse")) if (!klasseKolom.includes(k.id)) klasseKolom.push(k.id);
  });
  // Klassen: één kolom rechts van het laatste cluster, om het midden verdeeld.
  const kolomX = (delen.length - 1) * 760 + 430;
  klasseKolom.forEach((id, i) => { zet(id, [kolomX, ((klasseKolom.length - 1) / 2 - i) * 55, klasseRij++ % 2 ? -30 : 30]); });

  const nodes = knopen.map((k): GraafKnoop => {
    const [x, y, z] = pos.get(k.id) ?? [0, 0, 0];
    const kleur = k.klasse ? klasseKleur(k.klasse) : k.rand ? (k.soort === "extern" ? BRONKLEUR.extern! : RANDKLEUR) : BRONKLEUR[k.soort] ?? "#398ab8";
    const label = k.soort === "lid" && k.lid && k.artikel ? `Artikel ${k.artikel} · lid ${k.lid}` : k.label;
    const kortLabel = k.soort === "lid" && k.lid && !k.rand ? `Lid ${k.lid}` : label;
    return { ...k, label, kort: kort(kortLabel), kleur, x, y, z, fx: x, fy: y, fz: z };
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
