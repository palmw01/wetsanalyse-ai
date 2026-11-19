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
