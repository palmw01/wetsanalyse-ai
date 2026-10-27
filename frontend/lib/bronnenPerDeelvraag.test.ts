import { describe, expect, it } from "vitest";

import { bepalingEnRegeling, ookBijZin } from "./bronnenPerDeelvraag";

describe("bronnen per deelvraag (spoor K/L)", () => {
  it("splitst een label in bepaling en regeling, en noemt de andere deelvragen", () => {
    expect(bepalingEnRegeling("Artikel 9, lid 1 – Invorderingswet 1990"))
      .toEqual({ bepaling: "Artikel 9, lid 1", regeling: "Invorderingswet 1990" });
    expect(bepalingEnRegeling("Invorderingswet 1990 – Artikel 9, Lid 1"))
      .toEqual({ bepaling: "Artikel 9, Lid 1", regeling: "Invorderingswet 1990" });
    expect(bepalingEnRegeling("Invorderingswet 1990 – Hoofdstuk V – Invorderingsrente"))
      .toEqual({ bepaling: "Hoofdstuk V – Invorderingsrente", regeling: "Invorderingswet 1990" });
    expect(bepalingEnRegeling("Invorderingswet 1990 – artikel 9"))
      .toEqual({ bepaling: "artikel 9", regeling: "Invorderingswet 1990" });
    expect(bepalingEnRegeling("urn:bwb:x")).toEqual({ bepaling: "urn:bwb:x", regeling: "" });
    expect(bepalingEnRegeling("Wet A – Wet B")).toEqual({ bepaling: "Wet A – Wet B", regeling: "" });
    expect([ookBijZin([]), ookBijZin([2]), ookBijZin([2, 3, 4])])
      .toEqual(["", "ook bij deelvraag 2", "ook bij deelvragen 2, 3 en 4"]);
  });
});
