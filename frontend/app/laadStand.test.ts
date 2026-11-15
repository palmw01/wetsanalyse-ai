import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén laadstand (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §2): het laden,
 *  de fout met *Opnieuw proberen* en de stand "verwijderd" stonden in acht panelen en tabs met de hand, met drie
 *  soorten titels ("Niet geladen", "Het X kon niet worden geladen.", geen) en vier herstelknoppen. Nu is het `LaadStand`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app"), ...alle("lib")];
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("een object laden is LaadStand", () => {
  it("Opnieuw proberen staat alleen in LaadStand en op een paar plekken met een eigen vorm", () => {
    const eigenVorm = new Set([
      "components/ui/LaadStand.tsx",
      "components/ui/Melding.tsx", // het voorbeeld in de uitleg van MeldingActie
      "app/error.tsx", "app/global-error.tsx", // de foutgrenzen van Next
      "components/graaf/Graaf.tsx", "components/graaf/useGraafStand.ts", // de melding midden op het graafcanvas
      "components/werkplek/ConnectorsMenu.tsx", // een regel in het menu
      "components/werkplek/WerkplekClient.tsx", // de geschiedenis boven het gesprek, die ook "weg" kan zijn
      "components/werkgebieden/BronnenBijDeelvraag.tsx", // de bronnen staan er, alleen de indeling ontbreekt
    ]);
    expect(bestanden.filter((p) => !eigenVorm.has(p) && lees(p).includes("Opnieuw proberen"))).toEqual([]);
  });

  it("geen eigen laadstand of titel 'Niet geladen' naast LaadStand", () => {
    const fout = bestanden.filter((p) => p !== "components/ui/LaadStand.tsx")
      .filter((p) => /function \w*LaadStand\b|titel="Niet geladen"/.test(lees(p)));
    expect(fout).toEqual([]);
  });

  it("de titel zegt wat niet geladen is, en herhaalt de foutzin niet", () => {
    const s = lees("components/ui/LaadStand.tsx");
    expect(s).toContain("`${wat} kon niet worden geladen.`");
    expect(s).toContain("fout === titel ? null : fout");
  });
});
