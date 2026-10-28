import { describe, expect, it } from "vitest";

import {
  annotatieDoelVan, artefactLabel, artefactSleutel, artefactVanBericht, isTeOpenen, parseArtefact, werkgebiedArtefactVan,
  werkgebiedLabel,
} from "./artefact";

const IRI = "urn:bwb:BWBR0004770:artikel:9:lid:1";

describe("parseArtefact", () => {
  it("neemt een geldig artefact van elke soort over", () => {
    expect(parseArtefact({ soort: "annotatie", ref: { bron_iri: IRI }, titel: "Art. 9" }))
      .toEqual({ soort: "annotatie", ref: { bron_iri: IRI }, titel: "Art. 9" });
    expect(parseArtefact({ soort: "begrippen", ref: { werkgebied_id: "w", run_id: "r" } })?.titel).toBe("");
    expect(parseArtefact({ soort: "regels", ref: {} })?.soort).toBe("regels");
  });

  it("weigert een onbekende soort of een ref zonder de verplichte sleutels", () => {
    expect(parseArtefact({ soort: "plaatje", ref: {} })).toBeUndefined();
    expect(parseArtefact({ soort: "annotatie", ref: {} })).toBeUndefined();
    expect(parseArtefact({ soort: "begrippen", ref: { werkgebied_id: "w" } })).toBeUndefined();
    expect(parseArtefact({ soort: "begrippen", ref: [] })).toBeUndefined();
    expect(parseArtefact(null)).toBeUndefined();
  });
});

describe("artefactVanBericht", () => {
  it("leest het artefactveld", () => {
    const a = artefactVanBericht({ artefact: { soort: "begrippen", ref: { werkgebied_id: "w", run_id: "r" }, titel: "Invordering" } });
    expect(werkgebiedArtefactVan(a)).toEqual({ soort: "begrippen", werkgebied_id: "w", run_id: "r", titel: "Invordering" });
    const b = artefactVanBericht({ artefact: { soort: "bronnen", ref: { werkgebied_id: "w", run_id: "r2" }, titel: "Inv" } });
    expect(werkgebiedArtefactVan(b)?.soort).toBe("bronnen");
    expect(parseArtefact({ soort: "bronnen", ref: { werkgebied_id: "w" } })).toBeUndefined();
  });

  it("maakt van een ouder bericht met alleen een bronnode een annotatie-artefact", () => {
    const a = artefactVanBericht({ annotatie_doel: { bron_iri: IRI, label: "IW – art. 9 lid 1", snapshot_id: "s" }, annotatie_titel: "" });
    expect(a?.soort).toBe("annotatie");
    expect(a?.titel).toBe("IW – art. 9 lid 1");
    expect(annotatieDoelVan(a)).toEqual({ bron_iri: IRI, label: "IW – art. 9 lid 1", snapshot_id: "s" });
  });

  it("een bericht zonder verwijzing heeft geen artefact; alleen een slug is een tombstone, geen artefact", () => {
    expect(artefactVanBericht({ annotatie_titel: "Art. 3" })).toBeUndefined();
  });
});

describe("annotatieDoelVan en werkgebiedArtefactVan", () => {
  it("geven alleen iets voor hun eigen soort", () => {
    const begrippen = parseArtefact({ soort: "begrippen", ref: { werkgebied_id: "w", run_id: "r" } });
    expect(annotatieDoelVan(begrippen)).toBeUndefined();
    expect(werkgebiedArtefactVan(parseArtefact({ soort: "annotatie", ref: { bron_iri: IRI } }))).toBeUndefined();
  });

  it("de titel is het label als de ref er geen draagt", () => {
    expect(annotatieDoelVan({ soort: "annotatie", ref: { bron_iri: IRI }, titel: "Lid 1" })?.label).toBe("Lid 1");
  });
});

it("afleidingsregels zijn gereserveerd en nog niet te openen", () => {
  expect(isTeOpenen({ soort: "regels", ref: {}, titel: "" })).toBe(false);
  expect(isTeOpenen({ soort: "begrippen", ref: { werkgebied_id: "w", run_id: "r" }, titel: "" })).toBe(true);
});

describe("een artefact dat naar één begrip wijst (F3d; F4 als begrippen met begrip_id)", () => {
  const ruw = { soort: "begrip", titel: "Termijn",
    ref: { werkgebied_id: "w", begrip_id: "b1", kaart_run_id: "k", actie: "voorbeelden" } };

  it("is geldig zonder run_id, maar niet zonder werkgebied of begrip", () => {
    const a = parseArtefact(ruw)!;
    expect(a.soort).toBe("begrip");
    expect(parseArtefact({ soort: "begrip", ref: { begrip_id: "b1" } })).toBeUndefined();
    expect(parseArtefact({ soort: "begrip", ref: { werkgebied_id: "w" } })).toBeUndefined();
    expect(parseArtefact({ soort: "bronnen", ref: { werkgebied_id: "w", begrip_id: "b1" } })).toBeUndefined();
  });

  it("een bewaard bericht van vóór F3d (begrippen met begrip_id) wordt een begrip", () => {
    const a = parseArtefact({ ...ruw, soort: "begrippen" })!;
    expect(a.soort).toBe("begrip");
    expect(werkgebiedArtefactVan(a)?.begrip_id).toBe("b1");
  });

  it("opent als één begrip, met een eigen label en sleutel", () => {
    const a = parseArtefact(ruw)!;
    const w = werkgebiedArtefactVan(a)!;
    expect(w).toEqual({ soort: "begrip", werkgebied_id: "w", run_id: "", begrip_id: "b1", titel: "Termijn" });
    expect(artefactLabel(a)).toBe("Begrip");
    expect(werkgebiedLabel(w)).toBe("Begrip");
    const voorstellen = werkgebiedArtefactVan(parseArtefact({ soort: "begrippen", ref: { werkgebied_id: "w", run_id: "r" } }))!;
    expect(werkgebiedLabel(voorstellen)).toBe("Begripsvoorstellen");
    expect(artefactSleutel(w)).not.toBe(artefactSleutel(voorstellen));
  });
});

describe("een artefact dat naar één deelvraag wijst (F3d)", () => {
  it("vraagt werkgebied en deelvraag, en opent in het werkgebiedpaneel", () => {
    const a = parseArtefact({ soort: "deelvraag", ref: { werkgebied_id: "w", deelvraag_id: "d1" }, titel: "Wie betaalt?" })!;
    expect(artefactLabel(a)).toBe("Deelvraag");
    const w = werkgebiedArtefactVan(a)!;
    expect(w).toEqual({ soort: "deelvraag", werkgebied_id: "w", run_id: "", deelvraag_id: "d1", titel: "Wie betaalt?" });
    expect(artefactSleutel(w)).not.toBe(artefactSleutel({ ...w, deelvraag_id: "d2" }));
    expect(parseArtefact({ soort: "deelvraag", ref: { werkgebied_id: "w" } })).toBeUndefined();
  });
});

describe("het werkgebied als artefact (activiteit 1)", () => {
  it("wijst alleen het werkgebied aan en opent in het werkgebiedpaneel", () => {
    const a = parseArtefact({ soort: "werkgebied", ref: { werkgebied_id: "wg1" }, titel: "Box 3" });
    expect(a?.soort).toBe("werkgebied");
    expect(werkgebiedArtefactVan(a)).toEqual({ soort: "werkgebied", werkgebied_id: "wg1", run_id: "", titel: "Box 3" });
    expect(artefactLabel(a!)).toBe("Werkgebied");
    expect(isTeOpenen(a!)).toBe(true);
    expect(parseArtefact({ soort: "werkgebied", ref: {} })).toBeUndefined();
  });
});
