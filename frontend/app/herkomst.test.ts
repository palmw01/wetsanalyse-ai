import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

// Het bronvenster (PR 1, kernprincipe van de gebruiker 9 nov 2026: generieke componenten in plaats van deeloplossingen):
// de herkomst van een bepaling – welke wet, waar in de wet, welke stand – komt uit één plek, `lib/herkomst.ts`. Geen
// component bouwt zelf "label, regeling", geen tweede korte vindplaats, geen eigen melding over de stand.
const ROOT = join(__dirname, "..");

function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const CODE = ["app", "components", "lib"].flatMap(bestanden);
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

describe("de herkomst van een bepaling komt uit één plek", () => {
  it("geen eigen `${…label}, ${…regeling}` buiten lib/herkomst.ts", () => {
    const fout = CODE.filter((p) => p !== join("lib", "herkomst.ts") && /\$\{[^}]*\.label\}, \$\{[^}]*\.regeling\}/.test(bron(p)));
    expect(fout).toEqual([]);
  });

  it("één korte vindplaats van een annotatie, en één opschrift", () => {
    const exporteurs = CODE.filter((p) => /export function vindplaatsLabel\b/.test(bron(p))).map((p) => relative(".", p));
    // `lib/samenhang.ts` is de spiegel van `bronmodel.vindplaats` (de jci-vectoren toetsen hem); geen tweede.
    expect(exporteurs).toEqual([join("lib", "samenhang.ts")]);
    expect(CODE.filter((p) => /\bannotatieOpschrift\b/.test(bron(p)))).toEqual([]);
    expect(CODE.filter((p) => /export function (plaatsZin|afwijkendeToestand|bepalingKort)\b/.test(bron(p))))
      .toEqual([join("lib", "herkomst.ts")]);
  });

  it("de stand meldt zich via StandMelding, niet met een eigen zin", () => {
    expect(CODE.filter((p) => /nog niet in werking getreden/.test(bron(p)))).toEqual([join("lib", "herkomst.ts")]);
    expect(CODE.some((p) => /NogNietInWerking/.test(bron(p)))).toBe(false);
  });

  it("het paneel van een bepaling krijgt zijn kop van de herkomst", () => {
    const paneel = bron("components/werkplek/ContextPaneel.tsx");
    expect(paneel).toMatch(/herkomstKop\(/);
    expect(paneel).toMatch(/<HerkomstRegel /);
  });
});
