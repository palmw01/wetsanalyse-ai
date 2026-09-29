"use client";

import { useEffect, useState } from "react";
import { Kruis } from "@/components/ui/Icoon";

const SLEUTEL = "wa_graaf_hint";

/** Eenmalige uitleg van de bediening, onder in het canvas. Verdwijnt bij de eerste eigen
 *  interactie (`klaar`) of met het kruisje, en blijft dan per kijker weg. Opslag kan ontbreken
 *  (privévenster): dan verschijnt de hint gewoon weer, verder gaat er niets mis. */
export function GraafHint({ klaar }: { klaar: boolean }) {
  const [gezien, setGezien] = useState(true);
  useEffect(() => {
    // Pas na de eerste render lezen: de server kent geen localStorage.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setGezien(localStorage.getItem(SLEUTEL) === "1"); } catch { setGezien(false); }
  }, []);
  useEffect(() => {
    if (!klaar || gezien) return;
    try { localStorage.setItem(SLEUTEL, "1"); } catch { /* geen opslag: alleen deze sessie */ }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setGezien(true);
  }, [klaar, gezien]);
  if (gezien) return null;
  return <p role="status" data-testid="graaf-hint" className="pointer-events-auto flex items-center gap-2 rounded-full border border-line bg-paper/95 py-1.5 pl-3 pr-1.5 text-[11px] text-muted shadow-kaart">
    Sleep: draaien · scroll: zoomen · dubbelklik: verbindingen
    <button type="button" aria-label="Uitleg sluiten" onClick={() => { try { localStorage.setItem(SLEUTEL, "1"); } catch { /* */ } setGezien(true); }}
      className="focus-ring rounded-full p-1 hover:bg-surface hover:text-ink"><Kruis /></button>
  </p>;
}
