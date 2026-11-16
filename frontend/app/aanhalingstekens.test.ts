/** Eén stijl aanhalingstekens in beeld: “…” (melding gebruiker 16 nov 2026). graph-qa heeft dezelfde toets
 *  (`tests/test_aanhalingstekens.py`). */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function bestanden(map: string): string[] {
  return readdirSync(map).flatMap((n) => {
    const p = join(map, n);
    if (statSync(p).isDirectory()) return bestanden(p);
    return /\.tsx?$/.test(n) && !/\.test\.tsx?$/.test(n) ? [p] : [];
  });
}

describe("aanhalingstekens", () => {
  it("gebruikt “…” en nooit de lage vorm (U+201E)", () => {
    const fout = ["app", "components", "lib"].flatMap(bestanden).filter((p) => readFileSync(p, "utf8").includes("\u201e"));
    expect(fout).toEqual([]);
  });
});
