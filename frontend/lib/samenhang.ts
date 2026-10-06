import { forceLink, forceManyBody, forceSimulation } from "d3-force-3d";
import { jasStyle } from "./jas";
import { veiligDecoderen } from "./url";
import { nodeRequest, type NodeDoel } from "./annotatieNode";

/** Het antwoord van `GET /v1/annotatie/samenhang` (api/app/samenhang.py). */
export type KnoopSoort = "regeling" | "deel" | "artikel" | "lid" | "onderdeel" | "markering" | "klasse" | "extern";
export type RelatieGroep = "structuur" | "verwijzingen" | "annotaties";
export interface SamenhangKnoop {
  id: string; soort: KnoopSoort; label: string; tekst: string; klasse: string; lifecycle: string;
  element_id: string; bwb_id: string; artikel: string; lid: string; rand: boolean;
  /** Alleen bij een markering (api ≥ PR 10; bij een oudere api ontbreken ze). */
  herkomst?: string; aandacht?: string; subtype?: string; beslist_door?: string; twijfel?: boolean;
}

/** Welke markeringen in beeld blijven. Een kijkfilter: hij verbergt markeringen (en klassen die
 *  dan niets meer markeren), nooit bronstructuur of verwijzingen. */
export type MarkeringFilter = "alle" | "te_beoordelen" | "aandacht" | "jurist" | "twijfel";
export const MARKERING_FILTERS: { waarde: MarkeringFilter; label: string }[] = [
  { waarde: "alle", label: "alle" },
  { waarde: "te_beoordelen", label: "nog te beoordelen" },
  { waarde: "aandacht", label: "keuze voor de jurist (geel)" },
  { waarde: "jurist", label: "door een jurist gemarkeerd" },
  { waarde: "twijfel", label: "met twijfel in het spoor" },
];
export function pastBijMarkeringFilter(k: Pick<SamenhangKnoop, "lifecycle" | "aandacht" | "herkomst" | "twijfel">, f: MarkeringFilter): boolean {
  switch (f) {
    case "te_beoordelen": return k.lifecycle === "voorgesteld";
    case "aandacht": return k.aandacht === "geel";
    case "jurist": return k.herkomst === "mens";
    case "twijfel": return !!k.twijfel;
    default: return true;
  }
}
export interface SamenhangRelatie {
  bron: string; doel: string; soort: "bevat" | "verwijst_naar" | "markeert" | "heeft_klasse";
  groep: RelatieGroep; anker_tekst: string;
}
export interface Samenhang {
  schema_versie: 1; doel: NodeDoel; snapshot_id: string; artikel_iri: string;
  knopen: SamenhangKnoop[]; relaties: SamenhangRelatie[]; verwijzingen_beschikbaar: boolean; afgekapt: boolean;
}

/** Wat de canvas tekent. De posities komen uit een krachtlayout die hier – niet in de canvas – wordt
 *  gerekend en daarna vastligt: zo springt er niets bij uitklappen of filteren. */
export interface GraafKnoop extends SamenhangKnoop {
  kort: string; kleur: string; straal: number; x: number; y: number; z: number; fx: number; fy: number; fz: number;
}
export interface GraafRelatie {
  id: string; source: string; target: string; label: string; soort: SamenhangRelatie["soort"];
  groep: RelatieGroep; anker_tekst: string;
}
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
/** Heeft de API het samenhang-endpoint? Eén keer per pagina gevraagd.
 *
 *  Alleen een ántwoord wordt onthouden. Een fout (een koude start, een deploy) betekent "nu even
 *  niet" – bleef die hangen, dan was de 3D-weergave de rest van de sessie weg tot een volledige
 *  herlaadbeurt. Bij een fout vraagt de volgende aanroep het dus opnieuw. */
export function samenhangBeschikbaar(): Promise<boolean> {
  capabilities ??= nodeRequest<{ samenhang?: boolean }>("capabilities")
    .then((c) => Boolean(c.samenhang))
    .catch(() => {
      capabilities = undefined;
      return false;
    });
  return capabilities;
}

const BWB = /^BWB[RV]\d+$/;
const PADSLEUTELS = new Set(["hoofdstuk", "titeldeel", "afdeling", "paragraaf", "artikel", "lid", "o"]);

/** De bronnode van een verwijzing (graaf-IRI, jci of kaal BWB-id): de spiegel van
 *  `bronmodel.vindplaats` (packages/bronmodel). `soort` is `regeling`, een structuursoort, `artikel`,
 *  `lid`, `onderdeel` of `node` (een wet-lokale `id:`-IRI, zonder label). De vectoren in
 *  `jci-vectoren.json` toetsen beide kanten. */
export interface Vindplaats { bron_iri: string; bwb_id: string; pad: [string, string][]; soort: string; label: string }

export function vindplaatsVan(uri: string): Vindplaats | undefined {
  const ref = uri.trim().replace(/[.,;\\]+$/, "");
  let bwb = "", paren: [string, string][] = [];
  if (BWB.test(ref)) return { bron_iri: `urn:bwb:${ref}`, bwb_id: ref, pad: [], soort: "regeling", label: "" };
  if (ref.startsWith("urn:bwb:")) {
    // Veilig decoderen: dit draait tijdens het renderen van een antwoord, en één kapotte IRI uit de
    // tool-trace mag de werkplek niet onderuit halen.
    const delen = ref.slice("urn:bwb:".length).split(":").map(veiligDecoderen);
    if (delen.some((d) => d === undefined)) return undefined;
    const [id, ...rest] = delen as string[];
    if (!BWB.test(id) || rest.length % 2 || rest.some((d) => !d)) return undefined;
    bwb = id;
    for (let i = 0; i < rest.length; i += 2) paren.push([rest[i], rest[i + 1]]);
    if (paren.some(([k]) => k === "id")) return { bron_iri: ref, bwb_id: bwb, pad: paren, soort: "node", label: "" };
    if (paren.some(([k]) => !PADSLEUTELS.has(k))) return undefined;
  } else if (/^jci/i.test(ref)) {
    const m = ref.match(/^jci[\d.]+:c:(BWB[RV]\d+)(.*)$/i);
    if (!m) return undefined;
    bwb = m[1].toUpperCase();
    const ruw = [...new URLSearchParams(m[2].replace(/^&?/, ""))]
      .map(([k, v]) => [k.toLowerCase(), v] as [string, string]).filter(([k]) => k !== "z" && k !== "g");
    if (ruw.some(([, v]) => !v)) return undefined;
    paren = jciPad(ruw);
    // Alleen `&bijlage=1&o=a`: geen artikel en geen structuur, dus geen eigen node.
    if (ruw.length && !paren.length) return undefined;
  } else return undefined;
  const soort = paren.length ? (paren.at(-1)![0] === "o" ? "onderdeel" : paren.at(-1)![0]) : "regeling";
  return {
    bron_iri: `urn:bwb:${bwb}` + paren.map(([k, v]) => `:${k}:${iriSegment(v)}`).join(""),
    bwb_id: bwb, pad: paren, soort, label: vindplaatsLabel(paren),
  };
}

/** Een bron onder een antwoord (graaf-IRI of jci) als bronnode; de spiegel van `uitGraafIri` in
 *  `lib/url.ts`. Alleen een bepaling ónder een regeling telt: bij een hele wet is er geen artikel. */
export function bronDoel(uri: string): NodeDoel | undefined {
  const vp = vindplaatsVan(uri);
  if (!vp || vp.soort === "regeling" || vp.soort === "node") return undefined;
  const waarde = Object.fromEntries(vp.pad);
  return { bron_iri: vp.bron_iri, bwb_id: vp.bwb_id, artikel: waarde.artikel, lid: waarde.lid, label: vp.label || undefined };
}

/** Het leesbare label van een bronpad: "Artikel 2, lid 1, onderdeel aa, 1", "Hoofdstuk VI, afdeling 1".
 *  Zelfde vorm als `vindplaats` in packages/bronmodel; de vectoren in `jci-vectoren.json` toetsen beide. */
export function vindplaatsLabel(paren: [string, string][]): string {
  const onderdelen = paren.filter(([k]) => k === "o").map(([, v]) => v);
  const delen = paren.filter(([k]) => k !== "o").map(([k, v]) => `${k} ${v}`);
  if (onderdelen.length) delen.push(`onderdeel ${onderdelen.join(", ")}`);
  const tekst = delen.join(", ");
  return tekst.charAt(0).toUpperCase() + tekst.slice(1);
}

const STRUCTUUR = new Set(["hoofdstuk", "titeldeel", "afdeling", "paragraaf"]);

/** Het pad van een jci zoals de importer het als node-identiteit gebruikt
 *  (`jci_node_ref_key` in tools/bwb-import/app/references.py):
 *
 *  - met een artikel: `artikel` (het laatste), `lid` (het laatste) en elke `o` – het structuurpad
 *    ernaartoe hoort er níét in, want een artikel is binnen de regeling al uniek;
 *  - zonder artikel: het volledige structuurpad (hoofdstuk, titeldeel, afdeling, paragraaf),
 *    want "afdeling 1" komt in elk hoofdstuk terug.
 *
 *  De vectoren in `lib/jci-vectoren.json` toetsen beide kanten; wijkt dit af van de importer, dan
 *  opent "Bekijk samenhang in 3D" een bronnode die niet bestaat. */
function jciPad(paren: [string, string][]): [string, string][] {
  const laatste = (k: string) => paren.filter(([n]) => n === k).at(-1)?.[1];
  const artikel = laatste("artikel");
  if (artikel) {
    const lid = laatste("lid");
    return [["artikel", artikel], ...(lid ? [["lid", lid] as [string, string]] : []),
      ...paren.filter(([n]) => n === "o")];
  }
  return paren.filter(([n]) => STRUCTUUR.has(n));
}

/** Een waarde als IRI-segment, zoals de importer hem schrijft (`quote(s, safe="")`): een `:` in
 *  een Awb-artikelnummer ("3:40") wordt `%3A`, anders leest hij als een extra segment. */
export function iriSegment(waarde: string): string {
  return encodeURIComponent(waarde).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
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

/** Startposities per artikelcluster, radiaal: het artikel in het midden, leden in een ring en
 *  onderdelen verder naar buiten in het verlengde van hun lid (elk blad een eigen hoeksector naar
 *  gewicht), markeringen net buiten hun fragment, klassen in een kolom rechts. De structuur erboven
 *  (regeling, hoofdstuk) staat boven-achter het artikel; daarvoor blijft bovenin de ring een opening.
 *  Verwijzingen van of naar een lid staan buiten dat lid; verwijzingen naar het artikel als geheel
 *  – vaak de grootste groep – op een eigen ring áchter het artikel, zodat ze de leden niet bedekken.
 *  Afstand en positie betekenen juridisch niets; ze houden de kaart herkenbaar en leesbaar. */
function startposities(delen: Samenhang[]): Map<string, [number, number, number]> {
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
    // Klassen: een kolom rechts van het cluster waarin ze voor het eerst voorkomen. Niet afhankelijk
    // van het aantal clusters, anders zou bijladen de startstand van eerdere clusters veranderen.
    const nieuw = deel.knopen.filter((k) => k.soort === "klasse" && !pos.has(k.id));
    nieuw.forEach((k, i) => zet(k.id, verschuif([260, ((nieuw.length - 1) / 2 - i) * 55, i % 2 ? -30 : 30])));
  });

  return pos;
}

/** Straal per soort: de bron draagt het beeld, markeringen en verwijzingen zijn kleiner. */
const STRAAL_PER_SOORT: Record<KnoopSoort, number> = {
  artikel: 9, regeling: 7.5, deel: 6.5, lid: 6, klasse: 6.5, onderdeel: 4.5, markering: 4, extern: 3.5,
};
/** Rustafstand en stijfheid per relatie: structuur kort en stug, verwijzingen lang en los. */
const VEER: Record<SamenhangRelatie["soort"], [number, number]> = {
  bevat: [45, 0.9], markeert: [30, 0.8], heeft_klasse: [55, 0.35], verwijst_naar: [100, 0.35],
};

/** Deterministische diepte uit een id: het startpunt krijgt reliëf, zodat de krachten in drie
 *  dimensies uitwaaieren in plaats van in het vlak te blijven. */
function reliëf(id: string): number {
  let h = 2166136261;
  for (const c of id) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return ((h >>> 0) % 121) - 60;
}

type SimKnoop = { id: string; x: number; y: number; z: number; fx?: number; fy?: number; fz?: number };

/** De samenhang als 3D-graaf. Vaste startposities (radiaal per artikelcluster, zie hierboven) plus
 *  reliëf, daarna een krachtsimulatie per cluster met dezelfde engine als de renderer (d3-force-3d).
 *  Al geplaatste knopen van eerdere clusters liggen daarbij vast, zodat bijladen de bestaande kaart
 *  niet verschuift, en met `vast` (de vorige stand) behouden bestaande knopen hun plek na een
 *  annotatiewijziging. Zonder willekeur (d3 gebruikt een vaste lcg) is de uitkomst reproduceerbaar.
 *  Afstand en positie betekenen juridisch niets. */
export function bouwGraaf(delen: Samenhang[], vast?: GraafData): GraafData {
  const { knopen, relaties } = voegSamen(delen);
  const per = new Map(knopen.map((k) => [k.id, k]));
  const start = startposities(delen);
  // Knopen uit een vorige stand (na een annotatiewijziging) houden hun plek; alleen wat nieuw is,
  // wordt door de krachten geplaatst. Zo springt de kaart niet bij elke markering.
  const eerder = new Map((vast?.nodes ?? []).filter((n) => per.has(n.id)).map((n) => [n.id, [n.x, n.y, n.z] as [number, number, number]]));
  const geplaatst = new Map<string, [number, number, number]>(eerder);
  delen.forEach((deel, cluster) => {
    const ids = new Set(deel.knopen.map((k) => k.id));
    const sim: SimKnoop[] = [...ids].filter((id) => per.has(id)).map((id) => {
      const plek = geplaatst.get(id);
      if (plek) return { id, x: plek[0], y: plek[1], z: plek[2], fx: plek[0], fy: plek[1], fz: plek[2] };
      const [x, y, z] = start.get(id) ?? [0, 0, 0];
      // Het artikel van dit cluster is het anker; de rest schikt zich eromheen.
      return id === deel.artikel_iri
        ? { id, x, y, z, fx: x, fy: y, fz: z }
        : { id, x, y, z: z + reliëf(id) };
    });
    // Alleen de eigen relaties van dit cluster: een later bijgeladen artikel mag de simulatie van een
    // eerder cluster niet veranderen.
    const links = deel.relaties.filter((r) => ids.has(r.bron) && ids.has(r.doel))
      .map((r) => ({ source: r.bron, target: r.doel, soort: r.soort }));
    // Niets nieuw in dit cluster: de vorige stand is de uitkomst, zonder simulatie.
    if (sim.every((n) => n.fx !== undefined)) return;
    forceSimulation(sim, 3)
      .force("link", forceLink<SimKnoop, (typeof links)[number]>(links).id((n) => n.id)
        .distance((l) => VEER[l.soort][0]).strength((l) => VEER[l.soort][1]))
      .force("charge", forceManyBody().strength(-140).distanceMax(420))
      .stop()
      .tick(cluster === 0 ? 300 : 220);
    for (const n of sim) if (!geplaatst.has(n.id)) geplaatst.set(n.id, [n.x, n.y, n.z]);
  });

  const nodes = knopen.map((k): GraafKnoop => {
    const [x, y, z] = geplaatst.get(k.id) ?? start.get(k.id) ?? [0, 0, 0];
    const kleur = k.klasse ? klasseKleur(k.klasse) : k.rand ? (k.soort === "extern" ? BRONKLEUR.extern! : RANDKLEUR) : BRONKLEUR[k.soort] ?? "#398ab8";
    const label = k.soort === "lid" && k.lid && k.artikel ? `Artikel ${k.artikel} · lid ${k.lid}` : k.label;
    const kortLabel = k.soort === "lid" && k.lid && !k.rand ? `Lid ${k.lid}` : label;
    const straal = k.rand ? 3.5 : STRAAL_PER_SOORT[k.soort];
    return { ...k, label, kort: kort(kortLabel), kleur, straal, x, y, z, fx: x, fy: y, fz: z };
  });
  const links = relaties.filter((r) => per.has(r.bron) && per.has(r.doel)).map((r) => ({
    id: `${r.bron}|${r.soort}|${r.doel}`, source: r.bron, target: r.doel, label: RELATIE_LABEL[r.soort],
    soort: r.soort, groep: r.groep, anker_tekst: r.anker_tekst,
  }));
  return { nodes, links };
}

/** Filters veranderen alleen zichtbaarheid. Altijd zichtbaar: de bronstructuur van de geopende
 *  artikelen en – met de laag Annotaties aan – hun markeringen met JAS-klasse; wie het rustiger wil
 *  zet die laag uit. Verwijzingen naar buiten verschijnen pas als je een knoop uitklapt. */
export function zichtbareGraaf(data: GraafData, uitgebreid: string[], filters: Record<RelatieGroep, boolean>,
  markering: MarkeringFilter = "alle"): GraafData {
  const zichtbaar = new Set(data.nodes.filter((n) => !n.rand).map((n) => n.id));
  for (const id of uitgebreid) {
    zichtbaar.add(id);
    for (const edge of data.links) {
      if (!filters[edge.groep]) continue;
      if (edge.source === id) zichtbaar.add(edge.target);
      if (edge.target === id) zichtbaar.add(edge.source);
    }
  }
  // Markeringen die buiten het filter vallen, en klassen die dan niets meer markeren, verdwijnen.
  const weg = new Set(data.nodes.filter((n) => n.soort === "markering" && !pastBijMarkeringFilter(n, markering)).map((n) => n.id));
  if (weg.size) {
    const nogGemarkeerd = new Set(data.links.filter((e) => e.soort === "heeft_klasse" && !weg.has(e.source)).map((e) => e.target));
    for (const n of data.nodes) if (n.soort === "klasse" && !nogGemarkeerd.has(n.id)) weg.add(n.id);
  }
  const nodes = data.nodes.filter((n) => zichtbaar.has(n.id) && !weg.has(n.id)
    && (filters.annotaties || !["klasse", "markering"].includes(n.soort))
    && (filters.verwijzingen || !n.rand));
  const ids = new Set(nodes.map((n) => n.id));
  return { nodes, links: data.links.filter((e) => filters[e.groep] && ids.has(e.source) && ids.has(e.target)) };
}

/** Kan deze knoop als eigen artikel worden bijgeladen? Alleen een geïmporteerde randbepaling. */
export function uitklapbaar(knoop: Pick<SamenhangKnoop, "rand" | "soort" | "bwb_id">): boolean {
  return knoop.rand && knoop.soort !== "extern" && Boolean(knoop.bwb_id);
}

// ── Bediening: pure functies achter zoeken, inspector en dubbelklik (getest zonder DOM) ──────────

const normaal = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("nl");

/** Knopen die bij de zoekvraag passen, over de hele graaf (ook verborgen): eerst wat met de vraag
 *  begint, dan wat hem bevat; daarbinnen het eigen artikel vóór randknopen, en bronnen vóór
 *  markeringen en klassen. */
export function zoekKnopen(graaf: GraafData, vraag: string, max = 12): GraafKnoop[] {
  const v = normaal(vraag.trim());
  if (!v) return [];
  const rang: Record<KnoopSoort, number> = { artikel: 0, lid: 1, onderdeel: 2, regeling: 3, deel: 3, markering: 4, klasse: 5, extern: 6 };
  return graaf.nodes
    .map((n) => ({ n, tekst: normaal(`${n.label} ${n.klasse}`) }))
    .filter(({ tekst }) => tekst.includes(v))
    .sort((a, b) => Number(!a.tekst.startsWith(v)) - Number(!b.tekst.startsWith(v)) || Number(a.n.rand) - Number(b.n.rand)
      || rang[a.n.soort] - rang[b.n.soort] || a.n.label.localeCompare(b.n.label, "nl", { numeric: true }))
    .slice(0, max).map(({ n }) => n);
}

export type RelatieGroepNaam = "Bevat" | "Onderdeel van" | "Verwijst naar" | "Wordt verwezen door" | "Markeringen" | "Markeert" | "Klasse";
export interface RelatieRegel { knoop: GraafKnoop; anker_tekst: string }

/** De relaties van een knoop, per soort en richting, over de héle graaf: een verborgen buur staat
 *  er ook in, zodat je hem vanuit de inspector kunt kiezen. */
export function relatieGroepen(graaf: GraafData, id: string): { naam: RelatieGroepNaam; regels: RelatieRegel[] }[] {
  const per = new Map(graaf.nodes.map((n) => [n.id, n]));
  const groepen = new Map<RelatieGroepNaam, RelatieRegel[]>();
  const voeg = (naam: RelatieGroepNaam, ander: string, anker_tekst: string) => {
    const knoop = per.get(ander);
    if (knoop) groepen.set(naam, [...(groepen.get(naam) ?? []), { knoop, anker_tekst }]);
  };
  for (const l of graaf.links) {
    if (l.source === id) voeg(({ bevat: "Bevat", verwijst_naar: "Verwijst naar", markeert: "Markeert", heeft_klasse: "Klasse" } as const)[l.soort], l.target, l.anker_tekst);
    else if (l.target === id) voeg(({ bevat: "Onderdeel van", verwijst_naar: "Wordt verwezen door", markeert: "Markeringen", heeft_klasse: "Markeringen" } as const)[l.soort], l.source, l.anker_tekst);
  }
  const volgorde: RelatieGroepNaam[] = ["Onderdeel van", "Bevat", "Markeringen", "Markeert", "Klasse", "Verwijst naar", "Wordt verwezen door"];
  return volgorde.filter((n) => groepen.has(n)).map((naam) => ({ naam, regels: groepen.get(naam)! }));
}

export type Hoofdactie = "tekst" | "openen" | "wissel" | null;
/** De ene handeling die bij deze knoop het meest voor de hand ligt. `inPaneel` zijn de knopen van het
 *  artikel dat het paneel als tekst toont: een knoop uit een ánder geladen artikel (bijgeladen, of
 *  meegeopend vanuit een antwoord) kan daar niet in de tekst getoond worden; die opent het paneel
 *  op zijn eigen artikel ("wissel"). Zonder `inPaneel` is elke knoop "tekst", zoals voorheen. */
export function hoofdactie(knoop: Pick<GraafKnoop, "soort" | "rand" | "bwb_id" | "id">, geopend: string[],
  inPaneel?: ReadonlySet<string>): Hoofdactie {
  // Een klasse staat al met haar markeringen in beeld (laag Annotaties); daar valt niets te openen.
  if (knoop.soort === "klasse") return null;
  if (knoop.rand) return uitklapbaar(knoop) && !geopend.includes(knoop.id) ? "openen" : null;
  if (knoop.soort === "extern") return null;
  if (inPaneel && !inPaneel.has(knoop.id)) return knoop.soort === "regeling" ? null : "wissel";
  return "tekst";
}

/** Het doel waarop het paneel opent voor een knoop uit de graaf: de bronnode zelf, of voor een
 *  markering het artikel waarin hij staat. */
export function paneelDoel(knoop: Pick<GraafKnoop, "id" | "bwb_id" | "artikel" | "label">): NodeDoel | undefined {
  if (knoop.id.startsWith("urn:bwb:")) return { bron_iri: knoop.id, bwb_id: knoop.bwb_id, label: knoop.label };
  if (knoop.bwb_id && knoop.artikel) {
    return { bron_iri: `urn:bwb:${knoop.bwb_id}:artikel:${iriSegment(knoop.artikel)}`, bwb_id: knoop.bwb_id,
      artikel: knoop.artikel, label: `Artikel ${knoop.artikel}` };
  }
  return undefined;
}

/** Korte stand van zaken voor de inspector zonder selectie. */
export function samenvatting(graaf: GraafData): { leden: number; markeringen: number; verwijzingen: number } {
  return {
    leden: graaf.nodes.filter((n) => (n.soort === "lid" || n.soort === "onderdeel") && !n.rand).length,
    markeringen: graaf.nodes.filter((n) => n.soort === "markering").length,
    verwijzingen: graaf.links.filter((l) => l.soort === "verwijst_naar").length,
  };
}

/** Een tweede klik op dezelfde knoop binnen de drempel is een dubbelklik (de renderer kent alleen klik). */
export function isDubbelklik(vorige: { id: string; tijd: number } | null, id: string, tijd: number, drempel = 300): boolean {
  return !!vorige && vorige.id === id && tijd - vorige.tijd <= drempel;
}
