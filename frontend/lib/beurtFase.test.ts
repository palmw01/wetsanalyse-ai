import { describe, expect, it } from "vitest";
import { RUST, faseReducer, isBezig, lopendeRunId, magStarten, stopBaar, stoptNu, type BeurtFase, type FaseActie } from "./beurtFase";

const speel = (acties: FaseActie[], van: BeurtFase = RUST) => acties.reduce(faseReducer, van);

describe("faseReducer", () => {
  it("een gewone beurt: claim → aangehaakt → einde", () => {
    const starten = speel([{ type: "claim" }]);
    expect(starten).toEqual({ soort: "starten" });
    const volgen = faseReducer(starten, { type: "aangehaakt", runId: "r1" });
    expect(volgen).toEqual({ soort: "volgen", runId: "r1", stopt: false });
    expect(faseReducer(volgen, { type: "einde" })).toBe(RUST);
  });

  it("claim kan maar één keer: een tweede Enter in dezelfde tick verandert niets", () => {
    const starten = speel([{ type: "claim" }]);
    expect(magStarten(starten)).toBe(false);
    expect(faseReducer(starten, { type: "claim" })).toBe(starten);
    const volgen = speel([{ type: "claim" }, { type: "aangehaakt", runId: "r1" }]);
    expect(faseReducer(volgen, { type: "claim" })).toBe(volgen);
  });

  it("hervatten haakt aan vanuit rust", () => {
    expect(speel([{ type: "aangehaakt", runId: "r2" }])).toEqual({ soort: "volgen", runId: "r2", stopt: false });
  });

  it("verbroken houdt de run en de stopstand vast", () => {
    const f = speel([{ type: "aangehaakt", runId: "r1" }, { type: "stopGevraagd" }, { type: "verbroken", poging: 2 }]);
    expect(f).toEqual({ soort: "herstellen", runId: "r1", poging: 2, stopt: true });
    // Opnieuw aangehaakt: de stopvraag blijft gelden tot de run afloopt.
    expect(faseReducer(f, { type: "aangehaakt", runId: "r1" })).toEqual({ soort: "volgen", runId: "r1", stopt: true });
    // Zonder run valt er niets te herstellen.
    expect(speel([{ type: "verbroken", poging: 0 }])).toBe(RUST);
  });

  it("stoppen: gevraagd, en terug als het verzoek mislukt; zonder run doet het niets", () => {
    const v = speel([{ type: "aangehaakt", runId: "r1" }]);
    const gevraagd = faseReducer(v, { type: "stopGevraagd" });
    expect(stoptNu(gevraagd)).toBe(true);
    expect(stopBaar(gevraagd)).toBe(false);
    expect(faseReducer(gevraagd, { type: "stopMislukt" })).toEqual(v);
    expect(speel([{ type: "stopGevraagd" }])).toBe(RUST);
    expect(speel([{ type: "claim" }, { type: "stopGevraagd" }])).toEqual({ soort: "starten" });
  });
});

describe("afgeleiden per fase", () => {
  const fasen: [string, BeurtFase, { mag: boolean; bezig: boolean; stop: boolean; run: string | null }][] = [
    ["rust", RUST, { mag: true, bezig: false, stop: false, run: null }],
    ["starten", { soort: "starten" }, { mag: false, bezig: true, stop: false, run: null }],
    ["volgen", { soort: "volgen", runId: "r", stopt: false }, { mag: false, bezig: true, stop: true, run: "r" }],
    ["herstellen", { soort: "herstellen", runId: "r", poging: 1, stopt: false }, { mag: false, bezig: true, stop: true, run: "r" }],
  ];
  for (const [naam, f, v] of fasen) {
    it(naam, () => {
      expect(magStarten(f)).toBe(v.mag);
      expect(isBezig(f)).toBe(v.bezig);
      expect(stopBaar(f)).toBe(v.stop);
      expect(lopendeRunId(f)).toBe(v.run);
    });
  }
});
