// De modelkeuzes van Lex (plan instellingen-aanpassingen, PR 5; api `api/app/modelkeuzes.py`, catalogus
// `bronmodel/modelkeuzes.py`): welk modelprofiel een agentprofiel (`agent:<profiel>`) of een stap zonder profiel
// (`stap:<rol>`) gebruikt. Zonder keuze volgt een sleutel het standaardprofiel. De catalogus komt van de api; de werkplek
// houdt geen eigen lijst bij. `modelkeuzes.test.ts` toetst de rekenkern.

/** Het model dat Lex voor een sleutel gebruikt, zoals iedereen het mag zien. */
export interface Gekozen {
  profiel: string;
  model: string;
  /** `keuze`: de beheerder koos dit; `standaard`: de sleutel volgt het standaardprofiel. */
  bron: "keuze" | "standaard";
}

export interface Sleutel {
  sleutel: string;
  soort: "agent" | "stap";
  label: string;
  groep: string;
  beschrijving: string;
}

/** `GET /api/modelkeuzes`: voor iedereen. Een sleutel zonder bruikbaar model ontbreekt in `keuzes`. */
export interface Stand {
  standaard: Gekozen | null;
  keuzes: Record<string, Gekozen>;
  sleutels: Sleutel[];
}

/** Eén sleutel zoals het beheer hem ziet (`GET /api/admin/modelkeuzes`). */
export interface Keuze extends Sleutel {
  waarschuwing: string;
  profiel: string | null;
  model: string;
  niet_bruikbaar: string;
  door: string;
  bijgewerkt: string;
}

export interface Overzicht {
  standaard: string | null;
  standaard_model: string;
  standaard_niet_bruikbaar: string;
  keuzes: Keuze[];
  profielen: Record<string, { niet_bruikbaar: string; gebruikt_door: string[] }>;
}

/** De waarde van *Standaard* in de keuzelijst: geen profiel. Een profielnaam kan nooit leeg zijn. */
export const STANDAARD = "";

const isTekst = (x: unknown): x is string => typeof x === "string";

function isSleutel(x: unknown): x is Sleutel {
  const s = x as Sleutel;
  return !!s && isTekst(s.sleutel) && (s.soort === "agent" || s.soort === "stap") && isTekst(s.label)
    && isTekst(s.groep) && isTekst(s.beschrijving);
}

function isGekozen(x: unknown): x is Gekozen {
  const g = x as Gekozen;
  return !!g && isTekst(g.profiel) && isTekst(g.model) && (g.bron === "keuze" || g.bron === "standaard");
}

/** Streng: een rij die niet klopt valt weg; zonder lijst van sleutels is er geen stand (`null`). */
export function parseStand(x: unknown): Stand | null {
  const s = x as Stand;
  if (!s || typeof s !== "object" || !Array.isArray(s.sleutels)) return null;
  const keuzes = Object.fromEntries(Object.entries(s.keuzes ?? {}).filter(([, g]) => isGekozen(g)));
  return { standaard: isGekozen(s.standaard) ? s.standaard : null, keuzes, sleutels: s.sleutels.filter(isSleutel) };
}

export function parseOverzicht(x: unknown): Overzicht | null {
  const o = x as Overzicht;
  if (!o || typeof o !== "object" || !Array.isArray(o.keuzes)) return null;
  const keuzes = o.keuzes.filter((k) => isSleutel(k) && (k.profiel === null || isTekst(k.profiel)))
    .map((k) => ({ ...k, waarschuwing: k.waarschuwing ?? "", model: k.model ?? "", niet_bruikbaar: k.niet_bruikbaar ?? "",
      door: k.door ?? "", bijgewerkt: k.bijgewerkt ?? "" }));
  return { standaard: isTekst(o.standaard) ? o.standaard : null, standaard_model: o.standaard_model ?? "",
    standaard_niet_bruikbaar: o.standaard_niet_bruikbaar ?? "", keuzes, profielen: o.profielen ?? {} };
}

/** De sleutel van een agentprofiel uit de catalogus (`agentprofiel/definitie` → `agent:definitie`). */
export function sleutelVanProfiel(onderdeelId: string): string {
  return `agent:${onderdeelId.slice(onderdeelId.indexOf("/") + 1)}`;
}

/** Het model als tekst, voor wie niet kiest. Zonder bruikbaar model (geen keuze en geen bruikbare standaard) gebruikt
 *  Lex het model van de omgeving. */
export function modelTekst(g: Pick<Gekozen, "profiel" | "model" | "bron"> | null | undefined): string {
  if (!g || !g.model) return "het model van de omgeving";
  return g.bron === "standaard" ? `standaard (${g.model})` : `${g.profiel} (${g.model})`;
}

/** De keuzes in de lijst van het beheer: *Standaard* en elk profiel; een profiel dat Lex niet kan gebruiken staat
 *  uitgeschakeld, met de reden. */
export function keuzesVoor(o: Overzicht): { waarde: string; label: string; uit: boolean; reden: string }[] {
  const std = o.standaard_model ? `Standaard (${o.standaard_model})` : "Standaard (het model van de omgeving)";
  return [{ waarde: STANDAARD, label: std, uit: false, reden: "" },
    ...Object.entries(o.profielen).sort(([a], [b]) => a.localeCompare(b, "nl")).map(([naam, p]) => ({
      waarde: naam, label: p.niet_bruikbaar ? `${naam} – niet bruikbaar` : naam, uit: !!p.niet_bruikbaar, reden: p.niet_bruikbaar,
    }))];
}

/** De labels van de sleutels die een profiel gekozen hebben (voor *Gebruikt door* bij Modellen). */
export function gebruiktDoor(o: Overzicht, profiel: string): string[] {
  const label = Object.fromEntries(o.keuzes.map((k) => [k.sleutel, k.label]));
  return (o.profielen[profiel]?.gebruikt_door ?? []).map((s) => label[s] ?? s);
}
