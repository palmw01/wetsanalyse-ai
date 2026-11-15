import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén kop voor een venster (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §7):
 *  zeven vensters bouwden hun kop zelf, in drie vormen, met drie verschillende kruisjes, en vier hadden er geen, zodat je
 *  op een telefoon naast het venster moest tikken om het te sluiten. Nu geeft een venster zijn `kop` aan `Dialog`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app")];
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("een venster heeft één kop", () => {
  it("een bestand met een Dialog bouwt geen eigen titel", () => {
    const fout = bestanden.filter((p) => p !== "components/ui/Dialog.tsx")
      .filter((p) => lees(p).includes("<Dialog ") && /<h2\b/.test(lees(p)));
    expect(fout).toEqual([]);
  });

  it("het kruisje staat alleen in SluitKnop", () => {
    // Het kruisje op een tab (`Tabs`) is kleiner en hoort bij de tab, niet bij een paneel of venster.
    const fout = bestanden.filter((p) => p !== "components/ui/PaneelKop.tsx" && p !== "components/ui/Tabs.tsx")
      .filter((p) => lees(p).includes("M5 5l10 10M15 5L5 15"));
    expect(fout).toEqual([]);
  });

  it("de kop van een venster is DialoogKop, met SluitKnop", () => {
    const s = lees("components/ui/Dialog.tsx");
    expect(s).toContain("{kop && <DialoogKop {...kop} onSluit={onSluit} />}");
    expect(s).toMatch(/<SluitKnop onSluit=\{onSluit\}/);
  });
});
