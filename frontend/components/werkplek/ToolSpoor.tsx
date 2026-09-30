import { duurTekst, heeftInhoud, toolDoelLabel, type ToolExecution } from "@/lib/annotatieNode";

export function ToolSpoor({ events }: { events?: ToolExecution[] }) {
  if (!events?.length) return null;
  return <details className="my-2 rounded border border-line p-2 text-xs text-muted">
    <summary className="cursor-pointer">Graaf geraadpleegd · {events.length} aanroepen</summary>
    <ol className="mt-2 space-y-2">{events.map((e) => <li key={`${e.run_id}:${e.call_id}`}>
      {/* De tool zelf, en waarover: de `actie` ("bron_lezen") is een categorie en zei niet welke
          aanroep het was. */}
      <span className="font-medium text-ink">{e.tool}</span>
      {toolDoelLabel(e.doel) && <span> ({toolDoelLabel(e.doel)})</span>}{" · "}
      {e.phase === "started" ? "Bezig" : e.phase === "failed" ? "Mislukt" : "Uitgevoerd"}
      {typeof e.aantal === "number" && ` · ${e.aantal} resultaten`}
      {e.has_more && " · meer resultaten beschikbaar"}
      {typeof e.duur_ms === "number" && ` · ${duurTekst(e.duur_ms)}`}
      {heeftInhoud(e.actualiteit) && <p>Actualiteit: {typeof e.actualiteit === "string" ? e.actualiteit : JSON.stringify(e.actualiteit)}</p>}
      {e.melding && <p>{e.melding}</p>}
      {e.filters && Object.keys(e.filters).length > 0 && <p className="break-words">Filters: {JSON.stringify(e.filters)}</p>}
    </li>)}</ol>
  </details>;
}

