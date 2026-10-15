import { describe, expect, it } from "vitest";

import { annotatieDoelVan, artefactVanBericht, werkgebiedArtefactVan, isTeOpenen, parseArtefact } from "./artefact";

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
