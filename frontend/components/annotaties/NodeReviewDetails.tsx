"use client";

import { useState } from "react";
import { JAS_KLASSEN } from "@/lib/jas";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import type { NodeElement } from "@/lib/annotatieNode";
import type { Lifecycle } from "@/lib/types";

const ACTIE: Record<string, string> = { approve: "Akkoord", reject: "Verworpen", edit: "Aangepast", comment: "Toelichting", heropen: "Heropend" };
const VELD: Record<string, string> = { klasse: "Klasse", tekst: "Fragment", toelichting: "Toelichting", ankers: "Tekstankers", eigenaar_iri: "Bronnode" };
function wijzigingLabel(key: string, value: unknown): string {
  if (typeof value === "string") return `${VELD[key] || key}: ${value}`;
  if (value && typeof value === "object" && "voor" in value && "na" in value) {
    const diff = value as { voor: unknown; na: unknown };
    if (typeof diff.voor === "string" && typeof diff.na === "string") return `${VELD[key] || key}: ${diff.voor} → ${diff.na}`;
  }
  return `${VELD[key] || key} gewijzigd`;
}
export function NodeReviewDetails({ element: e, disabled, onEdit }: {
  element: NodeElement; disabled: boolean; onEdit: (wijziging: { klasse: string; toelichting: string }) => Promise<void>;
}) {
  const [klasse, setKlasse] = useState(e.klasse);
  const [toelichting, setToelichting] = useState(e.toelichting);
  const run = e.geproduceerd_door || e.provenance;
  return <details className="mt-2 text-sm">
    <summary className="cursor-pointer font-medium">Onderbouwing en historie</summary>
    <div className="mt-2 space-y-3">
      <p>{LIFECYCLE_LABEL[e.lifecycle as Lifecycle] || e.lifecycle} · {e.herkomst === "mens" ? "Handmatig gemarkeerd" : "Voorstel van Lex"}</p>
      {e.critic && <p><strong>Critic{e.aandacht ? ` · ${e.aandacht}` : ""}:</strong> {e.critic}</p>}
      {!!e.alternatieven?.length && <div><h4 className="font-medium">Alternatieve classificaties</h4>
        <ul className="list-disc pl-5">{e.alternatieven.map((a, i) => <li key={i}><strong>{a.klasse}</strong> — {a.motivatie}</li>)}</ul>
      </div>}
      {!!e.critic_rondes?.length && <div><h4 className="font-medium">Beoordelingen van de Critic</h4>
        <ol className="space-y-2">{e.critic_rondes.map((r, i) => <li key={i}>
          <p>Ronde {r.ronde}{r.aandacht ? ` · ${r.aandacht}` : ""}: {r.motivatie}</p>
          {r.voorstel_klasse && <p>Voorgestelde klasse: {r.voorstel_klasse}</p>}
          {r.voorstel_tekst && <p>Voorgesteld fragment: {r.voorstel_tekst}</p>}
          {r.actie && <p>{r.actie}{typeof r.toegepast === "boolean" ? (r.toegepast ? " · toegepast" : " · niet toegepast") : ""}</p>}
        </li>)}</ol>
      </div>}
      {e.critic_suggestie && <div className="rounded border border-line p-2">
        <p className="font-medium">Suggestie bij handmatig werk · {e.critic_suggestie.status}</p>
        <p>{e.critic_suggestie.motivatie}</p>
        {e.critic_suggestie.voorstel_klasse && <p>Voorgestelde klasse: {e.critic_suggestie.voorstel_klasse}</p>}
        {e.critic_suggestie.voorstel_tekst && <p>Voorgesteld fragment: {e.critic_suggestie.voorstel_tekst}</p>}
      </div>}
      {!!e.beslissingen?.length && <div><h4 className="font-medium">Beslissingen van reviewers</h4>
        <ol className="space-y-2">{e.beslissingen.map((b, i) => <li key={i}>
          <p>{ACTIE[b.type] || b.type} · {b.actor}{b.tijd ? ` · ${new Date(b.tijd).toLocaleString("nl-NL")}` : ""}</p>
          {b.review_reason && <p>Reden: {b.review_reason.replaceAll("_", " ")}</p>}
          {b.comment && <p>{b.comment}</p>}
          {Object.entries(b.wijziging || {}).map(([key, value]) => <p key={key}>{wijzigingLabel(key, value)}</p>)}
        </li>)}</ol>
      </div>}
      {run?.model && <p>Geproduceerd met {run.model}{run.provider ? ` (${run.provider})` : ""}{run.methode_versie ? ` · methode ${run.methode_versie}` : ""}</p>}
      {!e.verouderd && <fieldset disabled={disabled} className="space-y-2 rounded border border-line p-2">
        <legend>Classificatie aanpassen</legend>
        <label className="block">Klasse<select aria-label="Klasse" className="ml-2 rounded border p-1" value={klasse} onChange={(event) => setKlasse(event.target.value)}>
          {JAS_KLASSEN.map((k) => <option key={k}>{k}</option>)}
        </select></label>
        <label className="block">Onderbouwing<textarea className="mt-1 block w-full rounded border p-2" value={toelichting} onChange={(event) => setToelichting(event.target.value)} /></label>
        <button className="rounded border border-line px-2 py-1 disabled:opacity-40" disabled={disabled || (klasse === e.klasse && toelichting === e.toelichting)}
          onClick={() => void onEdit({ klasse, toelichting })}>Classificatie opslaan</button>
      </fieldset>}
    </div>
  </details>;
}
