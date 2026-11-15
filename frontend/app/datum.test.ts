import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén plek voor datum en tijd (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md`
 *  §8): ruim vijftien plekken formatteerden zelf, in zes vormen en deels zonder Nederlandse tijdzone, zodat hetzelfde
 *  moment op de begripskaart, in de historie en in de revisies telkens anders stond. Nu komt het uit `lib/datum.ts`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("datum en tijd komen uit lib/datum.ts", () => {
  it("niemand anders formatteert een datum of tijd", () => {
    const eigenVorm = new Set([
      "lib/datum.ts",
      // De reset van het tokenbudget rekent bewust in lokale kalenderdagen ("vandaag", "morgen"); zie tokenbudget.test.ts.
      "lib/tokenbudget.ts",
    ]);
    const fout = [...alle("components"), ...alle("app"), ...alle("lib")].filter((p) => !eigenVorm.has(p))
      .filter((p) => /toLocaleDateString\(|toLocaleTimeString\(|new Date\([^)]*\)\.toLocaleString\(|\bd\.toLocaleString\(|dateStyle:/.test(lees(p)));
    expect(fout).toEqual([]);
  });
});
