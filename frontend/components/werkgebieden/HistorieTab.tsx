"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { foutTekst, haalWerkgebiedAudit, lijstBegrippen } from "@/lib/api";
import type { Bronselectie, WerkgebiedAuditRegel } from "@/lib/types";
import { auditZin } from "@/lib/werkgebied";

const tijd = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Wie wat wanneer deed, nieuwste eerst. Alleen-lezend: de audit is append-only. */
export function HistorieTab({ id, bronnen }: { id: string; bronnen: Bronselectie[] }) {
  const [regels, setRegels] = useState<WerkgebiedAuditRegel[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [begrippen, setBegrippen] = useState<Map<string, string>>(new Map());
  // Een weggehaalde bron staat niet meer in `bronnen`; die regels tonen dan de IRI.
  const labels = useMemo(() => new Map(bronnen.map((b) => [b.bron_iri, b.label || b.bron_iri])), [bronnen]);

  const laad = useCallback(async () => {
    try {
      // De namen van de begrippen maken de regels leesbaar; zonder ze staat er "een begrip".
      const [audit, lijst] = await Promise.all([haalWerkgebiedAudit(id), lijstBegrippen(id).catch(() => null)]);
      setRegels(audit);
      if (lijst) setBegrippen(new Map(lijst.begrippen.map((b) => [b.id, b.inhoud.naam])));
    } catch (e) {
      setFout(foutTekst(e, "De historie kon niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  if (fout) return <Melding type="fout">{fout}</Melding>;
  if (!regels)
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-72" />
        <Skeleton className="h-4 w-64" />
      </div>
    );
  return (
    <ol className="space-y-2" aria-label="Historie van het werkgebied">
      {regels.map((r) => (
        <li key={r.id} className="flex flex-col gap-0.5 border-b border-line pb-2 text-sm sm:flex-row sm:items-baseline sm:gap-3">
          <span className="shrink-0 text-xs text-muted sm:w-40">{tijd(r.tijdstip)}</span>
          <span className="min-w-0 text-ink">
            {auditZin(r, labels, begrippen)} <span className="text-xs text-muted">· {r.actor}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
