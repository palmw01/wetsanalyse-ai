import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AANDACHTSPUNT, aandachtspunten, aanpassingUit, akkoordLabel, akkoordVoor, enigeDefinitie, groepDefinitie,
  groepenVanVraag, herkomstNaAanpassing, meedenkInhoud, meedenkOmvang, naBesluit, onbeoordeeldeAnnotaties, openVragen,
  overnameVoor, passageTekst, reviewItems, reviewVoortgang, samenAkkoord, sorteerGroepen, vergelijk, volgendeItem,
  voortgangsregel,
} from "./begripVoorstellen";
import type { Begrip, Betekenisgroep, ConceptKaart, GroepenAntwoord, Koppeling, VerdiepingWerkvoorraad } from "./types";

const lid = (id: string, tekst = id) => ({ element_id: id, tekst, jas_klasse: "Rechtssubject", review_status: "voorgesteld",
  bron_iri: "urn:x", vindplaats: "Artikel 9 · Lid 1" });
const groep = (id: string, leden: string[], over: Partial<Betekenisgroep> = {}): Betekenisgroep => ({
  id, aandacht: "groen", voorstel: { naam: id }, uitleg: [], conflicten: [], besluit: "open", reden: "", begrip_id: null,
  besloten_door: null, leden: leden.map((l) => lid(l)), lijkt_op: [], ...over,
});

describe("sorteerGroepen", () => {
  it("open vóór geparkeerd vóór besloten; geel vóór groen; meer leden eerst", () => {
    const uit = sorteerGroepen([
      groep("klaar", ["a", "b"], { besluit: "overgenomen" }),
      groep("park", ["c", "d"], { besluit: "geparkeerd" }),
      groep("groen2", ["e", "f"]),
      groep("groen3", ["g", "h", "i"]),
      groep("geel", ["j", "k"], { aandacht: "geel" }),
    ]);
    expect(uit.map((g) => g.id)).toEqual(["geel", "groen3", "groen2", "park", "klaar"]);
  });
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

it("passageTekst en voortgangsregel", () => {
  expect(passageTekst("a1", {}, [groep("G", ["a1"])])).toBe("“a1” (Artikel 9 · Lid 1)");
  expect(passageTekst("weg", {})).toBe("weg");
  expect(voortgangsregel("Lex · Groeperen: 3 groepen (12 ms)")).toBe("Groeperen: 3 groepen (12 ms)");
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

describe("meedenkInhoud", () => {
  const wv = (over: Partial<VerdiepingWerkvoorraad> = {}): VerdiepingWerkvoorraad => ({
    run: null, verdiept: false, aantal: 3, vragen: ["P1"], kaarten: ["G1", "G2"], batches: [],
    schatting: { per_item: 1000, basis: 4, totaal: 3000 }, schatting_toelichting: "uitleg",
    budget: { resterend: 2000, budget: 10000, actief: true, geblokkeerd: false }, ...over,
  });
  it("noemt omvang, schatting en een krap budget", () => {
    const i = meedenkInhoud(wv());
    expect(i).toMatchObject({ aantal: 3, vragen: 1, kaarten: 2, alKlaar: 0, schatting: 3000, budgetOver: 2000, budgetKrap: true });
    expect(meedenkOmvang(i)).toBe("1 twijfelpunt en 2 begrippen zonder definitie");
  });
  it("zonder geschiedenis of limiet geen getal en geen waarschuwing", () => {
    const i = meedenkInhoud(wv({ schatting: null, budget: { resterend: 0, budget: 0, actief: false, geblokkeerd: false } }));
    expect([i.schatting, i.budgetOver, i.budgetKrap]).toEqual([null, null, false]);
    expect(meedenkOmvang({ vragen: 2, kaarten: 0 })).toBe("2 twijfelpunten");
  });
});

// --- de review (fase D) ------------------------------------------------------------------------

const vraag = (kid: string, van: string, naar: string) => ({ kandidaat_id: kid, van, naar, regel: "", uitleg: [] });
const antwoord = (groepen: Betekenisgroep[], vragen = [vraag("P1", "a1", "z1")], besluiten = {}): GroepenAntwoord => ({
  run: { id: "r", werkgebied_id: "w", manifest_id: "m", status: "klaar", reden: "", overgeslagen: [], aantal_formuleringen: 9,
    uitkomst: { groep_ids: groepen.map((g) => g.id), relaties: [], vragen }, vragen_besluiten: besluiten,
    gestart_door: "a", gestart: "", gewijzigd: "" } as unknown as GroepenAntwoord["run"],
  groepen, passages: {}, verdieping: null,
});

describe("reviewItems en reviewVoortgang", () => {
  const groepen = [groep("Ggroen", ["a1", "a2"]), groep("Ggeel", ["b1", "b2"], { aandacht: "geel" }),
    groep("Gpark", ["c1", "c2"], { besluit: "geparkeerd" }), groep("Gklaar", ["d1", "d2"], { besluit: "overgenomen" })];
  const data = antwoord(groepen, [vraag("P1", "a1", "z1"), vraag("P2", "b1", "z2")],
    { P2: { antwoord: "apart", door: "a", op: "" } });
  it("te beoordelen: geel, dan de open vragen, dan groen – zonder besluiten", () => {
    expect(reviewItems(data, "te_beoordelen").map((i) => i.id)).toEqual(["Ggeel", "P1", "Ggroen"]);
  });
  it("aandacht: alleen geel en de vragen", () => {
    expect(reviewItems(data, "aandacht").map((i) => i.id)).toEqual(["Ggeel", "P1"]);
  });
  it("alles: daarna de besluiten en de beantwoorde vragen", () => {
    expect(reviewItems(data, "alles").map((i) => i.id)).toEqual(["Ggeel", "P1", "Ggroen", "Gpark", "Gklaar", "P2"]);
  });
  it("voortgang telt groepen en vragen; parkeren is een besluit", () => {
    expect(reviewVoortgang(data)).toEqual({ totaal: 6, beslist: 3, aandacht: 2 });
  });
});

it("volgendeItem en naBesluit lopen de getoonde volgorde door", () => {
  const items = reviewItems(antwoord([groep("Ga", ["a"]), groep("Gb", ["b"]), groep("Gc", ["c"])], []), "te_beoordelen");
  expect(volgendeItem(items, undefined, 1)?.id).toBe("Ga");
  expect(volgendeItem(items, undefined, -1)?.id).toBe("Gc");
  expect(volgendeItem(items, "Ga", 1)?.id).toBe("Gb");
  expect(volgendeItem(items, "Gc", 1)).toBeUndefined();
  const na = items.filter((i) => i.id !== "Gb");
  expect(naBesluit(items, "Gb", na)).toBe("Gc");
  expect(naBesluit(items, "Gc", items.filter((i) => i.id !== "Gc"))).toBe("Ga");
});

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

it("vergelijk noemt de signalen tegen combineren", () => {
  const met = (id: string, def: string, klasse: string, type: ConceptKaart["begripstype"]) => groep(id, ["x"], {
    voorstel: { naam: id, definitie: def }, conflicten: id === "Gb" ? ["X"] : [],
    leden: [{ ...lid(`${id}1`), jas_klasse: klasse }],
    kaart: { begripstype: type } as ConceptKaart,
  });
  const v = vergelijk([met("Ga", "D1", "Rechtssubject", "actor"), met("Gb", "D2", "Rechtsobject", "entiteit")]);
  expect(v.metDefinitie).toEqual(["Ga", "Gb"]);
  expect(v.signalen).toHaveLength(4);
  expect(v.signalen[0]).toContain("actor");
  expect(vergelijk([met("Ga", "D1", "Rechtssubject", "actor"), met("Gc", "", "Rechtssubject", "actor")]).signalen).toEqual([]);
});

it("onbeoordeeldeAnnotaties: alleen actuele, dragende, niet afgewezen koppelingen zonder oordeel van een jurist", () => {
  const k = (id: string, over: Partial<Koppeling>) => ({ id, rol: "duiding", beoordeling: "akkoord", actualiteit: "actueel",
    annotatie_beoordeeld: false, ...over }) as Koppeling;
  const b = { koppelingen: [k("1", {}), k("2", { annotatie_beoordeeld: true }), k("3", { rol: "context" }),
    k("4", { actualiteit: "gewijzigd" }), k("5", { beoordeling: "afgewezen" }), k("6", { rol: "definitie" })] } as Begrip;
  expect(onbeoordeeldeAnnotaties(b).map((x) => x.id)).toEqual(["1", "6"]);
});
