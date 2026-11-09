import { downloadAntwoord, parseError, type ExportFormaat } from "./api";
import { RELATIETYPEN } from "./jasRelaties";
import { pathSegment } from "./url";

/** Canonieke bronnodeweergave. Posities zijn Unicode-codepunten, niet UTF-16. */
export interface NodeDoel {
  bron_iri: string; type?: string; label?: string; bwb_id?: string;
  artikel?: string; lid?: string; snapshot_id?: string; citeertitel?: string;
  /** De versie van de chip (`artefact.ref.versie`): de stand van de annotatie direct na die beurt van Lex. Geen
   *  onderdeel van de bronnode; alleen de versiekiezer leest hem. */
  versie?: string;
}
export interface NodeSegment {
  bron_iri: string; parent_iri?: string; type: string; label: string; nummer?: string;
  tekst: string; bron_hash: string; volgorde: number;
  /** `bwb:status`, geërfd van het artikel. `nogniet` staat in de regeling maar geldt nog niet. Een oudere snapshot heeft
   *  hem niet. */
  status?: string;
}
export interface NodeAnker { bron_iri: string; start: number; eind: number; tekst: string; bron_hash: string }
export interface NodeElement {
  id: string; eigenaar_iri: string; laag_id: string; klasse: string; tekst: string;
  toelichting: string; ankers: NodeAnker[]; lifecycle: string; herkomst: string;
  aangemaakt_door?: string; gewijzigd_door?: string;
  verouderd?: boolean; beslissingen?: import("./types").Beslissing[];
  alternatieven?: import("./types").Alternatief[];
  aandacht?: string | null; review_uitleg?: string;
  trace?: import("./types").ElementTrace; jas_subtype?: string;
  geproduceerd_door?: import("./types").AgentRun | null;
  provenance?: Partial<import("./types").AgentRun>;
}
/** Wat de annotatieketen per bronnode kon bekijken (graph-qa `jas_pipeline/dekking.py`, deel B):
 *  per detectiedimensie of ze draaide, en de zinsdelen waar geen enkele kandidaat uit kwam – offsets
 *  in codepoints binnen de bronnode. Een meting van de detectoren, geen recall. De api geeft per
 *  bronnode alleen de nieuwste meting die nog over dezelfde tekst gaat. */
export interface StructureleDekking {
  dimensies: Record<string, "uitgevoerd" | "gedeeltelijk" | "overgeslagen">;
  ongedekt: { tekst: string; start: number; eind: number }[];
  /** Per dimensie hoeveel kandidaten een hypothese voor haar klasse(n) droegen. Ontbreekt bij een
   *  oudere meting – dan is het onbekend, niet 0. */
  aangetroffen?: Record<string, number>;
  /** Zinsdelen die alleen geraakt werden door een kandidaat over het geheel: binnen de zin niets
   *  gevonden. Ontbreekt bij een oudere meting. */
  alleen_als_geheel?: { tekst: string; start: number; eind: number }[];
}
export interface NodeDekking {
  voltooid?: boolean;
  bereik?: string[];
  structureel?: Record<string, StructureleDekking>;
}
export interface NodeLaag { id: string; bron_iri: string; revisie: number; status: string }
/** Eén kant van een relatie, zoals de api hem vraagt (ADR-011): een markering of een impliciete partij. */
export interface NodeEindpuntRef { soort: "element" | "impliciet"; id: string }
/** Een kant van een relatie zoals de weergave hem toont (`beschrijf` in `api/app/annotatie_v2_relaties.py`). Een
 *  element mag in een andere laag liggen; `bestaat: false` als het weg is. */
export interface NodeEindpunt extends NodeEindpuntRef {
  bestaat: boolean; klasse?: string; tekst?: string; laag_id?: string; actueel?: boolean;
}
/** Een relatie tussen twee markeringen. Ze hoort bij de laag van de drager (`laag_id`); `veranderd` zegt dat een
 *  eindpunt afwijkt van hoe het was toen de relatie werd vastgelegd of beoordeeld. */
export interface NodeRelatie {
  id: string; type: string; leesvorm: string; volgorde?: number | null; lifecycle: string; herkomst: string;
  aangemaakt_door?: string; laag_id: string; toelichting?: string;
  beslissingen?: import("./types").Beslissing[]; veranderd: boolean;
  van: NodeEindpunt; naar: NodeEindpunt;
}
/** Een partij die de tekst niet noemt (ADR-011): alleen een rechtssubject, alleen van de jurist. Geen markering. */
export interface NodeImpliciet {
  id: string; klasse: string; label: string; toelichting: string; vindplaats?: string; zelfde_als?: string;
  herkomst: string; aangemaakt_door?: string; laag_id: string; op?: string;
}
/** Een nieuwe relatie (`POST relaties`), zonder de revisies: die rekent `dragerRevisies`. */
export interface RelatieInvoer {
  van: NodeEindpuntRef; naar: NodeEindpuntRef; type: string; volgorde?: number | null; toelichting?: string;
}
export interface NodeWeergave {
  schema_versie: 2; doel: NodeDoel; snapshot_id: string; segmenten: NodeSegment[];
  lagen: NodeLaag[]; elementen: NodeElement[];
  verwijzingen: { id: string; eigenaar_iri: string; klasse: string; label: string; detail_url?: string }[];
  dekking: NodeDekking;
  /** Gezet als deze bepaling geannoteerd was en die annotatie is verwijderd (en er sindsdien geen
   *  nieuwe laag is). Zo leest een heropend gesprek "verwijderd" in plaats van een leeg paneel. */
  verwijderd?: { op: string } | null;
  /** De agent-rondes met hun meting, elk één keer (`run_sleutel` in de api); een element draagt zijn ronde zonder. */
  runs?: Record<string, import("./types").AgentRun>;
  /** De relaties met een eindpunt in beeld of de drager in een van de lagen (ADR-011). Een oudere api heeft ze niet. */
  relaties?: NodeRelatie[];
  /** De impliciete partijen van de lagen in beeld, en die waar een getoonde relatie naar wijst. */
  impliciet?: NodeImpliciet[];
}
export function nogNietInWerking(segment: { status?: string }): boolean {
  return segment.status === "nogniet";
}

export function nodeLink(doel: NodeDoel): string {
  return `/annotaties/node?${new URLSearchParams({ bron_iri: doel.bron_iri,
    ...(doel.snapshot_id ? { snapshot_id: doel.snapshot_id } : {}) })}`;
}
export function codepointOffset(tekst: string, utf16: number): number {
  return Array.from(tekst.slice(0, utf16)).length;
}
export function segmentAnker(segment: NodeSegment, startUtf16: number, eindUtf16: number): NodeAnker {
  const start = codepointOffset(segment.tekst, startUtf16), eind = codepointOffset(segment.tekst, eindUtf16);
  return { bron_iri: segment.bron_iri, start, eind,
    tekst: Array.from(segment.tekst).slice(start, eind).join(""), bron_hash: segment.bron_hash };
}
export function verwachteRevisies(view: NodeWeergave): Record<string, number> {
  return Object.fromEntries(view.lagen.map((l) => [l.bron_iri, l.revisie]));
}
/** De revisie van één laag als `verwachte_revisies`, of niets als die laag niet in beeld is: dan geeft de api een 412
 *  en leest het paneel de weergave opnieuw, zoals bij elke andere mutatie. */
function revisieVanLaag(view: NodeWeergave, laagId: string | undefined): Record<string, number> {
  const laag = laagId ? view.lagen.find((l) => l.id === laagId) : undefined;
  return laag ? { [laag.bron_iri]: laag.revisie } : {};
}

/** De laag van een eindpunt in beeld: van de markering of van de impliciete partij. */
function laagVanEindpunt(view: NodeWeergave, ep: NodeEindpuntRef): string | undefined {
  return ep.soort === "element"
    ? view.elementen.find((e) => e.id === ep.id)?.laag_id
    : view.impliciet?.find((i) => i.id === ep.id)?.laag_id;
}

/** `verwachte_revisies` voor een relatie: alleen de **dragerlaag** telt, de laag van de kant die de catalogus aanwijst
 *  (`drager` in `RELATIETYPEN`). Een bestaande relatie draagt haar laag zelf (`laag_id`); bij een nieuwe is het de laag
 *  van het eindpunt aan de dragerkant. Die kan een andere zijn dan de laag van het element waar je staat. */
export function dragerRevisies(view: NodeWeergave, r: Pick<NodeRelatie, "laag_id"> | RelatieInvoer): Record<string, number> {
  if ("laag_id" in r) return revisieVanLaag(view, r.laag_id);
  const kant = RELATIETYPEN[r.type]?.drager;
  return kant ? revisieVanLaag(view, laagVanEindpunt(view, r[kant])) : {};
}

/** `verwachte_revisies` voor een nieuwe impliciete partij: de laag van de bepaling in beeld, of 0 als die er nog niet
 *  is (dan maakt de api haar aan). */
export function bepalingRevisies(view: NodeWeergave): Record<string, number> {
  const iri = view.doel.bron_iri;
  return { [iri]: view.lagen.find((l) => l.bron_iri === iri)?.revisie ?? 0 };
}

export async function nodeError(response: Response): Promise<Error> {
  if (response.status === 412)
    return new Error("Deze annotatie is intussen gewijzigd. Laad opnieuw en controleer de laatste stand voordat je de wijziging opnieuw opslaat.");
  // Hetzelfde foutcontract als de rest van de app (`parseError`): de `melding` van een gestructureerde
  // fout, de 401 naar het inlogscherm. Alleen zonder tekst van de server een eigen terugval, want
  // `parseError` valt dan terug op de statustekst ("Conflict").
  const fout = await parseError(response);
  const zonderTekst = fout.detail === (response.statusText || `HTTP ${response.status}`);
  return new Error(zonderTekst ? `Verzoek mislukt (${response.status}).` : fout.detail);
}
export async function nodeRequest<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const response = await fetch(`/api/annotatie/v2/${path}`, body === undefined
    ? { cache: "no-store" } : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) throw await nodeError(response);
  return response.status === 204 ? undefined as T : response.json();
}
/** Eén element met zijn spoor, los van een weergave (`GET elementen/{id}`). */
export async function haalElement(id: string): Promise<NodeElement> {
  const { element } = await nodeRequest<{ element?: NodeElement }>(`elementen/${pathSegment(id)}`);
  if (!element) throw new Error("Geen element in het antwoord.");
  return element;
}
/** Eén element op zijn eigen pagina (spoor G3): het element, zijn laag, de bronstand waarop het rust en de
 *  bronnodes van zijn ankers met hun tekst (`GET elementen/{id}`). */
export interface ElementDetail {
  element: NodeElement;
  laag: NodeLaag;
  snapshot_id: string;
  actuele_snapshot_id?: string;
  bronnen: NodeSegment[];
}
export function haalElementDetail(id: string): Promise<ElementDetail> {
  return nodeRequest(`elementen/${pathSegment(id)}`);
}
/** Een beslissing op één element, tegen de laagrevisie en de bronstand van de detailpagina. */
export function beslisElement(d: ElementDetail, body: { type: "approve" | "reject" | "heropen"; review_reason?: string }) {
  return nodeRequest(`elementen/${pathSegment(d.element.id)}/beslissing`, {
    ...body, snapshot_id: d.snapshot_id, verwachte_revisies: { [d.element.eigenaar_iri]: d.laag.revisie },
  });
}
/** Technisch detail van één markering: haar RDF zoals de projectie hem schrijft, en de graafcontrole
 *  van haar laag (`GET elementen/{id}/graaf`). */
export interface LaagGraafcontrole {
  laag_id: string; revisie: number;
  status: "in_orde" | "achterstand" | "afwijking" | "onbeschikbaar" | "uit";
  afwijkingen: { soort: string }[];
  shacl: { beschikbaar: boolean; conform: boolean; aantal: number } | null;
}
export interface ElementGraaf { element_id: string; laag_id: string; turtle: string; graafcontrole: LaagGraafcontrole }
export function haalElementGraaf(id: string): Promise<ElementGraaf> {
  return nodeRequest(`elementen/${pathSegment(id)}/graaf`);
}
/** De plek van bepalingen in hun regeling (`POST plaatsen`, spoor H), in partijen van hoogstens 500. */
export async function haalPlaatsen(iris: readonly string[]): Promise<import("./bronPlaats").Plaats[]> {
  const uniek = [...new Set(iris)];
  const uit: import("./bronPlaats").Plaats[] = [];
  for (let i = 0; i < uniek.length; i += 500) {
    const { plaatsen } = await nodeRequest<{ plaatsen: import("./bronPlaats").Plaats[] }>("plaatsen", { bron_iris: uniek.slice(i, i + 500) });
    uit.push(...plaatsen);
  }
  return uit;
}
export async function haalNodeWeergave(doel: NodeDoel): Promise<NodeWeergave> {
  return nodeRequest(`weergave?${new URLSearchParams({ bron_iri: doel.bron_iri,
    ...(doel.snapshot_id ? { snapshot_id: doel.snapshot_id } : {}) })}`);
}

/** Waar `NodeAnnotatiePaneel` zijn weergave vandaan haalt en zijn handelingen heen stuurt.
 *
 *  Gewoon is dat de api (`apiOpslag`). De rondleiding geeft een opslag in het geheugen mee
 *  (`lib/rondleidingDemo.ts`), zodat de voorbeeldannotatie in hetzelfde paneel staat als echt werk,
 *  zonder één verzoek naar de api. Zo kan de rondleiding niet meer achterlopen op het paneel. De
 *  lichamen zijn die van de api: wat de demo ontvangt, is precies wat de api zou krijgen. */
export interface LaagBesluiten {
  verwachte_revisie: number; snapshot_id: string;
  besluiten: { element_id: string; type: "approve" | "reject" | "heropen" | "comment"; comment?: string }[];
}
export interface NodeOpslag {
  weergave(doel: NodeDoel): Promise<NodeWeergave>;
  beslis(elementId: string, body: Record<string, unknown>): Promise<unknown>;
  /** Besluiten op één laag in één transactie en één revisie (`POST lagen/{id}/beslissingen`). */
  beslisLaag(laagId: string, body: LaagBesluiten): Promise<unknown>;
  markeer(body: Record<string, unknown>): Promise<{ element?: { id?: string } } | undefined>;
  wis(elementId: string, verwachteRevisie: number): Promise<unknown>;
  status(laagId: string, body: { status: string; verwachte_revisie: number }): Promise<unknown>;
  verwijder(body: Record<string, unknown>): Promise<{ graaf?: string } | undefined>;
  exporteer(body: { bron_iri: string; snapshot_id: string; formaat: ExportFormaat }): Promise<void>;
  /** Relaties en impliciete partijen (ADR-011). Weglaten (de rondleiding, een oude versie) maakt het blok
   *  *Relaties* alleen-lezen. */
  legRelatie?(body: RelatieInvoer & { verwachte_revisies: Record<string, number> }): Promise<unknown>;
  beslisRelatie?(relatieId: string, body: { type: "approve" | "reject" | "heropen" | "comment"; comment: string; verwachte_revisies: Record<string, number> }): Promise<unknown>;
  wisRelatie?(relatieId: string, body: { verwachte_revisies: Record<string, number> }): Promise<unknown>;
  maakImpliciet?(body: { doel: { bron_iri: string }; snapshot_id: string; label: string; toelichting: string;
    vindplaats?: string; zelfde_als?: string; verwachte_revisies: Record<string, number> }): Promise<unknown>;
  wisImpliciet?(implicietId: string, body: { verwachte_revisies: Record<string, number> }): Promise<unknown>;
  /** Hoort er een kennisgraaf en een revisiehistorie achter? Zonder (de rondleiding) toont het
   *  paneel geen Graaf-tab en geen Historie: daar is niets op te halen. */
  levend: boolean;
}

/** Een oude versie van een annotatie (de versiekiezer): de weergave uit de opname, en elke wijziging geweigerd. Zoals de
 *  opslag van de rondleiding `levend: false`: er hoort geen kennisgraaf en geen historie bij. */
export function momentopnameOpslag(weergave: NodeWeergave): NodeOpslag {
  const weiger = async (): Promise<never> => { throw new Error("Een oude versie is alleen te lezen."); };
  return { weergave: async () => weergave, beslis: weiger, beslisLaag: weiger, markeer: weiger, wis: weiger, status: weiger, verwijder: weiger,
    exporteer: weiger, levend: false };
}

/** De annotatie van één bepaling verwijderen vanuit een lijst (`lib/verwijderen.ts`): eerst de weergave,
 *  voor de revisies in beeld, dan hetzelfde verzoek als het paneel. Een 412 betekent ook hier dat iemand
 *  intussen iets wijzigde. */
export async function verwijderAnnotatie(doel: NodeDoel, opslag: NodeOpslag = apiOpslag) {
  const view = await opslag.weergave(doel);
  return opslag.verwijder({
    bron_iri: view.doel.bron_iri, snapshot_id: view.snapshot_id, verwachte_revisies: verwachteRevisies(view),
  });
}

export const apiOpslag: NodeOpslag = {
  weergave: haalNodeWeergave,
  beslis: (id, body) => nodeRequest(`elementen/${encodeURIComponent(id)}/beslissing`, body),
  beslisLaag: (laagId, body) => nodeRequest(`lagen/${encodeURIComponent(laagId)}/beslissingen`, body),
  markeer: (body) => nodeRequest("elementen", body),
  wis: (id, revisie) => nodeRequest(`elementen/${encodeURIComponent(id)}?verwachte_revisie=${revisie}`, {}, "DELETE"),
  status: (laagId, body) => nodeRequest(`lagen/${encodeURIComponent(laagId)}/status`, body),
  verwijder: (body) => nodeRequest("weergave/verwijder", body),
  legRelatie: (body) => nodeRequest("relaties", body),
  beslisRelatie: (id, body) => nodeRequest(`relaties/${pathSegment(id)}/beslissing`, body),
  wisRelatie: (id, body) => nodeRequest(`relaties/${pathSegment(id)}/wis`, body),
  maakImpliciet: (body) => nodeRequest("impliciet", body),
  wisImpliciet: (id, body) => nodeRequest(`impliciet/${pathSegment(id)}/wis`, body),
  async exporteer(body) {
    const response = await fetch("/api/annotatie/v2/weergave/export", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!response.ok) throw await nodeError(response);
    // Hetzelfde downloadpatroon als de artikelexport: bestandsnaam van de server, link in het document.
    await downloadAntwoord(response, `annotatie.${body.formaat}`);
  },
  levend: true,
};
