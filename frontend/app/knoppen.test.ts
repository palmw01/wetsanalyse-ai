import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { KNOP_XS, knopKlasse } from "@/components/ui/Button";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");

// Spoor I4 (besluit gebruiker 26 okt 2026): elke knop is een pil, behalve *Nieuw gesprek* in de sidebar.
describe("één bedieningsstijl", () => {
  it("elke variant en maat van Button is een pil", () => {
    for (const v of ["primary", "secondary", "ghost", "danger"] as const)
      for (const m of ["xs", "sm", "md"] as const) expect(knopKlasse(v, m).split(" ")).toContain("rounded-full");
    expect(KNOP_XS.split(" ")).toContain("rounded-full");
    expect(bron("components/ui/Button.tsx")).not.toMatch(/rounded-button/);
  });

  it("Nieuw gesprek in de sidebar blijft letterlijk zoals hij was", () => {
    expect(bron("components/werkplek/GesprekSidebar.tsx")).toContain(
      'className="flex min-h-[44px] w-full items-center gap-2 rounded-kaart border border-line bg-paper px-3 py-2.5 text-sm font-medium text-lint shadow-zacht transition-colors hover:bg-white hover:shadow-kaart focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint"');
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
