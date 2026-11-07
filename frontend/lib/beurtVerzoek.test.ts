import { describe, expect, it } from "vitest";

import type { NodeElement, NodeWeergave } from "./annotatieNode";
import { bevestigt, startOpties, userVelden, type BeurtVerzoek, type WerkgebiedAnnoteren } from "./beurtVerzoek";
import type { AgentDoelInvoer } from "./types";
import { antwoordOp, type IntakeActie } from "./vraagkaart";
import { actieVerzoek, verzoekVan, type Onderwerp, type VraagLexActie } from "./vraagLex";

// Letterlijk de constructie die in `WerkplekClient.verstuur` stond (vóór E4 PR 3), als orakel.
function oud(vraagOver: Onderwerp | undefined, werkgebiedId: string | null, doel?: AgentDoelInvoer, hergebruik?: "opnieuw",
  doelen?: AgentDoelInvoer[], annoteren?: WerkgebiedAnnoteren, intake?: IntakeActie, actie?: VraagLexActie) {
  const basis = vraagOver ? verzoekVan(vraagOver) : undefined;
  const extra = doelen?.length && !vraagOver
    ? { ...basis, doelen }
    : doel && !vraagOver ? { ...basis, doel, ...(hergebruik ? { hergebruik } : {}) } : basis;
  return annoteren
    ? { modus: annoteren.modus ?? "werkgebied_annoteren", werkgebied_id: annoteren.werkgebiedId,
        ...(annoteren.bevestigd !== undefined ? { bevestigd: annoteren.bevestigd } : {}),
        ...(annoteren.bereik ? { bereik: annoteren.bereik } : {}),
        ...(annoteren.deelvraagId ? { deelvraag_id: annoteren.deelvraagId } : {}),
        ...(annoteren.werkvoorraadId ? { werkvoorraad_id: annoteren.werkvoorraadId } : {}) }
    : intake ? { intake_actie: intake, ...(werkgebiedId ? { werkgebied_id: werkgebiedId } : {}) }
    : actie && vraagOver && vraagOver.soort !== "markering"
      ? { ...actieVerzoek(vraagOver, actie), werkgebied_id: vraagOver.werkgebied_id }
    : actie && werkgebiedId ? { actie, werkgebied_id: werkgebiedId }
    : werkgebiedId ? { ...extra, werkgebied_id: werkgebiedId } : extra;
}

const element = {
  id: "e1", eigenaar_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1", klasse: "Rechtsfeit", tekst: "de aanslag",
} as unknown as NodeElement;
const view = {
  snapshot_id: "snap-1", doel: { bwb_id: "BWBR0004770", artikel: "9", lid: "1", label: "Artikel 9, lid 1" },
  segmenten: [{ tekst: "1. De aanslag" }],
} as unknown as NodeWeergave;
const markering: Onderwerp = { soort: "markering", element, view };
const deelvraag: Onderwerp = { soort: "deelvraag", werkgebied_id: "wg2", id: "dv1", label: "Wanneer?" };
const doel: AgentDoelInvoer = { bwbId: "BWBR0004770", artikel: "9", lid: "1", bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1" } as AgentDoelInvoer;
const intake = { intake_id: "wg-1", stap: "naam", actie: "antwoord", tekst: "Invordering" } as IntakeActie;
const actie = "bronselectie" as VraagLexActie;

describe("startOpties is gelijk aan de oude constructie", () => {
  const gevallen: [string, BeurtVerzoek, Onderwerp | undefined, string | null][] = [
    ["kale vraag", {}, undefined, null],
    ["kale vraag in een werkgebied", {}, undefined, "wg1"],
    ["doel", { doel }, undefined, null],
    ["doel opnieuw", { doel, hergebruik: "opnieuw" }, undefined, "wg1"],
    ["hergebruik zonder doel betekent niets", { hergebruik: "opnieuw" }, undefined, null],
    ["doelen", { doelen: [doel, doel] }, undefined, "wg1"],
    ["lege doelen", { doelen: [] }, undefined, null],
    ["doel bij een markering valt weg", { doel }, markering, null],
    ["advies bij een markering", {}, markering, "wg1"],
    ["onderwerp deelvraag", {}, deelvraag, "wg1"],
    ["doelen bij een onderwerp vallen weg", { doelen: [doel] }, deelvraag, null],
    ["annoteren", { annoteren: { werkgebiedId: "wg3" } }, undefined, "wg1"],
    ["annoteren bevestigd met bereik", { annoteren: { werkgebiedId: "wg3", bevestigd: 4, bereik: "deelvragen", deelvraagId: "dv1" } }, deelvraag, null],
    ["meedenken", { annoteren: { werkgebiedId: "wg3", bevestigd: 0, modus: "begrippen_verdiepen", werkvoorraadId: "wv1" } }, undefined, null],
    ["annoteren wint van intake en actie", { annoteren: { werkgebiedId: "wg3" }, intake, actie }, deelvraag, "wg1"],
    ["intake", { intake }, undefined, null],
    ["intake in een werkgebied", { intake, actie }, deelvraag, "wg1"],
    ["actie op een onderwerp", { actie }, deelvraag, "wg1"],
    ["actie bij een markering valt naar het werkgebied", { actie }, markering, "wg1"],
    ["actie bij een markering zonder werkgebied is advies", { actie }, markering, null],
    ["actie in een werkgebied", { actie }, undefined, "wg1"],
    ["actie zonder werkgebied", { actie, doel }, undefined, null],
  ];
  for (const [naam, v, over, wg] of gevallen) {
    it(naam, () => {
      expect(startOpties(v, { werkgebiedId: wg, onderwerp: over }))
        .toEqual(oud(over, wg, v.doel, v.hergebruik, v.doelen, v.annoteren, v.intake, v.actie));
    });
  }
});

describe("userVelden", () => {
  it("zet de contextregel in de tekst", () => {
    expect(userVelden({}, "Waarom?", "Artikel 9: de aanslag")).toEqual({ tekst: "Bij Artikel 9: de aanslag: Waarom?" });
    expect(userVelden({}, "Waarom?", "")).toEqual({ tekst: "Waarom?" });
  });

  it("een klik op een kaartje draagt zijn antwoord, een bevestigde knop zijn keuze", () => {
    expect(userVelden({ intake }, "Invordering", "")).toEqual({ tekst: "Invordering", intake_antwoord: antwoordOp(intake) });
    expect(userVelden({ annoteren: { werkgebiedId: "wg", bevestigd: 3 } }, "Annoteer", ""))
      .toEqual({ tekst: "Annoteer", bevestiging_antwoord: { keuze: "gestart" } });
    // Zonder `bevestigd` beantwoordt het geen voorstel: graph-qa vraagt dan eerst.
    expect(bevestigt({ annoteren: { werkgebiedId: "wg" } })).toBe(false);
    expect(bevestigt({ annoteren: { werkgebiedId: "wg", bevestigd: 0 } })).toBe(true);
  });
});
