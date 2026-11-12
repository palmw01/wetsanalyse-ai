# ADR-016 — De centrale agent en de werkplaats: één agentvorm, profielen en eigen onderdelen

Status: **concept, wacht op akkoord**. Datum: 2026-11-12. Totaalplan. Deze versie is na een kritische review herzien;
wat de review veranderde, staat in [*Wat de review veranderde*](#wat-de-review-veranderde).

Bouwt voort op [ADR-010](adr-010-agentarchitectuur.md) (vier lagen, contract, meetregel),
[ADR-012](adr-012-multi-agent-regie.md) (regie met kindgesprekken), [ADR-013](adr-013-connectors-en-externe-bronnen.md)
(connectors), [ADR-014](adr-014-catalogus.md) (de catalogus) en [ADR-015](adr-015-contextbeheer.md) (contextbeheer). De
bouw van MCP-servers wacht op [ADR-007](adr-007-llm-pad-en-verwerker.md). Wat dit ADR in die eerdere besluiten herziet,
staat in [*Gevolgen*](#gevolgen).

## Context

De gebruiker wil twee dingen, en ze horen bij elkaar.

**1. Zelf onderdelen maken.** Letterlijk: "Ik wil skills, agents, MCP's, agent tools, dus op de juiste wijze moeten die
natuurlijk blijven werken. En dan moet die samenhang in zitten. Maar het zou mooi vinden als ik ook zelf daarin skills
kan aanmaken, toevoegen. Zoals een skill JRM2."

**2. Eén centrale agent die subagents opstelt.** Letterlijk: "Als ik zeg maar binnen Lex iets opstart, dan is dat zeg
maar een centrale agent zou dat moeten zijn. En die kan eventueel andere agents aan het werk zetten op verschillende
opdrachten in subsessies. […] Die agents die zijn in de basis allemaal gelijk aan elkaar, maar afhankelijk van de vraag
kiezen ze hun eigen MCP, hun eigen skill, hun eigen tools, hun eigen connectors, om de vraag op te pakken die centraal
doorgegeven wordt. En als we dan klaar zijn, […] of zijn de vragen of wat dan ook, dan kan die gesteld worden of gaat
het centraal naar boven toe."

Het verband: de centrale agent en elke subagent draaien met een **agentprofiel**. Wat de gebruiker in Lex maakt, zijn
skills en profielen. Eén ontwerp dus, geen twee.

**Waaraan de gebruiker ziet dat het gelukt is** (12 nov 2026, alle vier):

- een grote opdracht in één keer geven, en één overzicht met de open vragen terugkrijgen;
- een gewone vraag kost niet meer tokens en tijd dan nu;
- antwoorden op samengestelde vragen zijn inhoudelijk beter en blijven brongetrouw;
- zelf een skill of profiel maken, dat Lex gebruikt zonder dat er code bij hoeft.

### De agents van nu, en waar het "net niet" zit

| Onderdeel | Wat het doet | Vorm |
|---|---|---|
| Routering in code (`agent/routes.py`, `nodes/supervisie._kies`) | 16 routes zonder model: een klik (`ACTIE_TAAK`), een bepaling, een overzicht, een leesvraag, een doorvraag. Zeven werken alleen vóór het model, acht ook erna (op de herschreven vraag), één alleen erna | code |
| Supervisor (`agent/supervisor.py`) | een model zonder tools dat kiest wat de code niet las (`WORKERS:`, `SPECIALIST:`, `TAAK:`). Hij herschrijft ook een vervolgvraag (`VRAAG:`), wijst af wat buiten de wetgeving valt, en herkent een antwoord op een open vraagkaart | één modelstap met een tekstformaat |
| Specialisten voor de open rest (`agent/specialists.py`) | `definitie`, `duiding`, `algemeen`: dezelfde antwoordlus met een eigen system, tools en sjablonen | dataclass-register |
| Specialisten als stap van een route | `annotaties_lezen` en `begrippen_lezen` (de code zocht al, zij formuleren) en `retrieval` (de ophaalstap van de annotatieroute, met JSON als uitvoer) | hetzelfde register |
| Taakagents (`agent/agents/`) | deelvragen, begrippen, annotatie: een `Taak`-lijst met hoogstens één strict modelstap per taak | code (feitelijk workflows) |
| Vaste workflows | bepaling, overzicht, bronselectie, werkgebied-intake, annotatieketen, begrippenketen | code |
| Regisseur (ADR-012, `agent/regie/`) | plan in code, bevestiging, kindgesprekken (kind-run met `ouder_run_id`, ≤ `REGIE_PARALLEL`), budget per kind, bundel | vaste workflow |

Waar het net niet zit:

1. **Er zijn twee half-centrale onderdelen, en geen van beide is de centrale agent.** De supervisor kiest één keer uit
   een vaste lijst en geeft dan uit handen. De regisseur verdeelt werk, maar kent maar twee opdrachten (*bronnen* en
   *annoteren* per deelvraag).
2. **De generieke vorm bestaat al, maar verstopt.** Drie specialisten zijn één antwoordlus met een profiel. Alleen staat
   dat profiel in Python, kiest alleen de supervisor het, en kan niemand er een bij maken.
3. **De supervisor kost een modelronde en weet daarna niets meer.** Hij herschrijft de vraag, kiest, en de specialist
   begint opnieuw. ADR-010 hield de vraag open of één agent dat beter doet (optie C, de vlag `EEN_ANTWOORDAGENT`). Die
   vergelijking is nooit gebouwd.
4. **De taakagents heten agents, maar zijn workflows.** Dat is goed (ADR-010), maar de supervisor behandelt ze als agent
   in plaats van als tool.
5. **Een kind meldt niets naar boven.** Een kind krijgt een actie, geen opdracht. Een vraag halverwege kan niet; open
   punten komen pas in de bundel.
6. **Skills, tools en connectors liggen per rol vast.** Een skill doet pas mee als code hem aan een rol koppelt.
   `wetsuitvoering` staat klaar, maar geen rol leest hem (`"rollen": {}`).
7. **Niemand kan iets maken.** Een nieuwe skill of agent is een PR met de hand (zie ADR-014; alleen één sectie is via
   C7 voor te stellen).

### Hoe Claude het doet

De bronnen zijn op 12 nov 2026 opgehaald. De citaten zijn letterlijk.

| Bron | Wat er staat | Wat Lex ermee doet |
|---|---|---|
| **Claude Code-subagents** ([sub-agents](https://code.claude.com/docs/en/sub-agents)) | een subagent is markdown met `name`, `description`, `tools`, `model`, `skills`, `mcpServers`, `maxTurns`; de body is de systeemprompt. Hij ziet de historie niet. `AskUserQuestion` valt weg. De hoofdagent werkt zelf als "the task needs frequent back-and-forth" of "latency matters", en delegeert als "the work is self-contained and can return a summary" | het profiel (A2), de eigen context (A3), geen vraag aan de jurist vanuit een subagent (A4), en wanneer de centrale agent delegeert (A1) |
| **Agent SDK** ([subagents](https://code.claude.com/docs/en/agent-sdk/subagents)) | "only its final message returns to the parent". Een definitie die per verzoek verschilt, bouwt **code** ("factory function", "created at query time"); het model kiest per aanroep alleen het type en schrijft de opdracht. Grenzen op diepte (3), gelijktijdigheid (20) en uitgaven (`max_budget_usd`). Een subagent is te hervatten met zijn hele geschiedenis. Het eindrapport wordt gescand op tekst die op een instructie lijkt | geen samenstelling door het model (A2), het rapport als enige weg omhoog en als gegeven, niet als instructie (A4), het plafond per opdracht (A5), hervatten (A4) |
| **Dynamic workflows** ([workflows](https://code.claude.com/docs/en/workflows)) | voor veel agents tegelijk houdt een script het plan, niet het model. "No mid-run user input […] For sign-off between stages, run each stage as its own workflow." Vooraf een akkoord met de fasen en een waarschuwing over tokens. Agents met hetzelfde voorvoegsel delen de cache; de rest van een fan-out wacht tot de eerste schrijft | de regisseur blijft code (A5), fasen met de jurist ertussen (A4), de bevestigingskaart (A5), de cache per profiel (A3) |
| **Skills** ([skills](https://code.claude.com/docs/en/skills), [specification](https://agentskills.io/specification)) | drie niveaus: naam en beschrijving altijd, de body "when the skill is activated", de bestanden "only when required". Een subagent met `skills` krijgt ze vooraf: "the full skill content is injected at startup". Een skill geeft instructies, geen tools | skills op beschrijving, vooraf geladen in een profiel dat ze noemt (A2) |
| **Skills-API** ([skills-guide](https://platform.claude.com/docs/en/api/skills-guide)) | "A new version is a complete snapshot, not a delta"; een aanroep kiest `latest` of een vaste versie | versies in de werkplaats (B1) |
| **Agents bouwen** ([building effective agents](https://www.anthropic.com/engineering/building-effective-agents), [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)) | begin eenvoudig; een workflow waar het pad vastligt. "Multi-agent systems use about 15× more tokens than chats". Geschikt voor werk dat naast elkaar kan en niet in één context past; slecht waar alle agents dezelfde context nodig hebben. Een opdracht noemt "an objective, an output format, guidance on the tools and sources to use" en de grenzen. "Our lead agents execute subagents synchronously." Begin met ongeveer 20 vragen | routes in code blijven ervoor (A1), de vorm van de opdracht (A3), wachten tot de subagents klaar zijn (A4), de agentset (A6) |
| **Plugins** ([plugins-reference](https://code.claude.com/docs/en/plugins-reference)) en **claude.ai** ([organisatieskills](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization)) | een bundel met versie en validatie; de beheerder stelt beschikbaar voor de organisatie | de rechten in de werkplaats (B4) |

**Waar Lex bewust afwijkt van Claude:**

| Claude | Lex | Waarom |
|---|---|---|
| het model kiest elke weg | routes in code vóór de centrale agent | een vaste vraag geeft hetzelfde antwoord, zonder tokens (ADR-010) |
| drie lagen subagents | één laag | de kosten en de boom groeien snel; graph-qa is klein |
| twintig tegelijk | `REGIE_PARALLEL` (2, hoogstens 3) | CPU, de limiet van de provider en de Postgres-pool (ADR-012) |
| een subagent schrijft en voert uit binnen zijn permissies | een subagent stelt voor; besluiten zijn van de jurist | de AI produceert, de mens beoordeelt |
| een achtergrond-subagent meldt zich in een latere beurt | de centrale run wacht tot elke subagent klaar is of wacht | een run overleeft geen herstart en er loopt één run per gesprek; een wekmechanisme is een latere stap (A4) |
| de gebruiker stuurt alleen via het hoofdgesprek | doorvragen in een deelgesprek mag | een deelgesprek is ook na afloop een plek om door te vragen (ADR-012) |
| een skill is na opslaan actief | een skill is actief na review, poort en uitrol | één waarheid: wat in het image zit (ADR-014) |
| de Agent SDK als runtime | de eigen antwoordlus in Python | de SDK draait niet op Microsoft Foundry, en de brongetrouwheid hoort in eigen code (ADR-010) |

## Besluit

De besluiten zijn van de gebruiker (12 nov 2026). De eerste vijf vragenrondes gaven de richting. De review legde elf
punten opnieuw voor; die staan onderaan.

## Randvoorwaarde: echte Python-agents

De gebruiker (12 nov 2026, letterlijk): "Wat ik wel belangrijk vind is dat die centrale agent en de sub-agents wel
allemaal in Python een basis kennen. Dus die agents moeten wel echt Python agents zijn."

- **De centrale agent en elke subagent zijn Python-agents in graph-qa, met één gedeelde basis.** Die basis is een klasse
  `Agent` in `agent/agentvorm.py`. `CentraleAgent` en `Subagent` zijn de enige twee subklassen. Ze verschillen alleen
  in hun eigen tools (`subagent` tegenover `rapport`).
- **Er komt geen tweede lus.** `Agent` bouwt en draait de antwoordketen die er al is (de LangGraph-graaf in
  `orchestrator.build_graph`: agent ⇄ tools → verify → correct → finalize), met een profiel waar nu een specialist
  staat. De gedeelde modelstap (`llm_stap`), de contextopbouw, `dispatch` met het filter, de controles, het verbruik en
  de events blijven wat ze zijn. `tests/test_graafopbouw.py` legt de vorm vast.
- **Skills, profielen, MCP's en connectors zijn configuratie die zo'n agent laadt.** Ze vervangen nooit code. Een profiel
  is een getypeerd object (`bronmodel.agentprofiel.Agentprofiel`), gevalideerd voordat het een agent opbouwt.
- **Een gemaakte skill of een gemaakt profiel stelt dus een Python-agent samen.** Er bestaat geen weg waarop een profiel
  buiten de basisklasse draait: zonder `Agent` geen modelaanroep, geen tool en geen kind. Een test bewaakt dat
  (`test_agentvorm.py`: elke modelaanroep in de open laag komt uit een `Agent`).
- Dit sluit aan op ADR-014. Het contract hoort bij de code die het nakomt; het profiel kiest alleen uit wat die code
  aanbiedt.

## Deel A — De centrale agent

### A1. Eén centrale agent, die zelf antwoordt

```
verzoek ─► routering in code ─┬─► vaste workflow                 (geen model: bepaling, overzicht, klik, …)
                              └─► centrale agent (de antwoordlus met het profiel `centraal`)
                                    ├─► graaf- en brontools: hij zoekt, leest en antwoordt zelf
                                    ├─► workflows en ketens als tool
                                    ├─► een skill laden
                                    ├─► subagent(profiel, opdracht) ─► kindgesprek
                                    └─► een vraag aan de jurist: het einde van zijn beurt, als keuzekaart
```

- **De routering in code blijft ervoor.** Wat de code eenduidig leest, gaat zonder model naar zijn workflow (ADR-010
  laag 1 en 2): dezelfde vraag geeft dezelfde tekst en bronnen, zonder tokens. De rest gaat naar de centrale agent.
- **De centrale agent is de ene agent van de open laag** (ADR-010 laag 4, optie C). Hij heeft de graaf- en brontools
  van het profiel `algemeen` van nu, en beantwoordt een gewone vraag zelf. De supervisorstap en de keuze tussen
  specialisten vervallen. Een gewone vraag kost dus niet meer rondes dan nu, en naar verwachting één minder.
- **Wat de supervisor nog meer deed, krijgt een plek:**
  - *een vervolgvraag begrijpen*: de centrale agent heeft het gesprek zelf (het venster van ADR-015). Herschrijven als
    aparte stap vervalt;
  - *de routes na het model* (bepaling, overzicht, lijstvraag, annotaties en begrippen lezen): dat worden tools van de
    centrale agent. Zo'n tool is **terminaal**: de code vult het antwoord, zoals een sjabloontool (ADR-008), en het
    model schrijft er niets overheen. De routes vóór het model blijven op de letterlijke vraag werken;
  - *afwijzen*: de centrale agent zegt het zelf, zonder tool, met de vaste tekst uit zijn instructie;
  - *een antwoord op een open vraagkaart*: een tool (`beantwoord_kaart`), die de stapmachine van de intake of de
    bronselectie aanroept;
  - *de bronkeuze* (`agent/bronkeuze.py`): blijft code, na de route.
- **Hij delegeert alleen wat zich daarvoor leent.** De regel staat in zijn instructie en wordt gemeten (A6):
  - wel: werk dat op zichzelf staat en met een rapport terug kan, veel leest (lange stukken, veel bronnen), of uit
    delen bestaat die naast elkaar kunnen;
  - niet: een vraag die hij in een paar toolrondes zelf beantwoordt, werk dat heen en weer vraagt met de jurist, en
    delen die elkaars uitkomst nodig hebben.
- **Elke subagent heeft dezelfde vorm**: dezelfde antwoordlus, met een ander profiel (A2) en een opdracht (A3).
- **Eén laag.** Een subagent heeft de tool `subagent` niet. Heeft hij meer nodig, dan zegt zijn rapport dat.
- **De taakagents en de ketens zijn tools**, van de centrale agent en van elk profiel dat ze noemt. Een agent doet het
  werk van een keten nooit zelf na.

### A2. Het agentprofiel: kiezen, niet samenstellen

Een profiel is wat een Claude Code-subagent ook is: een beschrijving, een instructie en een lijst onderdelen.

| Veld | Wat | Grens |
|---|---|---|
| `naam`, `beschrijving` | wanneer de centrale agent dit profiel kiest | – |
| `kiesbaar` | of de centrale agent het mag kiezen | `false` voor een profiel dat een stap van een route is |
| `instructie` | de systeemtekst | bovenop de identiteit van Lex; zet geen controle uit |
| `skills` | welke skills hij **vooraf** krijgt | alleen skills uit de catalogus (of een conceptversie in de proef, deel B) |
| `tools` | welke tools | een deelverzameling van de tools van de open laag; nooit `subagent`; nooit een besluit van de jurist |
| `connectors`, `mcp` | welke bronnen en servers | alleen wat in het gesprek aanstaat (ADR-013); `dispatch` blijft weigeren wat uitstaat |
| `sjablonen` | hoe hij afrondt | uit `SJABLONEN` |
| `modelklasse` | `licht` of `zwaar`, verwijst naar de modelprofielen in het beheer | – |
| `max_rondes`, `budget` | hoe lang en hoe duur | begrensd per profiel, en binnen het plafond van de opdracht (A5) |

**Eén register, twee herkomsten:**

- **Vaste profielen**, uit de catalogus. De specialisten van nu worden de eerste:
  - `centraal`: de centrale agent zelf, ook een profiel;
  - `algemeen`: het brede profiel voor een subagent, met alle leestools en de skills op beschrijving;
  - `definitie` en `duiding`: smal, met hun huidige system, tools en sjablonen;
  - `annotaties_lezen`, `begrippen_lezen` en `retrieval`: `kiesbaar: false`. Het zijn stappen van een route in code.
    Ze staan in hetzelfde register, maar de centrale agent kiest ze niet.
- **Werkplaatsprofielen**, door de gebruiker gemaakt (deel B), na promotie een bestand in de repo.

**De centrale agent stelt geen profiel samen.** Hij kiest een kiesbaar profiel en schrijft de opdracht. Dat is hoe
Claude het doet, en het houdt elk profiel meetbaar. De wens "afhankelijk van de vraag kiezen ze hun eigen MCP, skill,
tools en connectors" vervult het brede profiel: een subagent met `algemeen` kiest zelf, per vraag, uit zijn tools, de
connectors die aanstaan en de skills die hij op beschrijving ziet. Mist er een profiel, dan maakt de gebruiker het in
de werkplaats. Past geen profiel, dan kiest de centrale agent `algemeen`.

**Skills laden in drie niveaus**, zoals de Agent Skills-specificatie:

1. **Naam en beschrijving** van elke actieve skill staan in het vaste voorvoegsel van `centraal` en `algemeen`
   (ongeveer honderd tokens per skill). Zo werkt een nieuwe skill zonder code.
2. **De kern van een skill** laadt de agent met de tool `laad_skill(skill)`: de secties die de skill voor de generieke
   rol `agent` bestemt (`agentrollen.json`). Een profiel dat de skill in `skills` noemt, krijgt die secties vooraf in
   zijn systeemtekst.
3. **De references** leest hij met `lees_skill(skill, sectie)` wanneer hij ze nodig heeft.

Wat daarbij vastligt:

- **De rol `agent` is één nieuwe methoderol**, met een eigen `Rol` in `llm_stap` en een scenario in
  `test_modelverzoeken.py`. Dat is code en een meting (ADR-014 §5), één keer. De basis van `wetsanalyse` laadt altijd
  vooraf onder die rol, zodat `llm_stap` zijn methodekop vindt.
- **De vaste rollen van nu krijgen een nieuwe skill niet vanzelf.** De annotatieketen, de deelvragen en de andere
  rollen houden hun methodetekst byte-gelijk (ADR-010, P19). Een skill bereikt zo'n rol alleen als hij hem in
  `agentrollen.json` noemt, en dat vraagt een meting (deel B, poort 3).
- **Skilltekst is methode, geen bron.** Het resultaat van `laad_skill` en `lees_skill` komt niet in de `source_trace`
  en niet in het bronregister, zoals een annotatie. Het spoor toont het onder *Methode* (`spoorbronnen.METHODE`).
- **Een skill geeft geen tools.** Hij zegt hoe; wat mag, zegt het profiel.

### A3. De opdracht en de context van een subagent

- **Een subagent begint schoon.** Hij krijgt niet de historie van het hoofdgesprek, maar:
  - de identiteit van Lex, de instructie van zijn profiel en de skills die het profiel vooraf laadt;
  - de toolschema's van zijn profiel;
  - de **opdracht** van de centrale agent;
  - de werkgebiedcontext, begrensd per laag (ADR-010, `werkgebied_context.py`).
- **De opdracht heeft vaste velden** (een strict schema op de tool `subagent`): het doel, het onderwerp (een deelvraag,
  een bepaling, een stuk; als id uit het gesprek, `id_herkomst`), wat hij oplevert, welke bronnen voor de hand liggen,
  en wat er niet bij hoort. Een vage opdracht geeft dubbel werk.
- **De centrale agent ziet alleen wat naar boven komt**: het rapport en de artefacten. Niet de toolresultaten van de
  subagent. Zo blijft zijn context klein.
- **De contextweergave** (PR #1331, `plan-contextweergave.md`, de secties *Context per agent* en *Datacontract*) heeft
  één bron: het veld `contextopbouw` (herzien 12 nov 2026; eerder `context`). Het staat live op het `meting`-event
  (`beurtmeting.py`) en bewaard op het assistentbericht (`Bericht.contextopbouw`), en wordt per `model_aanroep`
  opgebouwd uit `verzoekopbouw.opbouw`. Voor de subagents betekent dat:
  - een subagent is een run met `ouder_run_id` in een kindgesprek, met een eigen `contextopbouw` op zijn eigen
    `meting`-event en bericht; de boom komt uit `ouder_run_id` en wordt bij het lezen door de api samengesteld uit de
    kindgesprekken; er komt geen tweede vorm;
  - een subagent heeft de categorie `opdracht`; na een vraag naar boven (A4) heeft hij daarnaast zijn eigen historie;
  - `profiel_id` en `profiel_versie` staan op `model_aanroep` en in `contextopbouw`; tot de agentvorm er is, zijn ze
    leeg;
  - in het raster van de centrale agent tellen het rapport en de vragen van een subagent als `toolresultaten`;
  - het verbruik van de boom (de eigen run plus alle kinderen) staat los van de context per agent.

  Geen nieuw veld heet `token`: de logredactie (`GEHEIME_VELDEN`) laat een veld met die naam weg.
- **Cache** (ADR-015): een profiel heeft één voorvoegsel (tools, systeemtekst, vooraf geladen skills), dat een uur
  warm blijft en voor alle juristen gelijk is. Subagents met hetzelfde profiel delen het. Start de centrale agent er
  meer tegelijk, dan wacht de rest tot de eerste zijn eerste antwoord begint: zo lezen ze het voorvoegsel in plaats
  van het elk te schrijven. De opdracht en de werkgebiedcontext staan ná het voorvoegsel.

### A4. Naar boven: één rapport, en vragen gebundeld

**Een subagent heeft één uitgang**, de strict tool `rapport`:

| Veld | Wat |
|---|---|
| `status` | `klaar`, `vraag` (hij kan niet verder zonder antwoord) of `niet_gelukt` |
| `gedaan` | wat hij deed, kort |
| `artefacten`, `bronnen` | refs uit code, nooit uit modeltekst |
| `vragen` | per vraag de tekst en zo mogelijk opties |
| `open` | wat niet lukte of niet aan bod kwam |

De controles (brongetrouwheid, id-herkomst) draaien op het rapport zoals op elk antwoord. Bereikt een subagent
`max_rondes` of zijn budget, dan sluit de code hem af met een rapport `niet_gelukt` en wat er lag. Er is geen aparte
tool om een vraag te stellen: een vraag is een rapport met `status: vraag`. Daarna is de run van de subagent gewoon
klaar; er wacht geen proces.

**De centrale run wacht tot elke subagent klaar is.** Zo volgt de regisseur zijn kinderen nu ook (`await run.taak`, op
dezelfde replica). Een subagent met een vraag houdt de anderen niet op: zij werken door. Daarna:

1. De centrale agent krijgt de rapporten als toolresultaat. De code zet er een kop boven die zegt dat het een rapport
   is, en maakt tekst onschadelijk die op een instructie of een beurtgrens lijkt. Een rapport is een gegeven, geen
   opdracht.
2. Kan hij een vraag beantwoorden uit wat er ligt (het dossier, een ander rapport), dan **hervat** hij die subagent:
   een nieuwe beurt in hetzelfde kindgesprek, met diens eigen geschiedenis. Dat mag één keer per subagent per beurt.
3. Wat overblijft, gaat naar de jurist. De beurt van de centrale agent eindigt met **de bundel**: de drie lijsten van
   ADR-012 (*opgeleverd*, *wacht op jou*, *mislukt of niet aan bod*), uit de stand bij de api, met per open vraag een
   keuzekaart. Hij gokt niet.
4. De jurist beantwoordt een kaart. Dat is een klik met een vaste actie, dus de code routeert hem zonder model. De
   centrale agent hervat de subagent met het antwoord, wacht, en bundelt opnieuw.

**De stand staat bij de api, niet in een proces.** Het object `delegatie` (A5) weet per taak het profiel, de opdracht,
het kindgesprek en de stand (*loopt*, *klaar*, *wacht op antwoord*, *niet gelukt*, *niet gestart*). Een run overleeft
geen herstart en geen inschalen (`minReplicas: 0`); dat blijft zo. Wat klaar was, blijft staan. Bij een vervolg leest
de centrale agent de stand (`delegatie_stand`) en start hij alleen wat niet af is. De bevestigingskaart zegt dat de
werkplek open moet blijven, zoals bij de regie.

**Wat de centrale agent over de rapporten schrijft, wordt getoetst.** De toolresultaten van de subagents gaan als
bronnen mee naar het bronregister van het hoofdgesprek (alleen toolresultaten, nooit modeltekst). `verify` toetst de
samenvatting daartegen, zoals elk antwoord.

**Fasen, met de jurist ertussen.** Een grote opdracht ("werk dit werkgebied uit") wordt een plan in fasen. Een fase
eindigt waar een besluit van de jurist nodig is: annoteren gaat alleen over bronnen die hij opnam. De centrale agent
voert de eerste fase uit en komt terug met de bundel. Het plan blijft bij de delegatie staan. Na de besluiten is de
volgende fase één klik, met een bevestiging op de stand van dat moment (het `plan_id`, zoals bij de regie). Lex neemt
nooit zelf een voorstel op om door te kunnen.

**Een vervolgvraag in het hoofdgesprek** gaat eerst langs de routes in code, dan naar de centrale agent. Die heeft de
bundel in zijn historie en de stand bij de api. Hij antwoordt uit het rapport, hervat een subagent, of start iets
nieuws.

**Doorvragen in een deelgesprek mag.** Een deelgesprek is een gewoon gesprek met het profiel van de subagent, dat op
het gesprek vastligt. Wat daar gebeurt, gaat niet vanzelf omhoog. De delegatie markeert het deelgesprek als *later
gewijzigd*, en de centrale agent leest bij een vervolg wat er nu ligt.

**Meteen in plaats van gebundeld** (een vraag tonen terwijl de rest doorloopt) is een latere stap. Het vraagt een
mechanisme dat de centrale agent wekt als een kind klaar is terwijl er geen run meer loopt. Dat komt er alleen als de
meting laat zien dat wachten hindert.

### A5. Wat in code blijft

| Wat | Waarom | Hoe |
|---|---|---|
| **Routering in code** vóór de centrale agent | dezelfde vraag, hetzelfde antwoord, nul tokens | `agent/routes.py`, de routeringsset (ADR-010) |
| **De deterministische ketens**: annoteren (ADR-001), bronnen vinden en de bronselectie (spoor J), de begrippenketen (ADR-004) | regels en tests, geen prompts; herhaalbaar en meetbaar | tools; een agent doet het werk van een keten nooit zelf na |
| **Verdelen per deelvraag** | het plan volgt uit de stand bij de api; dezelfde stand geeft hetzelfde plan, zonder tokens (ADR-012) | de regisseur blijft code en is een tool van de centrale agent (`regie_plan`). De centrale agent stelt alleen zelf subagents op voor werk zonder vast plan, hoogstens `MAX_SUBAGENTS` per fase |
| **De delegatie** | één plek voor de stand, het plan en de audit | een object bij de api. Het veralgemeent `regies`: het hoofdgesprek, de gebruiker, het werkgebied als dat er is, het plan in fasen, per taak het profiel met versie, de opdracht, het kindgesprek, de stand en het verbruik, en wie bevestigde. Een regie is een delegatie met een plan uit code. Eén lopende delegatie per gesprek en per gebruiker; het slot per werkgebied geldt voor een delegatie die annoteert |
| **De jurist als poort** | de AI stelt voor, de mens beslist | besluiten (opnemen, uitsluiten, beoordelen, accorderen) roept geen agent aan (`agent_toegang.TOEGESTAAN`); **een bevestigingskaart vóór meer dan één subagent, en vóór alles wat annoteert of iets voorstelt in een werkgebied**, met het plan, de profielen, de schatting en het plafond; één subagent die alleen leest of zoekt, start meteen |
| **Brongetrouwheid** | niet onderhandelbaar | grounding, verify en id-herkomst als controles op elke run, ook op elk rapport en op de bundel |
| **Tokens** | het budget is per gebruiker begrensd, en multi-agent kost een veelvoud | **een plafond per opdracht**, op de bevestigingskaart: standaard een vast deel van wat de gebruiker die week nog heeft (`DELEGATIE_AANDEEL`, vastgesteld na de nulmeting), op de kaart te verlagen of te verhogen. Bij het plafond start er niets nieuws; wat loopt, maakt af, en de bundel zegt het. Daaronder: `max_rondes` en `budget` per profiel, ≤ `REGIE_PARALLEL` tegelijk, één laag. Een schatting per profiel komt uit de mediaan van eerdere runs, zoals bij annoteren; tot die er is, zegt de kaart dat eerlijk |
| **Stoppen** | de jurist houdt de rem | *Stop alles* stopt de centrale run en zijn kinderen (`stop_met_kinderen`, een vlag, ook over replica's heen) |
| **De meetregel** | geen agent zonder meting (ADR-010) | A6 |

Wat vrij wordt: of de centrale agent zelf antwoordt of delegeert, welk profiel, de formulering van de opdracht, hoeveel
subagents (binnen de grenzen), het beantwoorden van een vraag uit wat er ligt, en de tekst van de samenvatting (de
feiten komen uit code).

**De werkplek** gebruikt wat er voor de regie al is: de kindgesprekken onder het hoofdgesprek, het kaartje met *Stop
alles*, de bevestiging en de bundel. Nieuw zijn het profiel bij elk deelgesprek, de stand *wacht op antwoord*, de
keuzekaarten in de bundel, en de knop voor de volgende fase. De events `regie` en `regie_taak` blijven het contract,
met het profiel erbij; er komt geen tweede set.

### A6. Meten: een meetlus per fase

De gebruiker (12 nov 2026, letterlijk): "Wat ik wel belangrijk vind is dat je zodra het kan ook echt testen gaat
uitvoeren. Eigenlijk een beetje zoals we de connectors ook hebben gedaan met die 30 vragen. […] je kent wel het principe
van zoveel mogelijk testen en bij te stellen waar nodig."

Het voorbeeld zijn de iteratierondes van de connectors (nov 2026): 30 vragen per connector, op acceptatie via de
acceptatie-MCP, beoordeeld tegen de officiële bron, generiek verbeterd per ronde, hoogstens vier rondes, met de
uitkomsten in `docs/architectuur/metingen/`. Voor de agents wordt dat het volgende.

**De agentset** (`eval/golden_centrale_agent.jsonl`, 30 opdrachten, gespreid):

| Groep | Aantal | Voorbeeld | Wat verwacht is |
|---|---|---|---|
| enkelvoudig, geen delegatie | 10 | "wat staat er in artikel 25 Iw 1990", "hoe verhoudt artikel 9 Iw zich tot de Awb" | de code-route, of de centrale agent zelf; geen subagent |
| één subagent | 5 | "zoek de rechtspraak bij artikel 9 Iw en vat per uitspraak samen wat ze over de termijn zegt" | één subagent, het juiste profiel, een opdracht met alle velden |
| meer subagents of fasen | 6 | "vergelijk de termijnen in de Iw, de Awb en de Leidraad", "zoek per deelvraag de bronnen", "werk dit werkgebied uit" | het aantal subagents (een bereik), de profielen, de regisseur als tool, de bevestigingskaart, stoppen bij de poort |
| een vraag naar boven | 4 | een dubbelzinnige regeling, een deelvraag die ontbreekt | een rapport met `status: vraag`; beantwoord door de centrale agent waar dat kan, anders een keuzekaart in de bundel; nooit gokken |
| vervolg | 5 | een vervolgvraag op een rapport, een antwoord op een keuzekaart, doorvragen in een deelgesprek en dan terug | de centrale agent gebruikt wat er ligt en start alleen opnieuw wat nodig is |

Per opdracht legt de set vast: de route (code of centraal), het bereik aan subagents, de verwachte profielen, de
verplichte en de verboden tools, of er een vraag naar boven hoort en bij wie hij landt, en het sjabloon. De opdrachten
gebruiken andere bepalingen dan de voorbeelden in de skill.

**Meetpunten en drempels.** Een ronde is goed als alle drempels gehaald zijn. Ze volgen de vier dingen waaraan de
gebruiker succes afleest.

| Meetpunt | Hoe gemeten | Drempel |
|---|---|---|
| gewone vragen niet duurder | delta van het verbruik en de duur per beurt (`meting`-event), de tien enkelvoudige opdrachten | mediaan van tokens en duur ≤ de nulmeting; geen opdracht meer dan 25 % duurder zonder verklaring |
| juiste delegatie (wel of niet, en hoeveel) | events `regie_taak` en de kindgesprekken, tegen de set | ≥ 27/30 |
| juiste profielkeuze | `profiel_id` op `model_aanroep`, de opdrachten met een subagent | ≥ 13/15 |
| brongetrouw en gegrond | elk antwoord, rapport en elke bundel tegen de officiële bron, zoals bij de connectors | 30/30 zonder onjuiste bron of verzonnen citaat |
| inhoudelijk juist | beoordeeld door de agent-jurist tegen de bron, per opdracht goed, deels of fout | samengesteld (20 opdrachten): beter dan de nulmeting; enkelvoudig: niet slechter |
| vragen naar boven | de 4 opdrachten met een vraag | 4/4 boven, geen enkele subagent die gokt |
| grote opdracht in één keer | de opdrachten met fasen | het plan klopt, de eerste fase loopt af, de bundel noemt wat wacht, de volgende fase start na één klik |
| kosten van delegatie | tokens per opdracht met subagents | binnen het plafond; gerapporteerd naast dezelfde opdracht als losse beurten |
| regressie | de kwaliteitsset en de routeringsset van nu | geen case van goed naar fout zonder verklaring |

**Nulmeting.** Eerst de agentset tegen de huidige Lex (supervisor, specialisten, regisseur), drie runs. Veel meervoudige
opdrachten zullen nu mislukken: dat is het vertrekpunt.

**Een ronde per fase.** Pas door naar de volgende fase als de ronde goed is.

| Fase | Wat de ronde meet | Drempel |
|---|---|---|
| T1, A1 (validator, profieltype) | de kwaliteitsset en de routeringsset | bitgelijk: geen verschil |
| A2 (de centrale agent, zonder subagents) | de enkelvoudige en de vervolgopdrachten, de kwaliteitsset en `golden_gesprek`, drie runs, hoogstens vier rondes. Dit is de vergelijking die ADR-010 als optie C openliet | niet duurder, niet slechter, brongetrouw 100 % |
| A3 (één subagent) | daarbij de opdrachten met één subagent; de regiemeting van `regie-2026-11-08` opnieuw (de regisseur op de delegatie) | de drempels hierboven; de regie gelijk of beter |
| A4 (vragen omhoog en hervatten) | daarbij de opdrachten met een vraag en met een vervolg | de drempels hierboven |
| A5 (meer tegelijk, fasen) | de hele agentset | de drempels hierboven |
| A6 (eindmeting) | de agentset en de kwaliteitsset, drie runs, tegen de nulmeting | de drempels, over drie runs; dat besluit A7 |
| B3, B4 (proef, promotie) | `wetsuitvoering` als conceptskill: 30 vragen over scenario's en relevante feiten, tegen de JRM-specificatie, plus 10 vragen die er niet over gaan | 30/30 brongetrouw, ≥ 26/30 inhoudelijk juist, de skill geladen bij ≥ 27/30 en bij hoogstens 1 van de 10 andere |
| B5 (profielen in de werkplaats) | een werkplaatsprofiel (bijv. JRM-scenario) in de agentset | dezelfde drempels als A3 voor zijn opdrachten |

Een ronde die drie keer bij dezelfde drempel strandt, gaat met een voorstel terug naar de gebruiker in plaats van door
te itereren. Runs verschillen sterk: een trend claimen we pas over drie runs.

**Werkwijze.**
- Elk meetspoor draait in een eigen subsessie, zoals bij de connectors:
  - *centrale agent en regressie* (A1–A2);
  - *delegatie* (A3–A6);
  - *werkplaats-proef* (B3–B5).

  De hoofdsessie bundelt de ronde-PR's (`claude/alles-samen-N`), volgt de merge en de uitrol, en geeft het sein voor de
  volgende ronde.
- Gemeten wordt op acceptatie via de acceptatie-MCP. Tokens zijn de delta van het verbruik (de cache telt vol mee).
  Beoordeeld wordt tegen de officiële bron (`bron_lezen`), en de agent-jurist beoordeelt de inhoud.
- Elke subsessie werkt in een **eigen werkgebied** en wist niets in bulk. Het acceptatie-account is gedeeld.
- De uitkomsten komen als meetbestanden in `docs/architectuur/metingen/centrale-agent-<datum>-r<n>/` (een `ronde-n.md`
  plus `ronde-n-runs.jsonl`), en een regel in het meetlogboek. Meetbestanden worden achteraf niet gewijzigd.
- Een profiel wordt opnieuw gemeten als het verandert of erbij komt (deel B, poort 3).

### A7. De overgang: naast elkaar, de meting beslist

1. De centrale agent komt achter de vlag `centraleAgent` (standaard uit, alleen acceptatie, met poort-guard), naast de
   huidige supervisor. Met de vlag uit is Lex bitgelijk aan nu. Elke stap (A2 tot en met A5) breidt uit wat de vlag
   aanzet, en is los te meten en terug te draaien.
2. De meting (A6) vergelijkt beide.
3. Bij winst vervallen de supervisor-modelstap, het `WORKERS:`-formaat en de keuze tussen specialisten. De regisseur
   blijft, als tool op de delegatie. Er blijven geen twee varianten bestaan.
4. Bij verlies blijft de oude weg, en zegt het meetlogboek waarom. Valt alleen de delegatie tegen en de centrale agent
   zonder subagents niet, dan blijft A2 en vervalt de rest.

## Deel B — De werkplaats: zelf skills, profielen en MCP's maken

### B1. Eén levenscyclus voor alles wat de gebruiker maakt

Er komt één register voor eigen onderdelen, de **werkplaats**, voor drie soorten: `skill`, `agentprofiel` (A2) en `mcp`
(een contextconnector, ADR-013 fase 2a, na ADR-007).

```
concept ──► proef (acceptatie) ──► voorgesteld (concept-PR) ──► actief (na review, poort, merge en uitrol)
   ▲              │                        │
   └──────────────┴──── nieuwe versie ◄────┘                       ingetrokken (op elk moment)
```

- **Concept.** De gebruiker maakt of bewerkt het onderdeel in Lex. Elke opslag is een nieuwe versie: een volledige
  snapshot met een hash (zoals de Skills-API), append-only, met de audit erbij.
- **Proef.** Op acceptatie is een conceptversie aan te zetten in een gesprek (B3).
- **Voorgesteld.** Een beheerder met 2FA promoveert een versie tot concept-PR met de hele map. Dit vervangt de
  sectie-editor van C7; een sectie bewerken is een conceptversie met één gewijzigd bestand.
- **Actief.** Een versie is actief als de catalogus van de draaiende graph-qa dezelfde hash toont. Lex leidt die stand
  af en schrijft hem nooit zelf. Er is één waarheid: wat in het image zit.
- **Bestaande skills** komen er vanzelf in: bewerken begint met een conceptversie uit de catalogus, met de hash van het
  image als basis. Is `master` intussen veranderd, dan vraagt Lex een nieuwe versie op de nieuwe basis.

Een gepromoveerd agentprofiel is een bestand `.claude/lex-agents/<naam>.md` met de frontmatter van A2 (de veldnamen van
een Claude Code-subagent waar ze overeenkomen). Een generator bundelt de profielen in het image, zoals het
methodepakket. Bewust niet in `.claude/agents/`: daar staan de Claude Code-subagents van het acceptatieteam, en Claude
Code zou een Lex-profiel met Lex-toolnamen als eigen subagent laden.

Een MCP-server wordt nooit een bestand in de repo: de URL hoort bij een omgeving, en de repo is publiek. Zijn "actief" is
de goedkeuring per tool door de beheerder (ADR-013).

### B2. Toetsen in drie poorten

| Poort | Wanneer | Wat | Wie toetst |
|---|---|---|---|
| **1. Validatie** | bij elke opslag, live in de editor | skill: de Agent Skills-specificatie plus de Lex-regels (`metadata.lex_*`, bronregister, unieke sectie-id's en broncodes over alle skills heen, alleen bestaande rollen, herkomst en licentie, een grens op de omvang); profiel: de grenzen van A2 | **dezelfde validator als de generator**, in `bronmodel` |
| **2. Evals in de proef** | op verzoek | de evals uit de skill (`evals/<case>/`, de vorm van `claude plugin eval`) als beurten met de conceptversie aan; de uitslag hangt aan die versie | de run-API, binnen het tokenbudget |
| **3. Meting bij promotie** | in de PR, als een skill een vaste rol raakt, en altijd bij een profiel | de meetregel van ADR-010 | de reviewer en de poort |

Een skill die alleen de rol `agent` noemt, raakt geen vaste rol. Hij doet mee op beschrijving (A2) en vraagt bij
promotie de toets op laden: geladen waar het hoort, niet waar het niet hoort (A6, de regel bij B3).

Regels uit een skill (`regels/`, S6) blijven buiten de werkplaats tot C9: een regel landt pas als hij zijn eigen tests
haalt.

### B3. De proef: werkt zoals na de merge

- Aan per gesprek in het menu *Bronnen en tools*, in een groep *Proef*. Een wijziging geldt vanaf de volgende beurt.
- Een conceptskill werkt zoals na de merge:
  - zijn beschrijving staat bij de skills van `centraal` en `algemeen`, en zijn secties voor de rol `agent` laden op
    verzoek;
  - noemt hij een vaste rol, dan gaan zijn secties in dat gesprek ook naar die rol.
- **Een concept voegt toe of vervangt zichzelf.** Een nieuwe versie van een bestaande skill vervangt in dat gesprek de
  versie uit het image, als geheel. Een concept kan geen secties van een ándere skill vervangen: sectie-id's zijn
  uniek over alle skills (poort 1).
- Een conceptprofiel kan de centrale agent kiezen, en de gebruiker met `/agent <naam>`.
- Graph-qa haalt de inhoud zelf bij de api op versie-id en hash (in `agent_toegang.TOEGESTAAN`) en valideert hem
  opnieuw. De browser stuurt alleen het id.
- Elk antwoord met een proef aan krijgt een label (*Proef: <naam> v<n>*), de versiehash staat in de provenance en in
  `model_aanroep`, en de beurt telt niet mee in metingen.
- Een proef heeft een eigen voorvoegsel en dus een koude cache. Dat is de prijs van proberen, en het label maakt het
  herkenbaar in de meting per beurt.
- De vlag `werkplaats` staat standaard uit, alleen op acceptatie aan, met poort-guard. Met de vlag uit is Lex bitgelijk.
- `test_context_per_agent` gaat ook over de proef: een agent krijgt het register plus precies de conceptversies die aan
  staan.

Dit is geen overlay zoals ADR-014 die afwees: een proef geldt alleen waar iemand hem aanzette, is in elk antwoord te
zien en telt niet mee in metingen.

### B4. Rechten

| Wat | Analist | Beheerder (met 2FA) |
|---|---|---|
| een concept maken en bewerken | ja, als de beheerder dat toestaat (standaard aan op acceptatie) | ja |
| een eigen concept proefdraaien | ja, in eigen gesprekken | ja |
| een concept delen voor de proef van anderen | nee | ja |
| promoveren tot concept-PR | nee | ja |
| intrekken | eigen concepten | alles |

**Een concept is invoer voor het model, en zo behandelt Lex het.** Het geeft geen tools en zet geen controle uit: wat
mag, beslissen het profiel en `dispatch`, en de controles draaien op elke run. Wie een concept schrijft, stuurt alleen
zijn eigen gesprekken; anderen bereikt het pas als een beheerder het deelt of promoveert. Elke stap staat in de audit.

### B5. Koppeling zonder koppeltabel

- Een skill noemt zijn rollen (`agentrollen.json`, met de generieke rol `agent`). Een nieuwe rol kan een skill
  niet maken (ADR-014 §5).
- Een profiel noemt zijn skills, tools, connectors en sjabloon (A2).
- De catalogus toont beide richtingen (`hangt_af_van`); `test_catalogus.py` houdt ze kloppend.

### B6. Openbaar of niet

- Promotie kan alleen bij vrije tekst: eigen woorden, of een vrije licentie met een `BRON.md`. De validator toetst
  `lex_letterlijk`, `lex_licentie` en de `BRON.md`.
- Tekst die niet letterlijk mag (het boek, de BRM-readers) kan een concept op acceptatie zijn, maar niet promoveren.
- Vóór de promotie toont Lex *Dit wordt openbaar in de repo*, met de bestanden. De beheerder bevestigt.
- De PR-tekst noemt het onderdeel, de versie, de toelichting en de uitslag van poort 1 en 2, en niets over de omgeving.

### B7. Maken: een editor op *Werkwijze van Lex*

Een editor per onderdeel: de bestanden in een boom, de validatie live ernaast, de versies, en vergelijken tussen
versies. *Nieuw* begint vanuit een lege map met de verplichte velden; *Bewerken* vanuit het image. Niet in deze stap
(besluit van de gebruiker): een ZIP uploaden, en een skill laten opstellen door Lex in het gesprek.

## Wat generiek is

- **Eén agentvorm in Python**: de basisklasse `Agent`, met `CentraleAgent` en `Subagent`, op de ene antwoordlus die er
  al is. Alleen het profiel en de opdracht verschillen.
- **Eén profielregister** voor de centrale agent, de subagents en de stappen van een route, met één validator in
  `bronmodel`. Geen samenstelling buiten het register.
- **Eén kindmechanisme**: de kind-run met `ouder_run_id` uit ADR-012 (gelijktijdigheid, *Stop alles*, botsingen), voor
  elke subagent en voor de regie.
- **Eén delegatie-object** bij de api voor de stand, het plan in fasen, het plafond en de audit. Een regie is er een.
- **Eén weg naar boven**: het rapport, met de keuzekaarten in de bundel.
- **Eén manier om een skill te laden**: beschrijving, kern, references; vooraf in een profiel dat hem noemt.
- **Eén register voor eigen onderdelen** (`/v1/werkplaats/*`), één weg naar de PR (de GitHub App van C7), één menu voor
  de proef (*Bronnen en tools*), één waarheid voor "actief" (de catalogushash).
- **Eén contextopbouw**, per run, in de contextweergave als boom.

## PR-volgorde

Spoor **A** (de centrale agent) gaat voor; de eerste stap die op acceptatie iets laat zien is A2. Spoor **B** (de
werkplaats) start ernaast. Ze komen samen bij het profiel.

| Stap | Wat | Raakt | Voorwaarde |
|---|---|---|---|
| **T0** | dit ADR | docs | – |
| **M0** | de agentset (30 opdrachten, A6) en de nulmeting tegen de huidige Lex, drie runs | eval, metingen | T0 |
| **T1** | de validatoren naar `bronmodel`: `bronmodel.skill` (Agent Skills-spec + Lex-regels) en `bronmodel.agentprofiel` (de grenzen van A2); de generator gebruikt ze; het methodepakket blijft byte-gelijk | bronmodel, graph-qa | – |
| **A1** | het profielregister: de specialisten worden profielen (met `kiesbaar`), `SPECIALISTS` wordt eruit afgeleid; `.claude/lex-agents/` en de generator; de soort `agentprofiel` in de catalogus. Gedrag bitgelijk | graph-qa, bronmodel | T1 |
| **A2** | **de centrale agent zonder subagents**, achter `centraleAgent`: `agent/agentvorm.py` (`Agent`, `CentraleAgent`) op de bestaande antwoordketen; het profiel `centraal`; de routes na het model, de taakagents en de ketens als tool; `beantwoord_kaart`; de rol `agent` met skills op beschrijving (`laad_skill`, `lees_skill`). Gemeten tegen de supervisor | graph-qa, deploy (vlag) | A1, M0 |
| **A3** | **één subagent**: `Subagent`, de tools `subagent` en `rapport`, het profiel op het kindgesprek, de delegatie bij de api (de regisseur gebruikt hem, bitgelijk; een kindgesprek kan ook buiten een werkgebied), de bronnen van het kind in het bronregister van het hoofdgesprek, het profiel in de boom van de werkplek en in de contextweergave | graph-qa, api, frontend | A2 |
| **A4** | **vragen omhoog en hervatten**: `status: vraag`, de keuzekaarten in de bundel, het antwoord als klik, hervatten in het kindgesprek, `delegatie_stand` bij een vervolg, *later gewijzigd* na doorvragen in een deelgesprek | graph-qa, api, frontend | A3 |
| **A5** | **meer tegelijk en fasen**: de bevestigingskaart met het plafond, hoogstens `REGIE_PARALLEL` tegelijk met de cache-wachtstap, het plan in fasen met de knop voor de volgende fase, `regie_plan` als tool | graph-qa, api, frontend | A4 |
| **A6** | de eindmeting tegen de huidige weg (A6 hierboven) en het besluit in het meetlogboek | metingen | A5 |
| **A7** | opruimen bij winst: de supervisor-modelstap, het `WORKERS:`-formaat en de keuze tussen specialisten vervallen | graph-qa | A6 |
| **B1** | het register `/v1/werkplaats/*`: onderdeel, versie (snapshot + hash), audit, rechten, de vlag `werkplaats`, vullen uit de catalogus | api, deploy (vlag) | T1 |
| **B2** | de editor op *Werkwijze van Lex*, voor skills; vervangt de sectie-editor van C7 | frontend | B1 |
| **B3** | de proef: de groep *Proef* in *Bronnen en tools*, de versie op de beurt, ophalen en valideren in graph-qa, label en provenance | graph-qa, api, frontend | B1; A2 voor een skill op beschrijving |
| **B4** | evals in de proef en promotie tot concept-PR met de hele map, de licentietoets en *Dit wordt openbaar*; de stand *actief* uit de catalogushash | api, frontend | B3; de GitHub App op acceptatie |
| **B5** | profielen in de werkplaats: editor, proef, promotie, `/agent <naam>` | api, frontend, graph-qa | B4, A3 |
| **B6** | de MCP-contextconnector als soort in de werkplaats, te noemen in een profiel (ADR-013 fase 2a) | alle | besluit ADR-007 |

Afhankelijkheden die niet uit de tabel blijken:

- A2 is op zichzelf een eindpunt. Valt de delegatie later tegen, dan blijft de centrale agent zonder subagents.
- A3 bevat api-werk (de delegatie, het kindgesprek buiten een werkgebied). Het raakt de regie, dus de regiemeting gaat
  opnieuw.
- B1 en B2 hebben A niet nodig. B3 werkt voor een vaste rol zonder A2, en voor een skill op beschrijving pas met A2.
- De GitHub App blokkeert alleen B4 en B5.

## Risico's

| Risico | Wat we doen |
|---|---|
| **De centrale agent kost meer tokens dan de supervisor.** | Hij antwoordt zelf en vervangt de supervisorstap; zijn voorvoegsel is vast en blijft een uur warm; de drempel is "niet duurder dan nu" en A2 meet precies dat, vóór er één subagent bestaat. |
| **De centrale agent delegeert te snel.** | De regel staat in zijn instructie; de agentset telt elke onnodige subagent als fout; de bevestigingskaart en het plafond begrenzen de schade. |
| **Eén opdracht maakt het weekbudget op.** | Het plafond per opdracht op de kaart, `max_rondes` en `budget` per profiel, één laag, `REGIE_PARALLEL`. |
| **Subagents doen ketenwerk na in de toollus.** | De ketens zijn tools; de profielen geven geen ruwe schrijftools; een test legt vast dat annoteren alleen via de annotatieketen gaat. |
| **Een vraag naar boven blijft hangen.** | Een vraag is een rapport, geen wachtend proces; de stand *wacht op antwoord* staat bij de api; de werkplek toont hem onder *wacht op jou*; hervatten is een nieuwe beurt. |
| **Een herstart of inschalen breekt een lopende opdracht.** | Wat klaar is, blijft; de delegatie kent de stand; een vervolg start alleen wat niet af is; de kaart zegt dat de werkplek open moet blijven. `minReplicas: 1` blijft een keuze van de eigenaar. |
| **Een rapport of een brontekst stuurt de centrale agent.** | Een rapport is een gegeven: een kop, tekst die op een instructie lijkt onschadelijk gemaakt, feiten en refs uit code, en `verify` op de samenvatting. |
| **Het model roept een workflow-tool niet aan waar de oude route dat wel deed.** | De routes vóór het model blijven; de routeringsset en `golden_gesprek` meten de rest; een terminale tool vult het antwoord uit code. |
| **De proef wordt een tweede waarheid.** | Alleen acceptatie, alleen waar iemand hem aanzette, een label op elk antwoord, de hash in de provenance, geen meetbeurten. |
| **Een concept stuurt het model de verkeerde kant op.** | Een concept geeft geen tools en zet geen controles uit; delen en promoveren alleen door een beheerder met 2FA, met audit; een grens op de omvang. |
| **Te veel skills maken het voorvoegsel groot.** | Alleen naam en beschrijving staan vooraf (ongeveer honderd tokens per skill); de validator begrenst de beschrijving; de meting per beurt toont het. |
| **Vertrouwelijke tekst komt in de publieke repo.** | Promotie alleen bij vrije tekst (B6), bevestiging vooraf, review. |
| **De GitHub App is er nog niet.** | Alleen B4 en B5 wachten erop. |
| **graph-qa is klein** (0,5 vCPU, `minReplicas: 0`). | Eén laag, ≤ `REGIE_PARALLEL` tegelijk, geen wachtende processen. |

## Waarom niet anders

- **De centrale agent stelt per opdracht zelf een profiel samen.** Dat was het eerste besluit. Claude doet het niet: daar
  bouwt code een definitie en kiest het model een type. Een samenstelling is ongemeten en bouwt een eigen cache. Het
  brede profiel geeft dezelfde vrijheid, binnen één gemeten vorm.
- **De centrale agent doet alleen regie en delegeert elke vraag.** Elke vraag kost dan een extra lus, en het antwoord
  wordt twee keer geschreven.
- **De centrale agent plant ook het werk per deelvraag.** Het plan volgt uit de stand bij de api. Een model zou kiezen
  wat de code al weet, en dezelfde stand moet hetzelfde plan geven (ADR-012).
- **Een vraag meteen tonen terwijl de rest doorloopt.** Het vraagt een wekmechanisme dat er niet is, op een dienst die
  geen herstart overleeft. Eerst gebundeld; de meting zegt of meer nodig is.
- **Een tweede lus naast de LangGraph-graaf.** Twee plekken voor de controles, het venster en de events: precies het
  "net niet" dat dit ADR wil voorkomen.
- **De regisseur in code uitbreiden**, met een model dat alleen per opdracht een profiel kiest. Voorspelbaarder, maar de
  centrale agent stelt dan niets op: de opdrachten liggen vast.
- **Alles via de centrale agent, zonder routes ervoor.** Elke vaste vraag zou een modelronde kosten, en dezelfde vraag
  gaf niet meer gegarandeerd hetzelfde antwoord.
- **Volledig vrije subagents.** Niet te meten en niet te toetsen op brongetrouwheid.
- **Twee lagen subagents.** De kosten en de boom groeien snel, op een kleine graph-qa.
- **Direct vervangen.** Zonder vergelijking weet niemand of Lex beter of slechter wordt.
- **Skills alleen in de repo, of alleen in de database.** Alleen de repo: uitproberen kan niet. Alleen de database: dat
  is de overlay die ADR-014 afwees.
- **Een centrale koppeltabel**, of een private repo voor organisatieskills: een tweede register, of infra en een tweede
  bron voor het image.

## Gevolgen

- **ADR-010.** Laag 4 wordt de centrale agent. De open vraag "laag 4 als één agent (optie C)" beslist de meting van
  A2; de vlag heet `centraleAgent`, niet `EEN_ANTWOORDAGENT`. Laag 3 (de taakagents) zijn workflows, die als tool
  beschikbaar zijn. Twee afwijzingen blijven staan, met een nuance:
  - *"één grote agent voor alles"*: de garanties blijven in code (de routes ervoor, de tools per profiel, de jurist
    als poort). De centrale agent is de open laag, niet alles;
  - *"een subagent per lid of per bron"*: blijft afgewezen. Een subagent is er voor werk dat op zichzelf staat, en zijn
    voorvoegsel wordt gedeeld per profiel.
- **ADR-012.** De regisseur blijft code. *"Een model als regisseur"* blijft afgewezen voor werk met een plan uit de
  stand. Nieuw is dat een model subagents opstelt voor werk zonder vast plan. `regies` wordt de delegatie; de poort en
  de bundel blijven. Het budgetaandeel per kind blijft voor annoteren, onder het plafond per opdracht.
- **ADR-005.** De supervisor vervalt bij winst (A7). Een klik kiest nog steeds zonder model.
- **ADR-014.** De catalogus krijgt de soort `agentprofiel` en de methoderol `agent`; de sectie-editor van C7 gaat op in
  de werkplaats.
- **ADR-015.** Het voorvoegsel per profiel vervangt het voorvoegsel per specialist. De skillbeschrijvingen horen bij
  het vaste deel.
- Twee nieuwe vlaggen, allebei standaard uit, alleen op acceptatie, met poort-guard: `centraleAgent` en `werkplaats`.
- ADR-013 fase 2a krijgt de werkplaats als beheerplek.

## Wat de review veranderde

Op 12 nov 2026 is dit plan opnieuw beoordeeld: tegen de code van graph-qa, tegen de actuele documentatie van Claude,
en in drie vragenrondes met de gebruiker.

**Besluiten van de gebruiker in de review:**

- De centrale agent beantwoordt een gewone vraag zelf, en delegeert alleen wat zich daarvoor leent.
- **Herzien:** de centrale agent stelt geen profiel ad hoc samen. Hij kiest een bestaand profiel; het brede profiel
  kiest zelf zijn tools en skills.
- Vragen van subagents komen gebundeld, als iedereen klaar is of wacht. Meteen is een latere stap.
- Een bevestigingskaart bij meer dan één subagent, of bij alles wat annoteert of voorstelt. Ongewijzigd.
- Het verdelen per deelvraag blijft code (de regisseur), als tool van de centrale agent.
- Doorvragen in een deelgesprek mag.
- De eerste stap is de centrale agent zonder subagents. De werkplaats start ernaast.
- Succes is alle vier: een grote opdracht in één keer, gewone vragen niet duurder, betere antwoorden, zelf uitbreiden.
- Bij een poort van de jurist stopt Lex, met de volgende fase als één klik.
- Een actieve skill doet vanzelf mee, op beschrijving. De vaste rollen krijgen hem niet vanzelf.
- Een plafond per opdracht op de bevestigingskaart.

**Wat de review verder rechtzette:**

| Wat er stond | Wat er nu staat | Waarom |
|---|---|---|
| zes specialisten worden kiesbare profielen | drie; `annotaties_lezen`, `begrippen_lezen` en `retrieval` zijn `kiesbaar: false` | het zijn stappen van een route in code: de code zocht al, of de uitvoer is JSON voor de keten |
| de centrale agent heeft workflows, `subagent` en `vraag_jurist` | hij heeft ook de graaf- en brontools, en neemt herschrijven, afwijzen en het open kaartje van de supervisor over | anders kon hij niets zelf beantwoorden, en bleef er werk van de supervisor zonder eigenaar |
| een klasse `Agent` "met de lus" | `Agent` draait de bestaande antwoordketen | geen tweede lus |
| `vraag_naar_boven` zet een run op *wacht op antwoord*; "er wacht geen proces" | een vraag is een rapport; de centrale run wacht op alle kinderen; de stand staat op de delegatie | een run overleeft geen herstart, er loopt één run per gesprek, en niets wekt de centrale agent |
| de regisseur "levert zijn plan en zijn kindmechanisme" | de regisseur blijft code, als tool; `regies` wordt de delegatie | Claude houdt bij veel agents het plan ook in code; een kindgesprek buiten een werkgebied vroeg een algemener object |
| het aandeel van 1,25 × de schatting per kind | een plafond per opdracht, en `max_rondes` en `budget` per profiel | voor een open subagent bestaat geen schatting |
| een skill laadt "zoals een Agent Skill" | drie niveaus, de rol `agent` als één nieuwe methoderol, skilltekst is geen bron | `llm_stap` eist de methodekop; een leestool zou anders als bron tellen in de controle |
| enkelvoudig hoogstens +10 % tokens | niet duurder dan de nulmeting | de wens van de gebruiker, en haalbaar nu de supervisorstap vervalt |
| niets over een rapport als invoer | het rapport is een gegeven, met een kop en zonder werkende instructies | brontekst van buiten kan via een rapport de centrale agent bereiken |
| A2 bouwt subagents, A3 de centrale agent | A2 is de centrale agent zonder subagents; daarna één subagent, vragen, meer tegelijk | de kleinste stap die iets laat zien, en elke stap los te meten |
| niets over ADR-010 optie C en de eerdere afwijzingen | benoemd onder *Gevolgen* | de centrale agent ís optie C; de lezer moet weten wat herzien is |

**Bewust niet veranderd:** de randvoorwaarde van echte Python-agents, één laag, de routes in code ervoor, de jurist als
poort, de meetlus met 30 opdrachten en hoogstens vier rondes, de hele werkplaats (levenscyclus, drie poorten, rechten,
openbaar of niet), de plek van de profielen (`.claude/lex-agents/`), en de MCP-soort als gereserveerde laatste stap.
