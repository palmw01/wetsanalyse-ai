import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  IN_EDITOR, MAX_PAD, MAX_SKILL_NAAM, PAD, SKILL_NAAM, UIT, WERKPLAATS_SOORTEN, WERKPLAATS_SOORT_LABEL, bestandsvolgorde, conceptPad,
  eigenConcept, geldigLabel, leesWerk, naamFout, omvang, padFout, parseOnderdeel, parseOnderdelen, parseStand, parseToets, parseVersie,
  splitsFrontmatter, standLabel, versieKeuze, versiePad, voorOverzicht, werkSleutel, werkplaatsSoortVan, wijzigingZin, wijzigingen,
  type WerkplaatsOnderdeel,
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

describe("bewerken", () => {
  it("dezelfde padvorm en lengte als bronmodel.werkplaats, en dezelfde vormen bij de api", () => {
    const patroon = BRONMODEL.match(/^PAD = re\.compile\(r"([^"]+)"\)/m)?.[1] ?? "";
    expect(PAD.source).toBe(`^${patroon.replaceAll("/", "\\/")}$`);
    expect(Number(BRONMODEL.match(/^MAX_PAD = (\d+)/m)?.[1])).toBe(MAX_PAD);
    // Wat de editor stuurt en leest: de velden van `VersieIn` en `ToetsIn`, en het antwoord van de toets.
    for (const veld of ["bestanden: Bestanden", "toelichting: str", "na_versie: int", "soort: str", "naam: str"]) expect(ROUTER, veld).toContain(veld);
    expect(ROUTER).toMatch(/"geldig": not bevindingen, "bevindingen": bevindingen, "hash"/);
  });

  it("een pad dat de api zou weigeren, zegt het formulier al", () => {
    const er = ["SKILL.md", "references/a.md"];
    for (const goed of ["references/b.md", "evals/x/prompt.md", "BRON.md", "_x.json"]) expect(padFout(goed, er), goed).toBe("");
    for (const fout of ["../buiten.md", "/abs.md", "a//b.md", "met spatie.md", ".verborgen", "a/../b", "references/a.md", "references",
      "SKILL.md/x", "a".repeat(MAX_PAD + 1)]) expect(padFout(fout, er), fout).not.toBe("");
    expect(padFout("", er)).toBe("");
  });

  it("de wijzigingen per bestand: gewijzigd, nieuw en verwijderd", () => {
    const w = wijzigingen({ a: "1", b: "2", c: "3" }, { a: "1", b: "anders", d: "4" });
    expect(w).toEqual({ gewijzigd: ["b"], toegevoegd: ["d"], verwijderd: ["c"], aantal: 3 });
    expect(wijzigingZin(w)).toBe("1 gewijzigd, 1 nieuw, 1 verwijderd");
    expect(wijzigingen({ a: "1" }, { a: "1" }).aantal).toBe(0);
    expect(wijzigingZin(wijzigingen({ a: "1" }, { a: "2" }))).toBe("1 gewijzigd");
  });

  it("de omvang tegen de grenzen van de api; zonder grens geen oordeel", () => {
    const grenzen = { bestanden: 2, tekens_per_bestand: 5, tekens: 8, versies: 0, onderdelen: 0 };
    expect(omvang({ a: "12345", b: "123" }, grenzen)).toEqual({ tekens: 8, bestanden: 2, teVeel: [] });
    expect(omvang({ a: "123456", b: "123", c: "" }, grenzen).teVeel).toHaveLength(3);
    expect(omvang({ a: "x".repeat(99) }, UIT.grenzen).teVeel).toEqual([]);
    // Tekens zoals de api ze telt (codepoints), niet UTF-16.
    expect(omvang({ a: "𝒜𝒜" }, grenzen).tekens).toBe(2);
  });

  it("de frontmatter staat los van de tekst", () => {
    expect(splitsFrontmatter("---\nname: x\n---\n\n# Kop\n")).toEqual({ frontmatter: "name: x", rest: "\n# Kop\n" });
    expect(splitsFrontmatter("# Kop\n---\nx")).toEqual({ frontmatter: "", rest: "# Kop\n---\nx" });
  });

  it("niet-opgeslagen werk hoort bij een concept en een versie, en alleen pad naar tekst telt", () => {
    expect(werkSleutel("o1", 3)).toBe("lex.concept.o1.3");
    expect(leesWerk({ "SKILL.md": "x", "references/a.md": "" })).toEqual({ "SKILL.md": "x", "references/a.md": "" });
    for (const fout of [null, [], "x", { "SKILL.md": 3 }, { "../x": "y" }]) expect(leesWerk(fout)).toBeUndefined();
  });

  it("het antwoord van de toets", () => {
    expect(parseToets({ geldig: true, bevindingen: [], hash: "h" })).toEqual({ geldig: true, bevindingen: [], hash: "h" });
    expect(parseToets({ geldig: false, bevindingen: [{ code: "naam", melding: "m", bestand: "" }, { x: 1 }] })?.bevindingen).toHaveLength(1);
    expect(parseToets({})).toBeNull();
  });
});

describe("versies", () => {
  it("de versie en de vergelijking uit de URL: zonder keuze de laatste, standaard tegen de voorganger", () => {
    const n = [1, 2, 3, 5];
    expect(versieKeuze(null, null, n)).toEqual({ versie: null, met: null });
    expect(versieKeuze("5", null, n)).toEqual({ versie: 5, met: 3 });
    expect(versieKeuze("1", null, n)).toEqual({ versie: 1, met: null });
    expect(versieKeuze("3", "1", n)).toEqual({ versie: 3, met: 1 });
    expect(versieKeuze("3", "0", n)).toEqual({ versie: 3, met: null });
    // Een nummer dat niet bestaat, of een versie tegen zichzelf, telt niet.
    expect(versieKeuze("4", null, n)).toEqual({ versie: null, met: null });
    expect(versieKeuze("x", "1", n)).toEqual({ versie: null, met: null });
    expect(versieKeuze("3", "3", n)).toEqual({ versie: 3, met: null });
    expect(versieKeuze("3", "9", n)).toEqual({ versie: 3, met: null });
  });

  it("het pad van een versie", () => {
    expect(versiePad("o1", 3)).toBe("/werkwijze/concepten/o1?versie=3");
    expect(versiePad("o1", 3, 1)).toBe("/werkwijze/concepten/o1?versie=3&met=1");
    expect(versiePad("o1", 3, null)).toBe("/werkwijze/concepten/o1?versie=3&met=0");
  });
});
