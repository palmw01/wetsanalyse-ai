"use client";

import { Button } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";

/** "Je hebt niet-bewaarde wijzigingen": de vraag vóór een wissel die ze zou weggooien. In de pagina
 *  zelf, geen systeemvenster (zie `BevestigKnop` voor waarom). */
export function OnbewaardMelding({ onBlijf, onToch, className = "" }: {
  onBlijf: () => void;
  onToch: () => void;
  className?: string;
}) {
  return (
    <Melding type="waarschuwing" titel="Niet-bewaarde wijzigingen" className={className}>
      <p>Op de begripskaart staan wijzigingen die nog niet zijn opgeslagen. Wisselen gooit ze weg.</p>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <Button size="sm" variant="secondary" onClick={onBlijf}>
          Blijf hier
        </Button>
        <Button size="sm" variant="danger" onClick={onToch}>
          Toch wisselen
        </Button>
      </div>
    </Melding>
  );
}
