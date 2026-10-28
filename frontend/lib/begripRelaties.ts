// Begripsrelaties en opvolging (spoor D, fase F2). Puur, voor vitest.
//
// De richting komt uit de keten (`begrippen_pipeline/signalen.py`): bij `hierarchie` wijst `van` naar de
// bredere term en `naar` naar de soort ("X, zoals Y": van X naar Y). De zin draait dat daarom om
// ("Y is een soort X"); de andere typen lezen van links naar rechts.

import type { BegripRelatie, RelatiesAntwoord, RelatieType } from "./types";

export function isRelatiesAntwoord(x: unknown): x is RelatiesAntwoord {
  const r = x as RelatiesAntwoord;
  return !!r && typeof r === "object" && Array.isArray(r.relaties) && Array.isArray(r.voorstellen);
}

const VERBAND: Record<RelatieType, string> = {
  kwalificatie: "geldt als",
  inclusie: "omvat ook",
  uitsluiting: "omvat niet",
  hierarchie: "is een soort",
  verwant: "is verwant aan",
  opvolging: "is vervangen door",
};

export const TYPE_LABEL: Record<RelatieType, string> = {
  kwalificatie: "kwalificatie",
  inclusie: "inclusie",
  uitsluiting: "uitsluiting",
  hierarchie: "soort van",
  verwant: "verwant",
  opvolging: "opvolging",
};

/** Een relatie als zin: [links, verband, rechts]. */
export function relatieZin(type: RelatieType, van: string, naar: string): [string, string, string] {
  return type === "hierarchie" ? [naar, VERBAND.hierarchie, van] : [van, VERBAND[type], naar];
}

/** Hetzelfde voor een type dat de keten als hypothese noemt (de strook *Voorstellen van Lex*). */
export function hypotheseZin(hypothese: string, van: string, naar: string): [string, string, string] {
  return hypothese in VERBAND ? relatieZin(hypothese as RelatieType, van, naar)
    : hypothese === "zelfde_betekenis" ? [van, "betekent hetzelfde als", naar] : [van, hypothese, naar];
}

export const HERKOMST_LABEL: Record<BegripRelatie["herkomst"], string> = {
  lex: "voorgesteld door Lex",
  analist: "door de analist",
  systeem: "vastgelegd bij opvolging",
};

/** Wat de analist vanuit één begrip kan zeggen, als keuze in een lijst. `omgekeerd`: het andere begrip
 *  staat links in de relatie (van). */
export const KEUZES: { waarde: string; label: string; type: Exclude<RelatieType, "opvolging">; omgekeerd: boolean }[] = [
  { waarde: "kwalificatie", label: "geldt als", type: "kwalificatie", omgekeerd: false },
  { waarde: "inclusie", label: "omvat ook", type: "inclusie", omgekeerd: false },
  { waarde: "uitsluiting", label: "omvat niet", type: "uitsluiting", omgekeerd: false },
  { waarde: "soort-van", label: "is een soort", type: "hierarchie", omgekeerd: true },
  { waarde: "heeft-soort", label: "heeft als soort", type: "hierarchie", omgekeerd: false },
  { waarde: "verwant", label: "is verwant aan (toelichting verplicht)", type: "verwant", omgekeerd: false },
];

/** De invoer voor de api bij een keuze vanuit `dit` naar `ander`. */
export function relatieInvoer(keuze: string, dit: string, ander: string, toelichting: string) {
  const k = KEUZES.find((x) => x.waarde === keuze)!;
  return { van_begrip: k.omgekeerd ? ander : dit, naar_begrip: k.omgekeerd ? dit : ander, type: k.type,
    ...(toelichting.trim() ? { toelichting: toelichting.trim() } : {}) };
}

/** Kan een keuze verstuurd worden? `verwant` vraagt een toelichting, een relatie gaat naar een ander begrip. */
export function magVastleggen(keuze: string, dit: string, ander: string, toelichting: string): boolean {
  return !!ander && ander !== dit && (keuze !== "verwant" || !!toelichting.trim());
}

/** Vastgelegd eerst (veranderd bovenaan), dan afgewezen; opvolging hoort bij de kop, niet in de lijst. */
export function ordenRelaties(rs: readonly BegripRelatie[]): { vastgelegd: BegripRelatie[]; afgewezen: BegripRelatie[] } {
  const zonder = rs.filter((r) => r.type !== "opvolging");
  return {
    vastgelegd: zonder.filter((r) => r.beoordeling === "akkoord").sort((a, b) => Number(!!b.veranderd) - Number(!!a.veranderd)),
    afgewezen: zonder.filter((r) => r.beoordeling === "afgewezen"),
  };
}
