import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Het bronvenster, PR 4 (kernprincipe van de gebruiker: één ingang, geen deeloplossingen naast elkaar): onder een antwoord
// staan de chips (per bepaling, en de samenhang); een bepaling uit een lijst opent als tab naast het gesprek in plaats van
// een eigen uitklap met de wettekst; de citatiekaart heeft één *Openen*.
const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

describe("één ingang naar een bron", () => {
  it("onder een antwoord: chips, geen losse knop naar de graaf", () => {
    const rij = bron("components/werkplek/ThreadRij.tsx");
    expect(rij).toMatch(/<SamenhangChip /);
    expect(rij).not.toMatch(/<GraafIcoon \/>\{tekst\}/);
    expect(bron("components/werkplek/Markdown.tsx")).not.toMatch(/onOpenSamenhang/);
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
      expect(s, pad).toMatch(/ContextPaneelContext/);
    }
  });

  it("de bepaling in het paneel is het bronvenster", () => {
    const paneel = bron("components/werkplek/ContextPaneel.tsx");
    expect(paneel).toMatch(/<BronVenster /);
    expect(paneel).not.toMatch(/function BronInhoud/);
  });
});
