// Client-side fetch-helpers. Praten UITSLUITEND met de eigen Next.js-origin (/api/**);
// de BFF-laag injecteert het token server-side. Hier dus geen Authorization-header.

import {
  geldig,
  parseBronnen,
  parseDoel,
  parseElement,
  parseHergebruik,
  parseKandidaten,
  parseKeuze,
  parseRun,
  parseRunStart,
} from "./agentEvents";
import type {
  ApiError,
  ApiTokenCreated,
  ApiTokenOut,
  LlmProfileIn,
  LlmProfileOut,
  LoginVerifyResult,
  BudgetBeleid,
  MeAccount,
  RegistratieBulkRegel,
  RegistratieOut,
  Role,
  TempPassword,
  TestResult,
  TotpBegin,
  UserCreated,
  UserOut,
  VerbruikRegel,
  Verbruiksstand,
} from "./types";
import type {
  AdminBerichtenPaginaOut,
  AdminBerichtOut,
  AgentContext,
  AgentDoelInvoer,
  AgentDoel,
  AgentGrounding,
  AgentHergebruik,
  AgentKandidaat,
  AgentRun,
  Bericht,
  BerichtAanmakenIn,
  BerichtenPaginaOut,
  BerichtInvoer,
  BerichtOut,
  BerichtPublicatieIn,
  Bron,
  DocumentSamenvatting,
  Gesprek,
  GesprekSamenvatting,
  OngelezenAantalOut,
  RunStart,
  VoorstelElement,
} from "./types";
import { pathSegment } from "./url";

export async function parseError(res: Response): Promise<ApiError> {
  let detail = res.statusText;
  let reden: string | undefined;
  let data: Record<string, unknown> | undefined;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (body?.detail && typeof body.detail === "object") {
      // Een gestructureerde fout (`{reden, melding, …}`). Het `melding`-veld bestaat juist om
      // getoond te worden; die eruit halen scheelt dat er rauwe JSON in beeld komt. Zonder melding
      // blijft de JSON de terugval – een fout zonder leesbare tekst mag niet onzichtbaar worden.
      data = body.detail as Record<string, unknown>;
      reden = typeof data.reden === "string" ? data.reden : undefined;
      detail =
        typeof data.melding === "string" && data.melding.trim()
          ? data.melding
          : JSON.stringify(body.detail);
    }
  } catch {
    /* geen JSON-body */
  }
  const ra = res.headers.get("Retry-After");
  if (res.status === 401) naarInloggen();
  return { status: res.status, detail, reden, data, retryAfter: ra ? Number(ra) : undefined };
}

let opWegNaarInloggen = false;

/** De sessie is verlopen of ingetrokken: naar het inlogscherm, met de huidige plek als terugweg.
 *
 *  Een 401 betekent bij de BFF en de api altijd "geen geldige sessie" (een verkeerd wachtwoord is een
 *  400 of een `ok: false`). Zonder deze stap kwam "Niet ingelogd." als losse tekst in een bubbel of
 *  melding terecht en bleef de werkplek doen alsof er gewerkt kon worden. Eén keer per paginaleven:
 *  een handvol gelijktijdige calls die allemaal 401 krijgen, hoeven niet elk opnieuw te navigeren.
 *  De login-routes zelf komen hier niet langs – die handelen hun 401 af zonder `parseError`. */
export function naarInloggen(): void {
  if (typeof window === "undefined" || opWegNaarInloggen) return;
  if (window.location.pathname.startsWith("/login")) return;
  opWegNaarInloggen = true;
  const terug = window.location.pathname + window.location.search;
  // Harde navigatie, geen router: de sessie is weg, en de middleware moet de volgende paginalaad
  // opnieuw beoordelen (zie ook `LoginClient`).
  const doel = new URL("/login", window.location.origin);
  doel.searchParams.set("callbackUrl", terug);
  window.location.href = doel.href;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

/** JSON.parse dat `null` teruggeeft in plaats van te gooien. Bewust `unknown`: wat er binnenkomt
 *  staat niet vast, en dat is precies waarom de aanroeper het langs een schema haalt. */
function veiligJson(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return typeof e === "object" && e !== null && "status" in e && "detail" in e;
}

/** De leesbare reden achter een mislukte aanroep.
 *
 *  Let op waaróm dit bestaat: een `ApiError` is een object-literal, géén `Error`-instantie. Een
 *  handler die `e instanceof Error ? e.message : "<generiek>"` schrijft, valt dus bij *elke*
 *  api-fout terug op de generieke tekst – en dan wordt "een agent-voorstel verwerp je" (409)
 *  onzichtbaar achter "de markering is niet gewist". Gebruik deze helper, niet `instanceof`.
 */
export function foutTekst(e: unknown, terugval = "Er ging iets mis."): string {
  if (isApiError(e)) return e.detail;
  return (e as Error)?.message || terugval;
}

// --- Admin: LLM-modelprofielen ----------------------------------------------

export async function listProfiles(): Promise<LlmProfileOut[]> {
  const res = await fetch("/api/admin/profiles", { cache: "no-store" });
  return json<LlmProfileOut[]>(res);
}

export async function saveProfile(name: string, body: LlmProfileIn): Promise<LlmProfileOut> {
  const res = await fetch(`/api/admin/profiles/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<LlmProfileOut>(res);
}

export async function deleteProfile(name: string): Promise<void> {
  const res = await fetch(`/api/admin/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}

export async function setDefaultProfile(name: string): Promise<LlmProfileOut> {
  const res = await fetch(`/api/admin/profiles/${encodeURIComponent(name)}/default`, { method: "POST" });
  return json<LlmProfileOut>(res);
}

export async function testProfile(name: string): Promise<TestResult> {
  const res = await fetch(`/api/admin/profiles/${encodeURIComponent(name)}/test`, { method: "POST" });
  return json<TestResult>(res);
}

// --- Admin: gebruikers ------------------------------------------------------

export async function listUsers(): Promise<UserOut[]> {
  const res = await fetch("/api/admin/users", { cache: "no-store" });
  return json<UserOut[]>(res);
}

export async function createUser(userid: string, email: string, role: Role): Promise<UserCreated> {
  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userid, email, role }),
  });
  return json<UserCreated>(res);
}

export async function patchUser(
  userid: string,
  // `token_budget_wissen` bestaat omdat `token_budget: null` anders twee dingen zou betekenen:
  // niet meegestuurd, of bewust terug naar het beleid.
  body: { role?: Role; active?: boolean; token_budget?: number; token_budget_wissen?: boolean },
): Promise<UserOut> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(userid)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<UserOut>(res);
}

export async function resetUserPassword(userid: string): Promise<TempPassword> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(userid)}/reset-password`, { method: "POST" });
  return json<TempPassword>(res);
}

export async function deleteUser(userid: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(userid)}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}

// --- Tokenbudget ------------------------------------------------------------

/** De eigen stand. Stil falen is hier NIET gepast: de aanroeper beslist wat hij toont. */
export async function getVerbruik(): Promise<Verbruiksstand> {
  const res = await fetch("/api/account/verbruik", { cache: "no-store" });
  return json<Verbruiksstand>(res);
}

export async function getBudgetBeleid(): Promise<BudgetBeleid> {
  const res = await fetch("/api/admin/budget", { cache: "no-store" });
  return json<BudgetBeleid>(res);
}

export async function zetBudgetBeleid(body: {
  tokens: number;
  periode_dagen: number;
  actief: boolean;
}): Promise<BudgetBeleid> {
  const res = await fetch("/api/admin/budget", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<BudgetBeleid>(res);
}

export async function listVerbruik(): Promise<VerbruikRegel[]> {
  const res = await fetch("/api/admin/verbruik", { cache: "no-store" });
  return json<VerbruikRegel[]>(res);
}

// --- Admin: zelfregistratie-aanvragen ---------------------------------------

export async function listRegistraties(status?: string): Promise<RegistratieOut[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(`/api/admin/registraties${q}`, { cache: "no-store" });
  return json<RegistratieOut[]>(res);
}

/** Goedkeuren maakt het account aan. `userid` leeg = het voorstel overnemen. */
export async function approveRegistratie(
  id: number,
  body: { userid?: string; role: Role },
): Promise<UserOut> {
  const res = await fetch(`/api/admin/registraties/${id}/goedkeuren`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<UserOut>(res);
}

export async function rejectRegistratie(id: number, reden: string): Promise<void> {
  const res = await fetch(`/api/admin/registraties/${id}/afwijzen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reden }),
  });
  if (!res.ok) throw await parseError(res);
}

export async function approveRegistraties(
  ids: number[],
  role: Role,
): Promise<RegistratieBulkRegel[]> {
  const res = await fetch("/api/admin/registraties/goedkeuren", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, role }),
  });
  return json<RegistratieBulkRegel[]>(res);
}

/** Verwijderen is de enige manier om het e-mailadres weer vrij te geven. */
export async function deleteRegistratie(id: number): Promise<void> {
  const res = await fetch(`/api/admin/registraties/${id}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}

// --- Admin: genereerbare API-tokens -----------------------------------------

export async function listApiTokens(): Promise<ApiTokenOut[]> {
  const res = await fetch("/api/admin/api-tokens", { cache: "no-store" });
  return json<ApiTokenOut[]>(res);
}

export async function createApiToken(label: string): Promise<ApiTokenCreated> {
  const res = await fetch("/api/admin/api-tokens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  return json<ApiTokenCreated>(res);
}

export async function revokeApiToken(id: string): Promise<void> {
  const res = await fetch(`/api/admin/api-tokens/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}

// --- Login (pre-check vóór de Auth.js-sessie) -------------------------------

/** Stap A – pre-check: kloppen userid+wachtwoord, en is 2FA vereist? Een vertrouwd apparaat (cookie)
 *  levert direct code "ok". Zet zelf geen sessie. */
export async function loginVerify(
  userid: string,
  password: string,
): Promise<LoginVerifyResult> {
  const res = await fetch("/api/login-verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userid, password }),
  });
  // Een 5xx is een storing, geen oordeel over de inloggegevens: gooien, zodat de aanroeper zijn
  // "dienst niet bereikbaar"-melding toont. Zonder die worp werd een platte API hier stilzwijgend
  // "invalid" – en las de gebruiker dat zijn wachtwoord fout was. De API wijst een login af met een
  // 200 + `ok: false`, dus daar raakt dit niet aan.
  if (res.status >= 500) throw await parseError(res);
  if (!res.ok && res.status !== 200) {
    return { ok: false, code: res.status === 429 ? "rate" : "invalid", userid: "", email: "", role: "" };
  }
  return (await res.json()) as LoginVerifyResult;
}

/** Stap B – verifieer de 2FA-code op het aparte /login/2fa-scherm via het login-ticket (httpOnly
 *  cookie). `remember` zet de trusted-device-cookie (30 dagen). Zet zelf geen sessie. */
export async function login2fa(
  userid: string,
  totp: string,
  remember: boolean,
): Promise<LoginVerifyResult> {
  const res = await fetch("/api/login-2fa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userid, totp, remember }),
  });
  // Zie `loginVerify`: alleen een 5xx is een storing. De 401 van deze route (login-ticket verlopen)
  // blijft een gewone afwijzing – die hoort je terug naar stap A te sturen, niet naar een storing.
  if (res.status >= 500) throw await parseError(res);
  if (!res.ok && res.status !== 200) {
    return { ok: false, code: res.status === 429 ? "rate" : "invalid", userid: "", email: "", role: "" };
  }
  return (await res.json()) as LoginVerifyResult;
}

// --- PoC-disclaimer ----------------------------------------------------------

export async function accepteerDisclaimer(): Promise<void> {
  const res = await fetch("/api/disclaimer", { method: "POST" });
  if (!res.ok) throw await parseError(res);
}

/** Bij het uitloggen: de sessiecookie overleeft anders een logout in dezelfde browsersessie. */
export async function wisDisclaimer(): Promise<void> {
  await fetch("/api/disclaimer", { method: "DELETE" }).catch(() => {
    /* uitloggen mag hier nooit op stuklopen */
  });
}

// --- Account (self-service): 2FA --------------------------------------------

export async function getAccount(): Promise<MeAccount> {
  const res = await fetch("/api/account/me", { cache: "no-store" });
  return json<MeAccount>(res);
}

export async function begin2fa(): Promise<TotpBegin> {
  const res = await fetch("/api/account/2fa/begin", { method: "POST" });
  return json<TotpBegin>(res);
}

export async function activate2fa(totp: string): Promise<void> {
  const res = await fetch("/api/account/2fa/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ totp }),
  });
  if (!res.ok) throw await parseError(res);
}

export async function disable2fa(totp: string): Promise<void> {
  const res = await fetch("/api/account/2fa/disable", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ totp }),
  });
  if (!res.ok) throw await parseError(res);
}

export async function changePassword(current: string, nieuw: string): Promise<void> {
  const res = await fetch("/api/account/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current, new: nieuw }),
  });
  if (!res.ok) throw await parseError(res);
}

// --- Annotatie-workbench -----------------------------------------------------

/** De annotatielagen – één per bronnode, gedeeld. `mijn` beperkt tot lagen waar je zelf iets aan
 *  deed (dat staat in de audit; een laag heeft geen eigenaar). */
export async function lijstLagen(opties: { mijn?: boolean; limit?: number } = {}): Promise<DocumentSamenvatting[]> {
  const qs = new URLSearchParams({ limit: String(opties.limit ?? 200) });
  if (opties.mijn) qs.set("mijn", "true");
  return json<DocumentSamenvatting[]>(await fetch(`/api/annotatie/v2/node-lagen?${qs}`, { cache: "no-store" }));
}

// --- Gesprekken (chatgeschiedenis; per-gebruiker via de BFF-X-User-Id) ------

export async function lijstGesprekken(): Promise<GesprekSamenvatting[]> {
  return json<GesprekSamenvatting[]>(await fetch("/api/gesprekken", { cache: "no-store" }));
}

export async function maakGesprek(titel = ""): Promise<Gesprek> {
  const res = await fetch("/api/gesprekken", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titel }),
  });
  return json<Gesprek>(res);
}

export async function haalGesprek(id: string): Promise<Gesprek> {
  return json<Gesprek>(await fetch(`/api/gesprekken/${pathSegment(id)}`, { cache: "no-store" }));
}

export async function voegBerichtToe(id: string, bericht: BerichtInvoer): Promise<Bericht> {
  const res = await fetch(`/api/gesprekken/${pathSegment(id)}/berichten`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bericht),
  });
  return json<Bericht>(res);
}

export async function hernoemGesprek(id: string, titel: string): Promise<Gesprek> {
  const res = await fetch(`/api/gesprekken/${pathSegment(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titel }),
  });
  return json<Gesprek>(res);
}

/** Verwijder een gesprek. Een 404 telt als geslaagd: dan is het al weg, en dat is precies wat er
 *  gevraagd werd. Anders levert een tweede klik – of een tabblad dat hetzelfde gesprek al opruimde –
 *  de melding "Het gesprek is niet verwijderd" over iets dat wél verwijderd is. */
export async function verwijderGesprek(id: string): Promise<void> {
  const res = await fetch(`/api/gesprekken/${pathSegment(id)}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) throw await parseError(res);
}

/** De callbacks waarmee een beurt binnenkomt. Gedeeld door het starten van een run (`startRun`) en
 *  het aanhaken bij een lopende (`volgRun`) – één contract, twee ingangen. */
export type AgentHandlers = {
    onToolExecution?: (event: import("./annotatieNode").ToolExecution) => void;
    onStatus?: (m: string) => void;
    onReason?: (t: string) => void;
    onToken?: (t: string) => void;
    onSources?: (bronnen: Bron[]) => void;
    /** De brongetrouwheidstoets op dit antwoord. Kwam altijd al binnen als `grounding`-event, maar
     *  werd nergens uitgelezen – dus een niet-onderbouwde verwijzing bleef onzichtbaar. */
    onGrounding?: (g: AgentGrounding) => void;
    onDoel?: (doel: AgentDoel) => void;
    onElement?: (el: VoorstelElement) => void;
    /** De herkomst van deze beurt (model/agentversie); komt vóór de elementen. */
    onRun?: (run: AgentRun) => void;
  /** De vraag noemde een onderwerp, geen bepaling: dit zijn de gevonden bepalingen om uit te kiezen. */
  onKandidaten?: (k: AgentKandidaat[], keuze?: import("./types").AgentKeuze) => void;
  /** Een event van een reeks (`reeks`, `onderdeel`, of een event dat bij één onderdeel hoort).
   *  Ruw doorgegeven: `lib/reeks.ts` valideert en verwerkt het. Een fout bij één onderdeel
   *  beëindigt de stroom dus niet – de rest van de reeks loopt door. */
  onReeksEvent?: (event: Record<string, unknown>) => void;
  /** Lex hergebruikte (een deel van) de gedeelde laag in plaats van opnieuw te annoteren. */
  onHergebruik?: (h: AgentHergebruik) => void;
  /** Het volgnummer van het laatst verwerkte event. Daarmee haakt een client na een onderbreking
   *  weer aan op precies het juiste punt in plaats van vanaf het begin. */
  onSeq?: (seq: number) => void;
  /** Levensteken: er kwam een event over deze verbinding binnen. Geen inhoud, alleen het feit dát
   *  de stroom loopt – daarop haalt de werkplek de "verbinding weg"-melding weg en zet ze de
   *  herstelteller terug. Zonder dit zou een geslaagd heraanhaken pas zichtbaar zijn aan het eind. */
  onLeeft?: () => void;
  /** Er zijn events weggevallen (de eventlog van de run is gecapt). Toon een gat in plaats van te
   *  doen alsof de tekst compleet is. */
  onGat?: (aantal: number) => void;
  /** De agent heeft de uitkomst zelf vastgelegd (bericht + eventueel annotatiedocument). Komt vlak
   *  vóór het einde. Blijft hij uit, dan legt de werkplek het bericht zelf vast. */
  onOpgeslagen?: (uitkomst: { annotatie_slug: string; run_id: string; annotatie_doel?: import("./annotatieNode").NodeDoel }) => void;
  /** De beurt slaagde, maar niet alles is bewaard – bv. een markering die de api niet accepteerde.
   *  Geen fout (het meeste staat er wél), maar de jurist hoort te weten dat er iets ontbreekt. */
  onWaarschuwing?: (bericht: string) => void;
};

// --- Runs: de beurt is van de server -----------------------------------------
//
// De run draait bij graph-qa en de browser kijkt mee. Wegklikken, van gesprek wisselen of herladen
// koppelt alleen de kijker los – stoppen doe je met `stopRun`.
//
// Hier stond ook `annoteerAgentStream`: één POST naar `/api/annotatie/agent` die de beurt aan de
// verbinding van dat ene tabblad hing. Die is weg, en niet alleen omdat de run-route hem overbodig
// maakte. Hij stuurde het `conversation_id` uit de browser ongewijzigd door naar graph-qa, waar het
// de thread_id van het agent-geheugen is – zónder te controleren of dat gesprek van deze gebruiker
// was. Met een gespreks-id van iemand anders (die staat gewoon in de URL van de werkplek) las je zo
// diens gesprekshistorie terug. `startRun` hieronder verifieert het eigenaarschap wél, bij de api.

/** Start een beurt. Geeft de run terug, of – als er al een run voor dit gesprek loopt – de
 *  bestaande, zodat de aanroeper daarop aanhaakt in plaats van een tweede te starten.
 *
 *  Die tweede zou niet alleen verwarrend zijn: `conversation_id` is ook de thread_id van het
 *  agent-geheugen, dus twee gelijktijdige beurten schrijven door elkaar heen. */
export async function startRun(
  prompt: string,
  conversationId?: string,
  extra?: {
    modus?: "auto" | "advies";
    context?: AgentContext;
    doel?: AgentDoelInvoer;
    /** "opnieuw" = de jurist vraagt expliciet om een nieuwe ronde op een al geannoteerd artikel.
     *  Die vult de gedeelde laag aan; wat beoordeeld is blijft staan. */
    hergebruik?: "auto" | "opnieuw";
    /** Meerdere onderdelen van één bepaling, gekozen op de keuzekaart: één run, elk onderdeel
     *  een eigen laag (graph-qa `agent/reeks.py`). Sluit `doel` uit. */
    doelen?: AgentDoelInvoer[];
  },
): Promise<RunStart> {
  const res = await fetch("/api/annotatie/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: prompt,
      conversation_id: conversationId,
      ...(extra?.modus ? { modus: extra.modus } : {}),
      ...(extra?.context ? { context: extra.context } : {}),
      // Kennen we de bepaling al, dan hoeft niemand hem meer te zoeken: de agent slaat de
      // supervisor en de ophaal-agent over en annoteert precies deze.
      ...(extra?.doel ? { doel: extra.doel } : {}),
      ...(extra?.hergebruik ? { hergebruik: extra.hergebruik } : {}),
      ...(extra?.doelen ? { doelen: extra.doelen } : {}),
    }),
  });
  if (res.status === 409) {
    // Er loopt al een beurt op dit gesprek. Dat is geen storing, maar deze vraag is óók niet
    // aangenomen – en dat mag de aanroeper niet verwarren met "hij loopt". Gaf `startRun` hier de
    // bestaande run terug, dan verscheen het antwoord op de vórige vraag onder de nieuwe, en ging
    // de nieuwe vraag stilzwijgend verloren.
    const fout = await parseError(res);
    const lopend = fout.data?.run_id;
    throw {
      ...fout,
      loopendeRun: typeof lopend === "string" ? lopend : undefined,
    } as RunLooptAlFout;
  }
  if (res.status === 429) {
    // Twee soorten 429 met een heel verschillende betekenis: het tokenbudget is op (wachten tot de
    // reset, de invoer gaat dicht), of de gewone verzoek-rate-limit van de agent (zo nog eens
    // proberen). Alleen de eerste krijgt een eigen afhandeling; de tweede blijft een gewone fout.
    const fout = await parseError(res);
    if (fout.reden === "budget_op") throw { ...fout, budgetOp: true } as RunBudgetOpFout;
    throw fout;
  }
  const start = geldig(parseRunStart, await json<unknown>(res), "runs");
  if (!start) throw { status: 502, detail: "De agent gaf een onbegrijpelijk antwoord." } as ApiError;
  return start;
}

/** Een 409 van `startRun`: er loopt al een beurt op dit gesprek. `loopendeRun` wijst hem aan, zodat
 *  de werkplek kan aanbieden om daarop aan te haken in plaats van de vraag te verliezen. */
export interface RunLooptAlFout extends ApiError {
  loopendeRun?: string;
}

/** Een 429 van `startRun` omdat het tokenbudget op is. De vraag is NIET aangenomen; de werkplek
 *  zet hem terug in het invoerveld en ververst de verbruiksstand, zodat de strook en de dichte
 *  invoerbalk meteen kloppen in plaats van pas bij het volgende minuut-interval. */
export interface RunBudgetOpFout extends ApiError {
  budgetOp?: true;
}

/** Een fout die de agent zélf over de stroom stuurde (`error`-event), en niet een verbinding die
 *  brak. Het verschil is niet uit de status af te lezen – beide zijn 502 – en het bepaalt wél of
 *  opnieuw aanhaken zin heeft. Zie `definitieveStroomfout` in `lib/lopendeRun.ts`. */
export interface AgentFout extends ApiError {
  agentFout?: true;
}

/** Hoe lang een stroom stil mag vallen voordat we hem als verbroken beschouwen.
 *
 *  sse-starlette stuurt elke ~15 seconden een `:`-heartbeat, dus drie gemiste hartslagen is een
 *  veilige ondergrens. Zonder deze bewaking blijft `reader.read()` eeuwig hangen op een halfopen
 *  socket – geen fout, geen einde, en een werkplek die tot in het oneindige "bezig" toont. */
const STROOM_STILTE_MS = 45_000;

/** Haak aan bij een run en volg hem vanaf `vanaf`. Loskoppelen (abort) laat de run doorlopen —
 *  dat is het hele verschil met de oude stream. */
export async function volgRun(
  runId: string,
  handlers: AgentHandlers,
  vanaf = 0,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/annotatie/run/${pathSegment(runId)}/events?vanaf=${vanaf}`, {
    cache: "no-store",
    signal,
  });
  await verwerkSseStroom(res, handlers);
}

/** Vraag een run te stoppen. Een verzoek, geen feit: de agent-nodes zijn synchroon, dus een lopende
 *  LLM-call maakt zichzelf af en de run eindigt pas op de eerstvolgende grens. */
export async function stopRun(runId: string): Promise<void> {
  const res = await fetch(`/api/annotatie/run/${pathSegment(runId)}/cancel`, { method: "POST" });
  if (!res.ok) throw await parseError(res);
}

/** Loopt er nog een beurt in dit gesprek? Dit vraagt de werkplek bij binnenkomst, zodat een beurt
 *  die tijdens het wegklikken doorliep weer in beeld komt. Faalt stil: geen run kunnen vinden mag de
 *  werkplek niet blokkeren – dan zie je gewoon de gehydrateerde geschiedenis. */
export async function haalActieveRun(gesprekId: string): Promise<RunStart | null | "onbekend"> {
  // Drie uitkomsten, en het verschil telt: `null` betekent "er loopt niets", `"onbekend"` betekent
  // "ik kon het niet vaststellen". Die twee op één hoop gooien leverde een melding op dat je beurt
  // was afgebroken zodra het netwerk één keer hikte – terwijl hij gewoon doorliep.
  try {
    const res = await fetch(`/api/annotatie/run?gesprek=${encodeURIComponent(gesprekId)}`, {
      cache: "no-store",
    });
    if (!res.ok) return "onbekend";
    // Geen lopende run is een geldig antwoord (null); alleen een niet-lege body moet kloppen.
    const body = (await res.json()) as unknown;
    if (body === null) return null;
    return geldig(parseRunStart, body, "actieve run") ?? null;
  } catch {
    return "onbekend";
  }
}

/** De SSE-parser: frames uit de body halen en op de handlers afvuren.
 *
 *  Eén implementatie voor beide ingangen, zodat het eventcontract niet op twee plekken uit elkaar
 *  kan lopen. sse-starlette scheidt met \r\n; de CR wordt gestript zodat de framegrens klopt. */
async function verwerkSseStroom(res: Response, handlers: AgentHandlers): Promise<void> {
  if (!res.ok) throw await parseError(res);
  if (!res.body) throw { status: 0, detail: "Geen agentstroom." } as ApiError;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // De stiltebewaking. Bewust een verwérpende timer en géén `reader.cancel()`: cancellen levert
  // `done`, en dan zou een halve stroom als een keurig afgeronde beurt eindigen.
  let stilteTimer: ReturnType<typeof setTimeout> | undefined;
  const stilte = () =>
    new Promise<never>((_, mis) => {
      stilteTimer = setTimeout(
        () => mis({ status: 0, detail: "De verbinding viel stil." } as ApiError),
        STROOM_STILTE_MS,
      );
    });
  try {
    for (;;) {
      const { done, value } = await Promise.race([reader.read(), stilte()]);
      clearTimeout(stilteTimer);
      if (done) break;
      // sse-starlette scheidt met \r\n; strip de CR zodat indexOf("\n\n") de frame-grens vindt.
      buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");
      let scheiding: number;
      while ((scheiding = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, scheiding);
        buffer = buffer.slice(scheiding + 2);
        let data = "";
        for (const regel of frame.split("\n")) {
          if (regel.startsWith(":")) continue; // heartbeat
          if (regel.startsWith("data:")) data += regel.slice(5).trim();
        }
        if (!data) continue;
        // Alleen de envelop is hier bekend. De gestructureerde payloads blijven `unknown` tot
        // een schema ze heeft goedgekeurd — anders zou één `as` ze als geldige inhoud de UI in
        // laten lopen.
        const ev = veiligJson(data) as
          | {
              type?: unknown;
              message?: string;
              content?: string;
              doel?: unknown;
              element?: unknown;
              run?: unknown;
              sources?: unknown;
              kandidaten?: unknown;
              hergebruik?: unknown;
              seq?: number;
              weggevallen?: number;
              annotatie_slug?: string;
              annotatie_doel?: import("./annotatieNode").NodeDoel;
              run_id?: string;
              // grounding: `niveau` is nieuw; een oudere agent stuurt alleen `grounded`.
              niveau?: AgentGrounding["niveau"];
              grounded?: boolean;
              cited?: number;
              unsupported?: string[];
              niet_letterlijk?: string[];
            }
          | null;
        if (!ev) continue;
        // Er komt iets door: deze verbinding leeft. Vóór alle inhoudelijke afhandeling, zodat ook
        // een stroom die met een `error`-event begint het herstel eerst als geslaagd afmeldt.
        handlers.onLeeft?.();
        if (typeof ev.seq === "number") handlers.onSeq?.(ev.seq);
        const onderdeel = (ev as { onderdeel?: unknown }).onderdeel;
        if (ev.type === "reeks" || ev.type === "onderdeel" || (typeof onderdeel === "string" && onderdeel)) {
          // Zonder reeks-handler (een oudere aanroeper) valt het event door naar de gewone
          // afhandeling; een fout bij één onderdeel gooit dan zoals altijd.
          if (handlers.onReeksEvent) {
            handlers.onReeksEvent(ev as Record<string, unknown>);
            continue;
          }
        }
        if (ev.type === "gat") handlers.onGat?.(ev.weggevallen ?? 0);
        else if (ev.type === "status") handlers.onStatus?.(ev.message ?? "");
        else if (ev.type === "reason") handlers.onReason?.(ev.content ?? "");
        else if (ev.type === "token") handlers.onToken?.(ev.content ?? "");
        else if (ev.type === "sources" && ev.sources) {
          const bronnen = geldig(parseBronnen, ev.sources, "sources");
          if (bronnen) handlers.onSources?.(bronnen);
        }
        else if (ev.type === "grounding")
          handlers.onGrounding?.({
            niveau: ev.niveau ?? (ev.grounded === false ? "ongegrond" : "gegrond"),
            grounded: ev.grounded !== false,
            cited: ev.cited ?? 0,
            unsupported: ev.unsupported ?? [],
            niet_letterlijk: ev.niet_letterlijk ?? [],
          });
        else if (ev.type === "doel" && ev.doel) {
          const doel = geldig(parseDoel, ev.doel, "doel");
          if (doel) handlers.onDoel?.(doel);
        }
        else if (ev.type === "element" && ev.element) {
          const element = geldig(parseElement, ev.element, "element");
          if (element) handlers.onElement?.(element);
        }
        else if (ev.type === "run" && ev.run) {
          const run = geldig(parseRun, ev.run, "run");
          if (run) handlers.onRun?.(run);
        }
        else if (ev.type === "kandidaten") {
          const kandidaten = geldig(parseKandidaten, ev.kandidaten ?? [], "kandidaten");
          if (kandidaten) handlers.onKandidaten?.(kandidaten, parseKeuze((ev as { keuze?: unknown }).keuze));
        }
        else if (ev.type === "hergebruik" && ev.hergebruik) {
          const hergebruik = geldig(parseHergebruik, ev.hergebruik, "hergebruik");
          if (hergebruik) handlers.onHergebruik?.(hergebruik);
        }
        else if (ev.type === "tool_execution") {
          const { parseToolExecution } = await import("./annotatieNode");
          const execution = parseToolExecution(ev);
          if (execution) handlers.onToolExecution?.(execution);
        }
        else if (ev.type === "opgeslagen")
          handlers.onOpgeslagen?.({ annotatie_slug: ev.annotatie_slug ?? "", run_id: ev.run_id ?? "", annotatie_doel: ev.annotatie_doel });
        else if (ev.type === "waarschuwing") handlers.onWaarschuwing?.(ev.message ?? "");
        // `agentFout` onderscheidt dit van een 502 die zegt "de BFF kon graph-qa niet bereiken":
        // die is tijdelijk en mag opnieuw, deze is een uitkomst van de beurt zelf.
        else if (ev.type === "error")
          throw { status: 502, detail: ev.message ?? "Agent mislukt.", agentFout: true } as AgentFout;
      }
    }
  } finally {
    clearTimeout(stilteTimer);
    reader.cancel().catch(() => {});
  }
}

/** Exportformaten van een annotatie. */
export type ExportFormaat = "pdf" | "csv" | "json";

/** Bied een bestandsantwoord aan als download: Blob → `createObjectURL` → `<a download>`.
 *
 *  Het enige downloadpatroon in deze app – artikel- én bronnode-export lopen hierlangs, zodat de
 *  bestandsnaam overal van de server komt (`Content-Disposition`) en de link overal in het document
 *  hangt voor de klik (oudere Firefox- en Safari-versies negeren een klik op een losse `<a>`). */
export async function downloadAntwoord(res: Response, terugvalNaam: string): Promise<void> {
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = bestandsnaamUit(res.headers.get("content-disposition")) ?? terugvalNaam;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    // Niet meteen intrekken: Safari breekt de download dan af. Eén tick is genoeg.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

/** De bestandsnaam uit `Content-Disposition`: `filename*=UTF-8''…` (RFC 5987) gaat vóór
 *  `filename="…"`, want alleen die vorm draagt tekens buiten ASCII goed over. */
export function bestandsnaamUit(header: string | null): string | undefined {
  const uitgebreid = header?.match(/filename\*=(?:UTF-8|utf-8)''([^;]+)/);
  if (uitgebreid) {
    try {
      return decodeURIComponent(uitgebreid[1].trim());
    } catch {
      /* val terug op de gewone vorm */
    }
  }
  const m = header?.match(/filename="([^"]+)"/) ?? header?.match(/filename=([^;]+)/);
  return m?.[1]?.trim();
}

// --- Gebruikersfeedback -------------------------------------------------------

export async function stuurFeedback(body: {
  categorie: string;
  tekst: string;
  pagina?: string;
}): Promise<{ id: number }> {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<{ id: number }>(res);
}

// --- Admin: gebruikersfeedback -----------------------------------------------

export interface FeedbackItem {
  id: number;
  client_id: string;
  userid: string;
  categorie: string;
  tekst: string;
  pagina: string | null;
  created: string;
}

export interface FeedbackPaginaOut {
  items: FeedbackItem[];
  totaal: number;
}

export async function getFeedback(offset = 0, limit = 50): Promise<FeedbackPaginaOut> {
  const res = await fetch(
    `/api/admin/feedback?offset=${offset}&limit=${limit}`,
    { cache: "no-store" },
  );
  return json<FeedbackPaginaOut>(res);
}

export async function getOngelezenFeedbackAantal(): Promise<number> {
  const res = await fetch("/api/admin/feedback/ongelezen-aantal", { cache: "no-store" });
  const data = await json<{ aantal: number }>(res);
  return data.aantal;
}

export async function markeerFeedbackGezien(tot?: string): Promise<void> {
  const res = await fetch("/api/admin/feedback/markeer-gezien", {
    method: "POST",
    headers: tot ? { "Content-Type": "application/json" } : {},
    body: tot ? JSON.stringify({ tot }) : undefined,
  });
  if (!res.ok) throw await parseError(res);
}

export async function verwijderFeedback(id: number): Promise<void> {
  const res = await fetch(`/api/admin/feedback/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}

// --- Berichtensysteem (analist) ----------------------------------------------

export async function listBerichten(): Promise<BerichtOut[]> {
  const data = await json<BerichtenPaginaOut>(
    await fetch("/api/berichten?ongelezen=true&per_pagina=100", { cache: "no-store" }),
  );
  return data.items;
}

export async function listBerichtenPagina(pagina: number): Promise<BerichtenPaginaOut> {
  return json<BerichtenPaginaOut>(
    await fetch(`/api/berichten?pagina=${pagina}`, { cache: "no-store" }),
  );
}

export async function getOngelezenAantal(): Promise<OngelezenAantalOut> {
  return json<OngelezenAantalOut>(
    await fetch("/api/berichten/ongelezen-aantal", { cache: "no-store" }),
  );
}

export async function markeerAllesGelezen(): Promise<void> {
  const res = await fetch("/api/berichten/lees-alles", { method: "POST" });
  if (!res.ok) throw await parseError(res);
}

// --- Berichtensysteem (admin) ------------------------------------------------

export async function listAlleBerichten(pagina = 1, perPagina = 20): Promise<AdminBerichtenPaginaOut> {
  return json<AdminBerichtenPaginaOut>(
    await fetch(`/api/admin/berichten?pagina=${pagina}&per_pagina=${perPagina}`, { cache: "no-store" }),
  );
}

export async function maakBericht(body: BerichtAanmakenIn): Promise<AdminBerichtOut> {
  return json<AdminBerichtOut>(
    await fetch("/api/admin/berichten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function updateBericht(id: number, body: BerichtAanmakenIn): Promise<AdminBerichtOut> {
  return json<AdminBerichtOut>(
    await fetch(`/api/admin/berichten/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function zetPublicatie(id: number, gepubliceerd: boolean): Promise<AdminBerichtOut> {
  const body: BerichtPublicatieIn = { gepubliceerd };
  return json<AdminBerichtOut>(
    await fetch(`/api/admin/berichten/${id}/publicatie`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function verwijderBericht(id: number): Promise<void> {
  const res = await fetch(`/api/admin/berichten/${id}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res);
}
