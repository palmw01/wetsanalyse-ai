// Verwijderen werkt voor een annotatie, een werkgebied en een begrip op dezelfde manier: echt wissen,
// met de audit als bewijs (api), één knop (`components/ui/VerwijderKnop`) op dezelfde plekken – het
// paneel naast het gesprek, de pagina en de lijst – en daarna een toestand in plaats van een fout.
//
// Een verwijderd werkgebied of begrip geeft een 404 met `{fout: "verwijderd", soort, op, door}`; een
// paneel of een oud gesprek toont dan wanneer en door wie, zoals een verwijderde annotatie dat al deed.

import type { ApiError } from "./types";

export type VerwijderSoort = "annotatie" | "werkgebied" | "begrip";

/** Wat de knop als tooltip draagt: wat er weggaat en wat blijft. */
export const VERWIJDER_UITLEG: Record<VerwijderSoort, string> = {
  annotatie: "Verwijdert alle markeringen en beoordelingen van deze bepaling, ook uit de kennisgraaf",
  werkgebied: "Verwijdert het werkgebied met zijn bronselecties, deelvragen en begrippen, ook uit de kennisgraaf. De annotaties blijven staan.",
  begrip: "Verwijdert het begrip met zijn koppelingen en relaties, ook uit de kennisgraaf. De annotaties blijven staan.",
};

const NAAM: Record<VerwijderSoort, string> = { annotatie: "Annotatie", werkgebied: "Werkgebied", begrip: "Begrip" };

/** De toegankelijke naam van de knop: "Werkgebied verwijderen". */
export const verwijderLabel = (soort: VerwijderSoort) => `${NAAM[soort]} verwijderen`;

export interface Verwijderd {
  soort: "werkgebied" | "begrip";
  op: string;
  door: string;
}

/** De verwijderd-stand uit een api-fout, of `null` als het een andere fout is (ook een 404 van iets dat
 *  nooit bestond). */
export function verwijderdUit(e: unknown): Verwijderd | null {
  const fout = e as Partial<ApiError> | null;
  if (!fout || fout.status !== 404 || !fout.data || fout.data.fout !== "verwijderd") return null;
  const { soort, op, door } = fout.data;
  if ((soort !== "werkgebied" && soort !== "begrip") || typeof op !== "string") return null;
  return { soort, op, door: typeof door === "string" ? door : "" };
}

/** "Dit werkgebied is verwijderd op 21 okt 2026 door jurist-a." */
export function verwijderdZin(v: Verwijderd): string {
  const datum = new Date(v.op);
  const wanneer = Number.isNaN(datum.getTime()) ? "" :
    ` op ${datum.toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" })}`;
  return `${v.soort === "werkgebied" ? "Dit werkgebied" : "Dit begrip"} is verwijderd${wanneer}${v.door ? ` door ${v.door}` : ""}.`;
}
