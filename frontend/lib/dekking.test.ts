import { describe, expect, it } from "vitest";
import { dekkingPerBron, ongedektPerBron } from "./dekking";

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
