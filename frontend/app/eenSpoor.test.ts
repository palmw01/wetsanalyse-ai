import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén spoor per beurt (9 nov 2026). Onder een antwoord stond naast het Denkproces een tweede blok, "Graaf geraadpleegd ·
 *  N aanroepen", met toolnamen, ruwe JSON en milliseconden; het heette ook "graaf" als Lex een Kamerstuk las. Wat de
 *  jurist ervan nodig heeft, zet graph-qa als regel in het denkproces ("Kamerstukken · 16 gevonden",
 *  `agent/spoorbronnen.py`). Deze toets houdt het tweede blok weg. */

const WORTEL = join(__dirname, "..");

function bronnen(map: string): string[] {
  return readdirSync(map).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(pad).isDirectory()) return bronnen(pad);
    return /\.(ts|tsx)$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}

const CODE = ["app", "components", "lib"].flatMap((m) => bronnen(join(WORTEL, m)));

describe("één spoor per beurt", () => {
  it("er is geen apart toolspoor-component", () => {
    expect(existsSync(join(WORTEL, "components/werkplek/ToolSpoor.tsx"))).toBe(false);
    for (const pad of CODE) expect(readFileSync(pad, "utf8"), pad).not.toMatch(/\bToolSpoor\b/);
  });

  it("de werkplek leest de ruwe toolaanroepen niet", () => {
    // Het veld blijft in `Bericht` (audit, eval); wie het weer toont, bouwt het tweede blok opnieuw.
    for (const pad of CODE.filter((p) => !p.endsWith(join("lib", "types.ts"))))
      expect(readFileSync(pad, "utf8"), pad).not.toMatch(/tool_executions|toolExecutions|onToolExecution/);
  });

  it("nergens staat 'geraadpleegd ·'", () => {
    for (const pad of CODE) expect(readFileSync(pad, "utf8"), pad).not.toMatch(/geraadpleegd ·/i);
  });
});
