import { describe, expect, it } from "vitest";

import {
  conceptFout, conceptVan, deelvraagStappen, deelvragenSamen, overgenomenZin, splits, vervangtZin, wissel, zelfdeSet,
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

  it("een verbetering van Lex noemt de deelvraag die ze vervangt (F3d)", () => {
    const oud = dv("Wie betaalt?", 0);
    const beter = { ...dv("Wie is de belastingschuldige?", 1, "voorgesteld"), vervangt: oud.id };
    const los = dv("Wanneer?", 2, "voorgesteld");
    const lijst = [oud, beter, los];
    expect(vervangtZin(beter, lijst)).toBe("Vervangt “Wie betaalt?”");
    expect(vervangtZin(los, lijst)).toBe("");
    expect(overgenomenZin(beter, lijst)).toMatch(/vervangen/);
    expect(overgenomenZin(los, lijst)).toBe("Deelvraag overgenomen.");
  });
});

describe("deelvragenSamen", () => {
  it("zet de stappen om in één aanroep", () => {
    expect(deelvragenSamen([{ soort: "verwijder", id: "a" }, { soort: "wijzig", id: "b", vraag: "B?" }, { soort: "nieuw", vraag: "C?" }]))
      .toEqual({ verwijderen: ["a"], wijzigen: [{ id: "b", vraag: "B?" }], nieuw: ["C?"] });
  });
});

describe("het blok Deelvragen bewerken", () => {
  const oud = [{ id: "a", vraag: "Wat is een rekeningafspraak?" }, { id: "b", vraag: "Welke voorwaarden gelden?" }];

  it("eerst verwijderen, dan wijzigen, dan toevoegen; ongewijzigd en leeg nieuw tellen niet", () => {
    expect(deelvraagStappen(oud, [
      { id: "a", vraag: "Wat is een rekeningafspraak? " },
      { id: "b", vraag: "Welke voorwaarden gelden?", weg: true },
      { vraag: "Welke voorwaarden gelden?" },
      { vraag: "  " },
    ])).toEqual([{ soort: "verwijder", id: "b" }, { soort: "nieuw", vraag: "Welke voorwaarden gelden?" }]);
    expect(deelvraagStappen(oud, [{ id: "a", vraag: "Wat is een rekeningafspraak precies?" }, { id: "b", vraag: oud[1].vraag }]))
      .toEqual([{ soort: "wijzig", id: "a", vraag: "Wat is een rekeningafspraak precies?" }]);
    expect(deelvraagStappen(oud, conceptVan(oud))).toEqual([]);
  });

  it("een deelvraag die intussen weg is, komt niet terug", () => {
    expect(deelvraagStappen(oud, [{ id: "c", vraag: "Door een collega verwijderd" }])).toEqual([]);
  });

  it("een nieuwe regel die weer weg is, doet niets", () => {
    expect(deelvraagStappen(oud, [...conceptVan(oud), { vraag: "Nieuw", weg: true }])).toEqual([]);
  });

  it("een leeggemaakte bestaande deelvraag blokkeert opslaan; een verwijderde niet", () => {
    expect(conceptFout([{ id: "a", vraag: " " }])).toMatch(/leeg/);
    expect(conceptFout([{ id: "a", vraag: "", weg: true }, { vraag: "" }])).toBeNull();
  });
});
