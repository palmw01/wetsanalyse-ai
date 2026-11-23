/** De bediening van een paneel naast het gesprek, eenduidig (besluit gebruiker 23 nov 2026): **één knop per handeling,
 *  met één label en één icoon, op één plek – de kop van het paneel – in een vaste volgorde**. Wat een paneel is, zegt het
 *  paneel zelf; wáár het staat (de plek) bepaalt welke knoppen er zijn. Puur, getest in `paneelBediening.test.ts`;
 *  `components/ui/Paneel.tsx` tekent de knoppen, en niemand anders (`app/paneelBediening.test.ts` bewaakt dat).
 *
 *  Er is één weg naar groot: *Vergroten* (de volle weergave binnen de werkplek). De pagina zelf is een link om te delen,
 *  *Openen als pagina* in het menu ⋯, geen tweede knop. Sluiten staat alleen in de kop, niet ook op de tabs. */

/** Een handeling van het paneel. Het menu ⋯ is `MeerMenu`, één component voor de hele app; het staat altijd vooraan. */
export type Handeling = "vergroten" | "verkleinen" | "inklappen" | "uitklappen" | "sluiten";

/** De vaste woorden en iconen (paden in een vak van 20×20). Nergens anders een eigen label of icoon hiervoor. */
export const HANDELINGEN: Record<Handeling, { label: string; titel: string; icoon: string }> = {
  vergroten: { label: "Vergroten", titel: "Vergroten: de volle weergave", icoon: "M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" },
  verkleinen: { label: "Verkleinen", titel: "Verkleinen: terug naast het gesprek", icoon: "M16 9h-5V4M4 11h5v5M11 9l6-6M9 11l-6 6" },
  inklappen: { label: "Paneel inklappen", titel: "Paneel inklappen", icoon: "M5 5l5 5-5 5M11 5l5 5-5 5" },
  uitklappen: { label: "Paneel uitklappen", titel: "Paneel uitklappen", icoon: "M15 5l-5 5 5 5M9 5l-5 5 5 5" },
  sluiten: { label: "Sluiten", titel: "Sluiten", icoon: "M5 5l10 10M15 5L5 15" },
};

/** Waar een paneel staat.
 *  - `paneel`: het zijpaneel naast het gesprek (breed);
 *  - `vergroot`: hetzelfde zijpaneel over de volle breedte van de werkplek;
 *  - `ingeklapt`: het zijpaneel als strook (de inhoud blijft gemount, de kop is niet te zien);
 *  - `sheet`: op een telefoon, het paneel als sheet over het gesprek;
 *  - `sheet-vergroot`: die sheet over het hele scherm;
 *  - `rondleiding`: het vaste paneel van de rondleiding (niets te vergroten of in te klappen);
 *  - `pagina`: op een eigen pagina, buiten de werkplek (geen bediening van een paneel). */
export type PaneelPlek = "paneel" | "vergroot" | "ingeklapt" | "sheet" | "sheet-vergroot" | "rondleiding" | "pagina";

/** De knoppen op een plek, in de vaste volgorde. Sluiten kan alleen als de werkplek het paneel kan sluiten. */
export function knoppenVoor(plek: PaneelPlek, { kanSluiten = true }: { kanSluiten?: boolean } = {}): Handeling[] {
  const knoppen: Handeling[] =
    plek === "paneel" ? ["vergroten", "inklappen", "sluiten"]
      : plek === "vergroot" ? ["verkleinen", "inklappen", "sluiten"]
        : plek === "ingeklapt" ? ["uitklappen", "sluiten"]
          : plek === "sheet" ? ["vergroten", "sluiten"]
            : plek === "sheet-vergroot" ? ["verkleinen", "sluiten"]
              : plek === "rondleiding" ? ["sluiten"]
                : [];
  return kanSluiten ? knoppen : knoppen.filter((k) => k !== "sluiten");
}

/** Is het paneel op deze plek groot (de volle weergave)? */
export function isVergroot(plek: PaneelPlek): boolean {
  return plek === "vergroot" || plek === "sheet-vergroot";
}

/** De stand van het zijpaneel: één waarde, niet drie losse vlaggen. */
export type Weergave = "normaal" | "vergroot" | "ingeklapt";

/** Wat de stand verandert. `escape`: Escape verkleint eerst, en klapt anders in (verbergen, niet sluiten);
 *  `nieuw`: iets anders geopend – een klik op een ingang moet zichtbaar iets doen, dus een strook klapt uit. */
export type Gebeurtenis = "vergroten" | "verkleinen" | "inklappen" | "uitklappen" | "escape" | "nieuw";

export function volgende(stand: Weergave, gebeurtenis: Gebeurtenis): Weergave {
  switch (gebeurtenis) {
    case "vergroten": return "vergroot";
    case "verkleinen": case "uitklappen": return "normaal";
    case "inklappen": return "ingeklapt";
    case "escape": return stand === "vergroot" ? "normaal" : "ingeklapt";
    case "nieuw": return stand === "ingeklapt" ? "normaal" : stand;
  }
}

/** De plek van het zijpaneel bij een stand (breed). */
export function plekVanWeergave(stand: Weergave, vast: boolean): PaneelPlek {
  if (vast) return "rondleiding";
  return stand === "vergroot" ? "vergroot" : stand === "ingeklapt" ? "ingeklapt" : "paneel";
}

/** Waar de stand bewaard wordt (per browser, `lib/opslag.ts`); telt alleen bij een herstelde inhoud. */
export const OPSLAG_WEERGAVE = "lex.paneel.weergave";

export function leesWeergave(ruw: unknown): Weergave | undefined {
  return ruw === "vergroot" || ruw === "ingeklapt" ? ruw : undefined;
}
