# ADR-012: Multi-agent regie binnen een werkgebied

**Status:** aangenomen, 7 nov 2026. Ontwerp en bouwvolgorde (PLAN spoor S). De eerste stap is de bronselectie per
deelvraag en het annoteren per bepaling. Begrippen komen later.

## Context

Een jurist wil binnen één werkgebied in één keer vragen: "zoek per deelvraag de bronnen en annoteer de kern". Nu kan
dat alleen als losse beurten, na elkaar, in één gesprek. Het fundament voor meer tegelijk ligt er al:

- **Een beurt is een run op de server** (`agent/runstore/`). Een run overleeft losraken, heeft een eigenaar
  (`X-User-Id`) en kan gestopt worden met een vlag. Er loopt hoogstens één run per gesprek (een unieke index, 409).
- **Een actie kiest agent en taak zonder model** (`models.ACTIE_TAAK`, ADR-005).
- **De taken die we willen verdelen bestaan al**:
  - de bronselectie per deelvraag (spoor J): de stand staat bij de api, het zoeken gaat zonder model;
  - het annoteren van een werkgebied (`werkgebied_annotatie.py`): de werkvoorraad komt van de api, er is een
    bevestiging met een schatting, en per bepaling draait een gewone beurt (`reeks_stroom`).
- **Gesprekken horen bij een werkgebied** (spoor G1), en de sidebar toont de runstanden (E6).

Wat ontbreekt:

- iets dat het werk verdeelt;
- een koppeling tussen een gesprek en zijn deelgesprekken;
- het budget verdelen;
- botsingen voorkomen voordat ze tokens kosten;
- duidelijke poorten voor de jurist.

**Grenzen die gemeten of vastgelegd zijn:**
- graph-qa draait met 0,5 vCPU en 1 Gi, en op acceptatie met `minReplicas: 0` en `maxReplicas: 2`;
- er is geen globale limiet op runs;
- de classifier stuurt per beurt tot 4 batches tegelijk naar het model (`CLASSIFIER_PARALLEL`);
- de Postgres-pool van de runstore heeft per replica 4 verbindingen;
- de SDK herhaalt een aanroep twee keer, ook bij 429 en 529;
- GraphDB heeft één replica en antwoordt in milliseconden;
- het tokenbudget kent geen reservering, alleen een controle "is het op?";
- twee runs op dezelfde bepaling botsen pas bij het schrijven (412), dus de tweede run heeft zijn tokens dan al
  verbruikt.

## Besluit

### Een regisseur als vaste workflow

De regisseur is een vaste workflow (ADR-010, laag 2) in `agent/regie/`. Hij draait in een **regiegesprek** binnen een
werkgebied. Het is een eigen stroom in `_stroom_voor`, net als de reeks, en geen node in de graaf: hij start zelf runs.

```
regiegesprek:  plan (code) → bevestiging → [kind 1 | kind 2 | …] (≤ REGIE_PARALLEL tegelijk) → bundel
kindgesprek:   een gewone run met een actie, in hetzelfde werkgebied
```

**Eén ingang.** `POST /v1/runs` en de regisseur gebruiken dezelfde functie `start_beurt(request, gebruiker)`:
budgetcontrole, `runs.start` en `_stroom_voor`. Een kind-run is dus een gewone run. Hij heeft zijn eigen gesprek, de 409,
de eigenaar uit `X-User-Id`, het vastleggen bij de api en het boeken van het verbruik.

Er is geen HTTP-aanroep naar zichzelf. graph-qa is niet van buiten bereikbaar, en een kind zou dan op de andere replica
kunnen landen, waar de regisseur het niet kan volgen.

### Het plan komt uit code

`agent/regie/plan.py` is zuiver. Het leest wat er ligt bij de api: het werkgebied, de actieve deelvragen, de bronselectie
per deelvraag en de annotatie-werkvoorraad. Het maakt daar een `Plan` van: de taken, een schatting en wat buiten het plan
valt. Het `plan_id` is een hash van de inhoud. Dezelfde stand geeft hetzelfde plan.

Er zijn twee opdrachten:

- **`bronnen`**: één taak per deelvraag die nog niet klaar is.
  - De regisseur draait vooraf zelf één keer de zoekrun (`bronnen_run.zoek_run`). Die is idempotent en geldt voor het
    hele werkgebied, dus de kinderen wachten niet op elkaar.
  - Elk kind opent daarna de bronselectie van zijn deelvraag (de actie `bronselectie`, het onderwerp is de deelvraag) en
    eindigt bij het compacte kaartje.
  - Er draait geen model en het kost geen tokens.
- **`annoteren`**: de werkvoorraad (status *nieuw*, rol *analyseren*), disjunct verdeeld.
  - Elke eenheid hoort bij de eerste deelvraag waaronder ze valt, in de volgorde van de deelvragen.
  - Elk kind krijgt de lijst van zijn eenheden (`eenheden`, een deelverzameling van de werkvoorraad die de api
    teruggeeft).
  - Samen gaat het om hoogstens `PLAFOND` (40) eenheden. Wat erbuiten valt, noemt het plan.

**Een opdracht geven** kan door een klik (de acties `regie_bronnen` en `regie_annoteren`) of door een getypte zin. Een
getypte zin herkent de tekstroute `is_regievraag`: "per deelvraag" samen met bronnen of annoteren, binnen een
werkgebied. Een tekstroute krijgt negatieven in `eval/golden_gesprek.jsonl` (de regel uit de aanvulling op ADR-005).

### De jurist beslist

- **Een agent levert voorstellen.** Opnemen, uitsluiten, beoordelen, afronden en accorderen blijven handelingen van de
  jurist. De regisseur roept die endpoints nooit aan, en een test legt vast welke api-aanroepen hij wel doet.
- **"Zoek de bronnen en annoteer de kern" is twee regieronden, geen keten.** Annoteren gaat alleen over bronnen die de
  jurist heeft opgenomen. Een voorstel uit de bronnenronde is nog geen bron. De bundel van de eerste ronde eindigt
  daarom met de suggestie *Annoteer wat je opnam*.
- **Altijd eerst een bevestiging** (`soort: "regie"`). Die toont het plan, de schatting, het budget en wat er niet
  meegaat. Starten mag alleen met `bevestigd` gelijk aan het `plan_id` van de stand van nu. Anders zegt Lex dat het plan
  veranderde, en geeft hij een nieuwe bevestiging.
- **Een annotatiekind** krijgt `bevestigd = len(eenheden)`. Zo blijft de bestaande poort van `werkgebied_annotatie`
  gelden, binnen de bevestiging van het regiegesprek.

### Ouder en kind in de api

- **`gesprekken.ouder_id`** (leeg voor een gewoon gesprek). De api eist dat de ouder een eigen gesprek is in hetzelfde
  werkgebied.
- **Een regie is een object bij de api** (`regies`): werkgebied, regiegesprek, gebruiker, opdracht, `plan_id`, plan,
  status, budgetaandeel en tijden.
  - Er loopt hoogstens **één regie per werkgebied** en **één per gebruiker**, afgedwongen met unieke indexen (409).
  - Het slot per gebruiker voorkomt dat twee regies hetzelfde budget verdelen.
- **De werkplek** toont het regiegesprek met zijn kindgesprekken eronder. *Stop alles* stopt de regierun, en die stopt
  zijn kinderen. In de runstore draagt een kind-run `ouder_run_id`. Stoppen is een vlag, dus het werkt ook over
  replica's heen.
- **Een regiegesprek verwijderen** stopt de kinderen. De kindgesprekken blijven bestaan, zonder ouder, net zoals
  annotaties blijven staan als hun gesprek weg is.

### Budget

- **Vooraf.**
  - Het plan schat het verbruik: per bepaling de mediaan van de laatste annotatiebeurten, met een bovenkant. De
    bronnenronde kost niets.
  - Past de bovenkant niet in wat er nog resteert (`/v1/verbruik/controle`), dan **maakt de code het plan kleiner**
    tot het past, en zegt waarom. Dat gebeurt vóór de bevestiging.
- **Verdeeld.**
  - Elk kind krijgt een aandeel van 1,25 × zijn schatting.
  - Tussen twee eenheden stopt een kind zodra zijn eigen verbruik plus één eenheid meer zou zijn dan zijn aandeel. Dat
    staat naast de bestaande controle bij de api.
- **De eerlijke grens.**
  - Een eenheid die al loopt, maakt altijd af: een halve annotatie is erger dan een kleine overschrijding.
  - De overschrijding is daardoor hoogstens één eenheid per lopend kind.
  - Een reservering bij de api komt er nu niet.

### Hoeveel tegelijk

`REGIE_PARALLEL` staat standaard op 2, met een maximum van 3 (een `asyncio.Semaphore` in de regisseur). Waarom zo laag:

- **CPU.** De taalanalyse (spaCy) rekent op de CPU, en graph-qa heeft 0,5 vCPU.
- **Model.** Twee kinderen geven tot 8 classifieraanroepen tegelijk. De limiet van de provider is niet bekend. De
  SDK-retry vangt een piek op, maar is geen planning.
- **Postgres.** Elk event kost schrijfwerk in een pool van 4.
- **GraphDB** is geen knelpunt.

De regisseur volgt een kind op dezelfde replica met `await run.taak`, en leest daarna één keer de events. Er is geen
peiling per kind.

**`minReplicas: 0`.** Een regie overleeft geen herstart en geen inschalen.
- Een kind dat dan nog loopt, eindigt via de drain als `gestopt`, met een bericht. Een kind dat nog niet gestart was,
  start niet meer.
- Zolang de werkplek open is, houden de meekijkende stroom en de peiling van de runstanden de replica wakker.
- De bevestiging zegt dat. Hervatten is een nieuwe regie op de stand van nu: de werkvoorraad en de bronselectie zijn
  idempotent, en wat klaar is, blijft.
- `minReplicas: 1` voor graph-qa is een open keuze voor de eigenaar, omdat het geld kost.

### Botsingen

- **Binnen een regie**: geen overlap, door de verdeling in het plan. Geen twee kinderen werken aan dezelfde bepaling.
- **Tussen regies**: het slot per werkgebied.
- **Tegenover handwerk of een collega**: de revisiecontrole op de laag (412) en de afgeronde laag (409) blijven het
  vangnet. De bundel noemt zo'n botsing onder *wacht op jou*, niet onder *mislukt*.

### De bundel

Na afloop leest de regisseur de stand bij de api. Hij gebruikt geen modeltekst. Hij schrijft het bericht in drie lijsten:

1. **Opgeleverd**: per kind het kindgesprek en het artefact.
2. **Wacht op jou**: per deelvraag de voorgestelde bronnen in het paneel, per bepaling de gele markeringen, en de
   botsingen.
3. **Mislukt of niet aan bod**: met de reden (budget, gestopt, fout of plafond).

**Events.** `regie` (start en eind, met het plan) en `regie_taak` (per kind: start en eind, met de uitkomst). Het bericht
draagt het artefact `{soort: "regie", ref: {werkgebied_id, regie_id}}`.

### Eén trace

Kind-runs starten in de context van de regierun, dus ze vallen onder dezelfde trace. Dat gebeurt omdat `create_task` de
contextvars erft. Daarnaast komen er:

- **spans**: `graph_qa.regie`, en per kind `graph_qa.regie.taak`, met `regie_id`, `ouder_run_id` en `run_id`;
- **logregels**: dezelfde velden;
- **afloop**: één logregel `regie_afloop` met tellingen en verbruik.

## Bouwvolgorde

1. Dit document en het spoor in `PLAN.md`.
2. api: `gesprekken.ouder_id` en de regies.
3. graph-qa: één ingang (`start_beurt`) en `ouder_run_id`, met stoppen dat doorwerkt naar de kinderen.
4. graph-qa: het plan in code, en `eenheden` bij het annoteren van een werkgebied.
5. graph-qa: de regisseur, met routering, events en spans.
6. Werkplek: kindgesprekken onder het regiegesprek, het regiekaartje met *Stop alles*, de bevestiging en de bundel.
7. Meting op acceptatie, alleen na akkoord van de gebruiker. De bronnenronde is gratis, het annoteren kost tokens.

**Meten.** De wandkloktijd tegenover de reeks, het verbruik tegenover de schatting, geen dubbele laag, één trace, en
*Stop alles*. De meting gaat via de acceptatie-MCP.

## Wat nog open is

- **Begrippen in de regie.** Begrippen hangen af van de annotaties en van het hele werkgebied, dus ze laten zich slecht
  per deelvraag verdelen.
- **Een reservering bij de api** in plaats van het aandeel per kind.
- **`minReplicas: 1` voor graph-qa** tijdens een regie.
- **Een Grafana-paneel** voor regies.

## Waarom niet anders

- **Een model als regisseur.** Het plan volgt uit de stand bij de api, en die is in code te lezen. Een model zou kunnen
  kiezen wat de code al weet (ADR-010), en dezelfde vraag moet hetzelfde plan geven.
- **Alles in één run, met parallelle takken.** Dan delen de takken één checkpointer-thread en één gesprek, en ziet de
  jurist niet per taak wat er gebeurde. Een kindgesprek is ook na afloop een plek om door te vragen.
- **Een kind per bepaling.** Dat geeft tientallen gesprekken voor één werkgebied. Per deelvraag sluit aan bij hoe de
  jurist het werk ordent, en de verdeling per bepaling zit in de lijst `eenheden`.
- **Doorketenen van bronnen naar annoteren.** Dan annoteert Lex voorstellen die de jurist nog niet heeft opgenomen. Dat
  is precies de poort die bij de jurist hoort.
- **Een tweede ingang (een eigen regie-endpoint, of HTTP naar zichzelf).** Dan bestaan er twee wegen naar een run, met
  elk hun eigen controles.
