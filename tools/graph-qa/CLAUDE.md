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
| `nodes/sjabloon.py` | de afronding met een sjabloon (ADR-008): vullen uit de trace |
| `nodes/annotatie.py` | annoteer (voorbereiding + `jas_pipeline.keten.analyseer`) en emit |
| `nodes/annotatie_lezen.py` | de leesroute: eerst zoeken in de opgeslagen annotaties, dan formuleren |
| `nodes/bron_lezen.py` | een stuk dat de vraag bij id noemt (ADR-013): de leestool van de connector in code, dan formuleren |
| `nodes/bron_lijst.py` | een lijstvraag over een bron naast de wet ("het laatste stuk van dossier 32140"): de zoektool in code, het blok `stukken`, zonder model |
| `nodes/overzicht.py` | de overzichtsroute: overzicht en tekst uit de graaf, zonder model |
| `nodes/bepaling.py` | de bepalingsroute (ADR-010, laag 2): de tekst van een bepaling uit `bepaling_workflow`, zonder toollus |
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
            ├─ genoemd stuk:     bron_lezen → agent ⇄ tools → verify → finalize   (een id als kst-35496-F, ADR-013)
            ├─ lijstvraag:       bron_lijst → verify → finalize   (zoektool in code, geen model; bij een fout → agent)
            ├─ begrippen lezen:  begrippen_zoeken → agent ⇄ tools → verify → finalize
            ├─ overzichtsroute:  overzicht_bouwen → verify → finalize   (geen model; bij een bouwfout → agent)
            ├─ bepalingsroute:   bepaling_lezen → verify → finalize     (tekst uit code, één aanroep voor de toelichting; anders → agent)
            ├─ werkgebied-worker: werkgebied_intake → einde              (één stap van het samenstellen)
            ├─ agents:           agent_taak → einde                        (deelvragen, begrippen; F3c)
            └─ afwijzen (geen wetgevingsvraag)
```

De vorm ligt vast in `tests/test_graafopbouw.py` (nodes en edges, met en zonder supervisor). Wijzig je
de routering, dan faalt die test – dat hoort, maar het moet een bewuste wijziging zijn. Zonder supervisor
(`enable_planning=False`, alleen in tests) blijft alleen de antwoordketen over. De decompositieketen
(`ENABLE_DECOMPOSITION`) is in november 2026 weggehaald; hij staat in de git-historie
(`agent/nodes/decompositie.py`).

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
  `anthropic_schemas(only=spec.tools)`. Tekst stroomt niet mee: pas na de ronde is bekend of het narratie
  is. Een ronde mét tools gaat dan als `reason` naar het denkproces (`narratie.ronde_in_denk`, met `\n\n`
  op een rondegrens). Een ronde zonder tools is een eindantwoord: dat gaat de state in, nooit naar `reason`.
- **`tools_node`** – voert elke aanroep uit via `dispatch(...)` en voegt `(tool_naam, resultaat)` toe
  aan de `source_trace`. Dezelfde aanroep (naam + argumenten) gaat in één beurt één keer naar de graaf; een herhaling krijgt
  het bewaarde resultaat met `HERHAALD` (`_al_gedaan`, uit de berichten van de beurt). Elke aanroep houdt zijn resultaat,
  want het model eist er een. Een fout (`resultaat.is_fout`, dezelfde toets als de MCP-server) draagt `is_error` en mag
  één keer opnieuw (`MAX_POGINGEN`): een tijdelijke storing zegt niets over de graaf, een blijvende mag de beurtlimiet niet
  opeten.
- **`sjabloon_node`** – roept het model een sjabloontool aan (`agent/sjablonen/`, ADR-008), dan vult de code het antwoord
  uit de trace (register + deze beurt): blokken in `State.antwoord`, de vaste tekst uit `antwoord_tekst` in `answer`. Niet te
  vullen (`Onvulbaar`) is een `is_error`-resultaat en het model gaat verder; een halve vulling bestaat niet. Naast een
  graaftool wacht het sjabloon tot de volgende ronde. Tekst in plaats van de tool blijft geldig (log `sjabloon gemist`),
  behalve één keer per beurt na een zoek- of leesresultaat van een bronconnector (geen fout; ronde 2, B22: een tabel met
  zelf afgeleide nummers na een gelezen stuk): dan stuurt `route_after_agent` de agent terug naar
  zichzelf met `SJABLOON_GEVRAAGD` (`_gevonden_zonder_sjabloon`, `State.sjabloon_gevraagd`/`sjabloon_nu`, per beurt gereset;
  iteratie 11 nov 2026: lijsten als tekst of markdown-tabel zonder links of zoekvraag). Blijft het tekst, dan is dat het antwoord.
  Alleen de sjabloontools zijn `strict`, en ze staan niet in `TOOLS`. Per specialist: `Specialist.sjablonen`.
  `antwoord_duiding` (uitleg): het model wijst per passage de bepaling en de eerste en laatste woorden aan (`van`/`tot`,
  D5), de code neemt de tekst ertussen uit de bron; gezocht wordt met typografische tekens als hun gewone vorm (’ = '),
  een slotzin uit `get_lid` telt onder zijn lid en een jci wordt de iri van de rij. Ze toetst tegen de tekst van de aangewezen bepaling, niet tegen de hele trace, en
  weigert een bepaling die de uitleg noemt zonder passage; kort antwoord, waarom en twijfel gaan als tekst door `verify`.
  **Wat de uitleg noemt, is gelezen** (D, besluit gebruiker 7 nov 2026; `duiding._genoemd_is_gelezen`): wijst de opgehaalde
  tekst het genoemde artikel aan zonder zijn tekst (een verwijzing in `get_context`, in precies één regeling,
  `vullen.artikel_in_trace`), dan haalt `sjabloon_node` het op via `execute_tool` (hoogstens `MAX_OPHALEN`), zet het in het
  bronspoor en geeft de tekst bij de weigering mee; het model wijst daarna een passage aan of laat het weg. Uit het geheugen
  van het model haalt de code niets op. Een markering "niet opgehaald" bestaat bewust niet.
  Citeren kan alleen uit rijen met een iri bij hun tekst, dus niet uit `get_context`.
  `verify_node` toetst de blokken `annotaties`, `begrippen` en `leemte` niet (`NIET_GETOETST`): afgeleide duiding en tekst van de code.
  **Bronnen naast de wet** (`sjablonen/extern.py`, ADR-013): het blok `extern` (brontype, id, label, link, kop uit
  `kop_in_antwoord`, letterlijke passages). Als subsjabloon krijgt elk sjabloon het platte veld `extern: [{id, van_nr,
  tot_nr}]`, en als eigen sjabloon is er `antwoord_extern`, allebei alleen als er een connector aanstaat die de rol bedient
  (`agent_node`); zonder connector zijn de schema's byte-gelijk. De tekst komt uit de rijen van de leestool (contract:
  `stuk: {id, label, link, bron_hash, gewijzigd?}`, rijen `{nr, tekst, kop?}`). De pagina komt uit `tools/stuk_tekst.tekstpagina`, voor elke
  leestool dezelfde: de kop alleen waar hij verandert (`zonder_herhaling` op de pagina; `extern` vult hem aan met `aangevuld`),
  `inhoud` alleen als het stuk zonder niet op één pagina past, en `leesbaar: false` in `stuk` bij een stuk zonder tekst (derde
  meting 10 nov 2026: ECLI:NL:HR:2022:50 paste net niet, en het vervolg kostte een ronde). Na een weigering vraagt
  `sjabloon_node` het sjabloon opnieuw aan te roepen (`OPNIEUW`); `extern.blokken` noemt dan alle fouten van alle aanwijzingen in één
  weigering, met ontbrekende alinea's als reeksen (`_reeksen`; per fout een weigering kostte per fout een ronde, B16: vijf),
  en een reeks heeft geen grens per aanwijzing meer: de code splitst, en boven `MAX_ALINEAS` (48) per antwoord kapt de code af met een `Leemte` die zegt welke alinea's niet
  geciteerd zijn (Kamerstukken K15: vijf weigeringen van "hoogstens 6", 450k tokens; bekendmakingen ronde 4: een weigering op 48 kostte B21 twee rondes), en het gelezen stuk staat in de bronnenlijst als de vraag het noemt. Een stuk dat alleen in een zoekresultaat stond, is
  voor `check_grounding` geen signaal meer (10 nov 2026: een lijst opvolgende stukken gaf 13 keer "alleen gevonden");
  het zoekresultaat draagt label, soort, datum en titel, en in de bronnenlijst komt het pas als het gelezen is. De prompt
  (BRONNEN IN DEZE BEURT) en de zoektool vragen zo'n lijst in het veld `stukken`. **Een lijst gevonden stukken** is het blok `stukken` (veld
  `stukken: [id]` naast `extern`, in het subsjabloon en in `antwoord_extern`): het model wijst ids uit een zoekresultaat
  aan, `extern.lijsten` neemt label, soort, datum, titel en de rest uit de zoekrijen (of uit het `stuk` van de leestool,
  ook bij `alleen_pdf`), in de volgorde van het resultaat, met de zoekvraag in woorden (`zoekvraag_tekst`, uit
  `ConnectorBeschrijving.filters`) en het totaal (`zoekvraag_tekst`: per soort metadataveld een eigen vorm – "van de Eerste Kamer", een periode voluit
  – en de volgorde als eigen zin). Het blok staat in `NIET_GETOETST`: gevonden is daar geen signaal. Het
  blok `extern` draagt `datum` en `soort_stuk` uit het `stuk`. Een ISO-datum uit een bron telt in de controle als dezelfde
  datum voluit (`hoeveelheden`). Een kaal getal in een tabelcel telt met de eenheid uit zijn kolomkop of de titel van de tabel
  ("€ 106" onder "Opbrengst (€ mln)", `hoeveelheden.uit_tabellen`; K28). De slotzin van een lijst noemt het totaal ook
  als alles getoond is ("16 stukken."; K25). `tests/test_extern_sjabloon.py`.
- **`verify_node`** – `check_grounding(answer, source_trace)`. Bij ongegrond volgt via `correct_node`
  hoogstens één corrigerende ronde (`GROUNDING_CORRECT`, default aan; `state["corrected"]`). De controle
  keurt **twee** dingen af en `correct_node` moet ze allebei benoemen: `unsupported` (een vindplaats die
  niet uit de graaf kwam) en `niet_letterlijk` (een citaat dat niet letterlijk in de opgehaalde tekst
  staat). Bij de citaten gaan de passages zelf mee (afgekapt) – zonder de tekst weet het model niet
  wélk citaat het moet herstellen.
- **`finalize_node`** – de enige plek in de antwoordketen die `token` uitstuurt (ook voor het overzicht; `tests/test_uitgifte_na_controle.py` bewaakt het). Een controle die volgt op publicatie
  houdt niets tegen, dus de jurist ziet een antwoord pas ná `verify` en afgekeurde tekst nooit, ook niet in
  het denkproces (besluit 6 nov 2026). Blijft de tekst na de correctieronde afgekeurd, dan gaat hij mee met
  het oordeel in het `grounding`-event: de controle keurt ook terechte citaten af. Daarna `collect_sources`
  → `curate_sources` → `met_regelingnamen` → emit `sources` + `grounding`; werkt `entities_seen` bij.
  Het afgekeurde antwoord blijft wel als modelbericht in de checkpoint staan.

### Gespreksgeheugen (checkpointer)

`thread_id = conversation_id`; de agent krijgt per beurt de gepersisteerde `messages`-historie mee
(getrimd op `MAX_HISTORY_CHARS`; oudere tool-resultaten krimpen eerst, maar **de lopende beurt
krimpt nooit** – `berichten.beurt_start` – anders leest het model zijn verse resultaat als
"ingekort, vraag opnieuw op" en zoekt het in een lus; de opslagrem `berichten.MAX_HISTORIE_CHARS` hoort ruim daarboven te
liggen, `Settings.controleer_historie_grens` waarschuwt). `agent_node` geeft daarom de vraag mee aan
`_trim_messages`: zonder telt een correctiebericht als begin van de beurt, en krimpt de brontekst die het model
moet herstellen. Hoe vaak er gesprek uit het venster valt, meet de logregel `venster` (`berichten.venster_telling`,
één per beurt; zie `docs/observability.md`) – eerst meten, dan pas een index, samenvatting of ruimer venster. **Een `tool_use` zonder `tool_result` gaat niet naar het model** (`_schoon_messages`): de
checkpointer bewaart de aanroep vóór `tools_node` draait, dus stoppen, een crash of de stappenlimiet laat hem open
staan, en Anthropic weigert dan elke volgende beurt. Hij valt weg bij elke beurt, dus ook bestaande gesprekken
herstellen; `tests/test_gesprek_blijft_bruikbaar.py` breekt een beurt op elke nodegrens af. De annotatie-worker laat een korte
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
- **`llm_stap.py`** – de gedeelde modelstap (H5). `aanroep(llm, rol, **verzoek)` geeft de kwargs ongewijzigd door,
  geeft een `Stopreden` terug, logt één `model_aanroep` (rol, model, stopreden, duur, gebruik; geen inhoud) en eist dat
  de systeemprompt de methodetekst van de rol draagt (`Rol.methoderol`, of `methoderol=` voor de specialist van de
  antwoordlus). `stroom` doet hetzelfde voor de streamende antwoordlus en logt bij `final_message()`. Supervisor,
  antwoordlus, ophaal-agent en de toelichting van de bepalingsroute lopen erlangs. `vraag_tool` is de vorm voor één tool (meestal strict):
  `pogingen` verplicht, `haal` bepaalt wat bruikbaar is, de tellers houden hun namen (`llm_calls`, `review_calls`,
  `afgekapt`). Na `refusal` of `max_tokens` geen tweede poging (`GEEN_HERHALING`, H5d). Geen eigen retry (dat doet de SDK) en geen except. Een nieuwe modelaanroep gaat hierlangs, met een
  eigen `Rol` en een scenario in `tests/test_modelverzoeken.py`: dat legt elk verzoek byte voor byte vast.
  `tests/test_methoderollen.py` eist dat elke methoderol uit de skill een aanroep heeft, dat elke `Rol` gebruikt wordt
  en dat niemand buiten de adapter en de stap `llm.create` of `llm.stream` aanroept.
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
  loopt. `tests/test_mcp_server.py` bewaakt dat hij exact de tools van de agent aanbiedt. Naar buiten draagt hij het
  contract als MCP (review ADR-013): per tool `annotations` (`gedrag`: alleen lezen, herhaalbaar, `openWorldHint` voor een
  bronconnector), een `outputSchema` (`resultaat.CONTRACT_SCHEMA`) voor de graaftools en connectortools, het resultaat ook
  als `structuredContent` (gevalideerd tegen dat schema voor elke contracttool, elke pagina), en bij een gelezen stuk een
  `resource_link` met `lastModified` = de versie die gelezen is. In de antwoordlus van Lex verandert niets.

## Toollaag & queries

- **`tools/__init__.py`** – `TOOLS` (33 declaraties: 21 graaftools, de vier annotatieleestools uit
  `tools/annotatie_tools.py`, de twee begrippenleestools uit `tools/begrip_tools.py`, de twee Kamerstuktools uit
  `tools/kamerstuk_tools.py`, de twee bekendmakingtools uit `tools/bekendmaking_tools.py` en de twee Rechtspraaktools uit `tools/rechtspraak_tools.py`), `anthropic_schemas(only=)` en `dispatch()` (vangt
  `ValueError`/`MCPError`/`KeyError` als tekst). Een tool met `needs_settings` krijgt `settings` mee.
  `tools/jas_tools.py` (`JAS_TOOLS`) is dispatchbaar maar wordt in de draaiende keten niet aangeroepen.
- **Bronconnectors** (ADR-013): **de beschrijving in `bronmodel.connectors` is de enige bron** (naam, label, brontype,
  groep, wat hij dekt, signalen, tools, leestool, id-vorm, rollen, rol in het antwoord, grenzen, voorbeeldvragen).
  `CONNECTORS` (connector → tools), de connectortools van de specialisten (`specialists._met_connectors`), de
  `Literal`s van de contracten en het register van de api komen eruit; een nieuwe connector is een beschrijving, zijn
  tools en een straatvlag. `tests/test_connectorbeschrijving.py` maakt een onvolledige beschrijving of handwerk ernaast
  rood, met een nep-connector als bewijs dat er niets per connector bij hoeft. `toegestane_tools(tools, settings)` is de ene
  regel voor de schema's van de antwoordlus, de MCP-server en `dispatch`. Een connector staat uit tot de straat hem
  aanzet (`CONNECTOR_KAMERSTUKKEN=true`); uit is niet aangeboden, en een aanroep is dan `connector_uit`. **De beurt
  beperkt verder** (`ChatRequest.bronnen`, `State.bronnen`, per beurt): weggelaten = wat de straat aanbiedt, een lege
  lijst = alleen wetgeving, en een connector die de straat niet aanbiedt gaat nooit aan (`actieve_connectors`).
  `tool_execution` geeft de stand aan `dispatch`, dus ook een workflow die een tool in code aanroept valt eronder.
  **De bronstand** (`agent/bronstand.py`, `State.bronstand`) zegt per connector waaróm hij uit staat (`straat`,
  `gesprek`/`werkgebied` uit `ChatRequest.bronnen_herkomst`, `register_onleesbaar`, `beheerder`) en gaat als eerste
  event (`bronstand`) de stroom in; de logregel `beurt_meting` leest hem (`kamerstukken:aan`).
  **De prompt**: BRONSOORTEN in `SYSTEM_PROMPT` is generiek (geen connector met naam, binnen de cache); BRONNEN IN DEZE
  BEURT (`bronstand.prompt_blok`, ná het cachepunt in `agent_node`) zegt per connector uit de beschrijving wat hij dekt
  en waarvoor hij staat, of waarom hij uit staat en wie hem aanzet. Zonder aangeboden connector en zonder genoemde bron
  is dat blok leeg. `tests/test_bronprompt.py`. `tests/test_bronschakelaar.py`.
  **Kamerstukken** (`tools/kamerstuk_tools.py`, transport `adapters/sru_kamerstukken.py`): `zoek_kamerstukken`
  (filters, te combineren: een dossier of subdossier, `w.dossiernummer=="36200-IX"`, met `nummer` voor één stuk; woorden in
  de titel; `soort` in `w.subrubriek`, en bij een stuk zonder rubriek (of "Overig") op zijn plek in de titel: de tool toetst
  die stukken zelf en neemt ze op id op, zodat een brief met het woord in zijn titel niet meekomt (`_soort_cql`,
  `MAX_SOORT_TITEL`); `tekst` in de hele tekst
  (`cql.textAndIndexes`: een zinsdeel tussen aanhalingstekens als `adj`, losse woorden als `all`, hoogstens zes; meting
  `kamerstukken-tekstzoeken-2026-11-09`: 8 van 8 tegen 3 in de titel); `vanaf`/`tot` op de
  documentdatum, ook `JJJJ` of `JJJJ-MM`; `vergaderjaar`; `kamer`. De `volgorde` is de enum uit
  `KAMERSTUKKEN.volgordes`: `nieuwste`/`oudste` op `dt.date` met het id als tweede sleutel (alleen `sortBy` in de CQL
  sorteert, `sortKeys` negeert de dienst), `nummer` binnen een dossier (tot `MAX_DOSSIER` op nummer, daarboven de oudste
  eerst met een exact vervolg – nooit afgekapt), `relevantie` bij woorden; zonder volgorde een dossier op nummer, woorden
  op relevantie, de rest nieuwste. `aantal` begrenst de pagina. Elk resultaat draagt `zoekvraag` (filters en volgorde) en
  `totaal`; zonder bijlagen, `dt.type==Kamerstuk`) en `get_kamerstuk` (per alinea, met de kop, in documentvolgorde;
  een CALS-tabel als één rij (`soort: "tabel"`, titel, omvang, `tot_nr`) met `openen` naar `get_kamerstuk(tabel=)`: de kop met
  de kolommen als `cellen`, per rij `{soort: "tabelrij", cellen, tekst: "a | b"}`, de tabelnoten, en `samengevoegd` (een
  overspannende cel staat in haar eerste kolom); illustraties geteld in `overgeslagen`, de eigen inhoudsopgave apart; een voetnoot is een rij direct
  na zijn alinea (`soort: "voetnoot"`, `verwijst_naar` uit een `extref` naar een document), en de alinea noemt haar `noten`; een `tussenkop` (oud schema: `tuskop`) hoort bij de alinea's erna, zodat
  de artikelsgewijze toelichting haar artikel noemt; de eerste pagina draagt `inhoud`, per kop de offset, om te springen). De CQL bouwt de tool, de document-URL komt uit het
  SRU-record en alleen `repository.overheid.nl` over https; een fout is een foutresultaat, nooit een lege lijst, met de
  oorzaak als reden (`KamerstukFout.code` → `FOUTREDEN`): `bron_onbereikbaar` (storing), `zoekvraag_geweigerd` (een
  SRU-diagnose), `niet_gevonden` en `alleen_pdf` (het stuk bestaat, maar KOOP heeft nog alleen een PDF – vaak bij een
  onopgemaakt stuk; het resultaat draagt dan `stuk` met de metadata en de link). **Metadata uit KOOP**
  (`KAMERSTUKKEN.metadata`, sleutels uit `bronmodel.connectors.METADATA_SLEUTELS`): `Record` leest elk veld apart (de
  documentdatum `dt.date` en de publicatiedatum `dt.available` lopen soms weken uiteen), en `kamerstuk_tools.metadata`
  zet ze in de rij en in `stuk` (`label`, `soort`, `titel`, `datum`, `jaar`, `orgaan`, `indieners`; `gepubliceerd`,
  `reeks`, `gezamenlijk`, `status`, `leesbaar` alleen in de uitzondering; een stuk met `gezamenlijk` heet in de lijst
  "(gezamenlijk behandeld: 33752–33755)", `bronmodel.antwoord.gezamenlijk_tekst`, ronde 2 – een eigen sleutel, want `reeks`
  is bij wetgeving buiten de kennisgraaf de plek in de regeling, ronde 3). Een lege uitkomst noemt de grens van de
  zoekdienst (`GRENS`: Kamerstukken vanaf het vergaderjaar 1994-1995, ouder staat er niet in). Het label komt uit dossier en nummer, niet uit het id; een
  `w.subrubriek` "Overig" (oudere stukken) wordt het soort uit de titel. **Een id dat KOOP niet kent** zoekt
  `SruKamerstukken.record` op dossier en nummer in het hoofddossier: een herdruk (`kst-32740-1` → `kst-32740-1-n1`) en
  een onopgemaakt stuk (32140 nr. 342 = `kst-1278484`), en een lettercode van de Eerste Kamer die in een gezamenlijke
  behandeling naar het eerste dossier heet (`kst-33755-L` → `kst-33752-L`, alleen een letter en alleen eenduidig; ronde 3,
  K22); het `stuk` noemt het echte id en de toelichting zegt het. `get_kamerstuk(woorden=)` geeft de alinea's van één stuk die
  elk woord noemen (stam van zeven letters, tekst of kop) met hun offset (ronde 3, K07: tien offsets in drie stukken). Een rij draagt haar tekst onder `id`, niet onder `iri`/`uri`: een
  sjabloon citeert er dus niet uit als passage van een bepaling. **Cache met versiecontrole** (een Kamerstuk verandert
  na publicatie: onopgemaakt → opgemaakt, herdruk, rectificatie): binnen `VERS_S` geen aanroep, daarna een lichte
  metadatavraag op `dt.modified`/documentstatus/versie en alleen bij een verschil de XML opnieuw (log
  `kamerstuk_gewijzigd`); bij een storing (alleen `onbereikbaar`, niet een stuk dat verdween) de bewaarde versie met `gevalideerd: false`; grenzen `MAX_CACHE` en
  `MAX_CACHE_BYTES`. Het `stuk` noemt `bron_hash`, `gewijzigd`, `status` en `versie`, en het blok `extern`
  bewaart `bron_hash` en `gewijzigd`; `_gelezen` neemt de passages uit één lezing (dezelfde hash). Het contract met de echte dienst (indexen, sortering, recordvorm, documentstatus) toetst
  `tests/test_kamerstukken_live.py`: dagelijks in `bronnenwacht.yml`, lokaal met `BRONNEN_LIVE=1 uv run pytest -m live`
  (marker `live`; elke connector heeft er een, `test_connectorbeschrijving.py`). Niet in de poort.
  **De SRU van KOOP is gedeeld** (10 nov 2026): Kamerstukken en Staatsblad en Staatscourant gebruiken één transport,
  cache en recordvorm (`adapters/sru_koop.py`: `SruKoop`, `Record`, `KoopFout`; een subklasse zet alleen het filter,
  de terugval voor een id dat KOOP niet kent en de naam in de logregels), één bouwer van de CQL (`tools/sru_zoeken.py`:
  woorden in de titel, `cql.textAndIndexes`, `sortBy`, `per_record`) en één lezer van het OP-schema (`tools/op_xml.py`:
  wortel `stuk`, `staatsblad` of `staatscourant`, of in het oude schema van rond 2005 `staatsbl` met `art`, `wart`, `wlid`
  en `tuskop` (`tests/test_op_xml_oud_schema.py`); koppen per divisie, artikel – "Artikel I – Wijziging" –, lid en
  wijzigingsonderdeel; een `nr`/`li.nr` vóór de tekst die volgt; `wat`, `considerans.al` en de dagtekening als rij;
  ondertekeningen in `overgeslagen`). Een datum vóór 1800 in de metadata telt als onbekend (stb-2019-129 draagt
  0004-03-01). De datum van de jurist (`vanaf`/`tot`) komt voor elke connector uit `tools/zoekfilters.py`. Maak er
  geen kopie van per connector.
  **Staatsblad en Staatscourant** (`tools/bekendmaking_tools.py`, transport `adapters/sru_bekendmakingen.py`):
  `zoek_bekendmakingen` heeft twee wegen. Met `bwb_id` (en `artikel`) leest hij uit de graaf de publicaties die de BWB
  bij de huidige tekst noemt (`bwb:bron` = de laatste wijziging, `bwb:inwerkingtredingsbron`, met `bwb:inwerking`; bij
  een lid op het artikel erboven, zoals `queries.geldigheid`), zet "Stb.2009-610" om met `bronmodel.extern.koop_id_uit_bron`
  en haalt de records in één CQL (`dt.identifier==… OR …`); de rij zegt de koppeling in `wetsverwijzing`, de datum in
  `inwerking`, en de toelichting de grens (één toestand, eerdere wijzigingen niet). Zonder `bwb_id`: `publicatie`
  (Staatsblad/Staatscourant), `woorden`, `tekst`, `soort` (`dt.type all`; een inwerkingtredingsbesluit in de titel),
  `orgaan` (`dt.creator all`), `dossier` (`w.behandeldDossier`: de brug naar Kamerstukken), `vanaf`/`tot`, `jaar`
  (`w.jaargang`). `get_bekendmaking` leest per alinea; met `artikel` alleen de wijzigingsonderdelen (`wijzig-lid`) waarvan
  de opdracht dat artikel noemt (`_noemt_artikel`: 1.1.5 is niet 1.1.5b); met `regeling` alleen de artikelen van een
  verzamelwet waarvan de aanhef die regeling noemt ("De Invorderingswet 1990 wordt als volgt gewijzigd:"). De `inhoud` van
  de eerste pagina (`stuk_tekst.inhoud`, voor elke connector) draagt bij een kop op het bovenste niveau het begin van zijn
  eerste alinea (`begint`, tot `MAX_BEGIN` tekens op een woordgrens, letterlijk, met `begint_afgekapt` als er meer is;
  `begin_van`), zodat te zien is welke wetten een verzamelwet wijzigt zonder haar door te bladeren (meting 10 nov 2026:
  B16 338k tokens). Past de inhoud niet in haar deel van de begroting, dan gaan de koppen voor het begin (het bronvenster
  en de sprong hebben ze nodig): eerst alle koppen zonder `begint` (`inhoud_zonder_begin`), en pas daarna een ingekorte
  lijst (`inhoud_ingekort`); in beide gevallen noemt de pagina `inhoud_openen` (`stuk_tekst.inhoud_van`, `_met_inhoud`).
  Elke leestool leest met `inhoud: true` (`INHOUD_ARG`, `stuk_tekst.inhoudpagina`) de koppen op het
  bovenste niveau en daaronder zo diep als in één antwoord past (`_diepte_inhoudpagina`; een diepere kop met alleen zijn
  eigen naam en `diepte`, per niveau zodat een ouder zonder eigen alinea's er ook staat; staat de eerste pagina daardoor
  minder diep, dan `inhoud_dieper` met `inhoud_openen`; ronde 3 Kamerstukken, K15: gemeten tegen het pad korter maken op de
  eerste pagina, dat niet paste en een verzamelwet groter maakte), per pagina, het bovenste niveau elk met zijn eerste alinea als rij (`nr`, `tekst`: te citeren in `extern`) tot
  `MAX_AANHEF` tekens, en anders het begin (hermeting 11 nov 2026: 11 van de 30 artikelen van Stb. 2009, 610 op de eerste
  pagina, en een aanhef boven 160 tekens viel weg; controle: zonder `nr` citeerde het model de hele eerste pagina). Een
  stuk zonder koppen zegt `zonder_koppen` met het aantal alinea's en `lezen` (offset 0), en de statusregel "heeft geen
  koppen, 210 alinea’s"; "heeft geen tekst om te lezen" staat er alleen bij `leesbaar: false` (ronde 1 Kamerstukken). Het
  spoor noemt `inhoud` bij de filters, en elk argument van een connectortool buiten `doel` staat daar
  (`test_het_spoor_toont_de_filters_van_elke_connector`). **Een gefilterde lezing** (`artikel`, `regeling`) draagt `inhoud_publicatie`: de
  koppen van de hele publicatie met hun offset in een lezing zonder filter (`tekstpagina(publicatie=)`), zodat Lex gericht
  doorleest naar de inwerkingtreding of de toelichting (hermeting B08: anders las het model het hele stuk, 86k tegen 24k).
  Een genoemd stuk leest de code vooraf mét het genoemde artikel als de leestool `artikel` kent
  (`supervisie._te_lezen`), en zonder als dat niets oplevert (`bron_lezen`). Het `stuk` noemt de andere versies met hetzelfde blad, jaar en nummer (`versies`:
  herdruk, tweede versie, verbeterblad; `SruBekendmakingen.versies`, alleen op de eerste pagina), ook in de toelichting: in
  het veld las het model ze niet (ronde 2, B12). Is geen enkel genoemd stuk
  te lezen, dan antwoordt de code zonder model, voor elke connector hetzelfde (`bron_lezen._zonder_tekst`): geen tekst bij
  de bron, alleen een PDF (`alleen_pdf`, met het stuk in de lijst en `zonder_tekst` van de connector) of niet gevonden
  (`niet_gevonden`, met het id in de melding; ronde 1 Kamerstukken, K12/K27) of een bron die niet te bereiken is
  (`bron_onbereikbaar`; ronde 3, K11: het model verwees bij een storing naar een site die het niet kende). Een oud stuk heeft vaak alleen een PDF
  (`alleen_pdf`, met de metadata); een id dat KOOP niet kent zoekt de adapter op blad, jaargang en nummer. `geldigheid`
  noemt naast de BWB-vorm het id (`bekendmakingen`). Citeervormen "Stb. 2010, 176", "Stb.2009-610", "Staatscourant 2026,
  nr. 37344". **Uit de Staatscourant alleen regelgeving en beleid** (`REGELGEVENDE_SOORTEN`, een witte lijst op `dt.type`;
  "Overig" alleen bij een gerichte zoekvraag): de Staatscourant draagt ook deurwaardersexploten, faillissementen en
  curatele met namen van particulieren, en die zoekt of leest Lex niet (`binnen_bereik`, reden `buiten_bereik`).
  **Welke regeling een publicatie wijzigt** komt uit de graaf (`regelingen_bij`: `bwb:bron`/`bwb:inwerkingtredingsbron`
  terug naar de regeling, één query per pagina, in `wetsverwijzing`; zonder graaf ontbreekt alleen die regel). Met
  `bwb_id` filteren `publicatie`, `soort`, `jaar`, `vanaf` en `tot` de publicaties van die bepaling; zonder artikel zegt
  de toelichting dat een wijziging die bij geen bepaling meer de laatste is, er niet bij staat. Tests met opgenomen
  antwoorden van KOOP (`tests/fixtures/koop/`): `tests/test_bekendmaking_tools.py`, en de **vragenset**
  (`tests/data/bekendmakingen_vragenset.json`, zestien vragen uit het belastingdomein, ook voor de browsertoets en de meting)
  in `tests/test_bekendmakingen_vragenset.py`: route en argumenten per vraag, en het resultaat tegen een opname per verzoek
  (`tests/fixtures/koop/vragenset/`, opnieuw opnemen met `BEKENDMAKINGEN_OPNEMEN=1`; een verzoek dat niet is opgenomen
  faalt). Live `tests/test_bekendmakingen_live.py`.
  **Rechtspraak** (`tools/rechtspraak_tools.py`, transport `adapters/lido_rechtspraak.py`, ADR-013 fase 1c):
  `zoek_uitspraken` (bwb-id + artikel; de uitspraken die Linked Data Overheid aan het artikel koppelt, **verenigd over
  alle versies**, want een link hangt aan de versie die gold op de datum van de uitspraak) en `get_uitspraak` (de tekst
  van een Nederlandse ECLI bij de Rechtspraak, per alinea met kop – het deel en de titel van de sectie, "Uitspraak › 2
  Uitgangspunten in cassatie" – en `plek` ("r.o. 2.1") als de alinea in een genummerde rechtsoverweging staat, dat het blok `extern` toont (`ExternePassage.plek`); een `<?linebreak?>` in de bron is een spatie; een alinea boven
  `MAX_ALINEA` in delen; de eerste pagina draagt `inhoud` (`tools/stuk_tekst.py`, gedeeld met Kamerstukken); het label
  komt uit gerecht en datum, met procedure en rechtsgebied in `stuk`). **Begrensd** op `PER_SECONDE` (5) per host: de
  Rechtspraak vraagt hoogstens 10 per seconde en geen volledige download. **Cache met versiecontrole** zoals Kamerstukken:
  na `VERS_S` alleen de metadata (`return=META`), de tekst opnieuw als `dcterms:modified` verschilt
  (`uitspraak_gewijzigd`), bij een storing de bewaarde versie met `gevalideerd: false`. **Zonder artikel** zoekt
  `zoek_uitspraken` in de zoekfeed van de Rechtspraak (`_zoek_feed`): instantie en rechtsgebied als URI uit de
  waardelijsten (cache 24 uur; een onleesbare lijst is een storing, geen onbekend gerecht), "nieuwste"/"oudste" via een
  datumvenster (`_venster`: de feed sorteert alleen op wijzigingsdatum), `totaal` over de hele periode; een
  rechtsgebied met artikel is een invoerfout. De lijstroute leest ook "de 10 nieuwste uitspraken van de Hoge Raad in het
  belastingrecht" (`MetadataVeld.waarden`, het eerste orgaan dat past). `tests/test_rechtspraak_zoeken.py`. De zoektool
  leest jci en label-id van het artikel uit de graaf (`_q_artikel`); zonder graaf zoekt LiDO op bwb-id en nummer. De
  versies: eerst `get-id` met `juriconnect-ref` (bwb-id + artikel + datum, de vorige versie op de dag vóór de
  begindatum), en als die niets geeft (de Awb) de jci met de datum van een bestaande toestand uit de BWB-zoekdienst,
  vanaf de nieuwste die LiDO kent. Een `get-links`-antwoord dat halverwege afbreekt (HTTP 200 met een JSON-fout in de
  XML) valt terug op RDF; lukt dat niet, of raakt een versie `MAX_PAGINAS` of het artikel `MAX_AANROEPEN`, dan staat die
  versie in `onvolledig` en zegt de toelichting het – nooit stil korter. Eén herhaling bij een 400/5xx van LiDO; een 406
  van de BWB-zoekdienst met een geldig antwoord telt als antwoord (zoals in de importer). Per uitspraak alleen de vaste
  metadatasleutels (datum, gerecht en zaaknummer uit de titel); de soort gerecht voor het filter (`INSTANTIES`) komt uit de
  ECLI. Het resultaat draagt altijd `dekking: "ten minste"`, `versies`, `per_instantie` en `koppelingen` (automatisch
  herkend of redactioneel). **Een vermelding is geen uitleg**: de toolbeschrijving zegt "noemt", en een uitspraak is pas
  bron als ze gelezen is. De divisies van een beleidsregel kent LiDO niet; dat zegt de tool. **Elke rij zegt bij welke tekst ze hoort**
  (review, 10 nov 2026). `tekstversies` geeft de periode per LiDO-versie en vergelijkt die met `bwb:inwerking` en
  `terugwerkendTot` uit `_q_artikel`. De rij krijgt `tekst_vanaf`, `tekst_tot`, `tekststand` (huidige tekst, eerdere
  tekst, onbekend) en met het argument `peildatum` ook `op_peildatum`. Een ECLI aan meer versies telt als huidig zodra
  een van die versies de huidige is. Het resultaat draagt `huidige_tekst`, `per_tekststand` en `tekstversies`, en het
  filter `tekststand` kiest. Kent LiDO de huidige tekst nog niet, dan zegt de toelichting dat. LiDO koppelt naar de
  datum van de uitspraak, niet naar de tekst die de rechter toepaste: dat zegt de toolregel (`_VERSIE`). De peildatum
  van het werkgebied staat in `werkgebied_context` (voor het model) en in `State.werkgebied_peildatum`: de vaste
  lijstroute geeft hem mee als de zoektool het argument kent en de vraag een artikel noemt (`bron_lijst.met_peildatum`;
  meting `rechtspraak-versies-2026-11-11`, vraag 5). Een koppeling die LiDO alleen in RDF gaf, heeft geen titel: `_aangevuld` haalt dan
  datum, gerecht, titel en zaaknummer uit de metadata van de Rechtspraak (`LidoRechtspraak.metadata`, `return=META`,
  gecachet als de waardelijsten), vóór het sorteren tot `MAX_AANVULLEN` rijen, daarboven alleen voor de getoonde pagina;
  lukt dat niet, dan blijft het jaar uit de ECLI staan (vraag 3). Het blok `extern` neemt de tekstvelden uit de zoekrij
  (`extern._tekst_bij`, `TEKSTVELDEN`), want de leestool kent het artikel niet. **Na ronde 1 van de iteratie**
  (`docs/architectuur/metingen/rechtspraak-iteratie-2026-11-11/`): `get-links` vraagt alleen jurisprudentie
  (`ALLEEN_JURISPRUDENTIE`, het facet `obj_type`), want de wetten die een veelgebruikt artikel noemen braken het antwoord af
  (Awb 6:7: 0 van 6772); bij een plafond noemt de toelichting wat LiDO zelf telt (`totaal_lido`). Een regeling die niet in de
  kennisgraaf staat (`graaftoestanden`; een haperende graaf telt niet) zoekt LiDO op bwb-id en nummer, met een stand die niet
  vast te stellen is; staat de regeling er wel in en het artikel niet, dan `niet_gevonden`. `per_instantie`,
  `per_tekststand` en `tekstversies` tellen binnen de andere filters (een facet), `bij_het_artikel` zonder filters. Een soort
  gerecht in het meervoud ("gerechtshoven", `bronmodel.connectors.INSTANTIE_MEERVOUD`) leest de lijstroute en zet de tool om.
  De vragenset `tests/data/rechtspraak_vragenset_30.json` met de routetoets `tests/test_rechtspraak_vragenset.py` (een bekende
  afwijking in gedeelde code staat als `open`, `xfail(strict=True)`). Een rechtsgebied naast een artikel past de tool niet
  toe, en dat zegt de **`kanttekening`**: een veld van het resultaatcontract (`resultaat.CONTRACT_SCHEMA`) met een zin voor
  de jurist over de grens van de zoekvraag (onvolledig, LiDO kent het artikel niet, een regeling buiten de graaf, een filter
  dat niet kon). `extern.lijsten` zet hem achter de zoekvraag van het blok `stukken`, `extern.leemte_tekst` in de leemte
  (zonder volgorde: "Bij deze zoekvraag vond ik geen …"). Voor elke connector, ook in de ronde gedeeld gebouwd:
  `extern.lijsten` neemt pagina's van dezelfde zoekvraag (`_zoeksleutel`) als één lijst en houdt een gelezen stuk bij zijn
  zoekvraag; `van_orgaan` kiest het lidwoord ("van het College"); `provenance.collect_sources` slaat een foutresultaat over
  (`is_fout`: het voorbeeld in een foutmelding is geen bron); `bron_lijst` leest een maand, laat een werkwoord achter het
  onderwerp weg (`_WERKWOORDEN`), kent "kamerdossier" en telt een naam binnen een langere regelingnaam niet
  (`_zonder_ingesloten`). **Na ronde 2**: `zoek_uitspraken` met alleen `bwb_id` zoekt de uitspraken die de regeling als
  geheel noemen (LiDO op `juriconnect-ref=<bwb>`; de Leidraad Invordering 2008: 204); een regeling buiten de graaf krijgt haar
  titel uit de BWB-zoekdienst (`LidoRechtspraak.titel`); een buitenlandse of Europese ECLI is `buiten_bereik` met een `stuk`
  (`leesbaar: false`), zodat het antwoord haar mag noemen; `bron_lijst` geeft bij "alle" een volle pagina; de zoekvraag zegt
  "in maart 2025" en "van gerechtshoven". Gedeeld (Kamerstukken ronde 2): `grounding.genoemd_extern` herkent een stuk ook in
  de citeervorm van een connector ("Stb. 2013, 568"), zodat een gelezen stuk dat het antwoord zo noemt in de bronnenlijst
  blijft (`curate_sources`, `alleen_gelezen_extern`), en "Zoek …"/"Vind …" is een lijstvraag. **Na ronde 3** (gedeeld): een regeling die alleen
  in een zoekresultaat staat (de zoektools uit `spoorbronnen`), is geen bron, een bepaling met tekst uit een zoektool wel, en
  een lijst regelingen ook (`provenance._zoektools`, `REGELINGTOOLS`); een stuk in een foutresultaat houdt zijn label (`_labels`); een artikel met boeknummer
  (`boek=6&…&artikel=162`) telt als "6:162" (`grounding._BOEK_ARTIKEL`); de grens van het blok `stukken` geldt per bron. Een stuk van een connector is alleen een bron als het gelezen is,
  niet omdat een gelezen stuk het noemt (een voetnoot, `alleen_gelezen_extern`; Staatsblad B12); de titel van een regeling buiten
  de graaf komt uit de nieuwste toestand (`nieuwste_titel`; wetgeving_live I02). `tests/test_rechtspraak_tools.py`,
  live `tests/test_rechtspraak_live.py`, meting `docs/architectuur/metingen/lido-spike-2026-11-10/`.
- **Wetgeving buiten de kennisgraaf** (`tools/wetgeving_tools.py`, transport `adapters/sru_bwb.py`, ADR-013 fase 1e):
  wettekst van het BWB die niet in de graaf staat, live bij overheid.nl. **De graaf blijft de bron voor wat erin staat**,
  en dat beslist code: `_graafbesluit` vraagt de graaf (`graaftoestanden`, `q_in_graaf`, een cache per graafverbinding)
  of de regeling erin staat en welke toestand; valt de peildatum daarin, dan `in_graaf` met de graaftool, en een graaf die
  niet antwoordt is `graaf_onbereikbaar` (nooit "staat er niet in"). Een andere toestand (eerdere of toekomstige tekst)
  en een regeling buiten de graaf leest hij wel. `zoek_regelingen` (naam: afkorting exact + titel als woordgroep, de code
  rangschikt – exacte titel, afkorting, begin, geen regeling óver een andere, soort; filters: de dienst pagineert zelf met
  `startRecord`; een afkorting bij meer regelingen zegt "kies niet zelf"), `zoek_artikelen` (de artikelen, divisies en
  bijlagen in documentvolgorde met `reeks` = de koppen; `woorden` filtert op de tekst) en `get_wettekst` (rijen per lid
  en onderdeel met `nummer` en `jci`; de kop draagt de plek in de regeling; `status` vervallen of nog niet in werking).
  **Dezelfde lezer als de importer** (`bronmodel.bwb`): XSD, parser, `model_tekens` tegen `bron_tekens`; onder
  `STANDAARD_DREMPEL` weigert de adapter (`toestand_onvolledig`), onbekende structuur met volle dekking niet (de tool
  meldt het bij "niet gevonden"). **Eigen vindplaats**: `bwbt:<bwb>:<toestand>:<staart van de graaf-IRI>` (brontype
  `wettekst_live`, `bronmodel.extern.bwbt_delen`); de rijen dragen BWB-id's en jci's, maar `provenance.collect_sources`
  neemt van deze tools alleen het gelezen stuk (`LIVE_WETTEKST_TOOLS`), want de werkplek opent een BWB-vindplaats uit de
  graaf. Het bronvenster (`GET /v1/bronnen/wettekst_live/stukken/{id}`) krijgt daarvoor een graafverbinding. De
  graaftools geven bij een regeling die er niet in staat `niet_in_graaf` met `alternatief` (`_niet_in_graaf`), niet meer
  een lege lezing met een opgebouwde iri. **Herkennen in code** (`agent/buiten_graaf.py`, alleen met de connector aan):
  kandidaten uit vaste vormen (een samenstelling op -wet, een titel met "Wet", "7:610 BW", een afkorting na een artikel of
  lidwoord), wat de graaf bij naam kent valt af, de rest opgezocht bij de zoekdienst (exacte titel, of één regeling met die
  afkorting). In `supervisie._kies`: een dubbelzinnige afkorting is een vraag terug zonder model (`_keuze_regeling`), een
  genoemd artikel in een nieuw gesprek leest de code vooraf (`bron_lezen`), en na een modelkeuze komt het in het plan
  (`plan_regel`) en `bron_lezen`. Annoteren (`nodes/annotatie._niet_in_graaf`) en opnemen in een werkgebied
  (`bronselectie.NIET_IN_GRAAF`) zeggen dat het pas na een import kan. Tests met opnames van overheid.nl
  (`tests/fixtures/bwb_live/`, `WETGEVING_OPNEMEN=1`): `tests/test_wetgeving_tools.py`, `tests/test_buiten_graaf.py` en de
  vragenset `tests/test_wetgeving_live_vragenset.py`; live `tests/test_wetgeving_live_live.py`.
  **Na de eerste meting** (`docs/architectuur/metingen/wetgeving-live-2026-11-11/`, `tests/test_wetgeving_live_routes.py`):
  een tekstvraag naar één genoemd artikel gaat de **bepalingsworkflow** in (`bepaling_workflow.lees_buiten`, en `lees` met
  een peildatum buiten de graaftoestand: `live`, `peildatum`). De code leest het hele artikel met `get_wettekst` (alle
  pagina's) en toont het in het blok `extern` (`sjablonen.extern.heel_stuk`, zonder `MAX_PASSAGES`), met een `Leemte` bij
  vervallen of nog niet in werking; het model schrijft alleen de toelichting. `verify` toetst elke passage letterlijk tegen
  de gelezen rijen (`grounding.live_niet_letterlijk`), en een gelezen `wettekst_live`-stuk blijft in de bronnenlijst
  (`alleen_gelezen_extern`). `bron_lezen` leest bij `get_wettekst` ook alle pagina's (`HEEL_LEZEN`). Annoteren van een
  regeling buiten de graaf, en een vraag erover met de connector uit (maar wel in de straat), geeft een vaste melding
  zonder model (`supervisie._buiten_graaf_melding`; zonder connector op naam, `buiten_graaf.zonder_zoekdienst`). Na de
  controle (`controle.md` bij die meting): ook een verzoek om **op te nemen of toe te voegen** (`_OPNEEM_RE`) krijgt die
  vaste melding (`buiten_graaf.melding_opnemen`): het model schreef "staat nu in de bronselectie". Een onderdeel draagt
  zijn nummer als `plek` ("onderdeel b", `wetgeving_tools.onderdeel_plek`), want de tekst zelf draagt het niet. **Een duiding buiten de graaf rust op `extern`** (iteratie ronde 3): `onderbouwing` mag leeg als `extern` een gelezen stuk van `get_wettekst` aanwijst (`duiding.live_stukken`), en een weigering wijst dan naar `extern` met het id, ook als het model die tekst in `onderbouwing` zette (`_live_van`), nooit naar get_artikel: anders las het model de tekst opnieuw en schreef het het antwoord tot acht keer opnieuw (I13, 631k).
- **`graph/queries.py`** – de SPARQL-bouwers (o.a. `context()` = de GraphRAG-UNION).
  **`graph/schema.py`** – schema-introspectie met een cache van een uur. **`graph/results.py`** –
  `parse_select`: de MCP levert SELECT als JSON-string-gewrapte TSV.
- **`tool_execution.execute_tool`** – de ene uitvoeringsgrens voor tool-calls buiten de agent-lus
  (bron, dekking, leesroute), met `tool_execution`-events (start/einde, filters, status, aantal, duur, `bron`). Dat event is
  het contract voor eval, meting en audit; de jurist leest het niet. Wat hij moet weten zet `execute_tool` na het einde als
  **resultaatregel** in het denkproces, met de bron als actor: "Kamerstukken · 16 gevonden", "Begrippen · niets gevonden",
  "Kamerstukken · kst-33755-3 deels gelezen, er is meer dan dit", "Wetgeving · niet bereikbaar". Een aantal alleen bij
  een zoektool (bij een leestool telt het rijen, geen inhoud), een fout in woorden (`resultaat.REDEN_ZIN`), geen toolnaam,
  JSON of duur. Het tweede blok onder het antwoord ("Graaf geraadpleegd") is daarmee weg (9 nov 2026).
- **`agent/spoorbronnen.py`** – één register van wat Lex raadpleegt, intern (`WETGEVING`, `ANNOTATIES`, `BEGRIPPEN`,
  `METHODE`) en per connector afgeleid uit zijn beschrijving (`uit_connector`: label, werkwoorden, leestool = lezen, de
  rest zoekt). Daaruit komen het werkwoord van de statusregel (`toolregel`, achter `narratie._toolregel`) en de
  resultaatregel (`uitkomstregel`). Een nieuwe connector staat er zonder code in; een nieuwe graaftool krijgt hier een
  werkwoord en een zoek/lees-indeling, een nieuwe `reden` een zin in `REDEN_ZIN` – `tests/test_spoorbronnen.py` eist alle
  drie.

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
  zet daarna met één query per beurt de citeertitel in `regeling` en de afkortingen in `afkortingen`
  (de werkplek koppelt "artikel 9 Awb" daarmee alleen aan een bron uit de Awb). Het label komt waar nodig uit het
  toolresultaat (`_labels`): een wet-lokale `id:`-node (Leidraad 26.5) krijgt zo zijn naam in plaats van
  zijn IRI, en een structuurdeel zijn titel ("Hoofdstuk II – Invordering in eerste aanleg") – daaraan
  herkent de werkplek het deel in de tekst (cache per proces; een fout kost
  alleen de naam).
- **Een externe bron heeft een eigen soort** (ADR-013, `bronmodel.extern`): een Kamerstuk of Handelingen
  (`kst-36123-3`, `h-tk-…`), het Staatsblad of de Staatscourant (`stb-2023-123`), een uitspraak (ECLI) of EU-recht
  (`CELEX:…`, ELI). `vindplaats` blijft BWB-only, want tientallen aanroepers nemen een BWB-id aan. `iter_refs` levert de
  canonieke id; de bron draagt `brontype` en `link` (de publieke vindplaats), en `uri` is de id. `check_grounding` eist
  dat een genoemde id in de trace staat (op de canonieke vorm), `curate_sources` houdt een externe bron alleen als het
  antwoord haar id noemt. Een externe bron is geen wettekst: wat de wet zegt, onderbouwt hij niet.
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
- **Elke citaatvorm telt** (`_PAREN`: recht, typografisch, `„…”`, ook gemengd; binnen één alinea, geen lengtegrens). Eén
  tabel voor herkennen en herstellen. Cursief is geen citaatclaim; enkele aanhalingstekens blijven erbuiten.
- **`onbevestigd` is een signaal, geen afkeuring**: een artikel in gewone taal dat nergens in het opgehaalde voorkomt (ook
  niet in de wettekst zelf) en een blokcitaat dat niet letterlijk klopt. `niveau` zakt naar `onbepaald`, `grounded` blijft
  waar, dus geen correctieronde. `verify_node` logt het aantal: eerst meten hoe vaak dit vals alarm is.
- **Een bijna-letterlijk citaat wordt de brontekst** (`grounding.herstel_citaten`, in `agent_node`
  vóór de controle). Afwijkingen als een hoofdletter aan het begin of een punt
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
  `GET /v1/runs?actief=true` (`RunStore.voor_gebruiker`, E6) geeft alleen runs met precies die gebruiker, lopend of
  binnen `RECENT_S` geëindigd, als `Run.stand()` – zonder vraag of events; een lege header krijgt niets. Een lopende run
  zonder hartslag wordt daar ook verweesd verklaard, anders toont de sidebar "bezig" bij een beurt die nergens draait.
- **Eén ingang: `start_beurt`** (`api/main.py`). `POST /v1/runs` en de regisseur (ADR-012) starten een run langs
  dezelfde functie: het gesprek-slot, de eigenaar en `_stroom_voor` met vastleggen en boeken. Een kind-run draagt
  `ouder_run_id` (`Run`, kolom in `agent_runs`, in `RunStand` voor de sidebar). `stop_met_kinderen` stopt bij
  `cancel` en bij het verwijderen van een gesprek ook de lopende kinderen (`RunStore.kinderen`, over replica's heen).
  De budgetpoort is bij de route een dependency; `start_beurt(budget=True)` doet hem voor een aanroeper zonder route.
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
overleeft geen herstart (synchrone nodes, geen resume-pad).

**Elke run eindigt met precies één `done`, en die draagt de `uitkomst`** (klaar, mislukt, gestopt): `runstore.sluit_af`
staat om elke stroom in `_draai`, dus een route hoeft dat niet zelf te regelen. Kon de run zelf niet meer eindigen
(replica weg, proces sluit af), dan levert `volg` `afgebroken_events()`. Voor de client is alleen `done` het einde.

**De haak `bij_afbraak`** (`beurt.leg_afbraak_vast`) legt een bericht vast als niemand anders dat nog kan: de winnaar
van de verweesd-`UPDATE … RETURNING` (precies één, ook met meer lezers), de runs die `sluit()` annuleert, een crash in
de driver, en een fout uit een route die niet langs `voer_beurt_uit` gaat. Dubbel kan niet: de api ontdubbelt op
`run_id`. Lukt het schrijven niet, dan toont de werkplek de banner (`frontend/lib/lopendeRun.ts`).

> **Testen:** gebruik `with TestClient(app)` (zie `tests/test_run_endpoints.py`). Zonder `with` breekt de
> harnas per request zijn event loop af en sneuvelt de achtergrondtaak. Een bare `TestClient` draait de
> lifespan niet, dus de startup-checks storen de meeste tests niet.

### De uitkomst vastleggen (`agent/beurt.py`)

`voer_beurt_uit` zit om `answer_stream` heen, verzamelt de events (`BeurtSchrijver`) en schrijft aan het
eind via `agent/wetsanalyse_api.py`: **eerst de annotatielaag, dan het chatbericht**, gevolgd door één
`opgeslagen`-event. Dit staat **buiten** de LangGraph-code. **De server is de enige schrijver:** elke afloop krijgt
een bericht, ook een fout (`uitkomst: {status: "mislukt", melding}`, letterlijk de tekst van het `error`-event, dus
live en na herladen hetzelfde). Een bericht is daarmee ook de plek voor een kaartje dat na een fout klikbaar moet
blijven (`_leg_fout_vast`). Ook het oordeel van de controle staat op het bericht (`grounding`), met `afgekapt` als `agent_node` op `max_tokens` stuitte: de tekst blijft, tool-aanroepen vallen weg want hun argumenten zijn half, en `refusal` krijgt een eigen melding. Een nieuw veld op het bericht hoort in `BerichtInvoer`, `Bericht` én de mapping in
`gesprek_store.py`; de api laat een onbekend veld stil vallen (`test_contract_drift.py`). Een annotatie gaat als één batch per
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
- **Wat de api niet bewaart, meldt de driver als `error`** met een eigen tekst.
  `tests/test_gedeelde_laag.py` draait daarom tegen de échte client met een `MockTransport`.
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

**Tokenverbruik wordt niet via een event geboekt.** Wie meekijkt krijgt het wel te zien: vlak vóór `done` gaat
een `meting`-event mee met dezelfde cijfers als de logregel `beurt_meting`, plus het verbruik en de duur per
modelaanroep (`Verbruiksmeter.aanroepen`, hoogstens `MAX_AANROEPEN`). Alleen de run-events, niet `/v1/chat`;
de werkplek negeert het. Het boeken zelf blijft zoals hieronder. `AnthropicLLM` telt elk `usage`-blok op in een `Verbruiksmeter`
(`agent/models.py`, met een lock: takken kunnen parallel lopen). De aanroeper geeft dezelfde meter aan
`answer_stream` én `voer_beurt_uit`; de driver boekt hem in een `finally` (`POST /v1/verbruik`,
idempotent op `run_id`), zodat ook een mislukte of gestopte beurt telt. Een mislukte boeking is stil
(alleen log). De **pre-check** is `_budget_check` op `POST /v1/runs`: de api is de autoriteit (een
budget in procesgeheugen telt per replica), **fail-open** bij een onbereikbare api, en een lopende beurt
wordt nooit afgekapt – een halve annotatie is erger dan een kleine overschrijding.

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
   annoteert alles opnieuw, behalve afgeronde lagen. Is die ronde voltooid, dan zet de api de oude voorstellen van
   Lex zonder oordeel die ze niet meer maakte op `vervangen` (de respons van de batch draagt hun ids); `_leg_vast`
   zet er één zin achter de samenvatting over (`annotatie_samenvatting.vervangen_zin`), live en in het bericht.
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
  delegatiebevoegdheid, en op een Tijdsaanduiding "verbijzondert parameter") wordt alleen gezet bij
  eenduidig bewijs uit de detectiecodes, anders leeg. Het reist via het contract naar de api, de graaf
  (`jas:subtype`) en de exports. De toegestane waarden staan in `ALLE_SUBTYPEN`; de api-patroon en de
  zoektool moeten daar precies mee overeenkomen (`test_contract_drift.py`).
- **Een duur is één Tijdsaanduiding** (JAS-PRIORITY-001) met subtype "verbijzondert parameter"; alleen een
  getal in cijfers erin ('48' in 'binnen 48 uur') wordt een geneste Parameter (`jas.waarde.getal_in_duur`,
  code `DURATION_NUMBER`). Die code mag niet met `TEMPORAL_` beginnen, anders schrapt `specificiteit` hem
  (ADR-001, aanvulling bij PR 8).
- **Elke code in een `trace` heeft een verklaring** in `verklaringen.yaml`; `tests/test_verklaringen.py`
  weigert een code zonder verklaring en een verklaring zonder code. Draai daarna
  `python scripts/genereer_jas_vocabulaire.py`: die schrijft de vocabulairegraaf en `verklaringen.json`
  naar `api/app/vocabulaire/`, bewaakt door `tests/test_vocabulaire_drift.py`.
- **Relatievoorstellen, achter een proefvlag** (`RELATIE_VOORSTELLEN`, standaard uit; ADR-011 §*Voorstellen komen
  later*). `jas_pipeline/relaties.py` stelt na de keten relaties tussen haar voorstellen voor, zonder model, met vier
  regels: `uitvoer`/`invoer` uit de spans van `CALCULATION_QUANTITY` (`REL_UITVOER_FUNCTIE`, `REL_INVOER_FUNCTIE`),
  `waarde` uit de nesting met subtype (`REL_WAARDE_NESTING`), `operator_in` en `operand` met de woordvolgorde als
  `volgorde` (`REL_OPERATOR_IN_NESTING`, `REL_OPERAND_WOORDVOLGORDE`) en `voorwaarde` uit `advcl`+`mark` aan het
  hoofdpredicaat (`REL_VOORWAARDE_AANHECHTING`). Bij twijfel geen voorstel; elk voorstel gaat door de catalogus
  (`agent/jas_relaties.py`, gegenereerd door `scripts/genereer_jas_relaties.py`, dezelfde Python als de api). Een
  eindpunt is de lijst ankers van een voorstel; de api zet die om naar het element-id. Zonder vlag is de uitkomst
  bitgelijk (geen veld, geen fase, geen meting; `tests/test_relatievoorstellen.py`). Met vlag: `Uitkomst.relaties`,
  `meting.relaties`, `analyse.relaties`, één `relaties`-event na de elementen (`bron_annotatie.lokale_relaties`) en
  `relaties` in de batch. De vlag staat in `run.instellingen`. Kenmerk, tijd en rollen doet de keten nog niet. Een regel
  krijgt een code in `verklaringen.yaml` (sectie `relatie`) en vier testsoorten in `tests/test_relatievoorstellen.py`.
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
- **Geen begrip** (`geen_begrip.yaml`, `taal.geen_begrip`): een operator of parameterwaarde, een functiewoord, de kern van
  een vaste voorzetseluitdrukking ("kader", "betrekking") of een formulering die met "van" begint, doet niet mee aan
  zelfde term en de kop. De markering blijft; ze wordt alleen geen groep. `meting.geen_begrip` telt ze.
- **Relatievoorstellen uit wat er ligt** (S5; alle drie `Sterkte.MIDDEL`, dus een geel voorstel, `R-MIDDEL`): de kop van
  een samenstelling (`KOP_VAN_SAMENSTELLING`), een term met een bepalend woord naast zijn kern (`SPECIALISATIE_IN_TERM`:
  niet tussen twee termen uit dezelfde opsomming, die zijn nevenschikt) en het soortbegrip van een definitie
  (`GENUS_IN_DEFINITIE`: alleen met een afbakening erna, "X: de Y die …"; een komma is een opsomming en dan zijn het juist
  de soorten). `van` is het genus, `naar` de soort. Op de drie referentiesets is de uitkomst gelijk aan vóór deze regels;
  ze zijn dus niet bewezen op een gouden set.
- **Het bereik van een definitie** komt uit de aanhef ("Deze wet verstaat onder", "in dit artikel");
  "dit hoofdstuk" is onbekend, omdat de opbouw niet in de IRI staat.
- **Patronen** staan in `regels/relaties.yaml` met groepen `van`/`naar` en vier verplichte
  testsoorten (`tests/test_begrippen_patronen.py`); elke code heeft een regel in `verklaringen.yaml`.
- **Geen graafverkeer in de keten.** Definities buiten het werkgebied horen als contextbron in het
  manifest, of in de **onderzoeksstand** (spoor M): `Onderzoek`/`Contextbron` in `model.py`, gebouwd
  door de api (`api/app/begrip_onderzoek.py`), id `O…` uit de inhoud, getoetst met `past_bij(manifest)`.
  `keten.analyseer(..., onderzoek=)` laat definities in contextbronnen meetellen
  (`signalen.uit_contextdefinities`); zonder onderzoek is de uitkomst bitgelijk (`begrippen_eval`).
- **Het betekenisdossier** (`betekenis.py`, spoor M): per groep of begrip bronfeiten en signalen
  (`VOORKOMENS`, `PARALLELLE_BEPALINGEN` met de variantwoorden, `DEFINITIE_IN_CONTEXT`,
  `KWALIFICATIE_SAMENGESTELD`, `BEREKENING_OP_TERM`, `ROL_IN_BEPALING`, `AFLEIDINGSREGEL`,
  `GEEN_DEFINITIE_GEVONDEN`) plus open vragen. Deterministisch; het gaat naar de prompt (`blok`) en de
  toetsen (`toetsen.met_dossier`), nooit naar `besluit.py`. De berekeningspatronen staan in
  `betekenisregels/berekening.yaml` (vier testsoorten, `tests/test_betekenis.py`); `BEREKENING_IN_BEPALING`
  (onbeslist, zwak) maakt van `ZELFDE_BEPALING` een vraag. De fragmentruimte is manifest + onderzoek
  (`fragmenten.alle`, `onderzoeksfragmenten`: contextdefinities, eigen bronnen, zelfde artikel,
  verwijzingen, contextselecties). Meten: `uv run python -m eval.betekenisonderzoek_eval` (offline).
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
  context, en een
  definitie: *letterlijk* (de definiens, zonder model) > *samengesteld* (het model kiest fragmenten op
  id, code plakt ze aan elkaar) > *geformuleerd* (het model schrijft, noemt zijn fragmenten, altijd
  geel; een cirkel wordt verworpen). Voorbeelden horen bij fase E.
- **Fragmenten** (`fragmenten.knip`): zinsdelen met een id uit bron en offsets. Het model typt nooit
  brontekst over.
- **Toetsen** (`toetsen.py`): garanties (id bestaat, tekst letterlijk op offsets, over manifest +
  onderzoek) halen een definitie weg; signalen (circulair, rekenregel, gemengde klassen, geen begrip, en
  met het dossier: algemene naam met specifieke definitie, rechtsgevolg of afleiding in de definitie,
  onderbouwing uit één voorkomen, fragment draagt niet, tegenbewijs, context niet onderzocht) maken haar
  geel. Het model geeft per voorstel een `Duiding` (soort, bereik, voorkeursterm, ontbreekt): een
  interpretatie bij het voorstel, geen bewijs; afzien met `ontbreekt` wordt "Onvoldoende bewijs: …". Signalen gaan
  over wat Lex voorstelt, niet over de wet. Elke code heeft een tekst in `TEKST`.
- **Batches** zijn inhoudelijk (`verdieping.batch_id`: soort, id's, promptversie, model en – met een
  onderzoek – het `onderzoek_id`): dezelfde batch draait één keer, dus een herstart is hervatbaar én
  reproduceerbaar. De bevestiging draagt een `werkvoorraad_id` (`begrippen_verdieping.werkvoorraad_id`:
  vragen, kaarten, onderzoek, model, promptversies); een gelijk aantal met een andere inhoud start niet.
- Meten: `python -m eval.begrippen_eval --model --versie <set>` (drie herhalingen, kost geld).

### De begrippenrun (`agent/begrippen_run.py`, spoor D levering 3a)

`begrippen_stroom` (via `begrippen_beurt.begrippen_kern`, de taak `voorstellen` van de begrippen-agent;
het eigen endpoint `/v1/begrippen-runs` is met F3e vervallen): haal de run met manifest bij de api
(`GET …/begrippen-runs/{id}?manifest=true`), meld `…/loopt`, draai de keten in een thread met de fasen als `status`-events (`Lex · Taalanalyse: … (n ms)`), zet de uitkomst terug (`PUT …/uitkomst`)
en eindig met `opgeslagen` + `done`.

- **De api is de bron van het manifest**, graph-qa rekent alleen. Het manifest valideert tegen
  `Manifest` (letterlijkheid, geen dubbelen); klopt het niet, dan `mislukt` en een `error`.
- **Eén run per werkgebied tegelijk**: loopt er al een, dan wacht de taak erop (`begrippen_kern` peilt). Stoppen kijkt vóór en ná de keten (de keten
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
- **Eerst de brondefinitie** (S2, e2e 5 nov 2026: 153.504 tokens voor één onbruikbare definitie, daarna vond de
  zoekactie zonder model er drie). Twee stappen zonder model: de keten neemt een definitie uit het onderzoek letterlijk
  over als haar bereik een lid omvat (`kaart.naam_en_letterlijk`, ook bij `voorstel`, dus de groep valt uit de
  werkvoorraad), en vlak voor de kaartbatches zoekt `brondefinitie_eerst` per overgebleven groep in de graaf. Wat daar in
  het werkgebied of zijn regelingen staat, gaat niet naar het model; de kaart noemt de vindplaats en de analist neemt over
  op de begripskaart. Een treffer *elders* slaat het model niet over, en een haperende graaf ook niet.
- **De schatting volgt de meting** (api `schatting`): gemeten tokens per item, per soort, plus een bovenkant (`hoog`). De
  samenvatting noemt wat het kostte naast de schatting.
- **Alles klaar** → hergroeperen, kaarten, `PUT …/verdieping` (groepen met `door`, kaarten, oordelen,
  open vragen), en een samenvatting met het begrippenartefact.
- Tests: `tests/test_begrippen_verdieping_run.py` (nep-api en nep-model; het api-contract uit de bron).

### Lex naast de kaart (`agent/begrip_kaart.py`, `begrippen_pipeline/kaartacties.py`, fase E)

Vijf acties op één begrip, elk een voorstel per veld; de api bewaart ze als eigen object en het begrip
verandert pas als de analist overneemt (`api/app/begrip_voorstel_store.py`). Ingang: de taken van de
begrippen-agent (`kaart_beurt.kaart_kern`: `POST …/kaart-runs` bij de api, dan `kaart_stroom` – run met
invoer ophalen, `…/loopt`, rekenen, `PUT …/uitkomst`; loopt dezelfde actie al, dan wacht hij). Het eigen
endpoint `/v1/kaart-runs` is met F3e vervallen.

- **Zoek de brondefinitie** – geen model, geen budgetpoort. `q_brondefinities` zoekt
  `bwb:definieertBegrip` op naam en alternatieve termen, met de aanhef van de ouder (`CONTAINS`, want de graaf kent ook
  één begrip voor meer termen, "directeur, inspecteur of ontvanger"; `_draagt` toetst de term daarna exact, dus een langer
  woord telt niet). `q_onder` zoekt "Onder X wordt verstaan" in de tekst: de importer legt daar geen
  `bwb:definieertBegrip` op (Awb 1:2; 31 bepalingen op acceptatie). **Een definitie die alleen de term noemt en
  doorverwijst** ("de ontvanger, bedoeld in artikel 2 …", `definities.verwijst_door`) is circulair: `_gevolgd` volgt
  `bwb:heeftVerwijzing` naar lid en onderdeel uit de ankertekst (`doelen`, hoogstens twee stappen) en stelt de definitie
  daar voor; lukt dat niet, dan geel met `DEFINITIE_VERWIJST_DOOR`, nooit groen.
  `plaats` geeft elke treffer *werkgebied* (`in_selectie`), *regeling*, *definitieverwijzing* (een
  regeling waar een begripsbepaling uit de regelingen van het werkgebied naar verwijst, `q_verwezen`)
  of *elders*. `kaartacties.brondefinities` neemt alleen een echte definitie letterlijk over
  (`definities.definiens`; "verstaat mede/niet onder" niet – dat zegt `geen_definitie_melding`), de
  sterkste plaats eerst, hoogstens vijf; buiten het werkgebied is het voorstel geel.
- **Scherper, betekenisverschil, voorbeelden** – met het model (`LLM_MODEL`), elk één `strict` tool:
  fragmenten op id uit de bronnen van de passages en de begripsbepalingen van de term
  (`fragmenten_voor`); daarna `toetsen` in code. Een ongeldig antwoord, een onbekend fragment of geen
  verbetering levert een `melding` en geen voorstel; een geformuleerde cirkel wordt verworpen.
  Betekenisverschil (met `ander` uit de invoer) levert een alinea `uitleg` en, als de tekst de grens
  aanwijst, een `context` (de toelichting, `skos:scopeNote`); voorbeelden zijn altijd geel en zonder
  bronanker, met een signaal zonder tegenvoorbeeld, en het *waarom* van Lex staat als `motivatie` bij
  het voorstel, niet bij het begrip (spoor I1).
- **Budget** vóór een model-actie (`verbruik.budget_poort`); het verbruik op `kaart-<run>`, ook bij een fout.
- **Codes**: de aandachtspunten van deze acties staan in `kaartacties.TEKST`, los van `toetsen.TEKST`
  (de werkplek leest die laatste letterlijk mee; een nieuwe code daar breekt de frontend-drift-test).
- **Contract**: `tests/test_begrip_kaart.py` leest `api/app/begrip_voorstel_contracts.py` uit de bron.
- **Schrijf de uitleg in B1** (spoor I2, `kaartacties.uitleg`): alleen op een definitie, één strict tool
  (`schrijf_uitleg`: één alinea van hoogstens vijf zinnen, met fragmenten), daarna de **B1-toetsen in code**
  (`begrippen_pipeline/begrip_b1.py`, met de woordenlijst `b1_woorden.yaml`): `B1_LANGE_ZIN`, `B1_TE_LANG`,
  `B1_LIJDENDE_VORM` (spaCy `aux:pass`, zonder parser een patroon), `B1_MOEILIJK_WOORD`,
  `B1_VAKTERM_ONVERKLAARD`, `B1_HERHAALT_DEFINITIE`. Een treffer is een aandachtspunt, geen weigering; het
  voorstel is altijd geel. De regels staan in de skill (`references/nl-sbb-en-b1.md`, sectie
  `nl-sbb-taalniveau`, die de specialisten `definitie` en `algemeen` dragen; de prompt van `schrijf_uitleg` draagt hem
  niet, de toetsen zijn code).
- Meten: `uv run python -m eval.kaartacties_eval` (live tegen de graaf, geen model; een ontwikkelset,
  meetlogboek `kaartacties-2026-10-16`); de uitleg met `uv run python -m eval.uitleg_eval --runs 3` (graaf én
  model, kost geld: per code hoe vaak een B1-toets afgaat).

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
- In de antwoordroute gaat `werkgebied_id` mee als `State.werkgebied_id`: de begrippen van dat werkgebied
  staan vooraan bij `search_begrippen` (fase F4, hieronder).
- Tests: `tests/test_begrippen_beurt.py` (request-model, verloop tegen een nep-api).

### Bronnen vinden met Lex (`agent/bronnen_vinden.py`, `agent/bronnen_run.py`, fase A)

Vier modules, elk één taak (gesplitst 4 nov 2026, gedrag ongewijzigd – de eval was byte-gelijk):
`bronnen_vinden` (de graafmethoden, `Verzameling`, `vind`), `deelvraag_zoeken` (`kandidatenpool` en de
rangschikking `bepaling_opties`, gedeeld met de intake), `zoektermen` (termen, stammen, samenstellingen,
`uitsluitstammen`, `buiten_uit_afbakening`) en `bepaling_namen` (`_benoem`, `plek_uit_iri`,
`bepalingen_uit_tekst`).

Vanaf de selectie van een werkgebied (kern = rol *analyseren*) zoekt Lex bepalingen die erbij kunnen
horen; de api bewaart de kandidaten en de besluiten (`api/app/bronnen_run_store.py`).

- **Methoden, zonder model** (`METHODEN`): `overzicht` (onderwerp uit de analysevraag, anders de naam
  van het werkgebied; rol kern), `verwijzing_uit` (diepte 1 vanaf de kern en haar leden/onderdelen;
  afhankelijkheid bij een bekende functie, anders aanverwant), `verwijzing_in` (aanverwant),
  `definitie` (een `bwb:definieertBegrip` in de regeling van de kern waarvan de term letterlijk in de
  kern staat; afhankelijkheid), `opbouw` (de andere artikelen in hetzelfde deel; aanverwant),
  `gelijkenis` (`bwb_similarity`), `grondslag` (zoekvraag a: waar de gekozen gebeurtenis haar bestaansrecht krijgt,
  `zoekvragen.grondslag`; rol kern, alleen als het dossier een `gebeurtenis` draagt) en `deelvraag` (per actieve deelvraag `bepaling_opties`, dezelfde
  functie als de intake (F3f): binnen de regelingen van de selectie, op lid-niveau, hoogstens
  `MAX_PER_DEELVRAAG`; kern zonder kern, anders aanverwant; het bewijs draagt `deelvraag_id` en wat de
  bepaling raakt, zodat de api een opgenomen bron aan de deelvraag koppelt).
- **De standaard volgt de meting** (`standaard_voor`, meetlogboek `bronselectie-2026-10-15`): met een
  kern `STANDAARD` = verwijzing uit, definitie, opbouw; zonder kern `ZONDER_KERN` = het overzicht.
  Overzicht (met kern), `verwijzing_in` en `gelijkenis` hielpen niet aantoonbaar en staan uit. Wijzig
  je een methode, meet dan opnieuw: `uv run python -m eval.bronselectie_eval` (offline, tegen de
  opname naast de set) en `--opnemen` (live); `tests/test_bronselectie_eval.py` bewaakt dat de standaard
  alles vindt wat nodig is en niets uitgeslotens voorstelt. Heeft het werkgebied deelvragen (ze staan
  alleen dan in de invoer), dan komt `deelvraag` erbij: de analist vroeg er zelf om. Die methode meet
  `--intake` per deelvraag, met `recall_pool` (wat de index vindt vóór de rangschikking), het profiel
  `F3F` als ijkpunt en de ablatie per vlag van het `Zoekprofiel`; `--aanvullen` haalt alleen ontbrekende
  queries live op en laat een bestaande opname (bewijs) staan. Meetlogboek `bronselectie-2026-11-03`.
- **Zoeken en rangschikken per deelvraag** (`bepaling_opties`, `Zoekprofiel`): per regeling de index op
  alle termen samen (per knooptype) én per term apart; een samenstelling zoekt ook op haar delen
  (`splitsingen`, `(bezwaar AND *schrift*)`) en de telling vouwt een ellips uit (`ellipsen_uitgevouwen`:
  "bezwaar- of beroepschrift"); divisies van een beleidsregel zijn bepalingen; de kop van het deel komt voor
  de hele pool (`kop_raakt`); rangschikken is RRF (`RRF_K`, geen gewichten – geen set is groot genoeg om
  ze op af te stemmen). Het lemma bestaat als vlag maar staat uit (hielp niet). Daarna gaan de plaatsen om de beurt
  naar de regelingen, wet eerst (`per_regeling`, `om_de_beurt`, soort uit `bwb:soort` via `overzicht.RANG`), zodat
  een beleidsregel met lange divisies het kaartje niet vult; `lengte` (demping) bestaat als vlag en staat uit. Een treffer in de lijst van
  een term is het bewijs dat de bepaling die term raakt. Het dossier zoekt mee als vlag, en die vlaggen staan
  allemaal uit (meetlogboek `bronselectie-2026-11-04-dossier`): `dossier_velden` (aanleiding en doel),
  `dossier_lijsten` (een indexlijst per dossierterm; die verdringt de deelvraag), `dossier_omgeving` (artikel of
  eerste divisie, idf-gewogen; `omgeving_van`) en `gelijkenis` (`bwb_similarity` op deelvraag en
  praktijkvoorbeeld; vindt binnen de regelingen bijna niets). Een nieuwe dossieringreep krijgt een eigen vlag, en
  de eval-route `met <vlag>` gaat vanzelf mee via `DOSSIERVLAGGEN`.
- **Plek en bepaling uit de graaf, niet uit de IRI** (`agent/plekken.py`): de importer schrijft
  `bwb:vindplaats` en `bwb:inBepaling`. Een onderdeel telt voor zijn `inBepaling` (bij de Leidraad hangt
  `…:artikel:9:o:d` onder divisie 9.2); de IRI-knip (`_doel_van`) is alleen de terugval voor een wet.
  `_benoem` rekent de naam telkens opnieuw uit de bron-IRI ("Artikel 9.4 – Dagtekening aanslagbiljet –
  Leidraad Invordering 2008"), nooit uit een label dat er al stond – anders kwam de regeling er twee keer
  achter.
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
- **Eén ingang**: `bronnen_run.zoek_run`, de zoekfunctie van de bronselectie (spoor J); ze zegt alleen of het
  zoeken lukte, wat er gevonden is leest de bronselectie per deelvraag bij de api. De actie `bronnen_zoeken`
  gaat naar de bronselectie (`BRONSELECTIE_ACTIES`). Een open voorstel telt met één regel (`is_open`: ook niet
  `vervallen`, de api zet die vlag als de laatste klare run het niet meer vond).
  "Welke artikelen gaan over X?" blijft de overzichtsroute, ook binnen een werkgebied. Een weigering van de api (`geen_vertrekpunt`) is een antwoord.
- Tests: `tests/test_bronnen_vinden.py` (functiepatronen, methoden tegen een nep-graaf, het
  api-contract uit de bron, run, taak).

### Lex stelt deelvragen voor (`agent/deelvragen.py`, vervolg op fase F)

Deelvragen bij een werkgebied zijn optioneel (open keuze 4); de api bewaart ze
(`api/app/werkgebied_deelvragen.py`). Voorstellen is de taak `voorstellen` van de deelvragen-agent
(`deelvragen.voorstellen_kern`; het eigen endpoint `/v1/deelvragen-runs` is met F3e vervallen): werkgebied
ophalen, zonder analysevraag `geweigerd` (`soort: "invoer"`) zonder modelaanroep, dan één aanroep op
`LLM_MODEL` met één tool (`stel_deelvragen_voor`, niet strict: het schema begrenst aantal en lengte, en `valideer` doet
de rest; het hele dossier van het werkgebied gaat mee via
`werkgebied_context.context_tekst`, en de bestaande deelvragen, zodat Lex er geen variant van bedenkt),
`valideer` (alleen vragen met een vraagteken, ontdubbeld, hoogstens `MAX_DEELVRAGEN`),
`POST …/deelvragen/voorstellen`. Het verbruik telt mee in de beurt. De api laat weg wat er al staat of is
afgewezen. Tests: `tests/test_deelvragen.py` (het contract `DeelvraagVoorstellen` uit de api-bron).

### Lex annoteert het werkgebied (`agent/werkgebied_annotatie.py`, fase B)

Binnen een werkgebied annoteert Lex in één run de bepalingen die nog **nieuw** zijn – alleen van
bronnen met rol *analyseren*, per lid zoals de keuzekaart. Ingang: `POST /v1/runs` met `werkgebied_id`
en `modus: "werkgebied_annoteren"` of de actie `werkgebied_annoteren` (de reeks, in `_stroom_voor`). Getypt
("annoteer wat nog niet geannoteerd is") kiest de supervisor de annotatie-agent met taak `werkgebied`:
het voorstel met de bevestiging (`werkgebied_voorstel`, F3c).

- **De werkvoorraad komt van de api** (`GET …/annotatie-werkvoorraad`), nooit van de browser.
- **Drie bereiken** (`ChatRequest.bereik` + `deelvraag_id`, en zo ook in de `bevestiging`): het hele
  werkgebied; alleen de bronnen onder alle actieve deelvragen (`bereik: "deelvragen"`, de taak `deelvragen`
  van de annotatie-agent of de actie `deelvragen_annoteren`); of die onder één deelvraag (het onderwerp, of
  "deelvraag 2" via `deelvraag_op_nummer`). De api filtert; de teksten zeggen waar het over gaat (`plek`) en
  wat buiten het bereik blijft. Zijn er meer bepalingen dan bronnen, dan zegt Lex waarom (een artikel met leden
  per lid) en welke bronnen het meest bijdragen (`_bronnen_en_bepalingen`). Bij het hele werkgebied noemt Lex de kleinere werkvoorraad onder de
  deelvragen, als die er is (`_alternatief`, best-effort). Een weigering van de api (404, 409
  `niet_actief`/`geen_deelvragen`) is een antwoord (`weigering`), geen storing.
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
- **Een deel van de werkvoorraad** (ADR-012): `eenheden` neemt alleen de doorsnede met wat de api als nieuw geeft
  (`deel_van`), en `bevestigd` telt die doorsnede. `budget_aandeel` stopt de run tussen twee bepalingen zodra de volgende
  (de mediaan, of het gemiddelde tot nu toe, uit de `meting`-events) er niet meer in past (`binnen_aandeel`); de poort van
  de api blijft gelden. Zo werken de kinderen van een regie zonder overlap en binnen hun aandeel.
- Tests: `tests/test_werkgebied_annotatie.py`.

### Het plan van een regie (`agent/regie/plan.py`, ADR-012)

Zuiver en deterministisch, uit de stand bij de api: `plan_bronnen` (per deelvraag die niet klaar is een taak) en
`plan_annoteren` (de werkvoorraad zonder overlap: elke bepaling naar de eerste deelvraag waaronder ze valt; hoogstens
`PLAFOND`; krimpt tot de bovenkant `MARGE × mediaan` in het resterende budget past; per kind een aandeel `AANDEEL ×
schatting`, zonder schatting het budget gelijk verdeeld). `plan_id` hasht alleen het werk, niet de schatting. Wat niet
meegaat, staat in `buiten` met de reden, ook een bepaling die al een annotatie heeft (`_al_geannoteerd`: "al een annotatie en overgeslagen", met haar stand). `kind_verzoek` maakt het `ChatRequest` van een kind: de actie `bronselectie`
op de deelvraag, of `deelvragen_annoteren`/`werkgebied_annoteren` met `bevestigd`, `eenheden` en `budget_aandeel`.
Tests: `tests/test_regie_plan.py`.

### De regisseur (`agent/regie/regisseur.py`, ADR-012)

Een regie verdeelt het werk in een werkgebied over deelgesprekken: een eigen stroom in `_stroom_voor` (zoals de reeks),
geen node. Ingang: de acties `regie_bronnen` en `regie_annoteren` (`REGIE_ACTIES`, geen taak van een agent), of een getypte
opdracht met "per deelvraag" (`opdracht_in`, alleen een verzoek; met bronnen én annoteren eerst de bronnenronde).
`tests/test_regisseur.py` haalt elke vraag uit de routerings- en gespreksset erdoorheen: geen ervan mag erin vallen.

- **Eerst een bevestiging** (`soort: "regie"`, `plan_id`): zonder `plan_id` gelijk aan het plan van nu alleen het voorstel,
  met kosten, de grens op tegelijk en wat niet meegaat.
- **Dan de regie bij de api** (409: er loopt er al een), een hartslag elke `HARTSLAG_S`, en per taak een kindgesprek
  (`ouder_id`, `regie_id`) met een gewone run langs `start_beurt` (`ouder_run_id`, budgetpoort aan). Hoogstens
  `REGIE_PARALLEL` (2, max 3) tegelijk, met een semafoor; volgen is `await` op de taak van het kind. De bronnenronde zoekt
  vooraf één keer (`zoek_run`), zodat de kinderen niet op elkaar wachten.
- **Stoppen** van de regierun stopt de lopende kinderen (`_stopwacht`), en wie nog wacht, start niet.
- **De bundel** komt uit de stand bij de api na afloop: opgeleverd, wacht op jou (voorgestelde bronnen, markeringen te
  beoordelen, wat niet aan bod kwam), mislukt of niet aan bod. Het bericht draagt het artefact `regie`.
- **Geen besluit.** `API_AANROEPEN` is de lijst api-methoden die de regisseur gebruikt; de test toetst de code en een hele
  ronde ertegen. Opnemen, uitsluiten, beoordelen, afronden en accorderen staan er niet in.
- **Eén trace**: `_voer_uit` draait in een eigen taak onder de span `graph_qa.regie`, elk kind onder `graph_qa.regie.taak`;
  een kind-run erft die context. Logregels `regie_taak` en `regie_afloop`.

### Lex stelt een werkgebied samen (`agent/werkgebied_intake.py`, `nodes/werkgebied.py`, activiteit 1)

"Kunnen we een werkgebied samenstellen?" of "ik wil een wetsanalyse uitvoeren" (`is_werkgebiedvraag`)
start een **intake** (en met dezelfde kaartjes vult Lex het dossier van een bestaand werkgebied aan, zie
*Aanvullen* onderaan): één vraag per kaartje in de volgorde van de methode (spoor F, F2) – naam, dan
startactiviteit a (aanleiding, context, doel), analysevraag, praktijkvoorbeeld, deelvragen, wat valt
erbuiten, de regeling(en) (het zoekbereik, `werkgebied.regelingen`) en de gebeurtenis (dezelfde kaart als de
bronselectie, `bronselectie.gebeurtenis_opties`) – en een samenvatting met *Aanmaken*. Bepalingen kiest het
samenstellen niet meer (4 nov 2026): na het aanmaken stuurt de beurt-driver `opgeslagen.vervolg` (de bronselectie),
en de werkplek start die als volgende beurt. De
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
- **Terugbladeren** (‹ n van N ›, negen vaste stappen plus één kaartje per deelvraag): `wijzig` mag
  vanaf elke stap naar een eerdere (bij de bepalingen ook naar een eerder deel, `naar_deel`), vanaf de
  samenvatting naar elke stap. Het kaartje draagt `terug`/`beantwoord`, en `vooringevuld` komt dan uit
  het eerdere antwoord (`eerder_antwoord`).
- **De volgorde is een stapmachine** (`verwerk`), nooit het model. Een klik op een kaartje dat al
  beantwoord is (`stap` ≠ de huidige) verandert niets: Lex toont het huidige opnieuw. Een kaartje van
  een andere intake: "loopt niet meer". De naam is verplicht; de rest is over te slaan.
- **Aanleiding en doel** zijn de vaste lijsten van de Leidraad in eigen woorden (`AANLEIDINGEN`,
  `DOELEN`; de Leidraad is BRM-materiaal en hoort niet letterlijk in deze publieke repo), plus eigen
  tekst; doel is meerkeuze. Context en praktijkvoorbeeld zijn vrije tekst, zonder voorstel – een
  praktijkvoorbeeld verzint Lex niet.
- **Het model stelt alleen voor** (`stel_voor`, op `LLM_MODEL_ROUTER`, één tool, niet strict – het schema begrenst aantal en lengte): naam,
  voorselectie van aanleiding en doel (enum-sleutels; een onbekende valt weg), analysevraag en een
  onderwerp om mee te zoeken. Een startzin zonder inhoud kost bij de naam geen aanroep; een storing
  levert een kaartje zonder voorstellen.
- **Deelvragen** stelt Lex voor met `deelvragen.vraag_model` op `LLM_MODEL` (zelfde prompt als de
  deelvragenrun, met het hele dossier); zonder analysevraag niet, en dat staat op het kaartje. Het
  kaartje is meerkeuze met `meer_tekst`: eigen deelvragen komen als `teksten`. Elke vraag één keer
  (`normaliseer`, gelijk aan de api), met herkomst `lex` of `analist`.
- **Regelingen komen uit de graaf** (`regeling_opties`): eerst wat het dossier bij naam noemt (niet wat
  erbuiten valt), dan het overzicht van het onderwerp, dan het overzicht per deelvraag (hoogstens
  `MAX_DEELVRAAG_ZOEK`; `onderwerp_van_deelvraag`). Delen waarvan de kop raakt aan wat buiten het
  werkgebied valt, noemt de toelichting. Eigen tekst bij de regelingen is een nieuwe zoekopdracht.
- **Daarna per deelvraag één kaartje met bepalingen** (F3f; `intake["deel"]`, `kaartsleutel`
  `"bepalingen:<n>"` voor voorstellen, meldingen en voorbereiding; zonder deelvragen één kaartje bij de
  analysevraag). De opties komen zonder model uit `deelvraag_zoeken.bepaling_opties` – dezelfde functie
  als de deelvragen-agent – binnen de gekozen regelingen, op lid-niveau, hoogstens `MAX_BEPALINGEN`.
  Wat meer raakt aan wat erbuiten valt dan aan de deelvraag, valt niet stil weg: onderaan, met "valt
  mogelijk buiten de afbakening", nooit aangevinkt (fix 1). De keuze staat onder de tekst van de
  deelvraag (`deel_sleutel`), zodat terugbladeren en herordenen haar laten staan; een keuze bij een
  deelvraag die er niet meer is, telt niet. De keuzes op de bepalingen-kaartjes tellen niet mee in de
  hash van de voorbereiding (`dossier_hash(zonder=)`), dus terugbladeren zoekt niet opnieuw.
  **"Weet ik (nog) niet"** (`ONBEKEND`) staat altijd bij regelingen en bepalingen; bij de regelingen
  gaat het dan meteen naar de samenvatting.
- **Alleen een gekozen bepaling wordt een bronselectie** (rol *analyseren*, bereik *onderliggend*),
  gekoppeld aan de deelvragen op wier kaartje ze gekozen werd (één bron voor meer deelvragen). **Een getypte
  bepaling is ook een keuze** (spoor L): de node ontleedt de tekst vóór `verwerk` (
  `bepaling_namen.bepalingen_uit_tekst`, dezelfde regels als spoor J: geknipt vóór elk "artikel", per stuk de
  regeling die het noemt, anders de enige van de tekst of van de intake; Awb-nummers als 4:86) en toetst elke
  bepaling in de graaf (`bepaling_namen.bepaling_in_graaf`, één lichte query). Gevonden: `eigen` op het antwoord.
  Niet te bepalen, niet gevonden ("staat niet in AWR; wel in Awb – bedoel je die?") of een haperende graaf: het
  kaartje blijft staan met de vraag en de getypte tekst (`concept`) – nooit stil weg. `eigen` komt nooit van de
  client. Lange velden houden hun alinea's (`_met_alineas`), en een getypte regeling naast aangevinkte is een
  zoekopdracht die het aangevinkte laat staan. Een regeling zonder
  gekozen bepaling staat alleen in de afbakeningstekst (`afbakening`). Die tekst noemt de regelingen en wat
  erbuiten valt, niet de bepalingen: die staan één keer, als bronselectie per deelvraag (spoor K). Bij een
  deelvraag moet een optie een deelvraagterm raken; dossiertermen rangschikken alleen (anders vulde het dossier
  elk kaartje tot het maximum).
- **Aanmaken doet de beurt-driver** (`beurt._maak_werkgebied`), na het `werkgebied_aanmaken`-event:
  `POST /v1/werkgebieden` met het dossier, de deelvragen, het zoekbereik en de `intake_id` (idempotent bij de
  api). Bronnen kiest daarna de bronselectie per deelvraag; mislukt het werkgebied zelf, dan `error` met `foutcode: werkgebied_niet_aangemaakt`.
  Het bericht draagt het artefact `{soort: "werkgebied", ref: {werkgebied_id}}`.
- **Het kaartje reist mee**: een `vraagkaart`-event (vorm `api/app/gesprek_contracts.Vraagkaart`) en
  het veld `vraagkaart` op het bericht, zodat het na herladen nog te beantwoorden is.
- **Aanvullen: het dossier van een bestaand werkgebied** (`modus: "aanvullen"`, `aanvul_intake`). "Kun je
  het praktijkvoorbeeld toevoegen?" leverde eerst deelvragen-voorstellen op: er was geen taak voor het
  dossier, dus de supervisor pakte de dichtstbijzijnde. Nu:
  - **Ingang**: de supervisor kiest `werkgebied` met `TAAK: aanvullen` (getypt), of de actie
    `dossier_aanvullen` (`models.INTAKE_ACTIES`, geen taak van een agent en dus niet in `ACTIE_TAAK`). Beide
    zetten `State.intake_modus` (per beurt gereset). De prompt zegt ook: past geen taak, kies dan geen agent.
  - **Het thema** (spoor I7): een stap `thema` die alleen bij het aanvullen bestaat (`KAARTSTAPPEN`; het
    samenstellen houdt `STAPPEN`), na het praktijkvoorbeeld (`VOLGORDE_AANVULLEN`). De node haalt het voorstel
    zonder model bij de api (`…/thema-voorstel`, uit de WTI-rechtsgebieden van de bronnen) en vinkt het eerste
    aan als er nog geen thema is; alleen een thema dat op het kaartje stond telt. De samenvatting toont namen,
    de wijziging stuurt de TOOI-URI. *Kies een thema* (de suggestie) is `dossier_aanvullen` met die tekst.
  - **Welke velden**: `dossiervelden_in(vraag)` (woorden → stap; *afbakening* en *buiten* → `buiten`), en
    zonder genoemd veld de lege velden (`lege_velden`). Is niets leeg, dan noemt Lex wat er staat, zonder
    kaartje. Alleen `DOSSIERSTAPPEN` (naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld,
    buiten); deelvragen en bronnen blijven bij de deelvragen-agent.
  - **Beginstand uit het werkgebied** (`antwoorden_uit`, de omgekeerde richting van `als_werkgebied`):
    aanleiding en doel als eigen tekst zonder keuze, de afbakening bij `buiten` (de hele tekst, tot 4000
    tekens). `intake["werkgebied"]` bewaart het dossier met deelvragen en bronlabels, zodat `dossier` en
    `stel_voor` het hele werkgebied zien. Vooringevuld komt uit `eerder_antwoord`, ook voor vrije tekst.
  - **Stappen**: alleen de gevraagde (`intake["stappen"]`), ‹ n van N › daarover. Overslaan laat het veld
    staan. ‹ vraagt de werkplek de vorige stap van het samenstellen: `verwerk` neemt de laatste gevraagde
    stap die daar niet na komt. Een praktijkvoorbeeld en de context hebben geen voorstel en dus geen
    modelaanroep; voor de naam stelt Lex altijd voor (er ligt een dossier).
  - **Samenvatting** draagt `{wijzigingen: [{veld, label, toen, nu}]}` (`wijzigingen`; witruimte en een
    slotpunt tellen niet). Zonder wijziging "Er verandert niets." en geen *Opslaan* – `verwerk` weigert
    `opslaan` dan ook. `aanmaken` en `opslaan` horen elk bij hun eigen modus.
  - **Opslaan**: de node haalt eerst het werkgebied. Is de revisie veranderd (ook door een eerdere
    geslaagde opslag), dan een nieuwe intake op de stand van nu met de antwoorden van de analist ernaast
    (`op_nieuwe_stand`), geen wijziging. Anders een `werkgebied_wijzigen`-event (`wijzigverzoek`: alleen de
    gewijzigde velden, de revisie van het begin, en het samenvattingskaartje).
  - **De beurt-driver** (`beurt._wijzig_werkgebied` → `WetsanalyseApi.wijzig_werkgebied`, PATCH) legt het
    bericht vast met het werkgebiedartefact en een zin uit de wijziging (`wijzig_tekst`). 412 (iemand was
    net eerder): niets opgeslagen, en het samenvattingskaartje komt terug zodat opnieuw opslaan op de
    nieuwe stand landt; 404: het werkgebied bestaat niet meer; anders `error` met `foutcode:
    werkgebied_niet_gewijzigd`. De revisie in de historie is van de analist (`X-User-Id`).
- Tests: `tests/test_werkgebied_intake.py` en `tests/test_werkgebied_context.py`.

### De bronselectie per deelvraag (`agent/bronselectie.py`, `nodes/bronselectie.py`, spoor J)

"Help mij de bronnen bij dit werkgebied te bepalen" laat Lex de deelvragen één voor één afwerken met
vraagkaarten: eerst, als die nog leeg is, de gebeurtenis (`bs_gebeurtenis`, zie hieronder), dan kiezen (`bs_kies`), de kernbepalingen (`bs_bepalingen`), wat eraan hangt
(`bs_afhankelijkheden`), afronden (`bs_afronden`) en *Hoe wil je verder?* (`bs_verder`). Een eigen worker
onder de supervisor, naast de intake; zie `docs/architectuur/bronselectie-per-deelvraag.md`.

- **Een treffer bij een deelvraag is een kernbepaling van die deelvraag** (4 nov 2026), ook als er elders al bronnen
  zijn opgenomen (`bronnen_vinden._deelvraag`; voorheen `aanverwant`, buiten het kernkaartje). Het kernkaartje telt
  de bronnen van de deelvraag met de rol van de fase (`_telling`), dus geen "geen kernbepalingen" naast een gevuld paneel.
- **Zelf bepalingen noemen is een voorstel** (4 nov 2026, één lijn met de voorstellen van Lex): de actie
  `bepaling_toevoegen` (suggestie *Noem een bepaling* bij werkgebied en deelvraag, in `BRONSELECTIE_ACTIES`) en de
  regels op het compacte kaartje komen uit bij `noem`. `bs_toevoegen` vraagt zo nodig bij welke deelvraag, daarna
  één bepaling per regel (`meer_tekst`, `regel: REGEL_BEPALING`). `bepaling_treffers` ontleedt elke regel
  (`bepalingen_uit_tekst`) en zoekt haar via de api in de echte boom (`zoek_bepalingen`); elke treffer gaat als
  voorstel bij de deelvraag (`api.noem_voorstel` → api `POST …/voorstellen`, bewijs `genoemd`; rol `kern`, of
  `afhankelijkheid` bij ‘als context’ of in die fase). Daarna het compacte kaartje van de deelvraag (`_kaart_hier`,
  zonder zoekronde): de analist leest en besluit in het paneel. Lukte niets, dan staat het noemkaartje er weer met
  de regels en de reden. Geen treffer-kaartje en geen zoekvenster op het artefact.

- **De stand staat bij de api, niet in de state** (`GET …/bronselectie`, api §*Bronselectie per deelvraag*):
  elke beurt leest hem vers. Hervatten (herladen, ander gesprek, collega) is dus `start` op de stand van nu;
  een tussenvraag raakt hem niet. De node schrijft niets in `State`.
- **Routering zonder model**: een klik met `intake_id` `bs-<werkgebied>` (de intake heeft een uuid-hex), de
  actie `bronselectie` (`models.BRONSELECTIE_ACTIES`, geen taak van een agent), of de vaste zin
  (`is_bronselectievraag`, met werkgebied) – die gaat vóór het startzinpatroon van het samenstellen, en dat
  patroon sluit hem uit ("werkgebied … bepalen" nam hem anders over). Getypt kiest de supervisor `werkgebied`
  met `TAAK: bronselectie` – ook voor "zoek bepalingen bij deelvraag 2": de losse zoekknop is weg, en de actie
  `bronnen_zoeken` gaat naar de bronselectie. Een deelvraag aangewezen in de werkplek (`onderwerp`) of genoemd ("deelvraag 4",
  `deelvraag_nr_in`) gaat voor.
- **Het kaartje van de bepalingen is compact** (`kaart_bepalingen`, `weergave: paneel`, besluit gebruiker 3 nov 2026):
  geen vinkjes, wel de telling (`samenvatting: {kandidaten, opgenomen}`). Beslissen gebeurt in het paneel naast het
  gesprek, dat de api rechtstreeks aanroept. **`actie: klaar`** raakt geen besluit en schuift alleen de fase door;
  wat dan onbeslist is, is niet gekozen. Een getypte bepaling raakt de besluiten ook niet, en het kaartje blijft
  staan tot *Klaar*. Keuzes op een bepalingenkaartje (een oud kaartje met vinkjes) beslissen niets meer.
- **Een klik wordt een stap** (`verwerk`); er is geen *later*. **Eigen tekst op een bepalingenkaartje is een bepaling die de analist zelf
  toevoegt** (`bepalingen_uit_tekst`: artikel en lid uit de tekst, de regeling uit de tekst via
  `overzicht.regelingen_in_vraag` of – als het werkgebied er één heeft – uit het werkgebied; dan
  `GET …/bepalingen` voor de treffers en `POST …/bronselectie/{d}/voorstellen`, zodat ze in het paneel staat). Geen artikel, geen eenduidige regeling of een onbekende bepaling: een zin
  en hetzelfde kaartje. Eigen tekst op het afrondkaartje is een onderzoekspunt. Iets toevoegen kan later altijd
  door de vragen opnieuw te doorlopen (*Bepaal de bronnen bij deze deelvraag*, *verder onderzoeken*). Alles is
  idempotent bij de api, dus een dubbele klik wordt verwerkt op de stand van nu. Een 412
  geeft het kaartje van nu met "Iemand anders werkte intussen …".
- **Zoeken** is `bronnen_run.zoek_run` (zonder model) wanneer er nog niet, of op een andere stand van het
  werkgebied (selectie, dossier), gezocht is; na het opnemen dus opnieuw, voor de afhankelijkheden. `start` zoekt
  eerst opnieuw als de stand verouderd is, ook als alle deelvragen al af waren: pas daarna weet de api welke
  afronding door de nieuwe voorstellen weer open staat. Een lege fase slaat Lex over met een zin.
- **Uit code, niet van het model**: `beperkingen` (afgekapt, mislukt, verouderd), `controle_tekst` (zoek-,
  juridische en beoordelingsdekking apart, met `SLOT` alleen als alles beoordeeld is – nooit "volledig").
- **Uit gaan** `token`, `vraagkaart` (`modus: "bronselectie"`, `deelvraag_id`) en het artefact
  `{soort: "bronselectie", ref: {werkgebied_id, deelvraag_id?}}`. `tests/test_contract_drift.py` toetst de stappen
  tegen api en werkplek.
- **De gebeurtenis en de grondslag** (`agent/zoekvragen.py`, zoekvragen a–d, skill
  `references/zoekvragen-bronselectie.md`, plan `~/.claude/plans/zoekvragen-bronselectie.md` PR 3). Het zoeken op de
  woorden van de analist mist de wet ("de schuld laten vervallen" tegen "kwijtschelding", meetlogboek
  `bronselectie-2026-11-04-dossier`); de wet ordent zich naar haar gebeurtenissen.
  - `gebeurtenis_opties`, zonder model: de dossiertermen (met de naam) in de index, elke treffer naar de koppen erboven
    (`plaats_in_opbouw`; bij een beleidsregel alleen de hoofddivisie), per kop een idf-gewicht, uit de kop de
    gebeurtenissen (`kop_gebeurtenissen`: na het nummer, zonder "Algemene bepalingen over", geknipt op komma en "en",
    hoogstens `MAX_WOORDEN`). Wat het dossier letterlijk noemt (`genoemd_in`: het woord zelf, geen gedeelde stam) gaat
    voor.
  - `bs_gebeurtenis` (`kaart_gebeurtenis`): gevraagd als het werkgebied nog geen gebeurtenis heeft en de analist nog
    niet begon, of als de vraag het woord noemt (*Vraag Lex* bij het lege veld). Kiezen of typen is een `PATCH` van
    het werkgebied (met de revisie); daarmee verandert de invoer van de bronnenrun en zoekt Lex opnieuw. Overslaan
    slaat niets op. De node geeft `stel_voor` mee (zonder graaf geen voorstel, en dan geen kaartje).
  - `grondslag`: één zin noemt de gebeurtenis (woordbegin, `_raakt_woord`: "vallen" raakt "gevallen" niet) én draagt
    een signaal van bestaansrecht (`BESTAANSRECHT`; een zin die met "Geen" begint beperkt, zoekvraag b). Geen
    beleidsregel. Weg als de tekst méér raakt aan wat buiten de afbakening valt dan aan de gebeurtenis (zoals
    `bepaling_opties`; de afbakening noemt de gebeurtenis vaak zelf). Eerst de bepalingen onder een kop met de
    gebeurtenis, in documentvolgorde, dan de rest; om de beurt per regeling (`om_de_beurt`).
  - `pool` (PR 4, nog niet in de bronnenrun – de deelvragen rangschikken erbinnen in PR 5): vanaf de grondslag de
    **omgeving** (de delen van een wet of lagere regeling waarvan de kop de gebeurtenis draagt, `zoek_opbouw`) met per
    lid de zoekvraag uit de tekst (`zoekvraag_van`: c gevolg vóór d invulling vóór b voorwaarde/procedure/tijd – de
    laatste uit de JAS-regels voor voorwaarde en tijd), en d buiten de wet (de subdivisies van de beleidsregel bij de
    gebeurtenis of die naar de grondslag verwijst, `q_subdivisies`; de definities van termen in a–c,
    `bronnen_vinden.definities_in`). `genoemd_in` telt ook een vervoeging met een lange stam ("uitbetaald" →
    uitbetaling; het begin groeit mee met de stam, zodat "belasti" de belastingrente niet noemt).
  - **De deelvraag kiest in de pool** (PR 5, `opties_bij_deelvraag`, in `bronnen_vinden._deelvraag` zodra er een
    gebeurtenis is): de vraagvorm wijst de zoekvraag aan (`VRAAGVORM`: "onder welke voorwaarden" b, "wat kan iemand
    doen als" c, "wat is een" d, "wie kan" a); de woorden van die vorm (`METHODEWOORDEN`) en lege woorden
    (`LEGE_WOORDEN`) zoeken niet mee. Een woord weegt naar zijn zeldzaamheid in de pool (idf), de passende zoekvraag
    telt als het sterkste woord, en bij gelijke stand gaat wie de gebeurtenis noemt voor. Het zoeken op de woorden
    (`bepaling_opties`) vult alleen aan als de pool te weinig geeft (`PLAATSEN_WOORDEN = 0`: vaste plaatsen hielpen
    niet). Zonder gekozen regelingen zijn de regelingen waarvan een kop de gebeurtenis draagt het bereik
    (`regelingen_van_gebeurtenis`), niet de hele graaf. Een uitsluitstam die in de helft van de omgeving staat, telt
    niet ("belastin"). Recall nodig per deelvraag (eval-route `zoekvragen (PR 5)`): 0,10 → 0,29, 0,22 → 0,44,
    0,36 → 0,46, bezwaar 0,53 → 0,40.
  - **De woordenkloof** (PR 6): staat een woord van de deelvraag in geen kandidaat ("rekeningafspraak"), dan zoeken
    de woorden die het dossier er in dezelfde zin naast zet in zijn plaats (`brugtermen`, samen zo zwaar als één
    woord). `gebeurtenis_opties` weegt de dossiervelden (`VELDGEWICHT`: de gekozen gebeurtenis 3, naam en
    analysevraag 2, het praktijkvoorbeeld 0,5); staat de gekozen gebeurtenis in geen kop (een voorwerp,
    "bankrekening"), dan gaan de handelingen voor waaronder de bepalingen met het woord vallen (`onder_voorwerp`).
    `genoemd_in` eist bij een woordgroep elk inhoudswoord ("uitvoeren" noemt "uitvoering overheidsvordering" niet).
    In het gesprek (`bronselectie`, via de `toets` van de node en de `ContextVar` `_TOETS`): een eigen woord dat in
    geen regeling staat (`ontbrekende_woorden`) noemt Lex bij de start en bij een deelvraag zonder kernbepalingen,
    met de brugtermen; een voorwerp als gebeurtenis (`is_voorwerp`) laat het gebeurteniskaartje terugkomen, ook na
    het begin.
  - **De zoekversie** (`bronnen_run.ZOEKVERSIE`): een hash van `bronnen_vinden`, `deelvraag_zoeken`, `zoekvragen` en
    `zoektermen`, meegestuurd bij `start_bronnen_run`. Meldt de zoekdekking een andere versie, dan zoekt de
    bronselectie opnieuw bij het hervatten. Zonder dat bleef op acceptatie de uitkomst van de oude code staan.
  - Meten: `uv run python -m eval.bronselectie_eval --zoekvragen --set <set>` (de plek van de gebeurtenis van de set,
    met en zonder naam, en de recall van de grondslag op `zoekvraag: a`). Ontwikkelset kwijtschelding: plek 1 / 3,
    recall 0,67, precisie 0,25. Een brede gebeurtenis ("aansprakelijkheid") vult de grondslag met een heel
    hoofdstuk; de blinde meting (`verrekening-concept`) komt in PR 7.
- Tests: `tests/test_bronselectie.py` (de cyclus met vier deelvragen, hervatten, de vaste zin, de beurt, de
  gebeurtenis) en `tests/test_zoekvragen.py` (koppen, signalen, de voorstellen en de grondslag tegen een nepgraaf).

### Het werkgebied als context in het gesprek (`agent/werkgebied_context.py`)

Draagt een beurt een `werkgebied_id`, dan haalt `answer_stream` het werkgebied bij de api
(`_werkgebied_blok`, per beurt vers) en zet `als_blok` het in `State.werkgebied_context`;
`memory_context` geeft het naast de focus aan de supervisor en elke specialist – ook met
`Settings.enable_memory_context` uit (een veld zonder env-variabele, dus alleen in tests uit te zetten). Context, geen filter; zonder api of bij een storing leeg. Dezelfde
`context_tekst` voedt de intake en de deelvragenrun. De bronnenrun krijgt het dossier in zijn
invoer (`invoer.dossier`, api); alleen de methode `deelvraag` leest het, en dan voor de rangschikking en het
weglaten van wat buiten de afbakening valt. Meer vraagt eerst een meting (PLAN spoor F, *Vervolg*).

### Vraag Lex op een object (`agent/onderwerp.py`, F3b)

Vanuit een deelvraag, bronselectie, kandidaat, begrip of het werkgebied leidt één *Vraag Lex* naar het
gesprek, en ook vanuit een **bepaling** (`bron_iri`) of een **stuk uit een bronconnector** (`connector`, `stuk_id`),
die geen werkgebied nodig hebben (ontdubbelen PR 5). Voor die twee haalt `onderwerp.haal` niets bij de api: het blok
noemt wélk object het is, en Lex haalt de tekst zelf met zijn tools. Een actie op een bepaling zonder werkgebied
blijft een fout (geen werkgebied om in te werken). Het verzoek draagt alleen `onderwerp: {soort, werkgebied_id, id?, label?}` (`models.Onderwerp`);
`answer_stream` haalt het object per beurt bij de api (`onderwerp.haal`: het werkgebied, de dekking, de
kandidaten, het begrip met zijn open kaartvoorstellen) en zet het blok in `State.onderwerp_context`.
`memory_context` geeft het vóór het werkgebiedblok aan supervisor en elke specialist, ook met
`Settings.enable_memory_context` uit.

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
  `werkgebied_annoteren` zet een modus (de reeks).
- Tests: `tests/test_onderwerp.py` (contract, blok per soort tegen een nep-api, focus, de beurt, de
  api-routes uit de bron).

### De agents onder de supervisor (`agent/agents/`, `nodes/agent_taak.py`, F3c, ADR-005)

Naast `antwoord`, `annotatie` en `werkgebied` (met `TAAK: aanvullen` het dossier aanvullen, zie hierboven)
kiest de supervisor **`deelvragen`** en **`begrippen`**, met een `TAAK:`-regel uit een vaste lijst
(`agents/register.py`; `parse_taak`). De tekstpatronen die vroeger
harde routes vóór de supervisor kozen (`is_bronnenvraag`, `is_begrippenvraag`, `is_kaartvraag`,
`is_verdiepvraag`, `is_werkgebied_annoteervraag`) zijn **weg**: getypte tekst gaat altijd langs de
supervisor. `_stroom_voor` kent alleen nog `intake_actie`, het werkgebied annoteren als modus/actie (de
reeks) en `doelen`.

- **Kiest het model een agent, dan wint die keuze van de harde regels op de herschreven vraag**
  (leesvraag, begrippen lezen, overzicht); alleen een leesvraag in de oorspronkelijke tekst gaat voor. Het
  herschrijven van een vervolgvraag ("…gedekt door de annotaties?") zette de keuze anders om (eval 21 okt 2026).
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
  vraag of 2–4, anders `geen`) landen als voorstel bij de api – een verbetering met `vervangt` (F3d), zodat
  overnemen de oude deelvraag vervangt; `dekking` per actieve
  deelvraag uit de api (stand, bronnen met rol, open kandidaten).
- **Het artefact volgt het object** (F3d): een taak op één deelvraag (`verbeteren`, en `dekking` met een
  deelvraag) levert `{soort: "deelvraag", ref: {werkgebied_id, deelvraag_id}}`
  (`beurt.deelvraag_artefact`); zonder deelvraag het werkgebiedartefact. Een taak op één
  begrip levert `{soort: "begrip", ref: {werkgebied_id, begrip_id, kaart_run_id?, actie?}}`
  (`kaart_beurt.begrip_artefact`). De systeemtekst draagt de skillrol
  `deelvragen` (`deelvragen.systeem`), ook in de intake.
- **De begrippen-agent** (`agents/begrippen.py`): `voorstellen` (`begrippen_beurt.begrippen_kern`),
  `meedenken` (`begrippen_verdieping.verdieping_kern`; zonder `bevestigd` het voorstel met bevestiging),
  de vijf kaartacties (`kaart_beurt.kaart_kern`, dezelfde kaart-run als de knop), `uitwerken`
  (brondefinitie → zonder definitie een definitievoorstel → op een overgenomen definitie de uitleg in B1, als
  die er nog niet is, en voorbeelden; daarna zegt Lex wat er nog open is) – en na elke losse kaartactie noemt Lex het volgende logische stuk
  (`kaart_beurt.VOLGENDE`: definitie → uitleg → voorbeelden → relaties)
  en `relaties` (`GET …/relaties`, zonder model). Het begrip komt van het onderwerp (`als_rij`) of uit de
  term (`los_op`, zie *Welk begrip*). Geen skillrol: de regels voor begrippen staan in de keten en de toetsen, en
  `references/begrippen.md` is methode-uitleg (besluit 7 nov 2026).
- **Welk begrip** (`agents/begrippen._begrippen`, `kaart_beurt`). De termen komen uit de woorden van de analist, alleen
  zonder termen uit de herschreven vraag (`register.parameters`: `herschreven`): een herschrijving voegde een begrip toe
  dat niemand noemde (e2e 5 nov 2026). Noemt de vraag twee begrippen, dan wint de vraag van het onderwerp; het onderwerp
  vult alleen aan wat ontbreekt, en is nooit zijn eigen vergelijking (`zonder`). Geen exacte naam: `naaste` (de kern van
  de naam, zonder haakje, in de term of andersom; de meeste gedeelde woorden). Meer dan één: de **keuzekaart**
  (`keuzekaart`, `modus: "begrip"`, stap `begrip_kiezen`, `intake_id` `bk-<werkgebied>`; `Uitkomst.vraagkaart`). De klik
  draagt taak en id's in de `waarde` (`uit_keuze`) en gaat zonder model terug naar de taak (`_begrip_keuze` in
  `nodes/supervisie.py`). Een term die niets oplevert, wordt een zin, nooit het onderwerp. Bij een vergelijking noemt elke
  tekst beide begrippen (`samenvatting`, `melding`).
- **De annotatie-agent** heeft twee taken hier: `werkgebied` en `deelvragen` (alleen de bronnen onder de
  deelvragen, of onder één; `werkgebied_annotatie.werkgebied_voorstel`), het voorstel met de bevestiging. Met `bevestigd` blijft het de eigen reeks, want die draait per bepaling een
  gewone beurt.
- **Uitvoering**: `agent_taak` draait de async agent op de event loop van de beurt
  (`agents/uitvoering.draai`, `Bouw.loop`), events via een thread-veilige wachtrij; stoppen via
  `Context.gestopt`. Hij emit `status`, de tekst als `token`, en `artefact`/`bevestiging`; de beurt-driver
  legt die op het bericht en het `opgeslagen`-event. Een storing wordt een zin in het gesprek
  (`STORING`), zonder api `ZONDER_API`. Een onbekende taak: Lex vraagt wat hij moet doen.
- **Kaartacties en verdieping boeken zelf** (eigen run bij de api); `voorstellen`/`verbeteren` van de
  deelvragen gebruiken het model van de beurt en tellen mee in het verbruik van de beurt.
- **De eigen endpoints zijn weg** (F3e): `/v1/bronnen-runs`, `/v1/begrippen-runs`, `/v1/kaart-runs` en
  `/v1/deelvragen-runs` gebruikte alleen de werkgebiedpagina, die Lex nu in het gesprek vraagt.
  `tests/test_deelvragen.py` bewaakt dat ze niet terugkomen. De stromen erachter (`bronnen_stroom`,
  `begrippen_stroom`, `kaart_stroom`) blijven: de agents gebruiken ze.
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
  lege lijst (`begrens_begrippen_antwoord`). **Nul treffers is geen bewijs**: het resultaat draagt `geen_treffers` (wat
  er gezocht is, en hoeveel begrippen er wél liggen), en die zin vervangt het antwoord als de beurt verder niets las
  (`alleen_begrippen_gezocht`, ook buiten de leesroute). De e2e-test van 5 nov 2026 gaf 0 bij 21 concepten: de projectie
  klopte (status `ok`, geen achterstand) en concepten staan erin, dus het lag aan de argumenten van het model. Elk woord
  moet nu ergens staan, niet alles in één veld (de regel van de api); vulwoorden en meervoud zoeken niet (`_woorden`),
  en `werkgebied_id` mag de naam zijn (`dct:title` van het kader). De argumenten staan voortaan in `tool_execution.filters`.
  Een rij met `herbeoordelen` (geaccordeerd, maar een dragende
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
  al, dan wacht Lex. De uitkomst draagt een begripartefact (`soort: "begrip"`, F3d) met
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
5. **Uitgangen:** een `overzicht`-event (de werkplek toont het als kaartje met paneel en bewaart het in
   `Bericht.overzicht`); de samenvatting als `answer` (`finalize_node` stuurt de `token`) en assistent-bericht na het
   `tool_use`/`tool_result`-paar (`voor_model`, voor vervolgvragen); in de `source_trace` de
   vindplaatsen (`bronrijen`). Route `overzicht_bouwen → verify → finalize`; `route_after_verify` gaat
   met een overzicht nooit naar een correctieronde (die zou het model alsnog laten schrijven).
6. **Bronnen en controle uit het overzicht:** `finalize_node` neemt de bronnen uit het overzicht;
   `check_grounding(..., overzicht=)` toetst elk genoemd artikel én deel ("Hoofdstuk II", "Titel 5.4")
   tegen het overzicht, inclusief de bovenliggende delen (`opbouw`).
7. **Geen sjabloon (ADR-008):** de route heeft niets wat een sjabloon oplost. Er typt geen model feiten
   over, en `state["overzicht"]` blijft nodig voor de controle en de route. Een `Antwoord` zou alleen
   een tweede drager van dezelfde gegevens zijn.

De tool `overzicht_onderwerp` (`_h_overzicht`) bouwt met dezelfde code een overzicht buiten de route (MCP,
vrije vragen) en pagineert per deel binnen de begroting. Onderwerp en afbakening kiest dan de aanroeper.
Punt 5 en 6 gelden daar **niet**: de tool levert alleen `voor_model`, dus geen `overzicht`-event en geen
kaartje, en `state["overzicht"]` blijft leeg. De controle en de bronnen zijn dan die van een gewoon
antwoord. Bouwt het overzicht niet (graaf weg), dan krijgt het model een foutresultaat en zegt het dat;
de werkplek toont dan geen kaartje. `tests/test_overzicht.py` legt herkenning, samenstelling, volgorde,
de route en de eval-scorer vast.

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
   feit. Die begrenzing vangt het vrije antwoord; het sjabloon `antwoord_annotaties` (`sjablonen/annotaties.py`) gaat er niet
   langs en gebruikt dezelfde meldingen: een storing of nul treffers is een `leemte` en de toelichting van het model vervalt.
   Getoond wordt de laatste zoekopdracht (pagina's voegen samen); `volledig` is ook onwaar bij een `volgende_offset`, want
   de api zet `volledig` alleen op de dekking van de projectie, niet op de paginering. `begrens_begrippen_antwoord` en
   `antwoord_begrip` delen zo `begrippen_stand`.

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
niets, een onterechte kost het antwoord. **Een bron naast de wet is binnen scope** (ADR-013): `SUPERVISOR_SYSTEM`
noemt elke bekende connector uit de beschrijving (`_scope_bronnen`), en de code draait een AFWIJZEN terug als de vraag een
connector raakt (`bronmodel.connectors.herkende`). Gaat de vraag alleen over bronnen die in deze beurt uit staan (en noemt
ze geen artikel), dan zegt Lex zonder model waarom en wie ze aanzet (`_bron_uit`, `bronstand.melding_uit`; route
`bron_uit`, met een `bron_uit`-event waarmee de werkplek *Zet aan* aanbiedt). **Noemt de vraag een stuk bij id** van een
connector die aanstaat (`connectors.genoemde_stukken`, ook in een citeervorm van de beschrijving: "Kamerstuk 32140, nr.
342" → `kst-32140-342`, dat de leestool bij de bron oplost), dan leest de code het vooraf (`_te_lezen`,
`nodes/bron_lezen.py`, de `leestool` met `lees_argument`; een kort stuk, hoogstens `MAX_RIJEN_KORT` rijen en `MAX_PAGINAS`
pagina's, helemaal, ongefilterd: anders bladerde het model met één ronde per pagina, ronde 2 bekendmakingen B21; in het spoor één regel per stuk, `spoorbronnen.voorleesregel`, in plaats van "deels gelezen" per pagina); zonder artikel in de vraag zonder supervisorcall. **Een
lijstvraag** ("geef de 10 meest recente Kamerstukken", "de laatste vijf moties van de Eerste Kamer", ook zonder volgorde
"Kamerstukken uit vergaderjaar 2025-2026 over invorderingsrente": dan kiest de zoektool, en een orgaan als "Eerste Kamer"
is nooit een volgorde) leest `agent/bron_lijst.py` helemaal in code – volgorde, aantal, dossier, soort (`ConnectorBeschrijving.soorten`), periode,
vergaderjaar, Kamer (`organen`) en een onderwerp van hoogstens vier woorden ("over …") als `tekst` – en dan zoekt
`nodes/bron_lijst.py` één keer, zonder model, met het blok `stukken` (leeg: een leemte met de zoekvraag; een fout: de
agent). Periodes: "uit/van/in 2018", "sinds 2011", "uit 2023 en 2024", "2023-2024", "tussen 2020 en 2022"; "hoeveel …" is
een lijstvraag (het blok zegt "N van de M stukken"). Blijft er een woord **of getal** over dat de code niet plaatst, of
vraagt de vraag naar de inhoud, dan geen route: een getal telde eerst niet mee, en dan viel een jaartal stil weg (meting
bekendmakingen B11, 10 nov 2026). Ook in een
gesprek vóór het model, en daarna op de herschreven vraag. `tests/test_bron_lijst.py`, `eval/golden_routering.jsonl`. Een vraag over een bron naast de wet start
nooit een werkgebied (het model koos dat in een lang gesprek). In de bronnenlijst staat een bron naast de wet alleen als ze
gelezen en genoemd is (`grounding.alleen_gelezen_extern`). `GET /v1/bronnen` zegt per connector of de
straat hem aanbiedt; de BFF (`/api/connectors`) toont in het menu alleen wat straat én register aanzetten. **`GET /v1/bronnen/{connector}/stukken/{id}`**
(het bronvenster van de werkplek, PR 6) leest één stuk voor de jurist: de connector is een naam of een brontype, de
leestool en haar argument komen uit de beschrijving (geen code per connector), de adaptercache wordt gedeeld met Lex,
`offset` volgt het `vervolg`, `tabel` opent een tabel. Het antwoord is `{connector: {naam, label, groep, brontype,
id_prefixen, metadata[{sleutel, label}]}, resultaat: <leesresultaat>}`; 404 als de straat de connector niet aanbiedt, 422
bij een id dat niet bij de connector hoort. De schakelaar per gesprek telt hier niet: die gaat over wat Lex gebruikt. De vlag hoort in de per-beurt-reset van `answer_stream`,
anders wijst één afgewezen vraag de hele thread af. De workerlijst is een **allowlist**
(`antwoord`/`annotatie`/`werkgebied`/`deelvragen`/`begrippen`; de laatste drie staan altijd alleen) met een cap van twee: een onbekende naam zou anders een extra antwoord-worker
worden.

**Advies bij twijfel** (`modus: "advies"`, op `/v1/runs`): de supervisor routeert hard naar
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
  gelijktijdig met de werkplek (de run-events). **`reason` = het denkproces, `token` =
  alléén het eindantwoord, na de controle** – houd ze gescheiden. `waarschuwing` heeft één afzender: een gedegradeerde taalanalyse
  (`nodes/annotatie.py`). De beurt slaagde; dat is iets anders dan `error`. `error` draagt `soort` (de exception-naam) naast de
  gesaniteerde melding, zodat de eval een providerstoring van een inhoudelijke fout onderscheidt.
- **De keten meldt zich per fase, met duur, in één idioom: `Actor · wat er gebeurde`.** Alle
  statusregels lopen via `narratie._stap(writer, actor, bericht)`; een test bewaakt de vorm. De
  annotatiefasen komen uit `analyseer` via zijn `melding`-callback (`Taalanalyse` / `Detectie` /
  `Besluit` / `Classificatie` / `Review` / `Resultaat`), met `(0,4 s)` in de tekst en `duur_ms` op het
  event – de tekst reist als `denk` mee naar het chatbericht en is zo na herladen nog te zien. De
  antwoordroute meldt `Controle · …`, `Correctie · …`, `Synthese · …`, `Klaar · N bronnen`; de
  LLM-narratie zelf blijft `reason`. Na een toolaanroep volgt zo nodig een resultaatregel met de bron als actor
  (`Kamerstukken · 16 gevonden`), met `bron` als eigen veld op het event (`agent/spoorbronnen.py`).
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
cd tools/graph-qa && .venv/bin/python eval/run_eval.py --herscoor run.jsonl    # bewaarde run opnieuw scoren, gratis
```

- **`tests/fakes.py`** levert `FakeLLM` / `FakeGraph` / `make_settings`. `FakeLLM` speelt een vaste reeks
  Anthropic-responses af via `create()` én `stream()` (gedeelde index); bouw multi-turn-scenario's met
  `response([text_block(...), tool_block(...)], stop_reason)`. `make_settings` zet de checkpointer
  in-memory en `CLASSIFIER_PARALLEL` op 1.
- **Vraagtype, bewaren en herscoren.** Elke case in `eval/golden.jsonl` en elke beurt in `eval/golden_gesprek.jsonl`
  draagt een `vraagtype` uit de vaste lijst in `eval/vraagtypen.py` (een gesprek mag een default geven; een
  onbekend of ontbrekend type laat `tests/test_eval_kwaliteit.py` falen). Het rapport toont per type aantal,
  slagingspercentage en toonovertredingen. `volgorde` en `sjabloon` in een case tellen mee voor slagen; de toon
  (`eval/kwaliteit.py`: emoji, koppen, u-vorm, interne termen, lange zinnen in de lopende tekst) bewust niet.
  `--bewaar run.jsonl` schrijft per case/beurt de events die de scorers lezen, `--herscoor run.jsonl` scoort ze
  opnieuw zonder agent of model (`eval/opname.py`). Een nieuwe scorer leest dus alleen uit de opname, anders is
  hij niet te herscoren.
- **De retrieval-smoke heeft bewust géén offline-variant.** Hij raakt elke graaftool één keer tegen de
  échte graaf en meldt een lege uitkomst waar data hoort – precies wat een `FakeGraph` niet kan meten.
  `_wacht_op_graaf` stopt bij drie identieke fouten in plaats van het wachtbudget leeg te draaien: een
  fout die niet door wachten overgaat (zoals een ontbrekende handshake) mag niet als "graaf nog niet
  gereed" lezen.

**Live meten gaat via de eval-job, niet vanaf je machine.** `run_eval.py` draait de agent in-proces en
heeft een directe graafverbinding nodig, en GraphDB staat op Azure op `external: false`. Draai
`azure-infra.yml` → actie **`eval`** (per straat): de retrieval-smoke en daarna `--annotatie` en `--gesprek`
elk **drie keer**, met het rapport in de workflow-samenvatting. Met de invoer `eval_set` (`gesprek`, `annotatie` of
`concept`) draait alleen die set: goedkoper als je één ding hermeet. `concept` zijn de bepalingen uit
`docs/wetsanalyse/referentieset/concept/`, met per klasse wat er gedekt is, en zonder schrijfactie op de lagen. Drie, omdat dezelfde bepaling tussen runs sterk
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
  gespreksgeheugen en run-register in Postgres (`CHECKPOINT_DB_URL_FILE`); `SIMILARITY_INDEX=bwb_similarity`.
  `tests/test_deploy_drift.py` bewaakt dat de bicep `WETSANALYSE_API_URL`/`_TOKEN`
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
