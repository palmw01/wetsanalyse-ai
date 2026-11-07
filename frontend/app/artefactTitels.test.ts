import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((n) => {
    const pad = join(map, n);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(n) && !/\.test\./.test(n) ? [pad] : [];
  });
}

// Besluit gebruiker 7 nov 2026: alle artefacten noemen zich op dezelfde manier, kort, en zonder de naam van het
// werkgebied (die staat al in de chatkop en het kruimelpad). De regel staat in `artefactKop` (`lib/artefact.ts`).
describe("de titel van een artefact", () => {
  it("een paneelkop krijgt zijn soort uit één namentabel, niet als losse tekst", () => {
    for (const pad of bestanden("components")) {
      for (const m of bron(pad).matchAll(/<PaneelKop\b[^>]*?\bsoort="([^"]*)"/g))
        expect.fail(`${pad}: <PaneelKop soort="${m[1]}"> – gebruik artefactKop of ARTEFACT_SOORT_LABEL`);
    }
  });

  it("chip, paneel en de balk laatste artefact gebruiken artefactKop", () => {
    expect(bron("components/werkplek/ThreadRij.tsx")).toMatch(/artefactKop\(artefact\)/);
    expect(bron("components/werkplek/WerkgebiedArtefactPaneel.tsx")).toMatch(/artefactKop\(doel\)/);
    expect(bron("components/werkplek/WerkplekClient.tsx")).toMatch(/artefactKop\(laatsteWgArtefact\)/);
    // Geen eigen namentabel naast ARTEFACT_SOORT_LABEL.
    expect(bron("components/werkplek/WerkgebiedArtefactPaneel.tsx")).not.toMatch(/const KOP\b/);
    expect(bron("components/werkplek/WerkplekClient.tsx")).not.toMatch(/werkgebiedLabel/);
  });
});
