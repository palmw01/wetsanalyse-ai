"use client";

import { Dialog } from "@/components/ui/Dialog";
import type { TabKey } from "@/lib/instellingen";
import { sluitInstellingen } from "@/lib/instellingenVenster";
import { InstellingenInhoud } from "./InstellingenInhoud";

/** Het instellingenvenster: een gecentreerde dialog over de pagina heen. Sluiten haalt de parameter weg en laat de
 *  pagina eronder staan (`sluitInstellingen`). */
export function InstellingenDialog({ actief, isBeheerder }: { actief: TabKey; isBeheerder: boolean }) {
  return (
    <Dialog label="Instellingen" variant="center" onSluit={sluitInstellingen}
      kop={{ titel: "Instellingen", sluitLabel: "Instellingen sluiten" }}>
      <InstellingenInhoud actief={actief} isBeheerder={isBeheerder} />
    </Dialog>
  );
}
