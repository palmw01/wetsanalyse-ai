"use client";

import { useEffect, useState } from "react";

import { Button, KNOP_XS } from "@/components/ui/Button";
import { Potlood } from "@/components/ui/Icoon";
import { foutTekst } from "@/lib/api";
import { bewerkToets, isGewijzigd } from "@/lib/bewerken";

/** Eén manier van bewerken in heel Lex (4 nov 2026, naar het voorbeeld van Claude: een bericht ter plekke
 *  aanpassen). De knop *Bewerken* staat bij het blok zelf (`BewerkKnop`); de tekst wordt op dezelfde plek een
 *  invoerveld, met daaronder rechts *Annuleren* · *Opslaan* (`BewerkVoet`). Escape annuleert, Ctrl/⌘+Enter slaat op,
 *  Enter in een veld van één regel ook (`useBewerken().toetsen`). Een fout staat bij het veld, niet achter een
 *  venster. Geen pop-up om tekst te bewerken; een keuze die meteen geldt (een klasse, een rol) en een selectie in een
 *  boom (bronnen koppelen) vallen hierbuiten. */

/** De pil *Bewerken* met een potloodje, rechts in de kop van het blok of de rij. `wat` maakt de naam ("Deelvraag
 *  bewerken"), want dezelfde knop staat bij elk blok en een schermlezer moet horen bij welk. */
export function BewerkKnop({ wat, onClick, disabled, className = "" }: {
  wat: string; onClick: () => void; disabled?: boolean; className?: string;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={`${wat} bewerken`} data-bewerk-knop
      className={`${KNOP_XS} border-line text-lint hover:border-lint hover:bg-lint/5 ${className}`}>
      <Potlood className="text-sm" />Bewerken
    </button>
  );
}

/** De voet onder een veld dat je bewerkt: rechts *Annuleren* (rustig) · *Opslaan* (primair). Opslaan staat uit zolang
 *  er niets veranderd is, en zegt *Bezig…* tijdens het opslaan. `submit`: de voet staat in een `<form>`. */
export function BewerkVoet({ onAnnuleer, onOpslaan, bezig, gewijzigd, opslaanTekst = "Opslaan", submit = false, fout }: {
  onAnnuleer: () => void;
  onOpslaan?: () => void;
  bezig: boolean;
  gewijzigd: boolean;
  opslaanTekst?: string;
  submit?: boolean;
  fout?: string | null;
}) {
  return (
    <div className="mt-2" data-bewerk-voet>
      {fout && <p role="alert" className="mb-2 text-sm text-fout">{fout}</p>}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" size="sm" onClick={onAnnuleer} disabled={bezig} className="w-full sm:w-auto">
          Annuleren
        </Button>
        <Button type={submit ? "submit" : "button"} size="sm" onClick={submit ? undefined : onOpslaan}
          disabled={bezig || !gewijzigd} className="w-full sm:w-auto">
          {bezig ? "Bezig…" : opslaanTekst}
        </Button>
      </div>
    </div>
  );
}

/** Concept, open/dicht, opslaan en de toetsen van één bewerkveld. `opslaan` mag gooien: de fout blijft bij het veld en
 *  het veld blijft open. `onOnbewaard` meldt aan de bewaker van niet-bewaarde wijzigingen (`useOnbewaardBewaker`) of
 *  er iets openstaat dat nog niet bewaard is. */
export function useBewerken<T>({ begin, opslaan, onOnbewaard }: {
  begin: T;
  opslaan: (nu: T) => Promise<unknown> | unknown;
  onOnbewaard?: (onbewaard: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [concept, zet] = useState<T>(begin);
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const gewijzigd = open && isGewijzigd(begin, concept);
  useEffect(() => { onOnbewaard?.(gewijzigd); }, [gewijzigd, onOnbewaard]);
  const start = () => { zet(begin); setFout(null); setOpen(true); };
  const annuleer = () => { if (bezig) return; setOpen(false); setFout(null); zet(begin); };
  const slaOp = async () => {
    if (bezig || !isGewijzigd(begin, concept)) { if (!bezig) setOpen(false); return; }
    setBezig(true); setFout(null);
    try {
      const uit = await opslaan(concept);
      // `false` van de aanroeper: niet gelukt, maar de fout staat al elders (een `muteer` die zelf meldt).
      if (uit !== false) setOpen(false);
    } catch (e) {
      setFout(foutTekst(e, "Niet opgeslagen."));
    } finally {
      setBezig(false);
    }
  };
  /** `onKeyDown` voor een veld: `regel` = één regel (Enter slaat op). */
  const toetsen = (regel: boolean) => (e: React.KeyboardEvent) => {
    const wat = bewerkToets({ key: e.key, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey,
      isComposing: e.nativeEvent.isComposing }, regel);
    if (!wat) return;
    e.preventDefault();
    // Escape hoort bij dit veld: het pelt niet ook nog een paneel of venster af.
    e.stopPropagation();
    if (wat === "annuleren") annuleer();
    else void slaOp();
  };
  return { open, start, concept, zet, annuleer, slaOp, bezig, fout, gewijzigd, toetsen };
}
