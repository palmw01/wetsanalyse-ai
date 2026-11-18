import { describe, expect, it } from "vitest";

import { moetNuVerversen, TERUGKOMST_MS } from "./useBijTerugkomst";

describe("moetNuVerversen", () => {
  it("ververst alleen zichtbaar en niet vaker dan eens per wachttijd", () => {
    expect(moetNuVerversen(false, 100_000, 0)).toBe(false);
    expect(moetNuVerversen(true, TERUGKOMST_MS - 1, 0)).toBe(false);
    expect(moetNuVerversen(true, TERUGKOMST_MS, 0)).toBe(true);
  });
});
