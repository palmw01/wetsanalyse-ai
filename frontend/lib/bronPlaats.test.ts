import { describe, expect, it } from "vitest";

import { bladerenVan, bouwBoom, omvangZin, regelingUitLabel, rijenPerRegeling, type Plaats } from "./bronPlaats";

const IW = "urn:bwb:BWBR0004770";
const plaats = (iri: string, pad: [string, string][], volgorde: number, bwb = "BWBR0004770", titel = "Invorderingswet 1990"): Plaats => ({
  bron_iri: iri, regeling: { bwb_id: bwb, citeertitel: titel }, volgorde,
  pad: pad.map(([type, label], i) => ({ iri: `${iri}#${i}`, type, nummer: "", label })),
});

describe("bouwBoom", () => {
  it("regeling › hoofdstuk › artikel › lid, in de volgorde van de wet", () => {
    const iris = [`${IW}:artikel:28:lid:2`, `${IW}:artikel:9:lid:1`, `${IW}:artikel:9:lid:2`];
    const plaatsen = new Map([
      [iris[0], { ...plaats(iris[0], [["Hoofdstuk", "Hoofdstuk VI"], ["Artikel", "Artikel 28"], ["Lid", "Lid 2"]], 50) }],
      [iris[1], { ...plaats(iris[1], [["Hoofdstuk", "Hoofdstuk II"], ["Artikel", "Artikel 9"], ["Lid", "Lid 1"]], 10) }],
      [iris[2], { ...plaats(iris[2], [["Hoofdstuk", "Hoofdstuk II"], ["Artikel", "Artikel 9"], ["Lid", "Lid 2"]], 11) }],
    ]);
    // Zelfde artikel 9 voor beide leden: dezelfde sleutel in het pad.
    plaatsen.get(iris[2])!.pad[0].iri = plaatsen.get(iris[1])!.pad[0].iri;
    plaatsen.get(iris[2])!.pad[1].iri = plaatsen.get(iris[1])!.pad[1].iri;
    const boom = bouwBoom(iris, { iri: (x) => x, naam: (x) => x, plaatsen });
    expect(boom.map((r) => r.label)).toEqual(["Invorderingswet 1990"]);
    expect(boom[0].kinderen.map((h) => h.label)).toEqual(["Hoofdstuk II", "Hoofdstuk VI"]);
    const a9 = boom[0].kinderen[0].kinderen[0];
    expect([a9.soort, a9.label, a9.bladeren.map((b) => b.label)]).toEqual(["artikel", "Artikel 9", ["Lid 1", "Lid 2"]]);
    expect(omvangZin(boom)).toBe("3 bepalingen");
  });

  it("zonder plek: uit de IRI, met de regelingnaam uit het label", () => {
    const items = [
      { iri: `${IW}:artikel:9:lid:1`, label: "Artikel 9, lid 1 – Invorderingswet 1990" },
      { iri: "urn:bwb:BWBR0002320:artikel:30f:lid:2", label: "Artikel 30f, lid 2 – Algemene wet inzake rijksbelastingen" },
      { iri: `${IW}:artikel:9`, label: "Artikel 9 – Invorderingswet 1990" },
    ];
    const boom = bouwBoom(items, { iri: (x) => x.iri, naam: (x) => x.label, regelingNaam: (x) => regelingUitLabel(x.label) });
    expect(boom.map((r) => r.label).sort()).toEqual(["Algemene wet inzake rijksbelastingen", "Invorderingswet 1990"]);
    const iw = boom.find((r) => r.label === "Invorderingswet 1990")!;
    expect(iw.kinderen[0].label).toBe("Artikel 9");
    expect(iw.kinderen[0].bladeren.map((b) => b.label).sort()).toEqual(["Hele bepaling", "Lid 1"]);
    expect(omvangZin(boom)).toBe("3 bepalingen in 2 regelingen");
    // Plat per regeling (spoor K): één rij per bepaling, met haar plek, in de volgorde van de wet.
    const rijen = rijenPerRegeling(boom).find((r) => r.regeling === "Invorderingswet 1990")!.rijen;
    expect(rijen.map((r) => r.plek)).toEqual(["Artikel 9", "Artikel 9 · Lid 1"]);
  });

  it("een divisie van een beleidsregel staat op de plek van het artikel; onbekend valt onder de regeling", () => {
    const div = "urn:bwb:BWBR0024096:id:x";
    const plaatsen = new Map([[div, plaats(div, [["Divisie", "Artikel 26"], ["Divisie", "26.3"]], 3, "BWBR0024096", "Leidraad Invordering 2008")]]);
    const boom = bouwBoom([div, "urn:bwb:BWBR0024096:id:y"], { iri: (x) => x, naam: () => "divisie 9.1", plaatsen });
    expect(boom[0].label).toBe("Leidraad Invordering 2008");
    expect(boom[0].kinderen[0].label).toBe("Artikel 26");
    expect(boom[0].kinderen[0].kinderen[0].label).toBe("26.3");
    expect(boom[0].bladeren.map((b) => b.label)).toEqual(["divisie 9.1"]);
    expect(bladerenVan(boom[0])).toHaveLength(2);
  });
});
