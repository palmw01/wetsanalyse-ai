// Het overzicht van de afleidingsregels over werkgebieden heen (ADR-018, de zijbalk), in de vorm van het
// begrippenoverzicht (`lib/begrippenOverzicht.ts`): een leesingang die zoekt, filtert en doorklikt naar de regel in zijn
// werkgebied. Zoeken doet de api (`GET /v1/regels`); hier staan de URL-stand van de filters en de labels.
import type { RegelSoort, RegelStatus } from "./regels";

export interface RegelOverzichtRij {
  id: string;
  werkgebied_id: string;
  werkgebied_naam: string;
  naam: string;
  uitvoer: string;
  status: RegelStatus;
  revisie: number;
  soort: RegelSoort;
  brontype: "wet" | "beleid";
  gevallen: number;
  /** De regel in het taalpatroon, afgeleid door de api. */
  regeltekst: string;
  herkomst: "lex" | "jurist" | "import";
  gewijzigd: string | null;
}

export interface RegelsOverzicht {
  resultaten: RegelOverzichtRij[];
  totaal: number;
  /** Dezelfde filters zonder het statusfilter, zodat een teller klopt met wat de knop geeft. */
  per_status?: Partial<Record<RegelStatus, number>>;
}

/** De statussen als filterknop. Een beleidsregel telt bij *Geaccordeerd* in de api niet mee: die heeft een eigen knop. */
export const REGEL_FILTER_STATUSSEN: RegelStatus[] = ["concept", "geaccordeerd", "geaccordeerd_als_beleidsregel", "afgewezen", "vervangen"];

export interface RegelFilters {
  q: string;
  status: RegelStatus | "";
  werkgebied: string;
  /** *Door mij bewerkt*: alleen regels met een revisie van jou. */
  mijn: boolean;
}

const ID = /^[A-Za-z0-9-]{1,64}$/;

/** De filters uit de URL; wat niet klopt valt weg in plaats van een fout te geven. */
export function regelFiltersUitParams(p: URLSearchParams): RegelFilters {
  const status = REGEL_FILTER_STATUSSEN.find((s) => s === p.get("status")) ?? "";
  const werkgebied = p.get("werkgebied") ?? "";
  return { q: (p.get("q") ?? "").slice(0, 200), status, werkgebied: ID.test(werkgebied) ? werkgebied : "", mijn: p.get("mijn") === "1" };
}

/** De querystring voor de pagina-URL én de api: dezelfde namen, behalve het werkgebied en `mijn`. */
export function regelParamsVan(f: RegelFilters, voor: "pagina" | "api"): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.status) p.set("status", f.status);
  if (f.werkgebied) p.set(voor === "api" ? "werkgebied_id" : "werkgebied", f.werkgebied);
  if (f.mijn) p.set("mijn", voor === "api" ? "true" : "1");
  return p;
}
