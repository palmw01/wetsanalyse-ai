import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { CONCEPTEN, NEUTRAAL, SOORTEN, SOORT_LABEL, methodeLabel, parseCatalogus, parseOnderdeel, type Onderdeel } from "./catalogus";

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

  it("dezelfde concepten als bronmodel.catalogus.Concept (een rij met een onbekend concept valt weg)", () => {
    const bron = readFileSync(BRONMODEL, "utf8");
    const literal = bron.match(/^Concept = Literal\[([\s\S]*?)\]/m)?.[1] ?? "";
    expect([...literal.matchAll(/"([a-z]+)"/g)].map((m) => m[1])).toEqual([...CONCEPTEN]);
  });
});

describe("de methode van een onderdeel", () => {
  it("neutraal heet zoals in het bronmodel", () => {
    expect(readFileSync(BRONMODEL, "utf8")).toContain(`NEUTRAAL = "${NEUTRAAL}"`);
  });

  it("de werkplek noemt de skill bij naam en zegt het als een onderdeel van geen methode is", () => {
    expect(methodeLabel("wetsanalyse")).toBe("Wetsanalyse");
    expect(methodeLabel("wetsuitvoering")).toBe("Wetsuitvoering");
    expect(methodeLabel(NEUTRAAL)).toBe("Geen: voor elke methode");
    expect(methodeLabel(undefined)).toBe("");
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
