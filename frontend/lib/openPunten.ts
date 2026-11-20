// Open punten (L-X-1, lessenbundel 4; ADR-018 §6 en besluit 7.13): wat een analyse niet stil mag beslissen. De vorm komt
// uit de api (`api/app/open_punt_contracts.py`); hier staan de namen, wat bij een regel en een geval hoort, en het besluit.
// Het besluit is van de jurist en gaat via één route (`…/open-punten/{id}/besluit`), op de regelkaart én, later, vanuit
// de keuzekaart in het gesprek.

export type OpenPuntSoort = "interpretatiekeuze" | "ontbrekend_uitvoeringsbeleid" | "onderzoekspunt" | "gat_in_de_annotatie";
export type OpenPuntStatus = "open" | "gekozen" | "getoetst";
export type Methode = "grammaticaal" | "systematisch" | "wetshistorisch" | "teleologisch";
export type Bronsoort = "wettekst" | "wetsgeschiedenis" | "jurisprudentie" | "beleid" | "kennisgroepstandpunt"
  | "uitvoeringspraktijk" | "literatuur";

export interface Aanhaking { soort: "regel" | "geval" | "markering" | "begrip" | "deelvraag" | "werkgebied"; id: string; geval: string; bestaat?: boolean }
export interface Grondslag { soort: "markering" | "bron" | "begrip" | "stuk"; id: string; label: string }
export interface Lezing { label: string; omschrijving: string; grondslag: Grondslag[] }
export interface TeToetsen { bronsoort: Bronsoort; omschrijving: string; getoetst: boolean; uitkomst: string }
export interface Keuze { gekozen: string; motivering: string; methode: Methode | null; door: string; op: string | null }

export interface OpenPunt {
  id: string;
  werkgebied_id: string;
  status: OpenPuntStatus;
  revisie: number;
  soort: OpenPuntSoort;
  /** De naam zoals de skill hem schrijft ("ontbrekend uitvoeringsbeleid"). */
  soort_naam: string;
  inhoud: { soort: OpenPuntSoort; vraag: string; toelichting: string; hangt_aan: Aanhaking[]; lezingen: Lezing[];
    te_toetsen: TeToetsen[] };
  keuze: Keuze | null;
  herkomst: "lex" | "jurist" | "import";
}

/** Wat een keuze vraagt vóór de regel geaccordeerd wordt (api `regel_store.KEUZE_SOORTEN`); de rest is een signaal. */
export const KEUZE_SOORTEN: readonly OpenPuntSoort[] = ["interpretatiekeuze", "ontbrekend_uitvoeringsbeleid"];

export const OPEN_PUNT_STATUS_LABEL: Record<OpenPuntStatus, string> = { open: "Open", gekozen: "Gekozen", getoetst: "Getoetst" };

export const METHODE_LABEL: Record<Methode, string> = {
  grammaticaal: "Grammaticaal", systematisch: "Systematisch", wetshistorisch: "Wetshistorisch", teleologisch: "Teleologisch",
};

export const BRONSOORT_LABEL: Record<Bronsoort, string> = {
  wettekst: "Wettekst", wetsgeschiedenis: "Wetsgeschiedenis", jurisprudentie: "Jurisprudentie", beleid: "Beleid",
  kennisgroepstandpunt: "Standpunt kennisgroep", uitvoeringspraktijk: "Uitvoeringspraktijk", literatuur: "Literatuur",
};

/** De naam met hoofdletter, voor een label ("Interpretatiekeuze"). */
export function soortLabel(p: Pick<OpenPunt, "soort_naam">): string {
  return p.soort_naam.charAt(0).toUpperCase() + p.soort_naam.slice(1);
}

/** Houdt dit punt het accorderen tegen? Alleen een open keuze of open beleidspunt (ADR-018 besluit 2). */
export function blokkeert(p: Pick<OpenPunt, "soort" | "status">): boolean {
  return p.status === "open" && KEUZE_SOORTEN.includes(p.soort);
}

/** De punten bij één geval van een regel; met `geval` leeg de punten op de regel zelf. */
export function puntenBij(punten: OpenPunt[], regelId: string, geval = ""): OpenPunt[] {
  return punten.filter((p) => p.inhoud.hangt_aan.some((a) =>
    geval ? a.soort === "geval" && a.id === regelId && a.geval === geval : a.soort === "regel" && a.id === regelId));
}

/** Eerst wat open is en tegenhoudt, dan de andere open punten, dan wat gekozen of getoetst is. */
export function ordenPunten(punten: OpenPunt[]): OpenPunt[] {
  const rang = (p: OpenPunt) => (blokkeert(p) ? 0 : p.status === "open" ? 1 : 2);
  return [...punten].sort((a, b) => rang(a) - rang(b));
}

export interface BesluitInvoer { gekozen: string; motivering: string; methode: Methode | null }

/** Kan dit besluit weg? Met lezingen: een gekozen lezing; zonder: een motivering (hoe het verder gaat). Een
 *  interpretatiekeuze vraagt ook de methode en een motivering (ADR-018 §6: de keuze en waarom). */
export function besluitFout(p: Pick<OpenPunt, "soort" | "inhoud">, b: BesluitInvoer): string | null {
  const lezingen = p.inhoud.lezingen.map((l) => l.label);
  if (lezingen.length && !lezingen.includes(b.gekozen)) return "Kies een lezing.";
  if (!b.motivering.trim()) return lezingen.length ? "Zeg waarom je deze lezing kiest." : "Zeg hoe het verder gaat.";
  if (p.soort === "interpretatiekeuze" && !b.methode) return "Kies de methode van de interpretatie.";
  return null;
}

/** De zin van een genomen keuze: "Lezing B (grammaticaal): volgt uit lid 2." */
export function keuzeZin(p: Pick<OpenPunt, "keuze" | "inhoud">): string {
  const k = p.keuze;
  if (!k) return "";
  const lezing = k.gekozen ? `Lezing ${k.gekozen}${k.methode ? ` (${METHODE_LABEL[k.methode].toLowerCase()})` : ""}` : "";
  return [lezing, k.motivering.trim()].filter(Boolean).join(": ");
}

/** De open punten als Markdown-lijst, voor de export van een regel: kopieertekst, geen tabel. */
export function puntenAlsMarkdown(punten: OpenPunt[]): string {
  if (!punten.length) return "";
  return ["**Open punten**", "", ...punten.flatMap((p) => {
    const kop = `- ${soortLabel(p)} (${OPEN_PUNT_STATUS_LABEL[p.status].toLowerCase()}): ${p.inhoud.vraag}`;
    const lezingen = p.inhoud.lezingen.map((l) => `  - Lezing ${l.label}: ${l.omschrijving}`);
    const keuze = p.keuze ? [`  - Gekozen: ${keuzeZin(p)}`] : [];
    const toets = p.inhoud.te_toetsen.filter((t) => !t.getoetst).map((t) =>
      `  - Nog te toetsen: ${BRONSOORT_LABEL[t.bronsoort].toLowerCase()}${t.omschrijving ? ` (${t.omschrijving})` : ""}`);
    return [kop, ...lezingen, ...keuze, ...toets];
  }), ""].join("\n");
}
