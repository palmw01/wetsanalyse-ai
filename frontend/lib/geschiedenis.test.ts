import { describe, expect, it } from "vitest";
import { itemsUitGesprek } from "./geschiedenis";
import type { Bericht } from "./types";

const ART = "urn:bwb:BWBR0004770:artikel:9";
const leeg = { tekst: "", denk: "", bronnen: [], annotatie_slug: "", annotatie_titel: "", run_id: "" };
const b = (extra: Partial<Bericht>): Bericht => ({ rol: "assistant", ...leeg, ...extra });
const teller = () => { let n = 0; return () => `id${++n}`; };

describe("itemsUitGesprek", () => {
  it("een gewone vraag en antwoord, met de uitkomst en het oordeel op het bericht", () => {
    const { items } = itemsUitGesprek([
      b({ rol: "user", tekst: "Wat is een belastingschuldige?" }),
      b({ tekst: "Een antwoord.", run_id: "r1", uitkomst: { status: "mislukt", melding: "Mis." },
        grounding: { niveau: "onbepaald", grounded: false, cited: 0, unsupported: [] } }),
    ], teller());
    expect(items.map((x) => x.type)).toEqual(["user", "antwoord"]);
    const ant = items[1];
    expect(ant.type === "antwoord" && ant.uitkomst).toEqual({ status: "mislukt", melding: "Mis." });
    expect(ant.type === "antwoord" && ant.grounding?.niveau).toBe("onbepaald");
  });

  it("de berichten van één reeks worden één blok, en het run-id van de reeks telt mee", () => {
    const reeks = (index: number): Bericht => b({
      run_id: `run-1.${index + 1}`, reeks: { run_id: "run-1", index, totaal: 3, ouder: "Artikel 9" },
      annotatie_doel: { bron_iri: `${ART}:lid:${index + 1}`, label: `Lid ${index + 1}` },
    });
    const { items, runIds } = itemsUitGesprek([b({ rol: "user", tekst: "annoteer" }), reeks(0), reeks(1), reeks(2)], teller());
    expect(items.map((x) => x.type)).toEqual(["user", "reeks"]);
    expect(runIds).toContain("run-1");
    expect(runIds).toContain("run-1.2");
  });

  it("een bronselectie mét kaartje blijft een antwoord, zonder kaartje is het een artefact", () => {
    const artefact = { soort: "bronselectie" as const, ref: { werkgebied_id: "wg1" }, titel: "" };
    const met = itemsUitGesprek([b({ artefact, vraagkaart: { stap: "bepalingen" } })], teller()).items;
    const zonder = itemsUitGesprek([b({ artefact })], teller()).items;
    expect(met[0].type).toBe("antwoord");
    expect(zonder[0].type).toBe("artefact");
  });

  it("een annotatie met bronnode wordt een annotatie-item; een slug zonder bronnode een tombstone", () => {
    const { items, verwijderdeSlugs } = itemsUitGesprek([
      b({ annotatie_doel: { bron_iri: ART, label: "Artikel 9" }, tekst: " Samenvatting. " }),
      b({ annotatie_slug: "oude-slug", annotatie_titel: "Oud" }),
    ], teller());
    expect(items.map((x) => x.type)).toEqual(["annotatie", "annotatie"]);
    const eerste = items[0];
    expect(eerste.type === "annotatie" && [eerste.slug, eerste.tekst]).toEqual([ART, "Samenvatting."]);
    const tweede = items[1];
    expect(tweede.type === "annotatie" && [tweede.slug, tweede.titel]).toEqual(["oude-slug", "Oud"]);
    expect(verwijderdeSlugs).toEqual(["oude-slug"]);
  });

  it("een user-bericht houdt zijn antwoord op een kaartje en zijn keuze bij een voorstel", () => {
    const { items } = itemsUitGesprek([
      b({ rol: "user", tekst: "Annuleren", bevestiging_antwoord: { keuze: "geannuleerd" } }),
    ], teller());
    expect(items[0].type === "user" && items[0].bevestigingKeuze).toBe("geannuleerd");
  });

  it("elk item krijgt een eigen id uit de meegegeven bron", () => {
    const { items } = itemsUitGesprek([b({ rol: "user", tekst: "a" }), b({ tekst: "b" })], teller());
    expect(items.map((x) => x.id)).toEqual(["id1", "id2"]);
  });
});
