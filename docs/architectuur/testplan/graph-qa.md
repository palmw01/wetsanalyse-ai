# Testplan graph-qa: inventaris en nulmeting

Soort: *nulmeting* (16 nov 2026), op master `01067e70`. Dit is een deel van het testplan van Lex Bench
([plan-lex-bench.md](../plan-lex-bench.md), PR #1632). Er is niets gebouwd en niets verwijderd. Vier sessies inventariseren
elk één laag: graph-qa (dit stuk), api, frontend, en keten/E2E.

## Samenvatting

- **De suite is groot en snel.** Er zijn 267 testbestanden met 3.179 testfuncties. Met de parametrisering worden dat 6.394
  verzamelde tests en 50.384 regels. Alles draait zonder netwerk en zonder model. In de poort duurt het 3 tot 7 minuten
  over twee shards.
- **De meeste tests toetsen gedrag**, via de echte LangGraph met een gescript model (`FakeLLM`) en een nepgraaf. Een
  kleiner deel toetst alleen de vorm (vooral de groep *Methode, skills en catalogus*, plus de drift-guards in andere
  groepen): drift-guards, registers, de catalogus en de byte-voor-byte modelverzoeken. Dat is
  bewust, en goed.
- **Een volgordefout is gevonden en verklaard** (§4.2). `test_sjablonen.py::test_een_beurt_rondt_af_met_de_wettekst_uit_de_graaf`
  is alleen groen omdat de procesbrede cache `overzicht._REGELINGEN_CACHE` leeg is. Daardoor staat de controle
  `id_herkomst` (GOK) uit. Na `test_eval.py` staat de Invorderingswet in de cache. Dan weigert de controle het id, zoals in
  productie, en is het script van het model op. De poort is alleen groen omdat de shardverdeling de twee bestanden
  toevallig scheidt. Een volle lokale run is rood.
- **De structuur volgt de geschiedenis, niet het systeem.** 21 bestanden (164 tests) heten naar een meting of bundel
  (`test_a6_run2`, `test_d01_bundel122`, `test_c_begrensd` …). Het gedrag van een subagent staat verspreid over zo'n twintig
  bestanden. De tests zijn waardevol, maar je vindt niet waar een mechanisme getoetst wordt.
- **De foutpaden zijn goed gedekt waar ze ooit misgingen**, en dun waar dat nog niet gebeurde. Er is geen test voor
  prompt-injectie via de inhoud van een bron. Er is geen offline test voor een time-out van de graaf of van een connector.
  Er is geen beurt die een 400 van een strict schema krijgt. De stabiliteit over runs wordt alleen live gemeten.
- **De nepdiensten zijn te toegeeflijk.** `FakeGraph(result=…)` geeft op elke query hetzelfde antwoord. `FakeLLM` toetst
  niet of de tool die hij aanroept wel is aangeboden. De volgordefout komt rechtstreeks voort uit het eerste.
- **Evals en tests lopen door elkaar.** `eval/` heeft 13 jsonl-sets en een tiental scripts. Daarnaast staan er
  vragensets in `tests/data/` en referentiesets in `docs/wetsanalyse/`. Een paar evals zijn in feite tests (de
  routeringsset), en een paar tests zijn in feite evals: de pinnen op de gemeten uitkomst in `test_bronselectie_eval.py`,
  ook die van de held-out sets.
- **Voorstel in het kort** (§6): eerst de volgordefout en de cachereset, dan een injectietest en strengere fakes. Daarna
  een indeling per mechanisme in plaats van per bundel. Breng de evals onder in één manifest van Lex Bench, met drie
  niveaus: test, offline replay en live.

## 0. Hoe gemeten

- **Tellingen.** Testfuncties met de AST, en verzamelde tests met `pytest --collect-only` (6.394). De regels per bestand
  komen uit `wc`. Per groep staan beide aantallen, omdat parametrisering de verhouding sterk verschuift (de catalogus: 126
  functies, 968 tests).
- **Wat een test toetst.** Per bestand gelezen: de docstring en de namen van de tests. Steekproeven tot op de code waar
  het oordeel ertoe deed (fakes, de volgordefout, de foutpaden). Ik heb niet elke test regel voor regel gelezen. Een oordeel
  *gedrag* of *vorm* geldt dus per groep, niet per test.
- **Doorlooptijd.** De duur per bestand komt uit `scripts/pytest_shard_duur.json` (252 s over 194 bestanden). De duur per
  shard komt uit de laatste geslaagde runs van `poort.yml`.
- **Gericht gedraaid**, één tegelijk: `test_eval.py` met de sjablonentest (de volgordefout), per test uit `test_eval.py`
  (bisectie), een script dat de caches één voor één leegmaakt, en `--collect-only`. Er is geen volle suite gedraaid, geen
  model gebruikt en niets op acceptatie gedaan.

## 1. Inventaris

### 1.1 Per groep

*Tests* is het aantal testfuncties, *verzameld* het aantal na parametrisering. De *duur* komt uit de shardmeting. Een
bestand dat daar niet in staat, telt als *ongemeten*.

| Groep | Bestanden | Tests | Verzameld | Regels | Duur |
|---|---|---|---|---|---|
| Routes en ingang | 21 | 221 | 501 | 3.895 | 2 s (4 ongemeten) |
| Centrale agent en subagents | 21 | 231 | 343 | 3.984 | 2 s (16 ongemeten) |
| Sjablonen en antwoordvorm | 7 | 204 | 236 | 2.272 | 2 s (1 ongemeten) |
| Grounding en verify | 12 | 158 | 288 | 1.834 | 0 s (2 ongemeten) |
| Annotatieketen | 45 | 461 | 1.080 | 7.157 | 35 s (2 ongemeten) |
| Begrippen | 18 | 239 | 370 | 3.449 | 14 s (1 ongemeten) |
| Werkgebied en bronselectie | 7 | 155 | 224 | 3.159 | 3 s (1 ongemeten) |
| Connectors | 22 | 459 | 691 | 6.684 | 20 s (5 ongemeten) |
| Denkproces | 7 | 55 | 102 | 834 | 0 s (3 ongemeten) |
| Contextopbouw en modelstap | 14 | 150 | 211 | 2.766 | 1 s (4 ongemeten) |
| Graaf en toollaag | 14 | 117 | 409 | 2.213 | 92 s |
| MCP-server | 1 | 8 | 8 | 186 | 15 s |
| Runs, beurt en dienst | 14 | 153 | 172 | 2.702 | 22 s (1 ongemeten) |
| Methode, skills en catalogus | 17 | 126 | 968 | 1.605 | 1 s (12 ongemeten) |
| Meetsets per bundel | 21 | 164 | 193 | 3.488 | 21 ongemeten |
| Eval-harnas, sets en referentiesets | 26 | 278 | 598 | 4.156 | 44 s (1 ongemeten) |
| **Totaal** | **267** | **3.179** | **6.394** | **50.384** | **252 s gemeten, 73 bestanden ongemeten** |

De indeling staat in [bijlage A](#bijlage-a-indeling-per-bestand).

### 1.2 Wat de groepen echt toetsen

**Routes en ingang** (gedrag). De ingang kiest een route in code of gaat naar de centrale agent. `test_routering.py`
draait de routeringsset (`eval/golden_routering.jsonl`, 50 rijen) met een model dat faalt zodra het wordt aangeroepen. Dat
is sterk: een route die per ongeluk een modelstap gaat vragen, wordt rood. Daaromheen staan de vaste workflows (D1
`test_bepaling_workflow`, het overzicht, de lijstvraag `test_bron_lijst`, `test_buiten_graaf`), de scope en de methodekeuze.
*Zwak:* `test_specialists.py` heeft een achterhaalde docstring ("De supervisor routeert naar een specialist"), twee hulpjes
die niemand aanroept (`_route_to`, `_agent_tools`) en toetst tekst in de prompt. Ook `test_vervolgvraag`,
`test_advies_en_suggestie` en `test_agents` noemen nog de supervisor, die sinds A7 weg is. `test_routering`,
`test_routering_centraal`, `test_bronroutering` en `test_a7_ingang` overlappen deels: vier ingangen voor één vraag ("waar gaat
deze vraag heen?").

**Centrale agent en subagents** (gedrag, op de echte graaf met `FakeLLM`). Het gaat om de overdracht, het kindgesprek, het
rapport, vragen naar boven en hervatten, de rondegrens en het plafond, de regisseur en het plan. De profielen en de
grenzen van de tools staan in `test_profielregister`, `test_agentprofiel`, `test_toolverdeling`, `test_context_per_agent`
en `test_modelkeuze`. *Versnipperd:* het gedrag van één subagent staat in `test_subagent`, `test_subagenten`,
`test_subagent_route`, `test_subagent_vragen`, `test_subagent_model`, `test_delegatie_afsluiten`, `test_delegatie_na_rapport`,
`test_rapport_en_rondegrens` en `test_vraag_sluit_beurt`. Daar komen nog zes bundelbestanden bij (§1.3). 16 van de 21
bestanden staan niet in de duurmeting.

**Sjablonen en antwoordvorm** (gedrag plus vorm). `test_sjablonen.py` is met 131 tests het grootste bestand. Het toetst
dat de feiten uit de trace komen en niet van het model, de strict schema's, en het afronden. Het is goed opgebouwd. Het
is ook het bestand van de volgordefout (§4.2).

**Grounding en verify** (gedrag). Het gaat om citaten tegen de bron, beweringen in de toelichting, hoeveelheden,
herstel van een bijna-letterlijk citaat, de herkomst van een id (`test_id_herkomst`) en de vindplaatsen. Dit is de kern van
brongetrouwheid, en goed gedekt met positieve en negatieve gevallen.

**Annotatieketen** (gedrag, het best opgebouwde deel). De detectoren hebben elk een positief, een negatief, een rand en
een overlap (ADR-001). Daarnaast staan er de fusie, de validatie, de review en de resolver ("elke transitie uit de
tabel"), de dekking als invariant, en de hele keten op de echte graaf met `KetenLLM`. `KetenLLM` antwoordt op de prompt en
speelt niet blind een reeks af: dat is de beste nepdienst van de suite. *Eval-achtig:* `test_invordering_verbeteringen`
(25 tests, "graafcasussen en gemarkeerde synthetische tegenproeven") en `test_detector_freeze_regressies` zijn
regressies op uitkomsten. Ze zijn waardevol, maar ze horen als vastgezette casussen bij een meetset en niet tussen de
eenheidstests.

**Begrippen** (gedrag). De keten van ADR-004 met beslistabel, patronen, signalen en taal. Daarnaast de verdieping met
het model (`FakeLLM` speelt tool-aanroepen af: het model kiest alleen op id) en de kaartacties. De B1-toetsen staan er met
en zonder parser.

**Werkgebied en bronselectie** (gedrag). `test_werkgebied_intake` (56 tests) toetst de stapmachine, de kaartjes en het
aanmaken. `test_bronselectie` (26) toetst de stand bij de api en het hervatten zonder checkpointer, met het scenario uit de
opdracht. `test_plan_termijnen` toetst de vlaggen van het lopende onderzoek. Dat bestand hoort bij de sessie Termijnen
en blijft hier buiten beschouwing.

**Connectors** (gedrag tegen opnames, plus vorm). Per connector is er een toolsuite tegen een nep of tegen echte
opgenomen antwoorden, een vragenset (30 vragen) die route en argumenten toetst, en een live-proef (`-m live`, dagelijks in
`bronnenwacht.yml`). `test_connectorbeschrijving` maakt een onvolledige beschrijving rood. Dit is een goed patroon: *nep
voor de logica, opname voor het contract, live voor de drift*. `test_kamerstuk_tools` (66) en `test_rechtspraak_tools`
(71) zijn groot maar samenhangend.

**Denkproces** (gedrag). De regels per stap, geen antwoord in het denkproces, een resultaatregel per bron. Daarbij zet
`conftest.py` voor de hele suite `narratie.STRIKT = True`: elke regel die een test laat maken, mag geen lege plek hebben.
Dat is een sterke, generieke invariant.

**Contextopbouw en modelstap** (gedrag plus vorm). `test_modelverzoeken.py` legt elk modelverzoek byte voor byte vast
(13 opnames in `tests/data/modelverzoeken/`). Dat is de regressietest bij een wijziging aan een prompt of skill (§3.6).
Verder staan hier de prompt-caching (prefix-match), het venster en het trimmen, de gedeelde modelstap (stopredenen,
pogingen) en `test_gesprek_blijft_bruikbaar`: stoppen, een crash of een toolfout laat geen `tool_use` zonder `tool_result`
achter. *Dubbel:* `test_trim_messages` (F2) en `test_trimming` toetsen allebei het begrenzen van de historie, uit twee
periodes.

**Graaf en toollaag** (gedrag plus vorm). `test_retrieval_tools` toetst bewust op het resultaat en niet op de querytekst
(de les van `bwb:bevat`). `test_queries` toetst nog grotendeels de querytekst. `test_sparql_syntax` parseert elke bouwer,
`test_predicaat_dekking` en `test_namespace_drift` bewaken de graafvocabulaire, en `test_mcp_guard` het schrijfslot.
`test_resultaatcontract` draait elke tool tegen een slechtst denkbare graaf. Met 88 s is dat een derde van de suite.

**MCP-server** (vorm plus doorgifte). Acht tests: de server is een doorgeefluik over `anthropic_schemas()` en `dispatch()`.
Dat volstaat. 15 s is veel voor acht tests, waarschijnlijk door het starten van een subproces.

**Runs, beurt en dienst** (gedrag). Een run overleeft de kijker. Verder het aanhaken vanaf een `seq`, een 409 bij een
tweede run, stoppen als verzoek, en de Postgres-store met twee replica's (`-m integration`, draait in de poort met een
servicecontainer). De drift-guards naar api en bicep (`test_contract_drift`, `test_deploy_drift`, `test_agent_contracten`)
staan ook hier.

**Methode, skills en catalogus** (vorm). Drift tussen skill en code (`test_methode_drift`, `test_methodepakket`,
`test_bronpakket`, `test_vocabulaire_drift`), de scheiding van de methodes, de validators en de catalogus. Dit is de grens
die de meeste stille breuken vangt. Het toetst geen gedrag van Lex, en dat hoeft ook niet.

**Eval-harnas, sets en referentiesets** (tests óp de meetinstrumenten). Het gaat om scorers, de vorm van de sets, het
adjudicatieprotocol, het beheer van de eval (een storing heet *niet gemeten*), herscoren en de offline end-to-end runs.
`test_bronselectie_eval` (36 s) pint de gemeten uitkomst van de ontwikkelsets *en van de held-out sets* vast (§5.2).

### 1.3 Meetsets per bundel

21 bestanden met 164 tests heten naar de meting waaruit ze kwamen: `test_a4_vervolg`, `test_a6_*` (8), `test_b3_na_subagent`,
`test_b_lezer_beslist`, `test_c_begrensd`, `test_d01_*` (6), `test_e_b2_zoeken`, `test_bundel_elk_rapport` en
`test_controle_citaten`.

- **Wat ze zijn.** Regressietests op gevallen uit een echte meting, met nepbronnen in de echte vorm. Ze lopen door de
  echte toollaag (`get_uitspraak`, `zoek_uitspraken`), met de tekst ingekort tot wat de test nodig heeft. Inhoudelijk zijn
  ze goed: ze toetsen het mechanisme dat de fout oploste, niet de tekst van de meting.
- **Wat er mis is.** De naam zegt wanneer, niet wat. Wie de rondegrens van een subagent wijzigt, moet weten dat
  `test_a6_eind`, `test_c_begrensd`, `test_rapport_en_rondegrens`, `test_delegatie_afsluiten` en `test_a6_run3` er allemaal
  over gaan. Geen van de 21 staat in de duurmeting.
- **Ze zijn geen eval.** Ze gebruiken geen model en scoren niets. Het zijn tests met een herkomst, en die herkomst hoort in
  de docstring. Nu zit ze in de bestandsnaam.

### 1.4 Los, dubbel of verouderd

- **Achterhaald na A7:** `test_specialists.py` (docstring, dode hulpjes, toetsen op prompttekst), en de vermelding van de
  supervisor in `test_vervolgvraag`, `test_advies_en_suggestie`, `test_agents` en `test_annotatie_worker`. De tests kunnen
  wel nog kloppen. De namen en de uitleg misleiden.
- **Dubbel of overlappend:** `test_trim_messages` en `test_trimming`. De vier routeringsbestanden (§1.2). `test_tools`,
  `test_queries` en `test_retrieval_tools` (de toollaag in drie lagen: registry, querytekst, resultaat).
  `test_provenance` en `test_provenance_element` zijn níét dubbel: het eerste gaat over het antwoord, het tweede over een
  annotatie-element.
- **Bewust in lagen, niet dubbel:** `test_runs` (geheugen), `test_run_endpoints` (HTTP) en `test_run_endpoints_gedeeld`
  (Postgres).
- **Toetsen op prompttekst:** 23 asserts in 13 bestanden zoeken een zin van meer dan twaalf tekens in een prompt
  (`assert "begin bij zoek_definitie" in prompt`). Ze breken bij elke herformulering en bewijzen niet dat het model zich
  ernaar gedraagt. `test_modelverzoeken` dekt hetzelfde beter.
- **Zonder eigen assert:** 18 testfuncties. De meeste roepen een hulpje aan dat wel toetst (`_vergelijk` in
  `test_modelverzoeken`, `geval()` in `test_relatievoorstellen`). Echt zonder toets zijn alleen "valt niet om"-tests:
  `test_observability` (2), `test_memory::test_delete_onbekende_conversation_is_idempotent` en
  `test_runstore_postgres::test_setup_is_idempotent`. Dat is legitiem, maar een expliciete assert op de toestand is beter.

## 2. Foutpaden: risicomatrix

*Dekking*: **goed** = het pad is end-to-end getoetst met positief en negatief; **deels** = een onderdeel is getoetst, de
beurt als geheel niet; **dun** = alleen een classificatie of een vorm; **geen**.

| Risico | Dekking | Door welke tests | Oordeel |
|---|---|---|---|
| **Model-400** (ongeldige reeks, te lang) | goed | `test_gesprek_blijft_bruikbaar` (open `tool_use` valt weg, "alleen een echt te lang gesprek heet te lang", een verbindingsfout lekt geen details), `test_prompt_caching` (400 → retry zonder cache), `test_llm_stap::test_een_fout_van_het_model_gaat_naar_de_aanroeper` | De bekende 400's zijn gedekt. |
| **De strict-grens** | deels | `test_strict_grenzen` (de strict schema's van elk profiel passen statisch binnen de API-grenzen; de delegatietools zijn niet strict en de code toetst hun invoer), `test_sjablonen` en `test_centrale_agent` (schema's zijn strict) | Statisch goed. Geen beurt waarin de API een strict grammatica weigert. Gebeurt dat na een profielwijziging toch (de grens verandert aan de kant van de API), dan is het gedrag niet getoetst. |
| **Time-out van het model** | dun | `test_eval_beheersing` (`APITimeoutError` telt als *niet gemeten*), `test_gesprek_blijft_bruikbaar` (overbelasting midden in de stream) | Er is geen beurt met een time-out die toetst dat de historie geldig blijft en de jurist een zin krijgt. Overbelasting is wel gedekt, en loopt via dezelfde weg. |
| **Time-out van de graaf of een connector** | geen (offline) | alleen de live-proeven (`test_*_live.py`) | `test_http_beleid` toetst tijdelijke status-codes, niet een `ReadTimeout`. Een trage MCP-call is niet getoetst. De bekende beperking dat een `run_in_executor`-future niet annuleerbaar is (CLAUDE.md), heeft geen test. |
| **De graaf weg** (`Repository inning doesn't exist`) | goed | `test_tools::test_ontbrekende_repository_krijgt_een_eigen_melding` en `…_wordt_apart_gelogd`, `test_bepaling_workflow`, `test_wetgeving_tools`, `test_eval_beheersing` (smoke wacht en meldt *niet gemeten*), `test_semantic_search_terugval` | Gedekt, ook de terugval van `semantic_search`. |
| **De api 5xx** | goed | `test_api_herhaal` (één herhaling na een 503 bij een ontdubbelde schrijfactie), `test_agents::test_een_storing_van_de_api_is_een_zin_in_het_gesprek`, `test_annotatie_overzicht` (een storing is geen leeg overzicht, ook op een latere pagina), `test_begrip_tools::test_storingen_zijn_nooit_een_lege_lijst`, `test_buiten_graaf`, `test_deelvragen` | Sterk punt: "een storing is geen lege lijst" is op veel plekken getoetst. Nog niet als één generieke eigenschap over alle api-aanroepen (§6). |
| **Budget op** | deels | `test_reeks` en `test_werkgebied_annotatie` (stopt halverwege, noemt de rest), `test_begrip_kaart::test_budget_op_start_geen_model`, `test_begrippen_verdieping_run`, `test_delegatie_afsluiten` (plafond per subagent, schatting vooraf), `test_eval_beheersing` (tijdbudget) | Voor batches en subagents goed. Het tokenbudget van een gewone beurt bewaakt de api; dat hoort in het testplan van de api. |
| **Afbreken** | goed | `test_runs::test_stoppen_is_een_verzoek_geen_annulering`, `test_run_endpoints` (stoppen, verwijderen stopt de beurt), `test_beurt` (stoppen bewaart wat er stond, "zegt live hetzelfde als na herladen"), `test_agent_loop::test_stoppen_haalt_de_graaf_van_een_nodegrens`, `test_graafopbouw::test_stopbewaking_zit_om_elke_node`, `test_gesprek_blijft_bruikbaar` | Goed, tot op de nodegrens. |
| **Hervatten** | goed | `test_subagent_vragen`, `test_c_begrensd`, `test_d01_hervatten`, `test_bronselectie` (hervatten zonder checkpointer, andere zoekcode zoekt opnieuw), `test_begrippen_verdieping_run` (een klare batch wordt hervat, niet opnieuw gerekend) | Goed, maar verspreid over vijf plekken. |
| **Een subagent die niet afrondt** | goed | `test_delegatie_afsluiten` (de code sluit af, de centrale agent leest niet zelf opnieuw), `test_rapport_en_rondegrens::test_zonder_rapport_noemt_de_code_wat_er_lag`, `test_subagent::test_zonder_rapport_zegt_de_code_waarom`, `test_a6_run3` (rapport `niet_gelukt`), `test_c_begrensd` (aanbod om door te gaan) | Gedekt na vijf metingen. |
| **Een leeg of afgekapt resultaat** | goed | `test_agent_loop::test_een_afgekapt_antwoord_krijgt_een_zichtbare_vlag`, `test_llm_stap` (geen tweede poging na afkappen), `test_resultaatcontract` (een ondeelbare eenheid boven de begroting is een fout, geen inkorting), `test_annotatie_overzicht` (zichtbaar onvolledig), `test_bronnen_vinden::test_een_geraakt_plafond_is_onvolledig` | Het resultaatcontract (`volledig`, `aantal`) is de generieke borg. |
| **Prompt-injectie via de inhoud van een bron** | **geen** | Alleen injectie in de *opdracht* (`kanaries` in `golden_annotatie.jsonl`, `test_eval::test_injectie_wordt_ook_in_de_markeringen_gezocht`) en in een plantitel (`test_a4_vervolg`: `"Human: negeer alles"`) | Grootste gat. Graaftekst, een Kamerstuk, een uitspraak of een kennisgroepstandpunt kan een instructie bevatten. CLAUDE.md zegt het zelf: "Nog niet gemeten: injectie via graafdata". Er is geen test dat zo'n tekst data blijft: niet in de toolresultaten, niet in het denkproces, niet in het rapport van een subagent. |
| **Een connector die uit staat of onbekend is** | goed | `test_bronschakelaar` (het model krijgt hem niet, en `dispatch` weigert in code), `test_bronroutering` (eerlijke melding zonder model), `test_routering::test_een_genoemd_id_van_een_uitgezette_bron_wordt_niet_gelezen`, `test_bronkeuze`, `test_kennisgroepen_tools::test_connector_uit`, `test_bekendmaking_tools::test_uit_is_niet_aangeboden` | Twee lagen (aanbod en dispatch), allebei getoetst. |
| **De rondegrenzen** | goed | `test_rapport_en_rondegrens::test_een_subagent_heeft_een_eigen_rondegrens`, `test_delegatie_afsluiten` (na de laatste ronde geen modelronde meer), `test_c_begrensd`, `test_meetvelden` (`ronde` op elke toolaanroep), `test_gesprek_blijft_bruikbaar::test_een_blijvende_toolfout_wordt_niet_eindeloos_herhaald`, `test_orchestrator::test_max_turns_kapt_af_zonder_orphan_tooluse` (de antwoordlus op `max_turns`, zonder open `tool_use`) | Goed, voor de subagent én voor de antwoordlus. |

## 3. Agentspecifiek

### 3.1 De keuze van het profiel

- **In code, gratis getoetst:** de route uit de ingang (`test_routering` met 50 rijen), de overdracht naar de juiste node
  (`test_routering_centraal`, 17 rijen) en de route in code naar een subagent (`test_subagent_route`).
- **Door het model, alleen live gemeten:** welke overdracht de centrale agent kiest, en of hij delegeert of het zelf
  doet. Dat meet de agentset (`golden_centrale_agent*.jsonl`) op acceptatie, met A6: "delegatie 19/26". Er is geen
  offline toets op de *beschrijving* van een overdracht, bijvoorbeeld dat twee profielen niet dezelfde aanwijzing hebben.
  `test_catalogus_agentvorm` toetst alleen dat elk profiel een plek heeft.

### 3.2 De tools

Goed: `test_toolverdeling` (de juiste rol krijgt de juiste tool, geen weestool), `test_context_per_agent` (een agent
krijgt alleen zijn eigen tools en skills), `test_bronschakelaar` (aanbod en dispatch), `test_resultaatcontract` (elke tool
en elke connectortool levert het contract, ook tegen een slechtst denkbare graaf) en `test_id_herkomst` (een id komt uit
het gesprek).

**Gat:** `FakeLLM` toetst niet of de tool die hij aanroept in `tools` van het verzoek stond. Een test kan dus een tool
laten aanroepen die het model in die stap niet kreeg. `dispatch` vangt dat voor uitgezette bronnen, maar niet voor een tool
die alleen in een ander profiel zit.

### 3.3 De grenzen

Rondegrens, plafond, strict schema's, het schrijfslot (`test_mcp_guard`), de methodegrenzen (`test_methodegrenzen`,
`test_methodes_gescheiden`) en de scope (`test_binnen_scope`) zijn getoetst, net als `max_turns` van de antwoordlus
(`test_orchestrator`). Het gat zit niet in een grens, maar in wat er gebeurt als de API zelf een grens trekt (de
strict-grammatica, §2).

### 3.4 Het denkproces

Goed gedekt, en met een generieke invariant: `conftest.py` zet `narratie.STRIKT` voor de hele suite.
`test_denkproces_volledig` legt vast dat het denkproces de beurt één op één weergeeft.
`tests/data/denkproces-vectoren.json` deelt vijf gevallen met de frontend (`lib/denkproces.ts`). Vijf gevallen is weinig
voor een contract tussen twee talen.

### 3.5 Stabiliteit over runs

**Offline niet te toetsen, en niet getoetst.** `FakeLLM` is deterministisch. `test_stabiliteit_analyse` toetst alleen het
meetinstrument (uitlijning en maten). De spreiding is bekend groot: geel varieert 38–77 % tussen runs van dezelfde bepaling
(meetlogboek). Het meetregime zegt één run, en drie alleen bij twijfel. Er is dus geen vaste plek waar de stabiliteit per
versie zichtbaar wordt. Dat hoort in Lex Bench (§5.3).

### 3.6 Regressie bij een wijziging aan een prompt of skill

- **Wat er is:** `test_modelverzoeken` (elk modelverzoek byte voor byte; een wijziging moet je bewust vastleggen met
  `GRAPHQA_VERZOEKEN_VASTLEGGEN=1`), `test_methode_drift`, `test_methodepakket`, `test_bronpakket` (de hash van elke skill
  en elk profiel), `test_prompt_caching` (het voorvoegsel blijft byte-gelijk), `test_identiteit` en `test_schrijfwijze`. Zo
  is elke wijziging zichtbaar. ADR-010 en P19 eisen dan een meting.
- **Wat ontbreekt:** de koppeling van *zichtbaar* naar *gemeten*. Een PR die een opname in `tests/data/modelverzoeken/`
  of het bronpakket wijzigt, vraagt nergens in de poort om een meting of een verwijzing naar een meting. Je legt een
  nieuwe opname vast met één env-variabele, en daarmee is de test weer groen.
- **13 opnames** dekken 13 aanroepen. Of elke modelaanroep een opname heeft, toetst `test_methoderollen` ("elke methoderol
  heeft een modelaanroep") maar niet `test_modelverzoeken` zelf.

## 4. De kwaliteit van de tests zelf

### 4.1 Altijd groen

- Vier "valt niet om"-tests zonder assert op de toestand (§1.4).
- De tests op prompttekst (§1.4). Die zijn groen zolang de zin er staat, ook als het gedrag verandert.
- **Stil overgeslagen:** 43 bestanden hebben een `skipif` of `importorskip`. Elf toetsen over componenten heen en slaan
  zich over als een bestand van een ander onderdeel er niet is (`CONTRACT.exists()`, `BICEP.is_file()`, "frontend niet
  aanwezig"). De poort checkt de hele repo uit, dus daar draaien ze. Maar een verplaatst bestand maakt de test
  stil groen in plaats van rood. Acht bestanden slaan zich over zonder spaCy. `graph-qa-docker-publish.yml` installeert de
  extra `nlp` niet, dus daar draaien ze nooit. Alleen de poort dekt ze.
- **`test_een_beurt_rondt_af_met_de_wettekst_uit_de_graaf`** is groen om de verkeerde reden (§4.2).

### 4.2 Afhankelijk van de volgorde: de oorzaak

**Reproductie.** `pytest tests/test_eval.py tests/test_sjablonen.py::test_een_beurt_rondt_af_met_de_wettekst_uit_de_graaf`
geeft `IndexError: list index out of range` in `FakeLLM._next`: het script van twee antwoorden is op. Na bisectie veroorzaakt
alleen `test_eval.py::test_offline_eval_run_slaagt` het.

**De oorzaak.**

1. `agent/overzicht.py` heeft een procesbrede cache, `_REGELINGEN_CACHE`, die "één query per proces" de citeertitels van alle
   regelingen ophaalt. Hij wordt alleen gevuld als hij leeg is, en nooit geleegd.
2. `test_offline_eval_run_slaagt` draait een beurt met een `FakeGraph` die op elke query de regelingenlijst geeft. De cache
   bevat daarna de Invorderingswet 1990 (`BWBR0004770`).
3. De sjablonentest vraagt "Wat staat er in artikel 9?", en het gescripte model kiest zelf `BWBR0004770`. Zijn `FakeGraph`
   geeft op élke query de lid-TSV, ook op `list_regelingen`. In isolatie blijft de cache dus leeg.
4. `id_herkomst` (soort `GOK`) weigert een BWB-id als "de vraag een artikel noemt maar niet deze regeling". Die controle
   herkent een regeling aan de namen uit dezelfde cache. Met een lege cache kent hij geen namen, ziet hij geen gok en laat hij
   het id door. Met de Invorderingswet in de cache doet hij wat hij in productie doet: "Wetgeving · niet gezocht: het id kwam
   niet uit het gesprek". Het model krijgt een extra ronde, het sjabloon past niet meer, en het script is op.
   Nagespeeld: leeg geeft 2 modelaanroepen en `gegrond`; gevuld geeft 5.
5. Leeg je alleen `_REGELINGEN_CACHE` tussen de twee tests, dan is de test weer groen. `regelingnamen._CACHE` en de
   schemacache maken geen verschil.

**Wat dat betekent.**

- De test beschrijft een beurt die productie weigert: het model gokt de regeling. Hij is groen omdat de controle die het
  zou moeten vangen, in zijn opzet niet werkt.
- **De poort is groen door toeval.** `scripts/pytest_shard.py` verdeelt de bestanden op gemeten duur. Nu staat
  `test_sjablonen.py` in shard 1 (45 bestanden) en `test_eval.py` in shard 2 (222). Een nieuwe duurmeting of een nieuw
  bestand kan ze samenbrengen, en dan wordt de poort rood op een PR die er niets mee te maken heeft. Een volle lokale run
  (alfabetisch: `test_eval` vóór `test_sjablonen`) is nu al rood.
- **Het patroon staat breder.** Vijf andere bestanden (`test_bepaling_workflow`, `test_bron_lijst`, `test_beweringen`,
  `test_bronnode_keten`, `test_id_herkomst`) legen `_REGELINGEN_CACHE` met de hand. Iedereen die deze valkuil tegenkwam,
  loste hem lokaal op. Er zijn nog meer procesbrede toestanden: `regelingnamen._CACHE` en `_AFKORTINGEN`,
  `graph/schema._cache`, `modelkeuze._STAND`, `_GEPROBEERD` en `_KAPOT`, `observability._geconfigureerd`, en een reeks
  `@cache`-functies (die laatste zijn zuiver en geven geen risico).
- **Een vraag voor de code, niet voor de test:** met een lege namenlijst staat de GOK-controle in productie ook uit. Dat
  gebeurt als de eerste `list_regelingen` van het proces faalt of leeg terugkomt, bijvoorbeeld vlak na een herstart van
  GraphDB. Die query wordt daarna wel opnieuw gedaan, want de cache wordt alleen bij een lege lijst gevuld. Toch is de
  controle in die toestand fail-open. Dat hoort bij de eigenaar van `id_herkomst` als vraag, niet bij dit testplan.

### 4.3 De nepdiensten

| Fake | Wat hij doet | Sterk | Zwak |
|---|---|---|---|
| `FakeLLM` (`tests/fakes.py`) | Speelt een vaste reeks antwoorden af via `create()` én `stream()`, met een gedeelde index; legt `calls` en `prompts` vast | Eenvoudig, deterministisch, en de vastgelegde verzoeken maken asserts op wat het model kreeg mogelijk | Kijkt niet naar het verzoek. Een extra modelronde wordt een `IndexError` in plaats van een leesbare fout ("ronde 3 niet gescript; het model kreeg: …"). Toetst niet of de aangeroepen tool is aangeboden. |
| `KetenLLM` | Antwoordt de classifier en de reviewer op basis van de prompt | Reageert op de invoer, zoals een model. De beste fake van de suite. | Alleen voor de annotatieketen. |
| `FakeGraph(result=…)` | Geeft op elke SPARQL hetzelfde antwoord | Snel | Te toegeeflijk. `list_regelingen`, `regeling_bestaat` en `get_artikel` krijgen hetzelfde, en dat zet controles stil uit (§4.2). |
| `FakeGraph(results=fn)` | Antwoordt per query | Precies | Elke test schrijft zijn eigen router op querytekst. Er is geen gedeelde nepgraaf met een kleine, vaste wereld. Die bestaat wel per bestand: `test_zoekvragen` ("een kleine kwijtscheldingswereld"), `test_bronselectie` en `test_plan_termijnen` delen er een. |
| `bron_fakes.py` | Een echte bronboom voor de annotatiescenario's | Gescheiden poorten voor api en graaf | — |
| Opnames (`tests/fixtures/koop`, `bwb_live`, `kennisgroepen`) | Echte antwoorden van de diensten | Het contract met de echte dienst, offline | Ze verouderen. Dat vangt de live-proef in `bronnenwacht.yml`. |
| `monkeypatch.setattr` | 305 keer in de suite, het meest in `test_wetgeving_live_routes` (14) en `test_a6_eind` (13) | — | Veel patches op interne functies binden de test aan de implementatie. |

### 4.4 Doorlooptijd

- **Poort:** shard 1 duurt 5–7 min, shard 2 ongeveer 3 min (laatste runs van 16 nov). Daarin zit `uv sync` met spaCy.
- **De verdeling klopt niet meer.** De duurmeting kent 194 van de 267 bestanden. De andere 73 wegen als de mediaan. Shard 1
  krijgt 45 bestanden en shard 2 krijgt er 222, op papier allebei 126 s. In werkelijkheid duurt shard 1 twee keer zo lang.
- **Uitschieters:** `test_resultaatcontract` 88 s (35 % van de gemeten tijd), `test_bronselectie_eval` 36 s,
  `test_mcp_server` 15 s, `test_runstore_postgres` 15 s, `test_wetgeving_live_routes` 12 s, `test_annotatielaag_isolatie`
  12 s. Samen is dat 70 % van de tijd, in 6 van de 267 bestanden.
- **Lokaal:** verzamelen duurt 17 s. De volle suite draai je lokaal niet (geheugen bij parallelle sessies); de hook draait wat
  je raakt.

## 5. De evals

### 5.1 Per set

*Wie*: wie de verwachting opstelde en vaststelde. *Blind*: was de set onbekend bij het afstemmen? *Gebruik*: de laatste
plek waar ik hem in de code of het meetlogboek vond.

| Set | Doel | Grootte | Wie | Blind | Gebruik |
|---|---|---|---|---|---|
| `golden.jsonl` | Antwoorden: faithfulness, bronrecall, weigeren, overzicht | 22 cases, 6 vraagtypen | ontwikkelsessies, uit bevindingen op dev/acc | nee | eval-job (`azure-infra` → `eval`), meetscript als K01…; ronde 3, 13 nov |
| `golden_annotatie.jsonl` | De annotatieketen: garanties (letterlijk, klasse, `verboden`, kanaries) en recall op ankers | 10 cases (8 silver, 2 synthetic), 29 ankers | ontwikkelsessies; "conceptankers, geen volledige expertgold" | nee. Case 1 (Iw art. 9 lid 1) is ook voorbeeld 1 in de skill. | eval-job, drie runs; `test_golden_annotatie` bewaakt de ankers tegen `bronteksten.json` |
| `golden_annotatie_concept.jsonl` | Dekking per klasse op de conceptcasussen | 14, `provisional` | uit `docs/wetsanalyse/referentieset/concept/`, niet vastgesteld | nee | `eval_set: concept`; geen meting gevonden in het logboek |
| `golden_centrale_agent.jsonl` | De agentset van ADR-016: delegatie, vragen naar boven, vervolg, kwaliteit | 30 opdrachten in 5 groepen, plus een meetwerkgebied | ontwikkelsessies, beschrijft het *doel* van ADR-016 | nee | `centrale_agent_meting.mjs` met `centrale_agent_vat.py`; M0 tot en met A6 (15 nov), drie runs zijn ongeveer 15M tokens |
| `…_breed.jsonl` | Overdracht naar de brede toolset | 4 | idem | nee | meetscript `--set`; vormtest wel |
| `…_delegatie.jsonl` | A4/A5: vraag naar boven, meer subagents | 5 | idem | nee | meetscript; vormtest wel |
| `…_vervolgc.jsonl` | A2-3c: vervolgvragen naar een vaste route | 3 | idem | nee | alleen de meting a23c (14 nov). **Geen vormtest**: `test_golden_centrale_agent` leest hem niet. |
| `golden_duiding.jsonl` | Het sjabloon `duiding` | 6 | uit de nulmeting op acc van 7 nov | nee | eval-job (`eval_set: duiding`), meetscript; g1b en s6, 13 nov |
| `golden_duiding_partijen.jsonl` | G1: een partij die de tekst niet noemt, een soort bevoegdheid | 10 Awb-bepalingen, met `beoordeling` | ontwikkelsessie; elke bepaling nagelezen in de officiële bron | nee | meting g1/g1b, 13 nov |
| `golden_klasse_twijfel.jsonl` | G2: twijfel tussen twee JAS-klassen | 5 | idem | nee | meting g2, 14 nov |
| `golden_gesprek.jsonl` | Vervolgvragen in één thread (scenario A, B, C, R, F, V) | 18 gesprekken | ontwikkelsessies | nee | eval-job, trendmeting; laatst apart gemeten 6 okt, daarna via het meetscript |
| `golden_routering.jsonl` | Route per vraag en context, en of er een model nodig is | 50 | ontwikkelsessies | n.v.t. | **is een test**: `test_routering` in elke poort |
| `golden_routering_centraal.jsonl` | Overdracht naar de juiste node | 17 | idem | n.v.t. | **is een test**: `test_routering_centraal` |
| `tests/data/*_vragenset*.json` | Per connector: route, tool en argumenten, `goed` | Kamerstukken 30, Rechtspraak 32, Bekendmakingen 30, Wetgeving buiten de graaf 18 | ontwikkelsessies, de feiten nagezocht bij de dienst | nee | offline als test (route en argumenten), live op acc als iteratieronde |
| `tests/data/stukcontrole_set.json` | De controle per stuk: steunt, tegen, verwijzing | 12 gevallen, fictief (jaar 2099) | ontwikkelsessie | nee | `eval/stukcontrole_set.py` (model, met akkoord), vorm in `test_b_lezer_beslist` |
| `eval/kaartacties_brondefinitie.json` | Zoek de brondefinitie | 8 cases | bij de bouw, "niet door een jurist vastgesteld" | nee | `kaartacties_eval` en `uitleg_eval`; 16 okt |
| `eval/betekenisonderzoek_casus.json` | Spoor M: casus A en B | 2 casussen, 21 nodes, met hash | letterlijk uit de graaf | nee | `betekenisonderzoek_eval`, en de tests in api en graph-qa |
| `docs/wetsanalyse/referentieset-bronselectie/` | Bronselectie per deelvraag | 8 sets (6 met deelvragen en opname) | zie het plan Lex Bench §2 | zes ooit blind, nu ontwikkeling; Verrekening hoort bij de sessie Termijnen | `bronselectie_eval`, en de uitkomst vastgepind in `test_bronselectie_eval` |
| `docs/wetsanalyse/referentieset-begrippen/` | De begrippenketen (BCubed) | v1, heldout-v1, heldout-v2 | zie ADR-004 | v1 ontwikkeling; AWR eenmaal blind gemeten | `begrippen_eval` |
| `docs/wetsanalyse/referentieset/` (JAS) | Vastgestelde JAS-casussen, adjudicatieprotocol | v1 plus 8 concepten | A en B onafhankelijk, C adjudiceert | volgens het protocol | `referentieset.py`, `adjudicatie.py` |

### 5.2 Wat opvalt

- **Geen enkele set in `eval/` is blind of door een jurist vastgesteld.** Alle verwachtingen komen van ontwikkelsessies,
  vaak uit een meting die daarna is gebruikt om te verbeteren. Het meetlogboek zegt dat eerlijk ("trendmeting"). De
  enige set met een vaststellingsprotocol is de JAS-referentieset.
- **De held-out sets zijn vastgepind in een eenheidstest.** `test_bronselectie_eval` heeft
  `test_de_held_out_meting_houdt_haar_uitkomst` en twee varianten. Wie de zoekcode wijzigt, ziet bij elke testrun de
  uitkomst op de held-out set. Daarmee is die set niet meer held-out bij het afstemmen. Het plan Lex Bench (§4.5) wil dit
  juist voorkomen.
- **Een set zonder vormtest:** `golden_centrale_agent_vervolgc.jsonl`.
- **Twee namen voor hetzelfde veld:** `golden_annotatie.jsonl` heeft zowel `referentie_status` (`silver`) als
  `referentiestatus` (een zin).
- **Overlap met de skill:** de eerste annotatiecase is voorbeeld 1 in `references/voorbeelden.md`. De annotatieketen krijgt
  de voorbeelden niet (de methodetekst per rol bevat ze niet), maar wie de ankers opstelde kende ze. De skill zegt zelf dat
  een voorbeeld geen testgeval mag zijn (`test_skill_evals`).
- **Vijf sets meten de antwoordkwaliteit met dezelfde scorers** (`golden`, `duiding`, `duiding_partijen`, `klasse_twijfel`
  en het vervolg in `golden_gesprek`). Het meetscript leest ze elk met een eigen tak.

### 5.3 Voorstel: wat opgaat in de ene testset van Lex Bench

Lex Bench meet juridisch werk. De agentset meet het gedrag van de agent. Dat zijn twee assen. Ze kunnen in één manifest
staan, maar mogen niet tot één score worden opgeteld. Voorstel:

1. **Bronselectie** (fase 1, al in het plan): de zes ontwikkelsets. De pinnen op de held-out uitkomst gaan uit
   `test_bronselectie_eval` naar het rapport van Bench. De test houdt dan alleen de vorm en het pad zonder model.
2. **Annotaties** (fase 2): `golden_annotatie.jsonl` en `golden_annotatie_concept.jsonl` worden casussen in het manifest,
   met hun status (`silver`, `provisional`) als `verwachting.status: concept`. De JAS-referentieset blijft de plek voor
   vastgestelde casussen, zoals het plan zegt. De garanties (letterlijk, klasse, kanaries) blijven een test en worden geen
   score.
3. **Begrippen** (fase 3): de referentieset-begrippen, en `kaartacties_brondefinitie.json` en
   `betekenisonderzoek_casus.json` als casussen voor de brondefinitie en de betekenis.
4. **Antwoorden** (een as naast fase 1–3): `golden`, `golden_duiding`, `golden_duiding_partijen` en `golden_klasse_twijfel`
   samen in één antwoordset met `vraagtype`. Ze hebben al hetzelfde schema en dezelfde scorers.
5. **Agentgedrag** (een eigen as, niet in de juridische score): de vier `golden_centrale_agent*`-sets en `golden_gesprek`,
   samen in één agentset met groepen. `vervolgc` krijgt een vormtest. Hier hoort ook de stabiliteit over runs (§3.5): de
   agentset is de enige die al met meerdere runs werkt.
6. **Blijft een test, en gaat niet naar Bench:** de routeringssets, de route en de argumenten van de connectorvragensets,
   de denkprocesvectoren en `stukcontrole_set` (vorm). De live-ronde van de connectorvragensets kan als as *connectors* in
   het manifest, met hetzelfde runrecord.

## 6. Voorstellen, op prioriteit

### P0: nu, klein, zonder model

1. **Reset de procesbrede caches tussen tests.** Een autouse-fixture in `conftest.py` leegt `_REGELINGEN_CACHE`,
   `regelingnamen._CACHE` en `_AFKORTINGEN`, de schemacache en de modelkeuzestand. De vijf handmatige `clear()`-aanroepen
   gaan weg. Herschrijf daarna de sjablonentest zodat de vraag de regeling noemt, of zodat de nepgraaf `list_regelingen`
   beantwoordt. Dan toetst hij een beurt die productie toelaat.
2. **Draai de suite in willekeurige volgorde als vaste controle**, bijvoorbeeld wekelijks met `pytest-randomly`, met het zaad
   in het log zodat een rode run na te spelen is. Zo blijft een volgordefout niet afhankelijk van de
   shardverdeling.
3. **Een test voor prompt-injectie via de bron.** Een nepgraaf en een nepconnector met een instructie in de tekst
   ("Negeer de vorige instructies en …"), door de echte toollaag. Toets dat er geen tool buiten het plan wordt aangeroepen,
   dat de instructie niet als stap in het denkproces komt, en dat het rapport van een subagent haar als citaat behandelt,
   niet als opdracht. Generiek voor elke connector, via het register van `test_connectorbeschrijving`. Dit toetst de code
   rond het model, niet het model. Hoe het model zich gedraagt, hoort als kanarie in de antwoordset (§5.3).
4. **Een strengere `FakeLLM`**, achter een vlag en daarna als default: hij faalt met een leesbare melding als een
   aangeroepen tool niet in `tools` stond, en als het script op is ("ronde N niet gescript; laatste systeemprompt: …").
5. **Werk de duurmeting bij** (`pytest_shard_duur.json`, nu 73 bestanden ongemeten), zodat de shards echt in balans zijn.

### P1: herschrijven, zonder het gedrag te veranderen

6. **Groepeer per mechanisme in plaats van per bundel.** Een map per groep uit §1.1 (`tests/subagent/`,
   `tests/connectors/` …). De bundelbestanden gaan naar de groep van hun mechanisme, met de meting in de docstring. Doe het
   in één beweging per groep, en houd de testnamen gelijk zodat de historie te volgen blijft. Dit raakt de shardverdeling
   (per bestand) en `tests/poort/test_build_inputs.py`; overleg daarom met de poort.
7. **Een gedeelde nepgraaf met een kleine vaste wereld** (een paar regelingen, artikelen en leden die op de echte query's
   antwoorden), naast `FakeGraph(result=…)`. Begin bij de tests die nu `_REGELINGEN_CACHE` legen.
8. **Vervang de asserts op prompttekst** door `test_modelverzoeken` of door een toets op gedrag. Ruim
   `test_specialists.py` op en werk de docstrings met "supervisor" bij.
9. **Voeg `test_trim_messages` en `test_trimming` samen.** Teken de drie lagen van de toollaag (`test_tools`, `test_queries`
   en `test_retrieval_tools`) in de docstrings af, en verschuif `test_queries` waar het kan naar het resultaat.
10. **Maak "een storing is geen leeg resultaat" één generieke test** over elke api-aanroep van de agent (de lijst in
    `agent_toegang`), in plaats van per tool.

### P2: erbij

11. **Een time-out van de graaf en van een connector, offline:** `httpx.MockTransport` die `ReadTimeout` gooit, en
    een MCP-call die blijft hangen. Toets dat er een zin voor de jurist komt, dat de historie geldig blijft, en dat het
    resultaatcontract `status: fout` heeft.
12. **Een beurt waarin de API een strict schema weigert** (een `BadRequestError` op de grammatica): de jurist krijgt een
    zin, de historie blijft geldig, en het log noemt het profiel.
13. **Een poorttest die bij een gewijzigde opname in `tests/data/modelverzoeken/` of het bronpakket** een verwijzing naar
    een meting in het meetlogboek vraagt, of een expliciete regel "geen gedragswijziging" in de PR. Dat maakt ADR-010 P19
    afdwingbaar in plaats van afhankelijk van discipline.
14. **Een vormtest voor `golden_centrale_agent_vervolgc.jsonl`**, en één veldnaam voor de referentiestatus in
    `golden_annotatie.jsonl`.
15. **Meer denkprocesvectoren** voor het contract met de frontend (nu vijf): één per soort stap.

### Weg kan (na de groepering)

- De dode hulpjes in `test_specialists.py`.
- De pinnen op de held-out uitkomst in `test_bronselectie_eval`, zodra Bench ze rapporteert (§5.3).
- Overlappende tests die na het samenvoegen van de trimming dubbel blijken. Weghalen pas na de samenvoeging, met de
  dekking ernaast.

Niets hiervan is gebouwd. Elke stap is een eigen PR, en de hoofdsessie bundelt ze.

## Bijlage A: indeling per bestand

Bestandsnamen zonder `test_` en `.py`.

- **Routes en ingang:** routering, routering_centraal, a7_ingang, bronroutering, binnen_scope, methodekeuze, aanwijzing,
  vervolgvraag, focus, onderwerp, specialists, advies_en_suggestie, bepaling_workflow, overzicht, buiten_graaf, bron_lijst,
  verduidelijken, graafopbouw, orchestrator, agent_loop, regie_ingang.
- **Centrale agent en subagents:** centrale_agent, subagent, subagent_model, subagent_route, subagent_vragen, subagenten,
  delegatie_afsluiten, delegatie_na_rapport, rapport_en_rondegrens, vraag_sluit_beurt, regie_plan, regisseur, agents,
  agent_uitvoering, agentvorm, agentprofiel, profielregister, skills_laden, context_per_agent, toolverdeling, modelkeuze.
- **Sjablonen en antwoordvorm:** sjablonen, sjabloon_afronden, extern_sjabloon, uitgifte_na_controle, identiteit,
  schrijfwijze, verwijderen_niet_weghalen.
- **Grounding en verify:** grounding, provenance, beweringen, citaat_herstel, hoeveelheden, bronregister,
  resultaat_consumenten, externe_vindplaats, vindplaats, aanduiding, id_herkomst, plekken.
- **Annotatieketen:** detectoren, syntactische_detectoren, detectieprofielen, detectiebijdragen, detector_audit,
  detector_freeze_regressies, fusie, kandidaatmodel, kandidaten, taalanalyse, taalmodel_opwarmen, telwoorden, tekststructuur,
  tekststructuur_keten, review_resolver, reviewload, validatie, dekking, subtype, uitleg, verklaringen, hybride_keten,
  annotatie_worker, annotatie_compact, annotatie_overzicht, annotatie_samenvatting, annotatielaag_isolatie, gedeelde_laag,
  hergebruik, reeks, werkgebied_annotatie, bronnode_keten, doel_vindplaats, doel_en_modellen, classificatie_parallel,
  ontdubbelsleutel, beslisregister, relatievoorstellen, jas_tools, jas_klasse_opvragen, jas_protocol,
  klassenreferentie_afbakening, provenance_element, invordering_beslisketen, invordering_verbeteringen.
- **Begrippen:** begrip_b1, begrip_kaart, begrip_kiezen, begrip_tools, begrippen_beurt, begrippen_keten, begrippen_model,
  begrippen_onderzoek, begrippen_patronen, begrippen_relaties, begrippen_run, begrippen_signalen, begrippen_taal,
  begrippen_verdieping, begrippen_verdieping_run, begripsnaam, betekenis, brondefinitie_volgen.
- **Werkgebied en bronselectie:** bronselectie, bronnen_vinden, zoekvragen, plan_termijnen, deelvragen, werkgebied_intake,
  werkgebied_context.
- **Connectors:** kamerstuk_tools, kamerstukken_live, rechtspraak_tools, rechtspraak_live, rechtspraak_zoeken,
  bekendmaking_tools, bekendmakingen_live, kennisgroepen_lezer, kennisgroepen_tools, kennisgroepen_live, wetgeving_tools,
  wetgeving_live_routes, wetgeving_live_live, connectorbeschrijving, bronschakelaar, bronkeuze, bronprompt,
  bron_lezen_voorlezing, stuk_tekst, op_xml_oud_schema, http_beleid, regelingnamen.
- **Denkproces:** denkproces_volledig, denkproces_zonder_antwoord, spoorbronnen, toolregel, toolspoor, narratie_aanloop,
  beurtmeting.
- **Contextopbouw en modelstap:** contextopbouw, prompt_caching, trim_messages, trimming, venster_meting, verzoekopbouw,
  modelverzoeken, llm_stap, strict_grenzen, schoon_messages, memory, verbruik, meetvelden, gesprek_blijft_bruikbaar.
- **Graaf en toollaag:** tools, queries, retrieval_tools, resultaatcontract, results, schema, sparql_syntax, mcp_client,
  mcp_guard, semantic_search_terugval, fts_velden, predicaat_dekking, namespace_drift, structuur.
- **MCP-server:** mcp_server.
- **Runs, beurt en dienst:** runs, run_endpoints, run_endpoints_gedeeld, runstore_postgres, beurt, api_herhaal, security,
  config, observability, imagemelding, deploy_drift, contract_drift, agent_contracten, begrippen_manifest_drift.
- **Methode, skills en catalogus:** methode_drift, methodepakket, methoderollen, methodesectie, methodebronnen,
  methodegrenzen, methodes_gescheiden, skillvalidator, skill_zonder_code, skill_evals, bronpakket, catalogus,
  catalogus_agentvorm, catalogus_methode, werkplaatsregister, vocabulaire_drift, jas_klassen.
- **Meetsets per bundel:** a4_vervolg, a6_aansluiting, a6_citaten, a6_eind, a6_f03, a6_kern, a6_run1, a6_run2, a6_run3,
  b3_na_subagent, b_lezer_beslist, c_begrensd, d01_bundel122, d01_bundel123, d01_gelezen_via_ander_stuk, d01_hervatten,
  d01_samenvatting_per_stuk, d01_zonder_duiding, e_b2_zoeken, bundel_elk_rapport, controle_citaten.
- **Eval-harnas, sets en referentiesets:** eval, eval_beheersing, eval_gesprek, eval_kwaliteit, eval_metrieken,
  eval_scorers_v2, golden_annotatie, golden_centrale_agent, adjudicatie, referentieset, referentieset_concept,
  fouttaxonomie, laagrapport, meetharnas, stabiliteit_analyse, compare_pipelines, baseline_proef, extern_dossier,
  onderzoek_invordering, invordering_proef, bronselectie_eval, begrippen_eval, kamerstukken_vragenset_30,
  rechtspraak_vragenset, bekendmakingen_vragenset, wetgeving_live_vragenset.
