// Domeintypes – handmatig afgeleid van het API-contract (api/app/*.py).
// Dit bestand is de bron-van-waarheid voor de frontend; zie README (gen:types) voor
// een optioneel hulpmiddel om ze tegen /openapi.json te controleren.

// --- Admin: LLM-modelprofielen ----------------------------------------------

export interface LlmProfileIn {
  provider?: string;
  model?: string;
  api_base?: string;
  api_version?: string | null;
  output_strategy?: string;
  temperature?: number;
  /** Write-only: leeg laten = bestaande key ongewijzigd. */
  api_key?: string;
  is_default?: boolean;
}

export interface LlmProfileOut {
  name: string;
  provider: string;
  model: string;
  api_base: string;
  api_version: string | null;
  output_strategy: string;
  temperature: number;
  is_default: boolean;
  api_key_set: boolean;
  updated_by: string;
  updated: string;
}

export interface TestResult {
  ok: boolean;
  model: string;
  tokens_in: number;
  tokens_out: number;
  detail: string;
}

// --- Auth: accounts + rollen ------------------------------------------------

export type Role = "beheerder" | "analist";

export interface UserOut {
  userid: string;
  email: string;
  role: Role;
  totp_enabled: boolean;
  active: boolean;
  /** Afwijkend tokenbudget; null = volg het systeembrede beleid. */
  token_budget: number | null;
  created: string;
  updated: string;
}

/** Antwoord bij aanmaken/resetten: het tijdelijke wachtwoord wordt eenmalig getoond. */
export interface UserCreated extends UserOut {
  temp_password: string;
}

export interface TempPassword {
  userid: string;
  temp_password: string;
}

// --- Tokenbudget ---------------------------------------------------------------

/** Waar een gebruiker staat in het huidige venster. Komt van de api; niets hiervan wordt in de
 *  browser berekend – anders kan de meter iets anders zeggen dan de blokkade doet. */
export interface Verbruiksstand {
  userid: string;
  gebruikt: number;
  budget: number;
  /** Gekapt op 100; `gebruikt` is dat niet. */
  percentage: number;
  resterend: number;
  /** ISO-8601: wanneer de teller weer op nul staat. */
  reset_op: string;
  waarschuwing: boolean;
  geblokkeerd: boolean;
  /** False = de begrenzing staat uit; er wordt wel gemeten. */
  actief: boolean;
  eigen_budget: boolean;
}

/** Het systeembrede beleid (beheer). */
export interface BudgetBeleid {
  tokens: number;
  periode_dagen: number;
  anker: string;
  actief: boolean;
  updated_by: string;
  updated: string;
  /** Afgeleid: einde van het huidige venster. */
  reset_op: string;
}

/** Eén regel in het beheeroverzicht. */
export interface VerbruikRegel {
  userid: string;
  gebruikt: number;
  budget: number;
  percentage: number;
  eigen_budget: boolean;
  geblokkeerd: boolean;
}

// --- Zelfregistratie: aanvragen (admin) ---------------------------------------

/** Een aanvraag voor toegang. Dit is nog géén account: pas bij goedkeuring ontstaat er een
 *  gebruiker, met de userid die de beheerder bevestigt of corrigeert. */
export interface RegistratieOut {
  id: number;
  voornaam: string;
  achternaam: string;
  email: string;
  userid_voorstel: string;
  // "afgewezen" bestaat niet: afwijzen verwijdert de aanvraag.
  status: "aangevraagd" | "goedgekeurd";
  reden: string | null;
  userid: string | null;
  besloten_door: string | null;
  besloten_op: string | null;
  created: string;
  updated: string;
}

/** Uitkomst per aanvraag bij bulk-goedkeuring: best-effort, dus een botsende userid blokkeert de
 *  rest niet. */
export interface RegistratieBulkRegel {
  id: number;
  ok: boolean;
  userid: string;
  fout: string;
}

// --- Genereerbare API-tokens (admin) ------------------------------------------

export interface ApiTokenOut {
  id: string;
  label: string;
  token_prefix: string;
  scope: string;
  active: boolean;
  created_by: string;
  created: string;
  last_used: string | null;
}

/** Antwoord bij genereren: het volledige token wordt eenmalig getoond en nergens bewaard. */
export interface ApiTokenCreated extends ApiTokenOut {
  token: string;
}

/** Eigen account (self-service); spiegelt /v1/auth/me. */
export interface MeAccount {
  userid: string;
  email: string;
  role: Role;
  totp_enabled: boolean;
}

export interface TotpBegin {
  otpauth_uri: string;
}

/** Uitkomst van de login-pre-check (/api/login-verify). code: "" | "ok" | "invalid" | "totp_required" | "rate". */
export interface LoginVerifyResult {
  ok: boolean;
  code: string;
  userid: string;
  email: string;
  role: Role | "";
}

// --- API-fout doorgegeven door de BFF ---------------------------------------

export interface ApiError {
  status: number;
  /** De leesbare reden. Bij een gestructureerde fout is dit het `melding`-veld eruit; alleen als
   *  dat ontbreekt valt hij terug op de ruwe JSON. */
  detail: string;
  retryAfter?: number;
  /** `detail.reden` bij een gestructureerde fout: "budget_op", "run_loopt_al", … */
  reden?: string;
  /** Het volledige `detail`-object, zodat de aanroeper er losse velden uit kan lezen zonder de
   *  string opnieuw te parsen. */
  data?: Record<string, unknown>;
}

// --- Annotatie-domein: het weergavemodel van het artefact (zie lib/annotatieNodeAdapter.ts) ---

export type Lifecycle =
  | "voorgesteld" | "human_approved" | "edited" | "rejected" | "published" | "reused";
export type BeslissingType = "approve" | "edit" | "reject" | "comment" | "heropen" | "grens";
export type ReviewReason =
  | "verkeerde_klasse" | "bron_gemist" | "tekst" | "interpretatie" | "onvoldoende_context" | "anders";
export type Aandacht = "groen" | "geel" | "rood";
export type DocumentStatus = "in_review" | "geaccordeerd" | "gepromoveerd";

export interface Alternatief {
  klasse: string;
  motivatie: string;
}

/** Het herkomstspoor van één element, zoals de annotatieketen het meegeeft (graph-qa
 *  `jas_pipeline/keten.py:_spoor`). Alles optioneel: een handmatige markering heeft geen spoor, en
 *  de api bewaart het zoals het binnenkwam. De codes vertaalt `lib/verklaringen.ts`. */
export interface ElementTrace {
  pijplijn?: string;
  jas_versie?: string;
  kandidaat?: {
    id?: string;
    label?: string;
    mogelijke_klassen?: string[];
    /** Beoordeeld zonder zinsontleding: alleen de lexicale detectoren spraken mee. */
    gedegradeerd?: boolean;
    bewijs?: { detector: string; code: string; regel?: string; relatie?: string; detail?: string }[];
    spanopties?: { soort: string; start: number; eind: number }[];
  };
  /** `door`: regel | model | specificiteit. `reden` is bij `specificiteit` het regel-id. */
  beslissing?: { status?: string; klasse?: string; optie?: string; door?: string; reden?: string } | null;
  oorspronkelijke_beslissing?: ElementTrace["beslissing"];
  /** De exacte regel die het model over deze kandidaat zag; leeg als er geen model aan te pas kwam. */
  vraag?: string;
  twijfel?: { reden: string; huidig?: string; alternatieven?: string[]; detail?: string; categorie?: string }[];
  resolutie?: { reden?: string; actie?: string; regel: string; van?: string; naar?: string; motivering?: string }[];
  validatie?: { code: string; detail?: string; ernst?: string }[];
}

export interface Beslissing {
  type: BeslissingType;
  actor: string;
  tijd: string;
  review_reason?: ReviewReason | null;
  comment: string;
  wijziging: Record<string, unknown>;
}

/** De herkomst van één agent-ronde: wélk model de voorstellen maakte.
 *  Komt als `run`-SSE-event uit graph-qa en gaat mee in de PUT naar de api, die het op het
 *  document én op elk element vastlegt. Zonder dit is achteraf niet te zeggen waar een markering
 *  vandaan komt – precies wat de export en de latere graaf-promotie nodig hebben. */
export interface AgentRun {
  ronde: number;
  model: string;
  provider: string;
  agent_versie: string;
  stop_reden: string;
  /** "" (oud) | nieuw | opnieuw | hergebruik – wat deze ronde deed. */
  modus?: string;
  /** De leden die deze ronde (her)annoteerde of hergebruikte. */
  leden?: string[];
  prompt_hash?: string;
  methode_versie?: string;
  /** De meting van de beurt (graph-qa `nodes/annotatie.py:_instellingen`); de tijdlijn leest er de
   *  beurtsamenvatting uit. */
  instellingen?: { meting?: BeurtMeting };
  tijd: string;
}

export interface BeurtMeting {
  fasen?: { fase: string; samenvatting: string; ms: number }[];
  /** Bronnodes die zonder zinsontleding zijn beoordeeld. */
  gedegradeerd?: string[];
  reviewload?: { human_review?: number; juridisch?: number; technisch?: number };
  deterministisch?: number;
}

/** Waar een fragment stond toen het werd gemaakt: exacte offsets + quote-met-context als vangnet. */
export interface Anker {
  lid: string;
  start: number;
  eind: number;
  voor: string;
  na: string;
  bron_hash: string;
  /** Hash van alleen het lidsegment: daaraan ziet de gedeelde laag of dít lid veranderde. */
  lid_hash?: string;
}

export interface AnnotatieElement {
  id: string;
  klasse: string;
  tekst: string;
  lid: string;
  toelichting: string;
  vindplaats: string;
  /** Wie het element AANMAAKTE (agent | mens) – verandert nooit. */
  herkomst: string;
  /** Wie het daarna inhoudelijk aanpaste ("" | agent | mens). */
  gewijzigd_door: string;
  lifecycle: Lifecycle;
  alternatieven: Alternatief[];
  aandacht?: Aandacht | null;
  /** De uitleg van de gerichte review bij een twijfelgeval (resolver, ADR-001). */
  review_uitleg?: string;
  /** Waarom dit element er staat; zie `ElementTrace` en de Waarom-uitklap. */
  trace?: ElementTrace;
  jas_subtype?: string;
  /** De andere grenzen die de keten voor deze kandidaat voorstelde, als tekst (zie `grensOpties`).
   *  `index` is de positie in `trace.kandidaat.spanopties` – dat is wat de api terugkrijgt. */
  grensopties?: { index: number; soort: string; tekst: string }[];
  anker?: Anker | null;
  diff: Record<string, { voor: unknown; na: unknown }>;
  beslissingen: Beslissing[];
  /** null = markering van de jurist, of een agent-ronde van vóór de registratie. */
  geproduceerd_door?: AgentRun | null;
  /** De wettekst van dit lid is sinds de annotatie veranderd. Het oordeel blijft als historie
   *  staan, maar de markering is alleen-lezen en hoort niet meer in de werkvoorraad. */
  verouderd?: boolean;
  verouderd_op?: string | null;
}

export interface AnnotatieDocument {
  slug: string;
  user_id: string;
  client_id: string;
  /** Naam van de regeling zoals hij in beeld komt; los van `werkgebied` (het kennisdomein). */
  citeertitel: string;
  werkgebied: string;
  bwbId: string;
  artikel: string;
  lid: string;
  status: DocumentStatus;
  elementen: AnnotatieElement[];
  /** Het productiespoor: elke agent-ronde die aan dit document werkte. */
  runs: AgentRun[];
  /** De brontekstversies waar de ankers van dit document over gaan (`anker.bron_hash`).
   *
   *  Eén waarde is normaal. Méér betekent dat er opnieuw is geïmporteerd terwijl er al geannoteerd
   *  was, en dan wijzen de offsets van de oudere markeringen naar tekst die verschoven is – de
   *  markering springt dan naar een ander voorkomen of verdwijnt. Door de api afgeleid en niet
   *  opgeslagen; oudere responses kennen het veld niet, vandaar optioneel. */
  bronversies?: string[];
  /** Gevuld = de gedeelde laag van één artikel (voor iedereen, niet te verwijderen). */
  laag_sleutel?: string;
  created?: string | null;
  updated?: string | null;
}

/** Eén regel in het annotatie-overzicht: naam, voortgang en de JAS-verdeling voor de kleurstrip,
 *  zodat de lijst zonder tweede call kan tonen wat er nog te beoordelen is. */
export interface DocumentSamenvatting {
  bron_iri?: string;
  label?: string;
  snapshot_id?: string;
  slug: string;
  bwbId: string;
  artikel: string;
  lid: string;
  /** Weergavenaam; de server valt terug op werkgebied en dan bwbId. */
  citeertitel: string;
  werkgebied: string;
  status: DocumentStatus;
  aantal_elementen: number;
  te_beoordelen: number;
  per_aandacht: Record<string, number>;
  per_klasse: Record<string, number>;
  /** Leeg = geen agent-ronde geregistreerd (of alleen eigen werk). */
  laatste_model: string;
  /** Gevuld = gedeelde laag. */
  laag_sleutel?: string;
  /** Markeringen bij een oudere versie van de wettekst. */
  verouderd?: number;
  updated?: string | null;
}

/** Lex hergebruikte (een deel van) de gedeelde laag: die leden waren al geannoteerd en de wettekst
 *  is sindsdien niet veranderd. Komt als `hergebruik`-event, vóór `opgeslagen`. */
export interface AgentHergebruik {
  slug: string;
  leden: string[];
  /** Alles kwam uit de laag – er is niets nieuws geannoteerd. */
  volledig: boolean;
  bijgewerkt: string;
  telling: { markeringen: number; beoordeeld: number; afgewezen: number; te_beoordelen: number };
}

export interface Wijziging {
  klasse?: string | null;
  tekst?: string | null;
  toelichting?: string | null;
  lid?: string | null;
  // Hoort bij `tekst`: kort de jurist een markering in of breidt hij hem uit, dan schuift de plek
  // mee. Verandert de tekst zonder anker, dan wist de server het oude – een anker dat over het oude
  // fragment gaat zou de markering na herladen naar een ander voorkomen laten springen.
  anker?: Anker | null;
}

export interface BeslissingInvoer {
  type: BeslissingType;
  review_reason?: ReviewReason | null;
  comment?: string;
  wijziging?: Wijziging | null;
}

// --- Unified agent + artikeltekst uit de graaf (graph-qa) --------------------

/** Het doel dat de ophaal-agent heeft opgehaald (uit het `doel`-SSE-event), incl. de opgehaalde tekst
 *  zodat het documentpaneel precies dát toont (ook beleidsregels/divisies zoals '9.1'). */
export interface AgentDoel {
  bron_iri?: string;
  snapshot_id?: string;
  label?: string;
  bwbId: string;
  artikel: string;
  lid: string;
  nummer?: string;
  citeertitel?: string;
  leden_teksten?: { lid: string; tekst: string }[];
}

/** De bepaling die geannoteerd moet worden, meegestuurd bij het starten van een run.
 *
 *  Weet de werkplek hem al (een gekozen kandidaat, een open document), dan slaat de agent de
 *  supervisor én de ophaal-agent over. Het echte winstpunt is niet de besparing maar de zekerheid:
 *  de agent kan dan niet meer bij een ándere bepaling uitkomen dan de jurist aanwees.
 *  Spiegelt `AgentDoel` in `tools/graph-qa/agent/models.py`.
 */
export interface AgentDoelInvoer {
  bron_iri?: string;
  snapshot_id?: string;
  label?: string;
  bwbId: string;
  artikel?: string;
  lid?: string;
  nummer?: string;
  citeertitel?: string;
}

/** Een bepaling die de agent vond bij een ONDERWERP-vraag (uit het `kandidaten`-SSE-event).
 *
 *  De agent kiest er zelf geen: welke bepaling de werkvoorraad in gaat, bepaalt de jurist.
 */
export interface AgentKandidaat {
  bwbId: string;
  artikel: string;
  lid?: string;
  citeertitel?: string;
  fragment?: string;
  /** Bij een keuze uit de onderdelen van één bepaling (`keuze` op het event): de bronnode zelf,
   *  zodat de gekozen beurt niets meer hoeft op te zoeken. */
  bron_iri?: string;
  nummer?: string;
  soort?: string;
  label?: string;
  /** Hoe ver het werk aan dit onderdeel is; ontbreekt als de api het niet betrouwbaar wist. */
  stand?: KandidaatStand;
  /** De vraag noemde dit onderdeel al ("lid 1 en 3"): vooraf aangevinkt. */
  gekozen?: boolean;
}

export interface KandidaatStand {
  status: "nieuw" | "te_beoordelen" | "beoordeeld" | "afgerond";
  voorstellen: number;
  te_beoordelen: number;
}

/** Wat voor keuze de kandidaten vormen. Zonder dit veld: bepalingen bij een ONDERWERP-vraag.
 *  `onderdeel` = leden of subbepalingen van één bepaling (meerdere kiezen mag, `alles` biedt ze
 *  allemaal); `bepaling` = een dubbelzinnig nummer, precies één kiezen. */
export interface AgentKeuze {
  soort: "onderdeel" | "bepaling";
  ouder: string;
  alles: boolean;
}

/** Context bij een adviesvraag of een annotatie: waar gaat het over. */
export interface AgentContext {
  bron_iri?: string;
  snapshot_id?: string;
  slug?: string;
  bwbId?: string;
  artikel?: string;
  lid?: string;
  element_id?: string;
  klasse?: string;
  fragment?: string;
  corpus?: string;
  bestaande_elementen?: { id: string; klasse: string; tekst: string; lid: string; herkomst: string }[];
}

/** Een bron onder een agent-antwoord (uit het `sources`-SSE-event). */
export interface Bron {
  label: string;
  uri: string;
  /** Sinds de canonieke bronnen van graph-qa (additief; oudere berichten hebben ze niet): de
   *  bronnode volgens `bronmodel.vindplaats`, de jci voor de link en de naam van de regeling. */
  bron_iri?: string;
  jci?: string | null;
  bwb_id?: string;
  soort?: string;
  regeling?: string | null;
}

/** De uitkomst van de brongetrouwheidstoets op één antwoord (graph-qa `grounding`-event).
 *
 *  `niveau` is de waarde om te tonen, niet `grounded`: **onbepaald** betekent dat het antwoord geen
 *  enkele vindplaats of citaat noemde en er dus niets te controleren viel. Dat als "gecontroleerd"
 *  presenteren zou schijnzekerheid zijn – precies wat dit platform wil vermijden. */
export interface AgentGrounding {
  niveau: "gegrond" | "onbepaald" | "ongegrond";
  grounded: boolean;
  cited: number;
  /** Verwijzingen die niet in de graafresultaten voorkwamen. */
  unsupported: string[];
  /** Als citaat gepresenteerde tekst die niet letterlijk in de opgehaalde tekst staat. */
  niet_letterlijk: string[];
}

/** Artikeltekst uit de graaf (weergave == annotatie-corpus). */
export interface GraafArtikel {
  bwbId: string;
  artikel: string;
  citeertitel: string;
  opschrift: string;
  leden_teksten: { lid: string; tekst: string }[];
  /** Knooptype uit de graaf: "Artikel" of "Divisie". Stuurt alleen de bewoording van de
   *  vindplaats — een divisie van een beleidsregel is geen artikel en heeft geen leden.
   *  Optioneel: een oudere graph-qa stuurt het niet mee, en dan geldt de terugval "artikel". */
  soort?: string;
}

/** Eén voorgesteld element uit de graph-qa annotatie-SSE (nog niet gepersisteerd). */
export interface VoorstelElement {
  /** Stabiel id van de agent. Hierop matcht de server bij een volgende ronde, zodat beslissingen en
   *  levenscyclus behouden blijven. Ontbreekt het, dan valt de server terug op de tekst. */
  id?: string;
  klasse: string;
  tekst: string;
  lid: string;
  toelichting: string;
  vindplaats: string;
  alternatieven: Alternatief[];
  grounded: boolean;
  aandacht?: Aandacht;   // geel = keuze voor de jurist, groen = door de review bevestigd; afwezig = gewoon voorstel
  review_uitleg?: string;       // uitleg van de gerichte review
}

/** Eén agent-beurt als server-object (graph-qa `/v1/runs`).
 *
 *  De run leeft bij de agent, niet in het tabblad: wegklikken of herladen koppelt alleen de kijker
 *  los. `vraag` reist mee omdat een tabblad dat halverwege aanhaakt anders tokens uit het niets
 *  krijgt, en `volgende_seq`/`weggevallen` zeggen waar de eventlog staat zodat aanhaken op het
 *  juiste punt begint. */
export interface RunStart {
  run_id: string;
  conversation_id: string;
  vraag: string;
  status: "loopt" | "klaar" | "gestopt" | "mislukt";
  volgende_seq: number;
  weggevallen: number;
}

// --- Gesprekken (chatgeschiedenis) – afgeleid van api/app/gesprek_contracts.py ---

export type Rol = "user" | "assistant";

/** Eén beurt in een gesprek. Assistent-berichten dragen optioneel denkproces/bronnen, of het
 *  **artefact** dat de beurt opleverde (`artefact`: annotatie, begripsvoorstellen, later regels –
 *  zie `lib/artefact.ts`). Het artefact draagt een eigen `titel`: wordt wat erachter zit later
 *  verwijderd, dan blijft er in de thread een leesbare kaart staan in plaats van een naamloze
 *  verwijzing.
 *
 *  Oudere berichten verwijzen nog via `annotatie_doel` (een bronnode) of alleen een
 *  `annotatie_slug` (een annotatie die niet meer bestaat: de tombstone). */
export interface Bericht {
  artefact?: import("./artefact").Artefact | null;
  annotatie_doel?: import("./annotatieNode").NodeDoel;
  tool_executions?: import("./annotatieNode").ToolExecution[];
  id?: number;
  rol: Rol;
  tekst: string;
  denk: string;
  bronnen: Bron[];
  annotatie_slug?: string;
  annotatie_titel?: string;
  /** Lex hergebruikte (een deel van) de gedeelde laag; zelfde vorm als het `hergebruik`-event
   *  (maar met de leden zoals graph-qa ze stuurde – zie `parseHergebruik`). */
  hergebruik?: unknown;
  /** Het overzicht van een onderwerp; zelfde vorm als het `overzicht`-event (zie `parseOverzicht`). */
  overzicht?: unknown;
  /** Wat de annotatieketen kon bekijken, met de fasen en hun duur; de werkplek leest er alleen de
   *  meting uit (`metingUitDekking`). */
  dekking?: unknown;
  /** Van welke agent-run deze beurt de uitkomst is; de api gebruikt het als idempotentiesleutel,
   *  zodat twee meekijkende tabbladen niet elk hun eigen kopie wegschrijven. */
  run_id: string;
  /** Dit bericht is één onderdeel van een reeks (meerdere leden van één artikel in één run). De
   *  werkplek toont de berichten met dezelfde `reeks.run_id` samen als één reeksblok. */
  reeks?: ReeksPlek | null;
  /** Een opdracht die Lex niet zonder akkoord start (fase B): de werkplek toont er een knop bij. */
  bevestiging?: Bevestiging | null;
  created?: string;
}

/** Een opdracht die Lex niet zonder akkoord start; klikken start de run met `bevestigd: aantal`. Is de
 *  werkvoorraad intussen veranderd, dan weigert graph-qa en komt er een nieuwe bevestiging.
 *  `werkgebied_annoteren` (fase B): de nieuwe bepalingen annoteren. `begrippen_verdiepen` (fase C):
 *  meedenken over twijfelpunten en begrippen zonder definitie; `aantal` telt die samen. */
export interface Bevestiging {
  soort: "werkgebied_annoteren" | "begrippen_verdiepen";
  werkgebied_id: string;
  aantal: number;
  /** Tokens voor deze run, of `null` zonder eerdere annotatiebeurten om op te baseren. */
  schatting: number | null;
}

/** Stand van één annotatie-eenheid (een lid, of een artikel zonder leden) in een werkgebied. */
export type EenheidStatus = "nieuw" | "te_beoordelen" | "beoordeeld" | "zonder_markeringen" | "afgerond";

export interface WerkvoorraadEenheid {
  bron_iri: string;
  /** Het pad onder de regeling: "Artikel 9, Lid 1". */
  label: string;
  regeling: string;
  bwb_id: string;
  stand: { status: EenheidStatus; voorstellen: number; te_beoordelen: number };
  selecties: string[];
}

/** `GET /v1/werkgebieden/{id}/annotatie-werkvoorraad` (api `werkgebied_werkvoorraad.py`). */
export interface AnnotatieWerkvoorraad {
  werkgebied_id: string;
  revisie: number;
  naam: string;
  selecties: { id: string; bron_iri: string; label: string; bereik: BronBereik; eenheden: number;
    per_stand: Partial<Record<EenheidStatus, number>>; onbereikbaar: string | null }[];
  eenheden: WerkvoorraadEenheid[];
  te_annoteren: string[];
  context_niet_meegenomen: number;
  volledig: boolean;
  open_punten: string[];
  schatting: { per_bepaling: number; basis: number; totaal: number } | null;
  schatting_toelichting: string;
  budget: { resterend: number; budget: number; actief: boolean; geblokkeerd: boolean };
}

/** Het overzicht van een onderwerp ("welke artikelen gaan over invordering?"), door graph-qa
 *  deterministisch uit de graaf opgebouwd (`tools/graph-qa/agent/overzicht.py`). De werkplek toont
 *  het zoals het is: geen bereiken, geen samenvatting – elk nummer met zijn eigen vindplaats. */
export interface OverzichtBepaling { iri: string; nummer: string; label: string; jci?: string;
  /** Zoals de jurist haar leest ("art. 9", "28.3a"), door graph-qa gezet; ontbreekt bij oudere berichten. */
  naam?: string;
  /** Alleen bij "ook genoemd": het meest specifieke deel waarin de bepaling staat. */
  in_deel?: { iri: string; label: string } }
export interface OverzichtDeel { iri: string; soort: string; label: string; jci: string;
  /** "Hoofdstuk II – …", "28 – Invorderingsrente"; door graph-qa gezet, ontbreekt bij oudere berichten. */
  kop?: string;
  bepalingen: OverzichtBepaling[]; subdelen: { iri: string; label: string }[] }
export interface OverzichtRegeling { bwb_id: string; citeertitel: string; soort: string;
  delen: OverzichtDeel[]; ook_genoemd: OverzichtBepaling[] }
export interface Overzicht {
  /** Wat er gevraagd werd, en waarop er in opschriften en tekst gezocht is (elk het langste begin
   *  van het onderwerp dat iets opleverde). */
  gevraagd: string; onderwerp_opbouw: string; onderwerp_tekst: string;
  /** De regelingen die de vraag bij naam noemde (afbakening); leeg = alle. */
  scope: string[];
  /** False als het overzicht zijn plafond raakte. */
  volledig: boolean;
  definities: { iri: string; begrip: string; label: string; tekst: string; jci: string; bwb_id: string; citeertitel: string;
    /** "Artikel 2, lid 2, onderdeel e" (graph-qa, uit `bronmodel.vindplaats`). */
    vindplaats?: string }[];
  trefwoorden: { trefwoord: string; regelingen: { bwb_id: string; citeertitel: string }[] }[];
  regelingen: OverzichtRegeling[];
}

/** Spiegelt `ReeksPlek` in api/app/gesprek_contracts.py. */
export interface ReeksPlek {
  run_id: string;
  index: number;
  totaal: number;
  ouder: string;
}

/** Eén chat-gesprek met zijn berichten (volledig geladen). */
export interface Gesprek {
  id: string;
  user_id: string;
  titel: string;
  berichten: Bericht[];
  created?: string;
  updated?: string;
}

/** Lichte lijst-weergave voor de sidebar (chatgeschiedenis). */
export interface GesprekSamenvatting {
  id: string;
  titel: string;
  aantal_berichten: number;
  updated?: string;
}

/** Eén toe te voegen bericht (append). */
export interface BerichtInvoer {
  artefact?: import("./artefact").Artefact;
  annotatie_doel?: import("./annotatieNode").NodeDoel;
  tool_executions?: import("./annotatieNode").ToolExecution[];
  rol: Rol;
  tekst?: string;
  denk?: string;
  bronnen?: Bron[];
  annotatie_slug?: string;
  annotatie_titel?: string;
  run_id?: string;
}

// --- Berichtensysteem --------------------------------------------------------
//
// LET OP – twee soorten "bericht" in deze codebase, met eigen API-domeinen:
//   • `Bericht` / `BerichtInvoer` hierboven = een **chatbeurt** in de werkplek
//     (`/v1/gesprekken/{id}/berichten`).
//   • `BerichtOut` en de rest hieronder = een **release note / aankondiging** die een beheerder
//     publiceert en analisten lezen (`/v1/berichten`).
// De namen komen uit de API; ze verwijzen naar niets gemeenschappelijks.

export type BerichtType = "info" | "update" | "waarschuwing" | "kritiek";

/** Gepubliceerd bericht met leesstatus (voor analisten). */
export interface BerichtOut {
  id: number;
  titel: string;
  inhoud: string;
  type: BerichtType;
  versie: string | null;
  gepubliceerd: boolean;
  gepubliceerd_op: string | null;
  gelezen: boolean;
  created: string;
  updated: string;
}

/** Bericht zonder leesstatus (voor admin-beheerlijst). */
export type AdminBerichtOut = Omit<BerichtOut, "gelezen"> & { aangemaakt_door: string };

export interface OngelezenAantalOut {
  aantal: number;
}

export interface BerichtenPaginaOut {
  items: BerichtOut[];
  totaal: number;
  pagina: number;
  per_pagina: number;
}

export interface AdminBerichtenPaginaOut {
  items: AdminBerichtOut[];
  totaal: number;
  pagina: number;
  per_pagina: number;
}

export interface BerichtAanmakenIn {
  titel: string;
  inhoud: string;
  type: BerichtType;
  versie?: string | null;
}

export interface BerichtPublicatieIn {
  gepubliceerd: boolean;
}

// --- Werkgebieden (spoor D, levering 1) – afgeleid van api/app/werkgebied_contracts.py en de
// vormen in werkgebied_store.py / werkgebied_inventaris.py ---

export type WerkgebiedStatus = "in_voorbereiding" | "actief" | "afgerond";
export type BronBereik = "node" | "onderliggend";
export type BronRol = "analyseren" | "context";

export interface Bronselectie {
  id: string;
  bron_iri: string;
  bereik: BronBereik;
  rol: BronRol;
  reden: string;
  label: string;
  bwb_id: string;
  snapshot_id: string;
  bron_hash: string;
  toegevoegd_door: string;
  toegevoegd: string;
}

export interface WerkgebiedSamenvatting {
  id: string;
  naam: string;
  analysevraag: string;
  afbakening: string;
  peildatum: string | null;
  status: WerkgebiedStatus;
  revisie: number;
  aangemaakt_door: string;
  aangemaakt: string;
  gewijzigd: string;
  gearchiveerd: string | null;
  /** Alleen in de lijst. */
  aantal_bronnen?: number;
}

export interface Werkgebied extends WerkgebiedSamenvatting {
  bronnen: Bronselectie[];
  /** Optioneel (open keuze 4): actieve deelvragen en open voorstellen van Lex. Een oudere api stuurt
   *  het veld niet; lees het daarom als `wg.deelvragen ?? []`. */
  deelvragen?: Deelvraag[];
}

/** Gelijk aan `api/app/werkgebied_deelvragen.py:_deelvraag`. `bronnen` en `begrippen` zijn de id's van
 *  bronselecties en begrippen die bij deze deelvraag horen (alleen wat nog bestaat). */
export interface Deelvraag {
  id: string;
  vraag: string;
  volgorde: number;
  status: "actief" | "voorgesteld";
  herkomst: "analist" | "lex";
  reden: string;
  aangemaakt_door: string;
  aangemaakt: string;
  bronnen: string[];
  begrippen: string[];
}

export type DeelvraagStand = "gedekt" | "geen_begrip" | "geen_bron";

/** `GET …/deelvragen/dekking`: per actieve deelvraag of er een bron en een geaccordeerd begrip bij hoort. */
export interface DeelvragenDekking {
  deelvragen: {
    id: string;
    vraag: string;
    stand: DeelvraagStand;
    bronnen: { id: string; label: string }[];
    begrippen: { id: string; naam: string; status: BegripStatus }[];
  }[];
  telling: Record<DeelvraagStand, number>;
  totaal: number;
}

export interface WerkgebiedInvoer {
  naam: string;
  analysevraag?: string;
  afbakening?: string;
  peildatum?: string | null;
}

export interface WerkgebiedWijziging {
  verwachte_revisie: number;
  naam?: string;
  analysevraag?: string;
  afbakening?: string;
  peildatum?: string | null;
  status?: WerkgebiedStatus;
}

/** Een bepaling opnemen: via de bron-IRI, of via regeling + artikel (+ lid). */
export interface BronselectieInvoer {
  verwachte_revisie: number;
  bron_iri?: string;
  bwb_id?: string;
  artikel?: string;
  lid?: string;
  bereik?: BronBereik;
  rol?: BronRol;
  reden?: string;
}

/** Per selectie in de inventaris. `onbereikbaar` is een open punt, geen kleinere inventaris. */
export interface InventarisSelectie {
  id: string;
  bron_iri: string;
  label: string;
  rol: BronRol;
  bereik: BronBereik;
  aantal: number;
  afgewezen: number;
  bron_gewijzigd: boolean;
  onbereikbaar: string | null;
}

export interface InventarisElement {
  id: string;
  klasse: string;
  tekst: string;
  lifecycle: Lifecycle;
  aandacht?: Aandacht;
  jas_subtype?: string;
  eigenaar_iri: string;
  laag_id: string;
  ankers: { bron_iri: string; start: number; eind: number; tekst?: string }[];
  verouderd?: boolean;
  toelichting?: string;
  /** `analyseren` als een analyse-selectie het element dekt, anders `context`. */
  rol: BronRol;
  selecties: string[];
  /** Een anker valt buiten de selecties: gemeld, niet stil verbreed. */
  deels_buiten: boolean;
}

export interface Inventaris {
  werkgebied_id: string;
  revisie: number;
  selecties: InventarisSelectie[];
  elementen: InventarisElement[];
  volledig: boolean;
}

export interface WerkgebiedAuditRegel {
  id: number;
  actor: string;
  actie: string;
  detail: Record<string, unknown>;
  tijdstip: string;
}

// --- Begrippen (spoor D, levering 2) – afgeleid van api/app/begrip_contracts.py en de vormen in
// begrip_store.py ---

export type DefinitieHerkomst = "letterlijk" | "samengesteld" | "geformuleerd";
export type VoorbeeldOordeel = "wel" | "niet" | "onzeker";
export type KoppelRol = "duiding" | "definitie" | "context";
export type KoppelBeoordeling = "open" | "akkoord" | "afgewezen";
export type Actualiteit = "actueel" | "gewijzigd" | "verworpen" | "verdwenen";
/** `vervangen` (fase F2): alleen-lezen, opgevolgd door een ander begrip (nieuwe betekenis, combineren). */
export type BegripStatus = "concept" | "geaccordeerd" | "vervangen";

export interface Voorbeeld {
  tekst: string;
  oordeel: VoorbeeldOordeel;
  toelichting: string;
}

/** Werkindeling (PLAN §D), geen JAS-klasse. */
export type Begripstype = "entiteit" | "actor" | "toestand" | "gebeurtenis" | "eigenschap" | "relatie";

export interface BegripInhoud {
  naam: string;
  alternatieve_termen: string[];
  context: string;
  /** Leeg = nog niet ingedeeld. Oudere begrippen hebben het veld niet. */
  begripstype?: Begripstype | "";
  jas_klasse: string;
  jas_subtype: string;
  geldigheid: string;
  definitie: string;
  definitie_herkomst: DefinitieHerkomst | null;
  /** Wie de definitie voorstelde (fase E); de api zet het, nooit de client. Oudere begrippen missen het. */
  definitie_door?: "" | "analist" | "lex";
  uitleg: string;
  onderbouwing: string;
  voorbeelden: Voorbeeld[];
  eigenschappen: Record<string, string>;
  open_vragen: string[];
}

/** De bewaarde bewijsstand van een passage: zo zag het element eruit toen het gekoppeld werd. */
export interface Bewijs {
  tekst: string;
  klasse: string;
  jas_subtype?: string;
  ankers: { bron_iri: string; start: number; eind: number; tekst?: string; bron_hash?: string }[];
  eigenaar_iri: string;
  laag_id: string;
  snapshot_id: string;
  lifecycle: string;
  vindplaats: string;
  element_hash: string;
}

export interface Koppeling {
  id: string;
  begrip_id: string;
  element_id: string;
  rol: KoppelRol;
  motivatie: string;
  bewijs: Bewijs;
  beoordeling: KoppelBeoordeling;
  beoordeeld_door: string | null;
  beoordeeld_op: string | null;
  toegevoegd_door: string;
  toegevoegd: string;
  /** Bij het lezen bepaald, tegen het element zoals het nu is. */
  actualiteit: Actualiteit;
  lifecycle_nu: string | null;
  annotatie_beoordeeld: boolean;
  /** Herbeoordeling (fase F1): de analist zag de veranderde passage en het begrip klopt nog. Het
   *  bewijs zelf verandert nooit; de nieuwste bevestiging is de stand waartegen de api rekent. */
  bevestigingen?: KoppelBevestiging[];
  /** Deze koppeling verving een eerdere bij herkoppelen; diens bewijs blijft zo leesbaar. */
  vervangt?: { koppeling_id: string; element_id: string; bewijs: Bewijs; vervangen_op: string | null };
}

export interface KoppelBevestiging {
  element_hash: string;
  tekst: string;
  klasse: string;
  door: string;
  op: string;
  motivatie: string;
}

// --- Onderhoud van begrippen (spoor D, fase F1) ------------------------------------------------

export type Richting = "steun" | "tegen" | "onbeslist";

export interface BronSignaal {
  bron_iri: string;
  vindplaats: string;
  fragment: string;
  /** `onbekend`: de regeling was niet op te halen – een open punt, geen "ongewijzigd". */
  stand: "ongewijzigd" | "gewijzigd" | "weg" | "onbekend";
  tekst_nu?: string;
  fragment_gelijk?: boolean;
}

export interface Opvolger {
  element_id: string;
  tekst: string;
  klasse: string;
  lifecycle: string;
  annotatie_beoordeeld: boolean;
  signalen: { richting: Richting; uitleg: string }[];
}

export type HerbeoordelingsActie = "herkoppelen" | "bevestigen" | "loskoppelen";

export interface GeraakteKoppeling {
  koppeling_id: string;
  element_id: string;
  rol: KoppelRol;
  actualiteit: Actualiteit;
  redenen: string[];
  toen: Pick<Bewijs, "tekst" | "klasse" | "ankers" | "vindplaats" | "lifecycle" | "snapshot_id" | "eigenaar_iri"> & { jas_subtype?: string };
  bevestigingen: KoppelBevestiging[];
  nu: { tekst: string; klasse: string; jas_subtype: string; ankers: Bewijs["ankers"]; lifecycle: string; verouderd: boolean } | null;
  bron: BronSignaal[];
  opvolgers: Opvolger[];
  opnieuw_annoteren: string[];
  acties: HerbeoordelingsActie[];
}

export interface Herbeoordelingen {
  werkgebied_id: string;
  begrippen: {
    begrip_id: string; naam: string; status: BegripStatus; revisie: number; koppelingen: GeraakteKoppeling[];
    /** Doorwerking (fase F2): vastgelegde relaties waarvan de andere kant veranderde. */
    relaties?: GeraakteRelatie[];
  }[];
  volledig: boolean;
  open_punten: { bron_iri: string; label: string; melding: string }[];
}

export interface GeraakteRelatie {
  relatie_id: string;
  type: RelatieType;
  ander: { begrip_id: string; naam: string };
  reden: string;
}

// --- Begripsrelaties (spoor D, fase F2) ---------------------------------------------------------

export type RelatieType = "kwalificatie" | "inclusie" | "uitsluiting" | "hierarchie" | "verwant" | "opvolging";

export interface BegripRelatie {
  id: string;
  van_begrip: string;
  naar_begrip: string;
  van_naam: string;
  naar_naam: string;
  type: RelatieType;
  herkomst: "lex" | "analist" | "systeem";
  beoordeling: "akkoord" | "afgewezen" | "voorgesteld";
  toelichting: string;
  bewijs: {
    run_id?: string; kandidaat_id?: string; aandacht?: "groen" | "geel"; uitleg?: string[];
    van?: { element_id: string; tekst: string; vindplaats: string } | null;
    naar?: { element_id: string; tekst: string; vindplaats: string } | null;
    soort?: string; vorige_status?: string;
  };
  door?: string;
  op?: string;
  /** Een kant veranderde sinds het vastleggen (doorwerking). */
  veranderd?: boolean;
}

export interface RelatiesAntwoord {
  relaties: BegripRelatie[];
  voorstellen: BegripRelatie[];
}

export type DekkingStand = "te_verwerken" | "voorstel" | "gekoppeld" | "buiten_behandeling";

export interface DekkingElement {
  element_id: string;
  tekst: string;
  klasse: string;
  rol: BronRol;
  stand: DekkingStand;
  begrippen: { begrip_id: string; naam: string; rol: KoppelRol }[];
  buiten_behandeling: { reden: string; door: string; op: string } | null;
  nieuw_sinds_run: boolean;
}

export interface Dekking {
  werkgebied_id: string;
  totalen: Record<DekkingStand, number>;
  totaal: number;
  nieuw_sinds_run: number;
  laatste_run: string | null;
  elementen: DekkingElement[];
  volledig: boolean;
}

export interface Poort {
  mag: boolean;
  redenen: string[];
}

interface BegripBasis {
  id: string;
  iri: string;
  werkgebied_id: string;
  kader_iri: string;
  status: BegripStatus;
  revisie: number;
  inhoud: BegripInhoud;
  aangemaakt_door: string;
  aangemaakt: string;
  gewijzigd: string;
  geaccordeerd_door: string | null;
  geaccordeerd_op: string | null;
  geaccordeerd_revisie: number | null;
  accorderen: Poort;
  aandachtspunten: string[];
  /** Opvolging (fase F2). Een oudere api laat ze weg. */
  vervangen_door?: BegripVerwijzing | null;
  vervangt?: BegripVerwijzing[];
}

export interface BegripVerwijzing {
  begrip_id: string;
  naam: string;
  reden: string;
}

export interface Begrip extends BegripBasis {
  koppelingen: Koppeling[];
}

export interface BegripSamenvatting extends BegripBasis {
  aantal_koppelingen: number;
  element_ids: string[];
}

export interface BegrippenLijst {
  kader_iri: string;
  begrippen: BegripSamenvatting[];
  /** Per element het begrip dat het primair aanduidt. */
  primair: Record<string, { begrip_id: string; naam: string }>;
}

export interface BegripRevisie {
  revisie: number;
  actie: string;
  detail: Record<string, unknown>;
  status: BegripStatus;
  inhoud: BegripInhoud;
  actor: string;
  tijdstip: string;
}

// --- Voorstellen van Lex (spoor D, levering 3a) – afgeleid van api/app/begrippen_run_contracts.py
// en de vormen in begrippen_run_store.py ---

export type BegrippenRunStatus = "wacht" | "loopt" | "klaar" | "mislukt";
export type GroepBesluit = "open" | "overgenomen" | "gekoppeld" | "afgewezen" | "geparkeerd";

export interface Passage {
  element_id: string;
  tekst: string;
  jas_klasse: string;
  /** De stand van de annotatie bij de run (het manifest). */
  review_status: string;
  bron_iri: string;
  vindplaats: string;
  /** De stand van de annotatie nú (fase D); ontbreekt bij een verdwenen element. */
  lifecycle?: string;
  annotatie_beoordeeld?: boolean;
}



export interface Relatie {
  kandidaat_id: string;
  hypothese: "zelfde_betekenis" | "kwalificatie" | "inclusie" | "uitsluiting" | "hierarchie" | string;
  van: string;
  naar: string;
  aandacht: "groen" | "geel";
  uitleg: string[];
}

export interface TwijfelVraag {
  kandidaat_id: string;
  van: string;
  naar: string;
  regel: string;
  uitleg: string[];
}

export interface BegrippenRun {
  id: string;
  werkgebied_id: string;
  manifest_id: string;
  status: BegrippenRunStatus;
  reden: string;
  overgeslagen: { element_id: string; tekst: string; reden: string }[];
  aantal_formuleringen: number;
  uitkomst: { groep_ids: string[]; relaties: Relatie[]; vragen: TwijfelVraag[]; meting: Record<string, unknown> } | null;
  vragen_besluiten: Record<string, { antwoord: "samen" | "apart"; door: string; op: string }>;
  gestart_door: string;
  gestart: string;
  gewijzigd: string;
  /** Alleen bij `laatste`: geeft het werkgebied nu een ander manifest? `null` = onbekend (graaf weg). */
  verouderd?: boolean | null;
}

// --- De verdieping (fase C) – afgeleid van api/app/begrippen_run_contracts.py ----------------------

export type ModelOordeelSoort = "zelfde_betekenis" | "verwant_ander_begrip" | "betekenisverschil" | "onbeslist";

/** Het advies van Lex bij een twijfelvraag; de jurist beslist. */
export interface ModelOordeel {
  kandidaat_id: string;
  oordeel: ModelOordeelSoort;
  motivatie: string;
  /** Waarom er geen bruikbaar oordeel is (een code), anders leeg. */
  reden: string;
}

/** Een letterlijk stuk brontekst waar een definitie op rust. */
export interface KaartFragment {
  id: string;
  bron_iri: string;
  start: number;
  eind: number;
  tekst: string;
}

/** De concept-kaart bij een groep: een voorstel, nooit een begrip. */
export interface ConceptKaart {
  groep_id: string;
  naam: string;
  alternatieve_termen: string[];
  begripstype: Begripstype | null;
  begripstype_door: "regel" | "model" | "";
  context: string;
  definitie: string;
  herkomst: DefinitieHerkomst | null;
  definitie_bron_iri: string;
  definitie_vindplaats: string;
  fragmenten: KaartFragment[];
  motivatie: string;
  aandacht: "groen" | "geel";
  /** Codes uit graph-qa `toetsen.TEKST`; de werkplek zet ze om (`AANDACHTSPUNT`). */
  aandachtspunten: string[];
}

/** `GET …/verdieping`: wat het model nog moet doen voor de laatste klare run. */
export interface VerdiepingWerkvoorraad {
  run: BegrippenRun | null;
  verdiept: boolean;
  aantal: number;
  vragen: string[];
  kaarten: string[];
  batches: { id: string; soort: "vraag" | "kaart"; ids: string[] }[];
  schatting: { per_item: number; basis: number; totaal: number } | null;
  schatting_toelichting?: string;
  budget: { resterend: number; budget: number; actief: boolean; geblokkeerd: boolean } | null;
}

export interface Betekenisgroep {
  id: string;
  aandacht: "groen" | "geel";
  /** Wie de groep vormde: de beslistabel, of een oordeel van Lex (fase C; altijd geel). */
  door?: "regel" | "model";
  /** De concept-kaart van de verdieping (fase C); `null` zolang er niet is meegedacht. */
  kaart?: ConceptKaart | null;
  voorstel: { naam: string; definitie?: string; definitie_bron_iri?: string; definitie_vindplaats?: string };
  uitleg: string[];
  conflicten: string[];
  besluit: GroepBesluit;
  reden: string;
  begrip_id: string | null;
  besloten_door: string | null;
  /** De leden die nog geen begrip werden; na splitsen blijft de groep open met de rest. */
  leden: Passage[];
  /** Hoeveel leden al een begrip werden (splitsen, fase D). */
  afgehandeld?: number;
  lijkt_op: { begrip_id: string; naam: string; gedeeld: string[] }[];
  /** Wat de poort na een akkoord nog zou tegenhouden (alleen bij een open of geparkeerde groep). */
  poort_vooraf?: Poort | null;
}

/** Wat de jurist bij een akkoord anders wil dan het voorstel (api `Aanpassing`). */
export interface Aanpassing {
  definitie?: string;
  definitie_herkomst?: DefinitieHerkomst;
  context?: string;
  begripstype?: Begripstype | "";
  alternatieve_termen?: string[];
}

/** `POST …/groepen/akkoord` (fase D). */
export interface AkkoordInvoer {
  groep_ids: string[];
  naam: string;
  element_ids?: string[];
  met_definitie?: boolean;
  aanpassing?: Aanpassing;
  definitie_van?: string;
  kandidaat_id?: string;
}

export interface AkkoordAntwoord {
  begrip: Begrip;
  geaccordeerd: boolean;
  poort: Poort;
}

// --- Bronnen vinden met Lex (spoor D, fase A) – afgeleid van api/app/bronnen_run_contracts.py ---

export type BronMethode = "overzicht" | "deelvraag" | "verwijzing_uit" | "verwijzing_in" | "definitie" | "opbouw" | "gelijkenis";
export type KandidaatRol = "kern" | "afhankelijkheid" | "aanverwant";
export type KandidaatStatus = "voorgesteld" | "opgenomen" | "later" | "uitgesloten";

/** Waarom één methode deze bepaling vond. `detail` per methode: verwijzingen `{anker, functie}`,
 *  definitie `{begrip}`, overzicht `{onderwerp}`, opbouw `{deel}`, gelijkenis `{score}`. */
export interface KandidaatBewijs {
  methode: BronMethode;
  vanuit: string;
  detail: { anker?: string; functie?: string; begrip?: string; onderwerp?: string; deel?: string; score?: string;
    deelvraag_id?: string; vraag?: string };
}

export interface BronKandidaat {
  id: string;
  bron_iri: string;
  label: string;
  bwb_id: string;
  rol: KandidaatRol;
  bewijs: KandidaatBewijs[];
  status: KandidaatStatus;
  reden: string;
  run_id: string;
  in_laatste_run: boolean;
  /** Intussen met de hand opgenomen: geen open voorstel meer. */
  in_selectie: boolean;
  besloten_door: string | null;
  besloten_op: string | null;
}

export interface BronnenRun {
  id: string;
  werkgebied_id: string;
  invoer_id: string;
  status: "wacht" | "loopt" | "klaar" | "mislukt";
  reden: string;
  meting: Partial<Record<BronMethode, { aantal: number; volledig: boolean; ms?: number }>> | null;
  aantal_kern: number;
  gestart: string;
  /** Alleen bij `laatste`: veranderde de selectie of de analysevraag sinds deze run? */
  verouderd?: boolean;
}

export interface KandidatenAntwoord {
  run: BronnenRun | null;
  kandidaten: BronKandidaat[];
}

export interface GroepenAntwoord {
  run: BegrippenRun | null;
  groepen: Betekenisgroep[];
  /** De passages die twijfelvragen en relaties noemen, ook buiten een groep. */
  passages: Record<string, Passage>;
  /** Na de verdieping (fase C): de vragen die open blijven en het advies van Lex per vraag. */
  verdieping?: { vragen_open: string[]; oordelen: Record<string, ModelOordeel>; model: string; op?: string } | null;
}

// --- Lex naast de kaart (spoor D, fase E) ------------------------------------------------------

export type KaartActie = "brondefinitie" | "scherper" | "betekenisverschil" | "voorbeelden";
export type KaartVeld = "definitie" | "uitleg" | "open_vragen" | "voorbeelden";
export type VindplaatsSoort = "" | "werkgebied" | "regeling" | "definitieverwijzing" | "elders";

/** Een definitie zoals Lex haar voorstelt (`api/app/begrip_voorstel_contracts.DefinitieWaarde`). */
export interface DefinitieWaarde {
  definitie: string;
  herkomst: DefinitieHerkomst;
  fragmenten: KaartFragment[];
  definitie_bron_iri: string;
  definitie_vindplaats: string;
  vindplaats_soort: VindplaatsSoort;
}

/** De waarde van een voorstel voor uitleg, een open vraag of een voorbeeld. */
export interface TekstWaarde {
  tekst: string;
  fragmenten: KaartFragment[];
  oordeel?: VoorbeeldOordeel;
  toelichting?: string;
  vergelijking?: "zelfde_betekenis" | "verwant" | "verschil" | "onbeslist";
}

export interface KaartVoorstel {
  id: string;
  begrip_id: string;
  run_id: string;
  actie: KaartActie;
  veld: KaartVeld;
  volgorde: number;
  basis: { revisie: number; definitie: string; definitie_herkomst: DefinitieHerkomst | null };
  waarde: DefinitieWaarde | TekstWaarde;
  motivatie: string;
  aandacht: "groen" | "geel";
  aandachtspunten: string[];
  door: { bron: "model" | "graaf"; model: string; promptversie: string };
  status: "open" | "overgenomen" | "aangepast" | "afgewezen";
  reden: string;
  besloten_door: string | null;
  besloten_op: string | null;
  begrip_revisie: number | null;
  gemaakt: string;
  /** Alleen bij een open definitievoorstel: is de definitie veranderd sinds Lex het voorstelde? */
  verouderd?: boolean;
  nu?: { definitie: string; definitie_herkomst: DefinitieHerkomst | null };
}

export interface KaartRun {
  id: string;
  begrip_id: string;
  actie: KaartActie;
  status: "wacht" | "loopt" | "klaar" | "mislukt";
  melding: string;
  reden: string;
  basis_revisie: number;
  ander_begrip_id: string | null;
  gestart_door: string;
  gestart: string;
  gewijzigd: string;
}

export interface KaartVoorstellenAntwoord {
  voorstellen: KaartVoorstel[];
  /** Per actie de laatste run. */
  runs: Partial<Record<KaartActie, KaartRun>>;
  schatting?: Partial<Record<KaartActie, { tokens: number; basis: number }>>;
  budget?: { resterend: number; budget: number; actief: boolean; geblokkeerd: boolean };
}

/** De 409 bij een verouderd voorstel: wat er stond, wat er nu staat, en wat Lex voorstelde. */
export interface VoorstelVerouderd {
  fout: "voorstel_verouderd";
  toen: { definitie: string; definitie_herkomst: DefinitieHerkomst | null };
  nu: { definitie: string; definitie_herkomst: DefinitieHerkomst | null };
  voorstel: { definitie: string; definitie_herkomst: DefinitieHerkomst };
  melding: string;
}
