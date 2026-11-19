import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { GELDT_VOOR, geldtVoor, waardeUitFormule } from "./geldigheid";

describe("geldtVoor", () => {
  it("kent dezelfde tabel als bronmodel.definities.GELDT_VOOR", () => {
    const bron = readFileSync(new URL("../../packages/bronmodel/bronmodel/definities.py", import.meta.url), "utf8");
    const blok = /GELDT_VOOR = \{([\s\S]*?)\n\}/.exec(bron)?.[1] ?? "";
    const python = Object.fromEntries([...blok.matchAll(/"(\w+)": "([^"]*)"/g)].map((m) => [m[1], m[2]]));
    expect(python).toEqual(GELDT_VOOR);
  });

  it("noemt de regeling, en zonder soort niets", () => {
    expect(geldtVoor("regeling", { regeling: "Invorderingswet 1990" })).toBe("geldt in de hele Invorderingswet 1990");
    expect(geldtVoor("regeling")).toBe("geldt in de hele regeling");
    expect(geldtVoor("artikel_n", { waarde: "7" })).toBe("geldt voor artikel 7");
    expect(geldtVoor("")).toBe("");
    expect(geldtVoor("onbekend")).toBe("");
  });

  it("haalt het nummer of het woord uit de formule als dat er niet apart bij staat", () => {
    expect(waardeUitFormule("artikel_n", "voor de toepassing van artikel 7a")).toBe("7a");
    expect(waardeUitFormule("structuur", "In dit Hoofdstuk")).toBe("hoofdstuk");
    expect(waardeUitFormule("regeling", "Deze wet")).toBe("");
  });
});
