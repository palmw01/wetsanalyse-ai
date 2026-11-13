# Meting: de connector Kennisgroepstandpunten (stap 7)

Soort: *meetplan* · Opgesteld: 14 november 2026 · Uitvoering: op sein van de hoofdsessie, na de bundel met stap 1–6, de
uitrol en het aanzetten op acceptatie. Plan en criteria: [`plan-connector-kennisgroepen.md`](../architectuur/plan-connector-kennisgroepen.md)
§4. Dit bestand legt de **vragen met hun kenmerken** vooraf vast, zodat de uitkomst niet achteraf wordt uitgelegd. De
uitkomst komt in `docs/architectuur/metingen/kennisgroepen-<datum>/`, met een rij in het meetlogboek.

## Opzet (licht, besluit gebruiker 13 nov 2026)

- **Eén run** van de 20 vragen, alleen de centrale agent: `extra: {"agentvorm": "centraal", "bronnen": [...],
  "bronnen_herkomst": "gesprek"}`. Dat vraagt `CENTRALE_AGENT=meten` of `aan` op acceptatie.
- Elke vraag in een **nieuw gesprek**, via de acceptatie-MCP (`lex_start`, `lex_wacht` met `vanaf=9999`); tokens uit het
  `meting`-event.
- Standaard `bronnen: ["kennisgroepen", "wetgeving_live", "kamerstukken", "rechtspraak"]`; vraag 17 met `bronnen: []`.
- Een **tweede ronde alleen als de eerste fouten laat zien**, met dezelfde vragen voor wat fout of matig was; **hoogstens
  2 rondes**.
- Elk antwoord wordt beoordeeld tegen de officiële bron: de publicatie op kennisgroepen.belastingdienst.nl
  (`bron_lezen`) en de wettekst (`graaf_lezen` of wetten.overheid.nl).

## Voorwaarden

1. De stapel #1437 → #1440 → #1441 → #1446 → #1447 → #1456 → deze PR is gemerged en uitgerold (graph-qa, api, frontend,
   bwb-import).
2. `azure-infra` → acceptatie → `deploy`: `CONNECTOR_KENNISGROEPEN=true` op graph-qa en `--kennisgroepen` op de
   import-job en de graafwacht; de deploy start de import-job.
3. De index staat: de log van de import-job toont `=== Kennisgroepen-index ===` met `Geschreven : ja` (ongeveer 1180
   standpunten). Peilen kan ook met `graaf_lezen`: `SELECT (COUNT(?s) AS ?n) WHERE { GRAPH <urn:wa:graph:kennisgroepen>
   { ?s a ?t } }`.
4. De connector staat aan in het register (beheertab, of `list_connectors` van de admin-MCP ter controle).
5. Vlak voor de run: de kenmerken hieronder opnieuw tegen de live bron gecontroleerd (`bron_lezen`). Er is een nieuw
   standpunt bij gekomen of een status is veranderd? Dan wordt de verwachting aangepast en dat staat in het verslag.

## De vragen

Kenmerken en tellingen uit de 1180 publicaties van 13 nov 2026, gelezen met `bronmodel.kennisgroepen` zoals de index ze
leest. "Verwacht" is wat goed is; een telling uit de index mag verschuiven als de bron verschuift.

| # | soort | vraag | verwacht |
|---|---|---|---|
| 1 | genoemd kenmerk | Wat staat er in kennisgroepstandpunt KG:013:2026:4? | `get_standpunt` direct; blok met statusregel en datum (12 nov 2026); noemt dat het KG:013:2018:0173 intrekt |
| 2 | per artikel, in de graaf | Welke kennisgroepstandpunten gaan over artikel 36 van de Invorderingswet 1990? | `zoek_standpunten` per bepaling: 1 geldend (KG:207:2022:3); het ingetrokken standpunt alleen als verborgen genoemd; herkomst van de koppeling zichtbaar; "ten minste" |
| 3 | per artikel, buiten de graaf | Zijn er standpunten over artikel 3.111 Wet IB 2001? | 30 geldend, 1 ingetrokken verborgen; wettekst (als die nodig is) uit `wetgeving_live` |
| 4 | wet + beleid | Wat zegt artikel 10 Wet BPM 1992, en hoe past de Belastingdienst het toe bij een lopend RDW-onderzoek? | eerst de bepaling, dan het blok beleid (KG:013:2026:4) met statusregel, zichtbaar gescheiden |
| 5 | onderwerp, woorden | Heeft de Belastingdienst een standpunt over de reisbureauregeling? | KG:210:2026:10 en KG:210:2026:8 (geldend); KG:209:2022:2 (vervallen) niet als geldend |
| 6 | lijstvraag, nieuwste | Geef de vijf nieuwste standpunten van de kennisgroep Invordering. | KG:207:2026:1, KG:207:2025:6, :5, :4, :3, nieuwste eerst, blok `stukken` |
| 7 | lijstvraag, metadata | Welke standpunten over de rubriek Eigenwoningschuld publiceerde de kennisgroep Onroerende zaken in 2025? | filters kennisgroep + rubriek + periode: KG:051:2025:5, :6, :8, :9; volledig |
| 8 | telvraag | Hoeveel standpunten zijn er over de AWR, per belastingsoort? | 90 geldend (13 ingetrokken apart); verdeling uit de metadata (o.a. IB 37, AWR 24, Vpb 13); zegt wat geteld is |
| 9 | ingetrokken | Geldt standpunt KG:204:2023:7 nog? | ingetrokken; vervangen door KG:204:2024:14; nooit als geldend beleid |
| 10 | vervangen | Welk standpunt vervangt KG:013:2018:0173? | KG:013:2026:4 uit de index; het oude staat niet op de site (alleen via Woo) |
| 11 | status/waarde | Is een kennisgroepstandpunt bindend voor de rechter? | geen juridisch advies; de status zoals de bron die geeft (beleid, bindt de inspecteur), met vindplaats |
| 12 | niet gepubliceerd | Is er een kennisgroepstandpunt over de hondenbelasting? | "geen gepubliceerd standpunt gevonden", met de grens (niet alles wordt gepubliceerd; een gemeentelijke belasting valt buiten de kennisgroepen) |
| 13 | tekststand | Is artikel 25, zeventiende lid, van de Invorderingswet 1990 gewijzigd sinds standpunt KG:202:2022:13? | melding tekststand uit de graaf (standpunt van 5 apr 2022); geen eigen gok |
| 14 | ketting / omgekeerd | Welke standpunten noemen ECLI:NL:HR:2013:64, en wat zegt die uitspraak? | KG:013:2026:4 en KG:013:2023:3 via de koppeling `uitspraak`; daarna `get_uitspraak` |
| 15 | wetsgeschiedenis | Op welke Kamerstukken baseert standpunt KG:063:2026:6 zich? | kst-31930-3 en kst-31930-9, herkomst tekst (sinds deze PR); leest een Kamerstuk alleen als dat gevraagd wordt |
| 16 | vergelijken | Wat is het verschil tussen de standpunten KG:041:2026:8 en KG:204:2022:30 over de expatregeling? | beide gelezen; verschillen met letterlijke citaten (salarisnorm bij 30 jaar tegen dubbele huisvesting na afloop) |
| 17 | connector uit | vraag 1 met `bronnen: []` | melding zonder model, knop *Zet Kennisgroepstandpunten aan* |
| 18 | AVG | Wie is de heer X in standpunt KG:204:2022:23? | herleidt niemand; zegt dat de casus geanonimiseerd is |
| 19 | controle wettekst | Wat staat er in artikel 9 van de Invorderingswet 1990? | route `bepaling_lezen`, geen standpunt, tokens gelijk aan de nulmeting |
| 20 | buiten scope / verwarring | Wat vindt de Belastingdienst van mijn aangifte? | geen casusadvies; hoogstens algemene standpunten, geen persoonsgegevens gevraagd |

## Wat er per vraag wordt vastgelegd

Route, toolaanroepen (`tool_execution`), grounding, het sjabloon en de blokken, de statusregel, de bronnenlijst (brontype
`standpunt`), de tokens en de duur. Ruw in `runs.jsonl`, het oordeel (goed, matig, fout, met reden) in `ronde-1.md`.

## Criteria

Zoals plan §4, vooraf vastgelegd:

- **Garanties, 20/20:** geen standpunt onder een `doel` of als wettekst; elk standpuntblok heeft de statusregel en een
  datum; een ingetrokken of vervallen standpunt nooit als geldend; elk citaat letterlijk in de gelezen tekst; een
  uitgezette connector wordt niet gebruikt.
- **Kwaliteit:** minstens 17 goed en 0 fout na de laatste ronde.
- **Kosten:** tokens per vraag, naast de vergelijkbare vragen van Rechtspraak en Kamerstukken.

## Wat er al vóór de meting verbeterd is

Bij het vastzetten van vraag 15 bleek dat de lezer een Kamerstuk alleen herkende als `kst-`-id of als link. Een
standpunt citeert het meestal als "Kamerstukken II 2008/09, 31 930, nr. 3". Van de 530 standpunten die Kamerstukken
noemen, kregen er daardoor 143 geen enkel Kamerstuk als verwijzing. Deze PR herkent die citeervorm
(`bronmodel.kennisgroepen.kamerstukken_in_tekst`, herkomst `tekst`); daarna blijven er 16 over: brieven van de Eerste Kamer
met een letter en citaten zonder dossier of nummer, die bewust niet koppelen.
