# ADR-016 — De centrale agent en de werkplaats: één agentvorm, profielen en eigen onderdelen

Status: **concept, wacht op akkoord**. Datum: 2026-11-12. Totaalplan: dit ADR vervangt de eerste versie, die alleen
over de werkplaats ging.

Bouwt voort op [ADR-010](adr-010-agentarchitectuur.md) (vier lagen, contract, meetregel),
[ADR-012](adr-012-multi-agent-regie.md) (regie met kindgesprekken), [ADR-013](adr-013-connectors-en-externe-bronnen.md)
(connectors), [ADR-014](adr-014-catalogus.md) (de catalogus) en [ADR-015](adr-015-contextbeheer.md) (contextbeheer). De
bouw van MCP-servers wacht op [ADR-007](adr-007-llm-pad-en-verwerker.md).

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

Het verband: wat de centrale agent per opdracht kiest of samenstelt, is een **agentprofiel**. Wat de gebruiker in Lex
maakt, zijn skills en profielen. Eén ontwerp dus, geen twee.

### De agents van nu, en waar het "net niet" zit

| Onderdeel | Wat het doet | Vorm |
|---|---|---|
| Routering in code (`agent/routes.py`, `nodes/supervisie._kies`) | ±16 routes zonder model: een klik (`ACTIE_TAAK`), een bepaling, een overzicht, een leesvraag, een doorvraag | code |
| Supervisor (`agent/supervisor.py`) | een model kiest wat de code niet las: `WORKERS:` uit een vaste lijst (antwoord, annotatie, werkgebied, deelvragen, begrippen), `SPECIALIST:` en `TAAK:` | strict modelstap met een tekstformaat |
| Specialisten (`agent/specialists.py`) | definitie, duiding, algemeen, retrieval, annotaties_lezen, begrippen_lezen: dezelfde toollus met een eigen system, tools en sjablonen | dataclass-register |
| Taakagents (`agent/agents/`) | deelvragen, begrippen, annotatie: een `Taak`-lijst met hoogstens één strict modelstap per taak | code (feitelijk workflows) |
| Vaste workflows | bepaling, overzicht, bronselectie, werkgebied-intake, annotatieketen, begrippenketen | code |
| Regisseur (ADR-012, `agent/regie/`) | plan in code, bevestiging, kindgesprekken (kind-run met `ouder_run_id`, ≤ `REGIE_PARALLEL`), budget per kind, bundel | vaste workflow |

Waar het net niet zit:

1. **Er zijn twee half-centrale onderdelen, en geen van beide is de centrale agent.** De supervisor kiest één keer uit
   een vaste lijst en geeft dan uit handen. De regisseur verdeelt werk, maar kent maar twee opdrachten (*bronnen* en
   *annoteren* per deelvraag).
2. **De generieke vorm bestaat al, maar verstopt.** Zes specialisten zijn één toollus met een profiel. Alleen staat dat
   profiel in Python, kiest alleen de supervisor het, en kan niemand er een bij maken.
3. **De taakagents heten agents, maar zijn workflows.** Dat is goed (ADR-010), maar de naam suggereert iets anders, en de
   supervisor behandelt ze als agent in plaats van als tool.
4. **Een kind meldt niets naar boven.** Een kind krijgt een actie, geen opdracht. Een vraag halverwege kan niet; open
   punten komen pas in de bundel.
5. **Skills, tools en connectors liggen per rol vast.** Een kind kan niet "afhankelijk van de vraag" kiezen.
6. **Niemand kan iets maken.** Een nieuwe skill of agent is een PR met de hand (zie ADR-014; alleen één sectie is via
   C7 voor te stellen).

### Hoe Claude het doet

| Bron | Wat we overnemen |
|---|---|
| **Claude Code-subagents** ([sub-agents](https://code.claude.com/docs/en/sub-agents)) | een subagent is markdown met `name`, `description`, `tools` (allowlist), `model`, `skills` (vooraf geladen), `mcpServers`; de body is de systeemprompt. Een subagent krijgt een eigen context; de parent ziet alleen het eindrapport. Een subagent kan de gebruiker niets vragen (`AskUserQuestion` gaat eruit) |
| **Agent SDK** ([subagents](https://code.claude.com/docs/en/agent-sdk/subagents)) | de hoofdagent roept subagents aan met de Agent-tool; `AgentDefinition` (description, prompt, tools, model, skills, mcpServers, maxTurns) kan **dynamisch** worden opgebouwd; "only its final message returns to the parent"; grenzen op diepte, gelijktijdigheid en budget; een subagent is te hervatten met zijn eigen geschiedenis |
| **Agent Skills-specificatie** ([specification](https://agentskills.io/specification)) | een skill is een map met `SKILL.md` en `references/`; progressive disclosure: eerst naam en beschrijving, de body en references pas bij gebruik; `skills-ref validate` |
| **Skills-API** ([skills-guide](https://platform.claude.com/docs/en/api/skills-guide)) | een eigen skill is data met versies, elke versie "a complete snapshot, not a delta"; een aanroep kiest `latest` of een vaste versie |
| **Plugins** ([plugins-reference](https://code.claude.com/docs/en/plugins-reference)) en **claude.ai** ([organisatieskills](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization)) | een bundel met versie en validatie; de beheerder stelt beschikbaar voor de organisatie, leden maken eigen skills (uit te zetten) |

## Besluit

De besluiten zijn van de gebruiker (12 nov 2026, vijf vragenrondes), steeds de aanbevolen richting.

## Deel A — De centrale agent

### A1. Eén centrale agent, één agentvorm

```
verzoek ─► routering in code ─┬─► vaste workflow                 (geen model: bepaling, overzicht, klik, …)
                              └─► centrale agent (modellus) ──┬─► tools: workflows en ketens als tool
                                                              ├─► subagent(profiel, opdracht) ─► kindgesprek
                                                              ├─► subagent(profiel, opdracht) ─► kindgesprek
                                                              └─► vraag aan de jurist (keuzekaart)
```

- **De routering in code blijft ervoor.** Wat de code eenduidig leest, gaat zonder model naar zijn workflow (ADR-010
  laag 1 en 2): dezelfde vraag geeft dezelfde tekst en bronnen, zonder tokens. De rest gaat naar de centrale agent.
- **De centrale agent is één modellus per gesprek** (ADR-010 laag 4). Hij heeft drie soorten tools:
  - de vaste workflows en ketens als tool (bepaling lezen, bronnen vinden, de bronselectie per deelvraag, annoteren
    via de annotatieketen, begrippen voorstellen via de begrippenketen, het plan per deelvraag van de regisseur);
  - `subagent`: zet een subagent aan het werk met een profiel en een opdracht;
  - `vraag_jurist`: legt een vraag voor als keuzekaart in het hoofdgesprek.
- **Elke subagent heeft dezelfde vorm**: de generieke toollus, met de gedeelde modelstap, contextopbouw en
  controles (ADR-010). Wat verschilt, is alleen het profiel (A2) en de opdracht.
- **Eén laag.** Een subagent heeft de tool `subagent` niet. Heeft hij meer nodig, dan meldt hij dat naar boven.
- Supervisor, specialisten en regisseur gaan hierin op (A7): de specialisten worden profielen, de regisseur levert zijn
  plan en zijn kindmechanisme, de supervisor-modelstap vervalt.

### A2. Het agentprofiel: kiezen of samenstellen, binnen grenzen

Een profiel is wat een Claude Code-subagent ook is: een beschrijving, een instructie en een lijst onderdelen.

| Veld | Wat | Grens |
|---|---|---|
| `naam`, `beschrijving` | wanneer de centrale agent dit profiel kiest | – |
| `instructie` | de systeemtekst van de subagent | alleen in een vast of werkplaatsprofiel; een ad-hoc samenstelling gebruikt de generieke instructie |
| `skills` | welke skills hij krijgt | alleen skills uit de catalogus (of een conceptversie in de proef, deel B) |
| `tools` | welke tools | een deelverzameling van de tools van de open laag; nooit `subagent`; nooit een besluit van de jurist |
| `connectors`, `mcp` | welke bronnen en servers | alleen wat in het gesprek aanstaat (ADR-013); `dispatch` blijft weigeren wat uitstaat |
| `sjablonen` | hoe hij afrondt | uit `SJABLONEN` |
| `modelklasse` | `licht` of `zwaar`, verwijst naar de modelprofielen in het beheer | de centrale agent kan niet zwaarder kiezen dan het profiel toestaat |
| `max_rondes`, `budget` | hoe lang en hoe duur | begrensd per profiel en per kind (A5) |

Drie herkomsten, één type:

- **Vaste profielen**, uit de catalogus. De zes specialisten worden de eerste vaste profielen (`definitie`, `duiding`,
  `algemeen`, `retrieval`, `annotaties_lezen`, `begrippen_lezen`), met hun huidige system, tools en sjablonen.
- **Werkplaatsprofielen**, door de gebruiker gemaakt (deel B), na promotie een bestand in de repo.
- **Een ad-hoc samenstelling** door de centrale agent: skills, tools, connectors en sjabloon gekozen voor deze opdracht.
  Code valideert de samenstelling tegen de grenzen hierboven. De samenstelling krijgt een hash, die in de provenance en
  in `model_aanroep` staat. Wat vaak terugkomt, kan de gebruiker in de werkplaats tot vast profiel maken.

**Een skill in een profiel** laadt zoals een Agent Skill: de subagent ziet de naam en beschrijving van zijn skills, plus
de secties die de skill voor de generieke agentrol bestemt (`agentrollen.json`, rol `agent`). De references haalt hij op
met een leestool (`lees_skill(skill, sectie)`) wanneer hij ze nodig heeft. De methodetekst van de bestaande rollen blijft
byte-gelijk zolang de oude weg bestaat (ADR-010, P19).

### A3. De opdracht en de context van een subagent

- **Een subagent begint schoon.** Hij krijgt niet de historie van het hoofdgesprek, maar:
  - de identiteit van Lex, de instructie van zijn profiel en de skillsecties;
  - de toolschema's van zijn profiel;
  - de **opdracht** van de centrale agent: wat hij moet doen, waarover (het onderwerp, zoals een deelvraag of
    bepaling), wat hij moet opleveren en wat niet;
  - de werkgebiedcontext, begrensd per laag (ADR-010, `werkgebied_context.py`).
- **De centrale agent ziet alleen wat naar boven komt**: het rapport, de artefacten en de vragen. Niet de toolresultaten
  van de subagent. Zo blijft zijn context klein, zoals bij een Claude Code-subagent.
- **De contextweergave** (de sessie *contextweergave*) toont het gesprek als boom: de centrale agent met zijn
  subagents (`ouder_run_id`), en per knoop dezelfde contextkaart als bij een gewone beurt (identiteit, methodesecties met
  `methode.vingerafdruk`, `tools_hash`, `system_hash`, de opdracht in plaats van de historie). Er komt geen tweede vorm
  van de contextopbouw.
- **Cache** (ADR-015): subagents met hetzelfde profiel delen hun voorvoegsel. Een ad-hoc samenstelling bouwt een eigen
  cache; dat telt mee in de meting (A6).

### A4. Naar boven: vragen en klaar melden

Een subagent heeft twee eigen tools, allebei strict:

- **`vraag_naar_boven(vraag, opties?)`**. De subagent stopt zijn run met de stand *wacht op antwoord*. De vraag gaat naar
  de centrale agent:
  - kan hij hem beantwoorden uit wat er ligt (het dossier, een ander rapport), dan doet hij dat;
  - anders legt hij hem aan de jurist voor met `vraag_jurist`, als keuzekaart in het hoofdgesprek.

  Het antwoord hervat de subagent als nieuwe beurt in zijn kindgesprek, met zijn eigen geschiedenis. Zo overleeft een
  vraag een herstart en `minReplicas: 0`: er wacht geen proces, alleen een stand bij de api.
- **`klaar(rapport)`** sluit de subagent af. Het rapport heeft een vaste vorm: wat gedaan is, de artefacten (refs uit
  code, nooit uit modeltekst), de bronnen, open vragen, en wat niet lukte. De controles (brongetrouwheid, id-herkomst)
  draaien op het rapport zoals op elk antwoord.

De centrale agent bundelt de rapporten in het hoofdgesprek, met de drie lijsten van ADR-012: *opgeleverd*, *wacht op
jou*, *mislukt of niet aan bod*. De kindgesprekken staan eronder, zoals nu.

### A5. Wat in code blijft

| Wat | Waarom | Hoe |
|---|---|---|
| **Routering in code** vóór de centrale agent | dezelfde vraag, hetzelfde antwoord, nul tokens | `agent/routes.py`, de routeringsset (ADR-010) |
| **De deterministische ketens**: annoteren (ADR-001), bronnen vinden en de bronselectie (spoor J), de begrippenketen (ADR-004), het regieplan | regels en tests, geen prompts; herhaalbaar en meetbaar | tools van de centrale agent en de subagents; een subagent doet het werk van een keten nooit zelf na |
| **De jurist als poort** | de AI stelt voor, de mens beslist | besluiten (opnemen, uitsluiten, beoordelen, accorderen) roept geen agent aan (`agent_toegang.TOEGESTAAN`); **een bevestigingskaart vóór meer dan één subagent, of vóór een opdracht die annoteert of veel tokens kost**, met het plan, de profielen, de schatting en het budget; één subagent voor lezen of zoeken start meteen |
| **Brongetrouwheid** | niet onderhandelbaar | grounding, verify en id-herkomst als controles op elke run, ook op elk rapport |
| **Tokens** | het budget is per gebruiker begrensd | per kind een aandeel (1,25 × de schatting, ADR-012), ≤ `REGIE_PARALLEL` tegelijk, één laag, `max_rondes` per profiel, een plafond per boom |
| **De meetregel** | geen agent zonder meting (ADR-010) | A6 |

Wat vrij wordt: welk profiel of welke samenstelling, de formulering van de opdracht, hoeveel subagents (binnen de
grenzen), de volgorde, het beantwoorden van een vraag uit wat er ligt, en de tekst van de bundel (de feiten komen uit
code).

### A6. Meten

- De centrale agent en de generieke subagentvorm worden één keer gemeten tegen de huidige weg: de kwaliteitsset, de
  routeringsset en de meting per beurt, drie runs (ADR-010). Daarbij: tokens per beurt, duur, cache-aandeel en het
  aantal subagents.
- Een vast profiel wordt gemeten als het verandert of erbij komt (deel B, poort 3).
- Een ad-hoc samenstelling wordt niet apart gemeten: ze valt onder de meting van de vorm, haar hash staat in de
  provenance, en de controles bewaken elke run.

### A7. De overgang: naast elkaar, de meting beslist

1. De centrale agent komt achter de vlag `centraleAgent` (standaard uit, alleen acceptatie, met poort-guard), naast de
   huidige supervisor. Met de vlag uit is Lex bitgelijk aan nu.
2. De meting (A6) vergelijkt beide.
3. Bij winst gaan de specialisten op als vaste profielen, wordt de regisseur een tool plus het generieke
   kindmechanisme, en verdwijnen de supervisor-modelstap en het `WORKERS:`-formaat. Er blijven geen twee varianten
   bestaan.
4. Bij verlies blijft de oude weg, en zegt het meetlogboek waarom.

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
| **1. Validatie** | bij elke opslag, live in de editor | skill: de Agent Skills-specificatie plus de Lex-regels (`metadata.lex_*`, bronregister, unieke sectie-id's en broncodes, alleen bestaande rollen, herkomst en licentie); profiel: de grenzen van A2 | **dezelfde validator als de generator**, in `bronmodel` |
| **2. Evals in de proef** | op verzoek | de evals uit de skill (`evals/<case>/`, de vorm van `claude plugin eval`) als beurten met de conceptversie aan; de uitslag hangt aan die versie | de run-API, binnen het tokenbudget |
| **3. Meting bij promotie** | in de PR, als een skill een rol raakt, en altijd bij een profiel | de meetregel van ADR-010 | de reviewer en de poort |

Regels uit een skill (`regels/`, S6) blijven buiten de werkplaats tot C9: een regel landt pas als hij zijn eigen tests
haalt.

### B3. De proef: werkt zoals na de merge

- Aan per gesprek in het menu *Bronnen en tools*, in een groep *Proef*. Een wijziging geldt vanaf de volgende beurt.
- Een conceptskill werkt zoals na de merge: zijn secties gaan naar de rollen die hij noemt (en naar de profielen die hem
  noemen). Een conceptprofiel kan de centrale agent kiezen, en de gebruiker met `/agent <naam>`.
- Graph-qa haalt de inhoud zelf bij de api op versie-id en hash (in `agent_toegang.TOEGESTAAN`) en valideert hem
  opnieuw. De browser stuurt alleen het id.
- Elk antwoord met een proef aan krijgt een label (*Proef: <naam> v<n>*), de versiehash staat in de provenance en in
  `model_aanroep`, en de beurt telt niet mee in metingen.
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

### B5. Koppeling zonder koppeltabel

- Een skill noemt zijn rollen (`agentrollen.json`, inclusief de generieke rol `agent`). Een nieuwe rol kan een skill
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

- **Eén agentvorm**: de generieke toollus voor elke subagent; alleen het profiel en de opdracht verschillen.
- **Eén profieltype** voor vaste, werkplaats- en ad-hocprofielen, met één validator in `bronmodel`.
- **Eén kindmechanisme**: de kind-run met `ouder_run_id` uit ADR-012 (budgetaandeel, gelijktijdigheid, *Stop alles*,
  botsingen), voor elke subagent. De regisseur gebruikt hetzelfde mechanisme.
- **Eén weg naar boven**: `vraag_naar_boven` en `klaar`, met de keuzekaart in het hoofdgesprek.
- **Eén register voor eigen onderdelen** (`/v1/werkplaats/*`), één weg naar de PR (de GitHub App van C7), één menu voor
  de proef (*Bronnen en tools*), één waarheid voor "actief" (de catalogushash).
- **Eén contextopbouw**, per run, in de contextweergave als boom.

## PR-volgorde

Twee sporen die naast elkaar kunnen: **A** (de centrale agent) en **B** (de werkplaats). Ze komen samen bij het profiel.

| Stap | Wat | Raakt | Voorwaarde |
|---|---|---|---|
| **T0** | dit ADR | docs | – |
| **T1** | de validatoren naar `bronmodel`: `bronmodel.skill` (Agent Skills-spec + Lex-regels) en `bronmodel.agentprofiel` (de grenzen van A2); de generator gebruikt ze; het methodepakket blijft byte-gelijk | bronmodel, graph-qa | – |
| **A1** | het profieltype: de zes specialisten worden vaste profielen, `SPECIALISTS` wordt eruit afgeleid; `.claude/lex-agents/` en de generator; de soort `agentprofiel` in de catalogus. Gedrag bitgelijk | graph-qa, bronmodel | T1 |
| **A2** | de generieke subagent: één toollus die elk profiel draait, `vraag_naar_boven` en `klaar`, het kindmechanisme van de regisseur generiek gemaakt (de regisseur gebruikt het, bitgelijk), hervatten na een antwoord | graph-qa, api | A1 |
| **A3** | de centrale agent achter `centraleAgent`: de modellus met de workflows als tool, `subagent`, `vraag_jurist`, de bevestigingskaart, de bundel; de boom in de werkplek en de contextweergave | graph-qa, api, frontend, deploy (vlag) | A2 |
| **A4** | de meting tegen de huidige weg (A6) en het besluit in het meetlogboek | metingen | A3 |
| **A5** | opruimen bij winst: de supervisor-modelstap, het `WORKERS:`-formaat en de regie-opdrachten gaan op in de centrale agent | graph-qa | A4 |
| **B1** | het register `/v1/werkplaats/*`: onderdeel, versie (snapshot + hash), audit, rechten, de vlag `werkplaats`, vullen uit de catalogus | api, deploy (vlag) | T1 |
| **B2** | de editor op *Werkwijze van Lex*, voor skills; vervangt de sectie-editor van C7 | frontend | B1 |
| **B3** | de proef: de groep *Proef* in *Bronnen en tools*, de versie op de beurt, ophalen en valideren in graph-qa, label en provenance | graph-qa, api, frontend | B1 |
| **B4** | evals in de proef en promotie tot concept-PR met de hele map, de licentietoets en *Dit wordt openbaar*; de stand *actief* uit de catalogushash | api, frontend | B3; de GitHub App op acceptatie |
| **B5** | profielen in de werkplaats: editor, proef, promotie, `/agent <naam>` | api, frontend, graph-qa | B4, A2 |
| **B6** | de MCP-contextconnector als soort in de werkplaats, te noemen in een profiel (ADR-013 fase 2a) | alle | besluit ADR-007 |

A1–A3 en B1–B4 kunnen naast elkaar. B5 heeft A2 nodig.

## Risico's

| Risico | Wat we doen |
|---|---|
| **De centrale agent kost meer tokens dan de supervisor.** | De code-routes blijven ervoor; een lichte modelklasse waar het kan; budget per kind en een plafond per boom; de meting (A6) beslist. |
| **Een ad-hoc samenstelling is niet te meten.** | Ze kan alleen binnen de grenzen van A2, de controles draaien op elke run, de hash staat in de provenance; wat vaak terugkomt, wordt een vast profiel met een meting. |
| **Subagents doen ketenwerk na in de toollus.** | De ketens zijn tools; de profielen geven geen ruwe schrijftools; een test legt vast dat annoteren alleen via de annotatieketen gaat. |
| **Een vraag naar boven blijft hangen.** | De stand *wacht op antwoord* staat bij de api, niet in een proces; de werkplek toont hem onder *wacht op jou*; hervatten is een nieuwe beurt. |
| **De proef wordt een tweede waarheid.** | Alleen acceptatie, alleen waar iemand hem aanzette, een label op elk antwoord, de hash in de provenance, geen meetbeurten. |
| **Een concept stuurt het model de verkeerde kant op.** | Een concept geeft geen tools en zet geen controles uit; delen en promoveren alleen door een beheerder met 2FA, met audit; een grens op de omvang. |
| **Vertrouwelijke tekst komt in de publieke repo.** | Promotie alleen bij vrije tekst (B6), bevestiging vooraf, review. |
| **De GitHub App is er nog niet.** | Alleen B4 en B5 wachten erop. |
| **graph-qa is klein** (0,5 vCPU, `minReplicas: 0`). | Eén laag, ≤ `REGIE_PARALLEL` tegelijk, vragen als stand bij de api in plaats van wachtende processen. |
| **De cache breekt per profiel.** | Vaste profielen delen hun voorvoegsel; de meting telt het cache-aandeel mee (ADR-015). |

## Waarom niet anders

- **De regisseur in code uitbreiden**, met een model dat alleen per opdracht een profiel kiest. Voorspelbaarder, maar de
  centrale agent stelt dan niets op: de opdrachten liggen vast. Wel nemen we zijn plan, poort en kindmechanisme over.
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

- ADR-010: laag 4 wordt de centrale agent met subagents; laag 3 (de taakagents) zijn workflows, die als tool beschikbaar
  zijn.
- ADR-012: de regisseur levert zijn plan als tool en zijn kindmechanisme als het generieke mechanisme; de poort en het
  budget blijven.
- ADR-014: de catalogus krijgt de soort `agentprofiel`; de sectie-editor van C7 gaat op in de werkplaats.
- Twee nieuwe vlaggen, allebei standaard uit, alleen op acceptatie, met poort-guard: `centraleAgent` en `werkplaats`.
- ADR-013 fase 2a krijgt de werkplaats als beheerplek.
