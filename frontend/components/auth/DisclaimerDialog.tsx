"use client";

import { useRouter } from "next/navigation";

import { DisclaimerClient } from "@/components/auth/DisclaimerClient";
import { Dialog } from "@/components/ui/Dialog";

/** De voorwaarden zoals je ze vanuit de werkplek naleest: een dialog over de chat heen, net als de
 *  instellingen. Sluiten met `router.back()` – de intercepting route heeft een history-entry
 *  toegevoegd, dus je landt terug op precies de plek in je gesprek waar je was.
 *
 *  De blokkerende variant (nog geen akkoord) is de volle pagina `app/disclaimer/page.tsx`: dan stuurt
 *  de edge-gate je hierheen vóórdat de app rendert en is er niets om overheen te leggen. Beide tonen
 *  dezelfde `DisclaimerClient`, zodat de tekst maar op één plek bestaat. */
export function DisclaimerDialog({ alGeaccepteerd }: { alGeaccepteerd: boolean }) {
  const router = useRouter();
  // Eén sluitweg voor het kruisje, de achtergrondklik, Escape én de knop onderin. Die laatste was een
  // link naar `/` en liet de dialoog juist openstaan.
  const sluit = () => router.back();

  return (
    // Ook hier volgt de hoogte de inhoud: de voorwaarden zijn een half scherm tekst, geen venster
    // van 42rem.
    <Dialog label="Voorwaarden testomgeving" variant="compact" onSluit={sluit}
      kop={{ titel: "Voordat je begint", sluitLabel: "Voorwaarden sluiten" }}>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <DisclaimerClient alGeaccepteerd={alGeaccepteerd} onSluiten={sluit} />
      </div>
    </Dialog>
  );
}
