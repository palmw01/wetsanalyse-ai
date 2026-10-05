"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { GraafIcoon } from "@/components/graaf/GraafIcoon";
import type { NodeDoel } from "@/lib/annotatieNode";
import { plaatsPopover } from "@/lib/popover";
import { bronDoel, haalSamenhang } from "@/lib/samenhang";
import type { Bron } from "@/lib/types";
import { bronHref } from "@/lib/url";

const BREEDTE = 320;

/** Een vindplaats in het antwoord van Lex die bij een bron van de beurt hoort. De vermelding blijft
 *  de tekst zelf (wat je kopieert verandert niet); een klik opent een bronkaart met de bepaling.
 *
 *  Een knop en geen `Popover`: die is een `div`, en een vermelding staat midden in een alinea. De
 *  kaart hangt daarom via een portal aan de body, geplaatst zoals de selectiepopover. */
export function CitatieChip({ bron, children, onOpenSamenhang }: {
  bron: Bron; children: ReactNode; onOpenSamenhang?: (doel: NodeDoel) => void;
}) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const knop = useRef<HTMLButtonElement>(null);
  const doel = bronDoel(bron.uri);
  return <>
    <button ref={knop} type="button" aria-haspopup="dialog" aria-expanded={!!rect}
      onClick={(e) => setRect(rect ? null : e.currentTarget.getBoundingClientRect())}
      className="focus-ring inline rounded-sm text-lint underline decoration-lint/40 decoration-dotted underline-offset-2 hover:bg-lint/5"
      title={`Bron: ${doel?.label ?? bron.label}`}>
      {children}
    </button>
    {rect && doel && createPortal(
      <BronKaart doel={doel} bron={bron} rect={rect} onOpenSamenhang={onOpenSamenhang}
        onSluit={() => { setRect(null); knop.current?.focus(); }} />,
      document.body)}
  </>;
}

function BronKaart({ doel, bron, rect, onSluit, onOpenSamenhang }: {
  doel: NodeDoel; bron: Bron; rect: DOMRect; onSluit: () => void; onOpenSamenhang?: (doel: NodeDoel) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [tekst, setTekst] = useState<string>();
  const [fout, setFout] = useState(false);
  useEffect(() => {
    let weg = false;
    haalSamenhang(doel).then((s) => {
      if (!weg) setTekst(s.knopen.find((k) => k.id === doel.bron_iri)?.tekst ?? "");
    }, () => { if (!weg) setFout(true); });
    return () => { weg = true; };
  }, [doel]);
  useEffect(() => {
    ref.current?.focus();
    const opToets = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onSluit(); } };
    const opKlik = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onSluit(); };
    document.addEventListener("keydown", opToets, true);
    document.addEventListener("mousedown", opKlik);
    return () => { document.removeEventListener("keydown", opToets, true); document.removeEventListener("mousedown", opKlik); };
  }, [onSluit]);
  const plek = plaatsPopover({ midden: rect.left + rect.width / 2, boven: rect.top, onder: rect.bottom },
    { breedte: BREEDTE, hoogte: 220 }, { breedte: window.innerWidth, hoogte: window.innerHeight });
  const href = bronHref(bron.uri);
  return <div ref={ref} role="dialog" aria-label={`Bron: ${doel.label ?? "bepaling"}`} tabIndex={-1} data-testid="bronkaart"
    style={{ position: "fixed", top: plek.top, left: plek.left, width: BREEDTE }}
    className="z-50 rounded-kaart border border-line bg-paper p-3 text-left text-xs shadow-kaart outline-none">
    <p className="font-semibold text-lint">{doel.label ?? bron.label}</p>
    <p className="mt-1.5 max-h-32 overflow-y-auto leading-relaxed text-ink">
      {fout ? <span className="text-muted">De tekst kon niet worden opgehaald.</span>
        : tekst === undefined ? <span className="text-muted">Tekst ophalen…</span>
        : tekst || <span className="text-muted">Deze bepaling heeft geen eigen tekst.</span>}
    </p>
    <div className="mt-2 flex flex-wrap items-center gap-3">
      {href && <a href={href} target="_blank" rel="noopener noreferrer" className="text-lint underline underline-offset-2">wetten.overheid.nl</a>}
      {onOpenSamenhang && <button type="button" onClick={() => { onSluit(); onOpenSamenhang(doel); }}
        className="focus-ring inline-flex items-center gap-1 rounded text-lint underline underline-offset-2 hover:no-underline">
        <GraafIcoon />Bekijk samenhang in 3D</button>}
    </div>
  </div>;
}
