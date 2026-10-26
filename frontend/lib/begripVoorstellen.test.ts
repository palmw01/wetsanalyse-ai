import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AANDACHTSPUNT, aandachtspunten, aanpassingUit, akkoordLabel, akkoordVoor, enigeDefinitie, groepDefinitie,
  groepenVanVraag, herkomstNaAanpassing, openVragen, overnameVoor, passageTekst, samenAkkoord,
} from "./begripVoorstellen";
import type { Betekenisgroep, ConceptKaart, GroepenAntwoord } from "./types";

const lid = (id: string, tekst = id) => ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status: "voorgesteld",
  bron_iri: "urn:x", vindplaats: "Artikel 9 · Lid 1" });
const groep = (id: string, leden: string[], over: Partial<Betekenisgroep> = {}): Betekenisgroep => ({
  id, aandacht: "groen", voorstel: { naam: id }, uitleg: [], conflicten: [], besluit: "open", reden: "", begrip_id: null,
  besloten_door: null, leden: leden.map((l) => lid(l)), lijkt_op: [], ...over,
});

describe("overnameVoor", () => {
  const a = groep("Ga", ["a1", "a2"]), b = groep("Gb", ["b1", "b2"]);
  it("hele groep: geen element_ids", () => {
    expect(overnameVoor([a], new Set(["a1", "a2"]), " Alfa ", true)).toEqual({ groep_ids: ["Ga"], naam: "Alfa", met_definitie: true });
  });
  it("splitsen: alleen de gekozen leden", () => {
    expect(overnameVoor([a], new Set(["a1"]), "Alfa", false).element_ids).toEqual(["a1"]);
  });
  it("combineren: beide groepen, een gekozen lid van buiten telt niet", () => {
    const o = overnameVoor([a, b], new Set(["a1", "a2", "b1", "zz"]), "Samen", true);
    expect([o.groep_ids, o.element_ids]).toEqual([["Ga", "Gb"], ["a1", "a2", "b1"]]);
  });
});

it("enigeDefinitie geeft er alleen één als er precies één is", () => {
  const met = (id: string, d: string) => groep(id, ["x"], { voorstel: { naam: id, definitie: d, definitie_vindplaats: "art. 2" } });
  const d1 = { tekst: "D1", vindplaats: "art. 2", herkomst: "letterlijk", fragmenten: [] };
  expect(enigeDefinitie([met("a", "D1")])).toEqual(d1);
  expect(enigeDefinitie([met("a", "D1"), met("b", "D1")])).toEqual(d1);
  expect(enigeDefinitie([met("a", "D1"), met("b", "D2")])).toBeNull();
  expect(enigeDefinitie([groep("c", ["y"])])).toBeNull();
});

it("groepenVanVraag zet alleen open groepen klaar", () => {
  const vraag = { kandidaat_id: "P", van: "a1", naar: "b1", regel: "", uitleg: [] };
  expect(groepenVanVraag(vraag, [groep("Ga", ["a1"]), groep("Gb", ["b1"])])).toEqual(["Ga", "Gb"]);
  expect(groepenVanVraag(vraag, [groep("Ga", ["a1"]), groep("Gb", ["b1"], { besluit: "afgewezen" })])).toEqual(["Ga"]);
  expect(groepenVanVraag(vraag, [groep("Gab", ["a1", "b1"])])).toEqual(["Gab"]);
});

it("passageTekst", () => {
  expect(passageTekst("a1", {}, [groep("G", ["a1"])])).toBe("“a1” (Artikel 9 · Lid 1)");
  expect(passageTekst("weg", {})).toBe("weg");
});

it("samenOvername neemt beide passages en de open groep van een ervan", async () => {
  const { samenOvername } = await import("./begripVoorstellen");
  const vraag = { kandidaat_id: "P", van: "a1", naar: "x", regel: "", uitleg: [] };
  const o = samenOvername(vraag, [groep("Ga", ["a1", "a2"], { voorstel: { naam: "alfa" } })], {});
  expect(o).toEqual({ groep_ids: ["Ga"], naam: "alfa", element_ids: ["a1", "a2", "x"], met_definitie: true });
  const los = samenOvername({ ...vraag, van: "y" }, [], { y: { ...lid("y", "De Aanslag") } });
  expect([los.groep_ids, los.naam, los.element_ids]).toEqual([[], "aanslag", ["y", "x"]]);
});

// --- de verdieping (fase C) ---------------------------------------------------------------------

const kaart = (over: Partial<ConceptKaart> = {}): ConceptKaart => ({
  groep_id: "G1", naam: "aanslag", alternatieve_termen: [], begripstype: "entiteit", begripstype_door: "regel",
  context: "", definitie: "", herkomst: null, definitie_bron_iri: "", definitie_vindplaats: "", fragmenten: [],
  motivatie: "", aandacht: "geel", aandachtspunten: [], ...over,
});

describe("groepDefinitie", () => {
  it("neemt de kaart vóór de letterlijke definitie van de keten", () => {
    const fr = { id: "F0123456789", bron_iri: "urn:x", start: 0, eind: 3, tekst: "abc" };
    const g = groep("G1", ["a"], { voorstel: { naam: "a", definitie: "letterlijk" },
      kaart: kaart({ definitie: "Een beschikking.", herkomst: "geformuleerd", fragmenten: [fr] }) });
    expect(groepDefinitie(g)).toEqual({ tekst: "Een beschikking.", herkomst: "geformuleerd", vindplaats: "", fragmenten: [fr] });
    expect(groepDefinitie(groep("G2", ["a"], { voorstel: { naam: "a", definitie: "D" }, kaart: kaart() }))?.herkomst)
      .toBe("letterlijk");
    expect(groepDefinitie(groep("G3", ["a"]))).toBeNull();
  });
  it("combineren geeft geen definitie als twee groepen elk een andere hebben", () => {
    const a = groep("A", ["a"], { kaart: kaart({ definitie: "X", herkomst: "samengesteld",
      fragmenten: [{ id: "F1", bron_iri: "u", start: 0, eind: 1, tekst: "X" }] }) });
    const b = groep("B", ["b"], { voorstel: { naam: "b", definitie: "X" } });
    expect(enigeDefinitie([a, b])).toBeNull();      // zelfde tekst, andere herkomst: de analist kiest
  });
});

it("openVragen toont na de verdieping alleen wat open bleef", () => {
  const v = (k: string) => ({ kandidaat_id: k, van: "a", naar: "b", regel: "Z-ANDERS", uitleg: [] });
  const data = { run: { uitkomst: { vragen: [v("P1"), v("P2")] } }, groepen: [], passages: {} } as unknown as GroepenAntwoord;
  expect(openVragen(data).map((x) => x.kandidaat_id)).toEqual(["P1", "P2"]);
  expect(openVragen({ ...data, verdieping: { vragen_open: ["P2"], oordelen: {}, model: "m" } }).map((x) => x.kandidaat_id))
    .toEqual(["P2"]);
  expect(openVragen(null)).toEqual([]);
});

it("aandachtspunten zegt 'geen definitie' niet twee keer en laat een onbekende code zien", () => {
  expect(aandachtspunten(["GEEN_DEFINITIE", "MODEL_GEEN_DEFINITIE"])).toEqual([AANDACHTSPUNT.MODEL_GEEN_DEFINITIE]);
  expect(aandachtspunten(["GEEN_DEFINITIE"])).toEqual([AANDACHTSPUNT.GEEN_DEFINITIE]);
  expect(aandachtspunten(["NIEUW_SIGNAAL"])).toEqual(["NIEUW_SIGNAAL"]);
});

it("de aandachtspunten volgen graph-qa toetsen.TEKST, code voor code en woord voor woord", () => {
  const bron = readFileSync(resolve(__dirname, "../../tools/graph-qa/agent/begrippen_pipeline/toetsen.py"), "utf8");
  const tabel = bron.slice(bron.indexOf("TEKST: dict"), bron.indexOf("GARANTIES ="));
  const daar = Object.fromEntries([...tabel.matchAll(/"([A-Z_]+)": "([^"]+)"/g)].map((m) => [m[1], m[2]]));
  expect(AANDACHTSPUNT).toEqual(daar);
});

// --- het akkoord (fase D) ------------------------------------------------------------------------

const vraag = (kid: string, van: string, naar: string) => ({ kandidaat_id: kid, van, naar, regel: "", uitleg: [] });

it("akkoordLabel zegt vooraf of het een concept blijft", () => {
  expect(akkoordLabel(groep("G", ["a"], { poort_vooraf: { mag: true, redenen: [] } })).label).toBe("Akkoord");
  const l = akkoordLabel(groep("G", ["a"], { poort_vooraf: { mag: false, redenen: ["Er is nog geen definitie."] } }));
  expect([l.label, l.concept]).toEqual(["Akkoord als concept (1 open punt)", true]);
});

describe("akkoordVoor en samenAkkoord", () => {
  const a = groep("Ga", ["a1", "a2"]), b = groep("Gb", ["b1"]);
  it("hele groep, zonder lege aanpassing", () => {
    expect(akkoordVoor([a], new Set(["a1", "a2"]), "Alfa", { aanpassing: {} }))
      .toEqual({ groep_ids: ["Ga"], naam: "Alfa", met_definitie: true });
  });
  it("splitsen, aanpassing en de gekozen definitie bij combineren", () => {
    expect(akkoordVoor([a, b], new Set(["a1", "b1"]), "Samen", { aanpassing: { context: "X" }, definitieVan: "Gb" }))
      .toEqual({ groep_ids: ["Ga", "Gb"], naam: "Samen", element_ids: ["a1", "b1"], met_definitie: true,
        aanpassing: { context: "X" }, definitie_van: "Gb" });
  });
  it("samen bij een vraag beantwoordt die vraag", () => {
    const uit = samenAkkoord(vraag("P1", "a1", "z9"), [a], {}, " Alfa ");
    expect([uit.groep_ids, uit.element_ids, uit.naam, uit.kandidaat_id]).toEqual([["Ga"], ["a1", "a2", "z9"], "Alfa", "P1"]);
  });
});

describe("aanpassingUit en herkomstNaAanpassing", () => {
  const voorstel = { definitie: "de eerste", herkomst: "letterlijk" as const, context: "", begripstype: "" as const };
  it("ongewijzigd is geen aanpassing", () => {
    expect(aanpassingUit(voorstel, { ...voorstel, herkomst: null })).toEqual({});
  });
  it("alleen wat veranderde gaat mee", () => {
    expect(aanpassingUit(voorstel, { ...voorstel, herkomst: null, definitie: "de tweede", begripstype: "actor" }))
      .toEqual({ definitie: "de tweede", begripstype: "actor" });
  });
  it("een gekozen herkomst neemt de tekst mee", () => {
    expect(aanpassingUit(voorstel, { ...voorstel, herkomst: "geformuleerd" })).toEqual({ definitie: "de eerste", definitie_herkomst: "geformuleerd" });
  });
  it("een andere tekst is geformuleerd, tenzij letterlijk gekozen", () => {
    const oud = { tekst: "de eerste", herkomst: "letterlijk" as const };
    expect(herkomstNaAanpassing(oud, "de eerste", null)).toBe("letterlijk");
    expect(herkomstNaAanpassing(oud, "de tweede", null)).toBe("geformuleerd");
    expect(herkomstNaAanpassing(oud, "de tweede", "letterlijk")).toBe("letterlijk");
    expect(herkomstNaAanpassing(oud, " ", null)).toBeNull();
    expect(herkomstNaAanpassing({ tekst: "", herkomst: null }, "eigen", null)).toBe("geformuleerd");
  });
});
