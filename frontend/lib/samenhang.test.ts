import { describe, expect, it } from "vitest";
import vectoren from "./jci-vectoren.json";
import { bronDoel, clusterOmschrijving, inPartijen, MAX_SAMENHANG_MEER, vindplaatsVan, type Samenhang, type SamenhangKnoop } from "./samenhang";

const LAW = "urn:bwb:BWBR0004770", ART = `${LAW}:artikel:9`, L1 = `${ART}:lid:1`, L2 = `${ART}:lid:2`;
const A10 = `${LAW}:artikel:10`;
function knoop(id: string, soort: SamenhangKnoop["soort"], extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop {
  return { id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770",
    artikel: "", lid: "", rand: false, ...extra };
}
function samenhang(artikel = ART, extra: Partial<Samenhang> = {}): Samenhang {
  return {
    schema_versie: 1, doel: { bron_iri: artikel }, snapshot_id: "s", artikel_iri: artikel, verwijzingen_beschikbaar: true, afgekapt: false,
    knopen: [knoop(LAW, "regeling"), knoop(ART, "artikel"), knoop(L1, "lid", { lid: "1", artikel: "9" }),
      knoop(L2, "lid", { lid: "2", artikel: "9" }), knoop("element:e1", "markering", { klasse: "Rechtssubject", element_id: "e1" }),
      knoop("klasse:Rechtssubject", "klasse", { klasse: "Rechtssubject" }), knoop(A10, "artikel", { rand: true, artikel: "10" })],
    relaties: [
      { bron: LAW, doel: ART, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L1, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: ART, doel: L2, soort: "bevat", groep: "structuur", anker_tekst: "" },
      { bron: L2, doel: L1, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "het eerste lid" },
      { bron: L1, doel: A10, soort: "verwijst_naar", groep: "verwijzingen", anker_tekst: "artikel 10" },
      { bron: "element:e1", doel: L1, soort: "markeert", groep: "annotaties", anker_tekst: "" },
      { bron: "element:e1", doel: "klasse:Rechtssubject", soort: "heeft_klasse", groep: "annotaties", anker_tekst: "" },
    ],
    ...extra,
  };
}
describe("clusterOmschrijving", () => {
  it("omschrijft de clusters als delen en artikelen", () => {
    const hfd = `${LAW}:hoofdstuk:II`;
    const deel = samenhang(hfd, { knopen: [knoop(hfd, "deel"), knoop(ART, "artikel")], relaties: [] });
    expect(clusterOmschrijving([samenhang(), samenhang(A10)])).toBe("2 artikelen");
    expect(clusterOmschrijving([samenhang(), deel])).toBe("1 deel en 1 artikel");
    expect(clusterOmschrijving([deel, deel])).toBe("2 delen");
  });
});

describe("bronDoel", () => {
  it("gooit niet bij een kapotte percent-encoding, maar geeft niets terug", () => {
    expect(() => bronDoel("urn:bwb:BWBR0004770:artikel:10%")).not.toThrow();
    expect(bronDoel("urn:bwb:BWBR0004770:artikel:10%")).toBeUndefined();
  });

  it("vertaalt jci en graaf-IRI naar een bronnode", () => {
    expect(bronDoel("jci1.3:c:BWBR0004770&artikel=9&lid=2&z=2026-01-01&g=2026-01-01")).toMatchObject(
      { bron_iri: L2, bwb_id: "BWBR0004770", artikel: "9", lid: "2" });
    expect(bronDoel(ART)?.bron_iri).toBe(ART);
    // Een graaf-IRI blijft heel, ook met een ge-escapete dubbele punt in het artikelnummer.
    expect(bronDoel("urn:bwb:BWBR0005537:artikel:3%3A40")?.bron_iri).toBe("urn:bwb:BWBR0005537:artikel:3%3A40");
  });
  it.each(vectoren.vectoren)("$ref → $iri (zelfde regel als importer en agent)", ({ ref, iri, soort, label }) => {
    const doel = bronDoel(ref);
    // Een hele regeling of een verwijzing zonder eigen node is geen bronnode om te openen.
    if (soort === null || soort === "regeling") return expect(doel).toBeUndefined();
    expect(doel?.bron_iri).toBe(iri);
    expect(doel?.label).toBe(label);
  });
  it.each(vectoren.vectoren)("vindplaatsVan $ref (spiegel van bronmodel.vindplaats)", ({ ref, iri, soort, label }) => {
    const vp = vindplaatsVan(ref);
    if (soort === null) return expect(vp).toBeUndefined();
    expect([vp?.bron_iri, vp?.soort, vp?.label]).toEqual([iri, soort, label]);
  });
  it("weigert een hele regeling, een id-knoop en vreemde bronnen", () => {
    expect(bronDoel("jci1.3:c:BWBR0004770")).toBeUndefined();
    expect(bronDoel(`${LAW}:id:abc`)).toBeUndefined();
    expect(bronDoel("https://example.org")).toBeUndefined();
  });
});

describe("inPartijen", () => {
  it("knipt in opeenvolgende partijen en verliest niets", () => {
    const reeks = Array.from({ length: 31 }, (_, i) => i);
    const partijen = inPartijen(reeks, MAX_SAMENHANG_MEER);
    expect(partijen.map((p) => p.length)).toEqual([30, 1]);
    expect(partijen.flat()).toEqual(reeks);
  });
  it("geeft niets bij een lege reeks", () => {
    expect(inPartijen([], 30)).toEqual([]);
  });
});
