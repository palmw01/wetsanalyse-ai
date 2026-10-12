import { describe, expect, it } from "vitest";
import { datumTekst, verwijzingTekst, verwijzingVoor, type KnoopVerwijzing } from "./knoopinfo";

const A = "urn:bwb:BWBR0004770:artikel:26a:lid:8";
const v = (naar: string, anker: string, extra: Partial<KnoopVerwijzing> = {}): KnoopVerwijzing =>
  ({ richting: "uit", van: A, naar, anker, soort: "intref", doel_soort: "artikel", doel_pad: "", betrouwbaarheid: "", ...extra });

describe("knoopinfo", () => {
  it("datums in gewone woorden; 9999 is geen einddatum; de rest ongewijzigd", () => {
    expect(datumTekst("2026-07-01")).toBe("1 juli 2026");
    expect(datumTekst("9999-12-31")).toBe("geen einddatum");
    expect(datumTekst("Stb.2022-330")).toBe("Stb.2022-330");
  });

  it("een verwijzing in gewone woorden", () => {
    expect(verwijzingTekst({ soort: "tekstueel", doel_soort: "artikel", doel_pad: "" })).toBe("uit de tekst herkend · artikel");
    expect(verwijzingTekst({ soort: "extref", doel_soort: "pad", doel_pad: "hoofdstuk 3" })).toBe("naar een andere regeling · pad · hoofdstuk 3");
  });

  it("de verwijzing bij een relatieregel: op ankertekst, of de enige naar die knoop", () => {
    const lijst = [v("urn:x:107", "artikel 107", { soort: "tekstueel" }), v("urn:x:3", "artikel 3"), v("urn:x:3", "het derde artikel")];
    expect(verwijzingVoor(lijst, "uit", "urn:x:107", "")?.soort).toBe("tekstueel");
    expect(verwijzingVoor(lijst, "uit", "urn:x:3", "het derde artikel")?.anker).toBe("het derde artikel");
    // Twee naar dezelfde knoop zonder passend anker: liever niets dan de verkeerde.
    expect(verwijzingVoor(lijst, "uit", "urn:x:3", "")).toBeUndefined();
    expect(verwijzingVoor(lijst, "in", "urn:x:107", "")).toBeUndefined();
  });
});
