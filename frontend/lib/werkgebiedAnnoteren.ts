// Lex annoteert het werkgebied (spoor D, fase B).
//
// De werkvoorraad komt van de api (`GET /v1/werkgebieden/{id}/annotatie-werkvoorraad`); de run
// draait in graph-qa (`agent/werkgebied_annotatie.py`). Lex begint nooit zonder akkoord: de werkplek
// toont eerst wat er gebeurt en wat het kost, en start pas met `bevestigd: <aantal>`. Is de
// werkvoorraad intussen veranderd, dan weigert graph-qa en komt er een nieuwe bevestiging.
//
// Pure functies, zodat de teksten en de tellingen zonder DOM te testen zijn
// (lib/werkgebiedAnnoteren.test.ts).

import type { AnnotatieWerkvoorraad, Bevestiging, EenheidStatus } from "./types";

/** De vraag die in het gesprek komt te staan; graph-qa herkent hem ook zonder `modus`. */
export const ANNOTEER_PROMPT = "Annoteer het werkgebied";

/** Zoveel bepalingen per run (`PLAFOND` in graph-qa); de rest blijft nieuw voor een volgende run. */
export const PLAFOND = 40;

export const STAND_LABEL: Record<EenheidStatus, string> = {
  nieuw: "nieuw",
  te_beoordelen: "te beoordelen",
  beoordeeld: "beoordeeld",
  zonder_markeringen: "zonder markeringen",
  afgerond: "afgerond",
};

const STAND_VOLGORDE: EenheidStatus[] = ["nieuw", "te_beoordelen", "beoordeeld", "zonder_markeringen", "afgerond"];

export function parseBevestiging(ruw: unknown): Bevestiging | undefined {
  if (!ruw || typeof ruw !== "object") return undefined;
  const r = ruw as Record<string, unknown>;
  // Een soort die deze werkplek niet kent, krijgt geen knop: liever niets dan een knop die iets anders start.
  if (r.soort !== "werkgebied_annoteren" && r.soort !== "begrippen_verdiepen") return undefined;
  if (typeof r.werkgebied_id !== "string" || !r.werkgebied_id) return undefined;
  if (typeof r.aantal !== "number" || !Number.isInteger(r.aantal) || r.aantal < 0) return undefined;
  const schatting = typeof r.schatting === "number" && Number.isFinite(r.schatting) ? r.schatting : null;
  return { soort: r.soort, werkgebied_id: r.werkgebied_id, aantal: r.aantal, schatting };
}

/** Heeft het antwoord de vorm van een werkvoorraad? Een blok dat er niet op kan rekenen, mag de rest
 *  van de pagina (de inventaris eronder) niet meenemen. */
export function isWerkvoorraad(w: unknown): w is AnnotatieWerkvoorraad {
  const r = w as Partial<AnnotatieWerkvoorraad> | null;
  return !!r && Array.isArray(r.selecties) && Array.isArray(r.eenheden) && Array.isArray(r.te_annoteren)
    && Array.isArray(r.open_punten) && !!r.budget && typeof r.budget === "object";
}

/** 21000 → "21.000", zoals Lex het in het gesprek schrijft. */
export function getal(n: number): string {
  return Math.round(n).toLocaleString("nl-NL");
}

export function bepalingen(n: number): string {
  return n === 1 ? "1 bepaling" : `${n} bepalingen`;
}

/** "3 nieuw · 2 te beoordelen · 1 afgerond" – alleen de standen die voorkomen, in vaste volgorde. */
export function standRegel(perStand: Partial<Record<EenheidStatus, number>>): string {
  return STAND_VOLGORDE.filter((s) => (perStand[s] ?? 0) > 0).map((s) => `${perStand[s]} ${STAND_LABEL[s]}`).join(" · ");
}

/** Wat de bevestiging toont: de getallen, en wat er níét meegaat. */
export interface BevestigingInhoud {
  aantal: number;
  /** Zoveel doet deze run (hoogstens het plafond). */
  dezeRun: number;
  /** Tokens voor deze run, of `null` zonder geschiedenis. */
  schatting: number | null;
  schattingUitleg: string;
  /** Tokens over, of `null` als er geen limiet geldt. */
  budgetOver: number | null;
  /** De schatting is hoger dan wat er over is: de run stopt dan halverwege. */
  budgetKrap: boolean;
  nietMee: string[];
  openPunten: string[];
}

export function bevestigingInhoud(wv: AnnotatieWerkvoorraad): BevestigingInhoud {
  const aantal = wv.te_annoteren.length;
  const dezeRun = Math.min(aantal, PLAFOND);
  const schatting = wv.schatting ? wv.schatting.per_bepaling * dezeRun : null;
  const budgetOver = wv.budget.actief ? wv.budget.resterend : null;
  const al = wv.eenheden.filter((e) => e.stand.status !== "nieuw").length;
  const nietMee: string[] = [];
  if (al) nietMee.push(`${bepalingen(al)} met voorstellen, een oordeel of afgerond`);
  if (wv.context_niet_meegenomen)
    nietMee.push(wv.context_niet_meegenomen === 1 ? "1 contextbron" : `${wv.context_niet_meegenomen} contextbronnen`);
  if (aantal > PLAFOND) nietMee.push(`${bepalingen(aantal - PLAFOND)} boven het plafond van ${PLAFOND} per run (volgende run)`);
  return {
    aantal, dezeRun, schatting,
    schattingUitleg: wv.schatting_toelichting,
    budgetOver,
    budgetKrap: schatting !== null && budgetOver !== null && schatting > budgetOver,
    nietMee,
    openPunten: wv.open_punten,
  };
}
