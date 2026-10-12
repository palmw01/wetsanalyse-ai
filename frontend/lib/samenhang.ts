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

export async function haalSamenhang(doel: Pick<NodeDoel, "bron_iri">): Promise<Samenhang> {
  return nodeRequest(`samenhang?${new URLSearchParams({ bron_iri: doel.bron_iri })}`);
}

/** De samenhang van meerdere doelen in één verzoek – de delen van een overzicht. De api haalt per
 *  regeling één keer de bronboom op in plaats van per deel; een doel dat niet resolvet staat in
 *  `fouten`, de rest komt gewoon. Resultaten in de volgorde van de doelen. */
export async function haalSamenhangen(doelen: Pick<NodeDoel, "bron_iri">[]): Promise<{
  resultaten: Samenhang[]; fouten: { bron_iri: string; reden: string }[];
}> {
  // De api neemt hoogstens `MAX_SAMENHANG_MEER` doelen per verzoek en weigert anders het geheel; na
  // een paar keer "Open in het paneel" vanuit een overzicht zijn het er al meer. Dus in partijen, met
  // de uitkomst in de volgorde van de doelen.
  const partijen = await Promise.all(inPartijen(uniekeDoelen(doelen), MAX_SAMENHANG_MEER).map((partij) => {
    const params = new URLSearchParams(partij.map((d) => ["bron_iri", d.bron_iri]));
    return nodeRequest<{ resultaten: Samenhang[]; fouten: { bron_iri: string; reden: string }[] }>(`samenhang/meer?${params}`);
  }));
  return { resultaten: partijen.flatMap((p) => p.resultaten), fouten: partijen.flatMap((p) => p.fouten) };
}

/** Hoeveel doelen `/samenhang/meer` per verzoek aanneemt (`MAX_SAMENHANG_MEER` in
 *  api/app/annotatie_v2.py). */
export const MAX_SAMENHANG_MEER = 30;

/** Een reeks in opeenvolgende partijen van hoogstens `grootte`. */
export function inPartijen<T>(reeks: readonly T[], grootte: number): T[][] {
  const uit: T[][] = [];
  for (let i = 0; i < reeks.length; i += grootte) uit.push(reeks.slice(i, i + grootte));
  return uit;
}

/** Elk doel één keer, in de volgorde van eerste voorkomen (de api ontdubbelt ook, maar per partij). */
function uniekeDoelen<T extends Pick<NodeDoel, "bron_iri">>(doelen: readonly T[]): T[] {
  return doelen.filter((d, i) => doelen.findIndex((x) => x.bron_iri === d.bron_iri) === i);
}

let capabilities: Promise<boolean> | undefined;
/** Heeft de API het samenhang-endpoint? Eén keer per pagina gevraagd.
 *
 *  Alleen een ántwoord wordt onthouden. Een fout (een koude start, een deploy) betekent "nu even
 *  niet" – bleef die hangen, dan was de graaf de rest van de sessie weg tot een volledige
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
 *  opent "Bekijk in de graaf" een bronnode die niet bestaat. */
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

/** Is dit cluster een structuurdeel (hoofdstuk, afdeling …) in plaats van een artikel? */
export function isDeelCluster(d: Samenhang): boolean {
  return d.knopen.find((k) => k.id === d.artikel_iri)?.soort === "deel";
}

/** Wat de clusters zijn, voor de kop van de graaf: "8 artikelen", of bij een overzichtsantwoord
 *  "7 delen en 1 artikel" (een deel – hoofdstuk, afdeling – toont de api met zijn artikelen). */
export function clusterOmschrijving(delen: readonly Samenhang[]): string {
  const n = delen.filter(isDeelCluster).length, m = delen.length - n;
  const stuk = (x: number, een: string, meer: string) => `${x} ${x === 1 ? een : meer}`;
  if (!n) return stuk(m, "artikel", "artikelen");
  return stuk(n, "deel", "delen") + (m ? ` en ${stuk(m, "artikel", "artikelen")}` : "");
}
