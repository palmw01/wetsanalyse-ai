// Lex annoteert het werkgebied (spoor D, fase B).
//
// De werkvoorraad komt van de api (`GET /v1/werkgebieden/{id}/annotatie-werkvoorraad`); de run
// draait in graph-qa (`agent/werkgebied_annotatie.py`). Lex begint nooit zonder akkoord: hij zegt in
// het gesprek wat er gebeurt en wat het kost (een `bevestiging`), en de werkplek start pas met
// `bevestigd: <aantal>`. Is de werkvoorraad intussen veranderd, dan weigert graph-qa en komt er een
// nieuwe bevestiging.
//
// Pure functies, zodat de teksten en de tellingen zonder DOM te testen zijn
// (lib/werkgebiedAnnoteren.test.ts).

import type { ThreadItem } from "./threadItem";
import type { Bevestiging } from "./types";

/** De vraag die in het gesprek komt te staan; graph-qa herkent hem ook zonder `modus`. */
export const ANNOTEER_PROMPT = "Annoteer het werkgebied";

/** Zoveel bepalingen per run (`PLAFOND` in graph-qa); de rest blijft nieuw voor een volgende run. */
export const PLAFOND = 40;

export function parseBevestiging(ruw: unknown): Bevestiging | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  // Een soort die deze werkplek niet kent, krijgt geen knop: liever niets dan een knop die iets anders start.
  if (r.soort !== "werkgebied_annoteren" && r.soort !== "begrippen_verdiepen") return undefined;
  if (typeof r.werkgebied_id !== "string" || !r.werkgebied_id) return undefined;
  if (typeof r.aantal !== "number" || !Number.isInteger(r.aantal) || r.aantal < 0) return undefined;
  const schatting = typeof r.schatting === "number" && Number.isFinite(r.schatting) ? r.schatting : null;
  const uit: Bevestiging = { soort: r.soort, werkgebied_id: r.werkgebied_id, aantal: r.aantal, schatting };
  // Alleen een bereik dat deze werkplek kent; anders het hele werkgebied, zoals een oud bericht.
  if (r.soort === "werkgebied_annoteren" && r.bereik === "deelvragen") {
    uit.bereik = "deelvragen";
    if (typeof r.deelvraag_id === "string" && /^[A-Za-z0-9-]{1,64}$/.test(r.deelvraag_id)) uit.deelvraag_id = r.deelvraag_id;
  }
  return uit;
}

/** Het antwoord op een bevestiging: de knop (gestart) of *Annuleren*. */
export type BevestigingKeuze = "gestart" | "geannuleerd";

/** De tekst van het user-bericht bij *Annuleren*. */
export const ANNULEER_TEKST = "Annuleren";

export function parseBevestigingKeuze(ruw: unknown): BevestigingKeuze | undefined {
  const keuze = ruw && typeof ruw === "object" ? (ruw as Record<string, unknown>).keuze : undefined;
  return keuze === "gestart" || keuze === "geannuleerd" ? keuze : undefined;
}

/** Welke voorstellen zijn afgehandeld, en hoe: per item met een bevestiging het eerste antwoord dat erna
 *  komt, vóór het volgende voorstel. Een antwoord hoort dus nooit bij een ouder voorstel dan het laatste.
 *  Een voorstel zonder antwoord (ook van vóór deze regel) houdt zijn knoppen. */
export function afgehandeld(items: ThreadItem[]): Map<string, BevestigingKeuze> {
  const uit = new Map<string, BevestigingKeuze>();
  let open: string | undefined;
  for (const it of items) {
    if (it.type === "antwoord" && it.bevestiging) open = it.id;
    else if (open && it.type === "user" && it.bevestigingKeuze) {
      uit.set(open, it.bevestigingKeuze);
      open = undefined;
    }
  }
  return uit;
}

export function bepalingen(n: number): string {
  return n === 1 ? "1 bepaling" : `${n} bepalingen`;
}
