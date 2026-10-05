"use client";

import { useId } from "react";
import { Lagen } from "@/components/ui/Icoon";
import { DEKKINGSKLEUR } from "@/lib/dekking";
import type { RelatieGroep } from "@/lib/samenhang";

// Dezelfde kleuren als de lijnen in GraafCanvas (LIJN): de legenda ís het filter.
const LAGEN: { groep: RelatieGroep; naam: string; uitleg: string; voorbeeld: React.ReactNode }[] = [
  { groep: "structuur", naam: "Structuur", uitleg: "regeling, artikel, leden",
    voorbeeld: <><circle cx="4" cy="6" r="3" fill="#007bc7" /><path d="M7 6h10" stroke="#8aa1b6" strokeWidth="2" /><circle cx="20" cy="6" r="2.5" fill="#398ab8" /></> },
  { groep: "verwijzingen", naam: "Verwijzingen", uitleg: "naar en van andere bepalingen",
    voorbeeld: <><circle cx="4" cy="6" r="3" fill="#398ab8" /><path d="M7 7q6-6 10-1" stroke="#6b4e91" strokeWidth="1.6" fill="none" /><circle cx="20" cy="6" r="2.5" fill="none" stroke="#a7bfd3" strokeWidth="1.2" /></> },
  { groep: "annotaties", naam: "Annotaties", uitleg: "markeringen en hun JAS-klasse",
    voorbeeld: <><circle cx="4" cy="6" r="3" fill="#c0392b" /><path d="M7 6h8" stroke="#b7c4d1" strokeWidth="1" /><path d="M20 2.5 23 6 20 9.5 17 6Z" fill="#c0392b" opacity=".75" /></> },
];

/** Wat er in beeld staat: filters en legenda in één paneel, linksonder in het canvas. */
export function GraafLagen({ filters, onWissel, open, onOpen, dekking }: {
  filters: Record<RelatieGroep, boolean>; onWissel: (groep: RelatieGroep) => void;
  open: boolean; onOpen: (open: boolean) => void;
  /** De laag Dekking; weg als er geen zinsdeel zonder treffer is. Een kenmerk, geen relatiegroep. */
  dekking?: { aan: boolean; onWissel: () => void };
}) {
  const paneelId = useId();
  return <div className="pointer-events-auto">
    {open && <div id={paneelId} role="group" aria-label="Lagen" className="mb-2 w-64 rounded-kaart border border-line bg-paper/95 p-2 shadow-kaart">
      {LAGEN.map((laag) => <label key={laag.groep} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-surface">
        <input type="checkbox" checked={filters[laag.groep]} onChange={() => onWissel(laag.groep)} className="h-3.5 w-3.5 shrink-0 accent-lint" />
        <svg viewBox="0 0 24 12" className="h-3 w-6 shrink-0" aria-hidden="true">{laag.voorbeeld}</svg>
        <span className="min-w-0">
          <span className={`block text-xs ${filters[laag.groep] ? "text-ink" : "text-faint"}`}>{laag.naam}</span>
          <span className="block text-[10px] text-faint">{laag.uitleg}</span>
        </span>
      </label>)}
      {dekking && <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-surface">
        <input type="checkbox" checked={dekking.aan} onChange={dekking.onWissel} className="h-3.5 w-3.5 shrink-0 accent-lint" />
        <svg viewBox="0 0 24 12" className="h-3 w-6 shrink-0" aria-hidden="true">
          <circle cx="12" cy="6" r="3" fill="#398ab8" /><circle cx="12" cy="6" r="5.2" fill="none" stroke={DEKKINGSKLEUR} strokeWidth="1.2" strokeDasharray="1.6 1.2" />
        </svg>
        <span className="min-w-0">
          <span className={`block text-xs ${dekking.aan ? "text-ink" : "text-faint"}`}>Dekking</span>
          <span className="block text-[10px] text-faint">zinsdelen zonder detectortreffer (in de geopende bepaling)</span>
        </span>
      </label>}
      <p className="mt-1 border-t border-line px-2 pt-1.5 text-[10px] leading-relaxed text-faint">
        Open bol: buiten dit artikel. Afstand en positie hebben geen juridische betekenis.
      </p>
    </div>}
    <button type="button" aria-expanded={open} aria-controls={paneelId} onClick={() => onOpen(!open)}
      className={`focus-ring inline-flex min-h-9 items-center gap-2 rounded-full border px-3 text-xs shadow-kaart coarse:min-h-11 ${open ? "border-lint/50 bg-paper text-lint" : "border-line bg-paper/95 text-ink hover:border-lint/40"}`}>
      <Lagen /> Lagen
      <span className="flex gap-0.5" aria-hidden="true">
        {LAGEN.map((l) => <span key={l.groep} className={`h-1.5 w-1.5 rounded-full ${filters[l.groep] ? "" : "opacity-25"}`}
          style={{ backgroundColor: l.groep === "structuur" ? "#007bc7" : l.groep === "verwijzingen" ? "#6b4e91" : "#c0392b" }} />)}
        {dekking && <span className={`h-1.5 w-1.5 rounded-full ${dekking.aan ? "" : "opacity-25"}`} style={{ backgroundColor: DEKKINGSKLEUR }} />}
      </span>
    </button>
  </div>;
}
