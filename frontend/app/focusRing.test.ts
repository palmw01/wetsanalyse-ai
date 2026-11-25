import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..");

function bestanden(map: string): string[] {
  return readdirSync(map).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(pad).isDirectory()) return naam === "node_modules" ? [] : bestanden(pad);
    return pad.endsWith(".tsx") ? [pad] : [];
  });
}

/** De openingstag rond positie `i`: van de `<` ervoor tot de `>` die hem sluit (accolades tellen mee). */
function tagRond(bron: string, i: number): string {
  let begin = i;
  while (begin > 0 && !(bron[begin] === "<" && /[A-Za-z]/.test(bron[begin + 1] ?? ""))) begin--;
  let diepte = 0;
  for (let j = begin; j < bron.length; j++) {
    if (bron[j] === "{") diepte++;
    else if (bron[j] === "}") diepte--;
    else if (bron[j] === ">" && diepte === 0 && bron[j - 1] !== "=") return bron.slice(begin, j + 1);
  }
  return bron.slice(begin);
}

// Melding gebruiker 25 nov 2026: elke stap van de rondleiding had een blauw kader om de titel. De rondleiding zet de focus
// op die titel (voor de schermlezer), en een programmatische focus na een klik of toets is voor de browser
// `:focus-visible`. Een element dat alleen programmatisch focus krijgt (`tabIndex={-1}`: een staptitel, het paneel van
// een venster, de hoofdinhoud na de skip-link) is geen bediening en krijgt dus geen ring.
describe("geen focusring op een element met tabIndex -1", () => {
  const tags = ["app", "components"].flatMap((m) => bestanden(join(ROOT, m))).flatMap((pad) => {
    // Zonder opmerkingen: daar staat `tabIndex={-1}` soms als uitleg.
    const bron = readFileSync(pad, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    return [...bron.matchAll(/tabIndex=\{-1\}/g)].map((m) => ({ pad: relative(ROOT, pad), tag: tagRond(bron, m.index!) }));
  });

  it("vindt de plekken", () => {
    expect(tags.length).toBeGreaterThan(5);
    expect(tags.some((t) => t.pad.endsWith("TourBubbel.tsx"))).toBe(true);
  });

  it("draagt nooit focus-ring", () => {
    for (const { pad, tag } of tags) expect(tag, pad).not.toMatch(/focus-ring/);
  });

  it("zet de ring van de browser uit, behalve bij een veld (dat krijgt alleen een klik)", () => {
    const dialoog = readFileSync(join(ROOT, "components/ui/Dialog.tsx"), "utf8");
    const panelen = dialoog.slice(dialoog.indexOf("const PANEEL_CLASS"), dialoog.indexOf("};", dialoog.indexOf("const PANEEL_CLASS")));
    for (const vorm of ["fullscreen", "center", "compact", "side", "kolom", "drawer"]) {
      const regel = panelen.slice(panelen.indexOf(`${vorm}:`)).split(/\n\s{2}[a-z]+:/)[0];
      expect(regel, `PANEEL_CLASS.${vorm}`).toMatch(/outline-none/);
    }
    for (const { pad, tag } of tags) {
      if (/^<(input|textarea|select)\b/.test(tag)) continue;
      expect(/outline-none|PANEEL_CLASS\[/.test(tag), `${pad}: ${tag.slice(0, 120)}`).toBe(true);
    }
  });
});
