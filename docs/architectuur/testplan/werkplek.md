# Testplan, laag werkplek (`frontend/`): inventaris en nulmeting

Soort: *inventaris* (16 nov 2026), deel van het testplan bij [Lex Bench](../plan-lex-bench.md) (PR #1632). Getoetst op
master `01067e70`. **Alleen analyse: er is niets gebouwd en geen test gewijzigd.** De andere lagen (graph-qa, api,
keten/E2E) hebben elk een eigen inventaris naast deze.

Hoe gemeten:

- de bestanden zelf gelezen en geteld (`it(`/`it.each(`, bronlezers, mocks);
- één gerichte vitest-run lokaal: 40 bestanden (beurt en SSE, BFF-proxy, auth, alle vormtests in `app/`), 294 tests,
  groen in 6,4 s;
- de CI-historie van `poort.yml`: 200 runs van 13 tot 16 nov 2026, waarvan 50 de frontend raakten (50 frontend-jobs en
  200 browsershards);
- de browsertests zelf niet lokaal gedraaid: dat vraagt een `next dev` naast de laptop die al krap zit, en de CI-cijfers
  zeggen genoeg over doorloop en stabiliteit.

## 0. De stand in het kort

| Laag | Omvang | Toetst |
|---|---|---|
| vitest, logica (`lib/*.test.ts`, `lib/graaf/`) | 93 + 6 bestanden, ~1.100 tests (een `it.each` telt als één) | vooral **gedrag** van pure helpers |
| vitest, BFF en auth (`app/api/**`, `auth.config`, `proxy*`) | 8 bestanden, ~82 tests | **gedrag** van de BFF-proxy, de routegate, CSRF en de 2FA-plicht |
| vitest, vorm (`app/*.test.ts`, 6 in `components/`) | 28 + 6 bestanden, ~140 tests | **vorm**: regex over de bron (één component per patroon, stijl, tokens) |
| browserregressie (`scripts/test-*.mjs`) | 46 scripts, ~12.000 regels | **gedrag** op de echte Next-UI, met `/api/**` gemockt per script |
| statisch contract (`tests/poort/test_routecontract.py`, `test_vormen.py`) | buiten `frontend/` | elke aanroep browser → BFF → api landt op een route met die methode; elke upstream-`fetch` draagt `metTrace` |

De sterke kant: de beurt en de SSE-stroom (breuk, opnieuw aanhaken, volgnummer, gat, stilval, 409, 429) zijn op
logicaniveau grondig en deterministisch getest. Elke browsertest faalt op een paginafout. De poort draait alles parallel
in ~4,5 minuut, en in 50 runs zat geen enkele wisselvallige fout.

De zwakke kant, in volgorde van gewicht:

1. **Er zijn geen componenttests.** De 190 componenten (28.500 regels) en de hooks (`useBeurt`, `useOnbewaardBewaker`,
   …) worden alleen geraakt door de browsertests en door regex over hun bron. Er is geen DOM-omgeving in vitest.
2. **De mocks hebben geen contract op de vorm.** 45 van de 46 browserscripts hebben elk een eigen nep-api voor
   `**/api/**`. Het routecontract bewaakt pad en methode, maar niet de vorm van het antwoord. 29 scripts beantwoorden een
   onbekend pad stil met `200 {}` of `200 []`.
3. **De SSE-mock lijkt niet op de echte stroom.** De helper `sse()` staat 18 keer gekopieerd, scheidt frames met `\n\n`
   (sse-starlette gebruikt `\r\n`), en levert de hele stroom in één keer, vanaf `seq` 0. `vanaf=` wordt nergens
   gelezen. Breken en hervatten van de stroom wordt in de browser dus nooit getoetst.
4. **Een browsertest zweeft los.** `test-paneelkop.mjs` (231 regels, met axe) staat niet in `test:browser`, dus hij draait
   nergens, ook niet in de poort.
5. **Een paar beveiligingspaden hebben geen test**: de eigenaarscontrole bij het starten van een run
   (`app/api/annotatie/run/route.ts`), de allowlist van de annotatie-catch-all, de `jwt`-callback in `auth.ts`
   (intrekken via het accounttoken) en `lib/trace.ts` zelf.

## 1. Inventaris

### 1.1 vitest: logica in `lib/`

Alle tests draaien in `environment: "node"` zonder DOM (`vitest.config.ts`). `server-only` is een stub, zodat
server-helpers te testen zijn. Per onderwerp (aantal tests tussen haakjes):

**De beurt en SSE**: `api` (40), `beurtStroom` (10), `beurtLus` (11), `beurtFase` (6), `beurtVerzoek` (5), `lopendeRun`
(17), `runStanden` (14), `agentEvents` (3), `statusCache` (4), `delegatie` (19), `denkproces` (4), `waarom` (14).
*Gedrag, sterk.* De parser splitst frames ook met `\r\n` en slaat een misvormd event over. Een stroom zonder `done` is
een breuk, geen einde. Stilval wordt verworpen, het volgnummer gaat terug voor het aanhaken, een gat wordt benoemd, en
een 409 draagt het `run_id` mee. Een 429 met `budget_op` geeft een herkenbare fout, 502 en 504 elk een eigen fout, en de
401 van de 2FA-route is een afwijzing. In de lus: wachten met oplopende wachttijd, een plafond, 500 breuken zonder
recursie, een venster dat verdwijnt, en precies één keer in rust. `lopendeRun` herkent een run die gewoon klaar is, een
die verdween door een herstart, en een die niet meer van jou is. Dit is het best geteste deel van de werkplek.

**Artefacten**: `artefact` (18), `artefactVersie` (4), `artefactMarkdown` (7), `kaartVoorstel` (14), `paneelTabs` (8),
`zijpaneel` (3), `revisies` (5), `tekstverschil` (6). *Gedrag.*

**Werkgebied en intake**: `werkgebied` (17, met de allowlist `isWerkgebiedRoute`/`isGeneriekRoute`),
`werkgebiedPaden` (6), `werkgebiedOverzicht` (3), `werkgebiedAnnoteren` (8), `vraagkaart` (27), `conceptVraag` (3),
`deelvragen` (8), `dekking` (5). *Gedrag.*

**Bronselectie en bronnen**: `bronselectie` (10), `bronKandidaten` (9), `bronnenPerDeelvraag` (1), `bronnen` (21),
`bronPlaats` (3), `bronStuk` (6), `bronWeergave` (3), `herkomst` (15), `citaties` (24), `wetstructuur` (13),
`bepalingDetail` (6, met een drift-toets op het contract van de api). *Gedrag.*

**Begrippen**: `begrippen` (11), `begripVoorstellen` (17), `begripTermen` (8), `begripRelaties` (4), `begripGraaf` (4),
`begrippenOverzicht` (4), `herbeoordeling` (5). *Gedrag.*

**Annotatie en de graaf**: `annotatie` (50, met dezelfde gevallen als `api/tests/test_slotregel_drift.py`),
`annotatieNode` (6), `annotatieNodeAdapter` (26), `annotatieOverzicht` (22), `annotatieRelaties` (11), `markeerlaag`
(24), `markering` (12), `selectie` (14), `samenhang` (8), `terugval` (3), `jasRelaties` (2), `gedeeldeLaag` (9), en
`lib/graaf/*` (66). *Gedrag.*

**Connectors**: `connectorLijst` (8), `connectorsMenu` (18), en `app/api/connectors/route.test.ts` (6). *Gedrag.*

**Commando's en Vraag Lex**: `commandos` (9), `vraagLex` (13). *Gedrag.*

**Contextweergave**: `contextweergave` (24), `contextdelen` (4). *Gedrag.*

**Instellingen, aanpassingen, werkplaats**: `instellingen` (17), `aanpassingen` (7), `catalogus` (6), `modelkeuzes` (5),
`werkplaats` (26), `tooiThemas` (2). *Gedrag, deels vorm* (de bestanden met `bron=…` lezen ook bronbestanden).

**Gesprekken en sidebar**: `geschiedenis` (6), `gesprekGroepen` (8), `gesprekkenOpruimen` (3), `verwijderen` (3).
*Gedrag.*

**Rondleiding**: `rondleiding` (81, 710 regels). *Gedrag en vorm.* Het grootste testbestand van de werkplek, voor een
functie die buiten de kern ligt.

**Infrastructuur en randen**: `url` (33), `csp` (6), `clientIp` (3), `logger` (4), `sessie` (4), `tokenbudget` (15),
`onbewaard` (6), `uiSpoor` (11), `datum` (6), `popover` (10), `reeks` (16), `teststrook` (8), `overzicht` (10),
`disclaimer` (4), `begroeting` (8), `zonderEmoji` (3), `bewerken` (2). *Gedrag.*

**Zonder eigen test** (27 modules in `lib/`): onder meer `useBeurt` (220 regels, de hook van de beurt), `server`
(accountstatus, tokenstatus), `trace` (de `traceparent`), `config` (de tokens), `useOnbewaardBewaker`, `opslag`,
`authCookies` en alle andere `use*`-hooks. Hun logica staat voor een deel in geteste helpers (`beurtLus`, `onbewaard`),
maar de lijm zelf (welke helper wanneer, met welke staat) heeft geen test buiten de browser.

### 1.2 vitest: BFF en auth

- `app/api/_lib/proxy.test.ts` (16): 504 bij een time-out, 502 bij een onbereikbare api, het abort-signaal, streamen
  vóór het einde van de upstream, geen `content-encoding` doorgeven, 204 zonder body, graph-qa met zijn eigen token. Ook
  de 2FA-plicht: een beheerder zonder 2FA wordt tegengehouden met een leesbare code, het account dat niet te controleren
  is gaat dicht, en een sessie uit een accounttoken valt buiten de plicht. *Gedrag, sterk.*
- `auth.config.test.ts` (36): CSRF op `Origin` (ook `x-forwarded-host`, een onparseerbare origin en zonder header), de
  disclaimer-gate, de rolgate op beheer en de beheer-tabs, 401 in JSON op de BFF in plaats van een omleiding.
  *Gedrag.*
- `proxy.gate.test.ts` (6): de echte `proxy.ts` met de CSP en het nonce. `proxy.test.ts` (4) leest het matcher-patroon
  uit de bron. *Gedrag en vorm.*
- `app/api/gesprekken/groep/[groep]/route.test.ts` (5): de volgorde bij bulk-wissen (eerst de ids, dan het geheugen,
  dan de api). `app/api/health/route.test.ts` (5), `venstertel.test.ts` (4). *Gedrag.*

### 1.3 vitest: vormtests

`app/*.test.ts` (28 bestanden, ~100 tests) en `components/**/*.test.ts` (6). Ze lezen `.tsx`-bronnen en toetsen met
regex: één `Melding`, één `Uitklap`, één `LaadStand`, één `PaneelKop`, één weg naar het klembord, knoppen volgens het
stijlblad (`knoppen`, 17), tokens in plaats van losse kleuren, uitlijning op smalle schermen (`uitlijning`, 9), geen
eigen run-routes buiten `/api/annotatie/run`, de iconen uit het beeldmerk.

**Wat ze zijn.** Lint-regels voor het kernprincipe *generieke componenten*, geschreven als test. Ze zijn snel (de hele
map in een paar seconden) en vangen echt terugval naar een tweede variant. **Wat ze niet zijn:** een toets op gedrag.
`paneelWissel.test.ts` (onbewaard werk bij een paneelwissel) toetst bijvoorbeeld dat de setter alleen in `wisselPaneel`
staat, niet dat de vraag ook verschijnt.

**Altijd-groen-risico.** 21 van de 28 bestanden hebben geen positieve controle: geen toets dat de bestandslijst niet
leeg is, of dat de regex in het gewenste geval wél iets vindt. Hernoemt iemand `components/` of `Melding`, of verandert
de JSX-vorm (`<Melding\b[\s\S]*?</Melding>`), dan vindt de regex niets meer en blijft de test groen.
`tests/poort/test_routecontract.py` heeft die controle wel (`test_de_parser_vindt_genoeg`,
`test_het_contract_vangt_een_verwijderde_export`). Dat is het voorbeeld.

### 1.4 Browserregressie

**Vorm.** Elk script start Chromium via Playwright tegen een `next dev` op poort 3109, zet een sessiecookie met
`scripts/sessie.mjs` (een echt JWT met het testgeheim, voor dev- én productienamen) en vangt `/api/**` af met
`page.route`. De UI en de BFF-routing zijn echt. Alles daarachter is nep. 45 van de 46 scripts luisteren naar
`pageerror` en falen daarop (de uitzondering is `test-instellingen-breedte.mjs`).

**Per onderwerp** (duur in de poort van 12 nov 2026, uit `scripts/browsertests.mjs`):

- **Annotatie en samenhang**: `annotatie-nodes` (20 s, axe), `samenhang` (80 s, 953 regels), `reeks`, `toetsen` (axe),
  `werkgebied-annoteren`.
- **Werkgebieden en intake**: `werkgebieden` (22 s, axe), `werkgebied-intake`, `dossier-aanvullen`, `deelvragen`,
  `detailpaginas`.
- **Bronselectie en bronvenster**: `bronselectie`, `bronselectie-paneel`, `bronkandidaten`, `bronvenster-stuk`,
  `bronvenster-bekendmaking`, `bronvenster-wettekst`.
- **Begrippen** (acht scripts): `begrippen`, `begripvoorstellen`, `begrippen-verdieping`, `herbeoordeling`,
  `begriprelaties`, `begrippengraaf`, `begrippenoverzicht`, `generieke-begrippen`.
- **De beurt en artefacten**: `artefacten` (582 regels), `beurtuitkomst`, `subagent`, `antwoordweergave`,
  `contextweergave` (axe), `contextpaneel`, `zijpaneel`, `vraaglex`, `commandos` (axe), `runstanden`.
- **Gesprekken en navigatie**: `sidebar-groepen`, `gesprekken-opruimen`, `teststrook`, `rondleiding` (50 s).
- **Instellingen**: `instellingen` (axe), `instellingen-breedte` (61 s: elke tab op 375, 640, 800 en 1280 px),
  `api-tokens`, `connectors`, `connectors-menu` (24 s), `aanpassingen` (axe), `werkplaats` (599 regels).
- **Los**: `paneelkop` (axe). **Staat niet in `test:browser` en draait dus nooit.**

Ze toetsen **gedrag** op de UI: klikken, invullen, wat er verschijnt, welke verzoeken de UI stuurt (de scripts houden
de bodies bij en toetsen ze). Acht scripts draaien axe-core (WCAG 2.2 AA, zonder uitzonderingen), 18 scripts zetten
een smal viewport.

**De mocks.**

- Per script een eigen nep-api, met eigen vaste waarden. Er is geen gedeelde fixture: alleen `sessie.mjs` en `axe.mjs`
  zijn gedeeld. De begrippen hebben acht nep-api's, elk met een eigen vorm van een begrip.
- **29 scripts antwoorden op een onbekend pad met `200 {}` of `200 []`.** Een nieuwe aanroep die de UI doet, of een
  aanroep met een verkeerd pad, slaagt daar dus stil. Alleen `test-bronselectie` en `test-bronselectie-paneel` gooien
  bij een onverwachte aanroep een fout.
- De SSE-helper `sse(events)` staat in 18 scripts letterlijk gekopieerd: `data: {seq: i, …}\n\n`, alles in één
  `route.fulfill`. De echte stroom (sse-starlette) scheidt met `\r\n` en komt in delen binnen. De parser in `lib/api.ts`
  is op `\r\n` getest (`api.test.ts`), dus de browser toetst een vorm die in productie niet voorkomt. Op zich onschuldig,
  maar het betekent wel dat geen enkele browsertest de echte framing ziet.
- Wat de nep-api's afwijken van de echte, is niet te zien. Het routecontract vangt een **pad of methode** die niet
  bestaat. Een **veld** dat in de api is hernoemd, of een fout die een andere vorm heeft (`detail` als string of als
  object met `fout`/`melding`), vangt niets. Alleen `bepalingDetail.test.ts` en de slotregel-drift hebben een drift-toets
  op het contract van de api.

## 2. Foutpaden: risicomatrix

Dekking: **goed** (gedrag getoetst, ook het randgeval), **deels** (één laag of alleen het gewone geval), **vorm** (alleen
de bron), **nee**.

| Risico | Dekking | Door welke test | Oordeel |
|---|---|---|---|
| Verbroken stroom en hervatten | logica **goed**, browser **nee** | `api.test` (stroom zonder `done`, stilval, volgnummer, gat), `beurtLus.test` (breuk → wachten → opnieuw vanaf lege stand, 500 breuken), `beurtStroom.test` (twee keer afspelen geeft dezelfde stand), `lopendeRun.test` | De logica is deterministisch en volledig. Geen browsertest breekt een stroom halverwege af (`route.abort` komt nergens voor) of toetst `vanaf=`. `test-subagent` laat alleen een stroom zonder `done` 400 ms wachten. De lijm in `useBeurt` (de stopknop, de stand tussen twee pogingen) is daardoor niet end-to-end getoetst |
| 409 bij starten (er loopt al een run) | logica **goed**, browser **nee** | `api.test` (409 met het `run_id`) | `useBeurt` haakt dan aan bij die run, maar dat is niet getest: geen hooktest, en geen browsertest geeft 409 op `POST /api/annotatie/run`. De 409's in de browser (`begrippen`, `werkgebieden`, `werkplaats`) gaan over domeinregels (`al_besloten`, `al_opgenomen`, `poort`), niet over de run |
| 412 en revisieconflict | **goed** | browser: `werkgebieden`, `begrippen`, `begriprelaties`, `herbeoordeling`, `deelvragen`, `bronkandidaten`, `annotatie-nodes`; logica: `revisies.test` | Het best gedekte foutpad in de browser. De nep-api's toetsen `verwachte_revisie` echt. Wel heeft elk script zijn eigen vorm van `detail`, dus een wijziging in de api valt niet op |
| Een run die verdwenen is (herstart van graph-qa) | logica **goed**, browser **nee** | `lopendeRun.test` ("verdwenen door een herstart", "niet meer van jou of bestaat niet") | De waarschuwing die de gebruiker dan ziet, heeft geen browsertest. Dat de BFF bij een storing **geen** `null` teruggeeft (`run/route.ts`, `GET ?gesprek=`), heeft geen test, terwijl de code uitlegt dat dit een eerdere fout was |
| Upstream-timeout (504) en onbereikbaar (502) | BFF **goed**, browser **deels** | `proxy.test` (504 met reden, 502, de time-out tot de headers), `api.test` (504 en 502 elk een eigen fout); browser: `bronvenster-stuk` (502), `toetsen` en `samenhang` (503), `connectors-menu` (503, 504, traag) | De BFF is goed gedekt. In de browser alleen voor bronvenster, graaf en connectors. Geen browsertest geeft 502 of 504 op de start of de events van een run, en de koude start van graph-qa (`START_TIMEOUT_MS = 45 s`) heeft geen test |
| Connector onbekend of niet beschikbaar | **goed** | `connectors/route.test` (register × straat), `connectorLijst.test`, `connectorsMenu.test`, browser `connectors-menu` (503, 504, traag), `connectors` | Goed. Wat niet getest is: een connector die tijdens een beurt wegvalt (de tooluitkomst in de stroom). Dat hoort bij graph-qa |
| Onbewaard werk bij navigeren | logica **deels**, browser **deels**, vorm | `onbewaard.test` (welke link de pagina verlaat), `paneelWissel.test` (vorm), browser `begrippen` en `werkplaats` | Alleen de begripskaart en de concept-editor zijn in de browser getoetst. `useOnbewaardBewaker` zelf, de werkgebied-paneelwissel (FB-05) en `beforeunload` hebben geen gedragstest |
| Sessie via een accounttoken | BFF **deels**, auth **nee** | `proxy.test` (buiten de 2FA-plicht), `auth.config.test` (rolgate met `viaToken`), `sessie.test` (epoch), browser `api-tokens` (het beheerscherm) | De provider in `auth.ts` en de `jwt`-callback (een ingetrokken token beëindigt de sessie, de herverificatie, een `onbekend` als hapering) zijn niet getest. De poort bewaakt alleen dat `apiTokenLogin` default uit staat |
| De 2FA-plicht | **goed** | `proxy.test` (beheerder zonder 2FA dicht, account niet te controleren → dicht), `api.test` (koppelen met wachtwoord, opnieuw koppelen, 401 als afwijzing), browser `instellingen` | Goed op de BFF. Het inlogscherm met TOTP heeft geen browsertest; de scripts beginnen altijd met een cookie |
| Mobiel en touch | **deels**, vorm | 18 browserscripts op een smal viewport, `instellingen-breedte` (vier breedtes, overlap en horizontaal scrollen), `uitlijning.test` en `overzicht.test` (vorm, onder meer de Safari-flexregel) | Breedte is goed gedekt. **Touch niet**: geen script zet `hasTouch` of `isMobile`, er is geen `tap()`. Hover-afhankelijke bediening en de toetsenbordhoogte op iOS (F14 uit de audit) zijn niet te toetsen in deze opzet |
| Toegankelijkheid | **deels** | axe in 8 scripts (WCAG 2.2 AA, elke overtreding faalt), `Escape` in 15 scripts | Axe draait op 8 van de 46 schermen, en niet op de begrippen, de bronselectie, het bronvenster of de rondleiding. Focusvolgorde en `Tab` worden nergens getoetst (`keyboard.press("Tab")` komt niet voor), net als aankondigingen voor een schermlezer (`aria-live` bij een lopende beurt) |
| Tokenbudget op (429 `budget_op`) | **goed** | `api.test`, `tokenbudget.test`, `blokkade.test` (vorm) | Geen browsertest van de blokkade zelf |
| Paginafout of hydratatiefout | **goed** | `pageerror` in 45 van de 46 scripts | Goed. `console.error` wordt niet bewaakt, dus een React-waarschuwing (sleutel ontbreekt, ongeldige nesting) blijft stil |

## 3. BFF en beveiliging

**Tokens blijven server-side.** De tokens staan in `lib/config.ts` en `lib/server.ts`. `tests/poort/test_vormen.py`
(`test_een_client_component_komt_niet_bij_de_tokens`) toetst dat geen `"use client"`-bestand ze **direct** importeert.
Twee gaten:

- `lib/server.ts` heeft `import "server-only"`, maar `lib/config.ts` (waar het API-token staat) niet. Een client
  component die `config` via een tussenmodule binnenhaalt, komt door de vormtest heen, en de build zou het niet tegenhouden.
  Met `server-only` in `config.ts` faalt de build zelf.
- Geen test kijkt in de bundel. Een controle op de uitvoer van `next build` (geen tokenwaarde en geen `API_TOKEN` in
  `.next/static`) vangt elke weg, ook een transitieve.

**De allowlists van de routes.** Er zijn drie catch-alls met een eigen proxy:

- `werkgebieden/[...pad]` en `begrippen/[...pad]`: `isWerkgebiedRoute` en `isGeneriekRoute`. Goed getest
  (`werkgebied.test`: wat door mag, wat geweigerd wordt, met `..`), en het routecontract draait ze uit de echte bron. Ze
  toetsen het pad, niet de methode: de methode-export (`GET/POST/PATCH/DELETE`) geldt voor elk toegestaan pad, dus de api
  is de tweede grens.
- `annotatie/v2/[...pad]`: een allowlist op **alleen het eerste segment** plus een `..`-weigering. **Geen test.** De
  query gaat ongewijzigd door. Dat is bewust, maar het staat nergens in een test.

**`metTrace`.** `test_elke_upstream_fetch_draagt_de_trace` toetst elke `fetch(` in de BFF en in `lib/server.ts` op een
`metTrace(` in de 500 tekens erna. Dat is een vormtoets: hij vangt een vergeten aanroep, maar niet een `metTrace` die
niets doet. `lib/trace.ts` (21 regels) heeft geen unittest. De werking zelf is één keer gemeten (`docs/observability.md`).

**De eigenaarscontrole bij de start van een run** (`app/api/annotatie/run/route.ts`). De BFF vraagt de api eerst of het
gesprek van jou is (404 → "Onbekend gesprek", een andere fout gaat ongewijzigd door), en geeft de identiteit als
`X-User-Id`-header mee aan graph-qa, ook bij `GET ?actief=1` en `?gesprek=`. Dat is de bescherming tegen een vraag in
andermans geheugen. **Hier is in de frontend geen test op.** De api en graph-qa toetsen hun kant (zie hun inventaris).
Het BFF-deel, dat de controle vóór de start doet en een api-storing niet als "onbekend gesprek" leest, kan stil
verdwijnen bij een refactor.

**Verder goed**: CSRF op `Origin` voor elke muterende methode (`auth.config.test`, ook op publieke routes), 401 in JSON in
plaats van een omleiding op de BFF, de CSP met nonce (`proxy.gate.test`, `csp.test`), `pathSegment` en `isPuntSegment`
tegen `..` (`url.test`, 33), en de volgorde bij bulk-wissen.

## 4. De kwaliteit van de tests zelf

**Tests die altijd groen kunnen zijn.**

- 21 vormtests zonder positieve controle (§1.3).
- 29 browserscripts met een stille `200` op een onbekend pad. Een UI die een aanroep verliest of een verkeerd pad
  gebruikt, faalt daar niet. Het routecontract vangt een deel, maar alleen voor aanroepen in `lib/`, niet voor wat een
  script verwacht.
- `test-paneelkop.mjs` draait niet (§1.4). `browsertests.mjs` leest de lijst uit `test:browser`, dus een script dat daar
  ontbreekt, valt ook in de poort weg. Een test op "elk `scripts/test-*.mjs` staat in `test:browser`" ontbreekt.

**Wisselvalligheid.** In 50 poortruns met de frontend (200 browsershards, 13–16 nov 2026) faalde geen enkele shard, en
geen run werd herhaald (`attempt` steeds 1). Dat is een goede stand. Het risico zit in de wachttijden: 97 keer
`waitForTimeout` in de scripts, waarvan 29 in `test-samenhang` (50 tot 900 ms). Op een tragere runner is dat de eerste
plek waar het misgaat. En elke wachttijd kost doorlooptijd, of ze nodig is of niet.

**Doorlooptijd** (mediaan over de 50 runs):

- de job `frontend` (lint, typecheck, vitest): 101 s, maximaal 130 s;
- een browsershard: 250 s, maximaal 331 s, dus de browserregressie bepaalt ~4,5 minuut van de poort;
- serieel kost de browserregressie ~17 minuten (som van de gewichten plus de onbekende);
- lokaal is vitest snel: 40 bestanden in 6,4 s.

**Het sharden.** Vier shards, gelijk verdeeld op de gemeten duur (`GEWICHT`): 257 tot 281 s in de laatste run. Vier
scripts staan niet in `GEWICHT` en tellen als 8 s: `test-werkplaats` (599 regels), `test-subagent`, `test-contextweergave`
en `test-aanpassingen`. Dat
raakt de juistheid niet, alleen de balans. De drie zwaarste scripts (`samenhang` 80 s, `instellingen-breedte` 61 s,
`rondleiding` 50 s) zijn samen 190 s, en een shard kan nooit sneller zijn dan zijn zwaarste script.

**Mocks tegenover het contract** (§1.4): pad en methode bewaakt, vorm niet. Elke nep-api is handwerk, en een veld dat in
de api verandert, blijft groen tot iemand het op acceptatie ziet.

**Dubbel en verspreid.**

- Commando's en Vraag Lex staan op drie niveaus (logica, vorm, browser). Dat is goed als de niveaus elk iets anders
  toetsen, en dat doen ze.
- De begrippen hebben acht browserscripts met acht nep-api's. Dat is geen dubbele toets, maar wel dubbel onderhoud, en
  de vorm van een begrip kan per script uit elkaar lopen.
- `paneelKop.test.ts` (vorm) en `test-paneelkop.mjs` (browser, draait niet) toetsen hetzelfde onderwerp.
- De rondleiding heeft 81 unittests en een browsertest van 50 s: veel voor een functie buiten de kern, vergeleken met
  `useBeurt`, die geen eigen test heeft.

## 5. Voorstellen, op volgorde van prioriteit

**Erbij, eerst.**

1. **Een test op de eigenaarscontrole van `run/route.ts`**, in de vorm van `proxy.test.ts` (alleen `fetch` vervangen):
   een vreemd gesprek geeft 404 en start niets, een api-storing gaat door als storing, en `X-User-Id` staat op elke
   aanroep naar graph-qa (start, `actief`, `gesprek`). Klein, en het dekt het belangrijkste beveiligingspad van de
   werkplek.
2. **Een strikte nep-api als standaard.** Een gedeelde helper (`scripts/nepApi.mjs`) die een onbekend pad met een fout
   beantwoordt en de aanroep noemt, zoals `test-bronselectie` al doet. De scripts gaan er één voor één op over. Wie
   bewust iets negeert, zegt dat per pad.
3. **Elk `test-*.mjs` staat in `test:browser`**: één vitest- of poorttest. Daarna `test-paneelkop.mjs` weer laten
   meedraaien (of weghalen als hij achterhaald is).
4. **Een browsertest voor de stroom die breekt en hervat**: een gedeelde `sse()` die in delen schrijft met `\r\n`, een
   stroom die halverwege afbreekt, het aanhaken met `vanaf=`, 409 bij de start (aanhaken bij de lopende run), en een run
   die verdwijnt (de waarschuwing). Eén script, met de gedeelde helper, in plaats van achttien kopieën.
5. **`import "server-only"` in `lib/config.ts`**, en een controle op de bundel na `next build` dat er geen token of
   `API_TOKEN` in de statische bestanden staat. Dat hoort in de frontend-job, die al bouwt voor de typecheck.

**Erbij, daarna.**

6. **Componenttests met een DOM** (vitest met `happy-dom` of `jsdom` en Testing Library), te beginnen bij de lijm die nu
   alleen in de browser zit: `useBeurt` (stopknop, herstellen, 409), `useOnbewaardBewaker` (paneelwissel, `beforeunload`).
   Dat is sneller en preciezer dan een browsertest, en het haalt druk van de shards.
7. **Een contract op de vorm.** Laat de api zijn OpenAPI-schema uitschrijven (FastAPI doet dat al), en toets de vaste
   antwoorden van de nep-api's daartegen, of beter: laat de scripts hun fixtures uit één map halen die zo getoetst wordt.
   Begin bij de foutvorm (`detail` als string of als object met `fout`), want die wisselt nu per script.
8. **`auth.ts` testen**: de `jwt`-callback (ingetrokken accounttoken → geen sessie, een `onbekend` laat staan, een
   rolwijziging gaat meteen door) en de tokenprovider. Dezelfde opzet als `proxy.test.ts`.
9. **De annotatie-catch-all** krijgt dezelfde allowlist-test als `isWerkgebiedRoute`. De allowlist kan dan ook naar een
   functie in `lib/`, zodat het routecontract haar uit de bron draait.
10. **Toegankelijkheid verbreden**: axe op elk scherm dat een script al opent (het kost een regel per scherm), en een
    toets op de focusvolgorde met `Tab` en op `aria-live` bij een lopende beurt. Plus één script met `hasTouch`.
11. **`console.error` bewaken** naast `pageerror`, met een lijst van wat bewust mag.

**Herschrijven.**

12. **De vormtests krijgen een positieve controle**: per bestand een toets dat de bestandslijst niet leeg is en dat de
    regex op een klein voorbeeld wél iets vindt (het patroon van `test_de_parser_vindt_genoeg`). Ze blijven vorm, maar
    kunnen dan niet meer stil groen worden.
13. **`waitForTimeout` vervangen door wachten op een toestand** (`waitForResponse`, `expect.poll`, een locator),
    beginnend bij `test-samenhang` (29). Dat maakt de zwaarste shard sneller en de tests minder gevoelig voor een trage
    runner.
14. **`GEWICHT` bijwerken** met de vier ontbrekende scripts, en de drie zwaarste splitsen als de shards nog moeten
    zakken.

**Weg kan.**

15. De 18 kopieën van `sse()` en de losse sessie- en route-boilerplate, zodra de gedeelde helper er is (voorstel 2 en 4).
16. Vormtests die door een componenttest overbodig worden (bijvoorbeeld `paneelWissel.test.ts` zodra voorstel 6 het
    gedrag toetst). Pas weghalen als de vervanging groen is en het geval dekt.

**Wat bewust niet in dit plan staat.** Een echte ketentest (browser → BFF → api → graph-qa) hoort bij de inventaris
*keten/E2E*. Hoe goed de bronselectie of de annotaties inhoudelijk zijn, meet Lex Bench. Deze laag toetst of de werkplek
doet wat de api en de agent zeggen, en dat bij een fout de jurist ziet wat er speelt.
