import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { GESPREK_STATUS_TEKST } from "@/components/ui/GesprekStatus";

const ROOT = join(__dirname, "..", "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((f) => {
    const pad = `${map}/${f}`;
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(f) && !f.includes(".test.") ? [pad] : [];
  });
}

// E6: de stip achter een gesprek is één component. Een tweede stip met eigen tekst loopt anders uit de pas.
describe("de stip van een gesprek", () => {
  it("is een decoratieve ronde stip met tekst voor de schermlezer", () => {
    const code = bron("components/ui/GesprekStatus.tsx");
    expect(code).toMatch(/aria-hidden/);
    expect(code).toMatch(/sr-only/);
    expect(code).toMatch(/rounded-full/);
    // Beweging alleen als de gebruiker die toestaat.
    expect(code).not.toMatch(/(?<!motion-safe:)animate-pulse/);
    // Geen knop en geen focus: hij zegt iets over de rij.
    expect(code).not.toMatch(/<button|focus-ring|tabIndex/);
    expect(GESPREK_STATUS_TEKST).toEqual({ loopt: "Lex is bezig", nieuw: "Nieuw antwoord" });
  });

  it("staat in de rijen van de sidebar, en de teksten staan nergens anders", () => {
    expect(bron("components/werkplek/GesprekLijst.tsx")).toMatch(/<GesprekStatus stand=/);
    for (const pad of [...bestanden("components"), ...bestanden("app")]) {
      if (pad === "components/ui/GesprekStatus.tsx") continue;
      expect(bron(pad), pad).not.toMatch(/"(Lex is bezig|Nieuw antwoord)"/);
    }
  });
});
