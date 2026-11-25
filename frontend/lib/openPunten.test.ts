import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  BLOKKERENDE_STANDEN, BRONSOORT_LABEL, METHODE_LABEL, besluitFout, blokkeert, keuzeZin, nieuwePuntInhoud, nieuwFout,
  ordenPunten, puntenAlsMarkdown, puntenBij, type OpenPunt,
} from "./openPunten";

const punt = (over: Partial<OpenPunt> & { id: string }, inhoud: Partial<OpenPunt["inhoud"]> = {}): OpenPunt => ({
  werkgebied_id: "w", status: "open", revisie: 1, soort: "interpretatiekeuze", soort_naam: "interpretatiekeuze",
  keuze: null, herkomst: "jurist", ...over,
  inhoud: { soort: over.soort ?? "interpretatiekeuze", vraag: "Telt een deelbetaling?", toelichting: "",
    hangt_aan: [{ soort: "regel", id: "r4", geval: "" }],
    lezingen: [{ label: "A", omschrijving: "Ja", grondslag: [] }, { label: "B", omschrijving: "Nee", grondslag: [] }],
    te_toetsen: [], ...inhoud },
});

describe("de vorm volgt de api (open_punt_contracts.py)", () => {
  const bron = readFileSync(path.resolve(__dirname, "../../api/app/open_punt_contracts.py"), "utf8");
  const waarden = (klasse: string) => [...bron.split(`class ${klasse}(str, Enum):`)[1].split(/\n\n/)[0]
    .matchAll(/^\s+\w+ = "([a-z_]+)"/gm)].map((m) => m[1]).sort();
  it("methoden en bronsoorten", () => {
    expect(Object.keys(METHODE_LABEL).sort()).toEqual(waarden("Methode"));
    expect(Object.keys(BRONSOORT_LABEL).sort()).toEqual(waarden("Bronsoort"));
  });
  it("de standen die tegenhouden zijn die van de poort in de api", () => {
    const api = readFileSync(path.resolve(__dirname, "../../api/app/regel_store.py"), "utf8");
    expect(api).toContain(`BLOKKERENDE_STANDEN = (${BLOKKERENDE_STANDEN.map((s) => `"${s}"`).join(", ")},)`);
  });
});

describe("open punten bij een regel", () => {
  const opRegel = punt({ id: "p1" });
  const opGeval = punt({ id: "p2" }, { hangt_aan: [{ soort: "geval", id: "r4", geval: "2" }] });
  it("op de regel of op één geval", () => {
    expect(puntenBij([opRegel, opGeval], "r4").map((p) => p.id)).toEqual(["p1"]);
    expect(puntenBij([opRegel, opGeval], "r4", "2").map((p) => p.id)).toEqual(["p2"]);
  });
  it("elk open punt houdt tegen, ook een onderzoekspunt (20 nov 2026); eerst wat tegenhoudt", () => {
    const onderzoek = punt({ id: "p3", soort: "onderzoekspunt", soort_naam: "onderzoekspunt" }, { lezingen: [] });
    const gekozen = punt({ id: "p4", status: "gekozen" });
    const gesignaleerd = punt({ id: "p5", soort: "ontbrekend_uitvoeringsbeleid", status: "gesignaleerd" });
    expect([opRegel, onderzoek, gekozen, gesignaleerd].map(blokkeert)).toEqual([true, true, false, false]);
    expect(ordenPunten([gekozen, gesignaleerd, onderzoek, opRegel]).map((p) => p.id)).toEqual(["p3", "p1", "p5", "p4"]);
  });
});

describe("het besluit", () => {
  it("vraagt een lezing, een motivering en bij een interpretatiekeuze de methode", () => {
    const p = punt({ id: "p1" });
    expect(besluitFout(p, { gekozen: "", motivering: "x", methode: "grammaticaal" })).toBe("Kies een lezing.");
    expect(besluitFout(p, { gekozen: "B", motivering: " ", methode: "grammaticaal" })).toBe("Zeg waarom je deze lezing kiest.");
    expect(besluitFout(p, { gekozen: "B", motivering: "lid 2", methode: null })).toBe("Kies de methode van de interpretatie.");
    expect(besluitFout(p, { gekozen: "B", motivering: "lid 2", methode: "grammaticaal" })).toBeNull();
  });
  it("zonder lezingen is de motivering het besluit", () => {
    const p = punt({ id: "p3", soort: "onderzoekspunt", soort_naam: "onderzoekspunt" }, { lezingen: [] });
    expect(besluitFout(p, { gekozen: "", motivering: "", methode: null })).toBe("Zeg hoe het verder gaat.");
    expect(besluitFout(p, { gekozen: "", motivering: "Vragen bij de kennisgroep", methode: null })).toBeNull();
  });
  it("de zin van een genomen keuze, en de export als lijst", () => {
    const p = punt({ id: "p1", status: "gekozen",
      keuze: { gekozen: "B", motivering: "Volgt uit lid 2.", methode: "grammaticaal", door: "jurist", op: null } },
    { te_toetsen: [{ bronsoort: "wetsgeschiedenis", omschrijving: "MvT", getoetst: false, uitkomst: "" }] });
    expect(keuzeZin(p)).toBe("Lezing B (grammaticaal): Volgt uit lid 2.");
    const md = puntenAlsMarkdown([p]);
    expect(md).toContain("- Interpretatiekeuze (gekozen): Telt een deelbetaling?");
    expect(md).toContain("  - Gekozen: Lezing B (grammaticaal): Volgt uit lid 2.");
    expect(md).toContain("  - Nog te toetsen: wetsgeschiedenis (MvT)");
    expect(md).not.toMatch(/^\|/m);
  });
});

describe("na de e2e-run van Termijnen (20 nov 2026)", () => {
  it("ontbrekend beleid zegt of het beleid er is; gesignaleerd is geen keuze", () => {
    const p = punt({ id: "b", soort: "ontbrekend_uitvoeringsbeleid", soort_naam: "ontbrekend uitvoeringsbeleid" }, { lezingen: [] });
    expect(besluitFout(p, { gekozen: "", motivering: "Signaleren", methode: null })).toBe("Zeg of het beleid gevonden is of ontbreekt.");
    expect(besluitFout(p, { gekozen: "", motivering: "", methode: null, uitkomst: "gesignaleerd" })).toBe("Zeg welk beleid ontbreekt.");
    expect(besluitFout(p, { gekozen: "", motivering: "Geen afronding", methode: null, uitkomst: "gesignaleerd" })).toBeNull();
    expect(besluitFout(p, { gekozen: "", motivering: "LI 9.5", methode: null, uitkomst: "gekozen" })).toBeNull();
    const g = punt({ id: "g", soort: "ontbrekend_uitvoeringsbeleid", status: "gesignaleerd",
      keuze: { gekozen: "", motivering: "Geen afronding.", methode: null, door: "j", op: null, uitkomst: "gesignaleerd" } }, { lezingen: [] });
    expect(keuzeZin(g)).toBe("Het beleid ontbreekt: Geen afronding.");
    expect(blokkeert(g)).toBe(false);
  });
  it("een nieuw punt: een vraag, en bij een keuze twee lezingen met labels", () => {
    const n = { soort: "interpretatiekeuze" as const, vraag: "Per termijn?", toelichting: "", geval: "lid 5", lezingen: ["Ja", " "] };
    expect(nieuwFout(n)).toBe("Een interpretatiekeuze heeft ten minste twee lezingen.");
    expect(nieuwFout({ ...n, vraag: " " })).toBe("Zeg wat er open is.");
    const inhoud = nieuwePuntInhoud("r1", { ...n, lezingen: ["Ja", "Nee"] });
    expect(inhoud.hangt_aan).toEqual([{ soort: "geval", id: "r1", geval: "lid 5" }]);
    expect(inhoud.lezingen.map((l) => l.label)).toEqual(["A", "B"]);
    expect(nieuwePuntInhoud("r1", { ...n, geval: "", soort: "onderzoekspunt", lezingen: [] }).hangt_aan)
      .toEqual([{ soort: "regel", id: "r1", geval: "" }]);
  });
});

describe("een interpretatiekeuze signaleren (B9)", () => {
  const p = punt({ id: "i", soort: "interpretatiekeuze", status: "open" },
    { lezingen: [{ label: "A", omschrijving: "a", grondslag: [] }, { label: "B", omschrijving: "b", grondslag: [] }] });
  it("vraagt aan wie, een lezing, wat je signaleert en de methode", () => {
    const b = { gekozen: "", motivering: "", methode: null, uitkomst: "gesignaleerd" as const };
    expect(besluitFout(p, b)).toBe("Zeg aan wie je de keuze signaleert.");
    expect(besluitFout(p, { ...b, geadresseerde: "wetgever" })).toBe("Kies een lezing.");
    expect(besluitFout(p, { ...b, geadresseerde: "wetgever", gekozen: "B" })).toBe("Zeg wat je signaleert.");
    expect(besluitFout(p, { ...b, geadresseerde: "wetgever", gekozen: "B", motivering: "Twee termen, één betekenis." }))
      .toBe("Kies de methode van de interpretatie.");
    expect(besluitFout(p, { ...b, geadresseerde: "wetgever", gekozen: "B", motivering: "x", methode: "systematisch" })).toBeNull();
  });
  it("de zin noemt de keuze en aan wie", () => {
    const g = punt({ id: "g", soort: "interpretatiekeuze", status: "gesignaleerd",
      keuze: { gekozen: "B", motivering: "Synoniemen", methode: "systematisch", door: "j", op: null, uitkomst: "gesignaleerd",
        geadresseerde: "wetgever" } }, { lezingen: [] });
    expect(keuzeZin(g)).toBe("Lezing B (systematisch): Synoniemen · gesignaleerd aan de wetgever");
  });
});
