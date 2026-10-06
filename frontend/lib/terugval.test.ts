import { describe, expect, it } from "vitest";
import { parseElement } from "./agentEvents";
import { vraagSuggesties } from "./annotatie";
import { klasseLabel } from "./jas";

// Een terugval (geen klasse gekozen) doet geen klasseclaim: zonder klasse, met de mogelijke
// klassen als alternatief. De werkplek moet hem tonen in plaats van stil laten vallen.
const terugval = {
  id: "e1", klasse: "", tekst: "is invorderbaar", ankers: [],
  alternatieven: [{ klasse: "Rechtsbetrekking", motivatie: "" }, { klasse: "Rechtsfeit", motivatie: "" }],
};

describe("terugval zonder klasse", () => {
  it("de parser laat hem door als er alternatieven zijn, anders niet", () => {
    expect(parseElement(terugval)?.klasse).toBe("");
    expect(parseElement({ ...terugval, alternatieven: [] })).toBeUndefined();
  });

  it("in beeld heet hij 'Nog geen klasse'", () => {
    expect(klasseLabel("")).toBe("Nog geen klasse");
    expect(klasseLabel("Rechtsfeit")).toBe("Rechtsfeit");
  });

  it("de vragen gaan over de keuze, niet over een klasse die er niet is", () => {
    expect(vraagSuggesties(terugval)).toEqual([
      "Welke klasse past het best bij dit fragment?",
      "Wat is het verschil tussen Rechtsbetrekking en Rechtsfeit hier?",
      "Klopt de afbakening van dit fragment?",
    ]);
  });
});
