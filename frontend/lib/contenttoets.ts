// De contenttoets (plan docs/architectuur/plan-contenttoets.md): de spiegel van `packages/bronmodel/bronmodel/contenttoets.py`.
// `contenttoets.test.ts` leest die bron en vergelijkt de oordelen, de criteria en de telling.

import { aantal } from "./aantal";
import type { AntwoordVindplaats } from "./antwoord";
import type { StatusToon } from "@/components/ui/Lijst";

export type Oordeel = "juist" | "mogelijk_onjuist" | "onvolledig" | "niet_in_de_bron";

/** De volgorde van de telling: wat om een wijziging vraagt eerst. */
export const OORDELEN: readonly Oordeel[] = ["mogelijk_onjuist", "onvolledig", "niet_in_de_bron", "juist"];

export const OORDEEL_LABEL: Record<Oordeel, string> = {
  juist: "Juist", mogelijk_onjuist: "Mogelijk onjuist", onvolledig: "Onvolledig", niet_in_de_bron: "Niet in de bron",
};

export const OORDEEL_TELLING: Record<Oordeel, string> = {
  mogelijk_onjuist: "mogelijk onjuist", onvolledig: "onvolledig", niet_in_de_bron: "niet in de bron", juist: "juist",
};

/** De toon van het label: het oordeel draagt de kleur (rood, geel, grijs, groen), zoals in de mockup. */
export const OORDEEL_TOON: Record<Oordeel, StatusToon> = {
  mogelijk_onjuist: "rood", onvolledig: "geel", niet_in_de_bron: "neutraal", juist: "groen",
};

export const CRITERIA: Record<string, string> = {
  J1: "Waarde", J2: "Voorwaarde en uitzondering", J3: "Reikwijdte", J4: "Modaliteit", J5: "Telmoment", J6: "Samenhang",
  J7: "Geldigheid", V1: "Voorwaarde ontbreekt", V2: "Gevolg ontbreekt", V3: "Uitzondering ontbreekt",
};

export const criteriumTekst = (code: string) => (CRITERIA[code] ? `${code} ${CRITERIA[code]}` : "");

export interface ToetsBron { tekst: string; vindplaats: AntwoordVindplaats }

export interface Toetsbevinding {
  nr: number; citaat: string; begin: number; eind: number; oordeel: Oordeel; criterium: string;
  bronnen: ToetsBron[]; toelichting: string; twijfel: string; voorstel: string;
}

export interface ContenttoetsBlok {
  soort: "contenttoets"; door: "lex"; content: string; peildatum: string; getoetst_tegen: string[];
  voor_redacteur: string[]; bevindingen: Toetsbevinding[]; ontbreekt: { tekst: string; bronnen: ToetsBron[] }[];
  niet_getoetst: string[];
}

export function aantallen(b: Pick<ContenttoetsBlok, "bevindingen">): Record<Oordeel, number> {
  const uit: Record<Oordeel, number> = { mogelijk_onjuist: 0, onvolledig: 0, niet_in_de_bron: 0, juist: 0 };
  for (const x of b.bevindingen) uit[x.oordeel] += 1;
  return uit;
}

/** "11 beweringen: 3 mogelijk onjuist, 2 onvolledig, 2 niet in de bron, 4 juist. 1 punt ontbreekt.", zoals
 *  `telling_tekst` in `bronmodel/contenttoets.py`. */
export function tellingTekst(b: Pick<ContenttoetsBlok, "bevindingen" | "ontbreekt">): string {
  const n = aantallen(b);
  const totaal = OORDELEN.reduce((s, o) => s + n[o], 0);
  const delen = OORDELEN.filter((o) => n[o]).map((o) => `${n[o]} ${OORDEEL_TELLING[o]}`);
  let zin = `${aantal(totaal, "bewering", "beweringen")}${delen.length ? `: ${delen.join(", ")}.` : "."}`;
  const ontbreekt = b.ontbreekt.length;
  if (ontbreekt) zin += ` ${aantal(ontbreekt, "punt ontbreekt", "punten ontbreken")}.`;
  return zin;
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isBron = (v: unknown) => isObject(v) && typeof v.tekst === "string" && isObject(v.vindplaats) &&
  typeof v.vindplaats.iri === "string" && typeof v.vindplaats.label === "string";

/** Streng, zoals elk blok: een bevinding met een gat (geen oordeel, een plek buiten de content) maakt het blok ongeldig. */
export function isContenttoets(b: Record<string, unknown>): boolean {
  if (typeof b.content !== "string" || !Array.isArray(b.bevindingen)) return false;
  const lengte = [...b.content].length;
  return b.bevindingen.every((x) => isObject(x) && typeof x.citaat === "string" && OORDELEN.includes(x.oordeel as Oordeel) &&
    typeof x.begin === "number" && typeof x.eind === "number" && x.begin >= 0 && x.eind <= lengte && x.begin <= x.eind &&
    Array.isArray(x.bronnen) && x.bronnen.every(isBron)) &&
    (b.ontbreekt == null || (Array.isArray(b.ontbreekt) && b.ontbreekt.every((o) => isObject(o) && typeof o.tekst === "string")));
}
