import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { NodeElement, NodeWeergave } from "./annotatieNode";
import { vraagSuggesties } from "./annotatie";
import {
  ACTIES, MODULES, actieVerzoek, chipTekst, onderwerpUitUrl, overVan, suggestiesVan, verzoekVan, vraagUrl,
  type Onderwerp,
} from "./vraagLex";

const element = {
  id: "e1", eigenaar_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1", klasse: "Rechtsfeit", tekst: "de aanslag",
  alternatieven: [{ klasse: "Rechtsobject" }],
} as unknown as NodeElement;
const view = {
  snapshot_id: "snap-1", doel: { bwb_id: "BWBR0004770", artikel: "9", lid: "1", label: "Artikel 9, lid 1" },
  segmenten: [{ tekst: "1. De aanslag" }, { tekst: "a. binnen een maand" }],
} as unknown as NodeWeergave;
const markering: Onderwerp = { soort: "markering", element, view };
const deelvraag: Onderwerp = { soort: "deelvraag", werkgebied_id: "wg1", id: "dv1", label: "Wanneer is een aanslag invorderbaar?" };
const werkgebied: Onderwerp = { soort: "werkgebied", werkgebied_id: "wg1", id: "", label: "Invordering" };

describe("de markering blijft de adviesvraag", () => {
  it("het verzoek is byte-gelijk aan wat de werkplek stuurde vóór F3b", () => {
    // Letterlijk de constructie die in `WerkplekClient.verstuur` stond.
    const nodeContext = { element, view };
    const oud = { modus: "advies" as const, context: {
      bron_iri: nodeContext.element.eigenaar_iri, snapshot_id: nodeContext.view.snapshot_id,
      bwbId: nodeContext.view.doel.bwb_id, artikel: nodeContext.view.doel.artikel, lid: nodeContext.view.doel.lid,
      element_id: nodeContext.element.id, klasse: nodeContext.element.klasse, fragment: nodeContext.element.tekst,
      corpus: nodeContext.view.segmenten.map((s) => s.tekst).join("\n\n"),
    } };
    expect(JSON.stringify(verzoekVan(markering))).toBe(JSON.stringify(oud));
  });

  it("chip, suggesties en het bewaarde onderwerp zoals voorheen", () => {
    expect(chipTekst(markering)).toBe("de aanslag");
    expect(suggestiesVan(markering).map((s) => s.tekst)).toEqual(vraagSuggesties(element));
    expect(suggestiesVan(markering).every((s) => !s.actie)).toBe(true);
    expect(overVan(markering)).toBe("Artikel 9, lid 1: de aanslag");
  });
});

describe("een object stuurt alleen soort en id's", () => {
  it("deelvraag, bron, kandidaat en begrip", () => {
    expect(verzoekVan(deelvraag)).toEqual({
      onderwerp: { soort: "deelvraag", werkgebied_id: "wg1", id: "dv1", label: "Wanneer is een aanslag invorderbaar?" },
    });
    expect(chipTekst(deelvraag)).toBe("Wanneer is een aanslag invorderbaar?");
    expect(overVan(deelvraag)).toBe("deelvraag Wanneer is een aanslag invorderbaar?");
    for (const soort of ["bron", "kandidaat", "begrip"] as const) {
      expect(verzoekVan({ soort, werkgebied_id: "wg1", id: "x1", label: "" })).toEqual({
        onderwerp: { soort, werkgebied_id: "wg1", id: "x1" },
      });
    }
  });

  it("het werkgebied zonder id, met de handelingen als suggestie met een actie", () => {
    expect(verzoekVan(werkgebied)).toEqual({ onderwerp: { soort: "werkgebied", werkgebied_id: "wg1", label: "Invordering" } });
    const s = suggestiesVan(werkgebied);
    expect(s.map((x) => x.actie)).toEqual(["bronnen_zoeken", "begrippen_voorstellen", "begrippen_meedenken", "werkgebied_annoteren"]);
    expect(actieVerzoek(werkgebied as Extract<Onderwerp, { soort: "werkgebied" }>, "bronnen_zoeken")).toEqual({
      actie: "bronnen_zoeken", onderwerp: { soort: "werkgebied", werkgebied_id: "wg1", label: "Invordering" },
    });
  });

  it("elke soort heeft een module", () => {
    expect(Object.keys(MODULES).sort()).toEqual(["begrip", "bron", "deelvraag", "kandidaat", "markering", "werkgebied"]);
  });
});

describe("contract met graph-qa", () => {
  const models = readFileSync(resolve(__dirname, "../../tools/graph-qa/agent/models.py"), "utf8");

  it("de acties zijn die van ACTIE_TAAK", () => {
    const begin = models.indexOf("ACTIE_TAAK: dict[str, tuple[str, str]] = {");
    expect(begin).toBeGreaterThan(-1);
    const blok = models.slice(begin, models.indexOf("\n}", begin));
    const sleutels = [...blok.matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => m[1]);
    expect(sleutels.sort()).toEqual([...ACTIES].sort());
  });

  it("de soorten zijn die van Onderwerp, zonder markering", () => {
    const regel = models.split("\n").find((r) => r.includes("soort: Literal[") && r.includes("deelvraag")) ?? "";
    const soorten = [...regel.matchAll(/"([a-z]+)"/g)].map((m) => m[1]);
    expect(soorten.sort()).toEqual(Object.keys(MODULES).filter((s) => s !== "markering").sort());
  });
});

describe("buiten de werkplek", () => {
  it("de url draagt het onderwerp, en terug", () => {
    const url = vraagUrl(deelvraag as Extract<Onderwerp, { soort: "deelvraag" }>);
    expect(url).toBe("/workbench?werkgebied=wg1&vraag=deelvraag%3Adv1&vraag_label=Wanneer+is+een+aanslag+invorderbaar%3F");
    expect(onderwerpUitUrl(new URL(url, "http://x").searchParams)).toEqual(deelvraag);
    const wg = vraagUrl(werkgebied as Extract<Onderwerp, { soort: "werkgebied" }>);
    expect(onderwerpUitUrl(new URL(wg, "http://x").searchParams)).toEqual(werkgebied);
  });

  it("een onbekende soort, een markering of een vreemd id is geen onderwerp", () => {
    const q = (s: string) => onderwerpUitUrl(new URLSearchParams(s));
    expect(q("werkgebied=wg1")).toBeNull();
    expect(q("werkgebied=wg1&vraag=markering:e1")).toBeNull();
    expect(q("werkgebied=wg1&vraag=begrip:../x")).toBeNull();
    expect(q("vraag=begrip:b1")).toBeNull();
  });
});
