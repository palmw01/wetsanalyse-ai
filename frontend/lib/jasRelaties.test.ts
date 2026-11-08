import { describe, expect, it } from "vitest";

import { RELATIETYPEN, toegestaan, typenTussen } from "./jasRelaties";
import vectoren from "./jasRelaties.vectoren.json";

type Geval = { type: string; van: string; naar: string; van_subtype?: string; naar_subtype?: string; verwacht: boolean };

describe("toegestaan", () => {
  it("volgt dezelfde gevallen als de api (api/tests/test_jas_relaties.py)", () => {
    for (const g of vectoren.gevallen as Geval[]) {
      expect(toegestaan(g.type, g.van, g.naar, g.van_subtype ?? "", g.naar_subtype ?? ""), JSON.stringify(g)).toBe(g.verwacht);
    }
  });

  it("geeft bij een klassenpaar alleen typen in de goede richting", () => {
    expect(typenTussen("Rechtssubject", "Rechtsbetrekking")).toEqual(
      expect.arrayContaining(["plichthebbende", "rechthebbende"]),
    );
    expect(typenTussen("Rechtsbetrekking", "Rechtssubject")).not.toContain("plichthebbende");
    for (const code of typenTussen("Variabele en variabelewaarde", "Voorwaarde")) {
      expect(RELATIETYPEN[code].naar).toContain("Voorwaarde");
    }
  });
});
