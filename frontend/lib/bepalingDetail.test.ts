import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BEPALING_DETAIL_VELDEN, parseBepalingDetail, plaatsZin } from "./bepalingDetail";

const VP = { iri: "urn:bwb:BWBR0004770:artikel:36", label: "Artikel 36", jci: "", regeling: "Invorderingswet 1990" };
const LEEG = { aantal: 0, items: [] };
const DETAIL = {
  schema_versie: 1, bron_iri: VP.iri, beschikbaar: true, vindplaats: VP,
  plaats: [{ soort: "hoofdstuk", nummer: "VI", titel: "Aansprakelijkheid", iri: "urn:bwb:BWBR0004770:hoofdstuk:VI" },
    { soort: "afdeling", nummer: "1", titel: "", iri: "urn:bwb:BWBR0004770:hoofdstuk:VI:afdeling:1" }],
  status: "goed", inwerking: "2010-07-04", terugwerkend_tot: null, gewijzigd_bij: "Stb.2009-610",
  geldig_vanaf: "2026-10-01", geldig_tot: null, toestand_url: "",
  verwijst_naar: [{ van: { ...VP, label: "Artikel 36, lid 1" }, naar: { ...VP, label: "Artikel 1" }, anker: "artikel 1", in_graaf: true, door: "bron" }],
  verwijst_naar_volledig: true, verwezen_door: { aantal: 1, items: [VP] }, grondslag_voor: LEEG, bevoegdheid_voor: LEEG, genoemd_in: LEEG,
  definieert: ["bestuurder"],
};

describe("bepalingDetail", () => {
  it("volgt de velden van het contract in de api (drift)", () => {
    const bron = readFileSync(join(__dirname, "../../api/app/bepaling_graaf_contract.py"), "utf8");
    const klasse = bron.slice(bron.indexOf("class BepalingDetail"));
    const velden = [...klasse.matchAll(/^ {4}(\w+): /gm)].map((m) => m[1]);
    expect(velden).toEqual([...BEPALING_DETAIL_VELDEN]);
  });

  it("neemt een geldig detail aan en weigert een half detail", () => {
    expect(parseBepalingDetail(DETAIL)?.inwerking).toBe("2010-07-04");
    expect(parseBepalingDetail({ ...DETAIL, verwezen_door: { aantal: 1 } })).toBeUndefined();
    expect(parseBepalingDetail({ ...DETAIL, vindplaats: { iri: VP.iri } })).toBeUndefined();
    expect(parseBepalingDetail(null)).toBeUndefined();
  });

  it("noemt de plek in gewone woorden, met het opschrift", () => {
    expect(plaatsZin(DETAIL.plaats)).toBe("Hoofdstuk VI – Aansprakelijkheid › Afdeling 1");
    expect(plaatsZin([])).toBe("");
  });
});
