import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  BRONSOORT_LABEL, KEUZE_SOORTEN, METHODE_LABEL, besluitFout, blokkeert, keuzeZin, ordenPunten, puntenAlsMarkdown,
  puntenBij, type OpenPunt,
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
  it("de soorten die tegenhouden zijn die van de poort in de api", () => {
    const api = readFileSync(path.resolve(__dirname, "../../api/app/regel_store.py"), "utf8");
    expect(api).toContain(`KEUZE_SOORTEN = (${KEUZE_SOORTEN.map((s) => `"${s}"`).join(", ")})`);
  });
});

describe("open punten bij een regel", () => {
  const opRegel = punt({ id: "p1" });
  const opGeval = punt({ id: "p2" }, { hangt_aan: [{ soort: "geval", id: "r4", geval: "2" }] });
  it("op de regel of op één geval", () => {
    expect(puntenBij([opRegel, opGeval], "r4").map((p) => p.id)).toEqual(["p1"]);
    expect(puntenBij([opRegel, opGeval], "r4", "2").map((p) => p.id)).toEqual(["p2"]);
  });
  it("alleen een open keuze of beleidspunt houdt tegen; eerst wat tegenhoudt", () => {
    const onderzoek = punt({ id: "p3", soort: "onderzoekspunt", soort_naam: "onderzoekspunt" }, { lezingen: [] });
    const gekozen = punt({ id: "p4", status: "gekozen" });
    expect([opRegel, onderzoek, gekozen].map(blokkeert)).toEqual([true, false, false]);
    expect(ordenPunten([gekozen, onderzoek, opRegel]).map((p) => p.id)).toEqual(["p1", "p3", "p4"]);
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
