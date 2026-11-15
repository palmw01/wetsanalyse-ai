import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén weg naar het klembord (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md`
 *  §10): vier plekken kopieerden zelf, met drie zinnen als het niet lukte. Nu gaat het via `lib/kopieer.ts`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app"), ...alle("lib")].filter((p) => p !== "lib/kopieer.ts");
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("kopiëren gaat via lib/kopieer.ts", () => {
  it("niemand anders roept navigator.clipboard aan", () => {
    expect(bestanden.filter((p) => lees(p).includes("navigator.clipboard"))).toEqual([]);
  });

  it("de zin bij een mislukte kopie staat op één plek", () => {
    expect(bestanden.filter((p) => /Kopiëren (lukt|lukte) niet/.test(lees(p)))).toEqual([]);
  });
});
