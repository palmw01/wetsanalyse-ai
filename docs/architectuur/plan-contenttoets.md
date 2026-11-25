# Plan: de contenttoets in Lex

Concept, 25 nov 2026. Bijgewerkt met de besluiten van de gebruiker van dezelfde dag (zie *Besluiten*).
Mockup van fase 2: de schermafbeeldingen in `docs/architectuur/media/` (`mockup-contenttoets-desktop.png`,
`-desktop-bevinding.png`, `-mobiel-gesprek.png`, `-mobiel-paneel.png`, `-mobiel-bevinding.png`). De klikbare mockup zelf
staat niet in de repo, omdat hij de volledige webtekst bevat.

## Kort

Een jurist of redacteur plakt een stuk content, bijvoorbeeld een webtekst, achter `/contenttoets`. Lex legt elke
toetsbare bewering naast de bron en levert een **toetsrapport**: een korte toelichting, en per bewering een oordeel met
de letterlijke brontekst, de vindplaats, een toelichting, de twijfels en aannames, en een voorstel voor een betere zin.
Het rapport heeft twee lagen: een samenvatting in gewone taal voor de redacteur, en de juridische kern voor de jurist.
Lex stelt voor, de mens beoordeelt.

**De contenttoets staat los van de wetsanalyse.** Hij is een eigen skill en een eigen plugin, die je in Lex terugziet en
aan of uit zet. Hij hoort niet bij een werkgebied en gebruikt geen werkgebieden, annotaties, begrippen of de
annotatieketen. Wat hij wel deelt, is de **brondata**: de BWB-kennisgraaf die ook de wetsanalyse voedt.

**Twee fasen.**

1. **Fase 1, het gespreksvenster.** Het toetsrapport is een antwoord van Lex in het gesprek, in een vast sjabloon.
2. **Fase 2, het zijpaneel: het doel.** Je roept de skill aan met de content erachter, Lex analyseert, en in het gesprek
   staat een korte toelichting met een kaartje *Bekijk de contenttoets*, zoals bij een annotatie. Een klik opent rechts
   het paneel met de uitgewerkte toets: de content met de markeringen (goed, minder, fout), en per markering de bron.
   Dat is de mockup.

Fase 1 bouwt al naar dat doel toe: hetzelfde commando, dezelfde skill en hetzelfde contract (met de ankers in de
content). Fase 2 voegt alleen het kaartje en het paneel toe.

**De bron.** Op termijn hoort RegelSpraak de basis te zijn: de geformaliseerde regels waartegen je een bewering exact
kunt toetsen. Die is er nog niet. Fase 1 toetst daarom tegen de **wet- en regelgeving in de graaf**, met de connectors
die in het gesprek aanstaan erbij.

## Wat er al is, en wat we hergebruiken

| Nodig | Is er al | Waar |
|---|---|---|
| Aan/uit per gesprek, beheerder bepaalt wat kan | de bronconnectors | ADR-013 *Bronnen en tools*, `ChatRequest.bronnen`, `connectorsMenu` |
| Een skill die de centrale agent laadt | skills in drie niveaus | ADR-016 §A2, `agent/skills.py`, `laad_skill`/`lees_skill`, het bronpakket |
| Een skill zichtbaar in Lex | *Instellingen › Aanpassingen › Methodes* | `plan-instellingen-aanpassingen.md` |
| Een specialist met eigen instructie, tools en sjabloon | agentprofielen | `.claude/lex-agents/*.md`, `agentprofielen.py` |
| Een vast antwoordformaat dat de code vult | sjablonen als tool | ADR-008, `agent/sjablonen/`, `bronmodel/antwoord.py` |
| Een slash-commando zonder modelstap voor de route | commando's = suggesties met `commando` | `frontend/lib/commandos.ts`, `vraagLex.ts`; `/bron <naam>` heeft al een argument |
| Termijnen, bedragen, datums en percentages uit vrije tekst halen | `hoeveelheden.py`, `beweringen.py` | graph-qa |
| Een lezer die per zin zegt of een passage hem steunt of tegenspreekt, met een tweede, strengere lezing | `stukcontrole.py` (`steunt`, `spreekt_tegen`, `niet_te_zien`, `bevestig`) | graph-qa |
| Letterlijk citeren afdwingen | grounding en `niet_letterlijk` | graph-qa `grounding.py`, `tekstcitaten.py` |
| Een peildatum op de graaf | de toestanden in de graaf, `geldigheid` | graph-qa |
| Een anker in een tekst als offsets (fase 2) | de tekstankers in Unicode-codepoints | `packages/bronmodel` |
| Markeringen in een tekst, klikbaar (fase 2) | de annotatieweergave | `frontend/components/annotaties` (de vorm, niet de JAS-inhoud) |
| Een artefact naast het gesprek (fase 2) | het artefactmodel | `artefacten-langs-claude.md`, de paneelkop, `StatusLabel` |
| De bepaling lezen vanaf een vindplaats | het bronvenster | spoor bronvenster |
| Lange invoer | PR #1860 (de limiet van 2.000 tekens) | `agent/models.py` |

Het nieuwe werk zit vooral in de **skill** (wat is een toetsbare bewering, wanneer is iets onjuist of onvolledig), het
**sjabloon** en de **plugin**. De rest is aansluiten.

## De onderdelen

### 1. De skill `contenttoets`

`.claude/skills/contenttoets/`, in dezelfde opbouw als de andere skills (skillversie 4.0): `SKILL.md` als router, de
uitwerking in `references/`, en `agentrollen.json` met de secties voor de rol `agent` en de eigen rol `contenttoets`. Ze
noemt de skill wetsanalyse niet en leunt er niet op. `test_methodes_gescheiden.py` bewaakt dat.

- `SKILL.md`: drie dingen die altijd gelden (alleen letterlijk opgehaalde brontekst; "mogelijk", de mens beslist; twijfel
  en aannames benoemen), de werkstroom met een checklist, de oordelen en de veelgemaakte fouten.
- `references/beweringen.md`: wat een toetsbare bewering is. Bedragen, termijnen en datums, voorwaarden en
  uitzonderingen, rechtsgevolgen, bevoegdheden ("kan" tegenover "moet", "u hebt recht op" tegenover "de ontvanger kan"),
  voor wie iets geldt, en verwijzingen naar regels. Ook wat **niet** toetsbaar is: procesinformatie (formulieren, DigiD,
  per post), tone of voice en advies.
- `references/criteria.md`: de criteria hieronder, elk met een herkenningsvraag en een voorbeeld.
- `references/bronnen.md`: wat de bron is. Nu de wet- en regelgeving in de graaf en de connectors die aanstaan; later
  RegelSpraak. Welke bron een bewering kan dragen, en wat *niet in de bron* betekent: niet gevonden in wat Lex kan lezen,
  en dus niet fout.
- `references/eenvoud-is-geen-fout.md`: een publiekstekst mag vereenvoudigen. Weglaten is pas onvolledig als de lezer er
  anders door handelt (de toets van de materialiteit).
- `references/herschrijven.md`: hoe Lex een betere zin voorstelt. Dezelfde betekenis als de bron, in de taal van de
  oorspronkelijke tekst, zonder nieuwe beweringen die de bron niet draagt.
- `references/rapport.md`: het sjabloon met de twee lagen. Wat in de samenvatting voor de redacteur staat (gewone taal,
  wat er moet veranderen) en wat in de juridische kern (criterium, vindplaats, citaat).
- `references/voorbeelden.md`: de betalingsregeling uit de mockup, uitgewerkt per bewering.
- `evals/`: andere teksten dan in de voorbeelden, met de verwachte bevindingen.

**De criteria (voorstel).**

Juistheid:

- **J1 Waarde.** Een bedrag, termijn, percentage of datum is gelijk aan de bron. *Voorbeeld: 24 maanden tegenover twaalf.*
- **J2 Voorwaarde en uitzondering.** Een voorwaarde of uitzondering staat er zoals in de bron, met dezelfde grens.
  *€ 90.000 tegenover "ten minste € 100.000".*
- **J3 Reikwijdte.** De regel geldt voor de groep, de belasting of de schuld die de tekst noemt. *De regel voor
  toeslagschulden is overgenomen voor belastingschulden.*
- **J4 Modaliteit.** Een recht, een plicht of een bevoegdheid staat er niet sterker of zwakker dan in de bron.
- **J5 Telmoment.** Een termijn begint en eindigt op het moment dat de bron noemt. *Vier maanden na de laatste vervaldag,
  niet na het verzoek.*
- **J6 Samenhang.** De tekst spreekt zichzelf niet tegen. *Eerst 12 maanden, verderop 24.*
- **J7 Geldigheid.** De bron geldt op de peildatum: vandaag, of de publicatiedatum als je die meegeeft.

Volledigheid:

- **V1 Voorwaarde ontbreekt.** Een voorwaarde waardoor de lezer er niet onder valt, staat er niet. *Kort uitstel alleen
  onder € 20.000.*
- **V2 Gevolg ontbreekt.** Een gevolg waarmee de lezer rekening moet houden, staat er niet. *Verrekening van teruggaven;
  kwijtschelding in plaats van een regeling.*
- **V3 Uitzondering ontbreekt.** De tekst geeft een regel zonder de uitzondering die op de lezer van toepassing kan zijn.
- Telt alleen als het **materieel** is: zou de lezer anders handelen als hij het wist?

**De oordelen** (een gesloten lijst): *juist*, *mogelijk onjuist*, *onvolledig*, *niet in de bron* en, op het niveau van
de hele tekst, *ontbreekt*. Elk oordeel noemt zijn criterium. Een *mogelijk onjuist* zonder letterlijke brontekst bestaat
niet: dan is het *niet in de bron*.

### 2. Het sjabloon en het contract

Fase 1 is een **antwoordsjabloon** (ADR-008): de code vult de feiten (citaten, vindplaatsen, tellingen), het model
levert het oordeel, de toelichting en het voorstel. Het contract staat in `packages/bronmodel/bronmodel/contenttoets.py`,
met een spiegel in `frontend/lib/` en een drift-test, zoals `antwoord.py`. Fase 2 gebruikt hetzelfde contract, dus het
paneel komt erbij zonder dat graph-qa verandert.

- `content`: de tekst, de hash en de lengte.
- `samenvatting`: de telling per oordeel, en een korte toelichting die de code samenstelt.
- `voor_redacteur`: de samenvatting in gewone taal, per bevinding één regel over wat er moet veranderen.
- `bevindingen[]`: het citaat uit de content en, voor fase 2, het anker (begin en eind in codepoints); het oordeel en
  het criterium; de bronnen (vindplaats, BWB-id, jci of bron-URL, toestand en een letterlijk citaat); een toelichting;
  de twijfels en aannames apart; en een `voorstel`, de herschreven zin.
- `ontbreekt[]`: wat de bron zegt en de tekst niet noemt, met het citaat.
- `peildatum`, `getoetst_tegen` (de regelingen en connectors met hun toestand) en `niet_getoetst` (wat Lex bewust liet
  liggen, zoals procesinformatie).

**Hoe het rapport er in het gesprek uitziet (fase 1):**

1. Een korte toelichting: waartegen getoetst, met welke peildatum, en de telling ("3 mogelijk onjuist, 2 onvolledig").
2. *Voor de redacteur*: een lijst in gewone taal, per punt wat er moet veranderen.
3. *Per bewering*, in de volgorde van de tekst: het citaat uit de content, het oordeel als label, de letterlijke
   brontekst met de vindplaats (die opent het bronvenster), de toelichting, de twijfels en aannames, en het voorstel.
4. *Ontbreekt*: wat de bron zegt en de tekst niet noemt.
5. *Niet getoetst*: wat Lex liet liggen, en waarom.

Lijsten, geen tabellen, zodat *Kopieer* het rapport ongeschonden aan de redacteur geeft.

### 3. Graph-qa: de route, het profiel en de controles

```
/contenttoets <tekst>  ──►  route in code (actie contenttoets, geen modelstap)
"Valideer deze content: …" ──► centrale agent ──► overdracht contenttoets (alleen als de plugin aanstaat)
                                       │
            1. voorbereiden (code): zinnen, en per zin de hoeveelheden en de genoemde regelingen
            2. profiel contenttoets (model): per bewering de bron zoeken en lezen, en een oordeel voorstellen
            3. sjabloontool contenttoets: de code vult het contract
            4. controle (code): citaten uit de content letterlijk in de content, broncitaten letterlijk in de trace,
               oordeel uit de lijst
            5. tweede lezing van elke "mogelijk onjuist" (de `bevestig` van stukcontrole): bij twijfel "niet in de bron"
```

- **Profiel** `.claude/lex-agents/contenttoets.md`: de skill vooraf, de leestools van `centraal` plus `semantic_search`
  en `follow_verwijzingen`, de connectors die aanstaan, het sjabloon `contenttoets`, en `modelklasse: zwaar`. Geen
  annotatie-, begrippen- of werkgebiedtools. Gegenereerd en bewaakt zoals de andere profielen.
- **Delegeren past hier.** Een lange tekst met veel beweringen leest veel bronnen. Het profiel kan per groep beweringen
  een subagent starten (ADR-016 §A1).
- **Begrenzen**: een maximum aan tekens per toets en aan beweringen per run, binnen het tokenbudget van de gebruiker.
  Een te lange tekst krijgt een eerlijke melding, geen halve toets.

### 4. De plugin: aan en uit, en zichtbaar in Lex

*Bronnen en tools* krijgt naast bronnen **plugins** (werknaam; in het plan eerder "modules"). De contenttoets is de
eerste. Een plugin bundelt een skill, een profiel, commando's, een sjabloon en later een paneel.

- **Eén register** van plugins in `bronmodel` (naam, label, beschrijving, wat hij meebrengt), zoals `bronmodel.connectors`.
- **Per gesprek aan of uit.** De stand gaat mee met de beurt (`ChatRequest.plugins`) en staat op het gesprek, het pad
  van de bronnen. Geen standaard per werkgebied: de contenttoets hoort niet bij een werkgebied.
- **Eén filter**: staat de plugin uit, dan bestaat het commando niet, kiest de centrale agent het profiel niet, laadt
  `laad_skill` de skill niet, en weigert `dispatch` de sjabloontool.
- **Zichtbaar in Lex**: onder *Instellingen › Aanpassingen* staat de plugin met haar skill, zodat je de criteria kunt
  lezen. De beheerder bepaalt of hij in de straat beschikbaar is.
- **Let op de cache** (ADR-015): staat de skillbeschrijving alleen in het voorvoegsel als de plugin aanstaat, dan zijn
  er twee voorvoegsels. Het alternatief is haar altijd te noemen en alleen het gebruik te weigeren. Dat kiezen we na een
  meting.

### 5. Fase 2: het zijpaneel

Pas na fase 1, maar dit is het doel. In het gesprek blijft van het rapport alleen de korte toelichting over (wat
getoetst is en de telling), met het artefactkaartje *Bekijk de contenttoets*, zoals bij een annotatie. Een klik opent
rechts het artefact *Contenttoets*, met de vorm van de mockup:

- de samenvatting met de tellers als filter, en een legenda;
- de content met de markeringen (juist, onvolledig, mogelijk onjuist, niet in de bron); een markering opent haar
  bevinding;
- per bevinding de brontekst, de toelichting, het voorstel (geel, *Overnemen*, *Aanpassen*, *Afwijzen*) en *Eens* of
  *Oneens*;
- een vindplaats opent de bepaling in het bronvenster;
- op een smal scherm ligt het paneel over het gesprek.

Het rapport en de beoordelingen staan op het bericht in het gesprek. Er komt geen eigen opslag en geen audit.

## De meting

- **Een gouden set**: de betalingsregeling uit de mockup (vijf fouten en één omissie, met hun bron), plus vier tot zes
  andere teksten (kwijtschelding, uitstel bij bezwaar, invorderingsrente), elk met een paar fouten die we er bewust in
  zetten, en een tekst zonder fouten.
- **Wat we meten**: hoeveel van de bekende fouten Lex vindt, hoeveel *mogelijk onjuist* vals is (dat weegt het
  zwaarst), of elk citaat letterlijk is (moet 100% zijn), de tokens en de duur per toets.
- **Licht meten** (één run, gerichte set). Drie runs alleen bij een twijfelachtige uitkomst.

## De volgorde

**Fase 1: het gespreksvenster**

| Stap | Wat | Raakt |
|---|---|---|
| **C0** | De skill en de criteria in markdown, met de gouden set. **De gebruiker keurt de criteria goed vóór er code komt.** | `.claude/skills/contenttoets/` |
| **C1** | Het contract en het antwoordsjabloon, met de spiegel en de drift-test | `bronmodel`, graph-qa, `frontend/lib` |
| **C2** | Route, profiel en controles, achter een proefvlag die alleen op acceptatie aanstaat | graph-qa |
| **C3** | Het commando `/contenttoets` en het rapport in het gesprek | frontend |
| **C4** | Plugins in *Bronnen en tools* en in *Aanpassingen* | bronmodel, graph-qa, api, frontend |
| **C5** | De meting op acceptatie, en bijsturen in de skill | eval |

**C0** volgt in een eigen PR: de skill met `lex_soort: "plugin"`, zodat hij nog niet in het bronpakket staat en de
centrale agent hem niet ziet tot C4. De gouden set is `evals/` met zelfgemaakte teksten; de betalingsregeling is het
voorbeeld in de skill en de eerste casus voor de meting in C5.

**C1 staat er** (25 nov 2026): het blok `contenttoets` in `bronmodel/antwoord.py` (met de oordelen en criteria in
`bronmodel/contenttoets.py`), het sjabloon `antwoord_contenttoets` (`tools/graph-qa/agent/sjablonen/contenttoets.py`; de
content staat in de trace als `contenttoets_content`, gezet door de route van C2), de spiegel `frontend/lib/contenttoets.ts`
met de drift-test, en het blok in het gesprek (`ContenttoetsBlok`). Nog geen route, profiel of commando.

C0 staat los. C1 en C4 kunnen naast elkaar. C2 en C3 hebben C1 nodig. Bij UI-werk komen eerst screenshots.

**Fase 2: het zijpaneel**

| Stap | Wat | Raakt |
|---|---|---|
| **C6** | Het paneel *Contenttoets* uit de mockup, met de ankers en het bronvenster | frontend, graph-qa (ankers) |
| **C7** | Voorstellen overnemen en beoordelen, bewaard op het bericht | api (gesprekken), frontend |

**Later**: RegelSpraak als bron, zodra die er is.

## Risico's

- **Een vals "onjuist" kost vertrouwen.** Dat vangen de tweede lezing en de regel "geen citaat, dan geen onjuist" op.
- **De bron staat er niet.** Werkinstructies en formuliervoorwaarden zitten niet in de graaf, zoals de grens van
  € 90.000. Dat wordt *niet in de bron* met een aanname, nooit *onjuist*.
- **Vereenvoudigen is geen fout.** Zonder de materialiteitstoets wordt elk publiek stuk "onvolledig".
- **Lange teksten** kosten veel tokens; het budget en de grens per toets begrenzen dat.
- **Persoonsgegevens** in geplakte content: de AVG-poort (ADR-007) geldt ook hier.
- **Vermenging met wetsanalyse.** `test_methodes_gescheiden.py` krijgt de nieuwe skill erbij.

## Besluiten (gebruiker, 25 nov 2026)

1. **Naam**: `/contenttoets`. De skill heet ook `contenttoets`.
2. **Voor wie**: allebei, in twee lagen. Een samenvatting in gewone taal voor de redacteur, en de juridische kern voor
   de jurist.
3. **Bronnen**: de wet- en regelgeving in de graaf, en de connectors als ze in het gesprek aanstaan. Op termijn is
   RegelSpraak de basis.
4. **Herschrijven**: ja. Per bevinding een betere zin als voorstel.
5. **Bewaren**: alleen in het gesprek. Geen werkgebied, geen gedeelde opslag, geen audit.
6. **Peildatum**: standaard vandaag. Geef je een publicatiedatum mee, dan toetst Lex tegen de toestand op die datum.
7. **Plugins**: ja, generiek. *Bronnen en tools* krijgt plugins, en de contenttoets is de eerste.
8. **Los van de wetsanalyse**: een eigen skill en plugin, zichtbaar in Lex en aan of uit te zetten. Hij deelt alleen de
   brondata.
9. **Eerst het gespreksvenster**: fase 1 levert het rapport in het gesprek. Het doel is fase 2: een korte toelichting met
   een kaartje *Bekijk de contenttoets*, dat het zijpaneel opent, zoals bij een annotatie.
