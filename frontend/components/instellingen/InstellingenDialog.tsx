"use client";

import { IcoonKnop } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Kruis } from "@/components/ui/Icoon";
import type { TabKey } from "@/lib/instellingen";
import { sluitInstellingen } from "@/lib/instellingenVenster";
import { InstellingenInhoud } from "./InstellingenInhoud";

/** Het instellingenvenster: een gecentreerde dialog over de pagina heen. Sluiten haalt de parameter weg en laat de
 *  pagina eronder staan (`sluitInstellingen`). */
export function InstellingenDialog({ actief, isBeheerder }: { actief: TabKey; isBeheerder: boolean }) {
  return (
    <Dialog label="Instellingen" variant="center" onSluit={sluitInstellingen}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
        <h2 className="font-display text-base font-semibold text-lint">Instellingen</h2>
        <IcoonKnop size="sm" onClick={sluitInstellingen} aria-label="Instellingen sluiten"><Kruis /></IcoonKnop>
      </div>
      <InstellingenInhoud actief={actief} isBeheerder={isBeheerder} />
    </Dialog>
  );
}
