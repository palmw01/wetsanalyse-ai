import { describe, expect, it } from "vitest";

import {
  annotatieKopTekst, bepalingKort, herkomstKop, herkomstLabel, herkomstRegel, herkomstVan, plaatsKort, plaatsZin, standMeldingen,
  vindplaatsTekst,
} from "./herkomst";

const IW9 = "urn:bwb:BWBR0004770:artikel:9:lid:2";
const PLAATS = [
  { soort: "hoofdstuk", nummer: "II", titel: "Invordering" },
  { soort: "afdeling", nummer: "1", titel: "" },
  { soort: "artikel", nummer: "9", titel: "" },
];

describe("herkomst", () => {
  it("noemt de bepaling met de regeling, en nooit een kaal lid", () => {
    expect(vindplaatsTekst({ iri: IW9, label: "Artikel 9, lid 2", regeling: "Invorderingswet 1990" }))
      .toBe("Artikel 9, lid 2, Invorderingswet 1990");
    // Een segmentlabel is de staart van het pad: dan het pad uit de IRI.
    expect(herkomstVan({ iri: IW9, label: "Lid 2" }).bepaling).toBe("Artikel 9, lid 2");
    // Zonder citeertitel het BWB-id: eerlijk, nooit niets.
    expect(vindplaatsTekst({ iri: IW9, label: "Lid 2" })).toBe("Artikel 9, lid 2, BWBR0004770");
  });

  it("splitst een label dat de regeling al draagt, in beide volgordes", () => {
    expect(herkomstLabel(herkomstVan({ iri: IW9, label: "Invorderingswet 1990 – Artikel 9, Lid 2" })))
      .toBe("Artikel 9, lid 2, Invorderingswet 1990");
    expect(herkomstLabel(herkomstVan({ iri: IW9, label: "Artikel 9, lid 2 – Invorderingswet 1990" })))
      .toBe("Artikel 9, lid 2, Invorderingswet 1990");
  });

  it("houdt een eigen naam waar de IRI er geen heeft (een Leidraad-divisie)", () => {
    const iri = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36";
    expect(herkomstVan({ iri, label: "Artikel 36.8", regeling: "Leidraad Invordering 2008" }).bepaling).toBe("Artikel 36.8");
  });

  it("herhaalt de regeling niet als de bron de regeling zelf is", () => {
    const h = herkomstVan({ iri: "urn:bwb:BWBR0004770", regeling: "Invorderingswet 1990" });
    expect(h.bepaling).toBe("Invorderingswet 1990");
    expect(herkomstLabel(h)).toBe("Invorderingswet 1990");
  });

  it("geeft de plek kort en voluit, zonder het artikel", () => {
    expect(plaatsKort(PLAATS)).toBe("H II › Afd. 1");
    expect(plaatsZin(PLAATS)).toBe("Hoofdstuk II – Invordering › Afdeling 1");
  });

  it("bouwt de kop: de bepaling als titel, regeling · plek · stand eronder, de link met de toestand", () => {
    const h = herkomstVan({ iri: IW9, label: "Artikel 9, lid 2", regeling: "Invorderingswet 1990", plaats: PLAATS,
      geldig_vanaf: "2026-07-01", jci: "jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=2&g=2026-07-01" });
    expect(herkomstKop(h)).toEqual({ soort: "Bepaling", titel: "Artikel 9, lid 2" });
    expect(herkomstRegel(h)).toEqual(["Invorderingswet 1990", "H II › Afd. 1", "stand 1 juli 2026"]);
    expect(h.href).toBe("https://wetten.overheid.nl/jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=2&z=2026-07-01&g=2026-07-01");
  });

  it("meldt de stand: nieuwer dan Lex las, en na de peildatum", () => {
    const jci = "jci1.3:c:BWBR0004770&artikel=9&z=2026-01-01&g=2026-01-01";
    expect(standMeldingen({ geldig_vanaf: "2026-07-01", gelezenJci: jci }).map((m) => m.soort)).toEqual(["gelezen-ouder"]);
    expect(standMeldingen({ geldig_vanaf: "2026-07-01", peildatum: "2026-03-01" }).map((m) => m.soort)).toEqual(["na-peildatum"]);
    expect(standMeldingen({ geldig_vanaf: "2026-07-01", peildatum: "2026-08-01", gelezenJci: "" })).toEqual([]);
    expect(standMeldingen({ nogNietInWerking: true }).map((m) => m.soort)).toEqual(["nog-niet-in-werking"]);
  });

  it("houdt de korte vindplaats van een annotatie", () => {
    expect(bepalingKort({ artikel: "9", lid: "2" })).toBe("art. 9 lid 2");
    expect(annotatieKopTekst({ citeertitel: "Invorderingswet 1990", artikel: "9" }, { bwbId: "BWBR0004770", lid: "2" }))
      .toBe("Invorderingswet 1990 – art. 9 lid 2");
  });
});
