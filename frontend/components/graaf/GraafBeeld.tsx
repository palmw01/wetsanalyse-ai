"use client";

import { Passend, Terug } from "@/components/ui/Icoon";

const KNOP = "focus-ring flex h-9 w-9 items-center justify-center text-muted transition-colors hover:bg-surface hover:text-lint coarse:h-11 coarse:w-11";

/** Het beeld sturen, rechtsonder in het canvas, voor de graaf en het 2c-diagram gelijk. Eén knop terug (pijl): een keuze
 *  vervalt en de hele tekening komt weer in beeld. Eerder waren dat twee knoppen (*Naar het antwoord* en *Alles in
 *  beeld*), die in de praktijk hetzelfde deden (melding gebruiker 24 nov 2026). *Groot bekijken* (hoeken naar buiten)
 *  opent alleen de tekening groot in een venster boven de pagina (`TekeningVenster`); het paneel groot maken blijft
 *  *Vergroten* in de kop (besluit 23 nov 2026). Geen knoppen voor in- en uitzoomen: dat gaat met het muiswiel en met
 *  twee vingers. */
export function GraafBeeld({ onTerug, onGroot }: {
  /** Keuze weg en alles in beeld. */
  onTerug: () => void;
  /** Alleen de tekening groot in een venster; zonder (in dat venster zelf) ontbreekt de knop. */
  onGroot?: () => void;
}) {
  return <div role="group" aria-label="Beeld" className="pointer-events-auto flex shrink-0 flex-col divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper/95 shadow-kaart">
    <button type="button" className={KNOP} onClick={onTerug} aria-label="Alles in beeld" title="Terug: alles in beeld"><Terug /></button>
    {onGroot && <button type="button" className={KNOP} onClick={onGroot} aria-label="Groot bekijken" title="Groot bekijken"><Passend /></button>}
  </div>;
}
