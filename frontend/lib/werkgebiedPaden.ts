// De werkgebiedpagina als project (spoor G2): vier tabs als echte paden, de detailpagina's eronder, en
// de artefactkaarten. Zuiver, zodat vitest het zonder DOM toetst; de componenten lezen alleen.

import type { BegripSamenvatting, BronKandidaat, Werkgebied } from "./types";

/** Dezelfde tonen als `StatusLabel` (`components/ui/Lijst`); `lib/` importeert geen componenten. */
type StatusToon = "groen" | "geel" | "neutraal";

export const PROJECT_TABS = [
  { key: "overzicht", label: "Overzicht" },
  { key: "gesprekken", label: "Gesprekken" },
  { key: "bronnen", label: "Bronnen" },
  { key: "artefacten", label: "Artefacten" },
] as const;
export type ProjectTab = (typeof PROJECT_TABS)[number]["key"];

/** De artefacten van een werkgebied: bestaande zelfstandige objecten, als projectproduct getoond (besluit
 *  26 okt 2026, geen eigen tabel). *Specificaties* (afleidingsregels) blijft gereserveerd. */
export const ARTEFACT_SOORTEN = ["dossier", "bronselectie", "annotaties", "begrippen"] as const;
export type ArtefactSoort = (typeof ARTEFACT_SOORTEN)[number];
export const ARTEFACT_LABEL: Record<ArtefactSoort, string> = {
  dossier: "Dossier", bronselectie: "Bronselectie", annotaties: "Annotaties", begrippen: "Begrippen",
};

export function isArtefactSoort(s: string | undefined): s is ArtefactSoort {
  return ARTEFACT_SOORTEN.some((a) => a === s);
}

const basis = (id: string) => `/werkgebieden/${encodeURIComponent(id)}`;

export function projectPad(id: string, tab: ProjectTab = "overzicht"): string {
  return tab === "overzicht" ? basis(id) : `${basis(id)}/${tab}`;
}

export function historiePad(id: string): string {
  return `${basis(id)}/historie`;
}

export function voorstellenPad(id: string): string {
  return `${basis(id)}/bronnen/voorstellen`;
}

export function deelvraagPad(id: string, deelvraagId: string): string {
  return `${basis(id)}/deelvragen/${encodeURIComponent(deelvraagId)}`;
}

/** Het artefact Begrippen draagt zijn eigen stand in de URL: het gekozen begrip, of het als kaart openstaat,
 *  en de deelweergave *Samenhang*. */
export function artefactPad(id: string, soort: ArtefactSoort,
  extra: { begrip?: string; weergave?: "lezen" | "kaart"; deel?: "lijst" | "samenhang" } = {}): string {
  const qs = new URLSearchParams();
  if (soort === "begrippen") {
    if (extra.deel === "samenhang") qs.set("deel", "samenhang");
    else if (extra.begrip) {
      qs.set("begrip", extra.begrip);
      if (extra.weergave === "kaart") qs.set("weergave", "kaart");
    }
  }
  // Spoor L: de bronselectie per deelvraag woont op de tab Bronnen; het artefact is daar één plek mee.
  if (soort === "bronselectie") return `${basis(id)}/bronnen`;
  const pad = `${basis(id)}/artefacten/${soort}`;
  return qs.size ? `${pad}?${qs}` : pad;
}

/** De eigen pagina's van de juridische objecten (spoor G3): één bepaling uit de graaf, één JAS-element en
 *  één begrip. Elk is direct te openen en te delen; het werkgebied gaat mee als context, niet als eigenaar. */
/** De voorstellen van Lex voor één term in het begrippenkader (spoor H4); de term genormaliseerd. */
export function termPad(id: string, sleutel: string): string {
  return `${artefactPad(id, "begrippen")}/term/${encodeURIComponent(sleutel)}`;
}

export function bronPad(bronIri: string, werkgebiedId?: string): string {
  const qs = new URLSearchParams({ bron_iri: bronIri });
  if (werkgebiedId) qs.set("werkgebied", werkgebiedId);
  return `/bronnen?${qs}`;
}

export function elementPad(elementId: string): string {
  return `/annotaties/element/${encodeURIComponent(elementId)}`;
}

export function begripPad(werkgebiedId: string, begripId: string): string {
  return `/begrippen/${encodeURIComponent(werkgebiedId)}/${encodeURIComponent(begripId)}`;
}

/** Waar een oude link met `?tab=` heen gaat: bladwijzers en berichten van vóór G2 blijven werken. */
export function oudeTabNaar(id: string, p: { tab?: string; begrip?: string; weergave?: string }): string | null {
  const weergave = p.weergave === "kaart" ? "kaart" : "lezen";
  switch (p.tab) {
    case "bronnen": return projectPad(id, "bronnen");
    case "elementen": return artefactPad(id, "annotaties");
    // Een begrip als kaart heeft nu een eigen pagina; lezen blijft in het begrippenkader.
    case "begrippen": return p.begrip && weergave === "kaart" ? begripPad(id, p.begrip)
      : artefactPad(id, "begrippen", { begrip: p.begrip });
    case "samenhang": return artefactPad(id, "begrippen", { deel: "samenhang" });
    case "historie": return historiePad(id);
    default: return null;
  }
}

/** Wat de annotatie-werkvoorraad per selectie en per eenheid meldt (`GET …/annotatie-werkvoorraad`). */
export type EenheidStatus = "afgerond" | "te_beoordelen" | "beoordeeld" | "zonder_markeringen" | "nieuw";
export interface Werkvoorraad {
  selecties: { id: string; bron_iri: string; label: string; eenheden: number;
    per_stand: Partial<Record<EenheidStatus, number>>; onbereikbaar: string | null }[];
  eenheden: { bron_iri: string; label: string; stand: { status: EenheidStatus } }[];
  te_annoteren: string[];
  volledig: boolean;
}

export function isWerkvoorraad(x: unknown): x is Werkvoorraad {
  const w = x as Werkvoorraad;
  return !!w && Array.isArray(w.selecties) && Array.isArray(w.eenheden) && Array.isArray(w.te_annoteren);
}

/** De stand van één bronselectie in gewone woorden, uit de werkvoorraad. Een contextbron telt niet mee
 *  (geen werkvoorraad); een onbekende stand is geen nul. */
export function selectieStand(sel: Werkvoorraad["selecties"][number] | undefined):
  { tekst: string; toon: StatusToon } | null {
  if (!sel) return null;
  if (sel.onbereikbaar) return { tekst: "Niet te lezen", toon: "geel" };
  const n = sel.eenheden;
  if (!n) return null;
  const klaar = (sel.per_stand.afgerond ?? 0) + (sel.per_stand.beoordeeld ?? 0) + (sel.per_stand.zonder_markeringen ?? 0);
  const nieuw = sel.per_stand.nieuw ?? 0;
  if (klaar === n) return { tekst: "Beoordeeld", toon: "groen" };
  if (nieuw === n) return { tekst: "Nog niet geannoteerd", toon: "neutraal" };
  return { tekst: `${klaar} van ${n} beoordeeld`, toon: "geel" };
}

export interface ArtefactKaart {
  soort: ArtefactSoort;
  titel: string;
  omschrijving: string;
  /** Hoe ver het product is, in één regel ("r12", "8 begrippen"). */
  versie: string;
  status: { tekst: string; toon: StatusToon } | null;
}

/** De vier kaarten van de tab Artefacten, uit wat er al ligt. Een bron die (nog) niet geladen is, geeft
 *  een kaart zonder status in plaats van een verzonnen getal. */
export function artefactKaarten(wg: Werkgebied, extra: {
  begrippen?: BegripSamenvatting[] | null;
  werkvoorraad?: Werkvoorraad | null;
  kandidaten?: BronKandidaat[] | null;
} = {}): ArtefactKaart[] {
  const velden = ["aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "afbakening"] as const;
  const gevuld = velden.filter((v) => (wg[v] ?? "").trim()).length;
  const deelvragen = (wg.deelvragen ?? []).filter((d) => d.status === "actief").length;
  const analyse = wg.bronnen.filter((b) => b.rol === "analyseren").length;
  const open = extra.kandidaten?.filter((k) => k.status === "voorgesteld").length;

  const wv = extra.werkvoorraad;
  const eenheden = wv?.eenheden.length ?? 0;
  const klaar = wv?.eenheden.filter((e) => ["afgerond", "beoordeeld", "zonder_markeringen"].includes(e.stand.status)).length ?? 0;

  const b = extra.begrippen;
  const geaccordeerd = b?.filter((x) => x.status === "geaccordeerd").length ?? 0;
  const actief = b?.filter((x) => x.status !== "vervangen").length ?? 0;

  return [
    {
      soort: "dossier", titel: `Analysedossier ${wg.naam}`,
      omschrijving: "Aanleiding, context, doel, analysevraag, praktijkvoorbeeld, afbakening en deelvragen.",
      versie: `revisie ${wg.revisie}`,
      status: gevuld === velden.length
        ? { tekst: "Volledig", toon: "groen" }
        : { tekst: `${gevuld} van ${velden.length} velden · ${deelvragen} deelvragen`, toon: "neutraal" },
    },
    {
      soort: "bronselectie", titel: "Bronselectie en afbakening",
      omschrijving: "De bepalingen van dit werkgebied, met hun rol en reden.",
      versie: `${wg.bronnen.length} bepalingen · ${analyse} om te analyseren`,
      status: open ? { tekst: `${open} ${open === 1 ? "voorstel" : "voorstellen"} van Lex`, toon: "geel" } : null,
    },
    {
      soort: "annotaties", titel: "JAS-annotaties",
      omschrijving: "De geannoteerde elementen van de bepalingen om te analyseren, met hun beoordeling.",
      versie: wv ? `${eenheden} bepalingen` : "",
      status: !wv || !eenheden ? null
        : klaar === eenheden ? { tekst: "Beoordeeld", toon: "groen" }
        : { tekst: `${klaar} van ${eenheden} beoordeeld`, toon: klaar ? "geel" : "neutraal" },
    },
    {
      soort: "begrippen", titel: `Begrippenkader ${wg.naam}`,
      omschrijving: "De begrippen van dit werkgebied: betekenis, passages, relaties en beoordeling.",
      versie: b ? `${actief} begrippen` : "",
      status: !b || !actief ? null
        : geaccordeerd === actief ? { tekst: "Geaccordeerd", toon: "groen" }
        : { tekst: `${geaccordeerd} van ${actief} geaccordeerd`, toon: geaccordeerd ? "geel" : "neutraal" },
    },
  ];
}
