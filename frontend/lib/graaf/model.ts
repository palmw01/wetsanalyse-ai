/** Het graafmodel: één graphology-graaf uit wat de api levert, of dat nu de samenhang van één artikel
 *  is (`/samenhang`), de delen van een overzicht (`/samenhang/meer`) of de hele kennisgraaf (`/graaf`).
 *  Alle drie hebben dezelfde `Knoop`/`Relatie`-vorm (api/app/samenhang.py), dus er is één model.
 *
 *  Het model is pure data: geen posities, kleuren of zichtbaarheid. Posities komen uit de layout
 *  (`layout.ts`), het beeld uit de weergavestand (`weergave.ts`). Zo bouwt een wijziging in de
 *  annotaties het model opnieuw op zonder dat de kaart verschuift. */
import Graph from "graphology";
import type { SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";

export type { KnoopSoort, RelatieGroep, SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";

/** Een knoop zoals het model hem draagt: de data van de api plus de naam waaronder hij in beeld komt. */
export interface KnoopData extends SamenhangKnoop {
  /** De volledige naam (inspector, zoeken, tooltip): "Artikel 9 · lid 2", "Hoofdstuk II". */
  naam: string;
  /** Het label op de kaart: bij een lid binnen zijn artikel volstaat "Lid 2". */
  kort: string;
}
export interface RelatieData {
  soort: SamenhangRelatie["soort"];
  groep: SamenhangRelatie["groep"];
  anker_tekst: string;
}
export type GraafModel = Graph<KnoopData, RelatieData>;

/** Wat de api levert, ongeacht het endpoint. */
export interface GraafBron {
  knopen: SamenhangKnoop[];
  relaties: SamenhangRelatie[];
}

/** Het antwoord van `GET /v1/annotatie/graaf` (api/app/graaf.py). */
export interface KennisgraafAntwoord extends GraafBron {
  schema_versie: 1;
  /** Hash van de regelingtoestanden: verandert alleen bij een herimport. Sleutel van de layoutcache. */
  versie: string;
  regelingen: { bwb_id: string; citeertitel: string; toestand: string }[];
}

export const relatieSleutel = (r: Pick<SamenhangRelatie, "bron" | "soort" | "doel">) => `${r.bron}|${r.soort}|${r.doel}`;

const KORT_MAX = 27;
const inkorten = (tekst: string) => (tekst.length > KORT_MAX ? tekst.slice(0, KORT_MAX - 2) + "…" : tekst);

/** Naam en kaartlabel. De api geeft een deel al met zijn nummer ("Hoofdstuk II") en een regeling met
 *  haar citeertitel; alleen een lid krijgt hier zijn artikel erbij, want "Lid 2" zegt los niets. */
export function namen(k: SamenhangKnoop): Pick<KnoopData, "naam" | "kort"> {
  const isLid = k.soort === "lid" && k.lid && k.artikel;
  const naam = isLid ? `Artikel ${k.artikel} · lid ${k.lid}` : k.label;
  return { naam, kort: inkorten(isLid && !k.rand ? `Lid ${k.lid}` : naam) };
}

/** Bouwt één model uit een of meer antwoorden. Een knoop die in het ene antwoord rand is (een
 *  bepaling buiten wat dat antwoord laadde) en in het andere niet, is geen rand: het geladen antwoord
 *  wint. Relaties ontdubbeld op bron, soort en doel; een relatie naar een knoop die er niet is, valt
 *  weg. Volgorde-onafhankelijk in de uitkomst: knopen en relaties staan gesorteerd, zodat dezelfde
 *  bronnen in een andere volgorde hetzelfde model geven (en dus dezelfde layout). */
export function bouwModel(bronnen: readonly GraafBron[]): GraafModel {
  const knopen = new Map<string, SamenhangKnoop>();
  const relaties = new Map<string, SamenhangRelatie>();
  for (const bron of bronnen) {
    for (const k of bron.knopen) {
      const oud = knopen.get(k.id);
      knopen.set(k.id, !oud ? k : oud.rand && !k.rand ? k : { ...oud, rand: oud.rand && k.rand });
    }
    for (const r of bron.relaties) relaties.set(relatieSleutel(r), r);
  }
  const g: GraafModel = new Graph({ type: "directed", multi: true, allowSelfLoops: true });
  for (const id of [...knopen.keys()].sort()) {
    const k = knopen.get(id)!;
    g.addNode(id, { ...k, ...namen(k) });
  }
  for (const sleutel of [...relaties.keys()].sort()) {
    const r = relaties.get(sleutel)!;
    if (!g.hasNode(r.bron) || !g.hasNode(r.doel)) continue;
    g.addDirectedEdgeWithKey(sleutel, r.bron, r.doel, { soort: r.soort, groep: r.groep, anker_tekst: r.anker_tekst ?? "" });
  }
  return g;
}

/** Een bronknoop (wettekst: regeling, deel, artikel, lid, onderdeel, extern) en geen annotatie. */
export const isBron = (k: Pick<SamenhangKnoop, "soort">) => k.soort !== "markering" && k.soort !== "klasse";

/** De ouder in de bronboom (`bevat`), of `undefined` voor een wortel of een randknoop. */
export function ouderVan(g: GraafModel, id: string): string | undefined {
  for (const e of g.inEdges(id)) if (g.getEdgeAttribute(e, "soort") === "bevat") return g.source(e);
  return undefined;
}

/** De bronknoop die een markering markeert (`markeert`). */
export function ankerVan(g: GraafModel, markering: string): string | undefined {
  for (const e of g.outEdges(markering)) if (g.getEdgeAttribute(e, "soort") === "markeert") return g.target(e);
  return undefined;
}
