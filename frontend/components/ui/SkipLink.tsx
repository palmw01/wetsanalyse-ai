// "Naar de hoofdinhoud" — WCAG 2.4.2 (Bypass Blocks, niveau A). De schermen met een schil zetten
// een blijvende sidebar met de chatgeschiedenis vóór de inhoud; zonder deze link tabt een
// toetsenbordgebruiker daar elke keer helemaal doorheen.
//
// Onzichtbaar tot hij focus krijgt (`sr-only` + `focus:not-sr-only`), dan verschijnt hij
// linksboven. Kleur en focusring komen uit de huisstijl-tokens, niet uit losse waarden.

export const HOOFDINHOUD_ID = "hoofdinhoud";

export function SkipLink() {
  return (
    <a
      href={`#${HOOFDINHOUD_ID}`}
      className="focus-ring sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-field focus:bg-paper focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-ink focus:shadow-lg"
    >
      Naar de hoofdinhoud
    </a>
  );
}
