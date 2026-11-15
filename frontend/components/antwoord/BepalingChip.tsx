"use client";

import { PaneelChip, chipSub } from "@/components/ui/PaneelChip";
import { useOpenBron } from "@/components/werkplek/ContextPaneel";
import type { AntwoordVindplaats } from "@/lib/antwoord";
import { vindplaatsTekst } from "@/lib/herkomst";

/** Hoeveel bepalingen een eigen kaart krijgen; daarboven één kaart met de telling, die de lijst in het paneel opent. */
export const MAX_BEPALINGCHIPS = 3;

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
        <PaneelChip titel={titel} sub={chipSub("Bepalingen", "bekijken")} icoon={TEKSTICOON} data-bepaling-lijst={bepalingen.length}
          onClick={() => opener({ soort: "bepalingen", bepalingen: [...bepalingen], titel })} />
      </div>
    );
  }
  return (
    <div className="mt-3 space-y-2" data-bepaling-chips={bepalingen.length}>
      {bepalingen.map((v) => (
        <PaneelChip key={v.iri} titel={vindplaatsTekst(v)} sub={chipSub("Bepaling", "bekijken")} icoon={TEKSTICOON} onClick={() => open(v)} data-bepaling-chip={v.iri} />
      ))}
    </div>
  );
}
