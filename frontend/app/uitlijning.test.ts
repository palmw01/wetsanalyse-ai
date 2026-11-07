import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Uitlijning op elke breedte (7 nov 2026, melding van de gebruiker op een iPhone: filterknoppen die over twee regels
// liepen, kaartknoppen die ongelijk uit elkaar stonden). Elk patroon is één component in `components/ui`; deze toetsen
// houden de rest van de app daaraan. De browsertoets op 390 px staat in `scripts/test-werkgebieden.mjs`.

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
});
const tsx = () => [...alle("components"), ...alle("app")];

describe("filterchips staan in één KeuzeRij", () => {
  it("de rij wrapt nooit en scrolt horizontaal als hij niet past", () => {
    const chip = bron("components/ui/FilterChip.tsx");
    const rij = chip.slice(chip.indexOf("export const KEUZERIJ"), chip.indexOf("export function KeuzeRij"));
    expect(rij).toMatch(/overflow-x-auto/);
    expect(rij).toMatch(/overflow-y-hidden/);
    expect(rij).toMatch(/min-w-0/);
    expect(rij).not.toMatch(/flex-wrap/);
    // Een chip breekt zijn eigen tekst niet af en krimpt niet in de rij.
    const knop = chip.slice(chip.indexOf("export function FilterChip"), chip.indexOf("export const KEUZERIJ"));
    expect(knop).toMatch(/whitespace-nowrap/);
    expect(knop).toMatch(/shrink-0/);
  });

  it("wie een FilterChip gebruikt, zet hem in een KeuzeRij", () => {
    const los = tsx()
      .filter((f) => f !== "components/ui/FilterChip.tsx" && /<FilterChip\b/.test(bron(f)))
      .filter((f) => !/<KeuzeRij\b/.test(bron(f)));
    expect(los).toEqual([]);
  });

  it("de overzichtsbalk heeft een vaste indeling: chips en zoekveld op één regel vanaf sm", () => {
    const balk = bron("components/ui/OverzichtBalk.tsx");
    expect(balk).toMatch(/<KeuzeRij\b/);
    expect(balk).toMatch(/sm:grid-cols-\[minmax\(0,1fr\)_auto\]/);
    expect(balk).not.toMatch(/flex-wrap/);
  });
});

describe("een overzichtskaart eindigt in KaartActies", () => {
  const KAARTEN = ["components/werkgebieden/WerkgebiedKaart.tsx", "components/annotaties/AnnotatieKaart.tsx",
    "components/begrippen/BegripOverzichtKaart.tsx"];

  it("twee gelijke helften, even hoog", () => {
    const pagina = bron("components/ui/Pagina.tsx");
    const acties = pagina.slice(pagina.indexOf("export function KaartActies"), pagina.indexOf("export function Tellers"));
    expect(acties).toMatch(/grid grid-cols-2/);
    expect(acties).toMatch(/\[&>\*\]:w-full/);
    for (const f of KAARTEN) {
      const s = bron(f);
      expect(s, f).toMatch(/<KaartActies>/);
      expect(s, f).toMatch(/knopKlasse\("secondary", "sm"\)\}`\}>Openen</);
      expect(s, f).toMatch(/<VerwijderKnop[^>]*maat="sm"/);
      // Geen handgemaakte rijactie meer naast de knoppen.
      expect(s, f).not.toMatch(/text-\[11px\]/);
    }
  });

  it("Verwijderen springt nergens met ml-auto naar rechts, en deelt de maten van Button", () => {
    const metMarge = tsx().filter((f) => /<VerwijderKnop[^>]*ml-auto/.test(bron(f)));
    expect(metMarge).toEqual([]);
    const knop = bron("components/ui/VerwijderKnop.tsx");
    expect(knop).toMatch(/knopVorm\(maat\)/);
    expect(knop).not.toMatch(/min-h-\[|text-\[11px\]/);
  });
});
