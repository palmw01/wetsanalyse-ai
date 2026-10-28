import { describe, expect, it } from "vitest";

import { deelIn } from "./gesprekGroepen";
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
