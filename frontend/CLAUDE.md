# CLAUDE.md – wetsanalyse-frontend

Next.js (App Router) + TypeScript-webapp bovenop de graph-qa-agent en, voor login, beheer en
opslag, de [wetsanalyse-API](../api). De app **is de werkplek**: `/workbench` (de *Lex-pagina*) –
één chat-achtig gespreksvenster voor **vragen én JAS-annotatie**, live tegen graph-qa. De home (`/`)
leidt daarheen door.

> **Scope: chat-werkruimte.** De app bestaat uit de werkplek, het annotatie-overzicht, de
> login-flow en het instellingenvenster (account, verbruik, berichten, en voor beheerders
> modelprofielen, gebruikers, aanvragen, API-tokens, berichtenbeheer en feedback).

Lees ook de projectroot-`CLAUDE.md` en `../api/CLAUDE.md` – de API is de bron van waarheid voor de
datacontracten en de state machine; deze app is een **dunne, server-getokende schil** eroverheen.
Lokaal draaien, env-vars en uitrol staan in de [`README.md`](README.md); dit bestand beschrijft de
regels die je bij code-werk *in* de frontend niet mag breken.

## Dragend principe – BFF, token blijft server-side

De browser praat **uitsluitend** met de eigen Next.js-origin (`/api/**`). De Route Handlers (de
_backend-for-frontend_) proxyen server-side naar de API en graph-qa en injecteren het Bearer-token
(zie de README voor het schema). De **harde scheidingslijn**: alles met een token is server-only.

- `lib/config.ts` (tokens uit env/`*_FILE`, gecached), `lib/server.ts` (server→server fetch voor
  Server Components en de auth-verificatie) en `lib/logger.ts` mogen **nooit** vanuit een Client
  Component geïmporteerd worden – dan lekt het token naar de bundel.
- Client Components praten alleen via `lib/api.ts` met de eigen `/api/**`-routes, **zonder
  Authorization-header**.

## Lagen (waar hoort wat)

- **`app/api/_lib/proxy.ts`** – de kern van de BFF: één `proxy(path, init)` die de upstream-status
  en -body **ongewijzigd** teruggeeft, inclusief de headers in `PASS_THROUGH_HEADERS`
  (`Retry-After`, `Location`, `Content-Type`, `Content-Disposition`). `init.admin: true` injecteert
  het admin-token. Verzin in een nieuwe route geen eigen fetch-logica. De helper bewaakt ook de
  **wachttijd**, want Node's `fetch` kent geen standaardtimeout en een upstream die verbindt maar niet
  antwoordt laat de UI anders eeuwig laden: default 30 s → **504** met een leesbare reden
  (onbereikbaar = 502); `timeoutMs` per route hoger waar dat hoort (de modeltest: 120 s).
  **Uitzondering: SSE.** `app/api/annotatie/run/[id]/events/route.ts` gebruikt geen `proxy()` maar
  geeft `upstream.body` rauw door met `X-Accel-Buffering: no` en `Cache-Control: no-transform`.
- **`app/api/_lib/session.ts`** – `sessionUserId()` voor de vertrouwde `X-User-Id`-header.
- **`lib/server.ts`** – server-side helpers voor Server Components en auth
  (`verifyCredentials`/`getAccountStatus`/`getSetupStatus`), rechtstreeks server→server.
- **`lib/api.ts`** – alle client-side fetch-helpers naar `/api/**`, met één foutcontract
  (`parseError` → `ApiError` met `retryAfter`); gebruik `isApiError()` en `foutTekst()` in de UI.
- **`lib/agentEvents.ts`** – validatie van de SSE-stroom van de agent: een ongeldig event slaat
  over, het beëindigt de run niet.
- **`lib/types.ts`** – met de hand afgeleid van `../api/app/annotatie_v2_contracts.py` en
  `gesprek_contracts.py`; de bron van waarheid aan de TS-kant. `AnnotatieDocument` is het
  weergavemodel van het artefact, gevuld door `lib/annotatieNodeAdapter.ts`. Wijzigt
  het API-contract, werk dit bij (controle met `openapi-typescript`, zie de README).
  **`lib/jas.ts`** is de presentatie-helper voor de JAS-klassen (kleur, label, `jasVolgorde`); de
  namen en kleuren staan canoniek in `api/app/jas_klassen.py`, en `api/tests/test_jas_kleuren_drift.py`
  bewaakt dat deze kopie niet afdrijft. Verzin er geen
  klassen bij.
- **De rekenkern staat in `lib/`**, niet in componenten: vitest draait node-env zonder DOM, dus alleen
  pure helpers zijn testbaar (`selectie`, `annotatie`, `annotatieOverzicht`, `reeks`, `samenhang`,
  `markering`, `popover`, `wetstructuur`, `lopendeRun`, `rondleiding`, …).
- **`app/**/page.tsx`** (Server Components) – data via `lib/server.ts`, interactie in een
  `*Client.tsx`. `app/page.tsx` doet `redirect("/workbench")`. De werkplek zit in
  `app/workbench/page.tsx` én in `app/default.tsx` (de default van het children-slot); beide renderen
  `WerkplekVenster`, zodat de router bij het wisselen tussen die twee geen remount veroorzaakt en het
  open gesprek blijft staan. Auth-schermen: `app/login/*`, `app/setup`, `app/registreren`,
  `app/disclaimer`. Account en beheer leven in het **instellingenvenster**:
  `app/instellingen/[[...tab]]/page.tsx` als volle pagina, `app/@modal/(.)instellingen/…` als
  intercepting route die hem als dialoog over de werkplek opent. `app/beheer` en `app/account` zijn
  redirects naar de bijbehorende tab.
- **`components/`**:
  - `werkplek/` – de hele chat-werkruimte: schil, sidebar, thread (`ThreadRij`, `ToolSpoor`,
    `KeuzeKaart`, `ReeksBlok`, `HergebruikMelding`, `Markdown`) en het annotatiegereedschap in het
    artefactpaneel (`ArtefactInhoud`, `ArtefactPaneel`, `DocumentPaneel`, `ReviewQueue`,
    `SelectiePopover`, `ExportKnop`).
  - `annotaties/` – het overzicht en de losse annotatiepagina (`AnnotatiesClient`, `AnnotatieKaart`,
    `NodeAnnotatiePaneel`, `AnnotatiePaginaSchil`).
  - `graaf/` – de 3D-samenhangsgraaf.
  - `admin/` – de beheertabs achter het admin-token: `ProfielenPanel` (+ `ProfileEditor`),
    `UsersPanel` (+ `BudgetBeleidBlok`), `RegistratiesPanel`, `ApiTokensPanel`,
    `BerichtenBeheerPanel` (+ `BerichtEditor`), `FeedbackLijstClient`.
  - `account/`, `auth/` – account, login/2FA/setup/registratie, disclaimer, `AuthFrame`.
  - `instellingen/` – `InstellingenDialog` (de dialoogschil) en `InstellingenInhoud` (de tabs). De
    tabdefinities en pad-helpers staan in `lib/instellingen.ts`, bewust **zonder** `"use client"`,
    zodat Server Components ze mogen importeren.
  - `rondleiding/` – de rondleiding door de werkplek (zie §*Rondleiding*).
  - `ui/` – de primitives.

### Vormgeving (Rijkshuisstijl, Belastingdienst-stijlvak)

- **Tokens, geen hex-waarden.** Kleur en typografie lopen via CSS-variabelen in `app/globals.css` →
  Tailwind in `tailwind.config.ts` (en `lib/jas.ts` voor de JAS-badges). Het logo-asset
  `public/belastingdienst-logo.svg` blijft ongewijzigd; de JAS-klassekleuren komen exact uit
  `docs/wetsanalyse/wa-table.png`. Uitzondering: `app/global-error.tsx` gebruikt inline stijl met
  vaste huisstijlkleuren, omdat die boundary de hele documentboom vervangt en de app-CSS niet kan
  veronderstellen.
- **De root-font-size is overal 100%.** Schaal met de Tailwind-tekstklassen, niet met een globale
  krimp.
- **Primitives in `components/ui/`**: 40px-knoppen/velden die onder de `coarse:`-variant
  (`@media (pointer: coarse)`, `tailwind.config.ts`) naar 48px groeien.
- **Knoppen zijn mobile-first.** `Button`/`LinkButton` zijn breedte-neutraal (`inline-flex
  shrink-0`); actierijen lopen via `components/ui/ButtonRow.tsx` (mobiel gestapeld op volle breedte,
  vanaf `sm:` naast elkaar). Staat een knop buiten een `ButtonRow`, geef hem dan
  `className="w-full sm:w-auto"` en laat de container op mobiel stapelen (`flex flex-col …
  sm:flex-row`). Geen vaste of `flex-wrap`-knoprijen die op een smal scherm overlopen.
- **Symbolen zijn iconen, geen tekens.** `components/ui/Icoon.tsx` levert chevron, waarschuwing,
  vinkje, ruit en cirkel als inline SVG (`1em`, `currentColor`). Het font laadt alleen de
  latin-subset van Fira Sans (`app/fonts.ts`), dus tekens als `▾ ◇ ▸ ⚠ ✓ ← ○` vallen terug op het
  systeemfont en ogen per platform anders; emoji worden door het besturingssysteem in eigen kleuren
  getekend. `·` (U+00B7) zit in de subset en mag. Uitzondering: tekst die als **inhoud** wordt
  opgeslagen (de foutmelding die als chatbericht de geschiedenis in gaat) kan geen component dragen;
  daar staat een woord.
- **Kleur betekent iets, of hij hoort er niet.** Kleur is voor wat een oordeel draagt
  (aandacht-badge, JAS-badges, accentrand). Knoppen volgen de app: primair lintblauw (`bg-accent`),
  tweede keuze outline – geen volvlak statuskleuren.

## Werkplek – de Lex-pagina (`/workbench`)

> **De agent heet Lex** in beeld: de paginatitel, het label boven elk antwoord (`ThreadRij`), *Vraag
> Lex*, "voorstel van Lex", "Kanttekening van Lex". In de **code** heet alles `graph-qa` (map, image,
> env-vars) en in het **berichtcontract** blijft de rol `assistant` – de naam is presentatie. De lege
> thread draagt een korte zelfbeschrijving; de volledige staat in `tools/graph-qa/agent/prompts.py`
> (§IDENTITEIT), de toon in `docs/schrijfrichtlijn-lex.md`.

`app/workbench/page.tsx` → `WerkplekVenster` → `components/werkplek/WorkbenchShell.tsx`: een
volledige chat-app-shell met bovenaan de klikbare testomgeving-strook (naar de disclaimer). Er is
**geen globale chrome**: `app/layout.tsx` bevat alleen `Providers`, `{children}` en het
`modal`-slot. De shell-pagina's zetten zelf `h-[100dvh] overflow-hidden`; alles daarbuiten gebruikt
`AuthFrame` (zie §*Buiten de schil*).

- **Links de sidebar** (`AppSidebar` → `GesprekSidebar` + `GesprekLijst`): logo, *Nieuw gesprek*,
  de per gebruiker bewaarde chatgeschiedenis en onderin het gebruikersblok (instellingen, feedback,
  rondleiding, uitloggen, verbruiksmeter). Onder `lg` is het een off-canvas drawer via **`Dialog`
  met variant `drawer`** – niet als eigen constructie, want `Dialog` levert de enige focus-trap in de
  codebase; zonder die trap loopt Tab achter de scrim door naar de chat.
- **Rechts het chatvenster** (`WerkplekClient.tsx`): vragen én annotatie, beide als run bij
  graph-qa's unified agent. De thread hydrateert uit het actieve gesprek en **persisteert elke beurt**
  naar de API (`/v1/gesprekken/*`). De shell remount het venster (via `key`) alleen bij echt van
  gesprek wisselen, niet wanneer een verse chat bij de eerste beurt zijn id krijgt – anders breekt de
  stream. De graph-qa `conversation_id` (thread_id) is het `gesprekId`.
- **De annotatie is een artefact**: een annotatiebeurt toont een chip in de thread die het
  **`ArtefactPaneel`** opent. `DocumentPaneel` toont de wettekst met de **letterlijke** fragmenten
  (`segmenteer` + `lib/jas.ts:jasStyle`), `ReviewQueue` de beslissingskaarten.
- **Drie backends, de frontend orkestreert:**
  - *Chatgeschiedenis via de API* – `app/api/gesprekken/*` → `/v1/gesprekken/*` via `proxy()`, met
    `X-User-Id` uit de sessie (`lijstGesprekken`/`maakGesprek`/`haalGesprek`/`voegBerichtToe`/
    `hernoemGesprek`/`verwijderGesprek`). **Twee stores op dezelfde `conversation_id`**: de
    UI-historie in de API, het agent-geheugen in graph-qa's checkpointer. De BFF-DELETE wist daarom
    beide: na de API-delete ook graph-qa `DELETE /v1/conversations/{id}` (best-effort).
  - *Live agentverkeer via graph-qa* – `app/api/annotatie/run/**` (starten, events, `cancel`) met
    `graphQaBaseUrl()` + `GRAPH_QA_TOKEN` en `X-User-Id` (`startRun`/`volgRun`/`stopRun`/
    `haalActieveRun`).
  - *Review-state via de API* – de catch-all `app/api/annotatie/v2/[...pad]/route.ts` → `/v1/annotatie/{weergave,elementen,lagen,
    node-lagen,samenhang,capabilities,verklaringen}` (een allowlist op het eerste padsegment), met client-helpers in `lib/annotatieNode.ts`. De lagen zijn **gedeeld**,
    niet per gebruiker; gesprekken zijn per gebruiker.

### De beurt is van de server, niet van dit tabblad

Een beurt draait als **run** bij graph-qa (`POST /api/annotatie/run` → `startRun`); de werkplek kijkt
mee (`volgRun` op `/api/annotatie/run/[id]/events`). Van gesprek wisselen, naar `/annotaties` lopen of
herladen breekt hem niet af. Regels:

- **Unmount koppelt alleen los.** `afbrekenRef.current?.abort()` beëindigt de kijker, niet de run.
  Een `AbortError` in `volgBeurt` is daarom géén einde: niets bewaren, het antwoord komt later.
- **Bij binnenkomst haak je weer aan** (`hervatBeurt` na de hydratatie): loopt er nog een beurt, dan
  komt hij vanaf `seq 0` terug. Alleen bij status `loopt` – een afgeronde beurt staat al in de
  gehydrateerde geschiedenis, en twee keer tonen is erger dan missen.
- **Stoppen is een verzoek** (`stopRun`), geen dichtvallende socket. De agent stopt op een nodegrens,
  dat kan tientallen seconden duren; de knop blijft daarom in de `stopt`-stand. Stoppen vóór de
  voorstellen levert er nul op, en het bericht zegt dat.
- **Na een herstart van de agent is het run-register leeg.** `lib/lopendeRun.ts` onthoudt per gesprek
  welk run-id er liep; `standVanVorigeRun` bepaalt dan of de beurt gewoon is afgerond (het bericht met
  dat `run_id` staat in de geschiedenis) of echt verdwenen is. Alleen in dat tweede geval komt er een
  melding; zonder die controle zou elke normale afloop als "afgebroken" gemeld worden.
- **Een weggevallen verbinding is geen mislukte beurt.** Bij een deploy wordt de frontend-container
  vervangen terwijl de run doorloopt. `volgBeurt` haakt daarom **één keer** opnieuw aan
  (`naEenGebrokenStream`, na 1,5 s, met `vanaf: 0`); pas als die herkansing op is of het venster weg
  is, komt er een foutmelding. Eén poging: is de dienst echt onbereikbaar, dan vertelt doorproberen
  de gebruiker niets.
- **`run_id` reist mee naar de API** bij het bewaren van de assistent-beurt; kijken er twee tabbladen
  mee, dan landt de uitkomst toch één keer (de API dedupliceert erop).
- **Bij een 409 op `startRun`** (er loopt al een beurt op dit gesprek) haakt de client aan bij die run
  in plaats van te falen: twee gelijktijdige beurten schrijven door elkaar in het agent-geheugen.
- **De agent schrijft weg, de werkplek nooit.** graph-qa stuurt vlak vóór het einde een
  `opgeslagen`-event met het `annotatie_doel` (de bronnode); de client opent dan de weergave
  (`toonVastgelegdeBeurt`). Blijft dat event uit terwijl er markeringen waren, dan is dat een
  **storing** en toont de werkplek het zo. Zet er geen tweede schrijfpad vanuit de browser naast –
  bij gedeeltelijk falen levert dat een tweede annotatie op. Een eigen markering van de jurist is een
  andere handeling (`POST elementen` in `NodeAnnotatiePaneel`). Een graph-qa zonder API-koppeling meldt zelf met een
  `error`-event dat niets is vastgelegd (`agent/beurt.py`).
- **Tokens komen hooguit één keer per frame binnen** (`planStroom` in `volgBeurt`).

**Identiteit is een vertrouwensgrens.** De BFF zet `X-User-Id` uit de sessie op alle run-routes en
verifieert bij het starten eerst bij de API of het gesprek van deze gebruiker is. `conversation_id` is
ook de thread_id van het agent-geheugen: zonder die controle kan een vreemd gespreks-id (dat in de
URL van de werkplek staat) andermans historie lezen of er een vraag in injecteren. Er is daarom
**één weg naar de agent**: elk pad dat een `conversation_id` aanneemt, verifieert eerst bij de API van
wie dat gesprek is, zoals `app/api/annotatie/run/route.ts`. Zet er geen tweede ingang naast.

### De tijdlijn en het toolspoor van een beurt

graph-qa stuurt per fase een `status`-regel met duur (supervisor → ophaal-agent → Bron →
Taalanalyse → Detectie → Besluit → Classificatie → Review → Resultaat → Klaar); `onStatus` plakt die
als `· <regel>` aan `denk`, en `DenkProces` toont ze live. Onder de annotatiechip staat de **beurtsamenvatting** van de laatste
ronde (`beurtSamenvatting` in `lib/waarom.ts`, uit `geproduceerd_door.instellingen.meting`):
resultaat, bronnodes zonder zinsontleding en de totale duur. Het `annotatie`-item draagt ook een
`denk`-veld: de tijdlijn staat ingeklapt boven de chip als *"Zo is dit tot stand gekomen"*, wordt met
de beurt bewaard en bij hydratatie teruggehaald. Achteraf moet te zien zijn hoe een annotatie tot
stand kwam. `ToolSpoor` toont de graafaanroepen van de beurt (`tool_executions`), één regel per
aanroep.

### Brongetrouwheid onder en in het antwoord

- **`Brongetrouwheid`** (`ThreadRij`) leest het `grounding`-event. Het zwijgt bij
  `niveau: "gegrond"` – een groen vinkje bij elk antwoord leert mensen erover heen te kijken – en
  spreekt bij **ongegrond** (een verwijzing die niet uit de graaf kwam, of een citaat dat niet
  letterlijk in de opgehaalde tekst staat) en **onbepaald** (geen vindplaats en geen citaat, dus niets
  te controleren). Onbepaald is geen goedkeuring; toon het niet groen. De uitkomst reist niet mee in
  het berichtcontract, maar de statusregel staat in `denk`.
- **Een afgekeurd citaat wordt in de tekst zelf aangewezen.** `Markdown` neemt `nietLetterlijk` aan
  en wikkelt elke treffer in een `<mark>` (aandacht-geel, stippellijn en een `sr-only`-toelichting,
  zodat het signaal niet alleen aan kleur hangt). Dat is een **rehype-plugin op de hast-boom**, niet
  op de bron-markdown: er komt geen teken in de tekst die de jurist zou meekopiëren. Matchen gaat
  letterlijk – wijkt de weergave af van wat de controle vergeleek, dan markeer je liever niets dan
  het verkeerde stuk. Logica in `lib/markering.ts`.

### Citatie-chips onder en in het antwoord

Een vindplaats die Lex in gewone taal noemt ("artikel 9 lid 2", "art. 10a, derde lid") en die
**éénduidig** bij een bron van de beurt hoort, wordt een citatie-chip (`lib/citaties.ts`:
`vindVermeldingen` + `koppelBron`, via `bronDoel`). De rehype-plugin `markeerCitaties` wikkelt de
vermelding in een `cite` – de tekst zelf verandert niet, net als bij `markeerPassages`. Een klik
opent `CitatieChip` → een bronkaart via een portal (een `Popover` is een `div` en mag niet in een
alinea), met de wettekst (lui via `haalSamenhang`), een link naar wetten.overheid.nl en *Bekijk
samenhang in 3D*. Geen chip bij twijfel: liever een vermelding zonder kaart dan een kaart bij de
verkeerde bepaling. Werkt ook na herladen, want alleen `tekst` en `bronnen` zijn nodig. De lijst
*Bronnen (n)* toont leesbare labels (`bronLabel`) in plaats van rauwe IRI's.

### Annoteren op onderwerp

Noemt de vraag een onderwerp in plaats van een bepaling, dan komt er een `kandidaten`-event: de
thread toont `KandidatenKeuze` (in `ThreadRij`), en één klik stuurt `kandidaatPrompt(k)` als nieuwe
beurt in, **met `doelVanKandidaat(k)` als gestructureerd `doel`**. Daarmee slaat de agent de supervisor
en de ophaal-agent over en kan hij niet bij een andere bepaling uitkomen dan de jurist aanwees. De
prompt blijft als leesbare vraag in de thread staan, mét het bwbId, voor het geval een beurt tóch
zonder doel loopt. Algemene regel: **kent de werkplek de bepaling al, geef dan `doel` mee aan
`startRun`**. Een adviesvraag draagt nooit een doel – die route annoteert niet. Er is bewust geen
"annoteer ze allemaal": kandidaten uit verschillende artikelen samen zijn een werkgebied. De
kandidaten zitten niet in het berichtcontract; na herladen blijft de opsomming uit
`kandidatenAlsTekst`.

**Geen keuzemenu's – het is chat op de graaf.** Je kiest geen wet uit een lijst: je stelt je vraag en
de agent vindt de bepaling (het `doel`-event levert `bwbId`/`artikel`/`citeertitel`). Een keuze die de
agent ná je vraag voorlegt uit wat hij vond (kandidaten, `KeuzeKaart`) is een antwoord, geen menu.

### Kiezen binnen één artikel, en de reeks

Wijst de vraag een artikel met leden aan (of een beleidsregel met subbepalingen), dan draagt het
`kandidaten`-event een **`keuze`** (`parseKeuze`) met per optie `bron_iri`, `label`, `stand` en
eventueel `gekozen`. De thread toont dan **`KeuzeKaart`**: een listbox, focus erin bij verschijnen.
**Klik (op de regel of het vinkje) of spatie selecteert**; *Annoteer geselecteerde* start **één run
met `doelen`** (`doelenVanKandidaten`). **Enter** annoteert de selectie, of zonder selectie het
onderdeel onder de cursor (een gewone beurt met `doelVanKandidaat`). Een klik start nooit zelf een
run: dan loopt er een beurt op budget terwijl je nog kiest. De stand per onderdeel (nieuw / te
beoordelen / afgerond) staat erbij, en onderaan wat de keuze inhoudt, want elk onderdeel kost budget.

Die run is een **reeks** (graph-qa `agent/reeks.py`): per onderdeel een gewone beurt met een eigen
laag. De events komen ingedeeld binnen (`reeks`, `onderdeel`, en `onderdeel: <bron_iri>` op elk event
ertussen); `lib/api.ts` geeft ze ruw door aan `onReeksEvent`, zodat een fout bij één onderdeel de
stroom niet afbreekt. `lib/reeks.ts` (`verwerkReeksEvent`) maakt er het **`ReeksBlok`** van: per
onderdeel een regel, het lopende open met zijn eigen tijdlijn, een klaar onderdeel ingeklapt met
*Open ›*. Na herladen komt het blok terug uit de berichten: graph-qa bewaart per onderdeel een bericht
met `reeks: {run_id, index, totaal, ouder}` (`reeksUitBerichten`). Niet breken: een afgeronde reeks
herken je aan `reeks.run_id` (de berichten zelf dragen `<run>.<n>`), en bij opnieuw aanhaken aan een
lopende reeks gaat het gehydrateerde blok eerst weg – de eventlog speelt het geheel opnieuw af.

*Open ›* opent het paneel **op dat ene lid**, met een reeksbalk (`ReeksBalk` in
`NodeAnnotatiePaneel`, `reeksNavigatie` in `lib/reeks.ts`): "2 van 3" en ‹ › of `[` `]` naar het
buurlid. Bewust niet het hele artikel in één paneel: *Afronden* en *Verwijderen* werken op álle lagen
in beeld, ook op leden die niet gekozen waren. Alleen leden met een vastgelegde annotatie tellen mee
in het bladeren.

### Eén gesprek: vragen over een markering gaan via het centrale venster

*Vraag Lex* op een reviewkaart zet een vraag klaar in het chatveld; er is geen aparte mini-chat in de
kaart.

- `WerkplekClient` houdt `vraagOver` (slug + element). Zolang dat staat, toont een **chip** boven het
  invoerveld waar de vraag over gaat en gaat de beurt met `modus: "advies"` + `vraagContextVan(...)`.
  De chip verdwijnt na het versturen – anders wordt je volgende vraag ongemerkt ook een adviesvraag.
- **Drie vragen staan klaar** (`vraagSuggesties` in `lib/annotatie.ts`): waarom deze klasse, klopt de
  afbakening, en – als de agent een alternatief voorstelde – waarom die andere klasse dan niet. Eén
  klik verstuurt; ze verdwijnen zolang er een beurt loopt, want een tweede vraag zou worden
  afgewezen.
- Het antwoord is een gewone beurt, dus met bronnen, grounding en kopieerknop.
- De chip is UI-state; het bewaarde bericht krijgt een contextregel
  (`Bij <klasse> – "<fragment>" (art. 36): <vraag>`).
- **De context is één document.** `eigenMarkeringenVoorContext(doc)` levert de eigen, niet-verworpen
  markeringen van de bepaling die openstaat, niet alles wat in het gesprek geopend is – anders legt
  Lex een fragment uit artikel 36 naast de tekst van artikel 8. graph-qa handhaaft die grens nog eens.
- Op een **smal scherm** sluit het artefact al bij de klik op *Vraag Lex*: het paneel ligt daar over
  de chat, en anders typ je in een veld dat je niet ziet. Het versturen sluit het nog eens, als
  vangnet. De focus op de textarea blijft in dezelfde gebeurtenis als de klik: iOS opent het
  toetsenbord alleen binnen een gebruikersgebaar.

### Foutafhandeling in de werkplek

- **Foutmeldingen via `foutTekst` uit `lib/api.ts`, nooit via `e instanceof Error`.** Een `ApiError`
  is een object-literal, dus die test is altijd onwaar en vervangt elke serverreden door een
  generieke zin.
- **Niets faalt stil.** Het artefact openen toont een laadstand en bij een fout een `Melding` met
  *Opnieuw proberen* (`NodeAnnotatiePaneel`, `LaadStand`). Een mislukte beslissing landt in de
  `Melding` van het artefact (`ArtefactInhoud.beslis`/`wis` vangen), niet als chatbericht.
- **Een verwijderde annotatie is een toestand, geen fout.** Een bericht verwijst naar zijn annotatie
  zonder foreign key. Een bericht met alleen een `annotatie_slug` en geen `annotatie_doel` wijst naar
  iets wat niet meer bestaat: de chip wordt een **tombstone** (grijs, doorgestreepte titel, "Deze
  annotatie is verwijderd", link naar `/annotaties`) met een neutrale `Melding type="uitleg"` zonder
  *Opnieuw proberen*. Een bronnode-annotatie die intussen is verwijderd, meldt het paneel zelf
  (`verwijderd: {op}`). De kaart benoemt zichzelf via **`annotatie_titel`** in het berichtcontract
  (zonder dat veld: "Annotatie"). Bewust geen cascade server-side: het gesprek is een verslag van
  wat er gebeurde.
- **De laatste annotatie blijft bereikbaar** via een balk boven de chat (titel · *Openen*) zodra het
  paneel dicht is; verwijderde annotaties slaat die balk over.
- **Een knop die een call doet, toont dat.** `BevestigKnop` await't `onBevestig`, staat zolang op
  `Bezig…` en is uitgeschakeld; `AppSidebar`/`AnnotatiesClient` halen een rij meteen weg en zetten hem
  bij een fout terug. Anders is een trage call (de BFF belt bij het verwijderen van een gesprek
  diensten die koud kunnen starten, `minReplicas: 0`) niet te onderscheiden van een klik die niet
  aankwam.

### Prestaties van de thread

**Eén beurt is één `ThreadRij`, en die is een `memo`.** `WerkplekClient` rendert bij elke
toetsaanslag en elk frame van een lopende stroom opnieuw. `components/werkplek/ThreadRij.tsx` krijgt
daarom alleen stabiele props: het eigen item, het eigen document (niet de hele `docs`-map), scalaire
vlaggen en één `acties`-object dat `WerkplekClient` één keer maakt en via een ref naar de handlers van
de laatste render laat wijzen. **Geef een rij geen inline callback of vers object mee**, anders
rendert alles weer. Om de rij zit `.thread-rij` (`content-visibility: auto`, `globals.css`): buiten
beeld slaat de browser layout en paint over.

## Annotaties buiten het gesprek (`/annotaties`)

Een annotatie is een eersteklas object: een ingang in de sidebar die het hoofdgebied vult, terwijl de
sidebar blijft staan.

- **`AppSidebar`** bezit de gesprekkenlijst (laden, hernoemen, verwijderen) en de mobiele drawer, en
  is gedeeld door `WorkbenchShell` en de annotatiepagina's. In de werkplek wisselt een klik van gesprek
  in lokale state, op `/annotaties` navigeert hij naar `/workbench?gesprek=<id>`. `WorkbenchShell`
  verhoogt `verversSignaal` als een beurt een gesprek aanmaakt.
- **Elk scherm met `AppSidebar` moet de drawer openen.** Onder `lg` is de sidebar verborgen en
  verschijnt de drawer alleen als het scherm `drawerOpen` + `onDrawerSluit` doorgeeft; anders is er op
  een smal scherm geen navigatie, geen account en geen uitloggen. De hamburger zit in de gedeelde
  `components/werkplek/MobieleTopbar.tsx`; `components/werkplek/sidebar.test.ts` bewaakt dat elk
  scherm met `AppSidebar` `drawerOpen` en `onDrawerSluit` doorgeeft.
- **`/annotaties`** (`AnnotatiesClient`) heeft twee weergaven op één lijst: *te doen* (rood → geel →
  langst stil) en *alles* (per regeling). De stand staat in de URL (`?weergave=alles`, via `replace` –
  een weergavewissel is geen stap in de geschiedenis). De kaart toont een **JAS-kleurstrip**
  (`KleurStrip`) met de klasseverdeling. Sorteer-, groepeer- en zoeklogica staan in
  `lib/annotatieOverzicht.ts`.
- **Het overzicht toont de gedeelde lagen** (`lijstLagen` → `app/api/annotatie/lagen` plus
  `…/v2/node-lagen`): één annotatie per bepaling voor iedereen, zodat Lex een al geannoteerde bepaling
  kan hergebruiken. Een kaart met een `bron_iri` opent de bronnode-weergave (`/annotaties/node`), de
  rest het artikeldocument. *Door mij bewerkt* (`mijn=true`) beperkt tot lagen waar je zelf iets aan
  deed – een laag heeft geen eigenaar, de API leest dat uit de audit. De kaart telt verouderde
  markeringen apart. Alle query-parameters gaan ongewijzigd door de BFF-route; een parameter die daar
  sneuvelt faalt stil.
- **Verwijderen staat naast afronden**: *Verwijderen* in de actierij van `ArtefactInhoud`
  (`onVerwijder`, alleen als er een laag in beeld is), als `BevestigKnop`. Elke gebruiker mag het, ook
  op een afgeronde annotatie; de audit legt vast wie. `NodeAnnotatiePaneel.verwijder` stuurt
  `weergave/verwijder` met de revisies in beeld (412 als iemand intussen iets wijzigde) en laadt
  opnieuw. De API haalt alle lagen van de bepaling in beeld weg, ook uit de graaf; de weergave draagt
  dan `verwijderd: {op}` en het paneel zegt "Deze annotatie is verwijderd op …", ook als je hem later
  vanuit een oud gesprek opent. Lex annoteert zo'n bepaling bij een volgende vraag opnieuw.
- **Hergebruik en "opnieuw annoteren" staan bij de annotatie in het gesprek** (`HergebruikMelding`).
  Het `hergebruik`-event (`parseHergebruik`) zegt welke leden uit de laag kwamen; de melding blijft na
  herladen omdat graph-qa hem in het chatbericht zet (`Bericht.hergebruik`). *Lex opnieuw laten
  annoteren* start een run met `hergebruik: "opnieuw"` en het doel van de beurt (`doelVoorOpnieuw`) –
  zonder doel zou de agent de bepaling opnieuw moeten zoeken. Die ronde vult de laag aan; wat
  beoordeeld is blijft staan.
- **Verouderde markeringen zijn historie** (`splitsVerouderd`). Is de wettekst van een lid veranderd,
  dan zet de API de oude markeringen op `verouderd`: ze lichten niet op en staan niet in de
  reviewlijst, maar wel ingeklapt onder *Historie – tekst gewijzigd*, met het oordeel van toen
  (`LIFECYCLE_LABEL`).
- **`/annotaties/node`** toont een bronnode-annotatie op eigen benen, bewust zonder `onVraag`: er is
  geen chatveld om een vraag in klaar te zetten – daarvoor is *Openen in de werkplek*.

**Eén inhoud, twee schillen.** `components/werkplek/ArtefactInhoud.tsx` draagt de wettekst, de
reviewlijst en alle handlers; `ArtefactPaneel` is de `Dialog`-schil eromheen en de annotatiepagina
de tweede schil (hetzelfde patroon als `DisclaimerClient` en `InstellingenInhoud`). Een
**bronnode-annotatie** gebruikt dezelfde inhoud: `NodeAnnotatiePaneel` haalt de v2-weergave op en
vertaalt die via `lib/annotatieNodeAdapter.ts` (codepoints per bronnode ⇄ UTF-16 in de samengestelde
bron). **Bouw geen tweede weergave, breid de adapter uit** – een eigen paneel verliest alle opmaak en
bediening. `ArtefactInhoud` heeft daarvoor twee optionele haken: `onExport` (een eigen exportroute) en
`extra` (blokken onder de reviewlijst, zoals "overspant meerdere bepalingen" en de voortgang per
bepaling). De paginaschil (sidebar, mobiele topbar, terug naar het overzicht) is gedeeld in
`components/annotaties/AnnotatiePaginaSchil.tsx`.

**Escape handelt de inhoud zelf af** (selectie → bedieningsrij → gekozen element → `onSluiten`),
want de `Dialog`-schil is er niet altijd. `ArtefactPaneel` geeft `Dialog` daarom een **no-op**
`onEscape`; reageert die ook, dan springt Escape in één klap door alle lagen heen.

**Het kruisje staat altijd rechtsboven.** De kop van `ArtefactInhoud` is twee vaste regels: titel +
sluitknop, daaronder de acties (status, exporteren, afronden, verwijderen) rechts uitgelijnd. In één
wrappende rij verhuist het kruisje mee zodra de ruimte krap wordt. Sluiten zit op dezelfde plek en met
hetzelfde icoon (viewBox 20, `strokeWidth` 1.6) als in `InstellingenDialog`, `DisclaimerDialog`,
`FeedbackDialoog` en de gesprekkendrawer.

**Historie** (`components/annotaties/RevisieHistorie.tsx`, logica in `lib/revisies.ts`) staat in de
`extra`-haak van het paneel: per revisie van de lagen in beeld wie wat wanneer deed, pas geladen bij
openklappen en opnieuw bij een nieuwe revisie. Een geraakt element kies je met één klik. Alleen-lezend:
de api bewaart geen oude inhoud, dus er is geen "toon de laag zoals hij toen was".

**Afronden** zit in de kop van `ArtefactInhoud` (dus in beide schillen) en zet de status van elke laag
in beeld (`NodeAnnotatiePaneel.status`, `POST lagen/{id}/status`). Expliciet, want "alle elementen beslist" is niet hetzelfde als klaar zijn;
heropenen kan altijd. Afronden **bevriest de hele annotatie** (`isDocumentVergrendeld`): de handlers
vallen stil, de selectie-popover verdwijnt, `a`/`x`/`c` doen niets en een melding boven de lijst legt
het uit. De API weigert die mutaties toch met een 409, maar de UI laat het slot zien in plaats van die
fout af te wachten.

## De artefact-werkbank

Vanaf **1280px** (`lib/useBreedScherm.ts`) staat het artefact als **eigen kolom naast de chat**:
`Dialog`-variant **`kolom`**, zonder backdrop, `aria-modal` en focus-trap (die zou je opsluiten
terwijl de chat ernaast bereikbaar moet zijn); Escape sluit in alle varianten. Daaronder is het de
`side`-sheet (mobiel een bottom-sheet). De splitsing zit in `WerkplekClient` en niet in
`WorkbenchShell`, anders moeten `docs`/`infos` en alle handlers omhoog en weer omlaag.

Wettekst en reviewlijst hebben **elk een eigen scroll** (tekst `max-h-[45%]` bovenin), zodat de tekst
niet uit beeld loopt als je verderop in de lijst bent. Selecteren scrolt **beide kanten** in beeld:
de markering (`DocumentPaneel`) en de kaart (`ReviewQueue`), met respect voor
`prefers-reduced-motion`.

- **De kaart is compact**; toelichting, uitleg van de review, alternatieven en opmerking vouwen open
  bij selectie. Eén begrip stuurt alles: `actief`.
- **Eén vaste volgorde** (`sorteerReview`): JAS-tabelvolgorde (`jasVolgorde`) → lid (numeriek) → plek
  in de tekst → invoervolgorde. Geen van die sleutels verandert door reviewen, zodat je je plek niet
  kwijtraakt; scherpstellen doen de filters (*alles* / *te beoordelen* / *met aandacht*). De positie
  per element komt uit dezelfde `vindPositie` als de markeringen in de tekst, dus lijst en tekst
  spreken elkaar nooit tegen.
- **Zwevende markeringen worden benoemd.** Is een fragment niet meer in de tekst te vinden
  (`vindPositie` → `-1`), dan staat dat op de kaart en in de teller.
- **Toetsenbord**: `j`/`k` (of ↓/↑) door de getoonde lijst, `a` akkoord, `x` verwerpen, `c` klasse,
  `Escape` loslaten. De listener doet **niets zolang de focus in een invoerveld staat** – anders keur
  je iets goed door "a" te typen. Na *Akkoord* springt de selectie naar het volgende dat aandacht
  vraagt; knop en toets lopen via dezelfde `onAkkoord`.
- **Volgorde en open bedieningsrij leven in `ArtefactPaneel`/`ArtefactInhoud`**, niet in de lijst:
  zo doorloopt het toetsenbord dezelfde volgorde als je ziet, en staat er nooit op twee kaarten
  tegelijk een rij open.

### De reviewkaart

- **Geen badge is een gewoon voorstel.** De annotatieketen zet `aandacht` alleen als er iets te
  zeggen valt: **groen = "Bevestigd door review"** (een twijfelgeval dat de gerichte review besliste),
  **geel = "Keuze voor jou"** (twijfel die de reviewer niet besliste). De UI kent ook **rood =
  "Waarschijnlijk fout"**, maar de keten zet dat niet: de resolver in graph-qa geeft alleen groen of
  geel. Het veld `review_uitleg` draagt de uitleg van de review en staat uitgeklapt als "Review: …".
- **De aandacht is een badge met tekst**, in dezelfde vorm als de documentstatus-badge
  (`AANDACHT_PILL` in `ReviewQueue.tsx` naast `DOCUMENT_STATUS_STYLE`): één badgevorm in de app. Kleur
  doet mee via de linker accentrand en de zachte tint (het scan-signaal), maar draagt het oordeel niet
  alleen. De badge staat op volle sterkte terwijl de kaart dezelfde tint op 40% draagt – anders
  verdwijnt hij in zijn kleurfamilie.
- **De kaartkop is mobiel gestapeld en op `sm:` één regel**: aandacht-badge en lidnummer mét de
  acties, de klassebadge daaronder over de volle breedte. Klassenamen zijn canoniek en mogen niet
  korter ("Parameter en parameterwaarde"), dus de ruimte moet mee.
- **Het lidnummer staat alleen op de kaart als het document meer dan één lid beslaat** (`toonLid`,
  afgeleid van `doc.lid`, niet van de elementen – anders verschijnt en verdwijnt het tijdens het
  reviewen).
- **Waarom?** (`components/annotaties/WaaromUitklap.tsx`, logica in `lib/waarom.ts`) toont het
  herkomstspoor van het element (`trace`): wie besliste, het bewijs, twijfel, resolutie, controles
  en het subtype, met de ruwe modelvraag onder *Technisch detail*. Codes worden leesbare namen via
  `GET verklaringen` (`lib/verklaringen.ts`, één keer per pagina); het id staat in de tooltip, en een
  onbekende code verschijnt als zichzelf. Dezelfde uitklap staat in de graafinspector bij een
  markering; ligt die buiten de weergave van het paneel, dan haalt hij het element pas bij openklappen
  op (`haalElement`). Onder *Technisch detail* staan, pas bij openklappen opgehaald
  (`haalElementGraaf` → `GET elementen/{id}/graaf`), de graafcontrole van de laag
  (`graafStatusTekst`: alleen een afwijking vraagt aandacht) en de RDF van de markering. Een kandidaat zonder zinsontleding krijgt de badge *gedegradeerd*. De
  alternatief-chips dragen de twijfelreden uit het spoor als tooltip. `api/tests/test_verklaringen_frontend_drift.py`
  bewaakt dat de secties die de werkplek leest bestaan.
- **Andere grens**: onder de alternatieven staan de grensopties van de keten als chips
  (`grensOpties` in `lib/annotatieNodeAdapter.ts`: tekst uit de bron, zonder de huidige grens en
  zonder dubbelen). Een klik stuurt `{type: "grens", wijziging: {optie}}`; het anker rekent de api.
- **Geen lifecycle-jargon in beeld**: "voorstel van Lex" / "door jou aangepast" / "door jou
  gemarkeerd" + tijd. Het volledige spoor staat in het auditlog.

### Reviewen zonder formulier

Elk veld schrijft zichzelf weg. Bij een edit stuurt de client géén `review_reason`: de beslissing
legt de correctie zelf vast (`wijziging` en de oude waarden in `voor`), en vragen wat je zojuist deed
is dubbelop. Bij **verwerpen** blijft de reden een vraag aan de jurist; die staat in geen correctie.

- **Klasse** = de badge zelf; klikken opent het palet, een klasse kiezen ís de wijziging.
- **Toelichting** is een inline veld (Enter/blur bewaart, Escape annuleert). Een gevulde toelichting
  leegmaken vraagt een tweede klik: één misklik, en er is geen undo.
- **Bevestigen doet de knop zelf.** Onomkeerbare handelingen vragen een tweede klik op dezelfde plek
  (`components/ui/BevestigKnop.tsx`), nooit `window.confirm`: een systeemvenster is niet te stylen,
  niet te testen en soms geblokkeerd. Scherp gezet ontwapent de knop vanzelf (4 s, blur of Escape).
- **× betekent weghalen**, met twee uitkomsten: een agent-voorstel klapt de redenen-chips uit (één
  klik = verworpen, terug te draaien met *Heropenen*); een eigen markering wordt "Wissen?" en is na de
  tweede klik weg (`DELETE`). Een agent-voorstel verwijder je niet maar verwerp je, zodat het
  auditspoor laat zien dát er een voorstel was.
- **Een oordeel vergrendelt de kaart.** Bij `human_approved`/`rejected` (`isVergrendeld`; een ander
  begrip dan `isBeslist`, dat de filters en de telling stuurt) zijn klasse en toelichting alleen-lezen
  en zijn *Akkoord*, het kruisje, de alternatieven en de kanttekening-acties weg; **Heropenen**
  (`type: "heropen"`) zet het element terug in de review. Zonder vergrendeling zouden badge en
  toelichting na een akkoord stil een `edit` wegschrijven. Een **opmerking** mag wél op een vergrendeld
  element; `edited` vergrendelt niet (anders wringt er een heropening tussen klasse en toelichting);
  een **eigen markering** vergrendelt niet, want die is `human_approved` bij het aanmaken.
- **Verworpen markeringen tellen niet als "inmiddels gemarkeerd"** (`alGemarkeerd` in
  `lib/annotatie.ts`, voor de ongedekte zinsdelen uit de dekking), net zoals `DocumentPaneel`
  verworpen markeringen niet oplicht.
- **Fragment inkorten/uitbreiden**: klik de markering aan en selecteer opnieuw. Overlapt de selectie
  de actieve markering (`overlaptSelectie` + `vindPositie`), dan biedt `SelectiePopover` bovenaan
  *Fragment aanpassen* aan, mét een nieuw anker. Geen overlap = een nieuwe markering. Bewust een klik:
  een selectie die je maakte om te lezen mag nooit stil een annotatie wijzigen.

**De dekking is het vangnet voor wat ontbreekt.** graph-qa meet per bronnode welke detectiedimensies
draaiden en welke zinsdelen geen enkele kandidaat opleverden; de api geeft dat mee in de weergave
(`dekking.structureel`). Een meting, geen gok en geen recall.
- `ongedektVanNode` (`lib/annotatieNodeAdapter.ts`) vertaalt de zinsdelen naar de samengestelde bron
  en laat een deel weg als de tekst daar niet letterlijk staat; `nogOngedekt` haalt weg wat een
  actueel, niet-verworpen element al raakt.
- `DocumentPaneel` onderstreept ze gestippeld (standaard aan, *Verbergen* in de balk erboven).
  `segmentenVanBlok` knipt erop, de actieve markering gaat voor, en de segmenten blijven samen
  exact de regel. Een klik op een onderstreept zinsdeel opent dezelfde `SelectiePopover` met het
  hele deel: zelf markeren zonder de grenzen te trekken.
- `DekkingOverzicht` in de `extra`-haak toont per bronnode hoeveel dimensies volledig draaiden en
  welke niet (`lib/dekking.ts`).

### Zelf annoteren (tekstselectie)

De jurist selecteert tekst in `DocumentPaneel` en markeert die zelf. Eigen markeringen gaan via
`POST elementen` (`NodeAnnotatiePaneel.eigenMarkering`; niet de batch, dat is de uitkomst van een
agent-ronde) en zijn meteen `human_approved`.

- **Een selectie eindigt niet altijd met een muisklik.** Naast `onMouseUp` luistert `DocumentPaneel`
  op documentniveau naar `keyup` (Shift+pijltjes, WCAG 2.1.1) en `touchend` (selectiegrepen op een
  aanraakscherm). `ArtefactInhoud.sluitSelectie` ruimt de DOM-selectie op bij het sluiten van de
  popover, anders klapt die bij de volgende tik weer open.
- **De rekenkern staat in `lib/selectie.ts`**; het component doet alleen de `TreeWalker`-wandeling
  (`offsetVanGrens`) en geeft knooplengtes door aan `offsetInBlok`.
- **De tekst staat in blokken, en elk blok draagt `data-offset`.** `offsetVanGrens` telt alleen binnen
  het blok vanaf die startpositie, zodat de weergave (inspringing van leden en onderdelen) los staat
  van de offsets. **Haal `data-offset` niet weg** – dan landt elke markering stil op de verkeerde
  tekst.
- **Een markering wordt op de blokgrens geknipt** (`segmentenVanBlok`): een `<mark>` kan niet over
  twee blokken, dus het worden twee `<mark>`s met dezelfde klasse en hetzelfde id, optisch verbonden
  door `box-decoration-clone`.
- **De structuur komt uit `lib/wetstructuur.ts`** (`ontleed` + `blokkenVan`). Het nestingniveau is
  **afgeleid uit de nummervorm**: de echte nesting staat in de graaf, maar het artefact krijgt de tekst
  als `leden_teksten` (`{lid, tekst}[]`, door `lib/annotatieNodeAdapter.ts`). Een fout geeft hooguit een scheve marge, nooit een scheve
  markering. `blokkenVan` vangt af dat het lidvoorvoegsel `"1. "` dezelfde vorm heeft als een
  onderdeelnummer. De testvectoren staan in `wetstructuur.vectoren.json`.
- **De brontekst is een lijst `LidRegel`, geen lijst strings** (`regelsVan`/`bronVan` in
  `lib/annotatie.ts`). Het lidnummer reist mee omdat het **niet uit de volgorde af te leiden** is: bij
  een op één lid afgebakend document is index 0 bijvoorbeeld lid 3, en ingevoegde leden heten 2a.
  `lidUitOffset` leest het daarom uit de regel.
- **Elk element draagt een `anker`**: exacte offsets + quote-met-context + een hash van de bron.
  `segmenteer` gebruikt die in drie stappen (offsets → context → eerste voorkomen), zodat twee
  identieke fragmenten uit elkaar blijven en een markering een herimport overleeft. `vindplaats` is
  de mensleesbare bronaanduiding; daar horen geen offsets in.
- **De tekst toont hoogstens één markering: de geselecteerde.** Twee markeringen kunnen niet op
  dezelfde tekst liggen, dus alles tegelijk kleuren is onleesbaar én onvolledig. De reviewlijst is de
  ingang; de tekst laat zien wáár het gekozen element staat. Nog eens klikken verbergt hem, en een
  verse eigen markering wordt meteen actief. `segmenteer` heeft daardoor geen overlap-prioritering
  nodig; de bevriezingsregel (mens wint) leeft server-side.

### De annotatie exporteren

*Exporteren* in de kop van het artefact (`components/werkplek/ExportKnop.tsx`) biedt **PDF / CSV /
JSON / RDF (TriG)**. De vorm staat in de api (`api/app/annotatie_export.py`); de werkplek kiest alleen.

- **Ook halverwege.** Geen statusdrempel: het bestand zegt zelf hoeveel er nog te beoordelen is.
- **De wettekst komt van de api**, uit de bewaarde bronstand (`snapshot_id`) van de weergave: de
  export gaat over precies de tekst die de jurist zag.
- **De bestandsnaam komt van de server** (`Content-Disposition`); de proxy geeft die header door
  (`PASS_THROUGH_HEADERS`). `NodeAnnotatiePaneel.exporteer` post `weergave/export` en downloadt via
  `downloadAntwoord` in `lib/api.ts` (Blob → `createObjectURL` → `<a download>`), het enige
  downloadpatroon in de app. `ExportKnop` krijgt de download als `onDownload`; in de rondleiding is
  die er niet en sluit het keuzepaneel zonder bestand.
- De export draagt het **volledige spoor** per markering en **met welk model** de agent het voorstel
  maakte (`geproduceerd_door`), in dezelfde leesbare namen als de Waarom-uitklap: CSV met eigen
  herkomstkolommen, PDF met een herkomstzin, beurtmeting en dekking, JSON v3 met schema
  (`GET export-schema`), TriG met de lagen zoals de kennisgraaf ze krijgt.

## De samenhangsgraaf (3D)

`NodeAnnotatiePaneel` heeft naast *Tekst* een tab **3D-graaf** (`components/graaf/SamenhangGraaf.tsx`),
en onder een antwoord met een bron naar een BWB-bepaling staat **Bekijk samenhang in 3D**, dat hetzelfde
paneel op die tab opent. Beide verschijnen alleen als de API de capability `samenhang` meldt
(`samenhangBeschikbaar()`, één keer per pagina).

- **Data**: `GET /v1/annotatie/samenhang` (`api/app/samenhang.py`) via de v2-proxy: bronstructuur van
  het artikel, actuele markeringen met hun JAS-klasse, en de **letterlijke** verwijzingen uit de graaf,
  één stap uit en in. Een doel buiten het artikel is een **randknoop** (gedempt); *Artikel openen*
  haalt dat artikel erbij als eigen cluster. Een niet-geïmporteerd doel heet **extern** en is niet uit
  te klappen. Er wordt niets afgeleid: afstand en positie betekenen juridisch niets, en dat staat in
  beeld.
- **Rekenkern in `lib/samenhang.ts`** (samenvoegen, layout, zichtbaarheid, filters, `bronDoel` voor
  jci/graaf-IRI → bronnode, `hoofdactie`, `relatieGroepen`). De layout is een 3D-krachtsimulatie
  (`d3-force-3d`, dezelfde engine als de renderer) vanuit radiale startposities, per artikelcluster
  gerekend en daarna vast (`fx/fy/fz`): reproduceerbaar, en bijladen verschuift de bestaande kaart
  niet. Hij draait in `lib/`, niet in de canvas – anders herrekent elke uitklapping alles.
- **Weergave**: straal per soort, gebogen verbindingen met pijl, alles buiten de selectie gedimd, vaste
  labels alleen voor selectie en buren (de rest als tooltip, `.samenhang-tip` in `globals.css`, tekst
  altijd ge-escaped), camera vliegt naar de gekozen knoop.
- **three.js laadt lui**: `SamenhangGraaf` en `GraafCanvas` via `next/dynamic` met `ssr: false`. Zonder
  WebGL of na contextverlies blijven zoeken, Lagen en de inspector bruikbaar.
- **Bediening als een kaart-app.** In de graaf: **klik** kiest, **dubbelklik** toont/verbergt de
  verbindingen of opent een randknoop (`isDubbelklik`, 300 ms – de bibliotheek kent alleen
  `onNodeClick`), **achtergrond** heft de selectie op, **hover** geeft de naam. Daarbuiten één vaste
  plek per vraag, zwevend in het canvas: **zoeken** linksboven (`GraafZoek`, over alle knopen, ook
  verborgen), **Omgeving | Alles** rechtsboven (terug naar Omgeving herstelt je stand), **Lagen**
  linksonder (`GraafLagen`: filters en legenda), **Alles in beeld / in- / uitzoomen** rechtsonder
  (`GraafBeeld`) en een eenmalige hint (`GraafHint`, `localStorage` in try/catch).
- **De inspector** (`GraafInspector`): soort en naam, *Centreren* en ✕, en precies **één gevulde
  hoofdactie** (`hoofdactie()`): *Toon in tekst* (bron of markering binnen het artikel), *Artikel
  openen* (geïmporteerde randknoop), niets bij een klasse of extern. Daarnaast *Vraag Lex* (niet bij
  een klasse) en *Verbindingen tonen (n)* (dezelfde handeling als dubbelklik). Relaties per soort als
  uitklapgroepen. Breed staat hij rechts, smal onder de graaf en ingeklapt tot kop + hoofdactie.
- **Annotaties staan er meteen.** Met de laag *Annotaties* aan (default) toont de omgeving naast de
  bronstructuur alle markeringen met hun klasse; alleen verwijzingen naar buiten vragen om uitklappen.
  De laag uitzetten is de weg naar rust.
- **Kiezen klapt tijdelijk uit, dubbelklikken zet vast.** De omgeving is wat je zelf uitklapte
  (`uitgebreid`). Een gekozen knoop die verborgen was, klapt uit zolang hij gekozen is; dat is
  **afgeleid, niet opgeslagen** (`tijdelijk` in `SamenhangGraaf`) – sla het niet op in `uitgebreid`,
  anders blijft elke ooit aangeklikte knoop voorgoed staan. De schakelaar klapt zo'n knoop in zolang
  hij gekozen is (`ingeklapt`).
- **Eén selectie**: de gekozen markering is in tekst en graaf dezelfde (`actiefId` van het paneel).
  *Toon in tekst* wisselt naar de tekst en scrolt naar het lid (`data-lid` op de blokken van
  `DocumentPaneel`). *Vraag Lex* gaat voor een markering via `onVraag`; voor een bron zet het een
  gewone vraag met vindplaats klaar – geen eigen agentcontract.
- **Vergroten** gebruikt de `Dialog`-variant `fullscreen`. De stand staat daarom in de hook
  `useSamenhangStand` in het paneel, niet in de graaf: een variantwissel remount de inhoud. **Escape**
  van binnen naar buiten: zoeklijst → Lagen → selectie → verkleinen → sluiten.
- **Markeringsfilter** (in *Lagen*, alleen met de laag Annotaties aan): alle / nog te beoordelen /
  keuze voor de jurist (geel) / door een jurist gemarkeerd / met twijfel. De markeringsknoop draagt
  daarvoor `herkomst`, `aandacht`, `subtype`, `beslist_door` en `twijfel` (`api/app/samenhang.py`).
  Een kijkfilter: hij verbergt markeringen en klassen die dan niets meer markeren
  (`pastBijMarkeringFilter` in `zichtbareGraaf`), nooit structuur of verwijzingen. De inspector
  toont herkomst en aandacht als pil.
- **Laag Dekking**: de zinsdelen zonder detectortreffer uit het paneel (`ongedektPerBron` in
  `lib/dekking.ts`, sleutel = bron-IRI = knoop-id) geven een lid of onderdeel een okerkleurige halo
  (`DEKKINGSKLEUR`) en in de inspector een blok *Zonder detectortreffer*. Het is een kenmerk, geen
  relatiegroep: `toonDekking` staat los van `filters` en raakt Omgeving/Alles niet. Alleen de
  bronnodes van de geopende bepaling hebben een meting; de legenda zegt dat.
- **Live bij een annotatiewijziging**: `NodeAnnotatiePaneel` roept na elke mutatie (`muteer`,
  `status`) `graafStand.ververs()` aan. Die haalt elk geladen deel opnieuw op (per artikel vervangen);
  `bouwGraaf(delen, vorige)` houdt bestaande knopen op hun plek.
- Browserregressie: `scripts/test-samenhang.mjs`.

## Buiten de schil

Alles wat geen app-schil is – inloggen, 2FA, de eerste beheerder, registratie, de blokkerende
disclaimer en de fout-/laadpagina's – gebruikt **`components/auth/AuthFrame.tsx`**: een gecentreerde
kaart op `bg-surface` met het logo erboven. Bewust geen vervaagde werkplek achter het inlogscherm: dat
leest als "hij laadt", niet als "log eerst in".

- **De app-schil scrollt niet mee, ook niet op mobiel.** De body is `min-h-screen min-h-[100dvh]`:
  `100vh` is op mobiel de viewport zonder adresbalk, waardoor het document kan scrollen en de strook
  en topbar wegschuiven; `100dvh` volgt de zichtbare hoogte. Daarnaast staat
  `overscroll-behavior: contain` op elke scroller (`globals.css`), anders geeft een paneel aan zijn
  einde de scroll door aan het document (rubber-banding op iOS, pull-to-refresh op Android).
- **Een venster is zo hoog als zijn inhoud, tenzij die wisselt.** `Dialog`-variant `center` houdt een
  vaste hoogte (42rem) voor het instellingenvenster, dat anders bij elke tabwissel springt; `compact`
  groeit mee tot een plafond, voor een formulier of een lap tekst (feedback, voorwaarden).
- **De disclaimer heeft twee schillen, één tekst.** De edge-gate (`auth.config.ts` → `vereistAkkoord`)
  stuurt je zonder akkoord naar `/disclaimer`, de blokkerende volle pagina in `AuthFrame`. Klik je de
  teststrook aan vanuit de werkplek, dan onderschept `app/@modal/(.)disclaimer/page.tsx` dat pad en
  opent `DisclaimerDialog` over de werkplek – zelfde `DisclaimerClient`.
- **In een dialoogschil sluit je met `router.back()`, nooit met een link.** `DisclaimerClient` krijgt
  daarvoor `onSluiten`; kruisje, achtergrondklik, Escape en de knop onderin lopen erdoor. Een link
  sluit een intercepting-route-modal niet (het modal-slot houdt zijn toestand vast bij een soft
  navigation) en voegt een history-entry toe, waarna het kruisje je terugbrengt náár de dialoog.

## Berichten, feedback en rondleiding

- **Berichten** (release notes) – `BerichtenPanel` is de bel in de sidebar-kop met een
  ongelezen-badge; het archief is de tab `/instellingen/berichten`. Let op de naam: `Bericht`/
  `BerichtInvoer` in `lib/types.ts` zijn **chatbeurten**, `BerichtOut` en familie zijn release notes –
  twee API-domeinen (`/v1/gesprekken/…/berichten` vs `/v1/berichten`).
- **Feedback** – `FeedbackDialoog` opent vanuit het gebruikersmenu onderin de sidebar, bewust niet als
  zwevende knop: die valt over de chat-invoer. De ongelezen-teller voor beheerders is een badge op de
  feedbacktab (`TabDef.badge`).
- Beide halen hun teller periodiek of bij openen op en falen **stil**: een badge is een hint en mag de
  werkplek niet blokkeren.
- **Rondleiding** – `components/rondleiding/` loopt langs elementen met `data-tour="<anker>"` in de
  werkplek. Stappen, teksten en de opgeslagen stand (`localStorage`, faalt stil) staan in
  `lib/rondleiding.ts`; de voorbeeldscène in `lib/rondleidingDemo.ts` gebruikt letterlijke wettekst,
  ankers die met `maakAnker` over dezelfde brontekst berekend zijn, en raakt de API niet. Het type
  `ThreadItem` staat daarom in `lib/threadItem.ts`, zodat `lib/` geen component hoeft te importeren.

## Toegankelijkheid (WCAG 2.2 AA, NLDS-niveau)

- Markeringen in de tekst zijn **`<mark role="button" tabIndex={0}>`** met een `onKeyDown` voor
  Enter/Space: bedienbaar met het toetsenbord (2.1.1) maar **inline**. Een echte `<button>` is
  inline-block en wordt bij een markering over twee regels een rechthoekig blok. Daarbij hoort
  `box-decoration-clone`, anders krijgt alleen het eerste regelfragment een linkerrand.
- **Klikdoelen ≥ 24×24 CSS-px** (2.5.8) via `min-h-[24px]`, met de `coarse:`-variant naar 44px op
  aanraakschermen (AAA 2.5.5, dat NLDS aanhoudt).
- **Een uitklapper blijft binnen het scherm.** `components/ui/Popover` meet na het openen en corrigeert
  horizontaal (`lib/popover.ts:klemHorizontaal`); verticaal kiest de aanroeper (`top-full`/
  `bottom-full`). Een paneel dat de kolombreedte moet volgen gebruikt `positie="inset-x-3 …"` met
  `containerClassName="static"` (berichtenbel, gebruikersmenu). `SelectiePopover` hangt aan een
  muispositie en klemt zichzelf via `plaatsPopover`.
- Eén **`.focus-ring`-utility** in `globals.css` (2.4.13, AAA): een dubbele ring die ook op de donkere
  JAS-kleuren opvalt. Gebruik die in plaats van een eigen `focus-visible:outline`.
- Elke beslissing wordt **aangekondigd** via de `sr-only aria-live`-regio in `WerkplekClient`
  (`beslissingMelding`); anders is annoteren voor een schermlezer stil.
- **Escape en Tab zijn voor het bovenste venster.** `Dialog` houdt een stapel bij; alleen het
  bovenste venster reageert, en bij sluiten gaat de focus terug naar waar hij vandaan kwam. `Popover`
  en een scherpe `BevestigKnop` vangen hun Escape in de capture-fase af. De sneltoetsen van het
  artefact (`j/k/a/x/c`, `[`/`]`) werken alleen met de focus in het artefact (`focusBijArtefact`):
  in de kolomvariant staat de chat ernaast, en een `a` op een chatknop zou anders het gekozen element
  goedkeuren.

## Observability

`instrumentation.ts` registreert OpenTelemetry via `@vercel/otel` (alleen met
`OTEL_EXPORTER_OTLP_ENDPOINT`; tracing van route handlers en uitgaande `fetch`). **`@vercel/otel` zet
zelf geen `traceparent` op de request**, dus de keten valt dan stil uiteen in losse traces per dienst.
`lib/trace.ts` injecteert hem: **elke fetch naar een upstream loopt door `metTrace()`**, ook in routes
die hun eigen fetch doen. Zonder OTel is het een no-op.

`lib/logger.ts` is de **server-only** JSON-logger (secret-redactie, `LOG_LEVEL`, `trace_id`/`span_id`),
gebruikt in `proxy.ts`, `lib/server.ts` en de routes die zelf fetchen (run, artikel, gesprekken,
ui-spoor). Nooit importeren in een Client Component, nooit tokens, secrets of inhoud loggen. In vitest
wordt `server-only` gestubd (`vitest.config.ts` → `test/stub-empty.ts`).

**De klik zelf laat een spoor na.** `lib/uiSpoor.ts` → `POST /api/ui-spoor` meldt per handeling
`gestart` en de uitkomst (`metSpoor(...)` om de call). Zo is "ik klik en er gebeurt niets" te
onderzoeken: een klik die nooit een request werd, laat in `proxy()` niets achter. De actienamen staan
in een **gesloten lijst** – een vrije naam zou gebruikersinhoud (een gesprekstitel) de logs in trekken
– en de route weigert al het andere. Gebruik het op mutaties die kunnen blijven hangen, niet op elke
knop. Zie `docs/observability.md`.

## Regels (niet aan tornen)

- **Token nooit naar de client.** Geen import van `lib/config.ts`/`lib/server.ts` in Client
  Components; geen token in `NEXT_PUBLIC_*`. Nieuwe upstream-calls lopen via een Route Handler.
- **Geen onbetrouwde waarde rechtstreeks in een `href`.** Velden van de agent (`bronreferentie`,
  `verwijzing.doel.target`) kunnen een `javascript:`/`data:`-scheme bevatten; React escapet tekst,
  niet de scheme. Route ze via **`bronHref`** in `lib/url.ts` – één functie voor alle vormen (jci,
  graaf-IRI `urn:bwb:…`, kaal BWB-id, complete wetten.overheid.nl-URL); onbekend → `undefined` ⇒
  platte tekst. Zet er geen tweede helper naast: een graaf-IRI achter `wetten.overheid.nl/` plakken
  komt door de hostcontrole en levert een link naar een 404.
- **Status en headers ongewijzigd doorgeven.** De API bezit het gedrag (409 bij verkeerde state, 429 +
  `Retry-After`, 404 op andermans id); de BFF maskeert dat niet. Eén uitzondering aan de clientkant:
  een **401** betekent "geen geldige sessie", en `parseError`/`nodeError` sturen dan naar `/login`
  (`naarInloggen`). De middleware geeft op `/api/*` zonder sessie daarom een 401 als JSON en geen
  redirect – `fetch` zou die volgen naar de HTML van het inlogscherm.
- **Route-params altijd via `pathSegment`, en die weigert `.`/`..`.** `encodeURIComponent("..")` is
  `..`, en `fetch` normaliseert dat upstream weg: een param kan zo via `/v1/annotatie/lagen/../../…`
  bij elk `/v1/*`-endpoint uitkomen. De middleware weigert zulke paden met 400 (`isPuntSegment` in
  `auth.config.ts`); `pathSegment` en de v2-catch-all zijn het tweede net. Nooit een kale
  `encodeURIComponent` op een param.
- **Admin-pad apart.** `/api/admin/*` → `proxy(..., { admin: true })` → `/v1/admin/*`. Meng de twee
  tokens niet.
- **Login = Auth.js (NextAuth v5), de API is de identiteitsbron.**
  - `auth.ts` + `auth.config.ts`; `proxy.ts` (de Next 16-opvolger van `middleware`) bewaakt elke
    route en stuurt niet-ingelogden naar `/login`. De **matcher** verankert de bestandsextensies op het
    einde en zondert `/api/` daarvan uit, anders valt een route-parameter die op een bestandsnaam lijkt
    (`/api/gesprekken/abc.png`) buiten de gate. `proxy.test.ts` leest het patroon uit de bron; houd de
    matcher een **letterlijke string**, want Next analyseert hem statisch.
  - Inloggen gaat uitsluitend met de userid; e-mail is verplicht en uniek maar geen inlog-identiteit.
    De sessie is een httpOnly JWT-cookie (`AUTH_SECRET`) met `userid` + rol; de Credentials-provider
    verifieert bij de API (`verifyCredentials` → `/v1/auth/verify`). De API bewaart users, hash en
    TOTP; de BFF alleen de sessie.
  - Rollen: **`beheerder`** (beheertabs + `/api/admin/*`) en **`analist`**, afgedwongen in de
    `authorized`-callback (edge) én in `app/instellingen/[[...tab]]/page.tsx`
    (`isAdminTab(actief) && !isBeheerder` → redirect). `/setup` maakt eenmalig de eerste beheerder.
  - **Zelfregistratie**: `/registreren` (`RegistratieClient` → `/api/registreren`) legt een
    *aanvraag* vast, geen account. De API leidt de userid af uit voor- en achternaam en bewaart de
    bcrypt-hash van het gekozen wachtwoord; pas bij goedkeuring in de tab **Aanvragen**
    (`RegistratiesPanel`) ontstaat de gebruiker, met dat wachtwoord. **Afwijzen verwijdert de
    aanvraag** ("Afwijzen en verwijderen"), zodat e-mailadres en volgnummer vrijkomen. Er gaat bewust
    geen e-mail: wie inlogt terwijl zijn aanvraag loopt, krijgt de `code` `aanvraag_open` uit
    `/verify` (afgehandeld in `LoginClient` naast `totp_required`) – alleen bij het **juiste
    wachtwoord**, anders is het een middel om te ontdekken wie een aanvraag heeft.
  - **2FA (TOTP)** is optioneel en self-service in de accounttab. De account/2FA-routes zetten
    `X-User-Id` uit de sessie, nooit uit browser-input.
  - Auth.js' eigen routes leven onder `/api/auth/*`; zet daar geen eigen BFF-route bij (daarom
    `/api/setup`, `/api/registreren`, `/api/login-verify`, `/api/login-2fa`). Publieke paden staan in
    `isPublic()` in `auth.config.ts`; vergeet je er een, dan stuurt de gate een bezoeker zonder account
    naar `/login`.
- **Sessie-revocatie en CSRF.** De sessie is rollend: `session.maxAge` = `SESSIE_LANG` (30 dagen,
  cookie-bovengrens) + `updateAge` 1 dag in `auth.config.ts`; de custom `jwt.encode` in `auth.ts` zet de
  effectieve `exp` op 30 dagen bij *Ingelogd blijven op dit apparaat* (`token.rememberMe`), anders
  `SESSIE_KORT` (12 uur). Die ene checkbox op `/login` (default uit) stuurt ook de trusted-device-cookie
  (2FA overslaan); de keuze reist via `sessionStorage` (`wa_login_remember`) naar `/login/2fa`.
  **Een TOTP-code geldt één keer**: `/api/login-2fa` verbruikt hem en de API geeft een 2FA-ticket, dat
  in dezelfde httpOnly cookie als het login-ticket komt; `authorize` stuurt het bij de signIn mee en
  wist daarna de cookie. De node-`jwt`-callback herverifieert elke 5 min (`HERVERIFICATIE_MS`) de
  accountstatus (`getAccountStatus` → `/v1/auth/me`): een gedeactiveerd account invalideert de sessie,
  een rolwijziging werkt direct door. De edge draait de lichte variant zonder herverificatie
  (`lib/server.ts` is node-only); elke `auth()` in Server Components en route handlers herverifieert
  wél, en die 5 minuten zijn de feitelijke revocatiegrens. De `authorized`-callback handhaaft een
  **Origin-check** op muterende `/api/*`-calls (incl. `/api/login-verify`): vreemde Origin → 403,
  zonder Origin valt het terug op `SameSite=Lax`. De cookie-flags staan expliciet in `authConfig`.
- **Tokenbudget zichtbaar en begrenzend.** De stand komt van de API (`/api/account/verbruik` →
  `/v1/verbruik`) en wordt op één plek opgehaald – `WorkbenchShell` – zodat de drie weergaven niet
  uiteenlopen: de meter in het gebruikersblok van `GesprekSidebar`, de strook bovenin de werkplek en de
  blokkade van de invoerbalk in `WerkplekClient`. Verversen gebeurt na elke beurt (`onBeurtKlaar`), met
  60 s als vangnet.
  - **De strook wordt uit de serverstand afgeleid**, niet uit een clientvlag, zodat hij niet blijft
    hangen als hij niet meer geldt. Wegklikken duurt één sessie; bij 100% kan het niet, want dan is het
    de reden dat de invoer dicht is.
  - **De drempel komt van de server** (`stand.waarschuwing`). `WAARSCHUWINGSDREMPEL` in
    `lib/tokenbudget.ts` en `METER_WAARSCHUWING` in `ui/Meter` bestaan alleen voor de meterkleur en
    moeten dezelfde waarde houden als de API.
  - De gebruiker ziet het volledige beeld in de tab **Verbruik** (`VerbruikPanel`); de beheerder stelt
    het beleid in bovenaan de tab **Gebruikers** (`BudgetBeleidBlok`), met per gebruiker een afwijkend
    budget – een budget hoort bij wie er werkt, niet bij het model.
- **CSP met een nonce per request, geen inline scripts.** `proxy.ts` zet de Content-Security-Policy
  (`lib/csp.ts`): `script-src 'self' 'nonce-…' 'strict-dynamic'`, zonder `'unsafe-inline'`. Next zet
  het nonce zelf op zijn scripts; lui geladen chunks (`next/dynamic`, three.js) mogen via
  `'strict-dynamic'`.
  - **Geen eigen inline `<script>` en geen `next/script` met inline code**: die krijgt geen nonce en
    wordt in productie stil geblokkeerd. Nodig? Lees het nonce met `(await headers()).get("x-nonce")`
    in een Server Component en geef het mee.
  - **Elke pagina rendert dynamisch** (`app/layout.tsx` roept `auth()` aan); een statische pagina kan
    geen nonce krijgen.
  - `style-src` houdt `'unsafe-inline'`, omdat de server-render `style="…"`-attributen meegeeft en een
    nonce niet voor attributen geldt.
  - De CSP staat **niet** in `next.config.mjs` (dat zet alleen de overige security-headers): twee
    CSP-headers gelden allebei, en een statische versie zou inline scripts weer toelaten.

## Commando's

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000 (API óók op 3000? → npm run dev -- -p 3001)
npm run build        # productiebuild (output: 'standalone')
npm run lint         # ESLint
npm run typecheck    # tsc --noEmit
npm test             # vitest (node-env, geen DOM)
npm run test:browser # Playwright op de echte Next-UI met gemockte BFF (scripts/test-*.mjs)
```

`test:browser` draait `scripts/test-annotatie-nodes.mjs`, `test-samenhang.mjs`, `test-reeks.mjs` en
`test-toetsen.mjs`, en verwacht een devserver op poort 3109
(`AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109`).
Praat met **`localhost`**, niet met `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin,
waarna de pagina niet hydrateert en elke stap zonder duidelijke fout time-out.
`scripts/test-toetsen.mjs` bewaakt wat alleen in een browser te zien is: sneltoetsen alleen met de
focus in het artefact, Escape voor het bovenste venster, focus terug na sluiten, geen herstellus na
een geslaagde beurt, een vraag die blijft staan tijdens het laden, en zelf markeren op een
aanraakscherm (`TOUCH_ENGINE=webkit` voor de Safari-engine, als het systeem die kan draaien).

Lokaal draaien vraagt een bereikbare API en graph-qa plus `.env.local` (zie de README).

**Vóór een commit: `npm test && npm run lint && npm run typecheck`.** De rekenkern staat in `lib/`
zodat hij getest kan worden; de tests overslaan maakt die keuze zinloos. CI
(`frontend-docker-publish.yml`) draait dezelfde drie plus `npm run build`.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
