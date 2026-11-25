import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { bepalingLabel, kaalLabel, knoopLabel, stapLabel } from "@/lib/bepalingLabel";
import { segmentLabel } from "@/lib/annotatieNode";
import { herkomstVan } from "@/lib/herkomst";
import vectoren from "@/lib/bepalingLabel.vectoren.json";

/** Het label van een bepaling komt uit één plek (25 nov 2026): `lib/bepalingLabel.ts`, de spiegel van `bepaling_label` in
 *  `packages/bronmodel`. Een onderdeel zonder eigen nummer stond als "Onderdeel –" in het bepalingenpaneel (drie keer onder
 *  elkaar), een onderdeel van de Leidraad als "Onderdeel c." zonder artikel. Eerder losse reparaties (#1800, de
 *  hergebruikmelding en het annotatiepaneel) lieten de andere plekken staan; deze test maakt elke nieuwe plek rood. */

const ROOT = join(__dirname, "..");
const alle = (map: string): string[] => readdirSync(join(ROOT, map)).flatMap((n) => {
  const pad = `${map}/${n}`;
  return statSync(join(ROOT, pad)).isDirectory() ? alle(pad) : /\.tsx?$/.test(pad) && !pad.includes(".test.") ? [pad] : [];
});
const CODE = [...alle("components"), ...alle("app"), ...alle("lib")];
const lees = (p: string) => readFileSync(join(ROOT, p), "utf8");

describe("bepalingLabel tegen de gedeelde vectoren (ook getoetst door bronmodel)", () => {
  it.each(vectoren.vectoren)("$iri + '$gegeven' → '$label'", (v) => {
    expect(bepalingLabel(v.iri, v.gegeven)).toBe(v.label);
  });
});

describe("het label noemt waar een onderdeel staat", () => {
  const LR = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.3a%2FCirculaire.divisie25.3a.1";

  it("een streepje en een letter zijn kaal, een eigen naam niet", () => {
    for (const l of ["Onderdeel –", "Onderdeel c.", "Lid 2", "–", "•", "Onderdeel"]) expect(kaalLabel(l)).toBe(true);
    for (const l of ["Voorwaarden standaardbetalingsregeling", "Artikel 9", "25.3a.1", "Kort uitstel particulieren"])
      expect(kaalLabel(l)).toBe(false);
  });

  it("het bepalingenpaneel (herkomstVan) noemt de streepjes en de letter bij hun artikel", () => {
    const bepaling = (iri: string, label: string) => herkomstVan({ iri, label, regeling: "Leidraad Invordering 2008" }).bepaling;
    expect([1, 2, 3].map((n) => bepaling(`${LR}%2FTekst%2FOnderdeel._${n}`, "Onderdeel –")))
      .toEqual(["Artikel 25.3a.1, 1e streepje", "Artikel 25.3a.1, 2e streepje", "Artikel 25.3a.1, 3e streepje"]);
    expect(bepaling(LR.replace(/25\.3a(\.1)?/g, "25.5$1").replace("25.5.1", "25.5.3") + "%2FTekst%2FOnderdeelc", "Onderdeel c."))
      .toBe("Artikel 25.5.3, onderdeel c");
    expect(bepaling(LR, "Voorwaarden standaardbetalingsregeling")).toBe("Voorwaarden standaardbetalingsregeling");
  });

  it("onder het eigen artikel alleen de stap; het annotatiepaneel met het begin van de tekst", () => {
    expect(stapLabel(`${LR}%2FTekst%2FOnderdeel._2`, "Onderdeel –")).toBe("2e streepje");
    expect(stapLabel(`${LR}%2FTekst%2FOnderdeelc`, "Onderdeel c.")).toBe("Onderdeel c.");
    expect(segmentLabel({ bron_iri: `${LR}%2FTekst%2FOnderdeel._1`, label: "Onderdeel –", nummer: "–",
      tekst: "voorlopige aanslagen inkomstenbelasting over het lopende jaar," }))
      .toMatch(/^1e streepje – voorlopige aanslagen inkomstenbelasting/);
    expect(knoopLabel("BWBR0024096/Circulaire.divisie25/Circulaire.divisie25.3a")).toBe("Artikel 25.3a");
  });
});

describe("niemand zet zelf een bepalingslabel in elkaar", () => {
  it("geen eigen `Artikel ${…}`, `Lid ${…}` of `Onderdeel ${…}` buiten de gedeelde functies", () => {
    const zelf = /`(?:Artikel|Lid|Onderdeel) \$\{/;
    // De gedeelde functies, en demodata die zelf een graaf nabootst (de proefgraaf, de rondleiding): die maken geen
    // label voor een echte bepaling maar spelen de graaf na. `annotatie.ts` noemt in de hergebruikmelding leden bij nummer.
    const mag = new Set(["lib/bepalingLabel.ts", "lib/samenhang.ts", "lib/graaf/proefgraaf.ts",
      "lib/rondleidingDemo.ts", "lib/annotatie.ts"]);
    expect(CODE.filter((p) => !mag.has(p) && zelf.test(lees(p)))).toEqual([]);
  });

  it("één lijst opsommingstekens voor labels", () => {
    // `wetstructuur.ts` ontleedt de wettekst zelf (een streepje aan het begin van een regel), geen label.
    const eigen = CODE.filter((p) => p !== "lib/bepalingLabel.ts" && p !== "lib/wetstructuur.ts"
      && /\[\s*"–",\s*"—"/.test(lees(p)));
    expect(eigen).toEqual([]);
  });

  it("de plekken die een bepaling noemen, gebruiken de gedeelde functie", () => {
    const gebruikt = (p: string, naam: RegExp) => expect([p, naam.test(lees(p))]).toEqual([p, true]);
    gebruikt("lib/herkomst.ts", /bepalingLabel\(/); // paneel, chips, bronnenlijst, bronpagina, werkgebiedbronnen
    gebruikt("components/antwoord/Vindplaats.tsx", /herkomstVan\(/); // de korte vorm in de bronnenlijst onder een antwoord
    gebruikt("lib/graaf/model.ts", /bepalingLabel\(/);
    gebruikt("lib/graaf/ketenZin.ts", /bepalingLabel\(/);
    gebruikt("lib/reeks.ts", /bepalingLabel\(/);
    gebruikt("lib/annotatie.ts", /bepalingLabel\(/); // de keuzekaart (kandidaatNaam)
    gebruikt("lib/annotatieNode.ts", /stapLabel\(/);
    gebruikt("lib/bronPlaats.ts", /stapLabel\(/);
    gebruikt("components/werkplek/ContextPaneel.tsx", /herkomstVan\(/);
  });
});
