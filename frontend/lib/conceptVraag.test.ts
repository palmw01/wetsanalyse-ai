import { afterEach, describe, expect, it, vi } from "vitest";

import { bewaarConcept, conceptSleutel, leesConcept } from "./conceptVraag";

function nepOpslag() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
    m,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("het concept van de vraag", () => {
  it("staat per gesprek, en het nieuwe gesprek heeft er één", () => {
    expect(conceptSleutel("g1")).not.toBe(conceptSleutel("g2"));
    expect(conceptSleutel(null)).toBe("lex.concept.nieuw");
  });

  it("komt terug, en verdwijnt bij een lege tekst (versturen)", () => {
    const opslag = nepOpslag();
    vi.stubGlobal("window", { sessionStorage: opslag });
    bewaarConcept("g1", "Wat is een belastingplichtige");
    expect(leesConcept("g1")).toBe("Wat is een belastingplichtige");
    expect(leesConcept("g2")).toBe("");
    bewaarConcept("g1", "  ");
    expect(opslag.m.size).toBe(0);
  });

  it("werkt zonder opslag: geen fout, alleen geen concept", () => {
    vi.stubGlobal("window", { get sessionStorage(): Storage { throw new Error("geblokkeerd"); } });
    expect(() => bewaarConcept("g1", "tekst")).not.toThrow();
    expect(leesConcept("g1")).toBe("");
    vi.unstubAllGlobals();
    // Ook zonder `window` (de server-render).
    expect(leesConcept("g1")).toBe("");
  });
});
