import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { icoonKnopKlasse } from "@/components/ui/Button";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

function bestanden(map: string): string[] {
  return readdirSync(join(ROOT, map)).flatMap((naam) => {
    const pad = join(map, naam);
    if (statSync(join(ROOT, pad)).isDirectory()) return bestanden(pad);
    return /\.tsx?$/.test(naam) && !/\.test\.tsx?$/.test(naam) ? [pad] : [];
  });
}
const code = [...bestanden("components"), ...bestanden("app")];

// Eén vaste kop voor elk paneel naast het gesprek (8 nov 2026, melding van de gebruiker: drie rijen met twee
// uitlijningen). Rij 1: soort en titel, rechtsboven ↗ ⋯ ✕. Rij 2, alleen met iets erin: de status links en één
// hoofdactie rechts. Exporteren en verwijderen staan in het menu ⋯.
describe("de paneelkop", () => {
  const kop = bron("components/ui/PaneelKop.tsx");

  it("heeft geen vrij slot voor acties en wrapt nooit", () => {
    expect(kop).not.toMatch(/\bacties\??:/);
    expect(kop).not.toMatch(/flex-wrap/);
    for (const pad of code) expect(bron(pad), pad).not.toMatch(/<PaneelKop\b[^>]*\bacties=/s);
  });

  it("zet het kopgereedschap in een vaste volgorde: pagina, menu, sluiten", () => {
    const gereedschap = kop.slice(kop.indexOf("data-kop-gereedschap"));
    const plek = (s: string) => gereedschap.indexOf(s);
    expect(plek("data-naar-pagina")).toBeGreaterThan(0);
    expect(plek("<MeerMenu")).toBeGreaterThan(plek("data-naar-pagina"));
    expect(plek("<SluitKnop")).toBeGreaterThan(plek("<MeerMenu"));
    expect(kop).toMatch(/aria-label="Open volledige pagina"/);
  });

  it("raakvlakken van 44 px op een aanraakscherm", () => {
    expect(icoonKnopKlasse("sm")).toMatch(/coarse:h-11 coarse:w-11/);
    const sluit = kop.slice(kop.indexOf("export function SluitKnop"), kop.indexOf("export interface KopVulling"));
    expect(sluit).toMatch(/coarse:h-11 coarse:w-11/);
  });

  it("het rondleidingsanker staat alleen in de kop", () => {
    for (const pad of code) {
      if (pad.endsWith("PaneelKop.tsx")) continue;
      expect(bron(pad), pad).not.toMatch(/data-tour="artefact-acties"/);
    }
  });
});

describe("de inhoud van een paneel bouwt geen eigen kopregel", () => {
  it("werkgebied en begrip geven hun stand en menu aan de kop", () => {
    const wg = bron("components/werkplek/WerkgebiedArtefactPaneel.tsx");
    expect(wg).toMatch(/<PaneelKopVuller>/);
    expect(wg).not.toMatch(/<VerwijderKnop\b/);
    expect(wg).toMatch(/usePaneelKopVulling\(/);
    const compact = bron("components/werkgebieden/BegripInhoud.tsx");
    const start = compact.indexOf("export function BegripCompact");
    const eind = compact.indexOf("\nfunction ", start + 1);
    const begrip = compact.slice(start, eind > 0 ? eind : undefined);
    expect(begrip).toMatch(/usePaneelKopVulling\(/);
    expect(begrip).not.toMatch(/<BegripMenu\b|<MeerMenu\b/);
    // De stand staat alleen in de vulling van de kop, niet als eigen rij in de inhoud.
    expect(begrip.slice(begrip.indexOf("return ("))).not.toMatch(/<StatusLabel\b/);
  });

  it("de annotatie zet afronden in de kop met de vorm van een knop, en exporteren en verwijderen in het menu", () => {
    const a = bron("components/werkplek/ArtefactInhoud.tsx");
    const knop = a.slice(a.indexOf("function StatusKnop"));
    expect(knop).toMatch(/knopKlasse\("secondary", "xs"\)/);
    expect(a).not.toMatch(/<ExportKnop\b|<VerwijderKnop\b/);
    expect(a).toMatch(/<ExportRegels\b/);
    expect(a).toMatch(/<MenuVerwijder\b/);
    // De tab Graaf krijgt dezelfde kop, zodat hij bij een tabwissel niet springt.
    expect(bron("components/annotaties/NodeAnnotatiePaneel.tsx")).toMatch(/<AnnotatieKop\b/);
  });

  it("de export heeft één bron: ExportKnop gebruikt de regels", () => {
    const e = bron("components/werkplek/ExportKnop.tsx");
    const knop = e.slice(e.indexOf("export function ExportKnop"));
    expect(knop).toMatch(/<ExportRegels\b/);
    expect(knop).not.toMatch(/Kopieer als Markdown/);
  });
});
