import { describe, expect, it } from "vitest";

import {
  LEGE_INHOUD, begripUitParam, metKoppelstand, filterBegrippen, revisieZin,
  sorteerKoppelingen, volledigeInhoud,
} from "./begrippen";
import type { Begrip, KoppelStand, Koppeling } from "./types";

describe("volledigeInhoud", () => {
  it("vult een onvolledige inhoud van de api aan", () => {
    expect(volledigeInhoud({ naam: "X" }).voorbeelden).toEqual([]);
    // Spoor I1: wat een oud begrip nog meer droeg, valt weg.
    const oud = volledigeInhoud({ naam: "X", jas_klasse: "Rechtssubject", open_vragen: ["v"],
      voorbeelden: [{ tekst: "a", oordeel: "wel", toelichting: "t" }] } as never);
    expect(Object.keys(oud).sort()).toEqual(Object.keys(LEGE_INHOUD).sort());
    expect(oud.voorbeelden).toEqual([{ tekst: "a", oordeel: "wel" }]);
  });
});

it("sorteert passages op rol, dan natuurlijk op vindplaats", () => {
  const k = (id: string, rol: Koppeling["rol"], vindplaats: string) =>
    ({ id, rol, bewijs: { vindplaats, tekst: id } }) as unknown as Koppeling;
  expect(sorteerKoppelingen([k("c", "context", "A"), k("b", "duiding", "Artikel 10"), k("a", "duiding", "Artikel 9"),
    k("d", "definitie", "A")]).map((x) => x.id)).toEqual(["a", "b", "d", "c"]);
});

it("begripUitParam laat alleen een id door", () => {
  expect(begripUitParam("3f2a-9c")).toBe("3f2a-9c");
  expect(begripUitParam("../x")).toBeUndefined();
  expect(begripUitParam(undefined)).toBeUndefined();
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

describe("filterBegrippen", () => {
  const b = (naam: string, status: "concept" | "geaccordeerd" | "vervangen", definitie = "", alternatieve_termen: string[] = []) =>
    ({ status, inhoud: { ...LEGE_INHOUD, naam, definitie, alternatieve_termen } });
  const lijst = [b("Aanslag", "concept", "Een beschikking"), b("Schuld", "geaccordeerd", "", ["last"]), b("Oud", "vervangen")];
  it("filtert op status en zoekt in naam, termen en definitie", () => {
    expect(filterBegrippen(lijst, { term: "", status: "vervangen" }).map((x) => x.inhoud.naam)).toEqual(["Oud"]);
    expect(filterBegrippen(lijst, { term: "BESCHIK", status: "alle" }).map((x) => x.inhoud.naam)).toEqual(["Aanslag"]);
    expect(filterBegrippen(lijst, { term: "last", status: "alle" }).map((x) => x.inhoud.naam)).toEqual(["Schuld"]);
  });
});

describe("metKoppelstand", () => {
  const k = (id: string, x = {}) => ({ id, element_id: id, rol: "duiding", motivatie: "", bewijs: { tekst: id }, beoordeling: "open",
    beoordeeld_door: null, beoordeeld_op: null, actualiteit: "actueel", lifecycle_nu: "human_approved", annotatie_beoordeeld: true, ...x });
  const begrip = { id: "b", revisie: 2, status: "concept", inhoud: { naam: "Alfa" }, koppelingen: [k("a"), k("b")] } as unknown as Begrip;
  const stand = (kop: object[]) => ({ id: "b", revisie: 3, status: "concept", koppelingen: kop }) as unknown as KoppelStand;
  const s = (id: string, x = {}) => { const { bewijs: _, ...r } = k(id, x); return { ...r, bevestigingen: 0 }; };

  it("legt de stand over de kaart en houdt het bewijs", () => {
    const uit = metKoppelstand(begrip, stand([s("a", { beoordeling: "akkoord" }), s("b")]))!;
    expect(uit.revisie).toBe(3);
    expect(uit.inhoud.naam).toBe("Alfa");
    expect(uit.koppelingen[0]).toMatchObject({ beoordeling: "akkoord", bewijs: { tekst: "a" } });
  });

  it("laat een losgemaakte passage weg", () => {
    expect(metKoppelstand(begrip, stand([s("b")]))!.koppelingen.map((x) => x.id)).toEqual(["b"]);
  });

  it("vraagt de kaart opnieuw bij een nieuwe passage of bewijsstand", () => {
    expect(metKoppelstand(begrip, stand([s("a"), s("b"), s("c")]))).toBeNull();
    expect(metKoppelstand(begrip, stand([{ ...s("a"), bevestigingen: 1 }, s("b")]))).toBeNull();
  });
});

describe("revisieZin bij bulk en accorderen", () => {
  it("noemt de reden en het aantal", () => {
    expect(revisieZin({ actie: "begrip-geaccordeerd", detail: { reden: "Getoetst." } })).toBe("Geaccordeerd: Getoetst.");
    expect(revisieZin({ actie: "koppeling-gewijzigd", detail: { beoordeling: "akkoord", koppelingen: ["a", "b"] } })).toBe("2 passages beoordeeld: akkoord");
    expect(revisieZin({ actie: "koppeling-bevestigd", detail: { koppelingen: ["a", "b"] } })).toBe("2 veranderde passages bevestigd");
  });
});
