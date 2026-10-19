// Het overzicht van de begrippen over werkgebieden heen (spoor D, fase F4). Een leesingang: zoeken,
// filteren en doorklikken naar de kaart in zijn werkgebied. Wat er gezocht wordt, doet de api
// (`GET /v1/begrippen`); hier staan de URL-stand van de filters en de labels.
import type { BegripStatus } from "./types";

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
  geaccordeerd_op: string | null;
  gewijzigd: string;
}

export interface BegrippenOverzicht {
  resultaten: BegripOverzichtRij[];
  totaal: number;
  volgende_offset: number | null;
}

export const BEGRIP_STATUSSEN: BegripStatus[] = ["geaccordeerd", "concept", "vervangen"];

export const BEGRIP_STATUS_LABEL: Record<BegripStatus, string> = {
  concept: "Concept",
  geaccordeerd: "Geaccordeerd",
  vervangen: "Vervangen",
};

export interface OverzichtFilters {
  q: string;
  status: BegripStatus[];
  werkgebied: string;
}

const ID = /^[A-Za-z0-9-]{1,64}$/;

/** De filters uit de URL; wat niet klopt valt weg in plaats van een fout te geven. */
export function filtersUitParams(p: URLSearchParams): OverzichtFilters {
  const status = p.getAll("status").filter((s): s is BegripStatus => (BEGRIP_STATUSSEN as string[]).includes(s));
  const werkgebied = p.get("werkgebied") ?? "";
  return { q: (p.get("q") ?? "").slice(0, 200), status: [...new Set(status)], werkgebied: ID.test(werkgebied) ? werkgebied : "" };
}

/** De querystring voor de pagina-URL én de api – dezelfde namen, behalve het werkgebied. */
export function paramsVan(f: OverzichtFilters, voor: "pagina" | "api"): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set("q", f.q.trim());
  for (const s of f.status) p.append("status", s);
  if (f.werkgebied) p.set(voor === "api" ? "werkgebied_id" : "werkgebied", f.werkgebied);
  return p;
}

/** Waar een klik op een begrip heen gaat: de kaart in zijn werkgebied. */
export function kaartUrl(werkgebiedId: string, begripId: string): string {
  return `/werkgebieden/${encodeURIComponent(werkgebiedId)}?tab=begrippen&begrip=${encodeURIComponent(begripId)}`;
}

export function kort(tekst: string, n = 220): string {
  const t = tekst.replace(/\s+/g, " ").trim();
  return t.length <= n ? t : `${t.slice(0, n).trimEnd()}…`;
}
