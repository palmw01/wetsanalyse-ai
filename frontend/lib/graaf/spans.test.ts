import { describe, expect, it } from "vitest";
import type { NodeSegment } from "@/lib/annotatieNode";
import { segmentenVan, spansVan, type SpanElement } from "./spans";

const A9 = "urn:bwb:BWBR0004770:artikel:9";
const L2 = `${A9}:lid:2`, OA = `${L2}:onderdeel:a`;
const seg = (bron_iri: string, tekst: string, volgorde: number, extra: Partial<NodeSegment> = {}): NodeSegment =>
  ({ bron_iri, type: "Lid", label: "", tekst, bron_hash: "h", volgorde, ...extra });
const el = (id: string, start: number, eind: number, extra: Partial<SpanElement> = {}, bron_iri = L2): SpanElement =>
  ({ id, ankers: [{ bron_iri, start, eind, tekst: "", bron_hash: "h" }], lifecycle: "voorgesteld", ...extra });

describe("spans", () => {
  const lid = seg(L2, "De ontvanger vordert in.", 1);

  it("knipt de tekst op de ankers; de stukken zijn samen exact de tekst", () => {
    const stukken = spansVan(lid, [el("1", 3, 12), el("2", 13, 20)]);
    expect(stukken).toEqual([
      { tekst: "De " }, { tekst: "ontvanger", element: "1" }, { tekst: " " }, { tekst: "vordert", element: "2" }, { tekst: " in." },
    ]);
    expect(stukken.map((s) => s.tekst).join("")).toBe(lid.tekst);
  });

  it("bij overlap ligt de kortste markering bovenop", () => {
    expect(spansVan(lid, [el("lang", 0, 24), el("kort", 3, 12)]).map((s) => s.element)).toEqual(["lang", "kort", "lang"]);
  });

  it("telt in codepoints, niet in UTF-16", () => {
    const s = seg(L2, "€ 𝟙 boete", 1);
    expect(spansVan(s, [el("1", 4, 9)])).toEqual([{ tekst: "€ 𝟙 " }, { tekst: "boete", element: "1" }]);
  });

  it("een anker van een andere bronstand, een ander segment, of een verworpen of verouderde markering geeft geen span", () => {
    const anders = { ...el("1", 3, 12), ankers: [{ bron_iri: L2, start: 3, eind: 12, tekst: "", bron_hash: "oud" }] };
    expect(spansVan(lid, [anders, el("2", 3, 12, {}, OA), el("3", 3, 12, { lifecycle: "rejected" }), el("4", 3, 12, { verouderd: true })]))
      .toEqual([{ tekst: lid.tekst }]);
  });

  it("de segmenten van een knoop: zijzelf en alles eronder, in volgorde", () => {
    const segmenten = [seg(OA, "a. iets", 3, { parent_iri: L2, type: "Onderdeel" }), lid, seg(`${A9}:lid:1`, "Eerste.", 0)];
    expect(segmentenVan(segmenten, L2).map((s) => s.bron_iri)).toEqual([L2, OA]);
    expect(segmentenVan(segmenten, A9).map((s) => s.bron_iri)).toEqual([`${A9}:lid:1`, L2, OA]);
    expect(segmentenVan(segmenten, "urn:bwb:ander")).toEqual([]);
  });
});
