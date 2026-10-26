// Het overzicht van de begrippen over werkgebieden heen (spoor D, fase F4). Een leesingang: zoeken,
// filteren en doorklikken naar de kaart in zijn werkgebied. Wat er gezocht wordt, doet de api
// (`GET /v1/begrippen`); hier staan de URL-stand van de filters en de labels.
import type { BegripStatus } from "./types";
import { artefactPad } from "./werkgebiedPaden";

export interface BegripOverzichtRij {
  id: string;
  iri: string;
  werkgebied_id: string;
  werkgebied_naam: string;
  naam: string;
  alternatieve_termen: string[];
  status: BegripStatus;
  revisie: number;
  definitie: string;
  definitie_herkomst: string | null;
  vervangen_door: { begrip_id: string; naam: string } | null;
  aantal_dragend: number;
  /** Geaccordeerd, maar zoveel dragende passages veranderden sindsdien (een oudere api stuurt het niet). */
  herbeoordelen?: number;
  geaccordeerd_op: string | null;
  gewijzigd: string;
}

export interface BegrippenOverzicht {
  resultaten: BegripOverzichtRij[];
  totaal: number;
  volgende_offset: number | null;
  /** De tellers bij de statusknoppen: dezelfde filters zonder het statusfilter (een oudere api stuurt ze
   *  niet; dan staan er geen tellers). */
  per_status?: Partial<Record<BegripStatus, number>>;
}

export const BEGRIP_STATUSSEN: BegripStatus[] = ["geaccordeerd", "concept", "vervangen"];

export const BEGRIP_STATUS_LABEL: Record<BegripStatus, string> = {
  concept: "Concept",
  geaccordeerd: "Geaccordeerd",
  vervangen: "Vervangen",
};

/** Eén status of alle (`""`), zoals de filterknoppen van de andere overzichten (`OverzichtBalk`). */
export interface OverzichtFilters {
  q: string;
  status: BegripStatus | "";
  werkgebied: string;
  /** *Door mij bewerkt*: alleen begrippen met een revisie van jou (de api, `mijn`). */
  mijn: boolean;
}

const ID = /^[A-Za-z0-9-]{1,64}$/;

/** De filters uit de URL; wat niet klopt valt weg in plaats van een fout te geven. Een oude URL met meer
 *  statussen leest als de eerste geldige. */
export function filtersUitParams(p: URLSearchParams): OverzichtFilters {
  const status = p.getAll("status").find((s): s is BegripStatus => (BEGRIP_STATUSSEN as string[]).includes(s)) ?? "";
  const werkgebied = p.get("werkgebied") ?? "";
  return { q: (p.get("q") ?? "").slice(0, 200), status, werkgebied: ID.test(werkgebied) ? werkgebied : "",
    mijn: p.get("mijn") === "1" };
}

/** De querystring voor de pagina-URL én de api – dezelfde namen, behalve het werkgebied en `mijn`. */
export function paramsVan(f: OverzichtFilters, voor: "pagina" | "api"): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.status) p.set("status", f.status);
  if (f.werkgebied) p.set(voor === "api" ? "werkgebied_id" : "werkgebied", f.werkgebied);
  if (f.mijn) p.set("mijn", voor === "api" ? "true" : "1");
  return p;
}

/** Waar een klik op een begrip heen gaat: de kaart in zijn werkgebied. */
export function kaartUrl(werkgebiedId: string, begripId: string): string {
  return artefactPad(werkgebiedId, "begrippen", { begrip: begripId });
}

export function kort(tekst: string, n = 220): string {
  const t = tekst.replace(/\s+/g, " ").trim();
  return t.length <= n ? t : `${t.slice(0, n).trimEnd()}…`;
}
