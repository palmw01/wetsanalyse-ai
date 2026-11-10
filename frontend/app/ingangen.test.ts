import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Het bronvenster, PR 4, en ontdubbelen PR 3 (kernprincipe van de gebruiker: één ingang, geen deeloplossingen naast
// elkaar): onder een antwoord staat per bepaling één kaart, en de graaf is de tab Graaf van het venster dat die kaart
// opent – geen tweede kaart. Een bepaling uit een lijst opent als tab naast het gesprek in plaats van een eigen uitklap met
// de wettekst; de citatiekaart heeft één *Openen*. Elke ingang gaat via `useOpenBron`.
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

describe("één ingang naar een bron", () => {
  it("onder een antwoord: per bepaling één kaart, geen kaart of knop voor de graaf", () => {
    const rij = bron("components/werkplek/ThreadRij.tsx");
    expect(rij).toMatch(/<BepalingChips bepalingen=\{kaarten\.bepalingen\}/);
    expect(rij).toMatch(/zonderKaarten\(/);
    for (const pad of ["components/werkplek/ThreadRij.tsx", "components/werkplek/WerkplekClient.tsx", "components/antwoord/BepalingChip.tsx"]) {
      expect(bron(pad), pad).not.toMatch(/SamenhangChip|openSamenhang|data-samenhang-chip/);
    }
    expect(rij).not.toMatch(/<GraafIcoon \/>\{tekst\}/);
    expect(bron("components/werkplek/Markdown.tsx")).not.toMatch(/onOpenSamenhang/);
  });

  it("elke ingang opent via useOpenBron; alleen de werkplek kent de context zelf", () => {
    const lezers = CODE.filter((p) => /useContext\(ContextPaneelContext\)/.test(bron(p)));
    expect(lezers).toEqual([join("components", "werkplek", "ContextPaneel.tsx")]);
  });

  it("de citatiekaart opent de bepaling; de graaf staat in de tab", () => {
    const kaart = bron("components/werkplek/CitatieChip.tsx");
    expect(kaart).not.toMatch(/Bekijk in de graaf/);
    expect(kaart).toMatch(/>\s*Openen<\/button>/);
  });

  it("geen uitklap met de wettekst in een lijst naast het gesprek", () => {
    for (const pad of ["components/werkgebieden/BronnenBijDeelvraag.tsx", "components/werkplek/OverzichtPaneel.tsx"]) {
      const s = bron(pad);
      expect(s, pad).not.toMatch(/BepalingTekst|WettekstBlok/);
      expect(s, pad).toMatch(/useOpenBron\(\)/);
    }
  });

  it("de bepaling in het paneel is het bronvenster", () => {
    const paneel = bron("components/werkplek/ContextPaneel.tsx");
    expect(paneel).toMatch(/<BronVenster /);
    expect(paneel).not.toMatch(/function BronInhoud/);
  });
});
