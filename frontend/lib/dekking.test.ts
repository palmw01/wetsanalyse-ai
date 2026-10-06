import { describe, expect, it } from "vitest";
import { dekkingPerBron, gevondenTekst, ongedektPerBron } from "./dekking";

describe("dekkingPerBron", () => {
  it("telt per bronnode de volledig bekeken dimensies en de ongedekte zinsdelen, in tekstvolgorde", () => {
    const regels = dekkingPerBron({ structureel: {
      b: { dimensies: { actor: "uitgevoerd", tijd: "overgeslagen", waarde: "gedeeltelijk" }, ongedekt: [{ tekst: "x", start: 0, eind: 1 }] },
      a: { dimensies: { actor: "uitgevoerd" }, ongedekt: [] },
    } }, ["a", "b"]);
    expect(regels).toEqual([
      { bron_iri: "a", bekeken: 1, totaal: 1, onvolledig: [], ongedekt: 0 },
      { bron_iri: "b", bekeken: 1, totaal: 3, onvolledig: [
        { dimensie: "tijd", stand: "overgeslagen" }, { dimensie: "waarde", stand: "gedeeltelijk" }], ongedekt: 1 },
    ]);
  });

  it("draagt per dimensie wat er gevonden werd – en zonder telling niets (onbekend, geen 0)", () => {
    const [met] = dekkingPerBron({ structureel: { a: { dimensies: { tijd: "uitgevoerd", plaats: "uitgevoerd", actor: "uitgevoerd" },
      ongedekt: [], aangetroffen: { tijd: 2, plaats: 0, actor: 1 } } } }, ["a"]);
    expect(gevondenTekst(met.gevonden)).toBe("Gevonden: tijd 2, actor 1 · niets: plaats");
    const [zonder] = dekkingPerBron({ structureel: { a: { dimensies: { tijd: "uitgevoerd" }, ongedekt: [] } } }, ["a"]);
    expect(zonder.gevonden).toBeUndefined();
    expect(gevondenTekst(zonder.gevonden)).toBe("");
    expect(gevondenTekst([{ dimensie: "tijd", aantal: 0 }])).toBe("Niets gevonden");
  });

  it("telt wat alleen als geheel geraakt werd – en laat het weg bij een oudere meting", () => {
    const [met] = dekkingPerBron({ structureel: { a: { dimensies: { tijd: "uitgevoerd" }, ongedekt: [],
      alleen_als_geheel: [{ tekst: "Een aanslag is invorderbaar.", start: 0, eind: 28 }] } } }, ["a"]);
    expect(met.alleenGeheel).toBe(1);
    const [zonder] = dekkingPerBron({ structureel: { a: { dimensies: { tijd: "uitgevoerd" }, ongedekt: [] } } }, ["a"]);
    expect(zonder.alleenGeheel).toBeUndefined();
  });

  it("is leeg zonder meting", () => {
    expect(dekkingPerBron(undefined, [])).toEqual([]);
    expect(dekkingPerBron({}, [])).toEqual([]);
  });
});

describe("ongedektPerBron", () => {
  it("groepeert de zinsdelen per bron-IRI, in volgorde", () => {
    expect(ongedektPerBron([{ bron_iri: "a", tekst: "x" }, { bron_iri: "b", tekst: "y" }, { bron_iri: "a", tekst: "z" }]))
      .toEqual({ a: ["x", "z"], b: ["y"] });
    expect(ongedektPerBron([])).toEqual({});
  });
});
