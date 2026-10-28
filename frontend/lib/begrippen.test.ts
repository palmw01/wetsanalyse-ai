import { describe, expect, it } from "vitest";

import {
  LEGE_INHOUD, begripUitParam, gewijzigdeVelden, handmatigeInhoud, inhoudGewijzigd, isAlPrimair, isPoortFout, revisieZin,
  sorteerKoppelingen, volledigeInhoud, weergaveUitParam,
} from "./begrippen";
import type { Koppeling } from "./types";

const inhoud = (over = {}) => ({ ...LEGE_INHOUD, naam: "Belastingschuldige", ...over });

describe("inhoudGewijzigd", () => {
  it("ziet een echte wijziging, en niets bij lege regels of een andere sleutelvolgorde", () => {
    const oud = inhoud({ voorbeelden: [{ tekst: "a", oordeel: "wel" }], alternatieve_termen: ["schuldenaar"] });
    expect(inhoudGewijzigd(oud, { ...oud, definitie: "Wie de belasting verschuldigd is." })).toBe(true);
    expect(inhoudGewijzigd(oud, { ...oud, alternatieve_termen: ["schuldenaar", "  "] })).toBe(false);
    expect(inhoudGewijzigd(oud, { ...oud, voorbeelden: [...oud.voorbeelden, { tekst: " ", oordeel: "niet" }] })).toBe(false);
    expect(inhoudGewijzigd(oud, { ...oud, naam: " Belastingschuldige " })).toBe(false);
    expect(gewijzigdeVelden(oud, { ...oud, context: "x", definitie_herkomst: "letterlijk" }))
      .toEqual(["context", "definitie_herkomst"]);
  });

  it("vult een onvolledige inhoud van de api aan", () => {
    expect(volledigeInhoud({ naam: "X" }).voorbeelden).toEqual([]);
    // Spoor I1: wat een oud begrip nog meer droeg, valt weg.
    const oud = volledigeInhoud({ naam: "X", jas_klasse: "Rechtssubject", open_vragen: ["v"],
      voorbeelden: [{ tekst: "a", oordeel: "wel", toelichting: "t" }] } as never);
    expect(Object.keys(oud).sort()).toEqual(Object.keys(LEGE_INHOUD).sort());
    expect(oud.voorbeelden).toEqual([{ tekst: "a", oordeel: "wel" }]);
    expect(inhoudGewijzigd({ naam: "X" } as never, volledigeInhoud({ naam: "X" }))).toBe(false);
  });
});

it("sorteert passages op rol, dan natuurlijk op vindplaats", () => {
  const k = (id: string, rol: Koppeling["rol"], vindplaats: string) =>
    ({ id, rol, bewijs: { vindplaats, tekst: id } }) as unknown as Koppeling;
  expect(sorteerKoppelingen([k("c", "context", "A"), k("b", "duiding", "Artikel 10"), k("a", "duiding", "Artikel 9"),
    k("d", "definitie", "A")]).map((x) => x.id)).toEqual(["a", "b", "d", "c"]);
});

it("herkent de begripsfouten aan status en fout", () => {
  expect(isAlPrimair({ status: 409, detail: "x", data: { fout: "al_primair" } })).toBe(true);
  expect(isPoortFout({ status: 409, detail: "x", data: { fout: "poort", redenen: [] } })).toBe(true);
  expect(isPoortFout({ status: 409, detail: "x", data: { fout: "al_primair" } })).toBe(false);
});

it("begripUitParam laat alleen een id door", () => {
  expect(begripUitParam("3f2a-9c")).toBe("3f2a-9c");
  expect(begripUitParam("../x")).toBeUndefined();
  expect(begripUitParam(undefined)).toBeUndefined();
});

it("weergaveUitParam: alleen `kaart` opent de kaart, al het andere is lezen", () => {
  expect(weergaveUitParam("kaart")).toBe("kaart");
  expect(weergaveUitParam("lezen")).toBe("lezen");
  expect(weergaveUitParam("iets")).toBe("lezen");
  expect(weergaveUitParam(undefined)).toBe("lezen");
});

describe("revisieZin", () => {
  it("noemt de gewijzigde velden in gewone woorden", () => {
    expect(revisieZin({ actie: "begrip-gewijzigd", detail: { velden: ["definitie", "definitie_herkomst"] } }))
      .toBe("Gewijzigd: definitie, herkomst van de definitie");
  });
  it("telt passages en zegt het oordeel", () => {
    expect(revisieZin({ actie: "begrip-aangemaakt", detail: { element_ids: ["a", "b"] } })).toBe("Aangemaakt (2 passages)");
    expect(revisieZin({ actie: "begrip-gekoppeld", detail: { element_ids: [] } })).toBe("Passages gekoppeld");
    expect(revisieZin({ actie: "koppeling-gewijzigd", detail: { beoordeling: "akkoord" } })).toBe("Passage beoordeeld: akkoord");
    expect(revisieZin({ actie: "iets-nieuws", detail: {} })).toBe("iets-nieuws");
  });
});

it("een met de hand gewijzigde definitie is geformuleerd; ongewijzigd houdt ze haar herkomst", () => {
  const oud = { ...LEGE_INHOUD, naam: "termijn", definitie: "de tijd", definitie_herkomst: "letterlijk" as const };
  expect(handmatigeInhoud(oud, { definitie: " de tijd ", uitleg: "x" })).toMatchObject({ definitie_herkomst: "letterlijk", uitleg: "x" });
  expect(handmatigeInhoud(oud, { definitie: "de periode", uitleg: "" }).definitie_herkomst).toBe("geformuleerd");
  expect(handmatigeInhoud(oud, { definitie: "", uitleg: "" }).definitie_herkomst).toBeNull();
});

describe("definitieAard", () => {
  it("alleen een letterlijke definitie is een brondefinitie; de rest is een analysebegrip", async () => {
    const { definitieAard } = await import("./begrippen");
    expect(definitieAard({ definitie: "", definitie_herkomst: "letterlijk" }).soort).toBe("geen");
    expect(definitieAard({ definitie: "x", definitie_herkomst: "letterlijk" }).soort).toBe("brondefinitie");
    expect(definitieAard({ definitie: "x", definitie_herkomst: "samengesteld" })).toMatchObject({
      soort: "analysebegrip", uitleg: expect.stringContaining("geen wettelijke definitie") });
    expect(definitieAard({ definitie: "x", definitie_herkomst: "geformuleerd" }).soort).toBe("analysebegrip");
    expect(definitieAard({ definitie: "x" }).soort).toBe("analysebegrip");
  });
});
