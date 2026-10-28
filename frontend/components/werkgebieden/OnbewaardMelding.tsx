"use client";

import { Button } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";

const WERKWOORD = { wisselen: "Wisselen", verlaten: "Verlaten", sluiten: "Sluiten" } as const;

/** "Je hebt niet-bewaarde wijzigingen": de vraag vóór een wissel die ze zou weggooien. In de pagina
 *  zelf, geen systeemvenster (zie `BevestigKnop` voor waarom). */
export function OnbewaardMelding({ onBlijf, onToch, handeling = "wisselen", className = "" }: {
  onBlijf: () => void;
  /** Wat er wacht: een wissel binnen de pagina, de pagina verlaten of het paneel sluiten. */
  handeling?: keyof typeof WERKWOORD;
  onToch: () => void;
  className?: string;
}) {
  return (
    <Melding type="waarschuwing" titel="Niet-bewaarde wijzigingen" className={className}>
      <p>Op de begripskaart staan wijzigingen die nog niet zijn opgeslagen. {WERKWOORD[handeling]} gooit ze weg.</p>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <Button size="sm" variant="secondary" onClick={onBlijf}>
          Blijf hier
        </Button>
        <Button size="sm" variant="danger" onClick={onToch}>
          Toch {handeling}
        </Button>
      </div>
    </Melding>
  );
}
