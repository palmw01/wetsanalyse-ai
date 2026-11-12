# Plan – de context van een beurt zichtbaar maken

Status: plan, goedgekeurd door de gebruiker (12 nov 2026) en dezelfde dag herzien na een review tegen de code, de
ADR's en de Claude-documentatie (zie *Herziening*). Hoort bij ADR-015 (contextbeheer). Stap 1 tot en met 5 zijn gebouwd
(12 nov 2026, zie *Stand van de bouw*); de meting en de docs (6) nog niet.

## Doel

De jurist ziet in Lex twee dingen over een beurt, elk met een eigen naam:

- **Context**: hoe het verzoek aan het model is opgebouwd, zoals `/context` dat in Claude Code laat zien. Per categorie
  het aantal tokens en het aandeel, en hoeveel van het modelvenster het verzoek vult.
- **Verbruik van deze beurt**: wat de beurt in totaal kostte, over alle modelaanroepen en alle agents, zoals het
  tokenbudget het telt. Daarbij hoort of de beurt warm of koud begon.

Het zijn verschillende getallen. Een beurt met vijf modelrondes stuurt vijf keer een verzoek van ±30k tokens en kost
dan ±130k (meting `metingen/context-2026-11-12/`). Wie alleen het grootste verzoek ziet, begrijpt zijn budget niet.

Het is een weergave. Ze verandert niets aan wat Lex naar het model stuurt.

## Wat er al is (getoetst tegen de code)

- **Tokens per aanroep.** `Verbruiksmeter.aanroepen` (`agent/models.py`) bewaart per modelaanroep de `usage`:
  invoer, cache lezen, cache schrijven en uitvoer. Er is één meter per beurt (`agent.py`), dus alle workers van een run
  tellen erin mee. De lijst is begrensd op `MAX_AANROEPEN` (60); de sommen lopen door.
- **De opbouw in tekens.** `verzoekopbouw.opbouw` (#1277) telt per aanroep de toolschema's, het stabiele en het
  variabele systeemdeel, de historie en de lopende beurt, met `tools_hash` en `system_hash`.
  - Ze wordt nu **twee keer** berekend: in de adapter (voor de meter) en in `llm_stap` (voor de logregel
    `model_aanroep`).
  - **De rol staat alleen in de logregel.** De meter, en dus het `meting`-event, weet niet welke rol een aanroep deed.
  - De maten verschillen per deel: tools als JSON, het systeem als tekst, de berichten als Python-weergave van de
    blokken (`_msg_lengte`). Voor een verdeling over categorieën is één maat nodig.
  - Sinds ADR-015 staat de context van de beurt als blok in de vraag. Die telt nu mee in `beurt_tekens`; het variabele
    systeemdeel is leeg, behalve met de meetvlag.
- **De frontend toont daar niets van.** `BeurtMeting` (`frontend/lib/types.ts`) kent alleen de fasen van een
  annotatiebeurt. E6 (#1010, #1016, #1026) maakte lopende runs zichtbaar en voegde de logregel `venster` toe
  (`venster_telling`, alleen in de log), maar bracht geen tokens in beeld.
- **Het tokenbudget** (`/v1/verbruik`) boekt de som per beurt en per gebruiker, uit dezelfde meter. Wáár die tokens
  zaten, weet het niet. De zijbalk toont de stand met `components/ui/Meter`.
- **Het bericht** in de api (`gesprek_store._OPTIONEEL`) draagt optionele JSON-velden zoals `dekking`. Graph-qa schrijft
  het assistentbericht zelf (`beurt.py`, via `wetsanalyse_api.voeg_bericht_toe`), ook bij een fout of een stop. Een veld
  erbij vraagt geen migratie.
- **De boom bestaat al.** Een kind-run draagt `ouder_run_id` (runstore, ADR-012) en een kindgesprek draagt `ouder_id`
  (api). Met een regiegesprek is de boom dus nu al te bouwen en te testen.
- **De gesprekroutes kennen geen rol**, alleen de gebruiker (`actieve_userid`).
- **Er is al een paneel naast het gesprek voor wat geen artefact is**: `ContextPaneel` (bron, element, bibliotheek,
  overzicht, stuk), met één schil en hoogstens één paneel tegelijk.
- **Het modelvenster is niet op te vragen.** Lex praat met het model via Azure AI Foundry, en daar is de Models API
  niet beschikbaar. Graph-qa schaalt bovendien naar nul (`minReplicas: 0`): een cache in het proces is vaak leeg.

## Hoe Claude het doet

- **`/context` in Claude Code.** De referentie zegt: *"Visualize current context usage as a colored grid"*
  ([commands](https://code.claude.com/docs/en/commands)), en elders: een *"live breakdown by category with optimization
  suggestions"* ([context window](https://code.claude.com/docs/en/context-window)).
  - De officiële documentatie somt de categorieën niet op en zegt niet hoe ze geteld worden. De indeling hieronder
    volgt wat Claude Code toont (systeemprompt, tools, MCP-tools, agents, memory, skills, berichten, vrije ruimte); het
    is een voorbeeld, geen specificatie.
  - De basis is het laatste antwoord van de API: *"The status line reports the counts from the last API response"*,
    en `/context` voegt een schatting toe voor wat er daarna bij kwam ([statusline](https://code.claude.com/docs/en/statusline)).
  - Het percentage telt alleen invoer: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Uitvoer
    telt niet mee.
- **Subagents.** *"Each subagent runs in its own context window"* ([sub-agents](https://code.claude.com/docs/en/sub-agents));
  alleen de samenvatting komt terug bij de hoofdagent. In de Agent SDK telt `usage` alleen de bovenste lus, en
  `modelUsage` de hele boom ([cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking)). Dat is
  dezelfde tweedeling als hier: context per agent, verbruik over de boom.
- **De usage-velden van de API.** Het promptvolume is exact: `cache_read_input_tokens + cache_creation_input_tokens +
  input_tokens`. `input_tokens` is alleen wat na het laatste cachepunt komt. Het object `cache_creation` splitst het
  geschreven deel naar TTL: `ephemeral_1h_input_tokens` en `ephemeral_5m_input_tokens`
  ([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)).
- **`count_tokens`.** Gratis, met een eigen rate limit, en ook op Foundry beschikbaar. De documentatie noemt het een
  **schatting**; het gebruikt geen cache, en `messages` is verplicht
  ([token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)). Bij tools voegt de API zelf
  een systeemtekst toe (±500 tokens op Sonnet 4.6,
  [tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)). Sinds Claude 4.7 levert dezelfde
  tekst ongeveer 30% meer tokens op: een telling hoort bij een model.
- **Het venster.** Volgens de documentatie heeft Sonnet 4.6 standaard een venster van 1M tokens
  ([context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)). Of dat via Foundry ook
  zo is, stelt PR 2 vast.

## Besluiten

De eerste zeven zijn van de brainstorm; de herziening (drie vragenrondes, 12 nov 2026) scherpte ze aan. Alle besluiten
zijn van de gebruiker.

| Vraag | Besluit |
|---|---|
| Wat | **Twee blokken in één paneel**: *Context* (het verzoek van een agent) en *Verbruik van deze beurt* (alle aanroepen, alle agents). |
| Plek | Een **contextmeter** bij het invoerveld, en **`/context`** dat het paneel naast het gesprek opent. Eén component met twee ingangen. |
| Meter | Toont de omvang en het **percentage van het venster**, en krijgt een **signaal** zodra er iets speelt: historie ingekort, beurten weggevallen, of een koud begin. |
| Raster | Toont de **samenstelling van het verzoek** (100% = het verzoek). Het venster is één regel erboven: `36k · 3,6% van het venster`. Bij een venster van 1M zou een raster tegen het venster vrijwel leeg zijn. |
| Bereik | Standaard de **laatste beurt**, met een kiezer voor eerdere beurten en het **verloop** over het gesprek. |
| Voor wie | **Iedereen ziet alles.** Het detail per aanroep (cache, hashes, model) staat ingeklapt. Er komt geen rolfilter: het zijn tellingen en korte vingerafdrukken, en het is het eigen budget van de jurist. |
| Telwijze | Het totaal komt **exact uit `usage`**. Het voorvoegsel (tools + systeem) is **exact wanneer de API het meldt** (het 1-uursdeel van `cache_creation`). De rest gaat **naar tekens**, gemarkeerd met `≈`. **Geen extra aanroepen in productie.** `count_tokens` dient alleen om in de meting de afwijking te ijken. |
| Categorieën | `beurt` en **`toolresultaten`** zijn gescheiden: wat tools en subagents teruggaven is bij Lex de grote, wisselende post. |
| Reikwijdte | **Alle modelaanroepen** tellen mee in het verbruik. Een **contextraster** krijgt alleen een agent met een toollus (de antwoordlus; straks de centrale agent en elke subagent). Losse, strikte stappen (supervisor, classifier, kaartactie, deelvragen) zijn een rij in het verbruik. |
| Koud begin | Per agent wordt ook het **eerste verzoek** bewaard. Het paneel zegt voor iedereen of de beurt warm of koud begon, en waarom. |
| Boom | Per agent een eigen context. De boom ontstaat **bij het lezen**: de api geeft bij een gesprek de contextopbouw van zijn kindgesprekken. Niets wordt dubbel opgeslagen. |
| Opslag | Een veld **`contextopbouw` bij het bericht** in de api (niet `context`: dat woord is in Lex al vier keer bezet). Alleen tellingen en vingerafdrukken, geen inhoud. |
| Adviezen | Ja, uit **vaste regels**, zonder model. |
| Volgorde | **Nu bouwen, op wat er is**: de bestaande `Rol` en `ouder_run_id`. De profielvelden van ADR-016 zijn optioneel en komen later. Zo is de weergave er vóór de nulmeting van ADR-016 (M0). |

## Wat een "context" is

Lex bouwt elk verzoek opnieuw op en heeft geen doorlopende sessie zoals Claude Code. De regels:

- **Een context hoort bij een agent met een toollus.** Binnen een beurt groeit zijn berichtenreeks per ronde, en de
  lopende beurt krimpt nooit (ADR-015). Het **laatste verzoek** van de lus is dus het volste. Dat is de context die
  het raster toont, zoals Claude Code het laatste antwoord van de API als basis neemt.
- **Het eerste verzoek** van de lus zegt hoe de beurt begon: wat uit de cache kwam en wat geschreven werd.
- **Een losse stap heeft geen context die groeit.** Elke aanroep staat op zichzelf (twintig classifier-batches zijn
  twintig verzoeken, geen gesprek). Hij telt mee in het verbruik, per rol opgeteld.
- **Wie een aanroep deed**, zegt de `Rol` uit `llm_stap` (een gesloten lijst). Of een rol een lus is, staat in het
  register van rollen, niet in de meter. Een nieuwe rol kiest dat bij zijn definitie.

## De categorieën

Eén register, in deze volgorde. Elk deel van een verzoek valt in precies één categorie.

| Categorie (`id`) | Wat erin zit | Herkend aan | In Claude Code |
|---|---|---|---|
| `systeem` | de identiteit van Lex (`SYSTEM_PROMPT`) | het eerste systeemdeel dat de aanroeper opgeeft | System prompt |
| `methode` | de specialist- of rolprompt met de methodetekst; bij een subagent de instructie en skillsecties van zijn profiel | de overige systeemdelen | Skills, custom agents |
| `graaftools` | de schema's uit `anthropic_schemas`; straks ook de workflows als tool en de eigen tools van een agent | de toolnaam in het toolregister | System tools |
| `connectortools` | de tools van aangezette connectors (ADR-013) | de toolnaam in `CONNECTORS` | MCP tools |
| `sjablonen` | de sjabloontools (ADR-008) | de toolnaam in het sjabloonregister | – |
| `beurtcontext` | plan, gesprekscontext, werkgebied of dossier, bronstand, afrondregel | het blok met `BEURTCONTEXT_KOP`, of het variabele systeemdeel (meetvlag) | Memory files |
| `opdracht` | bij een subagent: de opdracht van de centrale agent (ADR-016) | het eerste bericht van het kindgesprek | de prompt van een subagent |
| `historie` | eerdere beurten (ingekort tot vraag en laatste antwoord) | de berichten vóór `beurt_start`, zonder de opdracht | Messages |
| `beurt` | de vraag van deze beurt en wat het model zelf schreef: tekst en toolaanroepen | de berichten vanaf `beurt_start`, zonder de twee hieronder en zonder de beurtcontext | Messages |
| `toolresultaten` | wat tools in deze beurt teruggaven, ook het rapport en de vragen van een subagent | blokken van het type `tool_result` vanaf `beurt_start` | Messages |
| `overig` | wat niet te herkennen is | de rest | – |

Buiten het register, als getal bij het raster:

- **Het venster**: `modelvenster(model)`, en het aandeel dat het verzoek ervan vult.
- **De historiegrens**: `MAX_HISTORY_CHARS`, omgerekend met de verhouding tussen tokens en tekens van dit verzoek. Ze
  staat bij de categorie `historie` (`12k van ≈ 20k`), niet als lijn in het raster: het is een grens op de historie,
  niet op het verzoek. Het is de tegenhanger van de autocompact-buffer: de plek waar Lex begint op te ruimen.

Eisen bij de herkenning:

- **Ze hangt niet af van de plek.** De beurtcontext wordt herkend aan haar kop, niet aan haar positie. De meetvlag
  `beurtcontext_plek` (alleen nog voor metingen) blijft dus werken.
- **De opdracht vervangt de historie niet.** Een subagent begint zonder historie, maar na een vraag naar boven hervat
  hij in zijn kindgesprek met zijn eigen geschiedenis (ADR-016 A4). Dan heeft hij een opdracht én historie.
- **Wat de API zelf toevoegt** (de systeemtekst voor tool use, het contextbudget van het model) is geen tekst van Lex
  en heeft geen tekens. Het zit in het totaal en komt bij de verdeling in het voorvoegsel terecht. De meting in PR 6
  zegt hoe groot het is.
- **Een meting breekt nooit een aanroep.** Lukt het indelen niet, dan is alles `overig` en klopt de som nog.

## Context per agent

De weergave volgt de vorm van ADR-016 en ADR-012, zoals Claude Code elke subagent een eigen venster geeft.

- **Een subagent is een run** in een eigen kindgesprek, met een `ouder_run_id`. Zijn `contextopbouw` staat op zijn
  eigen `meting`-event en op zijn eigen bericht in het kindgesprek. Er komt geen tweede vorm.
- **Binnen een run** staan de aanroepen per `Rol` bij elkaar. Een rol met een lus heeft een context; de andere rollen
  alleen verbruik. De supervisor is een rol in dezelfde run, geen ouder: een ouder is altijd een run.
- **De boom komt uit de api**, bij het lezen. Eén route geeft bij een gesprek de `contextopbouw` van de berichten in
  zijn kindgesprekken (via `ouder_id`). Het paneel van het hoofdgesprek toont daarmee:
  - eerst de eigen agent: zijn raster en zijn verbruik;
  - dan per kindgesprek een rij: de opdracht of actie, het profiel (als het er is), de omvang van zijn context en zijn
    verbruik. Een klik opent dezelfde contextkaart voor dat kind;
  - het verbruik van de boom: de eigen run plus alle kinderen. Dat is wat het budget zag.
- **Wat naar boven komt, kost de ouder tokens.** De centrale agent ziet alleen het rapport en de vragen van een
  subagent, niet zijn toolresultaten. Die terugmelding telt bij de ouder als `toolresultaten`.
- **Het profiel** (`profiel_id`, `profiel_versie`, ADR-016 A2) is een optioneel veld per agent. Het is leeg tot de
  agentvorm er is; de weergave werkt zonder.
- **Nu al**: een regiegesprek (ADR-012) heeft kind-runs. De boom is daarmee te bouwen en te testen vóór ADR-016.

## Telwijze

Per verzoek, deterministisch en zonder extra modelaanroep. Hetzelfde verzoek met dezelfde `usage` geeft altijd
dezelfde verdeling, ook op een andere replica of na een herstart.

1. **Tekens per categorie, in één maat.** `verzoekopbouw` krijgt een indeling (`samenstelling`) naast de bestaande
   velden, en wordt per aanroep **één keer** berekend: de modelstap geeft haar met de rol door aan de adapter.
   - De maat is voor elk deel dezelfde: de lengte van de JSON zoals het deel de deur uitgaat. `_msg_lengte` blijft
     wat hij is, want het historievenster rekent ermee.
   - Tools worden ingedeeld via hun register. Het systeem via de delen die de aanroeper opgeeft. De berichten naar hun
     vorm (kop, bloktype, plaats ten opzichte van `beurt_start`).
   - **Het verzoek zelf blijft byte-gelijk.** Een test bewaakt dat: elke byte meer breekt de cache.
2. **Het totaal, exact.** Totaal = `invoer + cache_lees + cache_schrijf` uit `usage`.
3. **Het voorvoegsel, exact waar de API het zegt.** Het cachepunt op de systeemprompt heeft een TTL van een uur en
   dekt tools en systeem (ADR-015); de punten op de berichten houden 5 minuten. Schrijft een verzoek het voorvoegsel,
   dan is `cache_creation.ephemeral_1h_input_tokens` precies de omvang van tools + systeem. Die omvang geldt voor alle
   verzoeken van die agent in die beurt met dezelfde `tools_hash` en `system_hash`.
   - Is er in de beurt geen schrijfbeurt gezien (een warm begin), dan is er geen anker en gaat ook het voorvoegsel naar
     tekens.
   - Er komt geen cache over beurten of processen heen: dat zou hetzelfde verzoek op twee replica's anders tonen.
4. **De rest naar tekens.** Binnen het voorvoegsel (of zonder anker: binnen het hele verzoek) krijgt elke categorie
   haar aandeel naar tekens. Afgerond wordt met de grootste-rest-methode, dus de som is precies het totaal.
5. **Wat exact is, zegt het contract.** Het totaal en de cachecijfers zijn altijd exact. Een categorie is `≈`. De som
   van `systeem`, `methode` en de drie toolcategorieën is exact als er een anker is; de weergave zegt dat erbij.
6. **Het venster.** `modelvenster(model)` is een klein register in graph-qa (per model-id, met een veilige default):
   op Foundry is het venster niet op te vragen. Een test eist een vermelding voor elk model dat in de config of de
   modelprofielen kan staan.

ADR-015 blijft daarmee wat het zei: er wordt niet geteld met een extra aanroep. `count_tokens` komt alleen in de meting
van PR 6 voor, als ijking: per categorie de schatting naast de telling. Is de afwijking te groot om er iets aan te
hebben (richtlijn: een categorie meer dan een kwart ernaast), dan komt er een voorstel om alsnog te tellen.

## Datacontract

Graph-qa zet `contextopbouw` op het `meting`-event (live) en op het assistentbericht (bewaard). Beide komen uit de
meter aan het eind van de beurt; er wordt achteraf niets bijgewerkt. De vorm, versie 1:

```text
contextopbouw
  versie            1
  run_id, ouder_run_id        de eigen run, en de run die hem startte (ADR-012/016), of leeg
  profiel_id, profiel_versie  het profiel van een subagent (ADR-016), of leeg
  agenten           [ per rol met een lus ]
    rol             Rol.naam (bv. antwoord)
    model, venster
    laatste         het laatste verzoek van de lus: de context
      delen         [{categorie, omvang}]      som = totaal
      totaal        invoer + cache_lees + cache_schrijf
      voorvoegsel   {omvang, exact: bool}      tools + systeem; exact bij een anker
      cache         {lees, schrijf, nieuw}
    begin           het eerste verzoek van de lus
      totaal, cache {lees, schrijf, nieuw}, tools_hash, system_hash
    historiegrens   de grens in dezelfde eenheid (afgeleid), of leeg
    venster_beurten {in_venster, gekrompen, weggevallen}     uit `venster_telling`
  verbruik          [ per rol, ook de losse stappen ]
    rol, model, aanroepen (aantal), invoer, cache_lees, cache_schrijf, uitvoer, duur
  som               {invoer, cache_lees, cache_schrijf, uitvoer}   gelijk aan wat naar `/v1/verbruik` gaat
  aanroepen         [{rol, totaal, cache_lees, cache_schrijf, invoer, uitvoer, ms, tools_hash, system_hash}]
```

- **Geen veld heet `token`.** De logredactie (`GEHEIME_VELDEN`) laat een veld met precies die naam weg. Daarom heten
  ze `omvang`, `totaal` en `venster`.
- **`laatste`, `begin` en de sommen komen uit alle aanroepen**, ook voorbij `MAX_AANROEPEN`. Alleen de lijst
  `aanroepen` is begrensd.
- **`som` is wat het budget zag.** Een test legt vast dat ze gelijk is aan wat dezelfde meter aan `/v1/verbruik`
  meldt. Hoe de api weegt, blijft bij de api.
- **Eén contract voor iedereen.** De api filtert niets op rol.
- **De boom**: `GET /v1/gesprekken/{id}/contextopbouw` geeft per kindgesprek (`ouder_id`) het gesprek, de titel en de
  `contextopbouw` van zijn assistentberichten. Alleen voor de eigen gesprekken, zoals elke gesprekroute. De BFF-route
  gebruikt `metTrace()`.
- **Oudere berichten hebben het veld niet.** De meter toont dan "nog niet gemeten". Er komt geen backfill (er is geen
  te behouden data).
- Een beurt zonder model (de overzichtsroute, vaste handelingen) krijgt geen `contextopbouw`. Het paneel zegt dan "deze
  beurt gebruikte geen model". Een beurt met alleen losse stappen heeft verbruik, maar geen context.

## De weergave

- **Contextmeter** bij het invoerveld: `components/ui/Meter` met `36k · 3,6%`. Hij hoort bij het laatste bericht met
  `contextopbouw` en werkt na `done` bij uit het `meting`-event, zonder te herladen.
  - Hij krijgt een signaal (kleur en een stip, met tekst voor een schermlezer) bij: historie ingekort, beurten
    weggevallen, of een koud begin.
  - Bij het aanwijzen toont hij de drie grootste categorieën en het verbruik van de beurt. Een klik opent `/context`.
- **`/context`**: een commando zonder beurt (`soort: "client"`, net als `/help`). Het opent het paneel naast het
  gesprek: een nieuwe soort in `ContextPaneel`, met dezelfde schil en `PaneelKop`. Het paneel heet *Context van deze
  beurt* en toont:
  - **Context**, per agent met een lus:
    - de regel `36k · 3,6% van het venster`;
    - het raster: een vast aantal vakjes, gekleurd per categorie, 100% = het verzoek;
    - de legenda per categorie, met omvang, aandeel en `≈`; bij `historie` de historiegrens;
    - hoe de beurt begon: warm of koud, in gewone taal.
  - **Verbruik van deze beurt**: de som, uitgesplitst in gelezen uit de cache, geschreven, nieuw en uitvoer; per rol
    een rij; bij een boom de kinderen en het totaal van de boom.
  - **De boom**: per kindgesprek een rij die dezelfde kaart opent (*Context per agent*).
  - een **beurtkiezer** en het **verloop**: per beurt de omvang van de context en het verbruik, als twee lijntjes;
  - de **adviezen**;
  - **Details per aanroep**, ingeklapt: cache lezen, schrijven en nieuw, uitvoer, duur en de vingerafdrukken.
- **Eén register van categorieën.** Id, label, kleur en volgorde staan op één plek. Graph-qa draagt de id's
  (`agent/contextdelen.py`) en `frontend/lib/contextdelen.ts` de weergave, met een drifttest ertussen, zoals bij
  `jas.ts`. De kleuren komen uit de Rijkshuisstijl-tokens van de app.
- Het paneel is een **weergave, geen artefact**. Je besluit er niets en er komt geen knop bij die Lex start. Het
  advies "begin een nieuw gesprek" verwijst naar `/nieuw`.
- Het paneel zegt wat het toont: "het laatste verzoek van deze beurt", en dat Lex de historie bij elke beurt opnieuw
  opbouwt.

## Adviezen (vaste regels)

Pure functies in `frontend/lib/contextweergave.ts`, over de bewaarde `contextopbouw` van deze en de vorige beurt. Elke
regel heeft een test. Iedereen ziet ze. De eerste drie geven ook het signaal op de meter.

| Regel | Voorwaarde | Tekst (kern) |
|---|---|---|
| Historie ingekort | `historie` ≥ 90% van de historiegrens, of `gekrompen > 0` | Oudere beurten worden ingekort tot vraag en antwoord. Met `/nieuw` begin je schoon. |
| Beurten weggevallen | `weggevallen > 0` | N eerdere beurten zitten niet meer in de context. |
| Koud begin door een andere toolset | `begin.cache.lees` ≈ 0 en `begin.tools_hash` anders dan bij de vorige beurt | De bronnen naast de wet wisselden, dus het vaste deel is opnieuw geschreven. Dat kost één keer extra. |
| Koud begin na een pauze | `begin.cache.lees` ≈ 0 en dezelfde vingerafdrukken | Dit vaste deel is een uur door niemand gebruikt, dus het is opnieuw geschreven. |
| Veel connectortools | `connectortools` > `graaftools` | De aangezette bronnen nemen meer ruimte in dan de wettools. Zet ze uit met `/bron` als je ze niet nodig hebt. |
| Venster bijna vol | totaal ≥ 80% van `venster` | Signaal; dat zou bij Lex niet mogen voorkomen (ADR-015). |

De cache is van iedereen met hetzelfde voorvoegsel (ADR-015). De tekst zegt daarom niet "jij was een uur stil".

## Wat generiek is

- **Eén berekening per aanroep.** De modelstap geeft de rol en de opbouw door aan de adapter; de meter en de logregel
  `model_aanroep` lezen hetzelfde. Elke worker en agent die er nu is of later bij komt, krijgt de indeling mee.
- **Eén register van rollen** zegt wie een lus is. De meter kent geen namen.
- **Tools worden ingedeeld via hun register**, niet via een lijst in de meter. Een nieuwe connector of een nieuw
  sjabloon valt vanzelf in de goede categorie.
- **Eén register van categorieën** voor graph-qa en de frontend, met een drifttest.
- **Eén vorm voor elke agent**: een run met een `contextopbouw`. De boom is `ouder_run_id`, voor de regie van nu en
  de subagents van straks.
- **Eén contract voor iedereen**, zonder rolfilter.
- **Eén weergavecomponent** voor de meter en het paneel, in de bestaande schil van `ContextPaneel`.

## PR-volgorde

Een plan per stap toetsen vóór de bouw. De hoofdsessie bundelt de PR's. Niets wacht op ADR-016.

1. **graph-qa: de indeling in tekens.** Het register van categorieën (`agent/contextdelen.py`) en het kenmerk "lus" op
   `Rol`. `verzoekopbouw` deelt tools, systeemdelen en berichten in, in één maat, en wordt per aanroep één keer
   berekend; de rol gaat mee naar de meter. Alleen de logregel en het `meting`-event veranderen.
   Tests: het verzoek blijft byte-gelijk; elk deel valt in precies één categorie en de som is het geheel; de
   beurtcontext wordt bij beide waarden van `beurtcontext_plek` herkend; een opdracht met historie (een hervat
   kindgesprek) wordt goed ingedeeld.
2. **graph-qa: tokens, begin en verbruik.** De verdeling uit `usage` met het anker, `laatste` en `begin` per lus, het
   verbruik per rol, en `modelvenster`. `contextopbouw` komt op het `meting`-event en op het bericht, met `run_id` en
   `ouder_run_id`. Eerst vaststellen wat Foundry teruggeeft: het object `cache_creation` en het venster van het model.
   Tests: de som is het totaal; `som` is gelijk aan de boeking; met en zonder anker; voorbij `MAX_AANROEPEN`; geen
   veld met de naam `token`.
3. **api: `Bericht.contextopbouw` en de leesroute.** Een optioneel veld in `_OPTIONEEL`, en
   `GET /v1/gesprekken/{id}/contextopbouw` voor de kindgesprekken. Een contracttest, plus `scripts/kruistests.sh` voor
   het routecontract.
4. **frontend: register, rekenwerk en meter.** `lib/contextdelen.ts` met drifttest, `lib/contextweergave.ts` (raster,
   verloop, adviesregels, signaal; vitest) en de contextmeter bij het invoerveld.
5. **frontend: `/context` en het paneel.** De client-handeling, de nieuwe soort in `ContextPaneel` met de twee
   blokken, de boom (met de BFF-route), de beurtkiezer, het verloop, de adviezen en de details. Een browsertest met
   een gemockt bericht en een gemockt kindgesprek. `frontend/CLAUDE.md` §*Commando's* bijwerken.
6. **docs en meting.** ADR-015 krijgt een paragraaf *Zichtbaar*, en `docs/observability.md` de velden. Een meting op
   acceptatie, in eigen gesprekken:
   - vijf beurten in één gesprek: per beurt de som tegen `usage` en tegen het geboekte verbruik, en of de meter klopt
     na herladen;
   - de ijking: per categorie de schatting naast een losse `count_tokens`, en hoeveel de API zelf toevoegt;
   - één regiegesprek: de boom en het verbruik van de boom tegen de delta van het budget.

   De meting komt in `metingen/`. Daarna is de weergave het instrument voor de nulmeting van ADR-016 (M0).

PR 1 en 2 kunnen samen, als de diff klein blijft. PR 3 kan parallel aan 1–2. PR 4–5 hebben het contract uit 2–3 nodig.

## Stand van de bouw (12 nov 2026)

Stap 3 (api) en stap 1–2 (graph-qa) zijn gebouwd. Wat daarbij is vastgesteld of gekozen:

- **Foundry meldt `cache_creation`.** De opgenomen modelruns van 29 sep 2026
  (`metingen/hybrid-v1-invordering-vervolg-2026-09-29/modelruns/`, provider `anthropic_via_azure_foundry`) dragen in
  `usage` het object `cache_creation` met `ephemeral_1h_input_tokens` en `ephemeral_5m_input_tokens`. Het anker kan dus
  werken. Die runs schreven geen cache; of het 1-uursdeel bij een koud begin precies tools + systeem is, toont de meting
  van stap 6 (het veld `cache_schrijf_1u` per aanroep in het `meting`-event). Ontbreekt het object, dan gaat alles naar
  tekens.
- **Het venster via Foundry is niet vastgesteld.** Dat kan alleen met een verzoek boven 200k tokens. Het register
  (`agent/modelvenster.py`) draagt de waarde uit de documentatie (1M voor Sonnet 4.6); een onbekend model krijgt 200k.
- **`systeem` en `methode` worden gescheiden op de tekst van `SYSTEM_PROMPT`**, niet op "het eerste systeemdeel": de
  antwoordlus geeft identiteit en specialist als één stabiel deel op, en ze splitsen zou het cachepunt verplaatsen.
- **Het begin van de beurt geeft de aanroeper mee** (`beurt_start`), en anders wijst de kop van de beurtcontext het aan.
  De oude afleiding (de laatste platte user-beurt) zag het herhaalverzoek om een sjabloon als begin.
- **De rol en de opbouw reizen naar de adapter in een contextvariabele** (`verzoekopbouw.aanroepkader`), niet in de
  kwargs: die blijven byte-gelijk, en de poort `LLMPort` verandert niet.
- **`opdracht`** is een vlag van de aanroeper; niemand zet haar nog (ADR-016 A3). De tool van een losse stap (de strict
  tool van de classifier) staat in geen register en is `overig`; een losse stap heeft geen raster.
- **`venster_beurten.gekrompen`** telt de toolresultaten die ingekort of weggelaten zijn (`venster_telling.ingekort`);
  `in_venster` telt de lopende beurt mee.
- **Volgorde**: stap 3 ging voor, want `test_contract_drift` eist dat de api elk veld van het bericht kent.

### Op acceptatie gezien (12 nov 2026, na stap 1–3)

Eén beurt in een eigen gesprek (duiding van art. 9 Iw 1990, vier modelaanroepen):

- `contextopbouw` staat op het `meting`-event en, gelijk, op het bericht.
- **Het anker werkt.** Het koude begin schreef 27.864 tokens; `cache_schrijf_1u` was 25.009, de rest (2.855) het
  5-minutendeel. Dat 1-uursdeel is het voorvoegsel: de twee rondes erna lazen precies 27.864 en 30.148. `laatste.voorvoegsel`
  was `{omvang: 25009, exact: true}`.
- De verhouding tekens per token is in het voorvoegsel 2,9 en in de rest 2,7: dicht genoeg bij elkaar voor een verdeling
  naar tekens. De ijking per categorie volgt in stap 6.
- Context en verbruik liggen uiteen zoals verwacht: het laatste verzoek was 30.890, de beurt kostte 93.012.

### Stap 4 en 5 (frontend)

- **De boom opent de kaart van een kind ter plekke** (de rij klapt uit), in plaats van naar het deelgesprek te gaan: je
  blijft in het paneel van het hoofdgesprek.
- **Een kind zonder meting** is aan geen beurt toe te wijzen; het staat bij de laatste beurt.
- **De beurten staan buiten de thread-items**, als eigen stand in de werkplek.
- **Het verloop** is twee lijntjes met elk een eigen schaal; de toelichting zegt dat.
- **De kleuren**: blauw in stappen voor het vaste deel, warme en neutrale kleuren voor de rest. De app heeft te weinig
  losse tokens voor elf kleuren, dus twee delen gebruiken een token met dekking.

## Risico's

- **De verdeling is een schatting.** Toolschema's (JSON) en Nederlandse tekst leveren niet evenveel tokens per teken
  op. Daar staat tegenover: het totaal en de cachecijfers zijn exact, het voorvoegsel is exact bij een anker, elke
  geschatte categorie draagt `≈`, en de ijking in PR 6 zegt hoe groot de afwijking is.
- **Foundry geeft het anker niet terug.** Dan ontbreekt `cache_creation` en gaat alles naar tekens. PR 2 stelt dat
  eerst vast; de weergave werkt in beide gevallen.
- **Het verzoek mag niet veranderen.** Elke wijziging aan systeemblokken of tools breekt de cache. De indeling leest
  alleen, en een test eist byte-gelijkheid.
- **Twee getallen door elkaar.** Context en verbruik hebben elk een eigen blok, een eigen naam en een eigen eenheid in
  de tekst ("het laatste verzoek", "de hele beurt").
- **Een kind zonder bericht.** Een kind-run die nog loopt of zonder bericht eindigde, heeft geen `contextopbouw`. De
  rij zegt dan "loopt nog" of "niet gemeten"; het totaal van de boom zegt dat het onvolledig is.
- **ADR-016 verandert de agentvorm.** Dan verandert wie de rol en het profiel zet, niet het contract: een agent blijft
  een run met een `contextopbouw`.
- **Een nieuw model zonder venster.** Dan geldt de default en faalt de test op het register. Zo wordt het geen stille
  fout.
- **Omvang van het bericht.** `aanroepen` is begrensd op `MAX_AANROEPEN` (60). Dat is een paar kB in het ergste
  geval, en alleen tellingen.

## Buiten dit plan

- Iets aan de context veranderen vanuit de weergave, zoals `/compact` of delen uitzetten. ADR-015 zegt al dat
  `/compact` geen tokens oplevert.
- Tellen met een extra aanroep, vóór of na een verzoek.
- Een rolfilter op het detail.
- Productie. Het rolt mee met de gewone release; er komt geen vlag.
- De begrippen- en bronnenruns die buiten een gespreksbeurt draaien (`bronnen_run`, `begrippen_run`). Ze hebben een
  eigen meter en geen bericht; hun verbruik staat in het journaal van de api.

## Herziening (12 nov 2026)

Wat de review veranderde, en waarom.

| Wijziging | Waarom |
|---|---|
| Twee blokken: context en verbruik | Het grootste verzoek (±30k) is niet wat de beurt kost (±130k); de Agent SDK maakt hetzelfde onderscheid. |
| Het raster toont de samenstelling; het venster is een regel | Bij een venster van 1M is een raster tegen het venster leeg. |
| De meter krijgt een signaal | Het percentage blijft bij Lex laag en zegt alleen iets als er iets speelt. |
| `toolresultaten` apart van `beurt`; `overig` in het register | Daar zit het wisselende volume; de tabel miste `overig`. |
| `opdracht` naast `historie`, niet in plaats ervan | Een hervat kindgesprek (ADR-016 A4) heeft beide. |
| Geen `count_tokens` in productie; het anker uit `cache_creation` | Graph-qa schaalt naar nul, `count_tokens` vraagt een bericht en telt toegevoegde tokens mee, het bewaarde bericht kon op `≈` bevriezen, en ADR-015 wees tellen af. |
| `begin` naast `laatste`; cache-adviezen voor iedereen | Het grootste verzoek is de laatste ronde en leest altijd uit de cache; het koude begin (40–70% van de kosten) was niet te zien. |
| Raster alleen voor een lus; losse stappen in het verbruik | Een classifier-batch is geen context die groeit. |
| De rol komt uit `llm_stap`; één berekening; één maat | De meter kende de rol niet, de opbouw werd twee keer berekend, en de maten verschilden per deel. |
| De supervisor is een rol, geen ouder | Een ouder is een run (`ouder_run_id`); `context_id` vervalt. |
| De boom via een leesroute in de api | Het plan zei niet hoe het hoofdgesprek de kinderen ophaalt; een kind kan later klaar zijn of hervatten. |
| Geen rolfilter | De gesprekroutes kennen geen rol; het zijn tellingen. |
| Het veld heet `contextopbouw` | `context` had al vier betekenissen. |
| Het paneel is een soort in `ContextPaneel` | Eén schil voor wat naast het gesprek opent. |
| Niets wacht op ADR-016 of op de A/B | De A/B is klaar; `ouder_run_id` bestaat sinds ADR-012. |
| Bronnen: alleen de officiële documentatie | De lijst categorieën kwam uit een blog; de documentatie somt ze niet op. |
