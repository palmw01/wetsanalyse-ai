import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Het bronvenster, PR 6 (kernprincipe: generieke componenten): de tekst van een stuk uit een bronconnector wordt op één
// manier getekend (`ConnectorTekst`), in het antwoord en in het venster; niets in `components/` kent een connector bij
// naam – wat een stuk is, komt uit de beschrijving van de connector.
const ROOT = join(__dirname, "..");
function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const COMPONENTEN = bestanden("components");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
const CONNECTORTEKST = join("components", "wettekst", "ConnectorTekst.tsx");

describe("één weergave van connectortekst", () => {
  it("de rijsoorten (voetnoot, tabel met cellen) staan alleen in ConnectorTekst", () => {
    const tekenaars = COMPONENTEN.filter((p) => /data-extern-voetnoot|data-extern-tabel|externGroepen\(/.test(bron(p)));
    expect(tekenaars).toEqual([CONNECTORTEKST]);
  });

  it("geen connector bij naam in components/", () => {
    // Commentaar telt niet: alleen code en tekst in beeld.
    const zonderCommentaar = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
    const fout = COMPONENTEN.filter((p) => /["'`]kst-|Kamerstuk|ECLI:/.test(zonderCommentaar(bron(p))));
    expect(fout).toEqual([]);
  });

  it("een stuk in een antwoord opent via StukVindplaats, niet met een kale link", () => {
    const antwoord = bron(join("components", "antwoord", "Antwoord.tsx"));
    expect(antwoord).not.toMatch(/href=\{blok\.link\}|href=\{s\.link\}/);
    expect(antwoord).toMatch(/<StukVindplaats /);
  });
});
