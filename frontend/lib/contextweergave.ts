/** Het rekenwerk van de contextweergave (plan contextweergave, ADR-015): wat `/context` in Claude Code laat zien, voor Lex.
 *
 *  Twee getallen die niet hetzelfde zijn, elk met een eigen naam:
 *  - **context**: hoe het laatste verzoek van een agent was opgebouwd, en hoeveel van het venster het vult;
 *  - **verbruik**: wat de hele beurt kostte, over alle modelaanroepen en alle agents.
 *
 *  Alles hier is puur en leest de `contextopbouw` die graph-qa uitrekende (`tools/graph-qa/agent/contextopbouw.py`,
 *  contract `api/app/gesprek_contracts.Contextopbouw`). De werkplek telt zelf niets: het totaal en de cachecijfers zijn
 *  exact, een categorie is een schatting. Geen veld heet `token`. */
import { CONTEXTDELEN, contextdeel, type Contextdeel } from "./contextdelen";
import type { Bericht } from "./types";

export interface Cache { lees: number; schrijf: number; nieuw: number }
export interface Deel { categorie: string; omvang: number }
export interface ContextAgent {
  rol: string;
  model: string;
  venster: number;
  /** Het profiel waarmee deze agent is opgebouwd (ADR-016), of leeg: de vaste agents van nu hebben er geen. */
  profiel_id: string;
  profiel_versie: string;
  laatste: { delen: Deel[]; totaal: number; voorvoegsel: { omvang: number; exact: boolean }; cache: Cache };
  begin: { totaal: number; cache: Cache; tools_hash: string; system_hash: string };
  historiegrens: number | null;
  venster_beurten: { in_venster: number; gekrompen: number; weggevallen: number } | null;
}
export interface Verbruik { invoer: number; cache_lees: number; cache_schrijf: number; uitvoer: number }
export interface RolVerbruik extends Verbruik { rol: string; model: string; aanroepen: number; duur: number }
export interface Aanroep {
  rol: string; totaal: number; cache_lees: number; cache_schrijf: number; invoer: number; uitvoer: number; ms: number;
  tools_hash: string; system_hash: string;
}
export interface Contextopbouw {
  versie: number;
  run_id: string;
  ouder_run_id: string;
  profiel_id: string;
  profiel_versie: string;
  agenten: ContextAgent[];
  verbruik: RolVerbruik[];
  som: Verbruik;
  aanroepen: Aanroep[];
}

/** Eén beurt met een meting, in de volgorde van het gesprek. */
export interface Beurt { run_id: string; contextopbouw: Contextopbouw }

/** De boom bij het lezen (`GET /api/gesprekken/{id}/contextopbouw`): de deelgesprekken met hun beurten. */
export interface KindContext { gesprek_id: string; titel: string; updated?: string | null; berichten: { run_id: string; contextopbouw: unknown }[] }
export interface ContextBoom { gesprek_id: string; kinderen: KindContext[] }

// ── Lezen ────────────────────────────────────────────────────────────────────────────────────────────────────────────

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const getal = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.round(v) : 0);
const tekst = (v: unknown): string => (typeof v === "string" ? v : "");
const rijen = (v: unknown): Record<string, unknown>[] => (Array.isArray(v) ? v.filter(isObject) : []);

function cache(v: unknown): Cache {
  const c = isObject(v) ? v : {};
  return { lees: getal(c.lees), schrijf: getal(c.schrijf), nieuw: getal(c.nieuw) };
}

function verbruik(v: unknown): Verbruik {
  const s = isObject(v) ? v : {};
  return { invoer: getal(s.invoer), cache_lees: getal(s.cache_lees), cache_schrijf: getal(s.cache_schrijf), uitvoer: getal(s.uitvoer) };
}

function agent(v: Record<string, unknown>): ContextAgent | undefined {
  const laatste = isObject(v.laatste) ? v.laatste : undefined;
  if (!laatste) return undefined;
  const begin = isObject(v.begin) ? v.begin : {};
  const voor = isObject(laatste.voorvoegsel) ? laatste.voorvoegsel : {};
  const beurten = isObject(v.venster_beurten) ? v.venster_beurten : undefined;
  return {
    rol: tekst(v.rol), model: tekst(v.model), venster: getal(v.venster),
    profiel_id: tekst(v.profiel_id), profiel_versie: tekst(v.profiel_versie),
    laatste: {
      delen: rijen(laatste.delen).map((d) => ({ categorie: tekst(d.categorie), omvang: getal(d.omvang) })).filter((d) => d.categorie),
      totaal: getal(laatste.totaal), voorvoegsel: { omvang: getal(voor.omvang), exact: voor.exact === true }, cache: cache(laatste.cache),
    },
    begin: { totaal: getal(begin.totaal), cache: cache(begin.cache), tools_hash: tekst(begin.tools_hash), system_hash: tekst(begin.system_hash) },
    historiegrens: getal(v.historiegrens) || null,
    venster_beurten: beurten
      ? { in_venster: getal(beurten.in_venster), gekrompen: getal(beurten.gekrompen), weggevallen: getal(beurten.weggevallen) } : null,
  };
}

/** De contextopbouw van een bericht of een `meting`-event. Een vorm die niet past (geen versie, geen object) is
 *  `undefined`: het bericht is dan "nog niet gemeten", nooit een fout. Onbekende velden vallen weg. */
export function parseContextopbouw(v: unknown): Contextopbouw | undefined {
  if (!isObject(v) || !getal(v.versie)) return undefined;
  return {
    versie: getal(v.versie), run_id: tekst(v.run_id), ouder_run_id: tekst(v.ouder_run_id),
    profiel_id: tekst(v.profiel_id), profiel_versie: tekst(v.profiel_versie),
    agenten: rijen(v.agenten).map(agent).filter((a): a is ContextAgent => !!a),
    verbruik: rijen(v.verbruik).map((r) => ({ ...verbruik(r), rol: tekst(r.rol), model: tekst(r.model), aanroepen: getal(r.aanroepen), duur: getal(r.duur) })),
    som: verbruik(v.som),
    aanroepen: rijen(v.aanroepen).map((a) => ({ rol: tekst(a.rol), totaal: getal(a.totaal), cache_lees: getal(a.cache_lees),
      cache_schrijf: getal(a.cache_schrijf), invoer: getal(a.invoer), uitvoer: getal(a.uitvoer), ms: getal(a.ms),
      tools_hash: tekst(a.tools_hash), system_hash: tekst(a.system_hash) })),
  };
}

/** De beurten met een meting uit de berichten van een gesprek, in volgorde. Oudere berichten en beurten zonder model
 *  hebben er geen. */
export function beurtenUitBerichten(berichten: Pick<Bericht, "rol" | "run_id" | "contextopbouw">[]): Beurt[] {
  const uit: Beurt[] = [];
  for (const b of berichten) {
    const c = b.rol === "assistant" ? parseContextopbouw(b.contextopbouw) : undefined;
    if (c) uit.push({ run_id: c.run_id || b.run_id || "", contextopbouw: c });
  }
  return uit;
}

/** Een nieuwe meting in de lijst: dezelfde run vervangt zijn eerdere stand (opnieuw aanhaken speelt de stroom opnieuw
 *  af), een nieuwe komt achteraan. */
export function metBeurt(beurten: Beurt[], nieuw: Contextopbouw): Beurt[] {
  const beurt = { run_id: nieuw.run_id, contextopbouw: nieuw };
  const i = nieuw.run_id ? beurten.findIndex((b) => b.run_id === nieuw.run_id) : -1;
  return i === -1 ? [...beurten, beurt] : beurten.map((b, j) => (j === i ? beurt : b));
}

// ── Getallen in woorden ──────────────────────────────────────────────────────────────────────────────────────────────

const NL = (n: number, decimalen: number) => n.toLocaleString("nl-NL", { minimumFractionDigits: 0, maximumFractionDigits: decimalen });

/** `36k`, `1,2k`, `980`, `1,3M`: kort genoeg voor de meter, met de Nederlandse komma. */
export function kort(n: number): string {
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) return `${NL(n / 1000, n < 10_000 ? 1 : 0)}k`;
  return `${NL(n / 1_000_000, 1)}M`;
}

/** Een aandeel als percentage: `3,6%`, onder de tien met één decimaal, en nooit `0%` voor iets wat er wel is. */
export function procent(deel: number, geheel: number): string {
  if (geheel <= 0 || deel <= 0) return "0%";
  const p = (deel / geheel) * 100;
  if (p < 0.1) return "< 0,1%";
  return `${NL(p, p < 10 ? 1 : 0)}%`;
}

/** Wat een beurt in totaal kostte: alles wat het model las en schreef, zoals het budget het telt. */
export function totaalVerbruik(v: Verbruik): number {
  return v.invoer + v.cache_lees + v.cache_schrijf + v.uitvoer;
}

/** De agent waarvan de context getoond wordt als er één regel is (de meter): die met het grootste laatste verzoek. */
export function hoofdagent(c: Contextopbouw | undefined): ContextAgent | undefined {
  return c?.agenten.reduce<ContextAgent | undefined>((beste, a) => (!beste || a.laatste.totaal > beste.laatste.totaal ? a : beste), undefined);
}

/** Het profiel van een agent als tekst ("bronnenzoeker, versie 3"), of leeg als hij er geen heeft. */
export function profielTekst(a: Pick<ContextAgent, "profiel_id" | "profiel_versie">): string {
  if (!a.profiel_id) return "";
  return a.profiel_versie ? `${a.profiel_id}, versie ${a.profiel_versie}` : a.profiel_id;
}

/** De regel bij het raster en op de meter: `31k · 3,1%` (van het venster). */
export function contextRegel(a: ContextAgent): string {
  return a.venster > 0 ? `${kort(a.laatste.totaal)} · ${procent(a.laatste.totaal, a.venster)}` : kort(a.laatste.totaal);
}

// ── Het raster en de legenda ─────────────────────────────────────────────────────────────────────────────────────────

/** Hoeveel vakjes het raster heeft: 100% = het verzoek, één vakje = één procent. */
export const VAKJES = 100;

/** Verdeel `totaal` vakjes over de gewichten met de grootste-rest-methode: de som is precies `totaal`, en dezelfde
 *  invoer geeft dezelfde uitkomst (bij gelijke rest wint de volgorde). */
export function grootsteRest(gewichten: number[], totaal: number): number[] {
  const som = gewichten.reduce((a, b) => a + b, 0);
  if (som <= 0 || totaal <= 0) return gewichten.map(() => 0);
  const uit = gewichten.map((g) => Math.floor((totaal * g) / som));
  const volgorde = gewichten.map((g, i) => [(totaal * g) % som, i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  let over = totaal - uit.reduce((a, b) => a + b, 0);
  for (const [, i] of volgorde) { if (over-- <= 0) break; uit[i] += 1; }
  return uit;
}

export interface LegendaRegel {
  deel: Contextdeel;
  omvang: number;
  /** Het aandeel in het verzoek, als tekst. */
  aandeel: string;
  /** Een categorie is een schatting naar tekens; het totaal en het vaste deel als geheel zijn exact. */
  geschat: boolean;
  /** Alleen bij de historie: de grens waarboven Lex oudere beurten inkort, in dezelfde eenheid. */
  grens?: number;
}

/** De delen van het laatste verzoek in de volgorde van het register, per categorie opgeteld (een onbekende categorie
 *  telt als *Overig*) en zonder lege regels. */
export function legenda(a: ContextAgent): LegendaRegel[] {
  const per = new Map<string, number>();
  for (const d of a.laatste.delen) {
    const id = contextdeel(d.categorie).id;
    per.set(id, (per.get(id) ?? 0) + d.omvang);
  }
  return CONTEXTDELEN.filter((d) => (per.get(d.id) ?? 0) > 0).map((deel) => {
    const omvang = per.get(deel.id) ?? 0;
    return { deel, omvang, aandeel: procent(omvang, a.laatste.totaal), geschat: true,
      ...(deel.id === "historie" && a.historiegrens ? { grens: a.historiegrens } : {}) };
  });
}

/** Het raster: `VAKJES` vakjes, elk met de categorie die het kleurt, in de volgorde van het register. Een categorie die
 *  er is maar onder een half procent blijft, krijgt geen vakje; de legenda noemt haar wel. */
export function raster(a: ContextAgent, vakjes = VAKJES): Contextdeel[] {
  const regels = legenda(a);
  const aantallen = grootsteRest(regels.map((r) => r.omvang), vakjes);
  return regels.flatMap((r, i) => Array.from({ length: aantallen[i] }, () => r.deel));
}

/** De drie grootste categorieën, voor de tooltip van de meter. */
export function grootste(a: ContextAgent, aantal = 3): LegendaRegel[] {
  return [...legenda(a)].sort((x, y) => y.omvang - x.omvang).slice(0, aantal);
}

// ── Het begin van de beurt, de adviezen en het signaal ───────────────────────────────────────────────────────────────

/** Een begin telt als koud als bijna niets uit de cache kwam: minder dan een twintigste van het eerste verzoek. */
const KOUD_ONDER = 0.05;
/** Vanaf dit deel van de historiegrens is de historie "bijna vol". */
const HISTORIE_VOL = 0.9;
/** Vanaf dit deel van het venster klopt er iets niet: het venster van Lex hoort er nooit bij in de buurt te komen. */
const VENSTER_VOL = 0.8;

export function beginKoud(a: ContextAgent): boolean {
  return a.begin.totaal > 0 && a.begin.cache.lees < a.begin.totaal * KOUD_ONDER;
}

export type AdviesId = "historie_ingekort" | "beurten_weggevallen" | "koud_toolset" | "koud_pauze" | "veel_connectortools" | "venster_vol";
export interface Advies {
  id: AdviesId;
  tekst: string;
  /** Geeft ook het signaal op de meter. */
  signaal: boolean;
}

const omvangVan = (a: ContextAgent, id: string) => a.laatste.delen.filter((d) => d.categorie === id).reduce((n, d) => n + d.omvang, 0);

/** De adviezen bij een beurt: vaste regels, zonder model, over deze en de vorige beurt. De cache is van iedereen met
 *  hetzelfde vaste deel, dus de tekst zegt nooit "jij was een uur stil". */
export function adviezen(nu: Contextopbouw, vorige?: Contextopbouw): Advies[] {
  const a = hoofdagent(nu);
  if (!a) return [];
  const uit: Advies[] = [];
  const beurten = a.venster_beurten;
  const historie = omvangVan(a, "historie");
  if ((a.historiegrens && historie >= a.historiegrens * HISTORIE_VOL) || (beurten?.gekrompen ?? 0) > 0) {
    uit.push({ id: "historie_ingekort", signaal: true,
      tekst: "Oudere beurten worden ingekort tot vraag en antwoord. Met /nieuw begin je een schoon gesprek." });
  }
  if ((beurten?.weggevallen ?? 0) > 0) {
    const n = beurten!.weggevallen;
    uit.push({ id: "beurten_weggevallen", signaal: true,
      tekst: `${n === 1 ? "Eén eerdere beurt zit" : `${n} eerdere beurten zitten`} niet meer in de context. Met /nieuw begin je een schoon gesprek.` });
  }
  if (beginKoud(a)) {
    const vorigeAgent = vorige?.agenten.find((x) => x.rol === a.rol);
    const andereTools = !!vorigeAgent && vorigeAgent.begin.tools_hash !== a.begin.tools_hash;
    // Een andere toolset komt door andere bronnen naast de wet, of doordat Lex de vraag anders indeelde: elk soort vraag
    // heeft zijn eigen tools (meting 12 nov 2026: de wissel van uitleg naar een algemene vraag schreef het vaste deel
    // opnieuw, met dezelfde bronnen aan).
    const andereBronnen = !!vorigeAgent && omvangVan(vorigeAgent, "connectortools") !== omvangVan(a, "connectortools");
    uit.push(andereTools
      ? { id: "koud_toolset", signaal: true,
          tekst: andereBronnen
            ? "De bronnen naast de wet wisselden, dus het vaste deel is opnieuw geschreven. Dat kost één keer extra."
            : "Deze vraag is van een ander soort dan de vorige en gebruikt andere tools, dus het vaste deel is opnieuw geschreven. Dat kost één keer extra." }
      : { id: "koud_pauze", signaal: true,
          tekst: "Het vaste deel stond niet meer klaar, dus het is opnieuw geschreven. Dat kost één keer extra; een volgende beurt binnen een uur leest het." });
  }
  if (omvangVan(a, "connectortools") > omvangVan(a, "graaftools")) {
    uit.push({ id: "veel_connectortools", signaal: false,
      tekst: "De bronnen naast de wet nemen meer ruimte in dan de wettools. Zet ze uit met /bron als je ze niet nodig hebt." });
  }
  if (a.venster > 0 && a.laatste.totaal >= a.venster * VENSTER_VOL) {
    uit.push({ id: "venster_vol", signaal: true,
      tekst: "Het verzoek vult het venster van het model bijna. Dat hoort niet voor te komen; begin een nieuw gesprek met /nieuw." });
  }
  return uit;
}

/** Het signaal op de meter: de eerste regel die er een geeft, of niets. */
export function signaal(nu: Contextopbouw, vorige?: Contextopbouw): Advies | undefined {
  return adviezen(nu, vorige).find((x) => x.signaal);
}

/** Hoe de beurt begon, in gewone taal, voor iedereen. */
export function beginTekst(a: ContextAgent): string {
  const { lees, schrijf } = a.begin.cache;
  if (beginKoud(a)) {
    return `Deze beurt begon koud: het vaste deel (${kort(schrijf)}) is opnieuw geschreven. Dat kost meer dan lezen.`;
  }
  return `Deze beurt begon warm: ${kort(lees)} kwam uit de cache${schrijf ? `, ${kort(schrijf)} is nieuw geschreven` : ""}.`;
}

// ── Het verloop en de boom ───────────────────────────────────────────────────────────────────────────────────────────

export interface VerloopPunt { run_id: string; context: number; verbruik: number }

/** Per beurt de omvang van de context en het verbruik: twee lijntjes over het gesprek. */
export function verloop(beurten: Beurt[]): VerloopPunt[] {
  return beurten.map((b) => ({ run_id: b.run_id, context: hoofdagent(b.contextopbouw)?.laatste.totaal ?? 0,
    verbruik: totaalVerbruik(b.contextopbouw.som) }));
}

/** De punten van één lijntje in een vak van `breedte` × `hoogte`, als `points` van een polyline. Eén punt is een
 *  horizontale lijn; de hoogste waarde raakt de bovenkant. */
export function lijn(waarden: number[], breedte: number, hoogte: number): string {
  if (!waarden.length) return "";
  const max = Math.max(...waarden, 1);
  const stap = waarden.length > 1 ? breedte / (waarden.length - 1) : 0;
  const punt = (w: number, i: number) => `${Math.round(i * stap * 10) / 10},${Math.round((hoogte - (w / max) * hoogte) * 10) / 10}`;
  return waarden.length === 1 ? `0,${punt(waarden[0], 0).split(",")[1]} ${breedte},${punt(waarden[0], 0).split(",")[1]}`
    : waarden.map(punt).join(" ");
}

export interface KindRij {
  gesprek_id: string;
  titel: string;
  /** De beurten van het kind die bij deze beurt horen (`ouder_run_id`), of alle als de beurt geen run kent. */
  beurten: Beurt[];
  /** De context van het kind: het laatste verzoek van zijn laatste beurt. `undefined` = niet gemeten of loopt nog. */
  context?: ContextAgent;
  verbruik: number;
  gemeten: boolean;
}

/** De rijen van de boom bij één beurt: de deelgesprekken die deze run startte (`ouder_run_id`).
 *
 *  Niet elk kind wijst naar een gemeten beurt van dit gesprek. Een regie (ADR-012) gebruikt zelf geen model en heeft dus
 *  geen meting, en de beurten van een reeks dragen geen ouder (meting 12 nov 2026). Zo'n kind is aan geen beurt toe te
 *  wijzen: het staat bij de laatste beurt, of – in een gesprek zonder gemeten beurt – op zichzelf. Hetzelfde geldt voor
 *  een kind zonder enige meting (het loopt nog, of eindigde zonder bericht): dat staat erbij als "niet gemeten", en het
 *  totaal van de boom is dan onvolledig.
 *
 *  `bekend` zijn de runs van de gemeten beurten van dit gesprek; `laatste` zegt of dit de laatste beurt is. */
export function kindRijen(boom: ContextBoom | undefined, runId: string, laatste = true, bekend: string[] = []): KindRij[] {
  if (!boom) return [];
  const uit: KindRij[] = [];
  for (const k of boom.kinderen) {
    const alle = beurtenUitBerichten(k.berichten.map((b) => ({ rol: "assistant" as const, run_id: b.run_id, contextopbouw: b.contextopbouw })));
    const eigen = alle.filter((b) => {
      const ouder = b.contextopbouw.ouder_run_id;
      return (runId !== "" && ouder === runId) || (laatste && !bekend.includes(ouder));
    });
    // Een kind dat alleen bij een andere beurt hoort, staat hier niet.
    if (!eigen.length && (alle.length || !laatste)) continue;
    uit.push({ gesprek_id: k.gesprek_id, titel: k.titel, beurten: eigen, gemeten: eigen.length > 0,
      context: hoofdagent(eigen.at(-1)?.contextopbouw),
      verbruik: eigen.reduce((n, b) => n + totaalVerbruik(b.contextopbouw.som), 0) });
  }
  return uit;
}

/** Het verbruik van de boom: de eigen run (als die gemeten is) plus alle kinderen. `volledig` is onwaar zodra een kind
 *  niet gemeten is. */
export function boomVerbruik(eigen: Contextopbouw | undefined, kinderen: KindRij[]): { totaal: number; volledig: boolean } {
  return { totaal: (eigen ? totaalVerbruik(eigen.som) : 0) + kinderen.reduce((n, k) => n + k.verbruik, 0),
    volledig: kinderen.every((k) => k.gemeten) };
}

/** De naam van een rol in de tabel van het verbruik. Een onbekende rol toont zijn eigen naam. */
const ROL_LABEL: Record<string, string> = {
  antwoord: "Antwoord", centraal: "Centrale agent", ophaal: "Bepaling zoeken", supervisor: "Vraag indelen", bepaling_toelichting: "Toelichting bij de bepaling",
  jas_classifier: "Markeringen classificeren", jas_reviewer: "Twijfelgevallen beoordelen", begrip_vergelijk: "Begrippen vergelijken",
  begrip_kaart: "Begripskaart", kaartactie: "Begrip uitwerken", deelvragen_voorstel: "Deelvragen voorstellen",
  deelvraag_verbeter: "Deelvraag verbeteren", intake: "Werkgebied samenstellen", onbekend: "Overig",
};

export function rolLabel(rol: string): string {
  return ROL_LABEL[rol] ?? rol;
}

/** De rollen waarvoor de werkplek een eigen naam heeft; de drifttest vergelijkt ze met `Rol` in graph-qa. */
export const BEKENDE_ROLLEN = Object.keys(ROL_LABEL).filter((r) => r !== "onbekend");
