import { describe, expect, it } from "vitest";

import {
  annotatieKopTekst, bepalingKort, herkomstKop, herkomstLabel, herkomstRegel, herkomstVan, plaatsKort, plaatsZin, standMeldingen,
  tekstBijMeldingen, tekstPeriode,
  vindplaatsTekst, WETTEKST_LIVE, wettekstMeldingen,
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

  it("leest het volle label van een chip terug: het pad, en de rest is de regeling", () => {
    const h = herkomstVan({ iri: IW9, label: "Artikel 9, lid 2, Invorderingswet 1990" });
    expect([h.bepaling, h.regeling]).toEqual(["Artikel 9, lid 2", "Invorderingswet 1990"]);
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

  it("zegt bij welke tekst van de bepaling een stuk hoort, en niets als de bron het niet zegt", () => {
    const oud = { tekst_vanaf: "2016-05-01", tekst_tot: "2022-12-31", tekststand: "eerdere tekst", op_peildatum: false };
    expect(tekstPeriode(oud)).toBe("de tekst van 1 mei 2016 tot en met 31 december 2022");
    expect(tekstBijMeldingen(oud).map((m) => m.soort)).toEqual(["eerdere-tekst", "buiten-peildatum"]);
    expect(tekstBijMeldingen(oud)[0].tekst).toContain("van 1 mei 2016 tot en met 31 december 2022");
    expect(tekstPeriode({ tekst_vanaf: "2023-01-01", tekststand: "huidige tekst" })).toBe("de huidige tekst (sinds 1 januari 2023)");
    expect(tekstBijMeldingen({ tekst_vanaf: "2023-01-01", tekststand: "huidige tekst", op_peildatum: true })).toEqual([]);
    expect(tekstBijMeldingen({ tekststand: "onbekend" }).map((m) => m.soort)).toEqual(["tekststand-onbekend"]);
    // Een Kamerstuk of een ouder bericht zonder deze velden: geen melding, geen gok.
    expect(tekstBijMeldingen({})).toEqual([]);
    expect(tekstPeriode({})).toBe("");
  });

  it("houdt de korte vindplaats van een annotatie", () => {
    expect(bepalingKort({ artikel: "9", lid: "2" })).toBe("art. 9 lid 2");
    expect(annotatieKopTekst({ citeertitel: "Invorderingswet 1990", artikel: "9" }, { bwbId: "BWBR0004770", lid: "2" }))
      .toBe("Invorderingswet 1990 – art. 9 lid 2");
  });
});


describe("wettekst buiten de kennisgraaf (connector wetgeving_live)", () => {
  it("zegt welke tekst het is, en nooit dat het een uitleg bij een andere tekst is", () => {
    const eerder = wettekstMeldingen({ tekststand: "eerdere tekst", tekst_vanaf: "2020-01-01", tekst_tot: "2020-06-30" });
    expect(eerder.map((m) => m.soort)).toEqual(["eerdere-tekst", "buiten-graaf"]);
    expect(eerder[0].tekst).toBe("Dit is de tekst van 1 januari 2020 tot en met 30 juni 2020: een eerdere tekst dan die nu geldt.");
    expect(eerder[0].tekst).not.toContain("Dit stuk noemt");
  });

  it("een toekomstige tekst en de status van de bepaling", () => {
    const later = wettekstMeldingen({ tekststand: "toekomstige tekst", tekst_vanaf: "2027-01-01",
      status: "nog niet in werking; treedt in werking op 2027-01-01" });
    expect(later.map((m) => m.soort)).toEqual(["toekomstige-tekst", "nog-niet-in-werking", "buiten-graaf"]);
    expect(later[0].tekst).toBe("Deze tekst gaat pas gelden op 1 januari 2027.");
    expect(wettekstMeldingen({ tekststand: "huidige tekst", status: "vervallen per 2026-01-01" }).map((m) => m.soort))
      .toEqual(["vervallen", "buiten-graaf"]);
  });

  it("tekstBijMeldingen kiest de wettekstmeldingen alleen bij het brontype wettekst_live", () => {
    const t = { tekststand: "eerdere tekst", tekst_vanaf: "2020-01-01", tekst_tot: "2020-06-30" };
    expect(tekstBijMeldingen(t, WETTEKST_LIVE)[0].tekst).toContain("Dit is de tekst");
    expect(tekstBijMeldingen(t, "uitspraak")[0].tekst).toContain("Dit stuk noemt");
  });
});
