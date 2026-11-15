import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén denkproces-opbouw (12 nov 2026). Het denkproces werd op twee plekken opgebouwd (de beurt en de reeks), elk met
 *  een eigen kopie van de regel, en de reeks miste de regelgrens. Nu doet alleen `lib/denkproces.ts` het (`denkBij`);
 *  deze toets houdt een tweede kopie weg. Het antwoord (`token`) komt er nooit in. */

const WORTEL = join(__dirname, "..");
const EIGENAAR = join("lib", "denkproces.ts");

function bronnen(map: string): string[] {
  return readdirSync(map).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(pad).isDirectory()) return bronnen(pad);
    return /\.(ts|tsx)$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}

const CODE = ["app", "components", "lib"].flatMap((m) => bronnen(join(WORTEL, m)));

describe("één denkproces-opbouw", () => {
  it("alleen lib/denkproces.ts plakt iets aan een denkproces", () => {
    for (const pad of CODE.filter((p) => !p.endsWith(EIGENAAR)))
      expect(readFileSync(pad, "utf8"), pad).not.toMatch(/\bdenk\s*\+|denk\s*\+=|denk:\s*[\w.]*denk\s*\+/);
  });

  it("de statusregel heeft één vorm", () => {
    for (const pad of CODE.filter((p) => !p.endsWith(EIGENAAR)))
      expect(readFileSync(pad, "utf8"), pad).not.toMatch(/"· "\s*\+/);
  });

  it("Lex is bezig: drie stippen, alleen in Denkt, alleen met beweging als de gebruiker die toestaat", () => {
    // Generieke componenten, 15 nov 2026 (`docs/architectuur/plan-generieke-componenten.md` §9): grijze stippen die
    // tegelijk knipperden bij een antwoord, blauwe die golfden bij een vraagkaart.
    const anders = CODE.filter((p) => !p.endsWith(join("components", "ui", "Denkt.tsx")))
      .filter((p) => /animationDelay|function Punten\b/.test(readFileSync(p, "utf8")));
    expect(anders).toEqual([]);
    for (const pad of CODE.filter((p) => p.includes(join("components", "werkplek"))))
      expect(readFileSync(pad, "utf8"), pad).not.toMatch(/(?<!motion-safe:)animate-pulse/);
  });
});
