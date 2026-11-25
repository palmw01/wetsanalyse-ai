import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { parseAntwoord } from "./antwoord";
import { CRITERIA, OORDEEL_LABEL, OORDEEL_TELLING, OORDELEN, contentDelen, isContenttoets, tellingTekst, toetsSleutel } from "./contenttoets";

// De bron van de spiegel: `bronmodel/contenttoets.py`.
const bron = readFileSync(new URL("../../packages/bronmodel/bronmodel/contenttoets.py", import.meta.url), "utf8");

function pyDict(naam: string): Record<string, string> {
  const blok = new RegExp(`^${naam}: dict\\[str, str\\] = \\{([\\s\\S]*?)^\\}`, "m").exec(bron)?.[1] ?? "";
  return Object.fromEntries([...blok.matchAll(/"([^"]+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]));
}

const vp = { iri: "urn:bwb:BWBR0024096:x", label: "Artikel 25.3a.1", jci: "", regeling: "Leidraad Invordering 2008" };
const blok = {
  soort: "contenttoets", door: "lex", content: "U betaalt in maximaal 24 maanden.", peildatum: "2026-11-25",
  getoetst_tegen: ["Leidraad Invordering 2008"], voor_redacteur: ["[1] Zet 24 op 12."], niet_getoetst: [],
  bevindingen: [{ nr: 1, citaat: "maximaal 24 maanden", begin: 13, eind: 32, oordeel: "mogelijk_onjuist", criterium: "J1",
    bronnen: [{ tekst: "maximaal twaalf maanden", vindplaats: vp }], toelichting: "", twijfel: "", voorstel: "12 maanden." }],
  ontbreekt: [],
};

describe("de spiegel van bronmodel/contenttoets.py", () => {
  it("kent dezelfde oordelen, in dezelfde volgorde", () => {
    const py = /^OORDELEN: tuple\[str, \.\.\.\] = \(([^)]*)\)/m.exec(bron)?.[1] ?? "";
    expect([...py.matchAll(/"(\w+)"/g)].map((m) => m[1])).toEqual([...OORDELEN]);
    expect(pyDict("OORDEEL_LABEL")).toEqual(OORDEEL_LABEL);
    expect(pyDict("OORDEEL_TELLING")).toEqual(OORDEEL_TELLING);
  });

  it("kent dezelfde criteria", () => {
    expect(pyDict("CRITERIA")).toEqual(CRITERIA);
  });

  it("telt zoals telling_tekst", () => {
    expect(tellingTekst(blok as never)).toBe("1 bewering: 1 mogelijk onjuist.");
    const meer = { ...blok, bevindingen: [...blok.bevindingen, { ...blok.bevindingen[0], nr: 2, oordeel: "juist" }],
      ontbreekt: [{ tekst: "x", bronnen: [] }, { tekst: "y", bronnen: [] }] };
    expect(tellingTekst(meer as never)).toBe("2 beweringen: 1 mogelijk onjuist, 1 juist. 2 punten ontbreken.");
  });
});

describe("het blok contenttoets", () => {
  it("is een geldig blok van een antwoord", () => {
    const a = parseAntwoord({ sjabloon: "contenttoets", versie: 1, doelen: [vp], blokken: [blok] });
    expect(a?.blokken[0]).toEqual(blok);
  });

  it("weigert een bevinding met een gat", () => {
    const met = (x: object) => isContenttoets({ ...blok, bevindingen: [{ ...blok.bevindingen[0], ...x }] });
    expect(met({})).toBe(true);
    expect(met({ oordeel: "fout" })).toBe(false);
    expect(met({ eind: 99 })).toBe(false);                      // buiten de content
    expect(met({ begin: 20, eind: 10 })).toBe(false);
    expect(met({ bronnen: [{ tekst: "x" }] })).toBe(false);     // een bron zonder vindplaats
    expect(isContenttoets({ ...blok, content: undefined })).toBe(false);
  });
});

describe("de content in het zijpaneel", () => {
  const b = (content: string, ...m: [number, number, number][]) => ({ content,
    bevindingen: m.map(([nr, begin, eind]) => ({ nr, begin, eind, oordeel: "juist" as const })) }) as never;

  it("markeert elke bevinding op haar codepoints", () => {
    expect(contentDelen(b("ab 😀 cd ef", [1, 3, 4], [2, 8, 10]))).toEqual([
      { tekst: "ab " }, { tekst: "😀", nr: 1, oordeel: "juist" }, { tekst: " cd " }, { tekst: "ef", nr: 2, oordeel: "juist" }]);
  });

  it("geeft bij overlap de eerste de tekst, en laat een lege bevinding uit de content", () => {
    expect(contentDelen(b("abcdef", [2, 2, 5], [1, 0, 3], [3, 4, 4])).map((d) => [d.tekst, d.nr])).toEqual([
      ["abc", 1], ["de", 2], ["f", undefined]]);
  });

  it("houdt de tekst heel", () => {
    expect(contentDelen(blok as never).map((d) => d.tekst).join("")).toBe(blok.content);
  });

  it("geeft dezelfde toets dezelfde sleutel", () => {
    expect(toetsSleutel(blok)).toBe(toetsSleutel({ ...blok }));
    expect(toetsSleutel(blok)).not.toBe(toetsSleutel({ ...blok, peildatum: "2026-01-01" }));
  });
});
