import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén melding (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §3): boven het
 *  gesprek stonden stroken met de hand gebouwd, zonder icoon en met `role="status"` bij een fout, naast `Melding`. De
 *  knop in een melding stond er zes keer in, met vier klassensets. Nu is een strook `Melding strook` en een handeling in
 *  een melding `MeldingActie` (of een link met `MELDING_ACTIE`). */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app")];
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

/** De binnenkant van elk `<Melding …>…</Melding>` (en de melding op het graafcanvas). */
function meldingen(s: string): string[] {
  return [...s.matchAll(/<(Melding|CanvasMelding)\b[\s\S]*?<\/\1>/g)].map((m) => m[0]);
}

describe("een melding is Melding", () => {
  it("het getinte vlak van een melding staat alleen in Melding", () => {
    // MeerMenu tint de tweede klik op Verwijderen; de teststrook is de vaste band van de testomgeving, geen melding.
    const toegestaan = new Set(["components/ui/Melding.tsx", "components/ui/MeerMenu.tsx", "components/werkplek/Teststrook.tsx"]);
    const fout = bestanden.filter((p) => !toegestaan.has(p))
      .filter((p) => /(?<![\w:-])bg-(fout|waarschuwing|succes|info)\/10\b/.test(lees(p)));
    expect(fout).toEqual([]);
  });

  it("een handeling in een melding is MeldingActie, geen eigen knop", () => {
    const fout = bestanden.filter((p) => p !== "components/ui/Melding.tsx")
      .filter((p) => meldingen(lees(p)).some((m) => /<button\b/.test(m)));
    expect(fout).toEqual([]);
  });

  it("een link in een melding heeft de stijl van MeldingActie", () => {
    const fout = bestanden.filter((p) => meldingen(lees(p))
      .some((m) => /<(Link|InstellingenLink)\b[^>]*className="[^"]*underline/.test(m)));
    expect(fout).toEqual([]);
  });
});
