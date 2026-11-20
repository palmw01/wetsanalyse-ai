// Afleidingsregels (activiteit 3b, ADR-018): de vorm uit de api (`api/app/regel_contracts.py`, `regel_store._regel`),
// de namen die overal gelijk zijn, en de export. De regeltekst maakt de api (`regeltekst.py`): de frontend typt hem
// nooit na, zodat kaart, paneel en export dezelfde tekst tonen.

/** Dezelfde tonen als `StatusLabel` (`components/ui/Lijst`); `lib/` importeert geen componenten. */
type StatusToon = "groen" | "geel" | "rood" | "neutraal";

export type RegelStatus = "concept" | "geaccordeerd" | "geaccordeerd_als_beleidsregel" | "afgewezen" | "vervangen";
export type RegelSoort = "rekenregel" | "beslisregel" | "specialisatie";
export type DragerRol = "grondslag" | "voorwaarde" | "invoer" | "uitvoer" | "tijd" | "context";
export type DragerBeoordeling = "open" | "akkoord" | "afgewezen";
export type VoorbeeldOordeel = "open" | "juist" | "onjuist" | "kan_niet";

export interface Term { soort: "begrip" | "operator" | "tekst"; begrip_id?: string; tekst?: string }
export interface Voorwaarde { tekst: string; element_ids?: string[]; niet?: boolean }
export interface Voorwaarden { verband: "alle" | "een_van"; delen: (Voorwaarden | Voorwaarde)[] }
export interface Geval { label: string; voorwaarden: Voorwaarden | null; uitkomst: Term[]; voorrang: number }
/** Een voorbeeld. Het oordeel, de maker en de beoordelaar zet de api: een nieuw voorbeeld is open, en een oordeel gaat via
 *  `beoordeelVoorbeeld` (maken en beoordelen zijn twee handelingen, e2e-run 20 nov 2026). */
export interface RegelVoorbeeld {
  geval: string; invoer: string; uitkomst: string; oordeel: VoorbeeldOordeel; toelichting: string;
  door?: string; beoordeeld_door?: string; beoordeeld_op?: string;
}

export interface RegelInhoud {
  soort: RegelSoort;
  regelbegrip_id: string;
  uitvoer_begrip_id: string;
  onderwerp_begrip_id: string;
  invoer: { begrip_id: string; rol: "invoer" | "parameter" }[];
  gevallen: Geval[];
  voorbeelden: RegelVoorbeeld[];
  toelichting: string;
  brontype: "wet" | "beleid";
  lidwoord: "de" | "het" | "";
}

export interface RegelDrager {
  id: string;
  element_id: string;
  rol: DragerRol;
  geval: string;
  bewijs: Record<string, unknown> | null;
  beoordeling: DragerBeoordeling;
  beoordeeld_door: string | null;
  /** De grond van het oordeel; een oudere api stuurt hem niet. */
  motivering?: string;
  /** Van `begrip_store.actualiteit`: is de dragende passage nog dezelfde? */
  actualiteit?: "actueel" | "gewijzigd" | "verworpen" | "verdwenen" | string;
}

export interface Regel {
  id: string;
  werkgebied_id: string;
  status: RegelStatus;
  revisie: number;
  herkomst: "lex" | "jurist" | "import" | "regelspecialist";
  opvolger_van: string | null;
  /** De regel die deze verving (status `vervangen`); een oudere api stuurt het niet. */
  vervangen_door?: string | null;
  inhoud: RegelInhoud;
  /** De naam van het regelbegrip ("bepalen termijnbedrag") en van de uitvoer. */
  naam: string;
  uitvoer: string;
  regeltekst: { tekst: string; markdown: string; gevallen: { label: string; tekst: string }[] };
  begrippen: Record<string, { id: string; naam: string; status: string }>;
  dragers: RegelDrager[];
  accorderen: { mag: boolean; redenen: string[] };
  signalen: string[];
  /** Hoeveel open punten aan de regel of een geval hangen, en hoeveel daarvan nog open zijn (R3). Een oudere api stuurt
   *  het niet. */
  open_punten?: { open: number; totaal: number; bij_voorganger?: number };
  aangemaakt_door: string;
  aangemaakt: string | null;
  gewijzigd: string | null;
  geaccordeerd_door: string | null;
  geaccordeerd_op: string | null;
  geaccordeerd_revisie: number | null;
}

export interface KetenSignaal { soort: "zelfde_uitvoer" | "kring"; regel_ids: string[]; begrip_id?: string; melding: string }
export interface RegelKeten {
  regels: { id: string; naam: string; uitvoer: string; status: RegelStatus; soort: RegelSoort; gevallen: number; brontype: "wet" | "beleid" }[];
  /** Van onder naar boven: een regel staat na alles waarvan hij de uitkomst gebruikt. */
  volgorde: string[];
  pijlen: { van: string; naar: string; begrip_id: string }[];
  basisgegevens: { begrip_id: string; naam: string }[];
  signalen: KetenSignaal[];
}

export interface RegelRevisie {
  revisie: number; actie: string; detail: string | null; status: RegelStatus; actor: string; tijdstip: string | null;
}

export const REGEL_STATUS_LABEL: Record<RegelStatus, string> = {
  concept: "Concept",
  geaccordeerd: "Geaccordeerd",
  geaccordeerd_als_beleidsregel: "Geaccordeerd als beleidsregel",
  afgewezen: "Afgewezen",
  vervangen: "Vervangen",
};

export const REGEL_STATUS_TOON: Record<RegelStatus, StatusToon> = {
  concept: "geel", geaccordeerd: "groen", geaccordeerd_als_beleidsregel: "groen", afgewezen: "rood", vervangen: "neutraal",
};

export const REGEL_SOORT_LABEL: Record<RegelSoort, string> = {
  rekenregel: "Rekenregel", beslisregel: "Beslisregel", specialisatie: "Specialisatie",
};

export const DRAGER_ROL_LABEL: Record<DragerRol, string> = {
  grondslag: "Grondslag", voorwaarde: "Voorwaarde", invoer: "Invoer", uitvoer: "Uitvoer", tijd: "Tijd", context: "Context",
};

export const DRAGER_BEOORDELING_LABEL: Record<DragerBeoordeling, string> = {
  open: "Te beoordelen", akkoord: "Akkoord", afgewezen: "Afgewezen",
};

export const VOORBEELD_OORDEEL_LABEL: Record<VoorbeeldOordeel, string> = {
  open: "Nog niet beoordeeld", juist: "Juridisch juist", onjuist: "Niet juist", kan_niet: "Kan zich niet voordoen",
};

export const HERKOMST_LABEL: Record<Regel["herkomst"], string> = {
  lex: "Voorstel van Lex", jurist: "Opgesteld door de jurist", import: "Geïmporteerd",
  regelspecialist: "Opgesteld door de regelspecialist",
};

/** Het nummer van een voorbeeld voor de api (`…/voorbeelden/{nr}/oordeel`): de plek in de lijst, vanaf 1. */
export function voorbeeldNr(r: Pick<Regel, "inhoud">, v: RegelVoorbeeld): number {
  return r.inhoud.voorbeelden.indexOf(v) + 1;
}

/** De labels van de gevallen, voor een keuzelijst ("" = de hele regel). */
export function gevalLabels(r: Pick<Regel, "inhoud">): string[] {
  return r.inhoud.gevallen.map((g) => g.label).filter(Boolean);
}

/** Is de regel nog te beoordelen (niet afgewezen of vervangen, niet geaccordeerd)? */
export function isOpen(r: Pick<Regel, "status">): boolean {
  return r.status === "concept";
}

export function isGeaccordeerd(r: Pick<Regel, "status">): boolean {
  return r.status === "geaccordeerd" || r.status === "geaccordeerd_als_beleidsregel";
}

/** De naam van een begrip zoals de regel hem kent, of het id als het begrip er (nog) niet is. */
export function begripNaam(r: Pick<Regel, "begrippen">, id: string): string {
  return r.begrippen[id]?.naam || id;
}

/** De invoer van een regel, gesplitst: begrippen en parameters (een vaste waarde met een eigen begrip). */
export function invoerVan(r: Pick<Regel, "inhoud" | "begrippen">): { invoer: string[]; parameters: string[] } {
  const naam = (id: string) => begripNaam(r, id);
  return {
    invoer: r.inhoud.invoer.filter((i) => i.rol !== "parameter").map((i) => naam(i.begrip_id)),
    parameters: r.inhoud.invoer.filter((i) => i.rol === "parameter").map((i) => naam(i.begrip_id)),
  };
}

/** De voorbeelden van één geval (leeg label bij een regel met één geval). */
export function voorbeeldenBij(r: Pick<Regel, "inhoud">, geval: string): RegelVoorbeeld[] {
  const enkel = r.inhoud.gevallen.length === 1;
  return r.inhoud.voorbeelden.filter((v) => enkel || (v.geval || "") === geval);
}

/** De regels die een begrip afleiden (de uitvoer) en die het gebruiken (invoer of in een uitkomst), voor de begripskaart
 *  (U4). Afgewezen en vervangen regels tellen niet mee. */
export function regelsBijBegrip(regels: Regel[], begripId: string): { afgeleidDoor: Regel[]; gebruiktIn: Regel[] } {
  const actief = regels.filter((r) => r.status !== "afgewezen" && r.status !== "vervangen");
  return {
    afgeleidDoor: actief.filter((r) => r.inhoud.uitvoer_begrip_id === begripId),
    gebruiktIn: actief.filter((r) => r.inhoud.uitvoer_begrip_id !== begripId && (
      r.inhoud.invoer.some((i) => i.begrip_id === begripId)
      || r.inhoud.gevallen.some((g) => g.uitkomst.some((t) => t.begrip_id === begripId)))),
  };
}

/** De regels in de volgorde van de keten (van onder naar boven); wat de keten niet kent (afgewezen, vervangen) achteraan. */
export function inKetenVolgorde<T extends { id: string }>(regels: T[], keten: Pick<RegelKeten, "volgorde"> | null): T[] {
  if (!keten) return regels;
  const plek = new Map(keten.volgorde.map((id, i) => [id, i]));
  return [...regels].sort((a, b) => (plek.get(a.id) ?? 1e6) - (plek.get(b.id) ?? 1e6));
}

/** Waar een regel op volgt en wat erop volgt, uit de pijlen van de keten. */
export function buren(keten: RegelKeten, regelId: string): { volgtOp: string[]; leidtTot: string[] } {
  return {
    volgtOp: [...new Set(keten.pijlen.filter((p) => p.naar === regelId).map((p) => p.van))],
    leidtTot: [...new Set(keten.pijlen.filter((p) => p.van === regelId).map((p) => p.naar))],
  };
}

/** Eén regel als Markdown: kopieertekst, dus lijsten en geen tabellen. De regeltekst is die van de api. */
export function regelAlsMarkdown(r: Regel): string {
  const { invoer, parameters } = invoerVan(r);
  const regels: string[] = [
    `# ${r.naam || "Afleidingsregel"}`, "",
    `${REGEL_SOORT_LABEL[r.inhoud.soort]} · ${REGEL_STATUS_LABEL[r.status]}${r.inhoud.brontype === "beleid" ? " · beleidsregel" : ""}`, "",
    "**Regel**", "", r.regeltekst.markdown, "",
  ];
  if (invoer.length || parameters.length) {
    regels.push("**Invoer**", "", ...invoer.map((n) => `- ${n}`), ...parameters.map((n) => `- ${n} (parameter)`), "");
  }
  const grondslag = r.dragers.filter((d) => d.rol === "grondslag" && d.beoordeling !== "afgewezen");
  if (grondslag.length) {
    regels.push("**Grondslag**", "", ...grondslag.map((d) => `- ${d.element_id} (${DRAGER_BEOORDELING_LABEL[d.beoordeling].toLowerCase()})`), "");
  }
  if (r.inhoud.voorbeelden.length) {
    regels.push("**Voorbeelden**", "", ...r.inhoud.voorbeelden.map((v) =>
      `- ${v.geval ? `Geval ${v.geval}: ` : ""}${v.invoer} → ${v.uitkomst} (${VOORBEELD_OORDEEL_LABEL[v.oordeel].toLowerCase()})`), "");
  }
  if (r.inhoud.toelichting.trim()) regels.push("**Toelichting**", "", r.inhoud.toelichting.trim(), "");
  return regels.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

/** Alle regels van een werkgebied in de volgorde van de keten, met de basisgegevens en de signalen. */
export function regelsAlsMarkdown(regels: Regel[], keten: RegelKeten | null, naam = ""): string {
  const delen = [`# Afleidingsregels${naam ? ` – ${naam}` : ""}`, ""];
  if (keten?.basisgegevens.length) {
    delen.push("**Basisgegevens** (invoer die geen regel afleidt)", "", ...keten.basisgegevens.map((b) => `- ${b.naam || b.begrip_id}`), "");
  }
  if (keten?.signalen.length) delen.push("**Signalen**", "", ...keten.signalen.map((s) => `- ${s.melding}`), "");
  delen.push(...inKetenVolgorde(regels, keten).map((r) => regelAlsMarkdown(r).replace(/^# /, "## ")));
  return delen.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}
