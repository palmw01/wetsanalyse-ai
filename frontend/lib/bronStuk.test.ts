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

  it("past een uitspraak zonder eigen code: kop, gegevens, inhoud en stand uit hetzelfde contract", () => {
    // De vorm die graph-qa `get_uitspraak` geeft (tools/graph-qa/agent/tools/rechtspraak_tools.py) en de beschrijving
    // die de stukkenroute meestuurt: niets hier kent Rechtspraak bij naam.
    const rs = { naam: "rechtspraak", label: "Rechtspraak", groep: "Uitspraken", brontype: "uitspraak", id_prefixen: ["ECLI:NL:"],
      metadata: [{ sleutel: "datum", label: "datum uitspraak" }, { sleutel: "soort", label: "soort" }, { sleutel: "orgaan", label: "instantie" },
        { sleutel: "nummer", label: "zaaknummer" }, { sleutel: "procedure", label: "procedure" }, { sleutel: "rechtsgebied", label: "rechtsgebied" }] };
    const stuk = { id: "ECLI:NL:HR:2022:50", label: "Hoge Raad 21 januari 2022, ECLI:NL:HR:2022:50", soort: "Uitspraak",
      datum: "2022-01-21", orgaan: "Hoge Raad", nummer: "21/00733", procedure: "Cassatie", rechtsgebied: "Bestuursrecht; Belastingrecht",
      link: "https://uitspraken.rechtspraak.nl/details?id=ECLI:NL:HR:2022:50", bron_hash: "h", gevalideerd: false };
    const a = parseStuk({ connector: rs, resultaat: { status: "ok", stuk, volledig: false, vervolg: { tool: "get_uitspraak", args: { id: stuk.id, offset: 40 } },
      inhoud: [{ kop: "Uitspraak › 2 Uitgangspunten in cassatie", offset: 4 }],
      resultaten: [{ nr: 1, kop: "Uitspraak › 2 Uitgangspunten in cassatie", ro: "2.1", tekst: "Aan belanghebbende zijn aanslagen opgelegd." }] } });
    expect(a).toBeDefined();
    const h = stukHerkomst(a!.beschrijving, a!.deel.stuk, stuk.id);
    expect([h.bepaling, h.regeling, h.plek]).toEqual([stuk.label, "Uitspraken", "Uitspraak · 21 januari 2022"]);
    expect(stukGegevens(a!.beschrijving, a!.deel.stuk).map((g) => g.label)).toEqual(
      ["datum uitspraak", "soort", "instantie", "zaaknummer", "procedure", "rechtsgebied"]);
    expect(a!.deel.inhoud?.[0].offset).toBe(4);
    expect(volgendeOffset(a!.deel)).toBe(40);
    expect(stukMeldingen(a!.deel).map((m) => m.soort)).toEqual(["bewaarde-versie"]);
    expect(hoortBij(a!.beschrijving, stuk.id)).toBe(true);
  });
});
