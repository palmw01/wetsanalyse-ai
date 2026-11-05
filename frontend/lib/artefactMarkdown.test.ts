import { describe, expect, it } from "vitest";

import { annotatieAlsMarkdown, begripAlsMarkdown, bestandsnaam, bronselectieAlsMarkdown, dossierAlsMarkdown, voorstellenAlsMarkdown } from "./artefactMarkdown";
import { parseBronselectie } from "./bronselectie";
import type { AnnotatieDocument, Begrip, Werkgebied } from "./types";

const WG = {
  id: "wg1", naam: "Rekeningafspraken", status: "in_voorbereiding", peildatum: "2026-11-04", revisie: 3,
  analysevraag: "Wanneer betaalt de Belastingdienst uit?", afbakening: "", aanleiding: "", context: "",
  doel: "", praktijkvoorbeeld: "", gebeurtenis: "uitbetaling",
  regelingen: [{ bwb_id: "BWBR0004770", label: "Invorderingswet 1990" }], bronnen: [],
  deelvragen: [{ id: "d1", vraag: "Op welke rekening?", status: "actief" }, { id: "d2", vraag: "Weg", status: "afgewezen" }],
} as unknown as Werkgebied;

describe("artefacten als Markdown", () => {
  it("het dossier: velden met inhoud, het zoekbereik en de actieve deelvragen met stand – geen tabellen", () => {
    const md = dossierAlsMarkdown(WG, parseBronselectie({ werkgebied_id: "wg1", naam: "R", deelvragen: [{ id: "d1", status: "in_behandeling" }] }));
    expect(md).toContain("# Rekeningafspraken");
    expect(md).toContain("**Analysevraag**\n\nWanneer betaalt de Belastingdienst uit?");
    expect(md).toContain("**Gebeurtenis**\n\nuitbetaling");
    expect(md).toContain("- Invorderingswet 1990");
    expect(md).toContain("1. Op welke rekening? (in behandeling)");
    expect(md).not.toContain("Weg");
    expect(md).not.toContain("**Context**");
    expect(md).not.toMatch(/\|/);
  });

  it("de bronselectie: per deelvraag bronnen per rol en de voorstellen met hun zoekvraag", () => {
    const o = parseBronselectie({ werkgebied_id: "wg1", naam: "R", modus: "deelvragen", deelvragen: [{
      id: "d1", nr: 1, vraag: "Op welke rekening?", status: "in_behandeling",
      bronnen: [{ selectie_id: "s1", bron_iri: "urn:x:9", label: "Artikel 9", rol: "analyseren" }],
      kandidaten: [{ id: "K1", bron_iri: "urn:x:10", label: "Artikel 10", rol: "kern", stand: "voorgesteld",
        bewijs_soorten: ["genoemd"], bewijs: [{ methode: "grondslag", detail: { zoekvraag: "a" } }] }] }] })!;
    const md = bronselectieAlsMarkdown(o);
    expect(md).toContain("## Deelvraag 1");
    expect(md).toContain("**Analyseren**\n\n- Artikel 9");
    expect(md).toContain("- Artikel 10 (zoekvraag a · bestaansrecht, zelf genoemd)");
  });

  it("een begrip en een annotatie", () => {
    const b = { inhoud: { naam: "rekening", alternatieve_termen: ["bankrekening"], definitie: "Een rekening bij een bank.",
      definitie_herkomst: "letterlijk", uitleg: "", context: "", voorbeelden: [{ tekst: "IBAN op naam", oordeel: "wel" }] } } as unknown as Begrip;
    const md = begripAlsMarkdown(b);
    expect(md).toContain("# rekening\n\nOok: bankrekening");
    expect(md).toContain("**Definitie**\n\nEen rekening bij een bank.");
    expect(md).toMatch(/- IBAN op naam \(.+\)/);
    const doc = { elementen: [
      { id: "1", klasse: "rechtssubject", tekst: "de ontvanger", lid: "1", toelichting: "", lifecycle: "human_approved" },
      { id: "2", klasse: "rechtssubject", tekst: "weg", lid: "", toelichting: "", lifecycle: "rejected" },
    ] } as unknown as AnnotatieDocument;
    const a = annotatieAlsMarkdown(doc, "Artikel 9 – Iw 1990");
    expect(a).toContain("- “de ontvanger” (lid 1) – akkoord");
    expect(a).not.toContain("weg");
  });

  it("een bestandsnaam uit de titel", () => {
    expect(bestandsnaam("Artikel 9 – Invorderingswet 1990")).toBe("artikel-9-invorderingswet-1990.md");
    expect(bestandsnaam("Ö")).toBe("o.md");
    expect(bestandsnaam("")).toBe("artefact.md");
  });
});

describe("voorstellenAlsMarkdown", () => {
  it("noemt de termen van de oude versie, met hun stand", () => {
    expect(voorstellenAlsMarkdown("Invordering", [{ naam: "termijn", passages: 2, open: [{}] }, { naam: "aanslag", passages: 1, open: [] }]))
      .toBe("# Invordering\n\n- termijn (2 passages, te beoordelen)\n- aanslag (1 passage, beoordeeld)\n");
    expect(voorstellenAlsMarkdown("Leeg", [])).toContain("Geen voorstellen.");
  });
});
