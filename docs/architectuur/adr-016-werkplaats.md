# ADR-016 — De werkplaats: skills, agentprofielen en MCP's maken in Lex

Status: **concept, wacht op akkoord**. Datum: 2026-11-12.

Bouwt voort op [ADR-014](adr-014-catalogus.md) (de catalogus) en hangt samen met [ADR-010](adr-010-agentarchitectuur.md)
(agentarchitectuur en de meetregel), [ADR-013](adr-013-connectors-en-externe-bronnen.md) (connectors) en
[ADR-007](adr-007-llm-pad-en-verwerker.md) (wat er naar het model mag).

## Context

De gebruiker wil vanuit Lex zelf skills kunnen aanmaken, toevoegen en bewerken, zoals een skill voor JRM 2. Agents,
MCP's en tools horen erbij, zoals in Claude en Claude Code. Letterlijk: "Ik wil skills, agents, MCP's, agent tools, dus
op de juiste wijze moeten die natuurlijk blijven werken. En dan moet die samenhang in zitten."

### Wat er nu is (12 nov 2026)

| Wat | Inzien in Lex | Wijzigen vanuit Lex | Toevoegen |
|---|---|---|---|
| Methode-skill (`.claude/skills/<naam>/`) | ja, op *Werkwijze van Lex* (catalogus) | één sectie van een bestaande reference, als concept-PR, alleen beheerder met 2FA (C7; de GitHub App is nog niet ingericht) | alleen met een PR met de hand; geen code nodig (`test_skill_zonder_code.py`) |
| Koppeling skill → rol | ja, via `hangt_af_van` | nee | `agentrollen.json` in de skill, met de hand |
| Regels uit een skill | ja | nee (C9 is open) | PR, achter de proefvlag `SKILL_REGELS` |
| Specialist, taakagent, workflow, route | ja | nee | PR met code en een meting (ADR-010) |
| Tool, bronconnector | ja | nee | PR met code en het resultaatcontract (ADR-013) |
| MCP-server (contextconnector) | – | – | ADR-013 fase 2a, wacht op ADR-007 |

Wat ontbreekt:

1. **Een nieuwe skill maken** in Lex. Er is alleen een sectie-editor voor bestaande tekst.
2. **Een hele skill bewerken**: `SKILL.md`, de references, de bronnen en de koppeling aan rollen.
3. **Uitproberen vóór het een PR is.** Nu zie je pas na merge en uitrol wat een wijziging met Lex doet.
4. **Een agent samenstellen** uit bestaande onderdelen (instructie, skills, tools, sjabloon) zonder code.
5. **Eén levenscyclus** voor alles wat de gebruiker maakt: concept, proef, voorstel, actief, met rechten en audit.
6. **De toetsing** van een nieuwe skill vóór hij actief is: validatie, evals en de meetregel als vaste stappen.

### Hoe Claude het doet

| Product | Skill | Agent | MCP | Beheer en versies |
|---|---|---|---|---|
| **Agent Skills-specificatie** ([agentskills.io/specification](https://agentskills.io/specification)) | een map met `SKILL.md` (frontmatter `name` ≤ 64, `description` ≤ 1024, optioneel `license`, `compatibility`, `metadata`, `allowed-tools`), `references/`, `assets/`, `scripts/`; progressive disclosure: eerst naam en beschrijving, de body bij gebruik, references op verzoek; `name` gelijk aan de mapnaam | – | – | `skills-ref validate` toetst de frontmatter en de naamregels |
| **Claude Code** ([sub-agents](https://code.claude.com/docs/en/sub-agents), [plugins](https://code.claude.com/docs/en/plugins-reference)) | skills als bestanden in de repo, de gebruikersmap of een plugin | een subagent is markdown met frontmatter: `name`, `description`, `tools` (allowlist), `model`, `skills` (vooraf geladen), `mcpServers`; de body is de systeemprompt | in `.mcp.json` of de plugin; een subagent krijgt alleen de servers die hij noemt | een plugin bundelt skills, agents, hooks en MCP's met een `version`; `claude plugin validate`; aan/uit per scope; managed settings gaan voor |
| **Skills-API** ([skills-guide](https://platform.claude.com/docs/en/api/skills-guide)) | een custom skill is data in de workspace: `POST /v1/skills`, een nieuwe versie met `POST /v1/skills/{id}/versions` | – | – | elke versie is een volledige snapshot ("a complete snapshot, not a delta"); een aanroep kiest `latest` of een vaste versie; de workspace is de grens |
| **claude.ai** ([organisatieskills](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization)) | een ZIP met `SKILL.md` uploaden | Projects: instructies plus kennis | connectors | de eigenaar stelt skills beschikbaar voor de organisatie; leden mogen standaard eigen skills uploaden, en dat is uit te zetten |

Twee lessen:

- **Data én bestand.** De API bewaart een skill als data met volledige versies; Claude Code leest hem als bestand. Lex
  doet allebei, elk voor een eigen fase: werken en proberen op data, actief worden als bestand in het image.
- **Een agent is een samenstelling.** In Claude Code is een subagent een beschrijving, een instructie en een lijst
  tools, skills en MCP-servers. Code is alleen nodig voor de tools zelf.

## Besluit

De besluiten in dit ADR zijn van de gebruiker (12 nov 2026, drie vragenrondes), steeds de aanbevolen richting.

### 1. Eén werkplaats voor alles wat de gebruiker maakt

Er komt één register voor eigen onderdelen, de **werkplaats**, met één levenscyclus voor drie soorten:

- `skill`: een methode-skill (ADR-014 §5);
- `agentprofiel`: een agent samengesteld uit bestaande onderdelen (§5 hieronder);
- `mcp`: een contextconnector (ADR-013 fase 2a); de bouw wacht op ADR-007 (§6).

De soorten volgen dezelfde stappen, rechten, audit en versies. Er komt geen eigen variant per soort.

```
concept ──► proef (acceptatie) ──► voorgesteld (concept-PR) ──► actief (na review, poort, merge en uitrol)
   ▲              │                        │
   └──────────────┴──── nieuwe versie ◄────┘                       ingetrokken (op elk moment)
```

- **Concept.** De gebruiker maakt of bewerkt het onderdeel in Lex. Elke opslag is een nieuwe versie: een volledige
  snapshot van alle bestanden, met een hash (zoals de Skills-API). De versies zijn append-only, met de audit erbij.
- **Proef.** Op acceptatie is een conceptversie aan te zetten in een gesprek (§3). Dat is de enige plek waar hij werkt
  zonder PR.
- **Voorgesteld.** Een beheerder met 2FA promoveert een versie tot concept-PR met de hele map. Dit vervangt de
  sectie-editor van C7: een sectie bewerken is een conceptversie van de skill met één gewijzigd bestand. Er blijft
  één editor en één weg naar de PR.
- **Actief.** Een versie is actief als de catalogus van de draaiende graph-qa dezelfde hash toont. Lex leidt die stand
  af, en schrijft hem nooit zelf. Zo blijft er één waarheid: wat in het image zit.
- **Ingetrokken.** Een concept of proef kan op elk moment uit. Een actief onderdeel verwijder je met een PR.

**Bestaande skills komen er vanzelf in.** Bewerken van `wetsanalyse` of `wetsuitvoering` begint met een conceptversie
die de api vult uit de catalogus (de inhoud en de hash van het image). Bij de promotie geldt die hash als basis: is de
skill op `master` intussen veranderd, dan zegt Lex dat en vraagt een nieuwe versie op de nieuwe basis.

### 2. Toetsen in drie poorten

| Poort | Wanneer | Wat | Wie toetst |
|---|---|---|---|
| **1. Validatie** | bij elke opslag, live in de editor | de Agent Skills-specificatie (naam, beschrijving, mapnaam, één niveau diep) plus de Lex-regels: `metadata.lex_*`, een bronregister met eigen broncodes, sectie-id's en broncodes uniek over de skills, alleen bestaande rollen, herkomst en licentie | **dezelfde validator als de generator**, in `bronmodel` |
| **2. Evals in de proef** | op verzoek, in de proef | de evals uit de skill (`evals/<case>/`, de vorm van `claude plugin eval`) draaien als beurten met de conceptversie aan; de uitslag hangt aan die versie | de bestaande run-API, binnen het tokenbudget van de gebruiker |
| **3. Meting bij promotie** | in de PR, als de skill een rol raakt | de meetregel van ADR-010: de kwaliteitsset, drie runs, vóór en na, in het meetlogboek | de reviewer en de poort; zonder meting landt de PR niet |

Een skill die geen rol raakt (zoals `wetsuitvoering` nu, `"rollen": {}`) heeft poort 3 niet nodig: hij verandert Lex
niet. Een agentprofiel heeft poort 3 altijd nodig, want het is een nieuwe instructie voor een model.

Regels uit een skill (`regels/`, S6) blijven buiten de werkplaats tot C9: een regel landt pas als hij zijn eigen tests
haalt, en dat is een eigen ontwerp.

### 3. De proef: werkt zoals na de merge

- Je zet een conceptversie aan per gesprek in het menu *Bronnen en tools* (ADR-013), in een groep *Proef*. Hetzelfde
  menu, dezelfde stand op het gesprek, dezelfde regel: een wijziging geldt vanaf de volgende beurt.
- **De conceptversie werkt zoals hij na de merge zou werken.** Zijn secties gaan naar de rollen die hij noemt, en
  vervangen voor die beurt de secties met hetzelfde id. Je test dus wat je straks voorstelt.
- **Graph-qa haalt de inhoud zelf bij de api**, op versie-id en hash. De browser stuurt alleen het id mee. De api-aanroep
  staat in `agent_toegang.TOEGESTAAN`. Graph-qa valideert de inhoud opnieuw met dezelfde validator voor hij hem
  gebruikt.
- **Altijd zichtbaar.** Elk antwoord met een proef aan krijgt een label (*Proef: <skill> v<n>*). De provenance en de
  `model_aanroep`-logregel dragen de versiehash naast `methode.vingerafdruk`. Een proefbeurt telt niet mee in metingen.
- **Alleen op acceptatie.** De vlag `werkplaats` staat standaard uit en alleen op acceptatie aan, met een poort-guard,
  zoals `catalogusVoorstellen` en `skillRegels`. Met de vlag uit is Lex bitgelijk aan nu.
- `test_context_per_agent` gaat ook over de proef: wat een agent meekrijgt, is het register plus precies de
  conceptversies die op het gesprek aanstaan, en niets anders.

Dit is geen overlay zoals ADR-014 die afwees. Een overlay verandert stil wat Lex voor iedereen doet. Een proef geldt
alleen in een gesprek waar iemand hem aanzette, is in elk antwoord te zien en telt niet mee in metingen.

### 4. Rechten

| Wat | Analist | Beheerder (met 2FA) |
|---|---|---|
| een concept maken en bewerken | ja, als de beheerder dat toestaat (instelling, standaard aan op acceptatie) | ja |
| een eigen concept proefdraaien | ja, alleen in eigen gesprekken | ja |
| een concept delen, zodat anderen het kunnen proefdraaien | nee | ja |
| promoveren tot concept-PR | nee | ja |
| intrekken | eigen concepten | alles |

Zoals in claude.ai: de beheerder bepaalt wat er voor anderen beschikbaar is, en kan het maken door analisten uitzetten.
Elke stap staat in de audit van de werkplaats (wie, wat, welke versie).

### 5. Koppeling: in de skill en in het agentprofiel

Er komt geen aparte koppeltabel. Elke richting staat op één plek:

- **Een skill noemt zijn rollen.** `agentrollen.json` in de skill zegt welke bestaande rollen welke secties krijgen,
  zoals nu. Een nieuwe rol kan een skill niet maken (ADR-014 §5, trap 2).
- **Een agentprofiel noemt zijn skills**, zoals `skills:` bij een Claude Code-subagent.
- De catalogus toont beide richtingen (`hangt_af_van`). De drift-test (`test_catalogus.py`) houdt ze kloppend.

**Het agentprofiel** is een samenstelling, geen code. Het volgt de vorm van een Claude Code-subagent:

```markdown
---
name: jrm-scenario
description: Werkt een juridisch scenario uit volgens JRM 2, vanuit een bepaling in de graaf.
skills: [wetsuitvoering]
tools: [get_bepaling, zoek_bepalingen]
sjabloon: uitleg
metadata:
  lex_soort: agentprofiel
---
Je bent de scenario-agent van Lex. …
```

- **Het draait in de open laag** (ADR-010 laag 4), met de gedeelde modelstap, contextopbouw en sjablonen.
- **De tools komen uit de bestaande toollaag.** Het profiel kiest een deel van de tools van laag 4. Op een tool die
  uitstaat (connector uit, of niet in het profiel) blijft `dispatch` weigeren. Een profiel maakt geen tools en kan
  geen controles (hooks) uitzetten. `allowed-tools` uit een skill geeft geen rechten in Lex.
- **De ingang is een keuze van de gebruiker**: het commando `/agent <naam>` of een keuze in het menu. De supervisor
  kiest een profiel niet. Routering naar een profiel vraagt een PR met routeringsrijen en een meting (ADR-010).
- **Na promotie** is het een bestand `.claude/lex-agents/<naam>.md`. Een generator bundelt de profielen in het image,
  zoals het methodepakket, en de catalogus leest ze als soort `agentprofiel` (concept *agent*, model `agent`).
  Bewust niet `.claude/agents/`: daar staan de Claude Code-subagents van het acceptatieteam, en Claude Code zou een
  Lex-profiel met Lex-toolnamen als eigen subagent laden.

Wat code blijft: een nieuwe tool, een bronconnector, een specialist of taakagent met een eigen contract, een workflow,
een route en een sjabloon. De catalogus en `catalogus.md` geven daarvoor de checklist, zoals nu.

### 6. MCP-servers: dezelfde werkplaats, na ADR-007

Een eigen MCP-server is de contextconnector van ADR-013 fase 2a: een MCP-URL plus OAuth, goedkeuring per tool met een
vastgezette hash, en de vertrouwensgrens. Hij krijgt de levenscyclus van de werkplaats:

- concept: de beheerder voert de server in en keurt de tools goed;
- proef: aan per gesprek, zoals een conceptskill;
- een agentprofiel kan zijn tools noemen, zoals `mcpServers` bij een Claude Code-subagent.

Een MCP-server wordt nooit een bestand in de repo: de URL hoort bij een omgeving, en de repo is publiek. Zijn
"actief" is de goedkeuring door de beheerder. De bouw begint pas na het besluit over ADR-007.

### 7. Openbaar of niet

De repo is publiek, dus een gepromoveerde skill wordt openbaar.

- **Promotie kan alleen bij vrije tekst**: eigen woorden, of een vrije licentie met een `BRON.md` (zoals W3C). De
  validator toetst `lex_letterlijk`, `lex_licentie` en de `BRON.md`.
- **Tekst die niet letterlijk mag** (het boek, de BRM-readers) kan een concept op acceptatie zijn, maar kan niet
  promoveren. De editor zegt dat bij het opslaan.
- **Vóór de promotie** toont Lex: *Dit wordt openbaar in de repo*, met de bestanden. De beheerder bevestigt.
- De PR-tekst noemt het onderdeel, de versie, de toelichting en de uitslag van poort 1 en 2, en verder niets over de
  omgeving.

### 8. Maken: een editor op *Werkwijze van Lex*

- Een editor per onderdeel op de bestaande pagina: de bestanden van de skill (SKILL.md, references, `agentrollen.json`,
  bronnen, evals) in een boom, met de validatie live ernaast, de versies en een vergelijking tussen twee versies.
- *Nieuwe skill* begint vanuit een lege skillmap met de verplichte velden; *Bewerken* begint vanuit het image.
- Niet in deze stap (besluit van de gebruiker): een ZIP uploaden, en een skill laten opstellen door Lex in het gesprek.
  Beide kunnen later op dezelfde werkplaats aansluiten, met dezelfde validatie.

## Wat generiek is

- **Eén register** (`/v1/werkplaats/*`) met `soort`, versies als snapshot, de levenscyclus en de audit, voor alle
  soorten. Een vierde soort is een adapter, geen tweede register.
- **Eén validator per soort**, in `bronmodel`, gebruikt door de generator, de api, graph-qa en de tests.
- **Eén weg naar de PR**: de GitHub App van C7, uitgebreid van één bestand naar een map. De sectie-editor van C7 gaat weg.
- **Eén menu voor de proef**: *Bronnen en tools*, met de stand op het gesprek (ADR-013).
- **Eén waarheid voor "actief"**: de hash in de catalogus van wat draait.

## PR-volgorde

Skills eerst, agentprofielen daarna, MCP als laatste (besluit van de gebruiker). Elke stap landt los en is op
acceptatie te proberen.

| Stap | Wat | Raakt | Voorwaarde |
|---|---|---|---|
| **W0** | dit ADR | docs | – |
| **W1** | de skillvalidator naar `bronmodel.skill` (Agent Skills-spec + Lex-regels); de generator gebruikt hem; het methodepakket blijft byte-gelijk | bronmodel, graph-qa | – |
| **W2** | het register `/v1/werkplaats/*`: tabellen voor onderdeel, versie (snapshot + hash) en audit, de rechten, de vlag `werkplaats` met poort-guard, het vullen uit de catalogus | api, deploy (vlag) | W1 |
| **W3** | de editor op *Werkwijze van Lex*: nieuw en bewerken, live validatie, versies, vergelijken; vervangt de sectie-editor van C7 | frontend | W2 |
| **W4** | de proef: de groep *Proef* in *Bronnen en tools*, de versie-id op de beurt, graph-qa haalt en valideert de inhoud, het label, de provenance; `test_context_per_agent` breidt uit | graph-qa, api, frontend | W2 |
| **W5** | evals in de proef (poort 2) en promotie tot concept-PR met de hele map, de licentietoets en *Dit wordt openbaar*; de stand *actief* uit de catalogushash | api, frontend | W4; de GitHub App op acceptatie (ingericht door de gebruiker) |
| **W6** | het agentprofiel als bestand: `.claude/lex-agents/`, de generator, de soort `agentprofiel` in de catalogus, de uitvoering in laag 4 met het toolfilter, het commando `/agent` | graph-qa, bronmodel, frontend | W1 |
| **W7** | agentprofielen in de werkplaats: editor, proef, promotie | api, frontend, graph-qa | W5, W6 |
| **W8** | de MCP-contextconnector als soort in de werkplaats (ADR-013 fase 2a) | alle | besluit ADR-007 |

W3 en W4 kunnen naast elkaar. W6 kan naast W2–W5.

## Risico's

| Risico | Wat we doen |
|---|---|
| **De proef wordt een tweede waarheid.** | Alleen acceptatie, alleen in een gesprek waar iemand hem aanzette, een label op elk antwoord, de versiehash in de provenance, geen meetbeurten. Actief is alleen wat de catalogus van het image toont. |
| **Een concept stuurt het model de verkeerde kant op**, met opzet of per ongeluk. | Een concept geeft geen tools en zet geen controles uit; de brongetrouwheidscontrole en de id-herkomst blijven. Delen en promoveren alleen door een beheerder met 2FA, met audit. Een grens op de omvang per versie. |
| **Vertrouwelijke tekst komt in de publieke repo.** | Promotie alleen bij vrije tekst (§7), toets in de validator, bevestiging vooraf, review van de PR. |
| **De GitHub App is er nog niet.** | W1–W4 en W6 werken zonder; W5 en W7 wachten op de inrichting. |
| **De basis verandert onder een concept.** | De basishash gaat mee met de PR; is `master` veranderd, dan vraagt Lex een nieuwe versie. |
| **Een proef kost tokens en breekt de cache.** | Een proefbeurt gaat binnen het tokenbudget van de gebruiker; de cache-prefix van ADR-015 geldt voor de gewone beurt, de proef bouwt zijn eigen. |
| **Metingen worden duur.** | Poort 3 alleen als een skill een rol raakt of bij een agentprofiel; een skill zonder rolkoppeling hoeft niet gemeten. |
| **Een agentprofiel lijkt op een specialist, maar is het niet.** | Het profiel heeft geen eigen routering of contract in code. Wie meer wil, maakt er een specialist of taakagent van met een PR (ADR-010). |

## Waarom niet anders

- **Alleen de repo, via een PR** (C7 uitbreiden). Elke poging kost een PR en een uitrol; uitproberen kan niet.
- **Alleen de database, direct actief.** Dat is de overlay die ADR-014 afwees: twee waarheden, geen poort, metingen
  die hem zouden moeten meetellen.
- **Een volledige agentdefinitie, ook voor de routering.** De routering in code heeft types en tests nodig (ADR-014).
  Een profiel krijgt alleen een ingang die de gebruiker kiest.
- **Een centrale koppeltabel.** Dat is een tweede register naast `agentrollen.json`.
- **Een aparte private repo voor organisatieskills.** Dat vraagt infra en een tweede bron voor het image.

## Gevolgen

- De sectie-editor van C7 verdwijnt; zijn backend (`catalogus_voorstel.py`) gaat op in de promotie van de werkplaats.
- `catalogus.md` krijgt de soort `agentprofiel` en de werkplaats als manier om een skill toe te voegen, naast de PR met
  de hand.
- Een nieuwe vlag `werkplaats` (standaard uit, alleen acceptatie, met poort-guard).
- ADR-013 fase 2a krijgt de werkplaats als beheerplek.
