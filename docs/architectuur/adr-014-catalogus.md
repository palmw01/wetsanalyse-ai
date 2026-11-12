# ADR-014 — De catalogus: wat Lex kan, op één plek

Status: **concept, wacht op akkoord**. Datum: 2026-11-12.

Hangt samen met [ADR-005](adr-005-vraag-lex-en-agents.md), [ADR-008](adr-008-antwoordsjablonen.md),
[ADR-010](adr-010-agentarchitectuur.md), [ADR-012](adr-012-multi-agent-regie.md) en [ADR-013](adr-013-connectors-en-externe-bronnen.md).

Werkdocument: [catalogus.md](catalogus.md).

## Context

De methode, de agents en de deterministische ketens van Lex staan verspreid over Python, YAML en de skill. Alleen wie
de repo leest, ziet:

- welke methode een rol krijgt;
- welke regel een markering voorstelde;
- of er een model aan te pas kwam;
- waar een tekst vandaan komt en onder welke licentie.

Zelfs in de repo is dat niet overal één plek. Elk register heeft een eigen vorm:

- `SPECIALISTS`, `AGENTS` met `ACTIE_TAAK` en `SJABLONEN`;
- de methodesecties in `agentrollen.json`;
- de YAML-regelsets van beide ketens;
- `CONNECTORS`.

Twee registers zijn half af:

- **De routering.** ADR-010 vraagt "één tabel", maar de volgorde staat als takken in `nodes/supervisie.py`.
- **De rollen.** De generator houdt een eigen `ROLLEN`-lijst bij naast `llm_stap.Rol`.

De gebruiker wil de onderdelen kunnen inzien, aanpassen, uitbreiden en toevoegen. Ook een tweede methode, zoals
JRM 2 / wetsuitvoering, moet erbij kunnen. De eisen: het is generiek, het is robuust, en het is geen tweede systeem
naast het bestaande.

Eén patroon in de repo doet dit al goed: de **connectorbeschrijving als enige bron** (ADR-013).

- De beschrijving staat één keer in `bronmodel/connectors.py`.
- De keten leidt er alles uit af: toollaag, specialisten, api-namen en het register.
- `test_connectorbeschrijving.py` maakt een onvolledige beschrijving rood. Een nep-connector komt zonder extra code mee.

## Besluit

### 1. Eén beschrijving per onderdeel, afgeleid uit het register dat er al is

`packages/bronmodel/bronmodel/catalogus.py` definieert `Onderdeel` met:

- `soort`: methode, rol, specialist, agent, workflow, route, connector, sjabloon of regelset;
- de zeven contractpunten van ADR-010: doel, ingang, context, tools, uitvoer, twijfel, eval;
- `model`: `geen`, `strict` of `agent`;
- `versie`: een hash van de inhoud;
- `herkomst`: bron, licentie, verwijzing, en of de tekst letterlijk in de repo mag;
- het bronbestand in de repo;
- wat via de app bewerkbaar is;
- de straatvlag;
- de afhankelijkheden;
- voor een workflow ook `laag` en `stappen`.

Hoe de catalogus aan zijn inhoud komt:

- **Uit het bestaande register.** Per soort leest één adapter (`agent/catalogus.py`, `uit_<soort>`) dat register. Er komt geen tweede lijst.
- **Wat het register niet weet, staat ernaast.** Doel, twijfel en herkomst gaan in één `BESCHRIJVING` per module, of in de YAML-kop of de skill-frontmatter.
- **`model` wordt afgeleid, nooit geschreven.** De bronnen zijn `MODEL_TAKEN`, `llm_stap.Rol` en de specialisten. Een YAML-regel is altijd `geen`.

### 1a. Ketens zijn workflows, met hun stappen als onderdelen

Elke keten staat in de catalogus als `soort: workflow`. Een keten heeft:

- een `laag` (ADR-010: routering, vaste workflow, taakagent of open laag);
- een geordende lijst `stappen`. Elke stap verwijst naar een onderdeel met een eigen `model`.

Een keten kan worden aangestuurd door een agent of een route. Die verwijst dan via `hangt_af_van` naar de workflow.

| Workflow | Laag | Stappen (model) | Regelsets en kennis | Aangestuurd door |
|---|---|---|---|---|
| annotatieketen (ADR-001) | taakagent | detectie (geen) → kandidaten (geen) → classifier (strict) → gerichte review bij twijfel (strict) → besluit (geen) | detectorregels, detectieprofielen, verklaringen, relatiecatalogus | agent `annotatie`, route annoteren |
| begrippenketen (ADR-004) | taakagent | taal (geen) → definities (geen) → signalen (geen) → groeperen (geen) → beslistabel (geen) → meedenken bij twijfel (strict); uitwerken van een begrip (strict) | relatiepatronen, betekenisregels, B1-woorden, geen-begrip | agent `begrippen` |
| bronnen vinden en bronselectie (spoor J) | vaste workflow | zoekvragen a–d (geen) → methoden (geen) → rangschikking (geen) → kaartjes per deelvraag (geen) | zoekvragen-bronselectie (skill) | agent `deelvragen`, acties `bronselectie` |
| bepaling, lijst, tel, overzicht en lezen | vaste workflow | geen model; de tekst komt uit de graaf of de connector | connectorbeschrijving | routes in de routeringstabel |
| regie (ADR-012) | vaste workflow | plan (geen) → bevestiging door de jurist → kindgesprekken (de workflow van het kind) | – | acties `regie_*` |
| werkgebied-intake (spoor F) | vaste workflow | stapmachine (geen); voorstel per veld (strict) | dossiervelden | route intake |

De stappen komen uit de code die ze uitvoert. Voorbeelden: `standaard_detectoren()`, de rijen van `besluit.TABEL`,
`bronnen_vinden.STANDAARD` en `regie.plan`. Er komt geen lijst met de hand naast. Zo is aan elke markering en elk
voorstel te zien welke stap het zette en of daar een model bij was.

### 2. De catalogus is introspectie van wat draait

- Graph-qa bouwt hem bij het starten.
- Hij is te lezen via `GET /v1/catalogus` en `GET /v1/catalogus/{id}`, naast `GET /v1/bronnen`. Die laatste gaat er later in op.
- Het antwoord geeft ook de inhoud: de methodetekst uit `PAKKET`, een regel met zijn testzinnen, de beschrijving van een connector.

Er komt geen gegenereerd catalogusbestand. Dan kan wat je ziet niet afwijken van wat draait.

### 3. Eén drift-test

`tools/graph-qa/tests/test_catalogus.py` werkt naar het voorbeeld van de connectortest. Hij toetst:

- dat elk registerentry precies één onderdeel heeft, en omgekeerd;
- dat elke ingang, elke tool en elk testpad bestaat;
- dat elke verwijzing oplost in het bronregister;
- dat letterlijke tekst van derden alleen voorkomt met een `BRON.md` die de licentie draagt;
- dat een nep-onderdeel meekomt zonder extra code.

### 4. Inzien in de app, wijzigen via een pull request

- **Inzien, voor iedereen.** Op de pagina *Werkwijze van Lex* (`/werkwijze`) staat per onderdeel:
  - het doel;
  - of er een model aan te pas komt;
  - de herkomst;
  - de inhoud;
  - waar het van afhangt.

  Het denkproces en het scherm "Waarom?" linken naar het onderdeel dat de stap zette. Dit is geen
  ontwikkelhulpmiddel: het laat de jurist zien hoe een voorstel ontstond. Drift-status en testuitslagen horen er niet op.
- **Een wijziging voorstellen** (besluit van de gebruiker, 12 nov 2026):
  - Alleen een beheerder kan het, met 2FA, en alleen op acceptatie. De vlag `catalogusVoorstellen` staat standaard uit en heeft een poort-guard.
  - De beheerder bewerkt een bewerkbare sectie.
  - De api valideert met **dezelfde validator als de generator**.
  - Daarna opent de api een **concept-PR** op deze repo.
  - Actief is de wijziging pas na review, de poort, de merge en de uitrol.
  - Er is geen overlay in de database, dus er is maar één waarheid. De metingen op de methode-hash blijven kloppen.
- **Eerst tekst, regels later.** Een voorstel voor een detector- of begrippenregel landt pas als de regel bij het
  opslaan zijn eigen positieve, negatieve en randtests haalt.
- **Iets nieuws toevoegen gaat via een PR in de repo.** Dat geldt voor een skill, agent, workflow, connector of sjabloon.
  `catalogus.md` geeft per soort een checklist. De app maakt geen nieuwe code.

### 5. Een methode is een skill

- Een methode is een map `.claude/skills/<naam>/` met `metadata.lex` in de frontmatter. Daarin staan soort, herkomst en licentie.
- Hij heeft een eigen `agentrollen.json` en een eigen bronregister.
- De generator leest alle methoden. Zijn rollenlijst komt uit `llm_stap.Rol`.
- Hetzelfde bestand is een Claude Code-skill voor wie in de repo werkt, en een methodepakket voor Lex.
- Een nieuwe methode komt in drie trappen:
  1. **methodetekst** voor bestaande rollen;
  2. een **eigen rol of specialist**, alleen met een meting (ADR-010);
  3. **eigen classificaties of detectieprofielen**, alleen met een eigen ADR, want die raken het `act2`-contract.

### 6. Herkomst en licentie

De repo is publiek. Per bron geldt het volgende:

| Bron | Licentie | Letterlijk in de repo |
|---|---|---|
| Eigen werk | – | ja |
| BZK-bronnen, zoals `wetsanalyse-rijk/` en de JRM-specificatie `minbzk/wetsuitvoering` | W3C Software and Document License | ja, met de notice en een vermelding van wijzigingen, in een `BRON.md` naast de bron |
| Boek van Boom, readers van BRM | – | nee, alleen in eigen woorden |

`herkomst.letterlijk` maakt dat onderscheid controleerbaar.

### 7. Samenwerking: concepten, aanroepregels en context per agent (aanvulling 12 nov 2026)

Op verzoek van de gebruiker: "borg je wel de optimale samenwerking tussen de skills, tools (workflows) agents?" Dit
deel legt vast *hoe* de onderdelen samenwerken. De catalogus dwingt het af.

**Elke soort hoort bij één concept**, in lijn met Claude Code (`Onderdeel.concept`, afgeleid uit de soort):

| Concept | Wat het is | Soorten in Lex |
|---|---|---|
| skill | kennis of instructie die zelf niets uitvoert; bij gebruik geladen in de context van een agent of workflow (progressive disclosure: de catalogus toont naam en doel, de body pas op de pagina) | `methode`, `rol`, `regelset` |
| tool | één getypte handeling met het resultaatcontract | `tool`, `connector` (een bundel tools, zoals een MCP-server), `sjabloon` (de strikte afrondtool) |
| workflow | een vaste keten in code; een model alleen in een strict stap via `llm_stap` | `workflow` |
| agent | een modellus met eigen context, eigen tools en een contract (ADR-010); de subagent van Claude Code | `specialist`, `agent` |
| ingang | kiest zonder model één onderdeel | `route`; een commando is een ingang op een `Onderdeel.id` (#1276) |
| hook | een deterministische controle op een vast moment rond een agent of workflow | `controle`: brongetrouwheid na het antwoord (Stop), de herkomst van een id vóór een toolaanroep (PreToolUse), de feitentoets, het vullen van een sjabloon |

**Wie wat mag gebruiken.** `hangt_af_van` betekent "A gebruikt B". `MAG_GEBRUIKEN` legt het per concept vast, en
`test_catalogus.py` maakt een overtreding rood:

| Wie | Mag gebruiken | Model |
|---|---|---|
| skill | niets | `geen` |
| tool | niets; een tool hoort bij hoogstens één connector | `geen`, behalve een sjabloon: `strict` |
| workflow | tool, skill, hook, workflow | `geen` of `strict`. Een strict stap noemt de `llm_stap.Rol` die hem draagt |
| agent | tool, skill, hook, workflow | `agent` of `strict` |
| ingang | precies één workflow of agent | `geen` |
| hook | skill | `geen` |

Elke actie (`ACTIE_TAAK`, `BRONSELECTIE_ACTIES`, `INTAKE_ACTIES`, `REGIE_ACTIES`) is de ingang van precies één
onderdeel. Een commando wijst naar zo'n actie, en dus naar precies één onderdeel.

**Context per agent: alleen de eigen skills en tools.** Zo werkt contextisolatie bij een subagent. De bron blijft het
declaratieve register:
- tools: `Specialist.tools` met `toegestane_tools`;
- skill: de rol in `agentrollen.json`;
- sjablonen: `Specialist.sjablonen`.

De catalogus en de runtime lezen allebei dat register. `test_context_per_agent` vergelijkt wat de runtime per agent
meestuurt (de toolschema's en de methodevingerafdruk, `methode.vingerafdruk`) met de catalogus. Iets wat er buiten de
catalogus om bij komt, wordt rood. De `versie` van een rol ís die vingerafdruk.

**Een skill toevoegen zonder code.** Een methode-skill is een map met:
- `SKILL.md` (met `metadata.lex_*`);
- `agentrollen.json`, met zijn secties per **bestaande** rol;
- een eigen bronregister;
- eventueel regelsets onder `regels/`, in de vorm van een bestaande regelmap en met dezelfde verplichte tests.

De generator bundelt alle skills, dus het image heeft de skillmap niet nodig. Een nieuwe rol of agent vraagt wel code
en een meting (§5, trap 2). Een nep-skill in de test bewijst het, zoals de nep-connector dat voor connectors doet: een
sectie bij `duiding` en een detectorregel komen mee zonder één regel code buiten de map.

## Aansluiting op Claude Code

| Claude Code | Lex | Wat wel en niet |
|---|---|---|
| skill (`SKILL.md`, `references/`, progressive disclosure) | methode = skill, secties per rol | overgenomen; het is hetzelfde bestand |
| subagent (beschrijving, tools, model) | specialist en taakagent met contract | het idee is overgenomen, de vorm niet: het blijft een getypeerd Python-register, omdat de routering in code types en tests nodig heeft |
| plugin (bundel met aan/uit per scope) | methodepakket met aan/uit per straat en per beheerder | overgenomen via het patroon met twee schakelaars van de connectors |
| marketplace | – | niet overgenomen: alles komt uit deze repo en gaat door de poort |
| slash-command | een ingang naar een onderdeel | het commandoregister verwijst naar `Onderdeel.id` en houdt geen eigen lijst bij |
| hook (PreToolUse, Stop) | `controle`: id-herkomst vóór een tool, brongetrouwheid na het antwoord | overgenomen als begrip: deterministisch, op een vast moment, niet uitschakelbaar door het model |
| subagent-contextisolatie | een agent krijgt alleen zijn eigen skills en tools | overgenomen en afgedwongen (`test_context_per_agent`) |

## Waarom niet anders

- **Een overlay in de database, zodat een wijziging direct werkt.** Dat levert twee waarheden op: het image en de database.
  De metingen en de provenance zouden de overlay moeten meetellen. Een fout zou landen zonder poort. Afgewezen door de gebruiker.
- **Specialisten en agents als markdown met frontmatter, zoals Claude Code-subagents.** Dat leest prettig, maar de routering
  en de toollaag hebben types nodig. Het contract hoort bij de code die het nakomt.
- **Een gegenereerd `catalogus.json`.** Dat is nog een bestand dat kan afwijken. Introspectie kan dat niet.

## Gevolgen

- Een nieuw onderdeel zonder beschrijving maakt de poort rood.
- De takenlijst in `SUPERVISOR_SYSTEM` en `_QA_SPECIALISTS` worden afgeleid in plaats van met de hand bijgehouden.
- Acceptatie krijgt een GitHub-token met schrijfrecht op deze ene repo (`WA_GITHUB_PR_TOKEN`), en alleen voor concept-PR's.
- `references/jrm-verrijking.md` gaat op in de skill `wetsuitvoering`, zodat JRM op één plek staat.
