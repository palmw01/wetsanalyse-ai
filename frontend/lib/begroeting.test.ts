import { describe, expect, it } from "vitest";
import { begroeting } from "./begroeting";

const om = (u: number, m = 0) => new Date(2026, 9, 6, u, m);

describe("begroeting", () => {
  it.each([
    [0, 0, "Goedenacht"], [5, 59, "Goedenacht"],
    [6, 0, "Goedemorgen"], [11, 59, "Goedemorgen"],
    [12, 0, "Goedemiddag"], [17, 59, "Goedemiddag"],
    [18, 0, "Goedenavond"], [23, 59, "Goedenavond"],
  ])("%i:%i → %s", (u, m, groet) => {
    expect(begroeting(om(u, m))).toBe(groet);
  });
});
