import { describe, expect, it } from "vitest";

import { parseBronselectie } from "./bronselectie";
import { bepalingEnRegeling, bronnenPerDeelvraag, filterGroepen, ookBijZin, uniekeBronnen } from "./bronnenPerDeelvraag";
import type { Bronselectie, Deelvraag } from "./types";

const bron = (id: string, label: string, rol: Bronselectie["rol"] = "analyseren"): Bronselectie => ({
  id, bron_iri: `urn:bwb:BWBR0004770:artikel:${id}`, bereik: "onderliggend", rol, reden: "", label, bwb_id: "BWBR0004770",
  snapshot_id: "s", bron_hash: "h", toegevoegd_door: "t", toegevoegd: "2026-10-27T10:00:00Z",
});
const dv = (id: string, bronnen: string[]): Deelvraag => ({
  id, vraag: `Vraag ${id}?`, volgorde: 0, status: "actief", herkomst: "analist", reden: "", aangemaakt_door: "t",
  aangemaakt: "2026-10-27T10:00:00Z", bronnen, begrippen: [],
});
const BRONNEN = [bron("9", "Artikel 9, lid 1 – Invorderingswet 1990"), bron("10", "Artikel 10 – Invorderingswet 1990"),
  bron("2", "Artikel 2 – Invorderingswet 1990", "context")];

describe("bronnen per deelvraag (spoor K)", () => {
  it("één lijst, per deelvraag gekoppeld; wat nergens bij hoort staat apart", () => {
    const g = bronnenPerDeelvraag(BRONNEN, [dv("d1", ["9", "10"]), dv("d2", ["9"])]);
    expect(g.map((x) => x.deelvraag?.nr ?? null)).toEqual([1, 2, null]);
    expect(g[0].bronnen.map((b) => [b.selectie.id, b.ook])).toEqual([["9", [2]], ["10", []]]);
    expect(g[1].bronnen.map((b) => [b.selectie.id, b.ook])).toEqual([["9", [1]]]);
    expect(g[2].bronnen.map((b) => b.selectie.id)).toEqual(["2"]);
    expect(uniekeBronnen(g)).toBe(3);
  });

  it("zonder deelvragen één groep, ook als die leeg is; zonder losse bronnen geen groep Zonder deelvraag", () => {
    expect(bronnenPerDeelvraag(BRONNEN, []).map((x) => [x.deelvraag, x.bronnen.length])).toEqual([[null, 3]]);
    expect(bronnenPerDeelvraag([], []).length).toBe(1);
    expect(bronnenPerDeelvraag([BRONNEN[0]], [dv("d1", ["9"])]).map((x) => x.deelvraag?.id ?? null)).toEqual(["d1"]);
  });

  it("de rol bij de deelvraag en de open voorstellen komen uit de bronselectie", () => {
    const overzicht = parseBronselectie({
      werkgebied_id: "wg1", deelvragen: [{ id: "d1", nr: 1, vraag: "?", status: "in_behandeling",
        bronnen: [{ selectie_id: "9", bron_iri: "", label: "", rol: "context" }],
        kandidaten: [{ id: "k1", bron_iri: "urn:bwb:x", label: "Artikel 11", rol: "kern", stand: "voorgesteld" },
          { id: "k2", bron_iri: "urn:bwb:y", label: "Artikel 12", rol: "kern", stand: "niet_gekozen" }] }],
    });
    const [g] = bronnenPerDeelvraag(BRONNEN, [dv("d1", ["9"])], overzicht);
    expect(g.bronnen[0].rol).toBe("context");
    expect(g.voorstellen.map((v) => v.id)).toEqual(["k1"]);
  });

  it("filteren laat lege groepen weg, maar alleen als er gefilterd wordt", () => {
    const g = bronnenPerDeelvraag(BRONNEN, [dv("d1", ["9"]), dv("d2", [])]);
    expect(filterGroepen(g, () => true, false).length).toBe(3);
    expect(filterGroepen(g, (b) => b.rol === "context", true).map((x) => x.deelvraag)).toEqual([null]);
  });

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
