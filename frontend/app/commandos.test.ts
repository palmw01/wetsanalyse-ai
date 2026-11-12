import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");

function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
const code = [...bestanden("app"), ...bestanden("components"), ...bestanden("lib")];

// `/commando's` zijn één register (`lib/commandos.ts` over de suggesties van `lib/vraagLex.ts`) en één invoer: het
// invoerveld van de werkplek. Geen tweede lijst, geen tweede parser, en `/` is tekst, geen sneltoets.
describe("commando's: één register, één ingang", () => {
  it("alleen de werkplek gebruikt het menu en de regels", () => {
    const gebruikers = code.filter((p) => /from "@\/lib\/commandos"|from "\.\/commandos"/.test(bron(p)));
    expect(gebruikers.sort()).toEqual(["components/werkplek/CommandoMenu.tsx", "components/werkplek/WerkplekClient.tsx"]);
    expect(code.filter((p) => /<CommandoMenu\b/.test(bron(p)))).toEqual(["components/werkplek/WerkplekClient.tsx"]);
  });

  it("er is geen tweede lijst met commandonamen of een eigen ontleding van '/'", () => {
    for (const p of code.filter((x) => x !== "lib/commandos.ts")) {
      expect(bron(p), p).not.toMatch(/startsWith\(\s*["'`]\/["'`]\s*\)/);
      expect(bron(p), p).not.toMatch(/\bCLIENT_COMMANDOS\s*=/);
    }
  });

  it("'/' is geen sneltoets: geen toets '/' buiten een invoerveld", () => {
    for (const p of code) expect(bron(p), p).not.toMatch(/key\s*===?\s*["']\/["']/);
  });

  it("een suggestie en een commando gaan langs dezelfde functie", () => {
    const werkplek = bron("components/werkplek/WerkplekClient.tsx");
    expect(werkplek).toMatch(/onClick=\{\(\) => voerSuggestieUit\(s\)\}/);
    expect(werkplek).toMatch(/if \(u\.soort === "suggestie"\) return voerSuggestieUit\(u\.suggestie\)/);
    // Precies één plek die een suggestie verstuurt.
    expect(werkplek.match(/prompt: s\.tekst, actie: s\.actie/g)).toHaveLength(1);
  });
});
