// Het artefact van een beurt: wat Lex in het gesprek oplevert om te beoordelen – een annotatie, de
// begripsvoorstellen of gevonden bepalingen van een werkgebied, het werkgebied, één deelvraag of één
// begrip, of (later) afleidingsregels. Het bericht verwijst ernaar
// (`Bericht.artefact`, api `gesprek_contracts.Artefact`); de inhoud leeft in de api.
//
// Eén vorm voor alle soorten, zodat chip, paneel en de laatste-artefactbalk niet per soort een
// eigen weg krijgen. `ref` hangt af van de soort; de api toetst dat bij het bewaren, en
// `parseArtefact` doet het nog eens voor wat er via de SSE-stroom binnenkomt.

import type { NodeDoel } from "./annotatieNode";
import type { Bericht } from "./types";

export type ArtefactSoort = "annotatie" | "begrippen" | "bronnen" | "werkgebied" | "deelvraag" | "begrip" | "regels";

export interface Artefact {
  soort: ArtefactSoort;
  ref: Record<string, unknown>;
  titel: string;
}

/** Wat een artefact van een werkgebied aanwijst: de begripsvoorstellen of de gevonden bepalingen van
 *  één run (`run_id`); het werkgebied zelf, dat Lex in het gesprek samenstelde (activiteit 1); één
 *  deelvraag (`deelvraag_id`, F3d) of één begrip (`begrip_id`, F3d). */
export interface WerkgebiedArtefact {
  soort: "begrippen" | "bronnen" | "werkgebied" | "deelvraag" | "begrip";
  werkgebied_id: string;
  run_id: string;
  begrip_id?: string;
  deelvraag_id?: string;
  titel: string;
}

/** Hoe de chip de soort noemt. */
export const ARTEFACT_SOORT_LABEL: Record<ArtefactSoort, string> = {
  annotatie: "JAS-annotatie",
  begrippen: "Begripsvoorstellen",
  bronnen: "Gevonden bepalingen",
  werkgebied: "Werkgebied",
  deelvraag: "Deelvraag",
  begrip: "Begrip",
  regels: "Afleidingsregels",
};

const VERPLICHT: Record<ArtefactSoort, string[]> = {
  annotatie: ["bron_iri"],
  begrippen: ["werkgebied_id", "run_id"],
  bronnen: ["werkgebied_id", "run_id"],
  werkgebied: ["werkgebied_id"],
  deelvraag: ["werkgebied_id", "deelvraag_id"],
  begrip: ["werkgebied_id", "begrip_id"],
  regels: [],
};

const SOORTEN = Object.keys(VERPLICHT) as ArtefactSoort[];

const tekst = (v: unknown) => (typeof v === "string" ? v : "");

/** Streng: een onbekende soort of een ref zonder de verplichte sleutels is géén artefact. Liever geen
 *  chip dan een chip die een leeg paneel opent. Een bericht van vóór F3d noemde één begrip `begrippen`
 *  met `begrip_id`; dat wordt hier `begrip`. */
export function parseArtefact(ruw: unknown): Artefact | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  if (!SOORTEN.includes(r.soort as ArtefactSoort)) return undefined;
  const ref = r.ref && typeof r.ref === "object" && !Array.isArray(r.ref) ? (r.ref as Record<string, unknown>) : undefined;
  if (!ref) return undefined;
  const soort = r.soort === "begrippen" && tekst(ref.begrip_id) ? "begrip" : (r.soort as ArtefactSoort);
  if (VERPLICHT[soort].some((k) => !tekst(ref[k]))) return undefined;
  return { soort, ref, titel: tekst(r.titel) };
}

/** Het artefact van een bewaard bericht. Berichten van vóór het artefactveld dragen alleen
 *  `annotatie_doel`; die worden een annotatie-artefact. */
export function artefactVanBericht(b: Pick<Bericht, "artefact" | "annotatie_doel" | "annotatie_titel">): Artefact | undefined {
  const a = parseArtefact(b.artefact);
  if (a) return a;
  const d = b.annotatie_doel;
  if (!d?.bron_iri) return undefined;
  return { soort: "annotatie", ref: { ...d }, titel: d.label || b.annotatie_titel || "" };
}

/** De bronnode van een annotatie-artefact. */
export function annotatieDoelVan(a: Artefact | undefined): NodeDoel | undefined {
  if (a?.soort !== "annotatie" || !tekst(a.ref.bron_iri)) return undefined;
  const r = a.ref;
  return {
    bron_iri: tekst(r.bron_iri),
    ...(tekst(r.label) || a.titel ? { label: tekst(r.label) || a.titel } : {}),
    ...(tekst(r.snapshot_id) ? { snapshot_id: tekst(r.snapshot_id) } : {}),
    ...(tekst(r.bwb_id) ? { bwb_id: tekst(r.bwb_id) } : {}),
  };
}

/** Wat het werkgebiedpaneel opent: alles behalve een annotatie en de (gereserveerde) regels. */
export function werkgebiedArtefactVan(a: Artefact | undefined): WerkgebiedArtefact | undefined {
  if (!a || a.soort === "annotatie" || a.soort === "regels") return undefined;
  const p = parseArtefact(a);
  if (!p) return undefined;
  const r = p.ref;
  return {
    soort: p.soort as WerkgebiedArtefact["soort"], werkgebied_id: tekst(r.werkgebied_id), run_id: tekst(r.run_id),
    ...(p.soort === "begrip" ? { begrip_id: tekst(r.begrip_id) } : {}),
    ...(p.soort === "deelvraag" ? { deelvraag_id: tekst(r.deelvraag_id) } : {}),
    titel: p.titel,
  };
}

/** Hoe de chip dit artefact noemt. */
export function artefactLabel(a: Artefact): string {
  return ARTEFACT_SOORT_LABEL[a.soort];
}

/** Idem voor een geopend werkgebiedartefact. */
export function werkgebiedLabel(a: WerkgebiedArtefact): string {
  return ARTEFACT_SOORT_LABEL[a.soort];
}

/** Een sleutel die per artefact verschilt (React `key`). */
export function artefactSleutel(a: WerkgebiedArtefact): string {
  return `${a.soort}:${a.werkgebied_id}:${a.run_id}:${a.begrip_id ?? ""}:${a.deelvraag_id ?? ""}`;
}

/** Kan de werkplek dit artefact openen? Afleidingsregels zijn gereserveerd, nog niet gebouwd. */
export function isTeOpenen(a: Artefact): boolean {
  return a.soort !== "regels";
}
