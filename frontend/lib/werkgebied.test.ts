import { describe, expect, it } from "vitest";

import type { InventarisElement, InventarisSelectie, WerkgebiedAuditRegel } from "./types";
import {
  annotatieHref,
  auditZin,
  bronInvoer,
  filterElementen,
  groepeerPerSelectie,
  isAlOpgenomen,
  isRevisieConflict,
  klasseTelling,
  voortgang,
} from "./werkgebied";

const sel = (id: string, rol: "analyseren" | "context" = "analyseren"): InventarisSelectie => ({
  id, bron_iri: `urn:bwb:BWBR0004770:${id}`, label: `Artikel ${id}`, rol, bereik: "onderliggend",
  aantal: 0, afgewezen: 0, bron_gewijzigd: false, onbereikbaar: null,
});
const el = (id: string, selecties: string[], over: Partial<InventarisElement> = {}): InventarisElement => ({
  id, klasse: "Rechtssubject", tekst: id, lifecycle: "voorgesteld", eigenaar_iri: "urn:x", laag_id: "l",
  ankers: [], rol: "analyseren", selecties, deels_buiten: false, ...over,
});

describe("bronInvoer", () => {
  it("leest regeling + artikel + lid, ook met de woorden ervoor", () => {
    expect(bronInvoer({ regeling: " bwbr0004770 ", artikel: "Artikel 9", lid: "lid 2" }))
      .toEqual({ invoer: { bwb_id: "BWBR0004770", artikel: "9", lid: "2" } });
    expect(bronInvoer({ regeling: "BWBR0004770", artikel: "art. 3:1", lid: "" }))
      .toEqual({ invoer: { bwb_id: "BWBR0004770", artikel: "3:1" } });
  });

  it("neemt een graaf-IRI als bron-IRI, maar niet samen met een artikel", () => {
    expect(bronInvoer({ regeling: "urn:bwb:BWBR0004770:art9", artikel: "", lid: "" }))
      .toEqual({ invoer: { bron_iri: "urn:bwb:BWBR0004770:art9" } });
    expect(bronInvoer({ regeling: "urn:bwb:BWBR0004770:art9", artikel: "9", lid: "" })).toHaveProperty("fout");
  });

  it("weigert wat zonder graaf al fout is", () => {
    expect(bronInvoer({ regeling: "Invorderingswet", artikel: "9", lid: "" })).toHaveProperty("fout");
    expect(bronInvoer({ regeling: "BWBR0004770", artikel: "  ", lid: "" })).toHaveProperty("fout");
  });
});

describe("groepeerPerSelectie", () => {
  it("zet elk element één keer neer, onder de eerste selectie die het dekt", () => {
    const groepen = groepeerPerSelectie([sel("a"), sel("b")], [el("e1", ["b", "a"]), el("e2", ["b"])]);
    expect(groepen.map((g) => [g.selectie.id, g.elementen.map((e) => e.id)]))
      .toEqual([["a", ["e1"]], ["b", ["e2"]]]);
  });

  it("laat een element zonder bekende selectie weg in plaats van te crashen", () => {
    expect(groepeerPerSelectie([sel("a")], [el("e1", ["weg"])])[0].elementen).toEqual([]);
  });
});

describe("filter, telling en voortgang", () => {
  const els = [
    el("ontvanger", ["a"]),
    el("aanslag", ["a"], { klasse: "Rechtsobject", lifecycle: "human_approved" }),
    el("definitie", ["c"], { klasse: "Brondefinitie", rol: "context", toelichting: "begrip ontvanger" }),
    el("zonder", ["a"], { klasse: "", lifecycle: "reused" }),
  ];

  it("filtert op rol, klasse en zoekterm (ook in de toelichting)", () => {
    expect(filterElementen(els, { rol: "context", klasse: "alle", term: "" }).map((e) => e.id)).toEqual(["definitie"]);
    expect(filterElementen(els, { rol: "alle", klasse: "Rechtsobject", term: "" }).map((e) => e.id)).toEqual(["aanslag"]);
    expect(filterElementen(els, { rol: "alle", klasse: "alle", term: "ONTVANGER" }).map((e) => e.id))
      .toEqual(["ontvanger", "definitie"]);
    expect(filterElementen(els, { rol: "alle", klasse: "Nog geen klasse", term: "" }).map((e) => e.id)).toEqual(["zonder"]);
  });

  it("telt per klasse in de JAS-volgorde, met de terugval achteraan", () => {
    expect(klasseTelling(els).map((t) => t.klasse))
      .toEqual(["Rechtssubject", "Rechtsobject", "Brondefinitie", "Nog geen klasse"]);
  });

  it("rekent alleen de werkvoorraad, en hergebruik is geen oordeel", () => {
    expect(voortgang(els)).toEqual({ totaal: 3, beoordeeld: 1 });
  });
});

describe("foutherkenning", () => {
  it("herkent het revisieconflict en de dubbele bron aan status én fout", () => {
    expect(isRevisieConflict({ status: 412, detail: "x", data: { fout: "revisie_conflict", revisie: 4 } })).toBe(true);
    expect(isRevisieConflict({ status: 412, detail: "x" })).toBe(false);
    expect(isAlOpgenomen({ status: 409, detail: "x", data: { fout: "al_opgenomen" } })).toBe(true);
    expect(isAlOpgenomen(new Error("409"))).toBe(false);
  });
});

describe("auditZin", () => {
  const regel = (actie: string, detail: Record<string, unknown>): WerkgebiedAuditRegel =>
    ({ id: 1, actor: "jurist", actie, detail, tijdstip: "2026-10-15T10:00:00+00:00" });
  const labels = new Map([["urn:bwb:a", "Invorderingswet 1990 – artikel 9"]]);

  it("noemt de bron bij naam als die bekend is, anders de IRI", () => {
    expect(auditZin(regel("bron-toegevoegd", { bron_iri: "urn:bwb:a", rol: "context" }), labels))
      .toBe("Invorderingswet 1990 – artikel 9 opgenomen als contextbron");
    expect(auditZin(regel("bron-verwijderd", { bron_iri: "urn:bwb:weg" }), labels))
      .toBe("urn:bwb:weg uit het werkgebied gehaald");
  });

  it("somt gewijzigde velden op, en een onbekende actie blijft leesbaar", () => {
    expect(auditZin(regel("gewijzigd", { velden: ["naam", "status"] }), labels)).toBe("Gewijzigd: naam, status");
    expect(auditZin(regel("iets-nieuws", {}), labels)).toBe("iets-nieuws");
  });
});

it("annotatieHref codeert de IRI als query-parameter", () => {
  expect(annotatieHref("urn:bwb:BWBR0004770:a#1")).toBe("/annotaties/node?bron_iri=urn%3Abwb%3ABWBR0004770%3Aa%231");
});

it("tabUitParam valt terug op Bronnen", async () => {
  const { tabUitParam } = await import("./werkgebied");
  expect(tabUitParam("elementen")).toBe("elementen");
  expect(tabUitParam(undefined)).toBe("bronnen");
  expect(tabUitParam("begrippen")).toBe("begrippen");
  expect(tabUitParam("onbekend")).toBe("bronnen");
});

describe("scopeInModel", async () => {
  const { bouwModel } = await import("./graaf/model");
  const { scopeInModel } = await import("./werkgebied");
  const k = (id: string, soort: string, over: Record<string, unknown> = {}) => ({
    id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR1", artikel: "", lid: "",
    rand: false, ...over,
  });
  const r = (bron: string, soort: string, doel: string) => ({ bron, soort, doel, groep: "structuur", anker_tekst: "" });
  const g = bouwModel([{
    knopen: [
      k("reg", "regeling", { label: "Invorderingswet 1990" }), k("h1", "deel"), k("a9", "artikel"), k("a9l1", "lid"),
      k("a9l2", "lid"), k("a10", "artikel", { rand: true }), k("a11", "artikel", { rand: true }),
      k("awr3", "artikel", { rand: true, bwb_id: "BWBR2" }), k("x", "extern", { rand: true, bwb_id: "" }),
    ] as never,
    relaties: [
      r("reg", "bevat", "h1"), r("h1", "bevat", "a9"), r("a9", "bevat", "a9l1"), r("a9", "bevat", "a9l2"),
      r("a9l1", "verwijst_naar", "a10"), r("a9l2", "verwijst_naar", "a10"), r("a9l2", "verwijst_naar", "awr3"),
      r("a9l1", "verwijst_naar", "a9l2"), r("a9l1", "verwijst_naar", "h1"), r("a9l2", "verwijst_naar", "x"),
      r("a11", "verwijst_naar", "a10"),
    ] as never,
  }]);

  it("dekt bij `onderliggend` alles eronder, bij `node` alleen de knoop", () => {
    expect([...scopeInModel(g, [{ bron_iri: "a9", bereik: "onderliggend" }])].sort()).toEqual(["a9", "a9l1", "a9l2"]);
    expect([...scopeInModel(g, [{ bron_iri: "a9", bereik: "node" }])]).toEqual(["a9"]);
  });
});

describe("isWerkgebiedRoute", async () => {
  const { isWerkgebiedRoute } = await import("./werkgebied");
  it.each([
    [["w"]], [["w", "bronnen"]], [["w", "bronnen", "s"]], [["w", "elementen"]], [["w", "audit"]],
    [["w", "begrippen"]], [["w", "begrippen", "export"]], [["w", "begrippen", "b"]],
    [["w", "begrippen", "b", "koppelingen"]], [["w", "begrippen", "b", "accorderen"]],
    [["w", "begrippen", "b", "heropenen"]], [["w", "begrippen", "b", "revisies"]],
    [["w", "begrippen", "b", "koppelingen", "k"]],
    [["w", "begrippen-runs", "laatste"]], [["w", "begrippen-runs", "r"]], [["w", "begrippen-runs", "r", "vragen", "P1"]],
    [["w", "groepen"]], [["w", "groepen", "overnemen"]], [["w", "groepen", "akkoord"]], [["w", "groepen", "G1", "koppelen"]],
    [["w", "groepen", "G1", "afwijzen"]], [["w", "groepen", "G1", "parkeren"]], [["w", "groepen", "G1", "heropenen"]],
    [["w", "bronnen-runs", "laatste"]], [["w", "bronnen-runs", "r"]], [["w", "kandidaten"]],
    [["w", "kandidaten", "K1", "opnemen"]], [["w", "kandidaten", "K1", "later"]],
    [["w", "kandidaten", "K1", "uitsluiten"]], [["w", "kandidaten", "K1", "heropenen"]],
    [["w", "annotatie-werkvoorraad"]], [["w", "verdieping"]],
    // Lex naast de kaart (fase E): voorstellen lezen en besluiten.
    [["w", "begrippen", "b", "voorstellen"]], [["w", "begrippen", "b", "voorstellen", "v", "overnemen"]],
    [["w", "begrippen", "b", "voorstellen", "v", "afwijzen"]],
    // Onderhoud (fase F1): herbeoordelen, herkoppelen, bevestigen en de dekking.
    [["w", "herbeoordelingen"]], [["w", "begrippen", "b", "koppelingen", "k", "herkoppelen"]],
    [["w", "begrippen", "b", "koppelingen", "k", "bevestigen"]], [["w", "dekking"]],
    [["w", "dekking", "buiten-behandeling"]], [["w", "dekking", "buiten-behandeling", "e"]],
  ])("laat %j door", (pad) => expect(isWerkgebiedRoute(pad)).toBe(true));
  it.each([
    [[]], [["w", "onbekend"]], [["w", "elementen", "x"]], [["w", "bronnen", "s", "x"]],
    [["w", "begrippen", "export", "x"]], [["w", "begrippen", "b", "iets"]],
    [["w", "begrippen", "b", "accorderen", "x"]], [["w", "begrippen", "b", "koppelingen", "k", "x"]],
    // Alleen graph-qa schrijft de uitkomst; starten gaat via /api/begrippen-run.
    [["w", "begrippen-runs"]], [["w", "begrippen-runs", "r", "uitkomst"]], [["w", "begrippen-runs", "r", "loopt"]],
    [["w", "begrippen-runs", "r", "mislukt"]], [["w", "begrippen-runs", "r", "vragen"]],
    [["w", "groepen", "G1"]], [["w", "groepen", "G1", "verwijderen"]], [["w", "groepen", "overnemen", "x"]], [["w", "groepen", "akkoord", "x"]],
    // Ook bij de bronnen: starten via /api/bronnen-run, de rest is van graph-qa.
    [["w", "bronnen-runs"]], [["w", "bronnen-runs", "r", "uitkomst"]], [["w", "bronnen-runs", "r", "loopt"]],
    [["w", "bronnen-runs", "r", "mislukt"]], [["w", "kandidaten", "K1"]], [["w", "kandidaten", "K1", "wissen"]],
    [["w", "annotatie-werkvoorraad", "x"]],
    // De verdieping (fase C): lezen mag, de batches en de uitkomst zijn van graph-qa.
    [["w", "verdieping", "x"]], [["w", "begrippen-runs", "r", "batches", "B1"]], [["w", "begrippen-runs", "r", "verdieping"]],
    // Een kaartrun start alleen via /api/kaart-run; de run zelf (met invoer) en zijn uitkomst zijn van graph-qa.
    [["w", "begrippen", "b", "kaart-runs"]], [["w", "begrippen", "b", "kaart-runs", "r"]],
    [["w", "begrippen", "b", "kaart-runs", "r", "uitkomst"]], [["w", "begrippen", "b", "kaart-runs", "r", "loopt"]],
    [["w", "begrippen", "b", "voorstellen", "v"]], [["w", "begrippen", "b", "voorstellen", "v", "wissen"]],
    [["w", "begrippen", "b", "voorstellen", "v", "overnemen", "x"]], [["w", "begrippen", "b", "koppelingen", "k", "x", "y"]],
    [["w", "herbeoordelingen", "x"]], [["w", "dekking", "x"]], [["w", "dekking", "buiten-behandeling", "e", "x"]],
    [["w", "begrippen", "b", "koppelingen", "k", "wissen"]], [["w", "begrippen", "b", "voorstellen", "v", "herkoppelen"]],
  ])("weigert %j", (pad) => expect(isWerkgebiedRoute(pad)).toBe(false));
});

it("auditZin noemt een begrip bij naam", async () => {
  const { auditZin } = await import("./werkgebied");
  const r = (actie: string, detail: Record<string, unknown>) => ({ id: 1, actor: "a", actie, detail, tijdstip: "" });
  expect(auditZin(r("begrip-aangemaakt", { naam: "Ontvanger", element_ids: ["x"] }), new Map()))
    .toBe('Begrip "Ontvanger": aangemaakt (1 passage)');
  expect(auditZin(r("begrip-geaccordeerd", { begrip_id: "b1" }), new Map(), new Map([["b1", "Aanslag"]])))
    .toBe('Begrip "Aanslag": geaccordeerd');
  expect(auditZin(r("koppeling-verwijderd", { begrip_id: "weg" }), new Map())).toBe("Een begrip: passage losgemaakt");
});

it("auditZin noemt het besluit over een voorstel van Lex", async () => {
  const { auditZin } = await import("./werkgebied");
  const r = (actie: string, detail: Record<string, unknown>) => ({ id: 1, actor: "a", actie, detail, tijdstip: "" });
  const namen = new Map([["b1", "Aanslag"]]);
  expect(auditZin(r("groep-akkoord", { begrip_id: "b1", geaccordeerd: true }), new Map(), namen))
    .toBe('Akkoord op een voorstel van Lex: begrip "Aanslag" geaccordeerd');
  expect(auditZin(r("groep-akkoord", { begrip_id: "b1", geaccordeerd: false, deels: ["G1"] }), new Map(), namen))
    .toBe('Akkoord op een voorstel van Lex: begrip "Aanslag", nog een concept (een deel van de passages)');
  expect(auditZin(r("groep-afgewezen", { reden: "andere betekenis" }), new Map()))
    .toBe("Voorstel van Lex afgewezen – andere betekenis");
});

it("annotatieHref neemt het element mee", async () => {
  const { annotatieHref } = await import("./werkgebied");
  expect(annotatieHref("urn:x", "e1")).toBe("/annotaties/node?bron_iri=urn%3Ax&element=e1");
});
