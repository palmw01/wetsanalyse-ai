import { describe, expect, it } from "vitest";

import {
  bewijsZin, bijDeelvraag, filterVan, plekNaam, sorteerKandidaten, standaardRol, telPerFilter,
} from "./bronKandidaten";
import type { BronKandidaat } from "./types";

const L1 = "urn:bwb:BWBR0004770:artikel:9:lid:1";

const k = (over: Partial<BronKandidaat>): BronKandidaat => ({
  id: "K", bron_iri: "urn:bwb:BWBR0004770:artikel:8", label: "Artikel 8", bwb_id: "BWBR0004770", rol: "aanverwant",
  bewijs: [{ methode: "opbouw", vanuit: L1, detail: {} }], status: "voorgesteld", reden: "", run_id: "r",
  in_laatste_run: true, in_selectie: false, besloten_door: null, besloten_op: null, ...over,
});

describe("bewijsZin", () => {
  it("noemt de verwijzing, haar anker en haar functie", () => {
    expect(bewijsZin({ methode: "verwijzing_uit", vanuit: L1, detail: { anker: "artikel 8", functie: "uitzondering" } }))
      .toBe("verwezen vanuit Artikel 9, lid 1 (“artikel 8”) – uitzondering");
    expect(bewijsZin({ methode: "verwijzing_uit", vanuit: L1, detail: { functie: "onbekend" } }))
      .toBe("verwezen vanuit Artikel 9, lid 1 – functie onbekend");
  });

  it("gebruikt de naam van een selectie als die er is", () => {
    const labels = new Map([[L1, "IW 1990 – art. 9 lid 1"]]);
    expect(bewijsZin({ methode: "opbouw", vanuit: L1, detail: {} }, labels)).toBe("staat in hetzelfde deel als IW 1990 – art. 9 lid 1");
  });

  it("noemt het begrip en het onderwerp", () => {
    expect(bewijsZin({ methode: "definitie", vanuit: L1, detail: { begrip: "belastingaanslag" } }))
      .toBe("definieert “belastingaanslag”, dat in Artikel 9, lid 1 staat");
    expect(bewijsZin({ methode: "overzicht", vanuit: "", detail: { onderwerp: "invorderbaar" } }))
      .toBe("in het overzicht op “invorderbaar”");
    expect(bewijsZin({ methode: "gelijkenis", vanuit: L1, detail: {} })).toMatch(/zwak signaal/);
    expect(bewijsZin({ methode: "deelvraag", vanuit: "", detail: { deelvraag_id: "d1", vraag: "Wie betaalt?" } }))
      .toBe("gevonden bij de deelvraag “Wie betaalt?”");
  });
});

describe("filters", () => {
  it("met de hand opgenomen telt als opgenomen", () => {
    expect(filterVan(k({}))).toBe("open");
    expect(filterVan(k({ in_selectie: true }))).toBe("opgenomen");
    expect(filterVan(k({ status: "uitgesloten" }))).toBe("uitgesloten");
    expect(telPerFilter([k({}), k({ status: "later" }), k({ status: "opgenomen" })]))
      .toEqual({ open: 1, later: 1, uitgesloten: 0, opgenomen: 1 });
  });
});

it("standaardRol: kern wordt analyseren, de rest context", () => {
  expect(standaardRol({ rol: "kern" })).toBe("analyseren");
  expect(standaardRol({ rol: "afhankelijkheid" })).toBe("context");
});

it("sorteert op rol, dan op hoeveelheid bewijs", () => {
  const a = k({ id: "a", rol: "aanverwant", bewijs: [] , label: "A" });
  const b = k({ id: "b", rol: "kern", label: "B" });
  const c = k({ id: "c", rol: "aanverwant", label: "C", bewijs: [{ methode: "opbouw", vanuit: "", detail: {} }, { methode: "verwijzing_in", vanuit: "", detail: {} }] });
  expect(sorteerKandidaten([a, c, b]).map((x) => x.id)).toEqual(["b", "c", "a"]);
});

it("plekNaam valt terug op het pad na de regeling", () => {
  expect(plekNaam("urn:bwb:BWBR0024096:id:abc")).toBe("abc");
  expect(plekNaam("urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1")).toBe("divisie 9.1");
  expect(plekNaam("")).toBe("");
});

it("een kandidaat hoort bij de deelvraag die zijn bewijs noemt", () => {
  const k = { bewijs: [{ methode: "deelvraag" as const, vanuit: "", detail: { deelvraag_id: "d1", vraag: "Wie?" } }] };
  expect(bijDeelvraag(k, "d1")).toBe(true);
  expect(bijDeelvraag(k, "d2")).toBe(false);
  expect(bijDeelvraag({ bewijs: [{ methode: "opbouw" as const, vanuit: "", detail: {} }] }, "d1")).toBe(false);
});

describe("bewijsSamenvatting", () => {
  it("telt herhalingen per methode en houdt één bewijs letterlijk", async () => {
    const { bewijsSamenvatting } = await import("./bronKandidaten");
    const uit = (vanuit: string) => ({ methode: "verwijzing_uit" as const, vanuit, detail: { functie: "toepassing" } });
    expect(bewijsSamenvatting([uit("a"), uit("b"), uit("c"),
      { methode: "definitie", vanuit: "", detail: { begrip: "rijksbelastingen" } }]))
      .toBe("3× verwezen vanuit de kern · definieert “rijksbelastingen”");
    expect(bewijsSamenvatting([uit("urn:bwb:BWBR0004770:artikel:9:lid:1")])).toMatch(/^verwezen vanuit Artikel 9, lid 1/);
    expect(bewijsSamenvatting([
      { methode: "deelvraag", vanuit: "", detail: { deelvraag_id: "d1" } },
      { methode: "deelvraag", vanuit: "", detail: { deelvraag_id: "d2" } }])).toBe("gevonden bij 2 deelvragen");
  });
});

describe("metLeesbareBronnen", () => {
  it("vervangt ruwe IRI's door hun plek en laat de rest staan", async () => {
    const { metLeesbareBronnen } = await import("./bronKandidaten");
    expect(metLeesbareBronnen("Bepalingen: urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.3.9 – Leidraad Invordering 2008, Artikel 22"))
      .toBe("Bepalingen: divisie 26.3.9 – Leidraad Invordering 2008, Artikel 22");
    expect(metLeesbareBronnen("zie urn:bwb:BWBR0004770:artikel:9:lid:1.")).toBe("zie Artikel 9, lid 1.");
  });
});
