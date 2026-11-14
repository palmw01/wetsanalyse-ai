import { describe, expect, it } from "vitest";

import { deelgesprekProfiel, deelIn } from "./gesprekGroepen";
import type { GesprekSamenvatting } from "./types";

const g = (id: string, extra: Partial<GesprekSamenvatting> = {}): GesprekSamenvatting => ({
  id, titel: id, aantal_berichten: 1, ...extra,
});

describe("deelIn", () => {
  it("zet gesprekken onder hun werkgebied, losse onder recent", () => {
    const uit = deelIn([
      g("a", { werkgebied_id: "w1", werkgebied_naam: "Invorderingsrente" }),
      g("b"),
      g("c", { werkgebied_id: "w2", werkgebied_naam: "Uitstel" }),
      g("d", { werkgebied_id: "w1", werkgebied_naam: "Invorderingsrente" }),
    ]);
    expect(uit.werkgebieden.map((w) => [w.naam, w.gesprekken.map((x) => x.id)])).toEqual([
      ["Invorderingsrente", ["a", "d"]],
      ["Uitstel", ["c"]],
    ]);
    expect(uit.recent.map((x) => x.id)).toEqual(["b"]);
    expect(uit.archief).toEqual([]);
  });

  it("een gearchiveerd gesprek staat alleen in het archief", () => {
    const uit = deelIn([
      g("a", { werkgebied_id: "w1", werkgebied_naam: "W", gearchiveerd: "2026-10-26T10:00:00Z" }),
      g("b", { gearchiveerd: "2026-10-26T10:00:00Z" }),
    ]);
    expect(uit.werkgebieden).toEqual([]);
    expect(uit.recent).toEqual([]);
    expect(uit.archief.map((x) => x.id)).toEqual(["a", "b"]);
  });

  it("een werkgebied zonder naam (net gewist) krijgt een neutrale naam", () => {
    expect(deelIn([g("a", { werkgebied_id: "w1" })]).werkgebieden[0].naam).toBe("Werkgebied");
  });
});

describe("deelgesprekken van een regie (ADR-012)", () => {
  it("staan direct onder hun regiegesprek, de rest houdt zijn volgorde", () => {
    const w = { werkgebied_id: "w1", werkgebied_naam: "W" };
    const uit = deelIn([
      g("k2", { ...w, ouder_id: "r" }), g("los", w), g("r", w), g("k1", { ...w, ouder_id: "r" }),
    ]);
    expect(uit.werkgebieden[0].gesprekken.map((x) => x.id)).toEqual(["los", "r", "k2", "k1"]);
  });

  it("een deelgesprek zonder zijn ouder in de lijst blijft staan", () => {
    const uit = deelIn([g("k", { werkgebied_id: "w1", ouder_id: "weg" }), g("a", { werkgebied_id: "w1" })]);
    expect(uit.werkgebieden[0].gesprekken.map((x) => x.id)).toEqual(["k", "a"]);
  });
});

describe("het profiel van een deelgesprek (ADR-016 §A3)", () => {
  it("noemt het profiel van een subagent, niet bij een regie of een los gesprek", () => {
    expect(deelgesprekProfiel({ ouder_id: "o", profiel: "duiding" })).toBe("subagent duiding");
    expect(deelgesprekProfiel({ ouder_id: "o", profiel: "" })).toBe("");
    expect(deelgesprekProfiel({ ouder_id: "", profiel: "duiding" })).toBe("");
  });
});
