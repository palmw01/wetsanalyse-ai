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
  aandacht?: string | null; critic?: string;
  critic_rondes?: import("./types").CriticRonde[];
  critic_suggestie?: import("./types").CriticSuggestie | null;
  geproduceerd_door?: import("./types").AgentRun | null;
  provenance?: Partial<import("./types").AgentRun>;
}
export interface NodeLaag { id: string; bron_iri: string; revisie: number; status: string }
export interface NodeWeergave {
  schema_versie: 2; doel: NodeDoel; snapshot_id: string; segmenten: NodeSegment[];
  lagen: NodeLaag[]; elementen: NodeElement[];
  verwijzingen: { id: string; eigenaar_iri: string; klasse: string; label: string; detail_url?: string }[];
  dekking: Record<string, unknown>;
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
  const detail = typeof error.detail === "string" ? error.detail : `Verzoek mislukt (${response.status}).`;
  return new Error(detail);
}
export async function nodeRequest<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const response = await fetch(`/api/annotatie/v2/${path}`, body === undefined
    ? { cache: "no-store" } : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) throw await nodeError(response);
  return response.status === 204 ? undefined as T : response.json();
}
export async function haalNodeWeergave(doel: NodeDoel): Promise<NodeWeergave> {
  return nodeRequest(`weergave?${new URLSearchParams({ bron_iri: doel.bron_iri,
    ...(doel.snapshot_id ? { snapshot_id: doel.snapshot_id } : {}) })}`);
}
