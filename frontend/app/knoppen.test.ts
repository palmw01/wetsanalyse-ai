import { readFileSync, readdirSync, statSync } from "node:fs";
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

  // Eén manier van bewerken (4 nov 2026, naar het voorbeeld van Claude): ter plekke, met *Bewerken* bij het blok en
  // daaronder rechts Annuleren · Opslaan (`components/ui/Bewerkbaar`). Geen venster om tekst te bewerken.
  it("bewerken gebeurt ter plekke met dezelfde voet, nergens in een venster", () => {
    for (const f of ["werkgebieden/ProjectKop", "werkgebieden/Deelvragen", "werkgebieden/BegripPaneel", "werkgebieden/BegripKaart",
      "werkgebieden/KaartVoorstel", "werkplek/ReviewQueue", "werkplek/GesprekLijst", "werkplek/ChatKop",
      "admin/ProfileEditor", "admin/BerichtEditor"]) {
      expect(bron(`components/${f}.tsx`), f).toContain("BewerkVoet");
    }
    expect(bron("components/werkgebieden/ProjectKop.tsx")).not.toMatch(/<Dialog\b/);
    expect(bron("components/werkgebieden/ProjectKop.tsx")).not.toContain("GegevensDialoog");
    for (const f of ["werkgebieden/KaartVoorstel", "werkgebieden/BegripKaart"])
      expect(bron(`components/${f}.tsx`), f).not.toMatch(/>\s*(Terug|Wijzigingen weggooien)\s*</);
    // *Bewerken* van een deelvraag staat bij de rij, niet meer in het menu ⋯.
    expect(bron("components/werkgebieden/Deelvragen.tsx")).toContain("<BewerkKnop");
  });
});

// Het ene ⋯-menu (5 nov 2026, besluit gebruiker): bij een werkgebied, een deelvraag, een bron en een gesprek dezelfde
// knop (`MeerKnop`), hetzelfde paneel en dezelfde regels; verwijderen onderaan in het rood (`MenuVerwijder`).
describe("één menu ⋯", () => {
  const bestanden = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
    const pad = `${map}/${n}`;
    return statSync(join(ROOT, pad)).isDirectory() ? bestanden(pad) : pad.endsWith(".tsx") ? [pad] : [];
  });

  it("het icoon ⋯ staat alleen in MeerKnop", () => {
    const met = bestanden("components").filter((f) => /<Meer\s*\/>/.test(bron(f)));
    expect(met).toEqual(["components/ui/MeerMenu.tsx"]);
  });

  it("geen losse verwijderknop of eigen menuregels in een menu ⋯", () => {
    for (const f of ["werkgebieden/ProjectKop", "werkgebieden/Deelvragen", "werkgebieden/BronnenBijDeelvraag"]) {
      const s = bron(`components/${f}.tsx`);
      expect(s, f).toContain("<MeerMenu");
      expect(s, f).not.toMatch(/<VerwijderKnop|<Popover\b/);
    }
    for (const f of ["werkplek/ChatKop", "werkplek/GesprekLijst"]) expect(bron(`components/${f}.tsx`), f).toContain("<MeerKnop");
    expect(bron("components/werkplek/GesprekActies.tsx")).toContain("<MenuKnop");
  });
});
