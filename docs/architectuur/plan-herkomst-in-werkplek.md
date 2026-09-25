# Plan — de nieuwe annotatieketen zichtbaar maken: SSE, werkplek en exports

Status: **voorgesteld** · Datum: 2026-09-25 · Soort: *plan* · Vervolg op ADR-001 (PR 18, #510)

## Waarom

Sinds PR 18 draagt elk voorgesteld element een volledig `trace`, en de beurt een `run` met een
meting. Die informatie wordt nu opgeslagen (Postgres, `annotatie_v2_elementen.inhoud.trace`) en
zit in de JSON-export, maar **de werkplek toont er niets van** (`trace` komt in `frontend/` niet
voor). Tegelijk toont de werkplek nog onderdelen van de oude keten die niet meer gevuld worden
(`critic_rondes`, de `ontbrekend`-lijst, `suggestie`).

Wat er per element al is (`jas_pipeline/keten._spoor` + `_vervolledig`):

| veld | inhoud | vraag van de jurist |
|---|---|---|
| `kandidaat.bewijs[]` | detector, regel-id, code, grammaticale relatie | *waarom is dit gemarkeerd?* |
| `kandidaat.mogelijke_klassen` | de klassen die het profiel toeliet | *wat was er nog meer mogelijk?* |
| `kandidaat.spanopties[]` | kern / NP / clause met offsets | *had de grens anders gekund?* |
| `beslissing` | status, klasse, `door` (regel/model), reden | *wie besliste: regel of model?* |
| `vraag` | de exacte regel die het model zag | *wat is het model precies gevraagd?* |
| `validatie[]` | `V_*`-bevindingen | *klopt het technisch?* |
| `twijfel[]` | DETECTOR_CONFLICT / CLASSIFIER_ABSTAIN / ZELFDE_SPAN / DEGRADED_PARSE | *waarom geel?* |
| `resolutie[]` | reviewer-actie + resolverregel (`R-*`) | *wat deed de reviewer, en welke regel gold?* |

En per beurt (`run.instellingen.meting`): kandidaten, deterministisch vs. model, `llm_calls`,
`review_calls`, `per_status`, `twijfels`, `resolutie`, `validatie`, **`dekking`** (A: elke kandidaat
afgehandeld; B: per bronnode de twaalf detectiedimensies en de **ongedekte zinsdelen**) en
`gedegradeerd` (taalanalyse niet beschikbaar).

## Drie sporen

### 1. SSE — de beurt vertelt wat er gebeurde (graph-qa)

Nu: statusregels `Detectie · …` en `Classificatie · N kandidaten, M zonder model …`, daarna `run` en
`element`s. Voorstel:

1. **`dekking`-event** (nieuw, additief) vóór de elementen: per bronnode de uitgevoerde,
   overgeslagen en gedegradeerde dimensies plus de ongedekte zinsdelen (tekst + offsets). Vervangt
   inhoudelijk het vervallen `ontbrekend`: geen gok van een model over wat mist, maar een meting van
   welke tekst geen enkele detector raakte. Nooit geformuleerd als recall.
2. **Statusregels per fase** in plaats van één: `Taalanalyse · spaCy nl_core_news_md` (of
   `· gedegradeerd: alleen lexicale detectoren`), `Detectie · 23 kandidaten`, `Besluit · 9 zonder
   model`, `Classificatie · 14 in 1 call`, `Review · 3 twijfelgevallen → 2 bij jou`. Zelfde
   `_stap`-idioom; pure functies zodat ze testbaar blijven.
3. **Gedegradeerd is een `waarschuwing`**, niet alleen een statusregel: de beurt slaagt, maar de jurist
   moet weten dat subject/object/bijzin-detectie ontbrak.
4. Contractdiscipline: event-types additief, beide wegen (`/v1/chat` en run-events), `VLUCHTIGE_TYPES`
   ongewijzigd (`dekking` blijft staan bij cappen), `agent/beurt.py` legt `dekking` vast bij het
   chatbericht (veld in `BerichtInvoer`, contract-drift-test).

### 2. Werkplek — het spoor uitleggen, niet dumpen (frontend)

1. **"Waarom?"-uitklap op de elementkaart**: bewijs als leesbare zinnen ("tijdsregel T-TERMIJN-01:
   *binnen … weken*"), wie besliste (regel / model / reviewer), en bij geel de twijfelreden in
   gewone taal plus de resolutieregel. De ruwe `vraag` achter een "technisch detail"-knop.
2. **Geel wordt een keuze met context**: de alternatieven-chips bestaan al; toon er per chip de reden
   bij (welk patroon wees welke klasse aan). Eén klik blijft één beslissing in de audit.
3. **Grensalternatieven**: `spanopties` als "andere grens"-chips die de markering in de tekst
   verschuiven (nieuwe beslissing `grens`, api-contract additief). Het model kiest geen grens meer
   (PR 17); de jurist wel.
4. **Dekkingsbalk in het documentpaneel**: ongedekte zinsdelen subtiel onderstreept in de brontekst,
   met "markeer zelf" vanuit de bestaande selectiepopover. Vervangt de `OntbrekendLijst`.
5. **Beurtsamenvatting** in de tijdlijn: "14 voorstellen · 9 op vaste regels · 1 modelcall · 2 voor
   jou" en een gedegradeerd-badge.
6. **Opruimen**: `critic_rondes`, `critic_suggestie`, `OntbrekendLijst` en het `suggestie`-pad
   verwijderen uit types, parsers (`lib/agentEvents.ts`) en componenten. Oude data bestaat niet
   meer (acceptatie en productie gewist op 25 sep 2026).

### 3. Exports — herkomst die een ander kan controleren (api)

Nu: JSON bevat alles (inclusief `trace`); CSV stopt `trace` als JSON-blob in één kolom
`provenance`; PDF toont alleen `geproduceerd_door`. De v1-export (`annotatie_export.py`) draagt nog
Critic-velden en `critic_checked`.

1. **CSV**: vaste, platte kolommen in plaats van de blob — `besloten_door`, `regels` (regel-id's),
   `detectoren`, `twijfel`, `resolutieregel`, `mogelijke_klassen`, `validatie`. Filterbaar in een
   spreadsheet; de JSON blijft de volledige bron.
2. **PDF**: per element één regel "Herkomst: regel T-TERMIJN-01 · geen model" of "model (1 keuze uit 3)
   · reviewer: HUMAN_REVIEW (R-ONENIGHEID)", en in de kop de beurtmeting en de dekking (met de
   ongedekte zinsdelen als bijlage). Geen claim van recall.
3. **JSON**: `export.versie` → 3, met `run`-meting per laag erbij en een JSON-schema in de repo,
   zodat een afnemer weet wat `trace` bevat.
4. **RDF/PROV** (bestaat achter `JAS_PROJECTIE_PROV`): na 1–3 beoordelen of hij standaard aan kan;
   de export kan dan ook als Turtle.
5. **Opruimen**: v1-export en `STATUS_LABEL["critic_checked"]` alleen laten staan zolang contract 1
   bestaat; anders mee in de v1-verwijdering.

## Volgorde (PR's)

| PR | wat | afhankelijk van |
|---|---|---|
| A | graph-qa: `dekking`-event, statusregels per fase, gedegradeerd-waarschuwing; beurt legt `dekking` vast | — |
| B | frontend: dode legacy-UI weg (Critic-rondes, ontbrekend, suggestie) | — |
| C | frontend: "Waarom?"-uitklap + twijfelreden bij gele chips + beurtsamenvatting | A (samenvatting), B |
| D | api + frontend: dekkingsbalk en ongedekte zinsdelen in het documentpaneel | A |
| E | api: CSV-kolommen, PDF-herkomst, JSON v3 + schema | — |
| F | api + frontend: grenskeuze uit `spanopties` als beslissing | C |

A, B en E kunnen parallel. F raakt het api-contract en de audit; die komt als laatste.

## Open vragen

1. Mogen de regel-id's (`T-TERMIJN-01`) zichtbaar zijn voor de jurist, of alleen een leesbare naam
   uit de regel-YAML (`omschrijving`)? Voorstel: naam, met het id in de tooltip.
2. Grenskeuze (F): mag de jurist alleen tussen `spanopties` kiezen, of ook vrij slepen? Vrij slepen
   bestaat al via de selectiepopover; F voegt alleen de voorgestelde grenzen toe.
3. Moet de export de exacte modelvraag (`trace.vraag`) bevatten? Die bevat een fragment van de
   wettekst (openbaar) en geen persoonsgegevens; voorstel: ja, alleen in JSON.
