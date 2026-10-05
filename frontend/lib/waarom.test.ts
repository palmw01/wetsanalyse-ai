import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentRun, ElementTrace } from "./types";
import { beurtSamenvatting, laatsteJuristBeslissing, laatsteRun, redenVoorAlternatief, waaromVan } from "./waarom";
import { verklaar, type Verklaringen } from "./verklaringen";

const V: Verklaringen = {
  besluit: { regel: { naam: "vaste regel", uitleg: "Besloten zonder model." }, model: { naam: "model", uitleg: "Het model koos." },
    specificiteit: { naam: "specificiteit", uitleg: "De meest specifieke klasse wint." } },
  regels: { "jas.tijd.duur": { naam: "Termijn", uitleg: "Een duur.", soort: "detector" }, "JAS-PRIORITY-001": { naam: "JAS-PRIORITY-001", uitleg: "Tijd gaat voor." } },
  detectie: { TEMPORAL_DURATION: { naam: "Tijdsduur", uitleg: "Een termijn." } },
  twijfel: { DETECTOR_CONFLICT: { naam: "Detectoren spreken elkaar tegen", uitleg: "Twee klassen." } },
  resolutie: { "R-CONFLICT-KEEP": { naam: "Klasse behouden", uitleg: "De reviewer bevestigde." } },
  validatie: { V_ANKER: { naam: "Anker klopt niet", uitleg: "" } },
};

const TRACE: ElementTrace = {
  kandidaat: {
    gedegradeerd: false, mogelijke_klassen: ["Tijdsaanduiding", "Variabele en variabelewaarde"],
    bewijs: [
      { detector: "temporeel", code: "TEMPORAL_DURATION", regel: "jas.tijd.duur", detail: "binnen zes weken" },
      { detector: "lexicaal", code: "TEMPORAL_DURATION", regel: "jas.tijd.duur", detail: "binnen zes weken" },
      { detector: "np", code: "ONBEKEND_SIGNAAL" },
      { detector: "-", code: "PRIORITY_APPLIED" },
    ],
  },
  beslissing: { door: "regel", klasse: "Tijdsaanduiding" },
  twijfel: [{ reden: "DETECTOR_CONFLICT", alternatieven: ["Variabele en variabelewaarde"] }],
  resolutie: [{ regel: "R-CONFLICT-KEEP", motivering: "termijn" }],
  vraag: "",
};

describe("waaromVan", () => {
  it("vertaalt het spoor naar leesbare namen, met de code ernaast", () => {
    const w = waaromVan({ herkomst: "agent", trace: TRACE, jas_subtype: "" }, V);
    expect(w.handmatig).toBe(false);
    expect(w.besluit).toMatchObject({ naam: "vaste regel", code: "regel" });
    // Twee detectoren met dezelfde regel worden één regel; het administratieve bewijs valt weg.
    expect(w.bewijs).toEqual([
      { naam: "Termijn", code: "jas.tijd.duur", uitleg: "Een duur.", detail: "binnen zes weken" },
      { naam: "ONBEKEND_SIGNAAL", code: "ONBEKEND_SIGNAAL", uitleg: "" },
    ]);
    expect(w.twijfel[0].naam).toBe("Detectoren spreken elkaar tegen");
    expect(w.resolutie[0]).toMatchObject({ naam: "Klasse behouden", detail: "termijn" });
    expect(w.subtype).toBeUndefined();
  });

  it("toont zonder vocabulaire de codes zelf", () => {
    const w = waaromVan({ herkomst: "agent", trace: TRACE }, undefined);
    expect(w.besluit?.naam).toBe("regel");
    expect(w.bewijs[0].naam).toBe("jas.tijd.duur");
  });

  it("noemt bij specificiteit de voorrangsregel", () => {
    const w = waaromVan({ herkomst: "agent", trace: { beslissing: { door: "specificiteit", reden: "JAS-PRIORITY-001" } } }, V);
    expect(w.besluit).toMatchObject({ naam: "specificiteit", detail: "JAS-PRIORITY-001", uitleg: "Tijd gaat voor." });
  });

  it("markeert een gedegradeerde kandidaat en bewaart de modelvraag", () => {
    const w = waaromVan({ herkomst: "agent", trace: { kandidaat: { gedegradeerd: true }, beslissing: { door: "model" }, vraag: "k1 | …" } }, V);
    expect(w.gedegradeerd).toBe(true);
    expect(w.vraag).toBe("k1 | …");
  });

  it("is handmatig zonder spoor, en noemt de laatste beslissing van een jurist", () => {
    const w = waaromVan({ herkomst: "mens", jas_subtype: "parameter", beslissingen: [
      { type: "approve", actor: "jan", tijd: "2026-10-01T10:00:00Z", comment: "", wijziging: {} },
      { type: "comment", actor: "piet", tijd: "2026-10-02T10:00:00Z", comment: "hm", wijziging: {} },
    ] }, V);
    expect(w).toMatchObject({ handmatig: true, subtype: "parameter", bewijs: [] });
    expect(w.jurist).toMatch(/^akkoord bevonden door jan op /);
  });
});

describe("redenVoorAlternatief", () => {
  it("gebruikt de twijfel uit het spoor in plaats van de vaste motivatie", () => {
    expect(redenVoorAlternatief({ herkomst: "agent", trace: TRACE }, "Variabele en variabelewaarde", "ook mogelijk", V))
      .toBe("Detectoren spreken elkaar tegen: Twee klassen.");
    expect(redenVoorAlternatief({ herkomst: "agent", trace: TRACE }, "Rechtssubject", "ook mogelijk", V)).toBe("ook mogelijk");
  });
});

describe("verklaar", () => {
  it("zoekt een code met achtervoegsel op het deel vóór de dubbele punt", () => {
    expect(verklaar({ twijfel: { X: { naam: "Iks", uitleg: "" } } }, "twijfel", "X:detail").naam).toBe("Iks");
  });
});

describe("laatsteJuristBeslissing", () => {
  it("negeert opmerkingen en geeft niets zonder beslissing", () => {
    expect(laatsteJuristBeslissing([{ type: "comment", actor: "a", tijd: "", comment: "x", wijziging: {} }])).toBeUndefined();
    expect(laatsteJuristBeslissing()).toBeUndefined();
  });
});

describe("beurtsamenvatting", () => {
  const run = (tijd: string, meting?: object) => ({ ronde: 1, model: "m", provider: "p", agent_versie: "", stop_reden: "", tijd,
    instellingen: meting ? { meting } : undefined }) as AgentRun;

  it("vat de laatste ronde samen: resultaat, zonder zinsontleding en duur", () => {
    const meting = { fasen: [{ fase: "Detectie", samenvatting: "…", ms: 1200 }, { fase: "Resultaat", samenvatting: "12 voorgesteld", ms: 3000 }],
      gedegradeerd: ["urn:a"] };
    const r = laatsteRun([{ geproduceerd_door: run("2026-10-01T10:00:00Z") }, { geproduceerd_door: run("2026-10-02T10:00:00Z", meting) }, { geproduceerd_door: null }]);
    expect(beurtSamenvatting(r?.instellingen?.meting)).toBe("12 voorgesteld · 1 bronnode zonder zinsontleding · 4,2 s");
  });

  it("is leeg zonder meting", () => {
    expect(beurtSamenvatting(undefined)).toBe("");
    expect(beurtSamenvatting({ fasen: [] })).toBe("");
  });
});

describe("haalVerklaringen", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it("vraagt één keer per pagina, en opnieuw na een fout", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response("nee", { status: 503 }))
      .mockResolvedValueOnce(Response.json(V));
    vi.stubGlobal("fetch", fetch);
    const { haalVerklaringen } = await import("./verklaringen");
    expect(await haalVerklaringen()).toEqual({});
    expect(await haalVerklaringen()).toEqual(V);
    expect(await haalVerklaringen()).toEqual(V);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(String(fetch.mock.calls[0][0])).toBe("/api/annotatie/v2/verklaringen");
  });
});
