"use client";

import { type ReactNode } from "react";

import { useOpenBron } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { vindplaatsTekst } from "@/lib/herkomst";

/** Hoeveel bepalingen een eigen kaart krijgen; daarboven één kaart met de telling, die de lijst in het paneel opent. */
export const MAX_BEPALINGCHIPS = 3;

/** De kaart onder een antwoord (het bronvenster, PR 4; ontdubbelen PR 2): de enige ingang naar wat het antwoord aanwijst,
 *  een bepaling als tab naast het gesprek, met Tekst | Graaf. Dezelfde vorm als de chip na een annotatie. */
export function BronChip({ titel, sub, icoon, onClick, label, ...data }: {
  titel: string;
  sub: string;
  icoon: ReactNode;
  onClick: () => void;
  /** De voorleesnaam, als die meer zegt dan titel en sub samen. */
  label?: string;
} & Record<`data-${string}`, string | number | undefined>) {
  return (
    <button type="button" onClick={onClick} aria-label={label} {...data}
      className="flex w-full items-center gap-3 rounded-kaart border border-line bg-surface px-4 py-3 text-left shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-lint/10 text-lint" aria-hidden>{icoon}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-ink">{titel}</span>
        <span className="block truncate text-xs text-muted">{sub}</span>
      </span>
      <span className="shrink-0 text-muted" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
      </span>
    </button>
  );
}

const TEKSTICOON = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 5h16M4 10h16M4 15h10M4 20h7" />
  </svg>
);

/** De kaarten onder een antwoord (ADR-008, *Detail bij een antwoord*; ontdubbelen PR 2, ook bij vrije tekst): per bepaling
 *  één, die de bepaling als tab naast het gesprek opent, met de samenhang van het hele antwoord op de tab Graaf
 *  (`useOpenBron` in een `BerichtSamenhangContext`). Er is geen tweede kaart voor de graaf. Bij meer dan
 *  `MAX_BEPALINGCHIPS` staat er één kaart met de telling, die alle bepalingen als lijst in het paneel opent (soort
 *  `bepalingen`, zoals *Bronnen* in de chatkop; melding gebruiker 10 nov 2026: "6 bepalingen" opende er één). Buiten de
 *  werkplek is er geen gesprek om naast te staan, en dan geen kaart. */
export function BepalingChips({ bepalingen }: { bepalingen: readonly AntwoordVindplaats[] }) {
  const opener = useOpenBron();
  if (!opener || !bepalingen.length) return null;
  const open = (v: AntwoordVindplaats) =>
    opener({ soort: "bron", bron_iri: v.iri, titel: vindplaatsTekst(v), jci: v.jci || undefined });
  if (bepalingen.length > MAX_BEPALINGCHIPS) {
    const titel = `${bepalingen.length} bepalingen`;
    return (
      <div className="mt-3" data-bepaling-chips={bepalingen.length}>
        <BronChip titel={titel} sub="Bepalingen · bekijken" icoon={TEKSTICOON} data-bepaling-lijst={bepalingen.length}
          onClick={() => opener({ soort: "bepalingen", bepalingen: [...bepalingen], titel })} />
      </div>
    );
  }
  return (
    <div className="mt-3 space-y-2" data-bepaling-chips={bepalingen.length}>
      {bepalingen.map((v) => (
        <BronChip key={v.iri} titel={vindplaatsTekst(v)} sub="Bepaling · bekijken" icoon={TEKSTICOON} onClick={() => open(v)} data-bepaling-chip={v.iri} />
      ))}
    </div>
  );
}
