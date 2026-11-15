import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Tekstmaten, kleuren en hoeken uit de tokens (generieke componenten, 15 nov 2026,
 *  `docs/architectuur/plan-generieke-componenten.md` §11): 121 losse tekstmaten (11px, 0.7rem, 10px, 0.65rem …, deels
 *  hetzelfde anders geschreven), `bg-white` naast `bg-paper` (dat de donkere stand niet volgt) en eigen hoeken. Nu staan
 *  ze in `tailwind.config.ts`: `text-3xs`, `text-2xs`, `text-meta`, `text-lees`, `text-teller` en `rounded-vraag`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
// De foutgrens van Next vervangt de hele documentboom en kan de app-CSS niet veronderstellen (frontend/CLAUDE.md).
const bestanden = [...alle("components"), ...alle("app"), ...alle("lib")].filter((p) => p !== "app/global-error.tsx");
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("vormgeving uit de tokens", () => {
  it("geen losse tekstmaat", () => {
    expect(bestanden.filter((p) => /text-\[\d[\d.]*(px|rem)\]/.test(lees(p)))).toEqual([]);
  });

  it("geen bg-white: de achtergrond is bg-paper", () => {
    expect(bestanden.filter((p) => /\bbg-white\b/.test(lees(p)))).toEqual([]);
  });

  it("geen losse hoek in pixels", () => {
    expect(bestanden.filter((p) => /rounded-\[\d+px\]/.test(lees(p)))).toEqual([]);
  });
});
