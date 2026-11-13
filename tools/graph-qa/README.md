# graph-qa – Lex

> **De dienst heet `graph-qa`, de assistent heet Lex.** Naar de gebruiker stelt de agent zich voor als
> **Lex**, het hulpmiddel voor wetsanalyse; de map, het image (`ghcr.io/palmw01/graph-qa`) en de
> env-vars houden hun technische naam. Zijn zelfbeschrijving staat in het IDENTITEIT-blok van
> `agent/prompts.py`, zijn toon in [`docs/schrijfrichtlijn-lex.md`](../../docs/schrijfrichtlijn-lex.md).

Een Python/FastAPI-dienst die vragen over Nederlandse wet- en regelgeving beantwoordt door de
**BWB-kennisgraaf** (GraphDB, via MCP) te bevragen, en die bepalingen annoteert in JAS-klassen. Het
antwoord steunt **uitsluitend** op wat de graaf teruggeeft, met een letterlijke vindplaats en een
bronnenlijst die herleidbaar is tot de uitgevoerde queries. Daarnaast begeleidt de agent het werk aan
werkgebieden, bronselectie en begrippen. De agentlogica draait op een LangGraph-toestandsmachine met een
LLM (Anthropic via Azure AI Foundry).

## Wat de agent doet

Eén LangGraph-graaf (`agent/orchestrator.py`). Een **supervisor** kiest per beurt de route. Een klik op
een suggestie, een bevestiging of een vraagkaart gaat zonder model naar de juiste route; een getypte
vraag leest hij met een klein model. Een vraag die niet over wetgeving gaat, wijst hij af.

```
supervisor ─┬→ agent ⇄ tools [→ sjabloon] → verify ─┬→ correct → agent   antwoord
            │                                       └→ finalize → advance
            ├→ annotaties_zoeken → agent …                       leesroute annotaties
            ├→ begrippen_zoeken → agent …                        leesroute begrippen
            ├→ overzicht_bouwen → verify …                       overzichtsroute
            ├→ [agent ⇄ tools →] annoteer → emit → advance       annotatie-worker
            ├→ werkgebied_intake                                 werkgebied-worker
            ├→ bronselectie                                      bronselectie per deelvraag
            ├→ agent_taak                                        deelvragen- en begrippen-agent
            └→ afwijzen
```

- **Antwoord** (vragen): een specialist redeneert en roept getypeerde tools aan tegen de graaf
  (*tool-trace*) → een deterministische **grounding-controle** toetst vindplaatsen en citaten, met zo
  nodig één corrigerende ronde → **finalize** bouwt de bronnenlijst. Rondt het model af met een
  **sjabloon** ([ADR-008](../../docs/architectuur/adr-008-antwoordsjablonen.md), nu voor `begrip`), dan vult
  de code de blokken uit de trace en levert het model alleen de eigen tekst.
- **Annotatie** (*"annoteer artikel 36 lid 4 van de Invorderingswet 1990"*): de bronnode gericht
  ophalen → deterministische **detectoren** leveren kandidaat-fragmenten → een kleine **classifier**
  kiest per kandidaat een JAS-klasse → een **gerichte reviewer** kijkt alleen naar de twijfelgevallen →
  een vaste resolver voert de uitkomst uit, en `emit` is de enige uitgang. Elk voorstel is een
  letterlijk fragment met een JAS-klasse en zo nodig een aandacht-niveau (🟢, of 🟡 = een keuze voor de
  jurist). De uitkomst landt in de **gedeelde annotatielaag van de bronnode** (artikel, lid of
  onderdeel). Wat al geannoteerd is en niet veranderd, wordt **hergebruikt**; met
  `hergebruik: "opnieuw"` vraag je om een nieuwe ronde. Wijst een opdracht een artikel met leden aan,
  dan krijgt de jurist eerst een keuzekaart. Lex annoteert op verzoek ook een heel werkgebied of de
  bronnen onder de deelvragen, altijd pas na een bevestiging.
- **Leesroutes**: een vraag óver bestaande annotaties of begrippen. De route zoekt eerst zelf en laat
  het model daarna formuleren; zoeken is een stap in de keten, geen keuze van het model.
- **Overzichtsroute** ("welke artikelen gaan over X?"): overzicht en tekst komen deterministisch uit de
  graaf, zonder model.
- **Werkgebied-worker** (activiteit 1): een werkgebied samenstellen of aanvullen met vraagkaarten. Een
  vaste stapmachine; het model stelt alleen voor.
- **Bronselectie per deelvraag**: Lex werkt de deelvragen één voor één af. De stand staat bij de api, en
  de code kiest de volgende deelvraag.
- **Agents** (`agent/agents/`, ADR-005): één taak per beurt, met een model alleen in een strict stap.
  De deelvragen-agent stelt voor en verbetert en toetst de dekking. De begrippen-agent stelt
  begrippen voor, denkt mee, zoekt een brondefinitie, formuleert scherper, schrijft de uitleg,
  voorbeelden, het betekenisverschil en relaties, of werkt een begrip volledig uit.

De volledige keten en haar regels staan in [`CLAUDE.md`](CLAUDE.md) en in
[`docs/architectuur/annotatieketen.md`](../../docs/architectuur/annotatieketen.md).

### Specialisten

De supervisor kiest voor een gewone vraag één van de eerste drie. De twee leesspecialisten horen bij de
deterministische leesroutes. Elk is een **agentprofiel** (ADR-016): een bestand `.claude/lex-agents/<naam>.md` met een
eigen instructie en een **subset** van de tools, gebundeld in `agent/agentprofielen.py` en geladen door
`agent/profielen.py`:

| Specialist | Waarvoor | Kern-tools |
|---|---|---|
| `definitie` | Begrippen en definities herleiden en letterlijk citeren. | `zoek_definitie`, `resolve_begrip`, `search_begrippen`, `get_artikel`/`get_lid`, `verwijst_naar_deze` |
| `duiding` | Betekenis, structuur en samenhang van een bepaling; kruisverwijzingen volgen. | `get_context`, `follow_verwijzingen`, `verwijst_naar_deze`, `inhoudsopgave`, `grondslagen`, `geldigheid` |
| `algemeen` | Overige juridische vragen. | alle tools |
| `annotaties_lezen` | Vragen over bestaande annotaties. | `search_annotaties`, `overzicht_annotaties`, `get_annotatie`, `get_annotatiedekking` + de ophaaltools |
| `begrippen_lezen` | Vragen over vastgelegde begrippen. | `search_begrippen`, `get_begrip`, `zoek_definitie` + de ophaaltools |

De ophaal-agent van de annotatieketen (`retrieval`) krijgt bewust géén `grondslagen`/`geldigheid`: die
rol wijst een bepaling **aan**, hij duidt haar niet.

### De toollaag

Het model krijgt geen vrije SPARQL maar 29 getypeerde tools (`agent/tools/`): 21 op de kennisgraaf, 4 op
de opgeslagen annotaties, 2 op de begrippen en 2 op de Kamerstukken. De annotatie- en begriptools lopen via de
wetsanalyse-API; de Kamerstuktools staan achter een vlag (hieronder).

- **Zoeken** – `search_wetgeving` (full-text, veldgericht, te beperken tot één regeling of knooptype,
  met paginatie), `semantic_search` (op betekenis, via een GraphDB-similarity-index), `zoek_opbouw`
  (een onderwerp in de opschriften van hoofdstukken, afdelingen en divisies) en `overzicht_onderwerp`
  (het overzicht van een onderwerp).
- **Ophalen** – `get_artikel`, `get_lid`, `get_bepaling`. Een divisie van een beleidsregel haal je op met
  `get_bepaling` (`nummer: "25.1"`).
- **Structuur** – `inhoudsopgave`: de boom van een regeling in documentvolgorde, per deel met de nummers
  eronder; een ingeklapt deel opent met `vanaf=<iri>`.
- **Regelingen** – `list_regelingen`, `get_regeling_info` (soort, geldigheid, organisatie en de
  WTI-velden), `bijlagen`.
- **Verwijzingen** – `follow_verwijzingen` (uitgaand), `verwijst_naar_deze` (inkomend, op
  bepalingniveau), `referenced_by` (inkomend, alleen regelingen).
- **Context** – `get_context`: een bepaling met haar bevattende delen, leden, verwijzingen in beide
  richtingen en buren, in één query.
- **Definities** – `zoek_definitie` (waar de wet het begrip zelf definieert) en `resolve_begrip` (de
  SKOS-thesaurus; redactionele trefwoorden, géén wettelijke definitie).
- **Herkomst en tijd** – `grondslagen` (delegatieketen) en `geldigheid` (inwerkingtreding,
  terugwerkende kracht, wijzigingsbron, toestand).
- **Annotaties** – `search_annotaties`, `overzicht_annotaties`, `get_annotatie`, `get_annotatiedekking`.
  Elke treffer wordt tegen PostgreSQL geverifieerd.
- **Begrippen** – `search_begrippen`, `get_begrip`.
- **Introspectie** – `graph_schema`; **laatste redmiddel** – `raw_sparql` (read-only).

`jas_klasse_opvragen` staat daarbuiten en is opt-in per specialist.

### Bronnen naast de wet: Staatsblad en Staatscourant (ADR-013, fase 1d)

Achter `CONNECTOR_BEKENDMAKINGEN` krijgt Lex twee tools, op dezelfde SRU van KOOP als Kamerstukken (gedeelde laag in
`agent/adapters/sru_koop.py`; alleen lezen, alleen `repository.overheid.nl`; de dataset is CC0):

- **`zoek_bekendmakingen`**: met bwb-id en artikel de publicaties die de BWB bij de huidige tekst noemt (de laatste
  wijziging en het inwerkingtredingsbesluit, uit de graaf), anders op titel, tekst, soort, blad, datum, jaargang,
  ministerie en Kamerdossier, nieuwste, oudste of op relevantie.
- **`get_bekendmaking`**: de tekst per alinea met de kop van artikel en wijzigingsonderdeel; met `artikel` alleen de
  onderdelen die dat artikel wijzigen. Een oud stuk staat vaak alleen als PDF: dat zegt het resultaat, met de metadata.

### Bronnen naast de wet: Rechtspraak (ADR-013, fase 1c)

Achter `CONNECTOR_RECHTSPRAAK` krijgt Lex twee tools, met de transportlaag in `agent/adapters/lido_rechtspraak.py`
(alleen lezen, alleen `linkeddata.overheid.nl`, `zoekservice.overheid.nl` en `data.rechtspraak.nl`):

- **`zoek_uitspraken`** (bwb-id en artikel): de uitspraken en conclusies die Linked Data Overheid (KOOP, CC0) aan het
  artikel koppelt, **over alle versies** – een link hangt aan de versie die gold op de datum van de uitspraak (art. 9
  Iw: 12 op de huidige versie, 196 over alle). De versies vindt de adapter met `get-id` via de ref (bwb-id + artikel +
  datum) en, als die niets geeft (de Awb), via de jci uit de graaf met een toestanddatum uit de BWB-zoekdienst. Per
  uitspraak ECLI, gerecht, datum en zaaknummer (uit de titel), te filteren op instantie, soort en periode; nieuwste of
  oudste eerst. Altijd `dekking: "ten minste"`: LiDO loopt achter en kent geen relatie "vorige versie". Een afgebroken
  XML-antwoord van `get-links` valt terug op RDF; een plafond (`MAX_AANROEPEN`, `MAX_PAGINAS`) staat zichtbaar in de
  toelichting. De divisies van een beleidsregel kent LiDO niet.
- **Voorwaarden**: de Rechtspraak vraagt hoogstens 10 verzoeken per seconde en geen volledige download; de adapter
  houdt per host 5 per seconde aan (`PER_SECONDE`) en leest per uitspraak. De uitspraken zijn gepseudonimiseerd: Lex
  herleidt geen partij (`rol_in_antwoord`).
- **`zoek_uitspraken` zonder artikel**: de zoekfeed van de Rechtspraak (`data.rechtspraak.nl/uitspraken/zoeken`), op
  instantie (een soort gerecht of één gerecht, als URI uit de waardelijst Instanties), rechtsgebied (waardelijst
  Rechtsgebieden), soort en periode, altijd `return=DOC`. De feed sorteert alleen op wijzigingsdatum en geeft hoogstens
  1000 per verzoek: "nieuwste" en "oudste" op de datum van de uitspraak kiest de code met een datumvenster dat groeit of
  krimpt tot het genoeg uitspraken bevat en op één pagina past. `totaal` is het aantal in de hele gevraagde periode.
- **`get_uitspraak`** (ECLI): de tekst van een Nederlandse uitspraak (Public Domain Mark), per alinea met de kop, de
  inhoudsindicatie eerst; een alinea boven `MAX_ALINEA` in delen.

Een vermelding is geen uitleg: de tool zegt "noemt". De meting staat in
`docs/architectuur/metingen/lido-spike-2026-11-10/`; de live-proef in `tests/test_rechtspraak_live.py`.

### Bronnen naast de wet: Kamerstukken (ADR-013)

Achter `CONNECTOR_KAMERSTUKKEN` krijgt Lex `zoek_kamerstukken` en `get_kamerstuk`, op de SRU 2.0-zoekdienst van KOOP
(`repository.overheid.nl/sru`, collectie `officielepublicaties`). Wat de koppeling van die dienst gebruikt, in eigen
woorden; de bron is de *Handleiding SRU 2.0* van KOOP (v1.3, mei 2025, via data.overheid.nl), en de live-proef
(`tests/test_kamerstukken_live.py`, dagelijks in `bronnenwacht.yml`) houdt deze lijst eerlijk:

- **Zoeken** in CQL op `w.publicatienaam==Kamerstuk` en `dt.type==Kamerstuk` (zonder dat tweede komen de bijlagen
  mee), met `w.dossiernummer` (een subdossier als `36200-IX` is een eigen waarde, geen voorvoegsel) of woorden in
  `dt.title`. De query bouwt de tool; het model kiest alleen dossier, woorden en het stuk.
- **Hoeveel**: tot 1000 records per aanroep; `maximumRecords=0` geeft alleen het totaal. Een dossier tot 1000 stukken
  zet de tool zelf op nummer; een groter dossier pagineert op datum (`sortBy dt.available/sort.ascending`) met een
  exact vervolg. De dienst sorteert `w.ondernummer` als tekst, dus "10" vóór "2".
- **Het document** komt uit het record (`itemUrl` met `manifestation="xml"`), alleen van `repository.overheid.nl` over
  https. Het model kiest nooit een URL.
- **Versies**: een parlementair stuk verschijnt vaak eerst onopgemaakt en wordt later vervangen door de opgemaakte
  versie onder hetzelfde id (`w.documentstatus`); herdruk en rectificatie staan in `w.versieinformatie` en
  `w.versienummer`, de laatste wijziging in `dt.modified`. De cache valideert daarop, en `get_kamerstuk` noemt de
  versie en de hash van wat gelezen is.
- **De tekst** van een stuk staat in `stuk › divisie › al`, met koppen per divisie en een `tussenkop` per artikel in de
  artikelsgewijze toelichting. Tabellen zijn CALS (`table`, met `tgroup`, `thead`, `tbody`, `colspec` en cellen die met `namest`/`nameend`
  of `morerows` meer kolommen of rijen beslaan). Een tabel staat als één rij met `openen`; `get_kamerstuk(tabel=<nr>)`
  geeft de kolommen en per rij de cellen. De eigen inhoudsopgave van het stuk telt apart. Een voetnoot (`noot` met `noot.nr` en `noot.al`) is een eigen rij direct na zijn alinea; een
  `extref soort="document"` erin wordt `verwijst_naar`, een stuk dat Lex kan volgen. De eerste pagina van `get_kamerstuk` noemt per kop de offset (`inhoud`).
- **Fouten**: een SRU-diagnose of een onbereikbare dienst is een foutresultaat (`bron_onbereikbaar`), nooit een lege
  lijst. De JSON-uitvoer van de dienst is volgens de handleiding nog beperkt; de koppeling leest XML.

### Brongetrouwheid en geheugen

- **Bronnen komen uit de tool-trace, niet uit modeltekst.** Een geparafraseerde of verzonnen
  vindplaats in het antwoord wordt nooit als bron gepresenteerd.
- **Grounding** (deterministisch, geen extra LLM-call) toetst elke genoemde vindplaats en elk citaat
  tegen de tool-trace en het bronregister van het gesprek. Drie uitkomsten: `gegrond`, `ongegrond` (er
  is iets genoemd dat niet is opgehaald; dan hoogstens één corrigerende ronde) of `onbepaald` (er viel
  niets te controleren). `onbepaald` telt niet als goed; dat zou de schijnzekerheid zijn die het platform
  wil vermijden.
- **Tekst uit de graaf is data, nooit instructie**; de agent houdt zich aan zijn onderwerp.
- **Gespreksgeheugen** loopt via een durable LangGraph-checkpointer (sleutel = `conversation_id`).
  Feiten worden altijd opnieuw via de tools geverifieerd.

## API

**De werkplek gebruikt de run-endpoints; een andere weg is er niet.** Een beurt kan minuten duren; de run
draait als achtergrondtaak bij de agent en de browser kijkt mee. Sluit je het tabblad, dan loopt het
werk door en legt de agent de uitkomst zelf vast.

| Endpoint | Doel |
|---|---|
| `GET /health` | Liveness (geen auth). |
| `POST /v1/runs` | Start een beurt; geeft `run_id`. **409 + het lopende run_id** als er al een run voor dit gesprek is. Body: `question`, `conversation_id?`, optioneel `doel` (dan slaat de keten het zoeken over), `doelen` (2–60 onderdelen van één artikel, na elkaar geannoteerd), `modus` (`auto`/`advies`/`annotaties_lezen`/`werkgebied_annoteren`/`begrippen_verdiepen`), `context`, `hergebruik` (`auto`/`opnieuw`), `werkgebied_id`, `onderwerp` (`{soort, werkgebied_id, id?, label?}`: het object waarop *Vraag Lex* koos, als context), `actie` (een suggestie met een vaste route, zie CLAUDE.md §*Vraag Lex op een object*), `intake_actie` (een klik op een vraagkaart), en bij een bevestigd voorstel `bevestigd`, `werkvoorraad_id`, `bereik` (`werkgebied`/`deelvragen`) en `deelvraag_id`. Geeft 429 als het tokenbudget op is. |
| `GET /v1/runs/{id}/events?vanaf=<seq>` | **SSE**: eerst replay vanaf `vanaf`, dan live. Elk frame draagt zijn `seq`. |
| `POST /v1/runs/{id}/cancel` | 202 – stoppen is een verzoek: de lopende stap maakt zichzelf af. |
| `GET /v1/conversations/{id}/run` | De run waar je op kunt aanhaken, of `null`. |
| `GET /v1/runs?actief=true` | Je eigen runs die lopen of de laatste 10 minuten eindigden, nieuwste eerst: `[{run_id, conversation_id, status, afgerond_op}]`. Voor de sidebar en de tab; geen rate-limit. |
| `DELETE /v1/conversations/{id}` | Wist het agent-geheugen van één gesprek (idempotent → 204) en stopt een lopende beurt. |

**Events.** Antwoord: `status` · `reason` (denkproces) · `token` (eindantwoord) · `sources` ·
`grounding` · `conversation_id` · `tool_execution` · `overzicht` · `antwoord` (de blokken van een
sjabloon) · `done` · `error`. Annotatie: `doel` ·
`run` · `dekking` · `element` · `kandidaten` · `hergebruik` · `waarschuwing`, en bij een reeks `reeks` en
`onderdeel`. Werkgebied en agents: `vraagkaart` · `werkgebied_aanmaken` · `werkgebied_wijzigen` ·
`artefact` · `bevestiging`. Alleen bij runs: `opgeslagen` en `gat` (er is vluchtig verkeer weggevallen
bij het cappen van de log, en de client toont "…").

**Beveiliging.** `QA_API_TOKEN` wordt timing-safe vergeleken. Legt de agent zijn beurten zelf vast
(`WETSANALYSE_API_URL` + `_TOKEN` gezet), dan is dat token **verplicht** en weigert de dienst te
starten zonder. `X-User-Id` is de eigenaarsgrens van een run, en de BFF zet hem uit de sessie; de dienst
is daarom intern. Verder: CORS met credentials alleen bij een expliciete origin-lijst, een rate-limit
per gebruiker (`X-User-Id`, met het IP als terugval) en een read-only-vangnet dat SPARQL-updates
weigert.

## Lokaal draaien

Vereist [`uv`](https://docs.astral.sh/uv/) en Python ≥ 3.11 (het image draait 3.14). Zet minimaal `GRAPHDB_MCP_URL`, `GRAPHDB_TOKEN` en de
Azure-Foundry-variabelen (zie `.env.example`); zonder graafconfiguratie weigert de dienst te starten.
Vragen beantwoorden werkt zonder wetsanalyse-API; **annoteren niet**: de keten toetst eerst de
bestaande dekking bij de api en stopt als dat niet lukt. Let op: `.env.example` vult
`WETSANALYSE_API_URL` en een plaatshouder voor het token al in. Draai je zonder api, maak ze dan leeg;
anders denkt de dienst dat hij zelf vastlegt.

```bash
cd tools/graph-qa
cp .env.example .env                              # vul GRAPHDB_* + AZURE_FOUNDRY_* in
uv run --extra nlp graph-qa                       # uvicorn op poort 8080; nlp = spaCy voor de annotatieketen

uv run --extra dev --extra mcp pytest -q          # tests; zonder mcp slaat test_mcp_server zichzelf over
.venv/bin/python eval/run_eval.py --offline       # eval-harnas (fakes, geen netwerk/kosten)
uv run --extra mcp graph-qa-mcp                   # stdio-MCP over de toollaag, voor externe agents
```

Zonder de `nlp`-extra draait de annotatieketen gedegradeerd (alleen vaste patronen) en meldt dat.
GraphDB staat op Azure niet open naar buiten. Lokaal draaien vraagt een eigen GraphDB met een
geïmporteerde wet, of op acceptatie de MCP-proxy (zie
[`deploy/azure/README.md`](../../deploy/azure/README.md)). Metingen tegen de echte graaf gaan via de
eval-job (zie `CLAUDE.md`).

Laat de webapp de agent vinden met `GRAPH_QA_URL` en `GRAPH_QA_TOKEN` in `frontend/.env.local`. Voor
vastleggen zet je hier `WETSANALYSE_API_URL` en `_TOKEN`, en daarmee ook `QA_API_TOKEN`.

**Kwaliteitsmeting** gaat via het eval-harnas (`eval/run_eval.py`) met vier gouden sets: `--offline`
(antwoorden), `--annotatie`, `--gesprek` en `--annotatie --concept`. De annotatieset scheidt
**garanties** (letterlijke fragmenten, bestaande klassen, prompt-injectie-kanaries: slagen of zakken) van
**trendmeting** (precisie en recall, geen slaagcriterium). Twee runs over dezelfde bepaling verschillen
sterk; meet een trend dus nooit op één run. Live meten gaat via `azure-infra` → `eval`.

### Problemen oplossen

| Symptoom | Oorzaak en oplossing |
|---|---|
| De dienst weigert te starten | `GRAPHDB_MCP_URL` of `GRAPHDB_TOKEN` ontbreekt (bewust: geen agent zonder graaf), of `QA_API_TOKEN` ontbreekt terwijl de agent zelf vastlegt. |
| Annotaties landen niet, of Lex vindt geen bestaande annotaties | `WETSANALYSE_API_URL`/`_TOKEN` ontbreken of kloppen niet. |
| `semantic_search` gedraagt zich als tekstzoeken | De similarity-index ontbreekt of `SIMILARITY_INDEX` is niet gezet. De importer bouwt de index zelf terug. |
| Lex meldt `Repository inning doesn't exist` | GraphDB is herstart en leeg. Op Azure vult de graafwacht hem binnen een kwartier; forceren kan met `azure-infra` → `vul-graaf`. |
| Een LLM-call breekt af | `LLM_TIMEOUT_SECONDS` (default 120). `AZURE_FOUNDRY_BASE_URL` moet op `/anthropic` eindigen. |

## Configuratie (env)

Secrets kunnen ook als `<NAAM>_FILE` (pad naar een bestand) worden gezet: `GRAPHDB_TOKEN`,
`AZURE_FOUNDRY_API_KEY`, `QA_API_TOKEN`, `WETSANALYSE_API_TOKEN`, `CHECKPOINT_DB_URL`.

| Variabele | Default | Betekenis |
|---|---|---|
| `GRAPHDB_MCP_URL` *(verplicht)* | – | MCP-endpoint van de graaf. |
| `GRAPHDB_TOKEN` *(verplicht)* | – | Bearer-token voor de GraphDB-MCP. |
| `GRAPHDB_REPOSITORY_ID` | `inning` | Repository. |
| `GRAPHDB_SPARQL_TOOL` | `sparql_query` | Naam van de SPARQL-tool op de MCP-server. |
| `SIMILARITY_INDEX` | leeg | GraphDB-similarity-index voor `semantic_search` (op Azure `bwb_similarity`). Leeg → de tool degradeert naar `search_wetgeving`. Zie [`docs/embeddings-runbook.md`](docs/embeddings-runbook.md). |
| `CENTRALE_AGENT` | `uit` | De centrale agent (ADR-016 §A7): `uit` (de supervisor; een verzoek per run wordt genegeerd), `meten` (de supervisor, tenzij een run met `agentvorm: "centraal"` erom vraagt) of `aan` (de centrale agent, tenzij een run om `supervisor` vraagt). Alleen op acceptatie anders dan `uit`. |
| `CONNECTOR_KAMERSTUKKEN` | `false` | De bronconnector Kamerstukken (ADR-013): `zoek_kamerstukken` en `get_kamerstuk` op de officiële publicaties van KOOP. Uit = niet aangeboden. |
| `CONNECTOR_BEKENDMAKINGEN` | `false` | De bronconnector Staatsblad en Staatscourant (ADR-013, fase 1d): `zoek_bekendmakingen` en `get_bekendmaking`, op de SRU van KOOP. Uit = niet aangeboden. |
| `CONNECTOR_RECHTSPRAAK` | `false` | De bronconnector Rechtspraak (ADR-013, fase 1c): `zoek_uitspraken` (uitspraken die een artikel noemen, uit Linked Data Overheid) en `get_uitspraak` (de tekst, uit de open data van de Rechtspraak). Uit = niet aangeboden. |
| `KAMERSTUKKEN_SRU_URL` | de SRU-dienst van KOOP | Alleen voor een andere SRU-dienst; de documenten komen altijd uit `repository.overheid.nl`. |
| `AZURE_FOUNDRY_API_KEY` *(verplicht)* | – | Azure-AI-Foundry-key. |
| `AZURE_FOUNDRY_BASE_URL` *(verplicht)* | – | Foundry-endpoint **met** `/anthropic`-suffix. |
| `LLM_MODEL` | `claude-sonnet-4-6` | Draagt de classifier, de reviewer en de QA-specialisten; die hebben bewust geen eigen knop. |
| `LLM_MODEL_ROUTER` | = `LLM_MODEL` | Model voor de supervisor. |
| `LLM_MODEL_OPHAAL` | = `LLM_MODEL` | Model voor de ophaal-agent. Verlaag pas na meting: kiest hij de verkeerde bepaling, dan is alles daarna brongetrouw én verkeerd. |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `120` / `2` | Wachttijd en herhalingen per LLM-call (de eval-job zet 45 s). |
| `PROMPT_CACHING` | `true` | Prompt-caching op het stabiele deel van de systeemprompt. |
| `PROMPT_CACHE_TTL` | `1h` | Hoe lang het cachepunt op een gesplitste systeemprompt (met de tools ervóór) blijft: `1h` of `5m`. |
| `LEX_REVISIE` | leeg | De commit waaruit het image is gebouwd; de publish-workflow zet hem als build-arg. Gaat mee met de melding van wat er in het image zit (ADR-016 §B1). |
| `WETSANALYSE_API_URL` / `WETSANALYSE_API_TOKEN` | leeg | De wetsanalyse-API: vastleggen van beurten, annotatieleestools en dekkingscontrole. Beide gezet = de agent legt zelf vast. |
| `ANNOTATIE_READ_USER_ID` | leeg | Alleen voor CLI/MCP: namens wie de annotatietools lezen. Over HTTP geldt de rungebruiker. |
| `PORT` | `8080` | Luisterpoort. |
| `QA_API_TOKEN` | leeg = open | Token op de eigen endpoints; verplicht zodra de agent zelf vastlegt. |
| `CORS_ORIGINS` | `*` | Kommagescheiden origins; `*` = open. |
| `QA_RATE_LIMIT` / `QA_RATE_WINDOW_SECONDS` | `60` / `60` | Verzoeken per venster, per gebruiker. |
| `TRUST_PROXY` | `false` | Eerste `X-Forwarded-For`-hop als client-IP voor de rate-limit. |
| `CHECKPOINT_DB_URL` | leeg | Postgres voor het gespreksgeheugen én het run-register; gedeeld tussen replica's (verplicht bij meer dan één). |
| `CHECKPOINT_DB_PATH` | `conversations_checkpoints.db` | SQLite-bestand als `CHECKPOINT_DB_URL` leeg is (relatief = t.o.v. `tools/graph-qa`, per instance). |
| `MAX_TURNS` / `MAX_HISTORY_CHARS` | `20` / `40000` | Max. reason↔retrieve-beurten per vraag; historiebudget per beurt naar de LLM. |
| `GROUNDING_CORRECT` | `true` | Eén corrigerende ronde bij een ongegrond antwoord; kost alleen een call als er iets mis is. |
| `TAAL_PROVIDER` | `spacy:nl_core_news_md` | Taalanalyse voor de detectoren. |
| `CLASSIFIER_GRANULARITEIT` | `klasseverzameling` | Eén classificatiecall voor alles (`universeel`), per klassefamilie (`familie`) of per toegestane klasseverzameling. |
| `CLASSIFIER_PARALLEL` | `4` | Classificatiebatches tegelijk; de uitkomst verandert niet. |
| `CLASSIFIER_TEMPERATURE` | leeg | Leeg = providerdefault; nieuwe modellen weigeren sampling-parameters. |
| `CLASSIFIER_SPANKEUZE` | `false` | Mag de classifier een andere fragmentgrens kiezen dan de detector? |
| `DETERMINISTISCH_ACCEPTEREN` | `true` | Een kandidaat met één mogelijke klasse en sterk, vast bewijs wordt zonder modelcall voorgesteld. |
| `GERICHTE_REVIEW` | `true` | Reviewer op twijfelgevallen; uit = die gaan direct geel naar de jurist. |
| `BRONCONTEXT` | `true` | Ouderteksten als contextblok voor classifier en reviewer. |
| `AGENT_VERSION` | pakketversie | Versie in de herkomst van een annotatie. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg | OTLP-endpoint; leeg = alleen JSON-logs. Ook `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_SERVICE_NAME`, `LOG_FORMAT`, `LOG_LEVEL`. |

## Uitrol

Het image wordt vanaf de **projectroot** gebouwd (het neemt `packages/bronmodel` en de skill mee), door
`.github/workflows/graph-qa-docker-publish.yml`: tests → build → Trivy → uitrol naar acceptatie. Die
werkt ook het image van de eval-job bij, maar start hem niet. De app draait op Azure als interne
container-app `<appName>-graph-qa`, met maximaal twee replica's en PostgreSQL voor geheugen en
run-register; de env-vars en secrets staan in `deploy/azure/main.bicep`. Zie
[`deploy/azure/README.md`](../../deploy/azure/README.md).

## Verder lezen

- [`CLAUDE.md`](CLAUDE.md) – werkgids bij het aanpassen van de code: architectuur, invarianten, valkuilen,
  tests en eval.
- [`docs/architectuur/annotatieketen.md`](../../docs/architectuur/annotatieketen.md) en
  [`docs/architectuur/annotatie-bronnodes.md`](../../docs/architectuur/annotatie-bronnodes.md) – de
  annotatieketen en het contract van de lagen.
