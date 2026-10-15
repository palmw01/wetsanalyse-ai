import { describe, expect, it } from "vitest";

import {
  enigeDefinitie, groepenVanVraag, overnameVoor, passageTekst, sorteerGroepen, voortgangsregel,
} from "./begripVoorstellen";
import type { Betekenisgroep } from "./types";

const lid = (id: string, tekst = id) => ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status: "voorgesteld",
  bron_iri: "urn:x", vindplaats: "Artikel 9 · Lid 1" });
const groep = (id: string, leden: string[], over: Partial<Betekenisgroep> = {}): Betekenisgroep => ({
  id, aandacht: "groen", voorstel: { naam: id }, uitleg: [], conflicten: [], besluit: "open", reden: "", begrip_id: null,
  besloten_door: null, leden: leden.map((l) => lid(l)), lijkt_op: [], ...over,
});

describe("sorteerGroepen", () => {
  it("open vóór geparkeerd vóór besloten; geel vóór groen; meer leden eerst", () => {
    const uit = sorteerGroepen([
      groep("klaar", ["a", "b"], { besluit: "overgenomen" }),
      groep("park", ["c", "d"], { besluit: "geparkeerd" }),
      groep("groen2", ["e", "f"]),
      groep("groen3", ["g", "h", "i"]),
      groep("geel", ["j", "k"], { aandacht: "geel" }),
    ]);
    expect(uit.map((g) => g.id)).toEqual(["geel", "groen3", "groen2", "park", "klaar"]);
  });
});

describe("overnameVoor", () => {
  const a = groep("Ga", ["a1", "a2"]), b = groep("Gb", ["b1", "b2"]);
  it("hele groep: geen element_ids", () => {
    expect(overnameVoor([a], new Set(["a1", "a2"]), " Alfa ", true)).toEqual({ groep_ids: ["Ga"], naam: "Alfa", met_definitie: true });
  });
  it("splitsen: alleen de gekozen leden", () => {
    expect(overnameVoor([a], new Set(["a1"]), "Alfa", false).element_ids).toEqual(["a1"]);
  });
  it("combineren: beide groepen, een gekozen lid van buiten telt niet", () => {
    const o = overnameVoor([a, b], new Set(["a1", "a2", "b1", "zz"]), "Samen", true);
    expect([o.groep_ids, o.element_ids]).toEqual([["Ga", "Gb"], ["a1", "a2", "b1"]]);
  });
});

it("enigeDefinitie geeft er alleen één als er precies één is", () => {
  const met = (id: string, d: string) => groep(id, ["x"], { voorstel: { naam: id, definitie: d, definitie_vindplaats: "art. 2" } });
  expect(enigeDefinitie([met("a", "D1")])).toEqual({ tekst: "D1", vindplaats: "art. 2" });
  expect(enigeDefinitie([met("a", "D1"), met("b", "D1")])).toEqual({ tekst: "D1", vindplaats: "art. 2" });
  expect(enigeDefinitie([met("a", "D1"), met("b", "D2")])).toBeNull();
  expect(enigeDefinitie([groep("c", ["y"])])).toBeNull();
});

it("groepenVanVraag zet alleen open groepen klaar", () => {
  const vraag = { kandidaat_id: "P", van: "a1", naar: "b1", regel: "", uitleg: [] };
  expect(groepenVanVraag(vraag, [groep("Ga", ["a1"]), groep("Gb", ["b1"])])).toEqual(["Ga", "Gb"]);
  expect(groepenVanVraag(vraag, [groep("Ga", ["a1"]), groep("Gb", ["b1"], { besluit: "afgewezen" })])).toEqual(["Ga"]);
  expect(groepenVanVraag(vraag, [groep("Gab", ["a1", "b1"])])).toEqual(["Gab"]);
});

it("passageTekst en voortgangsregel", () => {
  expect(passageTekst("a1", {}, [groep("G", ["a1"])])).toBe("“a1” (Artikel 9 · Lid 1)");
  expect(passageTekst("weg", {})).toBe("weg");
  expect(voortgangsregel("Lex · Groeperen: 3 groepen (12 ms)")).toBe("Groeperen: 3 groepen (12 ms)");
});

it("samenOvername neemt beide passages en de open groep van een ervan", async () => {
  const { samenOvername } = await import("./begripVoorstellen");
  const vraag = { kandidaat_id: "P", van: "a1", naar: "x", regel: "", uitleg: [] };
  const o = samenOvername(vraag, [groep("Ga", ["a1", "a2"], { voorstel: { naam: "alfa" } })], {});
  expect(o).toEqual({ groep_ids: ["Ga"], naam: "alfa", element_ids: ["a1", "a2", "x"], met_definitie: true });
  const los = samenOvername({ ...vraag, van: "y" }, [], { y: { ...lid("y", "De Aanslag") } });
  expect([los.groep_ids, los.naam, los.element_ids]).toEqual([[], "aanslag", ["y", "x"]]);
});
