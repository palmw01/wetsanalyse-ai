"use client";

import { useRouter } from "next/navigation";
import { IcoonKnop } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Kruis } from "@/components/ui/Icoon";
import type { TabKey } from "@/lib/instellingen";
import { InstellingenInhoud } from "./InstellingenInhoud";

/** Het instellingenvenster zoals je het vanuit de werkplek opent: een gecentreerde dialog over de
 *  chat heen. Sluiten gaat met `router.back()` – de intercepting route heeft een history-entry
 *  toegevoegd, dus daarmee land je terug op de werkplek zonder de pagina te herladen. */
export function InstellingenDialog({ actief, isBeheerder }: { actief: TabKey; isBeheerder: boolean }) {
  const router = useRouter();

  return (
    <Dialog label="Instellingen" variant="center" onSluit={() => router.back()}>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
        <h2 className="font-display text-base font-semibold text-lint">Instellingen</h2>
        <IcoonKnop size="sm" onClick={() => router.back()} aria-label="Instellingen sluiten"><Kruis /></IcoonKnop>
      </div>
      <InstellingenInhoud actief={actief} isBeheerder={isBeheerder} vervangHistorie />
    </Dialog>
  );
}
