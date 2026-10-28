import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");

/** Alle `.ts`/`.tsx`-bestanden onder een map, recursief, zonder tests. */
function bronnen(pad: string): string[] {
  const uit: string[] = [];
  for (const naam of readdirSync(pad)) {
    const vol = join(pad, naam);
    if (naam === "node_modules" || naam.startsWith(".")) continue;
    if (statSync(vol).isDirectory()) uit.push(...bronnen(vol));
    else if (/\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam)) uit.push(vol);
  }
  return uit;
}

/** De bron zonder commentaar: blokcommentaar (ook `{/* … *\/}` in JSX) en `//` aan het begin of na witruimte,
 *  zodat een URL in een string blijft staan. */
function zonderCommentaar(bron: string): string {
  return bron.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
}

// Spoor I5: in beeld heet het *verwijderen*. "Weghalen", "wegklikken" en "haal(t) … weg" komen niet terug,
// ook niet als identifier (die belandt makkelijk in een label).
const WEGHALEN = /weg\s*-?hal|weggehaald|wegklik|\bhaalt?\s+(?:\S+\s+){0,5}weg\b/i;

describe("verwijderen, niet weghalen", () => {
  it("vindt de vormen en laat commentaar buiten beschouwing", () => {
    expect(WEGHALEN.test(zonderCommentaar('<button>Weghalen</button>'))).toBe(true);
    expect(WEGHALEN.test(zonderCommentaar('"Relatie weggehaald."'))).toBe(true);
    expect(WEGHALEN.test(zonderCommentaar('"Een gesprek verwijderen haalt ze niet weg."'))).toBe(true);
    expect(WEGHALEN.test(zonderCommentaar('aria-label="Vraag wegklikken"'))).toBe(true);
    expect(WEGHALEN.test(zonderCommentaar("// de melding weer weghalen\nconst a = 1;"))).toBe(false);
    expect(WEGHALEN.test(zonderCommentaar("/* wegklikken */ const b = 'https://x.nl/weg';"))).toBe(false);
  });

  it("geen tekst in components/, app/ of lib/ zegt weghalen", () => {
    const treffers = ["app", "components", "lib"]
      .flatMap((m) => bronnen(join(ROOT, m)))
      .flatMap((f) => zonderCommentaar(readFileSync(f, "utf8")).split("\n")
        .filter((r) => WEGHALEN.test(r)).map((r) => `${relative(ROOT, f)}: ${r.trim()}`));
    expect(treffers).toEqual([]);
  });
});
