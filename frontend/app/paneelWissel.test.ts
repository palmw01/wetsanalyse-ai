import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

// FB-05 (verbeterplan E5): onbewaarde invoer in het paneel van een werkgebied verdween bij elke wissel behalve sluiten.
// Elke wissel van dat paneel loopt nu door één setter met de bewaker (`wisselPaneel`); de kale setter staat alleen in
// zijn declaratie en in die setter.
describe("het paneel naast het gesprek wisselt alleen via de bewaker", () => {
  const code = bron("components/werkplek/WerkplekClient.tsx");

  it("de kale setter van het werkgebiedpaneel staat alleen in wisselPaneel", () => {
    expect(code).not.toMatch(/\bsetWgArtefact\b/);
    const kaal = [...code.matchAll(/\bzetWgArtefactOnbewaakt\b/g)].map((m) => m.index!);
    expect(kaal).toHaveLength(2);
    const begin = code.indexOf("function wisselPaneel(");
    const eind = code.indexOf("\n  }\n", begin);
    expect(begin).toBeGreaterThan(-1);
    expect(code.slice(0, kaal[0])).toMatch(/const \[wgArtefact, $/);
    expect(kaal[1]).toBeGreaterThan(begin);
    expect(kaal[1]).toBeLessThan(eind);
    expect(code.slice(begin, eind)).toMatch(/wgBewaker\.bewaak\(/);
  });

  it("ook het opnieuw laden (de key met wgLading) gaat door de bewaker", () => {
    expect([...code.matchAll(/\bsetWgLading\(/g)]).toHaveLength(1);
    const begin = code.indexOf("function wisselPaneel(");
    expect(code.indexOf("setWgLading(", begin)).toBeLessThan(code.indexOf("\n  }\n", begin));
  });

  it("het paneel gebruikt de bewaker van de werkplek, niet een eigen", () => {
    const paneel = bron("components/werkplek/WerkgebiedArtefactPaneel.tsx");
    expect(paneel).not.toMatch(/useOnbewaardBewaker\(/);
    expect(code).toMatch(/bewaker=\{wgBewaker\}/);
    expect(code).toMatch(/onOnbewaard=\{setWgOnbewaard\}/);
  });
});
