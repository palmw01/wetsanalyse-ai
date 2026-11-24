"use client";

import { useState, type ReactNode } from "react";

import { Dialog } from "@/components/ui/Dialog";
import { Melding } from "@/components/ui/Melding";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import type { ExportFormaat } from "@/lib/api";

/** De vormen waarin een tekening te bewaren is; een tekening kiest er een of meer. */
export const TEKENING_FORMATEN: Record<"svg" | "png", { formaat: ExportFormaat; label: string; uitleg: string }> = {
  svg: { formaat: "svg", label: "SVG", uitleg: "vectortekening, scherp op elk formaat; ook om te bewerken" },
  png: { formaat: "png", label: "PNG", uitleg: "afbeelding om in een document of presentatie te plakken" },
};

/** Een tekening (de graaf, een 2c-diagram) groot in een venster boven de pagina, met haar titel en een kruisje: *Groot
 *  bekijken* in `GraafBeeld` (melding gebruiker 24 nov 2026). Alleen de tekening, niet het paneel: het paneel groot maken
 *  blijft *Vergroten* in de kop. Bovenaan *Exporteren*, dezelfde knop als bij een annotatie of rapport (`ExportKnop`),
 *  met de vormen die de tekening kent. De inhoud vult het venster; Escape en de achtergrond sluiten. */
export function TekeningVenster({ titel, omschrijving, onSluit, exporteer, children }: {
  /** Waar de tekening over gaat ("Samenhang van Artikel 9, lid 1", "Rond rechtsbetrekking …"), niet wat voor tekening. */
  titel: ReactNode;
  /** Een regel onder de kop, links naast *Exporteren* (alleen zonder eigen kop van de tekening). */
  omschrijving?: ReactNode;
  onSluit: () => void;
  exporteer?: { formaten: ("svg" | "png")[]; onDownload: (formaat: ExportFormaat) => Promise<void> };
  /** De tekening. Heeft ze een eigen kop (de graaf: titel, telling, uitleg), geef dan een functie: die krijgt
   *  *Exporteren* mee en zet hem naast haar kop, zodat er geen eigen regel voor nodig is en de tekening meer ruimte
   *  houdt. Anders staat de knop rechtsboven op een eigen regel. */
  children: ReactNode | ((exporteren: ReactNode) => ReactNode);
}) {
  const [fout, setFout] = useState("");
  const knop = exporteer && (
    <div className="flex shrink-0 items-center justify-end gap-2">
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      <ExportKnop onFout={setFout} formaten={exporteer.formaten.map((f) => TEKENING_FORMATEN[f])}
        onDownload={async (f) => { setFout(""); await exporteer.onDownload(f); }} />
    </div>
  );
  const eigenKop = typeof children === "function";
  return (
    <Dialog label={typeof titel === "string" ? titel : "Tekening"} variant="fullscreen" onSluit={onSluit} kop={{ titel }}>
      <div className="flex min-h-0 flex-1 flex-col" data-tekening-venster>
        {eigenKop ? children(knop) : <>
          {/* Dezelfde regel als de kop van de graaf: links de omschrijving, rechts Exporteren, op de marges van de titel. */}
          {(omschrijving || knop) && <div className="flex shrink-0 items-center gap-3 border-b border-line px-5 py-2.5">
            <p className="min-w-0 flex-1 text-xs text-muted">{omschrijving}</p>{knop}</div>}
          <div className="flex min-h-0 flex-1 flex-col p-3">{children}</div>
        </>}
      </div>
    </Dialog>
  );
}
