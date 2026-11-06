import { describe, expect, it } from "vitest";
import { antwoordDoelen, antwoordKnopTekst, normaliseerBronnen } from "./bronnen";
import type { Bron } from "./types";

const IW = "BWBR0004770", AWB = "BWBR0005537", AWR = "BWBR0002320", AWIR = "BWBR0018472";
const iri = (bwb: string, ...pad: string[]) => `urn:bwb:${bwb}` + pad.map((p) => `:${p}`).join("");
const jci = (bwb: string, q: string) => `jci1.3:c:${bwb}&${q}&z=2026-07-01&g=2026-07-01`;
const oud = (uri: string): Bron => ({ label: uri, uri });

/** De vorm van de bronnenlijst bij "Welke artikelen gaan over invordering?" (7 okt 2026): elke
 *  bepaling als graaf-IRI én als jci, hoofdstukken als ruwe IRI én ruwe jci, en de regeling zelf. */
function overzichtsantwoord(): Bron[] {
  const genoemd: [string, string][] = [[AWB, "4:94a"], [AWB, "4:124"], [AWR, "61"], [IW, "4"], [AWIR, "31bis"],
    [IW, "68"], [AWB, "4:121"], [IW, "31"], [IW, "63"]];
  const iw = ["1", "10", "9", "11", "12", "13", "14", "15", "16", "17", "18", "18a", "19", "2", "20", "27a",
    "27quinquies", "28", "28a", "28b", "28c", "29", "3"];
  const hoofdstukken = ["I", "II", "III", "IV", "IX", "V", "VI", "VII", "VIII", "VIIa", "VIIbis", "X"];
  return [
    ...genoemd.map(([b, a]) => oud(iri(b, "artikel", encodeURIComponent(a)))),
    ...genoemd.map(([b, a]) => oud(jci(b, `artikel=${a}`))),
    oud(iri(IW, "artikel", "26a", "lid", "2")), oud(jci(IW, "artikel=26a&lid=2")), oud(iri(IW, "artikel", "24", "lid", "1")),
    oud(IW), oud(iri(IW)),
    ...hoofdstukken.map((h) => oud(iri(IW, "hoofdstuk", h))),
    ...iw.map((a) => oud(iri(IW, "artikel", a))),
    ...hoofdstukken.map((h) => oud(jci(IW, `hoofdstuk=${h}`))),
    ...iw.map((a) => oud(jci(IW, `artikel=${a}`))),
  ];
}

describe("normaliseerBronnen", () => {
  it("maakt van het overzichtsantwoord één bron per bepaling, per regeling", () => {
    const bronnen = overzichtsantwoord();
    const lijst = normaliseerBronnen(bronnen);
    const labels = lijst.groepen.flatMap((g) => g.items.map((i) => i.label));
    const sleutels = lijst.groepen.flatMap((g) => g.items.map((i) => i.sleutel));
    expect(new Set(sleutels).size).toBe(sleutels.length);
    expect(lijst.groepen.map((g) => g.bwb_id)).toEqual([AWB, AWR, IW, AWIR]);
    expect(lijst.overig).toEqual([]);
    // Geen ruwe IRI of jci meer in beeld.
    expect(labels.some((l) => /urn:|jci/.test(l))).toBe(false);
    const iw = lijst.groepen.find((g) => g.bwb_id === IW)!;
    // Ontdubbeld: 12 hoofdstukken + 27 artikelen + 2 leden; de regeling zelf is de kop.
    expect(iw.items).toHaveLength(12 + 27 + 2);
    expect(iw.href).toBe("https://wetten.overheid.nl/BWBR0004770");
    expect(lijst.aantal).toBeLessThan(bronnen.length);
  });

  it("zet structuur vóór artikelen, hoofdstukken Romeins en artikelen numeriek", () => {
    const iw = normaliseerBronnen(overzichtsantwoord()).groepen.find((g) => g.bwb_id === IW)!;
    const labels = iw.items.map((i) => i.label);
    expect(labels.slice(0, 12)).toEqual(["Hoofdstuk I", "Hoofdstuk II", "Hoofdstuk III", "Hoofdstuk IV", "Hoofdstuk V",
      "Hoofdstuk VI", "Hoofdstuk VII", "Hoofdstuk VIIa", "Hoofdstuk VIIbis", "Hoofdstuk VIII", "Hoofdstuk IX", "Hoofdstuk X"]);
    expect(labels.slice(12, 16)).toEqual(["Artikel 1", "Artikel 2", "Artikel 3", "Artikel 4"]);
    expect(labels.indexOf("Artikel 9")).toBeLessThan(labels.indexOf("Artikel 10"));
    expect(labels.indexOf("Artikel 24, lid 1")).toBeLessThan(labels.indexOf("Artikel 26a, lid 2"));
  });

  it("gebruikt de regelingnaam en de jci-link uit canonieke bronnen", () => {
    const lijst = normaliseerBronnen([{
      label: "Artikel 9", uri: iri(IW, "artikel", "9"), bron_iri: iri(IW, "artikel", "9"),
      jci: jci(IW, "artikel=9"), bwb_id: IW, soort: "artikel", regeling: "Invorderingswet 1990",
    }]);
    expect(lijst.groepen).toEqual([{ bwb_id: IW, naam: "Invorderingswet 1990", items: [
      { sleutel: iri(IW, "artikel", "9"), label: "Artikel 9", soort: "artikel",
        href: `https://wetten.overheid.nl/${jci(IW, "artikel=9")}` }] }]);
  });

  it("laat een verwijzing zonder bronnode staan, één keer", () => {
    const vreemd = "jci1.3:c:BWBR0005537&bijlage=1&o=a";
    const lijst = normaliseerBronnen([oud(vreemd), oud(vreemd)]);
    expect(lijst.overig.map((i) => i.label)).toEqual([vreemd]);
    expect(lijst.aantal).toBe(1);
  });
});

describe("antwoordDoelen", () => {
  const IW_NAAM = { regeling: "Invorderingswet 1990", afkortingen: ["IW", "Iw 1990"] };
  const AWB_NAAM = { regeling: "Algemene wet bestuursrecht", afkortingen: ["Awb"] };
  const iw = (...pad: string[]): Bron => ({ label: "x", uri: iri(IW, ...pad), ...IW_NAAM });
  const awb = (...pad: string[]): Bron => ({ label: "x", uri: iri(AWB, ...pad), ...AWB_NAAM });
  const uit = (tekst: string, bronnen: Bron[]) => antwoordDoelen({ type: "antwoord", tekst, bronnen });
  const iris = (tekst: string, bronnen: Bron[]) => uit(tekst, bronnen).doelen.map((d) => d.bron_iri);

  it("geeft één doel per bepaling, ook binnen één artikel", () => {
    expect(iris("Artikel 9, eerste lid, en artikel 9, derde lid.", [iw("artikel", "9", "lid", "1"), iw("artikel", "9", "lid", "3")]))
      .toEqual([iri(IW, "artikel", "9", "lid", "1"), iri(IW, "artikel", "9", "lid", "3")]);
  });

  it("laat een ouder wegvallen als een kind ook genoemd is, in beide volgordes", () => {
    const bronnen = [iw("artikel", "9"), iw("artikel", "9", "lid", "1")];
    expect(iris("Artikel 9 regelt dit. Artikel 9, eerste lid, zegt:", bronnen)).toEqual([iri(IW, "artikel", "9", "lid", "1")]);
    expect(iris("Artikel 9, eerste lid, zegt dit. Zie verder artikel 9.", bronnen)).toEqual([iri(IW, "artikel", "9", "lid", "1")]);
  });

  it("verwart een artikel niet met een artikel dat ermee begint", () => {
    const bronnen = [iw("artikel", "9"), iw("artikel", "9a")];
    expect(iris("Artikel 9 en artikel 9a.", bronnen)).toEqual([iri(IW, "artikel", "9"), iri(IW, "artikel", "9a")]);
  });

  it("verdiept een artikelbron naar het genoemde lid en onderdeel", () => {
    const { doelen } = uit("Zie artikel 2, eerste lid, onderdeel m.", [iw("artikel", "2")]);
    expect(doelen).toEqual([{ bron_iri: iri(IW, "artikel", "2", "lid", "1", "o", "m"), bwb_id: IW, artikel: "2", lid: "1",
      label: "Artikel 2, lid 1, onderdeel m", citeertitel: "Invorderingswet 1990", herkomst: "vermelding" }]);
  });

  it("verdiept vanaf de diepste bron erboven", () => {
    expect(iris("Artikel 2, eerste lid, onderdeel m.", [iw("artikel", "2"), iw("artikel", "2", "lid", "1")]))
      .toEqual([iri(IW, "artikel", "2", "lid", "1", "o", "m")]);
  });

  it("verzint niets: een bepaling zonder bron erboven of eronder telt niet", () => {
    const bron = iw("artikel", "2", "lid", "2");
    const { doelen } = uit("Artikel 2, eerste lid, en artikel 77.", [bron]);
    expect(doelen.map((d) => [d.bron_iri, d.herkomst])).toEqual([[iri(IW, "artikel", "2", "lid", "2"), "eerste_bron"]]);
  });

  it("toetst de wet als de regelingnaam achter de vermelding staat", () => {
    const bronnen = [iw("artikel", "9"), awb("artikel", "9")];
    expect(iris("Artikel 9, eerste lid, van de Algemene wet bestuursrecht.", bronnen)).toEqual([iri(AWB, "artikel", "9", "lid", "1")]);
    expect(iris("Artikel 9, eerste lid, onderdeel a Iw 1990.", bronnen)).toEqual([iri(IW, "artikel", "9", "lid", "1", "o", "a")]);
    const anders = uit("Artikel 9 van de Algemene wet bestuursrecht.", [iw("artikel", "9")]);
    expect(anders.doelen.map((d) => d.herkomst)).toEqual(["eerste_bron"]);
  });

  it("kiest niet tussen twee wetten als de tekst er geen noemt", () => {
    const { doelen } = uit("Artikel 9, eerste lid.", [iw("artikel", "9"), awb("artikel", "9", "lid", "1")]);
    expect(doelen.map((d) => d.herkomst)).toEqual(["eerste_bron"]);
  });

  it("valt terug op de eerste bepaling en zegt dat", () => {
    const { doelen } = uit("Geen vindplaats.", [oud(iri(IW)), iw("artikel", "9", "lid", "2")]);
    expect(doelen.map((d) => [d.bron_iri, d.herkomst, d.citeertitel])).toEqual([[iri(IW, "artikel", "9", "lid", "2"), "eerste_bron", "Invorderingswet 1990"]]);
  });

  it("geeft geen doel zonder bepaling", () => {
    expect(uit("Artikel 9.", [oud(iri(IW))]).doelen).toEqual([]);
    expect(antwoordDoelen({ type: "antwoord", tekst: "Niets." })).toEqual({ doelen: [], totaal: 0 });
    expect(antwoordDoelen({ type: "annotatie" })).toEqual({ doelen: [], totaal: 0 });
  });

  it("een sjabloon draagt zijn doelen zelf en de tekst doet niet mee", () => {
    const iri = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:k";
    const antwoord = { sjabloon: "begrip", versie: 1, blokken: [], doelen: [{ iri, label: "Artikel 2, lid 1, onderdeel k", jci: "", regeling: "Invorderingswet 1990" }] };
    const { doelen } = antwoordDoelen({ type: "antwoord", tekst: "Zie artikel 9.", antwoord });
    expect(doelen).toMatchObject([{ bron_iri: iri, label: "Artikel 2, lid 1, onderdeel k", citeertitel: "Invorderingswet 1990", herkomst: "vermelding" }]);
    expect(antwoordDoelen({ type: "antwoord", tekst: "Zie artikel 9.", antwoord: { ...antwoord, doelen: [] } })).toEqual({ doelen: [], totaal: 0 });
  });

  it("neemt het doel van een annotatie en van een chip over", () => {
    const doel = { bron_iri: iri(IW, "artikel", "9", "lid", "1"), label: "Artikel 9, lid 1" };
    expect(antwoordDoelen({ type: "annotatie", annotatie_doel: doel })).toEqual({ doelen: [{ ...doel, herkomst: "vermelding" }], totaal: 1 });
    expect(antwoordDoelen({ type: "citatie", doel })).toEqual({ doelen: [{ ...doel, herkomst: "vermelding" }], totaal: 1 });
  });

  it("begrenst het aantal en meldt het totaal", () => {
    const tekst = "Artikel 1, artikel 2 en artikel 3.";
    const { doelen, totaal } = antwoordDoelen({ type: "antwoord", tekst, bronnen: [iw("artikel", "1"), iw("artikel", "2"), iw("artikel", "3")] }, 2);
    expect([doelen.length, totaal]).toEqual([2, 3]);
  });

  it("noemt op de knop bepalingen, of de ene bepaling", () => {
    const twee = uit("Artikel 9, eerste lid, en artikel 9, derde lid.", [iw("artikel", "9")]);
    expect(antwoordKnopTekst(twee)).toBe("Bekijk samenhang van de 2 genoemde bepalingen");
    expect(antwoordKnopTekst({ doelen: twee.doelen.slice(0, 1), totaal: 2 })).toBe("Bekijk samenhang van Artikel 9, lid 1 Invorderingswet 1990");
    expect(antwoordKnopTekst(uit("Artikel 2, eerste lid, onderdeel m.", [iw("artikel", "2")])))
      .toBe("Bekijk samenhang van Artikel 2, lid 1, onderdeel m Invorderingswet 1990");
  });
});
