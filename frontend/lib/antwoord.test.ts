import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { BLOK_SOORTEN, parseAntwoord } from "./antwoord";

const v = { iri: "urn:bwb:BWBR1:artikel:2", label: "Artikel 2", jci: "", regeling: "Wet" };

describe("parseAntwoord", () => {
  it("laat een geldig sjabloon door", () => {
    const a = parseAntwoord({ sjabloon: "begrip", versie: 1, doelen: [v], blokken: [
      { soort: "definities", door: "bron", items: [{ term: "x", tekst: "x: y", vindplaats: v, bereik: "" }] },
      { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Uitleg." },
    ] });
    expect(a?.blokken).toHaveLength(2);
  });

  it("laat een duiding door: kort antwoord met eigen kop, citaten en twijfel", () => {
    const a = parseAntwoord({ sjabloon: "duiding", versie: 1, doelen: [v], blokken: [
      { soort: "toelichting", door: "lex", kop: "Kort antwoord", tekst: "Uitleg." },
      { soort: "citaten", door: "bron", items: [{ tekst: "x", vindplaats: v, waarom: "Omdat." }] },
      { soort: "twijfel", door: "lex", punten: ["Open punt."] },
    ] });
    expect(a?.blokken.map((b) => b.soort)).toEqual(["toelichting", "citaten", "twijfel"]);
  });

  it("weigert een blok met een gat, een onbekende soort en een leeg sjabloon", () => {
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [{ soort: "definities", items: [{ tekst: "x" }] }] })).toBeUndefined();
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [{ soort: "tabel" }] })).toBeUndefined();
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [] })).toBeUndefined();
    expect(parseAntwoord(undefined)).toBeUndefined();
  });

  it("kent dezelfde blokken als het contract in bronmodel", () => {
    const bron = readFileSync(new URL("../../packages/bronmodel/bronmodel/antwoord.py", import.meta.url), "utf8");
    const soorten = [...bron.matchAll(/soort: Literal\["(\w+)"\]/g)].map((m) => m[1]);
    expect([...soorten].sort()).toEqual([...BLOK_SOORTEN].sort());
  });
});
