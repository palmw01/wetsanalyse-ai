"use client";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Prullenbak, Vinkje } from "@/components/ui/Icoon";

const SOORT = {
  verwijderen: { icoon: Prullenbak, vraag: "Verwijderen?", rust: "hover:text-fout",
    scherp: "border-aandacht-rood-rand bg-aandacht-rood-bg text-aandacht-rood-tekst hover:text-aandacht-rood-tekst" },
  akkoord: { icoon: Vinkje, vraag: "Akkoord?", rust: "hover:text-aandacht-groen-tekst",
    scherp: "border-aandacht-groen-rand bg-aandacht-groen-bg text-aandacht-groen-tekst hover:text-aandacht-groen-tekst" },
} as const;

/** Het icoon-idioom in rijen en lijsten (spoor I4, besluit 26 okt 2026): in rust een icoon – prullenbak of
 *  vinkje –; de eerste klik klapt het uit tot de handeling in kleur (rood *Verwijderen?*, groen *Akkoord?*),
 *  de tweede voert uit. Het ontwapent zoals elke `BevestigKnop`: na een paar seconden, bij blur of met
 *  Escape. Het `aria-label` noemt het object ("Verwijder voorbeeld 2"), want dezelfde knop staat in elke rij.
 *  De stijl van de oude gesprekkenlijst (vóór G1). */
export function IcoonBevestig({ soort, label, vraag, onBevestig, disabled, titel, className = "" }: {
  soort: keyof typeof SOORT;
  /** De vraag bij de eerste klik, als het niet *Verwijderen?* of *Akkoord?* is (bv. *Losmaken?*). */
  vraag?: string;
  /** De toegankelijke naam in rust: wat er gebeurt, met welk object. */
  label: string;
  onBevestig: () => void | Promise<void>;
  disabled?: boolean;
  titel?: string;
  className?: string;
}) {
  const s = SOORT[soort];
  const Icoon = s.icoon;
  return (
    <BevestigKnop
      onBevestig={onBevestig}
      bevestigTekst={vraag ?? s.vraag}
      ariaLabel={label}
      titel={titel ?? label}
      disabled={disabled}
      className={`focus-ring inline-flex min-h-[24px] min-w-[24px] shrink-0 items-center justify-center rounded-full border border-transparent px-1.5 text-xs font-medium text-muted transition-colors disabled:opacity-50 coarse:min-h-[44px] coarse:min-w-[44px] ${s.rust} ${className}`}
      bevestigClassName={`px-2.5 ${s.scherp}`}
    >
      <Icoon className="text-sm" />
    </BevestigKnop>
  );
}
