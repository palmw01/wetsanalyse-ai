import { describe, expect, it } from "vitest";

import { Venstertel } from "@/app/api/_lib/venstertel";

describe("Venstertel", () => {
  it("laat door tot de grens en weigert daarna", () => {
    const tel = new Venstertel(3, 1000);
    expect([1, 2, 3].map(() => tel.mag("palmw01", 0))).toEqual([true, true, true]);
    expect(tel.mag("palmw01", 0)).toBe(false);
  });

  it("begint opnieuw zodra het venster voorbij is", () => {
    const tel = new Venstertel(2, 1000);
    tel.mag("palmw01", 0);
    tel.mag("palmw01", 0);
    expect(tel.mag("palmw01", 500)).toBe(false);
    expect(tel.mag("palmw01", 1001)).toBe(true);
  });

  it("telt per sleutel, niet over gebruikers heen", () => {
    const tel = new Venstertel(1, 1000);
    expect(tel.mag("a", 0)).toBe(true);
    expect(tel.mag("b", 0)).toBe(true);
    expect(tel.mag("a", 0)).toBe(false);
  });

  it("ruimt verlopen vensters op in plaats van te blijven groeien", () => {
    const tel = new Venstertel(5, 1000, 3);
    tel.mag("a", 0);
    tel.mag("b", 0);
    tel.mag("c", 0);
    expect(tel.omvang).toBe(3);
    // Ver na hun venster: de opruiming loopt en houdt alleen de nieuwe sleutel over.
    tel.mag("d", 5000);
    expect(tel.omvang).toBe(1);
  });
});
