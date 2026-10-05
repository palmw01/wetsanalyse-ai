import { naarInloggen } from "./api";
import { pathSegment } from "./url";

/** Canonieke bronnodeweergave. Posities zijn Unicode-codepunten, niet UTF-16. */
export interface NodeDoel {
  bron_iri: string; type?: string; label?: string; bwb_id?: string;
  artikel?: string; lid?: string; snapshot_id?: string; citeertitel?: string;
}
export interface NodeSegment {
  bron_iri: string; parent_iri?: string; type: string; label: string; nummer?: string;
  tekst: string; bron_hash: string; volgorde: number;
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
}
export interface NodeDekking {
  voltooid?: boolean;
  bereik?: string[];
  structureel?: Record<string, StructureleDekking>;
}
export interface NodeLaag { id: string; bron_iri: string; revisie: number; status: string }
export interface NodeWeergave {
  schema_versie: 2; doel: NodeDoel; snapshot_id: string; segmenten: NodeSegment[];
  lagen: NodeLaag[]; elementen: NodeElement[];
  verwijzingen: { id: string; eigenaar_iri: string; klasse: string; label: string; detail_url?: string }[];
  dekking: NodeDekking;
  /** Gezet als deze bepaling geannoteerd was en die annotatie is verwijderd (en er sindsdien geen
   *  nieuwe laag is). Zo leest een heropend gesprek "verwijderd" in plaats van een leeg paneel. */
  verwijderd?: { op: string } | null;
}
export interface ToolExecution {
  run_id: string; call_id: string; tool: string; phase: "started" | "completed" | "failed";
  actie?: string; filters?: Record<string, unknown>; doel?: unknown; status?: string;
  aantal?: number; has_more?: boolean; duur_ms?: number; actualiteit?: string | Record<string, unknown>;
  foutcode?: string; melding?: string;
}
export function parseToolExecution(value: unknown): ToolExecution | undefined {
  if (!value || typeof value !== "object") return;
  const v = { ...value } as Record<string, unknown>;
  if (v.phase === "start") v.phase = "started";
  if (v.phase === "end") v.phase = ["error", "unavailable", "invalid_request"].includes(String(v.status)) ? "failed" : "completed";
  if (typeof v.run_id !== "string" || typeof v.call_id !== "string" || typeof v.tool !== "string"
    || !["started", "completed", "failed"].includes(String(v.phase))) return;
  return v as unknown as ToolExecution;
}
export function mergeToolExecution(events: ToolExecution[], event: ToolExecution): ToolExecution[] {
  const index = events.findIndex((e) => e.run_id === event.run_id && e.call_id === event.call_id);
  if (index < 0) return [...events, event];
  // Een vertraagd/replayed started-event mag een afgeronde aanroep niet terugdraaien.
  if (events[index].phase !== "started" && event.phase === "started") return events;
  return events.map((e, i) => i === index ? { ...e, ...event } : e);
}
/** Het toolspoor zoals het in een bewaard bericht staat, als één regel per aanroep.
 *
 *  graph-qa stuurt per aanroep twee events – start en einde, met hetzelfde `call_id` – en een bewaard
 *  spoor kan die allebei los bevatten. Live voegt de werkplek ze samen; zonder datzelfde bij het
 *  laden van een gesprek staat elke aanroep er twee keer ("Bezig", daarna "Uitgevoerd") en telt de
 *  kop het dubbele. Hier dezelfde regel als live. */
export function toolSpoorUit(ruw: readonly unknown[] | null | undefined): ToolExecution[] {
  return (ruw ?? []).reduce<ToolExecution[]>((spoor, r) => {
    const e = parseToolExecution(r);
    return e ? mergeToolExecution(spoor, e) : spoor;
  }, []);
}
/** Waar een aanroep over ging, kort: "BWBR0004770 art. 9 lid 1", of het laatste stuk van de IRI.
 *  Zonder dit stonden er twee regels "bron_lezen · Uitgevoerd" onder elkaar, en was niet te zien
 *  wélke bepaling er gelezen was. */
export function toolDoelLabel(doel: unknown): string {
  if (!doel || typeof doel !== "object") return "";
  const d = doel as Record<string, unknown>;
  const tekst = (k: string) => (typeof d[k] === "string" || typeof d[k] === "number" ? String(d[k]).trim() : "");
  const delen = [tekst("bwb_id"), tekst("artikel") && `art. ${tekst("artikel")}`, tekst("lid") && `lid ${tekst("lid")}`].filter(Boolean);
  if (delen.length) return delen.join(" ");
  const iri = tekst("bron_iri") || tekst("id");
  return iri.startsWith("urn:bwb:") ? iri.slice("urn:bwb:".length).replace(/:/g, " ") : iri;
}

/** Een duur zoals een mens hem leest: onder een seconde in ms ("0.0 s" zei niets), daarboven in s. */
export function duurTekst(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

/** Een leeg object is truthy; "Actualiteit: {}" onder elke graafaanroep zei niets. */
export function heeftInhoud(waarde: unknown): boolean {
  if (typeof waarde === "string") return waarde.trim() !== "";
  return !!waarde && typeof waarde === "object" && Object.keys(waarde).length > 0;
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
export function elementVergrendeld(view: NodeWeergave, el: NodeElement): boolean {
  return !!el.verouderd || el.lifecycle === "published"
    || ((el.herkomst !== "mens" || !!el.beslissingen?.length) && ["human_approved", "rejected"].includes(el.lifecycle))
    || view.lagen.some((l) => l.bron_iri === el.eigenaar_iri && l.status === "geaccordeerd");
}
export async function nodeError(response: Response): Promise<Error> {
  const error = await response.json().catch(() => ({}));
  if (response.status === 412)
    return new Error("Deze annotatie is intussen gewijzigd. Laad opnieuw en controleer de laatste stand voordat je de wijziging opnieuw opslaat.");
  if (response.status === 401) naarInloggen();
  // Zelfde foutcontract als `parseError` in `lib/api.ts`: een gestructureerde fout (`{reden,
  // melding}`) draagt zijn leesbare tekst in `melding`. Die bleef hier onbenut, en dan stond er
  // "Verzoek mislukt (409)" waar de api precies had gezegd wat er mis was.
  const d = error?.detail;
  const melding = d && typeof d === "object" && typeof d.melding === "string" && d.melding.trim() ? d.melding : undefined;
  const detail = typeof d === "string" ? d : melding ?? `Verzoek mislukt (${response.status}).`;
  return new Error(detail);
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
export async function haalNodeWeergave(doel: NodeDoel): Promise<NodeWeergave> {
  return nodeRequest(`weergave?${new URLSearchParams({ bron_iri: doel.bron_iri,
    ...(doel.snapshot_id ? { snapshot_id: doel.snapshot_id } : {}) })}`);
}
