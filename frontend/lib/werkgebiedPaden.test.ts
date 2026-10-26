import { describe, expect, it } from "vitest";

import type { Werkgebied } from "./types";
import { artefactKaarten, artefactPad, deelvraagPad, oudeTabNaar, projectPad, selectieStand, type Werkvoorraad } from "./werkgebiedPaden";

const wg = (extra: Partial<Werkgebied> = {}): Werkgebied => ({
  id: "wg1", naam: "Invorderingsrente", status: "in_voorbereiding", revisie: 4, peildatum: null, aangemaakt_door: "t",
  aangemaakt: "", gewijzigd: "", analysevraag: "Hoe?", afbakening: "", aanleiding: "", context: "", doel: "",
  praktijkvoorbeeld: "", bronnen: [], deelvragen: [], ...extra,
} as Werkgebied);

describe("paden", () => {
  it("de vier tabs en de detailpagina's zijn echte paden", () => {
    expect(projectPad("wg1")).toBe("/werkgebieden/wg1");
    expect(projectPad("wg1", "bronnen")).toBe("/werkgebieden/wg1/bronnen");
    expect(deelvraagPad("wg1", "d 1")).toBe("/werkgebieden/wg1/deelvragen/d%201");
    expect(artefactPad("wg1", "begrippen", { begrip: "b9", weergave: "kaart" }))
      .toBe("/werkgebieden/wg1/artefacten/begrippen?begrip=b9&weergave=kaart");
    expect(artefactPad("wg1", "begrippen", { deel: "samenhang", begrip: "b9" }))
      .toBe("/werkgebieden/wg1/artefacten/begrippen?deel=samenhang");
    expect(artefactPad("wg1", "dossier", { begrip: "b9" })).toBe("/werkgebieden/wg1/artefacten/dossier");
  });

  it("een oude ?tab= gaat naar zijn nieuwe plek", () => {
    expect(oudeTabNaar("wg1", { tab: "bronnen" })).toBe("/werkgebieden/wg1/bronnen");
    expect(oudeTabNaar("wg1", { tab: "elementen" })).toBe("/werkgebieden/wg1/artefacten/annotaties");
    expect(oudeTabNaar("wg1", { tab: "begrippen", begrip: "b9" })).toBe("/werkgebieden/wg1/artefacten/begrippen?begrip=b9");
    expect(oudeTabNaar("wg1", { tab: "samenhang" })).toBe("/werkgebieden/wg1/artefacten/begrippen?deel=samenhang");
    expect(oudeTabNaar("wg1", { tab: "historie" })).toBe("/werkgebieden/wg1/historie");
    expect(oudeTabNaar("wg1", {})).toBeNull();
    expect(oudeTabNaar("wg1", { tab: "onzin" })).toBeNull();
  });
});

describe("selectieStand", () => {
  const sel = (per_stand: Werkvoorraad["selecties"][number]["per_stand"], eenheden: number, onbereikbaar: string | null = null) =>
    ({ id: "s1", bron_iri: "x", label: "x", eenheden, per_stand, onbereikbaar });
  it("zegt hoe ver de bepaling is, zonder verzonnen getal", () => {
    expect(selectieStand(undefined)).toBeNull();
    expect(selectieStand(sel({}, 0))).toBeNull();
    expect(selectieStand(sel({ afgerond: 2, zonder_markeringen: 1 }, 3))?.tekst).toBe("Beoordeeld");
    expect(selectieStand(sel({ nieuw: 3 }, 3))?.tekst).toBe("Nog niet geannoteerd");
    expect(selectieStand(sel({ afgerond: 1, te_beoordelen: 2 }, 3))).toEqual({ tekst: "1 van 3 beoordeeld", toon: "geel" });
    expect(selectieStand(sel({}, 0, "weg"))?.tekst).toBe("Niet te lezen");
  });
});

describe("artefactKaarten", () => {
  it("vier kaarten uit wat er ligt; zonder data geen status", () => {
    const k = artefactKaarten(wg());
    expect(k.map((x) => x.soort)).toEqual(["dossier", "bronselectie", "annotaties", "begrippen"]);
    expect(k[0].status?.tekst).toBe("1 van 6 velden · 0 deelvragen");
    expect(k[2].status).toBeNull();
    expect(k[3].status).toBeNull();
  });

  it("telt begrippen zonder de vervangen, en de open voorstellen van Lex", () => {
    const k = artefactKaarten(wg(), {
      begrippen: [{ status: "geaccordeerd" }, { status: "concept" }, { status: "vervangen" }] as never,
      kandidaten: [{ status: "voorgesteld" }, { status: "uitgesloten" }] as never,
    });
    expect(k[3]).toMatchObject({ versie: "2 begrippen", status: { tekst: "1 van 2 geaccordeerd", toon: "geel" } });
    expect(k[1].status?.tekst).toBe("1 voorstel van Lex");
  });
});
