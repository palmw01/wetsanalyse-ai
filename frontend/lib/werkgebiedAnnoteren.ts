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

export function bepalingen(n: number): string {
  return n === 1 ? "1 bepaling" : `${n} bepalingen`;
}
