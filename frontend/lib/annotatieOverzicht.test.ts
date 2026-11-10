import { describe, expect, it } from "vitest";

import {
  groepeerPerRegeling, inWeergave, isKlaarOmAfTeRonden, isTeBeoordelen, kleurstrip, legeWeergave, sorteerTeBeoordelen,
  uitlegWeergave, weergaveUitParam, WEERGAVEN, zoek,
} from "./annotatieOverzicht";
import { JAS_KLASSEN } from "./jas";
import type { DocumentSamenvatting } from "./types";
import { bepalingKort } from "./herkomst";

function doc(over: Partial<DocumentSamenvatting> = {}): DocumentSamenvatting {
  return {
    slug: "s1", bwbId: "BWBR1", artikel: "9", lid: "", citeertitel: "Invorderingswet 1990",
    werkgebied: "", status: "in_review", aantal_elementen: 3, te_beoordelen: 3,
    per_aandacht: {}, per_klasse: {}, laatste_model: "", updated: "2026-08-01T10:00:00Z",
    ...over,
  };
}

describe("te doen", () => {
  it("telt alleen wat de jurist niet heeft afgerond", () => {
    expect(isTeBeoordelen(doc({ te_beoordelen: 2 }))).toBe(true);
    expect(isTeBeoordelen(doc({ te_beoordelen: 0 }))).toBe(false);
    // Afgerond mét open elementen is een bewuste keuze, geen restpost.
    expect(isTeBeoordelen(doc({ status: "geaccordeerd", te_beoordelen: 5 }))).toBe(false);
  });

  it("noemt een laag klaar als alles beoordeeld is en alleen het afronden ontbreekt", () => {
    expect(isKlaarOmAfTeRonden(doc({ te_beoordelen: 0 }))).toBe(true);
    expect(isKlaarOmAfTeRonden(doc({ te_beoordelen: 1 }))).toBe(false);
    // Afronden is een handeling: wat afgerond is, is niet meer "klaar om".
    expect(isKlaarOmAfTeRonden(doc({ status: "geaccordeerd", te_beoordelen: 0 }))).toBe(false);
    expect(isKlaarOmAfTeRonden(doc({ status: "gepromoveerd", te_beoordelen: 0 }))).toBe(false);
    // Zonder actuele markeringen is er niets beoordeeld.
    expect(isKlaarOmAfTeRonden(doc({ aantal_elementen: 0, te_beoordelen: 0 }))).toBe(false);
  });

  it("verdeelt de lagen zonder overlap over de weergaven; alleen een lege laag staat uitsluitend bij Alles", () => {
    const open = doc({ te_beoordelen: 2 });
    const klaar = doc({ te_beoordelen: 0 });
    const akkoord = doc({ status: "geaccordeerd", te_beoordelen: 1 });
    const inGraaf = doc({ status: "gepromoveerd", te_beoordelen: 0 });
    const leeg = doc({ aantal_elementen: 0, te_beoordelen: 0 });
    const weergavenVan = (d: DocumentSamenvatting) =>
      WEERGAVEN.filter((w) => inWeergave(d, w.waarde)).map((w) => w.waarde);
    expect(weergavenVan(open)).toEqual(["te-beoordelen", "alles"]);
    expect(weergavenVan(klaar)).toEqual(["af-te-ronden", "alles"]);
    expect(weergavenVan(akkoord)).toEqual(["afgerond", "alles"]);
    expect(weergavenVan(inGraaf)).toEqual(["afgerond", "alles"]);
    expect(weergavenVan(leeg)).toEqual(["alles"]);
  });

  it("legt elke weergave uit en noemt dat de aantallen bepalingen tellen", () => {
    for (const { waarde } of WEERGAVEN) {
      expect(uitlegWeergave(waarde)).toContain("De aantallen tellen bepalingen, niet markeringen.");
      expect(legeWeergave(waarde)).toBeTruthy();
    }
    expect(legeWeergave("te-beoordelen")).not.toContain("afgehandeld");
  });

  it("zet rood boven geel, en daarna wat het langst stil ligt", () => {
    const geel = doc({ slug: "geel", per_aandacht: { geel: 4 } });
    const rood = doc({ slug: "rood", per_aandacht: { rood: 1 } });
    const oud = doc({ slug: "oud", updated: "2026-01-01T10:00:00Z" });
    const nieuw = doc({ slug: "nieuw", updated: "2026-08-18T10:00:00Z" });

    expect(sorteerTeBeoordelen([nieuw, geel, oud, rood]).map((d) => d.slug))
      .toEqual(["rood", "geel", "oud", "nieuw"]);
  });

  it("laat de invoer ongemoeid", () => {
    const lijst = [doc({ slug: "a" }), doc({ slug: "b", per_aandacht: { rood: 1 } })];
    sorteerTeBeoordelen(lijst);
    expect(lijst.map((d) => d.slug)).toEqual(["a", "b"]);
  });
});

describe("groeperen per regeling", () => {
  it("groepeert op bwbId en sorteert artikelen numeriek", () => {
    const groepen = groepeerPerRegeling([
      doc({ slug: "a", bwbId: "BWBR1", artikel: "10" }),
      doc({ slug: "b", bwbId: "BWBR1", artikel: "2" }),
      doc({ slug: "c", bwbId: "BWBR2", citeertitel: "Awb" }),
    ]);

    expect(groepen.map((g) => g.naam)).toEqual(["Awb", "Invorderingswet 1990"]);
    // '10' na '2': lexicaal sorteren zou de volgorde omdraaien.
    expect(groepen[1].documenten.map((d) => d.artikel)).toEqual(["2", "10"]);
  });

  it("valt terug op het bwbId als er geen naam is", () => {
    expect(groepeerPerRegeling([doc({ citeertitel: "" })])[0].naam).toBe("BWBR1");
  });

  it("sorteert leden numeriek binnen hetzelfde artikel", () => {
    const groep = groepeerPerRegeling([
      doc({ slug: "a", artikel: "9", lid: "10" }),
      doc({ slug: "b", artikel: "9", lid: "2" }),
    ])[0];
    expect(groep.documenten.map((d) => d.lid)).toEqual(["2", "10"]);
  });

  it("zet onderdelen van één lid op volgorde, na het lid zelf", () => {
    const groep = groepeerPerRegeling([
      doc({ slug: "c", artikel: "6", lid: "1", label: "Onderdeel c." }),
      doc({ slug: "a", artikel: "6", lid: "1", label: "Onderdeel a." }),
      doc({ slug: "l", artikel: "6", lid: "1", label: "Lid 1" }),
    ])[0];
    expect(groep.documenten.map((d) => d.slug)).toEqual(["l", "a", "c"]);
  });
});

describe("zoeken", () => {
  const lijst = [
    doc({ slug: "iw", citeertitel: "Invorderingswet 1990", artikel: "9" }),
    doc({ slug: "zvw", citeertitel: "Zorgverzekeringswet", bwbId: "BWBR2", artikel: "43", lid: "2" }),
  ];

  it("matcht woord voor woord, ongeacht volgorde", () => {
    expect(zoek(lijst, "zorgverzekering 43").map((d) => d.slug)).toEqual(["zvw"]);
    expect(zoek(lijst, "43 zorg").map((d) => d.slug)).toEqual(["zvw"]);
  });

  it("vindt een bepaling op wat erboven staat: artikel, lid en onderdeel", () => {
    const onderdeel = doc({ slug: "o", artikel: "6", lid: "1", soort: "Onderdeel", label: "Onderdeel c." });
    expect(zoek([onderdeel], "artikel 6")).toHaveLength(1);
    expect(zoek([onderdeel], "art. 6 lid 1")).toHaveLength(1);
    expect(zoek([onderdeel], "onderdeel c")).toHaveLength(1);
    expect(zoek([onderdeel], "onderdeel d")).toHaveLength(0);
    // Een nummer is een heel woord: de 9 uit "1990" is geen artikel 9.
    const iw = doc({ slug: "iw", citeertitel: "Invorderingswet 1990", artikel: "25", lid: "1" });
    expect(zoek([iw], "artikel 9")).toHaveLength(0);
    expect(zoek([iw], "invordering 25")).toHaveLength(1);
    expect(zoek([iw], "1990")).toHaveLength(1);
  });

  it("geeft alles terug bij een lege term", () => {
    expect(zoek(lijst, "   ")).toHaveLength(2);
  });

  it("vindt op bwbId en op de vindplaats", () => {
    expect(zoek(lijst, "BWBR2").map((d) => d.slug)).toEqual(["zvw"]);
    expect(zoek(lijst, "lid 2").map((d) => d.slug)).toEqual(["zvw"]);
  });
});

describe("kleurstrip", () => {
  it("volgt de canonieke JAS-volgorde, niet de invoervolgorde", () => {
    const strip = kleurstrip({ Voorwaarde: 2, Rechtssubject: 5 }, JAS_KLASSEN);
    expect(strip).toEqual([
      { klasse: "Rechtssubject", aantal: 5 },
      { klasse: "Voorwaarde", aantal: 2 },
    ]);
  });

  it("laat onbekende klassen niet verdwijnen – de strip mag niet liegen", () => {
    const strip = kleurstrip({ Rechtssubject: 1, Verzonnen: 3 }, JAS_KLASSEN);
    expect(strip.map((s) => s.klasse)).toEqual(["Rechtssubject", "Verzonnen"]);
  });

  it("slaat nullen over", () => {
    expect(kleurstrip({ Rechtssubject: 0 }, JAS_KLASSEN)).toEqual([]);
  });
});

describe("weergave", () => {
  it("valt terug op de werkvoorraad", () => {
    expect(weergaveUitParam("alles")).toBe("alles");
    expect(weergaveUitParam("af-te-ronden")).toBe("af-te-ronden");
    expect(weergaveUitParam("afgerond")).toBe("afgerond");
    expect(weergaveUitParam(null)).toBe("te-beoordelen");
    expect(weergaveUitParam("onzin")).toBe("te-beoordelen");
  });
});

describe("vindplaats", () => {
  it("noemt het lid alleen als het er is", () => {
    expect(bepalingKort(doc())).toBe("art. 9");
    expect(bepalingKort(doc({ lid: "2" }))).toBe("art. 9 lid 2");
    expect(bepalingKort(doc({ lid: "1", soort: "Onderdeel", label: "Onderdeel c." }))).toBe("art. 9 lid 1, onderdeel c");
    expect(bepalingKort(doc({ lid: "1", soort: "Lid", label: "Lid 1" }))).toBe("art. 9 lid 1");
  });
});

describe("decimale bepalingnummers", () => {
  it("sorteert subbepalingen per segment, niet op het eerste cijferblok", () => {
    // Alleen het eerste cijferblok lezen gaf alle "25.x.y" dezelfde sleutel (25), waardoor de
    // volgorde in de werkvoorraad van een beleidsregel willekeurig was.
    const groep = groepeerPerRegeling([
      doc({ slug: "a", artikel: "25.10" }),
      doc({ slug: "b", artikel: "25.2" }),
      doc({ slug: "c", artikel: "25.1.1" }),
      doc({ slug: "d", artikel: "3" }),
    ])[0];
    expect(groep.documenten.map((d) => d.artikel)).toEqual(["3", "25.1.1", "25.2", "25.10"]);
  });

  it("zet een letter-segment op zijn plaats tussen de cijfers", () => {
    const groep = groepeerPerRegeling([
      doc({ slug: "a", artikel: "73.4" }),
      doc({ slug: "b", artikel: "73.3a" }),
      doc({ slug: "c", artikel: "73.3" }),
    ])[0];
    expect(groep.documenten.map((d) => d.artikel)).toEqual(["73.3", "73.3a", "73.4"]);
  });

  it("noemt een divisie een bepaling en geen artikel met leden", () => {
    expect(bepalingKort({ artikel: "9", lid: "2" })).toBe("art. 9 lid 2");
    expect(bepalingKort({ artikel: "25", lid: "", soort: "Divisie" })).toBe("bepaling 25");
    expect(bepalingKort({ artikel: "25", lid: "25.1", soort: "Divisie" })).toBe(
      "bepaling 25, 25.1",
    );
  });
});
