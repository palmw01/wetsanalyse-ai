import { describe, expect, it } from "vitest";

import { losseVragen, normTerm, regelingVan, standaardKeuze, termAkkoord, termenVan, termOmvang, termVan } from "./begripTermen";
import type { Betekenisgroep, GroepenAntwoord, Passage } from "./types";

const p = (id: string, tekst: string, vindplaats: string): Passage => ({
  element_id: id, tekst, jas_klasse: "begrip", review_status: "voorgesteld", bron_iri: `urn:bwb:BWBR0004770:artikel:${id}`, vindplaats,
});

const g = (id: string, naam: string, leden: Passage[], extra: Partial<Betekenisgroep> = {}): Betekenisgroep => ({
  id, aandacht: "groen", voorstel: { naam }, uitleg: [], conflicten: [], besluit: "open", reden: "", begrip_id: null,
  besloten_door: null, leden, lijkt_op: [], ...extra,
});

const IW = "Invorderingswet 1990";
const data: GroepenAntwoord = {
  run: { id: "r1", vragen_besluiten: { v9: { antwoord: "apart", door: "x" } }, uitkomst: { relaties: [], vragen: [
    { kandidaat_id: "v1", van: "e1", naar: "e2", regel: "zelfde_term", uitleg: [] },
    { kandidaat_id: "v2", van: "e1", naar: "e5", regel: "zelfde_term", uitleg: [] },
    { kandidaat_id: "v3", van: "e1", naar: "e3", regel: "zelfde_term", uitleg: [] },
    { kandidaat_id: "v9", van: "e2", naar: "e3", regel: "zelfde_term", uitleg: [] },
  ] } } as unknown as GroepenAntwoord["run"],
  groepen: [
    g("g1", "tijdvak", [p("e1", "het tijdvak", `Artikel 9 · Lid 1 – ${IW}`)]),
    g("g2", "Tijdvak", [p("e2", "tijdvak", `Artikel 10 – ${IW}`), p("e3", "tijdvakken", "Artikel 3 – AWR")],
      { lijkt_op: [{ begrip_id: "b1", naam: "tijdvak", gedeeld: [] }] }),
    g("g3", "belastingrente", [p("e4", "belastingrente", `Artikel 30f – ${IW}`)]),
    g("g4", "tijdvak", [p("e6", "tijdvak", `Artikel 11 – ${IW}`)], { besluit: "geparkeerd" }),
    g("g5", "aanslag", [p("e7", "aanslag", `Artikel 1 – ${IW}`)], { besluit: "afgewezen" }),
  ],
  passages: { e5: p("e5", "termijn", `Artikel 9 · Lid 2 – ${IW}`) },
};

describe("begripTermen", () => {
  it("normaliseert zoals de api: kleine letters, zonder lidwoord", () => {
    expect(normTerm("Het Tijdvak ")).toBe("tijdvak");
    expect(normTerm("een aanslag")).toBe("aanslag");
    expect(normTerm("dezelfde")).toBe("dezelfde");
  });

  it("brengt de groepen per term samen, grootste eerst", () => {
    const t = termenVan(data);
    expect(t.map((x) => x.sleutel)).toEqual(["tijdvak", "belastingrente", "aanslag"]);
    const tv = t[0];
    expect(tv.naam).toBe("Tijdvak");
    expect(tv.open.map((x) => x.id)).toEqual(["g2", "g1", "g4"]);
    expect(tv.passages).toBe(4);
    expect(tv.regelingen).toEqual(["AWR", IW]);
    expect(tv.lijktOp).toEqual([{ begrip_id: "b1", naam: "tijdvak" }]);
    expect(t[2].open).toEqual([]);
    expect(t[2].besloten.map((x) => x.id)).toEqual(["g5"]);
  });

  it("splitst de vragen binnen de term van die naar een andere passage", () => {
    const tv = termenVan(data)[0];
    expect(tv.vragenBinnen.map((v) => v.kandidaat_id)).toEqual(["v1", "v3"]);
    expect(tv.vragenBuiten.map((v) => v.kandidaat_id)).toEqual(["v2"]);
  });

  it("een akkoord neemt de groepen van de gekozen passages en de vragen met beide kanten gekozen", () => {
    const tv = termenVan(data)[0];
    const vragen = [...tv.vragenBinnen, ...tv.vragenBuiten];
    const a = termAkkoord(tv, new Set(["e1", "e2"]), vragen);
    expect(a.groepen.map((x) => x.id)).toEqual(["g2", "g1"]);
    expect(a.kandidaat_ids).toEqual(["v1"]);
    expect(termAkkoord(tv, new Set(["e1", "e2", "e3"]), vragen).kandidaat_ids).toEqual(["v1", "v3"]);
  });

  it("vinkt standaard alles open aan, niet wat voor later bewaard is", () => {
    expect([...standaardKeuze(termenVan(data)[0])].sort()).toEqual(["e1", "e2", "e3"]);
  });

  it("vindt een term bij zijn sleutel en beschrijft de omvang", () => {
    const t = termenVan(data);
    expect(termVan(t, "Het tijdvak")?.sleutel).toBe("tijdvak");
    expect(termVan(t, "onbekend")).toBeUndefined();
    expect(termOmvang(t[0])).toBe("3 voorstellen in 2 regelingen");
    expect(termOmvang(t[1])).toBe(`1 voorstel · ${IW}`);
    expect(regelingVan({ vindplaats: "Artikel 9" })).toBe("");
  });

  it("een vraag zonder open groep aan een van beide kanten staat los", () => {
    const los = { ...data, run: { ...data.run!, uitkomst: { ...data.run!.uitkomst!,
      vragen: [...data.run!.uitkomst!.vragen, { kandidaat_id: "v4", van: "e7", naar: "e5", regel: "", uitleg: [] }] } } };
    expect(losseVragen(los, termenVan(los)).map((v) => v.kandidaat_id)).toEqual(["v4"]);
    expect(losseVragen(data, termenVan(data))).toEqual([]);
  });

  it("zonder data geen termen", () => {
    expect(termenVan(null)).toEqual([]);
  });
});
