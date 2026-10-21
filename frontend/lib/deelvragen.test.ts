import { describe, expect, it } from "vitest";

import {
  dekkingZin, isDeelvragenDekking, overgenomenZin, splits, vervangtZin, voorstellenVoor, wissel, zelfdeSet,
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

  it("telt wat gedekt is", () => {
    const telling = { gedekt: 2, geen_begrip: 1, geen_bron: 0 };
    expect(dekkingZin({ deelvragen: [], telling, totaal: 3 })).toBe("2 van 3 deelvragen gedekt");
    expect(dekkingZin({ deelvragen: [], telling: { ...telling, gedekt: 0 }, totaal: 1 })).toBe("0 van 1 deelvraag gedekt");
    expect(dekkingZin(null)).toBe("");
  });

  it("herkent de vorm van de dekking", () => {
    expect(isDeelvragenDekking({})).toBe(false);
    expect(isDeelvragenDekking({ deelvragen: [], totaal: 0, telling: {} })).toBe(true);
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
