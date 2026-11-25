// Klasse, waardebereik en eigenaar van een begrip, en de voorbeeldtabel van een regel (plan lessen
// Termijnen-bibliotheek, V2–V4).
import { describe, expect, it } from "vitest";

import { geldigheidZin, klasseZin, waardebereikUit, waardebereikZin } from "./begrippen";
import { voorbeeldTabel, type Regel } from "./regels";

const leeg = { soort: "", eenheid: "", decimalen: "", minimum: "", maximum: "", waarden: "", toelichting: "" };

describe("waardebereik", () => {
  it("zegt het bereik in één regel", () => {
    expect(waardebereikZin({ soort: "bedrag", eenheid: "euro", decimalen: 0, minimum: "0" })).toBe("bedrag in euro, 0 decimalen, vanaf 0");
    expect(waardebereikZin({ soort: "opsomming", waarden: ["april", "mei"] })).toBe("een van: april, mei");
    expect(waardebereikZin({ soort: "ja_nee", toelichting: "situatie" })).toBe("ja of nee (situatie)");
    expect(waardebereikZin(null)).toBe("");
  });

  it("komt uit het formulier, zonder soort niet", () => {
    expect(waardebereikUit(leeg)).toBeNull();
    expect(waardebereikUit({ ...leeg, soort: "aantal", decimalen: "0", minimum: " 1 " }))
      .toEqual({ soort: "aantal", eenheid: "", decimalen: 0, minimum: "1", maximum: "", toelichting: "", waarden: [] });
    expect(waardebereikUit({ ...leeg, soort: "opsomming", waarden: "april\n\n mei " })?.waarden).toEqual(["april", "mei"]);
    expect(waardebereikUit({ ...leeg, soort: "datum", waarden: "x" })?.waarden).toEqual([]);
  });
});

describe("klasse", () => {
  it("noemt de herkomst", () => {
    const uit = { "Variabele en variabelewaarde": 2 };
    expect(klasseZin({ klasse: "Variabele en variabelewaarde", afgeleid: "Variabele en variabelewaarde", uit_passages: uit, gekozen: "", reden: "" }))
      .toEqual({ klasse: "Variabele en variabelewaarde", herkomst: "uit 2 passages" });
    expect(klasseZin({ klasse: "Parameter en parameterwaarde", afgeleid: "Variabele en variabelewaarde", uit_passages: uit,
      gekozen: "Parameter en parameterwaarde", reden: "r" }))
      .toEqual({ klasse: "Parameter en parameterwaarde", herkomst: "gekozen; de passages zeggen Variabele en variabelewaarde" });
    expect(klasseZin(undefined)).toEqual({ klasse: "", herkomst: "" });
  });
});

describe("voorbeeldtabel", () => {
  const regel = {
    inhoud: {
      voorbeelden: [
        { geval: "", invoer: "a", uitkomst: "8", oordeel: "juist", waarden: [{ begrip_id: "m", waarde: "april" }] },
        { geval: "", invoer: "b", uitkomst: "1", oordeel: "open", waarden: [{ begrip_id: "m", waarde: "december" }, { begrip_id: "j", waarde: "ja" }] },
      ],
    },
    begrippen: { m: { id: "m", naam: "maand", status: "geaccordeerd", definitie: "" }, j: { id: "j", naam: "in het jaar", status: "concept", definitie: "" } },
  } as unknown as Regel;

  it("zet een kolom per voorbeeld en een rij per invoerbegrip", () => {
    expect(voorbeeldTabel(regel, regel.inhoud.voorbeelden)).toEqual({
      kolommen: [1, 2],
      rijen: [{ begrip: "maand", waarden: ["april", "december"] }, { begrip: "in het jaar", waarden: ["", "ja"] }],
    });
  });

  it("is er niet zonder waarden per begrip", () => {
    expect(voorbeeldTabel(regel, [{ ...regel.inhoud.voorbeelden[0], waarden: [] }])).toBeNull();
  });
});

describe("geldigheid", () => {
  it("zegt per wanneer een betekenis geldt (B8)", () => {
    expect(geldigheidZin({ geldig_vanaf: "2027-01-01", geldig_tot: "2027-12-31" })).toBe("van 01-01-2027 tot en met 31-12-2027");
    expect(geldigheidZin({ geldig_vanaf: "2027-01-01" })).toBe("vanaf 01-01-2027");
    expect(geldigheidZin({ geldig_tot: "2026-12-31" })).toBe("tot en met 31-12-2026");
    expect(geldigheidZin({})).toBe("");
  });
});
