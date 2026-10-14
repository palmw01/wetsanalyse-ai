"use client";

import { Min, Passend, Plus, Terug } from "@/components/ui/Icoon";

const KNOP = "focus-ring flex h-9 w-9 items-center justify-center text-muted transition-colors hover:bg-surface hover:text-lint coarse:h-11 coarse:w-11";

/** Het beeld sturen, rechtsonder in het canvas: zoals de zoomknoppen van een kaart. *Naar het
 *  antwoord* en *Alles in beeld* zijn bewust twee knoppen: het begin (wat het antwoord noemt) en de
 *  hele kaart. */
export function GraafBeeld({ onPasIn, onZoom, onNaarAntwoord, terug = "het antwoord" }: {
  onPasIn: () => void; onZoom: (factor: number) => void;
  /** Keuze op en terug naar wat het antwoord noemt; zonder focus ontbreekt de knop. */
  onNaarAntwoord?: () => void;
  /** "het antwoord", of waar de graaf anders naar terugkeert. */
  terug?: string;
}) {
  return <div role="group" aria-label="Beeld" className="pointer-events-auto flex shrink-0 flex-col divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper/95 shadow-kaart">
    {onNaarAntwoord && <button type="button" className={KNOP} onClick={onNaarAntwoord} aria-label={`Naar ${terug}`} title={`Naar ${terug}`}><Terug /></button>}
    <button type="button" className={KNOP} onClick={onPasIn} aria-label="Alles in beeld" title="Alles in beeld"><Passend /></button>
    <button type="button" className={KNOP} onClick={() => onZoom(0.7)} aria-label="Inzoomen" title="Inzoomen"><Plus /></button>
    <button type="button" className={KNOP} onClick={() => onZoom(1.4)} aria-label="Uitzoomen" title="Uitzoomen"><Min /></button>
  </div>;
}
