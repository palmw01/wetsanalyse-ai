import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { gesprekHref, metVanuit, vanuitGesprek, zonderVanuit } from "@/lib/terugNaarGesprek";

const ROOT = join(__dirname, "..");
const bron = (pad: string) => readFileSync(join(ROOT, pad), "utf8");
const params = (q: string) => new URLSearchParams(q);

// Melding gebruiker 23 nov 2026: na *Open volledige pagina* in het zijpaneel was het paneel weg en was er geen weg
// terug naar gesprek plus paneel. Eén patroon voor elk paneel: de kop neemt het gesprek mee, één strook brengt je terug.
describe("de weg terug naar het gesprek", () => {
  it("zet het gesprek op de link naar de pagina en laat de rest letterlijk staan", () => {
    expect(metVanuit("/werkgebieden/wg1/bronnen", "4c31088e")).toBe("/werkgebieden/wg1/bronnen?vanuit=4c31088e");
    const lid = "/bronnen?bron_iri=urn%3Abwb%3AX%2FY&werkgebied=wg1";
    expect(metVanuit(lid, "abc")).toBe(`${lid}&vanuit=abc`);
    expect(metVanuit("/annotaties/node?bron_iri=x#e1", "abc")).toBe("/annotaties/node?bron_iri=x&vanuit=abc#e1");
    // Een tweede keer vervangt in plaats van te stapelen.
    expect(metVanuit(metVanuit("/p?a=1", "een"), "twee")).toBe("/p?a=1&vanuit=twee");
  });

  it("laat de link ongemoeid zonder gesprek of met een vreemd id", () => {
    expect(metVanuit("/p", null)).toBe("/p");
    expect(metVanuit("/p", "")).toBe("/p");
    expect(metVanuit("/p", "a&b=c")).toBe("/p");
    expect(metVanuit("/p", "../x")).toBe("/p");
  });

  it("haalt vanuit weer weg", () => {
    for (const href of ["/p", "/p?a=1", "/p?a=1#h", "/bronnen?bron_iri=x&werkgebied=wg1"])
      expect(zonderVanuit(metVanuit(href, "abc"))).toBe(href);
  });

  it("leest het gesprek alleen buiten de werkplek, en alleen een geldig id", () => {
    expect(vanuitGesprek("/annotaties/node", params("bron_iri=x&vanuit=4c31"))).toBe("4c31");
    expect(vanuitGesprek("/workbench", params("vanuit=4c31"))).toBeNull();
    expect(vanuitGesprek("/annotaties/node", params("bron_iri=x"))).toBeNull();
    expect(vanuitGesprek("/annotaties/node", params("vanuit=%2F%2Fergens"))).toBeNull();
    expect(vanuitGesprek(null, null)).toBeNull();
  });

  it("gaat terug naar dat gesprek in de werkplek", () => {
    expect(gesprekHref("4c31")).toBe("/workbench?gesprek=4c31");
  });

  it("is één patroon: *Openen als pagina* in de paneelkop neemt het gesprek mee, de root-layout toont de strook op elke pagina", () => {
    const kop = bron("components/ui/PaneelKop.tsx");
    expect(kop).toMatch(/<MenuLink href=\{metVanuit\(pagina, gesprek\)\}/);
    expect(kop).toMatch(/gesprekId: gesprek \} = paneel/);
    expect(bron("components/werkplek/WerkplekClient.tsx")).toMatch(/const paneelGesprek = demo \? null : gesprekId;/);
    expect(bron("app/layout.tsx")).toMatch(/<TerugNaarGesprek \/>/);
  });
});
