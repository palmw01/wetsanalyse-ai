import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { aantal } from "@/lib/aantal";

/** Een aantal met het juiste woord (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md`
 *  §12): ruim zeventig keer met de hand, in drie schrijfwijzen (`n === 1 ? "1 bron" : …`, `${n} ${n === 1 ? … }` en
 *  `regeling{n === 1 ? "" : "en"}`), en vier eigen hulpjes. Nu is het `aantal` in `lib/aantal.ts`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app"), ...alle("lib")].filter((p) => p !== "lib/aantal.ts");
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("een aantal met het juiste woord is aantal()", () => {
  it("zegt 1 bron en 3 bronnen", () => {
    expect(aantal(1, "bron", "bronnen")).toBe("1 bron");
    expect(aantal(0, "bron", "bronnen")).toBe("0 bronnen");
    expect(aantal(3, "passage veranderde", "passages veranderden")).toBe("3 passages veranderden");
  });

  it("niemand schrijft het zelf", () => {
    const zelf = [
      /=== 1 \? "1 /, // n === 1 ? "1 bron" : `${n} bronnen`
      /\$\{([\w.?!\[\]()]+)\} \$\{\1 === 1 \?/, // `${n} ${n === 1 ? "bron" : "bronnen"}`
      /\{([\w.?!\[\]()]+)\} \{\1 === 1 \?/, // {n} {n === 1 ? "bron" : "bronnen"}
      /\w[{$]\{?[\w.?!\[\]()]+ === 1 \? "" : "\w+"/, // regeling{n === 1 ? "" : "en"}
      /\(\w+: number, een: string, meer: string\) =>/, // een eigen hulpje
    ];
    // De graafbalk zet het getal in duizendtallen (Intl.NumberFormat), het antwoord zegt "ten minste": dat is meer dan
    // een aantal met een woord.
    const eigenVorm = new Set(["lib/graaf/bediening.ts", "lib/antwoord.ts"]);
    expect(bestanden.filter((p) => !eigenVorm.has(p) && zelf.some((r) => r.test(lees(p))))).toEqual([]);
  });
});
