// De rekenkern van het blok *Model per rol* (`components/admin/ModelrollenBlok.tsx`): de groepen en de keuzes per rol.
// De rollen en hun volgorde komen van de api (`bronmodel.modelrollen`); hier wordt niets verzonnen.
import type { Modelrol, ModelrollenOverzicht } from "./types";

/** De waarde van de keuze *Standaard* in de lijst: een lege string, want een profielnaam is nooit leeg. */
export const STANDAARD_WAARDE = "";

/** De rollen per groep, in de volgorde van de api (eerste voorkomen van een groep bepaalt zijn plek). */
export function groepeerModelrollen(rollen: Modelrol[]): [string, Modelrol[]][] {
  const groepen = new Map<string, Modelrol[]>();
  for (const r of rollen) groepen.set(r.groep, [...(groepen.get(r.groep) ?? []), r]);
  return [...groepen.entries()];
}

export interface Keuze {
  waarde: string;
  label: string;
  /** Lex kan dit profiel niet gebruiken: zichtbaar in de lijst, niet te kiezen. */
  uit: boolean;
}

/** De keuzes voor één rol: eerst *Standaard* met het standaardprofiel erachter, dan elk profiel met zijn reden als Lex
 *  het niet kan gebruiken. Het gekozen profiel blijft kiesbaar, ook als het intussen onbruikbaar werd of verdween,
 *  anders toont de lijst stil een andere waarde dan wat er bewaard is. */
export function keuzesVoorRol(stand: ModelrollenOverzicht, rol: Modelrol): Keuze[] {
  // Het model staat al onder de rol ("Nu: …"); in de lijst past alleen de naam.
  const standaard = stand.standaard ? `Standaard (${stand.standaard})` : "Standaard";
  const keuzes: Keuze[] = [{ waarde: STANDAARD_WAARDE, label: standaard, uit: false }];
  for (const [naam, reden] of Object.entries(stand.profielen)) {
    const gekozen = naam === rol.profiel;
    keuzes.push({ waarde: naam, label: reden ? `${naam} (niet bruikbaar: ${reden})` : naam, uit: Boolean(reden) && !gekozen });
  }
  if (rol.profiel && !(rol.profiel in stand.profielen)) {
    keuzes.push({ waarde: rol.profiel, label: `${rol.profiel} (bestaat niet meer)`, uit: false });
  }
  return keuzes;
}
