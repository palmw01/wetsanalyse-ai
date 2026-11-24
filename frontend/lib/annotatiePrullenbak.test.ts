import { describe, expect, it } from "vitest";

import { bronVerwijderdZin, impactZinnen, inhoudZin, isVerwijderImpact, type VerwijderImpact } from "./annotatiePrullenbak";

const impact = (x: Partial<VerwijderImpact> = {}): VerwijderImpact => ({
  lagen: 1, markeringen: 9, beoordeeld: 7, historie: 0, relaties: 0, begrippen: [], regels: [], bewaartermijn_dagen: 30, ...x,
});

describe("de bevestiging noemt wat er verloren gaat", () => {
  it("markeringen, beoordeeld en wie ernaar verwijst", () => {
    const z = impactZinnen(impact({
      begrippen: [{ id: "b1", naam: "belastingschuldige", werkgebied_id: "w" }, { id: "b2", naam: "aanslag", werkgebied_id: "w" }],
      regels: [{ id: "r1", naam: "verschuldigd", werkgebied_id: "w" }],
    }));
    expect(z.verlies).toBe("9 markeringen, waarvan 7 beoordeeld, gaan naar de prullenbak.");
    expect(z.verwijzers).toBe("2 begrippen (“belastingschuldige” en “aanslag”) en 1 afleidingsregel (“verschuldigd”) verwijzen "
      + "ernaar; daar staat dan “bron verwijderd”.");
    expect(z.terug).toMatch(/^Je kunt de annotatie 30 dagen terugzetten/);
  });

  it("relaties, historie, enkelvoud en lange lijsten", () => {
    expect(impactZinnen(impact({ markeringen: 1, beoordeeld: 0 })).verlies)
      .toBe("1 markering, waarvan 0 beoordeeld, gaat naar de prullenbak.");
    expect(impactZinnen(impact({ relaties: 3, historie: 2 })).verlies)
      .toBe("9 markeringen, waarvan 7 beoordeeld, en 3 relaties gaan naar de prullenbak, met 2 markeringen uit de historie.");
    expect(impactZinnen(impact()).verwijzers).toBeNull();
    const vijf = Array.from({ length: 5 }, (_, i) => ({ id: `b${i}`, naam: `b${i}`, werkgebied_id: null }));
    expect(impactZinnen(impact({ begrippen: vijf })).verwijzers).toBe(
      "5 begrippen (“b0”, “b1”, “b2” en 2 meer) verwijzen ernaar; daar staat dan “bron verwijderd”.");
    expect(impactZinnen(impact({ regels: vijf.slice(0, 1) })).verwijzers).toMatch(/^1 afleidingsregel \(“b0”\) verwijst/);
  });

  it("toetst de vorm van het antwoord", () => {
    expect(isVerwijderImpact(impact())).toBe(true);
    expect(isVerwijderImpact({ markeringen: 1 })).toBe(false);
    expect(isVerwijderImpact(null)).toBe(false);
  });
});

describe("een verwijzing naar een verwijderd element", () => {
  it("zegt of het nog terug kan", () => {
    const b = { op: "2026-11-24T10:00:00+00:00", door: "jurist-a", weergave: "urn:x", prullenbak_id: "p1" };
    expect(bronVerwijderdZin(b)).toBe("bron verwijderd op 24 nov 2026 door jurist-a · in de prullenbak, terug te zetten");
    expect(bronVerwijderdZin({ ...b, prullenbak_id: null })).toMatch(/· definitief verwijderd$/);
    expect(inhoudZin({ markeringen: 1, beoordeeld: 1 })).toBe("1 markering, waarvan 1 beoordeeld");
  });
});
