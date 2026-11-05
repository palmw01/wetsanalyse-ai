import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { KNOP_XS, icoonKnopKlasse, knopKlasse } from "@/components/ui/Button";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

// Besluit gebruiker 5 nov 2026 (het stijlblad, vervangt spoor K/I4 voor de rijactie): **een pil is een label, een
// afgeronde rechthoek is een knop.** Elke maat knop heeft de vorm van *Nieuw gesprek*; een rijactie (xs) is een
// kleine rechthoek, geen pil meer.
describe("één bedieningsstijl", () => {
  it("een knop is in elke maat een afgeronde rechthoek, nooit een pil", () => {
    for (const v of ["primary", "secondary", "ghost", "danger"] as const) {
      for (const [m, hoek] of [["xs", "rounded-knop-xs"], ["sm", "rounded-knop"], ["md", "rounded-kaart"]] as const) {
        const k = knopKlasse(v, m).split(" ");
        expect(k, `${v}/${m}`).toContain(hoek);
        expect(k, `${v}/${m}`).not.toContain("rounded-full");
      }
    }
    expect(KNOP_XS.split(" ")).toContain("rounded-knop-xs");
    expect(KNOP_XS).not.toMatch(/rounded-full/);
    for (const m of ["xs", "sm"] as const) expect(icoonKnopKlasse(m)).not.toMatch(/rounded-full/);
    // Een vlak (primair, tweede keuze) heeft de schaduw van Nieuw gesprek, ook bij hover.
    for (const v of ["primary", "secondary"] as const)
      expect(knopKlasse(v, "md").split(" ")).toEqual(expect.arrayContaining(["shadow-zacht", "hover:shadow-kaart"]));
    expect(bron("components/ui/Button.tsx")).not.toMatch(/rounded-button/);
  });

  it("een label is de pil van StatusLabel, en een span", () => {
    const lijst = bron("components/ui/Lijst.tsx");
    const label = lijst.slice(lijst.indexOf("export function StatusLabel"));
    expect(label).toMatch(/<span[^>]*\n?[^>]*rounded-full/);
    expect(label.slice(0, label.indexOf("\n}\n"))).not.toMatch(/<button|<Link/);
  });

  it("geen zelfgemaakt label: een pil met rand en tekst is altijd StatusLabel of KlasseLabel", () => {
    // Een kleurstip (`h-2 w-2 rounded-full`) heeft geen padding en valt erbuiten.
    const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
      const pad = `${map}/${n}`;
      return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
    });
    const zelfgemaakt = [...alle("components"), ...alle("app")]
      .filter((f) => f !== "components/ui/Lijst.tsx")
      .flatMap((f) => [...bron(f).matchAll(/<span\b[^>]*className=[^>]*>/g)]
        .map((m) => m[0])
        .filter((tag) => /rounded-full/.test(tag) && /\bborder\b/.test(tag) && /\bpx-/.test(tag))
        .map((tag) => `${f}: ${tag.slice(0, 80)}`));
    expect(zelfgemaakt).toEqual([]);
  });

  it("een knop is nergens in de app een pil; alleen de verstuurknop is rond", () => {
    // Een klikbaar element herken je aan `focus-ring` (elke knop en link heeft hem). Rond mag alleen de verstuurknop
    // van het invoerveld: de hoofdactie van het gesprek, zoals bij Claude. Een teller, voortgangsbalk of avatar heeft
    // geen focus-ring en valt erbuiten.
    const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
      const pad = `${map}/${n}`;
      return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
    });
    const rond = [...alle("components"), ...alle("app")].flatMap((f) =>
      bron(f).split("\n").map((regel, i) => ({ f, i: i + 1, regel }))
        .filter(({ regel }) => /focus-ring/.test(regel) && /rounded-full/.test(regel)))
      .map(({ f, i }) => `${f}:${i}`);
    expect(rond).toHaveLength(1);
    expect(rond[0]).toMatch(/^components\/werkplek\/WerkplekClient\.tsx:/);
    expect(bron("components/werkplek/WerkplekClient.tsx")).toMatch(/aria-label=\{bezig \? \(stopt[^\n]*"Versturen"/);
  });

  it("de stijlgids staat in de instellingen, alleen voor beheerders", () => {
    expect(bron("lib/instellingen.ts")).toMatch(/key: "stijl", pad: "beheer\/stijl"[^}]*admin: true/);
    expect(bron("components/instellingen/InstellingenInhoud.tsx")).toContain("<StijlPanel />");
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
    // De deelvragen hebben één *Bewerken* voor het hele blok, net als de analyseopdracht (5 nov 2026); geen invoerveld
    // in rust en geen bewerkknop per rij.
    const dv = bron("components/werkgebieden/Deelvragen.tsx");
    expect(dv.match(/<BewerkKnop/g)).toHaveLength(1);
    expect(dv).toContain('wat="Deelvragen"');
    expect(dv).not.toMatch(/id="nieuwe-deelvraag"/);
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
