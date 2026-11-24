// De buurt van een 2c-diagram is in de werkplek en in het rapport dezelfde: `diagramBuurt` hier en `diagram.buurt` in
// api/app/diagram.py lezen allebei `diagram.vectoren.json`.
import { describe, expect, it } from "vitest";
import type { SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";
import VECTOREN from "./diagram.vectoren.json";
import { bouwModel } from "./model";
import { DIAGRAM_DIEPTE, diagramBuurt } from "./weergave";

const knoop = (id: string, klasse: string): SamenhangKnoop => {
  const [soort, eigen] = id.split(":");
  return { id, soort: soort === "impliciet" ? "impliciet" : "markering", label: eigen, tekst: "", klasse, lifecycle: "",
    element_id: soort === "element" ? eigen : "", bwb_id: "", artikel: "", lid: "", rand: false };
};

describe("de buurt van een diagram (vectoren)", () => {
  it("de diepte is die van het rapport", () => {
    expect(VECTOREN.diepte).toBe(DIAGRAM_DIEPTE);
  });

  for (const g of VECTOREN.gevallen) {
    it(g.naam, () => {
      const klassen = g.klassen as unknown as Record<string, string>;
      const ids = new Set<string>([`element:${g.centraal}`, ...(g.relaties as string[][]).flatMap(([v, n]) => [v, n])]);
      const knopen = [...ids].map((id) => knoop(id, klassen[id.split(":")[1]] ?? "Rechtssubject"));
      const relaties: SamenhangRelatie[] = (g.relaties as string[][]).map(([bron, doel, type, lifecycle]) => ({
        bron, doel, soort: "jas_relatie", groep: "relaties", anker_tekst: type, type, leesvorm: type, lifecycle,
        veranderd: false, volgorde: null,
      }));
      const buurt = diagramBuurt(bouwModel([{ knopen, relaties }]), `element:${g.centraal}`);
      expect([...(buurt ?? [])].sort()).toEqual(g.buurt);
    });
  }
});

describe("het diagram in de werkplek", () => {
  it("haalt zich opnieuw op na een besluit: de versie volgt de revisies van de lagen", async () => {
    const { weergaveVersie } = await import("@/lib/annotatieNode");
    const view = { lagen: [{ id: "b", bron_iri: "x", revisie: 2, status: "" }, { id: "a", bron_iri: "y", revisie: 5, status: "" }] };
    expect(weergaveVersie(view as never)).toBe("a:5,b:2");
  });

  it("tekent de punt van een lijn op het eindpunt, en noemt de lijn zoals ze leest", async () => {
    const { pijlpunt, lijnNaam, knoopKleuren } = await import("@/lib/diagram2c");
    expect(pijlpunt({ x1: 0, y1: 0, x2: 10, y2: 0 })).toBe("10.00,0.00 5.00,-2.40 5.00,2.40");
    const knopen = [{ id: "a", tekst: "de ontvanger" }, { id: "b", tekst: "een belastingaanslag" }] as never[];
    const lijn = { van: "a", naar: "b", label: ["heeft als", "voorwerp"] } as never;
    expect(lijnNaam(lijn, knopen)).toBe("“de ontvanger” heeft als voorwerp “een belastingaanslag”");
    // Dezelfde kleuren als de badges, met een terugval voor een onbekende klasse.
    expect(knoopKleuren("Rechtsbetrekking")).toEqual({ vlak: "#90a2d0", rand: "#707ea2" });
    expect(knoopKleuren("Onbekend").vlak).toBe("#edefef");
  });
});
