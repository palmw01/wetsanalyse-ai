import { describe, expect, it } from "vitest";

import { markeerbanen } from "./markeerbanen";
import VECTOREN from "./markeerbanen.vectoren.json";

type Stuk = [number, number, string | null, [string, number][], string[]];

/** Dezelfde gevallen als `api/tests/test_markeerbanen.py`: rapport en werkplek tekenen dezelfde banen. */
describe("markeerbanen – de gedeelde gevallen met het rapport", () => {
  for (const g of VECTOREN.gevallen) {
    it(g.naam, () => {
      const uit = markeerbanen(g.lengte, (g.spans as [string, number, number][]).map(([sleutel, start, eind]) => ({ sleutel, start, eind })));
      expect(uit.aantal).toBe(g.verwacht.aantal);
      expect(uit.stukken.map((s) => [s.start, s.eind, s.vlak, s.banen.map((b) => [b.sleutel, b.baan]), s.eindigt]))
        .toEqual(g.verwacht.stukken as Stuk[]);
    });
  }
});

describe("markeerbanen – eigenschappen", () => {
  it("de stukken sluiten aan en dekken de hele tekst", () => {
    for (const g of VECTOREN.gevallen) {
      const { stukken } = markeerbanen(g.lengte, (g.spans as [string, number, number][]).map(([sleutel, start, eind]) => ({ sleutel, start, eind })));
      expect(stukken[0].start).toBe(0);
      expect(stukken.at(-1)!.eind).toBe(g.lengte);
      stukken.slice(1).forEach((s, i) => expect(s.start).toBe(stukken[i].eind));
    }
  });

  it("art. 13 lid 1 AWR: de rechtsbetrekking en de voorwaarde liggen eronder, de woorden houden hun vlak", () => {
    const g = VECTOREN.gevallen.find((x) => x.naam.startsWith("art. 13"))!;
    const { stukken, aantal } = markeerbanen(g.lengte, (g.spans as [string, number, number][]).map(([sleutel, start, eind]) => ({ sleutel, start, eind })));
    expect(aantal).toBe(2);
    const metVlak = new Set(stukken.map((s) => s.vlak).filter(Boolean));
    expect(metVlak.has("2")).toBe(false);     // de rechtsbetrekking
    expect(metVlak.has("1")).toBe(false);     // de voorwaarde
    expect(metVlak.has("3")).toBe(true);      // de grootte
    expect(stukken.every((s) => s.banen.some((b) => b.sleutel === "2"))).toBe(true);
  });
});
