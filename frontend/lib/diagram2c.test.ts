import { describe, expect, it } from "vitest";

import { inhoudKader, LEESBARE_SCHAAL, leesbaarBegin, type DiagramData } from "./diagram2c";

const knoop = (x: number, y: number) => ({ knoop: {} as never, x, y, b: 60, h: 30, kop: "", regels: [] });

describe("inhoudKader", () => {
  it("omsluit de knopen en de labels, niet de volle breedte van de plaatsing", () => {
    const data = {
      plaatsing: { breedte: 300, hoogte: 120, knopen: [knoop(120, 0), knoop(120, 80)] },
      lijnen: [{ x1: 150, y1: 30, x2: 150, y2: 80, lx: 150, ly: 55, lb: 80, lh: 10 } as DiagramData["lijnen"][number]],
    };
    expect(inhoudKader(data, 3)).toEqual({ x: 107, y: -3, b: 86, h: 116 });
  });

  it("valt zonder inhoud terug op de plaatsing", () => {
    expect(inhoudKader({ plaatsing: { breedte: 300, hoogte: 120, knopen: [] }, lijnen: [] }, 3))
      .toEqual({ x: -3, y: -3, b: 306, h: 126 });
  });
});

describe("een leesbaar begin in een paneel", () => {
  const alles = { x: -3, y: -3, b: 1026, h: 198 };
  const centraal = { x: 180, b: 120 };

  it("toont de hele tekening als die leesbaar in de breedte past", () => {
    expect(leesbaarBegin(alles, centraal, 1600)).toEqual(alles);
    expect(leesbaarBegin(alles, centraal, 0)).toEqual(alles); // nog niet gemeten
  });

  it("begint anders op leesbare schaal, over de volle hoogte, rond de centrale formulering", () => {
    const b = leesbaarBegin(alles, centraal, 480);
    expect(480 / b.b).toBeCloseTo(LEESBARE_SCHAAL);
    expect([b.y, b.h]).toEqual([alles.y, alles.h]);
    expect(b.x + b.b / 2).toBeCloseTo(240);
  });

  it("blijft binnen de tekening", () => {
    const links = leesbaarBegin(alles, { x: 0, b: 20 }, 300);
    expect(links.x).toBe(alles.x);
    const rechts = leesbaarBegin(alles, { x: 1000, b: 20 }, 300);
    expect(rechts.x + rechts.b).toBeCloseTo(alles.x + alles.b);
  });
});
