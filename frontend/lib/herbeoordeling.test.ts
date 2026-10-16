import { describe, expect, it } from "vitest";

import { geraaktPerKoppeling, geraakteBegrippen, isDekking, isHerbeoordelingen, markeer, strookKop } from "./herbeoordeling";
import type { GeraakteKoppeling, Herbeoordelingen } from "./types";

const k = (id: string): GeraakteKoppeling => ({
  koppeling_id: id, element_id: `e-${id}`, rol: "duiding", actualiteit: "gewijzigd", redenen: [],
  toen: { tekst: "Beta", klasse: "Rechtssubject", ankers: [], vindplaats: "Lid 2", lifecycle: "", snapshot_id: "", eigenaar_iri: "" },
  bevestigingen: [], nu: null, bron: [], opvolgers: [], opnieuw_annoteren: [], acties: ["loskoppelen"],
});

const h: Herbeoordelingen = {
  werkgebied_id: "w", volledig: true, open_punten: [],
  begrippen: [
    { begrip_id: "A", naam: "A", status: "geaccordeerd", revisie: 3, koppelingen: [k("1"), k("2")] },
    { begrip_id: "B", naam: "B", status: "concept", revisie: 1, koppelingen: [k("3")] },
  ],
};

describe("herbeoordeling", () => {
  it("telt per begrip en noemt het in de kop", () => {
    expect(geraakteBegrippen(h)).toEqual(new Map([["A", 2], ["B", 1]]));
    expect(strookKop(h)).toBe("2 begrippen herbeoordelen · 3 passages veranderden");
    expect(strookKop({ ...h, begrippen: [h.begrippen[1]] })).toBe("1 begrip herbeoordelen · 1 passage veranderde");
  });

  it("zoekt de geraakte koppelingen van één begrip", () => {
    expect([...geraaktPerKoppeling(h, "A").keys()]).toEqual(["1", "2"]);
    expect(geraaktPerKoppeling(h, "C").size).toBe(0);
    expect(geraaktPerKoppeling(null, "A").size).toBe(0);
  });

  it("wijst een fragment aan in de tekst van nu, of zegt dat het er niet meer staat", () => {
    expect(markeer("Beta gamma", "Beta")).toEqual(["", "Beta", " gamma"]);
    expect(markeer("Other", "Beta")).toBeNull();
    expect(markeer("x", "")).toBeNull();
  });
});

it("een ander antwoord is geen herbeoordeling of dekking", () => {
  expect(isHerbeoordelingen({})).toBe(false);
  expect(isHerbeoordelingen(h)).toBe(true);
  expect(isDekking({})).toBe(false);
  expect(isDekking({ elementen: [], totalen: { te_verwerken: 0 } })).toBe(true);
});
