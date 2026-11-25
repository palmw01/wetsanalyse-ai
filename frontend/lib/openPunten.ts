// Open punten (L-X-1, lessenbundel 4; ADR-018 §6 en besluit 7.13): wat een analyse niet stil mag beslissen. De vorm komt
// uit de api (`api/app/open_punt_contracts.py`); hier staan de namen, wat bij een regel en een geval hoort, en het besluit.
// Het besluit is van de jurist en gaat via één route (`…/open-punten/{id}/besluit`), op de regelkaart én, later, vanuit
// de keuzekaart in het gesprek.

export type OpenPuntSoort = "interpretatiekeuze" | "ontbrekend_uitvoeringsbeleid" | "onderzoekspunt" | "gat_in_de_annotatie";
export type OpenPuntStatus = "open" | "gesignaleerd" | "gekozen" | "getoetst";
/** Wat een besluit is: een keuze, of (alleen bij ontbrekend uitvoeringsbeleid) de vaststelling dat het beleid ontbreekt. */
export type Uitkomst = "gekozen" | "gesignaleerd";
export type Methode = "grammaticaal" | "systematisch" | "wetshistorisch" | "teleologisch";
export type Bronsoort = "wettekst" | "wetsgeschiedenis" | "jurisprudentie" | "beleid" | "kennisgroepstandpunt"
  | "uitvoeringspraktijk" | "literatuur";

export interface Aanhaking { soort: "regel" | "geval" | "markering" | "begrip" | "deelvraag" | "werkgebied"; id: string; geval: string; bestaat?: boolean }
export interface Grondslag { soort: "markering" | "bron" | "begrip" | "stuk"; id: string; label: string }
export interface Lezing { label: string; omschrijving: string; grondslag: Grondslag[] }
export interface TeToetsen { bronsoort: Bronsoort; omschrijving: string; getoetst: boolean; uitkomst: string }
export interface Keuze {
  gekozen: string; motivering: string; methode: Methode | null; door: string; op: string | null; uitkomst?: Uitkomst;
  /** Bij een gesignaleerd punt: aan wie (B9). */
  geadresseerde?: Geadresseerde;
}

/** Aan wie een gesignaleerd punt gaat (B9): de beleidsverantwoordelijken of de wetgever. */
export type Geadresseerde = "beleid" | "wetgever";
export const GEADRESSEERDE_LABEL: Record<Geadresseerde, string> = { beleid: "het beleid", wetgever: "de wetgever" };

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
  herkomst: "lex" | "jurist" | "import" | "regelspecialist";
}

/** De standen die het accorderen van een regel tegenhouden (api `regel_store.BLOKKERENDE_STANDEN`): elk punt dat nog
 *  open staat, van elke soort, ook een onderzoekspunt (besluit gebruiker 20 nov 2026, "Ja, blokkeren"). */
export const BLOKKERENDE_STANDEN: readonly OpenPuntStatus[] = ["open"];

export const OPEN_PUNT_STATUS_LABEL: Record<OpenPuntStatus, string> = {
  open: "Open", gesignaleerd: "Gesignaleerd", gekozen: "Gekozen", getoetst: "Getoetst",
};

/** De soorten in de volgorde van de skill, met een naam voor een keuzelijst. */
export const SOORT_KEUZES: { waarde: OpenPuntSoort; label: string }[] = [
  { waarde: "interpretatiekeuze", label: "Interpretatiekeuze" },
  { waarde: "ontbrekend_uitvoeringsbeleid", label: "Ontbrekend uitvoeringsbeleid" },
  { waarde: "onderzoekspunt", label: "Onderzoekspunt" },
  { waarde: "gat_in_de_annotatie", label: "Gat in de annotatie" },
];

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

/** Houdt dit punt het accorderen tegen? Elk punt dat nog open staat (ADR-018 besluit 2, aangevuld 20 nov 2026). */
export function blokkeert(p: Pick<OpenPunt, "soort" | "status">): boolean {
  return BLOKKERENDE_STANDEN.includes(p.status);
}

/** De punten bij één geval van een regel; met `geval` leeg de punten op de regel zelf. */
export function puntenBij(punten: OpenPunt[], regelId: string, geval = ""): OpenPunt[] {
  return punten.filter((p) => p.inhoud.hangt_aan.some((a) =>
    geval ? a.soort === "geval" && a.id === regelId && a.geval === geval : a.soort === "regel" && a.id === regelId));
}

/** Eerst wat open is en tegenhoudt, dan de andere open punten, dan wat gesignaleerd, gekozen of getoetst is. */
export function ordenPunten(punten: OpenPunt[]): OpenPunt[] {
  const rang = (p: OpenPunt) => (blokkeert(p) ? 0 : p.status === "gesignaleerd" ? 1 : 2);
  return [...punten].sort((a, b) => rang(a) - rang(b));
}

export interface BesluitInvoer {
  gekozen: string; motivering: string; methode: Methode | null; uitkomst?: Uitkomst | null; geadresseerde?: Geadresseerde | "";
}

/** Kan dit besluit weg? Met lezingen: een gekozen lezing; zonder: een motivering (hoe het verder gaat). Een
 *  interpretatiekeuze vraagt ook de methode en een motivering (ADR-018 §6: de keuze en waarom). */
export function besluitFout(p: Pick<OpenPunt, "soort" | "inhoud">, b: BesluitInvoer): string | null {
  const lezingen = p.inhoud.lezingen.map((l) => l.label);
  // B9: een interpretatiekeuze die je signaleert, is een keuze én een signaal aan het beleid of de wetgever.
  if (b.uitkomst === "gesignaleerd" && p.soort === "interpretatiekeuze") {
    if (!b.geadresseerde) return "Zeg aan wie je de keuze signaleert.";
    if (lezingen.length && !lezingen.includes(b.gekozen)) return "Kies een lezing.";
    if (!b.motivering.trim()) return "Zeg wat je signaleert.";
    return b.methode ? null : "Kies de methode van de interpretatie.";
  }
  // Bij ontbrekend beleid zegt het besluit of het beleid er is (api: `uitkomst`); "het ontbreekt" is geen keuze.
  if (b.uitkomst === "gesignaleerd") return b.motivering.trim() ? null : "Zeg welk beleid ontbreekt.";
  if (p.soort === "ontbrekend_uitvoeringsbeleid" && !b.uitkomst && !(lezingen.length && b.gekozen)) {
    return "Zeg of het beleid gevonden is of ontbreekt.";
  }
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
  if (k.uitkomst === "gesignaleerd" && (k.gekozen || k.geadresseerde === "wetgever")) {
    const aan = `gesignaleerd aan ${GEADRESSEERDE_LABEL[k.geadresseerde ?? "beleid"]}`;
    return [[lezing, k.motivering.trim()].filter(Boolean).join(": "), aan].filter(Boolean).join(" · ");
  }
  if (k.uitkomst === "gesignaleerd") return ["Het beleid ontbreekt", k.motivering.trim()].filter(Boolean).join(": ");
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

export interface OpenPuntNieuw { soort: OpenPuntSoort; vraag: string; toelichting: string; geval: string; lezingen: string[] }

/** Kan dit punt worden vastgelegd? De regels van de api (`OpenPuntInhoud`): een vraag, en bij een interpretatiekeuze ten
 *  minste twee lezingen. */
export function nieuwFout(n: OpenPuntNieuw): string | null {
  if (!n.vraag.trim()) return "Zeg wat er open is.";
  if (n.soort === "interpretatiekeuze" && n.lezingen.filter((l) => l.trim()).length < 2) {
    return "Een interpretatiekeuze heeft ten minste twee lezingen.";
  }
  return null;
}

/** Waar het punt aan hangt: de regel, of één geval ervan. */
export function aanhaking(regelId: string, geval: string): Aanhaking[] {
  return [geval ? { soort: "geval", id: regelId, geval } : { soort: "regel", id: regelId, geval: "" }];
}

/** De inhoud voor `POST …/open-punten`: lezingen krijgen de labels A, B, … in hun volgorde. */
export function nieuwePuntInhoud(regelId: string, n: OpenPuntNieuw) {
  const lezingen = n.lezingen.map((l) => l.trim()).filter(Boolean)
    .map((omschrijving, i) => ({ label: String.fromCharCode(65 + i), omschrijving, grondslag: [] }));
  return { soort: n.soort, vraag: n.vraag.trim(), toelichting: n.toelichting.trim(), hangt_aan: aanhaking(regelId, n.geval),
    lezingen, te_toetsen: [] };
}
