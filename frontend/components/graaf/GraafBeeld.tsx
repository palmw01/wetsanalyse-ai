"use client";

import { Passend, Richten, Terug } from "@/components/ui/Icoon";

const KNOP = "focus-ring flex h-9 w-9 items-center justify-center text-muted transition-colors hover:bg-surface hover:text-lint coarse:h-11 coarse:w-11";

/** Het beeld sturen, rechtsonder in het canvas, voor de graaf en het 2c-diagram gelijk. *Alles in beeld* (vizier)
 *  centreert de hele tekening; *Groot bekijken* (hoeken naar buiten) opent alleen de tekening groot in een venster boven
 *  de pagina (`TekeningVenster`), met een kruisje om te sluiten. Dat is iets anders dan *Vergroten* van het paneel in de
 *  kop: dat blijft de enige weg naar een groot paneel (besluit 23 nov 2026). Geen knoppen voor in- en uitzoomen: dat gaat
 *  met het muiswiel en met twee vingers (melding gebruiker 24 nov 2026). *Naar het antwoord* staat er alleen bij een
 *  keuze. */
export function GraafBeeld({ onPasIn, onGroot, onNaarAntwoord, terug = "het antwoord" }: {
  onPasIn: () => void;
  /** Alleen de tekening groot in een venster; zonder (in dat venster zelf) ontbreekt de knop. */
  onGroot?: () => void;
  /** Keuze op en terug naar wat het antwoord noemt; zonder focus ontbreekt de knop. */
  onNaarAntwoord?: () => void;
  /** "het antwoord", of waar de graaf anders naar terugkeert. */
  terug?: string;
}) {
  return <div role="group" aria-label="Beeld" className="pointer-events-auto flex shrink-0 flex-col divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper/95 shadow-kaart">
    {onNaarAntwoord && <button type="button" className={KNOP} onClick={onNaarAntwoord} aria-label={`Naar ${terug}`} title={`Naar ${terug}`}><Terug /></button>}
    <button type="button" className={KNOP} onClick={onPasIn} aria-label="Alles in beeld" title="Alles in beeld"><Richten /></button>
    {onGroot && <button type="button" className={KNOP} onClick={onGroot} aria-label="Groot bekijken" title="Groot bekijken"><Passend /></button>}
  </div>;
}
