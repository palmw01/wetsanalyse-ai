import { describe, expect, it } from "vitest";
import { detailFactor, effectieveZoom, kiesLabels, labelPrioriteit, magLabel, type LabelKandidaat } from "./labels";

const kand = (id: string, links: number, boven: number, prioriteit: number, extra: Partial<LabelKandidaat> = {}): LabelKandidaat =>
  ({ id, links, boven, breedte: 100, hoogte: 14, prioriteit, ...extra });
const beeld = { breedte: 800, hoogte: 600 };
const overlappen = (a: LabelKandidaat, b: LabelKandidaat) =>
  a.links < b.links + b.breedte && b.links < a.links + a.breedte && a.boven < b.boven + b.hoogte && b.boven < a.boven + a.hoogte;

describe("labels", () => {
  it("laat nooit twee gekozen labels overlappen", () => {
    const kandidaten = Array.from({ length: 400 }, (_, i) => kand(`k${i}`, (i * 37) % 760, (i * 53) % 580, i % 7));
    const uit = kandidaten.filter((k) => kiesLabels(kandidaten, beeld).has(k.id));
    expect(uit.length).toBeGreaterThan(10);
    for (const a of uit) for (const b of uit) if (a !== b) expect(overlappen(a, b)).toBe(false);
  });

  it("de hoogste prioriteit wint een botsing; bij gelijke prioriteit het label dat er al stond", () => {
    const a = kand("a", 10, 10, 1), b = kand("b", 50, 12, 2);
    expect([...kiesLabels([a, b], beeld)]).toEqual(["b"]);
    const c = kand("c", 10, 10, 2);
    expect([...kiesLabels([c, b], beeld)]).toEqual(["b"]);
    expect([...kiesLabels([c, b], { ...beeld, vorige: new Set(["c"]) })]).toEqual(["c"]);
  });

  it("de keuze staat er altijd, ook als ze botst; buiten beeld telt niet", () => {
    const a = kand("a", 10, 10, 9000), keuze = kand("keuze", 20, 10, 1, { altijd: true });
    expect(kiesLabels([a, keuze], beeld)).toEqual(new Set(["keuze"]));
    expect(kiesLabels([kand("weg", 900, 10, 1)], beeld).size).toBe(0);
    expect(kiesLabels([kand("rand", 750, 10, 1)], beeld).size).toBe(0);
    expect(kiesLabels([kand("rand", 750, 10, 1, { altijd: true })], beeld).size).toBe(1);
  });

  it("de bediening boven de kaart telt als bezet; de keuze gaat er wel overheen", () => {
    const zoek = { links: 0, boven: 0, breedte: 300, hoogte: 40 };
    expect(kiesLabels([kand("onder", 10, 10, 9)], { ...beeld, bezet: [zoek] }).size).toBe(0);
    expect(kiesLabels([kand("vrij", 10, 100, 9)], { ...beeld, bezet: [zoek] }).size).toBe(1);
    expect(kiesLabels([kand("keuze", 10, 10, 9, { altijd: true })], { ...beeld, bezet: [zoek] }).size).toBe(1);
  });

  it("meer detail naarmate je inzoomt, gewogen naar de grootte van de kaart", () => {
    const kennisgraaf = effectieveZoom(1, 6500), artikel = effectieveZoom(1, 60);
    expect(magLabel("regeling", kennisgraaf)).toBe(true);
    expect(magLabel("artikel", kennisgraaf)).toBe(false);
    expect(magLabel("artikel", effectieveZoom(0.3, 6500))).toBe(true);
    expect(magLabel("markering", effectieveZoom(0.3, 6500))).toBe(false);
    expect(magLabel("markering", effectieveZoom(0.08, 6500))).toBe(true);
    // Eén artikel staat bij zoom 1 al op leesafstand.
    expect(magLabel("markering", artikel)).toBe(true);
    expect(detailFactor("onderdeel", kennisgraaf)).toBeLessThan(1);
    expect(detailFactor("onderdeel", artikel)).toBe(1);
    expect(detailFactor("artikel", kennisgraaf)).toBe(1);
  });

  it("prioriteit: niveau, dan vast label, dan soort", () => {
    expect(labelPrioriteit(2, false, "markering")).toBeGreaterThan(labelPrioriteit(1, true, "regeling"));
    expect(labelPrioriteit(1, true, "lid")).toBeGreaterThan(labelPrioriteit(1, false, "regeling"));
    expect(labelPrioriteit(1, false, "artikel")).toBeGreaterThan(labelPrioriteit(1, false, "lid"));
  });
});
