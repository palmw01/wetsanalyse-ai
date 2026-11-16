# Testplan: de keten en E2E, inventaris en nulmeting

Soort: *plan* (16 nov 2026), een deel van het testplan van Lex Bench
([`plan-lex-bench.md`](../plan-lex-bench.md), PR #1632). Getoetst op master `01067e70`. **Alleen analyse**: er is niets
gebouwd en niets gedraaid op acceptatie. De cijfers over de poort komen uit de GitHub-runhistorie van 16 nov 2026.

Deze laag is alles wat **over de grens van één onderdeel** test: de lagen die op elkaar passen, de straat die na een
uitrol werkt, en een gebruikersreis van begin tot eind. De suites per onderdeel (api, frontend, graph-qa) hebben elk een
eigen inventaris in deze map. Dit stuk noemt ze alleen waar ze een ketenrisico afdekken.

## In het kort

- **Statisch is de keten goed bewaakt.** Het routecontract, de kruistests en een dertigtal guards maken drift tussen de
  lagen rood, ook als alleen de andere kant wijzigt. Dat is sterker dan in de meeste agentplatforms.
- **Dynamisch is er geen geautomatiseerde ketentest.** Geen enkele test laat in CI een beurt lopen van browser via BFF,
  api en graph-qa naar GraphDB en terug. De browsertests mocken `/api/**`, de graph-qa-suite mockt de api en het model,
  en de rooktest na een uitrol peilt alleen `/health`.
- **De E2E bestaat, maar als handwerk.** Het team agent-jurist en agent-gegevensspecialist doorloopt via de
  acceptatie-MCP een echte wetsanalyse. Dat is waardevol en vindt echte fouten (het verslag Rekeningafspraken: 13
  bevindingen, waarvan 3 hoog). Maar het is één run, op een gedeeld beheerdersaccount, zonder vaste verwachting. En de
  reis werd niet afgemaakt: DV2 tot en met DV5, de logs, de browser en de analistrechten zijn niet getest.
- **De overdracht tussen de stappen wordt nergens getoetst.** Bronselectie → annotatie → begrippen heeft per stap een
  eval, maar geen meting van wat een fout in stap k kost in stap k+1.
- **Foutpaden zijn per onderdeel gedekt en in de keten niet.** Een wees-run na een deploy, een lege graaf, een
  model-400 of een 429: de mechanismen hebben unittests, maar niemand ziet wat de jurist ervan merkt.
- **De poort is snel en stabiel.** Van de laatste 30 runs duurde de langste 7,7 minuten. Over 200 runs: 177 groen, 13
  rood, 10 geannuleerd, en geen enkele herhaalde poging. Flakiness is dus niet zichtbaar in de historie, maar wordt ook
  niet gemeten.

## 1. Inventaris

### 1.1 De poort (`.github/workflows/poort.yml`)

Eén verplichte check, `poort`, bovenop parallelle jobs, sinds 12 nov 2026. Er is bewust geen `paths`-filter: de job
`raakt` bepaalt zelf wat een PR raakt.

| job | wat | wanneer |
|---|---|---|
| `raakt` | bepaalt de geraakte onderdelen; skill- en profielmarkdown en `packages/bronmodel/` tellen als code | altijd |
| `guards` | de structurele toetsen (zie hieronder), seconden | altijd |
| `kruistests` | `scripts/kruistests.sh` | bij elke codewijziging |
| `mcp-tools` | typecheck, tests en `dist` van de MCP-servers | als geraakt |
| `frontend` | vitest, lint, typecheck | als geraakt |
| `frontend-browser` | Playwright, 45 scripts in 4 shards (`scripts/browsertests.mjs`), elk met een eigen `next dev` | als geraakt |
| `graph-qa` | pytest in 2 shards, met een eigen PostgreSQL; shard 1 draait ook `genereer_jas_klassen.py --check` | als geraakt |
| `api` | pytest in 3 shards, met een eigen PostgreSQL | als geraakt |
| `bwb-import` | pytest | als geraakt |
| `poort` | de aggregaat (`if: always()`): rood als een benodigde job faalt; `raakt` en `guards` moeten echt slagen | altijd |

**De guards in de workflow zelf** (shell en inline Python): geen job die op `merged == true` wacht; elk Python-image ruimt
de vendored pip-SBOM op; één Trivy-beleid, niet slapper dan HIGH; `apiExtern`, `apiTokenLogin`, `skillRegels`,
`relatieVoorstellen`, `werkplaats` en `centraleAgent` staan alleen op acceptatie aan; GraphDB blijft `external: false`
en de proxy alleen op acceptatie, alleen met token; testdossiers (`docs/acceptatie/lokaal/`) staan niet in de repo.
Daarnaast is er `geen-omgevingsgegevens.yml` op hostnamen, IP's en machinenamen.

**De pre-push-hook** (`.githooks/pre-push`) doet lokaal hetzelfde, maar alleen na `git config core.hooksPath .githooks`,
en hij is te omzeilen met `SKIP_HOOK=1`. Het geheugen van het project noemt dat een push met de hook soms stil wegvalt.
De poort is dus de enige harde grens.

### 1.2 De kruistests (`scripts/kruistests.sh`, `tests/poort/`)

Het script draait bij elke codewijziging, in de poort en in de hook:

- **het contract**: `tests/poort/` met alleen de standaardbibliotheek, 14 bestanden, ongeveer 1.300 regels;
- de tests van graph-qa, api en bwb-import die **buiten hun eigen map lezen**. Ze worden gevonden op een regex over
  `parents[n] / "frontend"` en dergelijke, niet uit een lijst. Een nieuwe kruistest wordt zo niet vergeten;
- de vitest-bestanden van de frontend die `../../tools` of `../../api` lezen.

| bestand | bewaakt |
|---|---|
| `test_routecontract.py` (+ `routeboek.py`) | elke aanroep browser → BFF → api, graph-qa → api en admin-MCP → api landt op een route die bestaat, met die methode. Statisch geparsed, met een ondergrens op het aantal gevonden aanroepen |
| `test_agent_toegang.py` | het agent-token mag precies de routes die graph-qa aanroept, en nooit een beslissingsroute |
| `test_waardensets.py`, `test_gedeelde_lijsten.py`, `test_relatiecatalogus.py` | waardensets en lijsten die aan twee kanten staan, blijven gelijk |
| `test_build_inputs.py` | poort, hook en publish kennen dezelfde build-inputs van graph-qa (skills, profielen) |
| `test_poort_parallel.py` | shards verliezen geen testbestand, elke job staat in `needs` van `poort`, geen `paths`-filter |
| `test_uitrolpoort.py` | de uitrolpoort staat één keer, in de composite action, en houdt de rooktest |
| `test_deploy_namen.py`, `test_kennisgroepen_uitrol.py`, `test_2fa_herstel.py`, `test_bronnenwacht.py` | de vorm van `azure-infra.yml`, `opruimen` en de schema-workflows |
| `test_vormen.py` | regels uit de CLAUDE-bestanden die in code kunnen staan (o.a. `metTrace`) |

**Wat dit niet is.** Het contract toetst dat een route *bestaat*, niet dat de vorm van de payload past. Een veld dat de
api hernoemt en de BFF doorgeeft, of een SSE-event dat graph-qa anders noemt, gaat erdoor. Dat vangen alleen de
waardensets die er expliciet in staan.

### 1.3 Na een uitrol

- **De uitrolpoort** (`.github/actions/wacht-op-revisie`, `wacht.sh`): wacht tot de nieuwste revisie van elke app
  `Running`, `RunningAtMaxScale` of `ScaledToZero` is, en doet dan de **rooktest** `/api/health?keten=1` op de frontend:
  12 pogingen met 15 s ertussen. Gebruikt door de vier publish-workflows, `promote.yml`, `rollback.yml` en
  `azure-infra.yml`.
- **De rooktest** (`frontend/app/api/health/route.ts`) peilt `api/health` en `graph-qa/health`, met 10 s time-out voor een
  koude start, en geeft 503 als een van beide niet antwoordt. Een frontend van vóór de rooktest krijgt een waarschuwing
  in plaats van een fout (N-1).

  **Wat hij niet toetst:** dat graph-qa GraphDB bereikt, dat de repository `inning` gevuld is, dat het model antwoordt,
  dat de api de database bereikt (als `/health` dat niet doet), en dat een sessie werkt. Een straat met een lege graaf
  of een verlopen modelsleutel komt groen door de poort.
- **De bouwwacht** (`bouwwacht.yml`, elk kwartier): vergelijkt het revisielabel van `:latest` met master, dispatcht bij
  achterstand, en herstart een mislukte `deploy`-job hoogstens twee keer. 100 van de laatste 100 runs groen. Hij meet
  of het *image* klopt, niet of de straat *werkt*.
- **De importpoort** (bwb-import, `dekking.poortbesluit`): de graph wordt offline gebouwd en tegen de bron gemeten vóór de
  `PUT`. De regel is *vervang nooit door minder*, met `BWB_MIN_DEKKING` 0,995. Bij een weigering eindigt de job met
  exitcode 2 en wordt hij rood. Dit is de enige ketenpoort op de *inhoud*: de wettekst die Lex citeert.
- **De graafwacht** (elk kwartier, `--alleen-bij-verlies`): importeert alleen als de graaf weg is. Het paneel *Graaf weg*
  in Grafana toont dat.
- **De bronnenwacht** (`bronnenwacht.yml`, dagelijks): de live-tests van de connectors tegen de echte diensten, buiten de
  poort, met een aparte melding `DIENST ONBEREIKBAAR`.

### 1.4 De acceptatie-MCP en het team

`tools/wetsanalyse-acceptatie-mcp/` bedient de webapp **via de BFF**, met een sessie uit een accounttoken. Daardoor
gelden sessie, rol, eigenaarschap en tokenbudget zoals voor een gebruiker. Daarnaast heeft hij tools voor de
beoordeling, buiten de BFF: `bron_lezen` (de officiële XML), `graaf_lezen` (alleen-lezen SPARQL via de proxy),
`logs_zoek` (vaste queries via Grafana) en een logboek dat alleen kan aanvullen.

- **Het scenario** [`docs/acceptatie/wetsanalyse-e2e.md`](../../acceptatie/wetsanalyse-e2e.md): negen stappen, van het
  werkgebied tot en met de bewijzen in de logs, met acht **vastliggende controles** (citaat letterlijk op de plek van
  het anker, juiste `bronreferentie`, klasse uit de dertien, dekking per deelvraag, geen stille beslissing, elke omweg
  in het logboek). Plus een inhoudelijk oordeel op een steekproef.
- **De briefing** [`briefing-team.md`](../../acceptatie/briefing-team.md) en de agents `agent-jurist` en
  `agent-gegevensspecialist` (`.claude/agents/`). Ze hebben geen `Write`, `Edit` of `Bash`, en geen admin- of graaf-MCP.
  Ze nemen echte beslissingen op acceptatie.
- **Daarnaast**: [`connectors-meting.md`](../../acceptatie/connectors-meting.md) en
  [`kennisgroepen-meting.md`](../../acceptatie/kennisgroepen-meting.md), vragensets per connector.
- **Het enige verslag in de repo**: [`verslag-e2e-rekeningafspraak-2026-11-16.md`](../../acceptatie/verslag-e2e-rekeningafspraak-2026-11-16.md).
  1,25M Lex-tokens. Stap 1 helemaal, stap 2 alleen DV1, stap 3 onder één deelvraag (140 voorstellen), stap 4 vier
  begrippen. Niet getest: de browser, de analistrechten, de logs en de vergelijking bron–graaf (de toegang ontbrak),
  DV2–DV5, ongeveer 50 open elementen, de relaties, de commando's en *Aanpassingen*. Bevinding V-1: een agent kan
  stap 2–5 niet in één context afmaken, omdat de antwoorden te groot zijn (B-1).

De rendering test deze MCP bewust niet. Dat doet Playwright, op een gemockte BFF.

### 1.5 De metingen als bewijsvorm

[`docs/architectuur/metingen/`](../metingen/README.md) heeft ruim 80 meetmappen en een logboek met per regel de datum, de
code, de uitkomst en de gegevens. Meetbestanden worden achteraf niet gewijzigd. Het meetregime is licht: één run, een
gerichte set en een plafond, en drie runs alleen bij twijfel.

Als **ketenbewijs** is dit sterk op herleidbaarheid (commit, bundel, run-id's, verbruik uit het `meting`-event) en zwak
op drie punten:

- **Geen vaste verwachting voor de keten.** Bijna elke meting meet één route (de centrale agent, één connector, de
  bronselectie, de begrippen). Geen meting volgt één casus door alle stappen.
- **Geen juridisch oordeel.** De referentieset is *provisional*, met 0 casussen `adjudicated`. Dat staat er zelf bovenaan,
  en dat is eerlijk.
- **De straat verandert onder de meting.** De graaf, de modelversie en andere runs op het gedeelde account (*het gedeelde
  account telde ~200k van een andere run mee*, 16 nov) zijn niet vastgelegd zoals de code. Het runrecord van Lex Bench
  (§6 van het plan) lost dat op voor de bronselectie.

### 1.6 De eval-job op Azure

`<appName>-eval` (`main.bicep`) draait in de omgeving zelf, omdat GraphDB intern is. Hij wordt handmatig gestart
(`azure-infra` → `eval`), want elke run kost tokens. Eerst de **retrieval-smoke**: elke graaftool één keer, 0 tokens,
met rc=1 bij een fout. Dan drie runs `--annotatie` en drie runs `--gesprek` (die laatste tellen niet mee in de exitcode).
Hij schrijft niets naar de api, zodat er geen eval-annotaties tussen het werk van juristen komen.

**De retrieval-smoke is de enige geautomatiseerde test tegen de echte graaf.** Hij hangt alleen aan de dure eval-job, en
niet aan een uitrol of de graafwacht.

## 2. Scenario's van begin tot eind

**Legenda.**

- *auto*: een geautomatiseerde test over meer lagen.
- *delen*: elke laag apart getest, met mocks.
- *hand*: de E2E via de acceptatie-MCP.
- *meting*: een eval of meetmap.
- *–*: niets.

| reis | dekking | wat er is | wat ontbreekt |
|---|---|---|---|
| Werkgebied samenstellen (activiteit 1, vraagkaarten) | delen, hand | `test-werkgebied-intake.mjs`, `test-dossier-aanvullen.mjs`, de stapmachine in graph-qa, E2E stap 1 helemaal | een geautomatiseerde reis: kaart → *Aanmaken* → werkgebied in de api → paneel |
| Bronselectie per deelvraag | delen, meting, hand (alleen DV1) | `bronselectie_eval` offline op zes sets, `test-bronselectie*.mjs`, de stand per deelvraag in de api | alle deelvragen afronden, *Hoe wil je verder?*, en herladen of een tussenvraag midden in de reis |
| Annoteren en beoordelen | delen, meting, hand (één deelvraag) | de annotatieketen met `golden_annotatie`, de eval-job (3 runs), `test-werkgebied-annoteren.mjs`, de projectie naar de graaf (`test_graaf_projectie_v2.py`) | de beslissing van de jurist die terugkomt in de laag én de graaf, geautomatiseerd; bulkbesluit-foutpaden (B-5) |
| Begrippen tot en met de export | delen, meting, hand (vier begrippen) | `begrippen_eval`, `test_begrip_projectie.py`, `test-begrippen*.mjs`, Turtle-export in de api | export ⇔ graaf ⇔ kaart in één toets; opvolger na herannotatie in de keten; generieke begrippen over twee werkgebieden |
| Afleidingsregels | – | gereserveerd in het artefactmodel | hoort nog niet tot de functionaliteit |
| Een vraag met een connector | delen, meting | neps per connector in graph-qa, de bronnenwacht live, de iteratiemetingen (30 vragen per connector) | een connector die uitvalt *tijdens* een beurt, gezien vanuit de werkplek |
| Subagents (centrale agent, ADR-016) | delen, meting, hand | de agentset (30 opdrachten), `test-subagent.mjs`, de A6-tests | een vaste test op de bevinding B-3 (de duiding van de centrale agent die niet in de bron staat) |
| Inloggen, 2FA, registratie | delen | `api/tests/test_auth.py`, `test_users_auth.py`, `test_registraties.py`, `test_herstel_2fa.py` | **geen browsertest van de login**: de MCP mag geen wachtwoord, de browsertests mocken de sessie. Auth.js ⇔ api ⇔ TOTP is nergens samen getoetst |
| Rollen (analist tegenover beheerder) | delen | de rolcontroles in de api | de E2E draait als beheerder: analistrechten zijn nooit van begin tot eind getest |
| Uitrol | auto | de uitrolpoort met de rooktest, de bouwwacht | de rooktest bereikt GraphDB en het model niet |
| Rollback | auto (vorm) | `rollback.yml` gebruikt dezelfde poort; `maxInactiveRevisions: 5` | nooit geoefend: er is geen run die een rollback tot het einde toetst, en de N-1-compatibiliteit van de api met de database na een rollback is niet getoetst |
| Graaf herstellen na verlies | auto (deels) | de graafwacht, de importpoort, *Graaf weg* in Grafana, de tekst van Lex bij `Repository inning doesn't exist` (`test_tools.py`) | de jurist die midden in een reis een lege graaf treft |

### 2.1 Ontbrekende scenario's, met hun foutpaden

Elk scenario hieronder is een reis plus een verstoring. De verwachting is wat de jurist ziet en wat er *niet* mag
gebeuren. Ze zijn generiek: ze gelden voor elke casus.

1. **K1 – De graaf is leeg midden in een reis.** Bronselectie bij DV2 terwijl GraphDB net herstart is.
   - *Verwacht*: Lex zegt dat de wettekst tijdelijk weg is, er komen geen voorstellen zonder bron, de stand van DV1
     blijft, en na de graafwacht gaat het verder.
   - *Mag niet*: een bron uit het geheugen, een stille lege lijst, of een annotatie die opnieuw door het model gaat omdat
     de laag er even niet is (`bron_annotatie.py` zegt dat de api leidend is: dat moet in de keten blijken).
2. **K2 – Een deploy van graph-qa halverwege een beurt.** De runstore kent wezen (`test_runstore_postgres.py`: een run
   zonder hartslag eindigt met een fout en een `done`).
   - *Verwacht*: de werkplek toont dat de beurt is afgebroken, de vraag staat nog in het gesprek, een nieuwe beurt kan
     direct, en er is geen half artefact (een half annotatievoorstel, een half werkgebied).
   - Ook voor een kindgesprek van een subagent: de ouder krijgt een rapport *mislukt*, geen eeuwige wachttijd.
3. **K3 – Een model-400 of een 429.**
   - *Verwacht*: een begrijpelijke fout in het gesprek, geen kale tekst van de provider, geen tokens die dubbel tellen in
     het verbruik, en een herhaling alleen waar het beleid dat zegt (`test_http_beleid.py`).
   - Bij een 429 midden in een annotatie van tien bepalingen: wat al klaar is, blijft staan, en de rest is zichtbaar als
     niet gedaan.
4. **K4 – Een gedeeld account.** Twee sessies (twee agents, of een agent en de gebruiker) op hetzelfde account en hetzelfde
   werkgebied.
   - *Verwacht*: een tweede run op hetzelfde gesprek botst netjes (dat toetst de runstore al), een besluit van de een
     overschrijft dat van de ander niet stil, het verbruik is per run te scheiden, en bulk wissen raakt alleen wat
     de sessie zelf maakte.
   - Dit is in november tweemaal misgegaan: een meting telde ~200k van een andere run mee, en bulk verwijderen raakte een
     gesprek van de gebruiker.
5. **K5 – Het tokenbudget raakt op midden in een reis.** De annotatie van een deelvraag stopt op het plafond. *Verwacht*:
   wat klaar is blijft, de melding noemt het budget, en er is geen half artefact.
6. **K6 – Een connector die uitvalt of traag is.** LiDO met 211 s latentie (gemeten 12 nov). *Verwacht*: het antwoord
   noemt welke bron niet antwoordde en vult niets aan uit het geheugen.
7. **K7 – Herladen en een tweede tabblad.** De bronselectie zegt zelf dat herladen niets breekt omdat de stand bij de api
   staat. Toets dat in de keten: herladen tijdens een lopende beurt, en hetzelfde werkgebied in twee tabbladen.
8. **K8 – Inloggen tot en met de eerste beurt.**
   - Zelfregistratie → goedkeuring door een beheerder → eerste login → 2FA instellen → beurt.
   - Een beheerder zonder 2FA ziet het beheer dicht.
   - Na een rollback van de api blijft een bestaande sessie werken, of krijgt de gebruiker een nette nieuwe login.
9. **K9 – Een rollback onder last.** Een beurt loopt, en de frontend en graph-qa gaan een revisie terug.
   - *Verwacht*: de rooktest groen, de lopende beurt als K2, en het gesprek leesbaar in de oude versie (N-1).
10. **K10 – Een analist tegenover een beheerder.** Dezelfde reis als analist. *Verwacht*: geen beheerroute, wel alle
    stappen van de methode, en het verbruik binnen het budget van de rol.

## 3. De ketentest: de overdracht tussen de stappen

**Wat er nu is.** Elke stap heeft een eigen eval op een eigen set:

- **bronselectie**: `bronselectie_eval` op de referentieset bronselectie;
- **annotatie**: `run_eval --annotatie` op `golden_annotatie*.jsonl`;
- **begrippen**: `begrippen_eval` op de referentieset begrippen.

De sets beschrijven **niet dezelfde casussen**. Er is dus geen enkele plek waar de uitvoer van stap k de invoer van stap
k+1 is en beide een verwachting hebben. Ook de E2E meet de overdracht niet. Zij laat de reis wel lopen, maar zonder
verwachting per stap. Wat daar misgaat, staat als bevinding, niet als verlies per stap.

**Waar de overdracht stil kan breken** (de naden):

| naad | wat er overgaat | wat er nu bewaakt | wat er niet bewaakt |
|---|---|---|---|
| werkgebied → bronselectie | dossier, deelvragen, zoekbereik | de dossiervlaggen in de eval, `werkgebied_context.py` | of een wijziging van het dossier de bronselectie zichtbaar ververst (*opdracht bronnen na dossierwijziging*) in de keten |
| bronselectie → annotatie | de opgenomen bronnen per deelvraag, op lidniveau | `bevestigd` met het aantal | dat precies de opgenomen bronnen geannoteerd worden, niet het hele artikel of een uitgesloten lid (B-12: artikel- tegenover lidniveau) |
| annotatie → begrippen | de passages met klasse en anker | `test_begrip_projectie.py`, de herbeoordeling | dat een gemiste of verkeerde klasse in stap 2 een gemist begrip in stap 3 wordt, en hoeveel |
| annotatie → graaf | de laag als W3C-annotatie | de projectie (`test_graaf_projectie_v2.py`), de controle bij de api | of de laag in de graaf na een beslissing gelijk is aan Postgres, als toets in de keten (nu alleen als handwerk in E2E stap 5) |
| begrippen → export | NL-SBB, Turtle | de projectie en de conformiteit | export ⇔ graaf ⇔ kaart in één vergelijking |
| begrippen → afleidingsregels | – | – | nog geen functionaliteit; het formulier kan wel al vast |

**Hoe de ketentest eruitziet.** Dit sluit aan op §8 van het plan Lex Bench. Per casus en per stap k twee runs:

- `k|eigen`: op de uitvoer van Lex uit stap k−1;
- `k|vast`: op de vastgestelde verwachting van stap k−1.

Het verlies door de overdracht is `score(k|vast) − score(k|eigen)`. Het rapport toont één rij per stap.

Concreet, en zo veel mogelijk zonder model:

1. **Eén keten-casusformaat** dat schema 4 van Bench uitbreidt. Per casus:
   - `bronnen[]` (al in schema 3);
   - `annotaties[]` (in de vorm van `golden_annotatie`, op dezelfde bron-IRI's);
   - `begrippen[]` (in de vorm van de referentieset begrippen, gekoppeld aan de ankers van `annotaties[]`).

   Het formaat kopieert niets uit de bestaande sets. Het wijst ernaar, zoals het manifest van Bench.
2. **Een adapter per naad**, in `eval/`, die de uitvoer van stap k−1 omzet naar de invoer van stap k. Dat is de code die
   de keten op acceptatie ook doet. De adapter is deterministisch en heeft unittests.
3. **Stap 1 → 2 offline**: de bronnen die `--intake` voor de casus kiest, gaan als werkvoorraad naar de annotatieketen.
   Die draait in de eval-job (het model is nodig). Daarnaast loopt dezelfde run op `bronnen[]` uit de verwachting.
   Gemeten wordt de ankerdekking op `annotaties[]`.
4. **Stap 2 → 3 zonder model**: de begrippenketen is deterministisch (ADR-004). Ze draait op de eigen annotaties en op
   `annotaties[]`, en wordt gescoord met BCubed en `samengevoegd_verschillend`. Deze naad kost 0 tokens en kan in de
   poort, op opnames.
5. **Een naadtoets per overgang, in de poort, zonder model**: een kleine vaste casus (twee bepalingen, drie annotaties,
   één begrip) die de werkelijke overgangen in api en graph-qa doorloopt:
   - opnemen in de bronselectie;
   - de werkvoorraad van de annotatie;
   - een beslissing;
   - de projectie naar de graaf (op een in-memory rdflib-store);
   - een begripskoppeling;
   - de Turtle-export.

   Elke stap toetst wat de volgende verwacht (ids, lidniveau, ankers). Dit is de ontbrekende *dynamische* tegenhanger
   van het routecontract.

## 4. De kwaliteit van de testinfrastructuur

- **De doorlooptijd van de poort.** Van de laatste 30 runs duurde de mediaan ongeveer 5 minuten en de langste 7,7 (vóór
  12 nov 23–28 minuten). Dat is goed. De browserregressie start per shard een eigen `next dev`, en dat blijft de
  traagste job. Bij meer browserscripts zijn meer shards de knop. De verdeling staat op één plek.
- **Flakiness.** Over 200 poortruns: 177 groen, 13 rood, 10 geannuleerd, en **0 herhaalde pogingen**. Er is dus geen spoor
  van "opnieuw draaien tot het groen is", maar ook geen meting.

  Over alle rode runs sinds de parallelle poort faalde het vaakst `graph-qa (2/2)` (13 keer, soms samen met andere jobs),
  dan `graph-qa (1/2)` (6) en `frontend-browser (4/4)` (4). Of dat echte fouten of wisselvallige tests waren, is uit de
  historie niet af te lezen zonder de logs.

  Een rode run die bij een volgende push vanzelf groen
  wordt, valt nu niet op. De browsertests zijn al eens wisselvallig geweest (PR #888). De poort leunt verder op
  externe diensten bij het installeren: het spaCy-wiel van GitHub (de bronnenwacht zegt het zelf). Een storing daar maakt
  elke PR rood, zonder dat er iets mis is met de code.
- **De testdata op het gedeelde account.**
  - Alle E2E- en meetruns draaien op één beheerdersaccount, dat ook de gebruiker gebruikt.
  - Op acceptatie wordt niets verwijderd, dus de data groeit: 480 gesprekken werden in november met de hand opgeruimd.
    Opruimen per werkgebied of per ouder ontbreekt (O-1).
  - De gevolgen:
    - het verbruik van een meting is besmet door andere runs;
    - de inventaris van een werkgebied kan elementen van een eerdere run tonen;
    - het generieke begrippenkader groeit met testbegrippen die in de volgende run als bestaand opduiken;
    - analistrechten worden nooit getoetst.
- **De herhaalbaarheid.**
  - Goed waar er geen model is: offline evals op opnames van de graaf (`graafantwoorden.json`), en de deterministische
    begrippenketen.
  - Slecht voor de E2E, om drie redenen:
    - de casus staat lokaal en gitignored, dus niemand anders kan de run herhalen;
    - de straat verandert tussen runs (graaf, model, data op het account);
    - er is geen vaste verwachting, alleen een oordeel.
  - Annotatieruns verschillen sterk (geel 38–77 % op dezelfde bepaling). Het meetregime weet dat, maar een eenmalige
    E2E is daardoor een anekdote.
- **De traceerbaarheid van eis naar test naar uitkomst.**
  - De keten *uitkomst → code* is goed: de meetmappen noemen de commit en de bundel, de E2E noemt `trace_id`'s en
    `run_id`'s, en `logs_zoek` volgt de keten op één trace-id.
  - De keten *eis → test* ontbreekt. De eisen staan in CLAUDE.md, de ADR's, PLAN.md en het scenario (de acht
    vastliggende controles). Geen test of meting verwijst ernaar met een id, en geen overzicht zegt welke eis door welke
    test gedekt is.
  - De bevindingen van een E2E (B-1 tot en met B-13) gaan als PR met een test de repo in, maar de koppeling *bevinding →
    test → hermeting* is niet vastgelegd.

## 5. Voorstellen, op volgorde van prioriteit

Elk voorstel is generiek: het geldt voor elke casus, en niets is maatwerk voor één werkgebied.

1. **De rooktest dieper maken, zonder model.** Breid `?keten=1` uit:
   - graph-qa meldt of GraphDB antwoordt en of `inning` meer dan nul regelingen heeft (één `ASK`, de query van de
     graafwacht);
   - de api meldt of de database antwoordt.

   Dan komt een straat met een lege graaf niet meer groen door de uitrol. Draai de retrieval-smoke (0 tokens) als
   aparte job na `vul-graaf` en na de graafwacht, niet alleen in de dure eval-job. *Klein, direct nut, sluit het grootste
   gat in §1.3.*
2. **Een naadtoets in de poort, zonder model** (§3, punt 5). Eén vaste minicasus die de echte overgangen in api en
   graph-qa doorloopt, met PostgreSQL uit de bestaande service-container en een in-memory graaf. Dit is de dynamische
   tegenhanger van het routecontract en vangt payload-drift die het contract niet ziet.
3. **Een vast testaccount en een eigen ruimte op acceptatie.**
   - Een analistaccount voor de E2E en Bench, los van het account van de gebruiker. Alleen de gebruiker kan dat
     aanmaken.
   - Een naamconventie (`acc-test-…`, `Bench …`) die elke run draagt.
   - Een opruimroute per werkgebied of per ouder (O-1), die alleen wat de run maakte archiveert of wist, nooit iets
     anders.

   Daarmee worden het verbruik, de rechten en de opruiming per run zuiver. *Vraagt een besluit van de gebruiker.*
4. **De E2E als vaste reis, niet als eenmalige run.**
   - Een **ketencasus** in de repo, in eigen woorden: het formaat van §3, punt 1.
   - Vaste stappen met een **verwachting per stap**: eigenschappen, geen exacte tekst.
   - Een rapport in een vaste vorm, met een regel in het meetlogboek.

   Het lokale dossier blijft voor wat interne namen draagt. Los eerst B-1 (compacte antwoorden) op, anders haalt een
   agent stap 2–5 niet (V-1). Dit is het startpunt van de ketentest uit §8 van het plan Lex Bench.
5. **De foutpaden K1–K10 als scenario's.**
   - K1, K2, K3 en K5 kunnen grotendeels in de graph-qa-suite, met een SSE-kijker die de werkplek nabootst: verstoring
     inspuiten, en toetsen wat er in het gesprek en in de api staat.
   - K4, K7 en K9 vragen de straat, en draaien als onderdeel van de vaste reis van punt 4, met akkoord.
   - K8 vraagt een browsertest van de login tegen een echte api (zie het stuk over de frontend).
   - Uitgewerkt in [`docs/acceptatie/foutpaden.md`](../../acceptatie/foutpaden.md); K1, K2, K3 en K5 staan in
     `tools/graph-qa/tests/test_foutpaden_keten.py`.
6. **Een ketenmatrix: eis → test → uitkomst.** Eén bestand (`docs/architectuur/testplan/matrix.md`, of een kolom in de
   Bench-voortgang) met per eis:
   - een id;
   - de bron (CLAUDE.md, ADR, scenario);
   - de test of meting die hem dekt;
   - de laatste uitkomst.

   Zo blijft zichtbaar wat niet gedekt is. Bevindingen uit een E2E krijgen een id dat in de test en in de hermeting
   terugkomt. Een poorttest bewaakt alleen dat elke id ergens heen wijst.
7. **Flakiness meten in plaats van aannemen.** Een wekelijkse workflow (zoals de bouwwacht) die de poortruns van die week
   leest. Hij telt de rode runs die bij dezelfde commit later groen werden, per job en per testbestand. Verder: het
   spaCy-wiel en de Playwright-browser uit een cache of een eigen artefact, zodat een externe storing de poort niet rood
   maakt.
8. **Een rollback oefenen.**
   - Eén keer per release-cyclus op acceptatie: een rollback van api, graph-qa en frontend naar N-1, met de rooktest en
     een lopende beurt (K9).
   - Een poorttest die toetst dat een migratie van de api N-1-compatibel is: de oude code op het nieuwe schema.

   Nu is de rollback alleen in vorm getoetst.

Wat bewust **niet** wordt voorgesteld:

- een live E2E in de poort: elke PR zou dan van de straat en een model afhangen, en dat is het argument van de
  bronnenwacht;
- een drempel op een score: dat staat in de grenzen van het plan Lex Bench;
- verwijderen op acceptatie zonder akkoord.
