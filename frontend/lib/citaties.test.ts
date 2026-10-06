import { describe, expect, it } from "vitest";
import { bronLabel, koppelBron, markeerCitaties, vindVermeldingen } from "./citaties";
import type { HastKnoop } from "./markering";

const B = "urn:bwb:BWBR0004770";
const bron = (pad: string) => ({ label: `${B}:${pad}`, uri: `${B}:${pad}` });

describe("vindVermeldingen", () => {
  it("herkent artikel, lid en rangtelwoord", () => {
    const tekst = "Volgens artikel 9 lid 2 en art. 10a, derde lid geldt artikel 3.1.";
    expect(vindVermeldingen(tekst).map(({ artikel, lid }) => ({ artikel, lid }))).toEqual([
      { artikel: "9", lid: "2" }, { artikel: "10a", lid: "3" }, { artikel: "3.1", lid: undefined },
    ]);
    const [eerste] = vindVermeldingen(tekst);
    expect(tekst.slice(eerste.start, eerste.eind)).toBe("artikel 9 lid 2");
  });
  it("leest Awb-nummers en achtervoegsels helemaal, niet alleen het eerste getal", () => {
    const tekst = "Artikel 4:94a Awb, artikel 31bis Awir, artikel 27quinquies en art. 3:40, tweede lid.";
    expect(vindVermeldingen(tekst).map(({ artikel, lid }) => ({ artikel, lid }))).toEqual([
      { artikel: "4:94a", lid: undefined }, { artikel: "31bis", lid: undefined },
      { artikel: "27quinquies", lid: undefined }, { artikel: "3:40", lid: "2" },
    ]);
  });
});

describe("koppelBron", () => {
  const bronnen = [bron("artikel:9:lid:1"), bron("artikel:9:lid:2"), bron("artikel:10")];
  it("koppelt alleen éénduidig", () => {
    expect(koppelBron({ start: 0, eind: 0, artikel: "9", lid: "2" }, bronnen)).toBe(1);
    expect(koppelBron({ start: 0, eind: 0, artikel: "10" }, bronnen)).toBe(2);
    // "artikel 9" zonder lid: twee leden, geen hele-artikelbron – geen chip.
    expect(koppelBron({ start: 0, eind: 0, artikel: "9" }, bronnen)).toBe(-1);
    expect(koppelBron({ start: 0, eind: 0, artikel: "11" }, bronnen)).toBe(-1);
    // Eén lid onder een artikel: dan is "artikel 9" wél dat lid.
    expect(koppelBron({ start: 0, eind: 0, artikel: "9" }, [bron("artikel:9:lid:1")])).toBe(0);
  });
});

describe("markeerCitaties", () => {
  it("wikkelt de vermelding in, zonder tekst toe te voegen of weg te halen", () => {
    const boom: HastKnoop = { type: "root", children: [{ type: "element", tagName: "p", children: [
      { type: "text", value: "Zie artikel 9 lid 2 en artikel 11." }] }] };
    markeerCitaties([bron("artikel:9:lid:2")])()(boom);
    const p = boom.children![0];
    expect(p.children!.map((k) => k.tagName ?? "text")).toEqual(["text", "cite", "text"]);
    expect(p.children![1].properties).toEqual({ dataBron: "0" });
    const tekst = (k: HastKnoop): string => k.value ?? (k.children ?? []).map(tekst).join("");
    expect(tekst(p)).toBe("Zie artikel 9 lid 2 en artikel 11.");
  });

  it("laat code en links met rust", () => {
    const boom: HastKnoop = { type: "root", children: [{ type: "element", tagName: "code", children: [
      { type: "text", value: "artikel 9 lid 2" }] }] };
    markeerCitaties([bron("artikel:9:lid:2")])()(boom);
    expect(boom.children![0].children![0].type).toBe("text");
  });
});

describe("bronLabel", () => {
  it("maakt een leesbaar label van een graaf-IRI en laat de rest staan", () => {
    expect(bronLabel(bron("artikel:9:lid:2"))).toBe("Artikel 9, lid 2");
    expect(bronLabel({ label: "iets", uri: "https://example.org" })).toBe("iets");
  });
});
