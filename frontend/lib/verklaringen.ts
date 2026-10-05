import { nodeRequest } from "./annotatieNode";

/** De leesbare namen van de codes in het herkomstspoor (`GET /v1/annotatie/verklaringen`).
 *
 *  Gegenereerd in graph-qa uit `jas_pipeline/verklaringen.yaml` naar `api/app/vocabulaire/`; dezelfde
 *  namen staan in de JAS-vocabulairegraaf. De frontend verzint er geen eigen namen bij: een code die
 *  hier ontbreekt, verschijnt als zichzelf. */
export interface Verklaring { naam: string; uitleg: string; soort?: string }
export type VerklaringSectie = "besluit" | "classifier" | "detectie" | "regels" | "resolutie" | "twijfel" | "validatie";
export type Verklaringen = Partial<Record<VerklaringSectie, Record<string, Verklaring>>>;

/** De secties die de werkplek leest; `api/tests/test_verklaringen_frontend_drift.py` toetst ze tegen
 *  de gegenereerde JSON. */
export const GEBRUIKTE_SECTIES: readonly VerklaringSectie[] = ["besluit", "detectie", "regels", "resolutie", "twijfel", "validatie"];

/** Naam en uitleg van één code. Zonder vocabulaire, of bij een onbekende code, is de naam de code
 *  zelf en de uitleg leeg – liever een id in beeld dan een verzonnen omschrijving. Een code met een
 *  achtervoegsel (`CLASSIFIER_ONGELDIGE_KLASSE:Tijd`) zoekt op het deel vóór de dubbele punt. */
export function verklaar(v: Verklaringen | undefined, sectie: VerklaringSectie, code: string): Verklaring & { code: string } {
  const sleutel = code.split(":")[0];
  const gevonden = v?.[sectie]?.[code] ?? v?.[sectie]?.[sleutel];
  return { code, naam: gevonden?.naam || code, uitleg: gevonden?.uitleg ?? "", ...(gevonden?.soort ? { soort: gevonden.soort } : {}) };
}

let cache: Promise<Verklaringen> | undefined;
/** Eén keer per pagina opgehaald. Net als `samenhangBeschikbaar`: alleen een ántwoord wordt
 *  onthouden, een fout vraagt de volgende keer opnieuw – de uitklap toont dan tot die tijd codes. */
export function haalVerklaringen(): Promise<Verklaringen> {
  cache ??= nodeRequest<Verklaringen>("verklaringen").catch(() => {
    cache = undefined;
    return {};
  });
  return cache;
}
