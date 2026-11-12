import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  SOORTEN, SOORT_LABEL, filterOnderdelen, onderdeelPad, parseCatalogus, parseOnderdeel, perSoort, type Onderdeel,
} from "./catalogus";

const BRONMODEL = join(__dirname, "..", "..", "packages", "bronmodel", "bronmodel", "catalogus.py");

function o(id: string, extra: Partial<Onderdeel> = {}): Onderdeel {
  const soort = id.split("/")[0] as Onderdeel["soort"];
  return { id, soort, label: id, doel: `doel van ${id}`, model: "geen", versie: "x", bestand: [], ingang: [],
    context: "", tools: [], uitvoer: "", twijfel: "", tests: [], hangt_af_van: [], straat: null, bewerkbaar: [],
    laag: null, stappen: [], aan: true, concept: "skill", deel_van: null, herkomst: { bron: "b", licentie: "repo", letterlijk: false, verwijzing: [] },
    ...extra };
}

describe("de catalogus volgt het bronmodel", () => {
  it("dezelfde soorten in dezelfde volgorde als bronmodel.catalogus.Soort", () => {
    const bron = readFileSync(BRONMODEL, "utf8");
    const literal = bron.match(/^Soort = Literal\[([\s\S]*?)\]/m)?.[1] ?? "";
    expect([...literal.matchAll(/"([a-z]+)"/g)].map((m) => m[1])).toEqual([...SOORTEN]);
    for (const s of SOORTEN) expect(SOORT_LABEL[s].een).toBeTruthy();
  });
});

describe("parseCatalogus", () => {
  it("laat een rij met een onbekende soort of zonder vaste velden weg", () => {
    const c = parseCatalogus({ onderdelen: [o("rol/duiding"), { id: "onzin/x", soort: "onzin" }, { id: "rol/y" }] });
    expect(c?.onderdelen.map((x) => x.id)).toEqual(["rol/duiding"]);
    expect(parseCatalogus({})).toBeNull();
  });

  it("een detail krijgt een lege inhoud en lege gebruikt_door als ze ontbreken", () => {
    const d = parseOnderdeel(o("sjabloon/antwoord_begrip"));
    expect(d?.inhoud).toEqual({});
    expect(d?.gebruikt_door).toEqual([]);
    expect(parseOnderdeel({ id: "x" })).toBeNull();
  });
});

describe("filteren en groeperen", () => {
  const lijst = [o("workflow/annotatieketen", { label: "Annotatieketen" }), o("regelset/jas.detector.tijd"),
    o("rol/duiding"), o("workflow/regie", { doel: "Verdeelt het werk over deelgesprekken" })];

  it("op soort en op alle woorden van de zoekterm, in label, doel en id", () => {
    expect(filterOnderdelen(lijst, { soort: "workflow", zoek: "" }).map((x) => x.id))
      .toEqual(["workflow/annotatieketen", "workflow/regie"]);
    expect(filterOnderdelen(lijst, { soort: "", zoek: "werk deelgesprekken" }).map((x) => x.id)).toEqual(["workflow/regie"]);
    expect(filterOnderdelen(lijst, { soort: "", zoek: "TIJD" }).map((x) => x.id)).toEqual(["regelset/jas.detector.tijd"]);
  });

  it("per soort in de volgorde van SOORTEN, zonder lege soorten", () => {
    expect(perSoort(lijst).map((g) => g.soort)).toEqual(["rol", "regelset", "workflow"]);
  });

  it("het pad van een onderdeel", () => {
    expect(onderdeelPad("regelset/jas.detector.tijd")).toBe("/werkwijze/regelset/jas.detector.tijd");
    expect(onderdeelPad("onzin")).toBe("/werkwijze");
  });
});
