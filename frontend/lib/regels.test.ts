import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  DRAGER_ROL_LABEL, REGEL_SOORT_LABEL, VOORBEELD_OORDEEL_LABEL, buren, inKetenVolgorde, invoerVan, regelAlsMarkdown,
  regelsAlsMarkdown, regelsBijBegrip, voorbeeldenBij, type Regel, type RegelKeten,
} from "./regels";

/** R4 van Termijnen in de vorm van de api: één rekenregel met twee gevallen (de vorm van `regel_store._regel`). */
function r4(over: Partial<Regel> = {}): Regel {
  return {
    id: "r4", werkgebied_id: "w", status: "concept", revisie: 3, herkomst: "import", opvolger_van: null,
    inhoud: {
      soort: "rekenregel", regelbegrip_id: "rb4", uitvoer_begrip_id: "tb", onderwerp_begrip_id: "",
      invoer: [{ begrip_id: "bedrag", rol: "invoer" }, { begrip_id: "aantal", rol: "parameter" }],
      gevallen: [
        { label: "1", voorwaarden: null, uitkomst: [{ soort: "begrip", begrip_id: "bedrag" }], voorrang: 0 },
        { label: "2", voorwaarden: null, uitkomst: [{ soort: "tekst", tekst: "nihil" }], voorrang: 1 },
      ],
      voorbeelden: [
        { geval: "1", invoer: "€ 1.200 in 12 termijnen", uitkomst: "€ 100", oordeel: "juist", toelichting: "" },
        { geval: "2", invoer: "geen aanslag", uitkomst: "nihil", oordeel: "open", toelichting: "" },
      ],
      toelichting: "Uit art. 9 lid 1.", brontype: "wet", lidwoord: "het",
    },
    naam: "bepalen termijnbedrag", uitvoer: "termijnbedrag",
    regeltekst: {
      tekst: "Het termijnbedrag moet bepaald worden volgens het geval dat geldt:",
      markdown: "_Het termijnbedrag_ moet bepaald worden volgens het geval dat geldt:\n- **Geval 2 (gaat voor)**: nihil.\n- **Geval 1**: _bedrag_.",
      gevallen: [{ label: "2", tekst: "nihil." }, { label: "1", tekst: "bedrag." }],
    },
    begrippen: { bedrag: { id: "bedrag", naam: "bedrag van de aanslag", status: "geaccordeerd" },
      aantal: { id: "aantal", naam: "aantal termijnen", status: "concept" } },
    dragers: [
      { id: "d1", element_id: "el-9-1", rol: "grondslag", geval: "", bewijs: null, beoordeling: "akkoord", beoordeeld_door: "jurist", actualiteit: "actueel" },
      { id: "d2", element_id: "el-9-2", rol: "voorwaarde", geval: "2", bewijs: null, beoordeling: "afgewezen", beoordeeld_door: "jurist" },
    ],
    accorderen: { mag: false, redenen: ["Nog geen beoordeeld voorbeeld bij geval 2."] }, signalen: [],
    aangemaakt_door: "import", aangemaakt: null, gewijzigd: null,
    geaccordeerd_door: null, geaccordeerd_op: null, geaccordeerd_revisie: null,
    ...over,
  };
}

describe("de vorm volgt de api (regel_contracts.py)", () => {
  const bron = readFileSync(path.resolve(__dirname, "../../api/app/regel_contracts.py"), "utf8");
  const waarden = (klasse: string) => {
    const blok = bron.split(`class ${klasse}(str, Enum):`)[1].split(/\n\n/)[0];
    return [...blok.matchAll(/^\s+\w+ = "([a-z_]+)"/gm)].map((m) => m[1]).sort();
  };
  it.each([
    ["RegelSoort", REGEL_SOORT_LABEL], ["DragerRol", DRAGER_ROL_LABEL], ["VoorbeeldOordeel", VOORBEELD_OORDEEL_LABEL],
  ] as const)("%s", (klasse, labels) => expect(Object.keys(labels).sort()).toEqual(waarden(klasse)));
});

describe("regelAlsMarkdown", () => {
  const md = regelAlsMarkdown(r4());
  it("is kopieertekst: kopjes en lijsten, geen tabel", () => {
    expect(md).toMatch(/^# bepalen termijnbedrag\n/);
    expect(md).not.toMatch(/^\|/m);
    expect(md).toContain("- **Geval 2 (gaat voor)**: nihil.");
  });
  it("noemt invoer en parameters, de grondslag die niet is afgewezen en de voorbeelden met hun oordeel", () => {
    expect(md).toContain("- bedrag van de aanslag\n- aantal termijnen (parameter)");
    expect(md).toContain("- el-9-1 (akkoord)");
    expect(md).not.toContain("el-9-2");
    expect(md).toContain("- Geval 1: € 1.200 in 12 termijnen → € 100 (juridisch juist)");
    expect(md).toContain("**Toelichting**\n\nUit art. 9 lid 1.");
  });
});

describe("de keten", () => {
  const keten: RegelKeten = {
    regels: [], volgorde: ["r2", "r4"], basisgegevens: [{ begrip_id: "bedrag", naam: "bedrag van de aanslag" }],
    pijlen: [{ van: "r2", naar: "r4", begrip_id: "aantal" }], signalen: [{ soort: "kring", regel_ids: ["r4"], melding: "Een kring." }],
  };
  it("zet de regels van onder naar boven, en wat de keten niet kent achteraan", () => {
    expect(inKetenVolgorde([{ id: "x" }, { id: "r4" }, { id: "r2" }], keten).map((r) => r.id)).toEqual(["r2", "r4", "x"]);
    expect(inKetenVolgorde([{ id: "b" }, { id: "a" }], null).map((r) => r.id)).toEqual(["b", "a"]);
  });
  it("kent de buren van een regel", () => {
    expect(buren(keten, "r4")).toEqual({ volgtOp: ["r2"], leidtTot: [] });
    expect(buren(keten, "r2")).toEqual({ volgtOp: [], leidtTot: ["r4"] });
  });
  it("de export noemt basisgegevens en signalen, en elke regel als eigen kop", () => {
    const md = regelsAlsMarkdown([r4()], keten, "Termijnen");
    expect(md).toMatch(/^# Afleidingsregels – Termijnen/);
    expect(md).toContain("- bedrag van de aanslag");
    expect(md).toContain("- Een kring.");
    expect(md).toContain("## bepalen termijnbedrag");
  });
});

describe("hulpjes van de kaart", () => {
  it("splitst invoer en parameters", () => {
    expect(invoerVan(r4())).toEqual({ invoer: ["bedrag van de aanslag"], parameters: ["aantal termijnen"] });
  });
  it("de voorbeelden per geval; bij één geval alle", () => {
    expect(voorbeeldenBij(r4(), "2").map((v) => v.uitkomst)).toEqual(["nihil"]);
    const enkel = r4();
    enkel.inhoud = { ...enkel.inhoud, gevallen: [enkel.inhoud.gevallen[0]] };
    expect(voorbeeldenBij(enkel, "").length).toBe(2);
  });
  it("de begripskaart: afgeleid door en gebruikt in, zonder afgewezen regels (U4)", () => {
    const afgewezen = r4({ id: "r9", status: "afgewezen" });
    const r6 = r4({ id: "r6", inhoud: { ...r4().inhoud, uitvoer_begrip_id: "ander", invoer: [{ begrip_id: "tb", rol: "invoer" }] } });
    expect(regelsBijBegrip([r4(), r6, afgewezen], "tb")).toEqual({ afgeleidDoor: [r4()], gebruiktIn: [r6] });
    expect(regelsBijBegrip([r4()], "bedrag").gebruiktIn.map((r) => r.id)).toEqual(["r4"]);
  });
});
