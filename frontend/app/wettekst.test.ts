import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Het bronvenster, PR 2 (kernprincipe van de gebruiker: generieke componenten in plaats van deeloplossingen): de
// wettekst wordt op één manier getekend (`WettekstBlok`) en op één manier opgehaald (`useBron`). Geen plek bouwt een
// eigen weergave of haalt de weergave zelf op.
const ROOT = join(__dirname, "..");
function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const CODE = ["app", "components", "lib"].flatMap(bestanden);
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

describe("één wettekstweergave", () => {
  it("de tekst met markeringen staat alleen in WettekstBlok", () => {
    // Het testid van de tekst en de markeringen-op-ankers (`spansVan`) horen bij één component.
    const tekenaars = CODE.filter((p) => /data-testid="graaf-knooptekst"/.test(bron(p)));
    expect(tekenaars).toEqual([join("components", "wettekst", "WettekstBlok.tsx")]);
    const spans = CODE.filter((p) => /\bspansVan\(/.test(bron(p)) && !p.startsWith(join("lib", "graaf")));
    expect(spans).toEqual([join("components", "wettekst", "WettekstBlok.tsx")]);
    expect(CODE.some((p) => /\bKnoopTekst\b/.test(bron(p)))).toBe(false);
  });

  it("geen eigen component Wettekst buiten components/wettekst", () => {
    const eigen = CODE.filter((p) => !p.startsWith(join("components", "wettekst"))
      && /function Wettekst\b|export (const|function) Wettekst\b/.test(bron(p)));
    expect(eigen).toEqual([]);
    expect(CODE.some((p) => /components\/bronnen\/Wettekst/.test(bron(p)))).toBe(false);
  });

  it("de weergave van een bepaling haalt alleen useBron op (en de annotatieopslag)", () => {
    const halers = CODE.filter((p) => /\bhaalNodeWeergave\(/.test(bron(p)));
    expect(halers.sort()).toEqual([join("lib", "annotatieNode.ts"), join("lib", "useBron.ts")]);
  });

  it("de filter op de actuele markeringen staat op één plek", () => {
    // De adapter van de annotatie filtert strenger (ook `vervangen`, alleen met klasse): die hoort bij het annoteren.
    const filters = CODE.filter((p) => p !== join("lib", "annotatieNodeAdapter.ts")
      && /!e\.verouderd && e\.lifecycle !== "rejected"/.test(bron(p)));
    expect(filters).toEqual([join("lib", "bronWeergave.ts")]);
  });

  it("de bronpagina is het bronvenster als pagina, zonder eigen tekstkaart (PR 5)", () => {
    const pagina = bron(join("components", "bronnen", "BronPagina.tsx"));
    expect(pagina).toMatch(/<BronVenster variant="pagina"/);
    expect(pagina).not.toMatch(/<WettekstBlok|<Kaart titel="Wettekst"|<Kaart titel="JAS-elementen"/);
  });

  it("de graaf van een bron staat alleen in BronGraaf, met één keuze Tekst | Graaf (ontdubbelen PR 1)", () => {
    const graven = CODE.filter((p) => /\buseGraafStand\(/.test(bron(p)) && !p.endsWith("useGraafStand.ts"));
    expect(graven.sort()).toEqual([join("components", "werkgebieden", "SamenhangTab.tsx"), join("components", "wettekst", "BronGraaf.tsx")]);
    // Geen eigen Tekst/Graaf-knoppen met aria-pressed, en geen losse samenhangknop in de kop van het venster.
    for (const p of CODE) {
      expect(bron(p), p).not.toMatch(/\(\["tekst", "graaf"\] as const\)\.map/);
      expect(bron(p), p).not.toMatch(/data-bron-samenhang/);
    }
  });

  it("de annotatie tekent dezelfde wettekst, met de markeerlaag erop (ontdubbelen PR 4)", () => {
    // Geen tweede tekstweergave: geen DocumentPaneel, `data-offset` (de selectie-ankers) alleen in WettekstBlok, en de
    // blokken uit de nummervorm (`blokkenVan`) niet meer in een component.
    expect(CODE.filter((p) => /DocumentPaneel/.test(p))).toEqual([]);
    const offsets = CODE.filter((p) => /data-offset=/.test(bron(p)));
    expect(offsets).toEqual([join("components", "wettekst", "WettekstBlok.tsx")]);
    const blokken = CODE.filter((p) => p.startsWith("components") && /\bblokkenVan\(/.test(bron(p)));
    expect(blokken).toEqual([]);
    expect(bron(join("components", "werkplek", "AnnotatieTekst.tsx"))).toMatch(/<WettekstBlok groot laag=/);
  });
});
