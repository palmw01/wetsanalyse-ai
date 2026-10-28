/** De bediening van de graaf: zoeken, de relaties van een knoop, de ene hoofdactie en het doel waarop
 *  het paneel opent. Pure functies over het model, getest zonder DOM. */
import type { NodeDoel, NodeWeergave } from "@/lib/annotatieNode";
import { iriSegment } from "@/lib/samenhang";
import { voegToe, type GraafModel, type KnoopData, type KnoopSoort, type RelatieData } from "./model";

export const SOORT_LABEL: Record<KnoopSoort, string> = {
  regeling: "Regeling", deel: "Structuur", artikel: "Artikel", lid: "Lid", onderdeel: "Onderdeel",
  markering: "Markering", klasse: "JAS-klasse", extern: "Niet-geïmporteerde bepaling", begrip: "Begrip",
};

const normaal = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("nl");
const RANG: Record<KnoopSoort, number> = { artikel: 0, lid: 1, onderdeel: 2, regeling: 3, deel: 3, begrip: 4, markering: 4, klasse: 5, extern: 6 };

/** Knopen die bij de zoekvraag passen, over het hele model (ook wat een laag verbergt): eerst wat met
 *  de vraag begint, dan wat hem bevat; daarbinnen geladen vóór rand, bronnen vóór markeringen en
 *  klassen, en op naam in natuurlijke volgorde (artikel 9 vóór artikel 10). */
export function zoekKnopen(g: GraafModel, vraag: string, max = 12): string[] {
  const v = normaal(vraag.trim());
  if (!v) return [];
  const treffers: { id: string; a: KnoopData; begint: boolean }[] = [];
  g.forEachNode((id, a) => {
    const tekst = normaal(`${a.naam} ${a.klasse}`);
    if (tekst.includes(v)) treffers.push({ id, a, begint: tekst.startsWith(v) });
  });
  return treffers
    .sort((x, y) => Number(!x.begint) - Number(!y.begint) || Number(x.a.rand) - Number(y.a.rand)
      || RANG[x.a.soort] - RANG[y.a.soort] || x.a.naam.localeCompare(y.a.naam, "nl", { numeric: true }))
    .slice(0, max).map((t) => t.id);
}

export type RelatieGroepNaam = "Onderdeel van" | "Bevat" | "Markeringen" | "Markeert" | "Klasse" | "Verwijst naar" | "Wordt verwezen door"
  | "Begrippen" | "Dragende passages" | "Relaties met begrippen" | "Voorgestelde relaties";
export interface RelatieRegel { id: string; anker_tekst: string }

const UIT: Record<RelatieData["soort"], RelatieGroepNaam> = {
  bevat: "Bevat", verwijst_naar: "Verwijst naar", markeert: "Markeert", heeft_klasse: "Klasse",
  duidt: "Dragende passages", begripsrelatie: "Relaties met begrippen", begripsvoorstel: "Voorgestelde relaties",
};
const IN: Record<RelatieData["soort"], RelatieGroepNaam> = {
  bevat: "Onderdeel van", verwijst_naar: "Wordt verwezen door", markeert: "Markeringen", heeft_klasse: "Markeringen",
  duidt: "Begrippen", begripsrelatie: "Relaties met begrippen", begripsvoorstel: "Voorgestelde relaties",
};
const VOLGORDE: RelatieGroepNaam[] = ["Onderdeel van", "Bevat", "Begrippen", "Markeringen", "Markeert", "Klasse",
  "Dragende passages", "Relaties met begrippen", "Voorgestelde relaties", "Verwijst naar", "Wordt verwezen door"];

/** De relaties van een knoop, per soort en richting, in vaste volgorde. Over het hele model: een buur
 *  die een laag verbergt staat er ook in, zodat je hem vanuit de inspector kunt kiezen. */
export function relatieGroepen(g: GraafModel, id: string): { naam: RelatieGroepNaam; regels: RelatieRegel[] }[] {
  if (!g.hasNode(id)) return [];
  const groepen = new Map<RelatieGroepNaam, RelatieRegel[]>();
  const voeg = (naam: RelatieGroepNaam, ander: string, anker_tekst: string) => voegToe(groepen, naam, { id: ander, anker_tekst });
  g.forEachOutEdge(id, (_, a, __, doel) => voeg(UIT[a.soort], doel, a.anker_tekst));
  g.forEachInEdge(id, (_, a, bron) => voeg(IN[a.soort], bron, a.anker_tekst));
  const opNaam = (x: RelatieRegel, y: RelatieRegel) =>
    g.getNodeAttribute(x.id, "naam").localeCompare(g.getNodeAttribute(y.id, "naam"), "nl", { numeric: true });
  return VOLGORDE.filter((n) => groepen.has(n)).map((naam) => ({ naam, regels: groepen.get(naam)!.sort(opNaam) }));
}

/** De ene handeling die bij een knoop het meest voor de hand ligt.
 *
 *  - `tekst` – een bron of markering in de bepaling die het paneel toont: *Toon in tekst*;
 *  - `wissel` – een bron uit een ánder geladen artikel: het paneel opent op dat artikel;
 *  - `laden` – een bepaling buiten wat geladen is (rand), die in de kennisgraaf staat: erbij laden;
 *  - `null` – een klasse (staat al met haar markeringen in beeld), een niet-geïmporteerde bepaling of
 *    een regeling buiten het paneel. */
export type Hoofdactie = "tekst" | "wissel" | "laden" | null;

export function hoofdactie(a: Pick<KnoopData, "soort" | "rand" | "bwb_id">, id: string, inPaneel?: ReadonlySet<string>): Hoofdactie {
  if (a.soort === "klasse" || a.soort === "extern" || a.soort === "begrip") return null;
  if (a.rand) return a.bwb_id ? "laden" : null;
  if (inPaneel && !inPaneel.has(id)) return a.soort === "regeling" ? null : "wissel";
  return "tekst";
}

/** Hoort deze knoop bij de weergave die het paneel toont? Het paneel toont zijn doel (vaak één lid),
 *  niet het hele artikel dat de graaf laadt: een bron hoort erbij als hij het doel is, er een segment
 *  van is of een IRI eronder heeft (leden en onderdelen onder hun artikel); een markering als zij in
 *  de elementen van de weergave staat. Zonder model: een artikel hangt in de IRI niet onder zijn
 *  hoofdstuk – daarvoor is `knopenInWeergave`. */
export function hoortBijWeergave(id: string, w: Pick<NodeWeergave, "doel" | "segmenten" | "elementen">): boolean {
  if (id.startsWith("element:")) return w.elementen.some((e) => `element:${e.id}` === id);
  const doel = w.doel.bron_iri;
  return id === doel || id.startsWith(`${doel}:`) || w.segmenten.some((s) => s.bron_iri === id);
}

/** De knopen van het model die het paneel als tekst kan tonen: `hoortBijWeergave`, plus alles wat het
 *  doel in de opbouw bevat (`bevat`) – bij een hoofdstuk zijn artikelen. */
export function knopenInWeergave(g: GraafModel, w: Pick<NodeWeergave, "doel" | "segmenten" | "elementen">): Set<string> {
  const uit = new Set(g.filterNodes((id) => hoortBijWeergave(id, w)));
  const stapel = g.hasNode(w.doel.bron_iri) ? [w.doel.bron_iri] : [];
  while (stapel.length) {
    const id = stapel.pop()!;
    uit.add(id);
    g.forEachOutEdge(id, (_, a, __, doel) => { if (a.soort === "bevat" && !uit.has(doel)) stapel.push(doel); });
  }
  return uit;
}

/** Het doel waarop het paneel opent voor een knoop: de bronnode zelf, of voor een markering het
 *  artikel waarin ze staat. */
export function paneelDoel(id: string, a: Pick<KnoopData, "bwb_id" | "artikel" | "naam">): NodeDoel | undefined {
  if (id.startsWith("urn:bwb:")) return { bron_iri: id, bwb_id: a.bwb_id, label: a.naam };
  if (a.bwb_id && a.artikel) {
    return { bron_iri: `urn:bwb:${a.bwb_id}:artikel:${iriSegment(a.artikel)}`, bwb_id: a.bwb_id, artikel: a.artikel, label: `Artikel ${a.artikel}` };
  }
  return undefined;
}

export interface Telling { regelingen: number; bepalingen: number; markeringen: number; verwijzingen: number; begrippen?: number }

/** Wat er geladen is, voor de kop en de inspector zonder keuze. Randbepalingen tellen niet mee. */
export function telling(g: GraafModel): Telling {
  const t: Telling = { regelingen: 0, bepalingen: 0, markeringen: 0, verwijzingen: 0, begrippen: 0 };
  g.forEachNode((_, a) => {
    if (a.rand) return;
    if (a.soort === "regeling") t.regelingen++;
    else if (a.soort === "markering") t.markeringen++;
    else if (a.soort === "begrip") t.begrippen!++;
    else if (a.soort === "artikel" || a.soort === "lid" || a.soort === "onderdeel") t.bepalingen++;
  });
  g.forEachEdge((_, a) => { if (a.soort === "verwijst_naar") t.verwijzingen++; });
  return t;
}

const getal = new Intl.NumberFormat("nl-NL");
/** "2 regelingen · 1.240 bepalingen · 85 markeringen · 3.488 verwijzingen", zonder de nullen. */
export function tellingTekst(t: Telling): string {
  const deel = (n: number, een: string, meer: string) => (n ? `${getal.format(n)} ${n === 1 ? een : meer}` : "");
  return [deel(t.regelingen, "regeling", "regelingen"), deel(t.bepalingen, "bepaling", "bepalingen"),
    deel(t.markeringen, "markering", "markeringen"), deel(t.begrippen ?? 0, "begrip", "begrippen"),
    deel(t.verwijzingen, "verwijzing", "verwijzingen")].filter(Boolean).join(" · ");
}
