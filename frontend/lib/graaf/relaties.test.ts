// Relaties tussen markeringen en impliciete partijen in de graaf (ADR-011, stap 4B): stijl, laag, diagrammodus en
// layout. Alleen wat de api levert; de graaf leidt niets af.
import { describe, expect, it } from "vitest";
import type { Samenhang, SamenhangKnoop, SamenhangRelatie } from "@/lib/samenhang";
import { relatieGroepen, SOORT_LABEL } from "./bediening";
import { plaatsAnnotaties, structuurVan, type Posities } from "./layout";
import { bouwModel, isBron, type GraafBron } from "./model";
import { eigenKleur, IMPLICIET_VULLING, klasseKleur, RELATIEKLEUR, relatieStijl, VOORSTELKLEUR } from "./stijl";
import {
  diagramBuurt, knoopBeeld, lagenVoor, lijnBeeld, STANDAARD_LAGEN, verborgenKnopen, weergaveContext, type WeergaveStand,
} from "./weergave";

const A9 = "urn:bwb:BWBR0004770:artikel:9", L1 = `${A9}:lid:1`, L2 = `${A9}:lid:2`;

function knoop(id: string, soort: SamenhangKnoop["soort"], extra: Partial<SamenhangKnoop> = {}): SamenhangKnoop {
  return { id, soort, label: id, tekst: "", klasse: "", lifecycle: "", element_id: "", bwb_id: "BWBR0004770", artikel: "9", lid: "",
    rand: false, ...extra };
}
const m = (id: string, klasse: string) => knoop(`element:${id}`, "markering", { klasse, element_id: id, label: id });
const bevat = (bron: string, doel: string): SamenhangRelatie => ({ bron, doel, soort: "bevat", groep: "structuur", anker_tekst: "" });
const markeert = (id: string, lid: string): SamenhangRelatie => ({ bron: `element:${id}`, doel: lid, soort: "markeert", groep: "annotaties", anker_tekst: "" });
const relatie = (bron: string, doel: string, type: string, lifecycle = "human_approved", extra: Partial<SamenhangRelatie> = {}): SamenhangRelatie => ({
  bron, doel, soort: "jas_relatie", groep: "relaties", anker_tekst: `is ${type} van`, type, leesvorm: `is ${type} van`, lifecycle,
  veranderd: false, volgorde: null, ...extra,
});

/** Een rechtsbetrekking (zin) met een plichthebbende (ontvanger), een voorwerp (aanslag) en een voorwaarde
 *  (termijn) in lid 2; aan de voorwaarde hangt weer een tijdsaanduiding (dag), en verder nog een rechtsobject (ver)
 *  dat op drie stappen ligt. De belastingschuldige is een impliciete partij. */
const BRON: GraafBron = {
  knopen: [
    knoop(A9, "artikel"), knoop(L1, "lid", { lid: "1" }), knoop(L2, "lid", { lid: "2" }),
    m("zin", "Rechtsbetrekking"), m("ontvanger", "Rechtssubject"), m("aanslag", "Rechtsobject"), m("termijn", "Voorwaarde"),
    m("dag", "Tijdsaanduiding"), m("ver", "Rechtsobject"), m("los", "Rechtssubject"),
    knoop("impliciet:I1", "impliciet", { klasse: "Rechtssubject", label: "de belastingschuldige", toelichting: "volgt uit de aanslag" }),
  ],
  relaties: [
    bevat(A9, L1), bevat(A9, L2),
    markeert("zin", L1), markeert("ontvanger", L1), markeert("aanslag", L1), markeert("termijn", L2), markeert("dag", L2),
    markeert("ver", L2), markeert("los", L2),
    relatie("element:ontvanger", "element:zin", "plichthebbende"),
    relatie("element:zin", "element:aanslag", "voorwerp", "voorgesteld"),
    relatie("element:zin", "element:termijn", "voorwaarde"),
    relatie("element:termijn", "element:dag", "tijd"),
    relatie("element:dag", "element:ver", "kenmerk"),
    relatie("impliciet:I1", "element:zin", "rechthebbende"),
    relatie("element:los", "element:zin", "rechthebbende", "rejected"),
  ],
};
const g = bouwModel([BRON]);
const stand = (s: Partial<WeergaveStand> = {}): WeergaveStand => ({
  lagen: STANDAARD_LAGEN, markering: "alle", selectie: null, focus: null, ongedekt: new Set(), ...s,
});
const lijn = (bron: string, doel: string, s: WeergaveStand) => {
  const e = g.edges(bron, doel).find((x) => g.getEdgeAttribute(x, "soort") === "jas_relatie")!;
  return lijnBeeld(g.getEdgeAttributes(e), bron, doel, weergaveContext(g, s));
};

describe("relaties: types en model", () => {
  it("de api-vorm past in het samenhangtype en het model draagt type en beoordeling", () => {
    const s: Samenhang = { schema_versie: 1, doel: { bron_iri: A9 }, snapshot_id: "s", artikel_iri: A9, verwijzingen_beschikbaar: true,
      afgekapt: false, relaties_weggelaten: 1, ...BRON };
    expect(s.relaties.filter((r) => r.soort === "jas_relatie")).toHaveLength(7);
    const e = g.edges("element:zin", "element:aanslag")[0];
    expect(g.getEdgeAttributes(e)).toMatchObject({ soort: "jas_relatie", type: "voorwerp", lifecycle: "voorgesteld", veranderd: false });
  });

  it("twee relaties tussen dezelfde markeringen blijven twee lijnen", () => {
    const twee = bouwModel([{ knopen: BRON.knopen, relaties: [
      relatie("element:ontvanger", "element:zin", "plichthebbende"), relatie("element:ontvanger", "element:zin", "rechthebbende"),
      relatie("element:aanslag", "element:zin", "operand", "human_approved", { volgorde: 1 }),
      relatie("element:aanslag", "element:zin", "operand", "human_approved", { volgorde: 2 }),
    ] }]);
    expect(twee.size).toBe(4);
  });

  it("een impliciete partij is geen bron en telt niet in de layout", () => {
    expect(isBron({ soort: "impliciet" })).toBe(false);
    expect(structuurVan(g).knopen.map((k) => k.id)).not.toContain("impliciet:I1");
    expect(structuurVan(g).relaties.some((r) => r.soort === "jas_relatie")).toBe(false);
    expect(SOORT_LABEL.impliciet).toBe("Impliciete partij");
  });
});

describe("relaties: stijl", () => {
  it("een voorstel en een veranderde relatie zijn geel, beoordeeld neutraal, afgewezen niet in beeld", () => {
    expect(relatieStijl({ lifecycle: "voorgesteld" })).toEqual({ kleur: VOORSTELKLEUR, zichtbaar: true });
    expect(relatieStijl({ lifecycle: "human_approved", veranderd: true }).kleur).toBe(VOORSTELKLEUR);
    expect(relatieStijl({ lifecycle: "human_approved" })).toEqual({ kleur: RELATIEKLEUR, zichtbaar: true });
    expect(relatieStijl({ lifecycle: "rejected" }).zichtbaar).toBe(false);
  });

  it("een impliciete partij is hol: wit met een omtrek in haar klasse", () => {
    const a = g.getNodeAttributes("impliciet:I1");
    expect(eigenKleur(a)).toBe(klasseKleur("Rechtssubject"));
    const b = knoopBeeld("impliciet:I1", a, weergaveContext(g, stand({ lagen: { ...STANDAARD_LAGEN, relaties: true } })));
    expect(b).toMatchObject({ kleur: IMPLICIET_VULLING, omtrek: klasseKleur("Rechtssubject"), verborgen: false });
  });

  it("de inspector leest de relatie als zin, met haar stand", () => {
    const groepen = relatieGroepen(g, "element:zin");
    expect(groepen.find((x) => x.naam === "Relaties")?.regels.map((r) => r.anker_tekst))
      .toEqual(expect.arrayContaining(["is voorwerp van · voorstel van Lex", "is voorwaarde van"]));
    expect(groepen.find((x) => x.naam === "Relaties hierheen")?.regels.map((r) => r.id))
      .toEqual(expect.arrayContaining(["element:ontvanger", "impliciet:I1"]));
  });
});

describe("relaties: laag en diagrammodus", () => {
  it("de laag Relaties staat standaard uit: geen relatielijnen en geen impliciete partijen zonder keuze", () => {
    expect(STANDAARD_LAGEN.relaties).toBe(false);
    expect(verborgenKnopen(g, STANDAARD_LAGEN, "alle").has("impliciet:I1")).toBe(true);
    expect(lijn("element:ontvanger", "element:zin", stand()).verborgen).toBe(true);
    const aan = stand({ lagen: { ...STANDAARD_LAGEN, relaties: true } });
    expect(lijn("element:ontvanger", "element:zin", aan)).toMatchObject({ verborgen: false, pijl: true, kleur: RELATIEKLEUR });
    expect(lijn("element:zin", "element:aanslag", aan).kleur).toBe(VOORSTELKLEUR);
    expect(lijn("element:los", "element:zin", aan).verborgen).toBe(true);      // afgewezen
  });

  it("een centrale markering kiezen toont het diagram tot diepte twee, met de impliciete partij", () => {
    expect([...diagramBuurt(g, "element:zin")!].sort()).toEqual(
      ["element:aanslag", "element:dag", "element:ontvanger", "element:termijn", "element:zin", "impliciet:I1"]);
    const ctx = weergaveContext(g, stand({ selectie: "element:zin" }));
    expect(ctx.nadruk!.has("element:dag")).toBe(true);           // twee stappen: zin → termijn → dag
    expect(ctx.nadruk!.has("element:ver")).toBe(false);          // drie stappen
    expect(ctx.nadruk!.has("element:los")).toBe(false);          // alleen via een afgewezen relatie
    expect(ctx.verborgen.has("impliciet:I1")).toBe(false);       // de partij rond de keuze komt in beeld
    expect(lijn("element:termijn", "element:dag", stand({ selectie: "element:zin" }))).toMatchObject({ verborgen: false, niveau: 2 });
    expect(lijn("element:dag", "element:ver", stand({ selectie: "element:zin" })).verborgen).toBe(true);
  });

  it("een markering buiten de centrale klassen heeft geen diagram: alleen haar directe relaties", () => {
    expect(diagramBuurt(g, "element:termijn")).not.toBeNull();   // een voorwaarde is centraal
    expect(diagramBuurt(g, "element:ontvanger")).toBeNull();
    const ctx = weergaveContext(g, stand({ selectie: "element:ontvanger" }));
    expect(ctx.nadruk!.has("element:zin")).toBe(true);
    expect(ctx.nadruk!.has("element:aanslag")).toBe(false);
    expect(lijn("element:ontvanger", "element:zin", stand({ selectie: "element:ontvanger" })).verborgen).toBe(false);
  });

  it("een verborgen impliciete partij kiezen zet de lagen aan die nodig zijn", () => {
    const { lagen } = lagenVoor(g, "impliciet:I1", STANDAARD_LAGEN, "alle");
    expect(lagen).toEqual({ ...STANDAARD_LAGEN, relaties: true });
  });
});

describe("relaties: layout", () => {
  it("een impliciete partij staat bij het zwaartepunt van haar relaties; de rest verschuift niet", () => {
    const bron: Posities = new Map([[A9, [0, 0]], [L1, [10, 0]], [L2, [-10, 0]]]);
    const pos = plaatsAnnotaties(g, bron);
    const [x, y] = pos.get("impliciet:I1")!;
    const [zx, zy] = pos.get("element:zin")!;
    expect(Math.hypot(x - zx, y - zy)).toBeLessThan(10);
    const zonder = plaatsAnnotaties(bouwModel([{ knopen: BRON.knopen.filter((k) => k.soort !== "impliciet"),
      relaties: BRON.relaties.filter((r) => r.soort !== "jas_relatie") }]), bron);
    for (const [id, p] of zonder) expect(pos.get(id)).toEqual(p);
  });
});
