import type { ToolExecution } from "@/lib/annotatieNode";

export function ToolSpoor({ events }: { events?: ToolExecution[] }) {
  if (!events?.length) return null;
  return <details className="my-2 rounded border border-line p-2 text-xs text-muted">
    <summary className="cursor-pointer">Graaf geraadpleegd · {events.length} aanroepen</summary>
    <ol className="mt-2 space-y-2">{events.map((e) => <li key={`${e.run_id}:${e.call_id}`}>
      <span className="font-medium text-ink">{e.actie || e.tool}</span>{" · "}
      {e.phase === "started" ? "Bezig" : e.phase === "failed" ? "Mislukt" : "Uitgevoerd"}
      {typeof e.aantal === "number" && ` · ${e.aantal} resultaten`}
      {e.has_more && " · meer resultaten beschikbaar"}
      {typeof e.duur_ms === "number" && ` · ${(e.duur_ms / 1000).toFixed(1)} s`}
      {e.actualiteit && <p>Actualiteit: {typeof e.actualiteit === "string" ? e.actualiteit : JSON.stringify(e.actualiteit)}</p>}
      {e.melding && <p>{e.melding}</p>}
      {e.filters && Object.keys(e.filters).length > 0 && <p className="break-words">Filters: {JSON.stringify(e.filters)}</p>}
    </li>)}</ol>
  </details>;
}
