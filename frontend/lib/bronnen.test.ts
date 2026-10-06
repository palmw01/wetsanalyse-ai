import { describe, expect, it } from "vitest";
import { normaliseerBronnen } from "./bronnen";
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
