import { describe, expect, it } from "vitest";
import { parseOverzicht } from "./agentEvents";
import { bepalingNaam, deelKop, overzichtAlsMarkdown, overzichtDoelen, overzichtKnopTekst, telling, zoekverantwoording } from "./overzicht";
import type { Overzicht } from "./types";

const IW = "urn:bwb:BWBR0004770", AWB = "urn:bwb:BWBR0005537", LEIDRAAD = "urn:bwb:BWBR0024096";

/** De vorm van het overzicht bij "Welke artikelen gaan over invordering?" (8 okt 2026), ingekort. */
function invordering(): Overzicht {
  return {
    gevraagd: "invordering", onderwerp_opbouw: "invordering", onderwerp_tekst: "invordering", scope: [], volledig: true,
    definities: [{ iri: `${IW}:artikel:2:lid:2:o:e`, begrip: "invorderen van rijksbelastingen", label: "Onderdeel e.",
      tekst: "", jci: "", bwb_id: "BWBR0004770", citeertitel: "Invorderingswet 1990" }],
    trefwoorden: [{ trefwoord: "Invorderingsrecht", regelingen: [{ bwb_id: "BWBR0004770", citeertitel: "Invorderingswet 1990" }] }],
    regelingen: [
      { bwb_id: "BWBR0004770", citeertitel: "Invorderingswet 1990", soort: "wet",
        delen: [
          { iri: `${IW}:hoofdstuk:II`, soort: "Hoofdstuk", label: "Hoofdstuk II – Invordering in eerste aanleg", jci: "",
            bepalingen: ["8", "9", "10"].map((n) => ({ iri: `${IW}:artikel:${n}`, nummer: n, label: `Artikel ${n}` })), subdelen: [] },
          { iri: `${IW}:hoofdstuk:V`, soort: "Hoofdstuk", label: "Hoofdstuk V – Invorderingsrente", jci: "",
            bepalingen: ["27a", "27quinquies", "31"].map((n) => ({ iri: `${IW}:artikel:${n}`, nummer: n, label: `Artikel ${n}` })), subdelen: [] },
        ],
        ook_genoemd: [{ iri: `${IW}:artikel:4`, nummer: "4", label: "Artikel 4",
          in_deel: { iri: `${IW}:hoofdstuk:I`, label: "Hoofdstuk I – Algemene bepalingen" } }] },
      { bwb_id: "BWBR0005537", citeertitel: "Algemene wet bestuursrecht", soort: "wet",
        delen: [{ iri: `${AWB}:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.4`, soort: "Afdeling",
          label: "Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel", jci: "",
          bepalingen: [{ iri: `${AWB}:artikel:4%3A112`, nummer: "4:112", label: "Artikel 4:112" }],
          subdelen: [{ iri: `${AWB}:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.4:paragraaf:4.4.4.2`, label: "Paragraaf 4.4.4.2 – Invordering bij dwangbevel" }] }],
        ook_genoemd: [] },
      { bwb_id: "BWBR0024096", citeertitel: "Leidraad Invordering 2008", soort: "beleidsregel",
        delen: [{ iri: `${LEIDRAAD}:artikel:28`, soort: "Divisie", label: "Invorderingsrente", jci: "",
          bepalingen: ["28.1", "28.3a"].map((n) => ({ iri: `${LEIDRAAD}:id:BWBR0024096%2FCirculaire.divisie${n}`, nummer: n, label: n })),
          subdelen: [] }],
        ook_genoemd: [] },
    ],
  };
}

describe("overzicht", () => {
  it("komt ongeschonden door de parser, ook uit een bewaard bericht", () => {
    const ov = invordering();
    expect(parseOverzicht(JSON.parse(JSON.stringify(ov)))).toEqual(ov);
  });

  it("weigert een overzicht met een rij zonder bron-IRI – een blok met een gat oogt volledig", () => {
    const ov = invordering() as unknown as { regelingen: { delen: { iri: string }[] }[] };
    ov.regelingen[0].delen[0].iri = "javascript:alert(1)";
    expect(parseOverzicht(ov)).toBeUndefined();
  });

  it("opent de delen in de volgorde van het overzicht, los van de tekst", () => {
    const keuze = overzichtDoelen(invordering());
    expect(keuze.doelen.map((d) => d.bron_iri)).toEqual([
      `${IW}:hoofdstuk:II`, `${IW}:hoofdstuk:V`, `${AWB}:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.4`, `${LEIDRAAD}:artikel:28`,
    ]);
    expect(keuze.doelen[0].citeertitel).toBe("Invorderingswet 1990");
    expect(overzichtKnopTekst(keuze, invordering())).toBe("Bekijk samenhang van de 4 delen");
    expect(overzichtKnopTekst(overzichtDoelen(invordering(), 2), invordering())).toBe("Bekijk samenhang van de 4 delen (2 getoond)");
  });

  it("zonder delen: de bepalingen die het onderwerp noemen", () => {
    const ov = { ...invordering(), regelingen: [{ ...invordering().regelingen[0], delen: [] }] };
    expect(overzichtDoelen(ov).doelen.map((d) => d.bron_iri)).toEqual([`${IW}:artikel:4`]);
    expect(overzichtKnopTekst(overzichtDoelen(ov), ov)).toBe("Bekijk samenhang van Artikel 4");
  });

  it("noemt artikelen en divisies elk op hun eigen manier, zonder bereik", () => {
    const [iw, , leidraad] = invordering().regelingen;
    expect(iw.delen[1].bepalingen.map(bepalingNaam)).toEqual(["art. 27a", "art. 27quinquies", "art. 31"]);
    expect(leidraad.delen[0].bepalingen.map(bepalingNaam)).toEqual(["28.1", "28.3a"]);
    expect(deelKop(leidraad.delen[0])).toBe("28 – Invorderingsrente");
    expect(deelKop(iw.delen[0])).toBe("Hoofdstuk II – Invordering in eerste aanleg");
  });

  it("telt en verantwoordt", () => {
    expect(telling(invordering())).toEqual({ regelingen: 3, delen: 4, bepalingen: 9, ookGenoemd: 1 });
    expect(zoekverantwoording(invordering())).toBe("Gezocht op „invordering” in de opschriften en in de wettekst.");
    const smal = { ...invordering(), gevraagd: "invordering van belastingen", onderwerp_tekst: "invordering belastingen" };
    expect(zoekverantwoording(smal)).toBe(
      "Gezocht op „invordering” in de opschriften en op „invordering belastingen” in de wettekst (gevraagd: „invordering van belastingen”).");
  });

  it("kopieert dezelfde inhoud als het blok", () => {
    const md = overzichtAlsMarkdown(invordering());
    expect(md).toContain("- Hoofdstuk V – Invorderingsrente: art. 27a, art. 27quinquies, art. 31");
    expect(md).toContain("- Ook genoemd: art. 4 (Hoofdstuk I – Algemene bepalingen)");
    expect(md).toContain("  - waarin Paragraaf 4.4.4.2 – Invordering bij dwangbevel");
    expect(md).toContain("- 28 – Invorderingsrente: 28.1, 28.3a");
    // Geen bereik: elk nummer staat er zelf.
    expect(md).not.toMatch(/\d+\s*(–|t\/m)\s*\d+/);
  });
});
