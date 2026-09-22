"use client";

import { Melding } from "@/components/ui/Melding";
import { hergebruikTekst } from "@/lib/annotatie";
import type { AgentHergebruik } from "@/lib/types";

/** Bij een annotatie in het gesprek: kwam (een deel) uit de gedeelde laag, en de weg naar een nieuwe
 *  ronde.
 *
 *  Zonder deze melding leest een hergebruikte annotatie als een snelle nieuwe – en dan denkt de
 *  jurist dat Lex dezelfde bepaling twee keer precies gelijk annoteert, terwijl er in werkelijkheid
 *  niets opnieuw is bekeken. De knop maakt "opnieuw" een bewuste keuze: hij vult de laag aan, wat al
 *  beoordeeld is blijft staan.
 */
export function HergebruikMelding({
  hergebruik,
  onOpnieuw,
  uitgeschakeld,
}: {
  hergebruik?: AgentHergebruik;
  /** Ontbreekt dit, dan is er geen knop (bv. een laag die niet meer te openen is). */
  onOpnieuw?: () => void;
  uitgeschakeld?: boolean;
}) {
  return (
    <div className="mt-2 space-y-1.5">
      {hergebruik && (
        <Melding type="uitleg" compact>
          {hergebruikTekst(hergebruik)}
        </Melding>
      )}
      {onOpnieuw && (
        <button
          type="button"
          onClick={onOpnieuw}
          disabled={uitgeschakeld}
          title="Lex bekijkt de bepaling opnieuw en vult de annotatie aan. Wat al beoordeeld is blijft staan."
          className="focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-muted transition-colors hover:bg-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 coarse:min-h-[44px]"
        >
          Lex opnieuw laten annoteren
        </button>
      )}
    </div>
  );
}
