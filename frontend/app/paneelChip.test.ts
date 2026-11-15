import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { chipSub } from "@/components/ui/PaneelChip";

/** Eén kaartje naar een paneel (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md`
 *  §1): de bepaling onder een antwoord, de annotatie, een ander artefact, het overzicht en een kandidaat stonden elk met
 *  eigen klassen in het gesprek, met drie werkwoorden voor dezelfde handeling. Alles gaat nu door `PaneelChip`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app"), ...alle("lib")];
const HIER = "components/ui/PaneelChip.tsx";

describe("een kaartje naar een paneel is PaneelChip", () => {
  it("de icoontegel en de chevron van de chip staan alleen in PaneelChip", () => {
    const fout = bestanden.filter((p) => p !== HIER).filter((p) => {
      const s = readFileSync(join(ROOT, p), "utf8");
      return s.includes("h-9 w-9 shrink-0 items-center justify-center rounded-lg") || s.includes("m9 18 6-6-6-6");
    });
    expect(fout).toEqual([]);
  });

  it("geen knop in het gesprek met de klassen van de chip", () => {
    const fout = bestanden.filter((p) => /^components\/(werkplek|antwoord)\//.test(p)).filter((p) =>
      /<button[^>]*className="[^"]*rounded-kaart border border-line bg-surface/.test(readFileSync(join(ROOT, p), "utf8")));
    expect(fout).toEqual([]);
  });

  it("de ondertitel is soort · handeling, met één werkwoord per handeling", () => {
    expect(chipSub("Annotatie", "beoordelen")).toBe("Annotatie · beoordelen");
    expect(chipSub(undefined, "bekijken")).toBe("bekijken");
    const gesprek = readFileSync(join(ROOT, "components/werkplek/ThreadRij.tsx"), "utf8");
    expect(gesprek).not.toContain("review openen");
  });
});
