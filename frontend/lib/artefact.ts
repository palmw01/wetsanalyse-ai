// Het artefact van een beurt: wat Lex in het gesprek oplevert om te beoordelen – een annotatie, de
// begripsvoorstellen van een werkgebied, of (later) afleidingsregels. Het bericht verwijst ernaar
// (`Bericht.artefact`, api `gesprek_contracts.Artefact`); de inhoud leeft in de api.
//
// Eén vorm voor alle soorten, zodat chip, paneel en de laatste-artefactbalk niet per soort een
// eigen weg krijgen. `ref` hangt af van de soort; de api toetst dat bij het bewaren, en
// `parseArtefact` doet het nog eens voor wat er via de SSE-stroom binnenkomt.

import type { NodeDoel } from "./annotatieNode";
import type { Bericht } from "./types";

export type ArtefactSoort = "annotatie" | "begrippen" | "bronnen" | "werkgebied" | "regels";

export interface Artefact {
  soort: ArtefactSoort;
  ref: Record<string, unknown>;
  titel: string;
}

/** Wat een artefact van een werkgebied aanwijst: de begripsvoorstellen of de gevonden bepalingen van
 *  één run op één werkgebied – of, bij een kaartactie vanuit het gesprek (fase F4), één begrip
 *  (`begrip_id`, en dan is `run_id` leeg). Soort `werkgebied` is het werkgebied zelf, dat Lex in het
 *  gesprek samenstelde (activiteit 1): alleen `werkgebied_id`. */
export interface WerkgebiedArtefact {
  soort: "begrippen" | "bronnen" | "werkgebied";
  werkgebied_id: string;
  run_id: string;
  begrip_id?: string;
  titel: string;
}

/** Hoe de chip de soort noemt. */
export const ARTEFACT_SOORT_LABEL: Record<ArtefactSoort, string> = {
  annotatie: "JAS-annotatie",
  begrippen: "Begripsvoorstellen",
  bronnen: "Gevonden bepalingen",
  werkgebied: "Werkgebied",
  regels: "Afleidingsregels",
};

const VERPLICHT: Record<ArtefactSoort, string[]> = {
  annotatie: ["bron_iri"],
  // Of `begrip_id` in plaats van `run_id` – zie `parseArtefact`.
  begrippen: ["werkgebied_id", "run_id"],
  bronnen: ["werkgebied_id", "run_id"],
  werkgebied: ["werkgebied_id"],
  regels: [],
};

const tekst = (v: unknown) => (typeof v === "string" ? v : "");

/** Streng: een onbekende soort of een ref zonder de verplichte sleutels is géén artefact. Liever geen
 *  chip dan een chip die een leeg paneel opent. */
export function parseArtefact(ruw: unknown): Artefact | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  const soort = r.soort;
  if (soort !== "annotatie" && soort !== "begrippen" && soort !== "bronnen" && soort !== "werkgebied"
    && soort !== "regels") return undefined;
  const ref = r.ref && typeof r.ref === "object" && !Array.isArray(r.ref) ? (r.ref as Record<string, unknown>) : undefined;
  if (!ref) return undefined;
  const nodig = soort === "begrippen" && tekst(ref.begrip_id) ? ["werkgebied_id", "begrip_id"] : VERPLICHT[soort];
  if (nodig.some((k) => !tekst(ref[k]))) return undefined;
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

/** Werkgebied en run (of begrip) van een begrippen- of bronnenartefact; of het werkgebied zelf. */
export function werkgebiedArtefactVan(a: Artefact | undefined): WerkgebiedArtefact | undefined {
  if (a?.soort === "werkgebied") {
    const werkgebied_id = tekst(a.ref.werkgebied_id);
    return werkgebied_id ? { soort: "werkgebied", werkgebied_id, run_id: "", titel: a.titel } : undefined;
  }
  if (a?.soort !== "begrippen" && a?.soort !== "bronnen") return undefined;
  const werkgebied_id = tekst(a.ref.werkgebied_id), run_id = tekst(a.ref.run_id);
  const begrip_id = a.soort === "begrippen" ? tekst(a.ref.begrip_id) : "";
  if (!werkgebied_id || !(run_id || begrip_id)) return undefined;
  return { soort: a.soort, werkgebied_id, run_id, ...(begrip_id ? { begrip_id } : {}), titel: a.titel };
}

/** Hoe de chip dit artefact noemt: één begrip heet "Begrip", niet "Begripsvoorstellen". */
export function artefactLabel(a: Artefact): string {
  return a.soort === "begrippen" && tekst(a.ref.begrip_id) ? "Begrip" : ARTEFACT_SOORT_LABEL[a.soort];
}

/** Idem voor een geopend werkgebiedartefact. */
export function werkgebiedLabel(a: WerkgebiedArtefact): string {
  return a.begrip_id ? "Begrip" : ARTEFACT_SOORT_LABEL[a.soort];
}

/** Een sleutel die per artefact verschilt (React `key`). */
export function artefactSleutel(a: WerkgebiedArtefact): string {
  return `${a.soort}:${a.werkgebied_id}:${a.run_id}:${a.begrip_id ?? ""}`;
}

/** Kan de werkplek dit artefact openen? Afleidingsregels zijn gereserveerd, nog niet gebouwd. */
export function isTeOpenen(a: Artefact): boolean {
  return a.soort !== "regels";
}
