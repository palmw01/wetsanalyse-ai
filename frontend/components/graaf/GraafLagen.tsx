"use client";

import { useId } from "react";
import { Lagen as LagenIcoon } from "@/components/ui/Icoon";
import { BRONKLEUR, DEKKINGSKLEUR, GEDIMD, LIJNKLEUR, RANDKLEUR, klasseKleur } from "@/lib/graaf/stijl";
import type { Lagen } from "@/lib/graaf/weergave";
import { MARKERING_FILTERS, type MarkeringFilter } from "@/lib/samenhang";

type Laag = Exclude<keyof Lagen, "dekking">;
const LAGEN: { laag: Laag; naam: string; uitleg: string; kleur: string; voorbeeld: React.ReactNode }[] = [
  { laag: "leden", naam: "Leden en onderdelen", uitleg: "uit: de kaart tot op artikelniveau", kleur: BRONKLEUR.lid,
    voorbeeld: <><circle cx="4" cy="6" r="3" fill={BRONKLEUR.artikel} /><path d="M7 6h10" stroke={LIJNKLEUR.bevat} strokeWidth="1.6" /><circle cx="20" cy="6" r="2.2" fill={BRONKLEUR.lid} /></> },
  { laag: "verwijzingen", naam: "Verwijzingen", uitleg: "met de bepalingen buiten wat geladen is", kleur: LIJNKLEUR.verwijst_naar,
    voorbeeld: <><circle cx="4" cy="6" r="3" fill={BRONKLEUR.lid} /><path d="M7 6h8" stroke={LIJNKLEUR.verwijst_naar} strokeWidth="1.4" /><path d="m15 3.5 3 2.5-3 2.5Z" fill={LIJNKLEUR.verwijst_naar} /><circle cx="21" cy="6" r="2.2" fill="#fff" stroke={RANDKLEUR} strokeWidth="1.2" /></> },
  { laag: "annotaties", naam: "Annotaties", uitleg: "markeringen in de kleur van hun JAS-klasse", kleur: klasseKleur("Rechtssubject"),
    voorbeeld: <><circle cx="4" cy="6" r="3" fill={BRONKLEUR.lid} /><path d="M7 6h6" stroke={LIJNKLEUR.markeert} strokeWidth="1.2" /><circle cx="15" cy="6" r="2" fill={klasseKleur("Rechtssubject")} /><circle cx="21" cy="6" r="2" fill={klasseKleur("Rechtsfeit")} /></> },
];

const SOORTEN: { naam: string; kleur: string; r: number }[] = [
  { naam: "Regeling", kleur: BRONKLEUR.regeling, r: 4.5 }, { naam: "Hoofdstuk, afdeling", kleur: BRONKLEUR.deel, r: 3.8 },
  { naam: "Artikel", kleur: BRONKLEUR.artikel, r: 3.2 }, { naam: "Lid", kleur: BRONKLEUR.lid, r: 2.6 },
  { naam: "Onderdeel", kleur: BRONKLEUR.onderdeel, r: 2.2 },
];

/** Wat er in beeld staat: lagen, markeringsfilter en legenda in één paneel, linksonder in het canvas.
 *  De legenda zegt ook wat gedimd betekent, zodat de keuze in de graaf geen raadsel is. */
export function GraafLagen({ lagen, onWissel, open, onOpen, dekking, markering }: {
  lagen: Lagen; onWissel: (laag: keyof Lagen) => void;
  open: boolean; onOpen: (open: boolean) => void;
  /** Is er een meting van de detectoren (alleen voor de geopende bepaling)? Anders geen laag Dekking. */
  dekking: boolean;
  markering: { waarde: MarkeringFilter; onKies: (f: MarkeringFilter) => void };
}) {
  const kiesId = useId();
  const paneelId = useId();
  const rij = "flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-surface coarse:min-h-11";
  return <div className="pointer-events-auto">
    {open && <div id={paneelId} role="group" aria-label="Lagen en legenda"
      className="mb-2 max-h-[min(30rem,calc(100dvh-12rem))] w-72 overflow-y-auto rounded-kaart border border-line bg-paper/95 p-2 shadow-kaart">
      {LAGEN.map((l) => <label key={l.laag} className={rij}>
        <input type="checkbox" checked={lagen[l.laag]} onChange={() => onWissel(l.laag)} className="h-3.5 w-3.5 shrink-0 accent-lint" />
        <svg viewBox="0 0 24 12" className="h-3 w-6 shrink-0" aria-hidden="true">{l.voorbeeld}</svg>
        <span className="min-w-0">
          <span className={`block text-xs ${lagen[l.laag] ? "text-ink" : "text-faint"}`}>{l.naam}</span>
          <span className="block text-[10px] text-faint">{l.uitleg}</span>
        </span>
      </label>)}
      {dekking && <label className={rij}>
        <input type="checkbox" checked={lagen.dekking} onChange={() => onWissel("dekking")} className="h-3.5 w-3.5 shrink-0 accent-lint" />
        <svg viewBox="0 0 24 12" className="h-3 w-6 shrink-0" aria-hidden="true">
          <circle cx="12" cy="6" r="4.4" fill={BRONKLEUR.lid} stroke={DEKKINGSKLEUR} strokeWidth="1.6" />
        </svg>
        <span className="min-w-0">
          <span className={`block text-xs ${lagen.dekking ? "text-ink" : "text-faint"}`}>Dekking</span>
          <span className="block text-[10px] text-faint">okeromtrek: zinsdelen zonder detectortreffer (geopende bepaling)</span>
        </span>
      </label>}
      {lagen.annotaties && <div className="flex items-center gap-2 px-2 py-1.5">
        <label htmlFor={kiesId} className="shrink-0 text-xs text-ink">Markeringen</label>
        <select id={kiesId} value={markering.waarde} onChange={(e) => markering.onKies(e.target.value as MarkeringFilter)}
          className="focus-ring min-w-0 flex-1 rounded border border-line bg-paper px-1.5 py-1 text-xs text-ink coarse:min-h-11">
          {MARKERING_FILTERS.map((f) => <option key={f.waarde} value={f.waarde}>{f.label}</option>)}
        </select>
      </div>}

      <div className="mt-1 space-y-1.5 border-t border-line px-2 pb-1 pt-2 text-[10px] leading-relaxed text-muted" data-testid="graaf-legenda">
        <ul className="flex flex-wrap gap-x-3 gap-y-1">
          {SOORTEN.map((s) => <li key={s.naam} className="flex items-center gap-1">
            <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden="true"><circle cx="5" cy="5" r={s.r} fill={s.kleur} /></svg>{s.naam}
          </li>)}
          <li className="flex items-center gap-1">
            <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden="true"><circle cx="5" cy="5" r="3.6" fill="#fff" stroke={RANDKLEUR} strokeWidth="1.4" /></svg>
            Omtrek: buiten wat geladen is
          </li>
          <li className="flex items-center gap-1">
            <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden="true"><circle cx="5" cy="5" r="3.6" fill={GEDIMD} /></svg>
            Gedimd: niet verbonden met je keuze
          </li>
        </ul>
        <p className="text-faint">De plek volgt de opbouw van de wet: elke regeling een eigen gebied, met haar hoofdstukken erin. Afstand heeft verder geen juridische betekenis.</p>
      </div>
    </div>}
    <button type="button" aria-expanded={open} aria-controls={paneelId} onClick={() => onOpen(!open)}
      className={`focus-ring inline-flex min-h-9 items-center gap-2 rounded-full border px-3 text-xs shadow-kaart coarse:min-h-11 ${open ? "border-lint/50 bg-paper text-lint" : "border-line bg-paper/95 text-ink hover:border-lint/40"}`}>
      <LagenIcoon /> Lagen
      <span className="flex gap-0.5" aria-hidden="true">
        {LAGEN.map((l) => <span key={l.laag} className={`h-1.5 w-1.5 rounded-full ${lagen[l.laag] ? "" : "opacity-25"}`} style={{ backgroundColor: l.kleur }} />)}
        {dekking && <span className={`h-1.5 w-1.5 rounded-full ${lagen.dekking ? "" : "opacity-25"}`} style={{ backgroundColor: DEKKINGSKLEUR }} />}
      </span>
    </button>
  </div>;
}
