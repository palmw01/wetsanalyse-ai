import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Eén Vraag Lex (ontdubbelen PR 5, kernprincipe van de gebruiker: één component per patroon). De knop is overal
// `VraagLexKnop`, de suggesties staan in één register per soort (`lib/vraagLex.ts`), en elke plek geeft alleen haar
// onderwerp mee. Geen eigen knop met de tekst *Vraag Lex*, geen voorgevulde vraag naast het register, geen dode haak.
const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const CODE = ["app", "components", "lib"].flatMap(bestanden);
const KNOP = join("components", "werkplek", "VraagLexKnop.tsx");

describe("één Vraag Lex", () => {
  it("de tekst Vraag Lex of Bespreek met Lex op een knop staat alleen in VraagLexKnop", () => {
    // Als JSX-tekst of als string-literal in een knop; uitleg in een zin ("Vraag Lex om …") telt niet.
    const plekken = CODE.filter((p) => p.endsWith(".tsx") && p !== KNOP
      && (/>\s*(Vraag Lex|Bespreek met Lex)\s*</.test(bron(p)) || /["'`](Vraag Lex|Bespreek met Lex)["'`]/.test(bron(p))));
    expect(plekken).toEqual([]);
  });

  it("geen eigen ketens naast het register", () => {
    for (const p of CODE) {
      const s = bron(p);
      expect(s, p).not.toMatch(/onVraagOverBron|onVraagLex\b/);
      // De oude markeringsketen (`onVraag(el, view)`) is `vraagOnderwerp`.
      expect(s, p).not.toMatch(/\bonVraag=\{/);
    }
  });

  it("een vraag-URL komt alleen uit vraagUrl", () => {
    // In een string (niet in uitleg tussen backticks in commentaar): "/workbench?vraag=…".
    const bouwers = CODE.filter((p) => /["'][^"'\n]*[?&]vraag=/.test(bron(p)) && p !== join("lib", "vraagLex.ts"));
    expect(bouwers).toEqual([]);
  });

  it("de kop van venster, annotatie en werkgebiedpaneel draagt de knop", () => {
    for (const p of ["components/werkplek/ContextPaneel.tsx", "components/annotaties/NodeAnnotatiePaneel.tsx",
      "components/werkplek/WerkgebiedArtefactPaneel.tsx"]) {
      expect(bron(p), p).toMatch(/<VraagLexKnop onderwerp=/);
    }
  });
});
