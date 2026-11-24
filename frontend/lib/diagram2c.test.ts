import { describe, expect, it } from "vitest";

import { inhoudKader, type DiagramData } from "./diagram2c";

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
