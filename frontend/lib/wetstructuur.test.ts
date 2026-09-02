import { describe, expect, it } from "vitest";

import { blokkenVan, ontleed } from "./wetstructuur";
import vectorenBestand from "./wetstructuur.vectoren.json";

describe("ontleed – de gedeelde vectoren", () => {
  // Dezelfde lijst die `api/tests/test_wetstructuur.py` draait. Loopt één van beide weg, dan staat
  // een onderdeel in de PDF op een andere marge dan in de werkplek.
  const { vectoren } = vectorenBestand as {
    vectoren: { _geval: string; regel: string; uit: Record<string, unknown> }[];
  };

  it.each(vectoren.map((v) => [v._geval, v] as const))("%s", (_naam, v) => {
    expect(ontleed(v.regel)).toEqual(v.uit);
  });

  it("dekt de valkuilen die de parser moet kennen", () => {
    // Zonder deze bewaking kan iemand de vectoren uitkleden tot alleen de makkelijke gevallen.
    const gevallen = vectoren.map((v) => v._geval).join(" ");
    expect(gevallen).toContain("VALKUIL");
    expect(vectoren.filter((v) => v._geval.includes("VALKUIL")).length).toBeGreaterThanOrEqual(4);
  });
});

describe("ontleed – de tekst blijft heel", () => {
  it("geeft elk teken terug dat erin ging", () => {
    // De weergave verplaatst tekst, ze verandert hem niet. Dit is de eis waaronder deze functie
    // mag bestaan: wat eruit komt moet weer tot de regel samen te stellen zijn, op de scheidende
    // spaties en de dubbele punt na.
    const regels = [
      "a. rijksbelastingen: belastingen als bedoeld in artikel 1;",
      "1°. Koninkrijk: Koninkrijk der Nederlanden;",
      "– de gevraagde gegevens zijn niet verstrekt;",
      "Een belastingaanslag is invorderbaar zes weken na de dagtekening.",
    ];
    for (const regel of regels) {
      const { nummer, term, tekst } = ontleed(regel);
      const samen = [nummer, term ? `${term}:` : "", tekst].filter(Boolean).join(" ");
      expect(samen.replace(/\s+/g, " ")).toBe(regel.replace(/\s+/g, " "));
    }
  });
});

describe("ontleed – het niveau", () => {
  it("zet graden een niveau dieper dan letters", () => {
    // Precies wat art. 2 lid 1 IW 1990 nodig heeft: 1°.–4°. hangen onder de container tussen a. en b.
    expect(ontleed("a. rijksbelastingen: iets;").niveau).toBe(1);
    expect(ontleed("1°. Koninkrijk: Koninkrijk der Nederlanden;").niveau).toBe(2);
  });

  it("houdt 1. en 1°. uit elkaar", () => {
    // Zonder de graden-tak vallen ze samen en verdwijnt de nesting – dezelfde reden waarom
    // `_onderdeel_nummer` in de agent de ° laat staan.
    expect(ontleed("1. de ontvanger stelt de termijn vast;").niveau).toBe(1);
    expect(ontleed("1°. de ontvanger stelt de termijn vast;").niveau).toBe(2);
  });

  it("laat een aanhef op niveau 0 staan", () => {
    expect(ontleed("Deze wet verstaat onder:").niveau).toBe(0);
    expect(ontleed("Deze wet verstaat onder:").term).toBe("");
  });
});

describe("blokkenVan – de invariant die de weergave draagt", () => {
  // De regels zoals `regelsVan` ze opbouwt: lidnummer los, voorvoegsel in de regel.
  const regels = [
    { lid: "1", regel: "1. Deze wet verstaat onder:\na. rijksbelastingen: belastingen als bedoeld in artikel 1;\n1°. Koninkrijk: Koninkrijk der Nederlanden;\nb. de ontvanger: de functionaris;" },
    { lid: "2", regel: "2. Waar in deze wet wordt gesproken van beslag, wordt daaronder begrepen:\n– beslag onder derden;\n– bodembeslag;" },
  ];

  it("laat elk blok exact op zijn offset in de brontekst staan", () => {
    // DIT is waar alles aan hangt. Klopt dit niet, dan wijst een zelfgemaakte markering naar de
    // verkeerde tekst — en dat gebeurt stil, want de markering ziet er in de UI prima uit.
    const bron = regels.map((r) => r.regel).join("\n\n");
    for (const b of blokkenVan(regels)) {
      expect(bron.slice(b.offset, b.offset + b.regel.length)).toBe(b.regel);
    }
  });

  it("houdt de blokken in de volgorde van de wet", () => {
    const blokken = blokkenVan(regels);
    // Het lidnummer telt als nummer op niveau 0 – het is de kop van het lid, geen onderdeel.
    expect(blokken.map((b) => b.nummer)).toEqual(["1.", "a.", "1°.", "b.", "2.", "–", "–"]);
    // 1°. hangt onder a. – dat is precies wat er zonder inspringing niet te zien was.
    expect(blokken.map((b) => b.niveau)).toEqual([0, 1, 2, 1, 0, 1, 1]);
  });

  it("markeert het eerste blok van elk lid, en draagt het lidnummer mee", () => {
    const blokken = blokkenVan(regels);
    expect(blokken.filter((b) => b.eersteVanLid).map((b) => b.lid)).toEqual(["1", "2"]);
    expect(blokken.map((b) => b.lid)).toEqual(["1", "1", "1", "1", "2", "2", "2"]);
  });

  it("werkt op een artikel zonder genummerde leden", () => {
    const los = [{ lid: "", regel: "Een belastingaanslag is invorderbaar zes weken na de dagtekening." }];
    const blokken = blokkenVan(los);
    expect(blokken).toHaveLength(1);
    expect(blokken[0].offset).toBe(0);
    expect(blokken[0].niveau).toBe(0);
  });

  it("geeft een lege lijst bij lege invoer", () => {
    expect(blokkenVan([])).toEqual([]);
  });
});

describe("blokkenVan – het lidvoorvoegsel is geen onderdeel", () => {
  it("leest '1. ' aan het begin van lid 1 als de lidkop, niet als onderdeel a-stijl", () => {
    // `regelsVan` zet "1. " vóór de lidtekst, en dat heeft exact de vorm van een onderdeelnummer.
    // Zonder onderscheid springt de aanhef van élk genummerd lid in alsof het een onderdeel was en
    // verschuift de hele bepaling een niveau. Alleen `blokkenVan` weet dat het om het lid gaat.
    const blokken = blokkenVan([{ lid: "1", regel: "1. De ontvanger verleent uitstel.\na. op verzoek;" }]);
    expect(blokken[0].niveau).toBe(0);
    expect(blokken[0].nummer).toBe("1.");
    expect(blokken[0].tekst).toBe("De ontvanger verleent uitstel.");
    expect(blokken[1].niveau).toBe(1);
  });

  it("laat een onderdeel '1.' verderop in het lid wél een onderdeel zijn", () => {
    const blokken = blokkenVan([{ lid: "3", regel: "3. De aanhef:\n1. het eerste onderdeel;" }]);
    expect(blokken[0].nummer).toBe("3.");
    expect(blokken[0].niveau).toBe(0);
    expect(blokken[1].nummer).toBe("1.");
    expect(blokken[1].niveau).toBe(1);
  });

  it("raakt een lid met een letter (2a) niet kwijt", () => {
    const blokken = blokkenVan([{ lid: "2a", regel: "2a. Een ingevoegd lid." }]);
    expect(blokken[0].nummer).toBe("2a.");
    expect(blokken[0].niveau).toBe(0);
    expect(blokken[0].tekst).toBe("Een ingevoegd lid.");
  });
});
