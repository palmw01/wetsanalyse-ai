# Plan: Instellingen › Aanpassingen, en Werkwijze weg

Stand: 15 nov 2026, versie 3. Status: **goedgekeurd 15 nov 2026; PR 1–4 gebouwd** (#1545 navigatie, #1546 Methodes,
Agents en de werkplaats, #1547 Connectors en Modellen; PR 4 zit in #1546, zodat *Nieuw concept* nooit tussen twee PR's
wegvalt), #1550 het model per agentprofiel en stap (op #1544, de api van *Model per rol*), #1548 de agentvorm uit
graph-qa (mergen na A6). Het uitgangspunt is door de gebruiker goedgekeurd
en daarna bijgestuurd (Werkwijze verdwijnt helemaal); de uitwerking hieronder nog niet. Vooral frontend; de
modelkeuze per agent leunt op het api- en graph-qa-werk van de sessie *Model per rol* (zie *Afstemming*).

## Uitgangspunt (goedgekeurd 15 nov 2026, bijgestuurd dezelfde dag)

Naar het voorbeeld van Claude, waar Instellingen een groep **Aanpassingen** heeft (Skills, Connectors, Plug-ins):

| Claude | Lex |
|---|---|
| Skills | **Methodes** – de skills in `.claude/skills/` |
| Subagents | **Agents** – de agentprofielen in `.claude/lex-agents/` |
| Connectors | **Connectors** |
| API-sleutels / model | **Modellen** – de modelprofielen |
| Plug-ins | (geen) |

1. Instellingen krijgt de groep *Aanpassingen* met Methodes, Agents, Connectors en Modellen, elk als lijst met
   *Voeg toe* waar dat kan (werkplaats: concept → proef op acceptatie → actief na uitrol), en een zoekveld in de
   navigatie.
2. **Het model hoort op het agentprofiel** (zoals `model:` bij een Claude Code-subagent), niet in een losse tabel "per
   rol". Stappen die geen agent zijn (supervisor, classifier, reviewer, …) krijgen elk ook zo'n regel.
3. **Werkwijze verdwijnt helemaal**: geen sidebaritem, geen pagina, ook geen alleen-lezen *Hoe Lex werkt*. Wat nuttig
   was, verhuist naar Methodes en Agents; de uitleg van routes, ketens en supervisor staat in de repo (ADR's,
   `CLAUDE.md`'s) en niet meer in de app. `/werkwijze` verwijst door.

Buiten dit plan: C7 (wijziging voorstellen als concept-PR, `catalogusVoorstellen`) wordt elders verwijderd.

## Wat er nu is

- **Werkwijze** (`/werkwijze`, ADR-014): eigen pagina, vierde hoofditem in de sidebar. `WerkwijzeClient` toont de hele
  catalogus per concept (kennis en methode, vaste ketens, agents, handelingen, ingangen, controles), het blok *Hoe een
  vraag binnenkomt* (`AgentvormBlok`) en, met de vlag `WERKPLAATS`, de groep *Concepten* met *Nieuw concept*.
  Detailpagina's `/werkwijze/<soort>/<naam>` (`OnderdeelPagina`) en `/werkwijze/concepten/<id>` (`ConceptPagina` met
  editor, versies, *Loopt achter*).
- **Instellingen** (`?instellingen=<tab>`, `Dialog` 56rem × 42rem, tabs links): *Persoonlijk* (Account, Beveiliging,
  Verbruik, Gesprekken, Berichten, Rondleiding) en voor een beheerder *Beheer* (Modelprofielen, Gebruikers, Aanvragen,
  API-tokens, Connectors, Berichten beheren, Feedback). Geen zoekveld; de groepkop verschijnt alleen voor een beheerder.
- **Connectors staan er twee keer**: als beheer-tab met aan/uit en audit (`ConnectorsPanel`), en in de catalogus als
  soort `connector`, alleen lezen.
- **Het model van Lex** komt nu uit env (`LLM_MODEL…`); de modelprofielen in de api bereiken Lex niet. De sessie *Model
  per rol* maakt dat per stap instelbaar (`llm_stap.Rol`, 14 rollen plus de subagent).

### Wie de catalogus nog gebruikt (`git grep`, 15 nov 2026)

- **Het register zelf blijft**: `bronmodel/catalogus.py` en `tools/graph-qa/agent/catalogus.py` (`catalogus()`,
  `onderdeel()`). Ze dragen de drift-tests van graph-qa (`tests/test_catalogus.py`: elk register, elke actie, elk
  commando, elke route en elke controle heeft precies één onderdeel; ook `test_catalogus_methode.py`,
  `test_context_per_agent.py`, `test_methodegrenzen.py`, `test_skill_zonder_code.py`, `test_bronpakket.py`), en
  `bronmodel.catalogus.Stap` wordt gebruikt door `jas_pipeline/keten.py` en `begrippen_pipeline/keten.py`. Dat is
  bewaking van de code, geen weergave.
- **De endpoints `GET /v1/catalogus[/{soort}/{naam}]`** (graph-qa `api/main.py`) en de BFF-routes `app/api/catalogus/**`
  hebben één afnemer: de werkwijze. Ze blijven nodig, want Methodes, Agents en Connectors lezen er hun beschrijving uit
  (doel, connectors, sjablonen, methodetekst, herkomst).
- **`agentvorm()`** in `agent/catalogus.py` en het veld `agentvorm` in `GET /v1/catalogus` bestaan alleen voor het blok
  *Hoe een vraag binnenkomt*. (Het woord *agentvorm* komt ook elders in graph-qa voor als runtimebegrip; dat blijft.)
- **Geen andere afnemers**: de admin-MCP, de acceptatie-MCP, `nl-sbb-begrip`, de api en Lex zelf roepen de catalogus niet
  aan. `lib/commandos.ts` noemt hem alleen in commentaar (de drift-test staat in graph-qa).
- **Links naar `/werkwijze`**: alleen in de frontend (sidebar, `onderdeelPad`, `conceptPad`, `versiePad`, `achterPad`,
  de browsertests) en in twee ADR's (ADR-014 §*Inzien*, ADR-016 §B over de editor). Lex, graph-qa, de api en de
  rondleiding linken er niet naar.

## De navigatie

```
┌ Instellingen ───────────────────────────────────────────────────────── ✕ ┐
│ [ Zoek in instellingen ]   │                                             │
│                            │   (paneel van de gekozen tab)               │
│ PERSOONLIJK                │                                             │
│   Account                  │                                             │
│   Beveiliging              │                                             │
│   Verbruik                 │                                             │
│   Gesprekken               │                                             │
│   Berichten                │                                             │
│   Rondleiding              │                                             │
│ AANPASSINGEN               │                                             │
│   Methodes                 │                                             │
│   Agents                   │                                             │
│   Connectors               │                                             │
│   Modellen      (beheerder)│                                             │
│ BEHEER          (beheerder)│                                             │
│   Gebruikers               │                                             │
│   Aanvragen            (2) │                                             │
│   API-tokens               │                                             │
│   Berichten beheren        │                                             │
│   Feedback             (1) │                                             │
└────────────────────────────┴─────────────────────────────────────────────┘
```

- **Drie groepen, kop altijd zichtbaar.** `INSTELLINGEN_TABS` krijgt `groep: "persoonlijk" | "aanpassingen" | "beheer"`
  en `alleenBeheerder: boolean` in plaats van `admin`. De kop komt uit `groep`, niet meer uit "de eerste admin-tab".
- **Modelprofielen verhuist van Beheer naar Aanpassingen** als *Modellen* (sleutel `modellen`; `tabUitParam` en
  `tabUitPad` vangen `modelprofielen` en `beheer/modelprofielen` op). Alleen voor een beheerder: een profiel draagt een
  API-sleutel. **Connectors** verhuist ook (zie hieronder).
- **Zoeken in de navigatie**: één veld bovenaan de tabkolom; het filtert de tabs op label en een paar trefwoorden per
  tab (`trefwoorden`, bv. Methodes: skill, methode, JAS, JRM; Agents: subagent, profiel, model; Modellen: API-sleutel,
  endpoint). Een groep zonder treffer verdwijnt. Het zoekt niet in de panelen; elke lijst heeft een eigen zoekveld.
  Escape wist eerst het veld, daarna sluit het venster.
- **Mobiel**: het venster is daar een sheet van onderen met de tabs als horizontale strook; met 15 tabs scant dat niet
  meer. Op een telefoon toont het venster eerst de navigatie als lijst met groepkoppen en het zoekveld, en een gekozen
  tab vervangt die lijst (*‹ Instellingen* terug). Eén gedrag van `Tabs` onder `sm:`, geen tweede component.

## Eén lijstpagina-patroon

De vier tabs gebruiken één nieuwe component, **`components/instellingen/AanpassingLijst.tsx`**, gebouwd uit wat er al
is (`SettingGroup`-kop, `OverzichtBalk`, `Groep`/`GroepRij`, `StatusLabel`, `MeerMenu`, `Menu`, `Button`). Geen
variant per tab: wat verschilt (de rijen, de groepen, de knop) komt binnen als data.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Methodes                                                 [+ Voeg toe ▾] │
│ De methode die Lex volgt, als skill. Een methode voert zelf niets uit.  │
│                                                                         │
│ ( In Lex (2) ) ( Concepten (3) )               [ Zoek op naam of doel ] │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Wetsanalyse                                     [Draait nu]       ⋯ │ │
│ │ Methode Wetsanalyse met het JAS · 9 rollen · versie 4.0             │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ Wetsuitvoering                                  [Draait nu]       ⋯ │ │
│ │ Juridisch Referentiemodel (JRM 2) · nog aan geen rol gekoppeld      │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

  + Voeg toe ▾
  ┌──────────────────────────────┐
  │ Nieuwe methode               │   leeg concept, alleen de naam (nu: Nieuw concept)
  │ Vanuit een methode in Lex …  │   kies er een; = de knop Bewerken (uit_image)
  └──────────────────────────────┘
```

- **Segmenten *In Lex* / *Concepten*** (het analogon van *Ontdekken* / *Van jou*), als `OverzichtBalk`-chips met
  tellers. *In Lex* is wat in het image draait (uit de catalogus), *Concepten* wat jij maakte of wat met je gedeeld is
  (de werkplaats). Met de werkplaats uit (productie) is er geen segment *Concepten* en geen *Voeg toe*.
- **⋯ per rij** alleen waar iets te doen is: bij een onderdeel in Lex *Bewerken als concept* (of *Open mijn concept*);
  bij een concept *Openen* en *Intrekken*.
- **+ Voeg toe** alleen bij `stand.aan && stand.mag_maken`, en alleen voor een soort in `IN_EDITOR`. Geen *Maak met Lex
  aan* (dat gaat via het gesprek, artefactmodel) en geen *Upload*.
- **Geen filter- of sorteerknop**: bij deze aantallen volstaan zoeken en de groepen.
- Zoekterm, segment en geopend onderdeel staan in de URL naast de tab: `?instellingen=methodes&segment=concepten&q=…`,
  `?instellingen=agents&onderdeel=agentprofiel/definitie`. Een tabwissel laat ze vallen.

### Detail in het venster, de editor als pagina

- **Een onderdeel uit *In Lex* opent als tweede niveau in het venster** (`onderdeel=`), met *‹ Methodes* terug. Eén
  detailcomponent, `AanpassingDetail`, met de kaarten die per soort horen (zie de tabs hieronder), opgebouwd uit wat
  `OnderdeelPagina` nu per soort toont. Alles in één kolom: `SplitDetail` kiest zijn kolommen op de schermbreedte
  (`lg:`), en in een paneel van ±42rem wordt de hoofdkolom anders te smal.
- **Wat het detail niet meer toont**: de stappen van een workflow, *Leunt op* / *Gebruikt door* naar ketens, routes en
  controles, de tests en waar het in de repo staat. Dat is uitleg voor wie aan Lex bouwt; die staat in de repo.
- **Een concept opent als eigen pagina**, `/aanpassingen/concepten/<id>`: de editor heeft tot tientallen bestanden, een
  balk onderaan en een `beforeunload`-bewaker, en een concept is een artefact met een eigen pagina (besluit 13 nov 2026).
  Kruimelpad *Instellingen › Methodes › naam*, terug naar `?instellingen=methodes&segment=concepten`.

## De vier tabs

### Methodes

- *In Lex*: de catalogus-onderdelen van soort `methode` (nu Wetsanalyse en Wetsuitvoering). Per rij het doel, hoeveel
  rollen eraan hangen en de versie.
- Het detail: het doel, de herkomst (bron, licentie), de versie die draait, en de **methoderollen** van die methode als
  lijst met hun methodetekst (opklapbaar). Een rol is geen eigen rij meer.
- *Concepten*: werkplaats-soort `skill`. *Voeg toe*: ja (*Nieuwe methode*, *Vanuit een methode in Lex*).

### Agents (met de modelkeuze)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Agents                                                  [+ Voeg toe ▾]  │
│ Wie een vraag beantwoordt: elk profiel met een eigen opdracht,          │
│ connectors, sjablonen en model.                                         │
│                                                                         │
│ ( In Lex (8) ) ( Concepten (0) )               [ Zoek op naam of doel ] │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Centrale agent                                   Model [Standaard▾] │ │
│ │ Beantwoordt een vraag zelf en zet subagents in                      │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ Definitie                                        Model [Sonnet   ▾] │ │
│ │ Wat een begrip in de wet betekent · 2 connectors · 1 sjabloon       │ │
│ │ …                                                                   │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ STAPPEN ZONDER AGENTPROFIEL  12                                         │
│ Een losse modelstap. Ook die krijgt een model.                          │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Supervisor – kiest wie een vraag krijgt          Model [Standaard▾] │ │
│ │ JAS-classifier – klasse per kandidaat     ⚠      Model [Standaard▾] │ │
│ │ JAS-reviewer – twijfelgevallen            ⚠      Model [Standaard▾] │ │
│ │ Intake werkgebied · Deelvragen voorstellen · Deelvraag verbeteren · │ │
│ │ Begrip vergelijken · Begripskaart · Kaartactie · Toelichting bij    │ │
│ │ een bepaling · Stukcontrole · Subagent                              │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ ⚠ Een ander model voor het JAS-oordeel verandert de annotaties; meet    │
│   eerst (ADR-010).                                                      │
└─────────────────────────────────────────────────────────────────────────┘

  Detail (tweede niveau)                                         ‹ Agents
  ┌─────────────────────────────────────────────────────────────────────┐
  │ Definitie                                        Model [Sonnet   ▾] │
  │ Wat een begrip in de wet betekent.                                  │
  │ CONNECTORS   Wetgeving live · Kamerstukken          (naar Connectors)│
  │ SJABLONEN    Antwoord bij een bepaling                              │
  │ METHODE      Wetsanalyse, rol definitie            (naar Methodes)  │
  │ OPDRACHT     de instructie uit het profiel (opklapbaar)             │
  └─────────────────────────────────────────────────────────────────────┘
```

- *In Lex*: de agentprofielen uit `.claude/lex-agents/` (catalogus-soort `agentprofiel`). Per rij wat het doet en
  hoeveel connectors en sjablonen het heeft; in het detail de connectors, de sjablonen, de methoderol en de opdracht.
- **Per rij de modelkeuze** – *Standaard* (het model uit de omgeving) of een modelprofiel. De keuze staat in de rij en in
  het detail en geldt direct (net als de connector-schakelaar), met een audit. Alleen een beheerder met 2FA ziet de
  keuzelijst; een analist ziet het gekozen model als tekst (`Model: Standaard`).
- **Stappen zonder agentprofiel**: een vaste groep onderaan *In Lex*, met dezelfde keuzelijst per stap; het zoekveld
  filtert ook deze rijen. Het zijn de rollen uit `llm_stap.Rol` die bij geen profiel horen, plus de subagent. Namen,
  korte uitleg en groep komen uit de api-catalogus van *Model per rol* (`app/llm_rollen.py`), niet uit de frontend.
  Het is de enige plek waar de supervisor nog in de app staat: als stap met een model, niet als uitleg van de routering.
- De JAS-classifier en -reviewer dragen een waarschuwing (besluit gebruiker 15 nov 2026: instelbaar, met waarschuwing).
- Een profiel dat ergens gekozen is, kan in *Modellen* niet weg: de api geeft 409 en het venster zegt bij welke agents
  of stappen het in gebruik is.
- *Concepten*: werkplaats-soort `agentprofiel`. *Voeg toe* zodra het profiel in de editor kan (B5); tot dan geen knop.
  Een concept-profiel krijgt de regel `model:` in zijn frontmatter als voorstel; wat Lex gebruikt, kiest de beheerder
  hier.

### Connectors: één lijst

- Iedereen ziet de bronnen naast de wet (catalogus-soort `connector`), met doel en of de straat ze aanbiedt; in het
  detail de beschrijving en welke agents hem gebruiken.
- Een beheerder met 2FA ziet per rij de schakelaar aan/uit en in ⋯ *Audit tonen*; zonder 2FA staat `BeheerVraagt2fa`
  boven de lijst in plaats van de schakelaars.
- `ConnectorsPanel` gaat op in deze tab; de api-calls blijven (`listConnectors`, `zetConnector`, `connectorAudit`).
- *Concepten*: werkplaats-soort `mcp`, met *Voeg toe* pas als de MCP-stap van de werkplaats er is.

### Modellen

- De huidige `ProfielenPanel` (lijst, editor, *Test verbinding*, standaardprofiel) op `AanpassingLijst`: per rij naam,
  model, endpoint en *Standaard*; *+ Voeg toe* opent de bestaande `ProfileEditor` (een gewoon formulier, geen
  werkplaats).
- Per profiel staat erbij waar het gekozen is (*Gebruikt door: Definitie, Supervisor*), met een link naar *Agents*.
- **Geen blok "Model per rol" hier**: die keuze staat op de agents en de stappen.
- Alleen voor een beheerder, met de 2FA-melding zoals nu.

## Wat verdwijnt (opruimen)

Frontend:

- `app/werkwijze/**` wordt drie doorverwijzingen (zie *Routes*); `components/werkwijze/WerkwijzeClient.tsx`,
  `Agentvorm.tsx` en de pagina-schil van `OnderdeelPagina` gaan weg. `ConceptenGroep` gaat op in `AanpassingLijst`. De
  concept-componenten (`ConceptPagina`, `ConceptEditor`, `ConceptVersies`, `ConceptAchter`) verhuizen naar
  `components/aanpassingen/` en blijven.
- In `lib/catalogus.ts`: `CONCEPT_LABEL`, `CONCEPT_VOLGORDE`, `perConcept`, `parseAgentvorm` en de types `Agentvorm*`;
  `SOORT_LABEL` houdt alleen de soorten die een tab tonen. `ModelLabel` (*Zonder model* / *Model met tools*) gaat weg:
  het gekozen model zegt nu meer.
- Het sidebaritem *Werkwijze* (en `werkwijzeActief`).
- `scripts/test-werkwijze.mjs` en `scripts/test-werkwijze-breedte.mjs` worden `test-aanpassingen.mjs` en
  `test-aanpassingen-breedte.mjs` (zie *Tests*); de verwijzingen in `package.json`, het commentaar in
  `components/ui/Badge.tsx` en `frontend/CLAUDE.md` gaan mee.
- `lib/catalogus.test.ts`: de tests op wat weggaat.

graph-qa (raakt het image, dus pas na de A6-meting en via de hoofdsessie):

- `agentvorm()` in `agent/catalogus.py` en het veld `agentvorm` in `GET /v1/catalogus`, met de tests die alleen dat
  blok toetsen (`test_catalogus_agentvorm.py` voor zover het de weergave betreft; de drift-tests die nagaan dat elke
  overdracht en elk profiel een onderdeel heeft, blijven).

Blijft bewust:

- `bronmodel/catalogus.py`, `agent/catalogus.py` (`catalogus()`, `onderdeel()`) en hun drift-tests: bewaking van de
  code, en de bron voor Methodes, Agents en Connectors.
- `GET /v1/catalogus[/{soort}/{naam}]` en de BFF-routes: de nieuwe tabs lezen eruit.
- Het veld `concept` (ADR-014 §7) in het bronmodel: de graph-qa-tests gebruiken het; zonder weergave is het een
  kandidaat voor later opruimen, niet in deze stapel.

Docs:

- ADR-014 §*Inzien* en ADR-016 §B (editor onder de werkwijze) krijgen een regel *Bijgewerkt 15 nov 2026*: de catalogus
  wordt niet meer als geheel getoond; methodes, agents en connectors staan onder Instellingen › Aanpassingen, de editor op
  `/aanpassingen/concepten/<id>`. Een ADR wordt niet herschreven.
- `docs/architectuur/catalogus.md` (werkdocument): idem.
- `frontend/CLAUDE.md` §*De werkwijze van Lex* wordt §*Aanpassingen*, §*De werkplaats* krijgt de nieuwe paden, en de
  beschrijving van het instellingenvenster de groepen. Root-`CLAUDE.md` (component 2) noemt de sidebar en de
  Aanpassingen.

## Routes en deep links

- `/werkwijze` → `/workbench?instellingen=agents`.
- `/werkwijze/<soort>/<naam>` → `methode` → methodes met `onderdeel=`; `rol` → methodes met de methode van die rol;
  `agentprofiel` → agents met `onderdeel=`; `connector` → connectors met `onderdeel=`; elke andere soort (workflow, route,
  controle, tool, regelset, agent, sjabloon) → agents zonder `onderdeel`.
- `/werkwijze/concepten/<id>[?…]` → `/aanpassingen/concepten/<id>[?…]`, met `versie`, `met`, `achter` en `bestand` mee.
- `/beheer` → `?instellingen=gebruikers` (Modelprofielen is geen beheer meer); `/instellingen/beheer/modelprofielen` →
  `?instellingen=modellen`.
- Alle links in de app lopen via `onderdeelPad`, `conceptPad`, `versiePad` en `achterPad`; die krijgen de nieuwe vorm, en
  één functie `tabVoorSoort` beslist welke tab een soort heeft. Lex, graph-qa, de api en de rondleiding linken niet naar
  `/werkwijze`, dus daar valt niets om te leiden.
- De doorverwijzingen blijven staan, net als die voor `/beheer` en `/instellingen/*`: een bladwijzer of een link in een
  oud gesprek breekt dan niet.

## Sidebar, rondleiding, mobiel

- **Sidebar**: *Werkwijze* gaat weg; drie hoofditems blijven. De naam linksonder blijft de ingang van de instellingen.
- **Rondleiding**: noemt *Werkwijze* niet. De afsluiter zegt dat een beheerder via de naam linksonder *Beheer* vindt
  "voor modelprofielen en gebruikers"; dat wordt "de modellen en de gebruikers". Verder geen wijziging.
- **Mobiel**: zie *De navigatie*; de breedte-test loopt op 375 px het venster na.

## Wie wat ziet

- **Analist**: Persoonlijk, en Aanpassingen zonder Modellen. Alles te lezen; het gekozen model als tekst. *Voeg toe* en
  *Bewerken als concept* alleen met de werkplaats aan en `mag_maken`.
- **Beheerder**: daarnaast Modellen en Beheer, de modelkeuze per agent en stap, en de connector-schakelaars; die drie
  pas met 2FA.
- **Werkplaats uit** (productie): geen segment *Concepten*, geen *Voeg toe*, de concept-route geeft 404.

## Afstemming met *Model per rol*

De sessie *Model per rol configureerbaar in beheer* bouwt de api (`llm_modelrollen`, `GET/PUT /v1/admin/modelrollen`,
audit, 409 bij een gebruikt profiel) en graph-qa (`agent/modelkeuze.py`, `llm_stap` kiest per rol). Haar UI-deel is in
dit plan opgenomen (tab *Agents*, PR 5). Wat dit plan van haar api vraagt (voorgelegd 15 nov 2026, antwoord open):

- **De sleutel is het agentprofiel of de stap, niet alleen de `Rol`.** `Rol.ANTWOORD` draait vijf profielen (definitie,
  duiding, algemeen, annotaties_lezen, begrippen_lezen) en `Rol.CENTRAAL` twee (centraal, centraal_breed). Voorstel:
  `agent:<profielnaam>` en `stap:<rol>` (`stap:supervisor`, `stap:jas_classifier`, …, `stap:subagent`); `llm_stap` zoekt
  eerst het profiel van de aanroep en valt terug op de stap.
- **De catalogus van keuzes komt van de api** (`app/llm_rollen.py`): per sleutel een label, een korte uitleg, een groep
  en of hij een waarschuwing draagt. Een drift-test bewaakt dat elk agentprofiel en elke `Rol` zonder profiel er precies
  één keer in staat.
- **Lezen voor iedereen, schrijven voor de beheerder.** Een lees-endpoint zonder beheerrecht met per sleutel
  profielnaam en modelnaam; geen endpoint, sleutel of secret naar de browser.
- **Bij een profiel: waar het gebruikt wordt** (voor *Gebruikt door* in Modellen en de 409-melding).

De bestanden die dit plan in het instellingenvenster raakt (`lib/instellingen.ts`, `InstellingenInhoud.tsx`,
`components/ui/Tabs.tsx`, `ProfielenPanel.tsx`) bouwt alleen deze stapel; *Model per rol* raakt ze niet.

## PR-volgorde

Eén stapel, gebundeld via de hoofdsessie (`alles-samen-N`), niet los mergen. PR 1–5 zijn frontend en raken Lex niet;
PR 5 wacht op de api van *Model per rol*; PR 6 raakt graph-qa en wacht tot de A6-meting klaar is.

1. **Navigatie** – `INSTELLINGEN_TABS` met `groep`, `alleenBeheerder`, `trefwoorden`; groepkoppen altijd; zoekveld in de
   tabkolom (`Tabs` krijgt een optioneel zoekslot); op een telefoon eerst de lijst. Modelprofielen heet *Modellen* en
   staat onder Aanpassingen; Connectors ook. Nog geen nieuwe inhoud.
2. **`AanpassingLijst`, `AanpassingDetail`, Methodes en Agents (lezen), Werkwijze weg** – de twee componenten, de tabs
   *Methodes* en *Agents* op de catalogus, `tabVoorSoort`; `/werkwijze[/…]` verwijst door; het sidebaritem,
   `WerkwijzeClient`, `Agentvorm.tsx`, `ModelLabel` en de concept-indeling in `lib/catalogus.ts` gaan weg; de
   browsertests op het venster.
3. **Connectors als één lijst en Modellen op de lijst** – Connectors met de schakelaar, `ProfielenPanel` op
   `AanpassingLijst`; `ConnectorsPanel` weg.
4. **Werkplaats in de lijsten** – segment *Concepten*, *Voeg toe ▾*, ⋯ per rij; `ConceptenGroep` weg; de concept-
   componenten naar `components/aanpassingen/`, de pagina naar `/aanpassingen/concepten/<id>` met doorverwijzing en
   kruimelpad.
5. **Model per agent en per stap** – de keuzelijst op Agents (rij en detail), de groep *Stappen zonder agentprofiel*, de
   waarschuwing bij het JAS-oordeel, *Gebruikt door* en de 409-melding in Modellen. Op de api van *Model per rol*.
6. **graph-qa opruimen** – `agentvorm()` en het veld `agentvorm` uit `GET /v1/catalogus`, met hun weergavetests; de
   regels in ADR-014, ADR-016 en `catalogus.md`.

`frontend/CLAUDE.md` en de root-`CLAUDE.md` gaan mee in de PR die het gedrag verandert (vooral 1, 2 en 4).

## Tests

- **Vitest**
  - `lib/instellingen.test.ts`: elke tab heeft een groep; volgorde persoonlijk → aanpassingen → beheer;
    `alleenBeheerder` voor Modellen en Beheer; oude sleutels en paden (`modelprofielen`, `beheer/modelprofielen`) komen
    uit op `modellen`; het filter op trefwoorden.
  - nieuw `lib/aanpassingen.test.ts`: `tabVoorSoort` geeft elke soort in `SOORTEN` een tab (een nieuwe soort in het
    bronmodel maakt de test rood); de doorverwijzing per soort, ook voor een rol (naar zijn methode).
  - `lib/catalogus.test.ts` / `lib/werkplaats.test.ts`: de pad-functies in de nieuwe vorm; de soorten blijven getoetst
    tegen `bronmodel/catalogus.py`.
  - modelkeuze: de keuzes komen uit de api-catalogus; een onbekende sleutel wordt niet getoond; de waarschuwing staat bij
    precies de sleutels die de api zo markeert.
  - `app/knoppen.test.ts`: `AanpassingLijst` gebruikt `SettingGroup`, `OverzichtBalk`, `Groep`/`GroepRij` en
    `MeerMenu`; geen ander bestand in `components/instellingen` tekent een eigen lijstkop of chiprij; nergens een link
    naar `/werkwijze` behalve de doorverwijzingen; `components/werkwijze/` bestaat niet meer; `ProfielenPanel` heeft geen
    blok per rol.
- **Browserregressie** (`npm run test:browser`, gemockt `/api/**`)
  - `test-aanpassingen.mjs` (was `test-werkwijze.mjs`): `/werkwijze` komt uit op Agents; elke deep link per soort komt in
    de juiste tab; een rij opent het tweede niveau, terug werkt; zoeken in de lijst.
  - `test-werkplaats.mjs`: met de vlag uit geen *Concepten* en geen *Voeg toe*; met de vlag aan *Voeg toe ▾ → Nieuwe
    methode* komt uit op `/aanpassingen/concepten/<id>`; de oude conceptpaden verwijzen door met querystring.
  - instellingen: een analist ziet Persoonlijk en Aanpassingen (zonder Modellen); het zoekveld filtert; Escape wist eerst
    het veld; op 375 px eerst de lijst, dan de tab.
  - agents: een beheerder kiest een model en ziet het na herladen terug; een analist ziet het als tekst; zonder 2FA geen
    keuzelijst; een gebruikt profiel verwijderen geeft de melding met de agents.
  - connectors: een analist zonder schakelaar, een beheerder met.
  - `test-aanpassingen-breedte.mjs` (was `test-werkwijze-breedte.mjs`): op 375 px elke tab, elk segment en elk
    onderdeel zonder zijwaarts scrollen, met `WERKWIJZE_FIXTURE` hernoemd naar `CATALOGUS_FIXTURE`.
- **graph-qa** (PR 6): `GET /v1/catalogus` heeft geen veld `agentvorm` meer; de drift-tests in `test_catalogus.py`
  blijven groen.
- Lokaal alleen de geraakte vitest-bestanden en één browserscript tegelijk; de volle suites draait de poort.

## Open keuzes voor de gebruiker

1. **De concepteditor.** Voorstel: blijft een eigen pagina (`/aanpassingen/concepten/<id>`). Alternatief: een breder
   venster voor Aanpassingen (zoals Claude, bijna schermvullend) met de editor erin; dat herziet het besluit van 13 nov
   2026.
2. **Het model zichtbaar voor de analist.** Voorstel: ja, als tekst bij elke agent en stap. Alternatief: alleen de
   beheerder ziet modellen.
3. **Waar `/werkwijze` heen gaat.** Voorstel: Agents (daar staat het meeste van wat de werkwijze toonde). Alternatief:
   Methodes.
