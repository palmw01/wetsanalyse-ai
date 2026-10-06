/** De begroeting bij het uur van de dag, in de lokale tijd van de gebruiker. Puur: `nu` komt van
 *  buiten, zodat de grenzen te testen zijn en de server (die de tijd van de gebruiker niet kent)
 *  hem nooit hoeft te berekenen. */
export function begroeting(nu: Date): string {
  const uur = nu.getHours();
  if (uur < 6) return "Goedenacht";
  if (uur < 12) return "Goedemorgen";
  if (uur < 18) return "Goedemiddag";
  return "Goedenavond";
}

/** Wat er staat zolang de tijd van de gebruiker nog niet bekend is (server-render, eerste frame). */
export const BEGROETING_ZONDER_TIJD = "Welkom";
