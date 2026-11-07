// De titel van het tabblad zegt of Lex bezig is (E6): wie in een ander tabblad werkt, ziet zo dat een antwoord
// binnen is, zonder browsermelding.
//
// - zolang er ergens een beurt loopt: `Bezig · <titel>`;
// - kwam er een antwoord binnen terwijl het tabblad verborgen was: `Klaar · <titel>`, tot je weer kijkt;
// - anders de gewone titel.

const VOORVOEGSEL = /^(Bezig|Klaar) · /;

/** De titel zonder ons voorvoegsel: na een hot reload of een tweede mount staat het er soms al. */
export function kaleTitel(titel: string): string {
  return titel.replace(VOORVOEGSEL, "");
}

export function tabTitel(basis: string, stand: { bezig: boolean; klaarVerborgen: boolean }): string {
  const kaal = kaleTitel(basis);
  // Klaar gaat voor: dat is het nieuws, ook als er elders nog iets loopt.
  if (stand.klaarVerborgen) return `Klaar · ${kaal}`;
  if (stand.bezig) return `Bezig · ${kaal}`;
  return kaal;
}
