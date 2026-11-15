import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén uitklap (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §6): ruim twintig
 *  `<details>` in drie families met eigen klassen, de ene met een draaiende chevron, de andere met het driehoekje van de
 *  browser (per platform anders, zie *Symbolen zijn iconen*), en één zonder focusring. Nu is het `Uitklap`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
});
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("een uitklap is Uitklap", () => {
  it("<details> en <summary> staan alleen in Uitklap", () => {
    const fout = [...alle("components"), ...alle("app")].filter((p) => p !== "components/ui/Uitklap.tsx")
      .filter((p) => /<(details|summary)\b/.test(lees(p)));
    expect(fout).toEqual([]);
  });

  it("de chevron draait op de dichtstbijzijnde uitklap en het driehoekje van de browser is weg", () => {
    const s = lees("components/ui/Uitklap.tsx");
    expect(s).toContain("[[open]>summary>&]:rotate-0");
    expect(s).toContain("list-none");
    expect(s).toContain("[&::-webkit-details-marker]:hidden");
    expect(s).toContain("focus-ring");
  });
});
