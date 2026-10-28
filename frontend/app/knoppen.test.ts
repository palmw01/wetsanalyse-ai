import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { KNOP_XS, knopKlasse } from "@/components/ui/Button";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

// Spoor K (besluit gebruiker 27 okt 2026, vervangt I4 voor de hoofdknoppen): een hoofdknop heeft de vorm van
// *Nieuw gesprek* – een afgeronde rechthoek met een zachte schaduw die bij hover dieper wordt; een rijactie (xs)
// blijft een kleine pil.
describe("één bedieningsstijl", () => {
  it("een hoofdknop is een afgeronde rechthoek, een rijactie een pil", () => {
    for (const v of ["primary", "secondary", "ghost", "danger"] as const) {
      for (const [m, hoek] of [["sm", "rounded-knop"], ["md", "rounded-kaart"]] as const) {
        const k = knopKlasse(v, m).split(" ");
        expect(k, `${v}/${m}`).toContain(hoek);
        expect(k, `${v}/${m}`).not.toContain("rounded-full");
      }
      expect(knopKlasse(v, "xs").split(" ")).toContain("rounded-full");
    }
    expect(KNOP_XS.split(" ")).toContain("rounded-full");
    // Een vlak (primair, tweede keuze) heeft de schaduw van Nieuw gesprek, ook bij hover.
    for (const v of ["primary", "secondary"] as const)
      expect(knopKlasse(v, "md").split(" ")).toEqual(expect.arrayContaining(["shadow-zacht", "hover:shadow-kaart"]));
    expect(bron("components/ui/Button.tsx")).not.toMatch(/rounded-button/);
  });

  it("Nieuw gesprek in de sidebar is de tweede keuze van Button, geen eigen stijl meer", () => {
    expect(bron("components/werkplek/GesprekSidebar.tsx")).toContain('knopKlasse("secondary", "md")');
  });

  it("geen handgemaakte primaire knop naast knopKlasse", () => {
    for (const f of ["werkgebieden/ProjectKop", "werkgebieden/ProjectTabs", "werkplek/WerkgebiedArtefactPaneel",
      "werkplek/VraagLexKnop", "werkplek/KeuzeKaart", "rondleiding/Rondleiding", "rondleiding/TourBubbel", "graaf/GraafInspector"]) {
      const s = bron(`components/${f}.tsx`);
      expect(s, f).not.toMatch(/rounded-full (bg-accent|bg-lint) px-/);
    }
  });

  it("de werkgebiedcomponenten hebben geen eigen knopstijl meer naast KNOP_XS", () => {
    for (const f of ["BegripKaart", "BegripPassages", "BegripRelaties", "BronKandidaten", "Herbeoordeling", "SamenhangTab"]) {
      const s = bron(`components/werkgebieden/${f}.tsx`);
      expect(s, f).not.toMatch(/const KNOP\w* =\s*\n?\s*"/);
    }
  });

  it("de verwijderstap in de gesprekkenlijst staat altijd onder elkaar", () => {
    const s = bron("components/werkplek/GesprekActies.tsx");
    const stap = s.slice(s.indexOf("data-gesprek-verwijderen"), s.indexOf("Annuleren"));
    expect(stap).not.toMatch(/sm:flex-row/);
  });
});
