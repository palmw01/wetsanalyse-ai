import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { CONTEXTDELEN, contextdeel } from "./contextdelen";
import { BEKENDE_ROLLEN } from "./contextweergave";

const bron = (pad: string) => readFileSync(resolve(__dirname, "../../tools/graph-qa/agent", pad), "utf8");

describe("het register van contextdelen", () => {
  it("draagt dezelfde categorieën in dezelfde volgorde als graph-qa", () => {
    // De constanten (`SYSTEEM = "systeem"`) en de volgorde van `CATEGORIEEN` in agent/contextdelen.py.
    const py = bron("contextdelen.py");
    const naam = Object.fromEntries([...py.matchAll(/^([A-Z]+) = "([a-z]+)"$/gm)].map((m) => [m[1], m[2]]));
    const register = [...py.matchAll(/^    Categorie\((\w+), "[^"]*"(, voorvoegsel=True)?\),$/gm)]
      .map((m) => ({ id: naam[m[1]], voorvoegsel: !!m[2] }));
    expect(register.length).toBeGreaterThan(5);
    expect(CONTEXTDELEN.map((d) => ({ id: d.id, voorvoegsel: d.voorvoegsel }))).toEqual(register);
  });

  it("geeft elke categorie een eigen label en een eigen kleur uit de tokens van de app", () => {
    expect(new Set(CONTEXTDELEN.map((d) => d.label)).size).toBe(CONTEXTDELEN.length);
    expect(new Set(CONTEXTDELEN.map((d) => d.kleur)).size).toBe(CONTEXTDELEN.length);
    for (const d of CONTEXTDELEN) {
      expect(d.kleur).toMatch(/^bg-[a-z-]+(\/\d+)?$/);   // een token (eventueel met dekking), geen hex-waarde
      expect(d.uitleg.length).toBeGreaterThan(10);
    }
  });

  it("telt een categorie die de werkplek niet kent als Overig", () => {
    expect(contextdeel("iets_nieuws").id).toBe("overig");
    expect(contextdeel("historie").label).toBe("Eerdere beurten");
  });

  it("heeft een naam voor elke rol die een model aanroept", () => {
    // `Rol` in agent/llm_stap.py: de naam is het eerste lid van de tuple.
    const rollen = [...bron("llm_stap.py").matchAll(/^    [A-Z_]+ = \("([a-z_]+)", /gm)].map((m) => m[1]);
    expect(rollen.length).toBeGreaterThan(5);
    expect([...BEKENDE_ROLLEN].sort()).toEqual([...rollen].sort());
  });
});
