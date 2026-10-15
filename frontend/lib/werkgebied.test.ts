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
  expect(tabUitParam("begrippen")).toBe("bronnen");
});
