import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { HANDELINGEN } from "@/lib/paneelBediening";

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
const TABEL = "lib/paneelBediening.ts";
const KNOP = "components/ui/Paneel.tsx";

// Eenduidig (besluit gebruiker 23 nov 2026): één knop per handeling van een paneel, met één label en één icoon uit één
// tabel (`HANDELINGEN`), getekend door één component (`PaneelKnop`) in de kop. Rood als een paneel een eigen knop, label
// of icoon voor zo'n handeling krijgt, of als er een tweede weg naar hetzelfde terugkomt.
describe("de bediening van een paneel is eenduidig", () => {
  it("de labels van de handelingen staan alleen in de tabel", () => {
    for (const { label } of Object.values(HANDELINGEN)) {
      if (label === "Sluiten") continue;    // ook het kruisje van een venster (`SluitKnop`), geen paneel
      for (const pad of code) expect(bron(pad), `${pad}: "${label}"`).not.toContain(`"${label}"`);
    }
  });

  it("de iconen van de handelingen staan alleen in de tabel", () => {
    for (const { icoon } of Object.values(HANDELINGEN))
      for (const pad of code) {
        if (icoon === HANDELINGEN.sluiten.icoon && /components\/ui\/(PaneelKop|Dialog)\.tsx$/.test(pad)) continue;
        expect(bron(pad), pad).not.toContain(icoon);
      }
  });

  it("alleen de kop en de strook tekenen de knoppen", () => {
    for (const pad of code) {
      if (pad === KNOP) continue;
      const gebruikt = /<PaneelKnop\b/.test(bron(pad));
      expect(gebruikt, pad).toBe(["components/ui/PaneelKop.tsx", "components/ui/Zijpaneel.tsx"].includes(pad));
    }
  });

  it("geen tweede weg: geen balk, geen paginaknop, geen ✕ op een tab, geen ✕ van een paneel buiten de tabel", () => {
    const verboden = [/data-zijpaneel-balk/, /Open volledige pagina/, /Sluit tab/, /data-tab-sluiten/, /data-paneel-vergroten/,
      /data-paneel-inklappen/, /ZijpaneelContext|PaneelTabsContext|PaneelGesprekContext/];
    for (const pad of code) for (const r of verboden) expect(bron(pad), `${pad}: ${r}`).not.toMatch(r);
  });

  it("een paneel geeft zijn kop geen sluitknop: sluiten komt uit de plek", () => {
    const kop = bron("components/ui/PaneelKop.tsx");
    const handtekening = kop.slice(kop.indexOf("export function PaneelKop("), kop.indexOf("}) {", kop.indexOf("export function PaneelKop(")));
    expect(handtekening).not.toMatch(/\bonSluit\b/);
    for (const pad of code) {
      expect(bron(pad), pad).not.toMatch(/<PaneelKop\b[^>]*\bonSluit=/s);
      expect(bron(pad), pad).not.toMatch(/<AnnotatieKop\b[^>]*\bonSluiten=/s);
    }
  });

  it("het kruisje van een venster staat alleen in vensters, niet in een paneel", () => {
    const met = code.filter((pad) => /<SluitKnop\b/.test(bron(pad)));
    expect(met.sort()).toEqual(["components/rondleiding/TourBubbel.tsx", "components/ui/Dialog.tsx",
      "components/werkplek/GesprekSidebar.tsx"]);
  });

  it("de tabel is de bron", () => {
    expect(bron(TABEL)).toMatch(/export const HANDELINGEN/);
    expect(bron(KNOP)).toMatch(/HANDELINGEN\[handeling\]/);
  });
});
