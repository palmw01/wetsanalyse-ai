# De centrale agent in de breedte: aansluiting vóór de eindmeting A6

Status: **analyse**, 14 nov 2026, op `1aad39e7` (bundel 121: hervatten #1505, de samenvatting per stuk #1508, gelezen
via een ander stuk met de afbakening onder het antwoord #1511). Er is niets gebouwd en op acceptatie niets gemeten.
Gelezen is de code van frontend, api en graph-qa, de agentset en de metingen. Op acceptatie is alleen gelezen
(gesprekken via de BFF, GET), op een D01-gesprek uit de meting van bundel 120.

Bundel 121 raakt alleen graph-qa: de periode die de jurist koos (`gekozen_periode`, `Afloop.periode`), de afbakening
onder het antwoord (`antwoord.afbakening_regel`) en een stuk dat alleen via een ander stuk bekend is. Frontend, api,
`tools_node` en de overdrachtstools bleven gelijk, dus de gaten hieronder gelden ook na bundel 121.

Hoort bij [ADR-016](adr-016-centrale-agent-en-werkplaats.md). De vraag: is de centrale agent in de hele applicatie goed
aangesloten (UI-ingangen, SSE, componenten, toegang, logging, configuratie), zodat de eindmeting A6 (drie runs) iets
meet wat ook in de werkplek klopt?

## Samenvatting

De kern is goed aangesloten. De routes in code gaan vóór de centrale agent, en elke klik met een `actie`, `intake_actie`,
`doel` of `modus` blijft een vaste route zonder model. De centrale agent bereikt de route-uitgangen (bepaling, overzicht,
annotaties en begrippen lezen, stukken, werkgebied, taakagents, regie) via overdrachtstools. Er is één weg naar een run
(`start_beurt`), met de budgetpoort voor kinderen. *Stop* stopt de kinderen mee. Herladen hangt opnieuw aan bij de run. De
vraagkaarten `sa_vraag` en `sa_start` gaan heen en terug en blijven na herladen staan. De api-allowlist dekt de
delegaties en raakt geen besluit.

Er zijn vier gaten die de A6-uitkomst bepalen voordat er gemeten is, en vier die eerst dicht moeten voordat `aan` de
standaard wordt:

| # | Gat | Ernst |
|---|---|---|
| 1 | De agentset verwacht onderdelen die niet gebouwd zijn: `delegatie_stand` (F03), een vraag die de centrale agent zelf beantwoordt (V03), fasen met een knop voor de volgende fase (M04), het profiel `retrieval` bij regiekinderen (M04, M05) | **blokkeert A6** |
| 2 | Een geweigerde toolaanroep (`tool buiten profiel`, `tool na subagent geweigerd`) geeft geen `tool_execution`-event. De meetmaat `tool_buiten_profiel` staat daardoor altijd op 0, en het denkproces meldt dat Lex de stukken leest | **blokkeert A6** (meetpunt blind), en moet vóór `aan` |
| 3 | Het lichte model staat uit op acceptatie, dus subagents draaien op het gewone model, en `beurt_meting.model` noemt altijd het gewone model | **blokkeert A6** (eerst besluiten wat A6 meet) |
| 4 | Een getypt verzoek om te annoteren ("annoteer artikel 9 lid 1 Iw 1990", "doe hetzelfde voor lid 2", "annoteer deelvraag 2") heeft bij de centrale agent geen tool (A2-4 niet gebouwd), en zit niet in de gemeten sets | **moet vóór aan**; A6 moet het als niet gemeten benoemen |
| 5 | Een getypt antwoord op een open vraagkaart gaat nog langs de supervisor (`beantwoord_kaart` niet gebouwd) | moet vóór het opruimen van de supervisor (A7.3) |
| 6 | Het deelgesprek van een subagent bewaart de opdracht niet, en evenmin de antwoorden bij het hervatten: er staan alleen rapporten | moet vóór aan |
| 7 | De werkplek leest de delegatie niet: geen stand *wacht op antwoord*, geen kaartje met de lopende subagents, de tellingen van `regie` worden genegeerd | moet vóór aan |
| 8 | Observability: geen span per subagent, geen `ouder_run_id` of vorm in `beurt_meting`, geen boomtotaal in Grafana; de trace-keten van kind naar ouder is niet geverifieerd | later; het meetpunt is vóór A6 aanbevolen |

Daarnaast zijn er een paar kleinere punten (§7).

## 1. Ingangen in de UI

`agentvorm` stuurt de werkplek nooit (`frontend/lib/api.ts`, `startRun`). De straat beslist dus
(`agentvorm.vorm_van`):

- met `meten` draait elke beurt uit de werkplek de supervisor, en alleen een meetrun (de acceptatie-MCP met
  `agentvorm: centraal`) krijgt de centrale agent;
- met `aan` krijgt elke beurt de centrale agent, behalve als een route in code hem eerder pakt.

De tabel geldt voor `aan`, of voor een meetrun met `meten`.

| Ingang | Wat de werkplek stuurt | Verwachte route (ADR-016) | Werkelijke route | Klopt |
|---|---|---|---|---|
| Typen in het invoerveld, zonder werkgebied | `question` | routes in code, anders centraal | `_kies`: methodekeuze, verduidelijken, leesvraag, overzicht, bepaling, bron uit, buiten de graaf, genoemd stuk, lijst; dan `subagent_route.past`, dan centraal | ja |
| Typen in een werkgebiedgesprek | `question`, `werkgebied_id` | idem, plus de werkgebiedroutes | eerst **vóór de graaf** `opdracht_in` (de regie: "zoek per deelvraag de bronnen"), dan in `_kies` de bronselectie, het samenstellen en de dekking; de rest centraal | ja |
| Typen terwijl er een vraagkaart openstaat | `question` | `beantwoord_kaart`, een tool van de centrale agent | de supervisor (`_centraal` sluit `_open_kaartje` uit) | **nee**, gat 5 |
| Typen: "annoteer artikel X" | `question` | de overdracht `annoteer` (A2-4) | centraal zonder annotatietool; `taakagent` kent alleen `deelvragen` en `begrippen` | **nee**, gat 4 |
| Suggestie met een `actie` (`deelvragen_voorstellen`, `begrippen_meedenken`, `dekking`, `brondefinitie`, …) | `actie`, `werkgebied_id` | `ACTIE_TAAK`, zonder model | `ACTIE_TAAK` (`_kies`, vóór `_centraal`) | ja |
| `bronselectie`, `bronnen_zoeken`, `bepaling_toevoegen` | `actie` | de bronselectie-worker | `BRONSELECTIE_ACTIES` | ja |
| `dossier_aanvullen` (*Vul het dossier aan*, *Vraag Lex* bij een leeg veld) | `actie` | de intake | `INTAKE_ACTIES` | ja |
| `werkgebied_annoteren`, `deelvragen_annoteren` | `actie` | de reeks, met bevestiging | `is_werkgebied_annotatie`, vóór de graaf | ja |
| `regie_bronnen`, `regie_annoteren` (de knop *Start de regie*) | `actie`, `plan_id` | de regisseur | `regie_stroom`, vóór de graaf | ja |
| *Vraag Lex* bij een markering | `modus: advies`, `context` | een route in code | `advies`, hard naar het profiel `duiding` (geen subagent, geen centrale agent) | ja; bewust, maar zie §7 |
| *Vraag Lex* bij een deelvraag, bron, kandidaat, begrip, werkgebied, bepaling of stuk, met een suggestie zonder `actie` | `onderwerp`, `question` | centraal, met het object als context | centraal; `onderwerp_context` en `werkgebied_context` gaan mee (`agent.py`) | ja |
| *Annoteer dit onderdeel* (de bepaling) | `doel` | de annotatieroute | `_heeft_opgegeven_doel`, zonder model | ja |
| Commando's (`/deelvragen`, `/bronnen`, `/annoteer`, …) | dezelfde suggestie (`lib/commandos.ts`) | als de suggestie | als de suggestie; `/nieuw`, `/bron` en `/help` starten geen beurt | ja |
| Vraagkaart van het samenstellen of de bronselectie | `intake_actie` | de stapmachine | `intake_actie` gaat vóór alles (ook in `_stroom_voor`) | ja |
| `sa_vraag`: de vraag van een subagent | `intake_actie` (`sa-…`) | zonder model naar `subagent_vervolg`, hervatten, dan de bundel van de centrale agent | `_subagent_vervolg` → `subagent_vervolg_node` → `agent` (profiel `centraal`) | ja; dit werkt ook bij `meten` zonder `agentvorm`, want de node kijkt alleen naar de straat |
| `sa_start`: de bevestiging vóór meer subagents | `intake_actie` | starten, dan de bundel | `voer_plan_uit` → de bundel | ja |
| Doorvragen in een deelgesprek | `question` in het kindgesprek | het profiel van het deelgesprek | `_deelgesprek`, met `later_gewijzigd` op de delegatie | ja |

**Wat ADR-016 bedoelt, klopt:** de routes in code eerst, en de regisseur als tool (`regie_plan`) én als route vóór
de graaf. De tabel van de routeringsset (`tests/test_routering.py`) meet alleen de supervisorvorm. Er is geen
routeringstest die per rij met `model: true` zegt welke tool de centrale agent zou moeten hebben. Daardoor viel gat 4
niet op.

## 2. De run en de SSE-stroom

**Wat werkt.**

- Kinderen starten langs `start_beurt` (`Kinderen.start`), met `ouder_run_id` en de budgetpoort.
- Het kind is een gewone run in een eigen gesprek, met een eigen stroom, en wordt vastgelegd en geboekt.
- *Stop* op de ouder: `stop_met_kinderen` en `_stopwacht` stoppen het kind ook.
- De SSE-heartbeat houdt de stroom open terwijl een kind minuten loopt (stilte-grens van 45 s in de frontend).
- Herladen hangt via `haalActieveRun` weer aan bij de ouder; een deelgesprek heeft zijn eigen run.

**Events die graph-qa stuurt en de werkplek negeert of half leest:**

| Event | Wat erin staat | Wat de werkplek doet | Wat bewaard wordt |
|---|---|---|---|
| `regie` (`fase: start`/`eind`, `soort: subagent`, `hervat`) | het plan (titel, profiel) en de tellingen `opgeleverd`, `wacht`, `niet_gelukt`, `afgesloten`, `mislukt` en `kinderen` | negeert het (`verwerkSseStroom` kent het type niet) | niets (`BeurtSchrijver` kent het niet) |
| `regie_taak` | `gesprek_id`, `profiel`, `gekozen_model`, `model`/`modellen`, `rapport` (status, gedaan, bevindingen, open, gelezen, afbakening, stukken, bepalingen) | gebruikt alleen dat het er is: de gesprekslijst ververst (`onRegieTaak`) | niets |
| `meting` van het kind | de contextopbouw van het kind | komt niet in de stroom van de ouder; de contextweergave haalt de boom bij de api | op het bericht van het kind |
| `tool_execution` | elk toolgebruik | nergens gelezen (ook niet bij gewone beurten) | op het bericht |

Wat de meting als `kind_modellen`, `afgesloten`, `afbakening`, `periode` en `gelezen` leest, bestaat dus alleen in de
stroom en bij de delegatie. In de werkplek is het nergens te zien, en na herladen alleen via het deelgesprek en de
contextweergave. Dat hoort bij gat 7.

Sinds bundel 121 bereikt één ervan de jurist toch: een afbakening die de subagent zelf koos, zet de code als regel of
blok *Afbakening* onder het antwoord (`afbakening_regel`), en zo staat ze op het bericht. Dat is de goede weg (uit code,
op het bericht, ook na herladen). Voor de rest van de kindregel (uitkomst, gelezen, periode, model) is die weg er nog
niet.

**Omgekeerd** stuurt de werkplek niets wat graph-qa negeert. `profiel`, `opdracht` en `delegatie_id` neemt
`POST /v1/runs` terecht niet aan van buiten.

**De chatgeschiedenis (api).** `BerichtInvoer` neemt `vraagkaart` (met `modus: subagent`, `sa_vraag` en `sa_start` in
`IntakeStap`), `intake_antwoord`, `contextopbouw` en `uitkomst` aan, en er gaat geen veld stil verloren. Op acceptatie
gecontroleerd (een D01-gesprek van 14 nov): de drie `sa_vraag`-kaarten, de antwoorden met `intake_antwoord` en de
eindbundel staan er alle.

Twee punten:

- **Gat 6. Een deelgesprek heeft geen opdracht.** `subagent._draai_kind` maakt het gesprek en start de run, maar
  schrijft het eerste bericht (de opdracht, of bij het hervatten de antwoorden van de jurist) nergens weg. Op acceptatie
  hebben de deelgesprekken één of twee berichten, en die zijn alle twee een rapport van de assistent. Wie het
  deelgesprek opent of erin doorvraagt, ziet niet wat de subagent moest doen. De regiekinderen (ADR-012) doen het net
  zo, maar daar is de titel de opdracht. *Fix:* in `_draai_kind` vóór `kinderen.start` een gebruikersbericht met
  `opdracht_tekst(...)`, of bij het hervatten met `antwoord_tekst(...)`, via `voeg_bericht_toe`. Neem
  `voeg_bericht_toe` op in `subagent.API_AANROEPEN`; de route staat al in `agent_toegang.TOEGESTAAN`.
- **De bovenste `contextopbouw.profiel_id` is altijd leeg.** `beurt._leg_vast` geeft hem niet door. Per agent en per
  aanroep staat het profiel er wel. De rij van een deelgesprek in de contextweergave (`Contextweergave.tsx:245`) leest
  het bovenste veld en toont daardoor geen profiel. *Fix:* in `voer_beurt_uit` het profiel van de run meegeven
  (`request.profiel`, en de versie uit `profielen`).

## 3. De UI-componenten

**Wat werkt.**

- De sidebar zet een deelgesprek onder zijn ouder, met het profiel erbij (`gesprekGroepen.profielVan`: "subagent
  algemeen").
- De vraagkaart toont `sa_vraag` en `sa_start` met *Laat maar.*
- De contextweergave toont de deelgesprekken met hun verbruik en het verbruik van de boom.
- De bronnen en de grounding van de bundel staan op het bericht.
- Vitest gedraaid op `vraagkaart`, `contextweergave`, `gesprekGroepen`, `agentEvents` en `beurtVerzoek`: 86/86 groen.

**Wat ontbreekt of afwijkt.**

- **Gat 2, het denkproces.** `tools_node` schrijft de statusregel ("leest uitspraak …") voor alle aanroepen vóór de
  weigering (`na_subagent`, `agent.mag`). Op acceptatie zei een bundel na het hervatten in het denkproces dat Lex vier
  uitspraken las, terwijl de code ze alle vier weigerde; `tool_executions` op dat bericht is leeg. De jurist leest dus
  iets wat niet gebeurde, en de meting ziet de weigering niet. *Fix:* de statusregel alleen voor wat werkelijk
  uitgevoerd wordt, en per geweigerde aanroep een `tool_execution` met `status: geweigerd` en de reden. Zo telt
  `centrale_agent_sets.tool_buiten_profiel` weer, en ziet `tools_verboden_gezien` een poging.
- **Gat 7, geen zicht op de delegatie.** ADR-016 §A5 noemt voor de werkplek "het profiel bij elk deelgesprek, de stand
  *wacht op antwoord*, de keuzekaarten in de bundel, en de knop voor de volgende fase". Er zijn alleen het profiel en
  de keuzekaarten. De frontend roept `/v1/delegaties` nergens aan, en er is geen kaartje dat tijdens de beurt zegt welke
  subagents lopen. Er is ook geen *Stop alles*: de gewone stopknop stopt wel de kinderen. *Fix:* het `regie`-event
  parsen tot een klein voortgangsblok (plan, per kind de stand en een link naar het deelgesprek), en de stand van een
  deelgesprek in de sidebar uit de delegatie.
- **Er is geen browsertest** voor de subagentkaarten of de deelgesprekken van een subagent (`npm run test:browser`
  noemt geen subagent). *Fix:* een `test-subagent.mjs` met een gemockte stroom: `regie`, `regie_taak`, `sa_vraag`,
  het antwoord en de bundel, ook op mobiele breedte. Mobiel is in deze analyse niet in de browser bekeken.

## 4. De toegang van de agent

**Wat werkt.**

- **Tools.** `centraal` heeft de kernset van elf graaftools, `centraal_breed` alle 23 via `meer_tools`, en de
  connectors van het profiel (alleen wat in de beurt aanstaat). `CentraleAgent.mag` weigert de rest.
- **Subagents.** Ze kiezen uit `algemeen`, `definitie` en `duiding`, hebben geen eigen tools en geen `subagent` (één
  laag), en ronden af met het rapport.
- **Context.** De werkgebiedcontext, het onderwerp, de focus en de bronstand gaan mee in de state. Het kind krijgt het
  werkgebied en dezelfde bronnen.
- **Begrippen en annotaties** lopen via `lees_begrippen` en `lees_annotaties`: dezelfde route als de supervisor, met
  verificatie.
- **Schrijfpaden.** `agent_toegang.TOEGESTAAN` heeft `POST`, `GET` en `PATCH` op `/v1/delegaties` en
  `POST /v1/gesprekken`, en geen beslissingsroute. De taakagents en het werkgebied lopen via dezelfde `_agent` en
  `werkgebied_route` als bij de supervisor, dus met dezelfde bevestiging.

**Wat mist.**

- **Gat 4, annoteren** (het grootste gat bij `aan`). Er is geen overdracht `annoteer`, en `TAAKAGENTS` mist
  `annotatie`. Van de supervisorvorm werkte dit wel ("annoteer artikel 9 lid 1 …" → `WORKERS: annotatie`; "Annoteer
  deelvraag 2." → de annotatie-agent met de taak `deelvragen`). Ronde 2 van A2 liet zeven gesprekken die met annoteren
  beginnen bewust weg (`metingen/centrale-agent-2026-11-12-r2/ronde-2.md`), dus geen meting heeft dit gezien. *Fix:* de
  overdracht `annoteer` die de state van de annotatieroute zet (`specialist: annotatie`, `worker_plan`), dezelfde
  weigering bij meer dan één artikel (`melding_meerdere`), en `annotatie` met de taken `werkgebied` en `deelvragen` in
  `TAAKAGENTS`. Met tests in `test_centrale_agent.py` en een centrale variant van de routeringsset.
- **`laad_skill` en `lees_skill`** (§A2, niveau 2 en 3) en de skillbeschrijvingen in het voorvoegsel zijn niet gebouwd.
  Voor A6 is dat geen gat: de agentset vraagt geen skill. Voor B3 (wetsuitvoering als conceptskill) wel. Ernst: later.
- **Zelf een vraag van een subagent beantwoorden** (§A4, stap 2) kan niet. `VRAAG_AANWIJZING` verbiedt het, en
  `hervat` wordt alleen aangeroepen met `van="van de gebruiker"`. Dat was een bewuste keuze na bundel 116, maar V03
  verwacht het (`landt_bij: centraal`). Zie gat 1.
- **`delegatie_stand`** (§A4, een vervolg) is niet gebouwd. F03 vraagt hem verplicht.

**Wat hij ten onrechte mag:** niets gevonden. Een besluit staat niet op de allowlist. Een kind kan geen kind starten.
`regie_plan` en het plan met meer subagents vragen een bevestiging. Eén subagent die leest, start meteen, zoals de ADR
het wil.

## 5. Logging en observability

**Wat er is.**

- **Logregels:** `worker gekozen` (met `worker: centraal`, `subagent: true` of `deelgesprek: true`), `run gestart` (met
  `ouder_run_id`), `regie_taak` (met `ouder_run_id`, profiel, uitkomst en duur), `subagent_afloop`, `subagent_model`
  (met de terugval), `subagent_model_terugval`, `tool buiten profiel`, `tool na subagent geweigerd` en `beurt_meting`
  per run.
- **Spans:** één per node (`graph_qa.node.<naam>`) en `graph_qa.answer`.
- **Verbruik:** elk kind boekt zijn eigen verbruik bij de api, en de contextweergave telt de boom op.

**Wat ontbreekt (gat 8).**

- **Geen span voor een subagent.** De regie heeft `graph_qa.regie.taak` met `regie_id`, `ouder_run_id` en `run_id`; de
  subagent niets. Dat het kind in dezelfde trace valt als de ouder, is aannemelijk: `draai` gebruikt
  `run_coroutine_threadsafe`, en dat neemt de context van de aanroepende thread mee. Het is alleen niet geverifieerd,
  want de logs van acceptatie waren vanuit deze sessie niet te lezen (de acceptatie-MCP mist zijn
  Grafana-instelling). *Fix:* een span `graph_qa.subagent` rond `voer_uit` en `hervat`, met `delegatie_id`, `profiel`,
  `kind_run_id` en `uitkomst`, en één controle in Application Insights of ouder en kind één trace-id delen.
- **`beurt_meting` kent de vorm niet.** De route is het profiel. Een kind met `algemeen` valt daardoor in dezelfde rij
  als de specialist `algemeen` van de supervisor. `ouder_run_id`, `agentvorm` en `subagent` ontbreken, en `model` is
  altijd `settings.llm_model`, ook als het kind licht draaide. *Fix:* die drie velden erbij, en het model uit de laatste
  aanroep (`meter`).
- **Grafana** (`dashboard-keten.json`) heeft geen paneel voor de centrale agent of de delegatie. *Fix:* de panelen
  *Wachttijd* en *Tokens per beurtsoort* splitsen op `agentvorm` en `subagent`, plus een paneel *Delegatie*: kinderen
  per uitkomst, de kosten van de boom, terugvallen van het lichte model en geweigerde tools.

## 6. Configuratie en deploy

- `CENTRALE_AGENT`: de default in `main.bicep` is `uit`, en `azure-infra.yml` zet `--centrale-agent meten` alleen op
  acceptatie. De poort-guard toetst de default, de parameterkoppeling en de acceptatieconditie. Hij staat op de
  graph-qa-app én op de eval-job.
- `LLM_MODEL_LICHT`: de default is leeg, en de regel in `azure-infra.yml` staat uitgecommentarieerd (de Foundry van
  acceptatie heeft geen Haiku). `LLM_MODEL_ROUTER` staat niet in de bicep. Subagents draaien dus op `LLM_MODEL`, en
  `subagent_model` logt `geen_lichte_klasse`. **Gat 3:** A6 meet zo de kosten van delegatie met het zware model. Besluit
  vóór A6: meten zo, en het verslag zegt het; of eerst een licht model dat de straat heeft.
- `REGIE_PARALLEL` en `MAX_SUBAGENTS` (3) zijn constanten in code. `DELEGATIE_AANDEEL` geeft alleen een plafond bij
  meer dan één subagent; één subagent heeft alleen zijn eigen tokenplafond per kind.
- **`meten` tegenover `aan`.** Omzetten vraagt een wijziging van `azure-infra.yml` en een infra-`deploy` op acceptatie.
  Die raakt GraphDB: de graaf is daarna even leeg, tot de import en de graafwacht hem weer vullen. Plan dat buiten
  een meting.

**Wat er voor de gebruiker op acceptatie verandert met `aan`:**

1. Elke getypte vraag die geen route in code pakt, gaat naar de centrale agent. Er is geen supervisorstap meer, en de
   agent leest het gesprek zelf.
2. Een getypt annotatieverzoek werkt niet meer zoals nu (gat 4).
3. Opdrachten "per uitspraak" of "per artikel" gaan naar een subagent in een deelgesprek, met een vraagkaart als de
   subagent iets moet weten, en bij twee of drie opdrachten eerst een bevestiging.
4. Werk van dezelfde gebruiker in een ander gesprek (een regie of subagent) geeft een 409. De agent zegt dan dat het
   later kan (`BEZET`).
5. Een getypt antwoord op een open kaart, *Vraag Lex* bij een markering en alle klikken blijven gelijk.
6. Ook de eval-job krijgt `aan`, en meet dan de centrale vorm, tenzij hij per run `supervisor` vraagt.

Productie verandert niet: daar staat `uit`.

## 7. Kleinere punten

- *Vraag Lex* bij een markering (`modus: advies`) gaat altijd naar `duiding`, nooit naar de centrale agent. Dat is een
  route in code en past bij ADR-016. Noem het bij A7.3, want `duiding` blijft dan als profiel van een route bestaan.
- `frontend/lib/vraagLex.ts` zegt nog "gaat met het onderwerp langs de supervisor". Met `aan` is dat de centrale agent.
- De agentset noemt bij M04 en M05 het profiel `retrieval`, maar regiekinderen hebben geen profiel (`profiel: ""` op het
  gesprek). De meetmaat *juiste profielkeuze* kan daar niet scoren.
- Het eerste bericht van een beurt die via `subagent_route` (code) naar een subagent gaat, heeft geen `contextopbouw`
  (de ouder riep geen model aan). Dat is correct; de contextweergave toont dan de deelgesprekken (`Contextweergave.tsx:84`).

## Voorstel: wat vóór A6, wat vóór `aan`

**Vóór A6** (anders meet A6 iets wat bij voorbaat vastligt, of iets blinds):

1. **De agentset gelijktrekken met wat er is** (gat 1). Voor F03 (`delegatie_stand`), V03 (zelf beantwoorden), M04
   (fasen) en M04/M05 (`retrieval`): bouwen, of in de set en het meetplan vastleggen dat deze opdrachten iets meten wat
   niet gebouwd is, met een eigen regel bij de drempel ≥ 27/30. Dit is een besluit van de gebruiker.
2. **Geweigerde aanroepen zichtbaar maken** (gat 2): een `tool_execution` met `status: geweigerd`, en geen statusregel
   voor wat niet draait. Klein, alleen in graph-qa, met een test in `test_centrale_agent.py`.
3. **Het model van een subagent vastleggen** (gat 3): besluit of A6 met of zonder licht model meet, en zet
   `beurt_meting.model` op het werkelijke model.

**Vóór `aan`:** gat 4 (de overdracht `annoteer`, met een centrale routeringstest), gat 6 (de opdracht in het
deelgesprek), gat 7 (de voortgang en de stand van de delegatie in de werkplek), en een browsertest voor de
subagentstroom.

**Later:** gat 5 (`beantwoord_kaart`, vóór A7.3), gat 8 (span, velden, Grafana), `laad_skill` en `lees_skill` (B3), en
de punten van §7.
