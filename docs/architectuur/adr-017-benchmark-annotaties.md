# ADR-017 — Een regressiebenchmark voor annotaties

Status: **concept, voorstel aan de hoofdontwikkelaar** · Datum: 2026-11-12 · Technisch voorstel en plan: los
document bij dit ADR · Hangt samen met:
[ADR-001](adr-001-hybride-jas-pijplijn.md), [PLAN spoor A](../PLAN.md) (V7),
[referentieset](../wetsanalyse/referentieset/README.md), [meetlogboek](metingen/README.md)

## Context

Wie de annotatieketen verandert, wil snel zien wat dat met de uitvoer doet. Het eval-harnas
(`tools/graph-qa/eval/`) meet de keten tegen sets die geen juridische referentie zijn: de ankerset en de
conceptset zijn *silver*, en referentieset v1 is *provisional*.

Deze benchmark is een **regressietest**: hij laat zien of en waar de uitvoer verandert ten opzichte van een
annotatie die een analist heeft afgerond. Of een verandering goed of fout is, beslist de ontwikkelaar, die haar
zo nodig aan een analist voorlegt. Een lagere score is dus niet vanzelf een slechtere keten. De benchmark staat
naast de andere tests en vervangt er geen; blijkt hij overbodig, dan gaat hij weer weg.

Drie dingen maken dit lastiger dan het lijkt:

- **Een annotatielaag blijft veranderen.** Na het kiezen kan iemand haar heropenen, aanvullen of verwijderen.
  Een referentie mag dat niet.
- **De keten leest en schrijft de lagen.** Bij een afgeronde laag weigert hij te annoteren (`AFGEROND` in
  `agent/bron_annotatie.py`), en bij een voltooide dekking hergebruikt hij wat er ligt. Een benchmarkcasus ís
  zo'n afgeronde laag: een gewone run zou weigeren, of de referentie teruggeven en alles vinden. En een run die
  wél schrijft, verandert de laag die als referentie dient.
- **Eén cijfer wordt een oordeel.** PLAN §*Leidende principes*: "Kwaliteit laat zich zien in indicatoren, niet
  in één cijfer."

## Besluit

### 1. Een benchmarkcasus is een bevroren momentopname

- **Een beheerder kiest** een geverifieerde annotatie: een annotatie waarvan elke laag in beeld door een analist
  is afgerond (`geaccordeerd`). De beheerder is verantwoordelijk voor de keuze; de software toetst alleen dat de
  annotatie afgerond is. Hoeveel analisten er naar kijken, is een werkafspraak van de beheerders;
  de software legt alleen het afronden vast. Wie beoordeelde en afrondde staat al in de audit van de annotatie; de casus neemt dat
  over. Kiezen is een beheerhandeling met een naam, zoals de andere in `/v1/admin`.
- **De api legt een momentopname vast**: de bron-IRI van de bepaling in beeld, per bronnode de bronhash en de
  snapshot-id, en per element de klasse, de ankers (bronnode, start, eind, fragment), het subtype, de lifecycle en
  de herkomst (voorstel van Lex of door de analist gemarkeerd). Verworpen elementen gaan mee als *verworpen*.
- **De momentopname verandert nooit.** Wat er daarna met de annotatie gebeurt, raakt de casus niet. Wordt ze
  heropend, gewijzigd en opnieuw gekozen, dan krijgt de casus een nieuwe versie (§2).
- **Wat niet meegaat:** relaties tussen markeringen (ADR-011) en impliciete partijen. Die komen er pas bij als
  er een scorer voor is.

### 2. Casussen en sets hebben versies

- Een casus heeft een vaste id (de bepaling in beeld) en een versie per momentopname. Een gewijzigde
  annotatie opnieuw kiezen geeft een nieuwe casusversie; de oude blijft bestaan.
- Een set heeft een naam en een lijst casusversies. Een casus toevoegen, vervangen door een nieuwere versie of
  uit de set halen maakt een **nieuwe setversie**; de id is een SHA-256 over de casusversies, op dezelfde manier
  als `manifest.json` van referentieset v1. Een oude setversie blijft opvraagbaar en draaibaar.
- **Een benchmarkcasus is geen `adjudicated` casus** in de zin van referentieset v1 (meer beoordelaars,
  adjudicatie). De benchmark meet verandering, geen juridische juistheid.
- **Oordelen van analisten komen niet in de repo.** De set staat in de opslag van de omgeving (§3).

### 3. Een run draait de keten in meetmodus

**Meetmodus** (`modus: "benchmark"` in de agent):

- **niets schrijven**: geen batch, geen gesprek, geen bericht, geen werkvoorraad, geen artefactversie. Een run
  verandert dus ook in productie niets;
- **de laag van de casus zelf nooit lezen**: anders geeft de keten de referentie terug;
- **twee varianten** voor de andere annotaties in het systeem, omdat die ook de toekomstige annotaties
  beïnvloeden:
  - *zonder*: geen `get_annotatiedekking`, `get_annotatieweergave` of `search_annotaties`; de keten krijgt een
    lege poort, zoals `GesprekAnnotaties` in de eval;
  - *met*: de keten leest de andere lagen zoals in het gewone pad, met de lagen van de casus eruit gefilterd.
  De variant staat in de manifest. De eerste levering bouwt *zonder*; *met* volgt;
- **niet boeken op een tokenbudget** van een gebruiker. Het verbruik wordt wel gemeten en bij de run bewaard,
  met een plafond per run (zoals `SUITE_TOKENS`); boven het plafond stoppen de overige casussen en heten ze
  *niet gemeten*;
- **de bron van nu**: de keten leest de wettekst uit de graaf. Wijkt de bronhash af van de casus, dan wordt de
  casus niet gescoord maar gemeld als `bron_gewijzigd`;
- **een storing is geen slechte score**: een casus die sneuvelt op de provider of het plafond heet *niet
  gemeten* en telt niet mee, net als in het harnas.

**Een run is een indicatie, geen poort.** Hij blokkeert geen merge en geen uitrol.

**De run draait in de eval-job.** Een ontwikkelaar start hem met `azure-infra` → `eval`, set `benchmark`, met de
setversie, het aantal herhalingen en de variant als invoer. Dat is de bestaande weg om de keten live te meten: de
job draait hetzelfde image als de app, binnen de omgeving, tegen de echte graaf. De api roept graph-qa dus niet
aan; de richting tussen de diensten blijft zoals hij is.

**De job krijgt een eigen, begrensd token.** Hij moet de casussen lezen en de uitkomst vastleggen, maar mag
niets anders. Daarvoor:

- een client-id `benchmark` in `WETSANALYSE_API_TOKENS`, met een eigen lijst in `agent_toegang.py`: alleen de
  routes onder `/v1/benchmark/*`. Een laag, gesprek of werkgebied schrijven weigert de api dus;
- in de job onder **eigen env-namen** (`BENCHMARK_API_URL`, `BENCHMARK_API_TOKEN_FILE`), niet onder
  `WETSANALYSE_API_URL`/`_TOKEN`. Daardoor blijft `legt_zelf_vast` onwaar en probeert de keten niet eens te
  schrijven. Twee sloten: de configuratie van de job en de allowlist van de api.

**Dit wijkt af van wat er nu is**, op twee punten:

1. `agent_toegang.py` begrenst nu precies één client (`graph-qa`); `benchmark` is de tweede. De functie `mag`
   wordt een tabel van client naar lijst, en `tests/poort/test_agent_toegang.py` bewaakt ook de nieuwe lijst.
2. De eval-job draagt nu bewust geen api-token (`main.bicep`: "een meting mag de gemeten toestand niet
   veranderen"). Met dit token verandert dat niet in de bedoeling – de job kan de gemeten toestand nog steeds
   niet wijzigen – maar wel in de vorm: de job praat met de api.

**De api bewaakt het plafond.** Bij het starten van een run rekent de api een schatting uit (de mediaan van de
gemeten tokens per casus × casussen × herhalingen); ligt die boven het plafond, dan start de run niet. Tijdens de
run telt de api het gemelde verbruik op en weigert verdere uitkomsten boven het plafond. Het plafond staat in de
database, zoals het tokenbudget, zodat het zonder redeploy te wijzigen is.

De variant *met* is pas echt zinvol op de annotaties van productie; voor nu draait de benchmark alleen op
acceptatie, achter een vlag die standaard uit staat, zoals de andere proefvlaggen.

### 4. Scores en verschillen, geen cijfer

Per run, per herhaling en over de herhalingen (gemiddelde en bandbreedte):

- **garanties**: letterlijkheid, geldige klassen;
- **dekking van de referentie**: recall op de geaccordeerde elementen, met de exacte span en de span-IoU,
  apart voor de elementen die de analist zelf markeerde;
- **klasse**: juistheid van de klasse bij een gevonden span;
- **precisie** tegen de geaccordeerde én de verworpen elementen;
- **dezelfde maten per JAS-klasse**;
- **tokens** (invoer, uitvoer, cache lezen, cache schrijven) en **duur**, per casus en voor de hele run.

Omdat het een regressietest is, toont het rapport per casus ook **de verschillen**: welke elementen erbij kwamen,
wegvielen of van klasse of grens veranderden, ten opzichte van de referentie en van de vorige run op dezelfde
setversie.

Er is geen totaalscore en geen geslaagd/gezakt op de indicatoren. Een cijfer of een automatisch oordeel kan
later, met een eigen besluit over de weging.

- **De scorers zijn die van het harnas** (`eval/scoring.py`), uitgebreid met matchen op ankers (bronnode en
  offsets) naast tekst. Eén definitie van "recall".
- **De ruwe uitkomst wordt bewaard** (de elementen per casus en per herhaling), zodat een nieuwe scorer een
  oude run opnieuw kan scoren zonder model, zoals `run_eval.py --herscoor`.

### 5. Elke score weet waartegen hij gemeten is

Een run draagt een **manifest**: de setversie, de variant, de straat, de commit en het image van api en graph-qa
(het OCI-label `org.opencontainers.image.revision`), het modelprofiel en model, de detectorversies en
`agent_versie`, het aantal herhalingen, de start- en eindtijd en het totale tokenverbruik. De geschiedenis van de
runs is te filteren op set en setversie. Zo staat elke score naast de testset en de versie van de applicatie.

### Routes in de api

| Route | Wat |
|---|---|
| `POST /v1/admin/benchmark/casussen` | een afgeronde annotatie kiezen als casus (een nieuwe casusversie als ze al bestond) |
| `GET /v1/admin/benchmark/casussen` · `/{id}/versies` | de casussen en hun versies |
| `POST /v1/admin/benchmark/sets` · `PUT /{id}` · `GET` · `GET /{id}/versies/{versie}` | sets, hun samenstelling en versies |
| `GET /v1/admin/benchmark/runs` · `/{id}` | de geschiedenis en één run met scores, verschillen en manifest |
| `GET /v1/admin/benchmark/sets/{id}/versies/{versie}/export` · `POST /v1/admin/benchmark/import` | een setversie als JSON bewaren en terugzetten, met de hash als controle |
| `PUT /v1/admin/benchmark/plafond` | het tokenplafond per run |
| `POST /v1/benchmark/runs` · `GET …/{id}/casussen` · `PUT …/{id}/uitkomsten/{casus}/{herhaling}` · `POST …/{id}/afronden` | alleen het `benchmark`-token: een run openen (de api toetst het plafond), de casussen lezen, de uitkomst melden |

## Gevolgen

- De meetmodus is een tweede pad door de annotatieketen. Hij verschilt alleen in de poort, de schrijver
  (geen) en de meter (eigen plafond). Een test bewaakt dat het gewone pad en de meetmodus *zonder* op dezelfde
  bron dezelfde kandidaten opleveren.
- De benchmark controleert alleen de gekozen annotaties. Hij vervangt het eval-harnas en de andere tests niet.
- Een benchmarkrun kost tokens op de LLM-resource van de straat. Het plafond per run en het aantal herhalingen
  staan in de manifest.
- PLAN spoor A blijft staan: de meetmodus voegt geen semantiek toe aan de keten.
- Vier PR's: **api** (casussen en versies, sets, runs met manifest, de client `benchmark`), **graph-qa**
  (meetmodus, de scorers op ankers en de verschillen), **infra** (de eval-job met het token, de set in
  `azure-infra`), **frontend** (een beheertab *Benchmark*: casussen kiezen en de scores).

## Gekozen voor de eerste levering

- **Herhalingen:** 5 per casus.
- **Omvang:** één casus, om te zien hoe het gaat.
- **Opslag:** de database van acceptatie, met export en import per setversie. Het risico daarvan staat in het
  technische voorstel.
- **Productie:** nog niet. Eerst kijken of dit is wat men wil.

## Open keuzes

1. **De afwijkingen in §3**: een tweede begrensde client in `agent_toegang.py`, en een eval-job die met de api
   praat. Akkoord van de hoofdontwikkelaar nodig.
2. **De export van een setversie**: waar dat bestand buiten de repo staat.
3. **Productie**: of en wanneer, en dan de variant *met*.
