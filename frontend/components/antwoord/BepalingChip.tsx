"use client";

import { useContext, type ReactNode } from "react";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import { ContextPaneelContext } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { vindplaatsTekst } from "@/lib/herkomst";

/** Hoeveel bepalingen een eigen chip krijgen; daarboven één chip die de eerste opent. De andere staan als link in de blokken. */
export const MAX_BEPALINGCHIPS = 3;

/** De chip onder een antwoord (het bronvenster, PR 4): de enige ingang naar wat het antwoord aanwijst – een bepaling als
 *  tab naast het gesprek, of de samenhang ervan in de graaf. Dezelfde vorm als de chip na een annotatie. */
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

/** De chips onder een sjabloonantwoord (ADR-008, *Detail bij een antwoord*): een klik opent de bepaling als tab naast het
 *  gesprek, met wat de graaf er verder over weet. Buiten de werkplek is er geen gesprek om naast te staan, en dan geen chip. */
export function BepalingChips({ bepalingen }: { bepalingen: readonly AntwoordVindplaats[] }) {
  const opener = useContext(ContextPaneelContext);
  if (!opener || !bepalingen.length) return null;
  const open = (v: AntwoordVindplaats) =>
    opener({ soort: "bron", bron_iri: v.iri, titel: vindplaatsTekst(v), jci: v.jci || undefined });
  const chips = bepalingen.length > MAX_BEPALINGCHIPS
    ? [{ v: bepalingen[0], titel: `${bepalingen.length} bepalingen`, sub: `Bepaling · bekijken, te beginnen bij ${bepalingen[0].label}` }]
    : bepalingen.map((v) => ({ v, titel: vindplaatsTekst(v), sub: "Bepaling · bekijken" }));
  return (
    <div className="mt-3 space-y-2" data-bepaling-chips={bepalingen.length}>
      {chips.map(({ v, titel, sub }) => (
        <BronChip key={v.iri} titel={titel} sub={sub} icoon={TEKSTICOON} onClick={() => open(v)} data-bepaling-chip={v.iri} />
      ))}
    </div>
  );
}

/** De samenhang van wat een antwoord of overzicht noemt, in de graaf (de tab *Samenhang*). Eén chip naast de bepalingen,
 *  in plaats van een losse knop eronder; de voorleesnaam blijft wat de knop zei. */
export function SamenhangChip({ titel, label, onClick }: { titel: string; label: string; onClick: () => void }) {
  return (
    <div className="mt-2">
      <BronChip titel={titel} sub="Graaf · bekijken" label={label} icoon={<GraafIcoon />} onClick={onClick} data-samenhang-chip="" />
    </div>
  );
}
