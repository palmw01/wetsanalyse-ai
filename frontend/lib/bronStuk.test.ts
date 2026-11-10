import { describe, expect, it } from "vitest";

import { hoortBij, parseStuk, stukGegevens, stukHerkomst, stukMeldingen, stukVerwijzingen, volgendeOffset } from "./bronStuk";

const BESCHRIJVING = { naam: "kamerstukken", label: "Kamerstukken", groep: "Parlementaire stukken", brontype: "kamerstuk",
  id_prefixen: ["kst-"], metadata: [{ sleutel: "soort", label: "soort stuk" }, { sleutel: "datum", label: "documentdatum" },
    { sleutel: "indieners", label: "indieners" }, { sleutel: "leesbaar", label: "leesbaar" }] };
const STUK = { id: "kst-32140-342", label: "Kamerstukken 32140, nr. 342", link: "https://zoek.officielebekendmakingen.nl/kst-32140-342",
  soort: "Brief", datum: "2026-05-04", indieners: ["A", "B"], bron_hash: "h2", leesbaar: true };

describe("bronStuk", () => {
  it("leest het antwoord van graph-qa: streng op de beschrijving, het resultaat zoals de leestool het gaf", () => {
    const a = parseStuk({ connector: BESCHRIJVING, resultaat: { status: "ok", stuk: STUK, resultaten: [{ nr: 1, tekst: "x", kop: "" }] } });
    expect(a?.beschrijving.groep).toBe("Parlementaire stukken");
    expect(a?.deel.resultaten).toHaveLength(1);
    expect(parseStuk({ connector: { naam: "x" }, resultaat: {} })).toBeUndefined();
  });

  it("maakt de kop uit de beschrijving en de metadata, niet uit een connectornaam", () => {
    const h = stukHerkomst(BESCHRIJVING, STUK, "terugval");
    expect([h.bepaling, h.regeling, h.plek]).toEqual(["Kamerstukken 32140, nr. 342", "Parlementaire stukken", "Brief · 4 mei 2026"]);
    expect(h.href).toBe(STUK.link);
    expect(stukHerkomst(undefined, undefined, "kst-1-1").bepaling).toBe("kst-1-1");
  });

  it("zet de gegevens in de volgorde en de woorden van de beschrijving", () => {
    expect(stukGegevens(BESCHRIJVING, STUK)).toEqual([
      { label: "soort stuk", waarde: "Brief" }, { label: "documentdatum", waarde: "4 mei 2026" }, { label: "indieners", waarde: "A, B" }]);
  });

  it("meldt een andere versie, een bewaarde versie en alleen een PDF", () => {
    expect(stukMeldingen({ status: "ok", stuk: STUK }, { bron_hash: "h1" }).map((m) => m.soort)).toEqual(["stuk-gewijzigd"]);
    expect(stukMeldingen({ status: "ok", stuk: { ...STUK, gevalideerd: false } }, { bron_hash: "h2" }).map((m) => m.soort)).toEqual(["bewaarde-versie"]);
    expect(stukMeldingen({ status: "fout", reden: "alleen_pdf" }).map((m) => m.soort)).toEqual(["alleen-pdf"]);
  });

  it("weet waar het volgende deel begint, en welke verwijzingen er zijn", () => {
    expect(volgendeOffset({ status: "ok", volledig: false, vervolg: { args: { offset: 40 } } })).toBe(40);
    expect(volgendeOffset({ status: "ok", volledig: true })).toBeUndefined();
    const v = { id: "kst-32140-1", label: "nr. 1", link: "" };
    expect(stukVerwijzingen([{ nr: 1, tekst: "", kop: "", verwijst_naar: [v] }, { nr: 2, tekst: "", kop: "", verwijst_naar: [v] }])).toEqual([v]);
    expect(hoortBij(BESCHRIJVING, "kst-32140-1")).toBe(true);
    expect(hoortBij(BESCHRIJVING, "ECLI:NL:HR:2020:1")).toBe(false);
  });
});
