# CLAUDE.md – graph-qa

Werkgids bij het aanpassen van deze agent. Wat de dienst doet, hoe je hem start en welke env-vars er
zijn, staat in `README.md`; dit bestand beschrijft hoe de code in elkaar zit en welke eigenschappen je
niet mag breken.

## In één zin

Een retrieval-augmented QA- en annotatiedienst op de BWB-kennisgraaf: antwoorden komen
**uitsluitend** uit de graaf (via een getypeerde toollaag) en worden achteraf op brongetrouwheid
gecontroleerd; annotaties komen uit een hybride pijplijn (detectoren → classifier → gerichte reviewer)
met offsets die nooit van een model komen.

**Naar de gebruiker heet deze agent Lex.** De naam en de kadering (hulpmiddel voor wetsanalyse, de
jurist beoordeelt en beslist, geen juridisch advies) staan in het **IDENTITEIT-blok** van
`SYSTEM_PROMPT` (`agent/prompts.py`) – de enige plek met de volledige tekst; de specialisten stapelen
erop, dus hij geldt voor alle drie. Lex stelt zich **alleen op verzoek** voor. De interne rollen van de
annotatieketen (classifier en reviewer in `agent/jas_pipeline/`) blijven **naamloos**: Lex is de dienst
als geheel. Code, image en env-vars heten `graph-qa`.

## Opbouw

De code leeft in `agent/` (domein) en `api/` (HTTP); er is bewust **geen** `graph_qa/`-package, dus
`pyproject.toml` noemt de packages van de wheel expliciet – anders faalt `uv sync`. De bron- en
ankerlogica die de api en de agent delen staat in `packages/bronmodel` (`wetsanalyse-bronmodel`).

### De graaf (`agent/orchestrator.py` + `agent/nodes/`)

`orchestrator.build_graph` bouwt een LangGraph `StateGraph`; de nodes staan per keten in `agent/nodes/`:

| Module | Wat erin zit |
|---|---|
| `nodes/supervisie.py` | supervisor, `_entry_node`, advance, afwijzen |
| `nodes/antwoord.py` | agent ⇄ tools, verify, correct, finalize |
| `nodes/decompositie.py` | decompose, solve, synthesize, resynth |
| `nodes/annotatie.py` | annoteer (voorbereiding + `jas_pipeline.keten.analyseer`) en emit |
| `nodes/annotatie_lezen.py` | de leesroute: eerst zoeken in de opgeslagen annotaties, dan formuleren |
| `nodes/context.py` | `Bouw` – wat een node buiten zijn state om nodig heeft |

De nodes zijn gewone functies `(b: Bouw, state)`; `Bouw` draagt de poorten, de stopvlag, de drie
modelnamen en de contexthelpers, en `build_graph` bindt hem met `functools.partial`. **Roept een node
een andere aan, geef `b` dan expliciet door** – de suite wijst die valkuil aan.

```
supervisor ─┬─ antwoord-worker:  agent ⇄ tools → verify → (correct) → finalize → advance
            ├─ annotatie-worker: [agent ⇄ tools als ophaal-agent] → annoteer → emit → advance
            ├─ leesroute:        annotaties_zoeken → agent ⇄ tools → verify → finalize
            └─ afwijzen (geen wetgevingsvraag)
```

De vorm ligt vast in `tests/test_graafopbouw.py` (nodes en edges per configuratietak). Wijzig je de
routering, dan faalt die test – dat hoort, maar het moet een bewuste wijziging zijn. De annotatieketen
legt één helper (`annotatieketen()`) in elke tak identiek; de antwoordketen staat per tak apart omdat
die echt verschilt (`verify → resynth` bij decompositie, `verify → correct` anders). Decompositie
(`ENABLE_DECOMPOSITION`, op Azure uit) bouwt in `solve_node` een eigen agent-lus per deelvraag na met
lokale scratch-messages; alleen de synthese streamt.

Ondersteunend, op agent-niveau omdat meerdere ketens ze delen: `agent/state.py` (de `State`-TypedDict;
`messages` en `entities_seen` zijn `operator.add`-reducers), `agent/berichten.py` (het venster naar de
LLM), `agent/narratie.py` (de statusregels, `_stap`) en `agent/doel.py` (waar gaat deze beurt over).
`agent/agent.py:answer_stream` is de dunne wrapper: providers bouwen, checkpointer kiezen, graaf
compileren, SSE-events leveren, en per beurt de beurtvelden resetten.

### De nodes van de antwoordketen

- **`supervisor_node`** – één LLM-call (`SUPERVISOR_SYSTEM` in `agent/supervisor.py`, geen tools) die
  worker(s), specialist en plan kiest; eerder geraadpleegde bepalingen gaan als context mee. Een
  leesvraag (`is_leesvraag`), een meegegeven `doel` of `modus: "advies"` beslist hij zonder LLM-call.
- **`agent_node`** – draait de specialist (`agent/specialists.py`): `SYSTEM_PROMPT` + methode-instructies
  (`agent/methode.py`, uit het gegenereerde `methodepakket.py`) + addendum + plan, met
  `anthropic_schemas(only=spec.tools)`. Op een beurtgrens (turns > 0) gaat vóór de eerste tekst-delta één
  `\n\n` uit, zodat de narratie van opeenvolgende beurten niet aan elkaar plakt.
- **`tools_node`** – voert elke aanroep uit via `dispatch(...)` en voegt `(tool_naam, resultaat)` toe
  aan de `source_trace`.
- **`verify_node`** – `check_grounding(answer, source_trace)`. Bij ongegrond volgt via `correct_node`
  hoogstens één corrigerende ronde (`GROUNDING_CORRECT`, default aan; `state["corrected"]`). De controle
  keurt **twee** dingen af en `correct_node` moet ze allebei benoemen: `unsupported` (een vindplaats die
  niet uit de graaf kwam) en `niet_letterlijk` (een citaat dat niet letterlijk in de opgehaalde tekst
  staat). Bij de citaten gaan de passages zelf mee (afgekapt) – zonder de tekst weet het model niet
  wélk citaat het moet herstellen.
- **`finalize_node`** – `collect_sources` → `curate_sources` → emit `sources` + `grounding`; werkt
  `entities_seen` bij.

### Gespreksgeheugen (checkpointer)

`thread_id = conversation_id`; de agent krijgt per beurt de gepersisteerde `messages`-historie mee
(getrimd op `MAX_HISTORY_CHARS`; oudere tool-resultaten krimpen eerst, maar **de lopende beurt
krimpt nooit** – `berichten.beurt_start` – anders leest het model zijn verse resultaat als
"ingekort, vraag opnieuw op" en zoekt het in een lus; de opslagrem `berichten.MAX_HISTORIE_CHARS` hoort ruim daarboven te
liggen, `Settings.controleer_historie_grens` waarschuwt). De annotatie-worker laat een korte
samenvatting van de markeringen achter, zodat vervolgvragen context hebben. Backend
(`agent.py:_checkpointer_ctx`, voorrang): `CHECKPOINT_DB_URL` → `AsyncPostgresSaver` (gedeeld,
verplicht bij >1 replica) → `CHECKPOINT_DB_PATH` → `AsyncSqliteSaver` (per instance; de default is een
**relatief** bestand in de graph-qa-root) → in-memory.

> **Twee gescheiden stores op dezelfde `conversation_id`.** De UI-historie leeft in de api
> (`/v1/gesprekken/*`), het agent-geheugen in deze checkpointer. Een gesprek verwijderen wist bewust
> beide (de BFF roept de api-delete én `DELETE /v1/conversations/{id}` aan). Wordt één store gereset,
> dan kan de UI historie tonen die de agent niet meer heeft; dat is geaccepteerd.

### Poorten & adapters (DI)

- **`ports.py`** – `GraphPort` / `LLMPort`. Alles wat naar buiten praat loopt hierlangs, zodat tests
  fakes injecteren.
- **`adapters/anthropic_llm.py`** – Anthropic Messages API via Azure AI Foundry (`…/anthropic`),
  `create()` en `stream()`, bewust géén langchain-chatmodel. **Prompt-caching**: het systeemblok mag
  als `[stabiel, variabel]` binnenkomen (`ports.Systeem`) en het cache-punt gaat op het stabiele deel.
  Caching is een prefix-match: zet je plan of geheugen-context vóór de identiteit, dan is de cache
  stil waardeloos. Onder `_MIN_CACHE_TEKENS` gaat er geen cache-punt op. Weigert de provider
  `cache_control` (op Foundry een beta-functie), dan zet de adapter zichzelf uit en herhaalt de call
  zonder – caching mag nooit "de dienst ligt plat" kosten. Knop: `PROMPT_CACHING=false`.
- **`adapters/graphdb_graph.py`** – `make_graph(settings)` → `MCPClient`; roept `require_graph()`.
- **`mcp_client.py`** – synchrone MCP-client (Streamable HTTP): `sparql()` via `sparql_query`,
  `semantic_search()` via `similarity_search`, één persistente `httpx.Client`. `_reject_updates`
  weigert SPARQL die op een update lijkt. **De MCP-handshake hoort bij de verbinding, niet bij de
  aanroeper**: GraphDB weigert zonder sessie élke `tools/call` met een HTTP 400. `_rpc` doet de
  handshake zelf bij de eerste aanroep en herhaalt hem één keer bij een 404 (de server kent de sessie
  niet meer – GraphDB is niet-persistent en komt na een herstart zonder sessies op). Een `FakeGraph`
  kan dit principieel niet vangen: die antwoordt zonder handshake.
- **`mcp_server.py`** – de andere kant op: een stdio-MCP-server over de eigen toollaag (`graph-qa-mcp`,
  `mcp`-extra). `tools/list` is `anthropic_schemas()`, `tools/call` is `dispatch()` – een doorgeefluik,
  geen kopie. Hij bestaat zodat een externe agent niet zelf SPARQL schrijft en in de valkuilen hieronder
  loopt. `tests/test_mcp_server.py` bewaakt dat hij exact de tools van de agent aanbiedt.

## Toollaag & queries

- **`tools/__init__.py`** – `TOOLS` (22 declaraties: 19 graaftools plus de drie annotatieleestools uit
  `tools/annotatie_tools.py`), `anthropic_schemas(only=)` en `dispatch()` (vangt
  `ValueError`/`MCPError`/`KeyError` als tekst). Een tool met `needs_settings` krijgt `settings` mee.
  `tools/jas_tools.py` (`JAS_TOOLS`) is dispatchbaar maar wordt in de draaiende keten niet aangeroepen.
- **`graph/queries.py`** – de SPARQL-bouwers (o.a. `context()` = de GraphRAG-UNION).
  **`graph/schema.py`** – schema-introspectie met een cache van een uur. **`graph/results.py`** –
  `parse_select`: de MCP levert SELECT als JSON-string-gewrapte TSV.
- **`tool_execution.execute_tool`** – de ene uitvoeringsgrens voor tool-calls buiten de agent-lus
  (bron, dekking, leesroute), met `tool_execution`-events (start/einde, filters, status, aantal, duur).

**Lees dit vóór je een graaftool toevoegt of wijzigt.** De faalmodus die deze regels bestrijden is
telkens **stille onvolledigheid**: geen fout, geen leeg resultaat, gewoon een antwoord dat minder weet
dan de graaf.

- **Elke bepaling loopt via `queries.node_patroon`**, nooit rechtstreeks via `artikel_iri` (die weigert
  een punt en mist dan de divisies van een beleidsregel). De tools nemen `artikel` én `nummer` aan
  (`_aanduiding`).
- **`bwb:bevat` bestaat niet.** De importer schrijft per niveau een eigen `heeft…`-predicaat; de
  alternatie staat als `queries.BEVAT`. `tests/test_predicaat_dekking.py` toetst elke `bwb:`-term
  statisch tegen `tools/bwb-import/app/ontology.py`.
- **De zoekvelden zijn een contract met de importer.** `queries.FTS_VELDEN`/`FTS_TYPES` moeten gelijk
  zijn aan de connector-config in `tools/bwb-import/app/graphdb_writer.py`; een onbekende veldnaam geeft
  nul treffers zonder fout. `tests/test_fts_velden.py` bewaakt het.
- **Een tool landt pas als hij is toegewezen én uitgelegd.** `tests/test_toolverdeling.py` weigert een
  weestool (in geen enkele specialist-set), een rolnaam die niet bestaat (die negeert
  `anthropic_schemas(only=)` stil), een beschrijving die niet zegt wát er terugkomt, en een tool zonder
  controle in `eval/retrieval_smoke.py`.
- **Te véél rijen is net zo fout als te weinig.** `?node a ?type` matcht ook gematerialiseerde
  superklassen: bind `?soort` met `FILTER(?t IN (…CONCRETE_TYPES…))`. Meerwaardige properties in losse
  OPTIONALs vermenigvuldigen elkaar: gebruik `GROUP_CONCAT`. Beide glippen door elke leegte-controle
  heen – vandaar `min_rijen`/`max_rijen` in de smoke en de kardinaliteitsguard in
  `tests/test_predicaat_dekking.py`.
- **Verwijzingen hangen aan het LID, niet aan het artikel.** `follow_verwijzingen` en `context()` volgen
  `(heeftLid|heeftOnderdeel)+` mee en melden in `?vanuit` waar de verwijzing vandaan komt.
- **De graaf bevat ook de JAS-annotatielagen** (`urn:jas:graph:*`, door de api geprojecteerd). Omdat de
  queries de union bevragen, moet elke bouwer óf op subjecten onder `urn:bwb:` filteren óf alleen
  `bwb:`-predicaten volgen (`resolve_begrip` filtert op `NS`, anders geeft hij JAS-klassen als begrip).
  `tests/test_annotatielaag_isolatie.py` draait **elke** bouwer uit `test_sparql_syntax.GEVALLEN` met
  en zonder laag en eist identieke rijen; `api/tests/test_graaf_rijk.py` bewaakt dat de fixture
  (`tests/fixtures/jas_laag_v3_voorbeeld.ttl`) de echte projectie volgt.
- **Het fallback-label van een verwijsdoel staat op `bwb:doelLabel`.** Lees het als
  `COALESCE(rdfs:label, bwb:doelLabel)`; op `rdfs:label` verdubbelt elke label-query haar rijen.

### Bepalingen ophalen: wat de graafstructuur vraagt

De tools `get_artikel`, `get_lid` en `get_bepaling` voeden het model; het annotatiecorpus komt níét
hier vandaan maar uit `bronmodel.resolve` (zie §*De annotatieketen*).

- **Onderdelen hangen aan `heeftOnderdeel`**, en dat is een boom (`aa.` onder het lid, `1°` onder `aa.`),
  vandaar `heeftOnderdeel+`.
- **Tool-resultaten gaan door `truncate`** (8000 tekens). `get_artikel` laat de onderdelen onder een lid
  daarom weg (een definitieartikel zou zijn staart verliezen); `get_lid` levert ze in één
  `GROUP_CONCAT`-cel met per onderdeel zijn eigen jci.
- **Decimale nummers ("25.1") lopen via `get_bepaling`** (op `bwb:nummer` binnen de regeling), want
  `artikel_iri` weigert een punt. `bwb:tekst` is daar optioneel: veel bepalingen hebben alleen
  onderdelen of subdivisies.
- **Een bepaling kan een container zijn.** Een circulaire heeft `heeftDivisie`/`heeftArtikel`
  (subdivisies) náást `heeftOnderdeel` (de opsomming ván één divisie). `get_bepaling` noemt de
  subdivisies met het begin van hun tekst, zodat het model ziet dát er inhoud is. Een **heel getal**
  bij een beleidsregel heeft wél een `:artikel:`-IRI.
- **`_NUMMER_VRIJ_RE` staat letters op elk segment toe** ("7a.1", "22bis.1", "73.3a.2") – anders
  worden bestaande bepalingen als tikfout geweigerd.
- **Een divisie is geen artikel.** `aanduiding_in_woorden` maakt "art. 9 lid 1" of "bepaling 25, 25.1"
  op grond van het knooptype, niet uit het nummer.
- **`ORDER BY` op een IRI is lexicaal**: lid 10 komt dan vóór lid 2 en geneste onderdelen vóór hun
  ooms. Sorteer numeriek (in SPARQL of bij de consument).

## Brongetrouwheid (`provenance.py` + `grounding.py`)

- `provenance.iter_refs` herkent vindplaatsen (BWB-IRI's, jci-strings, kale BWB-id's) in
  **tool-resultaten**; `collect_sources` bouwt de ontdubbelde bronnenlijst. Bronnen komen nooit uit de
  prozatekst van het model.
- **Een annotatie is geen vindplaats.** `urn:jas…`-IRI's bevatten een BWB-id maar worden vóór het
  zoeken weggelaten (`_AFGELEID_RE`); anders lijkt een annotatie wettekst te onderbouwen die niet is
  opgehaald.
- `grounding.check_grounding` toetst op BWB-granulariteit of elk aangehaald BWB-id in de trace staat, en
  of elk citaat (≥ 5 woorden tussen aanhalingstekens; kortere zijn begrippen) letterlijk,
  witruimte-ongevoelig, in de trace staat – dezelfde eis als `annotatie.komt_letterlijk_voor`. Het
  oordeel is `niveau`: **gegrond** / **ongegrond** / **onbepaald** (niets te controleren – géén
  goedkeuring). `grounded` blijft bestaan voor het event-contract en de eval: er is niets aangetroffen
  dat níét klopt.
- `curate_sources` snoeit tot aangehaalde regelingen, en binnen een regeling met een precieze
  vindplaats tot bronnen op het pad daarvan. Omhulsels (`hoofdstuk`, `afdeling`) en datums tellen niet
  mee in het pad: een jci draagt ze vaak, de graaf-IRI niet.

## API-laag (`api/main.py`)

Endpoints: zie `README.md`. De **lifespan** doet fail-fast `require_graph()` en `require_api()`, start
het opwarmen van het spaCy-model op een achtergrondthread, zet de run-store klaar en flusht bij
shutdown de OTel-buffers. Beveiliging: CORS-credentials nooit samen met `*` (elke `"*"` telt als
wildcard), timing-safe token-check, en rate-limit en budgetcheck als **dependency, niet als
middleware** – middleware buffert de SSE. De rate-limit telt per gebruiker (`X-User-Id`, IP als
terugval): al het verkeer komt van één BFF-container, dus op IP tellen geeft één emmer voor alle
juristen. `/v1/runs/{id}/events` heeft geen rate-limit.

### Runs: de beurt is van de server (`agent/runs.py`, `agent/runstore/`)

Een run draait als achtergrondtaak met een eigen, seq-genummerde event-log; een client kijkt mee en
kan opnieuw aanhaken. Regels die je niet mag breken:

- **Losraken ≠ annuleren.** De generator in `runs.volg` is een kijker; het werk zit in `run.taak`.
- **409 is bescherming.** `thread_id == conversation_id`, dus twee gelijktijdige beurten schrijven door
  elkaar in dezelfde checkpointer-thread. De controle geldt over gebruikers heen.
- **Een run heeft een eigenaar.** `X-User-Id` (door de BFF uit de sessie gezet) bepaalt wie hem mag
  volgen en stoppen; andermans run geeft 404. Eén identiteitsbron: de header, niet de body.
- **Cappen is klassebewust.** Alleen `VLUCHTIGE_TYPES` (`token`/`reason`/`status`) mogen sneuvelen;
  er gaat dan een `gat`-event voorop.
- **Stoppen is een vlag, geen `task.cancel()`.** Elke node is gewikkeld in `stopbaar()`
  (`orchestrator.py`): staat de vlag om, dan gooit hij `BeurtGestopt` en betreedt de graaf geen nieuwe
  node. `answer_stream` vangt dat op als gewone afloop, zonder `error`. Taak-annulering breekt de
  MCP-verbinding onder een draaiende executor-thread. De prijs: stoppen kost tijd, en omdat `emit` terminaal
  is levert stoppen dáárvóór nul voorstellen op – het bericht zegt dat.

De store kiest `api/main.py:_maak_runstore`, met dezelfde voorrang als de checkpointer: `GeheugenStore`
(dit proces; lokaal en tests) of `PostgresStore` (met `CHECKPOINT_DB_URL`, gedeeld tussen de twee
replica's). In Postgres is de 409 een **unieke index** (geen check-then-insert), het stopverzoek een
vlag die een polstaak elke 2 s op de `Run` zet (zodat `stop_check()` een synchrone attribuutlezing
blijft), en een hartslag maakt een run van een omgevallen replica na een minuut `mislukt`. Een run
overleeft geen herstart (synchrone nodes, geen resume-pad); de werkplek meldt dat
(`frontend/lib/lopendeRun.ts`).

> **Testen:** gebruik `with TestClient(app)` (zie `tests/test_run_endpoints.py`). Zonder `with` breekt de
> harnas per request zijn event loop af en sneuvelt de achtergrondtaak. Een bare `TestClient` draait de
> lifespan niet, dus de startup-checks storen de meeste tests niet.

### De uitkomst vastleggen (`agent/beurt.py`)

`voer_beurt_uit` zit om `answer_stream` heen, verzamelt de events (`BeurtSchrijver`) en schrijft aan het
eind via `agent/wetsanalyse_api.py`: **eerst de annotatielaag, dan het chatbericht**, gevolgd door één
`opgeslagen`-event. Dit staat **buiten** de LangGraph-code. Een annotatie gaat als één batch per
bronnode: `POST /v1/annotatie/lagen/batch` met `batch_id` (= run_id), `bron_iri`, `snapshot_id`,
`verwachte_revisies`, elementen, dekking, `run` en het beslisregister. Het contract staat in
`docs/architectuur/annotatie-bronnodes.md`.

- **`done` gaat er pas uit ná het wegschrijven** – anders ziet een client die dan herlaadt noch de run,
  noch het bericht.
- **Er wordt pas aan het eind geschreven.** `emit` is terminaal; een laag die al bij het `doel`-event
  ontstond, bleef bij elke afgebroken run als leeg skelet staan.
- **`run_id` is de idempotentiesleutel** van batch, bericht en verbruik; twee meekijkende tabbladen
  leveren geen twee antwoorden op.
- **Niet kunnen schrijven is een zichtbare fout** (`error`), nooit stil verlies. Uitzondering: een 404 op
  het gesprek (`GesprekVerdwenen`) – de jurist verwijderde het gesprek zelf; de beurt eindigt stil en de
  annotatie blijft staan. `DELETE /v1/conversations/{id}` zet bovendien het stopverzoek.
- **Een afgeronde laag** geeft de foutcode `annotatie_afgerond` met de vraag om te heropenen;
  `wetsanalyse_api` logt de reden van de api (`api_reden`, nooit de body).
- **Wat de api niet bewaart, meldt de driver als `waarschuwing`** (geen `error`: de beurt slaagde):
  verworpen elementen (header `X-Verworpen`) en al geannoteerde, ongewijzigde leden. **Lees
  response-headers in kleine letters** – httpx geeft ze zo terug. `tests/test_gedeelde_laag.py` draait
  daarom tegen de échte client met een `MockTransport`.
- **De contractgrens ligt in `wetsanalyse_api.naar_contract`.** Hier `aandacht: str = ""`, bij de api
  `Aandacht | None`: dat verschil is een 422. Vertaal zulke velden op de grens en zet ze in `OPGEVANGEN`
  in `tests/test_contract_drift.py`, dat beide modellen veld voor veld vergelijkt – ook het chatbericht
  tegen `BerichtInvoer` van de api (Pydantic laat onbekende velden stil vallen).
- **Tool-executions worden samengevoegd op `(run_id, call_id)`**, met dezelfde regel als
  `mergeToolExecution` in de werkplek; los bewaard telt de werkplek na herladen elke aanroep dubbel.

Zonder api (`Settings.legt_zelf_vast` is False) is de driver een doorgeefluik; leverde de beurt
markeringen op, dan meldt hij dat ze niet zijn vastgelegd.

> **Vertrouwensgrens.** Het verzoek draagt zelf de `user_id` waarnamens er geschreven wordt, en de api
> bindt `client_id` niet aan `user_id`. Het api-token van graph-qa is daarmee een schrijfprimitief op
> elk gebruikersgesprek. Vandaar `Settings.require_api`: kan graph-qa schrijven, dan weigert hij te
> starten zonder eigen `QA_API_TOKEN`. De BFF vult `user_id` uit de sessie – nooit uit de browser-body.

**Tokenverbruik reist niet als event.** `AnthropicLLM` telt elk `usage`-blok op in een `Verbruiksmeter`
(`agent/models.py`, met een lock: takken kunnen parallel lopen). De aanroeper geeft dezelfde meter aan
`answer_stream` én `voer_beurt_uit`; de driver boekt hem in een `finally` (`POST /v1/verbruik`,
idempotent op `run_id`), zodat ook een mislukte of gestopte beurt telt. Een mislukte boeking is stil
(alleen log). De **pre-check** is `_budget_check` op `POST /v1/runs`: de api is de autoriteit (een
budget in procesgeheugen telt per replica), **fail-open** bij een onbereikbare api, en een lopende beurt
wordt nooit afgekapt – een halve annotatie is erger dan een kleine overschrijding. `/v1/chat` draagt
geen identiteit en krijgt geen check.

## De annotatieketen

```
[ophaal-agent (agent ⇄ tools)] → annoteer → emit → advance
```

Achtergrond en PR-roadmap: `docs/architectuur/adr-001-hybride-jas-pijplijn.md`; de werking en de
configuratie: `docs/architectuur/annotatieketen.md`.

**Een meegegeven `doel` slaat de ophaal-agent over.** Met `doel` (`{bwbId, artikel|nummer, lid?,
citeertitel?}` of `bron_iri`) doet de supervisor geen LLM-call en gaat de beurt recht naar `annoteer`.
Dat is geen besparing maar een garantie: de ophaal-agent is de enige plek waar de keten bij een ándere
bepaling kan uitkomen dan de jurist aanwees. Een half doel (alleen een `bwbId`) telt niet. Het veld
wordt **per beurt gereset** in `answer_stream`, net als de andere annotatievelden.

`annoteer_node` doet na elkaar:

1. **Bron** (`bron_annotatie.lees_bron`): `bronmodel.resolve` levert een snapshot van de bronnode met
   per node een SHA256 en de corpusspans (`CorpusMap`). Een niet-resolvebare vindplaats breekt de beurt;
   er is geen terugval op de tool-trace.
2. **Keuze** – wijst het doel een artikel met leden of een divisie met subbepalingen aan, dan emit hij
   een `kandidaten`-event met `keuze: {soort, ouder, alles}` en per optie `bron_iri`, `nummer`, `soort`,
   `label`, `fragment`, optioneel `stand` (`bron_annotatie.stand_per_optie`) en `gekozen`, en stopt –
   geen modelcall. De gekozen optie komt terug als doel met `bron_iri`. `AgentDoel.geheel` slaat de keuze
   over (alleen voor metingen).
3. **Hergebruik en afronding** (`bron_annotatie.controleer_hergebruik`): de api is leidend
   (`get_annotatiedekking` + `get_annotatieweergave`, als toolspoor). Nodes die al af zijn of een
   afgeronde laag hebben gaan niet opnieuw door de keten; is er niets meer te doen, dan stopt de beurt
   vóór de eerste modelcall (volledig hergebruik: `emit` stuurt `hergebruik` + een `run` met
   `modus="hergebruik"`). **Een onleesbare dekking stopt de beurt** – een api-storing is geen bewijs dat
   annotaties ontbreken. Daarom kan de keten niet annoteren zonder api. `hergebruik: "opnieuw"`
   annoteert alles opnieuw, behalve afgeronde lagen.
4. **Analyse** (`jas_pipeline.keten.analyseer`): de hele bepaling is context, alleen de niet-hergebruikte
   nodes leveren kandidaten. De classificatiebatches gaan tegelijk naar het model
   (`CLASSIFIER_PARALLEL`, `_classificeer_batches`), elk met een eigen meting en in batchvolgorde terug.
   `make_settings` in de tests zet 1, omdat de gescripte `FakeLLM` op volgorde antwoordt. Het
   spaCy-model laadt bij het opstarten op een achtergrondthread, met een lock in de provider.

**Een ONDERWERP in plaats van een bepaling** ("annoteer alles over aansprakelijkheid van de bestuurder")
levert een keuze, geen annotatie: de ophaal-agent geeft `{"kandidaten": [...]}` terug, `annoteer_node`
emit één `kandidaten`-event en stopt. Welke bepaling de werkvoorraad in gaat, kiest de jurist.

**Eén artikel per annotatievraag.** Noemt de vraag meer artikelen, dan wijst `aanwijzing.lees_aanwijzing`
(deterministisch) haar af vóór de ophaal-agent draait; de ophaal-JSON `{"meerdere": [...]}` en
`doel._meerdere_artikelen` vangen de rest. "Artikel 9 lid 1 en 3" wordt het artikel met die leden
vooraf aangevinkt op de keuzekaart.

**Meerdere onderdelen zijn één run: een reeks** (`agent/reeks.py`). `doelen` (2–60, elk met `bron_iri`,
sluit `doel` uit) → vooraf toetst `bronmodel.gedeelde_bepaling` dat alle doelen kiesbare onderdelen van
dezelfde bepaling zijn → per doel de gewone beurt, na elkaar, met eigen `run_id` `<run>.<n>` en een eigen
bericht met `reeks: {run_id, index, totaal, ouder}`. De stroom krijgt `reeks`- en `onderdeel`-events
(start/eind) en elk event daartussen `onderdeel: <bron_iri>`; er is één `done`. Vóór elk volgend
onderdeel: stopverzoek en budget (fail-open); een fout in één onderdeel stopt de rest niet.

### De pijplijn (`agent/jas_pipeline/`)

Pure functies zonder LangGraph. Onderdelen: taalanalyse (`taal/`: een UD-model met verwisselbare
providers; spaCy `nl_core_news_md`, zie `docs/architectuur/adr-002-taalprovider.md`), detectieprofielen
per klasse (`profielen/*.yaml`, officiële tekst alleen via `H2:NN`), het kandidaatmodel
(`kandidaten.py`), de detectoren (`detectoren/`), fusie, deterministische besluiten (`besluit.py`), de
classifier (`classificatie.py`), validatie (`validatie.py`, `V_*`-codes), twijfel (`onzekerheid.py`), de
reviewer (`review.py`), de resolver (`resolver.py`), dekking, beslisregister en subtype.

- **Een detectorregel wijzig je in `detectoren/regels/*.yaml`, met vier testsoorten erbij** (positief,
  negatief, rand, overlap) – `tests/test_detectoren.py` weigert een regel zonder. Hoeveel
  referentiespans de detectoren aanreiken meet `python -m eval.kandidaat_eval` (seconden, geen model);
  dat is ankerdekking, geen recall.
- **Het model kiest, het typt niet.** De classifier krijgt labels, fragmenten, bewijscodes en de
  toegestane beslissingen en antwoordt via één `strict` tool met enums. Een ongeldige of ontbrekende
  beslissing wordt `UNCERTAIN` met een reden – nooit geraden, nooit stil weggelaten.
- **`tool_choice` blijft `auto` en `temperature` staat standaard uit**: geforceerde tool-use en
  sampling-parameters geven op de nieuwste modellen een 400. Wat er gebruikt is, staat in
  `run.instellingen` (met de meting onder `run.instellingen.meting`).
- **Geen terugval naar een generatieve prompt.** Zonder spaCy-model draait de keten gedegradeerd
  (`niveau=TOKENS`, alleen lexicale en structurele detectoren) en zegt dat in de meting, de statusregel
  én een `waarschuwing`-event.
- **Een gerichte reviewer, alleen op twijfel.** `onzekerheid.py` signaleert `DETECTOR_CONFLICT`,
  `CLASSIFIER_ABSTAIN`, `ZELFDE_SPAN` en `DEGRADED_PARSE`; de eerste drie gaan naar de reviewer
  (KEEP / CHANGE / HUMAN_REVIEW per geval, via een `strict` tool). Wat dat oordeel doet beslist
  `resolver.TABEL`, elke transitie in `meting["resolutie"]`: onenigheid wordt HUMAN_REVIEW (geel, met
  alternatieven), een CHANGE tegen JAS-PRIORITY wordt niet uitgevoerd, en er wordt nooit iets
  automatisch "rood" doorgevoerd. `GERICHTE_REVIEW=false` stuurt de twijfelgevallen direct geel naar de
  jurist. De uitleg van de reviewer staat op het element in het veld `review_uitleg`.
- **Een technische storing is geen juridische twijfel.** Een ongeldige classifierkeuze blijft
  `CLASSIFIER_ABSTAIN` met dezelfde afhandeling, maar draagt `categorie: CLASSIFIER_CONTRACT_ERROR` en de
  gele kaart zegt "Technische storing". Bij `R-ONGELDIG` bewaart de resolutie `oordeel_ruw` en
  `ongeldig_omdat`; `meting.reviewload` (`reviewload.py`) splitst geel in juridisch en technisch. Zet
  `categorie` nooit in de reviewer-prompt: dat is een promptwijziging, en die hoort pas na de
  V7-baseline.
- **Het JAS-subtype** (`subtype.py`: variabele/variabelewaarde, parameter/parameterwaarde,
  delegatiebevoegdheid) wordt alleen gezet bij eenduidig bewijs uit de detectiecodes, anders leeg. Het
  reist via het contract naar de api, de graaf (`jas:subtype`) en de exports.
- **Elke code in een `trace` heeft een verklaring** in `verklaringen.yaml`; `tests/test_verklaringen.py`
  weigert een code zonder verklaring en een verklaring zonder code. Draai daarna
  `python scripts/genereer_jas_vocabulaire.py`: die schrijft de vocabulairegraaf en `verklaringen.json`
  naar `api/app/vocabulaire/`, bewaakt door `tests/test_vocabulaire_drift.py`.
- **De klassenduiding komt uit de skill.** Het JAS_KLASSEN-blok in `agent/jas_klassen.py` en
  `agent/methodepakket.py` worden gegenereerd door `scripts/genereer_jas_klassen.py` (CI draait
  `--check`), bewaakt door `tests/test_methode_drift.py`. Bewerk de markdown in
  `.claude/skills/wetsanalyse/`, niet de Python.

### Wat `emit` uitstuurt

- **`emit_node` is de enige plek die annotatie-events uitstuurt**: `hergebruik` (als van toepassing),
  één `run`, `dekking`, een `element` per voorstel en de samenvattings-`token`.
- **Offsets komen nooit van een model.** `bron_annotatie.lokale_elementen` valideert de ankers tegen de
  snapshot (`bronmodel.valideer_ankers`: bestaan, bereik, hash, letterlijkheid) en bepaalt de eigenaar
  als diepste gemeenschappelijke bronnode. Een element zonder controleerbaar anker is een fout.
  Voorstellen houden de contractvorm (`ankers` per bronnode + `trace`); ids zijn deterministisch
  (kandidaat + klasse + grens).
- **Elke beurt meldt zijn herkomst.** Het `run`-event draagt `model`/`provider`/`agent_versie`/`modus`,
  `prompt_hash` (= `classificatie.promptversie`), `methode_versie` (= `jas_klassen.methode_versie()`) en
  `instellingen` met de meting. Per element staat de route in `trace` (bewijs, vraag, besluit, validatie,
  twijfel, resolutie); `tests/test_provenance_element.py` toont de zestien vragen die daarmee te
  beantwoorden zijn.
- **`dekking`** gaat vóór de elementen en zegt wat de keten wel en niet kon bekijken: per bronnode de
  dimensies en de ongedekte zinsdelen mét offsets, de procesdekking en de fasen met duur. Het draagt ook
  het **beslisregister** (`jas_pipeline/beslisregister.py`: per kandidaat de uitkomst, ook de
  afgewezen). Dat gaat met de batch naar de api en bewust níét in het chatbericht of op de elementen.
  Dekking is nooit te lezen als recall.
- **Geel is een vraag, geen oordeel.** De werkplek toont de alternatieven als aanklikbare chip.
- **Dezelfde markering komt maar één keer terug.** Zonder id is de sleutel `annotatie.sleutel_van(tekst,
  lid)` – genormaliseerde tekst + lid, **zonder klasse**, zodat een herclassificatie hetzelfde element
  treft. Dezelfde regel staat in `mergeVoorstellen` van de werkplek, bewaakt door
  `tests/test_ontdubbelsleutel.py`.

## De leesroute: vragen óver bestaande annotaties

1. **Herkenning is hard** (`tools/annotatie_tools.py:is_leesvraag`): een onderwerp (annotatie, markering,
   element, klasse, …) plus een leeswoord en géén schrijfwoord (`markeer`, `classificeer`), of
   `modus: "annotaties_lezen"`. Een kale klassenaam telt níét – *Voorwaarde* is ook gewone juridische
   taal. Een leesvraag kan zo topologisch geen annotatie worden; `annoteer` en `emit` weigeren
   bovendien expliciet in de leesroute.
2. **Zoeken is een stap, geen keuze** (`nodes/annotatie_lezen.py`). `annotaties_zoeken` voert vóór de
   eerste LLM-call zelf `search_annotaties` uit, met filters uit de vraag (`jas_klassen.klassen_in_tekst`)
   en het doel. Het resultaat gaat als echt `tool_use`/`tool_result`-paar de historie en de
   `source_trace` in; daarna formuleert de agent, met de tools beschikbaar voor verdieping. Laat je dit
   aan de vrije toolkeuze over, dan antwoordt het model soms zonder te zoeken dat het niet kon
   raadplegen.
3. **Een storing wordt nooit een leeg antwoord** (`begrens_antwoord`): zonder bruikbaar zoekresultaat
   vervangt die het modelantwoord door een eerlijke melding, met een logregel. Die melding gaat **niet**
   in `messages`: anders leest het model zijn eigen "ik kon niet raadplegen" in de volgende beurt als
   feit.

**Wat de doelbepaling leest is alleen deze beurt** (`doel._deze_beurt`). De thread bewaart alle
beurten; las `_doel_uit_toolcalls` de hele historie, dan filterde de leesroute op de wet van een
eerdere vraag en gaf "annoteer artikel 10" na artikel 9 een melding over meerdere artikelen.

**Het model ziet een compacte uitkomst** (`annotatie_tools.compacte_uitkomst`): status en
volledigheid vóórop, per treffer id, klasse, tekst, `vindplaats` ("BWBR… art. 9 lid 1"), aandacht,
alternatieven en een ingekorte toelichting – zonder `geproduceerd_door`, die per element de run van
de hele batch meedroeg. `get_annotatie` houdt het spoor (`trace`). Klassenamen worden vóór de api
genormaliseerd ("rechtssubjecten" → `Rechtssubject`); een 400/422 geeft de reden van de api mee als
`detail`. Een vraag met `modus: "advies"` is nooit een leesvraag.

De drie annotatietools lopen via de api (`agent/annotatie_read.py`), niet via SPARQL: de api verifieert
zijn graafkandidaten tegen Postgres, en die controle mag niet te omzeilen zijn. De actor is de
rungebruiker; een CLI/MCP-client zet `ANNOTATIE_READ_USER_ID` uit vertrouwde configuratie – een
toolargument bepaalt nooit namens wie er gelezen wordt. `aantal` in een `tool_execution` staat er alleen
als het antwoord een lijst of element draagt.

## Routering: afwijzen, advies en modellen

**Afwijzen eindigt bij de supervisor.** `PLAN: AFWIJZEN` → `_entry_node` → `afwijzen`: één beleefde
melding, geen specialist, geen graafverkeer. Afwijzen mag alleen als de vraag **niet over wetgeving
gaat**. Of een bepaalde regeling in de graaf zit weet de supervisor niet (hij heeft geen tools), dus
zo'n vraag gaat naar de antwoord-worker, die zoekt en zelf zegt als er niets is. Een afwijzing kost
niets, een onterechte kost het antwoord. De vlag hoort in de per-beurt-reset van `answer_stream`,
anders wijst één afgewezen vraag de hele thread af. De workerlijst is een **allowlist**
(`antwoord`/`annotatie`) met een cap van twee: een onbekende naam zou anders een extra antwoord-worker
worden.

**Advies bij twijfel** (`modus: "advies"`, op `/v1/runs` én `/v1/chat`): de supervisor routeert hard naar
de `duiding`-specialist, dus een adviesvraag kan topologisch geen annotatie wijzigen. `ChatRequest`
eist een context met minimaal een fragment, `bwbId` of `bron_iri`. `_advies_context` (in
`orchestrator.py`) bakent de vraag af tot dát element: andere markeringen mogen erbij als dat nodig is,
maar krijgen geen eigen motivering, "ook niet als je ze eerder in dit gesprek hebt voorgesteld" – de
tegenkracht tegen het gespreksgeheugen. De buren komen uit `context.bestaande_elementen` (begrensd op
20), niet uit de historie. Gebruik "ONDERWERP" daar niet als kopje: dat woord is in de systeemprompt al
de onderwerp-afbakening.

**Model per rol.** `LLM_MODEL_ROUTER` en `LLM_MODEL_OPHAAL` zetten supervisor en ophaal-agent op een eigen
model (`Settings.model_voor`). Classifier, reviewer en QA-specialisten draaien altijd op `LLM_MODEL`:
wie een oordeel velt over wetgeving hoort niet met een env-var te verzwakken.

## Kern-invarianten (niet breken)

- **Brongetrouwheid.** Bronnen én grounding komen uit de tool-trace, nooit uit modeltekst. "Niets te
  controleren" is `onbepaald`, geen goedkeuring.
- **Het annotatiecorpus is één bronnode**, gericht opgehaald via `bronmodel.resolve`. Reconstrueer het
  **niet** uit de tool-trace: die plakt alle fetch-resultaten aaneen en is afgekapt op 8000 tekens.
- **Offsets komen nooit van een model** (zie §*Wat `emit` uitstuurt*).
- **`GRAPHDB_MCP_URL` en `GRAPHDB_TOKEN` zijn verplicht**, afgedwongen bij startup én per request
  (`make_graph → require_graph`). Maak het token niet optioneel: op Azure is de netwerkgrens het slot en
  negeert GraphDB het token, maar de code blijft fail-closed voor een opzet met een auth-proxy.
- **Geen vrije SPARQL voor het model.** Nieuwe retrieval = een getypeerde tool in `tools/` met een
  bouwer in `graph/queries.py`. `raw_sparql` blijft de afgeschermde ontsnapping; `graph_schema` levert
  het vocabulaire en de IRI-patronen, zodat die ontsnapping niet op geraden predicaten draait.
- **DI, geen globale clients.**
- **SSE-event-contract.** De event-types zijn het contract met de werkplek; wijzig ze bewust,
  gelijktijdig en over beide wegen (`/v1/chat` én de run-events). **`reason` = het denkproces, `token` =
  alléén het eindantwoord** – houd ze gescheiden. `waarschuwing` betekent dat de beurt slaagde maar niet
  alles bewaard is; dat is iets anders dan `error`. `error` draagt `soort` (de exception-naam) naast de
  gesaniteerde melding, zodat de eval een providerstoring van een inhoudelijke fout onderscheidt.
- **De keten meldt zich per fase, met duur, in één idioom: `Actor · wat er gebeurde`.** Alle
  statusregels lopen via `narratie._stap(writer, actor, bericht)`; een test bewaakt de vorm. De
  annotatiefasen komen uit `analyseer` via zijn `melding`-callback (`Taalanalyse` / `Detectie` /
  `Besluit` / `Classificatie` / `Review` / `Resultaat`), met `(0,4 s)` in de tekst en `duur_ms` op het
  event – de tekst reist als `denk` mee naar het chatbericht en is zo na herladen nog te zien. De
  antwoordroute meldt `Controle · …`, `Correctie · …`, `Synthese · …`, `Klaar · N bronnen`; de
  LLM-narratie zelf blijft `reason`.
- **Onderwerp-afbakening & injectie.** De agent antwoordt alleen over wetgeving en behandelt graaftekst
  als data. Verzwak `SYSTEM_PROMPT`/`SUPERVISOR_SYSTEM` hierin niet zonder reden.

## Tests & eval

```bash
cd tools/graph-qa && uv run --extra dev pytest -q
cd tools/graph-qa && uv run --extra dev pytest tests/test_orchestrator.py -q
cd tools/graph-qa && uv run --extra dev pytest -m integration          # vraagt RUNSTORE_TEST_DSN (Postgres)
cd tools/graph-qa && uv run python scripts/genereer_jas_klassen.py --check
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --offline               # QA-harnas, gescript
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --annotatie --offline   # annotatie-harnas
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --annotatie             # live (kost geld)
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --gesprek --offline     # gesprekken-harnas
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --gesprek               # live (kost geld)
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --retrieval-smoke       # live, alleen de graaf
```

- **`tests/fakes.py`** levert `FakeLLM` / `FakeGraph` / `make_settings`. `FakeLLM` speelt een vaste reeks
  Anthropic-responses af via `create()` én `stream()` (gedeelde index); bouw multi-turn-scenario's met
  `response([text_block(...), tool_block(...)], stop_reason)`. `make_settings` zet de checkpointer
  in-memory en `CLASSIFIER_PARALLEL` op 1.
- **De retrieval-smoke heeft bewust géén offline-variant.** Hij raakt elke graaftool één keer tegen de
  échte graaf en meldt een lege uitkomst waar data hoort – precies wat een `FakeGraph` niet kan meten.
  `_wacht_op_graaf` stopt bij drie identieke fouten in plaats van het wachtbudget leeg te draaien: een
  fout die niet door wachten overgaat (zoals een ontbrekende handshake) mag niet als "graaf nog niet
  gereed" lezen.

**Live meten gaat via de eval-job, niet vanaf je machine.** `run_eval.py` draait de agent in-proces en
heeft een directe graafverbinding nodig, en GraphDB staat op Azure op `external: false`. Draai
`azure-infra.yml` → actie **`eval`** (per straat): de retrieval-smoke en daarna `--annotatie` **drie
keer**, met het rapport in de workflow-samenvatting. Drie, omdat dezelfde bepaling tussen runs sterk
verschillende uitkomsten geeft: lees precisie/recall en span-IoU als bandbreedte; de garanties horen
wél op 100%. Niet vlak na een deploy draaien: de importjob loopt dan nog.

- **De eval-job draait hetzelfde image als de app.** `graph-qa-docker-publish.yml` werkt na de app ook
  `<appName>-eval` bij; controleer met `azure-infra` → `inventaris` dat beide dezelfde digest tonen.
  Een rapport gaat over de uitgerolde code, niet over je werkkopie.
- **De job draagt bewust geen `WETSANALYSE_API_URL`/`_TOKEN` en geen `CHECKPOINT_DB_URL`**: anders landt
  elke eval-run in de werkvoorraad van een jurist en in de gedeelde thread-store. Een meting mag de
  gemeten toestand niet veranderen. Hij zet wel `CHECKPOINT_DB_PATH=/tmp/…` (de relatieve default is in
  `/app` niet schrijfbaar) en `LLM_TIMEOUT_SECONDS=45`.
- **De suite bewaakt zichzelf** (`SUITE_MINUTEN`/`SUITE_TOKENS` in `eval/run_eval.py`): bij overschrijding
  vallen de resterende cases af en volgt een onvolledig maar leesbaar rapport. Elke case meldt zijn
  voortgang; `python -u` in de job is daarvoor voorwaarde (gebufferde uitvoer geeft Log Analytics
  willekeurige volgorde).
- **Een storing is geen kwaliteitsregressie.** Een case die sneuvelt op een overbelaste provider of een
  bereikt budget heet **niet gemeten** en telt niet mee; de exitcode kijkt alleen naar gemeten cases, en
  zijn ze allemaal ongemeten, dan wordt de run rood.

**Drie gouden sets.** `eval/golden.jsonl` meet antwoorden (citaat-faithfulness, bron-recall, refusal);
`eval/golden_annotatie.jsonl` meet de annotatieketen; `eval/golden_gesprek.jsonl` meet
**vervolgvragen**: gesprekken van een paar beurten in één thread (scenario A doorvragen op een
antwoord, B vragen naar andere annotaties, C doorvragen op een element, R regressies), per beurt
gescoord op route, tools en antwoord (`eval/gesprek.py`). De route komt uit de `status`-regels en de
tools uit `tool_execution` – wat de jurist ziet, niet een apart eval-kanaal. Omdat de eval-job geen
api heeft, annoteert en zoekt hij via `GesprekAnnotaties`: die onthoudt wat Lex in dat gesprek
markeerde plus de `andere_annotaties` die de case zaait. De gesprekken zijn een trendmeting en tellen
niet mee in de exitcode van de job. De annotatie-scorers splitsen:

- **Garanties** (slaag/zak, horen op 1.0): elk fragment staat letterlijk in de bron, elke klasse
  bestaat, niets komt uit een niet-gevraagde bepaling (`verboden`), en een injectie in de opdracht wordt
  niet opgevolgd (`kanaries`). Zakt er één, dan is een garantie gesneuveld.
- **Trendmeting** (gerapporteerd, geen slaagcriterium): precisie en recall tegen `verwacht`.

**`golden_annotatie.jsonl` is een ANKERSET**: `verwacht` bevat de elementen die een competente annotator
hoe dan ook moet vinden, niet de volledige analyse. **Recall** is dus de bruikbare maat; **precisie**
deelt door alles wat de agent voorstelde en is geen kwaliteitsoordeel. Precisie/recall tellen alleen
over cases mét ankers. Ankers komen uit `eval/bronteksten.json` (de letterlijke tekst uit de importer);
`tests/test_golden_annotatie.py` bewaakt dat elk anker daar letterlijk in staat, dat de klassenaam
bestaat met de juiste hoofdletters en dat geen anker met het lidnummer begint – anders zakt een
overgetypt fragment stil weg als "niet gevonden". De cases zijn gekozen op **signaal per teken**: de
kosten volgen de corpusomvang, dus een korte bepaling met veel verschillende JAS-signalen meet meer per
euro dan een lange. Eén case annoteert een heel artikel, zodat het pad met meerdere leden gedekt is.
Nog **niet** gemeten: injectie via graafdata.

**De keten vergelijken en rapporteren.**

- `eval/compare_pipelines.py`: per casus dezelfde bronfixture, P/R/F1 op positie, stabiliteit,
  efficiëntie en foutcategorieën volgens `eval/fouttaxonomie.py` (`debatable` telt nergens mee); ook de
  maten voor alleen onbetwiste voorstellen, want geel is een vraag. Alleen `hybrid_v1` is meetbaar
  (`MEETBAAR`); oudere rapporten blijven leesbaar (`ROUTES`). `--offline` toetst het harnas.
- `eval/laagrapport.py` (validatieplan V6): per laag kandidaat, span, classificatie, proces, contract en
  stabiliteit, per familie en tekstsoort; fouten apart naar juridisch, technisch en evaluatie; geen
  totaalscore; de relationele checklist als invulbijlage.
- `eval/stabiliteit_analyse.py`: detectie-, span- en klassestabiliteit per casus. Hoge overeenstemming
  is geen kwaliteitsbewijs – zie `docs/architectuur/metingen/README.md`.

## Deployment & integratie

- **CI:** `.github/workflows/graph-qa-docker-publish.yml` – test (`uv sync --extra dev --extra mcp`,
  `genereer_jas_klassen.py --check`, pytest) → build naar GHCR (bouwcontext = repo-root, want het image
  neemt `packages/bronmodel` mee) → Trivy-gate → uitrol naar acceptatie met health-gate, daarna de
  eval-job. Hij draait ook bij wijzigingen in `packages/bronmodel/**` en `.claude/skills/wetsanalyse/**`.
- **Azure** (`deploy/azure/main.bicep`, `<appName>-graph-qa`): intern (`external: false`), poort 8080,
  `maxReplicas: 2`. Secrets als bestanden onder `/run/secrets` via `*_FILE`-env (`config._read_secret`);
  gespreksgeheugen en run-register in Postgres (`CHECKPOINT_DB_URL_FILE`); `SIMILARITY_INDEX=bwb_similarity`;
  `ENABLE_DECOMPOSITION=0`. `tests/test_deploy_drift.py` bewaakt dat de bicep `WETSANALYSE_API_URL`/`_TOKEN`
  zet – zonder die twee legt de agent niets vast en toont de werkplek markeringen die nergens landen.
- **Werkplek:** de frontend gebruikt de run-endpoints (BFF-routes in `frontend/app/api/annotatie/run/**`);
  de review-state en de wettekst van het paneel lopen via de api (`/v1/annotatie/*`), waar graph-qa
  zelf naar schrijft.

## Aandachtspunten

- `semantic_search` vereist een bestaande similarity-index; zonder degradeert hij naar
  `search_wetgeving`. De index overleeft een GraphDB-herstart niet; de importer bouwt hem terug.
- GraphDB draait op Azure zonder eigen security; de netwerkgrens is het slot. De read-only-guard in
  `mcp_client.py` (`_reject_updates`) is wat een schrijf-SPARQL vanuit de agent tegenhoudt.
- **SSE-client-disconnect:** de nodes zijn synchroon en draaien in de default-executor; een
  `run_in_executor`-future is niet annuleerbaar. Valt de client weg, dan loopt een in-flight LLM-call
  (timeout `LLM_TIMEOUT_SECONDS`) of MCP-call nog door, ook als `finally: graph.close()` de httpx-client
  al sloot. `MCPClient.close()` is daarom best-effort (idempotent, slikt fouten). Volledige annulering
  vergt async-nodes; bewust niet gedaan.
