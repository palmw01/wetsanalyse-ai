// Instellingen › Aanpassingen (plan instellingen-aanpassingen): welke tab een onderdeel van de catalogus toont, en waar
// een oude link naar de werkwijze van Lex (`/werkwijze/…`) nu heen gaat. Zonder `"use client"`: de doorverwijzingen zijn
// server components.
import { INSTELLINGEN_PARAM, type TabKey } from "./instellingen";
import { SOORTEN, type Soort } from "./catalogus";

/** De parameters die naast `?instellingen=` de stand van een lijst in Aanpassingen dragen. Een tabwissel laat ze vallen. */
export const ONDERDEEL_PARAM = "onderdeel";
export const ZOEK_PARAM = "q";
export const SEGMENT_PARAM = "segment";
export const LIJST_PARAMS = [ONDERDEEL_PARAM, ZOEK_PARAM, SEGMENT_PARAM] as const;

/** De twee segmenten van een lijst: wat in Lex draait (de catalogus) en wat jij maakt (de werkplaats). */
export type Segment = "lex" | "concepten";

/** De tab van een soort. Een methode en haar rollen staan bij Methodes, een agentprofiel bij Agents, een connector bij
 *  Connectors. Wat de werkwijze verder toonde (ketens, routes, controles, handelingen, regelsets) staat niet meer in de
 *  app; een oude link daarheen opent Agents. */
export function tabVoorSoort(soort: Soort): TabKey {
  switch (soort) {
    case "methode":
    case "rol":
      return "methodes";
    case "connector":
      return "connectors";
    default:
      return "agents";
  }
}

/** Het onderdeel dat een tab als tweede niveau opent, of niets: een soort zonder eigen plek opent alleen de tab. */
export function toontOnderdeel(soort: Soort): boolean {
  return soort === "methode" || soort === "rol" || soort === "agentprofiel" || soort === "connector";
}

/** Het venster op de werkplek bij een tab en eventueel een onderdeel. */
export function aanpassingPad(tab: TabKey, onderdeel?: string | null): string {
  const qs = new URLSearchParams({ [INSTELLINGEN_PARAM]: tab });
  if (onderdeel) qs.set(ONDERDEEL_PARAM, onderdeel);
  return `/workbench?${qs}`;
}

/** Waar een onderdeel van de catalogus te zien is: zijn tab, met het onderdeel open als het er een eigen plek heeft. */
export function onderdeelPad(id: string): string {
  const i = id.indexOf("/");
  const soort = id.slice(0, i);
  if (i < 0 || !(SOORTEN as readonly string[]).includes(soort)) return aanpassingPad("agents");
  return werkwijzeDoorverwijzing(soort, id.slice(i + 1));
}

/** Waar `/werkwijze/<soort>/<naam>` nu heen gaat. Een onbekende soort opent Agents. */
export function werkwijzeDoorverwijzing(soort: string | undefined, naam: string | undefined): string {
  if (!soort || !(SOORTEN as readonly string[]).includes(soort)) return aanpassingPad("agents");
  const s = soort as Soort;
  return aanpassingPad(tabVoorSoort(s), toontOnderdeel(s) && naam ? `${s}/${naam}` : null);
}

/** De pagina van een concept uit de werkplaats (de editor is een eigen pagina, besluit 13 nov 2026). */
export const CONCEPT_ROUTE = "/aanpassingen/concepten";
