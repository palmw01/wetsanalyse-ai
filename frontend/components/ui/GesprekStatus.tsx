import type { GesprekRunStand } from "@/lib/runStanden";

export const GESPREK_STATUS_TEKST: Record<GesprekRunStand, string> = {
  loopt: "Lex is bezig",
  nieuw: "Nieuw antwoord",
};

/** De stip achter een gesprek in de sidebar (E6): Lex is er bezig, of er staat een antwoord dat je nog niet zag.
 *  De stip is decoratief; de tekst staat er voor de schermlezer, zodat het signaal niet aan kleur hangt. Bezig
 *  pulseert, alleen als de gebruiker beweging toestaat. Geen knop en geen label: hij zegt iets over de rij. */
export function GesprekStatus({ stand }: { stand: GesprekRunStand }) {
  const tekst = GESPREK_STATUS_TEKST[stand];
  return (
    <span data-gesprek-status={stand} title={tekst} className="inline-flex shrink-0 items-center">
      <span
        aria-hidden
        className={`block size-2 rounded-full bg-lint ${stand === "loopt" ? "motion-safe:animate-pulse" : ""}`}
      />
      <span className="sr-only">{tekst}</span>
    </span>
  );
}
