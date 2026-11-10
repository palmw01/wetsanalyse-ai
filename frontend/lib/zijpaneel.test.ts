import { describe, expect, it } from "vitest";

import { CHAT_MIN, MIN_BREEDTE, STAP, begrens, grenzen, leesBreedte, naToets } from "./zijpaneel";

describe("zijpaneel", () => {
  it("houdt het paneel tussen 320 px en 60%, en het gesprek minstens 300 px", () => {
    expect(grenzen(1280)).toEqual({ min: MIN_BREEDTE, max: 768 });
    // Op 800 px is 60% (480) strenger dan de ruimte voor het gesprek (500); op 700 px wint het gesprek (400).
    expect(grenzen(800)).toEqual({ min: MIN_BREEDTE, max: 480 });
    expect(grenzen(700)).toEqual({ min: MIN_BREEDTE, max: 400 });
    expect(begrens(100, 1280)).toBe(MIN_BREEDTE);
    expect(begrens(2000, 1280)).toBe(768);
    expect(1280 - begrens(2000, 1280)).toBeGreaterThanOrEqual(CHAT_MIN);
  });

  it("pijltjes verplaatsen de scheiding in stappen, Home en End naar de grenzen", () => {
    expect(naToets(500, "ArrowLeft", 1280)).toBe(500 + STAP);
    expect(naToets(500, "ArrowRight", 1280)).toBe(500 - STAP);
    expect(naToets(330, "ArrowRight", 1280)).toBe(MIN_BREEDTE);
    expect(naToets(500, "Home", 1280)).toBe(MIN_BREEDTE);
    expect(naToets(500, "End", 1280)).toBe(768);
    expect(naToets(500, "a", 1280)).toBeNull();
  });

  it("leest alleen een zinnige bewaarde breedte", () => {
    expect(leesBreedte(512.4)).toBe(512);
    expect(leesBreedte("512")).toBeUndefined();
    expect(leesBreedte(10)).toBeUndefined();
    expect(leesBreedte(Number.NaN)).toBeUndefined();
  });
});
