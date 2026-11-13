# CLAUDE.md – wetsanalyse-api

Headless FastAPI-backend voor de **Wetsanalyse-werkplek**: een zelfstandige, Dockeriseerbare dienst
die de [frontend](../frontend) (werkplek, login, beheervenster) en graph-qa bedient. Lees ook de
projectroot-`CLAUDE.md`. Endpoints, env-vars met defaults en lokaal draaien staan in
[`README.md`](README.md); dit bestand gaat over hoe de code in elkaar zit en wat je niet mag breken.

## Lijn van de code

Nieuwe domeinen volgen **stijl C**: de store gooit de HTTP-fouten in de transactie, de router is dun. Zo zitten de
sloten waar de transactie zit. Oudere modules wijken af en dat is geen bug: `gesprek_store` is een klasse met `Depends`
(A), `users`, `registraties`, `profiles`, `api_tokens`, `verbruik`, `berichten` en `feedback` geven domeinfouten die de
router vertaalt (B), en `begrippen_overzicht` en `artefact_versies` hebben router en store in één bestand (D). Niet
ombouwen zonder reden.

## Wat de API doet

1. **Het JAS-annotatiedomein** (`/v1/annotatie/*`): markeringen, beslissingen, append-only audit,
   export. De agent stelt voor, de jurist beslist, de API bewaart de review-state en projecteert hem
   naar de kennisgraaf. Eén laag per bronnode (artikel, lid of onderdeel) – zie §*Annotaties*.
2. **De chatgeschiedenis** (`/v1/gesprekken/*`), per gebruiker gescopet.
3. **Login en gebruikersbeheer** (`/v1/auth/*`, `/v1/admin/users`, `/v1/admin/registraties`): de API
   is de identiteitsbron van de webapp.
4. **LLM-modelprofielbeheer** (`/v1/admin/profiles`).
5. **Tokenbudget** (`/v1/verbruik/*`, `/v1/admin/budget`, `/v1/admin/budget/rollen/{rol}`, `/v1/admin/verbruik`,
   `/v1/admin/users/{userid}/verbruik/reset`).
6. **Berichten** (release notes, `/v1/berichten/*` + `/v1/admin/berichten/*`) met leesbewijzen per
   (bericht, gebruiker), en **gebruikersfeedback** (`/v1/feedback` + `/v1/admin/feedback/*`).
7. **Werkgebieden** (`/v1/werkgebieden/*`, spoor D levering 1): benoemde analyses met
   bronselecties en een inventaris van de geannoteerde elementen – zie §*Werkgebieden*.
8. **Begrippen** (`/v1/werkgebieden/{id}/begrippen/*`, spoor D levering 2): begrippen per werkgebied
   met koppelingen naar annotatie-elementen, beoordeling, revisies en export – zie §*Begrippen*.
9. **Voorstellen van Lex** (`/v1/werkgebieden/{id}/begrippen-runs/*`, `…/groepen/*`, levering 3a):
   het manifest voor de begrippenketen, runs en de betekenisgroepen – zie §*Voorstellen van Lex*.
10. **Lex naast de kaart** (`/v1/werkgebieden/{id}/begrippen/{begrip_id}/kaart-runs/*`, `…/voorstellen/*`,
   fase E): voorstellen per veld van een begrip en de besluiten erover – zie §*Lex naast de kaart*.
11. **Bronnen vinden met Lex** (`/v1/werkgebieden/{id}/bronnen-runs/*`, `…/kandidaten/*`, fase A):
   kandidaatbepalingen met rol en bewijs per ontdekmethode, en de besluiten erover – zie §*Bronnen
   vinden met Lex*.
12. **Onderhoud van begrippen** (`/v1/werkgebieden/{id}/herbeoordelingen`, `…/koppelingen/{k}/herkoppelen`
   en `/bevestigen`, `…/dekking/*`, fase F1): geraakte dragende passages, opvolgers na herannotatie en de
   dekking van het werkgebied – zie §*Onderhoud van begrippen*.
13. **Begripsrelaties en opvolging** (`/v1/werkgebieden/{id}/relaties/*`, `…/begrippen/{b}/nieuwe-betekenis`
   en `/combineren`, fase F2) – zie §*Begripsrelaties en opvolging*.
14. **Begrippen naar de kennisgraaf** (`…/begrippen/export?formaat=ttl`, `…/begrippen/conformiteit`,
   `…/begrippen/samenhang`, fase F3): NL-SBB-projectie per werkgebied, conformiteit en Turtle-export –
   zie §*Begrippen naar de kennisgraaf*.
15. **Begrippen over werkgebieden heen** (`/v1/begrippen`, `/v1/begrippen/verifieer`, `/v1/begrippen/{id}`,
   fase F4): het overzicht in de webapp en de verificatie van wat Lex in de graaf vond – zie §*Begrippen
   lezen*.
16. **Deelvragen** (`/v1/werkgebieden/{id}/deelvragen/*`, vervolg op F): optionele deelvragen bij een
   werkgebied, voorstellen van Lex en de dekkingscheck per deelvraag – zie §*Deelvragen*.
17. **Bronselectie per deelvraag** (`/v1/werkgebieden/{id}/bronselectie/*`, spoor J): de voortgang van de
   bronselectie per deelvraag en de besluiten per deelvraag – zie §*Bronselectie per deelvraag*.
18. **Versies van artefacten** (`/v1/artefact-versies/*`, 4 nov 2026): de stand van een artefact na elke beurt van
   Lex, voor de versiekiezer – zie §*Versies van artefacten*.
19. **Generieke begrippen** (`/v1/begrippen/{id}`, `…/begrippen/gebruik/*`, `…/generiek-maken`, ADR-006): begrippen boven
   de werkgebieden, gebruikt zonder kopie – zie §*Generieke begrippen*.
20. **Regies** (`/v1/werkgebieden/{id}/regies/*`, ADR-012): het object waarmee de regisseur van graph-qa het werk in een
   werkgebied over deelgesprekken verdeelt – zie §*Regies*.

21. **De werkplaats** (`/v1/werkplaats/*`, `/v1/admin/werkplaats/*`, ADR-016 deel B): wat een gebruiker zelf maakt
   (een skill, een agentprofiel) als concept met versies – zie §*De werkplaats*.

> **De wettekst komt uit de graaf.** De API leest uit GraphDB de **bronboom** (`bron_resolver.py`):
> daarmee toetst hij ankers, legt hij snapshots vast en levert hij de segmenten van de weergave.

## Architectuur (`app/`)

| Module | Rol |
|---|---|
| `main.py` | Routers, `/health`, `/ready`, gzip voor grote antwoorden (`GZipMiddleware`, ≥1 kB; Starlette slaat `text/event-stream` over), lifespan: LLM-throttle, DB-init met bounded retry (`_init_db_met_retry`), seeding van profiel en budgetbeleid, start van de projectielussen als `GRAPHDB_URL` gezet is. |
| `config.py` | `Settings` uit de env; `_read_secret` leest `NAAM` of `NAAM_FILE`. |
| `db.py` | Async SQLAlchemy Core: engine en alle tabellen. Zie §*Schema*. |
| `deps.py` | `get_gesprek_store`. |
| `auth.py`, `api_tokens.py` | Client-bearer (`require_client`) en admin-bearer (`require_admin`). |
| `user.py`, `users.py`, `registraties.py`, `routers/auth.py` | Login, 2FA, zelfregistratie. |
| `llm_profile.py`, `profiles.py`, `secrets_crypto.py`, `llm/` | Modelprofielen, Fernet-versleuteling, LiteLLM-client, `llm/throttle.py`. |
| `verbruik.py`, `verbruik_contracts.py`, `routers/verbruik.py` | Tokenbudget. |
| `berichten.py`, `feedback.py` + routers | Release notes en feedback. |
| `gesprek_contracts.py`, `gesprek_store.py`, `routers/gesprekken.py` | Chatgeschiedenis. |
| `annotatie_v2.py` (router), `annotatie_v2_store.py`, `annotatie_v2_contracts.py`, `annotatie_v2_zoeken.py` | Het annotatiedomein. |
| `bron_resolver.py` + `packages/bronmodel` | Bronboom ophalen uit de BWB-named graph, snapshot bouwen, ankers valideren. `bronmodel` is een lokaal pakket dat de API en graph-qa delen (één bronidentiteit en ankerbasis). |
| `graaf_projectie_v2.py`, `vocabulaire/` | Projectie van de lagen naar GraphDB, en de JAS-vocabulaire. |
| `graaf_client.py` | De weg naar de kennisgraaf: `repo()`, `sparql_select` en `sparql_ask`. Elke module die de graaf leest, gebruikt deze; niet `_select` uit de projectie lenen. |
| `graafcontrole.py`, `shacl.py`, `shapes/jas-v2.ttl` | Controle achteraf: klopt de graaf met Postgres? |
| `samenhang.py` | Structuur, annotaties en verwijzingen van één artikel (of het overzicht van een structuurdeel), voor de graafweergave; de bouwstenen (`bronknoop`, `markeringen`, `verwijzingen`) deelt hij met `graaf.py`. |
| `graaf.py` | De complete graaf (`/graaf`): alle regelingen met structuur, verwijzingen en markeringen; structuur en verwijzingen gecachet per `(bwb_id, toestandUrl)`. Ook `lees_bron`: de gecachete bronboom voor leesroutes. |
| `knoopinfo.py` | Wat de kennisgraaf over één knoop weet (`/knoop`), voor de inspector van de graaf. |
| `werkgebieden.py` (router), `werkgebied_store.py`, `werkgebied_contracts.py`, `werkgebied_inventaris.py`, `werkgebied_werkvoorraad.py` | Werkgebieden: bronselecties, revisies, audit, de inventaris en de annotatie-werkvoorraad. Elke store vraagt het werkgebied via `werkgebied_store.werkgebied_rij` (404 via `niet_gevonden`) en toetst een revisie met `toets_revisie`; een bepaling opnemen verifieert `werkgebieden.geverifieerde_bron`. |
| `werkgebied_export.py`, `werkgebied_rapport.py`, `bepaling_graaf.py`, `markdown_opmaak.py`, `pdf_opmaak.py`, `fonts/` | Het hele werkgebied als één rapport (ADR-009; `bepaling_graaf` is de graaflezing die het deelt met het paneel bij een antwoord): `werkgebied_rapport` is het contract en de tekstlaag, `werkgebied_export` leest de stand en vult het; de gedeelde PDF-opmaak met ingesloten lettertypen. |
| `werkgebied_deelvragen.py` | Deelvragen: opslag, voorstellen van Lex, koppelingen en de dekkingscheck. |
| `begrippen.py` (router), `begrip_store.py`, `begrip_contracts.py` | Begrippen: inhoud, koppelingen met bewijsstand, actualiteit, de accorderingspoort, revisies en export. |
| `begrippen_runs.py` (router), `begrippen_run_store.py`, `begrippen_run_contracts.py`, `begrip_manifest.py` | Voorstellen van Lex: manifest voor de begrippenketen, runs, betekenisgroepen en besluiten. |
| `begrip_voorstellen.py` (router), `begrip_voorstel_store.py`, `begrip_voorstel_contracts.py` | Lex naast de kaart: kaartruns en voorstellen per veld, overnemen en afwijzen. |
| `bronnen_runs.py` (router), `bronnen_run_store.py`, `bronnen_run_contracts.py` | Bronnen vinden met Lex: runs van de ontdekmethoden, kandidaatbepalingen en hun besluiten. |
| `runs.py` | De statusmachine van de drie runsoorten (bronnen-, begrippen- en kaartruns): `VERLOPEN`, de status voor de client, en `loopt`/`mislukt` als één conditionele UPDATE, zodat een klare run nooit meer verandert. |
| `bronselectie.py`, `bronselectie_contracts.py` (routes in `bronnen_runs.py`) | Bronselectie per deelvraag: voortgang, besluiten per deelvraag, de volgende deelvraag en het overzicht. |
| `begrip_onderhoud.py` (router), `begrip_onderhoud_store.py`, `begrip_onderhoud_contracts.py` | Onderhoud van begrippen: herbeoordelingen, opvolgers, herkoppelen, bevestigen en dekking. |
| `begrip_relaties.py` (router), `begrip_relatie_store.py`, `begrip_relatie_contracts.py` | Begripsrelaties (voorstellen uit de keten, vastleggen, afwijzen, doorwerking) en opvolging: nieuwe betekenis, combineren. |
| `begrip_projectie.py`, `shapes/nl-sbb-1.0.0.ttl`, `shapes/begrippen-wa.ttl` | Begrippen naar de kennisgraaf (NL-SBB), conformiteit per begrip en de Turtle-export. |
| `begrippen_overzicht.py` (router) | Begrippen over werkgebieden heen: zoeken, verifiëren voor Lex, één begrip. |
| `regies.py` (router), `regie_store.py`, `regie_contracts.py` | Regies (ADR-012): één lopende per werkgebied en per gebruiker, hartslag en afronden. |
| `werkplaats.py` (router), `werkplaats_store.py` + `bronmodel.werkplaats` | De werkplaats: onderdelen met een eigenaar, versies die alleen aangroeien, poort 1 bij elke opslag, audit en beleid. |
| `artefact_versies.py` | Versies van artefacten: de momentopname bij een beurt van Lex, en de routes om ze te lezen. |
| `annotatie_statistiek.py`, `scripts/statistiek.py` | Reviewstatistiek over de elementen: uitkomst per klasse en per model, klasse-verschuivingen, aandacht tegenover correctie. |
| `jas_klassen.py`, `validation.py` | De dertien JAS-klassen, volgorde en kleuren (canoniek); `GELDIGE_JAS_KLASSEN`, `JAS_KLASSE_KLEUREN`, `jas_sorteersleutel`. |
| `ratelimit.py` | In-process rate limit per client. |
| `observability.py` | JSON-logging en OpenTelemetry. |

## Annotaties: bronnodes

De specificatie is [`docs/architectuur/annotatie-bronnodes.md`](../docs/architectuur/annotatie-bronnodes.md)
(ankers, dekkingsregels, leestools, uitvoeringsspoor); het RDF-model staat in
[`docs/wetsanalyse-workbench/jas-annotatie-ontologie.md`](../docs/wetsanalyse-workbench/jas-annotatie-ontologie.md).
Hieronder wat je moet weten om de code te wijzigen.

- **Een laag hoort bij één canonieke bron-IRI** – een artikel, een lid of een onderdeel. Lagen zijn
  **gedeeld**, niet per gebruiker: wie wat deed staat in `annotatie_v2_audit` en in de beslissingen
  op het element. Elke route vraagt wel een actieve gebruiker (`actieve_userid`).
- **Postgres is de waarheid, RDF een herbouwbare projectie.** Tabellen: `annotatie_v2_state`,
  `_snapshots`, `_lagen`, `_elementen`, `_batches`, `_dekking`, `_audit`.
- **Eén globaal schrijfslot.** `annotatie_v2_store.schrijftransactie` neemt een rij-lock op
  `annotatie_v2_state` (id 1) en serialiseert zo alle kleine schrijfacties, ook over processen en
  replica's heen. Geen process-local locks.
- **Revisies en snapshots.** Elke laag draagt een revisie; schrijfacties sturen
  `verwachte_revisies` mee en krijgen **412** bij een tussentijdse wijziging. Elke schrijfactie legt
  de snapshot van de bronboom vast; een beslissing of export tegen een andere bronstand geeft
  **409**.
- **Revisiehistorie.** `schrijftransactie` houdt bij welke lagen `_raak` raakte en welke
  auditregels er vielen, en schrijft ná de laatste mutatie (vóór de commit) per laag één regel
  `revisie` met `laag_id` in een eigen kolom. `GET lagen/{laag_id}/revisies` leest alleen die regels.
  Een geweigerde mutatie (409/412) schrijft er dus geen. Geef `_audit` een `laag_id` mee waar de
  regel bij één laag hoort; een regel zonder laag (de `batch`) telt bij elke laag van de transactie.
- **Grenskeuze** (`type: "grens"`, `wijziging: {"optie": i}`): de jurist kiest een van de
  grensopties die de keten voorstelde (`trace.kandidaat.spanopties`). De client stuurt alleen de
  index; `_grens_wijziging` rekent het anker uit de brontekst en daarna loopt het als een `edit`
  (validatie, eigenaar, `edited`, slot). De beslissing legt `voor` en `nieuw` vast.
- **Batches zijn idempotent** op `batch_id` plus payload (`POST lagen/batch`). Een eigen markering
  van de jurist (`POST elementen`) loopt door hetzelfde pad met `mens=True`.
- **De API toetst ankers zelf** (`annotatie_v2_store.valideer`): klasse bestaat, fragment niet
  leeg, elk anker valt binnen het gevraagde bereik, `tekst[start:eind]` van de bronnode is exact het
  ankerfragment en de `bron_hash` klopt, geen dubbele ankers, en de elementtekst is de
  ankerfragmenten in volgorde. De eigenaar van het element volgt uit de ankers
  (`bronmodel.valideer_ankers`), niet uit wat de client zegt.
- **Verouderd.** Wijkt de hash van een geankerde bronnode af van de actuele bron, dan is het
  element verouderd: alleen-lezen (409), telt niet mee bij afronden. De lifecycle blijft staan als
  historie.
- **Opnieuw annoteren ruimt op** (`_vervang_oude_voorstellen`). Een batch met `run.modus == "opnieuw"` en een voltooide
  dekking zet elk element met de eigenaar in het bereik dat van de agent komt, actueel is, geen oordeel draagt en niet
  opnieuw in de batch zit op `vervangen` (`vervangen_in`, auditregel `element-vervangen`); wissen doet hij niet. De
  respons draagt `vervangen` (ids). Komt hetzelfde id later terug, dan leeft het op (`element-hersteld`). Staat het er nog met een andere duiding (`VERVERS`: subtype, toelichting, alternatieven, aandacht, reviewuitleg, grounded), dan ververst de ronde het als niemand erover besliste (`_ververs`, auditregel `element-bijgewerkt` met de velden); een gelijk voorstel blijft byte-gelijk. `vervangen` is
  niet actueel (`NIET_ACTUEEL`, `is_vervangen`): `weergave` en `actuele_elementen` laten het weg (de weergave en de
  inventaris noemen het apart in `vervangen`, `actuele_elementen(inclusief_vervangen=True)` voor wie het wil tonen), net
  als zoeken, werkvoorraad, statistiek, overzicht, afronden en `laag_invoer` (de projectie); `slot_van` en `_beslis_in`
  maken het alleen-lezen; `begrip_store.actualiteit` geeft `gewijzigd`. Een nieuwe lezer van de elementtabel moet
  dezelfde keuze maken. Zie de specificatie §*Opslag en projectie*.
- **Eén definitie van beoordeeld** (`annotatie_v2_contracts`): `BEOORDEELD` (`human_approved`, `edited`, `published`),
  `AFGEHANDELD` (daarnaast `rejected`), `VERGRENDELD` (`AFGEHANDELD` zonder `edited`) en `NIET_ACTUEEL` (`vervangen`).
  Schrijf de lifecycles nergens los uit; `frontend/lib/annotatie.ts` draagt dezelfde waarden en `tests/test_lifecycle_drift.py` bewaakt dat.
- **Relaties tussen markeringen** (ADR-011, `annotatie_v2_relaties.py`).
  - Een relatie hoort bij de laag van de drager: leggen, beoordelen en wissen lopen door het schrijfslot met
    revisie, 412 en audit.
  - De typen en klassenparen komen uit de gegenereerde `jas_relaties.py`; bewerk die niet.
  - Een gewist element of een verwijderde bepaling neemt haar relaties mee (`wis_bij`).
  - Een impliciete partij (`annotatie_v2_impliciet`) is geen markering. Een nieuwe lezer van de elemententabel
    hoeft haar dus niet te kennen.
  - De weergave draagt `relaties` en `impliciet`.
  - De projectie (schema 4) zet ze in de graph van de dragerlaag (`laag_invoer` levert ze, `bouw_graaf(…,
    relaties=)`). Een directe triple `rel:<type>` komt er alleen bij een beoordeelde relatie; `veranderd` niet,
    want dat hangt af van een andere laag.
  - De graafcontrole meldt `relaties.hangend` en `relaties.kardinaliteit`, diagnostisch en buiten `in_orde`.
  - **Voorstellen van de keten** komen mee in de batch (`Batch.relaties`, `RelatieVoorstel`: `van_ankers`, `naar_ankers`,
    `type`, `volgorde`, `spoor`; graph-qa-proefvlag `RELATIE_VOORSTELLEN`). `annotatie_v2_relaties.leg_voorstellen` draait
    ná de elementen in dezelfde transactie: een eindpunt is het element in `saved` met precies die ankers (twee klassen
    op dezelfde ankers: de catalogus kiest, anders `dubbelzinnig`), daarna `toegestaan`. Vastgelegd als `herkomst:
    "agent"`, `voorgesteld`, `aandacht: "groen"`, met het spoor en `geproduceerd_door` (zonder meting); auditregel
    `relatie-voorgesteld`. Wat niet kan, staat in `relaties_overgeslagen` met een reden (`eindpunt_onbekend:<kant>`,
    `klassen_passen_niet`, `dubbelzinnig`, `eindpunt_niet_actueel`, `laag_afgerond`, `volgorde_bezet`, …), nooit geraden.
    Het id volgt uit de inhoud: een gelijk voorstel blijft gelijk, een afgewezen komt niet terug. Een ronde `opnieuw` met
    voltooide dekking zet oude agentrelaties zonder oordeel in het bereik die niet opnieuw kwamen op `vervangen`
    (`relaties_vervangen`, `relatie-vervangen`); een relatie van de jurist nooit. Een vervangen relatie staat niet in de
    weergave en niet in de projectie; komt ze terug, dan leeft ze op (`relatie-hersteld`). Zonder relaties is de
    vingerafdruk van de batch dezelfde als voor het veld bestond.
  - Zie de specificatie §*Relaties tussen markeringen*.
- **Een oordeel vergrendelt.** Een element in `VERGRENDELD` dat van de agent komt of een oordeel draagt
  (`heeft_oordeel`), accepteert alleen `comment` en `heropen` (`annotatie_v2_store._beslis_in`). Afronden (`zet_status`
  → `geaccordeerd`) kan pas als elk actueel element afgehandeld is en de bron niet veranderde.
- **Een eigen markering heeft een beslissingsregel** (`type: "markering"`, met actor, tijd en klasse), zodat de audit van
  elk element compleet is. Die regel is geen oordeel: de maker mag nog bijwerken en wissen, en de statistiek telt hem niet.
- **De toelichting volgt de klasse.** Wisselt een `edit` de klasse zonder eigen toelichting, dan ging de oude over de
  vorige klasse: ze wijkt voor een zin die dat zegt (`_herzien_toelichting`), en de beslissing bewaart haar in `voor`.
- **Antwoorden op een besluit zijn klein** (`compact_element`): zonder `trace` en `geproduceerd_door`. De werkplek laadt
  de weergave daarna toch opnieuw. Elk element droeg de hele meting van zijn ronde; **`GET weergave` draagt elke meting nu
  één keer** (`compacte_weergave`, `runs` op `run_sleutel`) en `GET elementen/{id}` geen. De opslag, de export en
  `bouw_graaf` lezen de volledige `store.weergave`: daar hoort de meting bij.
- **Bulk per laag** (`POST lagen/{id}/beslissingen`, `beslis_laag`): hoogstens 500 besluiten in één transactie en één
  revisie, alles of niets (409 `besluit_geweigerd` met het element), met `_beslis_in` als enige pad, dus dezelfde regels en
  auditregels als los. `edit` alleen op klasse en toelichting: ankers kunnen de eigenaar verplaatsen.
- **Wissen van één element** (`DELETE elementen/{id}`) mag alleen voor een eigen, nog niet
  beoordeelde markering.
- **Verwijderen van de bepaling in beeld mag iedereen** (`POST weergave/verwijder`,
  `annotatie_v2_store.verwijder_weergave`): alle lagen op het doel en de bronnodes eronder, met hun
  elementen, in één transactie onder het schrijfslot en met de revisietoets (412).
  - **De dekking gaat mee**, anders leest Lex de bepaling bij de volgende beurt als "al
    geannoteerd". Een dekkingsrij van een ruimere bepaling houdt haar bereik buiten deze scope en
    verliest `voltooid`.
  - **Een element van een ruimere laag blijft staan.** Valt het met één anker in deze bepaling, dan
    is het daar een verwijzing, geen eigendom.
  - **De audit blijft**: per laag een regel `laag-verwijderd` naast de bestaande regels. Daaruit
    leest de weergave `verwijderd: {op}`, zodat een heropend gesprek "verwijderd" toont in plaats
    van een leeg paneel.
  - **Geen afhankelijkheid van de brongraaf.** De route neemt de bewaarde snapshot
    (`historische_snapshot`); alleen een bronstand die nooit is weggeschreven wordt opnieuw
    opgehaald, en die geeft 409 als hij intussen veranderde.
  - **De graaf direct, de lus als vangnet**: na de commit `graaf_projectie_v2.verwijder_projecties`
    (DROP van de graph plus de registerregels). Hapert GraphDB, dan meldt de respons
    `graaf: "volgt"` en ruimt `verwijder_verweesde_projecties` de wees bij de volgende ronde op.
- **Zoeken** (`annotatie_v2_zoeken.zoek`) haalt kandidaten uit de graaf en **verifieert ze tegen
  Postgres** (manifest van lagen en revisies). Elk filter staat dus twee keer: in `zoek_query`
  (SPARQL) en in de Python-controle – ook de herkomstfilters `herkomst`, `aandacht`, `subtype`,
  `beslist_door` en `met_twijfel` (`_past_herkomst`). `tools/graph-qa/tests/test_contract_drift.py`
  bewaakt dat het toolschema van `search_annotaties` niets vraagt wat `Zoekvraag` niet kent. Een storing of een achterlopende projectie is nooit
  een leeg, succesvol resultaat: de respons draagt `volledig`.
- **Bronboom** (`bron_resolver.resolve_bron`): leest alleen de expliciete BWB-named graph, nooit
  een union met de annotatiegraphs. Zonder `GRAPHDB_URL` of bij een haperende GraphDB geeft de
  router 503; een ongeldige bron-IRI 422.
- **`/verklaringen`** levert `vocabulaire/verklaringen.json`: leesbare namen voor alles wat in een
  `trace` kan staan. Dat bestand en `vocabulaire/jas-vocabulaire.ttl` worden **gegenereerd** door
  `tools/graph-qa/scripts/genereer_jas_vocabulaire.py`; bewerk ze niet met de hand.
  `tests/test_vocabulaire.py` bewaakt dat elke klasse van de API een concept heeft.
- **Elke export is een eigen bestand** (`bestandsnaam.met_tijd`): de naam draagt datum en tijd op de seconde, in Nederland,
  in dezelfde vorm als de Markdown van de werkplek (`bestandsnaam` in `frontend/lib/artefactMarkdown.ts`).
- **Export** (`POST weergave/export`, `annotatie_export.py`): `json` (v4, schema in
  `schemas/annotatie-export-v4.schema.json`, ook op `GET export-schema`; v3 blijft staan als historie), `csv`, `pdf` en `trig`.
  v4 maakt `relaties` en `impliciet` (ADR-011) expliciet, ook als ze leeg zijn. De CSV krijgt per relatie een rij van soort
  `relatie`, met de kolommen `leesvorm`, `relatietype`, `van_*`/`naar_*` (klasse en tekst), `volgorde` en `veranderd` achteraan
  (lifecycle en herkomst in de bestaande kolommen); de PDF een lijst *Relaties* per bepaling (de dragerlaag) en de impliciete
  partijen. Hier staan ook afgewezen relaties, met hun lifecycle, net als afgewezen markeringen.
  `herkomst_regels` zet het spoor om in de leesbare namen uit `verklaringen.json`, met dezelfde
  opzoekregels als `frontend/lib/waarom.ts`. De oude CSV-kolommen blijven vooraan staan; nieuwe komen
  erachter. TriG bouwt per laag met `laag_invoer` + `bouw_graaf`, dus exact wat de projectie schrijft.
- **`/samenhang/antwoord`** (`samenhang_antwoord.py`) is de ketting bij een antwoord: per doel de keten
  erboven, het doel, één niveau eronder, de markeringen daarop (boven `MAX_MARKERINGEN` alleen de telling), de
  begrippen die daar gelden en de uitgaande verwijzingen, zonder broers en zonder klasseknopen. Een wettelijk
  begrip komt uit `bwb:definieertBegrip` en staat er alleen als de term letterlijk in de getoonde tekst staat én
  het doel binnen het geldingsbereik valt (formules in `bronmodel.definities`, op te lossen via de boom; niet op te
  lossen is niet tonen). `komt_voor_in` zegt dus alleen dat de term er letterlijk staat. Een begrip uit een
  werkgebied hangt aan een getoonde markering; in een los gesprek alleen geaccordeerde generieke begrippen.
  `begrippen_beschikbaar: false` bij een haperende graaf, nooit "geen begrippen".
- **`/samenhang`** (`samenhang.py`) geeft drie soorten relaties en niets anders: de bronboom, de
  letterlijke verwijzingen uit de BWB-import (één stap in en uit, max. `MAX_VERWIJZINGEN`) en de
  actuele markeringen. Er wordt niets afgeleid. Een doel buiten de boom krijgt een leesbaar label:
  de naam uit de graaf, anders het anker als dat een naam noemt of het importerlabel een kaal BWB-id
  is, anders dat label; een verwijzing met `betrouwbaarheid` laag heet "… (doel onzeker)". Een markeringsknoop draagt herkomst, aandacht,
  subtype, `beslist_door` en `twijfel` uit het element, zodat de werkplek erop kan filteren. Is het
  doel een **structuurdeel** (hoofdstuk, titeldeel, afdeling, paragraaf), dan is het een overzicht: het
  deel met de structuur en artikelen eronder, zonder leden, onderdelen, markeringen en verwijzingen
  (die horen bij een geopend artikel; anders wordt een hoofdstuk een kluwen van honderden knopen).
  Daarnaast de **relaties tussen markeringen** (ADR-011): `samenhang.jas_relaties` zet `weergave["relaties"]` om in
  lijnen `jas_relatie` (groep `relaties`, met `type`, `leesvorm` – ook in `anker_tekst` –, `lifecycle`, `veranderd`
  en `volgorde`) en `weergave["impliciet"]` in knopen `impliciet` (`impliciet:<id>`, met `klasse`, `label`,
  `toelichting`). Alleen wat is vastgelegd, niets afgeleid; een afgewezen relatie valt weg, en een relatie met een
  eindpunt dat niet in de graaf staat (ander artikel, verworpen, verouderd) ook, geteld in `relaties_weggelaten`.
  `/samenhang/meer` loopt via `samenhang()` en krijgt ze dus mee; `/graaf` leest ze in één leestransactie
  (`annotatie_v2_relaties.alle_relaties`), met een impliciete partij alleen als de bronnode van haar laag in beeld is.
  **`/samenhang/meer`** (hoogstens 30 `bron_iri`'s) geeft de samenhang van meerdere doelen in één
  verzoek en haalt per regeling de bronboom één keer op (`bron_resolver.haal_bronrijen` +
  `snapshot_uit`); een doel dat niet resolvet staat in `fouten`. Een overzicht opent zo 15 delen met 4
  bronbomen in plaats van 15.
  **`/graaf`** (`graaf.py`, `bwb_id` herhaalbaar, leeg = alle) levert de complete graaf in dezelfde
  `Knoop`/`Relatie`-vorm, zonder tekst (≈2 MB JSON voor alles, gzip). Structuur (`haal_bronrijen`) en
  uitgaande verwijzingen (uit de named graph van de regeling, zonder LIMIT) staan per proces in een
  cache onder `(bwb_id, bwb:toestandUrl)`: een herimport met een nieuwe toestand ververst vanzelf.
  Markeringen komen altijd vers (`store.actuele_elementen`). `versie` = hash van de toestanden; daarop
  cachet de werkplek de layout. Een BWB-id gaat letterlijk een query in en wordt strikt gevalideerd.
  Een bronknoop draagt `vindplaats` uit de importer (`bwb:vindplaats`, "Artikel 9.2, onderdeel d") en zijn
  `artikel`/`lid` komen uit de boom (`plaats_in`), niet uit de IRI: die liegt bij de Leidraad. `bron_query` leest
  `vindplaats` en `inBepaling` op de node, maar `snapshot_id` hasht ze niet (`bronmodel.PLEK`).
  Het label van een deel krijgt zijn nummer (`_label`: de bronboom draagt "Hoofdstuk" en "II" apart);
  bewust hier en niet in `bronmodel`, waar het de snapshot-identiteit van bestaande lagen zou raken.
  **`POST /plaatsen`** (`graaf.plaatsen`, hoogstens 500 `bron_iris`) geeft per bepaling de regeling en het pad
  eronder (hoofdstuk/afdeling/divisie › artikel › lid › onderdeel) met `_label` en `volgorde`, om in de
  werkplek te groeperen (spoor H). De structuur per regeling staat in een eigen cache op `(bwb_id,
  toestandUrl)` (`_structuur`) die `/graaf` deelt; een onbekende IRI krijgt `pad: []`. Alleen het BWB-id gaat
  een query in.
  **`/knoop`** (`knoopinfo.py`, `bron_iri`) geeft wat de BWB-import en de WTI-verrijking verder aan
  één knoop hangen, letterlijk en zonder afleiding: de bekende predicaten in vaste groepen met een
  Nederlandse naam (`FEITEN`: geldigheid – ook die van de regeling erboven –, herkomst, regeling,
  grondslag en bevoegdheid – ook inkomend `heeftGrondslag` –, genoemd in, begrip, vindplaats), de
  `bwb:Verwijzing`-knopen van en naar de knoop (soort, soort doel, pad, betrouwbaarheid: wat een lijn
  in de graaf niet draagt), en **alle** uitgaande triples ruw, zodat er nooit iets ontbreekt. Een
  nieuw predicaat verschijnt dus eerst alleen ruw; geef hem een plek in `FEITEN`. De IRI gaat
  letterlijk een query in en moet `samenhang._IRI` volledig matchen (422); een haperende graaf 503.
  **`/bepaling`** (`bepaling_detail.py`, `bron_iri`; ADR-008 *Detail bij een antwoord*) is wat het paneel naast het gesprek
  over één bepaling toont: plek in de opbouw met opschriften (`graaf.plaatsen` + `bwb:titel`), geldigheid, de verwijzingen
  vanuit de bepaling en haar leden met ankertekst, wie ernaar verwijst (telling, de eerste tien, zonder de bepaling zelf),
  grondslag en bevoegdheid, genoemd in en gedefinieerde begrippen. De vorm staat in `bepaling_graaf_contract.py`
  (`Structuurdeel`, `Verwijzing`, `Telling`, `BepalingDetail`), de ene graaflezing per bepaling die het werkgebiedrapport
  deelt (ADR-009). De opschriften, de uitgaande verwijzingen en de tellingen komen uit `bepaling_graaf.lees`: de bepaling met
  `met_inkomend=True`, haar leden en onderdelen zonder (één telquery, niet één per lid). Alleen wie ernaar verwijst, de
  geldigheid en grondslag/bevoegdheid/genoemd in leest het endpoint zelf: dat wil het rapport niet. `detail_uit` is puur; een
  haperende graaf geeft `beschikbaar: false` met status 200, nooit een leeg detail. De herkomst voor de kop van het
  bronvenster: `vindplaats.jci` komt uit `owl:sameAs` mét de toestand die de graaf draagt (`&z=…&g=<geldig_vanaf>`), zodat
  de link de versie opent die het paneel toont; een `id:`-divisie zonder jci-vorm krijgt geen verzonnen jci. Daarnaast
  `bwb_id` en `url` (`bwb:bronUrl`, anders `owl:sameAs`).

### Projectie naar de kennisgraaf

`graaf_projectie_v2.py`. Named graph `urn:jas:graph:v2:<laag-id>`, register
`urn:jas:graph:register:v2`. De API is de enige schrijver onder `urn:jas:`; graph-qa leest alleen.

- **Direct na de commit.** Elke laagwijziging loopt via `_raak`, die de laag op de verbinding
  noteert; `schrijftransactie` roept ná een geslaagde commit `na_mutatie` aan, die op de achtergrond
  projecteert. Een geweigerde mutatie (409/412) projecteert dus niets, en een haperende GraphDB laat
  de beslissing van een jurist niet falen.
- **De lus is het vangnet** (`lus`, interval `JAS_PROJECTIE_INTERVAL`). `reconcile` vergelijkt de
  revisies die **in de graaf** staan met Postgres, zodat ook een lege GraphDB na een herstart wordt
  opgemerkt en opnieuw gevuld, ruimt verweesde projecties op (na een hercontrole onder het
  schrijfslot) en zet de vocabulaire neer als die ontbreekt. Elke tiende ronde logt hij de lichte
  graafcontrole (`annotatie_graaf_afwijking`, voor Grafana).
- **Rekenwerk met rdflib gaat via `asyncio.to_thread`** – bouwen, serialiseren, parsen, isomorfie, SHACL.
  Het is pure Python, en de lus deelt de event loop met elk verzoek: synchroon hield één ronde van de
  lichte graafcontrole ruim een halve minuut de hele api vast (acceptatie, 28 okt 2026: 504's op elk
  scherm). `test_het_rdflib_werk_draait_niet_op_de_event_loop` bewaakt dat.
- **`projecteer`** neemt een rij-lock op de laag en een lock per laag in het proces, en schrijft
  `geprojecteerd_revisie` pas na een geslaagde `PUT` plus registerupdate.
- **Invarianten** (getest, en gecontroleerd door `graafcontrole.py`): geen subject onder `urn:bwb:`,
  geen `urn:bwb-ns:`-predicaat en geen schema-axioma's (domain/range/subClassOf/sameAs) in een
  `urn:jas:graph:*`. Anders duikt een annotatie op als wettekst in de queries, de similarity-index of
  de bronnencontrole van Lex.
- **Herkomst in RDF.** `bouw_graaf` zet per element een `prov:Activity` voor de run (model als
  `prov:SoftwareAgent`) en de beoordelingen erbij.
- **Graafcontrole per laag** (`graafcontrole.controleer_laag`, via `GET /v1/annotatie/elementen/{id}/graaf`
  voor elke actieve gebruiker): dezelfde toetsen als hieronder voor één laag (`_controleer_laag` is
  gedeeld), zonder verweesde graphs en invarianten. Het endpoint geeft er de Turtle van het element
  bij, gebouwd met `bouw_graaf` – het technisch detail in de werkplek.
- **Graafcontrole** (`GET /v1/admin/annotatie/graafcontrole`, alleen lezend): consistentie
  (register, revisies, verweesde graphs), bouw (opgehaalde graph isomorf met `bouw_graaf` uit de
  Postgres-stand), SHACL per niveau (`rdf`/`jas_model`) en de invarianten. Een laag die nog niet
  geprojecteerd is heet achterstand, geen afwijking. Een onbereikbare graaf levert
  `graaf_beschikbaar: false` en `in_orde: null`, nooit "in orde". SHACL draait nooit in het
  schrijfpad; zonder pyshacl geeft `shacl.valideer` `beschikbaar: False`.

### Reviewstatistiek

`annotatie_statistiek.rapport` telt over element-dicts wat juristen met de voorstellen deden: de
zwaarste beslissing per element, per klasse en per model (`geproduceerd_door`), de
klasse-verschuivingen (uit `voor` en `wijziging` van een edit – `beslis` legt `voor` daarvoor vast)
en per aandacht-niveau hoe vaak de jurist corrigeerde. Twee ingangen op dezelfde functie:
`GET /v1/admin/annotatie-statistiek` (de `limit` laatst gewijzigde lagen, achter het admin-token
omdat het een meting van de agent is) en `scripts/statistiek.py` over JSON-exports. Aggregeren
gebeurt in Python, want de elementen staan als JSON en de tests draaien op SQLite.

## Werkgebieden

`werkgebieden.py`, `werkgebied_store.py`, `werkgebied_inventaris.py`; het ontwerp staat in PLAN
spoor D (*Werkgebied als node*).

- **Het thema is een TOOI-URI** (spoor I6, `app/tooi.py`): `thema` komt uit de snapshot van tooitop
  (`tooi_themas.json`, CC0, met bron en datum); een ander thema geeft 422. `GET …/thema-voorstel` stelt
  zonder model thema's voor uit de WTI-rechtsgebieden van de regelingen van de bronnen (een kleine
  afbeeldingstabel, `RECHTSGEBIED_THEMA`); zonder graaf een lege lijst.
- **Gedeeld**, zoals de annotaties: elke actieve gebruiker ziet en wijzigt alle werkgebieden; wie
  wat deed staat in `werkgebied_audit` (alleen inserts).
- **Eén schrijfpad per mutatie** (`werkgebied_store._gewijzigd`): rij-lock op het werkgebied
  (`FOR UPDATE`), `verwachte_revisie` → 412 `{fout: "revisie_conflict", revisie}`, revisie +1,
  auditregel. Het annotatieslot (`annotatie_v2_state`) blijft erbuiten: een werkgebied schrijft
  geen annotaties.
- **Aanmaken vanuit het gesprek is idempotent** (activiteit 1): graph-qa stuurt de `intake_id` mee,
  en een tweede `POST` met dezelfde id geeft hetzelfde werkgebied terug (unieke index
  `ux_werkgebieden_intake`; de race tussen replica's vangt de `IntegrityError`). Zonder `intake_id`
  is elk verzoek een nieuw werkgebied.
- **Het dossier** (spoor F, F2): naast naam, analysevraag en afbakening draagt een werkgebied
  `aanleiding`, `context` en `doel` (startactiviteit a van de Leidraad) en een `praktijkvoorbeeld`
  (activiteit 1b), elk vrije tekst; wijzigen loopt door hetzelfde schrijfpad. Bij het aanmaken mogen
  `deelvragen` (`{vraag, herkomst: analist|lex}`) mee: actief, op volgorde, één keer per genormaliseerde
  vraag, in dezelfde transactie; de auditregel `aangemaakt` telt ze. Lex gebruikt dit dossier als
  context voor elk voorstel (graph-qa).
- **De peildatum is standaard de aanmaakdag** (in Nederland, `werkgebied_store.dag_in_nl`; besluit gebruiker 3 nov
  2026): `maak` zet hem als er geen is opgegeven, een oude rij zonder peildatum leest hem ook zo, en
  `peildatum_standaard` zegt of hij dat nog is. **`GET {id}/toestanden`** zet de peildatum naast de toestand van elke
  regeling in de bronnen (`bwb:geldigVanaf`/`geldigTot`). De graaf heeft per regeling alleen de nieuwste toestand:
  `na_peildatum` zegt dat de tekst kan afwijken. Een haperende graaf geeft `volledig: false`.
- **Een bronselectie wordt geverifieerd** via de bronresolver (`bron_iri`, of `bwb_id` + `artikel`
  (+ `lid`)); de canonieke `bron_iri`, het label, `snapshot_id` en `bron_hash` worden bewaard.
  Dezelfde bron met dezelfde rol en hetzelfde bereik opnieuw toevoegen is idempotent (200, geen
  revisiesprong); met een andere rol of ander bereik 409.
- **Bepaling toevoegen zoekt in de echte boom** (`bepaling_zoeken.py`, 3 nov 2026; sinds 4 nov aangeroepen door
  graph-qa, het kaartje `bs_toevoegen_treffers`): `GET {id}/bepalingen?bwb_id=&q=` leest
  een getypte vindplaats ("9 lid 2", "art. 9, tweede lid", "21.1", "25.4 onderdeel b", "36 lid 5 sub a"; `lees`) en
  zoekt hem in de bronboom van die regeling (`zoek`: precies, dan wat eronder hangt, dan artikelen die met het
  nummer beginnen; zonder nummer op de kop), met vindplaats, titel en het begin van de tekst. Artikel en lid komen
  uit de boom, niet uit de IRI, en "9 lid 2" bij een beleidsregel is divisie 9.2. Een `BronKeuze` bij opnemen geeft
  422 `{melding, opties}`, zodat de werkplek kan laten kiezen.
- **De lijst** (`GET /v1/werkgebieden`) met `mijn=true` geeft alleen werkgebieden met een auditregel
  van deze gebruiker (*Door mij bewerkt* in de webapp, zoals bij de annotaties). Met `bron_iri` alleen de
  werkgebieden met een actieve selectie die die bepaling omvat (`werkgebied_store.omvat`: de bepaling zelf,
  of bij `onderliggend` een bronnode eronder volgens het pad van de IRI) – voor de bronpagina (spoor G3).
  Een selectie op een structuurdeel draagt de artikelen niet in haar pad en mist deze toets: liever een
  gemiste dan een verkeerde.
- **Een selectie weghalen is soft** (een tijdstip). De annotaties van de bron blijven altijd staan.
- **Een werkgebied verwijderen is echt wissen**, net als een annotatie (`DELETE /v1/werkgebieden/{id}`,
  `werkgebied_store.verwijder`/`wis`): onder het rij-slot en met de revisietoets (412) gaan het werkgebied
  en elke rij in `WERKGEBIED_TABELLEN` weg, plus de begriprevisies en de deelvraagkoppelingen via hun
  ouder. **De audit blijft**, met een laatste regel `werkgebied-verwijderd`; via `_audit` volgt de
  begrippengraaf (geen werkgebied → DROP van de graph). De annotaties blijven: die horen bij een
  bronnode. De `intake_id` is daarna weer vrij. Een nieuwe tabel met `werkgebied_id` (of `begrip_id`)
  hoort in de wislijst; `tests/test_werkgebied_verwijderen.py` faalt anders – behalve `gesprekken`: die
  worden los (`werkgebied_id = ""`), niet gewist, want een gesprek is een verslag van de gebruiker. Archiveren bestaat niet
  meer, en een zacht verwijderd begrip ook niet: de kolommen `werkgebieden.gearchiveerd` en `begrippen.verwijderd`
  zijn weg (H3). Wat er nog mee gemarkeerd stond, wist de start eenmalig zoals verwijderen dat doet
  (`db._wis_oude_zachte_verwijdering`).
- **Een verwijderd object zegt wanneer en door wie.** `GET` op een verwijderd werkgebied of begrip
  geeft `404 {fout: "verwijderd", soort, op, door, melding}` uit de audit (`niet_gevonden`; ook voor
  oude gearchiveerde werkgebieden, via hun auditregel `gearchiveerd`); een id dat nooit bestond blijft een
  gewone 404. De werkplek toont dan "… is verwijderd op … door …", zoals bij een annotatie.
- **Lezen uit de cache, vastleggen tegen de bron van nu.** Eén scherm vraagt `elementen`, `dekking`, `herbeoordelingen`,
  `annotatie-werkvoorraad` en `begrippen-runs/laatste` tegelijk, en elk las alle regelingen van het werkgebied (acceptatie, 5
  regelingen: samen 5,4 s). Deze GET's krijgen daarom `werkgebieden.lees_bron` (`graaf.lees_bron`): de gebouwde snapshot per
  `(bwb_id, toestandUrl)`, één keer per proces gebouwd ook bij parallelle verzoeken, hoogstens `GELDIG_S` (10 min) oud,
  want een herimport met een andere parser houdt de toestand. Hij gaat over de hele regeling (`doel` is de wortel) en is
  gedeeld: niet wijzigen. Elke route die iets vastlegt, houdt `resolve_bron`.
  De bronboom was niet de grootste post. Een leesroute over de hele elemententabel neemt daarom `store.compacte_elementen`
  (`actuele_elementen(compact=True)`): op Postgres valt `ZWAAR` al in de query weg, want dat parsen kost anders op 0,5 vCPU
  bij elk scherm rond een seconde. De werkvoorraad leest per snapshot alleen nog de bron-hashes, één keer per proces
  (`_bronstanden`; een snapshot-id is de hash van zijn inhoud). Lees `annotatie_v2_snapshots` nooit zonder filter.
- **De inventaris** (`GET {id}/elementen`) leest per regeling één bronboom en de actuele
  elementen. Elk element staat één keer in de inventaris; `analyseren` wint van `context`;
  `deels_buiten` als een anker buiten de selecties valt; afgewezen elementen staan apart in `afgewezen` (de tab toont ze
  achter een filter), omdat het manifest en koppelen alleen `elementen` lezen.
  Per selectie is `bron_gewijzigd` een signaal, geen ongeldigverklaring. Een onbereikbare bron geeft
  `onbereikbaar` en `volledig: false`, nooit een stil kleinere inventaris.
- **De annotatie-werkvoorraad** (`GET {id}/annotatie-werkvoorraad`, `werkgebied_werkvoorraad.py`,
  fase B) zegt wat Lex nog moet annoteren. Alleen selecties met rol *analyseren*; contextbronnen
  worden geteld. De eenheden volgen `bronmodel.annotatie_eenheden` – de regel van de keuzekaart, dus
  een artikel met leden per lid – en staan elk één keer. De stand per eenheid komt uit Postgres
  (lagen, elementen, dekking): `afgerond`, `te_beoordelen`, `beoordeeld`, `zonder_markeringen`
  (geannoteerd, niets gevonden – telt dus niet als nieuw) of `nieuw`; `te_annoteren` is de lijst
  `nieuw`. De schatting is de mediaan van het verbruik van de laatste 20 annotatiebeurten van de
  gebruiker (run met een annotatie-artefact of `annotatie_doel`) keer het aantal; zonder geschiedenis
  `null`, nooit een verzonnen getal. Een onbereikbare bron: `volledig: false` plus een open punt.
  **Het bereik** (`?bereik=werkgebied|deelvragen[&deelvraag_id=]`, default het hele werkgebied): met
  `deelvragen` alleen de selecties die aan de actieve deelvragen gekoppeld zijn (`selecties_in_bereik`;
  een selectie onder meer deelvragen telt één keer), met `deelvraag_id` die van één. De respons draagt dan
  `bereik`, `deelvragen` (`{id, vraag, selecties}`) en `buiten_bereik` (analysebronnen die niet meegaan).
  `deelvraag_id` zonder `bereik=deelvragen` 422; een onbekende deelvraag 404; een niet-actieve 409
  `niet_actief`; geen actieve deelvragen 409 `geen_deelvragen` (elk met `melding`).
- **De export** (`GET {id}/export?formaat=pdf|md|json&inhoud=beoordeeld|alles`, `werkgebied_export.py`; het schema op `GET /v1/werkgebieden/export-schema`): het hele werkgebied als één PDF of Markdown, een
  overdrachtsdossier voor wie niet in Lex werkt. De PDF komt uit één gestructureerd document (`werkgebied_rapport.Rapport`, ADR-009):
  `bouw_rapport` vult het, `rapport_regels` maakt er tekst van, en de uitvoer gaat letterlijk door de JSON heen. Een nieuw
  veld hoort in het contract én in de tekstlaag; `test_elke_tekst_in_het_rapport_komt_in_de_uitvoer` bewaakt dat. Versie 2 (ADR-009, aanvulling nov 2026) heeft
  `document` (kenmerk, concept, `inhoud_hash`: SHA-256 over de inhoud zonder `stand`, gelijk bij gelijke inhoud), `samenvatting` (kerncijfers) en een besluitenlog (`BESLUITEN`: welke audit-acties een besluit zijn). Het
  JSON-schema (`app/schemas/werkgebied-rapport-v2.schema.json`) maak je opnieuw met `werkgebied_rapport.schrijf_schema()`, en een test vergelijkt het. Op de stand van nu en met één vaste inhoud, zonder bovengrens: voorblad met
  bronstand en waarschuwingen, inhoudsopgave en bladwijzers, dossier, deelvragen en bronnen, wettekst met markeringen,
  begrippen, korte verantwoording. De indeling (v2): titelblad, colofon, inhoud, 1 Samenvatting, 2 Leeswijzer (met de JAS-legenda),
  3 Werkgebied, 4 Deelvragen en bronnen, 5 Analyse per bepaling, 6 Begrippen (lijst), dan de bijlagen (`BIJLAGEN`, letters op volgorde):
  Begripskaarten, Bronnenregister, Contextbepalingen (rol context zonder markering, `Regeling.context`), Samenhang, Niet meegenomen,
  Verantwoording.
  - **Relaties en regelskelet** (ADR-009, aanvulling relaties; ADR-011): `Bepaling.relaties` (elke relatie één keer, bij de bepaling
    van de drager) en per Afleidingsregel `Markering.regelskelet` (uitvoer, invoer op volgorde, operatoren met operanden, voorwaarden,
    parameters met waarde, tijd, uitzonderingen, toepassing), uit `annotatie_v2_relaties.bij_elementen`. Een afgewezen relatie staat er
    niet in maar in de bijlage *Afgewezen relaties* (`Wettekst.afgewezen_relaties`, met de reden); wat ontbreekt zegt het skelet
    ("Geen uitvoer vastgelegd."). Altijd lijsten, nooit tabellen. Een relatie heet pas "beoordeeld: akkoord" als haar
    element-eindpunten beoordeeld zijn (`RelatieEind.lifecycle`); anders "vastgelegd; een eindpunt is nog een voorstel van Lex".
  - **De inhoud** (WA TRM H1, 8 nov 2026): de route kiest standaard `inhoud=beoordeeld`. Dan staan in de analyse alleen
    markeringen in `BEOORDEELD` (ook wat de jurist zelf markeerde) en geen relatievoorstellen van de keten; de kerncijfers en
    `Wettekst.markeringen` tellen alles, `weggelaten_voorstellen` zegt wat er niet staat, en `Document.inhoud` legt de keuze
    vast. Een relatie die de jurist legde blijft staan, ook als haar eindpunten nog voorstellen zijn. `verzamel` zelf heeft
    `inhoud="alles"` als standaard (de tests).
  - **Graaf in het rapport** (`bepaling_graaf.lees`, best-effort zoals de toestanden; dezelfde lezer als het paneel bij een antwoord, met het contract in `bepaling_graaf_contract`, ADR-009 is de eigenaar): per regeling de WTI-gegevens (soort,
    eerstverantwoordelijke, TOOI-organisatie, afkorting, toestand-URL), en per voorouder van een geselecteerde bronnode
    (`werkgebied_export.structuur_iris`) de titel, `bwb:inwerking` en `bwb:bron`. Een artikel krijgt zo zijn `plaats` in de opbouw, die
    boven het artikel en in de kopregel staat (`PLAATS`). Alleen strikte IRI's gaan de query in (`BRON_IRI`). Een haperende graaf geeft het
    signaal `graaf_onvolledig`. De router geeft `bepaling_graaf.lees` mee, de tests vervangen hem. Tellingen (inkomend, grondslag, bevoegdheid) komen alleen met `met_inkomend=True`, voor het paneel; `structuur_voor(iris)` geeft de delen boven losse bepalingen.
    De verwijzingen komen uit `bwb:heeftVerwijzing`/`bwb:naar`, alleen vanuit bronnodes in het dossier (`bron_iris`; inkomende verwijzingen
    zijn ruis), met `bwb:ankerTekst` letterlijk. De query is begrensd (`MAX_VERWIJZINGSRIJEN`, hij vraagt er één meer): raakt hij de grens, dan `volledig: false` en `verwijzingen_volledig: false`, en de bijlage zegt "minstens". Tel nooit een begrensde rijenlijst als totaal. Ze staan bij de bepaling en in de bijlage Samenhang. Een doel telt als "in dit dossier" als het
    daar zelf staat of als een van zijn delen er staat.
  - **Markeringen in de wettekst**: `Bepaling.spans` (alleen ankers die nog letterlijk op hun offsets staan) gaan als regel `SPANS` (JSON)
    vlak vóór het citaat mee. `pdf_opmaak.gemarkeerd` kleurt en nummert, `markdown_opmaak` maakt vet met ⁽ⁿ⁾. Een markering in de tekst
    draagt haar nummer, en de lijst eronder herhaalt het citaat niet. `verzamel` leest met dezelfde functies als de schermen, en `regels` geeft (stijl, tekst),
  zonder reportlab te testen.
  - Geen modelvragen, hashes of beurtmeting: dat spoor staat in de annotatie-export.
  - Alles draagt zijn status; voorstellen, afgewezen en uitgesloten staan in eigen delen.
  - Staat een ankerfragment niet meer op zijn offsets, dan toont de PDF toen en nu. Wat niet te lezen was, staat op het
    voorblad én op zijn plek. Is geen enkele regeling te lezen, dan 503.
  - Reportlab is puur Python: zetten gebeurt in een thread (`asyncio.to_thread`), niet op de event loop.
  - **De pagina-opbouw ligt vast.** Een eigen pagina krijgen elk deel, elke regeling, elk begrip, *Afgewezen markeringen* en
    de *Open voorstellen van Lex*. De kop van een begrippengroep staat boven zijn eerste begrip: de breuk hoort vóór een kop,
    want een breuk erna laat hem alleen staan. Een deelvraag en een markering blijven bij elkaar (`BLOK_BEGIN`/`BLOK_EIND`).
    Een artikel krijgt geen eigen pagina: dat zijn er honderden. De begrippagina heeft altijd dezelfde kopjes, en een leeg veld
    zegt dat. Toets de opbouw met `render(..., spoor=[])`, niet met `pdftotext`: poppler staat niet op CI.
- **PDF-opmaak** (`pdf_opmaak.py`, ook voor de annotatie-export). `PAGINA` is `PageBreakIfNotEmpty`: twee kale `PageBreak`s
  achter elkaar geven een blanke pagina. De lettertypen zijn ingesloten (`app/fonts/`, met licentie):
  de standaardletters kennen alleen cp1252 en maakten van een `ā` of harde afbreekstreep stil een `■`. Wat Fira Sans niet
  heeft, tekent DejaVu per teken (`opgemaakt`). Elke tekst gaat daar doorheen: hij wordt ook geëscaped.
  Vanaf pagina 2 staat er een kopregel (titel en het lopende hoofdstuk) en op elke pagina een voetregel met "Pagina n van N"
  (`Teller`: het totaal komt pas bij het opslaan). Het document draagt `/Lang nl-NL`, `DisplayDocTitle` en metadata. Citaten
  krijgen een lijn (`Lijn`), signalen een kader. Reportlab maakt geen tagged PDF, dus PDF/UA is niet haalbaar (ADR-009, aanvulling).
  Wat wél kan, bewaakt `tests/test_pdf_opmaak.py`: contrast volgens WCAG AA (`KLEURPAREN` en de JAS-kleuren), taal en metadata,
  en geen niet-ingesloten letter. De inhoudsopgave krijgt daarom een eigen tabelstijl, want de standaard zet Helvetica op elke cel.
  Regels `Titelblad:<veld>` (`TITELBLAD_VELDEN`) vooraan worden op pagina 1 getekend: het Lex-merk (`MERK`, een test vergelijkt het met
  `frontend/merk/lex-merk.svg`), titel, vraag en een statusblok, zonder kop- en voetregel. Markdown maakt er een `#`-kop en een lijst van.
  Alles op het titelblad wordt echt gezet binnen de breedte (`passend`: dezelfde zetter, met DejaVu-terugval). Wat niet in zijn ruimte
  past, wordt op een woordgrens ingekort met een ellips, en een noot zegt waar de volledige tekst staat (colofon of samenvatting). Kop- en
  voetregel kappen af op breedte (`op_breedte`); de voetregel laat ruimte voor "Pagina n van N". `paginas[i]["getekend"]` legt elk getekend
  blok vast, zodat een test kan nagaan dat niets buiten de marges of over elkaar valt.
- Tests: `tests/test_werkgebieden.py` en `tests/test_werkgebied_werkvoorraad.py` (SQLite) en
  `tests/test_werkgebieden_postgres.py` (het rij-slot, met `ANNOTATIE_TEST_DSN`).

## Begrippen

`begrippen.py`, `begrip_store.py`, `begrip_contracts.py`; het ontwerp staat in PLAN spoor D
(*Elementen, groepen en begrippen*, *Datamodel*).

- **Een slank begrip volgens NL-SBB** (spoor I1, `BegripInhoud`): naam, alternatieve termen,
  definitie, uitleg (`rdfs:comment`), context (de *toelichting*, `skos:scopeNote`) en voorbeelden
  (tekst + oordeel). JAS-duiding, begripstype, geldigheid, eigenschappen, onderbouwing en open vragen
  bestaan niet meer; een oude rij verliest ze bij het lezen (`begrip_store.slank`, `extra="ignore"`).
  **De herkomst kiest niemand**: `begrip_store.met_afgeleid` rekent bij elke schrijfactie herkomst en
  `definitie_door` – een ongewijzigde definitie houdt ze, een nieuwe of andere tekst is `geformuleerd`
  door de `analist`, geen definitie heeft geen herkomst. Letterlijk wordt een definitie alleen door een
  overgenomen brondefinitie (kaartvoorstel of het akkoord op een groep).
- **Eén kader per werkgebied, impliciet.** Een begrip hangt aan een werkgebied, of is generiek (§*Generieke begrippen*);
  het kader heeft geen tabel, alleen een afgeleide IRI (`urn:wa:kader:<werkgebied>`). Begrippen zijn analyse-uitkomsten,
  nooit wettelijke definities; de export zegt dat ook.
- **Tabellen**: `begrippen` (inhoud als JSON, status `concept`/`geaccordeerd`, revisie),
  `begrip_revisies` (per revisie een **volledige kopie** van de inhoud, plus actie en detail – anders
  dan bij de annotatielagen bewaren we de oude inhoud wél) en `begrip_koppelingen`. De audit gaat in
  `werkgebied_audit` (acties `begrip-*`, `koppeling-*`), zodat het werkgebied één tijdlijn heeft.
- **Eén schrijfpad** (`begrip_store._gewijzigd`): eerst de rij-lock op het werkgebied, dan die op het
  begrip – altijd in die volgorde, anders kunnen twee transacties elkaar vastzetten. Daarna
  `verwachte_revisie` → 412, revisie +1, revisiekopie en auditregel. De revisie van het werkgebied gaat
  niet omhoog: die gaat over de scope. Zonder echte wijziging (dezelfde inhoud, een element dat al
  gekoppeld is) gebeurt er niets, ook geen revisie.
- **Elke mutatie behalve accorderen maakt een geaccordeerd begrip weer een concept** – met één
  uitzondering: herkoppelen en bevestigen (fase F1) laten de inhoud staan en het begrip geaccordeerd.
  Een **vervangen** begrip (fase F2) is alleen-lezen: elke mutatie 409 `vervangen`.
- **Een 412 draagt een `melding`**, net als de 409's (`al_primair`, `al_gekoppeld`, `poort`): de
  werkplek toont die tekst waar hij de fout niet zelf afhandelt, in plaats van ruwe JSON. Dat geldt ook
  voor de werkgebieden.
- **Een besluit over koppelingen geeft de stand, niet de kaart** (`begrip_store.koppelstand`): koppelen, wijzigen, losmaken,
  herkoppelen en bevestigen antwoorden met status, revisie, poort en per koppeling de rol en beoordeling, zonder inhoud en
  bewijs. Anders wordt een reeks besluiten kwadratisch in het aantal passages. De werkplek legt de stand over de kaart die
  ze heeft (`metKoppelstand`) en haalt hem alleen opnieuw op bij een nieuwe passage of bewijsstand.
- **Bulk op koppelingen**: `POST …/koppelingen/beoordelen` en `…/koppelingen/bevestigen` (hoogstens 500), in één revisie
  en één auditregel met `koppelingen`, alles of niets. Wat er al zo staat telt niet mee; niets te doen is geen revisie.
- **Per begrip één koppeling per element en rol.** Bij koppelen idempotent; een rol ombuigen naar een
  rol die dat element bij dit begrip al heeft geeft 409 `al_gekoppeld`. Een wijziging die niets
  verandert, is geen revisie.
- **Een koppeling draagt haar bewijsstand** (tekst, klasse, ankers met `bron_hash`, eigenaar, laag,
  snapshot, vindplaats, `element_hash`). Annotatie-elementen worden **hard** verwijderd
  (`annotatie_v2_store.verwijder`/`verwijder_weergave`), dus er is geen foreign key en geen cascade.
  Koppelen kan alleen met elementen uit de inventaris van het werkgebied (`bewijzen`: actueel, niet
  verworpen, binnen de selecties; anders 422 `element_buiten_werkgebied`). Dat vraagt de graaf, en
  gebeurt dus vóór de schrijftransactie.
- **Actualiteit bij het lezen**, uit Postgres zonder graaf: `actueel`, `gewijzigd` (`element_hash`
  over tekst, klasse, subtype en ankers wijkt af, of het element is verouderd; een oordeel van een
  jurist telt niet als wijziging), `verworpen` of `verdwenen`. Plus `annotatie_beoordeeld`
  (lifecycle `human_approved`/`edited`/`published`).
- **Eén primaire duiding per element per werkgebied**: een tweede `duiding` van hetzelfde element
  aan een ander begrip geeft 409 `al_primair` (met de naam van dat begrip). Ook bij het ombuigen van
  een rol. Het werkgebiedslot maakt dit race-vrij; `GET …/begrippen` geeft per element het primaire
  begrip mee (`primair`).
- **De poort** (`begrip_store.poort`) staat bij elke GET als `accorderen: {mag, redenen}`; accorderen
  zonder geeft 409 `{fout: "poort", redenen}`. Voorwaarden: definitie, toelichting (`context`; de gegenereerde
  vindplaatsregel "Komt voor in …" telt niet, `eigen_toelichting`, S6), minstens één aanduidende passage, en elke dragende koppeling (`duiding`/`definitie`, niet
  afgewezen) beoordeeld, actueel en op een door een jurist beoordeelde annotatie. Een voorbeeld is
  geen voorwaarde. Elke analist mag accorderen; de revisie en de audit leggen vast wie en waarom: `Accordering.reden`
  is verplicht (422 zonder), staat in het revisiedetail en de audit, en `accordeer_in` weigert zonder reden. Een akkoord op
  een voorstel zonder reden blijft dus een concept met beoordeelde passages; alleen het opnieuw accorderen na koppelen vanuit
  de review draagt een vaste zin, omdat er dan al een geaccordeerd begrip lag.
- **Verwijderen is echt wissen** (`DELETE …/begrippen/{id}`, `begrip_store.verwijder`/`wis_begrippen`):
  het begrip met zijn revisies, koppelingen, relaties (beide richtingen), voorstellen en kaartruns
  (`BEGRIP_TABELLEN`), en zijn plek bij de deelvragen; een betekenisgroep houdt haar uitkomst en verliest
  alleen `begrip_id`. Eerst zet `_herstel_voorgangers` een vervangen voorganger terug. De audit
  `begrip-verwijderd` blijft. Een vervangen begrip zelf gaat niet weg (409: verwijder de opvolger).
- **Export** (`GET …/begrippen/export?formaat=json|csv|ttl`; Turtle zie §*Begrippen naar de kennisgraaf*): JSON (`begrippen-export-v1`) met de
  volledige begrippen en koppelingen. CSV heeft één rij per koppeling met vindplaats en bron-IRI, zodat
  elke passage terug te vinden is; cellen krijgen dezelfde formuleverdediging als de annotatie-export.
- Tests: `tests/test_begrippen.py` (SQLite, met de acceptatie uit PLAN) en
  `tests/test_begrippen_postgres.py` (de sloten, met `ANNOTATIE_TEST_DSN`).

## Voorstellen van Lex

`begrippen_runs.py`, `begrippen_run_store.py`, `begrip_manifest.py`; het ontwerp is ADR-004 en
PLAN spoor D (*Verwerking*). De keten zelf draait in graph-qa (`agent/begrippen_run.py`); de api
bouwt de invoer, toetst en bewaart de uitkomst, en legt de besluiten vast.

- **Het manifest** (`begrip_manifest.bouw`) komt uit dezelfde inventaris als de tab Elementen
  (`inventaris_met_bronbomen`), dus met contextbronnen: een definitie buiten de analyseselectie
  hoort juist mee. Vorm = `Bron`/`Formulering` van `begrippen_pipeline.model`; `aanhef` is de tekst
  van de directe ouder (de houder: "Deze wet verstaat onder:"), `label` de vindplaats. Een element met
  meer dan één anker, of dat verouderd is, staat in `overgeslagen` met reden – nooit stil weg.
- **`manifest_id` rekent zoals `Manifest.id`.** Twee diensten, dus geen import:
  `docs/wetsanalyse/referentieset-begrippen/manifest-id.vectoren.json` legt id's en veldnamen vast,
  en zowel `tests/test_begrippen_runs.py` als graph-qa `tests/test_begrippen_manifest_drift.py`
  toetsen ertegen. Wijzigt het model van de keten, laat de vectoren dan door de keten herberekenen.
- **De onderzoeksstand** (`begrip_onderzoek.py`, spoor M): naast het manifest de context die de keten
  moet lezen – eerst een begripsbepaling die een formuleringstekst als term definieert (`gedefinieerd`; ook in een
  regeling die alleen via een verwijzing in beeld komt, want de keten neemt haar letterlijk over en dan is er geen model
  nodig), dan leden van hetzelfde artikel, begripsbepalingen en kwalificaties met een
  formuleringstekst, verwijzingen één stap vanaf de ankers (`samenhang._uitgaand`; een andere regeling
  via `resolve`), contextselecties – in die prioriteit, binnen `MAX_*`, met `ontbrekend` (`budget`,
  `niet_in_graaf`, `onbereikbaar`) en vergelijkingsbegrippen. `onderzoek_id` rekent zoals `Onderzoek.id`, met
  `ontbrekend` erin (het stuurt `CONTEXT_NIET_ONDERZOCHT` en de prompt: na een storing is de run dus verouderd)
  (`onderzoek-id.vectoren.json`, beide kanten). Kolommen `begrippen_runs.onderzoek(_id)`; kaartruns
  dragen het in hun `invoer`. De garanties gelden over manifest + onderzoek
  (`begrippen_verdieping.fragmentruimte`).
- **Runs zijn idempotent op (werkgebied, manifest, onderzoek)**: een andere onderzoeksstand is een nieuwe
  run, en `laatste` meldt dan `verouderd`. Een tweede start geeft de bestaande run (200,
  `nieuw: false`). Een run in `wacht`/`loopt` die `VERLOPEN` (5 min) niets van zich liet horen, telt
  als `mislukt` en mag opnieuw; graph-qa meldt `…/loopt` bij de start. Een onvolledige inventaris of
  minder dan twee passages: 409 met melding, geen run.
- **De uitkomst wordt getoetst** (`PUT …/uitkomst`): zelfde `manifest_id`, en elk genoemd element-id
  staat in het manifest (422 `onbekend_element`). Dezelfde uitkomst nog eens is idempotent; een andere
  op een klare run 409. `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor graph-qa; de BFF laat ze niet
  door.
- **Een besluit hoort bij de groep** (`betekenisgroepen`, sleutel werkgebied + groep-id = de inhoudshash
  van de keten). Komt dezelfde groep in een latere run terug, dan blijft een afwijzing staan.
- **Akkoord** (`POST groepen/akkoord`, fase D) maakt één begrip met de gekozen leden als
  `duiding` – meer groepen is combineren, een deel van de leden splitsen. De letterlijke
  brondefinitie gaat alleen mee als er precies één is (herkomst `letterlijk`). Zonder kaart komt de
  context uit de vindplaatsen (`context_uit`, de tweeling van graph-qa `kaart._context`; een
  drift-test in `test_begrippen_akkoord.py` bewaakt de zin). Een passage buiten de gekozen groepen mag
  mee (het antwoord *samen* op een twijfelvraag), mits ze in het manifest van de laatste klare run
  staat; `groep_ids` mag dan leeg zijn. Uit elke gekozen groep moet minstens één eigen passage mee.
  `lijkt_op` per groep: begrippen die een passage delen of de voorgestelde naam als naam of
  alternatieve term dragen.
  Het oordeel van de jurist zit erin, in **één transactie** (`akkoord`; een los *overnemen* zonder oordeel bestaat
  sinds H3 niet meer): begrip, koppelingen met `beoordeling: akkoord`, accorderen als de poort
  het toelaat (`begrip_store.accordeer_in`), groepsbesluit en – met `kandidaat_id` of `kandidaat_ids`
  (spoor H4: alle vragen tussen de gekozen passages van een term, ≤ 500) – de twijfelvragen als *samen*.
  Een onbekende vraag is 404; een vraag waarvan een kant niet bij de gekozen passages hoort 422
  `vraag_buiten_keuze`. Antwoord `{begrip, geaccordeerd, poort}`: lukt accorderen niet, dan blijft het een
  concept en noemt de poort wat er openstaat. Met `aanpassing` wijzigt de jurist naam, definitie,
  context of alternatieve termen; een gewijzigde definitie wordt `geformuleerd` (een herkomst kiezen kan
  niet meer, spoor I1). Bij combineren kiest `definitie_van` welke
  groep zijn definitie en kaart meegeeft. Een tweede akkoord geeft 409 `al_besloten` met
  `begrippen: {groep: begrip}`.
- **Splitsen laat de rest staan.** Worden niet alle leden van een groep een begrip, dan blijft de
  groep open met de overige leden (kolom `afgehandeld`); pas als alle leden zijn afgehandeld is ze
  `overgenomen` of `gekoppeld`. Een afgehandelde passage nog eens kiezen geeft 409.
- **Koppelen** aan een bestaand begrip (`POST groepen/{id}/koppelen`) gaat langs hetzelfde pad, in
  één transactie; met `akkoord: true` zijn de koppelingen beoordeeld en wordt een geaccordeerd begrip
  opnieuw geaccordeerd als de poort het toelaat.
- `GET …/groepen` geeft per open groep **`poort_vooraf`**: de poort op de inhoud en de koppelingen
  zoals een akkoord ze nu zou maken. Per passage staat de stand van de annotatie nú
  (`lifecycle`, `annotatie_beoordeeld`), want het manifest is de stand bij de run.
- **Sloten**: altijd eerst het werkgebied, dan de groepen, dan het begrip. De `*_in`-varianten in
  `begrip_store` (`maak_in`, `koppel_in`, `accordeer_in`, `_gewijzigd_in`) draaien in de transactie
  van de aanroeper.
- Besluiten en runs komen in `werkgebied_audit` (`begrippen-run-gestart`, `begrippen-voorgesteld`,
  `groep-*` – waaronder `groep-akkoord` met `geaccordeerd` en de aangepaste velden –,
  `vraag-beantwoord`). Een besluit wijzigt nooit annotaties.

**De verdieping** (`begrippen_verdieping.py`, fase C): het model op twijfelparen en kaarten, bovenop de
laatste klare run. graph-qa rekent (`agent/begrippen_verdieping.py`), de api bewaart en toetst.

- `GET …/verdieping` is de **werkvoorraad**: twijfelvragen (behalve `Z-RELATIE-GAAT-VOOR`) en groepen
  zonder definitie, min wat in een klare batch zit; plus de klare batches, een schatting (gemeten
  tokens per item, per soort, over de laatste 20 batches van de gebruiker, met `hoog` als bovenkant; anders `null`) en het budget. `aantal`
  is wat een `bevestiging` (`soort: "begrippen_verdiepen"`) noemt.
- `PUT …/begrippen-runs/{run}/batches/{batch_id}` bewaart **één afgeronde batch** (`begrippen_batches`;
  alleen klare batches staan erin, dus een herstart doet de rest). Idempotent op (run, batch-id) +
  inhoud; een andere inhoud onder dezelfde id 409. Een vraagbatch noemt alleen twijfelvragen van de run.
- `PUT …/begrippen-runs/{run}/verdieping` zet de uitkomst: de groepen na hergroeperen (ook nieuwe,
  `door: model`) met hun kaart, de oordelen en de vragen die open blijven, in `begrippen_runs.verdieping`.
  Idempotent op inhoud; daarna geen batches meer.
- **De garanties toetst de api zelf** tegen het manifest (`garanties`, dezelfde codes als graph-qa
  `toetsen.garanties`): fragment-id volgt uit bron en offsets (`fragment_id`, zelfde hash), de tekst
  staat letterlijk op de offsets, een letterlijke definitie staat in haar bron, een samengestelde is
  precies haar fragmenten (`SCHEIDING`). Anders 422 `garantie` en wordt er niets bewaard.
- `GET …/groepen` geeft na de verdieping de groepen ná hergroeperen, plus elke groep van de keten met
  een besluit; per groep `door` en `kaart`, en bovenaan `verdieping` (open vragen, oordelen, model).
  `lijkt_op` kijkt ook naar de alternatieve termen van de kaart.
- **Overnemen** vult het begrip uit de kaart: alternatieve termen, context en de definitie met haar
  herkomst; de bron draagt het begrip via zijn passages (`dct:source`). Een definitie gaat alleen mee als er precies één is.
- Tests: `tests/test_begrippen_verdieping.py`.

## Lex naast de kaart

`begrip_voorstellen.py`, `begrip_voorstel_store.py`, `begrip_voorstel_contracts.py`; PLAN spoor D, fase E.
Vijf acties op één begrip: `brondefinitie` (een graafquery, geen model), `scherper`, `uitleg` (spoor I2: de
uitleg in B1, alleen op een definitie – anders 409 `geen_definitie`, net als `voorbeelden`), `betekenisverschil`
(met een ander begrip, `ander_begrip_id`) en `voorbeelden`. graph-qa rekent, de api legt vast en toetst.

- **Een voorstel is geen wijziging.** `begrip_voorstellen` is een eigen tabel; Lex schrijft nooit in het
  begrip. `POST …/voorstellen/{id}/overnemen` loopt door `begrip_store._gewijzigd_in` (revisie, kopie,
  audit `voorstel-overgenomen` met voorstel-id, actie en model) en zet het besluit in dezelfde
  transactie. Sloten: werkgebied → begrip → voorstel.
- **Niets stil overschreven.** Een definitievoorstel bewaart `basis` (de definitie en herkomst bij het
  starten). Wijkt het begrip daarvan af, dan 409 `voorstel_verouderd` met `toen`, `nu` en `voorstel`;
  `GET …/voorstellen` meldt het vooraf als `verouderd`. Vervangen kan dan alleen bewust: met
  `nu_gezien` = de definitie die de analist naast het voorstel zag (klopt die niet meer: weer 409). Uitleg, toelichting en voorbeelden worden
  toegevoegd, nooit vervangen; wat er al staat, geeft geen revisie (wel het besluit).
- **Het bewijs blijft na overnemen** (spoor M): `GET` van een begrip draagt `definitie_onderbouwing`,
  afgeleid uit het voorstel achter de revisie die de huidige definitie zette (fragmenten met rol
  `ondersteunend`, vindplaats, duiding, `onderzoek_id`). Paste de analist de definitie aan, bij het overnemen of later,
  dan blijft ze staan met `aangepast: true` (S8), en de projectie noemt die bronnen dan niet meer als onderbouwing;
  `null` als er nooit een voorstel of groep achter zat.
  Langs overnemen en akkoord op een groep staat de onderbouwing bevroren in het revisiedetail van het
  aanmaken (`detail.onderbouwing`: `groep_id`, `run_id`, de kaart of het letterlijke voorstel), zodat een
  latere verdieping haar niet verandert.
  Een definitievoorstel bewaart de `duiding`, een voorbeeld `soort_voorbeeld`, `toetst` en `kenmerk`
  (in `waarde`), en `door.onderzoek` zegt wat Lex onderzocht.
- **Herkomst gaat mee.** `BegripInhoud.definitie_door` (`lex` | `analist` | leeg) zet de api, nooit de
  client (`begrip_store.met_afgeleid`): een ongewijzigde definitie houdt wie haar voorstelde, een nieuwe of
  andere tekst is van de analist. Overnemen zet `lex` en de herkomst van het voorstel; met `aanpassing`
  wordt het `geformuleerd` + `analist`. Het akkoordpad van fase D zet `lex` (of `analist` bij een aanpassing).
  Het afgeleide veld telt niet als gewijzigd veld in de revisie.
- **De run**: `POST …/kaart-runs` legt de invoer vast (begrip op zijn revisie, de actuele dragende
  passages die in het manifest staan, het manifest, de selecties). Idempotent op (actie, revisie van
  begrip en ander begrip, manifest): een lopende run, of een klare met open voorstellen, komt terug;
  anders een nieuwe. `voorbeelden` zonder definitie en `scherper`/`betekenisverschil` zonder passages: 409.
- **De garanties toetst de api zelf** (`begrippen_verdieping.definitie_fouten`/`fragment_fouten`):
  fragmenten letterlijk in het manifest, samengesteld = precies de fragmenten, letterlijk = in de bron.
  Een brondefinitie buiten het manifest wordt tegen de bronboom uit de graaf getoetst. Een veld dat
  niet bij de actie hoort: 422 `VELD_HOORT_NIET_BIJ_ACTIE`. Een geformuleerde definitie is nooit groen.
- `GET …/voorstellen` geeft ook per model-actie een schatting (mediaan tokens van de laatste 20 klare
  runs van de gebruiker) en het budget, voor de knoppen.
- Tests: `tests/test_begrip_voorstellen.py`.

## Onderhoud van begrippen

`begrip_onderhoud.py`, `begrip_onderhoud_store.py`, `begrip_onderhoud_contracts.py`; PLAN spoor D, fase F1.
Acceptatie: *een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand blijft.*

- **Twee bronnen van verandering.** `begrip_store.actualiteit` ziet alleen Postgres: een gewijzigde,
  verworpen, verdwenen of door herannotatie verouderde annotatie. Een nieuwe wettekst zonder herannotatie
  ziet hij niet. `GET …/herbeoordelingen` (`?begrip_id=`) vraagt daarom ook de bronboom
  (`inventaris_met_bronbomen`) en zet per anker `bron_signalen`: `ongewijzigd`, `gewijzigd` (met
  `fragment_gelijk`: staat het gemarkeerde fragment nog letterlijk op zijn offsets), `weg` of `onbekend`
  (regeling niet op te halen – een open punt, nooit "ongewijzigd").
- **Het bewijs verandert nooit.** Een koppeling leest als `bewijs` de laatst bevestigde stand
  (`begrip_store.bevestigde_stand`, ook in de export en `wa:passage`), en als `bewijs_bij_koppelen` de stand van toen; de
  rij zelf blijft ongemoeid (N2). Per geraakte koppeling: `toen` (die bevestigde stand), `nu` (het element),
  `bron`, `redenen` (zinnen voor de werkplek), `opvolgers`, `opnieuw_annoteren` en `acties`.
- **Opvolgers** (`opvolgers`, zuiver): herannotatie maakt een nieuw element met een nieuw id. Kandidaat =
  actueel element op een bronnode van de oude ankers of met dezelfde eigenaar; signalen met richting
  (klasse, tekst, plek, al elders primair). Geen score: de volgorde is plek → tekst → positie.
- **Herkoppelen** (`POST …/koppelingen/{k}/herkoppelen {verwachte_revisie, element_id}`): nieuwe koppeling
  met de rol van de oude en `beoordeling: akkoord` (de analist zag toen en nu), de oude krijgt
  `verwijderd` + `vervangen_door`. De nieuwe draagt bij het lezen `vervangt` met het oude bewijs. Dezelfde
  passage: 422 `zelfde_passage`; buiten het werkgebied 422; al primair elders 409 `al_primair`.
- **Bevestigen** (`POST …/bevestigen`): voegt aan `bevestigingen` een stand toe (`element_hash`, ankers
  met de bron-hash van nu); daarna rekent de actualiteit daartegen (`referentie_hash`). Alleen als de
  annotatie bestaat, niet verworpen en niet verouderd is (422 `niet_te_bevestigen`), en elk fragment
  letterlijk op zijn plek staat (422 `fragment_weg`). Niets te bevestigen: geen revisie.
- **Geaccordeerd blijft geaccordeerd** bij herkoppelen en bevestigen (besloten 16 okt 2026). Wat dan nog
  openstaat, noemt `aandachtspunten` (ook een dragende annotatie die een jurist nog niet beoordeelde).
- **Dekking** (`GET …/dekking`): elk element van de inventaris één keer, voorrang `gekoppeld` (dragend
  aan een geaccordeerd begrip) → `buiten_behandeling` → `voorstel` (concept-begrip of open groep van de
  laatste klare run) → `te_verwerken`; plus `nieuw_sinds_run` (niet in manifest of `overgeslagen` van die
  run). `POST …/dekking/buiten-behandeling {element_ids, reden}` (reden verplicht, idempotent, tabel
  `werkgebied_element_besluiten`) en `DELETE …/buiten-behandeling/{element_id}` (soft). Audit
  `element-buiten-behandeling` / `element-in-behandeling`; geen revisie, het raakt de scope niet.
- Tests: `tests/test_begrip_onderhoud.py`.

## Begripsrelaties en opvolging

`begrip_relaties.py`, `begrip_relatie_store.py`, `begrip_relatie_contracts.py`; PLAN spoor D, fase F2.

- **Tabel `begrip_relaties`**: van, naar, `type` (`kwalificatie`, `inclusie`, `uitsluiting`, `hierarchie`,
  `verwant`, `opvolging`), `herkomst` (`lex` | `analist` | `systeem`), bewijs, toelichting, `beoordeling`
  (`akkoord` | `afgewezen`), `stand_van`/`stand_naar` (hash van definitie + context bij het vastleggen),
  soft delete. Audit `relatie-*`, `begrip-vervangen`, `begrip-opgevolgd`, `begrip-gecombineerd`,
  `begrip-hersteld`. Geen platslaan tot "verwant": de typen houden hun juridische betekenis.
- **Voorstellen worden afgeleid** (`_voorstellen`): een relatie tussen twee elementen uit de laatste klare
  run (`uitkomst.relaties`), die elk primair een ander, niet vervangen begrip aanduiden. Id
  `R<hash(van, naar, type)>`. Lezen schrijft niets; `POST …/relaties {voorstel_id}` legt vast (herkomst
  `lex`), `POST …/relaties/voorstellen/{id}/afwijzen {reden}` schrijft een afgewezen rij, en die sleutel
  komt niet terug. Een voorstel dat er niet meer is: 409 `voorstel_weg`.
- **Zelf vastleggen**: `{van_begrip, naar_begrip, type}`; `verwant` vraagt een toelichting (422);
  `opvolging` kan niet (422); naar zichzelf 422 `zelfde_begrip`; dezelfde actieve relatie 409
  `al_vastgelegd`; een vervangen begrip 409 `vervangen`. `DELETE …/relaties/{id}` (opvolging niet: 409).
- **Doorwerking** (`doorwerking`): wijkt de stand van één kant af van wat bij het vastleggen gold, dan staat
  de relatie bij het begrip aan de andere kant in `GET …/herbeoordelingen` (`relaties`), en in
  `GET …/relaties` als `veranderd`. `POST …/relaties/{id}/bevestigen` legt de stand van nu vast.
- **Nieuwe betekenis** (`POST …/begrippen/{b}/nieuwe-betekenis {verwachte_revisie, reden}`), één
  transactie: het begrip wordt `vervangen`, een nieuw concept krijgt de inhoud en alle niet-afgewezen
  koppelingen (met hun bewaarde bewijs, opnieuw `open`), plus een relatie `opvolging` met de vorige status
  in het bewijs. **Combineren** (`POST …/begrippen/{b}/combineren {verwachte_revisie, ander_begrip_id,
  ander_revisie, reden}`): de ander wordt vervangen, `b` krijgt diens passages (open) en naam als
  alternatieve term. Beide begrippen dragen hun revisie (412).
- **Een vervangen begrip** houdt geen primaire duiding vast (`_toets_primair`, `primaire_duidingen`),
  telt niet in de dekking en de herbeoordeling, en staat niet bij `lijkt_op`. `GET` van een begrip geeft
  `vervangen_door` en `vervangt`. **De opvolger verwijderen** zet het vervangen begrip terug op zijn vorige
  status (`_herstel_voorgangers`, revisie `begrip-hersteld`) en neemt zijn relaties mee.
- Tests: `tests/test_begrip_relaties.py`.

## Begrippen naar de kennisgraaf

`begrip_projectie.py`, `shapes/`; PLAN spoor D, fase F3; ADR-003 (NL-SBB is het datacontract).

- **TOOI in de export** (spoor I6): het kader krijgt `dct:subject <thema>`, en in de Turtle-export krijgt elk
  brondocument `dct:publisher <TOOI-organisatie>` van zijn regeling (`uitgevers`, uit
  `bwb:eerstverantwoordelijkeOrganisatie`, best-effort zoals `paginas`).
- **Per werkgebied één named graph** `urn:wa:graph:werkgebied:<id>`, register
  `urn:wa:graph:register:begrippen` (`wa:werkgebiedId`, `wa:projectieHash`, `wa:inGraaf`). Kader =
  `skos:ConceptScheme` met `dct:title` en de toelichting "analyse-uitkomst, geen wettelijke definitie";
  begrip = `skos:Concept` (`prefLabel`, `altLabel`, `definition`, `rdfs:comment` = uitleg, `scopeNote` =
  context, `example` = voorbeelden met oordeel *wel*; *niet* is `wa:tegenvoorbeeld`, *onzeker*
  `wa:grensgeval`; de bronnen van de overgenomen definitie zijn ook `dct:source`, met `wa:rol
  "definitieonderbouwing"` – een alleen onderzochte bron niet, `inScheme`, `dct:source` → `foaf:Document` met
  vindplaats en `dct:title`, de vindplaats of bij een bron zonder passage de naam uit de IRI). Eigen predicaten onder `urn:wa-ns:`: status, revisie, herkomst en `definitieDoor`,
  JAS-klasse (IRI uit de vocabulaire), geaccordeerd-op, en per koppeling (`urn:wa:koppeling:<id>`) rol,
  beoordeling, element (`urn:jas:element:<id>`), `elementHash` (de bewijsstand, of de laatste bevestiging)
  en de bronnode. **Alle begrippen met hun status**, ook concepten en vervangen begrippen.
- **Relaties houden hun type**: `wa:kwalificeert`, `wa:omvat`, `wa:omvatNiet`, `wa:heeftSoort`,
  `wa:verwantMet`, plus een `wa:Begripsrelatie` met herkomst. Alleen een hiërarchie krijgt ook
  `isothes:broaderGeneric` (de soort → de bredere term); opvolging is `dct:isReplacedBy`/`dct:replaces`.
  Alleen relaties met beoordeling *akkoord*.
- **Postgres is de waarheid.** `invoer(conn, werkgebied_id)` leest alles wat de graph draagt;
  `bouw_graaf` is zuiver en de projectie hangt niet van de brongraaf af. `invoer_hash` is de stand in
  het register. Geen personen, en geen subject onder `urn:bwb:` (een bronnode is alleen object).
- **Direct na de commit**: `werkgebied_store._audit` noteert het werkgebied op de verbinding
  (`db.noteer_na_commit`); het `commit`-event van de engine geeft het aan `begrip_projectie.na_mutatie`
  (`db.na_commit_haak`), een rollback gooit het weg. Elke audited werkgebiedmutatie projecteert dus,
  zonder dat een schrijfpad eraan hoeft te denken. Het event valt **vóór** de COMMIT: `projecteer`
  neemt daarom eerst een leesslot (`FOR SHARE`) op het werkgebied, dat de schrijver afwacht
  (`test_begrippen_postgres.py` bewijst dat). Wat dit proces al zo schreef, slaat hij over.
- **De lus** (`graaf_projectie_v2.lus`, zelfde interval) roept `begrip_projectie.reconcile` aan met een
  eigen vangnet: projecteert wat afwijkt van de hash in het register of wiens graph ontbreekt, en haalt
  graphs weg van verwijderde of lege werkgebieden.
- **Conformiteit** (`conformiteit`, `GET …/begrippen/conformiteit`): diagnostisch, nooit in het
  schrijfpad. Twee lagen: `nl_sbb` (het vastgepinde profiel `shapes/nl-sbb-1.0.0.ttl`, letterlijk uit
  `geonovum/NL-SBB`, CC-BY 4.0; herkomst en hash in `shapes/BRON.md`) en `eigen`
  (`shapes/begrippen-wa.ttl`: herkomst van de definitie, geaccordeerd-op, koppeling → element +
  hash, bron bij een dragende passage, schone wettekst). Een begrip is **conform** als het profiel geen
  Violation geeft op het begrip of zijn bronnen; waarschuwingen en eigen meldingen staan erbij. Zonder
  pyshacl `conform: null`, nooit `true`.
- **Turtle-export** (`GET …/begrippen/export?formaat=ttl[&inclusief=alle]`): dezelfde `bouw_graaf`,
  standaard alleen geaccordeerde begrippen (en relaties tussen twee die meegaan), met `dct:conformsTo`
  NL-SBB, `wa:nlSbbVersie`, `prov:generatedAtTime` en per begrip `wa:nlSbbConform`. `foaf:page` komt
  best-effort uit de brongraaf (`owl:sameAs` = de jci, anders `bwb:bronUrl`); zonder graaf ontbreekt
  hij, de bron-IRI staat er altijd.
- **`GET …/begrippen/samenhang`**: begrippen, koppelingen (rol, beoordeling, actualiteit) en relaties
  (vastgelegd en voorgesteld) voor de samenhangsgraaf van de werkplek, uit Postgres.
- **Graafcontrole** (`graafcontrole.controleer` → `begrippen`): achterstand (hash wijkt af), afwijkingen
  (graph ontbreekt, inhoud niet isomorf), verweesde graphs, de invariant en – met SHACL – het aantal
  niet-conforme begrippen (telt niet mee voor `in_orde`: een concept zonder definitie is gewoon nog niet af).
- **Een nieuwe NL-SBB-versie** is een bewuste overstap: nieuw shapesbestand, nieuwe hash in de test,
  `NL_SBB_VERSIE` en `NL_SBB` mee.
- Tests: `tests/test_begrip_projectie.py` en het slot in `tests/test_begrippen_postgres.py`.

## Generieke begrippen

`begrip_store.py`, `begrip_relatie_store.py`, `begrippen_overzicht.py`, `begrip_projectie.py`; besluit in ADR-006.

- **Eén begrip, overal gebruikt.** `begrippen.werkgebied_id` leeg = generiek, in `urn:wa:kader:generiek`, met `ontstaan_in`.
  `werkgebied_begrippen` is het gebruik (`gezien_revisie`, soft delete). `in_werkgebied` is de ene plek die zegt welke
  begrippen een werkgebied in beeld heeft. Passages blijven per werkgebied; `lijst`, `haal` en `primair` gelden per
  werkgebied, `haal_generiek` geeft ze allemaal met `gebruik`.
- **Generiek maken** (`POST …/begrippen/{b}/generiek-maken`): alleen geaccordeerd (409 `niet_geaccordeerd`), dezelfde
  voorkeursterm één keer (409 `al_generiek`). Id en IRI blijven; het werkgebied gaat het gebruiken.
- **De inhoud wijzig je alleen op `/v1/begrippen/{id}`** (`PATCH`, `accorderen`, `heropenen`, `nieuwe-betekenis`, `DELETE`).
  Vanuit een werkgebied: 409 `generiek`. `_gewijzigd_in` met `werkgebied_id=None` neemt geen werkgebiedslot en schrijft de
  audit bij elk gebruikend werkgebied. `passage=True` (koppelen, wijzigen, ontkoppelen, herkoppelen, bevestigen) mag wel
  vanuit een werkgebied en laat de status staan: één analyse zet het begrip niet voor iedereen terug.
- **Gebruik**: `POST …/begrippen/gebruik {begrip_id}` (idempotent), `DELETE …/gebruik/{b}` (de passages hier gaan los).
  Een werkgebied wissen laat het begrip staan. Verwijderen kan niet zolang het gebruikt wordt (409 `in_gebruik`).
- **Doorwerking**: `GET …/herbeoordelingen` draagt `generiek`: wat veranderde sinds `gezien_revisie`, met toen en nu uit
  `begrip_revisies` (`generiek_veranderd`). Een nieuwe revisie door een passage elders telt niet. `POST …/gebruik/{b}/bevestigen`.
- **Opvolging**: `POST /v1/begrippen/{id}/nieuwe-betekenis` geeft een concept zonder passages (relatie zonder werkgebied);
  elk werkgebied neemt hem zelf over met `POST …/gebruik/{b}/opvolger`, met zijn passages opnieuw open.
- **Combineren**: `POST …/begrippen/{b}/combineren-generiek {verwachte_revisie, generiek_id, reden}`: het lokale begrip wordt
  vervangen, de passages gaan mee, de inhoud van het generieke begrip verandert niet.
- **De graaf**: de id `generiek` is één extra graph (`urn:wa:graph:werkgebied:generiek`) met de passages uit alle
  werkgebieden; een werkgebied noemt `wa:gebruiktBegrip`. `GET /v1/begrippen/export` en `/conformiteit`.
- **Lex**: `lijkt_op` kijkt ook naar generieke begrippen die dit werkgebied nog niet gebruikt (`generieke_buiten`), en
  koppelen aan zo'n begrip is het gaan gebruiken. Lex maakt niets generiek.
- Tests: `tests/test_begrippen_generiek.py`.

## Begrippen lezen

`begrippen_overzicht.py`; PLAN spoor D, fase F4. Alleen lezend, uit Postgres, over alle actieve
werkgebieden. Een verwijderd begrip of werkgebied is gewist en bestaat hier dus niet.

- **`GET /v1/begrippen`** (`q`, `status` herhaalbaar, `werkgebied_id`, `eerst`, `limit`, `offset`) is het
  overzicht van de webapp. Zoeken gebeurt in Python (de inhoud is JSON, de tests draaien op SQLite):
  zonder hoofdletters en diakrieten, rangorde exacte naam → exacte term → in de naam → in een term →
  in de definitie → alle woorden ergens; daarna het werkgebied `eerst`, dan geaccordeerd → concept →
  vervangen. Een rij noemt het werkgebied, `vervangen_door`, `aantal_dragend` en bij een geaccordeerd begrip
  `herbeoordelen`: het aantal dragende passages dat sinds het accorderen veranderde (de actualiteit uit
  Postgres, zoals de aandachtspunten van de kaart; een nieuwe wettekst zonder herannotatie ziet alleen
  `…/herbeoordelingen`). Ook in `verifieer`, zodat Lex het kan noemen. `mijn=true` (een route-parameter,
  geen veld van `BegripZoekvraag`: graph-qa heeft het niet nodig) geeft alleen begrippen met een revisie
  van deze gebruiker; `per_status` telt met dezelfde filters zonder het statusfilter, voor de tellers op
  de knoppen. Het contract is
  `BegripZoekvraag`; graph-qa (`search_begrippen`) vraagt niets wat daar niet in staat.
- **Lex zoekt in de graaf, de api bevestigt** (`POST /v1/begrippen/verifieer {ids, werkgebieden}`), net
  als bij `search_annotaties`: per id de rij van nu of `null`, en per werkgebied de `projectie_hash`
  die `begrip_projectie.invoer_hash` nu zou geven. Wijkt die af van `wa:projectieHash` op het kader in
  de graaf, dan loopt de projectie achter en meldt Lex dat zijn resultaat onvolledig kan zijn.
- **`GET /v1/begrippen/{id}`**: `{werkgebied: {id, naam}, begrip: <kaart>, relaties: <akkoord>}`, zonder
  dat de vrager het werkgebied hoeft te kennen (`get_begrip` van Lex, de werkplek).
- Tests: `tests/test_begrippen_overzicht.py`.

## Bronnen vinden met Lex

`bronnen_runs.py`, `bronnen_run_store.py`, `bronnen_run_contracts.py`; het ontwerp staat in PLAN
spoor D (*Bronnen vinden voor een werkgebied*, fase A). De methoden draaien in graph-qa; de api legt de
invoer vast, toetst en bewaart de kandidaten, en legt de besluiten vast.

- **De invoer is de selectie** (`invoer_van`): kern = bronselecties met rol *analyseren*, context = de
  rest, plus naam en analysevraag. Zonder kern én zonder analysevraag: 409 `geen_vertrekpunt`.
  **Idempotent op (werkgebied, invoer)** (`invoer_id`, een inhoudshash, mét het dossier); `laatste` meldt
  `verouderd` als de selectie, de analysevraag of het dossier intussen veranderde. graph-qa stuurt bij het
  starten de **`zoekversie`** mee (een hash van zijn zoekcode, `bronnen_run.ZOEKVERSIE`): die gaat in de invoer en
  dus in de identiteit van de run, zodat nieuwe zoekcode opnieuw zoekt, ook bij een gelijk werkgebied (anders bleef
  de uitkomst van de oude code staan, ook na *Verder onderzoeken*). `verouderd` telt de versie niet: het zegt alleen
  dat het werkgebied veranderde. De zoekdekking van de bronselectie meldt de versie van de laatste run. Een klare run wordt alleen
  hergebruikt als hij de nieuwste is (na A → B → A zoekt Lex opnieuw), en de uitkomst van een ingehaalde run
  wordt vastgelegd zonder de kandidaten te raken. Een run die `VERLOPEN` (5 min) stil was, telt als `mislukt`
  en mag opnieuw.
- **Wat telt, is de laatste klare run** (`basis_run_id`): een open voorstel dat die run niet vond, is
  `vervallen` (vlag in `GET …/kandidaten`) en staat niet in de bronselectie; een besluit (opgenomen,
  uitgesloten) vervalt nooit. Zo blijven na een dossierwijziging geen oude voorstellen hangen.
- **Eén kandidaat per bepaling**: sleutel (werkgebied, `kandidaat_id(bron_iri)`), over runs heen.
  Vinden meer methoden haar, dan groeit het bewijs (`methode`, `vanuit`, `detail`) en wint de sterkste
  rol (`kern` > `afhankelijkheid` > `aanverwant`). Wat bij `PUT …/uitkomst` al in de selectie staat,
  wordt geen kandidaat.
- **Het besluit hoort bij de kandidaat**: een latere run werkt bewijs, rol en `run_id` bij en laat de
  status staan. **Een uitgesloten kandidaat komt dus niet terug** (de acceptatie van L1). Uitsluiten
  vraagt een reden (422 zonder). Besluiten lopen alleen via de bronselectie per deelvraag
  (`POST …/bronselectie/{deelvraag}/kandidaten/{id}`; zonder deelvragen `analysevraag`, dan werkgebiedbreed);
  de werkgebiedbrede routes `…/kandidaten/{id}/{opnemen,later,uitsluiten,heropenen}` en de status `later` zijn
  weg (`reconcile_schema` maakt van een oude rij een voorstel). Uitsluiten en heropenen nemen het slot op het
  werkgebied maar dragen geen revisie: ze wijzigen de scope niet.
- **Opnemen** wijzigt de scope en draagt daarom `verwachte_revisie` (412). De api verifieert de bron
  zoals bij zelf opnemen en schrijft selectie én kandidaatstatus in één transactie
  (`werkgebied_store.voeg_bron_toe(..., binnen=…)`). Rol: *analyseren* bij een kernkandidaat, anders
  *context*, tenzij de analist kiest. Haalt de analist die selectie weer weg
  (`verwijder_bron`), dan wordt de kandidaat in dezelfde transactie weer `voorgesteld`.
- `GET …/kandidaten` geeft de laatste run en de kandidaten (sterkste rol eerst), met `vervallen` (niet
  gevonden door de laatste klare run) en `in_selectie` (intussen met de hand opgenomen); de werkplek leest
  het alleen (de bronverkenner). `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor
  graph-qa.
- Het artefact van een bronnenbeurt is `{soort: "bronnen", ref: {werkgebied_id, run_id}}`.
- Tests: `tests/test_bronnen_runs.py` (SQLite) en het slot in `tests/test_werkgebieden_postgres.py`.

## Deelvragen

`werkgebied_deelvragen.py`, routes in `werkgebieden.py`; open keuze 4 is besloten op **optioneel**: een
werkgebied zonder deelvragen werkt zoals altijd.

- **Tabellen** `werkgebied_deelvragen` (vraag, volgorde, `status` `actief` | `voorgesteld` | `afgewezen` |
  `vervangen`, `herkomst` `analist` | `lex`, reden, `vervangt`, soft delete) en `werkgebied_deelvraag_koppelingen` (een set per
  deelvraag, `soort` `bron` | `begrip`, zonder foreign key; wat niet meer bestaat valt bij het lezen weg).
  `GET /v1/werkgebieden/{id}` draagt `deelvragen` (actief en voorgesteld, met hun geldige koppelingen).
- **Een actieve deelvraag hoort bij de scope**: toevoegen en weghalen (`POST …/deelvragen/samen`, de bewerkstand in
  één revisie) en wijzigen (`PATCH …/deelvragen/{id}`: tekst, volgorde, overnemen met `status: actief`, afwijzen met
  verplichte reden) lopen door `werkgebied_store._gewijzigd` (revisie, 412, audit `deelvraag-*`). Dezelfde vraag nog
  eens (genormaliseerd: hoofdletters, diakrieten, leestekens) geeft 409 `al_gesteld`. De koppelingen zet geen client
  zelf: ze ontstaan bij het opnemen van een kandidaat (`koppel_bron_in`) en gaan mee bij een vervanging.
- **Voorstellen van Lex** (`POST …/deelvragen/voorstellen {vragen, model}`, graph-qa): geen revisie, alleen
  het slot en een auditregel `deelvragen-voorgesteld`. Wat er al staat, is afgewezen of weggehaald, komt er
  niet bij (`overgeslagen` met de reden).
- **Een verbetering vervangt** (F3d). Met `vervangt: <id>` (herformuleren of splitsen door de deelvragen-agent)
  moet dat een actieve deelvraag zijn (anders 422 `vervangt_onbekend`); elk voorstel draagt de kolom.
  Overnemen (`status: actief`) zet de oude op `vervangen` (audit `deelvraag-vervangen`, alleen bij de eerste
  overname van een splitsing), kopieert haar geldige koppelingen naar de opvolger en zet die op haar plek,
  ná een eerder overgenomen deel (`_op_de_plek_van` nummert de actieve deelvragen opnieuw). Een vervangen
  deelvraag staat niet meer in de lijst, wijzigen geeft 409 `vervangen`, de status zet geen client (422),
  en Lex stelt haar tekst niet opnieuw voor. `koppel_bron_in` volgt een vervangen deelvraag naar haar
  actieve opvolger(s). `GET …/deelvragen/{id}` geeft één deelvraag in elke stand, met `opvolgers` en de open
  `voorstellen` die haar vervangen (het deelvraagpaneel van de werkplek).
- **Dekking** (`GET …/deelvragen/dekking`): per actieve deelvraag `met_bron` of `geen_bron`, met de gekoppelde
  bronnen; uit Postgres, zonder graaf. Een begrip telt niet mee: begrippen horen bij het werkgebied, niet bij
  een deelvraag (spoor K, methode M04 H3). De werkplek toont per deelvraag de voortgang van de bronselectie.
- **De bronnenrun zoekt per deelvraag**: `bronnen_run_store.invoer_van` neemt de actieve deelvragen op (alleen
  met deelvragen een sleutel, zodat de `invoer_id` van een werkgebied zonder deelvragen gelijk blijft); met
  alleen deelvragen is er ook een vertrekpunt. Op dezelfde manier gaat het dossier mee als sleutel `dossier`
  (alleen de gevulde velden van aanleiding, context, doel, praktijkvoorbeeld en afbakening). Bewijs van de methode `deelvraag` draagt `deelvraag_id`;
  opnemen koppelt de nieuwe selectie in dezelfde transactie aan die deelvragen (`koppel_bron_in`).
- Tests: `tests/test_werkgebied_deelvragen.py`.

## Bronselectie per deelvraag

`bronselectie.py`, `bronselectie_contracts.py`, routes in `bronnen_runs.py`; PLAN spoor J. Lex begeleidt
de bronselectie in het gesprek, maar de stand staat hier – niet in de gesprek-checkpointer –, zodat hij er
na herladen, in een ander gesprek en bij een collega ook is.

- **Het overzicht herhaalt het bewijs niet.** Per kandidaat staan `bewijs_soorten` en `zoekvragen`; het bewijs zelf staat
  in `GET …/kandidaten`. Per deelvraag herhaald was het de oorzaak van 760 KB, terwijl geen afnemer het hier las.
- **Zelf genoemd is een voorstel** (4 nov 2026): `POST …/bronselectie/{deelvraag}/voorstellen {bron_iri, rol: kern|
  afhankelijkheid, tekst}` (`bronselectie.noem`) zet een bepaling die de analist noemt als kandidaat bij die
  deelvraag, met bewijs `methode: genoemd` (`detail.deelvraag_id`, `tekst`, `door`), zodat ze in het paneel staat
  zoals de voorstellen van Lex en daar beslist wordt. Zo'n voorstel vervalt niet (`bronnen_run_store.vervallen` slaat
  het over), een volgende run voegt zijn bewijs toe zonder het genoemde te wissen (`_leg_kandidaten_vast`), en het
  blijft *voorgesteld* tot er een besluit is (ook na het fase-wisselen). Al opgenomen bij deze deelvraag of
  werkgebiedbreed uitgesloten: 409. `_hoort_bij` koppelt elk bewijs met `detail.deelvraag_id` aan die deelvraag.
- **Het zoekbereik staat op het werkgebied** (`regelingen: [{bwb_id, label}]`, 4 nov 2026): gekozen bij het
  samenstellen of aanvullen, in de invoer van de bronnenrun (`invoer_van`, alleen als het er is).
  `werkgebied_store.regelingen_van` is de ene plek die "de regelingen van het werkgebied" afleidt: eerst dit veld, dan
  de regelingen van de bronnen (peildatum/toestanden, thema-voorstel).
- **Voortgang per deelvraag** (`bronselectie_voortgang`, sleutel werkgebied + deelvraag): geen rij =
  `niet_gestart`, dan `in_behandeling`, `voorlopig_afgerond`, `beoordeeld`; plus `fase` (`kern`,
  `afhankelijkheden`, `afronden`) en `open_punten`. Dit is de stand van het werk; de deelvraagstatus
  (`actief`, `vervangen`) en de dekkingscheck (`gedekt`, `geen_bron`) staan los. Een werkgebied zonder
  actieve deelvragen heeft één eenheid, `analysevraag`; met deelvragen geeft die 409 `heeft_deelvragen`.
- **`POST …/bronselectie/{deelvraag}/status {actie}`**: `openen` (navigeren: start de deelvraag als dat nog
  niet gebeurd was, maakt haar de actieve – de laatst geopende in behandeling –, geen revisie), `fase`,
  `afronden`, `beoordelen`, `heropenen` (elk met `verwachte_revisie` van de rij → 412). Staat de rij al
  waar de actie heen wil, dan gebeurt er niets, ook geen revisietoets: een dubbele klik of een opnieuw
  afgespeelde actie is geen conflict. `beoordelen` gaat door een **poort** (409 `poort` met `redenen`): de vragen
  zijn doorlopen (fase `afronden`, of al afgerond) en er staat geen onderzoekspunt open. Niet gestart: 409
  `niet_gestart`.
- **Kiezen is het besluit; er is geen *later*.** Wie het kaartje beantwoordt, kiest: een voorstel dat toen niet
  aangevinkt werd, heeft bij het lezen de stand `niet_gekozen` – afgeleid uit de fase (kernvoorstellen zodra de
  deelvraag voorbij `kern` is, de rest bij `afronden`), niet bewaard. De fase terugzetten (de vragen opnieuw
  doorlopen) maakt er weer een `voorgesteld` van. Een oud besluit *later* op `bron_kandidaten` telt als voorstel.
- **Een afronding staat op een scope**: `scope_stand` = hash van analysevraag, afbakening, de genormaliseerde
  deelvraagtekst en de kandidaat-ids in de lijst van die deelvraag. Een ander dossier heropent dus pas iets
  als de nieuwe zoekopdracht er iets anders door vindt. Wijkt die bij het lezen af, dan `opnieuw_bekijken: true` en `klaar: false`; er wordt niets
  gewist. Een verbeterde deelvraag (F3d) erft voortgang en besluiten (`erf_in`, vanuit
  `werkgebied_deelvragen._vervang`), met de oude stand – dus op *opnieuw bekijken*.
- **Besluiten per deelvraag** (`POST …/bronselectie/{deelvraag}/kandidaten/{id} {besluit}`):
  - `opnemen` koppelt de bepaling aan deze deelvraag met een eigen `rol` (`werkgebied_deelvraag_koppelingen.rol`;
    leeg = de rol van de selectie). Staat ze nog niet in het werkgebied, dan loopt het via
    `bronnen_run_store.opnemen` met `deelvraag_ids=[deze]`. Eén selectie, meer koppelingen: nooit een duplicaat.
    Scope, dus `verwachte_revisie` van het werkgebied; dezelfde koppeling nog eens geeft geen revisie;
    een optionele `reden` staat op de koppeling (per deelvraag) en, bij een nieuwe selectie, ook op de selectie. Er is
    **geen standaardreden** meer: wie besloot is `gekoppeld_door`/`toegevoegd_door`, wie voorstelde
    `werkgebied_bronselecties.voorgesteld_door` (`analist` bij bewijs `genoemd` of zelf toevoegen, anders `lex`). De
    kandidaat met stand `opgenomen` en de bron in het overzicht dragen `reden` en `besloten_door` van de koppeling, en
    het rapport toont "Opgenomen door X, voorgesteld door Lex / zelf genoemd" (WA TRM H1, 8 nov 2026);
    **per lid**: `bron_iri` kiest de kandidaat zelf of een lid of onderdeel eronder (`bronselectie.onder`; anders 422
    `niet_onder_kandidaat`), en de selectie komt op dat deel. Een lid onder een artikel dat bij deze deelvraag al staat
    is 409 `valt_onder`; een artikel over opgenomen leden heen mag. De kandidaat heet dan `opgenomen` met
    `opgenomen_delen`; loskoppelen en uitsluiten gaan over alles van de kandidaat bij die deelvraag, en een weggehaalde
    lid-selectie maakt de kandidaat weer een voorstel als er geen deel meer staat;
  - `loskoppelen` haalt alleen de koppeling weg (revisie);
  - `uitsluiten` (reden verplicht) schrijft `bron_kandidaat_deelvragen`; met `overal: true` gaat de
    uitsluiting naar `bron_kandidaten` en geldt ze bij elke deelvraag. `heropenen` wist het besluit hier, met
    `overal` ook het werkgebiedbrede. Geen revisie, wel het slot en een audit `bronselectie-*`;
  - een besluit start de deelvraag als dat nog niet gebeurd was.
- **`GET …/bronselectie?na=`**: per eenheid `nr`, stand, `revisie`, `opnieuw_bekijken`, `klaar`, `bronnen` (met
  rol hier), `kandidaten` met `stand` hier (`voorgesteld`, `niet_gekozen`, `uitgesloten`, `opgenomen`), `overal`,
  `elders_opgenomen` en `bewijs_soorten` (`verwijzing`, `definitie`, `structuur`, `tekst`, `gelijkenis`:
  een tekstuele overeenkomst is geen bewijs van noodzaak), `telling` en `beoordelen: {mag, redenen}`. Plus
  `actief`, `volgende` (deterministisch: de eerste niet-klare na `na`, anders vooraan verder), `alle_klaar`,
  `zonder_deelvraag` (open voorstellen die bij geen deelvraag horen – niet stil weg) en `zoekdekking` uit de
  laatste run (`gezocht`, `volledig`, `onvolledig` per methode, `verouderd`, `reden`).
- **Welke kandidaat hoort bij een deelvraag** is deterministisch: bewijs `deelvraag` met haar id (of dat van
  een voorganger), een besluit hier, opgenomen hier, of een bewijs `vanuit` een bron die hier opgenomen is
  (een afhankelijkheid).
- Tests: `tests/test_bronselectie.py`.

## Regies

`regies.py`, `regie_store.py`, `regie_contracts.py`; het ontwerp is ADR-012 (PLAN spoor S). De regisseur in graph-qa
verdeelt het werk in een werkgebied over deelgesprekken; de api houdt het object bij en de deelgesprekken
(`gesprekken.ouder_id`, §*Gesprekken*). Stijl C: de store gooit de fouten.

- **Eén lopende regie per werkgebied én per gebruiker** (partiële unieke indexen op `status = 'loopt'`, dus race-vrij
  tussen replica's). Een tweede start geeft 409 `regie_loopt_al` met `regie_id` en `werkgebied_id` van wie het slot heeft.
- **Een regie zonder hartslag telt als mislukt.** graph-qa stuurt `PATCH {status: "loopt"}` als teken van leven; na
  `VERWEESD_NA` (3 min) zonder leest de regie als `mislukt`, en een nieuwe start legt hem eerst zo vast (`uitkomst:
  {reden: "verweesd"}`), anders blokkeert een omgevallen replica het werkgebied.
- **Afronden is eenmalig**: een eindstand (`klaar`, `gestopt`, `mislukt`) met de `uitkomst`; dezelfde nog eens is
  idempotent, een andere 409 `regie_afgerond`. Alleen de eigenaar wijzigt (anders 404).
- **Het regiegesprek** is een eigen gesprek in het werkgebied (404 of 409 `ander_werkgebied`).
- De api voert niets uit: het plan is wat de jurist bevestigde, bewaard als JSON. Besluiten over bronnen en markeringen
  lopen via hun eigen routes, door de jurist.
- Tests: `tests/test_regies.py`.

## De werkplaats

`werkplaats.py`, `werkplaats_store.py`, de beheerroutes in `routers/admin.py`; het ontwerp is ADR-016 deel B (stap B1-1 en B1-2).
Achter `WERKPLAATS` (default uit, alleen acceptatie, met een poort-guard): zonder de vlag geven alle routes 404, behalve
`GET /v1/werkplaats/stand` (`{aan: false}`).

- **Eén levenscyclus voor elke soort.** Tabellen `werkplaats_onderdelen`, `werkplaats_versies`, `werkplaats_audit` en de
  ene rij `werkplaats_beleid`; geen tabel per soort. Wat een soort is (naamvorm, toets, het lege begin) staat in
  `bronmodel.werkplaats.REGISTER`; een nieuwe soort is een regel daar. `mcp` staat in `SOORTEN` maar is gesloten (422).
- **Een versie is een volledige snapshot** (`bestanden`: pad → tekst) met `bronmodel.werkplaats.hash_van`. De tabel
  groeit alleen aan: geen UPDATE of DELETE op een versie. Dezelfde inhoud als de laatste versie geeft die versie terug;
  `na_versie` wijkt af van de laatste → 409; het unieke `(onderdeel_id, nummer)` vangt de race.
- **Poort 1 draait bij elke opslag** (`bronmodel.werkplaats.toets`, dezelfde validatoren als de generator in graph-qa).
  De uitkomst staat bij de versie (`geldig`, `bevindingen`). **Een ongeldige versie wordt bewaard**; alleen
  `werkplaats_store.bruikbaar` (geldig, onderdeel niet ingetrokken) mag naar de proef of een PR. Vraag het daar, niet
  met een eigen regel.
- **Wat nooit bewaard wordt** (`bronmodel.werkplaats.weiger`, 422): een pad dat geen pad is, een snapshot boven de grens,
  een onbekende of gesloten soort, een ongeldige naam. Plus hoogstens `MAX_VERSIES` per onderdeel en `MAX_ONDERDELEN`
  per gebruiker (409).
- **Een onderdeel heeft een eigenaar**; de naam is uniek per soort en eigenaar zolang het niet is ingetrokken (in de
  transactie bewaakt). `zelfde_naam` op het onderdeel telt de concepten van anderen met dezelfde soort en naam.
- **De stand wordt afgeleid**: `concept`, `actief` of `ingetrokken`. Er komt geen kolom `status`; *voorgesteld* komt
  er in een latere stap bij, ook afgeleid.
- **Wat er in het image zit, meldt graph-qa** (`PUT /v1/werkplaats/image`, tabel `werkplaats_image`: één rij). De api
  roept graph-qa nergens aan, dus graph-qa stuurt bij het starten zijn bronpakket: per skill en per agentprofiel de
  bestanden en de hash, met de hash van het hele pakket (`bronmodel.werkplaats.pakkethash`) en de commit.
  - **Idempotent op de pakkethash.** Kent de api hem, dan schrijft hij niets. Stuurde graph-qa alleen de hash en kent
    de api hem niet, dan is het antwoord `bekend: false` en volgt het hele pakket. Het schrijven is één upsert op rij 1:
    twee replica's die tegelijk melden, botsen niet. Een melding moet met zichzelf kloppen (`_toets_pakket`: elke hash
    is die van de bestanden, de pakkethash die over alle hashes), anders 422.
  - **Alleen graph-qa** (`AGENT_CLIENT`, anders 403), en het is de enige route van de werkplaats in
    `agent_toegang.TOEGESTAAN`: het agent-token maakt, leest of wijzigt geen concept.
  - **De stand volgt uit de hashes, bij het lezen** (`_stand`): `actief_versie` (de nieuwste versie met de hash van het
    image; `stand` is `actief` als dat de laatste is), `in_image`, `basis_verouderd` (de basis van het concept is niet
    meer wat er draait en het concept zelf ook niet: master veranderde) en per versie `actief`. **Kent de api het image
    niet, dan zijn ze `None`** (`image_bekend: false`): onbekend is nooit "niet actief". Lees `None` niet als nee.
  - Een image dat ouder is dan master maakt een versie dus niet actief: dat wordt ze pas als graph-qa met het nieuwe
    image start en zich meldt. `GET /stand` toont `image: {bekend, pakket_hash, revisie, gemeld_op, onderdelen}`,
    zodat te zien is van wanneer de stand is.
- **Bewerken** (`POST /onderdelen` met `uit_image: true`): versie 1 is de versie uit het image, met haar hash als
  `basis_hash`. 409 `image_onbekend` zolang graph-qa zich niet meldde, 404 `niet_in_image`.
- **Een skill toetst ook tegen de andere skills in het image** (`_andere_skills` → `wp.toets(andere=)`): een sectie-id
  en een broncode zijn van één skill. Het concept vervangt zijn eigen versie. Zonder image toetst een skill alleen op
  zichzelf.
- **Rechten (§B4).** Lezen: de eigenaar, iedereen bij een gedeeld onderdeel, een beheerder met 2FA alles; anders 404.
  Wijzigen en intrekken: alleen de eigenaar (403). Maken: een analist alleen als het beleid dat toestaat (default aan).
  Delen, andermans concept intrekken en het beleid: `/v1/admin/werkplaats/*`, achter het admin-token én
  `beheerder_met_2fa`. Een beheerder zonder 2FA werkt als analist.
- **De audit en de logregels dragen geen inhoud en geen naam van een concept**: het onderdeel-id, het versienummer, de
  hash en wie. Een concept kan tekst bevatten die niet openbaar mag worden.
- **Stijl C**: de store gooit de HTTP-fouten (`{melding, bevindingen?}`), de router toetst alleen wie het vraagt.
- Nog niet: de editor en het samenvoegen bij een verouderde basis (B2), de proef (B3), promotie (B4). Een account
  verwijderen laat zijn concepten staan; een beheerder kan ze intrekken.
- Tests: `tests/test_werkplaats.py`, `tests/test_werkplaats_image.py` (ook met het echte bronpakket van graph-qa).

## Versies van artefacten

`artefact_versies.py`, tabel `artefact_versies`; het ontwerp staat in `docs/architectuur/artefacten-langs-claude.md`
(de versiekiezer zoals bij Claude). Een artefact van Lex is een levend object: de chip opent de stand van nu. Wil je
de stand van die beurt zien, dan heb je een momentopname nodig. Alleen een begrip bewaarde oude inhoud
(`begrip_revisies`); werkgebied, deelvraag, bronselectie, annotatie en de groepen niet.

- **Eén schrijfpad.** `POST /v1/gesprekken/{id}/berichten` met `rol: assistant`, een `run_id` en een `artefact` legt
  de stand van nu vast (`leg_vast`), met dezelfde leesfuncties als de routes van het paneel:
  - `werkgebied`: het werkgebied en het bronselectie-overzicht;
  - `deelvraag`: de deelvraag, het werkgebied en het overzicht;
  - `bronselectie`: het overzicht;
  - `begrip`: het begrip met zijn relaties;
  - `begrippen`: de groepen;
  - `annotatie`: de v2-weergave van de bronnode.

  Het id komt in `artefact.ref.versie` van het bericht. `regels` en een user-bericht krijgen er geen. Een
  bericht is daarna onveranderlijk, dus de versie hoort voorgoed bij die beurt.
- **Een versie is de stand direct na een beurt van Lex** (besluit gebruiker). Een handmatige wijziging ertussen is
  geen eigen versie; die zie je in *Nu*.
- **Per object tellen, over gesprekken heen.** Daarvoor dient de `sleutel`: `werkgebied:<wid>`,
  `deelvraag:<wid>:<did>`, `bronselectie:<wid>`, `begrip:<wid>:<bid>`, `begrippen:<wid>` of
  `annotatie:<bron_iri>`. De objecten zijn gedeeld, dus hun versies ook.
- **Idempotent op (`run_id`, `sleutel`)** (unieke index `ux_artefact_versies_run_sleutel`): dezelfde beurt nog eens
  geeft dezelfde versie.
- **Een mislukte opname laat het bericht landen**, zonder `versie`. Denk aan een object dat niet meer bestaat, een
  haperende graaf of een fout in de database. De versie is een gemak, geen voorwaarde. Het wordt gelogd.
- **Lezen.** Toegang heeft elke actieve gebruiker.
  - `GET /v1/artefact-versies/{id}` geeft `{id, soort, sleutel, inhoud, gemaakt, nr, totaal, vorige, volgende}`;
  - een onbekend id geeft 404;
  - `GET /v1/artefact-versies?sleutel=` geeft de lijst, van oud naar nieuw.
- **Echt wissen, zoals het object.** De tabel staat in `werkgebied_store.WERKGEBIED_TABELLEN`. Een verwijderde
  annotatie wist de versies van de bepaling in beeld en van haar bronnodes (`annotatie_v2_store.verwijder_weergave`).
  De berichten blijven staan, en hun `versie` geeft dan 404.
- Tests: `tests/test_artefact_versies.py`.

## Gesprekken

`gesprek_contracts.py`, `gesprek_store.py`, `routers/gesprekken.py`. Per gebruiker gescopet via
`actieve_userid`; 404 op andermans gesprek.

- **Een gesprek hoort bij een werkgebied of is los** (spoor G1): `werkgebied_id` (leeg = los) en
  `gearchiveerd` (een tijdstip, zoals bij werkgebieden). `POST` neemt `werkgebied_id` aan, `PATCH` wijzigt
  alleen wat meekomt (`titel`, `werkgebied_id` – `""` koppelt los –, `gearchiveerd`), `GET` filtert op
  `werkgebied_id` (`""` = alleen losse) en `gearchiveerd`, en geeft per rij `werkgebied_naam` mee. Koppelen
  aan een onbekend werkgebied geeft de 404 van het werkgebied; werkgebieden zijn gedeeld, dus bestaan is
  genoeg. Verplaatsen of archiveren zet `updated` niet: het gesprek springt niet bovenaan de lijst. Geen
  foreign key: een gewist werkgebied maakt zijn gesprekken los (`werkgebied_store.wis`), en een gewist
  gesprek raakt niets in de andere domeinen. Archiveren, verplaatsen en verwijderen zijn bewust drie
  handelingen; verwijderen blijft echt wissen.
- **Deelgesprekken** (ADR-012): `ouder_id` en `regie_id` op het gesprek. `POST` toetst dat de ouder een eigen gesprek is in
  hetzelfde werkgebied en zelf geen ouder heeft (404, 409 `ander_werkgebied`/`te_diep`), en dat de regie bij die ouder hoort
  (409 `andere_regie`), en van dezelfde gebruiker is. **Het agent-token maakt alleen zo'n deelgesprek**, onder een regie die loopt (403 `alleen_deelgesprek`, 409 `regie_afgerond`): anders kon het namens elke `X-User-Id` gesprekken aanmaken. `GET ?ouder_id=` geeft de deelgesprekken (`""` = alleen gesprekken zonder ouder). Een ouder
  verwijderen, het gesprek verhuizen of het werkgebied wissen maakt een deelgesprek los; het wordt nooit mee gewist.

- Een bericht verwijst via **`artefact`** naar wat de beurt opleverde: `{soort, ref, titel}` met
  `soort` `annotatie` (ref `{bron_iri, label?, snapshot_id?}`), `begrippen` (ref
  `{werkgebied_id, run_id}`; met `begrip_id` in plaats van `run_id` alleen nog in berichten van vóór F3d),
  `begrip` (ref `{werkgebied_id, begrip_id, kaart_run_id?, actie?}`: één begrip, F3d), `deelvraag` (ref
  `{werkgebied_id, deelvraag_id}`: één deelvraag, F3d), `bronnen` (ref `{werkgebied_id, run_id}`, fase A),
  `werkgebied` (ref `{werkgebied_id}`: een werkgebied dat Lex in het gesprek samenstelde, activiteit 1)
  of `regels` (gereserveerd, nog niet in gebruik). `Artefact` toetst de
  verplichte ref-sleutels per soort (422). Bij een beurt van Lex zet de api zelf `ref.versie` (§*Versies van
  artefacten*). Oudere berichten verwijzen via `annotatie_doel`; graph-qa
  schrijft beide voor een annotatie. Het bericht draagt ook het uitvoeringsspoor van de beurt
  (`tool_executions`). Een antwoord op een overzichtsvraag draagt het
  `overzicht` dat graph-qa uit de graaf bouwde, zodat het blok na herladen hetzelfde is.
  Een voorstel dat Lex niet zonder akkoord start (fase B: het werkgebied annoteren) draagt een
  **`bevestiging`** `{soort: "werkgebied_annoteren" | "begrippen_verdiepen", werkgebied_id, aantal, schatting,
  bereik: "werkgebied" | "deelvragen", deelvraag_id}` (het bereik van de werkvoorraad, zodat de knop na herladen hetzelfde annoteert). Het user-bericht
  dat zo'n voorstel beantwoordt – de knop of *Annuleren* – draagt **`bevestiging_antwoord`** `{keuze: "gestart" | "geannuleerd"}`,
  zodat de knoppen na herladen weg zijn; de werkplek
  toont er een knop bij, ook na herladen. Bij het samenstellen van een werkgebied (activiteit 1) draagt
  elke vraag van Lex een **`vraagkaart`** `{intake_id, soort: vraag|samenvatting, stap, nr, totaal,
  vraag, opties[{label, waarde, bron, omschrijving}], meerkeuze, vrije_tekst, meer_tekst, overslaanbaar,
  vooringevuld, samenvatting, terug, beantwoord}`; de stappen (`IntakeStap`) zijn `naam`, `aanleiding`,
  `context`, `doel`, `analysevraag`, `praktijkvoorbeeld`, `deelvragen`, `buiten`, `regelingen`,
  `bepalingen`, `samenvatting`. `modus` is `samenstellen` (default) of `aanvullen`: het dossier van een
  bestaand werkgebied, met in de samenvatting `{wijzigingen: [{veld, label, toen, nu}]}`. Het user-bericht van een klik draagt
  **`intake_antwoord`** `{intake_id, stap, actie}` (`actie` ook `opslaan`, de knop van het aanvullen): zo bundelt de werkplek na herladen de antwoorden
  in één Vragen-kaart en onderscheidt hij ze van een getypte tussenvraag. `reeks.totaal` mag 1 zijn: een werkgebied kan één nieuwe
  bepaling hebben. `modus: "begrip"` (stap `begrip_kiezen`, `intake_id` `bk-<werkgebied>`) is de keuzekaart van de
  begrippen-agent: welk begrip bedoel je? Lex gokt niet.
  De review-state zelf blijft in het annotatiedomein. **Een veld dat graph-qa meestuurt moet in
  `BerichtInvoer` staan**, anders laat Pydantic het stil vallen en verdwijnen na het heropenen de
  chip naar het annotatiepaneel en het toolspoor. `tools/graph-qa/tests/test_contract_drift.py`
  toetst dat.
- **`contextopbouw`** (plan contextweergave, ADR-015): hoe de verzoeken van de beurt waren opgebouwd en wat de beurt
  kostte, door graph-qa uitgerekend. Alleen tellingen en vingerafdrukken; geen veld heet `token` (de logredactie laat
  die naam weg). Het contract (`Contextopbouw`) legt het bovenste niveau vast en begrenst de lijsten; de lagen eronder
  zijn van graph-qa. Het veld staat in `_OPTIONEEL`: een vorm die niet meer past, valt weg zonder het gesprek te
  breken. Er is geen rolfilter. **`GET /v1/gesprekken/{id}/contextopbouw`** geeft de boom bij het lezen: per
  deelgesprek (`ouder_id`, alleen de eigen) de contextopbouw van zijn assistentberichten; een kind zonder meting
  staat erin met een lege lijst. Niets is dubbel opgeslagen. Tests: `tests/test_contextopbouw.py`.
- De verwijzing heeft **geen foreign key**, dus draagt het bericht een eigen label
  (`artefact.titel`; bij oude berichten `annotatie_titel`). Een annotatie verwijderen raakt de
  berichten niet: het gesprek is een verslag.
- **`run_id` is een idempotentiesleutel.** Een agent-beurt hangt niet aan één browserverbinding en
  meerdere tabbladen kunnen op dezelfde run meekijken. `voeg_bericht_toe` geeft bij een bekend
  `run_id` het bestaande bericht terug; de partiële unieke index `ux_gesprek_berichten_run` dekt de
  race tussen replica's, en de insert staat in een SAVEPOINT omdat een `IntegrityError` op Postgres
  anders de hele transactie aborteert.
- **De schrijver is meestal graph-qa**, met een eigen client-id in `WETSANALYSE_API_TOKENS`
  (`graph-qa:<token>`) plus de `X-User-Id` van de jurist. `client_id` is niet aan `user_id`
  gebonden: dat token kan in elk gebruikersgesprek schrijven, en graph-qa blijft daarom intern.

## Login, registratie, 2FA

- **Inloggen gaat met de `userid`** (primaire sleutel van `users`); `email` is verplicht en uniek
  maar geen inlog-identiteit. bcrypt, rollen `beheerder`/`analist`. `/v1/auth/*` hangt achter
  `require_client`; de BFF (Auth.js) is de enige client en zet `X-User-Id` server-side. De
  browsersessie leeft in de frontend.
- **Een TOTP-code geldt één keer** (`users._verbruik_totp`): de gebruikte tijdstap staat in
  `users.totp_laatste_stap` en het vastleggen is één voorwaardelijke `UPDATE`, dus twee
  gelijktijdige pogingen met dezelfde code halen het nooit allebei. Omdat de webapp na het
  2FA-scherm nóg eens verifieert, geeft `/verify` na een verbruikte code een **2FA-ticket** mee
  (`maak_2fa_ticket`, 5 min, Fernet); `verify_credentials` meldt dat als `"ok_totp"`. De 2FA-secret
  is versleuteld met dezelfde Fernet-key als de LLM-keys. Tests zetten de klok stil via
  `users._nu`; `_totp_now` in `tests/test_users_auth.py` schuift per code een stap op.
- **Een 2FA-koppeling starten vraagt het wachtwoord** (`users.begin_2fa`), en actieve 2FA blijft
  staan: een sessie alleen mag de tweede factor niet vervangen. Die weigering (409, security-log
  `2fa_begin_geweigerd`) zit in de voorwaardelijke `UPDATE`, niet in een eerdere lezing. Uitzetten kan
  alleen met een code, en **niet voor een beheerder** (`BeheerderHoudt2faError`, 409): zonder 2FA is het beheer
  dicht, en voor de enige beheerder is er dan niemand die beheert. De weigering staat vóór het verbruiken van de
  code.
- **Opnieuw koppelen terwijl 2FA aan blijft** (`begin_2fa` mét `totp`, dan `activate_2fa`): met het wachtwoord
  én een code van de huidige app (of een herstelcode) komt een nieuw secret in `users.totp_nieuw_enc`. De oude app
  blijft gelden tot een code van de nieuwe het in één voorwaardelijke `UPDATE` (op precies dat klaargezette secret)
  overzet; die code telt als gebruikt en er komt een nieuwe set herstelcodes. `_wis_2fa` (uitzetten, reset) ruimt
  een klaargezette app op.
- **Herstelcodes** (`users.py`, tabel `herstelcodes`): tien stuks van 80 bits bij `activate_2fa`, één keer
  getoond en daarna alleen als sha256 over `userid|code`. Verbruiken is één voorwaardelijke `DELETE`.
  `_verbruik_tweede_factor` kiest op de **vorm** van de invoer, in hetzelfde veld als de TOTP-code; zo raakt
  een herstelcode de Fernet-sleutel niet en overleeft hij een geroteerde `LLM_CONFIG_SECRET`. Ze werken bij
  het inloggen (`"ok_herstelcode"`, security-log `herstelcode_login`), bij `disable_2fa` en bij
  `vervang_herstelcodes`, en als bewijs bij opnieuw koppelen. Een nieuwe telefoon is dus: inloggen met een code,
  opnieuw koppelen met de volgende.
- **Er blijft altijd een actieve beheerder** (`users.patch_user`, `users.delete_user`): degraderen,
  deactiveren en verwijderen weigeren (409) als het doel de laatste actieve beheerder is. Een inactieve
  beheerder telt niet mee. Beide nemen eerst hetzelfde slot (`_beheerdersslot`, een advisory xact-lock op
  Postgres) en lezen daarna de doelrij en de telling opnieuw, in de transactie van de wijziging; een toets
  vóór het slot laat twee beheerders elkaar tegelijk verwijderen. Webapp, admin-API en admin-MCP gaan alle drie
  langs deze twee functies; de races staan in `tests/test_beheerders_postgres.py`.
- **De 2FA-plicht is afgeleide toestand** (`users.moet_2fa_koppelen`): `role == "beheerder"` zonder
  `totp_enabled`, en `/v1/auth/me` meldt hem als `tfa_nodig`. Er is geen controle per ingang, dus `/setup`,
  promotie, een nieuw account en een goedgekeurde aanvraag vallen vanzelf onder dezelfde regel. Afdwingen doet
  de BFF (`proxy()`, zie `frontend/CLAUDE.md`), omdat `/v1/admin` geen gebruiker kent. Zo'n account logt
  gewoon in en werkt als analist, want koppelen vraagt een sessie. Zonder `LLM_CONFIG_SECRET` kan niemand
  koppelen, dus blijft het beheer dicht (fail-closed); de api logt dat bij het starten.
- **Reset door een beheerder** (`POST /v1/admin/users/{id}/2fa/reset`, `users.reset_2fa`): achter
  `require_admin` én `huidige_beheerder`, dus een kaal admin-token komt er niet door en de `door` in het
  security-log (`2fa_reset`) is een persoon. De uitvoerder heeft zelf 2FA en reset zichzelf niet. Secret en
  herstelcodes gaan weg, `sessions_valid_from` wordt nu. De laatste beheerder heeft geen collega: daar dragen
  de herstelcodes het, zie `deploy/azure/README.md` §*2FA voor beheerders*.
- **Zelfregistratie** (`registraties.py`): een aanvraag is **geen account** – tot de goedkeuring
  bestaat er geen rij in `users`. De userid wordt afgeleid uit de naam (vier letters achternaam +
  eerste letter voornaam + volgnummer) en is bij goedkeuren corrigeerbaar; de bcrypt-hash gaat
  ongewijzigd over (`users.insert_user_met_hash`), zodat er geen tijdelijk wachtwoord rondgaat.
  **Afwijzen verwijdert de rij**: e-mailadres en volgnummer zijn meteen weer vrij; de reden staat in
  het security-log. Er gaat geen e-mail uit: bij een openstaande aanvraag meldt `/verify` de `code`
  `aanvraag_open`, en **alleen bij het juiste wachtwoord** – anders is het een oracle voor wie er een
  aanvraag heeft liggen.
- **Actief-controle.** `actieve_userid` (`routers/auth.py`) controleert dat het account bestaat en
  actief is, met een cache van 30 s; de admin-router roept `vergeet_actief()` aan bij deactiveren of
  verwijderen, zodat dat meteen bijt. `huidige_userid` leest alleen de header, voor endpoints die hun
  eigen bewijs vragen (wachtwoord, 2FA-code).
- **Admin-bearer levert geen userid.** Admin-endpoints die per-beheerder state schrijven (zoals
  `feedback_gezien_op`) lopen daarom ook via `huidige_beheerder`.
- **Admin-tokens**: `require_admin` (async) accepteert de env-tokens (`WETSANALYSE_ADMIN_TOKENS`,
  het bootstrap-pad) en DB-tokens uit `api_tokens.py`. Die staan alleen als sha256-hash in
  `api_tokens`, worden één keer getoond en zijn intrekbaar; ze voeden o.a. de admin-MCP
  (`tools/wetsanalyse-admin-mcp/`).
- **Accounttokens** (scope `gebruiker`, prefix `wa_pat_`): een token dat bij één account hoort en na 90
  dagen verloopt. Ze staan in dezelfde tabel, maar de twee soorten kruisen niet: `verify()` kijkt alleen
  naar scope `admin`, dus een accounttoken opent `/v1/admin` nooit. De BFF wisselt zo'n token in voor een
  gewone sessie (`POST /v1/auth/api-token/verify`) en controleert het periodiek
  (`GET /v1/auth/api-token/{id}/status`); wat de sessie mag volgt uit het account. Alles hangt achter
  `API_TOKEN_LOGIN`, default uit (404). Een geweigerd account krijgt geen token, en verwijderen trekt de
  tokens in: anders erft een nieuw account met dezelfde userid ze.

## Tokenbudget

`verbruik.py`. **Verbruik is een journaal, de stand is een som.** `token_verbruik` krijgt één rij per
LLM-call; de stand is `sum(...) WHERE userid = ? AND tijdstip >= vanaf`. `vanaf` is het vensterbegin
(uit het `anker` in `budget_beleid`), of de laatste reset door een beheerder als die later ligt.
Daaruit volgt:

- **Werk weggooien geeft geen tokens terug.** `userid` is de enige harde sleutel; `gesprek_id` en
  `run_id` zijn metadata zonder foreign key, want `gesprek_store.verwijder_gesprek` en
  `annotatie_v2_store.verwijder_weergave` ruimen hun eigen rijen hard op.
- **De reset vraagt geen cronjob**, en elk getal is navraagbaar tot op de call.
- Wat meetelt is het volle promptvolume (invoer + uitvoer + cache_lees + cache_schrijf): caching
  verlaagt de factuur, niet het budget. De vier getallen staan apart, zodat een gewogen variant een
  rekenregel is en geen migratie.
- Het beleid staat in de database, want een limiet aanpassen mag geen redeploy vragen; de env-waarden
  seeden alleen de eerste rijen (`verbruik.ensure_seeded`). Boeken is idempotent op `run_id`.
- **Het budget volgt uit de rol, en uit niets anders** (`budget_rol`, `PUT /v1/admin/budget/rollen/{rol}`).
  Er is geen budget per gebruiker en geen algemeen budget: `WETSANALYSE_TOKEN_BUDGET` seedt elke rol. Een
  rolwissel geeft meteen het budget van de nieuwe rol, want `_budget_van` leest de rol elke keer vers.
  `PATCH /v1/admin/users/{id}` weigert onbekende velden, dus een oud `token_budget` geeft 422 en geen stille 200.
- **Een reset wist niets** (`POST /v1/admin/users/{userid}/verbruik/reset`, `verbruik.reset_verbruik`).
  Hij schrijft een rij in `budget_audit`, en de som begint bij de laatste reset binnen het venster. Geen
  tegenboeking: een negatieve rij is geen LLM-call, en alles wat over de calls telt (de schatting per beurt in
  `werkgebied_werkvoorraad`, een gewogen variant) zou hem moeten uitsluiten. Het venster schuift niet op, en wat
  na de reset geboekt wordt telt mee, ook van een beurt die al liep. In het volgende venster doet de reset niets meer.
- **Wijzigen draagt iemands naam.** Reset, `PUT /v1/admin/budget` en het rolbudget staan achter `require_admin`
  én `beheerder_met_2fa`: de BFF zet `X-User-Id` uit de sessie, een kaal admin-token (de admin-MCP) komt er niet
  door, en de `door` komt in `budget_audit`, append-only, met de oude en de nieuwe waarde.

## Bronconnectors (ADR-013)

`app/connectors.py`: het register van de bronconnectors; de beheerroutes staan in `routers/admin.py`. **Welke er bestaan staat in de code** (`BEKEND`, gelijk aan
`tools.CONNECTORS` van graph-qa; `tools/graph-qa/tests/test_bronschakelaar.py` leest deze bron): een bronconnector is een
getypeerde tool met een eigen soort vindplaats, geen configuratie. Het register zegt alleen aan of uit (tabel `connectors`;
een rij ontbreekt = uit), en elke wijziging is een regel in `connector_audit`.

- `GET /v1/admin/connectors`, `GET …/{naam}/audit`: admin-token.
- `PUT /v1/admin/connectors/{naam}` `{aan}`: een beheerder mét 2FA uit de sessie (`beheerder_met_2fa`, zoals het budget),
  dus niet met een los token of de admin-MCP. Dubbel aanzetten is geen auditregel.
- `GET /v1/connectors` (`routers/connectors.py`, `require_client`, en op de lijst van het agent-token in `agent_toegang.py`):
  `{aan: [naam]}`, voor graph-qa per beurt. Graph-qa zet daarnaast zijn eigen
  straatvlag (`CONNECTOR_<NAAM>`); een connector draait alleen als beide aanstaan, en een onleesbaar register zet niets aan.
- `GET /v1/connectors` draagt ook `connectors: [{naam, label, brontype}]`: wat de werkplek in het menu toont.
- **De stand per gesprek en per werkgebied** (fase 1b, het menu *Bronnen en tools*): `Gesprek.connectors`
  (`PATCH /v1/gesprekken/{id}` `{connectors}`; `null` = terug naar de standaard, weggelaten = ongewijzigd, geen `updated`)
  en `standaard_connectors` op het werkgebied (`PATCH` met de revisie). Niet `bronnen`: zo heten de bronselecties al in de
  uitvoer van een werkgebied. De werkplek rekent de stand en stuurt hem per beurt als `bronnen` naar graph-qa.
- Credentials en een rate-limit per connector komen met de eerste connector die ze nodig heeft (EUR-Lex).

## Voorstellen voor de methode (ADR-014 C7)

`app/catalogus_voorstel.py`, routes in `routers/admin.py`. Een beheerder met 2FA (`beheerder_met_2fa`) stelt een nieuwe tekst
voor een methodesectie voor; de api opent er op GitHub een **concept-PR** voor. Er is geen overlay en geen tweede waarheid:
de tekst gaat pas mee na review, meting (ADR-010), merge en uitrol.

- `GET /v1/admin/catalogus/voorstellen/stand` (`{aan, reden}`) en `POST /v1/admin/catalogus/voorstellen` (201 `{pr_url,
  branch, pr_nummer}`). Uit zonder `CATALOGUS_VOORSTELLEN` of zonder de GitHub App (`GITHUB_APP_ID`,
  `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_KEY`, de sleutel als bestand) en `GITHUB_REPO` (404).
- **Een App, geen persoonlijk token.** Per voorstel een JWT (RS256, tien minuten, getekend met `cryptography`) en daarmee een
  installatietoken van een uur, beperkt tot deze repo met *contents* en *pull requests*; niets wordt bewaard. Mergen houdt de
  ruleset op master tegen, niet deze code.
- Alleen `.claude/skills/<skill>/references/*.md` (422). De sectie leest en vervangt `bronmodel.methodesectie`, dezelfde
  validator als de generator van het methodepakket: precies één markerpaar, niet leeg, hoogstens 6000 tekens, geen
  HTML-commentaar; de rest van het bestand blijft byte-gelijk. Gelijke tekst 409; hetzelfde voorstel nog eens 409 (de branch
  is een hash van bestand, sectie en tekst).
- Het bestand komt van `master` op GitHub, niet uit het image. De PR-tekst draagt toen en nu, wie het voorstelde en de
  checklist voor de reviewer (meting, licentie, het methodepakket opnieuw genereren).
- Tests: `tests/test_catalogus_voorstel.py` (GitHub als `httpx.MockTransport` via `catalogus_voorstel._TRANSPORT`; de nep-GitHub
  controleert de handtekening van de JWT met de publieke sleutel).

## Schema

Er is geen Alembic. `db.bouw_schema` draait bij de start, onder een advisory lock zodat replica's op elkaar wachten:
`db.create_all` maakt **ontbrekende tabellen** aan;
`db.reconcile_schema` voegt daarna **ontbrekende kolommen** toe (`ALTER TABLE … ADD COLUMN`, mét
`server_default`) en maakt **ontbrekende indexen** aan (`checkfirst`). Nooit droppen of van type
wisselen: dat is een bewuste ingreep, die als benoemde uitzondering in `reconcile_schema` staat (nu: de oude
budgetkolommen, de NOT NULL van `werkgebied_id` voor generieke begrippen, en `werkgebieden.gearchiveerd` en
`begrippen.verwijderd`, waarvan de start eerst de gemarkeerde rijen wist). Declareer een nieuwe kolom dus altijd in de
`Table` in `db.py`; zonder die declaratie kent SQLAlchemy Core haar niet, ook als ze in de database
bestaat. `_na_kolom` vult een nieuw toegevoegde kolom waar de waarde al elders stond (nu alleen
`gesprek_berichten.run_id` uit `inhoud`).

Portable types: `JSON` wordt `JSONB` op Postgres; datetimes zijn tz-aware (`db.aware` repareert
naïeve SQLite-waarden). Een in-memory SQLite-URL krijgt een `StaticPool`. Let op: in-memory SQLite
deelt één verbinding, dus twee gelijktijdige requests zijn daarop niet te testen.

## Garanties (niet aan tornen)

- **Identiteit uit `X-User-Id`.** Gesprekken zijn per gebruiker gescopet (404 op
  andermans id, lekt niet). De header is vertrouwd omdat alleen de BFF en graph-qa hem zetten – zie
  §*Uitrol* voor wat een publieke ingress daarmee doet.
- **De admin-laag is altijd auth-plichtig.** Geen `AUTH_REQUIRED`-bypass; zonder admin-tokens is
  alles 401. De plaintext-API-key komt nooit terug (alleen `api_key_set`); opslaan vraagt een
  Fernet-master-key.
- **Append-only audit.** Elke annotatie-actie schrijft auditregels; de tijdlijn is `ORDER BY id`.
- **JAS-klassen zijn canoniek**: `validation.GELDIGE_JAS_KLASSEN`, gevoed door `jas_klassen.py`.
  Verzin er geen bij. `tests/test_jas_kleuren_drift.py` bewaakt dat `frontend/lib/jas.ts` dezelfde
  kleuren draagt.
- **De API toetst zelf wat hij vastlegt**, want hij is de laatste partij die iets kan tegenhouden.
  Hij doet de juridische interpretatie niet over: of een fragment letterlijk in de wet staat, toetst
  graph-qa. De API toetst de samenhang van anker, fragment en bron.
- **Een projectie laat nooit een beslissing falen.** GraphDB-fouten in het projectiepad worden
  gelogd en ingehaald door de lus; zoeken en graafcontrole melden onvolledigheid expliciet.
- **Secrets zijn bestanden** (`*_FILE`), nooit plain env in productie.
- **Log nooit tokens, secrets of prompt-inhoud.**

## Observability

`app/observability.py`: gestructureerde JSON-logging (`ts/niveau/categorie/bericht/…velden`,
secret-redactie, `LOG_LEVEL`/`LOG_FORMAT`) plus OpenTelemetry, gated op
`OTEL_EXPORTER_OTLP_ENDPOINT`. `setup()` draait vroeg in `main.py`; `RequestContextMiddleware`
(pure ASGI) zet een `X-Request-Id` en logt per request. `get_tracer()`/`get_meter()` geven no-op-shims
zonder de `otel`-extra, dus code mag onvoorwaardelijk spans en metrics maken. Zie
`docs/observability.md`.

## Commando's

```bash
cd api
uv sync --extra llm --extra dev
uv run --env-file .env uvicorn app.main:app --reload --port 3000   # --env-file is verplicht
uv run pytest -q                                                    # fakes, in-memory SQLite
```

Pre-commit: `uv run --extra dev --extra llm --extra otel --locked pytest -q` – dat draait CI
(`api-docker-publish.yml`) vóór de build.

Twee testsets draaien alleen met een echte database: `test_annotatie_v2_postgres.py` en
`test_projector_v2_integration.py` vragen `ANNOTATIE_TEST_DSN` (asyncpg-URL; elke test krijgt een
eigen schema), de laatste ook `ANNOTATIE_TEST_GRAPHDB_URL`. Raak je het schrijfslot, de revisies of
de projectie, draai ze dan: SQLite kent de rij-locks en de transactie-abort van Postgres niet.

Image bouwen vanaf de **projectroot** (het image neemt `packages/bronmodel` mee):
`docker build -f api/Dockerfile -t wetsanalyse-api .`

## Uitrol

De API draait als container app `<appName>-api` (`deploy/azure/main.bicep`), `maxReplicas: 3`,
non-root. Postgres is een eigen dienst (Azure PostgreSQL Flexible Server), zodat een
image-redeploy de database nooit raakt; bij een cold start overbrugt `_init_db_met_retry` de
wachttijd (`WETSANALYSE_DB_CONNECT_RETRIES`/`_BACKOFF`). `GRAPHDB_URL` wijst naar de interne GraphDB
van dezelfde straat. De verwerking is stateless per request, dus horizontaal schalen is veilig:
de v2-schrijfacties serialiseren op de database, niet in het proces.

**Ingress per straat** (`apiExtern`, default `false`):

- **productie** – intern, alleen bereikbaar binnen de container-apps-omgeving.
- **acceptatie** – publiek (`--api-extern` in `azure-infra.yml`), zodat de admin-MCP bij
  `/v1/admin/*` kan.

> De ingress zit vóór de hele app. Publiek betekent ook `/v1/annotatie`, `/v1/gesprekken`,
> `/v1/auth`, `/v1/berichten` en `/v1/feedback`, en daarmee valt de aanname onder `X-User-Id` weg:
> wie een client-token heeft, kiest zijn eigen identiteit. Op acceptatie is dat een bewuste
> afweging (proefdata); op productie niet. Een guard in `poort.yml` bewaakt dat de default `false`
> blijft en dat `--api-extern` alleen achter de acceptatie-conditie staat.
>
> `apiInternalUrl` is afgeleid van `ingress.fqdn`, en die wordt bij een publieke ingress
> `<app>.<domein>` in plaats van `<app>.internal.<domein>`. Frontend en graph-qa lopen dan via het
> publieke endpoint. Moet dit ooit naar productie, laat die twee dan eerst op de app-naam praten.

**Secrets.** De bicep zet ze als container-app-secrets en mount ze als bestanden onder
`/run/secrets/` (`llm_api_key`, `llm_config_secret`, `api_tokens`, `admin_tokens`, `database_url`).
`azure-infra.yml` roteert ze niet: GitHub environment-secret (`WA_*`) → wat er in Azure draait →
anders vers genereren. `llm-config-secret` is de Fernet-sleutel voor de API-keys van modelprofielen
én de 2FA-secrets; genereer je hem opnieuw, dan zijn alle opgeslagen keys en 2FA-inschrijvingen
onleesbaar. De job faalt bij een ontbrekend secret en wacht na het uitrollen tot elke app een gezonde
revisie draait.

Troubleshooting van de uitrol staat in [`README.md`](README.md#troubleshooting).

## Misbruik- en kostenbeheersing

Knoppen via env (0 = uit; defaults in de README): `WETSANALYSE_RATE_LIMIT_MAX`/`_WINDOW` (per
client → 429), `WETSANALYSE_ADMIN_TEST_RATE_MAX`/`_WINDOW` (krappe limiet op de verbindingstest, die
een betaalde LLM-call doet achter alleen het admin-token), `WETSANALYSE_LLM_MAX_CONCURRENCY` en
`WETSANALYSE_LLM_TIMEOUT_S`. De testfout is gesaniteerd: een vaste melding in de respons, de ruwe
providerfout alleen in het serverlog. De rate-limiter is begrensd (sweep + harde cap van 10.000
sleutels, fail-closed), zodat aanvaller-gekozen sleutels via de publieke login-route het geheugen
niet vullen. `POST /v1/auth/registratie` heeft een eigen rate limit.

De inlogrem op `/v1/auth/verify` telt alleen **missers** (fout wachtwoord, foute code), per (client-IP, userid),
plus een globale teller op twintig keer die grens. Het IP komt uit `X-Client-IP`, en alleen van de client
`frontend` (`IP_VERTROUWD` in `routers/auth.py`); de BFF leest het in `frontend/lib/clientIp.ts`. Zonder
vertrouwd IP remt hij op de userid alleen. Zo sluiten de missers van een ander de echte gebruiker niet buiten.

## Nog niet gebouwd

- **Externe IdP/OIDC.** De API is zelf de identiteitsbron.
- **Activiteit 3, verder.** Werkgebieden, begrippen en de deterministische voorstellen van Lex
  bestaan, het model voor twijfelparen en definitievoorstellen (fase C), Lex naast de kaart (fase E) en
  herbeoordeling en dekking (fase F1), begripsrelaties en opvolging (fase F2), de NL-SBB-projectie en
  Turtle-export (fase F3) en het lezen over werkgebieden heen (fase F4).
- **RegelSpraak-formalisering.** Komt later.
