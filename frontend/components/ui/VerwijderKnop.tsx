"use client";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { VERWIJDER_UITLEG, verwijderLabel, type VerwijderSoort } from "@/lib/verwijderen";

/** De ene verwijderknop voor een annotatie, een werkgebied en een begrip – in het paneel naast het
 *  gesprek, op de pagina en per rij in de lijst (`lib/verwijderen.ts`). Altijd *Verwijderen*, de
 *  tweede klik bevestigt (*Verwijderen?*), de tooltip zegt wat er weggaat en wat blijft. */
export function VerwijderKnop({ soort, onBevestig, disabled, className = "" }: {
  soort: VerwijderSoort;
  onBevestig: () => void | Promise<void>;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <BevestigKnop
      onBevestig={onBevestig}
      bevestigTekst="Verwijderen?"
      ariaLabel={verwijderLabel(soort)}
      titel={VERWIJDER_UITLEG[soort]}
      disabled={disabled}
      className={`focus-ring inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-muted transition-colors hover:border-fout/40 hover:text-fout disabled:opacity-60 coarse:min-h-[44px] coarse:px-3 ${className}`}
      bevestigClassName="border-fout bg-fout text-paper hover:text-paper"
    >
      Verwijderen
    </BevestigKnop>
  );
}
