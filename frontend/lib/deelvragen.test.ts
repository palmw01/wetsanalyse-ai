import { describe, expect, it } from "vitest";

import {
  overgenomenZin, splits, vervangtZin, voorstellenVoor, wissel, zelfdeSet,
} from "./deelvragen";
import type { Deelvraag } from "./types";

const dv = (id: string, volgorde: number, status: Deelvraag["status"] = "actief"): Deelvraag => ({
  id, vraag: id, volgorde, status, herkomst: status === "voorgesteld" ? "lex" : "analist", reden: "",
  aangemaakt_door: "a", aangemaakt: "2026-10-19T10:00:00Z", bronnen: [], begrippen: [],
});

describe("deelvragen", () => {
  it("splitst actieve deelvragen en voorstellen, in volgorde", () => {
    const { actief, voorgesteld } = splits([dv("b", 2), dv("x", 3, "voorgesteld"), dv("a", 0)]);
    expect(actief.map((d) => d.id)).toEqual(["a", "b"]);
    expect(voorgesteld.map((d) => d.id)).toEqual(["x"]);
    expect(splits(undefined)).toEqual({ actief: [], voorgesteld: [] });
  });

  it("wisselt een id en vergelijkt sets", () => {
    expect(wissel(["a", "b"], "a")).toEqual(["b"]);
    expect(wissel(["a"], "b")).toEqual(["a", "b"]);
    expect(zelfdeSet(["a", "b"], ["b", "a"])).toBe(true);
    expect(zelfdeSet(["a"], ["a", "b"])).toBe(false);
  });

  it("een verbetering van Lex hoort bij de deelvraag die ze vervangt (F3d)", () => {
    const oud = dv("Wie betaalt?", 0);
    const beter = { ...dv("Wie is de belastingschuldige?", 1, "voorgesteld"), vervangt: oud.id };
    const los = dv("Wanneer?", 2, "voorgesteld");
    const lijst = [oud, beter, los];
    expect(voorstellenVoor(oud.id, lijst)).toEqual([beter]);
    expect(vervangtZin(beter, lijst)).toBe("Vervangt “Wie betaalt?”");
    expect(vervangtZin(los, lijst)).toBe("");
    expect(overgenomenZin(beter, lijst)).toMatch(/vervangen/);
    expect(overgenomenZin(los, lijst)).toBe("Deelvraag overgenomen.");
  });
});
