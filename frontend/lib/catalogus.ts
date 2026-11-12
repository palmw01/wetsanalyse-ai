// De catalogus van Lex (ADR-014): wat Lex kan, op één plek. De spiegel van `bronmodel/catalogus.py`; graph-qa leidt
// hem af uit zijn registers (`GET /v1/catalogus`). Alleen lezen: een onderdeel toevoegen of wijzigen gaat via de repo
// (en later via een voorstel dat een concept-PR wordt). `catalogus.test.ts` toetst de soorten tegen de Python-bron.

export const SOORTEN = ["methode", "rol", "regelset", "tool", "connector", "sjabloon", "workflow", "agentprofiel", "agent",
  "route", "controle"] as const;
export type Soort = (typeof SOORTEN)[number];
export type Model = "geen" | "strict" | "agent";
/** Het concept uit Claude Code (ADR-014 §7): skill, tool, workflow, agent, ingang of hook. */
export const CONCEPTEN = ["skill", "tool", "workflow", "agent", "ingang", "hook"] as const;
export type Concept = (typeof CONCEPTEN)[number];

export interface Herkomst {
  bron: string;
  licentie: string;
  letterlijk: boolean;
  verwijzing: string[];
}

export interface Stap {
  naam: string;
  model: Model;
  onderdeel: string | null;
  rol?: string | null;
}

export interface Onderdeel {
  id: string;
  soort: Soort;
  label: string;
  doel: string;
  model: Model;
  herkomst: Herkomst;
  bestand: string[];
  versie: string;
  ingang: string[];
  context: string;
  tools: string[];
  uitvoer: string;
  twijfel: string;
  tests: string[];
  hangt_af_van: string[];
  straat: string | null;
  bewerkbaar: string[];
  laag: string | null;
  stappen: Stap[];
  concept: Concept;
  deel_van: string | null;
  /** Biedt deze omgeving het aan (de straatvlag); zonder vlag altijd waar. */
  aan: boolean;
}

export interface OnderdeelDetail extends Onderdeel {
  inhoud: Record<string, unknown>;
  gebruikt_door: string[];
}

export interface Catalogus {
  soorten: Soort[];
  onderdelen: Onderdeel[];
}

/** Hoe de werkplek een soort noemt, enkelvoud en meervoud. */
export const SOORT_LABEL: Record<Soort, { een: string; meer: string; uitleg: string }> = {
  methode: { een: "Methode", meer: "Methoden", uitleg: "De methode die Lex volgt, uit een skill." },
  rol: { een: "Methoderol", meer: "Methoderollen", uitleg: "Welke methodetekst een modelaanroep meekrijgt." },
  agentprofiel: { een: "Agentprofiel", meer: "Agentprofielen", uitleg: "Een agent die een soort vraag beantwoordt, met eigen instructie en tools." },
  agent: { een: "Agent", meer: "Agents", uitleg: "Een taak op een werkgebied; levert altijd een voorstel." },
  workflow: { een: "Workflow", meer: "Workflows", uitleg: "Een vaste keten van stappen." },
  route: { een: "Route", meer: "Routes", uitleg: "Een vaste weg voor een herkenbare vraag." },
  connector: { een: "Bron", meer: "Bronnen naast de wet", uitleg: "Een bron buiten de kennisgraaf." },
  sjabloon: { een: "Antwoordsjabloon", meer: "Antwoordsjablonen", uitleg: "De vaste vorm van een antwoord." },
  regelset: { een: "Regelset", meer: "Regelsets", uitleg: "Vaste regels zonder model, met hun eigen tests." },
  tool: { een: "Handeling", meer: "Handelingen", uitleg: "Eén getypte handeling op de kennisgraaf of een bron." },
  controle: { een: "Controle", meer: "Controles", uitleg: "Een vaste controle op een vast moment, niet door het model uit te zetten." },
};

/** De concepten in de taal van de jurist (ADR-014 §7), met wat ze zijn. De volgorde is die van de pagina. */
export const CONCEPT_LABEL: Record<Concept, { kop: string; uitleg: string }> = {
  skill: { kop: "Kennis en methode", uitleg: "Wat Lex weet en volgt: de methode, de tekst per rol en de vaste regels. Voert zelf niets uit." },
  workflow: { kop: "Vaste ketens", uitleg: "Stappen in een vaste volgorde; een model alleen in één afgebakende stap." },
  agent: { kop: "Agents", uitleg: "Zoeken en formuleren met een model, met eigen tools en een eigen opdracht." },
  tool: { kop: "Handelingen", uitleg: "Eén afgebakende handeling op de kennisgraaf of een bron, met een vaste vorm van het resultaat." },
  ingang: { kop: "Ingangen", uitleg: "Herkent een vraag en kiest zonder model de keten of agent die hem beantwoordt." },
  hook: { kop: "Controles", uitleg: "Vaste controles op een vast moment; het model kan ze niet overslaan." },
};
export const CONCEPT_VOLGORDE: Concept[] = ["skill", "workflow", "agent", "tool", "ingang", "hook"];

/** Of er een model aan te pas komt, in gewone woorden. Kleur draagt hier geen oordeel: lintblauw zegt wat het is. */
export const MODEL_LABEL: Record<Model, { tekst: string; uitleg: string }> = {
  geen: { tekst: "Zonder model", uitleg: "Alleen vaste regels en code: dezelfde invoer geeft dezelfde uitkomst." },
  strict: { tekst: "Model in één stap", uitleg: "Het model kiest of formuleert in één afgebakende stap; de code controleert." },
  agent: { tekst: "Model met tools", uitleg: "Het model zoekt zelf met tools; de controle achteraf toetst elk citaat." },
};

export function soortVan(id: string): Soort | null {
  const s = id.split("/", 1)[0];
  return (SOORTEN as readonly string[]).includes(s) ? (s as Soort) : null;
}

export function naamVan(id: string): string {
  return id.slice(id.indexOf("/") + 1);
}

/** Het pad van de pagina van een onderdeel. */
export function onderdeelPad(id: string): string {
  const s = soortVan(id);
  return s ? `/werkwijze/${s}/${encodeURIComponent(naamVan(id))}` : "/werkwijze";
}

/** Zoeken op label, doel en id; hoofdletterongevoelig, alle woorden moeten passen. */
export function filterOnderdelen(lijst: Onderdeel[], { soort = "", concept = "", zoek }:
  { soort?: Soort | ""; concept?: Concept | ""; zoek: string }): Onderdeel[] {
  const woorden = zoek.toLowerCase().split(/\s+/).filter(Boolean);
  return lijst.filter((o) => (!soort || o.soort === soort) && (!concept || o.concept === concept)
    && woorden.every((w) => `${o.label} ${o.doel} ${o.id}`.toLowerCase().includes(w)));
}

/** De onderdelen per concept, in de volgorde van de pagina; binnen een concept op soort (de volgorde van `SOORTEN`). */
export function perConcept(lijst: Onderdeel[]): { concept: Concept; onderdelen: Onderdeel[] }[] {
  const rang = (o: Onderdeel) => SOORTEN.indexOf(o.soort);
  return CONCEPT_VOLGORDE.map((concept) => ({ concept, onderdelen: lijst.filter((o) => o.concept === concept)
    .sort((a, b) => rang(a) - rang(b)) })).filter((g) => g.onderdelen.length > 0);
}

/** De onderdelen per soort, in de volgorde van `SOORTEN`; een soort zonder onderdelen valt weg. */
export function perSoort(lijst: Onderdeel[]): { soort: Soort; onderdelen: Onderdeel[] }[] {
  return SOORTEN.map((soort) => ({ soort, onderdelen: lijst.filter((o) => o.soort === soort) }))
    .filter((g) => g.onderdelen.length > 0);
}

export function telling(lijst: Onderdeel[]): Record<Soort, number> {
  const uit = Object.fromEntries(SOORTEN.map((s) => [s, 0])) as Record<Soort, number>;
  for (const o of lijst) uit[o.soort] += 1;
  return uit;
}

function isOnderdeel(x: unknown): x is Onderdeel {
  const o = x as Onderdeel;
  return !!o && typeof o.id === "string" && soortVan(o.id) === o.soort && typeof o.label === "string"
    && (CONCEPTEN as readonly string[]).includes(o.concept)
    && typeof o.doel === "string" && ["geen", "strict", "agent"].includes(o.model) && Array.isArray(o.hangt_af_van);
}

/** Streng: een onbekende soort of een rij zonder de vaste velden valt weg, zodat de pagina nooit half tekent. */
export function parseCatalogus(x: unknown): Catalogus | null {
  const c = x as Catalogus;
  if (!c || !Array.isArray(c.onderdelen)) return null;
  return { soorten: [...SOORTEN], onderdelen: c.onderdelen.filter(isOnderdeel) };
}

export function parseOnderdeel(x: unknown): OnderdeelDetail | null {
  const o = x as OnderdeelDetail;
  if (!isOnderdeel(o)) return null;
  return { ...o, inhoud: o.inhoud && typeof o.inhoud === "object" ? o.inhoud : {},
    gebruikt_door: Array.isArray(o.gebruikt_door) ? o.gebruikt_door : [] };
}
