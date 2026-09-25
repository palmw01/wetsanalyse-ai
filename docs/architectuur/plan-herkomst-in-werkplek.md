# Plan — annotatieketen volledig zichtbaar en controleerbaar: graaf, SSE, werkplek, exports

Status: **goedgekeurd, in uitvoering** · Datum: 2026-09-25 · Soort: *plan* · Vervolg op ADR-001 (PR 18, #510)

Vervangt de eerste versie van dit document (#515). Besluiten van de gebruiker staan in §Context.

## Context

Sinds ADR-001 PR 18 (#510) is de hybride keten de enige route. Elk element draagt een volledig
`trace` (bewijs, detectoren, regels, besluit, modelvraag, validatie, twijfel, resolutie), elke beurt
een `run` met meting (dekking A/B, ongedekte zinsdelen, gedegradeerd). Die rijkdom komt nu nergens
goed aan:

- **Graaf** (`api/app/graaf_projectie_v2.py`): bewust plat – klasse als stringliteral, geen
  alternatieven/aandacht/herkomst/beoordelingen/dekking; PROV alleen achter `JAS_PROJECTIE_PROV`
  (nergens aan) en dun. Er is **geen controle** of de graaf klopt met Postgres; SHACL draait alleen
  in tests op fixtures.
- **Productie projecteert helemaal niet**: de api daar mist `GRAPHDB_URL` (infra niet uitgerold
  sinds 22 sep; de bicep zet hem wel).
- **SSE/werkplek**: `trace` komt in `frontend/` niet voor; wel nog dode Critic-UI.
- **Exports**: `trace` alleen als JSON-blob.

Doel (gebruiker): alles zo rijk mogelijk, én aantoonbaar dat de annotatiegraaf netjes wordt
opgebouwd. Besluiten gebruiker: regel-id's als leesbare naam met id in tooltip; vrij selecteren
blijft naast voorgestelde grenzen; exacte modelvraag in de JSON-export; beoordelingen in de graaf
**zonder personen**; productie-infra herstellen als eerste stap.

Een klikbare mockup (voorbeeldbeurt art. 9 lid 1 IW 1990) is met de gebruiker doorgenomen.

UI-richting (besluit gebruiker): de bestaande opzet blijft – **gespreksvenster + annotatie als
zijpaneel** – en volgt zo dicht mogelijk de UI-patronen van Claude:
- **Stappenblok** boven het antwoord, ingeklapt ("Annoteerde art. 9 lid 1 in 14 s · 1 modelcall"),
  uitklapbaar naar de fasen met duur – zoals Claude's denk-/zoekstappen (PR 2 levert de fasen + duur).
- **Antwoord als proza met citatie-chips**; een chip opent een **bronkaart** (regelnaam, id, soort,
  uitleg) – zoals Claude's bronvermeldingen. Zelfde chips in de "waarom"-tekst van een element (PR 5).
- **Artefact-kaartje** in de thread opent het **zijpaneel**; kop met titel, **revisiekiezer** (de
  laagrevisies, zoals Claude's versies), segmentschakelaar **Tekst / Dekking / Graaf** (zoals
  Preview/Code; Graaf = de Turtle van de markering + graafcontrole-status), export-icoon, sluiten.
  Op smalle schermen wordt het paneel schermvullend.
- **Tekst selecteren** in het paneel → zwevende balk *Markeer als… / Vraag Lex*; Vraag Lex (ook op
  een kaart) zet een **citaat-chip** in het invoerveld met drie vervolgvragen – zoals "reply with quote".
- Kaarten als compacte rijen; open kaart toont uitleg met citaties, de andere lezing als chip,
  grenskeuze-chips (naast vrij selecteren), "Wat het model zag" (ingeklapt) en de acties.
- Ongedekte zinsdelen onderstreept in de tekst; tab Dekking met dimensies en *Zelf markeren*.
- Huisstijl (lintblauw, Fira, JAS-kleuren) blijft; indeling en bediening volgen Claude.
Extra frontend-werk t.o.v. het plan: revisiekiezer (api: revisiehistorie per laag lezen uit audit),
citatie-/bronkaartcomponent, stappenblok met duur (graph-qa: duur per fase in het status-event).

## Werkwijze

Per PR een branch → PR → `poort` → squash-merge (zoals de ADR-roadmap). Contracten additief,
beide SSE-wegen gelijk, drift-tests mee. Elke PR die graph-qa raakt ook testen zónder spaCy
(`uv run --isolated --extra dev pytest -q`), want CI heeft de nlp-extra niet.

## PR-volgorde

### PR 0 — Productie-infra bijwerken (geen code)
`azure-infra` → productie → `wat-if`; diff aan gebruiker tonen; na akkoord `deploy` (goedkeuring
environment). Controle: api-env heeft `GRAPHDB_URL`; reconcile-lus projecteert (logs
`annotatie_v2_geprojecteerd`). Productie heeft nu nul lagen, dus alleen het register verschijnt.

### PR 1 — Graafcontrole (eerst meten, dan verrijken)
Nieuw `api/app/graafcontrole.py`, hergebruikt `graaf_projectie_v2.bouw_graaf`, `_select`, `_repo`,
`REGISTER`, `graph_iri`, `laag_iri` en `app/shacl.valideer`:
- **Consistentie per laag**: Postgres-revisie = register-revisie = `jas:revisie` in de graph;
  element-id's gelijk; per element klasse, lifecycle, verouderd en ankers (bron, offsets, hash,
  citaat) gelijk. Verweesde graphs (graph zonder laag) en ontbrekende graphs apart.
- **Bouwcontrole**: `bouw_graaf(Postgres-stand)` isomorf met de opgehaalde graph (`rdflib.compare.isomorphic`)
  – vangt elke drift tussen projectiecode en opgeslagen graaf, ook na een schemawijziging.
- **SHACL** op de opgehaalde graphs, per groep (`RdfStructuur` / `JasModel`) gerapporteerd.
- **Invarianten** live: geen `urn:bwb:`-subject en geen `urn:bwb-ns:`-predicaat in `urn:jas:graph:*`,
  geen domain/range in de repository (ASK-queries).
- Ontsluiting: `GET /v1/admin/annotatie/graafcontrole` (admin-token), tool in
  `tools/wetsanalyse-admin-mcp/`, en een lichte variant (tellingen, geen SHACL) in de reconcile-lus
  met logveld `annotatie_graaf_afwijking` + Grafana-paneel (`deploy/azure/grafana/dashboard-keten.json`).
- `pyshacl` van dev- naar runtime-dependency van de api (nodig voor de live SHACL; imagegrootte meten
  en in de PR melden).
- Tests: controle tegen een rdflib-`Dataset` (fake SPARQL-endpoint via de injecteerbare `_select`),
  met mutaties: ontbrekend element, verkeerde revisie, verweesde graph, SHACL-fout, `urn:bwb`-subject.

### PR 2 (A) — SSE: de beurt vertelt wat er gebeurde (graph-qa)
- Nieuw event `dekking` vóór de elementen (per bronnode dimensies uitgevoerd/overgeslagen/gedegradeerd
  + ongedekte zinsdelen met offsets), bron `analyse.meting["dekking"]` in `nodes/annotatie.emit_node`.
- Statusregels per fase (Taalanalyse / Detectie / Besluit / Classificatie / Review) via `_stap`,
  pure functies naast `_analysemelding`.
- Gedegradeerde taalanalyse ook als `waarschuwing`-event.
- **Dekking naar de api**: `Batch.dekking` (api `annotatie_v2_contracts.py`) additief met
  `structureel` (dimensies + ongedekt) en `procesdekking` (A); graph-qa stuurt ze mee
  (`agent/beurt.py`, `wetsanalyse_api.py`); opslag in `annotatie_v2_dekking.inhoud`; weergave levert ze.
- Contract-drift-test (`tests/test_contract_drift.py`), `VLUCHTIGE_TYPES` ongewijzigd, `dekking` ook
  in `BerichtInvoer` zodat heropende gesprekken hem tonen.

### PR 3 (G) — Rijke annotatiegraaf (api), schema v3
- **Vocabulairegraaf** `urn:jas:graph:vocabulaire`: de 13 klassen én 16 officiële begrippen als
  `skos:Concept` (`skos:prefLabel`, `skos:definition`, `jas:herkenningsvraag`,
  `jas:uitdrukkingswijze`, `dcterms:source` "H2:NN", `jas:jasVersie` "1.0.10"), plus de JAS-regels
  (PRIORITY) en detectorregels (id + leesbare naam). Gegenereerd uit de skill/profielen door een
  script naar `api/app/vocabulaire/jas-v3.ttl`, met drift-test (patroon: `scripts/genereer_jas_klassen.py`
  + `test_methode_drift.py`), zodat de api geen graph-qa hoeft te importeren.
- **Markering** (naast wat er is): `jas:klasse` → concept-IRI (`jas:klasseNaam` blijft voor de
  zoekquery), `jas:subtype` (zie PR 3b), `jas:aandacht`, `jas:herkomst` (agent/mens),
  `oa:motivatedBy oa:classifying` + tweede `oa:hasBody` = het concept, `jas:alternatief`-nodes
  (klasse-IRI + reden), `jas:grensoptie`-nodes uit `spanopties`.
- **PROV standaard aan** (vlag weg): de run als `prov:Activity` `urn:jas:run:<run_id>` met model
  (`prov:SoftwareAgent urn:jas:agent:model:<naam>`), agentversie, `prompt_hash`, `methode_versie`,
  taalmodel, `prov:startedAtTime`; per element een besluit-activiteit met `jas:beslistDoor`,
  regels/detectoren (IRI's naar de vocabulaire), bewijscodes, twijfelcodes, resolutieregel,
  validatiecodes en `jas:modelvraag`.
- **Beoordelingsspoor zonder personen**: per beslissing een `jas:Beoordeling` (soort, `prov:atTime`,
  van/naar-klasse, of het een agentvoorstel wijzigde) – nooit actor of user-id.
- **Laag**: `jas:dekking` per bronnode (dimensies + ongedekte zinsdelen als
  `oa:SpecificResource` met selectors), link naar de laatste run en de snapshot.
- Schemaversie 3: `SCHEMA`-triple en `zoek_kandidaten`/`reconcile` herkennen v3 en projecteren alle
  lagen opnieuw; zoekquery ongewijzigd in betekenis.
- Invarianten blijven: geen `urn:bwb:`-subject, geen domain/range/subClassOf, OA-ontologie niet laden.
  `resolve_begrip` filtert al op `NS`; `test_annotatielaag_isolatie.py` met de vernieuwde fixture
  (`test_graph_qa_fixture_volgt_de_projectie` regenereert/bewaakt die).
- SHACL-shapes (`api/app/shapes/jas-v2.ttl` → `jas-v3.ttl`) uitbreiden voor alle nieuwe nodes;
  `jas-annotatie-ontologie.md` bijwerken; graafcontrole (PR 1) toetst v3 automatisch mee.

### PR 3b — JAS-subtype machineleesbaar (graph-qa)
`jas_subtype` op het element waar deterministisch vast te stellen (profielen noemen al
variabele/variabelewaarde, parameter/parameterwaarde, delegatiebevoegdheid/-invulling): bv. getal/
bedrag/datum-literal → *waarde*; delegatieformule → *bevoegdheid*. Onzeker → leeg, nooit geraden.
Detectorregels in `detectoren/regels/*.yaml` met hun vier testsoorten. Loopt mee in trace, export, graaf.

### PR 4 (B) — Dode legacy weg (frontend + api)
Frontend: `critic_rondes`, `critic_suggestie`, `critic`, `OntbrekendLijst`, `suggestie`-pad uit
`lib/types.ts`, `lib/agentEvents.ts`, `lib/annotatieNode*.ts`, `lib/threadItem.ts`, componenten
(`ArtefactInhoud`, `ReviewQueue`, `WerkplekClient`, `AnnotatieDetailClient`, `SelectiePopover`).
Api: `CriticSuggestie`/`suggesties` uit `annotatie_v2_contracts.py` en de store; `critic_checked` uit
shapes/labels. Drift-tests (`frontend/lib/jas.ts`, contract-drift) mee.

### PR 5 (C) — Werkplek legt het spoor uit (frontend)
- "Waarom?"-uitklap op de elementkaart: bewijs als zinnen met leesbare regelnaam (id in tooltip, uit
  de vocabulaire), wie besliste (regel/model/reviewer), twijfelreden in gewone taal, resolutieregel,
  subtype; ruwe modelvraag achter "technisch detail".
- Gele alternatief-chips met hun reden; één klik = één beslissing (bestaand).
- Beurtsamenvatting in de tijdlijn ("14 voorstellen · 9 op vaste regels · 1 modelcall · 2 voor jou")
  en een gedegradeerd-badge.

### PR 6 (D) — Dekking in het documentpaneel (frontend)
Ongedekte zinsdelen subtiel onderstreept in de brontekst (`DocumentPaneel`), met "markeer zelf" via
de bestaande `SelectiePopover`; dimensie-overzicht per bronnode. Bron: weergave-`dekking` uit PR 2.

### PR 7 (E) — Exports (api)
- CSV: platte kolommen `besloten_door`, `regels`, `detectoren`, `twijfel`, `resolutieregel`,
  `mogelijke_klassen`, `subtype`, `validatie`, `aandacht`, `herkomst`.
- PDF: herkomstregel per element; kop met beurtmeting en dekking, ongedekte zinsdelen als bijlage.
- JSON v3: volledig incl. `trace.vraag`, run-meting en dekking; JSON-schema in de repo.
- **Turtle-export**: dezelfde `bouw_graaf` + vocabulaire-verwijzingen, zodat export en graaf één bron hebben.

### PR 8 (F) — Grenskeuze (api + frontend)
`spanopties` als "andere grens"-chips; nieuwe beslissing `grens` (contract additief, audit);
vrij selecteren via de selectiepopover blijft.

### PR 9 (H, optioneel) — Lex zoekt op de rijkdom
`search_annotaties` (`api/app/graaf_projectie_v2.zoek_query` + `Zoekvraag`, graph-qa `annotatie_tools.py`)
filters op `herkomst`, `beslistDoor`, twijfel, aandacht, subtype; `test_toolverdeling`/retrieval-smoke mee.

Afhankelijkheden: 0 → 1; 2 vóór 3 (dekking) en 6; 4 vóór 5; 3 vóór 7 (Turtle) en 9; 5 vóór 8.

## Kritieke bestanden
- api: `app/graaf_projectie_v2.py`, `app/shacl.py`, `app/shapes/`, `app/annotatie_v2_contracts.py`,
  `app/annotatie_v2_store.py`, `app/annotatie_v2.py` (export), `app/routers/admin.py`, `pyproject.toml`
- graph-qa: `agent/nodes/annotatie.py`, `agent/beurt.py`, `agent/wetsanalyse_api.py`,
  `agent/jas_pipeline/keten.py`, `agent/jas_pipeline/detectoren/regels/`, `tests/test_contract_drift.py`
- frontend: `lib/agentEvents.ts`, `lib/types.ts`, `lib/annotatieNodeAdapter.ts`, `components/werkplek/*`
- docs: `docs/wetsanalyse-workbench/jas-annotatie-ontologie.md`, `docs/architectuur/plan-herkomst-in-werkplek.md`
- deploy: `deploy/azure/grafana/dashboard-keten.json`, `tools/wetsanalyse-admin-mcp/`

## Verificatie
- Per PR: api `uv run pytest`, graph-qa met én zonder spaCy, frontend `npm test`/typecheck, `poort`.
- Graaf offline: test die een batch van de échte keten (graph-qa-fixture → api-store in SQLite →
  `bouw_graaf`) SHACL-conform maakt in beide groepen en isomorf terugleest; mutatietests laten de
  graafcontrole elke afwijking melden.
- Graaf live (acceptatie, na PR 1 en na PR 3): één bepaling annoteren via de werkplek, beoordelen,
  dan `graafcontrole` → 0 afwijkingen, SHACL conform, invarianten groen; steekproef-SPARQL op
  herkomst/beoordeling/dekking. Na de volgende release hetzelfde op productie.
- Werkplek: handmatige doorloop op acceptatie (Chrome) – uitklap, chips, dekking, export in 4 formaten.
