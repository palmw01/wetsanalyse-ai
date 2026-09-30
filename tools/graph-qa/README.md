# graph-qa – Lex

> **De dienst heet `graph-qa`, de assistent heet Lex.** Naar de gebruiker stelt de agent zich voor als
> **Lex**, het hulpmiddel voor wetsanalyse; de map, het image (`ghcr.io/palmw01/graph-qa`) en de
> env-vars houden hun technische naam. Zijn zelfbeschrijving staat in het IDENTITEIT-blok van
> `agent/prompts.py`, zijn toon in `docs/schrijfrichtlijn-lex.md`.

Een Python/FastAPI-dienst die vragen over Nederlandse wet- en regelgeving beantwoordt door de
**BWB-kennisgraaf** (GraphDB, via MCP) te bevragen, en die bepalingen annoteert in JAS-klassen. Het
antwoord steunt **uitsluitend** op wat de graaf teruggeeft, met een letterlijke vindplaats en een
bronnenlijst die herleidbaar is tot de uitgevoerde queries. De agentlogica draait op een
LangGraph-toestandsmachine met een LLM (Anthropic via Azure AI Foundry).

## Wat de agent doet

Een **supervisor** kiest per opdracht een worker-keten. Een vraag die niet over wetgeving gaat, wijst
hij daar al af.

- **Antwoord-worker** (vragen): een specialist redeneert en roept getypeerde tools aan tegen de graaf
  (*tool-trace*) → een deterministische **grounding-controle** toetst of vindplaatsen en citaten in het
  antwoord uit die trace komen, met zo nodig één corrigerende ronde → **finalize** bouwt de
  bronnenlijst uit de trace.
- **Annotatie-worker** (*"annoteer artikel 36 lid 4 van de Invorderingswet 1990"*): de bronnode
  gericht ophalen → deterministische **detectoren** leveren kandidaat-fragmenten → een kleine
  **classifier** kiest per kandidaat een JAS-klasse → een **gerichte reviewer** kijkt alleen naar de
  twijfelgevallen → de elementen gaan uit. Elk voorstel is een letterlijk fragment met een JAS-klasse
  en een aandacht-niveau (🟢 of 🟡 = een keuze voor de jurist); de jurist beoordeelt ze in de werkplek.
  De uitkomst landt in de **gedeelde annotatielaag van de bronnode** (artikel, lid of onderdeel),
  voor iedereen. Wat al geannoteerd is en niet veranderd, wordt **hergebruikt**; met
  `hergebruik: "opnieuw"` vraag je om een nieuwe ronde. Wijst een opdracht een artikel met leden aan,
  dan krijgt de jurist eerst een keuzekaart.
- **Leesroute** (vragen óver bestaande annotaties, "welke elementen zijn een Rechtsobject?"): de
  route zoekt eerst zelf met `search_annotaties` en laat het model daarna formuleren.

De volledige keten en haar regels staan in `CLAUDE.md` en in `docs/architectuur/annotatieketen.md`.

### Specialisten

De supervisor kiest per vraag één specialist; elk krijgt een eigen instructie en een **subset** van de
tools (`agent/specialists.py`):

| Specialist | Waarvoor | Kern-tools |
|---|---|---|
| `definitie` | Begrippen en definities herleiden en letterlijk citeren. | `zoek_definitie`, `resolve_begrip`, `get_artikel`/`get_lid`, `verwijst_naar_deze` |
| `duiding` | Betekenis, structuur en samenhang van een bepaling; kruisverwijzingen volgen. | `get_context`, `follow_verwijzingen`, `verwijst_naar_deze`, `inhoudsopgave`, `grondslagen`, `geldigheid` |
| `algemeen` | Overige juridische vragen. | alle tools |
| `annotaties_lezen` | Vragen over bestaande annotaties. | `search_annotaties`, `get_annotatie`, `get_annotatiedekking` + de ophaaltools |

De ophaal-agent van de annotatieketen (`retrieval`) krijgt bewust géén `grondslagen`/`geldigheid`: die
rol wijst een bepaling **aan**, hij duidt haar niet.

### De toollaag

Het model krijgt geen vrije SPARQL maar 22 getypeerde tools: 19 op de kennisgraaf en 3 op de
opgeslagen annotaties (die lopen via de wetsanalyse-API, niet via SPARQL).

- **Zoeken** – `search_wetgeving` (full-text, veldgericht, te beperken tot één regeling of knooptype,
  met paginatie) en `semantic_search` (op betekenis, via een GraphDB-similarity-index).
- **Ophalen** – `get_artikel`, `get_lid`, `get_bepaling`. Werken ook op divisies van een beleidsregel
  (`nummer: "25.1"`).
- **Structuur** – `inhoudsopgave`: hoofdstukken, afdelingen, artikelen of divisies en waarin ze zitten.
- **Regelingen** – `list_regelingen`, `get_regeling_info` (soort, geldigheid, organisatie en de
  WTI-velden), `bijlagen`.
- **Verwijzingen** – `follow_verwijzingen` (uitgaand), `verwijst_naar_deze` (inkomend, op
  bepalingniveau), `referenced_by` (inkomend, alleen regelingen).
- **Context** – `get_context`: een bepaling met haar bevattende delen, leden, verwijzingen in beide
  richtingen en buren, in één query.
- **Begrippen** – `zoek_definitie` (waar de wet het begrip zelf definieert) en `resolve_begrip` (de
  SKOS-thesaurus; redactionele trefwoorden, géén wettelijke definitie).
- **Herkomst en tijd** – `grondslagen` (delegatieketen) en `geldigheid` (inwerkingtreding,
  terugwerkende kracht, wijzigingsbron, toestand).
- **Annotaties** – `search_annotaties`, `get_annotatie`, `get_annotatiedekking`.
- **Introspectie** – `graph_schema`; **laatste redmiddel** – `raw_sparql` (read-only).

### Brongetrouwheid en geheugen

- **Bronnen komen uit de tool-trace, niet uit modeltekst.** Een geparafraseerde of verzonnen
  vindplaats in het antwoord wordt nooit als bron gepresenteerd.
- **Grounding** (deterministisch, geen extra LLM-call) met drie uitkomsten: gegrond, ongegrond of
  onbepaald (er viel niets te controleren).
- **Tekst uit de graaf is data, nooit instructie**; de agent houdt zich aan zijn onderwerp.
- **Gespreksgeheugen** loopt via een durable LangGraph-checkpointer (sleutel = `conversation_id`).
  Feiten worden altijd opnieuw via de tools geverifieerd.

## API

**De werkplek gebruikt de run-endpoints, niet `/v1/chat`.** Een beurt duurt 60-90 seconden; de run
draait als achtergrondtaak bij de agent en de browser kijkt mee. Sluit je het tabblad, dan loopt het
werk door en legt de agent de uitkomst zelf vast.

| Endpoint | Doel |
|---|---|
| `GET /health` | Liveness (geen auth). |
| `POST /v1/runs` | Start een beurt; geeft `run_id`. **409 + het lopende run_id** als er al een run voor dit gesprek is. Body: `question`, `conversation_id?`, optioneel `doel` (dan slaat de keten het zoeken over), `doelen` (2–60 onderdelen van één artikel, na elkaar geannoteerd), `modus` (`auto`/`advies`/`annotaties_lezen`), `context` en `hergebruik` (`auto`/`opnieuw`). |
| `GET /v1/runs/{id}/events?vanaf=<seq>` | **SSE**: eerst replay vanaf `vanaf`, dan live. Elk frame draagt zijn `seq`. |
| `POST /v1/runs/{id}/cancel` | 202 – stoppen is een verzoek: de lopende stap maakt zichzelf af. |
| `GET /v1/conversations/{id}/run` | De run waar je op kunt aanhaken, of `null`. |
| `DELETE /v1/conversations/{id}` | Wist het agent-geheugen van één gesprek (idempotent → 204) en stopt een lopende beurt. |
| `POST /v1/chat` | Eén beurt **aan de verbinding gekoppeld** (SSE, zelfde body). Zonder eigenaarscontrole en zonder vastleggen: voor scripts en handmatig testen, niet voor de webapp. |

**Events** (gelijk over beide wegen). Antwoord: `status` · `reason` (denkproces) · `token`
(eindantwoord) · `sources` · `grounding` · `conversation_id` · `tool_execution` · `done` · `error`.
Annotatie: `doel` · `run` · `dekking` · `element` · `kandidaten` · `hergebruik` · `opgeslagen` ·
`waarschuwing`, en bij een reeks `reeks` en `onderdeel`. Over de run-events kan ook `gat` komen: er is
vluchtig verkeer weggevallen bij het cappen van de log, en de client toont "…".

**Beveiliging.** `QA_API_TOKEN` wordt timing-safe vergeleken. Legt de agent zijn beurten zelf vast
(`WETSANALYSE_API_URL` + `_TOKEN` gezet), dan is dat token **verplicht** en weigert de dienst te
starten zonder. Verder: CORS met credentials alleen bij een expliciete origin-lijst, een rate-limit
per gebruiker (`X-User-Id`, met het IP als terugval) en een read-only-vangnet dat SPARQL-updates
weigert.

## Lokaal draaien

Vereist [`uv`](https://docs.astral.sh/uv/). Zet minimaal `GRAPHDB_MCP_URL`, `GRAPHDB_TOKEN` en de
Azure-Foundry-variabelen (zie `.env.example`); zonder graafconfiguratie weigert de dienst te starten.
Vragen beantwoorden werkt zonder wetsanalyse-API; **annoteren niet**: de keten toetst eerst de
bestaande dekking bij de api en stopt als dat niet lukt.

```bash
cd tools/graph-qa
cp .env.example .env                              # vul GRAPHDB_* + AZURE_FOUNDRY_* in
uv run --extra nlp graph-qa                       # uvicorn op poort 8080; nlp = spaCy voor de annotatieketen

uv run --extra dev pytest -q                      # tests
.venv/bin/python eval/run_eval.py --offline       # eval-harnas (fakes, geen netwerk/kosten)
uv run --extra mcp graph-qa-mcp                   # stdio-MCP over de toollaag, voor externe agents
```

Zonder de `nlp`-extra draait de annotatieketen gedegradeerd (alleen vaste patronen) en meldt dat.
GraphDB staat op Azure niet open naar buiten; lokaal draaien vraagt een eigen GraphDB met een
geïmporteerde wet. Metingen tegen de echte graaf gaan via de eval-job (zie `CLAUDE.md`).

## Configuratie (env)

Secrets kunnen ook als `<NAAM>_FILE` (pad naar een bestand) worden gezet: `GRAPHDB_TOKEN`,
`AZURE_FOUNDRY_API_KEY`, `QA_API_TOKEN`, `WETSANALYSE_API_TOKEN`, `CHECKPOINT_DB_URL`.

| Variabele | Default | Betekenis |
|---|---|---|
| `GRAPHDB_MCP_URL` *(verplicht)* | – | MCP-endpoint van de graaf. |
| `GRAPHDB_TOKEN` *(verplicht)* | – | Bearer-token voor de GraphDB-MCP. |
| `GRAPHDB_REPOSITORY_ID` | `inning` | Repository. |
| `SIMILARITY_INDEX` | leeg | GraphDB-similarity-index voor `semantic_search` (op Azure `bwb_similarity`). Leeg → de tool degradeert naar `search_wetgeving`. Zie `docs/embeddings-runbook.md`. |
| `AZURE_FOUNDRY_API_KEY` *(verplicht)* | – | Azure-AI-Foundry-key. |
| `AZURE_FOUNDRY_BASE_URL` *(verplicht)* | – | Foundry-endpoint **met** `/anthropic`-suffix. |
| `LLM_MODEL` | `claude-sonnet-4-6` | Draagt de classifier, de reviewer en de QA-specialisten; die hebben bewust geen eigen knop. |
| `LLM_MODEL_ROUTER` | = `LLM_MODEL` | Model voor de supervisor. |
| `LLM_MODEL_OPHAAL` | = `LLM_MODEL` | Model voor de ophaal-agent. Verlaag pas na meting: kiest hij de verkeerde bepaling, dan is alles daarna brongetrouw én verkeerd. |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `120` / `2` | Wachttijd en herhalingen per LLM-call (de eval-job zet 45 s). |
| `PROMPT_CACHING` | `true` | Prompt-caching op het stabiele deel van de systeemprompt. |
| `WETSANALYSE_API_URL` / `WETSANALYSE_API_TOKEN` | leeg | De wetsanalyse-API: vastleggen van beurten, annotatieleestools en dekkingscontrole. Beide gezet = de agent legt zelf vast. |
| `ANNOTATIE_READ_USER_ID` | leeg | Alleen voor CLI/MCP: namens wie de annotatietools lezen. Over HTTP geldt de rungebruiker. |
| `QA_API_TOKEN` | leeg = open | Token op de eigen endpoints; verplicht zodra de agent zelf vastlegt. |
| `CORS_ORIGINS` | `*` | Kommagescheiden origins; `*` = open. |
| `QA_RATE_LIMIT` / `QA_RATE_WINDOW_SECONDS` | `60` / `60` | Verzoeken per venster, per gebruiker. |
| `TRUST_PROXY` | `false` | Eerste `X-Forwarded-For`-hop als client-IP voor de rate-limit. |
| `CHECKPOINT_DB_URL` | leeg | Postgres voor het gespreksgeheugen én het run-register; gedeeld tussen replica's (verplicht bij meer dan één). |
| `CHECKPOINT_DB_PATH` | `conversations_checkpoints.db` | SQLite-bestand als `CHECKPOINT_DB_URL` leeg is (relatief = t.o.v. `tools/graph-qa`, per instance). |
| `MAX_TURNS` / `MAX_HISTORY_CHARS` | `20` / `40000` | Max. reason↔retrieve-beurten per vraag; historiebudget per beurt naar de LLM. |
| `GROUNDING_CORRECT` | `true` | Eén corrigerende ronde bij een ongegrond antwoord; kost alleen een call als er iets mis is. |
| `ENABLE_DECOMPOSITION` | uit | `1` = samengestelde vragen eerst in deelvragen splitsen. Op Azure uit. |
| `MAX_SUBQUESTIONS` / `SUB_MAX_TURNS` | `5` / `8` | Cap op deelvragen en op beurten per deelvraag. |
| `TAAL_PROVIDER` | `spacy:nl_core_news_md` | Taalanalyse voor de detectoren. |
| `CLASSIFIER_GRANULARITEIT` | `klasseverzameling` | Eén classificatiecall voor alles (`universeel`), per klassefamilie (`familie`) of per toegestane klasseverzameling. |
| `CLASSIFIER_PARALLEL` | `4` | Classificatiebatches tegelijk; de uitkomst verandert niet. |
| `CLASSIFIER_TEMPERATURE` | leeg | Leeg = providerdefault; nieuwe modellen weigeren sampling-parameters. |
| `CLASSIFIER_SPANKEUZE` | `false` | Mag de classifier een andere fragmentgrens kiezen dan de detector? |
| `DETERMINISTISCH_ACCEPTEREN` | `true` | Een kandidaat met één mogelijke klasse en sterk, vast bewijs wordt zonder modelcall voorgesteld. |
| `GERICHTE_REVIEW` | `true` | Reviewer op twijfelgevallen; uit = die gaan direct geel naar de jurist. |
| `BRONCONTEXT` | `true` | Ouderteksten als contextblok voor classifier en reviewer. |
| `AGENT_VERSION` | pakketversie | Versie in de herkomst van een annotatie. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg | OTLP-endpoint; leeg = alleen JSON-logs. Ook `OTEL_SERVICE_NAME`, `LOG_FORMAT`, `LOG_LEVEL`. |

## Uitrol

Het image wordt gebouwd door `.github/workflows/graph-qa-docker-publish.yml` (tests → build → Trivy →
uitrol naar acceptatie, inclusief de eval-job). De app draait op Azure als interne container-app
`<appName>-graph-qa`; de env-vars en secrets staan in `deploy/azure/main.bicep`. Zie
`deploy/azure/README.md`.

## Verder lezen

- **`CLAUDE.md`** – werkgids bij het aanpassen van de code: architectuur, invarianten, valkuilen, tests
  en eval.
- `docs/architectuur/annotatieketen.md` en `docs/architectuur/annotatie-bronnodes.md` – de
  annotatieketen en het contract van de lagen.
