"use client";

import { Passend, Richten, Terug, Verkleinen } from "@/components/ui/Icoon";

const KNOP = "focus-ring flex h-9 w-9 items-center justify-center text-muted transition-colors hover:bg-surface hover:text-lint coarse:h-11 coarse:w-11";

/** Het beeld sturen, rechtsonder in het canvas, voor de graaf en het 2c-diagram gelijk. *Alles in beeld* (vizier)
 *  centreert de hele tekening; *Vergroten* (hoeken naar buiten) zet het paneel groot over het venster, zodat de
 *  tekening goed te zien is, en *Verkleinen* zet het terug – dezelfde stand als *Vergroten* in de kop van het paneel,
 *  dus één weg naar groot. Geen knoppen voor in- en uitzoomen: dat gaat met het muiswiel en met twee vingers (melding
 *  gebruiker 24 nov 2026). *Naar het antwoord* staat er alleen bij een keuze. */
export function GraafBeeld({ onPasIn, onVergroot, vergroot = false, onNaarAntwoord, terug = "het antwoord" }: {
  onPasIn: () => void;
  /** Het paneel groot of terug; zonder (een pagina die al groot is) ontbreekt de knop. */
  onVergroot?: () => void;
  vergroot?: boolean;
  /** Keuze op en terug naar wat het antwoord noemt; zonder focus ontbreekt de knop. */
  onNaarAntwoord?: () => void;
  /** "het antwoord", of waar de graaf anders naar terugkeert. */
  terug?: string;
}) {
  return <div role="group" aria-label="Beeld" className="pointer-events-auto flex shrink-0 flex-col divide-y divide-line overflow-hidden rounded-kaart border border-line bg-paper/95 shadow-kaart">
    {onNaarAntwoord && <button type="button" className={KNOP} onClick={onNaarAntwoord} aria-label={`Naar ${terug}`} title={`Naar ${terug}`}><Terug /></button>}
    <button type="button" className={KNOP} onClick={onPasIn} aria-label="Alles in beeld" title="Alles in beeld"><Richten /></button>
    {onVergroot && <button type="button" className={KNOP} onClick={onVergroot} aria-label={vergroot ? "Verkleinen" : "Vergroten"}
      title={vergroot ? "Verkleinen" : "Vergroten"} aria-pressed={vergroot}>{vergroot ? <Verkleinen /> : <Passend />}</button>}
  </div>;
}
