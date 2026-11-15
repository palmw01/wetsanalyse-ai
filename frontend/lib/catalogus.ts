// De catalogus van Lex (ADR-014): wat Lex kan, op één plek. De spiegel van `bronmodel/catalogus.py`; graph-qa leidt
// hem af uit zijn registers (`GET /v1/catalogus`). Alleen lezen: een onderdeel toevoegen of wijzigen gaat via de repo.
// `catalogus.test.ts` toetst de soorten tegen de Python-bron.

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
  /** De hash van de bronbestanden in het image (een skill of een agentprofiel), anders leeg. Een versie in de
   *  werkplaats met dezelfde hash is actief (ADR-016 §B1). */
  bronhash?: string;
  /** Van welke methode dit onderdeel is: de naam van een methode-skill, of "neutraal" (plan methodes scheiden). */
  methode?: string;
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

/** Een onderdeel dat van geen methode is (`bronmodel.catalogus.NEUTRAAL`). */
export const NEUTRAAL = "neutraal";

/** Hoe de werkplek de methode van een onderdeel noemt. De naam komt uit de skill; een onbekende naam blijft staan. */
export function methodeLabel(methode: string | undefined): string {
  if (!methode) return "";
  if (methode === NEUTRAAL) return "Geen: voor elke methode";
  return methode.charAt(0).toUpperCase() + methode.slice(1);
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

export function soortVan(id: string): Soort | null {
  const s = id.split("/", 1)[0];
  return (SOORTEN as readonly string[]).includes(s) ? (s as Soort) : null;
}

export function naamVan(id: string): string {
  return id.slice(id.indexOf("/") + 1);
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
