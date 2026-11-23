import { describe, expect, it } from "vitest";

import { HANDELINGEN, isVergroot, knoppenVoor, leesWeergave, plekVanWeergave, volgende, type PaneelPlek } from "@/lib/paneelBediening";

// Besluit gebruiker 23 nov 2026: één knop per handeling, één label en één icoon, in de kop, in een vaste volgorde; de
// plek bepaalt welke knoppen er zijn.
describe("de knoppen per plek", () => {
  const verwacht: Record<PaneelPlek, string[]> = {
    paneel: ["vergroten", "inklappen", "sluiten"],
    vergroot: ["verkleinen", "inklappen", "sluiten"],
    ingeklapt: ["uitklappen", "sluiten"],
    sheet: ["vergroten", "sluiten"],
    "sheet-vergroot": ["verkleinen", "sluiten"],
    rondleiding: ["sluiten"],
    pagina: [],
  };
  for (const [plek, knoppen] of Object.entries(verwacht))
    it(`${plek}: ${knoppen.join(", ") || "geen"}`, () => expect(knoppenVoor(plek as PaneelPlek)).toEqual(knoppen));

  it("zonder sluiten geen ✕", () => {
    expect(knoppenVoor("paneel", { kanSluiten: false })).toEqual(["vergroten", "inklappen"]);
  });

  it("vergroten en verkleinen staan nooit samen: één knop die wisselt", () => {
    for (const plek of Object.keys(verwacht) as PaneelPlek[]) {
      const k = knoppenVoor(plek);
      expect(k.includes("vergroten") && k.includes("verkleinen"), plek).toBe(false);
      expect(k.includes("verkleinen"), plek).toBe(isVergroot(plek));
    }
  });

  it("heeft per handeling één label en één icoon, nergens dubbel", () => {
    const labels = Object.values(HANDELINGEN).map((h) => h.label);
    const iconen = Object.values(HANDELINGEN).map((h) => h.icoon);
    expect(new Set(labels).size).toBe(labels.length);
    expect(new Set(iconen).size).toBe(iconen.length);
  });
});

describe("de stand van het zijpaneel", () => {
  it("vergroten, verkleinen, inklappen en uitklappen", () => {
    expect(volgende("normaal", "vergroten")).toBe("vergroot");
    expect(volgende("vergroot", "verkleinen")).toBe("normaal");
    expect(volgende("vergroot", "inklappen")).toBe("ingeklapt");
    expect(volgende("ingeklapt", "uitklappen")).toBe("normaal");
  });

  it("Escape verkleint eerst, en klapt anders in (verbergen, niet sluiten)", () => {
    expect(volgende("vergroot", "escape")).toBe("normaal");
    expect(volgende("normaal", "escape")).toBe("ingeklapt");
  });

  it("iets nieuws openen klapt een strook uit en laat vergroot staan", () => {
    expect(volgende("ingeklapt", "nieuw")).toBe("normaal");
    expect(volgende("vergroot", "nieuw")).toBe("vergroot");
    expect(volgende("normaal", "nieuw")).toBe("normaal");
  });

  it("de plek volgt de stand; de rondleiding is vast", () => {
    expect(plekVanWeergave("normaal", false)).toBe("paneel");
    expect(plekVanWeergave("vergroot", false)).toBe("vergroot");
    expect(plekVanWeergave("ingeklapt", false)).toBe("ingeklapt");
    expect(plekVanWeergave("vergroot", true)).toBe("rondleiding");
  });

  it("leest alleen een bekende stand uit de opslag", () => {
    expect(leesWeergave("vergroot")).toBe("vergroot");
    expect(leesWeergave("ingeklapt")).toBe("ingeklapt");
    expect(leesWeergave("normaal")).toBeUndefined();
    expect(leesWeergave(true)).toBeUndefined();
  });
});
