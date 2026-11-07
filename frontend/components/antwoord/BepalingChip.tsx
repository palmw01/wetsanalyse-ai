"use client";

import { useContext } from "react";

import { ContextPaneelContext } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";

/** Hoeveel bepalingen een eigen chip krijgen; daarboven één chip die de eerste opent. De andere staan als link in de blokken. */
export const MAX_BEPALINGCHIPS = 3;

/** De chip onder een sjabloonantwoord (ADR-008, *Detail bij een antwoord*): dezelfde vorm als de chip na een annotatie, en een
 *  klik opent de bepaling naast het gesprek, met wat de graaf er verder over weet. Een bepaling is context, geen artefact van
 *  de beurt: er valt niets te beoordelen. Buiten de werkplek is er geen gesprek om naast te staan, en dan geen chip. */
export function BepalingChips({ bepalingen }: { bepalingen: readonly AntwoordVindplaats[] }) {
  const opener = useContext(ContextPaneelContext);
  if (!opener || !bepalingen.length) return null;
  const open = (v: AntwoordVindplaats) =>
    opener({ soort: "bron", bron_iri: v.iri, titel: v.regeling ? `${v.label}, ${v.regeling}` : v.label, jci: v.jci || undefined });
  const chips = bepalingen.length > MAX_BEPALINGCHIPS
    ? [{ v: bepalingen[0], titel: `${bepalingen.length} bepalingen`, sub: `Bepaling · bekijken, te beginnen bij ${bepalingen[0].label}` }]
    : bepalingen.map((v) => ({ v, titel: v.regeling ? `${v.label}, ${v.regeling}` : v.label, sub: "Bepaling · bekijken" }));
  return (
    <div className="mt-3 space-y-2" data-bepaling-chips={bepalingen.length}>
      {chips.map(({ v, titel, sub }) => (
        <button key={v.iri} type="button" onClick={() => open(v)} data-bepaling-chip={v.iri}
          className="flex w-full items-center gap-3 rounded-kaart border border-line bg-surface px-4 py-3 text-left shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-lint/10 text-lint" aria-hidden>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 5h16M4 10h16M4 15h10M4 20h7" />
            </svg>
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-ink">{titel}</span>
            <span className="block truncate text-xs text-muted">{sub}</span>
          </span>
          <span className="shrink-0 text-muted" aria-hidden>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
          </span>
        </button>
      ))}
    </div>
  );
}
