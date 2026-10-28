import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const COMPONENTS = join(__dirname, "..");

function bestanden(pad: string): string[] {
  const uit: string[] = [];
  for (const naam of readdirSync(pad)) {
    const vol = join(pad, naam);
    if (statSync(vol).isDirectory()) {
      uit.push(...bestanden(vol));
    } else if (naam.endsWith(".tsx")) {
      uit.push(vol);
    }
  }
  return uit;
}

/** Elk scherm dat `AppSidebar` gebruikt, met de bron erbij. */
function schermenMetSidebar(): { pad: string; bron: string }[] {
  return bestanden(COMPONENTS)
    .map((pad) => ({ pad, bron: readFileSync(pad, "utf8") }))
    .filter(({ pad, bron }) => bron.includes("<AppSidebar") && !pad.endsWith("AppSidebar.tsx"));
}

describe("AppSidebar is op elk scherm bereikbaar", () => {
  it("vindt de schermen die hem gebruiken", () => {
    // Vangnet: verandert de opzet, dan faalt deze test hier in plaats van stilzwijgend niets te toetsen.
    expect(schermenMetSidebar().length).toBeGreaterThanOrEqual(3);
  });

  it.each(schermenMetSidebar().map(({ pad, bron }) => [pad.split("/components/")[1], bron]))(
    "%s opent de drawer op smalle schermen",
    (_naam, bron) => {
      // `AppSidebar` is onder `lg` een `hidden`-kolom en toont zijn drawer alléén als het scherm
      // `drawerOpen` + `onDrawerSluit` doorgeeft. `/annotaties` deed dat
      // niet: op een half scherm was er geen sidebar én geen enkele manier om er een te openen —
      // geen gesprekken, geen account, geen uitloggen. Alleen de propnaam toetsen is genoeg om die
      // val opnieuw te herkennen.
      expect(bron).toContain("drawerOpen");
      expect(bron).toContain("onDrawerSluit");
      // En er moet iets zijn dat hem opent.
      expect(bron).toContain("onOpenSidebar");
    },
  );
});

describe("de navigatie in de zijbalk", () => {
  it("staat in de volgorde waarin je werkt: Werkgebieden, Annotaties, Begrippen", () => {
    // Besluit gebruiker 21 okt 2026; de rondleiding (`lib/rondleiding.ts`, stap "sidebar") noemt dezelfde volgorde.
    const bron = readFileSync(join(__dirname, "GesprekSidebar.tsx"), "utf8");
    const plek = (href: string) => bron.indexOf(`href="${href}"`);
    expect(plek("/werkgebieden")).toBeGreaterThan(-1);
    expect(plek("/werkgebieden")).toBeLessThan(plek("/annotaties"));
    expect(plek("/annotaties")).toBeLessThan(plek("/begrippen"));
    const rondleiding = readFileSync(join(__dirname, "..", "..", "lib", "rondleiding.ts"), "utf8");
    const tekst = (w: string) => rondleiding.indexOf(`${w} (`);
    expect(tekst("Werkgebieden")).toBeLessThan(tekst("Annotaties"));
  });
});
