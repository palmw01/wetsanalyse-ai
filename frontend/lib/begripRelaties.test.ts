import { describe, expect, it } from "vitest";

import { hypotheseZin, isRelatiesAntwoord, magVastleggen, ordenRelaties, relatieInvoer, relatieZin } from "./begripRelaties";
import type { BegripRelatie } from "./types";

const r = (id: string, extra: Partial<BegripRelatie>): BegripRelatie => ({
  id, van_begrip: "a", naar_begrip: "b", van_naam: "A", naar_naam: "B", type: "inclusie", herkomst: "analist",
  beoordeling: "akkoord", toelichting: "", bewijs: {}, ...extra,
});

describe("begripsrelaties", () => {
  it("leest de richting van de keten: hiërarchie draait om", () => {
    expect(relatieZin("inclusie", "belastingaanslag", "navorderingsaanslag")).toEqual(["belastingaanslag", "omvat ook", "navorderingsaanslag"]);
    // "aanslag, zoals navorderingsaanslag": van = aanslag (breder), naar = navorderingsaanslag (de soort).
    expect(relatieZin("hierarchie", "aanslag", "navorderingsaanslag")).toEqual(["navorderingsaanslag", "is een soort", "aanslag"]);
    expect(hypotheseZin("hierarchie", "aanslag", "navorderingsaanslag")[0]).toBe("navorderingsaanslag");
    expect(hypotheseZin("zelfde_betekenis", "x", "y")[1]).toBe("betekent hetzelfde als");
  });

  it("maakt van een keuze vanuit dit begrip de juiste richting", () => {
    expect(relatieInvoer("soort-van", "dit", "ander", "")).toEqual({ van_begrip: "ander", naar_begrip: "dit", type: "hierarchie" });
    expect(relatieInvoer("heeft-soort", "dit", "ander", " x ")).toEqual({ van_begrip: "dit", naar_begrip: "ander", type: "hierarchie", toelichting: "x" });
    expect(magVastleggen("verwant", "dit", "ander", "")).toBe(false);
    expect(magVastleggen("verwant", "dit", "ander", "omdat")).toBe(true);
    expect(magVastleggen("inclusie", "dit", "dit", "")).toBe(false);
  });

  it("ordent: veranderd bovenaan, opvolging apart, afgewezen los", () => {
    const o = ordenRelaties([r("1", {}), r("2", { veranderd: true }), r("3", { type: "opvolging" }), r("4", { beoordeling: "afgewezen" })]);
    expect(o.vastgelegd.map((x) => x.id)).toEqual(["2", "1"]);
    expect(o.afgewezen.map((x) => x.id)).toEqual(["4"]);
  });

  it("herkent het antwoord", () => {
    expect(isRelatiesAntwoord({})).toBe(false);
    expect(isRelatiesAntwoord({ relaties: [], voorstellen: [] })).toBe(true);
  });
});
