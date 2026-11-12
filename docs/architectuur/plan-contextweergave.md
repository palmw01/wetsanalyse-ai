# Plan – de context van een beurt zichtbaar maken

Status: plan, goedgekeurd door de gebruiker (12 nov 2026). Hoort bij ADR-015 (contextbeheer). Nog niets gebouwd.

## Doel

De jurist ziet in Lex hoe de context van een beurt is opgebouwd, zoals `/context` dat in Claude Code laat zien: per
categorie het aantal tokens, het percentage van het venster en de vrije ruimte. Een beheerder ziet daarnaast waar de
kosten zitten: wat uit de cache kwam, wat werd geschreven, en per modelaanroep de vingerafdrukken.

Het is een weergave. Ze verandert niets aan wat Lex naar het model stuurt.

## Wat er al is

- **Tokens per aanroep.** `Verbruiksmeter.aanroepen` (`agent/models.py`) bewaart per modelaanroep de `usage`:
  invoer, cache lezen, cache schrijven en uitvoer.
- **De opbouw in tekens.** `verzoekopbouw.opbouw` (#1277) telt per aanroep de toolschema's, het stabiele en het
  variabele systeemdeel, de historie en de lopende beurt. Er staan ook `tools_hash` en `system_hash` bij. Het gaat de
  logregel `model_aanroep` in en, aan het eind van de beurt, het `meting`-event (`beurtmeting.py`).
- **De frontend toont daar niets van.** `BeurtMeting` (`frontend/lib/types.ts`) kent alleen de fasen van een
  annotatiebeurt. E6 (#1010, #1016, #1026) maakte lopende runs zichtbaar en voegde de logregel `venster` toe, maar
  bracht geen tokens in beeld.
- **Het tokenbudget** (`/v1/verbruik`) boekt de som per beurt en per gebruiker. Wáár die tokens zaten, weet het niet.
- **Het bericht** in de api (`gesprek_store._OPTIONEEL`) draagt al optionele JSON-velden zoals `dekking`. Graph-qa
  schrijft het assistentbericht zelf (`wetsanalyse_api.py`). Een veld erbij vraagt dus geen migratie.

## Hoe Claude het doet

- **`/context` in Claude Code.** De referentie zegt: *"Visualize current context usage as a colored grid"* ([commands](https://code.claude.com/docs/en/commands.md)).
  - Onder het raster staan de categorieën, elk met tokens en percentage: systeemprompt, systeemtools, MCP-tools,
    custom agents, memory files, skills, berichten, vrije ruimte en de autocompact-buffer. Daarna volgen de losse
    items en adviezen voor tools die veel ruimte innemen en voor een vol venster ([uitleg](https://blog.vincentqiao.com/en/posts/claude-code-context/)).
  - Het is de stand van nú: wat het volgende verzoek ongeveer meekrijgt.
- **De usage-velden van de API.** Het promptvolume is exact: `cache_read_input_tokens + cache_creation_input_tokens +
  input_tokens`. `input_tokens` is alleen wat na het laatste cachepunt komt ([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)).
- **`count_tokens`.** Het eindpunt is gratis en heeft een eigen rate limit. Het gebruikt geen cache en is ook op
  Foundry stabiel. De documentatie noemt het een **schatting**: het kan iets verschillen van het werkelijke verbruik
  ([token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)). Sinds Claude 4.7 telt de
  tokenizer ongeveer 30% hoger, dus een telling hoort bij een model.

## Besluiten (brainstorm, 12 nov 2026)

| Vraag | Besluit |
|---|---|
| Plek | Een **contextmeter** bij het invoerveld, en **`/context`** dat het raster in het paneel naast het gesprek opent. Eén component met twee ingangen. |
| Bereik | Standaard de **laatste beurt**, met een kiezer voor eerdere beurten en het **verloop** over het gesprek. |
| Voor wie | **Iedereen** ziet categorieën, tokens, % en de vrije ruimte. De **beheerder** ziet ook het detail per aanroep: cache, hashes en model. |
| Telwijze | Het totaal komt **exact uit `usage`**. De vaste delen telt `count_tokens` **één keer per vingerafdruk**. De rest wordt **naar tekens** verdeeld. |
| Reikwijdte | **Alle modelaanroepen**, generiek gelabeld: de antwoordlus, de supervisor, de annotatie-worker en de agents. **Per agent een eigen context**: de centrale agent en elke subagent krijgen elk een eigen raster (aanvulling na de afstemming over het totaalplan voor de agentarchitectuur, zie *Context per agent*). |
| Opslag | Een veld **`context` bij het bericht** in de api. Het bevat alleen tellingen en vingerafdrukken, geen inhoud. |
| Adviezen | Ja, uit **vaste regels**, zonder model. |

## De categorieën

Lex bouwt elk verzoek opnieuw op en heeft dus geen doorlopende sessie zoals Claude Code. De context van een agent in
een beurt is daarom **het grootste verzoek van die agent**: wat het model bij zijn zwaarste stap meekreeg. Bij de
antwoordlus is dat meestal de laatste ronde. Welke agent een aanroep deed, staat in *Context per agent*.

## Context per agent

Het totaalplan voor de agentarchitectuur heeft een centrale agent die generieke subagents opstelt. Elke subagent kiest
per opdracht zijn eigen skill, tools, MCP's en connectors, en werkt in een eigen context. De weergave volgt die vorm,
zoals Claude Code subagents apart toont.

- **Een subagent is een run** (ADR-016, in lijn met ADR-012). Een subagent is een gewone run in een eigen
  kindgesprek, met een `ouder_run_id`. Zijn `context` staat op zijn eigen `meting`-event en op zijn eigen
  bericht in het kindgesprek. De boom ontstaat uit `ouder_run_id`. Er komt geen tweede vorm.
- **Binnen een run** delen de aanroepen van dezelfde agent één berichtenreeks. De meter groepeert ze op
  `context_id`: de `run_id`, met de worker of rol erachter zolang een run nog meerdere workers draait. Het profiel van de
  subagent komt als `profiel_id` en `profiel_versie` mee op `model_aanroep` en op het `meting`-event.
- **De opdracht vervangt de historie.** Een subagent heeft geen eerdere beurten. Wat de centrale agent hem meegeeft,
  is de categorie `opdracht` (in plaats van `historie`).
- **Wat een agent meekrijgt, staat in zijn eigen indeling.** De categorieën zijn dezelfde, maar `methode` heet per
  agent naar de gekozen skill. `graaftools`, `connectortools` en `sjablonen` zijn de tools die die agent koos. Een
  subagent toont dus zijn eigen tools, niet die van de centrale agent.
- **De boom.** Het paneel toont eerst de centrale agent: zijn raster, plus wat de subagents samen kostten. Daaronder
  staat elke subagent als eigen rij: opdracht, profiel, totaal en percentage van zijn venster. Een klik opent dezelfde
  contextkaart voor die subagent. De centrale agent ziet alleen het eindrapport en de vragen van een subagent, niet zijn
  toolresultaten. Die terugmelding telt bij de centrale agent als `beurt` (toolresultaat). Zo is te zien wat ze
  kost.
- **Zonder centrale agent** (de huidige supervisor met vaste workers) is elke worker een agent met de supervisor als
  ouder. Er is één vorm, nu en straks.

De agentidentiteit hoort bij het totaalplan (ADR-016, PR #1330). Dit plan neemt over wat daar wordt vastgelegd en
voegt alleen de meting eraan toe.

| Categorie (`id`) | Wat erin zit | Herkend aan | Claude Code |
|---|---|---|---|
| `systeem` | identiteit van Lex (`SYSTEM_PROMPT`) | de prefix van het stabiele systeemdeel | System prompt |
| `methode` | specialist- of rolprompt met de methodetekst (`methoderol`) | de rest van het stabiele systeemdeel | Skills / custom agents |
| `graaftools` | de schema's uit `anthropic_schemas` | de toolnaam in het toolregister | System tools |
| `connectortools` | de tools van aangezette connectors (ADR-013) | de toolnaam in `CONNECTORS` | MCP tools |
| `sjablonen` | de sjabloontools (ADR-008) | de toolnaam in het sjabloonregister | – |
| `beurtcontext` | plan, gesprekscontext, werkgebied/dossier, bronstand, afrondregel | het blok met `BEURTCONTEXT_KOP`, of het variabele systeemdeel | Memory files |
| `historie` | eerdere beurten (gekrompen tot vraag en laatste antwoord) | de berichten vóór `beurt_start` | Messages |
| `opdracht` | bij een subagent: de opdracht van de centrale agent, in plaats van de historie (ADR-016) | het eerste bericht van een run met `ouder_run_id` | prompt van een subagent |
| `beurt` | vraag, toolaanroepen en toolresultaten van de lopende beurt | de berichten vanaf `beurt_start`, zonder de beurtcontext | Messages |
| `vrij` | het modelvenster min het verzoek | `modelvenster(model)` | Free space |

Er komt een markering bij die Claude Code niet heeft:

- **Historiegrens** (`MAX_HISTORY_CHARS`, omgerekend met de verhouding tekens/tokens van de historie in die beurt).
  Daarboven worden oude beurten ingekort. Het is de tegenhanger van de autocompact-buffer: de plek waar Lex begint op
  te ruimen.

Twee eisen bij de herkenning:

- **Ze hangt niet af van de plek.** De beurtcontext wordt herkend aan haar kop, niet aan haar positie. Zo blijft de
  indeling kloppen bij de A/B van `beurtcontext_plek`, en daarna.
- **Wat niet te herkennen is, heet `overig`.** De som blijft dan kloppen en een aanroep breekt nooit, net als nu in
  `verzoekopbouw`.

## Telwijze

Per verzoek, deterministisch en zonder extra modelaanroep:

1. **Tekens per categorie.** `verzoekopbouw` krijgt een indeling (`samenstelling`) naast de bestaande velden. Tools
   worden ingedeeld via hun register. Het systeem wordt ingedeeld via de delen die de aanroeper opgeeft: een
   bijargument dat niet wordt verstuurd en dat moet optellen tot de verstuurde tekst. Telt het niet op, dan valt het
   terug op `systeem`. De berichten worden ingedeeld naar hun vorm. **Het verzoek zelf blijft byte-gelijk.** Een test
   bewaakt dat, want elke byte meer breekt de cache en de A/B.
2. **Het totaal, exact.** Totaal = `invoer + cache_lees + cache_schrijf` uit `usage`.
3. **De vaste delen, exact genoeg.** Voor `systeem`, `methode`, `graaftools`, `connectortools` en `sjablonen` telt
   `count_tokens` het deel één keer per (model, vingerafdruk van het deel). Die telling gaat in een procescache. Ze
   draait ná de aanroep en buiten het kritieke pad. Een vingerafdruk is per uur hooguit een handvol keer nieuw.
   - Is de telling er nog niet, mislukt ze, of is er een rate limit, dan krijgt het deel zijn aandeel naar tekens en
     de markering `≈`.
4. **De rest naar tekens.** Rest = totaal min de vaste delen, met een ondergrens van 0. Die rest gaat naar
   `beurtcontext`, `historie` en `beurt` volgens hun tekens. Afgerond wordt met de grootste-rest-methode, dus de som
   is precies het totaal.
5. **Het venster.** `modelvenster(model)` is een klein register in graph-qa (per model-id, met een veilige default).
   Een test eist een vermelding voor elk model dat in de config of de modelprofielen kan staan.

Bij het advies "token counting vooraf" uit ADR-015 blijft het zo: er wordt niet vóór de aanroep geteld en nooit per
beurt. Alleen een nieuwe vingerafdruk van een vast deel wordt eenmalig geteld.

## Datacontract

Graph-qa zet `context` op het `meting`-event (live) en op het assistentbericht (bewaard). De vorm, versie 1:

```text
context
  versie            1
  historiegrens     de grens in tokens (afgeleid), of leeg
  agenten           [ per contextidentiteit, de centrale agent eerst ]
    context_id      run_id, met de worker erachter zolang een run meerdere workers draait
    ouder_run_id    de run die deze subagent startte (ADR-016), of leeg
    rol             Rol.naam (bv. ANTWOORD), of de opdracht van de subagent
    profiel_id, profiel_versie   het profiel van de subagent (ADR-016), of leeg
    model, venster  per agent: een subagent kan een ander model hebben
    hoofd           het grootste verzoek van deze agent
      delen         [{categorie, omvang, exact: bool}]   som = totaal
      totaal        invoer + cache_lees + cache_schrijf
      cache         {lees, schrijf, nieuw}
      uitvoer
    aanroepen       [{totaal, cache_lees, cache_schrijf, invoer, uitvoer, ms, tools_hash, system_hash}]
  venster_beurten   {in_venster, gekrompen, weggevallen}   uit `venster_telling` (de centrale agent)
```

- **Geen veldnaam bevat "token".** De logredactie (`GEHEIME_VELDEN`) zou het veld anders wegfilteren. Daarom heten
  ze `omvang`, `totaal` en `venster`.
- **De api toont `aanroepen` alleen aan een beheerder.** Dat gebeurt op één plek, bij het serialiseren van het
  bericht. Een analist krijgt `hoofd` en `venster_beurten`.
- **Oudere berichten hebben het veld niet.** De meter toont dan "nog niet gemeten". Er komt geen backfill (zie
  *Geen te behouden data*).
- Een beurt zonder model (de overzichtsroute, vaste handelingen) krijgt geen `context`. Het paneel zegt dan "deze
  beurt gebruikte geen model".

## De weergave

- **Contextmeter** bij het invoerveld: een smalle balk met `18% · 36k`. Hij hoort bij het laatste bericht met
  `context`. Na `done` werkt hij bij uit het `meting`-event, zonder te herladen. Bij het aanwijzen toont hij de drie
  grootste categorieën. Een klik opent `/context`.
- **`/context`**: een commando zonder beurt (`soort: "client"`, net als `/help`). Het opent het paneel naast het
  gesprek met:
  - het raster: een vast aantal vakjes, gekleurd per categorie, met `vrij` gedimd en de historiegrens als lijn;
  - de legenda per categorie, met tokens, percentage en `≈` waar een deel geschat is;
  - een beurtkiezer en het verloop: het totaal per beurt als lijntje, met het cachedeel erin;
  - de adviezen;
  - de boom van agents: eerst de centrale agent, daaronder elke subagent met een eigen raster (*Context per agent*);
  - voor beheerders, per agent, de tabel met aanroepen: cache lezen/schrijven/nieuw, uitvoer, duur en de
    vingerafdrukken.
- **Eén register van categorieën.** Id, label, kleur en volgorde staan op één plek. Graph-qa draagt de id's en
  `frontend/lib/contextdelen.ts` de weergave, met een drifttest ertussen, zoals bij `jas.ts`. De kleuren komen uit de
  Rijkshuisstijl-tokens van de app.
- Het paneel is een **weergave, geen artefact**. Je besluit er niets en er komt geen knop bij die Lex start. Het
  advies "begin een nieuw gesprek" verwijst naar `/nieuw`.

## Adviezen (vaste regels)

Pure functies in `frontend/lib/contextweergave.ts`, over het bewaarde `context` van deze en de vorige beurt. Elke
regel heeft een test.

| Regel | Voorwaarde | Tekst (kern) |
|---|---|---|
| Historie bij de grens | `historie` ≥ 90% van de historiegrens, of `gekrompen > 0` | Oudere beurten worden ingekort tot vraag en antwoord. Met `/nieuw` begin je schoon. |
| Beurten weggevallen | `weggevallen > 0` | N eerdere beurten zitten niet meer in de context. |
| Koude cache door een andere toolset | `cache.lees` ≈ 0 en `tools_hash` anders dan bij de vorige beurt | De bronnen naast de wet wisselden, dus het voorvoegsel is opnieuw geschreven. |
| Koude cache na een pauze | `cache.lees` ≈ 0 en dezelfde hashes | Langer dan een uur stil, dus de cache was verlopen. |
| Veel connectortools | `connectortools` > `graaftools` | De aangezette bronnen nemen meer ruimte in dan de wettools. Zet ze uit met `/bron` als je ze niet nodig hebt. |
| Venster bijna vol | totaal ≥ 80% van `venster` | Signaal; dat zou bij Lex niet mogen voorkomen (ADR-015). |

Alleen beheerders zien de regels over de cache: het gaat over kosten, niet over het antwoord.

## Wat generiek is

- **Elke modelaanroep loopt al door de adapter** (`anthropic_llm.py` → `Verbruiksmeter`). De indeling komt dus mee
  voor elke worker en agent die er nu is of later bij komt. Alleen een aanroeper die systeemdelen opgeeft, krijgt
  `systeem` en `methode` apart; de rest werkt zonder aanpassing.
- **Tools worden ingedeeld via hun register**, niet via een lijst in de meter. Een nieuwe connector of een nieuw
  sjabloon valt vanzelf in de goede categorie.
- **Eén register van categorieën** voor graph-qa en de frontend, met een drifttest.
- **Eén weergavecomponent** voor de meter en het paneel.
- **Eén plek voor het rolfilter** in de api.

## PR-volgorde

Een plan per stap toetsen vóór de bouw. De hoofdsessie bundelt de PR's.

1. **graph-qa: de indeling in tekens.** Het register van categorieën (`agent/contextdelen.py`). `verzoekopbouw` deelt
   tools, systeemdelen en berichten in, en de antwoordlus geeft haar systeemdelen op. Per aanroep komen `rol`,
   `context_id` en `ouder_run_id` mee, met de identiteit uit het totaalplan van de agentarchitectuur (ADR-016). Tot dat plan er
   is, geldt: een worker is een agent en de supervisor is zijn ouder.
   Tests: het verzoek blijft byte-gelijk, de som van de delen is gelijk aan de bestaande tellingen, en de
   beurtcontext wordt bij beide waarden van `beurtcontext_plek` herkend. Alleen logregel en `meting`-event.
   Wacht op de merge van de A/B van `beurtcontext_plek`, want beide raken de berichtopbouw.
2. **graph-qa: tokens en venster.** De verdeling uit `usage`, de telcache met `count_tokens` (met terugval) en
   `modelvenster`. `context` komt op het `meting`-event en op het bericht. Tests: de som is gelijk aan het totaal, de
   terugval bij een fout of rate limit, en geen veldnaam met "token".
3. **api: `Bericht.context`.** Een optioneel veld in `_OPTIONEEL`, met het rolfilter op `aanroepen`. Een
   contracttest, plus `scripts/kruistests.sh` voor het routecontract.
4. **frontend: register, rekenwerk en meter.** `lib/contextdelen.ts` met drifttest, `lib/contextweergave.ts` (raster,
   verloop, adviesregels; vitest) en de contextmeter bij het invoerveld.
5. **frontend: `/context` en het paneel.** De client-handeling, het paneel met raster, legenda, beurtkiezer, verloop,
   adviezen en het beheerdetail. Een browsertest met een gemockt bericht. `frontend/CLAUDE.md` §*Commando's* bijwerken.
6. **docs en meting.** ADR-015 krijgt een paragraaf *Zichtbaar*, en `docs/observability.md` de velden. Een meting op
   acceptatie, in een eigen gesprek: vijf beurten. Per beurt de som tegen `usage`, de exacte delen tegen een losse
   `count_tokens`, en of de meter klopt na herladen. De meting komt in `metingen/`.

PR 1 en 2 kunnen samen, als de diff klein blijft. PR 3 kan parallel aan 1–2. PR 4–5 hebben het contract uit 2–3 nodig.

## Risico's

- **`count_tokens` is een schatting.** Ze telt soms tokens mee die het systeem toevoegt, bijvoorbeeld voor tool use.
  De vaste delen kunnen dus iets afwijken van wat `usage` laat zien. Daar staan drie dingen tegenover: de rest heeft
  een ondergrens van 0, de som is altijd exact, en de meting in PR 6 laat de afwijking zien.
- **Het verzoek mag niet veranderen.** Elke wijziging aan systeemblokken of tools breekt de cache en vertroebelt de
  A/B. De indeling is daarom een bijargument en een test eist byte-gelijkheid.
- **Botsing met de A/B.** Ook `beurtcontext_plek` raakt `berichten.py` en de antwoordlus. PR 1 komt na die merge,
  en de herkenning gaat via de kop.
- **Afhankelijk van het totaalplan.** De agentidentiteit (`ouder_run_id`, `profiel_id`, `profiel_versie`) komt uit het totaalplan
  voor de agentarchitectuur. Verandert dat ontwerp, dan verandert alleen wie de identiteit zet, niet de meting of de
  weergave. De volgorde: eerst het totaalplan, dan PR 1 hier.
- **Rate limit of Foundry.** Is het telendpoint niet bereikbaar, dan zijn alle delen `≈`. De beurt merkt daar niets
  van.
- **Een misleidend beeld.** Lex heeft geen doorlopende context. Het paneel zegt daarom wat het toont: "het grootste
  verzoek van deze beurt". Ook zegt het dat de historie bij elke beurt opnieuw wordt opgebouwd.
- **Een nieuw model zonder venster.** Dan geldt de default en faalt de test op het register. Zo wordt het geen stille
  fout.
- **Omvang van het bericht.** `aanroepen` is begrensd op `MAX_AANROEPEN` (60). Dat is een paar kB in het ergste
  geval, en alleen tellingen.

## Buiten dit plan

- Iets aan de context veranderen vanuit de weergave, zoals `/compact` of delen uitzetten. ADR-015 zegt al dat
  `/compact` geen tokens oplevert.
- Tellen vóór een aanroep.
- Productie. Het rolt mee met de gewone release; er komt geen vlag.
- De begrippen- en bronnenruns die buiten een gespreksbeurt draaien (`bronnen_run`, `begrippen_run`). Ze kunnen
  dezelfde indeling later krijgen, maar hebben geen bericht om haar aan te hangen.
