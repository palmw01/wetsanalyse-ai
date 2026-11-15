import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Eén lege toestand (generieke componenten, 15 nov 2026, `docs/architectuur/plan-generieke-componenten.md` §4): "Nog
 *  geen …" stond in een kader, als losse regel in twee maten en drie grijzen, en cursief op de begripskaart. In
 *  `/annotaties` stonden beide vormen direct na elkaar. Nu is een lege lijst `Leeg` en een leeg veld `LeegWaarde`. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : pad.endsWith(".tsx") ? [pad] : [];
});
const bestanden = [...alle("components"), ...alle("app")].filter((p) => p !== "components/ui/Leeg.tsx");
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("een lege toestand is Leeg", () => {
  it("geen eigen grijze regel die met 'Nog geen' of 'Geen' begint", () => {
    const eigen = /<(p|span|li|div)\b[^>]*className="[^"]*\btext-(muted|faint)\b[^"]*"[^>]*>\s*(Nog geen|Geen )/;
    // "Nog geen account?" op het inlogscherm is een vraag, geen lege lijst.
    expect(bestanden.filter((p) => p !== "components/auth/LoginClient.tsx" && eigen.test(lees(p)))).toEqual([]);
  });

  it("het gestippelde kader van een lege lijst staat alleen in Leeg", () => {
    expect(bestanden.filter((p) => /border-dashed border-line px-/.test(lees(p)))).toEqual([]);
  });

  it("de lege stand van Groep en ObjectRijen is Leeg", () => {
    const pagina = lees("components/ui/Pagina.tsx");
    expect(pagina).not.toContain('<p className="text-sm text-muted">{leeg}</p>');
    expect(pagina.match(/<Leeg>\{leeg\}<\/Leeg>/g)?.length).toBe(2);
  });
});
