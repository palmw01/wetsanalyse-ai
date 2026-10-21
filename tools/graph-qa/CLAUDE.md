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
| `nodes/overzicht.py` | de overzichtsroute: overzicht en tekst uit de graaf, zonder model |
| `nodes/werkgebied.py` | de werkgebied-worker: één stap van het samenstellen van een werkgebied (activiteit 1) |
| `nodes/agent_taak.py` | één taak van een agent op een werkgebied (deelvragen, begrippen, het werkgebied annoteren; F3c) |
| `nodes/context.py` | `Bouw` – wat een node buiten zijn state om nodig heeft |

De nodes zijn gewone functies `(b: Bouw, state)`; `Bouw` draagt de poorten, de stopvlag, de drie
modelnamen en de contexthelpers, en `build_graph` bindt hem met `functools.partial`. **Roept een node
een andere aan, geef `b` dan expliciet door** – de suite wijst die valkuil aan.

```
supervisor ─┬─ antwoord-worker:  agent ⇄ tools → verify → (correct) → finalize → advance
            ├─ annotatie-worker: [agent ⇄ tools als ophaal-agent] → annoteer → emit → advance
            ├─ leesroute:        annotaties_zoeken → agent ⇄ tools → verify → finalize
            ├─ begrippen lezen:  begrippen_zoeken → agent ⇄ tools → verify → finalize
            ├─ overzichtsroute:  overzicht_bouwen → verify → finalize   (geen model; bij een bouwfout → agent)
            ├─ werkgebied-worker: werkgebied_intake → einde              (één stap van het samenstellen)
            ├─ agents:           agent_taak → einde                        (deelvragen, begrippen; F3c)
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
  worker(s), specialist en plan kiest; de focus (GESPREKSCONTEXT) gaat als context mee. Een
  leesvraag (`is_leesvraag`), een meegegeven `doel` of `modus: "advies"` beslist hij zonder LLM-call.
  **In een lopend gesprek leest hij eerst het gesprek** (`berichten.eerdere_beurten`: de laatste drie
  beurten als vraag + antwoord, zonder tool-ruis, en `VERVOLG_SYSTEM`) en zet hij een `VRAAG:`-regel:
  de vervolgvraag zelfstandig herschreven. Die `zelfstandige_vraag` voedt `is_leesvraag`,
  `lees_aanwijzing`, het klassefilter van de leesroute en het plan van de specialist; het
  user-bericht in de historie blijft de echte vraag. Een vraag óver een gemaakte markering is
  `duiding`, geen `annotatie`. Bij de eerste vraag van een gesprek verandert er niets (geen extra
  tekst, geen extra call).
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
- **`finalize_node`** – `collect_sources` → `curate_sources` → `met_regelingnamen` → emit `sources` +
  `grounding`; werkt `entities_seen` bij.

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

**De focus: waar het gesprek over gaat** (`agent/focus.py`, `State.focus`). Naast de berichten houdt
de thread een kleine, gestructureerde toestand bij:

- na een annotatie: de bepaling (`bron_iri`, label) en haar markeringen als `id · klasse · tekst`;
- na een antwoord: de geraadpleegde bronnen (de markeringen blijven staan);
- bij advies: het aangewezen element.

`focus.als_context` maakt er het GESPREKSCONTEXT-blok van. Dat gaat naar de supervisor én elke
specialist (`Bouw.memory_context`), samen met de markeringen van de open bepaling
(`context.bestaande_elementen`), die anders alleen bij advies werden gelezen. Het veld staat bewust
**niet** in de per-beurt-reset.

**De focus is context, geen filter.** Ze stuurt nooit zelf een doel of een zoekopdracht: "welke
rechtssubjecten ken je nog meer uit andere annotaties" gaat juist over iets anders dan de focus. De
geheugenregel na een annotatie draagt nu ook de bronnode en de element-id's, zodat `get_annotatie`
bruikbaar is.

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

- **`tools/__init__.py`** – `TOOLS` (27 declaraties: 21 graaftools, de vier annotatieleestools uit
  `tools/annotatie_tools.py` en de twee begrippenleestools uit `tools/begrip_tools.py`), `anthropic_schemas(only=)` en `dispatch()` (vangt
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

- **Elke graaftool levert het resultaatcontract** (`agent/resultaat.py`), dezelfde vorm als de
  annotatie-leestools: `{status, volledig, aantal, totaal?, vervolg?, resultaten, toelichting?}`. De
  tool begrenst zelf, op een natuurlijke grens (een rij, een lid, een structuurniveau), binnen
  `resultaat.BUDGET`, gemeten op de exacte JSON die het model krijgt. **Er wordt niets afgeknipt**:
  dat leverde een inhoudsopgave op IRI-volgorde, op 8000 tekens doorgesneden, waarin het model de
  gaten met "…" vulde. De betekenis ligt vast:
  - `volledig` = alles binnen de scope van déze aanroep staat erin (niet: alles over de bron);
  - `vervolg` als en alleen als `volledig` false is – de aanroep die dezelfde set aanvult, mag een
    andere tool zijn en is geldig tegen het schema van `vervolg.tool`;
  - `openen` op een rij = verdieping buiten de scope (een ingeklapt deel), geen onvolledigheid;
  - `aantal` = `len(resultaten)`; andere tellingen staan op de rij of in een eigen veld;
  - `status` is `ok` of `error` + `reden`. Een ondeelbare eenheid boven de begroting
    (`ondeelbare_eenheid_te_groot`) en een tool die zijn begroting overschrijdt
    (`resultaatcontract_overschreden`, `tool_resultaat_te_groot` in log en event) zijn fouten: het model
    krijgt dan zichtbaar géén resultaat, nooit een ingekort. `has_more` in het event is `not volledig`.
  - Consumenten lezen de **waarden**, niet de JSON-tekst: `resultaat.waarden` voor grounding en
    bronnen (anders valt een citaat over een `\n` in de JSON af).
  - `raw_sparql` is streng: alleen SELECT, een LIMIT (≤ 200) op het hoogste niveau, en het hele
    resultaat binnen de begroting – anders een foutresultaat met de reden (`limit_ontbreekt`,
    `alleen_select`, `resultaat_te_groot`). Vrije SPARQL herschrijven is foutgevoelig; weigeren met
    uitleg niet.

  `tests/test_resultaatcontract.py` draait elke graaftool tegen een worst-case graaf (honderden rijen,
  lange teksten, LIMIT/OFFSET) en eist: contract-JSON binnen de begroting, geen lege velden, `vervolg`
  en `openen` geldig tegen hun tool, ORDER BY bij paginering, en dat alle pagina's samen precies de
  dataset zijn. Gerangschikte lijsten vragen `limit + 1` rijen op (`queries._pagina`).
- **`inhoudsopgave` is een boom in documentvolgorde** (`agent/graph/structuur.py`): `bwb:volgtOp` met
  een natuurlijke terugval (hoofdstukken Romeins), opeenvolgende artikelen zonder titel als één rij
  met hun echte `nummers` (geen "32–35" dat een artikel 34 suggereert), zo diep als binnen de
  begroting past en nooit een half niveau. Een ingeklapt deel draagt zijn tellingen en `openen`
  (`vanaf` = zijn IRI; een nummer als "1" is dubbelzinnig: afdeling 1 komt in elk hoofdstuk terug). Past het bovenste niveau zelf niet (de Leidraad: ~800 divisies met
  titel), dan pagineert hij dat met `offset`.

- **Een overzichtsvraag is een vraag naar de opbouw** (`zoek_opbouw`, `queries.zoek_opbouw`). "Welke
  artikelen gaan over invordering?" gaf met `search_wetgeving` de bepalingen waarin het woord toevallig
  staat (Iw art. 4, 63, 68) en miste de hoofdstukken die er echt over gaan. `zoek_opbouw` zoekt in de
  opschriften van hoofdstuk, titeldeel, afdeling, paragraaf en divisie (alleen een divisie mét
  subdivisies; anders overspoelen de ~800 Leidraad-bladeren alles) en noemt per deel de bepalingen.
  **De Lucene-query bouwt de tool zelf** (`opbouw_lucene`): de index bevat stammen en een wildcardterm
  wordt niet geanalyseerd, dus `invordering*` mist "Invordering in eerste aanleg" (`invorder`) en
  `invordering` mist "Dwanginvordering". Per woord gaat het woord zelf óf `*stam*` de query in.
  Dezelfde vraag geeft zo dezelfde query, ongeacht wat het model als zoekterm verzint.
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
- **Structureel pagineren, op hele eenheden** (`resultaat.per_eenheid`). `get_artikel` levert de leden
  (de onderdelen onder een lid horen bij `get_lid`), `get_lid` de onderdelen – één rij per onderdeel,
  met zijn eigen jci, in documentvolgorde (a … z vóór aa, een genest onderdeel direct na zijn ouder;
  `ORDER BY ?o` is lexicaal) – en `get_bepaling` de subdivisies, numeriek gesorteerd. Past het niet,
  dan gaat `vervolg` verder bij de eerstvolgende eenheid; een lid of onderdeel wordt nooit
  doorgeknipt. De gegevens van de bepaling zelf (tekst, jci) staan één keer apart in het resultaat.
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
- **Eén bepaling is één bron.** `collect_sources` ontdubbelt op de bronnode uit
  `bronmodel.vindplaats` (dezelfde regels als de importer en `bronDoel` in de werkplek; de vectoren in
  `frontend/lib/jci-vectoren.json` toetsen alle drie). `uri` is de graaf-IRI, `iri`/`jci` bewaren beide
  vormen, `label` is leesbaar ("Artikel 26a, lid 2", "Hoofdstuk I") en `bron_iri`/`bwb_id`/`soort`
  reizen mee. Een hoofdstuk valt dus niet samen met de regeling. `regelingnamen.met_regelingnamen`
  zet daarna met één query per beurt de citeertitel in `regeling`. Het label komt waar nodig uit het
  toolresultaat (`_labels`): een wet-lokale `id:`-node (Leidraad 26.5) krijgt zo zijn naam in plaats van
  zijn IRI, en een structuurdeel zijn titel ("Hoofdstuk II – Invordering in eerste aanleg") – daaraan
  herkent de werkplek het deel in de tekst (cache per proces; een fout kost
  alleen de naam).
- **Een annotatie is geen vindplaats.** `urn:jas…`-IRI's bevatten een BWB-id maar worden vóór het
  zoeken weggelaten (`_AFGELEID_RE`); anders lijkt een annotatie wettekst te onderbouwen die niet is
  opgehaald.
- `grounding.check_grounding` toetst op BWB-granulariteit of elk aangehaald BWB-id in de trace staat, en
  of elk citaat (≥ 5 woorden tussen aanhalingstekens; kortere zijn begrippen) letterlijk,
  witruimte-ongevoelig, in de trace staat – dezelfde eis als `annotatie.komt_letterlijk_voor`. Het
  oordeel is `niveau`: **gegrond** / **ongegrond** / **onbepaald** (niets te controleren – géén
  goedkeuring). `grounded` blijft bestaan voor het event-contract en de eval: er is niets aangetroffen
  dat níét klopt.
- **Getoetst wordt tegen het gesprek, niet alleen tegen deze beurt** (`agent/bronregister.py`,
  `State.bronregister`). Het register bewaart over beurten heen de tool-resultaten zelf (begrensd:
  24 items, 60k tekens), plus de geannoteerde brontekst na een annotatie. `verify_node` toetst tegen
  register + trace, zodat een vervolgantwoord een eerder opgehaald citaat mag herhalen; zonder dit
  haalde de correctieronde bij doorvragen juist de onderbouwing weg. Het register bevat nooit
  modeltekst en nooit annotatieresultaten. Bronnen uit eerdere beurten komen alleen in de lijst als
  het antwoord hun regeling noemt.
- **Een bijna-letterlijk citaat wordt de brontekst** (`grounding.herstel_citaten`, in `agent_node`
  vóór het antwoord de deur uit gaat). Afwijkingen als een hoofdletter aan het begin of een punt
  binnen de aanhalingstekens zoekt hij hoofdletter- en witruimte-ongevoelig op in register + trace.
  Bij precies één vindplaats zet hij de brontekst terug, met een eventueel leesteken achter het
  aanhalingsteken. Alles daarbuiten (een ander woord, een weglating, eigen woorden) blijft voor
  `check_grounding` en de correctieronde. Een citaat wordt hier alleen letterlijker, nooit losser;
  annotaties zijn geen bron.
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

- **Het bericht draagt het artefact** (`annotatie_artefact`: `{soort: "annotatie", titel, ref:
  {bron_iri, label, snapshot_id}}`, naast het oudere `annotatie_doel`), en het `opgeslagen`-event
  draagt het ook; de werkplek opent het daarmee. De titel is het `label` van het doel. Het
  begrippenartefact legt de begrippenroute vast (hieronder).
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

**Meerdere onderdelen zijn één run: een reeks** (`agent/reeks.py`; de werkgebied-run hieronder gebruikt
dezelfde stroom over meerdere artikelen). `doelen` (2–60, elk met `bron_iri`,
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

## De begrippenketen (`agent/begrippen_pipeline/`, ADR-004)

Stelt voor welke geannoteerde formuleringen één begrip aanduiden (betekenisgroepen) en welke in een
relatie staan (kwalificatie, inclusie, uitsluiting, hiërarchie). Zuiver en deterministisch, zonder
model: `keten.analyseer(manifest, provider, melding)`. Hij draait als **begrippenrun** (hieronder),
niet als node in de LangGraph-graaf.

```
manifest → taal.py → definities.py + signalen.py + patronen.py → kandidaten
         → besluit.py (beslistabel) → groeperen.py (groepen / relaties / vragen) → uitleg.py
```

- **Een woord is geen begrip.** Sterk bewijs komt uit wat de wet zelf vastlegt: een wettelijke
  term (definitie of onderdeel van een opsommende definitie) binnen het bereik van de definitie, of
  een verwijzing ("bedoeld in", "die X"). Een gelijke term zonder meer is zwak en wordt een vraag.
  Eén uitzondering: **dezelfde term in dezelfde bronnode** (`ZELFDE_BEPALING`, one sense per
  discourse) is sterke steun en vormt een groep – maar geel, want het is een aanname en geen wet
  (`groeperen.AANNAMES`). Zonder die regel werd elk voorkomen in één lid een eigen vraag
  (acceptatie 15 okt: 17 vragen voor IW art. 9 lid 1 en 5, nu 5 gele groepen en 2 vragen).
  Een **zin** als formulering (een persoonsvorm in de span, `Taalanalyse.zin`) doet niet mee aan
  "zelfde term": haar kern is het onderwerp, geen term.
- **Bewijs heeft een richting en een ordinale sterkte, geen getal.** De beslistabel (`TABEL`, rij-id
  in elke beslissing) kent link / non-link / possible link. Sterk tegenbewijs wint altijd; zwak bewijs
  alleen levert géén relatievoorstel op.
- **Relaties worden geen groepen, en conflicten worden gemarkeerd, niet geknipt.**
- **Het bereik van een definitie** komt uit de aanhef ("Deze wet verstaat onder", "in dit artikel");
  "dit hoofdstuk" is onbekend, omdat de opbouw niet in de IRI staat.
- **Patronen** staan in `regels/relaties.yaml` met groepen `van`/`naar` en vier verplichte
  testsoorten (`tests/test_begrippen_patronen.py`); elke code heeft een regel in `verklaringen.yaml`.
- **Geen graafverkeer in de keten.** Definities buiten het werkgebied horen als contextbron in het
  manifest.
- Meten: `python -m eval.begrippen_eval --variant lemma|keten|keten_zonder_parse` op
  `docs/wetsanalyse/referentieset-begrippen/` (provisional, en een ontwikkelset – zie het meetlogboek).

### De model-laag: twijfelparen en concept-kaart (fase C)

Bovenop de uitkomst van de keten, nooit erin: de deterministische groepen, id's en uitleg blijven
wat ze zijn. Zuiver, in dezelfde map (`classificatie.py`, `verdieping.py`, `kaart.py`,
`fragmenten.py`, `toetsen.py`); het model komt binnen als `llm` met `create()`, zoals bij de
JAS-classifier, en draait op `LLM_MODEL` (een oordeel, dus geen eigen modelknop).

- **Alleen twijfelparen gaan naar het model** (`verdieping.te_vergelijken`): de vragen van de keten,
  behalve een paar dat de wet al als relatie noemt. Het kiest per kandidaat-id `zelfde_betekenis` /
  `verwant_ander_begrip` / `betekenisverschil` / `onbeslist` via een strict tool; ongeldig wordt
  `onbeslist` met een reden.
- **Alleen `zelfde_betekenis` verandert iets**: een link `door: "model"`, en de groep die erop rust is
  altijd geel. De andere oordelen laten de vraag staan, met het oordeel als advies – een foute
  scheiding zou anders onzichtbaar zijn (gemeten: `metingen/begrippen-model-2026-10-15`).
  `hergroepeer` gebruikt dezelfde `groeperen.groepeer`, dus dezelfde conflictcontrole.
- **De concept-kaart** (`kaart.basis` zonder model, `kaart.vul` met): naam, alternatieve termen,
  begripstype (uit de JAS-klasse; het model kiest alleen bij gemengde klassen), context, en een
  definitie: *letterlijk* (de definiens, zonder model) > *samengesteld* (het model kiest fragmenten op
  id, code plakt ze aan elkaar) > *geformuleerd* (het model schrijft, noemt zijn fragmenten, altijd
  geel; een cirkel wordt verworpen). Voorbeelden horen bij fase E.
- **Fragmenten** (`fragmenten.knip`): zinsdelen met een id uit bron en offsets. Het model typt nooit
  brontekst over.
- **Toetsen** (`toetsen.py`): garanties (id bestaat, tekst letterlijk op offsets) halen een definitie
  weg; signalen (circulair, rekenregel, gemengde klassen, geen begrip) maken haar geel. Signalen gaan
  over wat Lex voorstelt, niet over de wet. Elke code heeft een tekst in `TEKST`.
- **Batches** zijn inhoudelijk (`verdieping.batch_id`: soort, id's, promptversie, model): dezelfde batch
  draait één keer, dus een herstart is hervatbaar én reproduceerbaar.
- Meten: `python -m eval.begrippen_eval --model --versie <set>` (drie herhalingen, kost geld).

### De begrippenrun (`agent/begrippen_run.py`, spoor D levering 3a)

`POST /v1/begrippen-runs {werkgebied_id, run_id}` → `begrippen_stroom`: haal de run met manifest bij
de api (`GET …/begrippen-runs/{id}?manifest=true`), meld `…/loopt`, draai de keten in een thread met
de fasen als `status`-events (`Lex · Taalanalyse: … (n ms)`), zet de uitkomst terug (`PUT …/uitkomst`)
en eindig met `opgeslagen` + `done`.

- **De api is de bron van het manifest**, graph-qa rekent alleen. Het manifest valideert tegen
  `Manifest` (letterlijkheid, geen dubbelen); klopt het niet, dan `mislukt` en een `error`.
- **De runstore-sleutel is `werkgebied:<id>`**: de 409 "loopt al" geldt per werkgebied, en
  `/v1/runs/{id}/events` en `/cancel` werken ongewijzigd. Stoppen kijkt vóór en ná de keten (de keten
  zelf is één synchrone stap).
- **Per groep een voorstel** (`voorstel`): de naam is de term die de leden het vaakst dragen; is een lid
  de term van een begripsbepaling, dan de letterlijke definiens (`definities.definiens`) met vindplaats.
  De model-laag (twijfelparen, kaart) staat hierboven; de run met batches is de verdieping (fase C2).
- **Geen model, dus geen tokens en geen budgetpoort.** Een herstart op hetzelfde manifest levert
  dezelfde groep-id's; de api schrijft idempotent.
- **Elk faalpad is zichtbaar**: api onbereikbaar, ongeldig manifest, de keten faalt, de api weigert de
  uitkomst → `error` met `soort` (`api`/`manifest`/`keten`) en `…/mislukt` bij de api (best-effort; anders
  ziet de api de run na vijf minuten als vastgelopen).
- **Contract**: `naar_uitkomst` volgt `api/app/begrippen_run_contracts.py`;
  `tests/test_begrippen_run.py` leest die klassen uit de bron (zoals `test_contract_drift.py`), en
  `tests/test_begrippen_manifest_drift.py` bewaakt manifest-id en veldnamen via
  `manifest-id.vectoren.json`.

### Lex denkt mee: de verdieping als beurt (`agent/begrippen_verdieping.py`, fase C2)

De model-laag hierboven, uitgevoerd in batches met de api als geheugen. Sinds F3c de taak `meedenken` van
de begrippen-agent (`verdieping_kern`): de supervisor kiest hem, of de actie `begrippen_meedenken` (ook
`modus: "begrippen_verdiepen"` van de bevestigingsknop). Het voorstellen van begrippen biedt het ook aan:
na de voorstellen een zin en een `bevestiging` (`meedenk_aanbod`) als er twijfelpunten of begrippen
zonder definitie zijn.

- **De werkvoorraad komt van de api** (`GET …/verdieping`), met schatting en budget. Zonder
  `bevestigd`: alleen het voorstel en een `bevestiging` (`soort: "begrippen_verdiepen"`). Met
  `bevestigd: n` alleen als `n` het actuele `aantal` is. Is er niets voor het model, dan rekent hij
  meteen, zonder model (kaarten zoals de keten ze geeft).
- **De keten draait opnieuw** op het bewaarde manifest; wijken groepen of vragen af van wat de api
  bewaarde, dan stopt hij ("vraag eerst opnieuw om begrippen").
- **Per batch** (`verdieping.batch_id`): klaar bij de api → teruglezen (hervatten, ook zonder
  bevestiging); anders – alleen na bevestiging – stop en budget, het model in een thread met een eigen
  `AnthropicLLM` (meter), het verbruik geboekt op `<run>.v<n>`, en `PUT …/batches/{id}`. Een fout in één
  batch stopt de rest niet, maar dan blijft de verdieping open en zegt Lex hoeveel er klaar is.
- **Alles klaar** → hergroeperen, kaarten, `PUT …/verdieping` (groepen met `door`, kaarten, oordelen,
  open vragen), en een samenvatting met het begrippenartefact.
- `/v1/chat` weigert de modus (422), zoals de andere `WERKGEBIED_MODI`.
- Tests: `tests/test_begrippen_verdieping_run.py` (nep-api en nep-model; het api-contract uit de bron).

### Lex naast de kaart (`agent/begrip_kaart.py`, `begrippen_pipeline/kaartacties.py`, fase E)

Vier acties op één begrip, elk een voorstel per veld; de api bewaart ze als eigen object en het begrip
verandert pas als de analist overneemt (`api/app/begrip_voorstel_store.py`). Ingang:
`POST /v1/kaart-runs {werkgebied_id, begrip_id, run_id}` (runstore-sleutel `begrip:<id>:kaart`, dus één
actie per begrip tegelijk) → `kaart_stroom`: run met invoer ophalen, `…/loopt`, rekenen, `PUT …/uitkomst`.

- **Zoek de brondefinitie** – geen model, geen budgetpoort. `q_brondefinities` zoekt
  `bwb:definieertBegrip` op naam en alternatieve termen (`LCASE … IN`), met de aanhef van de ouder;
  `plaats` geeft elke treffer *werkgebied* (`in_selectie`), *regeling*, *definitieverwijzing* (een
  regeling waar een begripsbepaling uit de regelingen van het werkgebied naar verwijst, `q_verwezen`)
  of *elders*. `kaartacties.brondefinities` neemt alleen een echte definitie letterlijk over
  (`definities.definiens`; "verstaat mede/niet onder" niet – dat zegt `geen_definitie_melding`), de
  sterkste plaats eerst, hoogstens vijf; buiten het werkgebied is het voorstel geel.
- **Scherper, betekenisverschil, voorbeelden** – met het model (`LLM_MODEL`), elk één `strict` tool:
  fragmenten op id uit de bronnen van de passages en de begripsbepalingen van de term
  (`fragmenten_voor`); daarna `toetsen` in code. Een ongeldig antwoord, een onbekend fragment of geen
  verbetering levert een `melding` en geen voorstel; een geformuleerde cirkel wordt verworpen.
  Betekenisverschil (met `ander` uit de invoer) levert een alinea `uitleg` en bij twijfel een open
  vraag; voorbeelden zijn altijd geel en zonder bronanker, met een signaal zonder tegenvoorbeeld.
- **Budget** vóór een model-actie (`reeks._budget_poort`); het verbruik op `kaart-<run>`, ook bij een fout.
- **Codes**: de aandachtspunten van deze acties staan in `kaartacties.TEKST`, los van `toetsen.TEKST`
  (de werkplek leest die laatste letterlijk mee; een nieuwe code daar breekt de frontend-drift-test).
- **Contract**: `tests/test_begrip_kaart.py` leest `api/app/begrip_voorstel_contracts.py` uit de bron.
- Meten: `uv run python -m eval.kaartacties_eval` (live tegen de graaf, geen model; een ontwikkelset,
  meetlogboek `kaartacties-2026-10-16`).

### Begrippen voorstellen in het gesprek (`agent/begrippen_beurt.py`, fase AF2)

Staat de werkplek in de context van een werkgebied, dan draagt `POST /v1/runs` een `werkgebied_id`. Een
vraag om begrippen is sinds F3c de taak `voorstellen` van de begrippen-agent (supervisor of actie
`begrippen_voorstellen`); geen tekstpatroon, geen harde route.

- `begrippen_kern`: werkgebied ophalen → `POST …/begrippen-runs` bij de api (manifest + run, of de
  bestaande op dezelfde stand) → de keten via `begrippen_stroom` als de run nieuw is, wachten (peilen,
  hoogstens 3 min) als een ander hem al draait, niets als hij al klaar is → de groepen tellen → een
  uitkomst met het **begrippenartefact** (`begrippen_artefact`:
  `{soort: "begrippen", ref: {werkgebied_id, run_id}, titel: <werkgebiednaam>}`).
- **Een weigering van de api is een antwoord**, geen storing: 404 (werkgebied weg) en 409
  (`te_weinig_passages`, `inventaris_onvolledig`, in de woorden van `WEIGERING`) worden `geweigerd`
  zónder artefact. Een andere api-fout wordt in de node een zin (`STORING`).
- `/v1/chat` weigert een actie (422): de taak schrijft in werkgebied en gesprek.
- In de antwoordroute gaat `werkgebied_id` mee als `State.werkgebied_id`: de begrippen van dat werkgebied
  staan vooraan bij `search_begrippen` (fase F4, hieronder).
- Tests: `tests/test_begrippen_beurt.py` (request-model, verloop tegen een nep-api).

### Bronnen vinden met Lex (`agent/bronnen_vinden.py`, `agent/bronnen_run.py`, fase A)

Vanaf de selectie van een werkgebied (kern = rol *analyseren*) zoekt Lex bepalingen die erbij kunnen
horen; de api bewaart de kandidaten en de besluiten (`api/app/bronnen_run_store.py`).

- **Methoden, zonder model** (`METHODEN`): `overzicht` (onderwerp uit de analysevraag, anders de naam
  van het werkgebied; rol kern), `verwijzing_uit` (diepte 1 vanaf de kern en haar leden/onderdelen;
  afhankelijkheid bij een bekende functie, anders aanverwant), `verwijzing_in` (aanverwant),
  `definitie` (een `bwb:definieertBegrip` in de regeling van de kern waarvan de term letterlijk in de
  kern staat; afhankelijkheid), `opbouw` (de andere artikelen in hetzelfde deel; aanverwant),
  `gelijkenis` (`bwb_similarity`) en `deelvraag` (het overzicht per actieve deelvraag, met
  `onderwerp_van_deelvraag`: het vraagwoord vooraan eraf; kern zonder kern, anders aanverwant, hoogstens
  `MAX_PER_DEELVRAAG`; het bewijs draagt `deelvraag_id`, zodat de api een opgenomen bron aan de
  deelvraag koppelt).
- **De standaard volgt de meting** (`standaard_voor`, meetlogboek `bronselectie-2026-10-15`): met een
  kern `STANDAARD` = verwijzing uit, definitie, opbouw; zonder kern `ZONDER_KERN` = het overzicht.
  Overzicht (met kern), `verwijzing_in` en `gelijkenis` hielpen niet aantoonbaar en staan uit. Wijzig
  je een methode, meet dan opnieuw: `uv run python -m eval.bronselectie_eval` (offline, tegen de
  opname naast de set) en `--opnemen` (live); `tests/test_bronselectie_eval.py` bewaakt dat de standaard
  alles vindt wat nodig is en niets uitgeslotens voorstelt. Heeft het werkgebied deelvragen (ze staan
  alleen dan in de invoer), dan komt `deelvraag` erbij: de analist vroeg er zelf om. Die methode is nog
  niet gemeten.
- **De queries gaan op bron-IRI's** (`q_uitgaand`, `q_inkomend`, `q_teksten`, `q_definities`,
  `q_opbouw`), niet op bwb-id + artikel: een selectie kan een lid, onderdeel of Leidraad-divisie zijn.
  Alleen geïmporteerde doelen (`?naar a ?type`): een verwijzing naar een regeling buiten de graaf is
  niet op te nemen.
- **De functie van een verwijzing** (`verwijzingsfunctie`): een vast patroon direct vóór het anker
  (`bwb:ankerTekst`) in de tekst van de verwijzende node – *definitie* (de node definieert een begrip),
  *uitzondering*, *delegatie*, *toepassing* – anders *onbekend*. Liever geen functie dan een geraden.
- **Eén kandidaat per bepaling** (`Verzameling`), sterkste rol wint; wat gelijk is aan, binnen of rond
  een selectie valt (`in_selectie`, op de IRI-vorm), wordt geen kandidaat. Het label is de vindplaats
  uit de IRI plus de citeertitel (`_benoem`).
- **Niets valt stil weg**: elke methode heeft een plafond (`MAX_*`) en meldt `aantal`, `volledig`,
  `ms`. Een falende methode wordt `volledig: false` en laat de rest staan; falen ze **allemaal**, dan
  is de run mislukt (`error` met `soort: "graaf"`), geen lege uitkomst.
- **Twee ingangen**: `POST /v1/bronnen-runs {werkgebied_id, run_id}` (runstore-sleutel
  `werkgebied:<id>:bronnen`, naast die van de begrippen) en **in het gesprek** de taak `bronnen_zoeken`
  van de deelvragen-agent (`bronnen_kern`, F3c) – de uitkomst draagt een `bronnen`-artefact. "Welke
  artikelen gaan over X?" blijft de overzichtsroute, ook binnen een werkgebied. Een weigering van de api (`geen_vertrekpunt`) is een antwoord.
- Tests: `tests/test_bronnen_vinden.py` (functiepatronen, methoden tegen een nep-graaf, het
  api-contract uit de bron, run, route, endpoint).

### Lex stelt deelvragen voor (`agent/deelvragen.py`, vervolg op fase F)

Deelvragen bij een werkgebied zijn optioneel (open keuze 4); de api bewaart ze
(`api/app/werkgebied_deelvragen.py`). `POST /v1/deelvragen-runs {werkgebied_id}` (runstore-sleutel
`werkgebied:<id>:deelvragen`, budgetcheck vooraf zoals `/v1/runs`) → `deelvragen_stroom`: werkgebied
ophalen, zonder analysevraag een `error` (`soort: "invoer"`) zonder modelaanroep, dan één aanroep op
`LLM_MODEL` met een strict tool (`stel_deelvragen_voor`; het hele dossier van het werkgebied gaat mee via
`werkgebied_context.context_tekst`, en de bestaande deelvragen, zodat Lex er geen variant van bedenkt), `valideer` (alleen vragen met een vraagteken, ontdubbeld, hoogstens
`MAX_DEELVRAGEN`), `POST …/deelvragen/voorstellen`. Het verbruik op `deelvragen-<run>`, ook als opslaan
faalt. Events: `status`, `token` (samenvatting), `opgeslagen`, `done`. De api laat weg wat er al staat of
is afgewezen. Tests: `tests/test_deelvragen.py` (het contract `DeelvraagVoorstellen` uit de api-bron).

### Lex annoteert het werkgebied (`agent/werkgebied_annotatie.py`, fase B)

Binnen een werkgebied annoteert Lex in één run de bepalingen die nog **nieuw** zijn – alleen van
bronnen met rol *analyseren*, per lid zoals de keuzekaart. Ingang: `POST /v1/runs` met `werkgebied_id`
en `modus: "werkgebied_annoteren"` of de actie `werkgebied_annoteren` (de reeks, in `_stroom_voor`). Getypt
("annoteer wat nog niet geannoteerd is") kiest de supervisor de annotatie-agent met taak `werkgebied`:
het voorstel met de bevestiging (`werkgebied_voorstel`, F3c).

- **De werkvoorraad komt van de api** (`GET …/annotatie-werkvoorraad`), nooit van de browser.
- **Nooit starten zonder bevestiging.** Zonder `bevestigd` antwoordt Lex met aantal, schatting
  (mediaan van eerdere annotatiebeurten, of eerlijk "nog geen"), budget en wat er niet meegaat, en het
  bericht draagt een `bevestiging` (`{soort, werkgebied_id, aantal, schatting}`) waar de werkplek een
  knop bij toont. Met `bevestigd: n` draait hij alleen als `n` gelijk is aan de actuele werkvoorraad;
  anders "de werkvoorraad veranderde" met een nieuwe bevestiging.
- **Dezelfde stroom als een reeks** (`reeks_stroom` + `beurt_fabriek`): per eenheid de gewone beurt met
  `hergebruik: auto`, eigen `run_id` `<run>.<n>`, events en berichten zoals op de keuzekaart; `ouder` is
  `{bron_iri: "urn:wa:werkgebied:<id>", label: "werkgebied <naam>"}`. Stop en budget tussen eenheden;
  een fout in één eenheid stopt de rest niet. Hoogstens `PLAFOND` (40) per run.
- **Aan het eind** een samenvatting (geannoteerd, mislukt, niet aan bod gekomen en waarom, wat buiten
  het plafond bleef) als gewoon bericht met het `run_id` van de hele run.
- `/v1/chat` weigert de modus (422), net als `begrippen` en `bronnen` (`WERKGEBIED_MODI`).
- Tests: `tests/test_werkgebied_annotatie.py`.

### Lex stelt een werkgebied samen (`agent/werkgebied_intake.py`, `nodes/werkgebied.py`, activiteit 1)

"Kunnen we een werkgebied samenstellen?" of "ik wil een wetsanalyse uitvoeren" (`is_werkgebiedvraag`)
start een **intake**: één vraag per kaartje in de volgorde van de methode (spoor F, F2) – naam, dan
startactiviteit a (aanleiding, context, doel), analysevraag, praktijkvoorbeeld, deelvragen, wat valt
erbuiten, en pas dan regeling(en) en onderdelen – en een samenvatting met *Aanmaken*. De
werkgebied-worker staat onder de supervisor, naast `antwoord` en `annotatie`, en ketent met niets.

- **Routering.** Een klik op een kaartje (`ChatRequest.intake_actie`) en een startzin gaan zonder
  modelaanroep naar de worker, vóór elke andere regel; `_stroom_voor` laat een klik nooit een harde
  werkgebiedroute in. Een getypt antwoord op het open kaartje herkent de supervisor met het model
  (`INTAKE_SYSTEM`, "OPEN KAARTJE"); een andere vraag krijgt gewoon antwoord.
- **`State.intake` staat niet in de per-beurt-reset**: een tussenvraag laat de intake en het open
  kaartje staan. `intake_actie` wél.
- **Alles wat er ligt, is de context van Lex** (besluit van de gebruiker, 20 okt 2026). `dossier` (de
  startzin plus `werkgebied_context.context_tekst` over `als_werkgebied`) gaat mee in **elke**
  voorstelaanroep en zoekopdracht. Een stap bereidt zijn kaartje opnieuw voor zodra de hash van het
  dossier veranderde (`voorbereid` per stap, `dossier_hash`); het model draait één keer per stand van
  het dossier (`model_hash`), gedeeld door de stappen. Terugbladeren zonder iets te wijzigen kost dus
  niets; een gewijzigd antwoord geeft nieuwe voorstellen, en wat de analist al koos blijft kiesbaar
  ("eerder gekozen"). De tests eisen het dossier in de modelinvoer.
- **Terugbladeren** (‹ n van 10 ›): `wijzig` mag vanaf elke stap naar een eerdere, vanaf de
  samenvatting naar elke stap. Het kaartje draagt `terug`/`beantwoord`, en `vooringevuld` komt dan uit
  het eerdere antwoord (`eerder_antwoord`).
- **De volgorde is een stapmachine** (`verwerk`), nooit het model. Een klik op een kaartje dat al
  beantwoord is (`stap` ≠ de huidige) verandert niets: Lex toont het huidige opnieuw. Een kaartje van
  een andere intake: "loopt niet meer". De naam is verplicht; de rest is over te slaan.
- **Aanleiding en doel** zijn de vaste lijsten van de Leidraad in eigen woorden (`AANLEIDINGEN`,
  `DOELEN`; de Leidraad is BRM-materiaal en hoort niet letterlijk in deze publieke repo), plus eigen
  tekst; doel is meerkeuze. Context en praktijkvoorbeeld zijn vrije tekst, zonder voorstel – een
  praktijkvoorbeeld verzint Lex niet.
- **Het model stelt alleen voor** (`stel_voor`, op `LLM_MODEL_ROUTER`, één strict tool): naam,
  voorselectie van aanleiding en doel (enum-sleutels; een onbekende valt weg), analysevraag en een
  onderwerp om mee te zoeken. Een startzin zonder inhoud kost bij de naam geen aanroep; een storing
  levert een kaartje zonder voorstellen.
- **Deelvragen** stelt Lex voor met `deelvragen.vraag_model` op `LLM_MODEL` (zelfde prompt als de
  deelvragenrun, met het hele dossier); zonder analysevraag niet, en dat staat op het kaartje. Het
  kaartje is meerkeuze met `meer_tekst`: eigen deelvragen komen als `teksten`. Elke vraag één keer
  (`normaliseer`, gelijk aan de api), met herkomst `lex` of `analist`.
- **Regelingen en onderdelen komen uit de graaf** (`regeling_opties`): eerst wat het dossier bij naam
  noemt (niet wat erbuiten valt), dan het overzicht van het onderwerp, dan het overzicht per deelvraag
  (hoogstens `MAX_DEELVRAAG_ZOEK`; `onderwerp_van_deelvraag`). Per deel onthoudt de intake bij welke
  deelvragen het gevonden werd; de omschrijving zegt het ("deelvraag 2"). Een deel waarvan de kop
  raakt aan wat buiten het werkgebied valt (`werkgebied_context.uitsluitstammen`/`valt_buiten`) valt
  weg en de toelichting noemt het. Eigen tekst bij de regelingen is een nieuwe zoekopdracht.
  **"Weet ik (nog) niet"** (`ONBEKEND`) staat altijd bij regelingen en onderdelen; bij de regelingen
  gaat het dan meteen naar de samenvatting.
- **Alleen een gekozen onderdeel wordt een bronselectie** (rol *analyseren*, bereik *onderliggend*),
  plus artikelen uit eigen tekst als er precies één regeling is (`artikelen_in`). "De hele regeling"
  en een regeling zonder onderdeel staan alleen in de afbakeningstekst (`afbakening`).
- **Aanmaken doet de beurt-driver** (`beurt._maak_werkgebied`), na het `werkgebied_aanmaken`-event:
  `POST /v1/werkgebieden` met het dossier, de deelvragen en de `intake_id` (idempotent bij de api),
  per bron `POST …/bronnen`, en daarna per deelvraag `PUT …/koppelingen` met de bronnen die Lex erbij
  vond (een set, dus een herhaling koppelt niets dubbel). Een geweigerde bron laat het werkgebied staan
  en Lex noemt hem; mislukt het werkgebied zelf, dan `error` met `foutcode: werkgebied_niet_aangemaakt`.
  Het bericht draagt het artefact `{soort: "werkgebied", ref: {werkgebied_id}}`.
- **Het kaartje reist mee**: een `vraagkaart`-event (vorm `api/app/gesprek_contracts.Vraagkaart`) en
  het veld `vraagkaart` op het bericht, zodat het na herladen nog te beantwoorden is.
- Tests: `tests/test_werkgebied_intake.py` en `tests/test_werkgebied_context.py`.

### Het werkgebied als context in het gesprek (`agent/werkgebied_context.py`)

Draagt een beurt een `werkgebied_id`, dan haalt `answer_stream` het werkgebied bij de api
(`_werkgebied_blok`, per beurt vers) en zet `als_blok` het in `State.werkgebied_context`;
`memory_context` geeft het naast de focus aan de supervisor en elke specialist – ook met
`ENABLE_MEMORY_CONTEXT` uit. Context, geen filter; zonder api of bij een storing leeg. Dezelfde
`context_tekst` voedt de intake en de deelvragenrun. De bronnenrun krijgt het dossier al in zijn
invoer (`invoer.dossier`, api), maar de methoden gebruiken het nog niet: dat verandert een methode en
vraagt eerst een meting (PLAN spoor F, *Vervolg*).

### Vraag Lex op een object (`agent/onderwerp.py`, F3b)

Vanuit een deelvraag, bronselectie, kandidaat, begrip of het werkgebied leidt één *Vraag Lex* naar het
gesprek. Het verzoek draagt alleen `onderwerp: {soort, werkgebied_id, id?, label?}` (`models.Onderwerp`);
`answer_stream` haalt het object per beurt bij de api (`onderwerp.haal`: het werkgebied, de dekking, de
kandidaten, het begrip met zijn open kaartvoorstellen) en zet het blok in `State.onderwerp_context`.
`memory_context` geeft het vóór het werkgebiedblok aan supervisor en elke specialist, ook met
`ENABLE_MEMORY_CONTEXT` uit.

- **Context, geen filter en geen route.** De supervisor kiest zoals altijd; het onderwerp zegt alleen
  waar de vraag over gaat. `focus.bij_onderwerp` houdt het object vast voor een vervolgvraag zonder chip
  (`supervisor_node` om `_kies` heen); een aangewezen markering vervangt het weer (`bij_advies`).
- **Een markering is geen soort.** Die vraag blijft `modus: "advies"` met `context`, byte-gelijk aan wat
  de werkplek al stuurde (`frontend/lib/vraagLex.test.ts`).
- **Niets valt stil weg.** Een object dat de api niet (meer) kent, of een storing, geeft het label uit de
  werkplek met de zin dat de gegevens niet op te halen waren. De kop is *AANGEWEZEN IN DE WERKPLEK*,
  niet "ONDERWERP" (dat woord draagt de onderwerp-afbakening in de systeemprompt).
- **`actie`** (`ACTIE_TAAK`, F3c): een klik op een suggestie is een vaste handeling – een taak van een
  agent, zonder model gekozen (zie *De agents onder de supervisor*). De validator `_actie_kiest_de_route`
  neemt het werkgebied uit het onderwerp als het verzoek er geen draagt, eist er een, sluit `modus`,
  `doel`, `doelen` en `intake_actie` uit, en laat `bevestigd` alleen toe bij `BEVESTIG_ACTIES`. Alleen
  `werkgebied_annoteren` zet een modus (de reeks). `/v1/chat` weigert een actie (422).
- Tests: `tests/test_onderwerp.py` (contract, blok per soort tegen een nep-api, focus, de beurt, de
  api-routes uit de bron).

### De agents onder de supervisor (`agent/agents/`, `nodes/agent_taak.py`, F3c, ADR-005)

Naast `antwoord`, `annotatie` en `werkgebied` kiest de supervisor **`deelvragen`** en **`begrippen`**, met
een `TAAK:`-regel uit een vaste lijst (`agents/register.py`; `parse_taak`). De tekstpatronen die vroeger
harde routes vóór de supervisor kozen (`is_bronnenvraag`, `is_begrippenvraag`, `is_kaartvraag`,
`is_verdiepvraag`, `is_werkgebied_annoteervraag`) zijn **weg**: getypte tekst gaat altijd langs de
supervisor. `_stroom_voor` kent alleen nog `intake_actie`, het werkgebied annoteren als modus/actie (de
reeks) en `doelen`.

- **Een `actie` kiest zonder model** (`models.ACTIE_TAAK`: actie → agent + taak), net als een `doel`. De
  werkplek stuurt hem bij een klik op een suggestie of een knop in de werkgebiedbalk. `modus:
  "begrippen_verdiepen"` (de bevestigingsknop) wordt de actie `begrippen_meedenken`.
- **De vorm** (`agents/__init__.py`): per agent een `Taak`-enum, een Pydantic-`Invoer` en de gedeelde
  `Uitkomst` (`status` ok/bevestiging/geweigerd/fout, `reden`, `voorstellen`, `artefact`, `bevestiging`,
  `tekst` uit code, `meting`), en `async voer_uit(invoer, ctx)`. Een model alleen in een stap die een
  oordeel of formulering vraagt, als één strict tool (`MODEL_TAKEN`); de rest draait aantoonbaar zonder
  (`tests/test_agents.py` met `FakeLLM([])`).
- **De parameters** komen uit wat er ligt (`register.parameters`): het werkgebied, het aangewezen object
  (of dat de focus vasthoudt), en wat code uit de vraag leest – "deelvraag 2" (`deelvraag_nr`, de n-de
  actieve) en de term van een begrip (`kaart_beurt.termen_uit`). Nooit uit modeltekst.
- **De deelvragen-agent** (`agents/deelvragen.py`): `voorstellen` en `verbeteren` (herformuleren of
  splitsen, `deelvragen.verbeteren_kern`: één strict tool, `valideer_verbetering` – precies één nieuwe
  vraag of 2–4, anders `geen`) landen als voorstel bij de api; `bronnen_zoeken` is de bronnenrun
  (`bronnen_run.bronnen_kern`, met wat er bij de aangewezen deelvraag hoort); `dekking` per actieve
  deelvraag uit de api (stand, bronnen met rol, open kandidaten). De systeemtekst draagt de skillrol
  `deelvragen` (`deelvragen.systeem`), ook in de intake.
- **De begrippen-agent** (`agents/begrippen.py`): `voorstellen` (`begrippen_beurt.begrippen_kern`),
  `meedenken` (`begrippen_verdieping.verdieping_kern`; zonder `bevestigd` het voorstel met bevestiging),
  de vier kaartacties (`kaart_beurt.kaart_kern`, dezelfde kaart-run als de knop), `uitwerken`
  (brondefinitie → zonder definitie een definitievoorstel → voorbeelden pas op een overgenomen definitie)
  en `relaties` (`GET …/relaties`, zonder model). Het begrip komt van het onderwerp (`als_rij`) of uit de
  term (`los_op`). Skillrol `begrippen`.
- **De annotatie-agent** heeft één taak hier: `werkgebied` (`werkgebied_annotatie.werkgebied_voorstel`), het
  voorstel met de bevestiging. Met `bevestigd` blijft het de eigen reeks, want die draait per bepaling een
  gewone beurt.
- **Uitvoering**: `agent_taak` draait de async agent op de event loop van de beurt
  (`agents/uitvoering.draai`, `Bouw.loop`), events via een thread-veilige wachtrij; stoppen via
  `Context.gestopt`. Hij emit `status`, de tekst als `token`, en `artefact`/`bevestiging`; de beurt-driver
  legt die op het bericht en het `opgeslagen`-event. Een storing wordt een zin in het gesprek
  (`STORING`), zonder api `ZONDER_API`. Een onbekende taak: Lex vraagt wat hij moet doen.
- **Kaartacties en verdieping boeken zelf** (eigen run bij de api); `voorstellen`/`verbeteren` van de
  deelvragen gebruiken het model van de beurt en tellen mee in het verbruik van de beurt.
- **Endpoints blijven** (`/v1/bronnen-runs`, `/v1/begrippen-runs`, `/v1/kaart-runs`,
  `/v1/deelvragen-runs`) zolang de werkgebiedpagina ze gebruikt (tot F3e).
- Tests: `tests/test_agent_uitvoering.py` (de spike), `tests/test_agents.py`, `tests/test_agent_contracten.py`,
  en per kern de bestaande `test_begrippen_beurt`, `test_bronnen_vinden`, `test_begrip_tools`,
  `test_begrippen_verdieping_run`, `test_werkgebied_annotatie`. Routering meten: scenario F in
  `eval/golden_gesprek.jsonl`.

### Lex leest begrippen (`tools/begrip_tools.py`, `nodes/begrippen_lezen.py`, `agent/kaart_beurt.py`, fase F4)

Wat juristen in werkgebieden als begrip vastlegden, over alle werkgebieden heen; het werkgebied van het
gesprek staat vooraan. **Een begrip is een analyse-uitkomst** met een status, geen wettelijke definitie en
geen vindplaats: de tools staan met de annotatietools in `AFGELEIDE_TOOL_NAMEN`, dus hun resultaten tellen
niet als bron, niet in de grounding en niet in het bronregister. De prompt (TOOLKEUZE 7) zegt: noem status
en werkgebied, geen aanhalingstekens om een begripsdefinitie, wettekst apart ophalen.

- **`search_begrippen` zoekt in de graaf, de api bevestigt** – de vorm van `search_annotaties`.
  `q_begrippen` vraagt kandidaat-id's uit de NL-SBB-projectie (`urn:wa:graph:werkgebied:*`: `prefLabel`,
  `altLabel`, `definition`, `wa:status`), `Q_REGISTER` de projectiehash per werkgebied; daarna
  `POST /v1/begrippen/verifieer` (`agent/begrip_read.py`). Wat de api niet meer kent valt af, status en
  werkgebied gelden zoals de api ze nu kent, en wijkt de hash van een werkgebied af van wat de api nu zou
  projecteren, dan is het resultaat `partial`/`volledig: false`. Een haperende graaf of api is nooit een
  lege lijst (`begrens_begrippen_antwoord`). Een rij met `herbeoordelen` (geaccordeerd, maar een dragende
  passage veranderde) noemt Lex zo (TOOLKEUZE 7): niet als vaststaand, met de vraag het op de kaart te
  herbeoordelen. `tests/test_begrip_tools.py` draait de query tegen een
  nagebouwde projectie en leest `BegripStatus`/`BegripVerificatie` uit de api-bron.
- **`get_begrip`** leest altijd bij de api (`GET /v1/begrippen/{id}`): kaart, passages met actualiteit,
  relaties. De poort draagt `werkgebied_id` uit de state (`tool_execution.begrip_port`); de actor is
  de rungebruiker, nooit een toolargument.
- **De leesroute** (`is_begrip_leesvraag`: begrip(pen) plus een aanwijzing dat het om wat er al ligt gaat –
  *al, vastgelegd, geaccordeerd, hebben we, als begrip, status* – en geen handeling) → `begrippen_zoeken`
  zoekt vóór de eerste LLM-call, met een zoekterm alleen als de vraag hem aanwijst ("het begrip X",
  "X als begrip", tussen aanhalingstekens) en een status uit de vraag. Om nieuwe voorstellen vragen is
  een taak van de begrippen-agent; de leesvraag gaat vóór de supervisor.
- **Kaartacties vanuit het gesprek** (sinds F3c taken van de begrippen-agent, `kaart_beurt.kaart_kern`):
  "zoek de brondefinitie van termijn", "maak de definitie van X scherper", "geef voorbeelden van X",
  "betekenisverschil tussen X en Y". Het begrip komt van het onderwerp, of uit `GET /v1/begrippen` (exacte
  naam of alternatieve term, werkgebied van het gesprek eerst); meer kandidaten → Lex vraagt welke,
  alleen een vervangen begrip → de opvolger. Starten gaat **direct**, zoals de knop (besloten 19 okt
  2026): `POST …/kaart-runs` en `begrip_kaart.kaart_stroom`, met zijn budgetpoort; loopt dezelfde actie
  al, dan wacht Lex. De uitkomst draagt een begrippenartefact met
  `ref: {werkgebied_id, begrip_id, kaart_run_id, actie}`.

## De overzichtsroute: "welke artikelen gaan over X?"

Een overzichtsvraag liet de keten eerst over aan het model: het koos tool en zoekterm
(`zoek_opbouw("invordering")` → 16 delen, `"invordering van belastingen"` → 0), stelde de opbouw zelf
samen (art. 31 en 63 Iw "buiten de hoofdstukken", terwijl de graaf H V en H VII zegt), typte nummers
en titels over (bereiken die 28.3a verbergen) en de bronnen en de 3D-graaf volgden uit die tekst. De
SPARQL was deterministisch; de keten eromheen niet. Nu is wat feitelijk is code (`agent/overzicht.py`):

1. **Herkenning is hard** (`is_overzichtsvraag`, op `zelfstandige_vraag` bij een vervolgvraag): "welke
   artikelen/bepalingen/hoofdstukken … gaan over X", "… hebben betrekking op X", "… regelen X", "waar
   is X geregeld", "overzicht van X". Leesvraag, doel en advies gaan vóór. Zonder gesprek geen
   supervisor-call. `onderwerp_uit` haalt X eruit; een genoemde regeling ("in de Awb", bij
   citeertitel of afkorting, `regelingen_in_vraag`) is de **afbakening**, geen zoekwoord.
2. **Het overzicht bouwen** (`bouw_overzicht`, in `nodes/overzicht.py` vóór de eerste LLM-call):
   delen met het onderwerp in hun opschrift (`zoek_opbouw`, alle pagina's) met hun bepalingen
   (`bepalingen_in_delen`); bepalingen die het onderwerp in hun **tekst** noemen
   (`bepalingen_met_onderwerp`, opgetild naar artikel of hoofddivisie); hun **plek in de opbouw**
   (`plaats_in_opbouw`) – binnen een gevonden deel staat een bepaling niet ook los, anders krijgt ze
   het meest specifieke deel mee; de **wettelijke definitie** (`definities_van`) en het
   **redactionele trefwoord** (`trefwoord_regelingen`, `dct:subject`). Opbouw en tekst vallen elk apart
   terug op het langste begin van het onderwerp dat iets oplevert. `semantic_search` doet bewust niet
   mee: altijd k treffers, geen ondergrens.
3. **Vaste volgorde, geen zoekscores:** regelingen op rang (wet → AMvB → ministeriële regeling →
   beleidsregel, `overzicht.RANG`), dan op aantal bepalingen in delen; delen en bepalingen in
   documentvolgorde (`padsleutel`, `natuurlijke_sleutel`). Dezelfde vraag, ook anders geformuleerd,
   geeft byte-voor-byte hetzelfde overzicht (gemeten: vier formuleringen, één hash).
4. **Geen model in de route.** Een modelduiding ging buiten het overzicht ("bevoegdheid, hoogte,
   evenredigheid" bij de bestuurlijke boete – niets daarvan staat in de graaf) en wisselde van vorm.
   De tekst is nu `samenvatting(ov)`: 2–4 vaste zinnen met de eigen koppen en getallen van het
   overzicht (kern, verder, "ook genoemd", definitie, afbakening, ingekort onderwerp), geteld in de
   woorden van de bron: "5 hoofdstukken met 35 artikelen", "1 afdeling", "8 artikelen" (`soortwoord`:
   een Leidraad-divisie telt als artikel, zoals de Leidraad zelf verwijst). Namen staan in de data, op
   één plek: `kop` per deel ("28 – Invorderingsrente"), `naam` per bepaling **zoals de bron haar noemt**
   (`bwb:label`: "Artikel 79.5a" → "art. 79.5a", "79.5" → "79.5" – de Leidraad wisselt zelf, en dat
   verschil wordt niet weggepoetst), `vindplaats` per definitie (`bronmodel.vindplaats`).
5. **Uitgangen:** een `overzicht`-event (de werkplek toont het als blok en bewaart het in
   `Bericht.overzicht`); de samenvatting als `token`, `answer` en assistent-bericht na het
   `tool_use`/`tool_result`-paar (`voor_model`, voor vervolgvragen); in de `source_trace` de
   vindplaatsen (`bronrijen`). Route `overzicht_bouwen → verify → finalize`; `route_after_verify` gaat
   met een overzicht nooit naar een correctieronde (die zou het model alsnog laten schrijven).
6. **Bronnen en controle uit het overzicht:** `finalize_node` neemt de bronnen uit het overzicht;
   `check_grounding(..., overzicht=)` toetst elk genoemd artikel én deel ("Hoofdstuk II", "Titel 5.4")
   tegen het overzicht, inclusief de bovenliggende delen (`opbouw`) – ook als het model de tool vrij
   gebruikt.

De tool `overzicht_onderwerp` levert hetzelfde overzicht buiten de route (MCP, vrije vragen) en
pagineert per deel binnen de begroting. Bouwt het overzicht niet (graaf weg), dan krijgt het model een
foutresultaat en zegt het dat; de werkplek toont dan geen blok. `tests/test_overzicht.py` legt
herkenning, samenstelling, volgorde, de route en de eval-scorer vast.

## De leesroute: vragen óver bestaande annotaties

1. **Herkenning is hard** (`tools/annotatie_tools.py:is_leesvraag`): een onderwerp (annotatie, markering,
   element, klasse, …) plus een leeswoord en géén schrijfwoord (`markeer`, `classificeer`), of
   `modus: "annotaties_lezen"`. Een kale klassenaam telt níét – *Voorwaarde* is ook gewone juridische
   taal. Een leesvraag kan zo topologisch geen annotatie worden; `annoteer` en `emit` weigeren
   bovendien expliciet in de leesroute.
2. **Zoeken is een stap, geen keuze** (`nodes/annotatie_lezen.py`). Een overzichtsvraag mét klasse
   ("welke rechtssubjecten kennen we al") wordt `overzicht_annotaties`: de verschillende teksten per
   klasse met telling en vindplaatsen, gegroepeerd in graph-qa over dezelfde gecontroleerde
   zoekroute (hoogstens vijf pagina's van 100; daarboven `volledig: false`). "Andere", "elders" en
   "nog meer" zetten de bepaling uit de focus erbuiten (`uitgezonderd_bron_iri`). Anders voert
   `annotaties_zoeken` vóór de eerste LLM-call zelf `search_annotaties` uit, met filters uit de vraag (`jas_klassen.klassen_in_tekst`)
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

De duiding-specialist (ook de adviesroute) heeft `get_annotatie` en `jas_klasse_opvragen`: een vraag
óver een markering moet het spoor en de alternatieven kunnen lezen. `jas_klassen` is in de schema's
een enum, met een contracttest tegen de klassenlijst van de api.

De annotatietools lopen via de api (`agent/annotatie_read.py`), niet via SPARQL: de api verifieert
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
(`antwoord`/`annotatie`/`werkgebied`/`deelvragen`/`begrippen`; de laatste drie staan altijd alleen) met een cap van twee: een onbekende naam zou anders een extra antwoord-worker
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

- **Brongetrouwheid.** Bronnen én grounding komen uit tool-resultaten (de trace van deze beurt plus
  het bronregister van het gesprek), nooit uit modeltekst. "Niets te
  controleren" is `onbepaald`, geen goedkeuring.
- **Het annotatiecorpus is één bronnode**, gericht opgehaald via `bronmodel.resolve`. Reconstrueer het
  **niet** uit de tool-trace: die plakt alle fetch-resultaten aaneen en is gepagineerd.
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
`azure-infra.yml` → actie **`eval`** (per straat): de retrieval-smoke en daarna `--annotatie` en `--gesprek`
elk **drie keer**, met het rapport in de workflow-samenvatting. Met de invoer `eval_set` (`gesprek` of
`annotatie`) draait alleen die set: goedkoper als je één ding hermeet. Drie, omdat dezelfde bepaling tussen runs sterk
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

**Drie gouden sets.** `eval/golden.jsonl` meet antwoorden (citaat-faithfulness, bron-recall, refusal,
en bij een overzichtsvraag het overzicht zelf: `verwacht_overzicht` met de verwachte `delen` en wat
`niet_los` mag staan – deterministisch, dus streng);
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
