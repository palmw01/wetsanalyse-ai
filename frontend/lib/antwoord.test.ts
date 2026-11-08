import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { BLOK_SOORTEN, externGroepen, NIET_GETOETST, alleenNietGetoetst, bepalingenVan, groepeerWettekst, parseAntwoord } from "./antwoord";

const v = { iri: "urn:bwb:BWBR1:artikel:2", label: "Artikel 2", jci: "", regeling: "Wet" };

describe("parseAntwoord", () => {
  it("laat een geldig sjabloon door", () => {
    const a = parseAntwoord({ sjabloon: "begrip", versie: 1, doelen: [v], blokken: [
      { soort: "definities", door: "bron", items: [{ term: "x", tekst: "x: y", vindplaats: v, bereik: "" }] },
      { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "Uitleg." },
    ] });
    expect(a?.blokken).toHaveLength(2);
  });

  it("laat een duiding door: kort antwoord met eigen kop, citaten en twijfel", () => {
    const a = parseAntwoord({ sjabloon: "duiding", versie: 1, doelen: [v], blokken: [
      { soort: "toelichting", door: "lex", kop: "Kort antwoord", tekst: "Uitleg." },
      { soort: "citaten", door: "bron", items: [{ tekst: "x", vindplaats: v, waarom: "Omdat." }] },
      { soort: "twijfel", door: "lex", punten: ["Open punt."] },
    ] });
    expect(a?.blokken.map((b) => b.soort)).toEqual(["toelichting", "citaten", "twijfel"]);
  });

  it("weigert een blok met een gat, een onbekende soort en een leeg sjabloon", () => {
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [{ soort: "definities", items: [{ tekst: "x" }] }] })).toBeUndefined();
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [{ soort: "tabel" }] })).toBeUndefined();
    expect(parseAntwoord({ sjabloon: "begrip", blokken: [] })).toBeUndefined();
    expect(parseAntwoord(undefined)).toBeUndefined();
  });

  it("kent dezelfde blokken als het contract in bronmodel", () => {
    const bron = readFileSync(new URL("../../packages/bronmodel/bronmodel/antwoord.py", import.meta.url), "utf8");
    const soorten = [...bron.matchAll(/soort: Literal\["(\w+)"\]/g)].map((m) => m[1]);
    expect([...soorten].sort()).toEqual([...BLOK_SOORTEN].sort());
  });

  it("zet opeenvolgende leden van één artikel onder één kop, en laat een los lid staan", () => {
    const vp = (lid: string, art = "9") => ({ vindplaats: { iri: `urn:bwb:BWBR0004770:artikel:${art}:lid:${lid}`, label: `Artikel ${art}, lid ${lid}`,
      jci: `jci1.3:c:BWBR0004770&artikel=${art}&lid=${lid}&z=2026-10-01&g=2026-10-01`, regeling: "Invorderingswet 1990" } });
    const g = groepeerWettekst([vp("1"), vp("2"), vp("10"), vp("1", "10")]);
    expect(g).toHaveLength(2);
    expect(g[0].artikel).toEqual({ iri: "urn:bwb:BWBR0004770:artikel:9", label: "Artikel 9", regeling: "Invorderingswet 1990",
      jci: "jci1.3:c:BWBR0004770&artikel=9&z=2026-10-01&g=2026-10-01" });
    expect(g[0].items.map((i) => i.lid)).toEqual(["1", "2", "10"]);
    expect(g[1].artikel).toBeUndefined();
    expect(groepeerWettekst([{ vindplaats: { iri: "urn:bwb:BWBR0004770:artikel:9", label: "Artikel 9", jci: "", regeling: "" } }])[0].artikel).toBeUndefined();
  });

  it("opent bij annotaties de bronnodes van de markeringen, anders de doelen", () => {
    const blok = { soort: "annotaties" as const, door: "bron" as const, totaal: 3, volledig: true, items: [
      { id: "e1", klasse: "Rechtsfeit", tekst: "x", vindplaats: "Invorderingswet 1990 art. 9 lid 1", bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1" },
      { id: "e2", klasse: "Rechtsobject", tekst: "y", vindplaats: "Invorderingswet 1990 art. 9 lid 1", bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1" },
      { id: "e3", klasse: "Rechtsobject", tekst: "z", vindplaats: "2×: …" }] };
    const a = { sjabloon: "annotaties", versie: 1, blokken: [blok], doelen: [] };
    expect(bepalingenVan(a).map((v) => v.iri)).toEqual(["urn:bwb:BWBR0004770:artikel:9:lid:1"]);
    expect(alleenNietGetoetst(a)).toBe(true);
    expect(alleenNietGetoetst({ ...a, blokken: [blok, { soort: "toelichting", door: "lex", kop: "Toelichting van Lex", tekst: "t" }] })).toBe(false);
  });

  it("leest een blok extern (ADR-013) en weigert er een zonder passages", () => {
    const blok = { soort: "extern", door: "bron", brontype: "kamerstuk", id: "kst-33755-3", label: "Kamerstukken 33755, nr. 3",
      link: "https://zoek.officielebekendmakingen.nl/kst-33755-3", kop: "Uit de parlementaire geschiedenis",
      passages: [{ nr: 4, tekst: "Het doel is eenvoud.", kop: "1. Inleiding" }] };
    expect(parseAntwoord({ sjabloon: "extern", blokken: [blok] })?.blokken[0]).toEqual(blok);
    expect(parseAntwoord({ sjabloon: "extern", blokken: [{ ...blok, passages: undefined }] })).toBeUndefined();
    // De versie die Lex las (review ADR-013, punt 3) reist mee; een ouder bericht zonder versie blijft geldig.
    const metVersie = { ...blok, bron_hash: "abc", gewijzigd: "2026-01-02" };
    expect(parseAntwoord({ sjabloon: "extern", blokken: [metVersie] })?.blokken[0]).toEqual(metVersie);
  });

  it("deelt de passages van een bron naast de wet in: alinea, voetnoot en tabel met haar rijen", () => {
    const p = (nr: number, soort: string, extra: object = {}) => ({ nr, tekst: `t${nr}`, kop: "", soort, ...extra }) as never;
    const g = externGroepen([p(1, "alinea"), p(2, "voetnoot"), p(3, "tabel", { cellen: ["", "2014"] }),
      p(4, "tabelrij", { cellen: ["Totaal", "12"] }), p(5, "tabelrij", { cellen: ["Vpb", "8"] }), p(6, "alinea"),
      p(7, "tabelrij", { cellen: ["x"] })]);
    expect(g.map((x) => x.soort)).toEqual(["tekst", "voetnoot", "tabel", "tekst", "tabel"]);
    const tabel = g[2] as Extract<typeof g[number], { soort: "tabel" }>;
    expect(tabel.kop?.nr).toBe(3);
    expect(tabel.rijen.map((r) => r.nr)).toEqual([4, 5]);
    expect((g[4] as typeof tabel).kop).toBeUndefined();
    // Een ouder bericht zonder soort is gewoon tekst.
    expect(externGroepen([{ nr: 1, tekst: "x", kop: "" }]).map((x) => x.soort)).toEqual(["tekst"]);
  });

  it("kent dezelfde niet-getoetste blokken als het contract", () => {
    const bron = readFileSync(join(__dirname, "../../packages/bronmodel/bronmodel/antwoord.py"), "utf8");
    const set = /NIET_GETOETST = frozenset\(\{([^}]*)\}\)/.exec(bron)![1];
    expect([...set.matchAll(/"(\w+)"/g)].map((m) => m[1]).sort()).toEqual([...NIET_GETOETST].sort());
  });
});
