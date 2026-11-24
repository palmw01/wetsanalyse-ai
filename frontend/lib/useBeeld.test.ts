import { describe, expect, it } from "vitest";

import { knijp, maat, naarTekening, zoomRond, ZOOM_IN, type Beeld } from "./useBeeld";

const ALLES: Beeld = { x: 0, y: 0, b: 200, h: 100 };
const VAK = { left: 10, top: 20, width: 400, height: 200 };   // schaal 2, zonder rand

describe("useBeeld: de rekenkern van zoomen, slepen en knijpen", () => {
  it("vindt het punt in de tekening onder het scherm, ook met een rand (xMidYMid meet)", () => {
    expect(naarTekening(ALLES, VAK, 210, 120)).toEqual({ x: 100, y: 50 });
    const breed = { ...VAK, width: 600 };   // 100 px rand links en rechts
    expect(maat(ALLES, breed)).toEqual({ s: 2, ox: 100, oy: 0 });
    expect(naarTekening(ALLES, breed, 110, 20)).toEqual({ x: 0, y: 0 });
  });

  it("zoomt rond een punt dat op zijn plek blijft, en begrenst", () => {
    const v = zoomRond(ALLES, 0.5, ALLES, { x: 50, y: 50 });
    expect(v).toEqual({ x: 25, y: 25, b: 100, h: 50 });
    expect(zoomRond(ALLES, 0.001, ALLES).b).toBeCloseTo(ALLES.b / ZOOM_IN);
    expect(zoomRond(ALLES, 100, ALLES).b).toBeCloseTo(ALLES.b * 1.2);
  });

  it("knijpen: twee keer zo ver uit elkaar is twee keer zo dichtbij, met het midden op zijn plek", () => {
    const m = { x: 210, y: 120 };   // het midden van de tekening (100, 50)
    const v = knijp(ALLES, VAK, ALLES, { midden: m, afstand: 50 }, { midden: m, afstand: 100 });
    expect(v.b).toBeCloseTo(100);
    expect(v.h).toBeCloseTo(50);
    const s = maat(v, VAK);
    expect(v.x + (m.x - VAK.left - s.ox) / s.s).toBeCloseTo(100);
    expect(v.y + (m.y - VAK.top - s.oy) / s.s).toBeCloseTo(50);
  });

  it("knijpen verschuift mee met het midden van de vingers", () => {
    const v = knijp(ALLES, VAK, ALLES, { midden: { x: 210, y: 120 }, afstand: 80 }, { midden: { x: 250, y: 120 }, afstand: 80 });
    expect(v.b).toBeCloseTo(200);
    expect(v.x).toBeCloseTo(-20);   // 40 px naar rechts is 20 eenheden bij schaal 2
  });
});
