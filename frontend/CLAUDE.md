# CLAUDE.md – wetsanalyse-frontend

Next.js (App Router) + TypeScript-webapp bovenop de graph-qa-agent en, voor login, beheer en
opslag, de [wetsanalyse-API](../api). De app **is de werkplek**: `/workbench` (de *Lex-pagina*) –
één chat-achtig gespreksvenster voor **vragen én JAS-annotatie**, live tegen graph-qa. De home (`/`)
leidt daarheen door.

> **Scope: chat-werkruimte.** De app bestaat uit de werkplek, het annotatie-overzicht, de
> werkgebieden, het begrippenoverzicht, de werkwijze van Lex (de catalogus, ADR-014), de login-flow en het instellingenvenster (account, verbruik, berichten, en voor beheerders
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
  het admin-token, na de rolcontrole en de 2FA-plicht: `tweeFactorOntbreekt` vraagt bij elke admin-aanroep
  `/v1/auth/me` (403 `code: "2fa_nodig"`, 503 als dat niet lukt). Bewust niet uit de JWT: de cookie loopt
  achter, dus na het koppelen bleef het beheer dan tot vijf minuten dicht. Verzin in een nieuwe route geen
  eigen fetch-logica. De helper bewaakt ook de
  **wachttijd**, want Node's `fetch` kent geen standaardtimeout en een upstream die verbindt maar niet
  antwoordt laat de UI anders eeuwig laden: default 30 s → **504** met een leesbare reden
  (onbereikbaar = 502); `timeoutMs` per route hoger waar dat hoort (de modeltest: 120 s). De grens
  geldt tot de headers: de body **stroomt door** zonder buffer, zodat een grote export (de PDF van een
  werkgebied) niet op de time-out of het geheugen strandt. `Content-Encoding` en `Content-Length` gaan
  daarom niet mee – Node's `fetch` heeft het gzip-antwoord van de api al uitgepakt. Leest een route
  alleen de status van een proxy-antwoord (een eigenaarscontrole), sluit de stroom dan met `sluit()`.
  `agent: true` maakt graph-qa de upstream, met zijn eigen token; de run-routes (starten, de actieve
  run, stoppen) lopen zo ook via `proxy()`.
  **Uitzondering: SSE.** `app/api/annotatie/run/[id]/events/route.ts` gebruikt geen `proxy()` maar
  geeft `upstream.body` rauw door met `X-Accel-Buffering: no` en `Cache-Control: no-transform`.
- **`app/api/_lib/session.ts`** – `sessionUserId()` voor de vertrouwde `X-User-Id`-header.
- **Inloggen met een accounttoken** (`auth.ts`, provider `api-token`, alleen met `API_TOKEN_LOGIN`): een
  MCP-client wisselt zijn `wa_pat_`-token in voor een gewone sessie, dus de BFF-routes weten niets van tokens.
  Zo'n sessie draagt `viaToken`, duurt een uur, vervalt met het token en mag nooit bij
  `/api/admin/api-tokens`, `/api/account/password`, `/api/account/2fa` en de 2FA-reset van een gebruiker
  (`auth.config.ts`). De 2FA-plicht geldt er niet: zo'n sessie kan niet koppelen.
- **`lib/server.ts`** – server-side helpers voor Server Components en auth
  (`verifyCredentials`/`getAccountStatus`/`getSetupStatus`), rechtstreeks server→server.
- **`lib/api.ts`** – alle client-side fetch-helpers naar `/api/**`, met één foutcontract
  (`parseError` → `ApiError`); gebruik `isApiError()` en `foutTekst()` in de UI.
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
  `markering`, `popover`, `wetstructuur`, `lopendeRun`, `geschiedenis` (de bewaarde berichten als items), `beurtStroom` (wat één poging van een beurt ophoopt), `beurtVerzoek` (wat een beurt vraagt: `verstuur(verzoek)` en de run-aanvraag `startOpties`), `beurtLus` (een run volgen tot hij afloopt), `beurtFase` (waar de beurt van een venster staat), `rondleiding`, `werkgebied`, `begrippen`,
  `begripVoorstellen`, `begripTermen`, `bronPlaats`, `kaartVoorstel`, `herbeoordeling`, `begripRelaties`, `begripGraaf`, `begrippenOverzicht`, `artefact`, `bronKandidaten`, `deelvragen`, `onbewaard`, `vraagkaart`, `gesprekGroepen`, `werkgebiedPaden`, …).
- **`app/**/page.tsx`** (Server Components) – data via `lib/server.ts`, interactie in een
  `*Client.tsx`. `app/page.tsx` doet `redirect("/workbench")`. De werkplek zit in
  `app/workbench/page.tsx` én in `app/default.tsx` (de default van het children-slot); beide renderen
  `WerkplekVenster`, zodat de router bij het wisselen tussen die twee geen remount veroorzaakt en het
  open gesprek blijft staan. Auth-schermen: `app/login/*`, `app/setup`, `app/registreren`,
  `app/disclaimer`. Account en beheer leven in het **instellingenvenster**, en dat is **altijd een pop-up**
  (besluit gebruiker 7 nov 2026, zoals in Slack): `InstellingenVenster` in `app/layout.tsx` opent hem over elke pagina
  zolang `?instellingen=<tab>` in de URL staat, ook na herladen of via een link. Openen, van tab wisselen en sluiten gaan
  met de History API (`lib/instellingenVenster.ts`), dus de pagina eronder blijft staan; links gaan via
  `InstellingenLink`. Geef in die state alleen de eigen markering mee: met `{...history.state}` erin volgt
  `useSearchParams` de stap niet en blijft het venster dicht. `app/instellingen/[[...tab]]`, `app/beheer` en `app/account`
  zijn doorverwijzingen naar de werkplek met het venster open; een losse instellingenpagina bestaat niet.
- **`components/`**:
  - `werkplek/` – de hele chat-werkruimte: schil, sidebar, thread (`ThreadRij`,
    `KeuzeKaart`, `VraagDock`, `VragenKaart`, `ReeksBlok`, `HergebruikMelding`, `Markdown`) en het annotatiegereedschap in het
    artefactpaneel (`ArtefactInhoud`, `AnnotatieTekst`, `ReviewQueue`,
    `SelectiePopover`, `ExportKnop`).
  - `annotaties/` – het overzicht en de losse annotatiepagina (`AnnotatiesClient`, `AnnotatieKaart`,
    `NodeAnnotatiePaneel`, `AnnotatiePaginaSchil`).
  - `werkgebieden/` – overzicht en pagina van een werkgebied (`WerkgebiedenClient`,
    `WerkgebiedClient`, de tabs `OverzichtTab`/`ElementenTab`/`SamenhangTab`/`HistorieTab`, het kader `BegrippenKader`,
    het begrip als `BegripInhoud` met `useBegrip` (dezelfde inhoud op de pagina en naast het gesprek),
    `WerkgebiedSchil`, en
    `OpnemenInWerkgebied` voor de annotatiepagina).
  - `graaf/` – de samenhangsgraaf (sigma); de rekenkern staat in `lib/graaf/`.
  - `admin/` – de beheertabs achter het admin-token: `ProfielenPanel` (+ `ProfileEditor`),
    `UsersPanel` (+ `BudgetBeleidBlok`), `RegistratiesPanel`, `ApiTokensPanel`,
    `BerichtenBeheerPanel` (+ `BerichtEditor`), `FeedbackLijstClient`, `ConnectorsPanel` (de bronconnectors van ADR-013: aan of
    uit per beheerder mét 2FA, met de audit ingeklapt; welke er bestaan staat in de code; browserregressie
    `scripts/test-connectors.mjs`).
  - `account/`, `auth/` – account, login/2FA/setup/registratie, disclaimer, `AuthFrame`.
  - `instellingen/` – `InstellingenVenster` (leest de parameter), `InstellingenDialog` (de dialoogschil),
    `InstellingenInhoud` (de tabs) en `InstellingenLink`. De tabdefinities en helpers staan in `lib/instellingen.ts`,
    bewust **zonder** `"use client"`, zodat de doorverwijzing ze mag importeren.
  - `rondleiding/` – de rondleiding door de werkplek (zie §*Rondleiding*).
  - `ui/` – de primitives.

### Generieke componenten (kernprincipe, besluit gebruiker 9 nov 2026)

**Eén component per patroon, en geen deeloplossingen ernaast.** Wat op meer plekken terugkomt – een kop, een label, een
weergave van wettekst, een melding – is één component of één functie, en elke plek gebruikt die. Een tweede variant
verdwijnt; hij blijft niet "voorlopig" naast de nieuwe staan. Een vormtest in `app/*.test.ts` bewaakt dat er geen
tweede terugkomt (in de lijn van `knoppen.test.ts` en `eenSpoor.test.ts`). Bouw je iets wat er al bijna is, breid dan
het bestaande uit.

**De herkomst van een bepaling** (het bronvenster, PR 1; `app/herkomst.test.ts`): welke wet, waar in de wet en welke
stand komt uit `lib/herkomst.ts`.
- `herkomstVan` maakt de herkomst uit wat een plek weet (vindplaats, `BepalingDetail`). Het label komt uit de IRI als
  de bron alleen een staart gaf ("Lid 2" wordt "Artikel 9, lid 2"); een label dat de regeling al draagt wordt gesplitst.
  `vindplaatsTekst` is het volle label ("Artikel 9, lid 2, Invorderingswet 1990"), `bepalingKort` de korte vorm van een
  annotatie ("art. 9 lid 2"), `annotatieKopTekst` het opschrift van een annotatie.
- De kop van een paneel met een bepaling: `herkomstKop` als titel, `HerkomstRegel` (`components/ui`) als tweede regel:
  regeling · plek (`plaatsKort`, voluit in de tooltip) · stand · wetten.overheid.nl. `useBronHerkomst` haalt het
  detail (`haalBepalingDetail`, per sessie gecachet) en de peildatum van het werkgebied.
- Over de stand zegt alleen `StandMelding` iets (`standMeldingen`): nog niet in werking, een nieuwere toestand dan Lex
  las, een stand ná de peildatum. De graaf draagt één toestand per regeling; de melding suggereert nooit een oudere versie.
- Geen eigen `` `${v.label}, ${v.regeling}` ``, geen tweede `vindplaatsLabel` (die van `lib/samenhang.ts` is de spiegel
  van `bronmodel.vindplaats`), geen eigen zin over de stand.
- Wat het venster opent, is een `BronDoel` (`lib/bronDoel.ts`): een bepaling of een stuk uit een bronconnector.

**De wettekst** (het bronvenster, PR 2; `app/wettekst.test.ts`) wordt op één manier getekend en opgehaald.
- `components/wettekst/WettekstBlok` tekent de segmenten met de markeringen op hun ankers (`kiesbaar`/`onKies`,
  `gekozen`, `groot`), of een losse tekst met één fragment aangewezen (`tekst` + `markeer`, de herbeoordeling).
  `BepalingTekst` haalt de tekst van één bepaling zelf op, met laadregel, foutzin en eventueel *Open de bepaling*.
- `lib/useBron.ts` (`useBepaling`, `haalBepalingWeergave`, `vergeetBepalingWeergave`) is de enige plek naast de
  annotatieopslag die `haalNodeWeergave` aanroept: wat bewaard is staat er meteen, de lezing ernaast houdt de
  markeringen bij (`maakWeergaveCache` in `lib/bronWeergave.ts`). `actueleElementen` is de ene filter op de markeringen
  in de lopende tekst.
- Geen eigen component `Wettekst`, geen `KnoopTekst`, en geen tweede weergave voor de annotatie (ontdubbelen PR 4):
  `AnnotatieTekst` is `WettekstBlok` met de **markeerlaag** (`laag`: de ene gekozen markering, de ongedekte zinsdelen, zelf
  selecteren), dezelfde tekst als het leesvenster. De rekenkern van die laag staat in `lib/markeerlaag.ts`.

**Eén ingang, één venster, één Vraag Lex** (ontdubbelen PR 1–5, besluit gebruiker 10 nov 2026, naar het voorbeeld van
Claude: een citaat in de tekst, één kaart per object, en het object opent in één paneel):
- **Eén ingang per bron** (`app/ingangen.test.ts`): onder een antwoord per bepaling één kaart (`BepalingChips`,
  `kaartenVan`), inline citaten (`Vindplaats`, `CitatieChip`) openen dezelfde tab, en elke opener gaat via `useOpenBron`.
  Er is geen tweede kaart voor de graaf.
- **Eén venster** (`app/wettekst.test.ts`): een bepaling is één tab met Tekst | Graaf (`WeergaveBalk`, `BronGraaf`);
  annoteren is een laag op die tab (*Beoordelen*), met dezelfde wettekst (`WettekstBlok` met `laag`).
- **Eén Vraag Lex** (`app/vraagLex.test.ts`): `VraagLexKnop` met een onderwerp, de suggesties uit één register per soort
  (`lib/vraagLex.ts`).

**De graaf van een bron** (ontdubbelen PR 1): één `useBronGraaf` + `BronGraaf` (`components/wettekst/BronGraaf.tsx`) voor
het venster naast het gesprek, de bronpagina en de annotatie, met één keuze Tekst | Graaf (`WeergaveBalk`). Alleen de tab
Samenhang van een werkgebied (begrippen als toevoeging) roept `useGraafStand` nog zelf aan.

### Vormgeving (Rijkshuisstijl, Belastingdienst-stijlvak)

- **Tokens, geen hex-waarden.** Kleur en typografie lopen via CSS-variabelen in `app/globals.css` →
  Tailwind in `tailwind.config.ts` (en `lib/jas.ts` voor de JAS-badges). De JAS-klassekleuren komen exact uit
  `docs/wetsanalyse/wa-table.png`. Uitzondering: `app/global-error.tsx` gebruikt inline stijl met
  vaste huisstijlkleuren, omdat die boundary de hele documentboom vervangt en de app-CSS niet kan
  veronderstellen.
- **Het beeldmerk van Lex** (besluit gebruiker 7 nov 2026, richting *Markering*): drie regels wettekst, in de
  middelste één fragment gemarkeerd. Het is het logo van de applicatie en vervangt het Belastingdienst-logo op
  elke plek (besluit gebruiker 7 nov 2026); geen wapen, lint of ander overheidsbeeld. `LexLogo` (in `components/ui/LexMerk.tsx`;
  merk + "Lex" + "Juridische analyse met AI") staat in de sidebar (`compact`) en boven `AuthFrame` (`groot`).
  - **Eén bron**: `merk/lex-merk.svg` (raster van 32 met even maten, zodat het op 16 px op hele pixels valt) en
    `merk/lex-merk-mono.svg` (currentColor, voor print en getinte standen). `npm run iconen`
    (`scripts/genereer-iconen.mjs`, sharp) maakt er `app/icon.svg` (met een donkere stand via
    `prefers-color-scheme`), `app/favicon.ico` (16/32/48), `app/apple-icon.png` (180, opaak) en
    `public/icons/` (192, 512, maskable met de veilige zone) van. Next zet de `<link>`-tags; `app/manifest.ts`
    is het manifest. Wijzig de bron en draai het script, nooit de uitvoer.
  - **In de app** is het `components/ui/LexMerk` (decoratief, `aria-hidden`), met kleuren uit de merktokens
    `--merk-vlak`, `--merk-vorm` en `--merk-markering` in `globals.css`. De donkere stand ligt klaar achter
    `data-theme="dark"`: de tegel vervalt, de regels worden licht, het geel blijft. Het geel is een merkkleur en
    geen statuskleur: niet op knoppen of labels.
  - `app/iconen.test.ts` bewaakt de formaten, de veilige zone, SVG's zonder font of beeld, één themakleur
    (`--lint`), dat component en bron dezelfde rechthoeken tekenen, en dat het Rijkswapen en het
    Belastingdienst-logo niet terugkomen.
- **De root-font-size is overal 100%.** Schaal met de Tailwind-tekstklassen, niet met een globale
  krimp.
- **Primitives in `components/ui/`**: 40px-knoppen/velden die onder de `coarse:`-variant
  (`@media (pointer: coarse)`, `tailwind.config.ts`) naar 48px groeien.
- **Knoppen zijn mobile-first.** `Button`/`LinkButton` zijn breedte-neutraal (`inline-flex
  shrink-0`); actierijen lopen via `components/ui/ButtonRow.tsx` (mobiel gestapeld op volle breedte,
  vanaf `sm:` naast elkaar). Staat een knop buiten een `ButtonRow`, geef hem dan
  `className="w-full sm:w-auto"` en laat de container op mobiel stapelen (`flex flex-col …
  sm:flex-row`). *Bespreek met Lex* (`VraagLexKnop primair`) doet dat zelf. Geen vaste of `flex-wrap`-knoprijen die op een smal scherm overlopen.
- **Een paneel van de instellingen breekt op zijn eigen ruimte, niet op `sm:`** (7 nov 2026). Het staat naast de
  tabkolom, dus op een venster van 640 px is de kolom maar 325 px breed en is `sm:` al waar. Rijen lopen via
  `components/ui/SettingRow`: `SettingRow` (`veld` voor een invoerveld), `FormRij` en `FormKnoppen` (velden en knoppen op
  één regel zolang dat past) en `FormRaster` (twee kolommen of één). `app/knoppen.test.ts` bewaakt het, en
  `scripts/test-instellingen-breedte.mjs` loopt elk scherm na op 375, 640, 800 en 1280 px met lange namen.
- **Eén bedieningsstijl** (spoor I4, voor de hoofdknoppen herzien in spoor K, besluit gebruiker 27 okt 2026, en voor labels en knoppen op 5 nov 2026;
  `app/knoppen.test.ts` legt het vast):
  - **een hoofdknop heeft de vorm van *Nieuw gesprek*** (`Button`/`LinkButton`/`knopKlasse` in maat `sm`/`md`):
    een afgeronde rechthoek (`rounded-knop` op 32px, `rounded-kaart` op 40px), en als hij een vlak heeft
    (primair, tweede keuze) een zachte schaduw die bij hover dieper wordt. *Nieuw gesprek* zelf is
    `knopKlasse("secondary", "md")`. Geen handgemaakte primaire knop naast `knopKlasse`;
  - **een pil is een label, een afgeronde rechthoek is een knop** (besluit gebruiker 5 nov 2026, na een stijlblad; dit
    vervangt "een rijactie blijft een kleine pil"). In de instellingen deelt elk paneel de kop `SettingGroup`, met de
    hoofdknop rechts (`acties`), en staan de rijacties van een gebruiker in het menu ⋯. Toets een nieuwe knop of een nieuw label aan deze regels en aan
    `app/knoppen.test.ts`. Een stijlgids is voor de ontwikkeling en hoort niet in de applicatie (besluit gebruiker 5 nov 2026).
    - **Label**: `StatusLabel`, een pil met een getint vlak. De toon draagt het oordeel (groen, geel, rood); grijs is
      neutraal en lintblauw zegt waar iets over gaat. Een label heeft geen hover en is nooit een `button` of `Link`.
      Varianten:
      - `klein`: midden in een regel tekst;
      - `rekbaar`: een lange inhoud die afkapt, zoals het onderwerp boven het invoerveld;
      - `KlasseLabel`: een JAS-klasse die alleen informeert;
      - `Tag`: een technische waarde, in monospace.
      Een eigen label-pil faalt in `app/knoppen.test.ts`. Kleurtabellen zijn tonen (`DOCUMENT_STATUS_TOON`).
    - **Knop**: elke maat heeft de rechthoek van *Nieuw gesprek*: `rounded-kaart` (md), `rounded-knop` (sm) en
      `rounded-knop-xs` (xs, 6px, de rijactie, ook `KNOP_XS`). Bij hover wordt de rand lintblauw en de schaduw dieper.
    - **Icoonknop**: `IcoonKnop`/`icoonKnopKlasse`, een vierkant in dezelfde vorm (⋯, ✕). De enige ronde knop is de
      verstuurknop van het invoerveld.
    - **Kiezen**: `FilterChip`, een kleine rechthoek. Gekozen is lintblauw gevuld.
      Chips staan altijd in **`KeuzeRij`** (7 nov 2026, melding van de gebruiker op een iPhone): één regel, nooit
      wrappen; past hij niet, dan scrolt hij horizontaal, net als de tabs. Geen eigen `flex flex-wrap` om chips heen;
      `app/uitlijning.test.ts` bewaakt het.
    - **Suggestie**: `Suggestie`, de vorm van de voorbeeldvragen in de lege werkplek; `klein` boven het invoerveld.
      Meer dan één onder elkaar staat in **`SuggestieRij`** (7 nov 2026): op een telefoon elk over de volle breedte, met de
      tekst links; vanaf `sm:` gecentreerd naast elkaar. Boven het invoerveld is het één rij die zijwaarts schuift.
    - De JAS-klasse op de reviewkaart is een knop in de kleur van de klasse: een rechthoek met ▾ en een hover-rand.
    - `app/knoppen.test.ts` bewaakt het voor de hele app: een element met `focus-ring` (elke knop en link) is nooit
      `rounded-full`. Alleen de verstuurknop van het invoerveld is rond, als hoofdactie van het gesprek zoals bij Claude.
      Ook een sluitknop (✕) of icoonknop is een afgerond vierkant (`rounded-knop`). Een teller, voortgangsbalk of
      avatar mag rond blijven: die is niet klikbaar;
  - **de actierij van een overzichtskaart is `KaartActies`** (7 nov 2026): *Openen* (`knopKlasse("secondary", "sm")`)
    en `VerwijderKnop maat="sm"` als twee gelijke helften. `VerwijderKnop` deelt vorm en maat met `Button` (`knopVorm`):
    `xs` tussen de kleine gereedschappen van een paneelkop, `sm` op een kaart. `app/uitlijning.test.ts` bewaakt het;
  - **kaarten zijn één familie**: `rounded-kaart`, een lichte rand en `shadow-zacht`; klikbaar met `KLIK_KAART`
    (`components/ui/Pagina`: een lichte lift, een lintblauwe rand en `shadow-kaart` bij hover, zoals het
    artefactkaartje in het gesprek) – de tellers, de artefactkaarten en de drie overzichtskaarten;
  - **het icoon-idioom in rijen** (`components/ui/IcoonBevestig`): een prullenbak of vinkje dat bij de eerste
    klik rood *Verwijderen?* of groen *Akkoord?* toont, de tweede voert uit (een `BevestigKnop`, dus ontwapenen
    na een paar seconden, bij blur of met Escape). Voor voorbeelden, passages (*Losmaken?*), relaties en het
    akkoord op de reviewkaart. Hoofdacties blijven een knop met tekst (`VerwijderKnop` in een kop);
  - **bewerken gaat overal ter plekke** (4 nov 2026, naar het voorbeeld van Claude: een bericht aanpassen;
    `components/ui/Bewerkbaar`): *Bewerken* (`BewerkKnop`, een pil met potloodje) staat bij het blok of de rij zelf,
    de tekst wordt op dezelfde plek een invoerveld, en daaronder staat rechts *Annuleren* · *Opslaan* (`BewerkVoet`).
    Escape annuleert, Ctrl/⌘+Enter slaat op, Enter in een veld van één regel ook (`useBewerken`, `lib/bewerken.ts`);
    wat onbewaard openstaat meldt zich bij de bewaker. Geen venster om tekst te bewerken – *Gegevens bewerken* opent
    de dossierkaart met het formulier open (`GegevensFormulier`, `?bewerk=1`). Een keuze die meteen geldt (klasse,
    rol) en een selectie in een boom (*Bronnen koppelen*) vallen erbuiten. `app/knoppen.test.ts` bewaakt het;
  - **kopiëren en exporteren** heeft één bron (`ExportRegels` in `ExportKnop.tsx`, 4 nov 2026): in een paneel naast het
    gesprek staan de regels in het menu ⋯ van de paneelkop, op een pagina in de knop *Exporteren* (`ExportKnop`, in
    `KleineActies`). Bovenaan *Kopieer als Markdown* en *Download als Markdown* (`lib/artefactMarkdown.ts`: dossier, deelvraag, bronselectie, begrip,
    begrippen, annotatie – kopjes en lijsten, geen tabellen), daaronder de formaten van de soort (annotatie
    PDF/CSV/JSON/TriG, begrippen CSV/JSON/Turtle). De inhoud wordt bij de klik opgehaald; `downloadTekst` in
    `lib/api.ts` maakt het bestand;
  - **menu's** delen één rijstijl (`components/ui/Menu`: `MENU_RIJ`, `MENU_PANEEL`);
  - **Exporteren en ⋯ delen op mobiel één rij** (besluit gebruiker 6 nov 2026, `KleineActies` in
    `components/ui/Pagina`): in de kop van een pagina staan ze samen boven de hoofdknoppen, Exporteren links en ⋯
    rechts. De hoofdknoppen blijven op mobiel onder elkaar op volle breedte. Vanaf `sm:` staat alles in één rij, met ⋯
    als laatste. Een klein gereedschap krijgt geen eigen regel. `app/knoppen.test.ts` bewaakt het;
  - **het menu ⋯ is overal hetzelfde** (5 nov 2026, `components/ui/MeerMenu`):
    - plekken: werkgebied (kop), deelvraag, bron, gesprek (kop en zijbalk);
    - de knop is `MeerKnop`, een rondje met een lijn, in twee maten: `xs` in een rij (even hoog als *Bewerken*) en
      `sm` in een kop;
    - het paneel is `MENU_PANEEL`;
    - een gewone regel is `MenuKnop`, met een icoon ervoor;
    - een keuze die meteen geldt (de rol van een bron) is `MenuKeuze`, met een vinkje;
    - *Verwijderen* staat onderaan, rood, met een prullenbak (`MenuVerwijder`), en een tweede klik bevestigt. Een
      gesprek gebruikt daar `MenuKnop gevaar`, omdat het eerst archiveren aanbiedt;
    - geen losse knop in een menu, en *Bewerken* staat niet in het menu maar bij het blok;
    - `app/knoppen.test.ts` bewaakt dat het icoon ⋯ alleen in `MeerKnop` staat;
    - een `Groep` heeft geen `overflow-hidden`, want dat knipt het menu van de onderste rij af;
  - **`Select`** heeft een eigen chevron (`appearance-none`) en dezelfde maat en focus als `Input`;
  - **elk zijpaneel** heeft dezelfde kop (`components/ui/PaneelKop`; één vaste indeling sinds 8 nov 2026, melding van
    de gebruiker: de annotatiekop stond in drie rijen met twee uitlijningen). Hoogstens twee rijen, nooit wrappend:
    - rij 1: soort en titel (afgekapt), rechtsboven het kopgereedschap in vaste volgorde: ↗ *Open volledige pagina*
      (een icoonknop-link, `NaarPagina`), ⋯ (`MeerMenu sm`) en ✕ (`SluitKnop`);
    - rij 2, alleen als er iets is: de status links (`status`: een `StatusLabel`, eventueel met "revisie n") en
      hoogstens één hoofdactie rechts (`hoofdactie`, `knopKlasse("secondary", "xs")`; de annotatie: *Annotatie afronden*);
    - in het menu ⋯ (`menu`): eerst kopiëren en exporteren (`ExportRegels`), dan de zeldzame handelingen van de soort,
      onderaan rood *Verwijderen* (`MenuVerwijder`). In een paneel van 360 px passen ze niet naast de status;
    - een inhoud die zijn eigen object laadt (`WerkgebiedInhoud`, `BegripCompact`) zet zijn stand en menu in de kop met
      `usePaneelKopVulling`; de schil zet er `PaneelKopVuller` omheen. Geen kopregel in de inhoud;
    - de slots `onder` (één regel: de reeks, de versie) en `balk` (tabs en *Vergroten*) staan eronder;
    - de annotatie heeft die kop via `AnnotatieKop` (in `ArtefactInhoud`) op de tab Tekst én op de graaf, dus hij springt
      niet bij een tabwissel; de annotatiepagina `/annotaties/node` is hetzelfde paneel. Een pagina met `PaginaKop` houdt
      `KleineActies` (Exporteren en ⋯ op één rij): daar is ruimte.
    `app/paneelKop.test.ts` bewaakt het; `scripts/test-paneelkop.mjs` meet elk paneel op 375, 400, 800 en 1280 px en
    op touch (44 px). Geen paneel bouwt een eigen kop of sluitknop. Het
    `lex`-slot gebruikt alleen nog het annotatiepaneel; de werkgebiedpanelen hebben *Vraag Lex* in de kop (`vraag`, ontdubbelen PR 5).
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
  `Sectie` (kop, telling, toelichting, acties; geen rand) – met dezelfde kop als `Kaart`, `BlokKop` (7 nov 2026: de
  acties rechtsboven op elke breedte, want een kopactie is klein; een hoofdknop hoort in een `ButtonRow` eronder),
  `Lijst` + `LijstRij` (titel, meta, status
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
volledige chat-app-shell met bovenaan de klikbare testomgeving-strook (naar de disclaimer; `Teststrook`). Het
kruisje klikt hem weg voor de rest van de login (verzoek gebruiker 11 nov 2026): `localStorage` bewaart de sleutel
`<userid>:<loginAt>` die de session-callback als `loginSleutel` op de sessie zet (`lib/teststrook.ts`), dus herladen en
een tweede tab houden hem weg, en een nieuwe login of een ander account brengt hem terug zonder dat uitloggen iets hoeft
te wissen. Geen Escape: het is geen laag. De voorwaarden staan dan nog in het gebruikersmenu (*Voorwaarden
testomgeving*). Browserregressie: `scripts/test-teststrook.mjs`. Er is
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
  met soort `annotatie`, `begrippen`, `werkgebied`, `deelvraag`, `begrip`, `bronselectie` of `regels`. Elke soort heeft een chip in de thread en een paneel
  in dezelfde schil (kolom vanaf 800px, anders een sheet); er staat er één in beeld, de rest als tab ernaast (§*De artefact-werkbank*).
  - **De titel noemt het object zelf, nooit het werkgebied waar het in staat** (besluit gebruiker 7 nov 2026, `artefactKop`
    in `lib/artefact.ts`): een object met een eigen naam (bepaling, begrip, deelvraag, het werkgebied zelf) heeft die naam als
    titel en de soort klein erboven; een verzameling (`VERZAMELING`: begripsvoorstellen, bronselectie, afleidingsregels) heeft
    de soortnaam als titel en geen soortregel. De bewaarde `titel` telt bij een verzameling niet, dus een oud bericht krijgt
    vanzelf de nieuwe titel. Eén namentabel (`ARTEFACT_SOORT_LABEL`) voor chip, `PaneelKop`, de balk *laatste artefact* en het
    `aria-label`; het werkgebied staat al in `ChatKop`. Een Markdown-download heet naar zijn eigen kop (`kopVan`), die het
    werkgebied wel noemt. `app/artefactTitels.test.ts` bewaakt het.
  - **annotatie** – het `annotatie`-item met `AnnotatieChip`, dat **`NodeAnnotatiePaneel`** opent
    `AnnotatieTekst` toont de wettekst met de **letterlijke** fragmenten
    (`segmenteer` + `lib/jas.ts:jasStyle`), `ReviewQueue` de beslissingskaarten.
  - **begrippen** – het `artefact`-item met `ArtefactChip`, dat
    **`WerkgebiedArtefactPaneel`** opent: dezelfde `BegripVoorstellen` (`inklapbaar={false}`) als op de tab
    Begrippen, met een link naar het werkgebied. Het oude artefact *Gevonden bepalingen* (`bronnen`) bestaat niet
    meer: `parseArtefact` maakt er de bronselectie van dat werkgebied van (4 nov 2026); de bronverkenner is een pagina. Eén inhoud,
    twee schillen (`werkgebiedArtefactVan` in `lib/artefact.ts`). De voorstellen zijn altijd die van de
    laatste ronde; wijst de chip naar een eerdere (`ref.run_id`), dan zegt het paneel dat.
  - **begrip** (F3d) – een taak van de begrippen-agent op één begrip ("geef voorbeelden van termijn",
    *Werk het begrip volledig uit*) levert `ref: {werkgebied_id, begrip_id, kaart_run_id?, actie?}`. Een
    bericht van vóór F3d droeg dat als `begrippen` mét `begrip_id`; `parseArtefact` maakt er `begrip` van.
    Het paneel is **`BegripCompact`**, om `BegripInhoud`: dezelfde blokken als op de pagina, onder elkaar (spoor N). Je
    leest, bewerkt per blok, beoordeelt passages en accordeert hier. **Geen Lex-knoppen** – dat vraag je in het gesprek.
  - **deelvraag** (F3d) – een taak op één deelvraag (*Formuleer scherper*, *Splits*, en zoeken of dekking
    bij die deelvraag) levert `ref: {werkgebied_id, deelvraag_id}`. **`DeelvraagPaneel`** haalt
    `GET …/deelvragen/{id}` (ook een vervangen deelvraag) en toont de vraag met haar stand, de voorstellen
    van Lex die haar vervangen (`DeelvraagVoorstel` uit `Deelvragen.tsx`, met "Vervangt “…”"), de bronnen en
    begrippen, en `BronnenBijDeelvraag` (de bronselectie van die deelvraag). Overnemen
    vervangt de oude (api): na herladen zegt het paneel "vervangen door …" en opent de opvolger in hetzelfde
    paneel (`onWissel`).
  - **werkgebied** (activiteit 1) – een werkgebied dat Lex met de analist samenstelde: ref
    `{werkgebied_id}`. De chip heet *Werkgebied · bekijken* en opent hetzelfde `WerkgebiedArtefactPaneel`
    met eigen inhoud (`WerkgebiedInhoud`: status en revisie, de **`WerkgebiedSamenvatting`** en *Open het
    werkgebied*) – los van het annotatiepaneel. De samenvatting staat ook bovenaan de werkgebiedpagina
    (één component, F3a): het dossier in de volgorde van `DOSSIER_VELDEN` – aanleiding, context, doel,
    analysevraag, praktijkvoorbeeld, afbakening, een leeg veld als "Nog geen …" –, de actieve deelvragen
    met de voortgang van hun bronselectie (`useBronselectieStand`: `GET …/bronselectie` per revisie, faalt stil) en de
    bronnen met rol *analyseren*. Komt het binnen via `opgeslagen`, dan opent het
    paneel én gaat de werkplek verder in dat werkgebied (`onKiesWerkgebied`; het gesprek wordt eraan gekoppeld, de chatkop noemt het).
  - **regels** – gereserveerd voor de afleidingsregels: de kaart staat er, maar is geen knop.
  - **De versiekiezer** (deel 2 van de artefacten, `components/ui/VersieKiezer`, rekenkern `lib/artefactVersie.ts`):
    - een versie is de stand direct na een beurt van Lex (`artefact.ref.versie`, api §*Versies van artefacten*);
    - in het slot `onder` van `PaneelKop` staat ‹ *Versie n van m* › en daarachter *Nu*;
    - een chip opent zijn eigen versie; de nieuwste opent als *Nu*, live en bewerkbaar (`beginPlek`);
    - een oudere versie is alleen te lezen, met "Je bekijkt de versie van … · *Ga naar de huidige versie*". Kopiëren en
      exporteren gaan over wat je ziet;
    - het paneel toont niets zolang de kiezer nog niet koos, zodat er nooit even knoppen op een oude versie staan;
    - zonder `ref.versie` (een ouder bericht, een mislukte opname) is er geen kiezer;
    - een paneel krijgt de opname als prop `opname`: het haalt dan niets op en verbergt alles wat iets wijzigt.
      Bij elke soort: werkgebied, deelvraag, bronselectie, begrip en begrippen. De exports van het begrippenkader gaan
      over de stand van nu en staan op een oude versie uit;
    - de annotatie krijgt de opname via haar `opslag`-haak (`momentopnameOpslag`, zoals de rondleiding): ze is
      vergrendeld, zonder graaf en zonder afronden of verwijderen. Het paneel heeft twee koppen (Tekst en Graaf), dus
      de kiezer krijgt `gekozen` mee en begint na een tabwissel waar je was. `NodeDoel.versie` draagt de versie;
    - browserregressie: `scripts/test-artefacten.mjs`.
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
    (`bibliotheek`). Zelfde schil (kolom vanaf 800px, anders een sheet) en hoogstens één paneel: een
    artefact of annotatie sluit de context, een context sluit die (`ctx` in `WerkplekClient`, bijgesteld in de
    render). Ingangen: *Openen* op de bronkaart van een citatie-chip (via `useOpenBron`,
    alleen in de werkplek), *Bronnen* in de chatkop (`bronnenSignaal`) en een markering of elementrij in het
    paneel zelf (`onWissel`). Een bron krijgt het werkgebied van het gesprek mee. **Om te raadplegen, niet om
    in te werken**: geen beoordelingsknoppen; elk paneel – ook het artefact- en het annotatiepaneel – heeft
    bovenaan *Open volledige pagina* (`paginaVanContext`, `paginaVan`, `nodeLink`). Weg uit de werkplek is het
    paneel weg; terug in het gesprek staan zijn tabs er weer (per browser bewaard). Browserregressie: `scripts/test-contextpaneel.mjs`.
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
    node-lagen,samenhang,graaf,knoop,bepaling,capabilities,verklaringen}` (een allowlist op het eerste padsegment), met client-helpers in `lib/annotatieNode.ts`. De lagen zijn **gedeeld**,
    niet per gebruiker; gesprekken zijn per gebruiker.

### De beurt is van de server, niet van dit tabblad

Een beurt draait als **run** bij graph-qa (`POST /api/annotatie/run` → `startRun`); de werkplek kijkt
mee (`volgRun` op `/api/annotatie/run/[id]/events`). Van gesprek wisselen, naar `/annotaties` lopen of
herladen breekt hem niet af. De beurt van een venster is **`useBeurt`** (`lib/useBeurt.ts`): één fase
(`lib/beurtFase.ts`: rust, starten, volgen, herstellen, met `stopt`), synchroon in een ref bijgehouden, zodat twee
Enters in dezelfde tick geen twee beurten starten (`claim`). Wat het scherm met een beurt doet geeft `WerkplekClient`
mee (`beurtScherm`). Regels:

- **Unmount koppelt alleen los.** De cleanup van `useBeurt` aborteert de kijker, niet de run.
  Een `AbortError` in de lus (`volgTotEinde` in `lib/beurtLus.ts`) is daarom géén einde (`losgekoppeld`): niets bewaren, het antwoord komt later.
- **Bij binnenkomst haak je weer aan** (`beurt.hervat` na de hydratatie): loopt er nog een beurt, dan
  komt hij vanaf `seq 0` terug. Alleen bij status `loopt` – een afgeronde beurt staat al in de
  gehydrateerde geschiedenis, en twee keer tonen is erger dan missen.
- **Stoppen is een verzoek** (`stopRun`), geen dichtvallende socket. De agent stopt op een nodegrens,
  dat kan tientallen seconden duren; de knop blijft daarom in de `stopt`-stand. Stoppen vóór de
  voorstellen levert er nul op, en het bericht zegt dat.
- **Een run kan onbekend zijn als je terugkomt** (opgeruimd, of een agent zonder database; op Azure staat
  het register in Postgres). `lib/lopendeRun.ts` onthoudt per gesprek
  welk run-id er liep; `standVanVorigeRun` bepaalt dan of de beurt gewoon is afgerond (het bericht met
  dat `run_id` staat in de geschiedenis) of echt verdwenen is. Alleen in dat tweede geval komt er een
  melding; zonder die controle zou elke normale afloop als "afgebroken" gemeld worden.
- **Een weggevallen verbinding is geen mislukte beurt.** Bij een deploy wordt de frontend-container
  vervangen terwijl de run doorloopt. `volgTotEinde` haakt daarom opnieuw aan – één `while`-lus per run, geen recursie – zonder
  pogingen-cap, met oplopende wachttijd (`naEenGebrokenStream`, `herstelWachttijd`: 1,5 tot 15 s). De
  uitleg staat bij `naEenGebrokenStream` in `lib/lopendeRun.ts`.
- **Alleen `done` sluit een beurt.** graph-qa eindigt elke run met precies één `done` (met `uitkomst`:
  klaar, mislukt of gestopt; `runstore.sluit_af`, en `volg` bij een afgebroken run). Een stroom die sluit
  zonder `done` is een verbroken verbinding: `verwerkSseStroom` gooit, en `volgTotEinde` haakt opnieuw aan.
- **De uitkomst staat op het bericht** (`Bericht.uitkomst`, `parseUitkomst`): een mislukte beurt toont live en
  na herladen dezelfde melding (`BeurtUitkomstBlok` in `ThreadRij`), gestopt zegt de tekst zelf.
- **Bij een 409 op `startRun`** (er loopt al een beurt op dit gesprek) haakt de client aan bij die run
  in plaats van te falen: twee gelijktijdige beurten schrijven door elkaar in het agent-geheugen.
- **De agent schrijft weg, de werkplek nooit.** graph-qa legt elke afloop vast en stuurt vlak vóór het einde
  een `opgeslagen`-event met het `annotatie_doel` (de bronnode); de client opent dan de weergave
  (`toonVastgelegdeBeurt`). Zet er geen tweede schrijfpad vanuit de browser naast: bij gedeeltelijk falen
  levert dat een tweede annotatie op, en het `run_id` van zo'n bericht houdt het echte antwoord tegen. De ene
  uitzondering is de fout als `startRun` zelf mislukt: dan is er geen run en dus geen server die kan schrijven.
  Een eigen markering van de jurist is een andere handeling (`POST elementen` in `NodeAnnotatiePaneel`). Een
  graph-qa zonder API-koppeling meldt zelf met een `error`-event dat niets is vastgelegd (`agent/beurt.py`).
- **Tokens komen hooguit één keer per frame binnen** (`frameplanner` in `lib/beurtStroom.ts`, per poging in `useBeurt`). Wat een poging ophoopt is één `StroomStand` (`stroomReducer`); elke poging begint leeg, en `afronding` beslist het einde.
- **Runs buiten het open gesprek zijn zichtbaar** (E6, `lib/runStanden.ts`, `useRunStanden` in `WorkbenchShell`): de
  sidebar toont per gesprek de stip `components/ui/GesprekStatus` (*Lex is bezig* / *Nieuw antwoord*) en de tab heet
  `Bezig · …` of, bij een antwoord in een verborgen tab, `Klaar · …` (`lib/tabTitel.ts`). Bron: `GET
  /api/annotatie/run?actief=1` (graph-qa `/v1/runs?actief=true`). Peilen bij laden, focus, zichtbaar worden en
  `verversSignaal`; elke 5 s alleen zolang er een spoor is (`wa_lopende_run`, of een run die nog liep). Het register
  `wa_runs_gezien` staat in `localStorage` (try/catch); een run in het open gesprek telt als gezien. Geen
  browsermeldingen. Browserregressie: `scripts/test-runstanden.mjs`.

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
stand kwam.

**Eén spoor per beurt** (9 nov 2026). Er is geen tweede blok met de toolaanroepen ("Graaf geraadpleegd · N
aanroepen": toolnamen, ruwe JSON en milliseconden, en "graaf" ook bij een Kamerstuk). Wat de jurist eruit nodig heeft,
zet graph-qa als regel in het denkproces, met de bron als actor uit één register (`agent/spoorbronnen.py`, ook voor elke
connector): "Kamerstukken · 16 gevonden", "Begrippen · niets gevonden", "Kamerstukken · kst-33755-3 deels gelezen, er
is meer dan dit", "Wetgeving · niet bereikbaar". Het `tool_execution`-event en `Bericht.tool_executions` blijven voor
eval en audit; de werkplek leest ze niet. `app/eenSpoor.test.ts` bewaakt dat het tweede blok niet terugkomt.

### Commando's in het invoerveld (`/`)

Een `/` als eerste teken in het invoerveld opent een menu met wat Lex hier kan (`lib/commandos.ts`, `CommandoMenu`).
Het is een versneller naast de suggesties, geen vervanging, en **geen tweede router**:

- **Een commando ís een suggestie.** Een regel in `SUGGESTIES` (`lib/vraagLex.ts`) met `commando: {naam, hulp}` is ook
  `/naam`; welke er zijn, volgt het onderwerp of anders het werkgebied – dezelfde suggesties als de rij boven het veld,
  ook als je typt. Uitvoeren is `voerSuggestieUit`, dezelfde functie als de klik: dezelfde tekst in de thread, dezelfde
  `actie` of hetzelfde `doel`, dus zonder supervisor-aanroep bij graph-qa. Een nieuw commando is een `commando` op een
  suggestie, geen eigen lijst.
- **Clientcommando's** (`CLIENT_COMMANDOS`) zijn geen beurt en kosten geen tokens: `/nieuw` (*Nieuw gesprek*, in het
  werkgebied), `/bron <naam>` (een bron naast de wet om, via `kiesConnector`; de namen uit het connectormenu, alleen wat
  aan te zetten is), `/context` (de contextweergave naast het gesprek, zie hieronder) en `/help` (de hele lijst). Geen `/compact`: de historie is al begrensd en wordt gecachet gelezen
  (sessie contextbeheer, 12 nov 2026), dus samenvatten levert bijna geen tokens op.
- **De catalogus (ADR-014)**: een suggestiecommando wijst naar een actie uit graph-qa (`ACTIE_TAAK` en de andere
  actielijsten), en die actie is een ingang van een `Onderdeel`. Er komt dus geen eigen lijst van wat Lex kan. Vanaf
  C1 toetst een drift-test dat elke actie van een commando een ingang van een onderdeel is.
- **Toetsen**: ↑/↓ kiest, Tab vult aan, Enter voert uit (een commando met een argument vult eerst aan), Escape sluit het menu
  en laat de tekst staan. Geen treffer: het menu zegt dat en Enter verstuurt de tekst als vraag. `/` is tekst, geen
  sneltoets: niets reageert op `/` buiten het veld (`app/commandos.test.ts`).
- **Toegankelijk**: zolang het menu openstaat is het veld een combobox (`aria-expanded`, `aria-controls`,
  `aria-activedescendant`) met een listbox; de focus blijft in het veld en een `aria-live`-regel telt de treffers.
  Daarbuiten is het een gewoon tekstveld. Op een telefoon zijn de regels 44 px en voert een tik uit.
- **Eén regel per commando**, zoals het slash-menu van Claude: de naam, dan de hulp die afkapt (voluit in de tooltip);
  waarom een commando nu niet kan, staat apart aan het eind en kapt nooit af.
- Tijdens een beurt of zonder budget staat een suggestiecommando er met de reden, en doet Enter niets.
- Tests: `lib/commandos.test.ts` (register, context, menu), `app/commandos.test.ts` (één ingang) en
  `scripts/test-commandos.mjs`.

### De contextweergave: de meter en `/context` (plan contextweergave, ADR-015)

Wat `/context` in Claude Code laat zien, voor Lex: hoe het verzoek aan het model is opgebouwd en wat de beurt kostte. Eén
component (`components/werkplek/Contextweergave.tsx`) met twee ingangen, rekenkern in `lib/contextweergave.ts`.

- **Twee getallen, elk met een eigen naam.** *Context* is het laatste verzoek van een agent (zoveel van het venster);
  *Verbruik van deze beurt* is alles wat de beurt las en schreef, over alle rondes, zoals het budget het telt. Zet ze nooit
  onder één kop.
- **De werkplek telt zelf niets.** Ze leest `contextopbouw` (graph-qa `agent/contextopbouw.py`): op het bericht
  (`Bericht.contextopbouw`, na herladen) en op het `meting`-event vlak vóór `done` (`onContextopbouw`, live).
  `parseContextopbouw` is tolerant: een vorm die niet past is "nog niet gemeten", nooit een fout. De beurten staan in
  `WerkplekClient` (`contextBeurten`), buiten de thread-items: een item wisselt van soort, de meting hoort bij de run.
- **Eén register van categorieën** (`lib/contextdelen.ts`: id, label, uitleg, kleur, volgorde), gelijk aan graph-qa
  `agent/contextdelen.py`; `contextdelen.test.ts` leest die bron, ook voor de namen van de rollen (`rolLabel`). Een id dat
  de werkplek niet kent, telt als *Overig*. Blauw in stappen is het vaste deel, de rest wat per beurt verandert; kleur
  draagt nooit alleen, de legenda noemt elk deel met zijn omvang.
- **De contextmeter** (`ContextMeter`, rechts in de rij boven het invoerveld, naast *Bronnen en tools*): `31k · 3,1%` met
  `components/ui/Meter`. Een stip (met de tekst in de toegankelijke naam) bij een signaal: de historie is ingekort, er
  vielen beurten weg, of de beurt begon koud. De tooltip noemt de drie grootste delen en het verbruik. Een klik opent het
  paneel. Zonder meting: "nog niet gemeten".
- **Het paneel** is een soort van `ContextPaneel` (`contextopbouw`, één tab, zonder pagina): de beurtkiezer, per agent de
  regel, het raster (`VAKJES` vakjes, 100% = het verzoek, niet het venster), de legenda met `≈` en bij de historie de
  grens, en hoe de beurt begon; dan het verbruik, de adviezen, de details per aanroep (ingeklapt), de deelgesprekken en
  het verloop. De inhoud komt uit `ContextopbouwContext`, niet uit het doel: de tab wordt bewaard, de meting niet.
- **De boom** komt van `GET /api/gesprekken/{id}/contextopbouw` (`haalContextBoom`): per deelgesprek een rij met zijn
  context en verbruik, die dezelfde kaart opent. Een kind hoort bij de beurt die het startte (`ouder_run_id`); een kind
  zonder meting staat bij de laatste beurt als *niet gemeten*, en het totaal zegt dan "minstens". Ook een kind waarvan de
  ouder geen gemeten beurt van dit gesprek is, staat bij de laatste beurt: een regie gebruikt zelf geen model, en de
  beurten van een reeks dragen geen ouder. Heeft het gesprek zelf geen meting (een regiegesprek), dan staan de
  deelgesprekken er op zichzelf; de kaart van een kind toont elke beurt. Heeft een agent een
  profiel (`profiel_id`, `profiel_versie` per agent, ADR-016), dan staat het bij zijn context en in de rij (`profielTekst`).
- **De adviezen zijn vaste regels** (`adviezen`), zonder model, over deze en de vorige beurt. De cache is van iedereen
  met hetzelfde vaste deel: de tekst zegt nooit "jij was een uur stil".
- **Een weergave, geen artefact**: geen besluit, geen knop die Lex start, geen *Vraag Lex*. Het advies "begin een nieuw
  gesprek" noemt `/nieuw`.
- Tests: `lib/contextweergave.test.ts`, `lib/contextdelen.test.ts` en `scripts/test-contextweergave.mjs` (met
  `CONTEXT_SCREENSHOT=<map>` een beeld van het paneel).

### Bronnen en tools boven het invoerveld (ADR-013)

`ConnectorsMenu` (rekenkern `lib/connectorsMenu.ts`) staat boven het invoerveld zodra de beheerder een bronconnector
aanzette (`GET /api/connectors` → api `/v1/connectors`). De knop noemt *Wetgeving · Kamerstukken …* met een vinkje, *uit*,
of een geel `StatusLabel` *onbekend* / *niet beschikbaar* (een icoon, geen teken: dat valt buiten het font); het menu zet
per connector aan of uit (`MenuKeuze`), en in een werkgebied *Maak dit de standaard van het werkgebied*.

- **Nooit stil weg** (melding gebruiker 9 nov 2026: het menu ontbrak soms bij het openen van een gesprek). De lijst is
  van het venster, niet van de mount (`lib/connectorLijst.ts`, hook `useConnectorLijst`): `WorkbenchShell` mount de
  werkplek opnieuw bij elk gesprek (`mountKey`), en een eigen state begon dan leeg tot de BFF antwoordde – bij een koude
  graph-qa seconden lang. Nu toont een nieuwe mount meteen de laatst bekende stand en ververst hij op de achtergrond
  (één verzoek tegelijk). Mislukt het ophalen, dan blijft het menu staan (`laden: "mislukt"`, `toonMenu`) met de laatst
  bekende stand, of alleen Wetgeving, en een `Melding` met *Opnieuw proberen* (`menuMelding`).
- **De teksten in het menu volgen `docs/schrijfrichtlijn-lex.md`** (verzoek gebruiker 9 nov 2026): je-vorm, gewone taal,
  wat het voor de jurist betekent, geen beheer- of systeemtaal (geen beheerder, omgeving, register of connector). De
  toelichting onderaan zegt waar de stand vandaan komt: *Je koos dit voor dit gesprek.*, *Zoals ingesteld voor dit
  werkgebied.* of *Standaard: alle beschikbare bronnen staan aan.* `connectorsMenu.test.ts` toetst de meldingen.

- **De stand**: het gesprek (`Gesprek.connectors`, PATCH via `wijzigGesprek`) gaat voor het werkgebied
  (`standaard_connectors`, PATCH met de revisie), en dat voor alles wat de beheerder aanzette. Wat de beheerder niet
  aanbiedt, gaat nooit aan. Gekozen vóór er een gesprek was, wordt na het aanmaken bewaard (`connectorsTeBewaren`).
- **De beurt draagt `bronnen`** (`startRun`) alleen met een menu; zonder connector bij de beheerder beslist graph-qa.
- **Eén leesmodel, in de BFF** (`app/api/connectors/route.ts`, `metBeschikbaarheid`): het register met per connector
  `beschikbaarheid`, één van drie, generiek voor elke connector:
  - `aan`: de straat biedt hem aan; alleen dan een schakelaar;
  - `niet_aangeboden`: de beheerder zette hem aan, maar deze omgeving biedt hem niet aan. Hij staat er met "hier niet
    beschikbaar" (`data-connector-niet-aangeboden`) en een melding, gaat nooit aan en nooit mee in `bronnen`
    (incident 8 nov 2026); een opgeslagen keuze blijft bewaard;
  - `onbekend`: graph-qa was niet te lezen (3 s, `STRAAT_TIMEOUT_MS`). Zonder schakelaar en zonder *Zet … aan* (review
    ADR-013, punt 2); de beurt houdt de opgeslagen keuze (graph-qa toetst de straat zelf).

  Faalt het register, dan geeft de BFF een 503 met een reden.
- **Laden is geen oordeel** (melding gebruiker 10 nov 2026: op acceptatie stond vaak *Kamerstukken [onbekend]*, na een
  refresh goed; oorzaak: graph-qa staat op `minReplicas: 0` en start koud langer dan de time-out). Is de stand niet vast
  te stellen (een fout of `onbekend`), dan volgt in `lib/connectorLijst.ts` een korte reeks herpogingen (`HERPOGINGEN`:
  2, 4, 8 en 16 s, één reeks per venster) en staat `controleert` aan. De knop toont zo'n bron dan als `laden`: gedempt,
  zonder woord of kleur, `aria-busy` en "wordt gecontroleerd" in de naam en in het menu; geen melding, geen waarschuwing.
  Pas als de reeks op is, volgt het oordeel: `onbekend` met de melding uit `menuMelding`, of `laden: "mislukt"`. Een vaste
  stand (`niet_aangeboden`) wacht niet op de reeks. Daarna geen timer: een nieuwe reeks begint bij het openen van het
  menu, vóór en na een beurt (`verstuur`, `onBeurtKlaar`; de beurt wacht er niet op) en bij terugkomst in het venster
  (`focus`/`visibilitychange` in `useConnectorLijst`, hoogstens eens per 15 s), alleen als `moetVerversen` geldt. De
  browserregressie zet kortere wachttijden met `window.__connectorHerpogingen`.
- **De beurt werkt de stand bij**: het `bronstand`-event van graph-qa (`onBronstand`, `uitBronstand`) legt per connector
  `straat` → `niet_aangeboden`, `register_onleesbaar` → `onbekend` (en start een reeks, dus eerst `laden`) en `aan` → `aan`
  over de lijst. Uitgezet in gesprek,
  werkgebied of door de beheerder zegt niets over de omgeving.
- Het menu omzetten zet een gesprek niet bovenaan de lijst (geen `updated`).
- **Past de regel niet, dan de korte vorm** (melding gebruiker 10 nov 2026: op een telefoon liep de knop uit beeld): "Bronnen: alle 4 aan" of "3 van 4 aan" (`menuKort`), met één geel label als een bron niet beschikbaar of onbekend is, en zonder aantal zolang er gecontroleerd wordt. De knop meet het zelf tegen `[data-connectors-ruimte]` (`useTePast`), niet op een breakpoint, dus ook naast een open zijpaneel. Het menu en de toegankelijke naam blijven volledig.
- Browserregressie: `scripts/test-connectors-menu.mjs`.

### Brongetrouwheid onder en in het antwoord

- **`Brongetrouwheid`** (`ThreadRij`) leest het `grounding`-event. Het zwijgt bij
  `niveau: "gegrond"` – een groen vinkje bij elk antwoord leert mensen erover heen te kijken – en
  spreekt bij **ongegrond** (een verwijzing die niet uit de graaf kwam, of een citaat dat niet
  letterlijk in de opgehaalde tekst staat) en **onbepaald** (geen vindplaats en geen citaat, dus niets
  te controleren). Onbepaald is geen goedkeuring; toon het niet groen. Het oordeel staat op het bericht
  (`Bericht.grounding`, `parseGrounding`), dus blok en aanwijzing in de tekst blijven na herladen staan. Het blok
  spreekt ook bij `afgekapt`, zelfs als het niveau `gegrond` is: wat er staat klopt dan, maar het is niet af.
  `onbevestigd` noemt wat Lex noemde maar niet is teruggevonden (een artikel in gewone taal, een blokcitaat): een
  signaal bij niveau `onbepaald`, geen afkeuring.
- **Een afgekeurd citaat wordt in de tekst zelf aangewezen.** `Markdown` neemt `nietLetterlijk` aan
  en wikkelt elke treffer in een `<mark>` (aandacht-geel, stippellijn en een `sr-only`-toelichting,
  zodat het signaal niet alleen aan kleur hangt). Dat is een **rehype-plugin op de hast-boom**, niet
  op de bron-markdown: er komt geen teken in de tekst die de jurist zou meekopiëren. Matchen gaat
  letterlijk – wijkt de weergave af van wat de controle vergeleek, dan markeer je liever niets dan
  het verkeerde stuk. Logica in `lib/markering.ts`.

### Het antwoord als sjabloon

Een begripsvraag komt als `antwoord`-event binnen vóór de `token` en staat op het bericht (`Bericht.antwoord`,
`parseAntwoord` in `lib/antwoord.ts`, de spiegel van `bronmodel/antwoord.py`; ADR-008). **`components/antwoord/Antwoord.tsx`**
tekent de blokken: elk soort één functie in `BLOKKEN`, dus een nieuw soort zonder component compileert niet. **Geen kaart, geen
achtergrond, geen rand**: een sjabloon is een vorm van antwoorden, geen artefact (`app/knoppen.test.ts` bewaakt het). Wat Lex schreef
staat onder een eigen kop. Het blok `extern` (een bron naast de wet) deelt zijn passages in met `externGroepen` (`lib/antwoord.ts`):
een alinea als citaat, een voetnoot klein met een link naar het stuk waar ze naar verwijst (`verwijst_naar`, via `bronHref`), en
een tabel als `<table>` met de kolomkoppen van de tabelpassage en per tabelrij de `cellen`, scrollend in een eigen vak. Een ongeldig blok geeft geen sjabloon en dan is `tekst` het antwoord, net als bij vrije tekst. Heeft het sjabloon doelen, dan staat er geen
bronnenlijst bij: de blokken noemen elke vindplaats (`Vindplaats`: een klik opent de bepaling naast het gesprek).

**Detail bij een antwoord** (ADR-008, aanvulling 7 nov 2026). Onder het antwoord staat per bepaling een chip
(`components/antwoord/BepalingChip`, de vorm van de annotatiechip; `bepalingenVan` in `lib/antwoord.ts`: de doelen, of bij
`annotaties` de `bron_iri` van de markeringen). Die opent de context `bron`, en daar toont `BepalingFeiten` onder de wettekst wat
de graaf verder weet (`GET bepaling`, `lib/bepalingDetail.ts` met een drifttest op `api/app/bepaling_graaf_contract.py`). Geen
artefactsoort: een bepaling is context, er valt niets te beoordelen. De jci die Lex las gaat mee; draagt de graaf een latere
toestand, dan zegt het paneel dat (`standMeldingen` in `lib/herkomst.ts`, getoond door `StandMelding`). Leden van één artikel staan in het blok `wettekst` onder één kop
(`groepeerWettekst`). Een antwoord met alleen `NIET_GETOETST`-blokken krijgt geen "niets te controleren".

### Het overzicht van een onderwerp

Op "welke artikelen gaan over X?" bouwt graph-qa een overzicht uit de graaf (`agent/overzicht.py`) met een
samenvatting erbij, allebei zonder model. Dit is geen sjabloon (ADR-008). Het overzicht komt als `overzicht`-event
(`parseOverzicht` in `lib/agentEvents.ts`, streng op bron-IRI's: één slechte rij en er is geen blok)
en reist mee in het bericht (`Bericht.overzicht`), ook als de werkplek het bericht zelf vastlegt.
Het staat **naast het gesprek** (besluit gebruiker 6 nov 2026, in de lijn van de bronselectie): in het gesprek de
samenvatting met een kaartje (`OverzichtKaartje`), en **`OverzichtPaneel`** in het `ContextPaneel` (`soort: "overzicht"`,
de inhoud uit het bericht, zonder pagina). Het paneel opent vanzelf vanaf 800px; daaronder met het kaartje of de balk
boven de chat. Het toont, naast de samenvatting die graph-qa uit dezelfde data schrijft, zonder model: per regeling de delen als uitklapbare rijen met **al** hun bepalingen, als knoppen die de bepaling als tab openen (het bronvenster, PR 4) (`kop`/`naam` uit de data via `deelKop` en
`bepalingNaam` – nooit een bereik; de naam zoals de bron hem geeft, ook waar de Leidraad wisselt), wat het onderwerp verder noemt met zijn
plek in de opbouw (ingeklapt; open als de regeling geen deel heeft), de wettelijke definitie met haar
`vindplaats`, het redactionele trefwoord en waarop er gezocht is (`zoekverantwoording`). **Bij een
overzicht staat er geen bronnenlijst**: het paneel linkt elke vindplaats. De kopieerknop neemt het
overzicht mee (`overzichtAlsMarkdown`). Rekenkern in `lib/overzicht.ts`.

### Citatie-chips onder en in het antwoord

Een vindplaats die Lex in gewone taal noemt ("artikel 9 lid 2", "art. 10a, derde lid") en die
**éénduidig** bij een bron van de beurt hoort, wordt een citatie-chip (`lib/citaties.ts`:
`vindVermeldingen` + `koppelVermelding`, via `bronDoel`; "onderdeel m" hoort bij de vermelding, en een
artikelbron bij "artikel 9, eerste lid" opent dat lid via `data-doel`). De rehype-plugin `markeerCitaties` wikkelt de
vermelding in een `cite` – de tekst zelf verandert niet, net als bij `markeerPassages`. Een klik
opent `CitatieChip` → een bronkaart via een portal (een `Popover` is een `div` en mag niet in een
alinea), met de wettekst (lui via `BepalingTekst`, de gedeelde weergave), een link naar wetten.overheid.nl en
*Openen* (de bepaling als tab). Geen chip bij twijfel: liever een vermelding zonder kaart dan een kaart bij de
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
erbuiten, regeling(en) (het zoekbereik), de gebeurtenis, en een samenvatting met *Werkgebied aanmaken*. Daarna gaat
Lex zelf door met de bronselectie per deelvraag: `opgeslagen.vervolg` (`parseVervolg`, `VERVOLG_TEKST`) stuurt
`WerkplekClient` één keer, alleen live, als een klik op *Bepaal de bronnen per deelvraag* zodra de werkplek in het
werkgebied staat. Het kaartje komt als
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
- **Meer dan één eigen antwoord** (`meer_tekst`, `MeerRegels`): één regel is één ding – wat, zegt het kaartje
  (`Vraagkaart.regel`: deelvraag, bepaling; `regelNamen`). Enter in een gevulde regel of *+ Nog een …* opent de
  volgende, Ctrl/⌘+Enter of *Volgende* stuurt in. Hetzelfde onderdeel staat op het compacte kaartje van de
  bronselectie; bouw geen tweede invoer voor meer dingen. Ze gaan als `teksten` mee (`antwoordActie`), lege regels niet. Na terugbladeren staat elke
  eigen deelvraag weer op een eigen regel (`beginstand`).
- **De gebeurtenis** is de laatste vraag (*Verzend*, `isLaatsteVraag`), dezelfde kaart als in de bronselectie. Een
  oud kaartje van de stap `bepalingen` (met `deel`, van vóór 4 nov 2026) blijft leesbaar in de thread.
- **De samenvatting** toont het hele dossier: aanleiding, context, doel, analysevraag, praktijkvoorbeeld, de
  deelvragen, afbakening, de regelingen en de gebeurtenis – geen bronnen: die kies je per deelvraag in de
  bronselectie.
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

### De bronselectie per deelvraag (spoor J)

Dezelfde dock en Vragen-kaart dragen de bronselectie (`Vraagkaart.modus: "bronselectie"`, graph-qa
`agent/bronselectie.py`; zie `docs/architectuur/bronselectie-per-deelvraag.md`). Het kaartje noemt zijn deelvraag
(`deelvraag_id`, ook op de klik en op `intake_antwoord`); "n van N" is de deelvraag van het totaal; elk kaartje
heeft *Verzend* (`isLaatsteVraag`), want wat erna komt hangt af van het antwoord.

- **De stand staat bij de api** (`GET …/bronselectie`, `lib/bronselectie.ts`), niet in de werkplek. Eén inhoud op
  drie plekken (spoor L): de tab Bronnen, de deelvraagpagina (`deelvraagId`) en het paneel naast het gesprek
  (`inGesprek`: de deelvraag van het gesprek volledig, de andere als kop met *Ga verder met deelvraag n*) –
  **`BronnenBijDeelvraag`**. Het artefact Bronselectie ís de tab Bronnen (`artefactPad` en de route sturen erheen).
  Per
  deelvraag de voortgang (`VOORTGANG_LABEL`, groen alleen bij *beoordeeld*, geel bij *opnieuw bekijken*), de
  bronnen met hun rol bij díé deelvraag, de voorstellen met hun stand, de zoekvraag waar ze bij horen (`zoekvraagZin`,
  "zoekvraag a · bestaansrecht", uit `bewijs[].detail.zoekvraag`) en het soort bewijs (`BEWIJS_LABEL`), de
  onderzoekspunten, de zoekbeperkingen en de slotzin (`slotZin`: nooit "volledig"). De volgorde is die van het werk (`ordenVoorstellen`): eerst wat op een besluit wacht, dan
  wat uitgesloten is; wat je in een eerdere stap niet koos staat ingeklapt onder *Niet gekozen (n)*, zodat de rijen die om een
  besluit vragen dezelfde zijn als die op het kaartje. Per voorstel opnemen,
  uitsluiten met reden of heropenen (`besluitBronselectie`); de stappen zet Lex. In het menu ⋯ van een voorstel staan
  *Opnemen met reden…* en, bij een artikel, *Een lid opnemen…* (WA TRM H1, 8 nov 2026): de leden komen lui uit de samenhang
  (`ledenVan`), en het besluit draagt `bron_iri`; een deel dat is opgenomen staat in de regel ("opgenomen: Lid 2"). **Geen *later***: wat je op het
  kaartje niet aanvinkt, is *niet gekozen*; iets toevoegen doe je door de vragen opnieuw te doorlopen, of door
  een bepaling in het tekstveld van het kaartje te typen.
- **Het kaartje van de bepalingen is compact, het paneel beslist** (3 nov 2026, het artefactpatroon van Claude):
  bij `weergave: "paneel"` toont de werkplek `BronselectieKaart` in plaats van `VraagDock`. Die toont de telling (live,
  via `paneelTelling` en het venster-event `BRONSELECTIE_GEWIJZIGD`) met *Bronnen beoordelen* (opent het paneel),
  *Klaar* (`klaarActie`) en regels om zelf bepalingen te noemen (`MeerRegels`, `typActie` met `teksten`; ze worden
  voorstellen in het paneel). In het paneel (`inGesprek`) opent een kandidaat of bron als tab
  ernaast (`GroepRij onOpen`), in plaats van naar de bronpagina te gaan; de bronselectie blijft als tab staan. Onder de actieve
  deelvraag staat *Klaar met deze deelvraag*; die stuurt de actie van het open
  kaartje (`onKlaar`/`klaarVoor` vanuit `WerkplekClient`). Browserregressie: `scripts/test-bronselectie-paneel.mjs`.
- **Een bronselectiebeurt blijft een antwoord met kaartje**: het artefact `bronselectie` maakt er geen
  artefact-item van (anders is de open vraag weg), live (`toonVastgelegdeBeurt`) en na herladen. Het paneel
  opent vanzelf alleen vanaf 800px; daaronder via de balk *laatste artefact* (`bronselectieVanKaart`).
- **De suggesties volgen de methode** (`SUGGESTIES` in `lib/vraagLex.ts`): bij het werkgebied dossier, thema,
  deelvragen, *Bepaal de bronnen per deelvraag*, annoteren, begrippen en als laatste de dekking; bij een deelvraag
  eerst scherper of splitsen, dan de bronnen, annoteren en gedekt.
- **Van deelvraag wisselen** gaat in het gesprek: *Ga verder met deelvraag n* in het paneel zet de deelvraag als
  onderwerp (`VraagLexKnop alleenInGesprek`), en de suggestie *Bepaal de bronnen bij deze deelvraag* stuurt de
  actie `bronselectie`. Kiezen van een onderwerp klapt een open vraag weg (`kiesOnderwerp`), anders staan chip en
  suggesties eronder; *Een vraag stellen ›* haalt hem terug. *Bepaal de bronnen per deelvraag* staat bij de
  werkgebiedsuggesties en gaat ook in een nieuw gesprek verder waar je was.
- De allowlist laat `bronselectie` en `bronselectie/{d}/kandidaten/{k}` door; de stand van een deelvraag zet Lex.
- **De peildatum staat boven de bronnen** (`PeildatumRegel` in `BronnenBijDeelvraag`, dus op de tab, de deelvraagpagina
  en naast het gesprek): de peildatum (standaard de aanmaakdatum), per regeling sinds wanneer de tekst in de graaf
  geldt, en geel als die pas ná de peildatum ging gelden (`toestandMeldingen`). `GET …/toestanden`, faalt stil;
  `haalToestanden` toetst de vorm.
- **De bronverkenner** (`BronKandidaten` op `bronnen/voorstellen`) blijft: alles wat Lex vond, ook zonder
  deelvraag, met het bewijs per methode; `BronnenBijDeelvraag` linkt ernaar. Kan de stand per deelvraag niet laden,
  dan toont de tab de bronnen van het werkgebied met een melding: een storing kost de indeling, niet de lijst.
- Browserregressie: `scripts/test-bronselectie.mjs` (vier deelvragen: 1 → 2, tussenvraag, via het paneel naar
  4, herladen, hervatten, een ander gesprek, de pagina).

### Een regie over deelgesprekken (ADR-012)

"Zoek per deelvraag de bronnen" (of de suggestie met de actie `regie_bronnen`/`regie_annoteren`) laat graph-qa's regisseur
het werk in het werkgebied verdelen. Lex legt eerst het plan voor: een `bevestiging` met `soort: "regie"`, `plan_id` en
`opdracht` (`parseBevestiging`: zonder geldig plan geen knop). *Start de regie (n deelgesprekken)* stuurt
`verstuur({regie})` → `startRun({actie, werkgebied_id, plan_id})`; *Annuleren* zoals bij de andere bevestigingen.

- **Deelgesprekken staan onder hun regiegesprek** in de sidebar (`metDeelgesprekken` in `lib/gesprekGroepen.ts`, op
  `ouder_id`; ingesprongen, `data-deelgesprek`). Elk is een gewoon gesprek met zijn eigen runstand (E6).
- **Live**: een `regie_taak`-event (`onRegieTaak`) ververst de lijst, zodat een deelgesprek verschijnt zodra het start.
- **Stop alles** is de stopknop van het regiegesprek: graph-qa stopt met de regierun ook zijn kinderen.
- **De bundel** is een gewoon bericht met het artefact `regie` (ref `{werkgebied_id, regie_id}`); de chip opent het
  werkgebied (`werkgebiedArtefactVan`).

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
- **Suggesties per soort** (`SUGGESTIES`, F3d): werkgebied (het dossier aanvullen, *Kies een thema* (spoor I7: `dossier_aanvullen`
  met die tekst – een vraagkaart `thema` met het voorstel van Lex aangevinkt), deelvragen voorstellen, bepalingen zoeken,
  dekking, annoteren, de bepalingen van de deelvragen annoteren, begrippen voorstellen, meedenken), deelvraag
  (zoeken, de bepalingen hierbij annoteren, gedekt?, scherper, splitsen),
  begrip (uitwerken, brondefinitie, *Schrijf de uitleg in B1* (spoor I2), voorbeelden, relaties, en *Wat is
  het betekenisverschil met …* met `invullen`: in het veld, de analist noemt het andere begrip). De B1-aandachtspunten staan in `AANDACHTSPUNT_LEX` (gelijk aan graph-qa `kaartacties.TEKST`). Bron en kandidaat hebben alleen vragen
  zonder actie (waarom deze bepaling, verwijzingen, bij welke deelvraag): die gaan met het object langs de
  supervisor naar de antwoord-worker.
- **Het dossier aanvullen** (`dossier_aanvullen`) is in `ACTIES` maar geen taak van een agent: graph-qa
  routeert het naar de vraagkaarten (`INTAKE_ACTIES`; de test leest `Actie` en `ACTIE_TAAK`). Een onderwerp
  met `veld` (van een oude link met `vraag_veld`) zet *Vul het … aan* (`VELD_ZIN`) voorop; graph-qa leest het
  veld uit die tekst, niet uit het onderwerp.
- **`VraagLexKnop`** (`components/werkplek/VraagLexKnop.tsx`): binnen de werkplek zet hij het onderwerp
  via `VraagLexContext` (`kiesOnderwerp` in `WerkplekClient`: chip, leeg veld, focus, op een smal scherm
  het paneel dicht); daarbuiten is hij een **link** naar `vraagUrl` (`/workbench?werkgebied=…&vraag=<soort>:<id>&vraag_label=…`),
  zodat de bewaker van niet-bewaarde wijzigingen hem ziet. `WorkbenchShell` leest `vraag` één keer
  (`onderwerpUitUrl`, streng op soort en id's), haalt de parameters uit de URL en geeft
  `beginOnderwerp` alleen aan het venster waarmee de pagina opende. Hij staat als *Bespreek met Lex* (`primair`)
  in de kop van een detailpagina, en als *Vraag Lex* in de kop van elk paneel naast het gesprek (`PaneelKop.vraag`:
  het bronvenster van een bepaling of stuk, de annotatie, het werkgebied, een begrip, een deelvraag), op de reviewkaart
  (een markering) en in de graafinspector (een bepaling of markering). **Dit vervangt de regel van spoor K** ("geen
  Vraag Lex naast het gesprek"; besluit gebruiker 10 nov 2026): één knop overal, en de suggesties van de soort staan
  daarna boven het invoerveld. Daar zet ook een klik op een deelvraag in de `WerkgebiedSamenvatting` haar als onderwerp
  (`VraagLexContext`, `data-deelvraag-onderwerp`), en *Ga verder met deelvraag n* in de bronselectie is een
  `VraagLexKnop` met eigen `tekst`. `annoteer=`/`meedenk=`
  bestaan niet meer (F3e): de bevestiging komt in het gesprek; `app/geenRunRoutes.test.ts` bewaakt dat.
- **Een bepaling en een stuk** (ontdubbelen PR 5): de soorten `bepaling` (`bron_iri`, werkgebied optioneel, `annotatie`
  als er een laag op ligt) en `stuk` (`connector`, `stuk_id`) maken *Vraag Lex* mogelijk buiten een werkgebied – in het
  bronvenster, op `/bronnen` en op `/annotaties/node`. De link heet `vraag=bepaling&vraag_bron=<urn:bwb:…>` of
  `vraag=stuk&vraag_connector=…&vraag_stuk=…` (streng in `onderwerpUitUrl`). graph-qa kent dezelfde soorten
  (`models.Onderwerp`) en haalt de tekst zelf met zijn tools. *Annoteer dit onderdeel* (en *… opnieuw* met
  `hergebruik`) is een suggestie met een `doel`: hij neemt de bestaande annotatieweg (`startOpties` stuurt het doel en
  geen onderwerp), geen actie. *Neem op in een werkgebied* is geen suggestie: opnemen is een besluit, en dat staat als
  *Opnemen in werkgebied* bij de pagina.
- **Eén knop** (`app/vraagLex.test.ts`): de tekst *Vraag Lex*/*Bespreek met Lex* op een knop alleen in `VraagLexKnop`,
  geen `onVraagOverBron`/`onVraagLex`/`onVraag={…}`, een vraag-URL alleen uit `vraagUrl`.
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
  zonder foreign key. Een bronnode-annotatie die intussen is verwijderd, meldt het paneel zelf
  (`verwijderd: {op}`), met een neutrale melding zonder *Opnieuw proberen*. De kaart benoemt zichzelf via **`artefact.titel`** in het berichtcontract
  (bij oude berichten `annotatie_titel`; zonder beide: "Annotatie"). Bewust geen cascade server-side: het gesprek is een verslag van
  wat er gebeurde.
- **Het laatste artefact blijft bereikbaar** via een balk boven de chat (titel · *Openen*) zodra het
  paneel dicht is, over de soorten heen (stelde Lex na een annotatie begrippen voor, dan zijn dát het
  laatste werk); afleidingsregels slaat die balk over.
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
  gebruiker 21 okt 2026): onder de kop één balk, `components/ui/OverzichtBalk` (een vaste indeling sinds 7 nov
  2026: op een telefoon de filterknoppen met tellers op één scrollende regel, het zoekveld over de volle breedte en dan
  *Door mij bewerkt* met eventueel iets extra's; vanaf `sm:` de filterknoppen links en het zoekveld rechts op één
  regel, *Door mij bewerkt* eronder), en daaronder kaarten in twee kolommen (`AnnotatieKaart`, `WerkgebiedKaart`,
  `BegripOverzichtKaart`) met de naam als link en onderaan *Openen* en *Verwijderen* in `KaartActies`
  (`components/ui/Pagina`, 7 nov 2026): twee gelijke helften op elke breedte, even hoog, nooit een knop die met
  `ml-auto` wegspringt. *Door mij bewerkt*
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
  | begrip | menu ⋯ van `BegripCompact` | menu ⋯ in de kop van `BegripPagina` | rij in `BegrippenOverzichtClient` |

  Een verwijderd werkgebied of begrip geeft een 404 met `{fout: "verwijderd", op, door}`; `verwijderdUit`
  leest die en het paneel of de pagina zegt "Dit werkgebied is verwijderd op … door …" (`data-verwijderd`).
  Een lijst haalt de rij meteen weg en zet hem bij een fout terug; een 412 laadt opnieuw. Verwijder je het
  werkgebied waarin de werkplek staat vanuit het paneel, dan verlaat de werkplek het (`onVerwijderd`).
  Een vervangen begrip heeft geen knop (verwijder de opvolger).
  **In beeld heet het altijd *verwijderen*** (spoor I5): niet weghalen, wegklikken of "haalt … weg".
  `app/verwijderenNietWeghalen.test.ts` toetst de tekst buiten commentaar in `app/`, `components/` en `lib/`;
  graph-qa heeft dezelfde toets op zijn strings (`tests/test_verwijderen_niet_weghalen.py`).
  `metSpoor` met `annotatie_verwijderen`,
  `werkgebied_verwijderen` en `begrip_verwijderen`. Archiveren bestaat niet meer.
- **Verwijderen staat in het menu ⋯ van de kop**: onderaan in het menu van `AnnotatieKop`
  (`onVerwijder`, alleen als er een laag in beeld is), als `MenuVerwijder`. Elke gebruiker mag het, ook
  op een afgeronde annotatie; de audit legt vast wie. `NodeAnnotatiePaneel.verwijder` stuurt
  `weergave/verwijder` met de revisies in beeld (412 als iemand intussen iets wijzigde) en laadt
  opnieuw. De API haalt alle lagen van de bepaling in beeld weg, ook uit de graaf; de weergave draagt
  dan `verwijderd: {op}` en het paneel zegt "Deze annotatie is verwijderd op …", ook als je hem later
  vanuit een oud gesprek opent. Lex annoteert zo'n bepaling bij een volgende vraag opnieuw.
- **Hergebruik en "opnieuw annoteren" staan bij de annotatie in het gesprek** (`HergebruikMelding`).
  Het `hergebruik`-event (`parseHergebruik`) zegt welke leden uit de laag kwamen; de melding blijft na
  herladen omdat graph-qa hem in het chatbericht zet (`Bericht.hergebruik`). *Lex opnieuw laten
  annoteren* start een run met `hergebruik: "opnieuw"` en de bronnode van de beurt (`annotatie_doel`) –
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

**Het kruisje staat altijd rechtsboven.** De kop van `ArtefactInhoud` is de vaste `PaneelKop` (`AnnotatieKop`): titel
met ↗ ⋯ ✕, daaronder de status links en *Annotatie afronden* rechts; exporteren en verwijderen staan in het menu ⋯. In één
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
  - **Vijf tabs als paden** (`PROJECT_TABS`, `projectPad` in `lib/werkgebiedPaden.ts`): Overzicht
    (`OverzichtTab`: tellers, de analyseopdracht met de analysevraag centraal, deelvragen als rijen naar hun
    pagina, de laatste gesprekken, de artefacten), Gesprekken (`GesprekkenTab`: de eigen gesprekken, een klik
    opent de werkplek), Bronnen (`BronnenRegister` om `BronnenBijDeelvraag`, spoor K/L: **één lijst, per deelvraag
    getoond** (methode 1f/1g) – per actieve deelvraag een `Groep` met haar voortgang en haar bronnen als `GroepRij`
    (bepaling als titel, regeling · rol · annotatiestand · "ook bij deelvraag n" eronder, *Geselecteerd* of
    *Context*), de voorstellen van Lex bij die deelvraag (*Ter beoordeling*) met *Opnemen* / *Uitsluiten…* /
    *Heropenen*, de onderzoekspunten, en wat bij geen deelvraag hoort onder *Zonder deelvraag*; erboven de
    afbakening als tekst, zoeken, rolfilter en *Bespreek met Lex*; rol en verwijderen
    achter ⋯), Artefacten (`ArtefactenTab`: vier kaarten,
    `artefactKaarten`) en Historie (`HistoriePagina` → `HistorieTab`: de audit als zinnen, nieuwste eerst; de vijfde
    tab sinds 3 nov 2026).
  - **Detailpagina's** (`DetailPaginas.tsx`): `artefacten/[soort]` – `dossier` (de velden, *Bewerken* in
    een venster `GegevensDialoog` – met het TOOI-thema (spoor I6: een keuzelijst per hoofdthema uit
    `lib/tooiThemas.ts`, gelijk aan de api-snapshot, en het voorstel van Lex uit `…/thema-voorstel` met
    *Overnemen*) –, het beheer van de deelvragen), `bronselectie`, `annotaties` (de
    inventaris, `ElementenTab`) en `begrippen` (`BegrippenKader` en, met `?deel=samenhang`, `SamenhangTab`; een oude link met `?begrip=` gaat
    naar de pagina van het begrip) –, `deelvragen/[did]` (`DeelvraagPaneel` op een pagina, `SplitDetail`: links de
    deelvraag met haar bronnen, rechts de analysevraag en de andere deelvragen),
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
    werkgebied hoort); verwijderen staat in het menu ⋯.
- **Elk juridisch object heeft een eigen pagina** (spoor G3; paden in `lib/werkgebiedPaden.ts`):
  - **Bepaling** `/bronnen?bron_iri=…[&werkgebied=]` (`components/bronnen/BronPagina`): de letterlijke
    wettekst met álle markeringen in hun JAS-kleur (`WettekstBlok groot`; een klik opent het element), de
    elementen als rijen, wat de kennisgraaf weet (`BepalingFeiten`, met alle gegevens uit de kennisgraaf ingeklapt via `KnoopFeiten`), de werkgebieden met deze bepaling
    (`lijstWerkgebieden({bronIri})`) en *Opnemen in werkgebied*. Met `werkgebied` gaat het kruimelpad via
    dat werkgebied en staat *Bespreek met Lex* over de bronselectie in de kop. Het bronregister linkt hierheen.
  - **JAS-element** `/annotaties/element/[id]` (`components/annotaties/ElementPagina`, `haalElementDetail`):
    het bronvoorkomen, de classificatie met *Waarom?*, en accorderen, afwijzen met een reden of heropenen
    (`beslisElement`, tegen de laagrevisie en bronstand van het element). Klasse en grens aanpassen blijft in
    de annotatie van de bepaling, waar de buren ernaast staan. De reviewkaart (*Open als pagina*) en de
    passages van een begrip (*Element*) linken hierheen.
  - **Begrip** `/werkgebieden/[id]/begrippen/[begrip]` (`BegripPagina` → `BegripInhoud`, onder `WerkgebiedProject`); het
    oude pad `/begrippen/[wg]/[id]` is een doorverwijzing.
    Een rij in het kader, het begrippenoverzicht (`kaartUrl`), de samenhangsgraaf en het paneel naast het gesprek openen hem.
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
- **Op een artefact lees, bewerk en besluit je; zoeken en maken gaat via het gesprek** (4 nov 2026, het
  artefactmodel van Claude). Een bepaling zoeken en toevoegen staat daarom niet op de tab Bronnen of in het paneel,
  maar is een suggestie (*Noem een bepaling*, actie `bepaling_toevoegen`, bij het werkgebied en een deelvraag) of
  een regel op het compacte kaartje: één bepaling per regel (`MeerRegels`), Lex zet ze als voorstel (*zelf genoemd*) in
  het paneel, en daar lees en besluit je, net als bij de voorstellen van Lex. Op de tab staat *Bespreek met
  Lex*. Bouw geen eigen zoekvenster op een artefact. Verwijderen is een `BevestigKnop` en laat de
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
  de kop van het project, en dan een suggestie of een eigen vraag (§*Eén gesprek*). Geen knop in een rij;
  naast het gesprek één *Vraag Lex* in de kop van het paneel (ontdubbelen PR 5). Op de
  pagina staan geen knoppen die Lex starten, en de werkplek start niets vanuit de URL. De pagina toont
  wat Lex opleverde en draagt de handmatige besluiten erover. Er is daardoor geen BFF-route meer die een
  run start: de vier statische routes (`deelvragen-run`, `kaart-run`, `bronnen-run`, `begrippen-run`)
  en `annoteer=`/`meedenk=` zijn weg, en `app/geenRunRoutes.test.ts` bewaakt dat ze niet terugkomen.
- **De bronverkenner** (fase A; sinds spoor J alleen om rond te kijken): `BronKandidaten` op
  `bronnen/voorstellen`, in het deelvraagpaneel en als artefact `bronnen` – zonder zoekknop, zonder vinkjes,
  actiebalk of besluiten. Kiezen gaat per deelvraag in de bronselectie; zoeken doet de bronselectie zelf (er is
  geen suggestie *Zoek bepalingen* meer). De strook toont de laatste ronde (`bronnen-runs/laatste`) en de
  kandidaten.
  - **Per kandidaat** de rol als badge (kern / afhankelijkheid / aanverwant, met uitleg) en het bewijs
    per methode in gewone woorden (`bewijsZin` in `lib/bronKandidaten.ts`: "verwezen vanuit Artikel 9,
    lid 1 (“artikel 8”) – uitzondering"). Per methode de telling en "onvolledig" als ze haar plafond
    raakte. Filters *Voorstellen* / *Uitgesloten* / *Opgenomen* (`filterVan`: met de hand opgenomen telt als
    opgenomen, een oud *later* als voorstel).
  - **Rijen per regeling** (spoor K, was een boom in H2): de kandidaten per regeling als `Groep`, in de volgorde
    van de wet (`rijenPerRegeling` over `bouwBoom`, de plek uit `usePlaatsen`), per rij de plek ("Artikel 9 · Lid
    2"), de rol en één zin bewijs (`bewijsSamenvatting`); *Bewijs* klapt het hele bewijs uit. `BronBoom` blijft
    alleen waar je kiest met vinkjes: het koppelvenster van een deelvraag en de termpagina.
  - De allowlist (`isWerkgebiedRoute`) laat alleen `kandidaten` (lezen) en `bronnen-runs/laatste|{run}` door,
    nooit een besluit op een kandidaat, een kale POST op `bronnen-runs` of `…/uitkomst|loopt|mislukt`.
  - **Werkgebied vanuit een overzicht**: onderaan `OverzichtPaneel` de knop *Maak hier een werkgebied van*
    (`WerkgebiedUitOverzicht`): naam en analysevraag vooringevuld, de bepalingen uit het overzicht
    (`bepalingenVanOverzicht`) voorgeselecteerd. Daarna staat de werkplek in dat werkgebied; wat niet
    kon worden opgenomen staat in een zichtbare melding onder de balk.
  - Browserregressie: `scripts/test-bronkandidaten.mjs`.
- **Deelvragen** (optioneel, open keuze 4; api §*Deelvragen*, graph-qa §*Lex stelt deelvragen voor*):
  `Deelvragen` bovenaan de tab Bronnen. Zonder deelvragen verandert er niets.
  - Een deelvraag hoort bij de scope: toevoegen, bewerken, verwijderen en *Bronnen koppelen* (vinkjes, één keer
    opslaan, de hele set) lopen via `muteer` met de revisie in beeld.
  - **Eén *Bewerken* voor het hele blok** (besluit gebruiker 5 nov 2026), net als de analyseopdracht erboven:
    - in rust staan de deelvragen met hun stand, zonder invoerveld;
    - in de bewerkstand is elke deelvraag een veld, met een prullenbak per regel en *+ Nog een deelvraag*. Enter in een
      gevulde regel opent een nieuwe, Ctrl/⌘+Enter slaat op, Escape annuleert;
    - verwijderen gaat met de prullenbak: de deelvraag staat dan doorgestreept met *Terugzetten*, en gaat pas bij
      *Opslaan* echt weg. Een leeggemaakte deelvraag blokkeert *Opslaan*, zodat een leeg veld nooit stil een
      bronselectie weghaalt;
    - *Opslaan* is één `muteer`: eerst verwijderen, dan wijzigen, dan toevoegen (`deelvraagStappen` in
      `lib/deelvragen.ts`). Elke stap krijgt de revisie van de vorige. Gaat een stap mis, dan laadt het werkgebied
      opnieuw;
    - de voorstellen van Lex staan erboven en blijven los beslisbaar.
  - Voorstellen en verbeteren doet de deelvragen-agent in het gesprek (*Stel deelvragen voor*, of
    *Formuleer scherper* / *Splits* via *Bespreek met Lex* op de deelvraagpagina). Een voorstel staat hier geel met
    *Overnemen* of *Afwijzen…* (reden verplicht; Lex stelt het niet opnieuw voor).
  - De stand per deelvraag is de voortgang van haar bronselectie (spoor K; `GET …/bronselectie` per revisie,
    faalt stil, via `useBronselectieStand`): *Nog niet gestart*, *In behandeling*, *Voorlopig afgerond*,
    *Beoordeeld* (groen) of *Opnieuw bekijken* (geel) – `deelvraagStand` in `lib/bronselectie.ts`, met het
    aantal bronnen (`bronnenZin`). Geen begrip: begrippen horen bij het werkgebied, niet bij een deelvraag, en
    het koppelvenster koppelt alleen bronnen (bestaande begripskoppelingen blijven staan).
  - Een kandidaat die Lex bij een deelvraag vond, zegt dat (`bewijsZin`: "gevonden bij de deelvraag …");
    opnemen koppelt hem aan die deelvraag (api).
  - De allowlist laat `deelvragen/{id}`, `deelvragen/samen` en `deelvragen/dekking` door, nooit
    `deelvragen/voorstellen` (van graph-qa).
  - Browserregressie: `scripts/test-deelvragen.mjs`.
- **Deelvragen met structuur** (spoor H3): in het dossier is een deelvraag een rij – de vraag als link naar
  haar pagina, herkomst en omvang ("7 bronnen in 3 regelingen"), de voortgang van haar bronselectie; bewerken en
  verwijderen gaan via *Bewerken* van het blok. Bronnen komen bij een deelvraag via de bronselectie, niet via een
  koppelvenster; begrippen koppel je niet aan een deelvraag (spoor K). Op de deelvraagpagina staan haar bronnen als
  rijen (`Groep`/`GroepRij`). Een bronselectie
  heet *Verwijderen uit werkgebied*. Ruwe IRI's in oudere dossiertekst toont de werkplek als hun plek
  (`metLeesbareBronnen`).
- **Opnemen vanuit een annotatie**: *Opnemen in werkgebied* in de kop van `/annotaties/node`
  (`OpnemenInWerkgebied`). Daar is geen revisie in beeld; `neemOpInWerkgebied` haalt hem op en
  probeert bij een 412 één keer opnieuw – de bedoeling hangt niet af van de rest van het werkgebied,
  en opnemen is idempotent.
- **Begrippen** (levering 2; api in `../api/CLAUDE.md` §*Begrippen*). `BegrippenKader` is de pagina van het kader, in de
  vorm van de tab Bronnen: *Te doen* (de termen die Lex voorstelt en de begrippen om te herbeoordelen), dan zoeken, de
  status, export, *Nieuw begrip* (de naam ter plekke) en de begrippen als `GroepRij`. Een rij opent de pagina van het
  begrip. **Eén begrip is één inhoud** (spoor N, ADR-006): `useBegrip`
  (`lib/useBegrip.ts`) laadt het en draagt `muteer` – dezelfde vorm als bij het werkgebied: revisie in beeld, 412 laadt
  opnieuw en zegt het, een fout met een `melding` van de api (`al_primair`, `poort`, `element_buiten_werkgebied`)
  verschijnt zoals de api hem formuleert. `BegripInhoud` toont de blokken: op de pagina via `SplitDetail` (links
  Betekenis, Voorbeelden en passages, rechts Beoordeling, Relaties en Historie), naast het gesprek onder elkaar.
  *Bewerken* staat per blok (`useBewerken`); elke bewaring is een revisie, de andere velden blijven staan, en een 412
  laat je tekst in het open blok staan. Verwijderen staat in het menu ⋯ (`BegripMenu`). De prop `context` staat er voor
  het generieke kader (ADR-006).
  - **Het begrip is het slanke begrip van NL-SBB** (spoor G5, ADR-003; slank sinds spoor I1): term (voorkeursterm,
    alternatieve termen), betekenis (definitie, uitleg in eenvoudige taal, *Toelichting* = het veld `context`,
    `skos:scopeNote`) en voorbeelden (tekst en oordeel). Er is **geen herkomstkeuze**: de api leidt de herkomst af. De
    NL-SBB-eigenschap waarop de export landt, staat alleen tijdens het bewerken klein bij de kop (`data-kaart-groep`). **Brondefinitie of
    analysebegrip** staat bij de definitie (`DefinitieAard`, `definitieAard` in `lib/begrippen.ts`): alleen
    een letterlijk overgenomen definitie is een brondefinitie; samengesteld of geformuleerd is "een
    analyse-uitkomst, geen wettelijke definitie". Het label volgt de tekst meteen, ook vóór het opslaan
    (`herkomstNaAanpassing`: een andere tekst is geformuleerd); de kop van de begripspagina en
    `BegripInhoud` tonen hetzelfde, met *Van Lex overgenomen* of *Door de analist* eronder.
    Rust de definitie op een voorstel of groep van Lex, dan staat eronder ingeklapt waarop
    (`DefinitieOnderbouwing`, uit `definitie_onderbouwing` van de api, spoor M): de fragmenten met hun
    vindplaats als link naar de bepaling, en de duiding. Op de kaart alleen zolang de tekst de bewaarde is.
  - **Voorbeelden in kleur, en alles zichtbaar** (spoor I3, `components/werkgebieden/Voorbeelden.tsx`): lezen
    gaat als rijen met een `OordeelLabel` (groen *valt eronder*, rood *valt er niet onder*, oker *twijfel*;
    `OORDEEL_TOON` in `lib/begrippen.ts` – kleur draagt het oordeel nooit alleen), in `BegripInhoud` en bij een
    voorbeeld van Lex in `KaartVoorstelKaart`. Bewerken kiest het oordeel met `OordeelKeuze`: drie pillen over
    echte keuzerondjes (`role="radiogroup"`), geen uitklaplijst. Tekstvakken op de kaart en in het paneel zijn
    `components/ui/AutoTextarea`: ze groeien mee met de inhoud, zonder uitrekgreep.
  - **Onbewaard werk meldt zich.** Elk open blok met een wijziging meldt zich via `onOnbewaard`; een wissel van begrip of
    tab vraagt dan eerst bevestiging (`OnbewaardMelding`), en herladen of sluiten vangt `beforeunload`. Een link elders
    (sidebar) en een knop die zelf navigeert vangt `useOnbewaardBewaker` (`lib/useOnbewaardBewaker.ts`: links in de
    capture-fase op `document`, knoppen via `bewaak`; `?instellingen=` opent over de pagina en telt niet).
    In de werkplek hoort de bewaker van het paneel naast het gesprek bij `WerkplekClient` (FB-05): elke wissel van dat
    paneel (een ander artefact, een annotatie of context ervoor in de plaats, opnieuw laden na een beurt) loopt door
    `wisselPaneel`; `bewaak` leest de stand van nu, dus ook een beurt die later klaar is vraagt eerst.
    `app/paneelWissel.test.ts` bewaakt dat de kale setter nergens anders staat.
  - **Het concept van de vraag** staat per gesprek in `sessionStorage` (UI-08, `lib/conceptVraag.ts`, in try/catch):
    een ander gesprek of herladen gooit een half getypte vraag niet weg; versturen wist hem.
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
  `BegripVoorstellen` bovenaan het kader (en als artefact naast het gesprek), naast zelf
  een begrip maken. Voorstellen vraag je Lex in het gesprek (*Stel begrippen voor*, de begrippen-agent);
  het toont de laatste ronde (`begrippen-runs/laatste`): wanneer, hoeveel passages en groepen, wat
  niet meeging, of ze verouderd of mislukt is – en de reviewlijst. Geen knoppen die Lex starten.
  - **De allowlist** (`isWerkgebiedRoute`) laat `groepen/*`, `begrippen-runs/laatste|{run}` en
    `…/vragen/{kid}` door, maar nooit `…/uitkomst`, `…/loopt`, `…/mislukt` of een kale POST op
    `begrippen-runs`: een run maakt graph-qa.
  - **Per term** (spoor H4; api §*Voorstellen van Lex* – akkoord). De keten maakt één groep per term per
    bepaling, dus er staan geen groepen maar **termen** (`termenVan` in `lib/begripTermen.ts`: dezelfde
    normalisatie als de api, kleine letters zonder lidwoord): één `ObjectRij` per term met omvang, "lijkt op …"
    en *Keuze voor jou*, naar de **termpagina** `artefacten/begrippen/term/<term>` (`termPad`,
    `BegripTermPagina`). Beoordeelde termen staan ingeklapt; een twijfelvraag die bij geen term meer hoort
    (`losseVragen`) staat ingeklapt onder *Losse twijfelvragen*, met *Samen*/*Apart*. Naast het gesprek
    dezelfde rijen; een rij opent de pagina.
    - **De termpagina**: de passages van alle open groepen van de term in een `BronBoom` (per passage een
      blad, `sleutel` = element-id), standaard alles aangevinkt behalve wat voor later bewaard is
      (`standaardKeuze`); *Waarom stelt Lex dit voor?* ingeklapt. Daaronder **Het begrip**: naam, de definitie
      (bij meer dan één kies je uit welke groep, of geen; aanpassen telt als `aanpassing`, `herkomstNaAanpassing`
      zegt wat het wordt), de fragmenten en aandachtspunten van een kaart van Lex, en vooraf of het een concept
      blijft (`akkoordLabel`). Onderaan de vragen naar een andere term (*Samen* met een naam, *Apart*).
    - **De actiebalk** (sticky): *Eén begrip maken (n)* → `groepen/akkoord` met de groepen van de gekozen
      passages, `element_ids` bij een deel, en `kandidaat_ids`: de twijfelvragen met beide kanten gekozen
      (`termAkkoord`); daarna naar de begripspagina, waar een concept verder wordt afgemaakt. *Koppelen aan …*
      (per `lijkt_op`), *Later* en *Heropenen*, en *Geen begrip…* met een verplichte reden (afwijzen, per hele
      groep). Een 409 `al_besloten` noemt het bestaande begrip.
    - **Geen sneltoetsen**: de oude toetsenbord-review (`BegripReview`, `j`/`k`/`a`/…) is weg.
  - Browserregressie: `scripts/test-begripvoorstellen.mjs` (het kader per term en de termpagina) en de
    termrijen in het paneel in `test-artefacten.mjs`.
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
  - **Na het meedenken**: twijfelvragen tonen alleen wat open bleef (`openVragen`), met *Advies van Lex*
    (op de termpagina, of los in het kader);
    een groep `door: "model"` zegt "samengevoegd op advies van Lex"; de definitie komt uit de kaart
    (`groepDefinitie`: letterlijk heet "Brondefinitie", anders "Definitie, samengesteld uit de bron /
    geformuleerd door Lex", met de fragmenten en de toelichting ingeklapt); de aandachtspunten in tekst
    (`AANDACHTSPUNT`, gelijk aan graph-qa `toetsen.TEKST` – `begripVoorstellen.test.ts` leest die bron).
    Bij akkoord vult de api het begrip uit de kaart.
  - De allowlist laat `verdieping` niet door, en ook `…/batches/*` of `…/verdieping` op een run niet: dat is graph-qa.
  - Browserregressie: `scripts/test-begrippen-verdieping.mjs`.
- **Lex naast de kaart** (fase E; api §*Lex naast de kaart*, graph-qa §*Lex naast de kaart*). De vier
  acties – de brondefinitie zoeken (zonder model), een scherpere definitie, het betekenisverschil, voorbeelden
  – zijn sinds F3c/F3e taken van de begrippen-agent: *Bespreek met Lex* op de begripspagina en een suggestie (*Zoek de
  brondefinitie*, *Geef voorbeelden*, *Wat is het betekenisverschil met …*, *Werk het begrip volledig
  uit*). Er staan geen Lex-knoppen boven de kaart. De rekenkern van een voorstel staat in
  `lib/kaartVoorstel.ts`.
  - **Een voorstel staat onder zijn veld** (`KaartVoorstelKaart` in `BegripInhoud`): de tekst, de herkomst (`herkomstLabel`), de fragmenten, de aandachtspunten
    (`AANDACHTSPUNT_LEX`, gelijk aan graph-qa `kaartacties.TEKST` – de test leest die bron), en
    *Overnemen · Aanpassen · Afwijzen*. Alle knoppen zijn `type="button"` en Enter in het redenveld doet
    `preventDefault`: de kaart staat ín het formulier van het begrip.
  - **Niets stil overschreven.** Overnemen staat uit zolang de kaart onbewaarde wijzigingen heeft.
    `useBegrip` laadt de voorstellen opnieuw bij elke revisie, zodat een eigen wijziging een open
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
  - **Het kader**: *Te doen* noemt de begrippen met een geraakte passage (`strookKop` in `lib/herbeoordeling.ts`), de
    rij in de lijst ook; een klik opent de pagina van het begrip. Het antwoord komt van `GET …/herbeoordelingen` en vraagt de bronboom; het faalt stil
    (`isHerbeoordelingen`; zonder antwoord staan de begrippen er gewoon).
  - **Het kader verschijnt in één keer** (`BegrippenKader`): *Te doen* staat boven de lijst, dus rijen die later binnenkomen
    duwen de lijst omlaag. Tot begrippen, groepen (`onGeladen`) en herbeoordelingen er zijn of faalden staat er één skeleton,
    hoogstens `GEDULD_MS` (2,5 s): een haperende bron mag de lijst niet verbergen. `BegripVoorstellen` wacht niet op
    `begrippen-runs/laatste` (die rekent `verouderd` en duurt seconden); `groepen` draagt de run ook, en `verouderd` komt als
    zin in de regel *Laatste voorstel*, zodat hij geen eigen regel laat verschijnen.
  - **Bij de passage** (`Herbeoordeling` in `BegripPassages`, uit `useBegrip` dat per revisie
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
- **Relaties en opvolging** (fase F2; api §*Begripsrelaties en opvolging*). `BegripRelaties` is een blok in de zijkolom;
  *Nieuwe betekenis* en *Combineren* staan in het menu ⋯ (`BegripOpvolging`, een venster met de verplichte reden).
  - **Een relatie is een zin met richting** (`relatieZin` in `lib/begripRelaties.ts`): "belastingaanslag
    omvat ook navorderingsaanslag", nooit alleen een lijn of "verwant". Bij `hierarchie` wijst de keten van
    de bredere term naar de soort, dus draait de zin om ("Y is een soort X"); ook de relaties "ter
    informatie" in *Voorstellen van Lex* gebruiken die zin (`hypotheseZin`).
  - **Voorstellen van Lex** staan geel met de passages waarop ze rusten: *Akkoord* (`legRelatieVast` met
    `voorstel_id`) of *Afwijzen* met reden. **Zelf toevoegen** vanuit dit begrip (`KEUZES`: geldt als, omvat
    ook, omvat niet, is een soort, heeft als soort, is verwant aan); `relatieInvoer` zet de richting,
    `magVastleggen` eist een toelichting bij verwant. Een relatie waarvan een kant veranderde staat geel met
    *Klopt nog*; *Verwijderen* is een `BevestigKnop`.
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
    hoofdactie. `bijKnoop` geeft *Open het begrip*.
  - **Kaart**: `NlSbbStand` in het blok Accorderen/Status (`GET …/begrippen/conformiteit`, opnieuw per
    revisie, faalt stil): "NL-SBB-conform (profiel 1.0.0)" of "Niet NL-SBB-conform: definitie ontbreekt …"
    (`conformZin`), met de meldingen uitklapbaar. Diagnostisch: accorderen volgt alleen de poort.
  - **Export**: naast CSV en JSON *Turtle (NL-SBB)* (`formaat=ttl`, alleen geaccordeerd) en *Turtle, alle
    begrippen* (`inclusief=alle`); `exporteerBegrippen` vertaalt `ttl-alle`. De allowlist laat
    `begrippen/samenhang` en `begrippen/conformiteit` al door (pad van lengte 3).
  - Browserregressie: `scripts/test-begrippengraaf.mjs`.
- **Generieke begrippen** (ADR-006; api §*Generieke begrippen*). Een begrip kan boven de werkgebieden staan (`kader:
  "generiek"`). `useBegrip` kent twee contexten: in een werkgebied of generiek; de handelingen staan in `stand.api`, zodat
  `BegripInhoud` niet hoeft te weten welke route het is.
  - **In een werkgebied** lees je het begrip en beheer je je eigen passages; *Bewerk generiek begrip* gaat naar zijn pagina.
    `GeneriekVeranderdBlok` zet toen naast nu, met *Klopt nog voor dit werkgebied* of *Opvolger overnemen*. Voorstellen van
    Lex per veld horen er niet.
  - **De eigen pagina** `/begrippen/[id]` (`BegripGeneriekPagina`, `generiekPad`): bewerken en accorderen, passages per
    werkgebied, *Gebruikt in*, relaties. Het segment heet `[wg]` omdat `app/begrippen/[wg]/[id]` (de doorverwijzing) er nog staat.
  - **Het kader**: label *Generiek* op de rij, een wijziging bij *Te doen*, *Generiek begrip gebruiken* (`GeneriekGebruiken`).
  - **Het menu ⋯**: *Generiek maken*, *Combineren met generiek begrip…* (`BegripOpvolging`), *Niet meer gebruiken*.
  - **Het overzicht**: de keuze Kader (`generiek` in `OverzichtFilters`, `kader=generiek` in de URL).
  - De BFF `app/api/begrippen/[...pad]` laat alleen `isGeneriekRoute` door, nooit `verifieer`.
  - Browserregressie: `scripts/test-generieke-begrippen.mjs`.
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
- **Tabs scrollen, alleen horizontaal.** Tabs passen niet altijd naast elkaar op een telefoon; `TabLinks` en `Tabs`
  scrollen (`TABRIJ` in `components/ui/Pagina`, tabs `whitespace-nowrap`). Een afgekapte tab is onbereikbaar, en een
  toets op horizontale scroll van de pagina ziet dat niet. `overflow-x: auto` maakt ook `overflow-y` auto: met een
  tab die met `-mb-px` over de rand stak, schoof de rij op een telefoon op en neer. Daarom `overflow-y-hidden`, de
  lijn als inset-schaduw en geen negatieve marge; `test-werkgebieden.mjs` toetst het op 390 px.
- Browserregressie: `scripts/test-werkgebieden.mjs` en `scripts/test-begrippen.mjs` (mocks die revisies,
  de poort en de primaire duiding bijhouden zoals de api; de tweede loopt de acceptatie van levering 2).

## De werkwijze van Lex (`/werkwijze`, ADR-014)

Een leesingang in de sidebar (*Werkwijze*): wat Lex kan, uit graph-qa `GET /v1/catalogus` (de BFF `app/api/catalogus`,
`agent: true`). Per concept (ADR-014 §7: kennis en methode, vaste ketens, agents, handelingen, ingangen, controles;
`CONCEPT_LABEL`) een `Groep` met `GroepRij`'s, per rij de soort als label en of er een model aan te pas komt (`ModelLabel`:
*Zonder model*, *Model in één stap*, *Model met tools*; lintblauw, geen oordeel) en *hier uit* als de straat het niet
aanbiedt. De balk is `OverzichtBalk` zonder *Door mij bewerkt* (de props zijn optioneel); concept en zoekterm staan in de
URL. De pagina van een onderdeel (`/werkwijze/<soort>/<naam>`, `OnderdeelPagina`) toont het contract (ADR-010), de stappen
van een workflow, de inhoud per soort (methodetekst, regels met hun voorbeeldzinnen, de beschrijving van een bron), de
herkomst, *Leunt op* / *Gebruikt door* en waar het in de repo staat. **De catalogus is alleen lezen**: dit is geen
ontwikkelhulpmiddel maar uitleg voor de jurist hoe een voorstel ontstaat; drift en testuitslagen horen er niet. Wat Lex
gebruikt, verandert alleen via de repo. Zelf iets maken of aanpassen gaat in de werkplaats (hieronder), als concept.
De sectie-editor van C7 (*Wijziging voorstellen* op een methodesectie, een concept-PR) staat er nog en verdwijnt uit de
frontend in B2-4; de api-route en de vlag `catalogusVoorstellen` blijven tot de promotie van B4 ze vervangt. De rekenkern en de spiegel van het bronmodel staan
in `lib/catalogus.ts` (`catalogus.test.ts` toetst de soorten tegen `bronmodel/catalogus.py`). Browserregressie:
`scripts/test-werkwijze.mjs` (`WERKWIJZE_FIXTURE` en `WERKWIJZE_SCREENSHOT` voor een controle met de echte catalogus). Op een telefoon past alles: `scripts/test-werkwijze-breedte.mjs` loopt op 375 px het overzicht, elk concept en elk
onderdeel na (zonder fixture één onderdeel per soort uit `lib/catalogus.ts` met de langste waarden, met `WERKWIJZE_FIXTURE`
de echte catalogus) en faalt als de pagina zijwaarts scrolt of iets buiten zijn kaart steekt. Een pad of id als label is
`Tag` (`components/ui/Badge`), dat binnen zijn breedte afbreekt; een `Kaart` breekt een lang woord zonder spaties af
(`overflow-wrap: anywhere`) in plaats van breder te worden.

### De werkplaats: concepten (ADR-016 deel B, stap B2)

Wat een gebruiker zelf maakt of aanpast (nu: een skill) is een **concept** met versies bij de api (`/v1/werkplaats/*`,
`api/CLAUDE.md` §*De werkplaats*). Het staat onder de werkwijze, achter de vlag `WERKPLAATS`.

- **Met de vlag uit is er niets te zien.** `haalWerkplaatsStand` geeft dan (en bij elke fout of onleesbaar antwoord)
  `UIT`; geen component tekent iets en niemand vraagt de concepten op. De andere routes bestaan dan niet (404), dus lees
  altijd eerst de stand. `scripts/test-werkplaats.mjs` legt vast dat de werkwijze dan gelijk is aan voorheen, en de
  andere browsertests draaien zonder de werkplaats.
- **Een concept is een artefact** (besluit 13 nov 2026): je leest het, bewerkt het en besluit erover op zijn eigen
  pagina, `/werkwijze/concepten/<id>` (`ConceptPagina`). Niets op die pagina start Lex; iets laten opstellen door Lex gaat
  via het gesprek en hoort niet bij deze stap. Een eigen pagina en geen paneel naast het gesprek: een skill heeft tot
  tientallen bestanden.
- **De ingangen** (`components/werkwijze/Concepten.tsx`): de groep *Concepten* bovenaan het overzicht (`ConceptenGroep`:
  mijn concepten, wat met mij gedeeld is, ingetrokken onderaan; alleen bij *Alles* en *Kennis en methode*; de zoekterm
  filtert op naam), *Nieuw concept* (alleen de naam; de api begint met de verplichte bestanden) en *Bewerken* op de
  pagina van een methode (`ConceptBewerken`: een concept met de versie die draait, `uit_image`; heb ik er al een, dan *Open
  mijn concept*). Een methode in de catalogus is een skill met dezelfde naam (`werkplaatsSoortVan`). Wie niet mag maken
  (`mag_maken`), ziet geen knop.
- **Eén stand, één functie** (`standLabel` in `lib/werkplaats.ts`, getoond door `ConceptLabels`): *Concept*, *Draait nu*,
  *Concept · loopt achter* (er draait intussen een andere versie dan waar het concept op voortbouwt), *Ingetrokken*, en
  ***Concept · nog onbekend wat er draait*** zolang de api niet weet welke versie Lex gebruikt. **Onbekend is nooit "draait
  niet"**: `parseOnderdeel` maakt de afgeleide velden dan `null`, wat de rij ook zegt. Daarnaast of de laatste versie de
  controle haalt (`geldigLabel`). Schrijf geen eigen zin over de stand.
- **De pagina van een concept**: de bestanden van de laatste versie in een vaste volgorde
  (`bestandsvolgorde`: `SKILL.md`, de wortel, dan de mappen), het gekozen bestand in de URL (`?bestand=`), en wat de
  controle vond, per bestand. Op een telefoon staan lijst en bestand onder elkaar; een lange regel of bestandsnaam breekt af.
  Versies en vergelijken volgen in B2-3; "loopt achter" met de twee verschillen in B2-4. **Er wordt niet automatisch
  samengevoegd**: de pagina toont de verschillen en laat opnieuw beginnen, en zegt vooraf wat er met de eigen
  wijzigingen gebeurt.
- **Bewerken** (B2-2, `ConceptEditor`; rekenkern in `lib/werkplaats.ts`): alleen de eigenaar, op een concept dat niet is
  ingetrokken. Anders is het dezelfde pagina om te lezen.
  - **Een gewoon tekstvak** per bestand (`AutoTextarea`, vaste letterbreedte, regels breken af), met de omvang tegen de
    grenzen van de api (`omvang`, in codepoints zoals de api telt). Een Markdown-bestand heeft *Lezen* / *Bewerken*: de
    leesweergave toont de frontmatter los boven de opgemaakte tekst (`splitsFrontmatter`).
  - **De controle draait live**: na een korte pauze gaat de hele stand naar `POST /toets` (poort 1, zonder op te slaan).
    Een antwoord op een stand die intussen veranderde, telt niet (`ronde`). De kaart *Controle* zegt dan "Wat er nu
    staat …"; zonder wijzigingen toont ze de bevindingen van de bewaarde versie. De labels in de kop gaan altijd over
    de bewaarde versie.
  - **Bestanden**: *+ Bestand*, en in het menu ⋯ van het bestand *Hernoemen* en *Verwijderen* (tweede klik). `padFout`
    zegt een pad dat de api zou weigeren meteen. Een verwijderd bestand staat onder de lijst tot er is opgeslagen.
  - **De balk onderaan** verschijnt zodra er iets gewijzigd is: wat er gewijzigd is (`wijzigingZin`), een toelichting,
    *Opslaan als versie n* en *Verwerpen* (tweede klik). Opslaan maakt een volgende versie; ook een versie die de
    controle niet haalt wordt bewaard, en de balk zegt dat.
  - **Een nieuwere versie** (een ander venster sloeg op, 409): de editor leest bij de api na welke versie er is, laat de
    tekst staan en legt de keuze voor, met wat er met de eigen wijzigingen gebeurt: opslaan als de volgende versie (de
    andere blijft bewaard), of de eigen wijzigingen verwerpen. Lees een conflict niet uit de tekst van de fout.
  - **Niet-opgeslagen werk** staat in de browser per concept en versie (`werkSleutel`, na de pauze en bij `pagehide`) en
    staat er na herladen weer, met een melding. Weggaan vraagt eerst (`beforeunload`, `useOnbewaardBewaker` met
    `OnbewaardMelding`); wie dan toch weggaat, gooit het ook uit de browser weg. Opslaan en verwerpen ruimen het op.
  - **Intrekken** staat in het menu ⋯ van de kop (tweede klik); daarna is het concept alleen te lezen.
  - Geen sneltoets met een letter, dus ook geen Ctrl+S.
- **Versies en vergelijken** (B2-3, `components/werkwijze/ConceptVersies.tsx`). Versies groeien alleen aan; hier wordt
  niets gewijzigd.
  - **`VersiesKaart`** staat onder de bestanden en de controle: de nieuwste boven, met wie, wanneer, de toelichting, of de
    versie de controle haalt en welke er draait (`actief`; `null` = onbekend, dan geen label). Meer dan acht klapt uit.
  - **Een versie lezen** staat in de URL (`?versie=n`, `versiePad`, `versieKeuze`): `VersieWeergave`, zonder tekstvak. Zonder
    `met` vergelijkt ze met haar voorganger, `met=k` met een andere versie, `met=0` zonder vergelijking. De lijst noemt per
    bestand *gewijzigd*, *nieuw* of *verwijderd* (een verwijderd bestand blijft in de lijst staan, anders is het niet te
    zien), en het eerste bestand met een verschil staat open. Wat gelezen is, wordt niet opnieuw gehaald: een versie
    verandert nooit.
  - **`components/ui/Tekstverschil`** (rekenkern `lib/tekstverschil.ts`) is de ene weergave van twee teksten naast elkaar:
    per regel wat erbij kwam (groen, +) en wat wegviel (rood, −), met een paar gelijke regels eromheen en de rest
    ingeklapt. Eén kolom, dus ook op een telefoon zonder zijwaarts scrollen. Kleur draagt het nooit alleen: het teken staat
    ervoor en een schermlezer hoort "erbij" of "weg". Twee heel lange teksten vergelijkt het grof (`MAX_CELLEN`), en zegt
    dat. Gebruik dit voor een volgende vergelijking; bouw er geen tweede naast.
  - **`components/ui/Bestandenlijst`** is de ene lijst van bestanden om er één uit te kiezen (de editor en de versieweergave).
  - ***Zet terug als concept*** (de eigenaar, op een eerdere versie) zet de bestanden van die versie klaar als wijziging op
    de laatste. Er verandert niets tot er is opgeslagen, en de melding zegt welke versie het wordt en welke blijft staan.
- **BFF**: `app/api/werkplaats/**` (stand, onderdelen, één onderdeel, één versie, een volgende versie, intrekken en de
  toets), elk met `X-User-Id` uit de sessie en de query ongewijzigd door. `PUT /v1/werkplaats/image` is van graph-qa en heeft geen BFF-route.
- **De spiegel** (`lib/werkplaats.ts`): de soorten en de naamvorm volgen `bronmodel`, de velden de api;
  `werkplaats.test.ts` leest die bronnen. De editor opent alleen wat in `IN_EDITOR` staat (nu skills; profielen in B5).
- Browserregressie: `scripts/test-werkplaats.mjs` (met `WERKPLAATS_SCREENSHOT=<map>` beelden op 1280 en 375 px). Die
  draait tegen een gemockte BFF; zolang de vlag op acceptatie uit staat, is er geen controle tegen de echte api.

## De artefact-werkbank

Vanaf **800px** (`lib/useBreedScherm.ts`) staat het artefact als **eigen kolom naast de chat**:
`Dialog`-variant **`kolom`**, zonder backdrop, `aria-modal` en focus-trap (die zou je opsluiten
terwijl de chat ernaast bereikbaar moet zijn); Escape sluit in alle varianten. Daaronder is het de
`side`-sheet (mobiel een bottom-sheet). De splitsing zit in `WerkplekClient` en niet in
`WorkbenchShell`, anders moeten `docs`/`infos` en alle handlers omhoog en weer omlaag.

**Het zijpaneel** (het bronvenster, PR 3a; `components/ui/Zijpaneel`, rekenkern `lib/zijpaneel.ts`) is die kolom: één
vaste kolom rechts, naar het voorbeeld van Claude Code.
- **De scheiding** (`role="separator"`, `data-paneel-scheiding`) versleep je tussen 320 px en 60% van de werkplek, en het
  gesprek houdt minstens 300 px. Met de focus erop doen ←/→ een stap van 16 px en Home/End de grenzen; dubbelklik zet de
  standaard (`min(34rem,46%)`) terug.
- ***Inklappen*** maakt er een strook van 40 px van (`data-paneel-ingeklapt`); de inhoud blijft gemount. Iets anders
  openen (`sleutel`) klapt hem weer uit, want een klik op een ingang moet zichtbaar iets doen.
- ***Vergroten*** legt het paneel over het gesprek; Escape verkleint eerst. Er is één *Vergroten*: in het zijpaneel leest
  de graaf `ZijpaneelContext.vergroot`, en op de graaf claimt `NodeAnnotatiePaneel` Escape (`claimEscape`), zodat zijn
  volgorde lagen → selectie → verkleinen → sluiten blijft. Op de sheet en op `/annotaties/node` houdt de graaf zijn knop.
- **Per browser bewaard** (`lib/opslag.ts`, in try/catch, na het mounten): `lex.paneel.breedte`, en
  `lex.paneel.ingeklapt`, dat alleen telt bij een herstelde inhoud (`hersteld`, de tabs per gesprek).
- In de rondleiding is het paneel `vast`: altijd uitgeklapt, niets bewaard. Browserregressie: `scripts/test-zijpaneel.mjs`.

**De tabs** (het bronvenster, PR 3b; rekenkern `lib/paneelTabs.ts`, tabrij `TabRij` in `components/ui/Tabs`).
- **Eén paneel, veel tabs.** De slots in `WerkplekClient` (`ctx`, `nodeDoel` met zijn tab, extra doelen, graaf en reeks, en
  `wgArtefact`) zijn de actieve tab; `tabStand` is de lijst ernaast. Elke wijziging van de slots werkt de lijst bij
  (`openTab`, in de render bijgesteld). Wisselen laadt een tab in de slots (`laad`), altijd via `wisselPaneel`, dus met de
  bewaker. Een inactieve tab is een beschrijving, geen gemount paneel: de wettekst staat er bij terugkomen meteen
  (`lib/useBron.ts`), een annotatie laadt opnieuw.
- **Leestabs kunnen er meer zijn** (een bepaling, een element, de bronnen, een overzicht; de sleutel is `contextSleutelVan`).
  **Een bepaling is één tab, of je haar leest of annoteert** (ontdubbelen PR 2, besluit gebruiker 10 nov 2026): de
  annotatie is een laag op de tab van die bepaling, met dezelfde sleutel (`bepalingSleutel`). *Beoordelen* in de kop
  (rij 2, `data-beoordelen`) zet hem aan in dezelfde tab, op de weergave waar je was; een ingang naar een bepaling die in
  beoordeling openstaat (`openContext`) gaat naar die tab. Er kunnen dus meer bepalingen tegelijk in beoordeling
  openstaan. Het werkgebied-artefact heeft één tab: een tweede vervangt de eerste, via de bewaker. Hoogstens `MAX_TABS`
  (8); de oudste niet-actieve valt af.
- **Sluiten** (✕ op de tab, of ✕ in de kop van wat open is) gaat via `sluitPaneelTab`: de buur wordt actief.
  **Escape verbergt** en sluit geen tab (`verbergPaneel`): breed klapt het zijpaneel in (`inklapSignaal`), op een telefoon
  gaat de sheet weg (via de bewaker, want de inhoud wordt ontkoppeld), en *Paneel · n open* (`data-paneel-terug`) haalt
  hem terug. Elk paneel krijgt daarvoor `onVerberg` (de `onEscape` van zijn `Dialog`; bij de annotatie de laatste laag van
  Escape, `onEscapeEinde`). *Vraag Lex* en een gekozen onderwerp verbergen op een telefoon de sheet in plaats van te sluiten.
- **De tabrij** staat breed in de balk van het zijpaneel en op een telefoon boven de kop van de sheet (`PaneelTabsContext`
  in `PaneelKop`). De tooltip noemt het volle label en waar de tab geopend werd (`tabLabel`, `volgendeVanuit`: "het
  gesprek", "een antwoord", "Bronnen in de chatkop", "het paneel"). De sluitknop heet *Sluit tab …*: een knop met
  "Sluiten" in de naam zou in de browsertests op de sluitknop van een paneel lijken.
- **Per gesprek bewaard** (`lex.paneel.tabs.<gesprek>`, `bewaarVorm`/`leesBewaard`, streng): alleen de beschrijvingen,
  zonder de kennisgraaf. Een nieuw gesprek begint leeg; er wordt pas bewaard zodra het gesprek een id heeft. Breed komt
  de actieve tab na herladen terug (met de bewaarde ingeklapte stand); op een telefoon staat hij klaar achter
  *Paneel · Openen*, zodat herladen niet vanzelf een sheet opent.

**Het bronvenster en de ingangen** (PR 4; `app/ingangen.test.ts`).
- **Het venster van een bepaling** is `components/wettekst/BronVenster`, in vaste blokken onder de herkomstkop:
  - de stand;
  - de wettekst;
  - de markeringen, met *Beoordelen in de annotatie*;
  - *Wat de graaf weet* (`BepalingFeiten`: plek, geldigheid, verwijzingen, tellingen, definieert). Een verwijzing opent
    als eigen tab.

  Het venster heeft twee weergaven, **Tekst | Graaf** (`WeergaveBalk` in de balk van de kop, dezelfde `TabRij` als de tabs
  van het paneel, `aria-selected`; ontdubbelen PR 1). De graaf is een weergave van het venster, geen eigen paneel en geen
  knop in de kop: `components/wettekst/BronGraaf` (`useBronGraaf` + `BronGraaf`) tekent hem, ook onder de annotatie. Zonder
  samenhang van een antwoord toont hij de ketting van de bepaling zelf ("Deze bepaling"); met (`ContextDoel.samenhang`,
  niet in de tabsleutel, bewaard zonder kennisgraaf) wat het antwoord noemt. *Bekijk in de tekst* gaat terug naar Tekst op
  dat segment (`data-segment`), *Open in het paneel* opent de andere bepaling als eigen tab op Graaf. Escape pelt op de
  graaf eerst lagen, keuze en vergroten af (`escape`), dan verbergt het paneel.
- **Eén ingang per plek** (`useOpenBron` in `ContextPaneel.tsx` is de enige opener; geen andere plek leest
  `ContextPaneelContext`):
  - **onder een antwoord per bepaling één kaart** (ontdubbelen PR 3; `BronChip`/`BepalingChips`, `kaartenVan` in
    `lib/bronnen.ts`): bij een sjabloon de bepalingen die het draagt, bij vrije tekst de bepalingen die de tekst
    éénduidig noemt (geen kaart voor een gok). Bij meer dan drie (`MAX_BEPALINGCHIPS`) staat er één kaart met de telling
    ("6 bepalingen", `data-bepaling-lijst`), die de bepalingen als lijst in het paneel opent (`ContextDoel` soort
    `bepalingen`, zoals *Bronnen* in de chatkop; melding gebruiker 10 nov 2026: de telling opende er één). Eén tab per lijst,
    dus een tweede klik opent geen tweede; per regeling een kop, een rij opent de bepaling als eigen tab met "Dit antwoord"
    op Graaf, en de tab Graaf van de lijst toont ze samen. De lijst en de bronnen van het werkgebied delen `BronRijen`.
    Er is geen tweede kaart voor de graaf: die is de tab Graaf van het venster,
    met "Dit antwoord" – elke ingang in het bericht (kaart, vindplaats, citatie) neemt de samenhang van het bericht mee
    (`BerichtSamenhangContext` in `ThreadRij`). De bronnenlijst toont alleen wat geen kaart heeft (`zonderKaarten`):
    regelingen, connectorstukken, externe bronnen. Een overzicht heeft zijn kaartje, en de overzichttab heeft zelf
    Tekst | Graaf (de hele kennisgraaf met de nadruk op het overzicht); een artikel uit die graaf opent als eigen tab;
  - de citatiekaart heeft *Openen*, zonder eigen graafknop;
  - in de bronnenlijst opent een bepaling als tab (`Vindplaats kort`; met Ctrl/⌘ de bron zelf);
  - in het overzicht en in de bronselectie naast het gesprek opent een bepaling als tab (`GroepRij onOpen`, via
    `useOpenBron`) in plaats van een eigen uitklap met de wettekst. Buiten de werkplek blijft de rij een link
    naar de bronpagina.
- **Een stuk uit een bronconnector** (PR 6, ADR-013; `app/connectorTekst.test.ts`) opent als tab (`ContextDoel` soort
  `stuk`: brontype en id, met `gelezen` en `voorbeeld` uit het antwoord). Niets in `components/` kent een connector bij naam.
  - De BFF `app/api/bronnen/[connector]/[id]` leidt door naar graph-qa `GET /v1/bronnen/{connector}/stukken/{id}`, en
    stuurt `offset` en `tabel` mee. De rekenkern staat in `lib/bronStuk.ts`, de stand per sessie in `lib/useStuk.ts`.
  - De kop komt uit de beschrijving van de connector en de metadata (`stukHerkomst`): het label, en daaronder groep ·
    soort · datum · vindplaats. `HerkomstRegel` noemt de host van de link.
  - `components/wettekst/StukVenster` heeft deze blokken:
    - stand (`stukMeldingen`: een andere versie dan Lex las, de bewaarde versie, alleen een PDF);
    - inhoud;
    - tekst per deel, met *Volgende deel laden*;
    - gegevens (`stukGegevens`, in de volgorde van de beschrijving);
    - verwijzingen uit de voetnoten (een stuk van dezelfde bron opent als tab).

    Is de bron niet te bereiken, dan toont het venster wat Lex las.
  - `components/wettekst/ConnectorTekst` tekent de rijsoorten van het contract (alinea, voetnoot, tabel met `cellen`), in
    het antwoordblok `extern` en in het venster. Wat Lex citeerde staat gemarkeerd (`data-geciteerd`).
  - In het antwoord opent het label van een stuk (in `extern` en `stukken`) de tab via `StukVindplaats`; met Ctrl/⌘ gaat
    het naar de bron. Een stuk dat alleen een PDF is, blijft een link naar de bron.
  - **Bij welke tekst een stuk hoort** (review ADR-013, 10 nov 2026). Een uitspraak bij een eerdere versie van het
    artikel heeft een geel label in de lijst ("eerdere tekst", "niet op de peildatum") en de periode in de metaregel
    (`tekstPeriode`). In het blok `extern` en in het venster staat dezelfde melding. De zinnen komen uit
    `tekstBijMeldingen` in `lib/herkomst.ts`, een eigen zin elders faalt in `app/herkomst.test.ts`. Het venster krijgt de
    stand van de lijst mee (`ContextDoel.tekst`, buiten de tabsleutel); vanuit een ander blok weet het hem niet en zegt
    het niets.
  - Browserregressie: `scripts/test-bronvenster-stuk.mjs`.
- **De bronpagina is het bronvenster als pagina** (PR 5): `BronPagina` zet `BronVenster variant="pagina"` (tekst groot,
  markeringen als rijen naar hun pagina) onder de `PaginaKop` met de herkomstregel en de meldingen over de stand
  (`useBronHerkomst`, ook de peildatum met `?werkgebied=`); de zijkolom houdt Werkgebieden en Herleidbaarheid. ↗ in het
  paneel opent deze pagina. Geen eigen tekstkaart meer (`app/wettekst.test.ts`).

Wettekst en reviewlijst hebben **elk een eigen scroll** (tekst `max-h-[45%]` bovenin), zodat de tekst
niet uit beeld loopt als je verderop in de lijst bent. Selecteren scrolt **beide kanten** in beeld:
de markering (`WettekstBlok`, markeerlaag) en de kaart (`ReviewQueue`), met respect voor
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
  (`StatusLabel`): één badgevorm in de app. Kleur
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
- **Relaties** (ADR-011, stap 4A; `components/annotaties/Relaties.tsx`, rekenkern in `lib/annotatieNodeAdapter.ts` en
  `dragerRevisies` in `lib/annotatieNode.ts`). De uitgeklapte kaart draagt het blok *Relaties* (`elementExtra` van
  `ArtefactInhoud`): een lijst, gelezen vanaf dit element (de inverse als het element `naar` is), een veranderde relatie
  bovenaan met "Een eindpunt is veranderd …", herkomst en oordeel als bij een element. Akkoord (`IcoonBevestig`), *Klopt
  nog* bij een veranderde beoordeelde, *Afwijzen* met een optionele reden, *Heropenen*, en wissen alleen van een eigen
  relatie (de userid uit de sessie). *Verbind met…* kiest uit wat in beeld is (markeringen en impliciete partijen, geen
  zoekvenster) en biedt de typen uit `typenTussen` in beide richtingen, met de zin die zegt wat van en wat naar is; een plek
  alleen bij `invoer`/`operand`. *Impliciete partijen* staat bij de bepaling (`extra`): label en verplichte toelichting.
  `verwachte_revisies` is die van de dragerlaag; ligt die niet in beeld, dan volgt een 412 en leest het paneel opnieuw.
  Bulk (*Akkoord met de groene*) neemt relaties niet mee: `beslis_laag` kent alleen elementen. Browserregressie in
  `scripts/test-annotatie-nodes.mjs`.

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
- **× betekent verwerpen of wissen**, met twee uitkomsten: een agent-voorstel klapt de redenen-chips uit (één
  klik = verworpen, terug te draaien met *Heropenen*); een eigen markering wordt "Wissen?" en is na de
  tweede klik weg (`DELETE`). Een agent-voorstel verwijder je niet maar verwerp je, zodat het
  auditspoor laat zien dát er een voorstel was.
- **Een oordeel vergrendelt de kaart.** Bij `human_approved`/`rejected` (`slotVan`; een ander
  begrip dan `isBeslist`, dat de filters en de telling stuurt) zijn klasse en toelichting alleen-lezen
  en zijn *Akkoord*, het kruisje, de alternatieven en de kanttekening-acties weg; **Heropenen**
  (`type: "heropen"`) zet het element terug in de review. Zonder vergrendeling zouden badge en
  toelichting na een akkoord stil een `edit` wegschrijven. Een **opmerking** mag wél op een vergrendeld
  element; `edited` vergrendelt niet (anders wringt er een heropening tussen klasse en toelichting);
  een **eigen markering** vergrendelt niet, want die is `human_approved` bij het aanmaken.
- **Verworpen markeringen tellen niet als "inmiddels gemarkeerd"** (`alGemarkeerd` in
  `lib/annotatie.ts`, voor de ongedekte zinsdelen uit de dekking), net zoals de markeerlaag
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
- De markeerlaag onderstreept ze gestippeld (standaard aan, *Verbergen* in de balk erboven).
  `segmentenVanBlok` knipt erop, de actieve markering gaat voor, en de segmenten blijven samen
  exact de regel. Een klik op een onderstreept zinsdeel opent dezelfde `SelectiePopover` met het
  hele deel: zelf markeren zonder de grenzen te trekken.
- `DekkingOverzicht` in de `extra`-haak toont per bronnode hoeveel dimensies volledig draaiden en
  welke niet, en per dimensie wat er gevonden werd (`aangetroffen`, `gevondenTekst` in
  `lib/dekking.ts`). Een oudere meting zonder telling toont geen regel: onbekend is geen 0. Ook het
  aantal zinsdelen dat alleen als geheel geraakt werd (`alleen_als_geheel`, bv. alleen de hele
  normzin) staat erbij: in `ongedekt` telt zo'n zin als geraakt.

### Zelf annoteren (tekstselectie)

De jurist selecteert tekst in de markeerlaag (`WettekstBlok` via `AnnotatieTekst`) en markeert die zelf. Eigen markeringen gaan via
`POST elementen` (`NodeAnnotatiePaneel.eigenMarkering`; niet de batch, dat is de uitkomst van een
agent-ronde) en zijn meteen `human_approved`.

- **Een selectie eindigt niet altijd met een muisklik.** Naast `onMouseUp` luistert de markeerlaag
  op documentniveau naar `keyup` (Shift+pijltjes, WCAG 2.1.1) en `touchend` (selectiegrepen op een
  aanraakscherm). `ArtefactInhoud.sluitSelectie` ruimt de DOM-selectie op bij het sluiten van de
  popover, anders klapt die bij de volgende tik weer open.
- **De rekenkern staat in `lib/selectie.ts`**; het component doet alleen de `TreeWalker`-wandeling
  (`offsetVanGrens`) en geeft knooplengtes door aan `offsetInBlok`.
- **Elk segment is een blok, en elk blok draagt `data-offset`** (zijn begin in de samengestelde bron, `SegmentPlek`).
  `offsetVanGrens` telt alleen binnen het blok vanaf die startpositie, zonder het nummer (`data-buiten-tekst`), zodat de
  weergave (inspringing, nummer) los staat van de offsets. **Haal `data-offset` niet weg** en zet geen tekst naast de
  segmenten – dan landt elke markering stil op de verkeerde tekst. `test-annotatie-nodes` toetst de ankers (ook emoji en
  over twee leden).
- **Een markering wordt op de blokgrens geknipt** (`segmentenVanBlok`): een `<mark>` kan niet over
  twee blokken, dus het worden twee `<mark>`s met dezelfde klasse en hetzelfde id, optisch verbonden
  door `box-decoration-clone`.
- **De structuur komt uit de graaf** (ontdubbelen PR 4): de inspringing volgt `parent_iri` van de segmenten (`diepteVan`
  in `WettekstBlok`), net als bij lezen; een los onderdeel staat op de marge, zonder lege lidregel erboven. De
  samengestelde bron (`leden_teksten`, `lib/annotatieNodeAdapter.ts`) bestaat nog voor de posities en de reviewlijst;
  `blokkenVan` (`lib/wetstructuur.ts`) wordt in geen component meer gebruikt.
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

Het menu ⋯ in de kop van het artefact (`ExportRegels` in `components/werkplek/ExportKnop.tsx`) biedt **PDF / CSV /
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

### Het werkgebied exporteren

*Exporteren* in de kop van het werkgebied (`ProjectKop`) en het menu ⋯ van het werkgebiedpaneel naast het gesprek bieden naast de
Markdown van het dossier de **PDF van het werkgebied** en **Rapport als Markdown** (`exporteerWerkgebied`, `GET …/export`). Beide
komen uit één document in de api (`api/app/werkgebied_rapport.py`, ADR-009), dus met dezelfde inhoud; *Kopieer* en *Download als
Markdown* blijven het korte dossier uit `lib/artefactMarkdown.ts`. Eén keuze (WA TRM H1, 8 nov 2026): standaard staat alleen in het
rapport wat een jurist beoordeelde; het vinkje *Met de voorstellen van Lex* (`voorstellenKeuze` op `ExportKnop`) vraagt
`inhoud=alles`. Het rapport
gaat over de stand van nu en staat daarom niet op een oude versie. De route krijgt een ruime timeout, want hij leest de bronbomen.

## De samenhangsgraaf (sigma.js)

Het venster van een bepaling (lezen én annoteren) en van een overzicht heeft naast *Tekst* een tab **Graaf**
(`components/wettekst/BronGraaf.tsx` om `components/graaf/Graaf.tsx`); de kaart van een bepaling onder een antwoord opent
het venster, en daar staat de graaf (ontdubbelen PR 1–3). Een
2D-graaf op **sigma.js v4 + graphology**: WebGL 2 (ook de labels), gebouwd om de hele kennisgraaf (~6.500
knopen, ~10.000 lijnen) vloeiend te tekenen. De overstap van v3 (okt 2026) raakte alleen `GraafTekenaar`.

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
  - **relaties tussen markeringen** (ADR-011, lijnsoort `jas_relatie`, knoopsoort `impliciet`): de laag
    *Relaties* staat standaard uit, en dan staan relaties alleen binnen de nadruk (rond de keuze, in de focus), met
    de impliciete partijen rond de keuze – de ene plek waar een keuze iets in beeld brengt. Gericht, geel bij een
    voorstel of een veranderde relatie, neutraal (`RELATIEKLEUR`) als beoordeeld, afgewezen niet (`relatieStijl`).
    Een impliciete partij is een holle knoop (wit, omtrek in haar klasse; WebGL kent geen stippelrand). **Diagrammodus**
    (deelactiviteit 2c): is de keuze een markering van een `CENTRALE_KLASSEN`, dan is de nadruk de buurt over
    relaties tot `DIAGRAM_DIEPTE` 2 (`diagramBuurt`). Relaties trekken niet in de layout; een impliciete partij staat
    bij het zwaartepunt van haar relaties (`plaatsAnnotaties`), dus `LAYOUT_VERSIE` bleef gelijk.
- **`lib/graaf/labels.ts`** – **welke knopen een label krijgen**: nooit twee over elkaar, en meer detail
  naarmate je inzoomt. Sigma's eigen labelraster toetst de breedte van een label niet en zet
  `labelVisibility: "visible"` ongetoetst bovenop; daarom staat het op nul (`labelDensity: 0`) en kiest
  `kiesLabels` per camerastand: gulzig op prioriteit (keuze > nadruk > gewoon > gedimd, dan de soort), een
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
  posities, vraagt per knoop/lijn het beeld op bij `weergave.ts` en meldt klik/achtergrond terug. Eén
  knoopvorm (cirkel + `layerBorder` van `@sigma/node-border`): omtrek = randbepaling of laag Dekking; een
  verwijzing krijgt `head: "arrow"`. Lui geladen (`next/dynamic`).
  **Het beeld staat in de attributen van de tekengraaf, niet in een reducer** (`schrijfBeeld`, bij elke
  nieuwe context en bij een zoomdrempel van `detailFactor`): de styles lezen alleen attributen en
  knoopstatus. Een reducer laat sigma 4 bij elke hover en elk begin of einde van een gebaar álle knopen
  en lijnen opnieuw doorrekenen. **De labelkeuze is een eigen knoopstatus `label`**: `kiesLabels` draait
  op elke camera-`updated` en zet alleen het verschil met `setNodesState`, dus sigma ververst alleen die
  knopen. `schrijfBeeld` houdt per knoop bij wat de keuze nodig heeft (`labelInfo`).
  **Het font staat per label** (`labelFont`, met het gewicht in de string): sigma zet anders
  "sans-serif" en negeert het font van de primitives. Sigma tekent elke letter één keer in een
  SDF-atlas, dus de tekenaar wacht (hoogstens 1 s) tot het labelfont geladen is; anders blijft het
  reservefont voorgoed staan. SDF-tekst oogt zwaarder, vandaar gewicht 400.
  Valkuilen die hier verder opgelost zijn: een `ResizeObserver` doet `resize` én `refresh`; bij unmount
  wordt het **doel** van een lopende camerabeweging bewaard, niet de tussenstand (anders staat het
  vergrote beeld halverwege een vlucht); geen WebGL 2 of contextverlies → `onFout`. Een klik of hover
  op een label telt als op zijn knoop (`nodeLabelEvents: "extend"`).
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
  **`selectie` bevat alleen ids op de kaart.** Een keuze die van de kaart verdwijnt (verworpen markering)
  vervalt.

**Data en gedrag**:

- **De ketting bij een antwoord** (`GraafOpties.keten`, `GET samenhang/antwoord`, api §*`/samenhang/antwoord`*). *Dit
  antwoord* is de weg van regeling tot de diepste bepaling die het bericht aanwijst (`antwoordDoelen` in `lib/bronnen.ts`: per
  bepaling een doel met `herkomst`, een ouder valt weg als een kind genoemd is; de tekst selecteert alleen uit de bronnen),
  met de markeringen, de begrippen die daar gelden en de uitgaande verwijzingen. Er staat niets gedimd, want de rest is niet
  geladen; `ketenZin` zegt boven de graaf wat je ziet en wat er niet bij staat. De ketting krijgt de vorm van de hele kennisgraaf:
  een rond sterrenstel, geen boom met knopen onder elkaar (`layoutSterrenstel`, besluit gebruiker 6 nov 2026). `ketenFocus` geeft de nadruk: in de hele
  kennisgraaf licht de ketting op. *Toon het hele artikel* laadt het artikel erbij (`laadErbij`); de ketting telt daarbij niet
  als geladen. Een bepaling uit een antwoord, een annotatie in het gesprek en de
  doelen van `doel` uit de werkplek gebruiken de ketting; de tab Samenhang van een werkgebied en de annotatiepagina niet.
  Een overzicht opent in de kennisgraaf met zijn eigen focus (`eigenFocus`); zijn *Dit antwoord* is de ketting van de delen
  en de definities (`overzichtDefinities`).
  Een wettelijk begrip (`begrip_bron: "wet"`) heeft een eigen kleur (`WETBEGRIPKLEUR`) en toont in de inspector zijn
  definities met vindplaats en geldingsbereik. Browserregressie: scenario 0 in `scripts/test-samenhang.mjs`; de rest van dat
  script draait op het hele artikel, zodat de bediening getoetst blijft.
- **De graaf van een antwoord opent wat het antwoord noemt** (`antwoordDoelen` in `lib/bronnen.ts`, max.
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
  *Centreren* en ✕, de wettekst met de markeringen erin in hun JAS-kleur (`WettekstBlok`; een klik op een
  span kiest die markering in de graaf), bij een markering ook toelichting, review-uitleg,
  alternatieven en de Waarom-uitklap (open), en de relaties per soort. Alleen lezen: beoordelen gebeurt
  in de tekst. De gevulde knop is er alleen voor wat in de graaf blijft (*In de graaf laden*); *Bekijk
  in de tekst* / *Beoordeel in de tekst* / *Open in het paneel* zijn rustige links. De tekst komt uit de
  weergave van het paneel, en anders één keer per knoop via `GET weergave` (`useKnoopDetail` op `haalBepalingWeergave`, cache
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
- **Buiten het paneel** draagt `Graaf` twee haken: `benaming` (`GraafContext`: hoe de doelen heten in
  de bereikschakelaar, *Terug naar …*, de focusregel en de inspector; standaard het antwoord) en
  `bijKnoop` (een extra handeling in de inspector). De uitleg over "de tekst en de annotatie in het
  paneel" staat er alleen mét `weergave`. Gebruikt door de tab Samenhang van een werkgebied.
- Browserregressie: `scripts/test-samenhang.mjs` (klikken via de canvasmidden na *Centreren*, kiezen
  en lagen via de zoeklijst, `data-selectie`/`data-bereik`/`data-gereed` op de graaf,
  `data-labels`/`data-label-soorten` op de tekenaar;
  een gegenereerde kennisgraaf van ~6.500 knopen voor laadbalk, focus, koppeling en de cache).

## Buiten de schil

Alles wat geen app-schil is – inloggen, 2FA, de eerste beheerder, registratie, de blokkerende
disclaimer en de fout-/laadpagina's – gebruikt **`components/auth/AuthFrame.tsx`**: een gecentreerde
kaart op `bg-surface` met het logo van Lex (`LexLogo`) erboven. Bewust geen vervaagde werkplek achter het inlogscherm: dat
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
  ongelezen-badge; het archief is de tab *Berichten* van het instellingenvenster. Let op de naam: `Bericht`/
  `BerichtInvoer` in `lib/types.ts` zijn **chatbeurten**, `BerichtOut` en familie zijn release notes –
  twee API-domeinen (`/v1/gesprekken/…/berichten` vs `/v1/berichten`).
- **Feedback** – `FeedbackDialoog` opent vanuit het gebruikersmenu onderin de sidebar, bewust niet als
  zwevende knop: die valt over de chat-invoer. De ongelezen-teller voor beheerders is een badge op de
  feedbacktab (`TabDef.badge`).
- Beide halen hun teller periodiek of bij openen op en falen **stil**: een badge is een hint en mag de
  werkplek niet blokkeren.
- **Rondleiding** – `components/rondleiding/` loopt langs elementen met `data-tour="<anker>"` in de
  werkplek. Stappen en teksten staan in `lib/rondleiding.ts`. **De stand hoort bij de gebruiker**: de api
  (`rondleiding_aangeboden`, `rondleiding_knop` op `/v1/auth/me`) onthoudt of hij zich al aanbood en of de knop
  *Laat me de werkplek zien* op het startscherm staat, zodat dat op een andere computer niet terugkomt. Wegklikken of
  afronden handelt het aanbod af; de knop gaat alleen op eigen keuze weg: het vinkje aan het eind van de rondleiding, of de
  instellingen (tab *Rondleiding*), waar je hem ook weer aanzet en de rondleiding start (`START_URL`). De browser (`localStorage`, faalt stil) onthoudt
  alleen waar iemand op dit apparaat onderbroken werd. De rondleiding doet alleen iets als de gebruiker iets doet: een stap die om
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

- **axe meet het machinaal toetsbare deel** in `npm run test:browser`: `scripts/axe.mjs`
  (`toetsToegankelijkheid(page, scherm)`, tags `wcag2a`/`wcag2aa`/`wcag21aa`/`wcag22aa`) op de werkplek, de
  annotaties, het annotatiepaneel, de werkgebieden en de instellingen. Elke overtreding faalt, zonder drempel op
  ernst; een uitzondering staat in `UITZONDERINGEN` met regel en reden, voor alle schermen tegelijk. axe opent
  een tweede pagina in de context, dus een script dat hem gebruikt maakt zijn pagina via `browser.newContext()`.
  Toetsenbord, focus en aankondigingen meet axe niet: die bewaken de scripts met hun stappen.
- **`text-faint` haalt 4,5:1 op paper, surface en surface-2, niet op een getint vlak** (`bg-lint/10`, de actieve
  gespreksrij): gebruik daar `text-muted`.

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
- Elke beslissing wordt **aangekondigd** via de `sr-only aria-live`-regio in
  `NodeAnnotatiePaneel`; anders is annoteren voor een schermlezer stil.
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
gebruikt in `proxy.ts`, `lib/server.ts` en de routes die zelf fetchen (de run-events, het agent-geheugen bij gesprekken,
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
    `proxy.ts` geeft `auth()` een eigen handler mee (de CSP), en dan telt in `authorized` alleen een
    `Response`: een `false` negeert next-auth en de pagina rendert gewoon. `proxy.gate.test.ts` draait de
    echte proxy met echte sessiecookies; `auth.config.test.ts` ziet alleen de callback.
  - Inloggen gaat uitsluitend met de userid; e-mail is verplicht en uniek maar geen inlog-identiteit.
    De sessie is een httpOnly JWT-cookie (`AUTH_SECRET`) met `userid` + rol; de Credentials-provider
    verifieert bij de API (`verifyCredentials` → `/v1/auth/verify`). De API bewaart users, hash en
    TOTP; de BFF alleen de sessie.
  - Rollen: **`beheerder`** (beheertabs + `/api/admin/*`) en **`analist`**, afgedwongen in de
    `authorized`-callback (edge) en in de BFF (`/api/admin/*`); het instellingenvenster toont een beheer-tab alleen aan
    een beheerder (`InstellingenVenster`). `/setup` maakt eenmalig de eerste beheerder.
  - **Zelfregistratie**: `/registreren` (`RegistratieClient` → `/api/registreren`) legt een
    *aanvraag* vast, geen account. De API leidt de userid af uit voor- en achternaam en bewaart de
    bcrypt-hash van het gekozen wachtwoord; pas bij goedkeuring in de tab **Aanvragen**
    (`RegistratiesPanel`) ontstaat de gebruiker, met dat wachtwoord. **Afwijzen verwijdert de
    aanvraag** ("Afwijzen en verwijderen"), zodat e-mailadres en volgnummer vrijkomen. Er gaat bewust
    geen e-mail: wie inlogt terwijl zijn aanvraag loopt, krijgt de `code` `aanvraag_open` uit
    `/verify` (afgehandeld in `LoginClient` naast `totp_required`) – alleen bij het **juiste
    wachtwoord**, anders is het een middel om te ontdekken wie een aanvraag heeft.
  - **2FA (TOTP)** is self-service in de tab Beveiliging; inschakelen vraagt het huidige wachtwoord. De
    account/2FA-routes zetten `X-User-Id` uit de sessie, nooit uit browser-input. Voor een beheerder is het
    verplicht: `InstellingenInhoud` toont dan op de beheertabs `BeheerVraagt2fa` (de BFF houdt ze hoe dan
    ook dicht), en `AccountClient` toont een beheerder geen *Uitschakelen* (de api weigert het ook) maar wel
    *Opnieuw koppelen*: wachtwoord plus code van de huidige app, dan de QR van de nieuwe. Bij het koppelen komen de herstelcodes één keer in beeld; `TwoFactorClient` neemt een
    herstelcode aan in hetzelfde veld als de code uit de app. De 2FA-reset staat in het menu ⋯ van
    `UsersPanel` en zet `X-User-Id`, want de api wil weten welke beheerder het doet.
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
    het beleid in bovenaan de tab **Gebruikers** (`BudgetBeleidBlok`): het budget **per rol**, de
    resetperiode en aan/uit. Een budget per gebruiker bestaat niet. Per gebruiker staat wat zijn rol geeft
    (`budgetHerkomst`), en wie verbruik heeft kan een beheerder resetten in het menu ⋯ (`MenuVerwijder`, twee
    klikken): het journaal blijft staan, de teller begint opnieuw (`resetRegel` zegt wanneer en door wie).
  - **Wijzigen draagt een naam.** `PUT /api/admin/budget`, `PUT /api/admin/budget/rollen/[rol]` en `POST
    /api/admin/users/[userid]/verbruik-reset` zetten `X-User-Id` uit de sessie, naast `proxy(..., { admin: true })`.
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
