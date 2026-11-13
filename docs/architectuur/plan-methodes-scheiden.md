# Plan: wetsanalyse (JAS) en wetsuitvoering (JRM) zuiver scheiden

Status: plan, 13 november 2026, op master `2be1f804`; de open vragen zijn dezelfde dag beantwoord. Er is nog niets
gewijzigd aan de methodetekst, aan graph-qa, de api of de frontend. Dit document is de inventaris, wat er per vondst
gebeurt, de volgorde en de besluiten. De bouwstappen beginnen na meetronde 4.

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
| De andere secties (`basis`, `supervisor`, `retrieval`, `definitie`, `deelvragen`, `nl-sbb-taalniveau`) | `agentrollen.md` en de references | noemen JRM niet; ongewijzigd |
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

S1 kan meteen na meetronde 4. S2 tot en met S5 volgen elkaar op en kunnen zonder meting. S6 is de enige wijziging van
modeltekst en komt als laatste, in een eigen PR.

### De meting bij S6

De zin staat in de sectie `duiding`. Die gaat naar de rol `duiding` en naar de rol `agent` (de centrale agent).

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
