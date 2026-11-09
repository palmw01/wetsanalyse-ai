import { Melding } from "@/components/ui/Melding";
import type { StandMeldingData } from "@/lib/herkomst";

/** Wat er over de stand van een bron te zeggen valt (`standMeldingen` in `lib/herkomst.ts`): nog niet in werking, een
 *  nieuwere toestand dan Lex las, een stand ná de peildatum. Eén melding per geval, overal dezelfde zin. */
export function StandMelding({ meldingen }: { meldingen: readonly StandMeldingData[] }) {
  if (!meldingen.length) return null;
  return (
    <div className="space-y-1.5">
      {meldingen.map((m) => (
        <Melding key={m.soort} type="waarschuwing" compact><span data-stand-melding={m.soort}>{m.tekst}</span></Melding>
      ))}
    </div>
  );
}
