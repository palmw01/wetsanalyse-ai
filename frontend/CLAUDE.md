# CLAUDE.md – wetsanalyse-frontend

Next.js (App Router) + TypeScript-webapp bovenop de graph-qa-agent en, voor login, beheer en
opslag, de [wetsanalyse-API](../api). De app **is de werkplek**: `/workbench` (de *Lex-pagina*) –
één chat-achtig gespreksvenster voor **vragen én JAS-annotatie**, live tegen graph-qa. De home (`/`)
leidt daarheen door.

> **Scope: chat-werkruimte.** De app bestaat uit de werkplek, het annotatie-overzicht, de
> werkgebieden, het begrippenoverzicht, de login-flow en het instellingenvenster (account, verbruik, berichten, en voor beheerders
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
- **`lib/types.ts`** – met de hand afgeleid van `../api/app/annotatie_v2_contracts.py`,
  `gesprek_contracts.py`, `werkgebied_contracts.py` en `begrip_contracts.py`; de bron van waarheid aan de TS-kant. `AnnotatieDocument` is het
  weergavemodel van het artefact, gevuld door `lib/annotatieNodeAdapter.ts`. Wijzigt
  het API-contract, werk dit bij (controle met `openapi-typescript`, zie de README).
  **`lib/jas.ts`** is de presentatie-helper voor de JAS-klassen (kleur, label, `jasVolgorde`); de
  namen en kleuren staan canoniek in `api/app/jas_klassen.py`, en `api/tests/test_jas_kleuren_drift.py`
  bewaakt dat deze kopie niet afdrijft. Verzin er geen
  klassen bij.
- **De rekenkern staat in `lib/`**, niet in componenten: vitest draait node-env zonder DOM, dus alleen
  pure helpers zijn testbaar (`selectie`, `annotatie`, `annotatieOverzicht`, `reeks`, `samenhang`,
  `markering`, `popover`, `wetstructuur`, `lopendeRun`, `rondleiding`, `werkgebied`, `begrippen`,
  `begripVoorstellen`, `kaartVoorstel`, `herbeoordeling`, `begripRelaties`, `begripGraaf`, `begrippenOverzicht`, `artefact`, `bronKandidaten`, `deelvragen`, `onbewaard`, `vraagkaart`, `gesprekGroepen`, `werkgebiedPaden`, …).
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
    `KeuzeKaart`, `VraagDock`, `VragenKaart`, `ReeksBlok`, `HergebruikMelding`, `Markdown`) en het annotatiegereedschap in het
    artefactpaneel (`ArtefactInhoud`, `DocumentPaneel`, `ReviewQueue`,
    `SelectiePopover`, `ExportKnop`).
  - `annotaties/` – het overzicht en de losse annotatiepagina (`AnnotatiesClient`, `AnnotatieKaart`,
    `NodeAnnotatiePaneel`, `AnnotatiePaginaSchil`).
  - `werkgebieden/` – overzicht en pagina van een werkgebied (`WerkgebiedenClient`,
    `WerkgebiedClient`, de tabs `BronnenTab`/`ElementenTab`/`BegrippenTab`/`SamenhangTab`/`HistorieTab`,
    het begrip als leesweergave `BegripPaneel` of als kaart `BegripWerk`/`BegripKaart`/`BegripPassages`,
    `WerkgebiedSchil`, en
    `OpnemenInWerkgebied` voor de annotatiepagina).
  - `graaf/` – de samenhangsgraaf (sigma); de rekenkern staat in `lib/graaf/`.
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
- **Lijsten zijn rijen met een scheidingslijn, geen stapel boxen** (F3a, `components/ui/Lijst.tsx`):
  `Sectie` (kop, telling, toelichting, acties; geen rand), `Lijst` + `LijstRij` (titel, meta, status
  rechts, acties eronder), `Voorstel` (een voorstel van Lex: gele rand links mét de tekst "Voorstel van
  Lex"), `StatusLabel` (pil met tekst; `toon` groen/geel/neutraal alleen als hij een oordeel draagt) en
  `Regels` + `Regel` (naam en waarde, zoals de samenvatting op de vraagkaart). Het voorbeeld is de
  vraagkaart. Geef een rij geen negatieve marge: de scheidingslijn loopt dan buiten de kolom. In gebruik
  bij de werkgebieden (deelvragen, kandidaten, bronselecties); de rest van de app volgt later.

## Werkplek – de Lex-pagina (`/workbench`)

> **De agent heet Lex** in beeld: de paginatitel, het label boven elk antwoord (`ThreadRij`), *Vraag
> Lex*, "voorstel van Lex", "Kanttekening van Lex". In de **code** heet alles `graph-qa` (map, image,
> env-vars) en in het **berichtcontract** blijft de rol `assistant` – de naam is presentatie. De
> **`WerkplekHeader`** draagt een begroeting bij het uur (`lib/begroeting.ts`, pas na het mounten –
> de server kent de lokale tijd niet) en een korte zelfbeschrijving; volledig in de lege werkplek, een
> smalle strook met silhouet (`Skyline`, eigen tekening) en tagline zodra er een gesprek is, en op een
> smal scherm dan helemaal weg. De volledige zelfbeschrijving staat in `tools/graph-qa/agent/prompts.py`
> (§IDENTITEIT), de toon in `docs/schrijfrichtlijn-lex.md`.

`app/workbench/page.tsx` → `WerkplekVenster` → `components/werkplek/WorkbenchShell.tsx`: een
volledige chat-app-shell met bovenaan de klikbare testomgeving-strook (naar de disclaimer). Er is
**geen globale chrome**: `app/layout.tsx` bevat alleen `Providers`, `{children}` en het
`modal`-slot. De shell-pagina's zetten zelf `h-[100dvh] overflow-hidden`; alles daarbuiten gebruikt
`AuthFrame` (zie §*Buiten de schil*).

- **Links de sidebar** (`AppSidebar` → `GesprekSidebar` + `GesprekLijst`): logo, *Nieuw gesprek*,
  de per gebruiker bewaarde gesprekken en onderin het gebruikersblok (instellingen, feedback,
  rondleiding, uitloggen, verbruiksmeter). **De gesprekken zijn ingedeeld zoals projecten** (spoor G1,
  `deelIn` in `lib/gesprekGroepen.ts`): per werkgebied een uitklapbare groep met de eigen gesprekken
  (de stand per browser, `leesDicht`/`bewaarDicht`, in try/catch) en een *+* voor een nieuw gesprek in dat
  werkgebied, daaronder *Recente gesprekken* (los) en ingeklapt *Archief*. Elke rij heeft een menu
  (`GesprekActies`, inline onder de rij omdat de lijst scrolt): hernoemen, verplaatsen, naar recente
  gesprekken, archiveren of herstellen, en verwijderen – dat laatste pas na een eigen bevestiging die eerst
  archiveren aanbiedt en zegt dat annotaties, begrippen en werkgebieden blijven. Alles optimistisch met
  herstel bij een fout, en met `metSpoor` (`gesprek_archiveren`, `gesprek_verplaatsen`). Onder `lg` is het een off-canvas drawer via **`Dialog`
  met variant `drawer`** – niet als eigen constructie, want `Dialog` levert de enige focus-trap in de
  codebase; zonder die trap loopt Tab achter de scrim door naar de chat.
- **Rechts het chatvenster** (`WerkplekClient.tsx`): vragen én annotatie, beide als run bij
  graph-qa's unified agent. De thread hydrateert uit het actieve gesprek en **persisteert elke beurt**
  naar de API (`/v1/gesprekken/*`). De shell remount het venster (via `key`) alleen bij echt van
  gesprek wisselen, niet wanneer een verse chat bij de eerste beurt zijn id krijgt – anders breekt de
  stream. De graph-qa `conversation_id` (thread_id) is het `gesprekId`.
- **Wat Lex oplevert is een artefact** (`Bericht.artefact`, `lib/artefact.ts`): `{soort, ref, titel}`
  met soort `annotatie`, `begrippen`, `bronnen`, `werkgebied`, `deelvraag`, `begrip` of `regels`. Elke soort heeft een chip in de thread en een paneel
  in dezelfde schil (kolom vanaf 1280px, anders een sheet); er staat er hoogstens één open.
  - **annotatie** – het `annotatie`-item met `AnnotatieChip`, dat **`NodeAnnotatiePaneel`** opent
    (een bericht zonder bronnode wijst naar een verwijderde annotatie: een tombstone). `DocumentPaneel` toont de wettekst met de **letterlijke** fragmenten
    (`segmenteer` + `lib/jas.ts:jasStyle`), `ReviewQueue` de beslissingskaarten.
  - **begrippen** en **bronnen** – het `artefact`-item met `ArtefactChip`, dat
    **`WerkgebiedArtefactPaneel`** opent: dezelfde `BegripVoorstellen` (`inklapbaar={false}`) of
    `BronKandidaten` als op de tab Begrippen of Bronnen, met een link naar het werkgebied. Eén inhoud,
    twee schillen (`werkgebiedArtefactVan` in `lib/artefact.ts`). De voorstellen zijn altijd die van de
    laatste ronde; wijst de chip naar een eerdere (`ref.run_id`), dan zegt het paneel dat.
  - **begrip** (F3d) – een taak van de begrippen-agent op één begrip ("geef voorbeelden van termijn",
    *Werk het begrip volledig uit*) levert `ref: {werkgebied_id, begrip_id, kaart_run_id?, actie?}`. Een
    bericht van vóór F3d droeg dat als `begrippen` mét `begrip_id`; `parseArtefact` maakt er `begrip` van.
    Het paneel is **`BegripPaneel`**: een leesweergave (naam, status, termen, definitie met herkomst,
    uitleg, voorbeelden, relaties ingeklapt), de open voorstellen van Lex per veld (`KaartVoorstelKaart`:
    overnemen, aanpassen, afwijzen) en een kleine bewerking van definitie en uitleg (`handmatigeInhoud`: een
    gewijzigde definitie heet *geformuleerd*), met de onbewaard-bewaker. **Geen Lex-knoppen** – dat vraag
    je in het gesprek. *Open het werkgebied* gaat naar `?tab=begrippen&begrip=<id>`.
  - **deelvraag** (F3d) – een taak op één deelvraag (*Formuleer scherper*, *Splits*, en zoeken of dekking
    bij die deelvraag) levert `ref: {werkgebied_id, deelvraag_id}`. **`DeelvraagPaneel`** haalt
    `GET …/deelvragen/{id}` (ook een vervangen deelvraag) en toont de vraag met haar stand, de voorstellen
    van Lex die haar vervangen (`DeelvraagVoorstel` uit `Deelvragen.tsx`, met "Vervangt “…”"), de bronnen en
    begrippen, en `BronKandidaten deelvraagId` (alleen wat Lex bij haar vond, zonder zoekknop). Overnemen
    vervangt de oude (api): na herladen zegt het paneel "vervangen door …" en opent de opvolger in hetzelfde
    paneel (`onWissel`).
  - **werkgebied** (activiteit 1) – een werkgebied dat Lex met de analist samenstelde: ref
    `{werkgebied_id}`. De chip heet *Werkgebied · bekijken* en opent hetzelfde `WerkgebiedArtefactPaneel`
    met eigen inhoud (`WerkgebiedInhoud`: status en revisie, de **`WerkgebiedSamenvatting`** en *Open het
    werkgebied*) – los van het annotatiepaneel. De samenvatting staat ook bovenaan de werkgebiedpagina
    (één component, F3a): het dossier in de volgorde van `DOSSIER_VELDEN` – aanleiding, context, doel,
    analysevraag, praktijkvoorbeeld, afbakening, een leeg veld als "Nog geen …" –, de actieve deelvragen
    met hun stand (`useDeelvragenDekking`: `GET …/deelvragen/dekking` per revisie, faalt stil) en de
    bronnen met rol *analyseren*. Komt het binnen via `opgeslagen`, dan opent het
    paneel én gaat de werkplek verder in dat werkgebied (`onKiesWerkgebied`; het gesprek wordt eraan gekoppeld, de chatkop noemt het).
  - **regels** – gereserveerd voor de afleidingsregels: de kaart staat er, maar is geen knop.
  - **Het werkgebied hoort bij het gesprek** (spoor G1). Een geopend gesprek neemt zijn `werkgebied_id`
    mee (uit de lijst of, via `onGesprekGeladen`, uit het geladen gesprek); een nieuw gesprek krijgt het van
    `/workbench?werkgebied=<id>` (*Vraag Lex* op de werkgebiedpagina, de *+* bij een groep) en `maakGesprek`
    koppelt het bij de eerste beurt. Een expliciete keuze (verplaatsen, een werkgebied dat Lex net
    samenstelde – dat koppelt ook een bestaand gesprek) staat in `gekozenWg` en gaat voor. De URL volgt het
    werkgebied van het gesprek. **`ChatKop`** boven de chat noemt de titel (vanaf `lg`; daaronder staat die
    in de topbar), het werkgebied of *Los gesprek*, en het menu van het gesprek; hij vervangt de
    werkgebiedbalk met *Verlaten* (dat heet nu *Naar recente gesprekken* en koppelt echt los). Wat Lex met het werkgebied kan, staat sinds F3d als **suggesties boven het
    invoerveld** (`werkgebiedSuggesties`, zonder chip; ze wijken zodra je typt of er een onderwerp is).
    Elke beurt draagt dan `werkgebied_id`; een getypte vraag kiest graph-qa's supervisor de agent, een
    suggestie met actie doet dat zonder model. *Annoteer wat nog niet geannoteerd is* gaat zonder
    `bevestigd`: de bevestiging komt in het gesprek.
  - **Een context naast het gesprek** (spoor G4, `ContextPaneel`): wat geen artefact van een beurt is – een
    bepaling (`bron`), één JAS-element (`element`) of de bronnen van het werkgebied van het gesprek
    (`bibliotheek`). Zelfde schil (kolom vanaf 1280px, anders een sheet) en hoogstens één paneel: een
    artefact of annotatie sluit de context, een context sluit die (`ctx` in `WerkplekClient`, bijgesteld in de
    render). Ingangen: *Naast het gesprek* op de bronkaart van een citatie-chip (via `ContextPaneelContext`,
    alleen in de werkplek), *Bronnen* in de chatkop (`bronnenSignaal`) en een markering of elementrij in het
    paneel zelf (`onWissel`). Een bron krijgt het werkgebied van het gesprek mee. **Om te raadplegen, niet om
    in te werken**: geen beoordelingsknoppen; elk paneel – ook het artefact- en het annotatiepaneel – heeft
    bovenaan *Open volledige pagina* (`paginaVanContext`, `paginaVan`, `nodeLink`). Weg uit de werkplek is het
    paneel weg: het is lokale state. Browserregressie: `scripts/test-contextpaneel.mjs`.
  - `artefactVanBericht` maakt van een ouder bericht met alleen `annotatie_doel` een
    annotatie-artefact; `parseArtefact` is streng (onbekende soort of ref zonder verplichte sleutels:
    geen chip). Het `opgeslagen`-event draagt het artefact, `toonVastgelegdeBeurt` opent het.
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
    node-lagen,samenhang,graaf,knoop,capabilities,verklaringen}` (een allowlist op het eerste padsegment), met client-helpers in `lib/annotatieNode.ts`. De lagen zijn **gedeeld**,
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
ronde (`beurtSamenvatting` in `lib/waarom.ts`; de meting komt live uit `instellingen.meting` van het
`run`-event en na herladen uit `Bericht.dekking`, via `metingUitDekking` in `lib/agentEvents.ts`):
resultaat, bronnodes zonder zinsontleding en de totale duur. Het `annotatie`-item is een beurt van
Lex: naam, zijn **samenvatting** (`tekst`, hoogstens vier zinnen, door graph-qa uit de data opgebouwd
in `agent/nodes/annotatie_samenvatting.py` en als berichttekst bewaard), dan de chip. Het draagt ook
een `denk`-veld: de tijdlijn staat ingeklapt onderaan als *"Zo is dit tot stand gekomen"*, wordt met
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

### Het overzicht van een onderwerp

Op "welke artikelen gaan over X?" bouwt graph-qa een overzicht uit de graaf (`agent/overzicht.py`) en
schrijft Lex er alleen een korte duiding bij. Het overzicht komt als `overzicht`-event
(`parseOverzicht` in `lib/agentEvents.ts`, streng op bron-IRI's: één slechte rij en er is geen blok)
en reist mee in het bericht (`Bericht.overzicht`), ook als de werkplek het bericht zelf vastlegt.
**`OverzichtBlok`** toont het onder de samenvatting (die graph-qa uit dezelfde data schrijft, zonder
model): per regeling de delen met **al** hun bepalingen (`kop`/`naam` uit de data via `deelKop` en
`bepalingNaam` – nooit een bereik; de naam zoals de bron hem geeft, ook waar de Leidraad wisselt), wat het onderwerp verder noemt met zijn
plek in de opbouw (ingeklapt; open als de regeling geen deel heeft), de wettelijke definitie met haar
`vindplaats`, het redactionele trefwoord en waarop er gezocht is (`zoekverantwoording`). **Bij een
overzicht staat er geen bronnenlijst**: het blok linkt elke vindplaats. De kopieerknop neemt het
overzicht mee (`overzichtAlsMarkdown`). Met de graaf open zijn koppen en nummers aanwijsbaar in de
graaf (zie §*De samenhangsgraaf*). Rekenkern in `lib/overzicht.ts`.

### Citatie-chips onder en in het antwoord

Een vindplaats die Lex in gewone taal noemt ("artikel 9 lid 2", "art. 10a, derde lid") en die
**éénduidig** bij een bron van de beurt hoort, wordt een citatie-chip (`lib/citaties.ts`:
`vindVermeldingen` + `koppelBron`, via `bronDoel`). De rehype-plugin `markeerCitaties` wikkelt de
vermelding in een `cite` – de tekst zelf verandert niet, net als bij `markeerPassages`. Een klik
opent `CitatieChip` → een bronkaart via een portal (een `Popover` is een `div` en mag niet in een
alinea), met de wettekst (lui via `haalSamenhang`), een link naar wetten.overheid.nl en *Bekijk
in de graaf*. Geen chip bij twijfel: liever een vermelding zonder kaart dan een kaart bij de
verkeerde bepaling. Werkt ook na herladen, want alleen `tekst` en `bronnen` zijn nodig. De lijst
*Bronnen (n)* is **één bron per bepaling, gegroepeerd per regeling** (`normaliseerBronnen` in
`lib/bronnen.ts`): sleutel is de bronnode uit `vindplaatsVan` (`lib/samenhang.ts`, de spiegel van
`bronmodel.vindplaats`; `jci-vectoren.json` toetst beide), de kop is de `regeling` die graph-qa
meegeeft (anders het BWB-id), structuur staat vóór de artikelen en de link gaat bij voorkeur via de
jci. Oudere berichten, met dezelfde bepaling als graaf-IRI én jci, worden zo ook ontdubbeld. Geef
`Markdown` wél de ongenormaliseerde `bronnen`: `data-bron` van een citatie-chip is een index daarin.

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

### Een werkgebied samenstellen met vraagkaarten (activiteit 1)

"Kunnen we een werkgebied samenstellen?" of "ik wil een wetsanalyse uitvoeren" laat Lex één vraag per
kaartje stellen (graph-qa `agent/werkgebied_intake.py`), in de volgorde van de methode (F2): naam,
aanleiding, context, doel (startactiviteit a), analysevraag, praktijkvoorbeeld, deelvragen, wat valt
erbuiten, regeling(en), per deelvraag een kaartje met de bepalingen (F3f), en een samenvatting met
*Werkgebied aanmaken*. Het kaartje komt als
`vraagkaart`-event (`parseVraagkaart` in `lib/vraagkaart.ts`) en staat op het bewaarde bericht
(`Bericht.vraagkaart`). De vorm volgt hoe Claude een vraag stelt (F1):

- **De open vraag staat onderaan, op de plek van het invoerveld** (`VraagDock`, mobiel en desktop):
  ‹ n van N › (negen vaste stappen plus één per deelvraag; ‹ = `wijzig` naar het vorige kaartje (`vorige`):
  de vorige stap, of bij de bepalingen het vorige deel met `naar_deel`; › alleen als het kaartje al
  beantwoord was), ✕ klapt hem weg
  en geeft het invoerveld terug (UI-state, niets beantwoord). De hoogte volgt `visualViewport`, zodat de
  sheet boven het mobiele toetsenbord past.
- **Opties zijn regels met titel en omschrijving** (uit de graaf); een klik selecteert alleen, pas
  *Volgende* / *Verzend* (laatste vraag) / *Werkgebied aanmaken* stuurt in. "Typ je antwoord…" is de
  laatste regel: met tekst erin krijgt hij het vinkje en vervangt hij bij één keuze een gekozen optie.
  "Weet ik (nog) niet" sluit de andere keuzes uit. Knoppen zijn pillen (`Button pil`). Context en
  praktijkvoorbeeld krijgen een hoger veld (Shift+Enter voor een nieuwe regel).
- **De deelvragen** (`meer_tekst`): naast de voorstellen van Lex is elke eigen deelvraag een regel;
  Enter in een gevulde regel of *+ Nog een deelvraag* opent de volgende, Ctrl/⌘+Enter of *Volgende*
  stuurt in. Ze gaan als `teksten` mee (`antwoordActie`), lege regels niet. Na terugbladeren staat elke
  eigen deelvraag weer op een eigen regel (`beginstand`).
- **De bepalingen** (F3f): één kaartje per deelvraag (`Vraagkaart.deel: {index, totaal, deelvraag}`, de
  deelvraag staat onder de vraag), zonder deelvragen één over de analysevraag. Elke klik en het
  user-bericht (`intake_antwoord`, `antwoordOp`) dragen `deel`; een paar in de Vragen-kaart is er één per
  deel (`groepeerVragen` sleutelt op stap + deel – anders wist deelvraag 2 het antwoord op 1). *Verzend*
  staat op het laatste deel (`isLaatsteVraag`). Wat aan de afbakening raakt, staat onderaan met "valt
  mogelijk buiten de afbakening" en is nooit aangevinkt.
- **De samenvatting** toont het hele dossier: aanleiding, context, doel, analysevraag,
  praktijkvoorbeeld, de deelvragen, afbakening en bronnen (met hun deelvragen).
- **In de thread één Vragen-kaart per reeks** (`groepeerVragen`, `VragenKaart`): per vraag de vraag
  (grijs) en je antwoord, "Vraag" bij één en "Vragen" bij meer, daaronder "● Een vraag stellen ›" (opent
  de dock weer) of "Nadenken…" terwijl Lex de volgende voorbereidt. De antwoordbubbels en de zinnen van
  Lex per stap renderen niet; een getypte tussenvraag breekt de reeks. Opnieuw beantwoorden na ‹
  vervangt het paar en wat erna kwam.
- **Een klik is een gewone beurt met `intake_actie`**; het user-bericht draagt **`intake_antwoord`**
  (`parseAntwoordOp`), zodat de kaart na herladen hetzelfde is. De volgorde is van graph-qa.
- `ThreadRij` vergelijkt `vragen` op inhoud in zijn `memo` (`zelfdeRij`): de groepering is elke render
  vers.
- **Aanvullen** (`Vraagkaart.modus: "aanvullen"`): dezelfde dock op een bestaand werkgebied, voor de velden
  van het dossier. ‹ n van N › telt over de gevraagde stappen, een gevuld veld staat vooringevuld in het
  tekstveld (`beginstand`), *Verzend* op de laatste gevraagde stap (`isLaatsteVraag`). De samenvatting toont
  per veld toen → nu (`Samenvatting.wijzigingen`, "(leeg)" bij een leeg veld) en de knop heet *Opslaan*
  (`actie: "opslaan"`, ook op `intake_antwoord`); zonder wijziging is er geen knop. *Stop met aanvullen*.
  ‹ stuurt de vorige stap van het samenstellen; graph-qa kiest de gevraagde stap. Na het opslaan komt het
  werkgebiedartefact binnen via `opgeslagen` en laadt het paneel opnieuw (`wgLading` in de `key`), ook als
  het al op dat werkgebied openstond.
- Browserregressie: `scripts/test-werkgebied-intake.mjs` en `scripts/test-dossier-aanvullen.mjs`.

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
`NodeAnnotatiePaneel`, `reeksNavigatie` in `lib/reeks.ts`): "2 van 3" en ‹ › naar het
buurlid. Bewust niet het hele artikel in één paneel: *Afronden* en *Verwijderen* werken op álle lagen
in beeld, ook op leden die niet gekozen waren. Alleen leden met een vastgelegde annotatie tellen mee
in het bladeren.

### Eén gesprek: Vraag Lex gaat via het centrale venster

*Vraag Lex* zet een vraag klaar in het chatveld; er is geen aparte mini-chat bij het object. Sinds F3b is
dat één mechanisme voor elk object (`lib/vraagLex.ts`): `Onderwerp` is een markering (`{element, view}`)
of een object uit een werkgebied (`{soort, werkgebied_id, id, label}` – deelvraag, bron, kandidaat,
begrip, werkgebied), met per soort een module in `MODULES` (`chip`, `suggesties`, `verzoek`, `over`).

- **Markering** blijft de adviesvraag, byte-gelijk (`vraagLex.test.ts` bevat de oude constructie). De
  rest gaat als `onderwerp` (alleen soort en id's; graph-qa haalt het object bij de api,
  `agent/onderwerp.py`). Een suggestie met een **`actie`** (`ACTIES`, gelijk aan graph-qa `ACTIE_TAAK`;
  de test leest die bron) stuurt `actie` + `onderwerp` + het `werkgebied_id` van het onderwerp, zonder
  modus, context of doel – graph-qa kiest er zonder model een agent en taak bij (F3c, ADR-005).
- **Suggesties per soort** (`SUGGESTIES`, F3d): werkgebied (het dossier aanvullen, deelvragen voorstellen, bepalingen zoeken,
  dekking, annoteren, de bepalingen van de deelvragen annoteren, begrippen voorstellen, meedenken), deelvraag
  (zoeken, de bepalingen hierbij annoteren, gedekt?, scherper, splitsen),
  begrip (uitwerken, brondefinitie, voorbeelden, relaties, en *Wat is het betekenisverschil met …* met
  `invullen`: in het veld, de analist noemt het andere begrip). Bron en kandidaat hebben alleen vragen
  zonder actie (waarom deze bepaling, verwijzingen, bij welke deelvraag): die gaan met het object langs de
  supervisor naar de antwoord-worker.
- **Het dossier aanvullen** (`dossier_aanvullen`) is in `ACTIES` maar geen taak van een agent: graph-qa
  routeert het naar de vraagkaarten (`INTAKE_ACTIES`; de test leest `Actie` en `ACTIE_TAAK`). Bij een leeg
  veld in de `WerkgebiedSamenvatting` staat *Vraag Lex* met het werkgebied als onderwerp en `veld`; de eerste
  suggestie is dan *Vul het … aan* (`VELD_ZIN`), en graph-qa leest het veld uit die tekst. `veld` reist via
  `vraag_veld` in de URL, maar niet als onderwerp naar graph-qa.
- **`VraagLexKnop`** (`components/werkplek/VraagLexKnop.tsx`): binnen de werkplek zet hij het onderwerp
  via `VraagLexContext` (`kiesOnderwerp` in `WerkplekClient`: chip, leeg veld, focus, op een smal scherm
  het paneel dicht); daarbuiten is hij een **link** naar `vraagUrl` (`/workbench?werkgebied=…&vraag=<soort>:<id>&vraag_label=…`),
  zodat de bewaker van niet-bewaarde wijzigingen hem ziet. `WorkbenchShell` leest `vraag` één keer
  (`onderwerpUitUrl`, streng op soort en id's), haalt de parameters uit de URL en geeft
  `beginOnderwerp` alleen aan het venster waarmee de pagina opende. In de kop van de werkgebiedpagina en
  van elk werkgebiedpaneel (werkgebied, deelvraag, begrip), bij elke deelvraag in de
  `WerkgebiedSamenvatting` (`vraagLex`), en op de werkgebiedpagina bij elke rij (F3e): deelvraag,
  bronselectie, open kandidaat en begrip. Een element op de tab Elementen heeft er geen: een markering
  heeft geen URL-weg, en *Vraag Lex* staat al op de markering in de annotatie. `annoteer=`/`meedenk=`
  bestaan niet meer (F3e): de bevestiging komt in het gesprek; `app/geenRunRoutes.test.ts` bewaakt dat.
- Browserregressie: `scripts/test-vraaglex.mjs`.

**De markering in het bijzonder:**

- `WerkplekClient` houdt `onderwerp`. Zolang dat een markering is, toont een **chip** boven het
  invoerveld waar de vraag over gaat en gaat de beurt met `modus: "advies"` + de context.
  De chip verdwijnt na het versturen – anders wordt je volgende vraag ongemerkt ook een adviesvraag.
  Lex vergeet het element daarmee niet: graph-qa houdt het aangewezen element vast in zijn focus
  (`agent/focus.py`), zodat een vervolgvraag zonder chip nog weet over welke markering het ging.
- **Drie vragen staan klaar** (`vraagSuggesties` in `lib/annotatie.ts`, via de markeringmodule): waarom deze klasse, klopt de
  afbakening, en – als de agent een alternatief voorstelde – waarom die andere klasse dan niet. Eén
  klik verstuurt; ze verdwijnen zolang er een beurt loopt, want een tweede vraag zou worden
  afgewezen.
- Het antwoord is een gewone beurt, dus met bronnen, grounding en kopieerknop.
- De chip is UI-state; het bewaarde bericht krijgt een contextregel (`Bij <dit>: <vraag>`, met `overVan`:
  bij een markering `<bepaling>: <fragment>`).
- **De context is één bronnode.** `MODULES.markering.verzoek` (`lib/vraagLex.ts`) stuurt het element, de
  bronnode en als `corpus` de segmenten van de weergave die openstaat – niet alles wat in het gesprek
  geopend is, anders legt Lex een fragment uit artikel 36 naast de tekst van artikel 8. De buren leest
  graph-qa zelf (`context.bestaande_elementen`) en handhaaft die grens nog eens.
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
  (`verwijderd: {op}`). De kaart benoemt zichzelf via **`artefact.titel`** in het berichtcontract
  (bij oude berichten `annotatie_titel`; zonder beide: "Annotatie"). Bewust geen cascade server-side: het gesprek is een verslag van
  wat er gebeurde.
- **Het laatste artefact blijft bereikbaar** via een balk boven de chat (titel · *Openen*) zodra het
  paneel dicht is, over de soorten heen (stelde Lex na een annotatie begrippen voor, dan zijn dát het
  laatste werk); verwijderde annotaties en afleidingsregels slaat die balk over.
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
- **De drie overzichten – Annotaties, Werkgebieden, Begrippen – zien er hetzelfde uit** (besluit
  gebruiker 21 okt 2026): onder de kop één balk, `components/ui/OverzichtBalk` (links filterknoppen met
  tellers, dan *Door mij bewerkt*, eventueel iets extra's, rechts het zoekveld; slaat om als het niet
  past), en daaronder kaarten in twee kolommen (`AnnotatieKaart`, `WerkgebiedKaart`,
  `BegripOverzichtKaart`) met de naam als link en onderaan *Openen* en *Verwijderen*. *Door mij bewerkt*
  komt overal uit de audit (de api, `mijn`).
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
- **Verwijderen werkt voor annotatie, werkgebied en begrip gelijk** (besluit gebruiker 21 okt 2026,
  `lib/verwijderen.ts`): echt wissen (api), één knop `components/ui/VerwijderKnop` (*Verwijderen*, tweede
  klik *Verwijderen?*, `aria-label` "<Soort> verwijderen", de tooltip zegt wat weggaat en wat blijft) op
  dezelfde plekken, en daarna een toestand in plaats van een fout:

  | | paneel naast het gesprek | pagina | lijst |
  |---|---|---|---|
  | annotatie | `ArtefactInhoud` | nodepagina (dezelfde inhoud) | `AnnotatieKaart` in `/annotaties` (`verwijderAnnotatie`: eerst de weergave) |
  | werkgebied | `WerkgebiedInhoud` in `WerkgebiedArtefactPaneel` | kop van `WerkgebiedClient` | kaart in `WerkgebiedenClient` |
  | begrip | kop van `BegripPaneel` | `BegripPaneel` in de Begrippen-tab, en onderaan `BegripKaart` | rij in `BegrippenOverzichtClient` |

  Een verwijderd werkgebied of begrip geeft een 404 met `{fout: "verwijderd", op, door}`; `verwijderdUit`
  leest die en het paneel of de pagina zegt "Dit werkgebied is verwijderd op … door …" (`data-verwijderd`).
  Een lijst haalt de rij meteen weg en zet hem bij een fout terug; een 412 laadt opnieuw. Verwijder je het
  werkgebied waarin de werkplek staat vanuit het paneel, dan verlaat de werkplek het (`onVerwijderd`).
  Een vervangen begrip heeft geen knop (verwijder de opvolger). `metSpoor` met `annotatie_verwijderen`,
  `werkgebied_verwijderen` en `begrip_verwijderen`. Archiveren bestaat niet meer.
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
reviewlijst en alle handlers; `NodeAnnotatiePaneel` zet hem in de `Dialog`-schil en de annotatiepagina
is de tweede schil (hetzelfde patroon als `DisclaimerClient` en `InstellingenInhoud`). Een
**bronnode-annotatie** gebruikt dezelfde inhoud: `NodeAnnotatiePaneel` haalt de v2-weergave op en
vertaalt die via `lib/annotatieNodeAdapter.ts` (codepoints per bronnode ⇄ UTF-16 in de samengestelde
bron). **Bouw geen tweede weergave, breid de adapter uit** – een eigen paneel verliest alle opmaak en
bediening. `ArtefactInhoud` heeft daarvoor twee optionele haken: `onExport` (een eigen exportroute) en
`extra` (blokken onder de reviewlijst, zoals "overspant meerdere bepalingen" en de voortgang per
bepaling). De paginaschil (sidebar, mobiele topbar, terug naar het overzicht) is gedeeld in
`components/annotaties/AnnotatiePaginaSchil.tsx`.

**Escape handelt de inhoud zelf af** (selectie → bedieningsrij → gekozen element → `onSluiten`),
want de `Dialog`-schil is er niet altijd. `NodeAnnotatiePaneel` geeft `Dialog` daarom (op de Tekst-tab) een **no-op**
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

## Werkgebieden (`/werkgebieden`)

Spoor D, levering 1 (zie `docs/PLAN.md` en `../api/CLAUDE.md` §*Werkgebieden*). Een werkgebied brengt
bepalingen samen rond één analysevraag; het is, net als een annotatie, een ingang in de sidebar en
bestaat los van de gesprekken.

- **BFF**: `app/api/werkgebieden/route.ts` (lijst, aanmaken) en `…/[...pad]/route.ts`. Die laatste
  laat alleen de vormen uit `isWerkgebiedRoute` (`lib/werkgebied.ts`, getest) door – geen generieke
  proxy; een nieuwe api-route vraagt daar een regel. De query gaat ongewijzigd mee
  (`verwachte_revisie` bij DELETE). De inventaris en elke POST onder `begrippen` (koppelen toetst
  tegen de inventaris) krijgen 90 s, want de api haalt per regeling de bronboom uit de graaf.
- **Een werkgebied is een project** (spoor G2, naar de mock-up v4). `app/werkgebieden/[id]/layout.tsx`
  zet `WerkgebiedProject` om alle pagina's eronder: die laadt het werkgebied één keer, draagt `muteer`,
  verwijderen, de meldingen en de bewaker van niet-bewaarde wijzigingen, en laadt de stand voor tellers en
  kaarten (`useWerkgebiedStand`: eigen gesprekken, begrippen, kandidaten, annotatie-werkvoorraad – elk faalt
  stil, dan geen getal). Pagina's lezen het met `useWerkgebied()`. Een tabwissel is een navigatie (eigen URL,
  Terug werkt) maar laadt niets opnieuw: de layout blijft staan.
  - **Vier tabs als paden** (`PROJECT_TABS`, `projectPad` in `lib/werkgebiedPaden.ts`): Overzicht
    (`OverzichtTab`: tellers, de analyseopdracht met de analysevraag centraal, deelvragen als rijen naar hun
    pagina, de laatste gesprekken, de artefacten), Gesprekken (`GesprekkenTab`: de eigen gesprekken, een klik
    opent de werkplek), Bronnen (`BronnenRegister`: zoeken, rolfilter, per bron de stand uit de werkvoorraad
    – `selectieStand` –, rol en weghalen achter ⋯, opnemen in een venster `BronOpnemen`, de voorstellen van
    Lex in één regel naar `bronnen/voorstellen`) en Artefacten (`ArtefactenTab`: vier kaarten,
    `artefactKaarten`).
  - **Detailpagina's** (`DetailPaginas.tsx`): `artefacten/[soort]` – `dossier` (de velden, *Bewerken* in
    een venster `GegevensDialoog`, het beheer van de deelvragen), `bronselectie`, `annotaties` (de
    inventaris, `ElementenTab`) en `begrippen` (`BegrippenTab` en, met `?deel=samenhang`, `SamenhangTab`;
    `?begrip=` en `&weergave=kaart` in de URL) –, `deelvragen/[did]` (`DeelvraagPaneel` op een pagina),
    `historie` en `bronnen/voorstellen` (`BronKandidaten`).
  - **Een artefact is een bestaand object** (besluit 26 okt 2026): geen eigen opslag, de kaart leest wat
    er ligt. *Specificaties* blijft gereserveerd.
  - **Het idioom staat in `components/ui/Pagina.tsx`**: `PaginaKop` (kruimelpad, titel, één zin, meta,
    hoogstens twee knoppen), `TabLinks` (links met `aria-current`; een teller hoort in de naam, "Bronnen
    (4)"), `Kaart`, `SplitDetail`, `ObjectRij` (titel, subregel, status, chevron – geen knoppen en geen
    IRI's in een rij) en `Teller`.
  - **Een oude link met `?tab=`** gaat server-side naar zijn nieuwe plek (`oudeTabNaar`): bladwijzers en
    berichten van vóór G2 blijven werken. Bouw zelf geen `?tab=` meer; gebruik de padhelpers.
  - **De kop** (`ProjectKop`) draagt *Gegevens bewerken* en *Nieuw gesprek* (een gesprek dat bij het
    werkgebied hoort); historie en verwijderen staan in het menu ⋯.
- **Elk juridisch object heeft een eigen pagina** (spoor G3; paden in `lib/werkgebiedPaden.ts`):
  - **Bepaling** `/bronnen?bron_iri=…[&werkgebied=]` (`components/bronnen/BronPagina`): de letterlijke
    wettekst met álle markeringen in hun JAS-kleur (`KnoopTekst groot`; een klik opent het element), de
    elementen als rijen, wat de kennisgraaf weet (`KnoopFeiten`), de werkgebieden met deze bepaling
    (`lijstWerkgebieden({bronIri})`) en *Opnemen in werkgebied*. Met `werkgebied` gaat het kruimelpad via
    dat werkgebied en staat *Bespreek met Lex* over de bronselectie in de kop. Het bronregister linkt hierheen.
  - **JAS-element** `/annotaties/element/[id]` (`components/annotaties/ElementPagina`, `haalElementDetail`):
    het bronvoorkomen, de classificatie met *Waarom?*, en accorderen, afwijzen met een reden of heropenen
    (`beslisElement`, tegen de laagrevisie en bronstand van het element). Klasse en grens aanpassen blijft in
    de annotatie van de bepaling, waar de buren ernaast staan. De reviewkaart (*Open als pagina*) en de
    passages van een begrip (*Element*) linken hierheen.
  - **Begrip** `/begrippen/[wg]/[id]` (`BegripPagina` → `BegripWerk`): de volledige kaart, zonder lijst.
    *Begripskaart* in het begrippenkader, het begrippenoverzicht (`kaartUrl`), de samenhangsgraaf en het
    paneel naast het gesprek openen hem; lezen naast de lijst blijft in het begrippenkader. Een oude link met
    `&weergave=kaart` gaat hierheen.
- **Het overzicht** (`WerkgebiedenClient`): statusfilter met tellers (`lib/werkgebiedOverzicht.ts`; de
  status in de URL, `?status=`), *Door mij bewerkt* (`lijstWerkgebieden({mijn})`) en zoeken op naam,
  analysevraag, afbakening en context, client-side. **Aanmaken gaat via Lex**: er is geen formulier
  meer, wel *Samenstellen met Lex* (`WERKGEBIED_START_URL`, `/workbench?start=werkgebied`): de werkplek
  zet "Kunnen we een werkgebied samenstellen?" klaar in het invoerveld met de focus erin
  (`startVraagUitUrl`, één keer gelezen en uit de URL gehaald) en verstuurt niets zelf.
- **Verwijderen** (in het menu ⋯ van de kop, en per kaart in de lijst) wist het werkgebied echt; zie
  §*Annotaties buiten het gesprek* voor hoe verwijderen overal gelijk werkt.
- **Gedeeld, dus elke mutatie draagt de revisie in beeld.** Alle mutaties lopen via één `muteer` in
  `WerkgebiedProject`. Een 412 (`revisie_conflict`) laadt de nieuwste stand en zegt dat iemand anders
  het werkgebied wijzigde; de handeling wordt **niet** stil opnieuw uitgevoerd, want op de nieuwe stand
  kan ze iets anders betekenen. Een fout die over de invoer gaat (409 `al_opgenomen`, 422 van de
  graaf) vangt het formulier zelf af via `opFout`.
- **Bronnen**: opnemen met regeling (BWB-id) + artikel (+ lid) of een graaf-IRI (`bronInvoer` in
  `lib/werkgebied.ts` leest "artikel 9" als "9"; de api verifieert tegen de graaf). Dezelfde bron met
  dezelfde rol nog eens is idempotent en wordt zo gemeld. Weghalen is een `BevestigKnop` en laat de
  bepaling en haar annotaties staan.
- **Elementen** toont wat de api meldt in plaats van het weg te poetsen: `volledig: false` en
  `onbereikbaar` als open punt, `bron_gewijzigd` als signaal, `deels_buiten` bij het element, en een
  onbeoordeeld element (voorstel van Lex, hergebruik) met zichtbaar voorbehoud (`isBeoordeeld`). Elk
  element staat één keer, onder de eerste selectie die het dekt (`groepeerPerSelectie`). De voortgang
  telt alleen de werkvoorraad en zegt niets over juridische dekking.
- **De inventaris laadt pas op zijn pagina** (het artefact Annotaties), en opnieuw bij elke nieuwe
  revisie (`key`).
- **Samenhang** is de samenhangsgraaf met de bronselecties als doelen en focus (`useGraafStand` met
  stabiele doelen – een nieuw doel-object per render laadt eindeloos opnieuw) en `benaming` op het
  werkgebied in plaats van het antwoord. Opnemen kan in de inspector (`bijKnoop`), altijd met een rol.
  De suggestielijst die hier stond, is vervangen door de kandidaten van Lex op de tab Bronnen.
- **De pagina is raadplegen** (F3e). Wat Lex met een werkgebied doet – deelvragen voorstellen of
  verbeteren, bepalingen zoeken, de dekking, annoteren, begrippen voorstellen, meedenken, een begrip
  uitwerken – vraag je in het gesprek: met **één *Bespreek met Lex* in de kop van een detailpagina**
  (`VraagLexKnop primair`; spoor G2 verving *Vraag Lex* per rij, besluit 26 okt 2026), of *Nieuw gesprek* in
  de kop van het project, en dan een suggestie of een eigen vraag (§*Eén gesprek*). Een knop in een rij
  (`alleenInGesprek`) verschijnt alleen in de panelen naast het gesprek, waar hij het object klaarzet in
  hetzelfde gesprek. Op de
  pagina staan geen knoppen die Lex starten, en de werkplek start niets vanuit de URL. De pagina toont
  wat Lex opleverde en draagt de handmatige besluiten erover. Er is daardoor geen BFF-route meer die een
  run start: de vier statische routes (`deelvragen-run`, `kaart-run`, `bronnen-run`, `begrippen-run`)
  en `annoteer=`/`meedenk=` zijn weg, en `app/geenRunRoutes.test.ts` bewaakt dat ze niet terugkomen.
- **Bronnen vinden met Lex** (fase A; api §*Bronnen vinden met Lex*, graph-qa §*Bronnen vinden met
  Lex*): `BronKandidaten` bovenaan de tab Bronnen én als artefact naast het gesprek – één inhoud, twee
  schillen, allebei zonder zoekknop. Zoeken is de taak `bronnen_zoeken` van de deelvragen-agent; de
  strook toont de laatste ronde (`bronnen-runs/laatste`) en de kandidaten.
  - **Per kandidaat** de rol als badge (kern / afhankelijkheid / aanverwant, met uitleg) en het bewijs
    per methode in gewone woorden (`bewijsZin` in `lib/bronKandidaten.ts`: "verwezen vanuit Artikel 9,
    lid 1 (“artikel 8”) – uitzondering"). Per methode de telling en "onvolledig" als ze haar plafond
    raakte. Filters open / later / uitgesloten / opgenomen (`filterVan`: met de hand opgenomen telt als
    opgenomen).
  - **Een boom met een actiebalk** (spoor H2): de kandidaten in `BronBoom` per regeling › hoofdstuk ›
    artikel › lid (de plek uit `usePlaatsen`), per regel een vinkje, de rol en één zin bewijs
    (`bewijsSamenvatting`); *Bewijs* klapt het hele bewijs uit. Geen knoppen per regel.
  - **Besluiten** in de actiebalk, voor alles wat aangevinkt is (ook een heel artikel of hoofdstuk via
    het vinkje van de kop): *Opnemen om te analyseren* / *als context* – `neemKandidaatOp` haalt de revisie
    zelf op en probeert bij een 412 één keer opnieuw –, *Later*, *Uitsluiten…* (één verplichte reden,
    krijgt de focus) en *Heropenen*. Elk besluit is een eigen verzoek, in de volgorde van de boom; bij een
    fout stopt het en zegt het hoe ver.
  - De allowlist (`isWerkgebiedRoute`) laat `kandidaten/*` en `bronnen-runs/laatste|{run}` door, nooit
    een kale POST op `bronnen-runs` of `…/uitkomst|loopt|mislukt` (dat is van graph-qa).
  - **Werkgebied vanuit een overzicht**: onder `OverzichtBlok` de knop *Maak hier een werkgebied van*
    (`WerkgebiedUitOverzicht`): naam en analysevraag vooringevuld, de bepalingen uit het overzicht
    (`bepalingenVanOverzicht`) voorgeselecteerd. Daarna staat de werkplek in dat werkgebied; wat niet
    kon worden opgenomen staat in een zichtbare melding onder de balk.
  - Browserregressie: `scripts/test-bronkandidaten.mjs`.
- **Deelvragen** (optioneel, open keuze 4; api §*Deelvragen*, graph-qa §*Lex stelt deelvragen voor*):
  `Deelvragen` bovenaan de tab Bronnen. Zonder deelvragen verandert er niets.
  - Een deelvraag hoort bij de scope: toevoegen, bewerken, weghalen (`BevestigKnop`) en *Bronnen en
    begrippen* (vinkjes, één keer opslaan, de hele set) lopen via `muteer` met de revisie in beeld.
  - Voorstellen en verbeteren doet de deelvragen-agent in het gesprek (*Stel deelvragen voor*, of
    *Formuleer scherper* / *Splits* via *Vraag Lex* bij de deelvraag). Een voorstel staat hier geel met
    *Overnemen* of *Afwijzen…* (reden verplicht; Lex stelt het niet opnieuw voor).
  - De stand per deelvraag komt uit `GET …/deelvragen/dekking` (per revisie, faalt stil,
    `isDeelvragenDekking`, via `useDeelvragenDekking`): *Gedekt* (groen), *Nog geen geaccordeerd
    begrip* (geel), *Nog geen bron* – een `StatusLabel` met `STAND_TOON`.
    Rekenkern in `lib/deelvragen.ts`.
  - Een kandidaat die Lex bij een deelvraag vond, zegt dat (`bewijsZin`: "gevonden bij de deelvraag …");
    opnemen koppelt hem aan die deelvraag (api).
  - De allowlist laat `deelvragen`, `deelvragen/{id}`, `deelvragen/dekking` en `deelvragen/{id}/koppelingen`
    door, nooit `deelvragen/voorstellen` (van graph-qa).
  - Browserregressie: `scripts/test-deelvragen.mjs`.
- **Deelvragen met structuur** (spoor H3): in het dossier is een deelvraag een rij – de vraag als link naar
  haar pagina, herkomst en omvang ("7 bronnen in 3 regelingen · 0 begrippen"), de stand – met *Bronnen en
  begrippen koppelen*, *Bewerken* en **Verwijderen** achter ⋯. Koppelen gaat in een venster
  (`KoppelDialoog`): de bronnen als `BronBoom` met vinkjes (een heel artikel, hoofdstuk of regeling in één
  klik) en de begrippen. Op de deelvraagpagina staan haar bronnen als boom, met *Koppelen*. Een bronselectie
  heet *Verwijderen uit werkgebied*. Ruwe IRI's in oudere dossiertekst toont de werkplek als hun plek
  (`metLeesbareBronnen`).
- **Opnemen vanuit een annotatie**: *Opnemen in werkgebied* in de kop van `/annotaties/node`
  (`OpnemenInWerkgebied`). Daar is geen revisie in beeld; `neemOpInWerkgebied` haalt hem op en
  probeert bij een 412 één keer opnieuw – de bedoeling hangt niet af van de rest van het werkgebied,
  en opnemen is idempotent.
- **Begrippen** (levering 2; api in `../api/CLAUDE.md` §*Begrippen*). De tab staat tussen Elementen en
  Samenhang; het gekozen begrip staat in de URL (`?tab=begrippen&begrip=<id>`, via `kiesBegrip` in
  `WerkgebiedClient`, ook vanuit de tab Elementen). `BegrippenTab` is de lijst (`Lijst`/`LijstRij`, met
  *Vraag Lex* per begrip, export en *Nieuw begrip*). Het gekozen begrip opent om te **lezen**
  (`BegripPaneel`, hetzelfde paneel als naast het gesprek: de leesweergave, de open voorstellen van Lex per
  veld, een kleine bewerking); *Begripskaart* wisselt naar de **kaart** (`BegripWerk`). Er staat er steeds
  één. De weergave staat in de URL (`&weergave=kaart`, `weergaveUitParam` in `lib/begrippen.ts`) en blijft
  staan bij een wissel van begrip; een klik in de strook *Herbeoordelen* en *Open de begripskaart* in de
  samenhangsgraaf openen de kaart. Een wissel met onbewaarde wijzigingen vraagt eerst bevestiging, net als
  een wissel van begrip. `BegripWerk` laadt één begrip en draagt `muteer` – dezelfde vorm als bij het werkgebied:
  revisie in beeld, 412 laadt opnieuw en zegt het, een fout met een `melding` van de api (`al_primair`,
  `poort`, `element_buiten_werkgebied`) verschijnt zoals de api hem formuleert. Kaart en passages staan
  vanaf `xl` naast elkaar, daaronder wissel je; de schil is op deze tab breed (`max-w-7xl`).
  - **De kaart staat in de volgorde van NL-SBB** (spoor G5, ADR-003): groepen *Term* (voorkeursterm,
    alternatieve termen), *Betekenis* (definitie met herkomst, uitleg = toelichting, context = toepassings-
    gebied), *Voorbeelden*, dan wat eigen is aan de analyse (*Indeling*: JAS-duiding, begripstype,
    geldigheid, eigenschappen; *Onderbouwing en open vragen*). Bij elke kop staat klein de NL-SBB-eigenschap
    waarop de export landt. Een groep draagt geen label (`data-kaart-groep`): een label "Onderbouwing en …"
    zou het veld *Onderbouwing* overstemmen. **Brondefinitie of analysebegrip** staat bij de definitie
    (`DefinitieAard`, `definitieAard` in `lib/begrippen.ts`): alleen een letterlijk overgenomen definitie is
    een brondefinitie; samengesteld of geformuleerd is "een analyse-uitkomst, geen wettelijke definitie". Het
    volgt de gekozen herkomst meteen, ook vóór het opslaan; de kop van de begripspagina en `BegripPaneel`
    tonen hetzelfde.
  - **`BegripKaart` is één formulier met *Opslaan*, geen autosave**: elke bewaring is een revisie. De
    kaart werkt op een concept naast de serverstand (`basis`). Verandert de inhoud op de server terwijl
    er niets onbewaard is, dan neemt hij die over; mét onbewaarde wijzigingen zegt hij dat en blijft
    jouw tekst staan (*Nieuwe versie overnemen* of opslaan). Of er iets onbewaard is, bepaalt
    `inhoudGewijzigd` (`lib/begrippen.ts`: genormaliseerd, sleutelvolgorde telt niet). Met onbewaarde
    wijzigingen vraagt een wissel van begrip **én van tab** eerst bevestiging (`OnbewaardMelding`, geen
    systeemvenster): de tabs renderen lazy, dus een tabwissel gooide het concept anders stil weg. Het
    signaal staat daarom in `WerkgebiedClient`. Herladen of sluiten vangt `beforeunload`; een link
    elders (sidebar, *Alle werkgebieden*) en een knop die zelf navigeert (een gesprek openen) vangt
    `useOnbewaardBewaker` (`lib/useOnbewaardBewaker.ts`: links in de capture-fase op `document`, knoppen
    via `bewaak`; `/instellingen/*` opent over de pagina en telt niet). Het artefactpaneel van één begrip
    in de werkplek gebruikt dezelfde bewaker, ook voor sluiten.
  - **De poort rekent de server.** *Accorderen* staat uit zolang `accorderen.mag` onwaar is, met de
    redenen letterlijk eronder; met onbewaarde wijzigingen ook (de poort kijkt naar wat bewaard is).
  - **Elke knop per passage noemt zijn passage** (`aria-label`, "Akkoord met “…”"): dezelfde knoppen
    staan bij elke passage, en een schermlezer moet horen bij welke.
  - **`BegripPassages` toont elke passage apart**, met de bewaarde bewijstekst, vindplaats, rol,
    beoordeling en wat er nu mee is (`ACTUALITEIT_LABEL`, *annotatie nog niet door een jurist
    beoordeeld*). *Bekijk in de annotatie* gaat naar `/annotaties/node?bron_iri=…&element=<id>`; de
    pagina geeft `element` als `beginElement` aan `NodeAnnotatiePaneel`, dat die markering kiest.
  - **Elementselectie** in `ElementenTab`: selectievakjes en een balk met *Nieuw begrip uit selectie*
    en *Koppelen*; een element dat al een begrip aanduidt, noemt dat begrip (`primair` uit de lijst).
- **Voorstellen van Lex** (levering 3a; api §*Voorstellen van Lex*, graph-qa §*De begrippenrun*):
  de strook `BegripVoorstellen` bovenaan de tab Begrippen (en als artefact naast het gesprek), naast zelf
  een begrip maken. Voorstellen vraag je Lex in het gesprek (*Stel begrippen voor*, de begrippen-agent);
  de strook toont de laatste ronde (`begrippen-runs/laatste`): wanneer, hoeveel passages en groepen, wat
  niet meeging, of ze verouderd of mislukt is – en de reviewlijst. Geen knoppen die Lex starten.
  - **De allowlist** (`isWerkgebiedRoute`) laat `groepen/*`, `begrippen-runs/laatste|{run}` en
    `…/vragen/{kid}` door, maar nooit `…/uitkomst`, `…/loopt`, `…/mislukt` of een kale POST op
    `begrippen-runs`: een run maakt graph-qa.
  - **De review** (`BegripReview`, fase D; api §*Voorstellen van Lex* – akkoord) is de vorm van de
    annotatiereview: groepen én open twijfelvragen in één lijst (`reviewItems` in
    `lib/begripVoorstellen.ts`: geel, de vragen, groen; besluiten alleen bij *Alles*), voortgang
    (`reviewVoortgang`, parkeren telt als besluit), filters, en alleen het actieve item uitgeklapt.
    - **Akkoord** (`a`) gaat via `POST …/groepen/akkoord`: begrip, beoordeelde koppelingen en accorderen in
      één handeling. De knop zegt vooraf of het een concept blijft (`akkoordLabel` uit `poort_vooraf`).
      Blijft het een concept, dan staat het bovenaan met de redenen en de oplossing ter plekke:
      *Annotatie akkoord* per onbeoordeelde passage (`keurElementGoed` in `lib/annotatieNode.ts` – een
      aparte beslissing op de annotatie, met haar laagrevisie) en *Definitie toevoegen*; daarna probeert de
      review opnieuw te accorderen.
    - **Aanpassen** (`e`): naam, definitie met herkomst, context, begripstype; alleen wat veranderde gaat
      mee (`aanpassingUit`), en de werkplek toont welke herkomst het wordt (`herkomstNaAanpassing`, zoals
      de api). Enter in een veld of Ctrl+Enter in een tekstvak = akkoord.
    - **Splitsen** met de vinkjes; de rest van de groep blijft staan ("n al een begrip"). Na elk besluit
      vervalt de vinkjeskeuze. **Combineren**: `m` markeert, vanaf twee groepen staat de vergelijking
      bovenaan (`vergelijk`: definities naast elkaar, kies er één of geen, signalen ertegen).
      **Afwijzen** (`x`) en **parkeren** (`p`) vragen een reden; *Koppelen aan …* (bij *lijkt op*) koppelt
      met `akkoord: true`. Een vraag: `s` samen (één begrip, de vraag gaat met het akkoord mee) of `n` apart.
    - **Toetsen** alleen met de focus in de strook, in het artefactpaneel of nergens; nooit vanuit de chat
      of een tekstveld (een vinkje of keuzerondje telt niet als tekstveld). Na een besluit springt de
      selectie naar het volgende open item (`naBesluit`). Een 409 `al_besloten` opent het bestaande begrip.
  - Browserregressie: `scripts/test-begripvoorstellen.mjs` (de volledige review met alleen het toetsenbord)
    en de toetsen in het paneel in `test-artefacten.mjs`. Let op: een label om een tekstveld neemt de
    **inhoud** van het veld op in de toegankelijke naam – zoek een gevuld veld op een prefix.
- **Lex annoteert het werkgebied** (fase B; api §*Werkgebieden* – de annotatie-werkvoorraad, graph-qa
  §*Lex annoteert het werkgebied*). Lex begint nooit zonder akkoord.
  - **In de werkplek** (F3d): de suggestie *Annoteer wat nog niet geannoteerd is* vraagt Lex om het voorstel
    (aantal, schatting, budget, wat niet meegaat – graph-qa leest de werkvoorraad zelf); de bevestiging komt
    als bericht in het gesprek. Op de tab Elementen staat sinds F3e geen knop meer.
  - **Alleen de deelvragen**: *Annoteer de bepalingen van de deelvragen* (werkgebied) en *Annoteer de
    bepalingen hierbij* (deelvraag) sturen de actie `deelvragen_annoteren`; graph-qa annoteert dan alleen de
    bronnen onder de deelvragen, of onder die ene. De bevestiging draagt `bereik` en `deelvraag_id`.
  - **In het gesprek**: een antwoord met `bevestiging` (`parseBevestiging`; ook na herladen) krijgt de
    knop *Laat Lex annoteren*. Die gaat via `verstuur(…, annoteren)` →
    `startRun({modus: "werkgebied_annoteren", werkgebied_id, bevestigd, bereik?, deelvraag_id?})`.
  - **Annuleren** staat naast de knop (ook bij *Laat Lex meedenken*): geen beurt bij de agent, alleen een
    user-bericht "Annuleren" met `bevestiging_antwoord: {keuze: "geannuleerd"}`. De knop zelf zet
    `keuze: "gestart"` op zijn bericht. Een beantwoord voorstel toont geen knoppen meer maar een regel
    (`data-bevestiging-keuze`); welk voorstel een antwoord beantwoordt, rekent `afgehandeld`
    (`lib/werkgebiedAnnoteren.ts`): het laatste voorstel ervóór. Is de werkvoorraad intussen
    veranderd, dan begint graph-qa niet en komt er een nieuwe bevestiging.
  - De voortgang is het gewone `ReeksBlok` (labels met de regeling erbij); de samenvatting van de run
    staat eronder (`item.tekst` van het reeksitem).
  - Browserregressie: `scripts/test-werkgebied-annoteren.mjs`.
- **Lex denkt mee** (fase C; api §*Voorstellen van Lex* – de verdieping, graph-qa §*Lex denkt mee*).
  Lex begint nooit zonder akkoord; het model geeft advies en kaarten, de jurist beslist.
  - **Het aanbod staat in het gesprek** (F3e): de suggestie *Denk mee over de begrippen*, of Lex biedt het
    zelf aan na het voorstellen; graph-qa leest de werkvoorraad (`…/verdieping`) en antwoordt met een
    `bevestiging` (`soort: "begrippen_verdiepen"`) die *Laat Lex meedenken (n)* geeft. Die knop gaat via
    `verstuur(MEEDENK_PROMPT, …, {werkgebiedId, bevestigd, modus: "begrippen_verdiepen"})`.
    `parseBevestiging` kent beide soorten; een onbekende soort krijgt geen knop.
  - **Na het meedenken**: twijfelvragen tonen alleen wat open bleef (`openVragen`), met *Advies van Lex*;
    een groep `door: "model"` zegt "samengevoegd op advies van Lex"; de definitie komt uit de kaart
    (`groepDefinitie`: letterlijk heet "Brondefinitie", anders "Definitie, samengesteld uit de bron /
    geformuleerd door Lex", met de fragmenten en de toelichting ingeklapt); de aandachtspunten in tekst
    (`AANDACHTSPUNT`, gelijk aan graph-qa `toetsen.TEKST` – `begripVoorstellen.test.ts` leest die bron).
    Bij akkoord vult de api het begrip uit de kaart.
  - `BegripKaart` heeft het veld **begripstype** (werkindeling, geen JAS-klasse). "Geformuleerd" heet nu
    "door de analist of door Lex": de onderbouwing zegt wie.
  - De allowlist laat `verdieping` (lezen) door, nooit `…/batches/*` of `…/verdieping` op een run.
  - Browserregressie: `scripts/test-begrippen-verdieping.mjs`.
- **Lex naast de kaart** (fase E; api §*Lex naast de kaart*, graph-qa §*Lex naast de kaart*). De vier
  acties – de brondefinitie zoeken (zonder model), een scherpere definitie, het betekenisverschil, voorbeelden
  – zijn sinds F3c/F3e taken van de begrippen-agent: *Vraag Lex* bij het begrip en een suggestie (*Zoek de
  brondefinitie*, *Geef voorbeelden*, *Wat is het betekenisverschil met …*, *Werk het begrip volledig
  uit*). Er staan geen Lex-knoppen boven de kaart. De rekenkern van een voorstel staat in
  `lib/kaartVoorstel.ts`.
  - **Een voorstel staat onder zijn veld** (`KaartVoorstelKaart` in `BegripKaart`, via `lex` uit
    `BegripWerk`, en per veld in `BegripPaneel`): de tekst, de herkomst (`herkomstLabel`), de fragmenten, de aandachtspunten
    (`AANDACHTSPUNT_LEX`, gelijk aan graph-qa `kaartacties.TEKST` – de test leest die bron), en
    *Overnemen · Aanpassen · Afwijzen*. Alle knoppen zijn `type="button"` en Enter in het redenveld doet
    `preventDefault`: de kaart staat ín het formulier van het begrip.
  - **Niets stil overschreven.** Overnemen staat uit zolang de kaart onbewaarde wijzigingen heeft.
    `BegripWerk` laadt de voorstellen opnieuw bij elke revisie, zodat een eigen wijziging een open
    definitievoorstel meteen `verouderd` maakt: dan staan toen, nu en voorstel naast elkaar, en *Toch
    overnemen* stuurt `nu_gezien` mee (de api weigert anders met 409 `voorstel_verouderd`; `verouderdUit`
    leest die). Overnemen loopt via `muteer`, dus een 412 laadt opnieuw zoals elke mutatie.
  - **Herkomst**: bij het veld Definitie staat *Van Lex overgenomen* of *Door de analist*
    (`definitieDoor`, uit `definitie_door` dat de api zet); de historie noemt "Overgenomen van Lex: …"
    (`revisieZin`); besloten voorstellen staan ingeklapt onder *Eerdere voorstellen van Lex*.
  - De allowlist laat `…/voorstellen` (lezen) en `…/voorstellen/{id}/overnemen|afwijzen` door, nooit
    `…/kaart-runs/*`.
  - Browserregressie: het overnemen in het paneel in `scripts/test-artefacten.mjs`.
- **Herbeoordelen en dekking** (fase F1; api §*Onderhoud van begrippen*). Acceptatie: een gewijzigde
  dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand blijft.
  - **Tab Begrippen**: de strook *Herbeoordelen* (`strookKop` in `lib/herbeoordeling.ts`) noemt de
    begrippen met een geraakte passage, de lijst links ook; een klik in de strook opent het begrip op de
    kaart. Het antwoord komt van `GET …/herbeoordelingen` en vraagt de bronboom: het laadt los van de lijst
    en faalt stil
    (`isHerbeoordelingen`; zonder antwoord staan de begrippen er gewoon).
  - **Bij de passage** (`Herbeoordeling` in `BegripPassages`, uit `BegripWerk` dat per revisie
    `?begrip_id=` opnieuw vraagt): de redenen van de api, *toen* (het bewijs) naast *nu*, de wettekst van
    nu met het fragment aangewezen (`markeer`) of de zin dat het er niet meer staat, de opvolgers met hun
    signalen (teken + `sr-only`-richting, nooit een score). *Herkoppelen* en *Begrip klopt nog*
    (bevestigen) lopen via `muteer`, met een optionele toelichting; zonder opvolger en met een
    veranderde tekst op de plek een link om de bepaling opnieuw te annoteren. Een herkoppelde passage
    toont *Vervangt een eerdere passage* met het oude bewijs; een bevestigde zegt door wie.
  - **Tab Elementen**: `DekkingBalk` (te verwerken / voorstel / gekoppeld / buiten behandeling, plus
    *nieuw sinds de laatste begrippenronde*); per element de reden van *buiten behandeling* met
    *terughalen*, en in de selectiebalk *Buiten behandeling* met een verplichte reden. Een fout bij
    terughalen is een eigen melding, niet de fout van de tab.
  - De allowlist laat `herbeoordelingen`, `dekking`, `dekking/buiten-behandeling[/{element}]` en
    `…/koppelingen/{k}/herkoppelen|bevestigen` door; herbeoordelingen en dekking krijgen 90 s.
  - Browserregressie: `scripts/test-herbeoordeling.mjs`.
- **Relaties en opvolging** (fase F2; api §*Begripsrelaties en opvolging*). Onder de begripskaart staat
  `BegripRelaties` (buiten het formulier van de kaart).
  - **Een relatie is een zin met richting** (`relatieZin` in `lib/begripRelaties.ts`): "belastingaanslag
    omvat ook navorderingsaanslag", nooit alleen een lijn of "verwant". Bij `hierarchie` wijst de keten van
    de bredere term naar de soort, dus draait de zin om ("Y is een soort X"); ook de relaties "ter
    informatie" in *Voorstellen van Lex* gebruiken die zin (`hypotheseZin`).
  - **Voorstellen van Lex** staan geel met de passages waarop ze rusten: *Akkoord* (`legRelatieVast` met
    `voorstel_id`) of *Afwijzen* met reden. **Zelf toevoegen** vanuit dit begrip (`KEUZES`: geldt als, omvat
    ook, omvat niet, is een soort, heeft als soort, is verwant aan); `relatieInvoer` zet de richting,
    `magVastleggen` eist een toelichting bij verwant. Een relatie waarvan een kant veranderde staat geel met
    *Klopt nog*; *Weghalen* is een `BevestigKnop`.
  - **Nieuwe betekenis** (reden verplicht) en **Combineren met…** (vergelijking van de definities vooraf,
    een keuzerondje welk begrip blijft) leveren een ander begrip op; `onNaarBegrip` opent dat. Een vervangen
    begrip toont *Vervangen door …*, heeft geen *Lex naast de kaart* en geen opvolgknoppen; in de lijst staat
    het ingeklapt onder *Vervangen (n)*.
  - Herbeoordelen telt de relaties mee (`herbeoordelingZin(passages, relaties)`).
  - De allowlist laat `relaties`, `relaties/{id}`, `relaties/{id}/bevestigen`,
    `relaties/voorstellen/{id}/afwijzen` en `begrippen/{id}/nieuwe-betekenis|combineren` door.
  - Browserregressie: `scripts/test-begriprelaties.mjs`.
- **Begrippen in de graaf en NL-SBB** (fase F3; api §*Begrippen naar de kennisgraaf*).
  - **Tab Samenhang**: `SamenhangTab` haalt `GET …/begrippen/samenhang` op (faalt stil) en geeft
    `begripBron` (`lib/begripGraaf.ts`) als **toevoeging** aan `useGraafStand` – het zesde argument, apart
    van de stabiele `opties`. Een begrip is een knoop `begrip:<id>` (soort `begrip`, kleur per status in
    `BEGRIPKLEUR`), met `duidt` naar zijn markeringen (`element:<id>`) en per relatie een lijn met de zin
    als ankertekst (`relatieZin`): `begripsrelatie` (vastgelegd) of `begripsvoorstel` (geel, "voorstel van
    Lex: …"). Een afgewezen koppeling gaat niet mee; een lijn naar een niet-geladen markering valt in
    `bouwModel` weg.
  - **Geen wettekst**: `isBron` sluit begrippen uit, dus de layout van de bron verandert niet en er wordt
    niets gerekend; `plaatsAnnotaties` zet een begrip bij het zwaartepunt van zijn markeringen (zonder
    passage op een binnenring), op een plek uit zijn eigen id. Laag **Begrippen** (`Lagen.begrippen`) staat
    alleen in het lagenpaneel als er begrippen op de kaart zijn (`GraafLagen begrippen`).
  - **Inspector**: status en definitie ("een analyse-uitkomst … geen wettelijke definitie"), de groepen
    *Dragende passages*, *Relaties met begrippen* en *Voorgestelde relaties*; geen *Vraag Lex*, geen
    hoofdactie. `bijKnoop` geeft *Open de begripskaart* (`kiesBegrip` uit `WerkgebiedClient`).
  - **Kaart**: `NlSbbStand` in het blok Accorderen/Status (`GET …/begrippen/conformiteit`, opnieuw per
    revisie, faalt stil): "NL-SBB-conform (profiel 1.0.0)" of "Niet NL-SBB-conform: definitie ontbreekt …"
    (`conformZin`), met de meldingen uitklapbaar. Diagnostisch: accorderen volgt alleen de poort.
  - **Export**: naast CSV en JSON *Turtle (NL-SBB)* (`formaat=ttl`, alleen geaccordeerd) en *Turtle, alle
    begrippen* (`inclusief=alle`); `exporteerBegrippen` vertaalt `ttl-alle`. De allowlist laat
    `begrippen/samenhang` en `begrippen/conformiteit` al door (pad van lengte 3).
  - Browserregressie: `scripts/test-begrippengraaf.mjs`.
- **Begrippen over werkgebieden heen** (fase F4; api §*Begrippen lezen*): het sidebar-item *Begrippen*
  opent `/begrippen` (`BegrippenOverzichtClient` in `WerkgebiedSchil`, binnen een `Suspense` omdat de
  filters via `useSearchParams` in de URL staan). Een leesingang in de vorm van de andere overzichten
  (`OverzichtBalk`): één statuskeuze met tellers (`per_status` van de api), *Door mij bewerkt* (`mijn=1`
  in de URL, `mijn=true` naar de api), een compacte werkgebiedkeuze en zoeken (na 300 ms), en kaarten
  (`BegripOverzichtKaart`); `filtersUitParams`/`paramsVan` in `lib/begrippenOverzicht.ts` (de pagina heet
  het `werkgebied`, de api `werkgebied_id`; een oude URL met meer statussen leest als de eerste). Een rij noemt naam, status, werkgebied, alternatieve termen,
  definitie, *vervangen door* en – bij een geaccordeerd begrip met een veranderde dragende passage – geel
  *Herbeoordelen* (`herbeoordelen` van de api); een klik gaat naar de kaart (`kaartUrl`). BFF: de statische
  `app/api/begrippen/route.ts` geeft de query ongewijzigd door; `zoekBegrippen` toetst de vorm. Werk aan
  een begrip gebeurt op de kaart, niet hier. Browserregressie: `scripts/test-begrippenoverzicht.mjs`.
- **Tabs scrollen.** Tabs passen niet altijd naast elkaar op een telefoon; `TabLinks` en `Tabs` scrollen
  (`overflow-x-auto`, tabs `whitespace-nowrap`). Een afgekapte tab is onbereikbaar, en een toets op
  horizontale scroll van de pagina ziet dat niet.
- Browserregressie: `scripts/test-werkgebieden.mjs` en `scripts/test-begrippen.mjs` (mocks die revisies,
  de poort en de primaire duiding bijhouden zoals de api; de tweede loopt de acceptatie van levering 2).

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
- **Geen sneltoetsen** (besluit gebruiker 26 okt 2026): geen letters, geen `[`/`]`, geen hint. Een kaart
  kies je met een klik; beoordelen gaat met de knoppen. Alleen Escape pelt de lagen af (selectie →
  bedieningsrij → gekozen element → sluiten), en niet vanuit de chat ernaast. Na *Akkoord* springt de
  selectie naar het volgende dat aandacht vraagt (`onAkkoord`).
- **Volgorde en open bedieningsrij leven in `ArtefactInhoud`**, niet in de lijst: er staat nooit op twee
  kaarten tegelijk een rij open.

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
  De vlag "nog gemount" zet hij bij elke mount opnieuw: onder StrictMode (dev) bleef een knop die na een
  mislukte handeling blijft staan anders op `Bezig…` hangen.
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
  welke niet, en per dimensie wat er gevonden werd (`aangetroffen`, `gevondenTekst` in
  `lib/dekking.ts`). Een oudere meting zonder telling toont geen regel: onbekend is geen 0. Ook het
  aantal zinsdelen dat alleen als geheel geraakt werd (`alleen_als_geheel`, bv. alleen de hele
  normzin) staat erbij: in `ongedekt` telt zo'n zin als geraakt.

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

## De samenhangsgraaf (sigma.js)

`NodeAnnotatiePaneel` heeft naast *Tekst* een tab **Graaf** (`components/graaf/Graaf.tsx`), en onder een
antwoord met een bron naar een BWB-bepaling staat een knop die hetzelfde paneel op die tab opent
("Bekijk samenhang van … in de graaf"; in de bronkaart van een citatie-chip *Bekijk in de graaf*). Een
2D-graaf op **sigma.js v3 + graphology**: WebGL, gebouwd om de hele kennisgraaf (~6.500 knopen, ~10.000
lijnen) vloeiend te tekenen. Sigma 4 kwam uit op 8 okt 2026; de overstap raakt alleen `GraafTekenaar`.

**Lagen met één taak** – houd ze gescheiden:

```
api /samenhang, /samenhang/meer, /graaf ─► lib/graaf/model ─► layout (worker + cache) ─► weergave (puur) ─► GraafTekenaar (sigma)
                                                                       UI-schil: Graaf.tsx + useGraafStand ┘
```

- **`lib/graaf/model.ts`** – één graphology-graaf uit wat de api levert (alle endpoints hebben dezelfde
  `Knoop`/`Relatie`-vorm), pure data met `naam`/`kort` ("Artikel 9 · lid 2" / "Lid 2"). Gesorteerd, dus
  volgorde-onafhankelijk; een knoop is pas rand als hij dat in élk antwoord is.
- **`lib/graaf/layout.ts`** – deterministisch, twee lagen. *De wettekst*: een radiale boom per regeling
  als start, dan ForceAtlas2 met **alleen de opbouw (`bevat`) als veer** en een `adjustSizes`-fase tegen
  overlap; elke regeling wordt een eigen gebied met haar hoofdstukken erin. **Verwijzingen trekken
  niet** (3.500 verwijzingen trokken alles tot één kluwen) – behalve aan een randbepaling, die anders
  wegdrijft. *De annotaties* worden afgeleid (`plaatsAnnotaties`): een markering bij haar anker op een
  plek uit haar eigen id, de JAS-klassen in tabelvolgorde op een ring net buiten de kaart. Een
  beoordeling verschuift dus niets en vraagt geen nieuwe layout. Geen `graphology-layout-noverlap`:
  die gebruikt `Math.random`. Verhoog `LAYOUT_VERSIE` bij elke wijziging die de uitkomst verandert.
- **`lib/graaf/rekenaar.ts` + `layout.worker.ts`** – `layoutVoor(model, {vast})`: uit de cache, of in een
  Web Worker met voortgang. Met `vast` (bijladen, annotatiewijziging) liggen bestaande knopen vast en
  wordt er alleen gerekend als er nieuwe wettekst is. De worker vraagt `worker-src 'self'` in de CSP
  (`lib/csp.ts`), anders blokkeert `'strict-dynamic'` hem. Turbopack bundelt hem via
  `new Worker(new URL("./layout.worker.ts", import.meta.url))` – houd die vorm letterlijk.
- **`lib/graaf/cache.ts`** – posities in IndexedDB onder een SHA-256 van de structuur; elke toegang in
  try/catch, zonder opslag wordt er gewoon gerekend.
- **`lib/graaf/weergave.ts`** – **het enige selectiemodel**, puur en getest:
  - *zichtbaar* = lagen (*Leden en onderdelen*, *Verwijzingen*, *Annotaties*) + markeringsfilter. **Een
    klik in de graaf verandert nooit wat zichtbaar is.** Wie via zoeken of de inspector een verborgen
    knoop kiest, krijgt de nodige laag aan (`lagenVoor`) – de zoeklijst zegt "laag staat uit".
  - *nadruk* = de keuze met haar buren > de focus > alles. De rest is gedimd (`GEDIMD`: zichtbaar als
    kaart, zonder eigen label). **Er is geen beginkeuze: het begin is de focus**, in beide bereiken, en
    een klik op de achtergrond of Escape heft de keuze op en brengt dat begin terug. De keuze en (tot
    30) buren hebben voorrang op een label (`vastLabel`).
  - de focus (`focusVan`): de doelen, alles eronder, de markeringen daarop met hun klasse, en bij een
    bepaling ook haar verwijzingen (één stap, in- en uitgaand) – bij een hoofdstuk niet, dat zijn er
    honderden.
  - lijnen naar een JAS-klasse alleen bij een gekozen markering of klasse.
- **`lib/graaf/labels.ts`** – **welke knopen een label krijgen**: nooit twee over elkaar, en meer detail
  naarmate je inzoomt. Sigma's eigen labelraster toetst de breedte van een label niet en zet
  `forceLabel` ongetoetst bovenop; daarom staat het op nul (`labelDensity: 0`) en kiest `kiesLabels`
  per beeld: gulzig op prioriteit (keuze/aangewezen > nadruk > gewoon > gedimd, dan de soort), een
  label alleen als zijn rechthoek vrij ligt én helemaal in beeld past; wat vorig beeld stond wint bij
  gelijke prioriteit (geen geflikker). De zwevende bediening telt als bezet. Detailniveau per soort
  (`LABEL_VANAF`, `magLabel`) op een *effectieve* zoom die de grootte van de kaart meeweegt: uitgezoomd
  alleen regelingen, hoofdstukken en klassen, dan artikelen, leden, en ten slotte onderdelen en
  markeringen. Gedimde knopen dingen mee met een grijs oriëntatielabel (`GEDIMD_LABEL`). Uitgezoomd
  zijn onderdelen en markeringen kleiner (`detailFactor`).
- **`lib/graaf/spans.ts`** – de wettekst van een bronknoop met de markeringen erin, voor de inspector:
  alleen op hun **ankers** (codepoints, met dezelfde `bron_hash`), nooit via tekstzoeken; bij overlap
  de kortste bovenop; verworpen en verouderde markeringen niet.
- **`lib/graaf/bediening.ts`** – zoeken (over het hele model, diakritiek-ongevoelig, natuurlijk op
  nummer), relatiegroepen, de ene `hoofdactie` (`tekst` / `wissel` / `laden` / niets), `paneelDoel` en de
  telling in gewone woorden. **`lib/graaf/stijl.ts`** – het palet; WebGL kent geen CSS-variabelen, dus
  concrete kleuren, afgestemd op de tokens.
- **`components/graaf/GraafTekenaar.tsx`** – de **enige plek die sigma kent**: tekent het model op zijn
  posities, vraagt per knoop/lijn het beeld op bij `weergave.ts` (reducers) en meldt klik/achtergrond
  terug. Eén programma voor alle knopen (`@sigma/node-border`): omtrek = randbepaling of laag Dekking.
  Lui geladen (`next/dynamic`). Valkuilen die hier opgelost zijn: een keuze verandert grootte en
  tekenvolgorde, dus `refresh()` zonder `skipIndexation`; een `ResizeObserver` doet `resize` én
  `refresh`; bij unmount wordt het **doel** van een lopende camerabeweging bewaard, niet de tussenstand
  (anders staat het vergrote beeld halverwege een vlucht); geen WebGL of contextverlies → `onFout`.
  **De labelkeuze gebeurt bij het eerste label dat sigma tekent, niet in `beforeRender`**: daar zijn
  de knoopdata (na een `refresh`) en de cameramatrix nog die van het vorige beeld. De reducer houdt per
  knoop bij wat de keuze nodig heeft (`labelInfo`), zodat die geen 6.500 knoopdata hoeft te kopiëren.
  Inpassen op één knoop zoomt niet dieper dan de kaart vraagt (`minRatio`), zodat de buurt in beeld
  blijft.
  **Een klik herkent de tekenaar zelf** (`downNode`/`downStage` → `upNode`/`upStage`, hoogstens 5 px
  bewogen, zelfde knoop of achtergrond): sigma's `clickNode`/`clickStage` laten een klik alleen door
  bij minder dan 3 muisbewegingen – een telling, geen afstand – en met een trackpad of snelle muis
  deed klikken dan niets. Een dubbelklik zoomt nog steeds (sigma), en telt daarnaast als klik. De hover
  noemt de volledige `naam` ("Artikel 9 · lid 1"), niet het kaartlabel.
- **`components/graaf/useGraafStand.ts`** – data, laadfase, het getekende beeld (model + posities samen
  vervangen, nooit knopen zonder plek), keuze, lagen, camera. Leeft in het paneel (búiten de `Dialog`):
  vergroten remount de inhoud. Het layout-effect zet niets meer na een abort: `layoutVoor` toetst het
  `signal` na elke `await` (`blijfBijDeZaak`), anders zette een cache-lezing van een vervallen run een
  oude kaart over een nieuwere heen.
  **Twee foutkanalen.** `fout` blokkeert het tekenen in díe bron en dat bereik (samenhang, kennisgraaf,
  layout), staat midden op het canvas en heeft zijn eigen herstel (*Opnieuw proberen*); `melding`
  (verversen of bijladen mislukt) blokkeert niets en verdwijnt bij de volgende geslaagde handeling. Eén
  gedeelde foutstring liet een melding uit het andere bereik staan en hield de laadbalk weg.
  **`selectie` bevat alleen ids op de kaart.** Een keuze voor iets dat nog niet geladen is (het
  overzichtsblok wijst een knoop uit de kennisgraaf aan) is een `wachtendeKeuze`; die wordt een gewone
  `kies` (met `lagenVoor` en de melding aan het paneel) zodra de kaart er is. Een keuze die van de
  kaart verdwijnt (verworpen markering) vervalt.

**Data en gedrag**:

- **De knop opent wat het antwoord noemt** (`samenhangDoelen` in `lib/bronnen.ts`, max.
  `MAX_SAMENHANG_DOELEN`) of de delen van een overzicht (`overzichtDoelen` in `lib/overzicht.ts`, max.
  `MAX_OVERZICHT_DOELEN`, uit het overzicht en niet uit de tekst: dezelfde vraag geeft dezelfde kaart).
  Meer dan één doel gaat in **één** verzoek (`/samenhang/meer`, één bronboom per regeling) – in
  partijen van `MAX_SAMENHANG_MEER` (30, de grens van de api, die anders het hele verzoek weigert):
  na een paar keer *Open in het paneel* vanuit een overzicht zijn het er al meer. Het eerste
  doel is het doel van het paneel (tekst en annotatie); een knoop uit een ander artikel – meegeladen of
  uit de hele kennisgraaf – opent dát in het paneel (*Open in het paneel*), en bereik en focus gaan mee:
  `onWisselArtikel(doel, { bereik, kennisgraaf })` geeft het bereik van nú door, en de geladen
  kennisgraaf als die actueel is (`kennisgraafActueel`), zodat het geremounte paneel hem niet opnieuw
  ophaalt. `WerkplekClient` haalt die doorgegeven kennisgraaf weg bij elke andere doelwissel
  (`zonderKennisgraaf`): na een beurt van Lex klopt hij niet meer. Beide alleen als de API de capability `samenhang` meldt.
- **Een randbepaling** (buiten wat geladen is, als omtrek getekend) laad je erbij met *In de graaf laden*;
  de kaart blijft liggen. Een niet-geïmporteerde bepaling (`extern`) is niet te laden. Afstand en
  positie betekenen juridisch niets; dat staat in de legenda.
- **De inspector** (`GraafInspector`) **toont alles meteen, zonder de graaf te verlaten**: soort en naam,
  *Centreren* en ✕, de wettekst met de markeringen erin in hun JAS-kleur (`KnoopTekst`; een klik op een
  span kiest die markering in de graaf), bij een markering ook toelichting, review-uitleg,
  alternatieven en de Waarom-uitklap (open), en de relaties per soort. Alleen lezen: beoordelen gebeurt
  in de tekst. De gevulde knop is er alleen voor wat in de graaf blijft (*In de graaf laden*); *Bekijk
  in de tekst* / *Beoordeel in de tekst* / *Open in het paneel* zijn rustige links. De tekst komt uit de
  weergave van het paneel, en anders één keer per knoop via `GET weergave` (`useKnoopDetail`, cache
  per paneel, leeg na `ververs`) – de hele kennisgraaf draagt bewust geen tekst. Het element van een
  markering wordt bij het kiezen opgehaald (`useMarkeringElement`). Zonder keuze: *Dit antwoord* (de
  doelen, klikbaar) en wat er geladen is. Smal onder de graaf (details in te klappen); vergroot een
  **zijbalk** rechts (`md:w-[22rem] lg:w-[26rem] xl:w-[28rem]`), in te klappen tot een strook met een
  greep op zijn linkerrand – de stand per kijker in `localStorage` (`wa_graaf_zijbalk`, in try/catch),
  ingeklapt blijft ingeklapt bij een nieuwe keuze, de strook toont de kleur van de keuze. Per keuze
  een `key`, dus elke keuze begint bovenaan. **Eén scrollvak**: de schil geeft alleen hoogte door, het
  detailblok scrolt. Twee scrollvakken in elkaar slikken het muiswiel, want `overscroll-behavior:
  contain` (`globals.css`) laat het binnenste, dat niets te scrollen heeft, het wiel niet doorgeven.
  In *Uit de kennisgraaf* staat het label **boven** de waarde: naast elkaar liep een lang woord
  ("Eerstverantwoordelijke") in de zijbalk over zijn waarde.
- **Uit de kennisgraaf** (`KnoopFeiten`, `lib/graaf/knoopinfo.ts`, `GET knoop`, cache per paneel via
  `useKnoopInfo`): bij een bronknoop wat de graaf er verder over weet – geldigheid, herkomst van de
  tekst, regeling, grondslag en bevoegdheid, genoemd in, begrip, vindplaats – en ingeklapt alle
  triples ruw. Een waarde die op de kaart staat kies je in de graaf; de rest wordt een link via
  `bronHref` (een niet-BWB-IRI blijft tekst). Datums in gewone woorden (`datumTekst`). In *Verwijst
  naar* / *Wordt verwezen door* staat per regel wat de verwijzing is (`verwijzingTekst`: binnen deze
  regeling / naar een andere / uit de tekst herkend, soort doel, pad) en *lage betrouwbaarheid* bij een
  alleen uit de tekst herkende verwijzing. **Lijnen zijn bewust niet klikbaar**: sigma's raakgebied is
  de getekende dikte (1–1,7 px) op een picking-buffer met halve resolutie, en in de kennisgraaf liggen
  ~10.000 lijnen over elkaar – een klik naast een knoop zou dan een lijn kiezen.
- **Bediening als een kaart-app**: zoeken linksboven (`GraafZoek`, ook de toetsenbordroute), *Lagen*
  linksonder (`GraafLagen`: lagen, markeringsfilter en de legenda in één paneel), beeld rechtsonder
  (`GraafBeeld`: *Naar het antwoord*, *Alles in beeld*, zoomen), een eenmalige hint (`GraafHint`). Zolang
  er een keuze is staat onder het zoekveld *Terug naar het antwoord*. **Escape** van binnen naar buiten: zoeklijst → Lagen
  → keuze → verkleinen → sluiten.
- **Laadbalk**: "Graaf ophalen…" (onbepaald) → "Layout berekenen – n %" (`Meter`, met `percentage:
  null` voor onbepaald); hij verschijnt pas na 250 ms, zodat een layout uit de cache niet flitst.
- **Eén keuze**: de gekozen markering is in tekst en graaf dezelfde (`actiefId` van het paneel); een
  keuze uit de tekst vliegt in de graaf in beeld. *Bekijk in de tekst* wisselt naar de tekst en scrolt
  naar het lid (`data-lid`) – alleen voor wat **in de weergave van het paneel** staat
  (`knopenInWeergave`: het doel, wat het in de opbouw bevat, zijn segmenten en elementen). Het paneel
  toont vaak één lid terwijl de graaf het hele artikel heeft; de rest krijgt *Open in het paneel*, een
  markering op haar anker. Een id dat niet op de kaart staat, kiest niets.
- **Laag Dekking**: de zinsdelen zonder detectortreffer uit het paneel (`ongedektPerBron`) geven een lid
  of onderdeel een okeromtrek (`DEKKINGSKLEUR`) en in de inspector *Zonder detectortreffer*.
- **Live bij een annotatiewijziging – verversen is een toestand.** `NodeAnnotatiePaneel` roept na elke
  mutatie `graafStand.ververs()` aan, en dat noteert alleen dát de graaf achterloopt (`gevraagd` >
  `gedaan`). Mutaties gebeuren op de Tekst-tab; pas als de graaf weer zichtbaar is, haalt hij op: alle
  geladen delen in één `/samenhang/meer` en zo nodig de kennisgraaf. Eén ronde tegelijk; wat er tijdens
  een ronde nog bijkomt, geeft daarna precies één ronde – dus nooit een ouder antwoord over een
  nieuwer heen, en geen 2 MB per `a`-toets. De kaart verschuift niet.
- **Bereik: *Dit antwoord* | *Hele kennisgraaf*** (schakelaar rechtsboven, `Bereik` in `useGraafStand`;
  mobiel "Antwoord" | "Alles" met de volle naam als `aria-label`, zodat het zoekveld ernaast leesbaar
  blijft – om dezelfde reden is de focusregel in de kop mobiel één korte zin).
  De hele kennisgraaf (`/graaf`, `lib/graaf/data.ts`, ~6.500 knopen) wordt één keer per paneel opgehaald
  en samengevoegd met de geladen samenhang – die eerst, want zij draagt de wettekst. Elk bereik heeft een
  eigen layout; de kennisgraaf begint altijd vers en komt dus uit de cache (gemeten tegen de
  productiebuild: 4,6 s de eerste keer, 0,24 s daarna). Wisselen houdt keuze en lagen; bij een nieuwe kaart
  past de tekenaar de camera in (`inpassen`: de keuze, anders de focus). Na een annotatiewijziging wordt
  ook de kennisgraaf opnieuw opgehaald – de markeringen erin komen vers uit de api.
- **Focus** (in beide bereiken): wat het antwoord noemt (`focusVan`) heeft nadruk; de rest staat gedimd
  op de kaart. De kop zegt het ("Nadruk op wat het antwoord noemt (n …)"). Zonder expliciete focus zijn
  het de doelen van de knop. Beslaat de focus de hele kaart (het doel is een heel artikel), dan is er
  geen focus en dus niets gedimd.
- **Een overzicht opent de hele kennisgraaf** met als focus álles uit het overzicht (`overzichtFocus`:
  delen, subdelen, bepalingen en wat het onderwerp verder noemt – geen grens), zonder keuze: een keuze
  zou de focus overschrijven. De knop zegt het: "Bekijk de 4 delen in de kennisgraaf". *Dit antwoord*
  laadt daar de delen zelf (`/samenhang/meer`, hoogstens `MAX_OVERZICHT_DOELEN`).
- **Het overzichtsblok is de inhoudsopgave van de kaart** (`components/graaf/koppeling.ts`). Staat de
  graaf open, dan licht aanwijzen (hover of focus) van een kop of nummer de knoop uit
  (`WeergaveStand.aangewezen`) en kiest een klik hem – met Ctrl/⌘/Shift, of zonder open graaf, is het
  de gewone link. Een knoop die alleen in de kennisgraaf staat, schakelt daarheen. De graaf zet zijn
  handelingen in een ref (`koppelingRef`), de werkplek geeft via context een stabiel doorgeefluik aan de
  thread: zo rendert geen `ThreadRij` opnieuw als het paneel opent of sluit.
- **Buiten het paneel** draagt `Graaf` twee haken: `benaming` (`GraafContext`: hoe de doelen heten in
  de bereikschakelaar, *Terug naar …*, de focusregel en de inspector; standaard het antwoord) en
  `bijKnoop` (een extra handeling in de inspector). De uitleg over "de tekst en de annotatie in het
  paneel" staat er alleen mét `weergave`. Gebruikt door de tab Samenhang van een werkgebied.
- Browserregressie: `scripts/test-samenhang.mjs` (klikken via de canvasmidden na *Centreren*, kiezen
  en lagen via de zoeklijst, `data-selectie`/`data-aangewezen`/`data-bereik`/`data-gereed` op de graaf,
  `data-labels`/`data-label-soorten` op de tekenaar;
  een gegenereerde kennisgraaf van ~6.500 knopen voor laadbalk, focus, koppeling en de cache).

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
  `lib/rondleiding.ts`. De rondleiding doet alleen iets als de gebruiker iets doet: een stap die om
  een handeling vraagt (`interactie`) laat het aangewezen element bedienen en wacht erop – geen timer
  die de handeling overneemt – en de toetsen volgen `toetsActie` (een knop of veld handelt zijn eigen
  Enter af). Alle andere browserscripts zetten de rondleiding uit; `scripts/test-rondleiding.mjs`
  loopt hem door. De voorbeeldscène in `lib/rondleidingDemo.ts` is een v2-weergave met letterlijke
  wettekst en ankers die per lid berekend zijn (`segmentAnker`): artikel 9 **lid 1** van de
  Invorderingswet 1990 met de vier markeringen van de echte annotatie op acceptatie (Rechtsfeit over de
  hele zin, dus overlappend zoals bij echt werk), en één bewuste afwijking: Rechtsfeit staat op *Keuze voor
  jou*, zodat de badge-stap iets aanwijst. Werkgebieden en begrippen hebben (nog) geen eigen stap; de stap *Je werk terugvinden* en het slot noemen de zijbalk in de volgorde Werkgebieden, Annotaties, Begrippen (de volgorde van de navigatie, besluit gebruiker 21 okt 2026). Hij staat in **hetzelfde
  `NodeAnnotatiePaneel` als echt werk**, via de prop `opslag` (`NodeOpslag` in `lib/annotatieNode.ts`;
  standaard `apiOpslag`): een opslag in het geheugen die de lichamen van de api krijgt en niets
  verstuurt. Zo kan de rondleiding niet meer achterlopen op het paneel; een eigen documentvorm in een
  eigen paneel deed dat wel. Het type
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
  en een scherpe `BevestigKnop` vangen hun Escape in de capture-fase af. Lex heeft geen sneltoetsen;
  Escape van het artefact geldt alleen met de focus in het artefact (`focusBijArtefact`).

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
  het nonce zelf op zijn scripts; lui geladen chunks (`next/dynamic`, sigma) mogen via
  `'strict-dynamic'`.
  - **Geen eigen inline `<script>` en geen `next/script` met inline code**: die krijgt geen nonce en
    wordt in productie stil geblokkeerd. Nodig? Lees het nonce met `(await headers()).get("x-nonce")`
    in een Server Component en geef het mee.
  - **Elke pagina rendert dynamisch** (`app/layout.tsx` roept `auth()` aan); een statische pagina kan
    geen nonce krijgen.
  - `style-src` houdt `'unsafe-inline'`, omdat de server-render `style="…"`-attributen meegeeft en een
    nonce niet voor attributen geldt.
  - `worker-src 'self'`: zonder die regel valt een worker terug op `script-src`, waar
    `'strict-dynamic'` `'self'` ongeldig maakt – en dan weigert de browser de layout-worker van de graaf.
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

`test:browser` draait `scripts/test-annotatie-nodes.mjs`, `test-samenhang.mjs`, `test-reeks.mjs`,
`test-toetsen.mjs`, `test-werkgebieden.mjs`, `test-begrippen.mjs`, `test-begripvoorstellen.mjs` en
`test-artefacten.mjs` (de soorten artefacten in de werkplek), `test-bronkandidaten.mjs`, `test-sidebar-groepen.mjs` (spoor G1), `test-detailpaginas.mjs` (spoor G3), `test-contextpaneel.mjs` (spoor G4),
`test-werkgebied-annoteren.mjs`, `test-begrippen-verdieping.mjs`, `test-herbeoordeling.mjs`, `test-begriprelaties.mjs`, `test-begrippengraaf.mjs`, `test-begrippenoverzicht.mjs`, `test-deelvragen.mjs`, `test-vraaglex.mjs` en `test-rondleiding.mjs`, en verwacht een devserver op poort 3109
(`AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --port 3109`).
Praat met **`localhost`**, niet met `127.0.0.1`: Next 16 weigert dev-assets aan een andere origin,
waarna de pagina niet hydrateert en elke stap zonder duidelijke fout time-out.
`scripts/test-toetsen.mjs` bewaakt wat alleen in een browser te zien is: een letter beslist niets (geen
sneltoetsen), Escape voor het bovenste venster, focus terug na sluiten, geen herstellus na
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
