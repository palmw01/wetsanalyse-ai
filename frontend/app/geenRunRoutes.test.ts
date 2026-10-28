import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");

/** Alle `.ts`/`.tsx`-bestanden onder een map, recursief, zonder deze toets zelf. */
function bronnen(pad: string): string[] {
  const uit: string[] = [];
  for (const naam of readdirSync(pad)) {
    const vol = join(pad, naam);
    if (naam === "node_modules" || naam.startsWith(".")) continue;
    if (statSync(vol).isDirectory()) uit.push(...bronnen(vol));
    else if (/\.tsx?$/.test(naam) && vol !== __filename) uit.push(vol);
  }
  return uit;
}

// F3e: wat Lex met een werkgebied doet, vraag je in het gesprek (de agents onder de supervisor, ADR-005).
// De werkgebiedpagina startte vroeger zelf runs via vier statische BFF-routes en via `annoteer=`/`meedenk=`
// op de werkplek; een tweede weg naar hetzelfde werk mag niet terugkomen.
describe("één weg naar Lex", () => {
  const bestanden = ["app", "components", "lib"].flatMap((m) => bronnen(join(ROOT, m)));

  it("geen component of helper roept een /api/*-run-route aan", () => {
    const treffers = bestanden.filter((f) => /\/api\/(deelvragen|kaart|bronnen|begrippen)-run\b/.test(readFileSync(f, "utf8")));
    expect(treffers.map((f) => relative(ROOT, f))).toEqual([]);
  });

  it("de routes zelf bestaan niet meer", () => {
    const er = ["deelvragen-run", "kaart-run", "bronnen-run", "begrippen-run"]
      .filter((r) => existsSync(join(ROOT, "app", "api", r)));
    expect(er).toEqual([]);
  });

  it("de werkplek start niets meer vanuit de URL", () => {
    const treffers = bestanden.filter((f) => /[?&](annoteer|meedenk)=|get\("(annoteer|meedenk)"\)/.test(readFileSync(f, "utf8")));
    expect(treffers.map((f) => relative(ROOT, f))).toEqual([]);
  });
});
