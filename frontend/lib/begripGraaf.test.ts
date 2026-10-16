import { describe, expect, it } from "vitest";
import { begripBron, begripIdVan, conformZin, isBegripSamenhang, isConformiteit, veldVanPad, type BegripSamenhang } from "./begripGraaf";
import { bouwModel } from "./graaf/model";
import type { BegripRelatie } from "./types";

const rel = (o: Partial<BegripRelatie>): BegripRelatie => ({
  id: "r", van_begrip: "a", naar_begrip: "b", van_naam: "", naar_naam: "", type: "inclusie", herkomst: "analist",
  beoordeling: "akkoord", toelichting: "", bewijs: {}, ...o,
});

const S: BegripSamenhang = {
  begrippen: [
    { id: "a", iri: "urn:wa:begrip:a", naam: "aanslag", status: "geaccordeerd", definitie: "Een beschikking." },
    { id: "b", iri: "urn:wa:begrip:b", naam: "navorderingsaanslag", status: "concept", definitie: "" },
  ],
  koppelingen: [
    { begrip_id: "a", element_id: "e1", rol: "duiding", beoordeling: "akkoord", actualiteit: "actueel" },
    { begrip_id: "b", element_id: "e2", rol: "duiding", beoordeling: "afgewezen", actualiteit: "actueel" },
  ],
  relaties: [rel({ id: "r1", type: "hierarchie" })],
  voorstellen: [rel({ id: "R2", type: "kwalificatie", beoordeling: "voorgesteld", herkomst: "lex", van_begrip: "b", naar_begrip: "a" })],
};

describe("begripBron", () => {
  it("maakt begripsknopen met status en definitie, en lijnen met zinnen", () => {
    const bron = begripBron(S);
    expect(bron.knopen.map((k) => [k.id, k.soort, k.status, k.tekst])).toEqual([
      ["begrip:a", "begrip", "geaccordeerd", "Een beschikking."], ["begrip:b", "begrip", "concept", ""]]);
    // De afgewezen koppeling gaat niet mee.
    expect(bron.relaties.filter((r) => r.soort === "duidt").map((r) => [r.bron, r.doel])).toEqual([["begrip:a", "element:e1"]]);
    // Hiërarchie draait om in de zin: de soort staat voorop.
    expect(bron.relaties.find((r) => r.soort === "begripsrelatie")?.anker_tekst).toBe("navorderingsaanslag is een soort aanslag");
    expect(bron.relaties.find((r) => r.soort === "begripsvoorstel")?.anker_tekst).toBe("voorstel van Lex: navorderingsaanslag geldt als aanslag");
  });

  it("een lijn naar een markering die niet geladen is, valt in het model weg", () => {
    const g = bouwModel([{ knopen: [], relaties: [] }, begripBron(S)]);
    expect(g.hasNode("begrip:a")).toBe(true);
    expect(g.edges().some((e) => g.getEdgeAttribute(e, "soort") === "duidt")).toBe(false);
    expect(g.edges().filter((e) => g.getEdgeAttribute(e, "groep") === "begrippen")).toHaveLength(2);
  });

  it("herkent het antwoord en de knoop", () => {
    expect(isBegripSamenhang(S)).toBe(true);
    expect(isBegripSamenhang({})).toBe(false);
    expect(begripIdVan("begrip:a")).toBe("a");
    expect(begripIdVan("element:a")).toBeUndefined();
  });
});

describe("conformiteit", () => {
  it("noemt de velden die het profiel mist, en zwijgt als het onbekend is", () => {
    expect(veldVanPad("http://www.w3.org/2004/02/skos/core#definition")).toBe("definitie");
    expect(conformZin({ conform: true, meldingen: [] }, "1.0.0")).toBe("NL-SBB-conform (profiel 1.0.0)");
    expect(conformZin({ conform: false, meldingen: [
      { laag: "nl_sbb", ernst: "fout", pad: "http://www.w3.org/2004/02/skos/core#definition", melding: "" },
      { laag: "nl_sbb", ernst: "waarschuwing", pad: "http://www.w3.org/2004/02/skos/core#example", melding: "" },
      { laag: "eigen", ernst: "fout", pad: "urn:wa-ns:definitieHerkomst", melding: "" },
    ] }, "1.0.0")).toBe("Niet NL-SBB-conform (profiel 1.0.0): definitie ontbreekt of klopt niet");
    expect(conformZin({ conform: null, meldingen: [] }, "1.0.0")).toBeNull();
    expect(conformZin(undefined, "1.0.0")).toBeNull();
    expect(isConformiteit({ beschikbaar: true, nl_sbb_versie: "1.0.0", begrippen: {} })).toBe(true);
    expect(isConformiteit({ begrippen: {} })).toBe(false);
  });
});
