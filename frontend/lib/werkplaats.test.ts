import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  IN_EDITOR, MAX_SKILL_NAAM, SKILL_NAAM, UIT, WERKPLAATS_SOORTEN, WERKPLAATS_SOORT_LABEL, bestandsvolgorde, conceptPad,
  eigenConcept, geldigLabel, naamFout, parseOnderdeel, parseOnderdelen, parseStand, parseVersie, standLabel, voorOverzicht,
  werkplaatsSoortVan, type WerkplaatsOnderdeel,
} from "./werkplaats";

const WORTEL = join(__dirname, "..", "..");
const lees = (...pad: string[]) => readFileSync(join(WORTEL, ...pad), "utf8");
const BRONMODEL = lees("packages", "bronmodel", "bronmodel", "werkplaats.py");
const SKILL = lees("packages", "bronmodel", "bronmodel", "skill.py");
const STORE = lees("api", "app", "werkplaats_store.py");
const ROUTER = lees("api", "app", "werkplaats.py");

const versie = (extra: Record<string, unknown> = {}) => ({
  id: "v1", nummer: 1, hash: "a".repeat(64), basis_hash: "", toelichting: "", geldig: true, bevindingen: [], door: "jan",
  gemaakt: "2026-11-13T10:00:00+00:00", actief: false, ...extra,
});
const rij = (extra: Record<string, unknown> = {}) => ({
  id: "o1", soort: "skill", naam: "jrm-proef", eigenaar: "jan", gedeeld: false, stand: "concept", in_image: false,
  actief_versie: null, basis_verouderd: false, image_bekend: true, versies: 1, laatste: versie(), zelfde_naam: 0,
  gemaakt: "", bijgewerkt: "", ingetrokken_op: "", ingetrokken_door: "", ...extra,
});
const o = (extra: Record<string, unknown> = {}) => parseOnderdeel(rij(extra)) as WerkplaatsOnderdeel;

describe("de werkplaats volgt het bronmodel en de api", () => {
  it("dezelfde soorten in dezelfde volgorde als bronmodel.werkplaats.SOORTEN, elk met een label", () => {
    const tuple = BRONMODEL.match(/^SOORTEN: tuple\[str, \.\.\.\] = \(([^)]*)\)/m)?.[1] ?? "";
    expect([...tuple.matchAll(/"([a-z]+)"/g)].map((m) => m[1])).toEqual([...WERKPLAATS_SOORTEN]);
    for (const s of WERKPLAATS_SOORTEN) expect(WERKPLAATS_SOORT_LABEL[s]).toBeTruthy();
    for (const s of IN_EDITOR) expect(WERKPLAATS_SOORTEN).toContain(s);
  });

  it("dezelfde naamvorm en lengte als bronmodel.skill", () => {
    const patroon = SKILL.match(/^NAAM = re\.compile\(r"([^"]+)"\)/m)?.[1];
    expect(SKILL_NAAM.source).toBe(`^${patroon}$`);
    expect(Number(SKILL.match(/^MAX_NAAM = (\d+)/m)?.[1])).toBe(MAX_SKILL_NAAM);
  });

  it("de velden die de werkplek leest, geeft de api", () => {
    const onderdeel = STORE.slice(STORE.indexOf("def _onderdeel("), STORE.indexOf("def _versie("));
    const stand = STORE.slice(STORE.indexOf("def _stand("), STORE.indexOf("def _onderdeel("));
    for (const veld of ["id", "soort", "naam", "eigenaar", "gedeeld", "versies", "laatste", "zelfde_naam", "gemaakt", "bijgewerkt"])
      expect(onderdeel, veld).toContain(`"${veld}"`);
    for (const veld of ["stand", "in_image", "actief_versie", "basis_verouderd", "image_bekend"]) expect(stand, veld).toContain(`"${veld}"`);
    const v = STORE.slice(STORE.indexOf("def _versie("), STORE.indexOf("_KOP ="));
    for (const veld of ["id", "nummer", "hash", "basis_hash", "toelichting", "geldig", "bevindingen", "door", "gemaakt", "actief", "bestanden"])
      expect(v, veld).toContain(`"${veld}"`);
    expect(STORE).toMatch(/\{"code": b\.code, "melding": b\.melding, "bestand": b\.bestand\}/);
    for (const veld of ["aan", "mag_maken", "beheerder", "image", "grenzen", "tekens_per_bestand"]) expect(ROUTER, veld).toContain(`"${veld}"`);
    expect(STORE).toContain('"versielijst"');
    // De standen die de api afleidt, zijn de standen die de werkplek kent.
    expect([...new Set([...stand.matchAll(/"(ingetrokken|actief|concept)"/g)].map((m) => m[1]))].sort())
      .toEqual(["actief", "concept", "ingetrokken"]);
  });
});

describe("parseStand", () => {
  it("alles wat geen stand met aan: true is, is uit", () => {
    for (const x of [null, undefined, {}, { aan: false }, { aan: "ja" }, "x", []]) expect(parseStand(x)).toEqual(UIT);
  });

  it("leest wat de gebruiker mag en wat de api van het image weet", () => {
    const s = parseStand({ aan: true, mag_maken: true, beheerder: false,
      image: { bekend: true, revisie: "abc", gemeld_op: "2026-11-13T10:00:00+00:00", pakket_hash: "x", onderdelen: 10 },
      grenzen: { bestanden: 60, tekens_per_bestand: 100000, tekens: 400000, versies: 200, onderdelen: 50 } });
    expect(s.aan && s.mag_maken && !s.beheerder).toBe(true);
    expect(s.image).toEqual({ bekend: true, revisie: "abc", gemeld_op: "2026-11-13T10:00:00+00:00" });
    expect(s.grenzen.tekens).toBe(400000);
  });
});

describe("parseOnderdeel", () => {
  it("laat een rij zonder id, met een onbekende soort of een onbekende stand weg", () => {
    expect(parseOnderdelen([rij(), rij({ id: "" }), rij({ soort: "regelset" }), rij({ stand: "voorgesteld" }), null, 3]))
      .toHaveLength(1);
    expect(parseOnderdelen({})).toEqual([]);
  });

  it("onbekend blijft onbekend: zonder image zijn de afgeleide velden null, wat de rij ook zegt", () => {
    const x = o({ image_bekend: false, in_image: false, actief_versie: 3, basis_verouderd: true });
    expect([x.image_bekend, x.in_image, x.actief_versie, x.basis_verouderd]).toEqual([false, null, null, null]);
    expect(parseVersie(versie({ actief: null }))?.actief).toBeNull();
    expect(parseVersie(versie({ actief: undefined }))?.actief).toBeNull();
  });

  it("leest de versielijst en de bestanden van een versie", () => {
    expect(o({ versielijst: [versie(), versie({ nummer: 2 }), { nummer: "x" }] }).versielijst?.map((v) => v.nummer)).toEqual([1, 2]);
    expect(parseVersie(versie({ bestanden: { "SKILL.md": "tekst", "x.bin": 3 } }))?.bestanden).toEqual({ "SKILL.md": "tekst" });
    expect(parseVersie(versie())?.bestanden).toBeUndefined();
  });
});

describe("standLabel", () => {
  it("zegt in elk geval hetzelfde, en nooit 'draait niet' als onbekend is wat er draait", () => {
    expect(standLabel(o()).tekst).toBe("Concept");
    expect(standLabel(o({ stand: "actief", actief_versie: 1 }))).toMatchObject({ tekst: "Draait nu", toon: "groen" });
    expect(standLabel(o({ basis_verouderd: true }))).toMatchObject({ tekst: "Concept · loopt achter", toon: "geel" });
    expect(standLabel(o({ stand: "ingetrokken", basis_verouderd: true })).tekst).toBe("Ingetrokken");
    expect(standLabel(o({ actief_versie: 1 })).uitleg).toContain("Versie 1 draait");
    const onbekend = standLabel(o({ image_bekend: false }));
    expect(onbekend.tekst).toBe("Concept · nog onbekend wat er draait");
    expect(`${onbekend.tekst} ${onbekend.uitleg}`).not.toMatch(/draait niet|niet actief/i);
  });

  it("de laatste versie is geldig, of noemt het aantal bevindingen", () => {
    expect(geldigLabel(null)).toBeNull();
    expect(geldigLabel(parseVersie(versie()))?.tekst).toBe("Geldig");
    const b = { code: "naam", melding: "m", bestand: "SKILL.md" };
    expect(geldigLabel(parseVersie(versie({ geldig: false, bevindingen: [b] })))?.tekst).toBe("1 bevinding");
    expect(geldigLabel(parseVersie(versie({ geldig: false, bevindingen: [b, b] })))).toMatchObject({ tekst: "2 bevindingen", toon: "geel" });
  });
});

describe("de lijst en de ingangen", () => {
  it("een methode is een skill; wat de editor niet opent, heeft geen knop", () => {
    expect(werkplaatsSoortVan("methode")).toBe("skill");
    expect(werkplaatsSoortVan("agentprofiel")).toBeNull();
    expect(werkplaatsSoortVan("rol")).toBeNull();
  });

  it("het eigen concept is van mij, van deze soort en naam, en niet ingetrokken", () => {
    const lijst = [o({ id: "a", eigenaar: "piet" }), o({ id: "b", stand: "ingetrokken" }), o({ id: "c" }), o({ id: "d", naam: "anders" })];
    expect(eigenConcept(lijst, "skill", "jrm-proef", "jan")?.id).toBe("c");
    expect(eigenConcept(lijst, "skill", "jrm-proef", undefined)).toBeNull();
    expect(eigenConcept(lijst, "agentprofiel", "jrm-proef", "jan")).toBeNull();
  });

  it("het overzicht: de eigen eerst, ingetrokken onderaan, en alleen wat de editor opent", () => {
    const lijst = [o({ id: "1", naam: "z", eigenaar: "piet" }), o({ id: "2", naam: "b", stand: "ingetrokken" }), o({ id: "3", naam: "m" }),
      o({ id: "4", naam: "a" }), o({ id: "5", soort: "agentprofiel", naam: "p" })];
    expect(voorOverzicht(lijst, "jan").map((x) => x.id)).toEqual(["4", "3", "1", "2"]);
  });

  it("een naam die de api zou weigeren, zegt het formulier al", () => {
    for (const goed of ["jrm-scenario", "a", "x1-y2"]) expect(naamFout(goed)).toBe("");
    for (const fout of ["JRM", "jrm_scenario", "-x", "x-", "x--y", "met spatie", "a".repeat(MAX_SKILL_NAAM + 1)]) expect(naamFout(fout)).not.toBe("");
    expect(naamFout("")).toBe("");
  });

  it("de bestanden: het hoofdbestand, de wortel, dan de mappen", () => {
    expect(bestandsvolgorde(["references/b.md", "agentrollen.json", "evals/x/prompt.md", "SKILL.md", "references/a.md"]))
      .toEqual(["SKILL.md", "agentrollen.json", "evals/x/prompt.md", "references/a.md", "references/b.md"]);
    expect(conceptPad("o 1")).toBe("/werkwijze/concepten/o%201");
  });
});
