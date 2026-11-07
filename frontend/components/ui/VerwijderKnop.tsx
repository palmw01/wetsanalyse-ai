"use client";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { knopVorm } from "@/components/ui/Button";
import { VERWIJDER_UITLEG, verwijderLabel, type VerwijderSoort } from "@/lib/verwijderen";

/** De ene verwijderknop voor een annotatie, een werkgebied en een begrip – in het paneel naast het
 *  gesprek, op de pagina en per rij in de lijst (`lib/verwijderen.ts`). Altijd *Verwijderen*, de
 *  tweede klik bevestigt (*Verwijderen?*), de tooltip zegt wat er weggaat en wat blijft. In de maat van de knoppen
 *  ernaast (`knopVorm`): `xs` tussen de kleine gereedschappen van een paneelkop, `sm` in `KaartActies`. */
export function VerwijderKnop({ soort, onBevestig, disabled, maat = "xs", className = "" }: {
  soort: VerwijderSoort;
  maat?: "xs" | "sm";
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
      className={`focus-ring ${knopVorm(maat)} border-line text-muted hover:border-fout/40 hover:text-fout ${className}`}
      bevestigClassName="border-fout bg-fout text-paper hover:text-paper"
    >
      Verwijderen
    </BevestigKnop>
  );
}
