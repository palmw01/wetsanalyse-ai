# Plan: wetsanalyse (JAS) en wetsuitvoering (JRM) zuiver scheiden

Status: plan, 13 november 2026, op master `2be1f804`; de open vragen zijn dezelfde dag beantwoord. Er is nog niets
gewijzigd aan de methodetekst, aan graph-qa, de api of de frontend. Dit document is de inventaris, wat er per vondst
gebeurt, de volgorde en de besluiten. De bouwstappen beginnen na meetronde 4.

**Aanvulling, 13 november 2026 (deel 2, *Wetsanalyse versterken*).** De gebruiker wil dat wetsanalyse met het JAS bij
de scheiding ook inhoudelijk beter wordt neergezet, op basis van de bronnen, en dat de bijbehorende tools van Lex
meegaan. Deel 2 staat onderaan: de toets van de skill en de JAS-tools tegen de bronnen, de voorstellen, de gezamenlijke
volgorde met S1–S6, de metingen en de open vragen. Deel 2 corrigeert één vondst van deel 1 (de sectie `supervisor`,
zie §2). Eén sessie voert beide delen uit.

## Kort

- **Wat de gebruiker zag:** een vraag om een annotatie "volgens JRM" gaat de JAS-annotatieketen in. De annotatieketen,
  de annotatie-UI en de JAS-tools zijn op wetsanalyse gebouwd; een andere methode lift daar nu ongemerkt in mee.
- **De besluiten** (gebruiker, 13 nov 2026):
  1. Alles wat JRM heet of daaruit komt, verhuist naar de skill `wetsuitvoering`. Wetsanalyse houdt de dertien
     JAS-klassen, de relaties daartussen en de begrippen, en heet "Wetsanalyse: JAS".
  2. Zolang wetsuitvoering aan geen rol is gekoppeld, zegt Lex bij een vraag om een annotatie of analyse volgens JRM
     dat hij dat nog niet kan, en dat annoteren alleen volgens het JAS gaat. Hij start de JAS-annotatie niet vanzelf.
     Dat is een regel in code.
  3. De wijziging van de methodetekst komt na meetronde 4, als eigen stap met een eigen meting.
  4. De reikwijdte: de skill, de labels in de app, het analysedossier, de docs, ADR-016 en de werkplaats, en ook de
     tools en workflows. De relatiecatalogus (ADR-011) wordt niet herzien.
  5. Voor de toekomst: elke methode heeft een eigen skill, eigen tools, workflows en profielen, en een eigen
     resultaatvorm. Een nieuwe methode levert eerst tekst in het gesprek of een eigen zijpaneel, nooit JAS-markeringen.
- **De vermenging zit op vier plekken:** in de skill wetsanalyse (één reference, het dossier, de naam), in één zin van de
  methodetekst van de rol `duiding`, in de routering (geen methode in de keuze), en in het ontbreken van een eigenaar per
  tool, workflow en profiel. In de code van graph-qa, de api en de frontend staat het woord JRM nergens buiten wat uit de
  skills is gegenereerd.
- **Zeven PR's**, waarvan één een meting vraagt (de zin in `duiding`). Zie *De volgorde*.
- **De zes vragen uit dit plan zijn beantwoord** (13 nov 2026); de besluiten staan onderaan en zijn in de inventaris
  verwerkt.

## Wat JAS is en wat JRM is

De grens loopt niet langs woorden. Het JAS gebruikt zelf "rechtsgevolg" en "juridische toestand" in de omschrijving van
zijn klassen (een voorwaarde geldt "voor het intreden van een rechtsgevolg"; een rechtsfeit brengt "een wijziging in de
juridische toestand"). Die woorden blijven in wetsanalyse waar de bron van het JAS ze gebruikt.

| Hoort bij wetsanalyse (JAS) | Hoort bij wetsuitvoering (JRM) |
|---|---|
| de dertien klassen, hun herkenningsvragen en fragmentgrenzen | het juridisch scenario en de akte (begintoestand, rechtsfeit, rechtsgevolgen, eindtoestand) |
| de relaties tussen markeringen (ADR-011): rechtsbetrekking met partijen en object, afleidingsregel met invoer en uitvoer, voorwaarde | het rechtsgevolg als eigen, vast te leggen element |
| de begrippen (NL-SBB, activiteit 3a) | het juridisch relevante feit, met type, instantie en waarde |
| het werkgebied en de bronselectie (activiteit 1) | de juridische toestand als model van vóór en na |
| het analysedossier met bronnen, normeenheden, elementen, relaties en interpretaties | de JRM-classificaties en hun verhouding tot het JAS |

## De inventaris

### 1. De skill wetsanalyse

| Vondst | Waar | Wat ermee gebeurt |
|---|---|---|
| Het label "Wetsanalyse: JAS met JRM 2-verrijking" en de omschrijving | `SKILL.md`, frontmatter en de eerste alinea | wordt "Wetsanalyse: JAS"; de omschrijving noemt JRM niet meer. Verandert de catalogus en het bronpakket, geen modeltekst |
| De tabel *Wat ga je doen?*, regel C (samenhang) verwijst naar de JRM-verrijking | `SKILL.md` | verwijst alleen nog naar `relaties.md` |
| "Rechtsgevolgen, juridisch relevante feiten en scenario's leg je vast volgens de JRM-verrijking" | `SKILL.md`, de werkstroom samenhang | vervalt hier; één zin verwijst naar de skill wetsuitvoering voor wie de stap naar uitvoering wil zetten |
| `references/jrm-verrijking.md` | de hele reference (2,9 kB) | **gesplitst.** De rijen rechtsbetrekking, rechtsfeit, afleidingsregel en waarde zijn JAS-inhoud: die gaan naar `relaties.md` of het analyseprotocol, voor zover ze er nog niet staan. De rijen rechtsgevolg, juridisch relevant feit, juridische toestand en scenario gaan naar wetsuitvoering. Het bestand zelf verdwijnt |
| "Verschillen expliciet houden" (immuniteit, zwakke verplichting, rechtshandeling) | `jrm-verrijking.md` | de punten over JAS-duiding (immuniteit niet stilzwijgend verwijderen, geen definitief subtype uit één passage, niet elke handeling is een rechtshandeling) blijven in wetsanalyse, zonder verwijzing naar JRM. De vergelijking met de JRM-werkversie gaat naar wetsuitvoering (`classificaties.md`) |
| Stap 5 "Samenhang en toetsing met scenario's", de identiteiten G (gevolg) en S (scenario), de vier scenario's per beslispunt | `references/analyseprotocol.md` | toetsen met een praktijkvoorbeeld hoort bij de methode Wetsanalyse zelf; het JRM-scenario met aktes niet (besluit 1 onderaan). Wetsanalyse houdt "toetsen met praktijkvoorbeelden" (normaal geval, grensgeval), zonder S- en G-identiteiten; die gaan naar wetsuitvoering |
| "Methode: JAS met JRM 2-verrijking 2.1", §6 Scenario's, de regel over juridisch relevante feiten, de identiteiten G en S | `assets/analysedossier.md` | het dossier van wetsanalyse eindigt bij samenhang en interpretatie. Scenario's en relevante feiten krijgen het sjabloon van wetsuitvoering (`assets/scenario.md` bestaat al) |
| De rij "Scenario's" in de kwaliteitseisen | `references/kwaliteit.md` | wordt "Praktijkvoorbeelden" (besluit 1 onderaan) |
| P07 (JRM-verrijking) en P08 (scenario's en dekking) in het beslisregister; M06 als bron | `references/bronnen.md` | P07 en P08 verhuizen naar het beslisregister van wetsuitvoering. M06 blijft bron van wetsanalyse waar hij een JAS-keuze draagt (besluit 2 onderaan) |
| "Rechtsgevolg en juridisch relevant feit als eigen element … horen bij de JRM-werkversie" | `references/relaties.md` | blijft, als grens: de zin zegt juist dat ze er niet bij horen. De relatiecatalogus zelf blijft ongemoeid (besluit 4) |
| "Een andere methode (zoals wetsuitvoering, JRM) is een eigen map" | `references/platform.md` | blijft, aangevuld met de regel van besluit 5 |

### 2. De methodetekst per rol (`agentrollen.json`, `agentrollen.md`, `methodepakket.py`)

| Vondst | Waar | Wat ermee gebeurt |
|---|---|---|
| De kop "Grammatica, interpretatie en JRM 2" | `agentrollen.md` | de kop staat buiten de markers en gaat niet naar het model; hij wordt "Grammatica en interpretatie" |
| "Beschrijf waar relevant de rechtsbetrekking met partijen, object, relevante feiten, bevoegdheden en rechtsgevolgen volgens JRM 2" | de sectie `duiding`, tussen de markers | **dit is modeltekst.** De zin wordt: de rechtsbetrekking met partijen, object en voorwaarden, volgens het JAS. Dat verandert de vingerafdruk van de rollen `duiding` en `agent` (de centrale agent draagt `duiding` ook) en vraagt een meting |
| De secties `jrm-scenario` en `jrm-relevant-feit` | `wetsuitvoering/agentrollen.json` | blijven waar ze zijn; `"rollen": {}` blijft tot een eigen meting |
| "Beloof geen volledig JAS/JRM-dossier via een route die alleen markeringen of een antwoord levert" | de sectie `supervisor`, tussen de markers | **ook modeltekst** (correctie van 13 nov, deel 2: de eerste versie van dit plan zag deze zin niet). Wordt "geen volledig analysedossier". Verandert de vingerafdruk van de rol `supervisor`; gaat mee in S6 |
| "De dertien JAS-labels blijven ongewijzigd; JRM-verrijking is aanvullende uitleg, geen nieuwe annotatieklasse" | de slotzin van de sectie `duiding`, tussen de markers | modeltekst; vervalt in S6, samen met de andere JRM-zin van `duiding` |
| De andere secties (`basis`, `retrieval`, `definitie`, `deelvragen`, `nl-sbb-taalniveau`) | `agentrollen.md` en de references | noemen JRM niet; ongewijzigd |
| Het JAS_KLASSEN-blok van de classifier en de reviewer | `agent/jas_klassen.py`, uit `jas-klassen-referentie.md` | noemt JRM niet; ongewijzigd. De annotatieketen krijgt dus geen andere tekst |

### 3. De skill wetsuitvoering: wat er staat en wat erbij moet

Wat er al staat (uit de specificatie van BZK, W3C-licentie, in eigen woorden):

- `references/scenario.md`: het juridisch scenario, de akte, het rechtsgevolg, de werkwijze en welke scenario's je kiest;
- `references/relevant-feit.md`: het juridisch relevante feit, type en instantie, bepalend en bepaald, waarde, de stap naar een gegevensmodel;
- `references/classificaties.md`: de JRM-classificaties en hun verhouding tot het JAS;
- `references/voorbeelden.md` en `assets/scenario.md`: een uitgewerkt voorbeeld en het sjabloon.

Wat erbij moet, uit wat nu in wetsanalyse staat:

- **de juridische toestand** als eigen onderwerp (vóór en na, met wat onbekend is): nu alleen impliciet in het scenario;
- **de koppeling met een wetsanalyse**: hoe een scenario verwijst naar bronnen, elementen en relaties uit een
  JAS-dossier (de E-, B- en R-identiteiten), zonder dat het die opnieuw vastlegt;
- **de vier toetsgevallen per beslispunt** (P08), als werkwijze voor het kiezen van scenario's;
- **de verschillen tussen de JAS-indeling en de JRM-werkversie** (de drie hoofdgroepen tegenover immuniteit);
- **de projectkeuzes P07 en P08** in het eigen beslisregister.

**Let op de bron.** De verrijking in wetsanalyse rust op de werkversie van Bulles en Van der Hoven (M06); de skill
wetsuitvoering rust op de specificatie van BZK. Wat uit M06 komt, krijgt in wetsuitvoering een eigen regel in het
bronregister en wordt in eigen woorden geschreven: er gaat geen tekst van derden letterlijk mee. Waar M06 en de
BZK-specificatie verschillen, gaat de specificatie voor; M06 vult aan waar ze zwijgt (besluit 3 onderaan).

### 4. De routering

| Vondst | Waar | Wat ermee gebeurt |
|---|---|---|
| "Annoteer artikel 9 volgens JRM" kiest de annotatieketen | de supervisor kiest de worker op het werkwoord; de aanwijzing (`agent/aanwijzing.py`) leest alleen het artikel. Nergens telt de genoemde methode | **een regel in code, vóór het model**, voor beide vormen (supervisor en centrale agent): noemt een verzoek om te annoteren, markeren of analyseren een methode die aan geen rol is gekoppeld (JRM, juridisch referentiemodel, wetsuitvoering, scenario, akte), dan antwoordt Lex met een vaste zin en start hij niets. De zin zegt wat wel kan: annoteren volgens het JAS, en de wettekst lezen en uitleggen |
| De sectie `supervisor`: "markeringen vragen de annotatieketen" | modeltekst | ongewijzigd: de regel in code gaat ervoor |
| De acties van de werkplek (`werkgebied_annoteren`, `deelvragen_annoteren`, de keuzekaart) | `ACTIE_TAAK`, de reeks | ongewijzigd: een klik vraagt altijd de JAS-keten, en zegt geen methode |
| Welke methodes "gekoppeld" zijn | nu nergens vastgelegd | afgeleid uit de skills: een methode is gekoppeld als haar `agentrollen.json` een rol noemt. De regel leest dat, zodat ze vanzelf vervalt als wetsuitvoering een rol krijgt |

### 5. Tools, workflows, routes, profielen en sjablonen: van wie zijn ze

De catalogus (ADR-014) kent per onderdeel een soort en een concept, maar geen methode. Het voorstel: elk onderdeel
krijgt een afgeleid veld `methode`: de naam van één methode-skill, of uitdrukkelijk `neutraal`.

| Van wetsanalyse (JAS) | Methode-neutraal |
|---|---|
| de annotatieketen (ADR-001) met haar detectoren, regelsets, classifier en reviewer | de graaftools: zoeken, lezen, opbouw, verwijzingen, geldigheid, grondslagen |
| de annotatie-worker, de reeks en het annoteren van een werkgebied | de bronconnectors (ADR-013) |
| de annotatieleestools (`search_annotaties`, `get_annotatie`, `overzicht_annotaties`, de dekking) en de leesroute | de overzichtsroute en de bepalingsroute |
| de JAS-tools (`JAS_TOOLS`) en de relatiecatalogus | de antwoordsjablonen voor wettekst, duiding, definitie en bronnen naast de wet |
| de annotatie-UI: het paneel, de reviewlijst, de markeerlaag, de exports | de controles: brongetrouwheid, herkomst van een id, feiten zonder bron |
| de begrippenketen, de begrippen-agent en het begrippenkader (activiteit 3a) | de contextweergave, het tokenbudget, de gesprekken |
| het sjabloonblok `annotaties` en `antwoord_annotaties`; het profiel `annotaties_lezen` | de regisseur (hij verdeelt werk; wát hij verdeelt, is van een methode) |
| de vraag over een markering (*Vraag Lex* bij een element) | |
| het werkgebied, de deelvragen en de bronselectie (activiteit 1); delen bekijken we pas als wetsuitvoering gekoppeld wordt (besluit 4 onderaan) | |

De profielen `definitie`, `duiding`, `algemeen`, `centraal` en `centraal_breed` beantwoorden vragen over wetgeving en
dragen daarbij de methodetekst van wetsanalyse. Ze zijn van wetsanalyse zolang er één methode gekoppeld is; een tweede
methode krijgt eigen profielen (besluit 5), geen extra secties in deze.

### 6. De labels in de frontend

- De frontend draagt de naam van de methode niet zelf: *Werkwijze van Lex* toont `lex_label` uit de skill. Met de
  wijziging van het label in de skill is de app bij.
- In de code van de frontend staat "JRM" alleen als voorbeeldnaam in tests en in de placeholder van *Nieuw concept*
  ("bijvoorbeeld jrm-scenario"). Dat mag blijven: een concept voor wetsuitvoering is precies waar de werkplaats voor is.
- "Rechtsgevolg" in `lib/annotatie.ts` (de vragen bij een markering) en in de verklaringen van de detectoren is
  JAS-taal en blijft.

### 7. De docs en de CLAUDE.md's

| Vondst | Waar | Wat ermee gebeurt |
|---|---|---|
| "de JAS-methode met JRM 2-verrijking", "de JRM 2-verrijking" | root `CLAUDE.md` (§*Wat dit project is*, §*De wetsanalyse-skill*) | wordt "de JAS-methode"; de alinea over de tweede skill krijgt de regel van besluit 5 |
| `references/jrm-verrijking.md` in de lijst van references | root `CLAUDE.md` | uit de lijst |
| De scope "activiteit 2, en het begin van activiteit 3" | root `CLAUDE.md` | ongewijzigd |
| ADR-001 en ADR-011 noemen JRM als achtergrond | `docs/architectuur/` | ongewijzigd: het zijn besluiten van toen; ADR-011 wordt niet herzien |
| Het voorbeelddossier noemt de methode "JAS met JRM 2-verrijking" | `docs/wetsanalyse/referentieset/voorbeeld-dossier-rvv74.md` | blijft staan als bewijs van toen, met een regel erboven dat de methode sindsdien gesplitst is (besluit 5 onderaan) |
| `docs/wetsanalyse/methode-onderzoek.md`, de eisenmatrix, het verbeterplan van oktober | onderzoek | ongewijzigd: onderzoek mag verouderen (`docs/README.md`) |
| De briefing van het acceptatieteam noemt JRM | `docs/acceptatie/briefing-team.md` | nalopen bij de wijziging van de skill |

## De regel voor de toekomst (besluit 5)

Deze regel staat nu in ADR-016 (deel B) en ADR-014 (§5):

- Elke methode heeft een eigen skill, eigen tools, workflows en profielen, en een eigen resultaatvorm.
- De annotatieketen, de annotatie-UI en de JAS-tools zijn van wetsanalyse. Een skill of profiel van een andere methode
  krijgt er geen toegang toe: niet via een rol, niet via een tool in een profiel, niet via een route.
- Een nieuwe methode levert eerst tekst in het gesprek, of een eigen zijpaneel. Nooit JAS-markeringen.
- Een verzoek dat een methode noemt die aan geen rol is gekoppeld, krijgt een eerlijk antwoord uit code, geen werk
  volgens een andere methode.

## Tests die vermenging voortaan rood maken

1. **Geen JRM in wetsanalyse.** De skill wetsanalyse en de methodetekst van haar secties bevatten de naam "JRM" niet,
   en ook niet "juridisch relevant feit", "juridisch scenario" of "akte" als vastlegging. Uitzondering, met een lijst
   in de test: de ene zin die naar de skill wetsuitvoering verwijst, en de grenszin in `relaties.md`. Woorden die het
   JAS zelf gebruikt ("rechtsgevolg", "juridische toestand") vallen er niet onder.
2. **Een sectie is van één skill** (bestaat al: `bronmodel.skill.toets_samen`), en **een rol krijgt secties van één
   methode**, tenzij de rol `agent` is. Zo kan een tweede skill zich niet aan de rol van de classifier hangen.
3. **Elk onderdeel van de catalogus heeft een methode**: precies één methode-skill, of `neutraal`. De test vergelijkt
   het met een vaste lijst voor de onderdelen van de annotatieketen, zodat die niet stil neutraal worden.
4. **Een profiel van een andere methode noemt geen JAS-tool.** De grenzen van een agentprofiel
   (`bronmodel.agentprofiel`) weigeren een annotatieleestool of een annotatie-actie in een profiel waarvan de methoderol
   niet van wetsanalyse is. Dat geldt ook voor een concept in de werkplaats (poort 1).
5. **De regel in code**: de vragen "annoteer artikel 9 Iw volgens JRM", "maak een analyse volgens het juridisch
   referentiemodel" en "werk dit uit als scenario met aktes" starten geen annotatie en geen model. En de
   tegenvoorbeelden: "annoteer artikel 9 Iw", "wat is het rechtsgevolg van artikel 9?" en "wat zegt het JRM over een
   rechtsfeit?" (een vraag óver de methode) lopen zoals nu. De routerings- en gespreksset mogen er niet in vallen.

## De volgorde

| PR | Wat | Raakt | Meting |
|---|---|---|---|
| **S0** | dit plan, en de regel in ADR-016 en ADR-014 | docs | nee |
| **S1** | de regel in code: een verzoek volgens een niet-gekoppelde methode krijgt een vaste zin, voor beide vormen; test 5 | graph-qa | nee: geen modeltekst. De routerings- en gespreksset bewaken dat geen gewone vraag erin valt |
| **S2** | het veld `methode` op elk onderdeel van de catalogus, afgeleid; in *Werkwijze van Lex* te zien; test 3 | bronmodel, graph-qa, frontend | nee |
| **S3** | de grenzen: een rol krijgt secties van één methode, een profiel van een andere methode noemt geen JAS-tool; tests 2 en 4 | bronmodel, api (poort 1) | nee |
| **S4** | de skill wetsuitvoering aanvullen (de vijf punten van §3), met `"rollen": {}` | skill, bronpakket | nee: aan geen rol gekoppeld. De evals van de skill gaan mee |
| **S5** | de skill wetsanalyse opschonen buiten de markers: het label, `SKILL.md`, `jrm-verrijking.md` weg, het analyseprotocol, het dossier, de kwaliteitseisen, het bronregister; test 1 voor alles buiten de markers; de CLAUDE.md's en de briefing | skill, bronpakket, docs | nee: de methodetekst per rol blijft byte-gelijk, en de test op de vingerafdrukken bewijst dat |
| **S6** | de zin in de sectie `duiding`; test 1 voor de methodetekst | skill, methodepakket | **ja**, zie hieronder |

S1 kan meteen na meetronde 4. S2 tot en met S5 volgen elkaar op en kunnen zonder meting. S6 is in deel 1 de enige
wijziging van modeltekst en komt in een eigen PR. De gezamenlijke volgorde met de stappen van deel 2 (W en G) staat in
*Deel 2, De volgorde samen met S1–S6*.

### De meting bij S6

De zinnen staan in de secties `duiding` (twee zinnen) en `supervisor` (één zin, zie de correctie in §2). `duiding` gaat
naar de rol `duiding` en naar de rol `agent` (de centrale agent); `supervisor` naar de rol `supervisor`. De meting krijgt
daarom ook de routeringsset (`golden_routering`).

- **Wat verandert:** de vingerafdruk van `duiding` en `agent`, en daarmee het voorvoegsel van die twee (één keer koud).
- **Wat niet verandert:** de annotatieketen. De classifier en de reviewer krijgen het JAS_KLASSEN-blok, en dat noemt
  JRM niet. Er komt geen meting van de annotatie; de test op de vingerafdrukken volstaat (besluit 6 onderaan).
- **De meting** (ADR-010, P19): de kwaliteitsset en `golden_gesprek`, voor en na, drie runs, in beide vormen; de
  vragen van het type duiding apart. De drempels: brongetrouw gelijk, niet slechter, niet duurder (gewogen).
- **Waar ik op let:** of het antwoord op een duidingsvraag nog de partijen en het object van een rechtsbetrekking
  noemt, en of het geen rechtsgevolg meer toevoegt dat de tekst niet draagt.

## Wat ik niet doe

- De relatiecatalogus (ADR-011) herzien.
- Wetsuitvoering aan een rol koppelen: dat is een eigen stap met een eigen meting (ADR-010, ADR-014 §7).
- Een resultaatvorm voor wetsuitvoering bouwen (een scenario-paneel): dat volgt als de methode gekoppeld wordt.

## Besluiten op de zes vragen (13 nov 2026)

De vragen uit de eerste versie van dit plan zijn beantwoord; de eerste vier door de gebruiker, de laatste twee door de
hoofdsessie, telkens volgens het voorstel.

1. **Toetsen met een praktijkvoorbeeld blijft in wetsanalyse.** Een normaal geval en een grensgeval, zonder aktes en
   toestanden en zonder S- en G-identiteiten. Alleen het JRM-scenario verhuist naar wetsuitvoering.
2. **M06 (Bulles en Van der Hoven) blijft bron in wetsanalyse** waar hij een JAS-keuze onderbouwt. Alleen de
   projectkeuzes P07 en P08 verhuizen.
3. **In wetsuitvoering gaat de specificatie van BZK voor.** M06 vult aan waar de specificatie zwijgt, in eigen woorden en
   met een eigen regel in het bronregister.
4. **Het werkgebied, de deelvragen en de bronselectie zijn nu van wetsanalyse.** Of ze gedeeld worden, bekijken we pas
   als wetsuitvoering aan een rol gekoppeld wordt.
5. **De referentieset blijft staan als bewijs van toen**, met een regel erboven dat de methode sindsdien gesplitst is.
6. **Geen meting van de annotatie bij S6.** De test op de vingerafdrukken bewijst dat de annotatieketen dezelfde tekst
   krijgt.

---

# Deel 2: Wetsanalyse versterken

Status: plan, 13 november 2026. Er is niets gebouwd. Dit deel toetst de skill `.claude/skills/wetsanalyse/` en de
JAS-tools van Lex tegen de bronnen van de methode, en zegt per bevinding wat het voorstel is en wat het raakt.

## Kort

- **De skill volgt de Rijksspecificatie goed, en het boek en de Handleiding maar half.** De drie bronvelden per klasse
  (omschrijving, vraag, uitdrukkingswijze) staan er volledig. Wat het boek daarnaast per klasse geeft, ontbreekt: de
  subklassen van de rechtsbetrekking en het rechtsfeit, de samenhang met andere klassen, en de specialisatie. De
  markeerregels van de Handleiding staan er voor een deel.
- **Een deel van wat nu "JRM-verrijking" heet, is JAS.** Immuniteit, de zwakke verplichting en de rechtshandeling komen
  uit hoofdstuk 4 van het boek. Ze staan in de skill onder een JRM-kop. Bij de scheiding horen ze in de
  klassenreferentie, met hun eigen bron.
- **De methode Wetsanalyse kent zelf juridische scenario's.** Het boek (stap 4) en de Handleiding (deelactiviteiten 1c,
  1e en 4a) gebruiken ze, de Handleiding met begintoestand, rechtsfeit, rechtsgevolgen en eindtoestand. Besluit 1 legt
  het scenario bij wetsuitvoering. Dat kan, maar de skill moet dan zeggen waar de methode het scenario gebruikt en
  waar je het uitwerkt (besluit 1 van deel 2).
- **De modeltekst noemt JRM op drie plekken, niet op één.** Twee zinnen in `duiding` en één in `supervisor`. S6 wordt
  daardoor iets breder (zie §2 van deel 1).
- **Tien stappen erbij:** zeven zonder gedragswijziging (W1–W7: leestekst, bronregister, evals, tests) en drie met
  (G1–G3), elk met een eigen meting. Aan de drie bronvelden van de klassen verandert niets: de annotatieketen krijgt
  dezelfde klasseduiding.
- **De zeven vragen** onderaan zijn beantwoord (13 nov 2026): alle voorstellen zijn overgenomen.

## Wat ik heb getoetst

Gelezen en vergeleken:

- de hele skill wetsanalyse: `SKILL.md`, alle `references/`, `agentrollen.json`, `relaties.json`, `evals/`, `assets/`;
- de skill wetsuitvoering, voor de grens;
- M04, de Rijksspecificatie: `docs/wetsanalyse/wetsanalyse-rijk/` (H1, H2-JAS, H3);
- M01, het boek: hoofdstuk 3 (de stappen, vooral 1 tot en met 4) en hoofdstuk 4 (het analyseschema, alle klassen);
- M02, de Handleiding 1.0: §3.3 (activiteit 1, deelactiviteiten a–g), §3.4 (activiteit 2) en §3.6 (activiteit 4);
- de JAS-tools van Lex: de annotatieketen (`agent/jas_pipeline/`: systeemprompt van de classifier, de dertien
  klasseprofielen, de detectoren, de subtypen), `jas_klasse_opvragen`, de begrippentoetsen
  (`agent/begrippen_pipeline/toetsen.py`) en `docs/architectuur/annotatieketen.md`.

Niet opnieuw getoetst, en dat zeg ik erbij: de Leidraad (M03; P13 steunt erop), WetsTaal (M05) en de
begrippenregels in code tegen NL-SBB. Die toets hoort bij de stap die ze raakt (W5, W6) en komt in die PR.

Het boek en de readers staan niet in deze repo. Alles hieronder is in eigen woorden, met bron en sectie.

## Bevindingen per activiteit

Elke bevinding heeft vier regels: wat de bron zegt, wat de skill nu zegt, het voorstel, en wat het raakt. *Leestekst*
betekent: alleen tekst die het platform niet laadt. *Gedrag* betekent: modeltekst, een tool of een toets van Lex.

### Activiteit 1: het werkgebied

**B1. Juridische scenario's horen in de methode bij activiteit 1.**
- Bron: M02 §3.3.2, deelactiviteiten 1c en 1e. Een praktijkvoorbeeld wordt een juridisch scenario: één pad van één
  burger of bedrijf, met de juridische gebeurtenissen op volgorde, te beginnen met het meest gangbare geval. De
  deelvragen worden aan die gebeurtenissen verbonden. De volgorde van 1b–1c en 1d mag wisselen.
- Skill: het praktijkvoorbeeld en de gebeurtenis staan erin; het scenario niet. P13 zegt dat 1c en 1e "nog niet"
  gedaan worden.
- Voorstel (besluit 1 van deel 2): `werkgebied.md` zegt dat de methode hier een scenario kent, en waar
  je het uitwerkt.
- Raakt: leestekst (W6).

**B2. Meer dan één praktijkvoorbeeld, van gangbaar naar zeldzaam.**
- Bron: M02 §3.3.2, deelactiviteit 1b. Minstens één gangbaar voorbeeld; meer voorbeelden scherpen de afbakening aan.
- Skill: één praktijkvoorbeeld, en de regel dat je het niet verzint.
- Voorstel: `werkgebied.md` noemt de volgorde gangbaar → minder gangbaar en zegt wat een tweede voorbeeld oplevert.
- Raakt: leestekst (W6). De vraagkaarten van Lex blijven zoals ze zijn.

**B3. Delegatie en wetstechnische informatie bepalen het werkgebied.**
- Bron: M01 h.3 stap 1 en h.4 §14–15; M04 H2:125. Gedelegeerde regelgeving die gebruikt is, hoort in het werkgebied;
  de wetstechnische informatie bij een artikel helpt, maar is niet volledig.
- Skill: staat in de klassenreferentie (§12) en in `verwijzingen-volgen.md`, niet in `werkgebied.md`.
- Voorstel: één zin in `werkgebied.md` bij het zoekbereik, met de verwijzing.
- Raakt: leestekst (W6).

### Activiteit 2a: markeren

**B4. De markeerregels van de Handleiding staan er maar voor een deel.**
- Bron: M02 §3.4.2, deelactiviteit a. Je neemt het lidwoord mee (dan kun je nalopen of alle tekst behandeld is); je
  neemt een verwijzing in de formulering mee; een variabele markeer je zonder werkwoord en zonder voorwaarden; een
  afleidingsregel juist met werkwoord, voorwaarden, verwijzing en punt; een voorwaarde bij voorkeur als hele zin of
  zinsdeel; je begint waar het element ontstaat of wordt afgeleid, en herkent het daarna elders; een concreet
  voorbeeld helpt de grens te kiezen.
- Skill: `markeren-fragmentgrenzen.md` noemt het lidwoord en het zinseinde, en geeft per functie een controle. De
  verwijzing, de variabele zonder werkwoord, het beginpunt en het voorbeeld als hulpmiddel ontbreken.
- Voorstel: de tabel *Grenzen kiezen* per klasse aanvullen met deze regels, elk met de bron erbij.
- Raakt: leestekst (W3). De detectoren kiezen hun grenzen in code; of die hiermee stroken, is bevinding T4.

**B5. Je markeert wat aan een centrale klasse hangt.**
- Bron: M02 §3.4.2, deelactiviteit c en *Iteraties*. De analyse loopt per gebeurtenis: je werkt een centrale klasse
  uit en neemt mee wat ermee samenhangt. Dat voorkomt losse markeringen zonder verband.
- Skill: de werkstroom B gaat per normeenheid en eindigt met een dekkingscontrole. "Markeer niet alles om dekking te
  halen" staat er, het positieve criterium niet.
- Voorstel: in werkstroom B en in de markeringslijst het criterium toevoegen: een markering hoort bij een centrale
  klasse of is er zelf een; wat nergens aan hangt, verantwoord je in de dekking.
- Raakt: leestekst (W3).

### Activiteit 2b: classificeren, per klasse

De drie bronvelden staan volledig en letterlijk in `jas-klassen-referentie.md`. Daar verandert niets aan. De
bevindingen gaan over wat het boek er per klasse naast zet (M01 h.4, per klasse de onderdelen *Subklassen*, *Relatie
met eigen klasse* en *Relatie met andere klassen*) en wat de skill daarvan mist.

**B6. Rechtsbetrekking: de subklassen ontbreken.**
- Bron: M01 h.4 §3, *Subklassen*. Vier soorten, naar Hohfeld: aanspraak tegenover verplichting (met drie varianten,
  naar wat er bij niet-nakomen kan), bevoegdheid tegenover gehoudenheid (discretionair of gebonden), immuniteit
  tegenover geen bevoegdheid, en vrijheid tegenover geen aanspraak. M01 h.4 §4.2.2 geeft de herkenning: een gebonden
  bevoegdheid staat in de tegenwoordige tijd, een discretionaire aan "kan" of "naar zijn oordeel". Het boek waarschuwt
  dat een immuniteit moeilijk te onderscheiden is van een bevoegdheid onder een voorwaarde.
- Skill: de klassenreferentie noemt ze niet. `jrm-verrijking.md` noemt immuniteit en de zwakke verplichting, onder een
  JRM-kop. `SKILL.md` zegt alleen dat "kan" niet vanzelf een bevoegdheid is.
- Voorstel: een onderdeel *Subklassen* bij §3 van de klassenreferentie, in eigen woorden, met de herkenning en de
  waarschuwingen. De regel blijft: een subklasse noem je alleen als de tekst haar draagt.
- Raakt: leestekst (W2). De generator leest alleen de drie bronvelden; `agent/jas_klassen.py` blijft byte-gelijk, en
  de drifttest bewijst dat. Of Lex de subklasse ook noemt of vastlegt, is G1 en vraag 2.

**B7. Rechtsfeit: de vier soorten ontbreken.**
- Bron: M01 h.4 §4, *Subklassen*: rechtshandeling, feitelijke handeling met rechtsgevolg, gebeurtenis met
  rechtsgevolg, tijdsverloop met rechtsgevolg. En *Relatie met andere klassen*: een rechtsfeit werkt altijd op een
  rechtsbetrekking, heeft een voorwerp, en is aan een tijdstip of periode gekoppeld.
- Skill: de omschrijving noemt handeling, gebeurtenis en tijdsverloop; de rechtshandeling staat alleen in
  `jrm-verrijking.md`.
- Voorstel: een onderdeel *Subklassen* bij §4, en de drie vaste verbanden als controle.
- Raakt: leestekst (W2).

**B8. Rechtssubject en rechtsobject: specialisatie.**
- Bron: M01 h.4 §1 en §2, *Relatie met eigen klasse*. Een subject of object kan een specialisatie van een ander zijn;
  eigenschappen, betrekkingen en feiten van het algemene gelden ook voor het bijzondere. M01 h.4 §6: een
  afleidingsregel kan zo'n specialisatie afleiden ("wordt beschouwd als").
- Skill: het woord staat in het bronveld van de afleidingsregel. `relaties.md` zet specialisatie bij activiteit 3.
- Voorstel: bij §1, §2 en §6 uitleggen wat specialisatie is en hoe je haar herkent; `relaties.md` zegt waarom ze
  geen relatietype is (ADR-011 wordt niet herzien) en waar ze dan wel landt: in de toelichting, en later als
  begripsrelatie *soort van*.
- Raakt: leestekst (W2, W4).

**B9. Per klasse de samenhang met andere klassen.**
- Bron: M01 h.4, per klasse *Relatie met andere klassen*. Voorbeelden: een rechtsbetrekking heeft altijd twee
  partijen en een voorwerp, en vaak een duur; een tijds- of plaatsaanduiding neemt de verbanden over van de klasse die
  zij verbijzondert; een brondefinitie hoort bij een term voor een subject, object, variabele of parameter.
- Skill: `relaties.md` vat de verbanden samen vanuit de catalogus. Per klasse staat het niet in de referentie.
- Voorstel: een kort onderdeel *Samenhang* per klasse, dat naar het relatietype in de catalogus wijst. Eén afwijking
  benoemen: de catalogus staat `definieert` ook toe naar een betrekking, feit, tijd of plaats; dat is ruimer dan het
  boek en blijft een projectkeuze (P18).
- Raakt: leestekst (W2).

**B10. De afbakening tussen klassen staat in de code en niet in de skill.**
- Bron: de dertien klasseprofielen van de annotatieketen (`jas_pipeline/profielen/*.yaml`, `confusable_classes` en
  `negative_patterns`), elk met een verwijzing naar H2 of een projectregel.
- Skill: één onderscheid (rechtsbetrekking tegenover rechtsfeit), de samenloop van operator en afleidingsregel, en de
  voorrang van tijd en plaats. Rechtsfeit tegenover voorwaarde of tijdsaanduiding, rechtsbetrekking tegenover
  afleidingsregel of delegatie en subject tegenover object staan er niet.
- Voorstel: een onderdeel *Afbakening* per klasse in de referentie, met dezelfde paren als de profielen. Een test eist
  dat elk paar uit een profiel in de referentie staat, zodat skill en keten niet uiteenlopen.
- Raakt: leestekst en een test (W2). Geen gedrag: de profielen veranderen niet.

**B11. Voorwaarde, parameter en delegatie: details uit het boek.**
- Bron: M01 h.4 §5 (ook "in elk geval" en "ten minste" zeggen iets over cumulatie, en "ten minste" kan een
  niet-uitputtende lijst zijn die elders is ingevuld), §9–10 (de eenheid hoort bij de parameter; een parameterwaarde
  kan voorkomen zonder dat de parameter is uitgedrukt), §14–15 (een delegatie kan ook als "het door Onze Minister
  vastgestelde bedrag" staan; een invulling herken je aan de verwijzing terug naar de grondslag).
- Skill: de opsomming met "ten minste" staat in `markeren-fragmentgrenzen.md`; de rest ontbreekt.
- Voorstel: aanvullen in de referentie, buiten de drie bronvelden.
- Raakt: leestekst (W2).

**B12. De versie-aanduiding "JAS 1.0.10" heeft geen bron in het register.**
- Bron: `jas_pipeline/keten.py` en de systeemprompts van classifier en reviewer noemen die versie. `bronnen.md` (M04)
  noemt een commit en een datum, geen versienummer.
- Voorstel: in W1 uitzoeken waar het nummer vandaan komt en het in M04 en het manifest vastleggen. De prompt blijft
  zoals hij is.
- Raakt: leestekst (W1).

### Activiteit 2c: samenhang

**B13. De partij die de tekst niet noemt.**
- Bron: M01 h.4 §4.2.2 (*Rechten en plichten*) en §4.3.1. De wet noemt vaak één partij; de andere moet expliciet
  gemaakt worden om de rechtsbetrekking te duiden. Het boek noemt dat de dieptestructuur naast de oppervlaktestructuur.
- Skill: vooral een verbod. "Verzin geen wederpartij", "vul geen partij in", en in het voorbeeld "noteer impliciet,
  niet in deze bepaling". `relaties.md` zegt het zorgvuldiger: eerst koppelen aan een plek waar de partij wel staat.
- Voorstel: de regel omdraaien zonder hem losser te maken. Je benoemt de wederpartij als interpretatie, met de
  bepaling waaruit zij volgt; je citeert haar nooit en je raadt niet. In de annotatie blijft gelden wat ADR-011 zegt:
  alleen de jurist legt een impliciete partij vast.
- Raakt: leestekst (W4), en de modeltekst van `duiding` (G1) als Lex het ook zo moet doen. Dit is vraag 3.

**B14. Het diagram rond een centrale klasse is een product van activiteit 2.**
- Bron: M02 §3.4.2, deelactiviteit c. Het diagram toont de brontekst, de markeringen met hun klasse en de verbanden,
  en is een tussenresultaat dat later door een diagram van begrippen vervangen kan worden.
- Skill: `relaties.md` noemt het diagram; het dossier heeft een relatietabel en noemt een diagram "aanvullend".
- Voorstel: in `relaties.md` zeggen wat het diagram minimaal toont, en per centrale klasse welke verbanden je naloopt
  (uit B7 en B9). Geen nieuw type in de catalogus.
- Raakt: leestekst (W4).

**B15. De afleidingshiërarchie.**
- Bron: M01 h.4 §6, *Afleidingshiërarchie*: een regel kan de uitkomst van een andere regel nodig hebben.
- Skill: `relaties.md` zet verbanden tussen regels bij activiteit 3b.
- Voorstel: het verband noemen als iets wat je bij 2c signaleert (de invoer van deze regel is de uitvoer van een
  andere bepaling) en bij 3b uitwerkt. De catalogus blijft gelijk: de relatie `invoer` mag al naar een andere bepaling
  wijzen.
- Raakt: leestekst (W4).

### Activiteit 3a: begrippen

**B16. De richtlijnen voor de naam en de omschrijving van een begrip.**
- Bron: M01 h.3 stap 3a. Onder meer: sluit aan bij de woorden van de wet; begin met het kernwoord; geen ontkenning in
  de naam; de omschrijving moet het begrip in een zin kunnen vervangen; gebruik eerder vastgelegde begrippen opnieuw;
  zo min mogelijk afkortingen; een afleiding krijgt een eigen begrip ("bepalen …"); één formulering met meer
  betekenissen levert meer begrippen op, en verschillende formuleringen met één betekenis één begrip.
- Skill: `begrippen.md` heeft de kern (geen eigen naam als soortbegrip, geen rekenregel, het doel, de herkomst). De
  vervangtoets, de ontkenning, het kernwoord, het hergebruik en de afkortingen ontbreken.
- Voorstel: `begrippen.md` aanvullen met een lijst *Naam* en een lijst *Omschrijving*, elk met de bron.
- Raakt: leestekst (W5); `begrippen.md` is geen modeltekst. Twee van deze regels zijn in code te toetsen: zie T5.

**B17. Een voorbeeld bij een begrip heeft een vaste vorm.**
- Bron: M01 h.3 stap 3a en stap 4a. Het begrip vooraan, dan het subject met een verzonnen naam, dan het tijdvak, dan
  de waarde. Een grensgeval hoort erbij: het toetst of iedereen het begrip hetzelfde leest.
- Skill: voorbeelden toetsen een definitie, met een grensgeval; de vorm staat er niet.
- Voorstel: de vorm opnemen, met een eigen voorbeeld.
- Raakt: leestekst (W5).

**B18. Het begrip en zijn klasse.**
- Bron: M01 h.3 stap 3a: bij een begrip leg je onder meer de soort vast, en een verdieping van de klasse (het type
  rechtsbetrekking of rechtsfeit).
- Skill: "een begripstype of JAS-duiding stel je niet voor" (het slanke NL-SBB-begrip, ADR-003).
- Voorstel: de afwijking van de bron uitdrukkelijk als projectkeuze vastleggen in P15, met de reden. Of het anders
  moet, is vraag 6.
- Raakt: leestekst (W1).

### Valideren en het dossier (activiteit 4 en 5)

**B19. De methode kent drie manieren van valideren; de skill noemt er één.**
- Bron: M01 h.3 stap 4 (een review door de disciplines, concrete voorbeelden, juridische scenario's) en M02 §3.6.2
  (afleidingsregels toetsen met de scenario's; voorbeeldreeksen: alle varianten van de invoer met de verwachte
  uitkomst, ook nul, negatief en onbekend, en per uitkomst de vraag of zij juridisch juist is).
- Skill: stap 5 van het analyseprotocol draait "vier scenario's per beslispunt" en heet een projectkeuze (P08).
- Voorstel: stap 5 wordt *Toetsen*: de review, het voorbeeld bij een begrip, en de voorbeeldreeks bij een
  afleidingsregel. De vier gevallen van P08 blijven als hulpmiddel om een reeks te vullen (normaal, voorwaarde niet
  vervuld, uitzondering, grens), nu met de bron erbij. Het scenario volgt vraag 1.
- Raakt: leestekst (W6). Het sluit aan op besluit 1 van deel 1.

**B20. Ontbrekend uitvoeringsbeleid signaleren is een eigen stap.**
- Bron: M01 h.3 stap 5; M02 §3.7. Waar de analyse een interpretatie of invulling nodig heeft die nergens is
  vastgelegd, meld je dat, zodat het beleid er komt.
- Skill: "een open norm krijgt geen verzonnen drempel", en open punten met een reviewvraag.
- Voorstel: in het dossier een eigen soort open punt: *ontbrekend beleid*, met de norm, de keuze die nodig is en wie
  haar maakt.
- Raakt: leestekst (W6).

**B21. Rechtspraak naast de gangbare uitleg.**
- Bron: M01 h.3 stap 3d. Rechtspraak die de gangbare uitleg bevestigt, noem je als onderbouwing; rechtspraak die
  afwijkt, neem je niet zomaar over: eerst een standpunt van wie over de regeling gaat.
- Skill: "geen automatische regel dat beleid voor rechtspraak gaat".
- Voorstel: de twee gevallen noemen in `verwijzingen-volgen.md`, als open punt met een reviewvraag.
- Raakt: leestekst (W6).

## Bevindingen over de opbouw van de skill

**O1. JRM zit op meer plekken dan het woord.** Naast de vondsten van deel 1: de G-identiteit ("gebeurtenis of
rechtsgevolg") in het protocol en het dossier; de kolom *Ontstaat/wijzigt/eindigt* in §4 van het dossier, die een
rechtsgevolg als eigen rij vastlegt; "het gevolg voor de scenario's" in de tabel Interpretaties; "werk terug als een
scenario een tegenspraak blootlegt" in `SKILL.md`; en de zin in `relaties.json` onder `buiten_activiteit_2`. Dat een
rechtsfeit een rechtsbetrekking creëert, wijzigt of beëindigt, is JAS (H2:53) en blijft: als relatie, niet als eigen
element. Gaat mee in S5.

**O2. Het bronregister dekt niet elke methodestap.** `relaties.md`, `begrippen.md` en `werkgebied.md` noemen hun
grondslag; `analyseprotocol.md` §2 en §3 doen dat met een P-regel die naar "M01 h.3" of "M01 h.7" wijst zonder
paragraaf. Voorstel (W1): elke reference begint met een regel *Grondslag*; elke P-regel noemt bron en paragraaf, of
zegt "projectkeuze"; en een test eist dat. Dat maakt "volgt de bronnen aantoonbaar" toetsbaar.

**O3. Namen lopen uiteen.** Het bestand heet `annotatieprotocol.md`, de tekst noemt het de markeringslijst. Voorstel
(W3): hernoemen naar `markeringslijst.md`. Het staat niet in de lijst van vaste bestandsnamen in `platform.md`.

**O4. De evals dekken twee van de vijf werkstromen.** Er zijn er drie: werkgebied, markeren, en klassen bij een
delegatie. Voorstel (W7): erbij een geval voor samenhang (relaties leggen, met een partij die de tekst niet noemt),
voor een begrip (een definitie met herkomst), voor het dossier, en twee grensgevallen: een verzoek om een scenario
(de skill verwijst door naar wetsuitvoering en maakt geen JAS-markeringen) en een vraag die geen wetsanalyse is.

**O5. De voorbeelden tonen één soort bepaling.** Beide komen uit artikel 9 Invorderingswet en gaan over een toestand
en een uitzondering. Voorstel (W7): een derde voorbeeld met een rechtsbetrekking waarvan de wederpartij niet genoemd
is, en een vierde met een afleidingsregel (invoer, bewerking, uitvoer). Uit andere bepalingen dan de evals.

**O6. De router en de omschrijving.** `SKILL.md` is 12 kB en volgt de eisen: werkstromen met checklists, verwijzingen
één niveau diep, references met een inhoudsopgave. Na S5 noemt de omschrijving JRM niet meer; ze noemt dan wel wanneer
de skill níét past (een scenario, de stap naar gegevens), zodat Claude de goede skill kiest.

## Bevindingen over de tools van Lex

De gebruiker vroeg de bijbehorende tools mee te nemen. Dit zijn de tools die van wetsanalyse zijn (deel 1, §5).

**T1. De klasseduiding in de keten komt uit de skill, en dat is bewaakt.** De classifier bouwt zijn klassenblok uit
`jas_klassen.py`; `test_detectieprofielen` eist dat de officiële tekst daar vandaan komt en niet uit een profiel. Geen
actie.

**T2. De systeemprompts van classifier en reviewer staan in code, niet in de skill.** Ze dragen methoderegels ("een
rechtsfeit vereist een rechtsgevolg", "verzin geen tekstankers voor impliciete partijen"). Die regels kloppen met het
JAS en noemen JRM niet. Geen wijziging; in W1 krijgen ze een regel in het bronregister, zodat ook deze modeltekst naar
een bron wijst.

**T3. `jas_klasse_opvragen` geeft alleen de drie bronvelden.** Wie twijfelt tussen twee klassen, heeft juist de
afbakening nodig (B10). Voorstel (G2): de tool geeft ook de afbakening en de subklassen, gegenereerd uit de skill.
Raakt: gedrag van de rollen die de tool hebben.

**T4. De subtypen.** `jas_subtype` bestaat voor de paren en voor de tijdsaanduiding. De subklassen van rechtsbetrekking
en rechtsfeit (B6, B7) hebben er geen. Vastleggen in de annotatie raakt het contract van de api en de werkplek en
vraagt bewijs dat de keten zelden heeft. Voorstel: nu niet; zie vraag 2.

**T5. De begrippentoetsen.** De toetsen dekken een kringdefinitie, een rekenregel, een rechtsgevolg en een afleiding
in de definitie. Uit B16 zijn er twee bij te maken zonder model: een ontkenning in de naam, en een afkorting in de
naam. Voorstel (G3): twee signalen erbij, als aandachtspunt en nooit als weigering.

**T6. De grenzen van de detectoren tegenover de Handleiding (B4).** Niet in deze ronde getoetst: het vraagt een
vergelijking per detector. Voorstel: bij W3 een lijst maken van waar de detectoren afwijken van de markeerregels
(bijvoorbeeld de verwijzing in de formulering), en die als open punten in `annotatieketen.md` zetten. Een wijziging
van een detector is een eigen stap met een annotatiemeting en valt buiten dit plan.

## De stappen van deel 2

Zonder gedragswijziging (de methodetekst per rol en `jas_klassen.py` blijven byte-gelijk; de tests op de
vingerafdrukken en de drift bewijzen dat per PR):

- **W1. Het bronregister.** Elke reference een regel *Grondslag*; elke P-regel met bron en paragraaf of
  "projectkeuze"; P15 met de afwijking van B18; een regel voor de prompts van de keten (T2); de versie van B12; de
  test van O2. Raakt: skill (leestekst), bronpakket, een test.
- **W2. De klassenreferentie.** Per klasse *Subklassen* (B6, B7), *Samenhang* (B9), *Afbakening* (B10) en de details
  van B8 en B11, buiten de drie bronvelden; de test van B10. Raakt: skill (leestekst), bronpakket, een test.
- **W3. Markeren.** De markeerregels (B4), het criterium van de centrale klasse (B5), de hernoeming (O3), de lijst
  van T6. Raakt: skill (leestekst), bronpakket, docs.
- **W4. Samenhang.** De partij die de tekst niet noemt (B13, volgens vraag 3), het diagram (B14), specialisatie (B8)
  en de afleidingshiërarchie (B15). `relaties.json` blijft gelijk. Raakt: skill (leestekst), bronpakket.
- **W5. Begrippen.** De richtlijnen (B16) en de vorm van een voorbeeld (B17). Raakt: skill (leestekst), bronpakket.
- **W6. Werkgebied, toetsen en dossier.** B1–B3, B19–B21; het analyseprotocol en het dossier in hun nieuwe vorm.
  Raakt: skill (leestekst), bronpakket, het analysedossier.
- **W7. De skill als geheel.** De omschrijving en de router (O6), de evals (O4), de voorbeelden (O5). Raakt: skill
  (leestekst), bronpakket.

Met gedragswijziging (elk een eigen PR en een eigen meting):

- **G1. De sectie `duiding` sterker.** Na S6. Wat erbij komt, in de woorden van de bron: benoem de partij die de tekst
  niet noemt als interpretatie met haar vindplaats (B13); noem de soort rechtsbetrekking of rechtsfeit waar de tekst
  haar draagt, en anders niet (B6, B7). Raakt: de vingerafdruk van `duiding` en `agent`.
- **G2. `jas_klasse_opvragen` met afbakening en subklassen** (T3). Na W2. Raakt: een toolresultaat.
- **G3. Twee begrippentoetsen** (T5). Na W5. Raakt: de signalen op een begripskaart; geen modeltekst.

Niet in dit plan: subklassen als subtype in de annotatie (T4), een wijziging van een detector (T6), en wetsuitvoering
aan een rol koppelen.

## De volgorde samen met S1–S6

De stappen staan in de volgorde waarin ik ze aanbied. Elke regel is één PR. De hoofdsessie bundelt en merget.

1. **S0b**: dit deel 2. Alleen docs. Nu.
2. **S1**: de regel in code voor een verzoek volgens een niet-gekoppelde methode. Na het sein. Geen meting.
3. **S2**: het veld `methode` in de catalogus. Geen meting.
4. **S3**: de grenzen (een rol krijgt secties van één methode; geen JAS-tool in een profiel van een andere methode).
   Geen meting.
5. **S4**: wetsuitvoering aanvullen, met wat uit wetsanalyse verhuist. Geen meting.
6. **S5**: wetsanalyse opschonen buiten de markers, met O1; test 1 buiten de markers. Geen meting. Let op: P07 en P08
   staan in de bronnenlijst van de sectie `duiding` in `agentrollen.json`. Verandert het weghalen van die codes de
   vingerafdruk, dan blijven de codes staan tot S6. De test wijst het uit.
7. **W1**, **W2**, **W3**, **W4**, **W5**, **W6**, **W7**: de versterking van de leestekst, in die volgorde. Geen
   meting. W2 komt voor W4 omdat de samenhang op de subklassen steunt; W7 komt als laatste omdat de evals de nieuwe
   tekst toetsen.
8. **S6**: JRM uit de modeltekst van `duiding` en `supervisor`; test 1 voor de methodetekst. **Meting.**
9. **G1**: `duiding` sterker. **Meting**, met S6 als nulpunt.
10. **G2**: de tool. **Meting.**
11. **G3**: de twee toetsen. **Meting zonder model.**

S5 en W1–W7 raken dezelfde bestanden en gaan daarom na elkaar, niet naast elkaar. S1–S3 raken de skill niet en
kunnen naast S4–W7 lopen.

## De metingen

Voor elke meting geldt ADR-010 en P19: voor en na op dezelfde versie van al het andere, drie runs, en het resultaat in
`docs/architectuur/metingen/README.md`. Ik vraag een meting op acceptatie aan bij de hoofdsessie en start er zelf geen.

- **S6** (JRM uit `duiding` en `supervisor`). Een gerichte meting (besluit van de gebruiker, 13 nov 2026):
  - **Voor**: meetronde 4, de kwaliteitsset in beide vormen op `43ff91a0`. Dat geldt als nulpunt omdat de stappen
    daarna (S1–S5, W1–W7) de methodetekst per rol byte-gelijk laten.
  - **Na**, op S6 en alleen wat S6 raakt: de duidingsvragen drie runs en de kwaliteitsset één run, in beide vormen
    (supervisor en centrale agent), plus één keer de vragen van de deelvragen-agent (de kop van zijn prompt verandert
    door methodeversie 3.0). Ongeveer 8M tokens.
  - Drempel: brongetrouwheid gelijk; kwaliteit niet slechter; niet duurder, gewogen. Of de routering gelijk blijft,
    toetst `golden_routering` gratis in CI.
  - Waar ik op let: een duidingsantwoord noemt nog de partijen en het voorwerp, en voegt geen rechtsgevolg toe dat de
    tekst niet draagt.
  - G1 gaat pas naar master als deze meting binnen is.
- **G1** (`duiding` sterker).
  - Sets: `golden_duiding` en de kwaliteitsset; in beide vormen. Erbij een kleine vaste set van tien bepalingen met
    een bekende soort (vijf met een partij die de tekst niet noemt, vijf met een gebonden of discretionaire
    bevoegdheid), uit andere bepalingen dan de voorbeelden in de skill: `eval/golden_duiding_partijen.jsonl`. De set
    staat in de PR van G1; omdat een evalbestand het gedrag niet raakt, draait het nulpunt dezelfde set op de code van
    S6.
  - Drempel: brongetrouwheid gelijk; op de vijf vragen met `toets: partij` noemt Lex de wederpartij met een vindplaats,
    of zegt hij dat zij onbekend is, en nooit als citaat; op de vijf met `toets: soort` noemt hij de juiste soort; samen
    minstens acht van de tien; geen verzonnen partij op de bestaande sets; niet meer dan tien procent duurder,
    gewogen.
- **G2** (de tool).
  - Sets: de vragen in `golden_duiding` en `golden_gesprek` waar de tool wordt aangeroepen; als dat er minder dan vijf
    zijn, eerst vijf twijfelvragen toevoegen ("is dit een voorwaarde of een rechtsfeit?").
  - Drempel: het antwoord op een twijfelvraag noemt het onderscheid uit de referentie; brongetrouwheid gelijk; het
    toolresultaat blijft onder een vaste lengte.
- **G3** (de toetsen).
  - Sets: de referentieset begrippen (`v1`, `heldout-v1`, `heldout-v2`), zonder model.
  - Drempel: geen signaal op een begrip dat de referentie goed noemt, behalve waar de naam werkelijk een ontkenning of
    afkorting draagt; het aantal nieuwe signalen staat in de meting.
- **S5 en W1–W7**: geen meting. Het bewijs per PR is dat de vingerafdrukken per rol en `agent/jas_klassen.py` gelijk
  zijn (`test_methodepakket`, `test_methode_drift`), en dat `test_bronpakket` en `test_profielregister` slagen.

## De tests van deel 2

Naast de vijf van deel 1:

6. **Elke methodestap heeft een bron** (O2): elke reference heeft een regel *Grondslag* met bekende codes; elke
   P-regel noemt een bron met paragraaf, of het woord "projectkeuze".
7. **De afbakening loopt gelijk** (B10): elk paar uit `confusable_classes` van een klasseprofiel staat in de
   klassenreferentie bij die klasse.
8. **De evals noemen geen bepaling uit de voorbeelden** (O4, O5): een voorbeeld in de skill is geen testgeval.

Test 1 van deel 1 krijgt één verfijning: de woordenlijst volgt de uitkomst van vraag 1.

## Besluiten op de zeven vragen van deel 2 (13 nov 2026)

De gebruiker is op 13 november 2026 akkoord gegaan met alle zeven voorstellen. De vragen staan eronder, met het
voorstel dat nu het besluit is.

1. **Het scenario blijft bij wetsuitvoering.** Wetsanalyse zegt in een paar zinnen waar de methode het scenario
   gebruikt, met de bron, en verwijst door. Een wetsanalyse legt zelf geen scenario vast.
2. **De subklassen komen in de skill en in het duidingsantwoord.** Vastleggen als subtype bij een markering wordt een
   open keuze in `docs/PLAN.md`.
3. **Lex benoemt de partij die de tekst niet noemt als interpretatie**, met de bepaling waaruit zij volgt, nooit als
   citaat. Bij annoteren legt alleen de jurist haar vast.
4. **S6 en G1 worden apart gemeten**, S6 eerst.
5. **`methode_versie` gaat bij S6 naar 3.0, `skill_versie` bij S5 naar 4.0.**
6. **Een begrip krijgt geen JAS-klasse of begripstype.** De afwijking van het boek staat met de reden in P15.
7. **G2 en G3 worden in dit spoor gebouwd.** Subklassen als subtype en een wijziging van een detector niet.

## De vragen van deel 2, met het voorstel

**1. Het juridische scenario: waar ligt de grens precies?**
Het boek (stap 4) en de Handleiding (1c, 1e, 4a) gebruiken het juridische scenario binnen Wetsanalyse zelf, de
Handleiding met begintoestand, rechtsfeit, rechtsgevolgen en eindtoestand. Besluit 1 legt het scenario bij
wetsuitvoering.
*Voorstel:* besluit 1 blijft. Wetsanalyse zegt in een paar zinnen waar de methode het scenario gebruikt (bij het
werkgebied en bij het toetsen), met de bron, en verwijst voor het uitwerken naar wetsuitvoering. Een wetsanalyse legt
zelf geen scenario vast. Wetsuitvoering krijgt in S4 een regel in het bronregister voor het boek en de Handleiding,
naast de specificatie van BZK. De test staat het woord toe in die verwijzende zinnen.
*Het alternatief:* wetsanalyse houdt het eenvoudige scenario van de Handleiding (gebeurtenissen op volgorde) en alleen
de akte gaat naar wetsuitvoering.

**2. De subklassen van rechtsbetrekking en rechtsfeit: alleen uitleg, of ook vastleggen?**
*Voorstel:* nu alleen in de skill (W2) en in het antwoord van Lex bij een duiding (G1). Vastleggen als subtype bij
een markering raakt de api en de werkplek en komt als open keuze in `docs/PLAN.md`.

**3. De partij die de tekst niet noemt.**
De bron zegt: maak haar expliciet. De skill zegt nu vooral: vul niets in.
*Voorstel:* Lex benoemt de wederpartij in een duiding als interpretatie, met de bepaling waaruit zij volgt, en nooit
als citaat. Bij annoteren verandert niets: alleen de jurist legt een impliciete partij vast (ADR-011).

**4. S6 en G1: twee metingen of één?**
S6 haalt JRM uit `duiding`, G1 zet er iets voor in de plaats. Apart meten geeft per meting één oorzaak; samen scheelt
één meetronde.
*Voorstel:* apart, S6 eerst.

**5. De versienummers.**
`methode_versie` (nu 2.1) staat in de kop van elke systeemprompt. Zonder JRM is de methode een andere.
*Voorstel:* bij S6 naar 3.0, in dezelfde meting, omdat die meting alle rollen al raakt. `skill_versie` gaat bij S5
naar 4.0; dat is geen modeltekst.

**6. Het begrip en zijn JAS-klasse.**
Het boek legt bij een begrip de soort en het type rechtsbetrekking of rechtsfeit vast. De skill stelt geen
begripstype voor (het slanke NL-SBB-begrip).
*Voorstel:* zo laten, en de afwijking van de bron met de reden in het beslisregister zetten (P15).

**7. De tools: hoe ver in dit spoor?**
*Voorstel:* G2 (de tool geeft ook de afbakening) en G3 (twee begrippentoetsen) bouw ik in dit spoor. De subklassen als
subtype (T4) en een wijziging van een detector (T6) niet: die krijgen een regel bij de open keuzes.
