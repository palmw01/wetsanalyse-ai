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
export function TekeningVenster({ titel, onSluit, exporteer, children }: {
  titel: ReactNode;
  onSluit: () => void;
  exporteer?: { formaten: ("svg" | "png")[]; onDownload: (formaat: ExportFormaat) => Promise<void> };
  children: ReactNode;
}) {
  const [fout, setFout] = useState("");
  return (
    <Dialog label={typeof titel === "string" ? titel : "Tekening"} variant="fullscreen" onSluit={onSluit} kop={{ titel }}>
      <div className="flex min-h-0 flex-1 flex-col gap-2 p-3" data-tekening-venster>
        {exporteer && (
          <div className="flex items-center justify-end gap-2">
            {fout && <Melding type="fout" compact>{fout}</Melding>}
            <ExportKnop onFout={setFout} formaten={exporteer.formaten.map((f) => TEKENING_FORMATEN[f])}
              onDownload={async (f) => { setFout(""); await exporteer.onDownload(f); }} />
          </div>
        )}
        {children}
      </div>
    </Dialog>
  );
}
