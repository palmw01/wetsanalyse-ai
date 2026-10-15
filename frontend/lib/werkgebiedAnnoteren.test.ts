import { describe, expect, it } from "vitest";

import type { AnnotatieWerkvoorraad, EenheidStatus } from "./types";
import { bevestigingInhoud, getal, isWerkvoorraad, parseBevestiging, PLAFOND, standRegel } from "./werkgebiedAnnoteren";

function eenheid(n: number, status: EenheidStatus = "nieuw") {
  return { bron_iri: `urn:bwb:BWBR0004770:artikel:${n}`, label: `Artikel ${n}`, regeling: "Invorderingswet 1990",
    bwb_id: "BWBR0004770", stand: { status, voorstellen: 0, te_beoordelen: 0 }, selecties: ["s1"] };
}

function werkvoorraad(nieuw: number, extra: Partial<AnnotatieWerkvoorraad> = {}): AnnotatieWerkvoorraad {
  const eenheden = Array.from({ length: nieuw }, (_, i) => eenheid(i + 1));
  return {
    werkgebied_id: "wg1", revisie: 2, naam: "Invorderbaarheid", selecties: [], eenheden,
    te_annoteren: eenheden.map((e) => e.bron_iri), context_niet_meegenomen: 0, volledig: true, open_punten: [],
    schatting: { per_bepaling: 3000, basis: 12, totaal: 3000 * nieuw },
    schatting_toelichting: "Mediaan van je laatste 12 annotatiebeurten, keer het aantal bepalingen.",
    budget: { resterend: 100_000, budget: 500_000, actief: true, geblokkeerd: false },
    ...extra,
  };
}

describe("parseBevestiging", () => {
  it("neemt een geldige bevestiging over", () => {
    expect(parseBevestiging({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: 9000 }))
      .toEqual({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3, schatting: 9000 });
    expect(parseBevestiging({ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 3 })?.schatting).toBeNull();
  });
  it("kent ook het meedenken over de begrippen (fase C)", () => {
    expect(parseBevestiging({ soort: "begrippen_verdiepen", werkgebied_id: "wg1", aantal: 4, schatting: null }))
      .toEqual({ soort: "begrippen_verdiepen", werkgebied_id: "wg1", aantal: 4, schatting: null });
  });
  it.each([
    [null], [{}], [{ soort: "iets", werkgebied_id: "wg1", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "", aantal: 1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: -1 }],
    [{ soort: "werkgebied_annoteren", werkgebied_id: "wg1", aantal: 1.5 }],
  ])("weigert %j", (ruw) => expect(parseBevestiging(ruw)).toBeUndefined());
});

describe("bevestigingInhoud", () => {
  it("noemt aantal, schatting en budget", () => {
    const b = bevestigingInhoud(werkvoorraad(3));
    expect([b.aantal, b.dezeRun, b.schatting, b.budgetOver, b.budgetKrap]).toEqual([3, 3, 9000, 100_000, false]);
    expect(b.nietMee).toEqual([]);
  });
  it("zonder geschiedenis geen verzonnen getal", () => {
    expect(bevestigingInhoud(werkvoorraad(2, { schatting: null })).schatting).toBeNull();
  });
  it("zegt wat er niet meegaat, ook boven het plafond", () => {
    const wv = werkvoorraad(PLAFOND + 5, { context_niet_meegenomen: 2 });
    wv.eenheden.push(eenheid(999, "afgerond"));
    const b = bevestigingInhoud(wv);
    expect(b.dezeRun).toBe(PLAFOND);
    expect(b.schatting).toBe(3000 * PLAFOND);
    expect(b.nietMee).toEqual([
      "1 bepaling met voorstellen, een oordeel of afgerond", "2 contextbronnen",
      `5 bepalingen boven het plafond van ${PLAFOND} per run (volgende run)`]);
  });
  it("waarschuwt als de schatting het budget overstijgt, en zwijgt zonder limiet", () => {
    expect(bevestigingInhoud(werkvoorraad(50)).budgetKrap).toBe(true);
    const zonder = bevestigingInhoud(werkvoorraad(50, { budget: { resterend: 0, budget: 0, actief: false, geblokkeerd: false } }));
    expect([zonder.budgetOver, zonder.budgetKrap]).toEqual([null, false]);
  });
});

it("standRegel noemt alleen wat voorkomt, in vaste volgorde", () => {
  expect(standRegel({ afgerond: 1, nieuw: 3, te_beoordelen: 0 })).toBe("3 nieuw · 1 afgerond");
  expect(standRegel({})).toBe("");
});

it("getal schrijft zoals Lex", () => expect(getal(21000)).toBe("21.000"));

it("isWerkvoorraad weigert een half antwoord", () => {
  expect(isWerkvoorraad(werkvoorraad(1))).toBe(true);
  expect(isWerkvoorraad({})).toBe(false);
  expect(isWerkvoorraad(null)).toBe(false);
});
