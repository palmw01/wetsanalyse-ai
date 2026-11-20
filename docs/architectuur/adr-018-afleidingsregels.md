# ADR-018 — Afleidingsregels in Lex (deelactiviteit 3b)

Status: **aangenomen (gebruiker, 19 nov 2026: de richting en de voorstellen bij alle open keuzes); nog niets gebouwd**
· Datum: 2026-11-19 · Hoort bij: [plan-afleidingsregels-in-lex.md](plan-afleidingsregels-in-lex.md) (§12 de gekozen
richting, §13 het bouwplan, R0), [ADR-011](adr-011-relaties-tussen-markeringen.md) (het regelskelet),
[ADR-003](adr-003-nl-sbb-begrippencontract.md), [ADR-005](adr-005-vraag-lex-en-agents.md),
[ADR-006](adr-006-generieke-begrippen.md), [ADR-009](adr-009-werkgebiedrapport.md),
[ADR-016](adr-016-centrale-agent-en-werkplaats.md), skill
[`references/afleidingsregels.md`](../../.claude/skills/wetsanalyse/references/afleidingsregels.md) (PR #1766),
`plan-lessen-e2e-termijnen.md` (PR #1764).

## Context

Lex dekt activiteit 1 tot en met 3a: werkgebied, markeren en relaties, begrippen. Deelactiviteit 3b, de
afleidingsregels, had geen plek; het artefact `regels` was alleen gereserveerd. Op 19 november 2026 stelde een team
van agents op acceptatie de regels van werkgebied Termijnen op (R1–R8, PR #1762). Die regels, met vier beslistabellen,
twee parameters met hun waarde per tijdvak, zeven interpretatiekeuzes en zes punten ontbrekend beleid, staan alleen in
een logboek en een document.

Drie dingen staan vast:

- **De methode** (skill `references/afleidingsregels.md`, in eigen woorden naar M01–M04): een regel heeft precies één
  uitvoer en krijgt een begrip "bepalen <uitvoer>". Hij wordt geschreven met begrippen in een vast taalpatroon, en rust
  via gemarkeerde formuleringen op wetgeving of beleidsregels. Per afgeleid begrip is er één regel. Tussenresultaten
  krijgen een begrip. Een operatorbegrip ontstaat bij een formulering. Een duur bij een tijdstip is een
  Tijdsaanduiding. Een regel gebruikt de parameter, niet de waarde. Open punten worden expliciet.
- **Het regelskelet bestaat al** (ADR-011): de relaties `uitvoer`, `invoer` (met volgorde), `operator_in`, `operand`,
  `voorwaarde`, `waarde`, `tijd`, `uitzondering_op` en `toepassing` per afleidingsregel. Het rapport rekent het uit
  (`werkgebied_export._regelskelet`).
- **De werkplek heeft een vast model** (`artefacten-langs-claude.md`, ADR-016). Wat een beurt oplevert, is een
  artefact naast het gesprek. Op een artefact lees, bewerk en besluit je; maken en zoeken gaan via het gesprek. Lex
  stelt voor en de jurist besluit. Componenten zijn generiek.

De gebruiker koos uit vier richtingen (regelkaart, beslistabel, regelketen, skelet naar regel), na een toets op de
methode, de uitgangspunten van Lex en het gebruik, voor een combinatie: **de regelkaart in de keten**
(plan §12).

## Besluit

### 1. De regel is een eigen object, zoals een begrip

Een regel hoort bij één werkgebied en is gedeeld, net als begrippen en annotatielagen; wie wat deed, staat in de audit.
Hij heeft revisies, een status, een historie, opvolgers en een herbeoordeling, met dezelfde mechanismen als een begrip.
Er komt geen parallelle structuur: koppelingen met bewijsstand, revisies, audit, artefactversies en de projectie volgen
het patroon van de begrippen.

### 2. Waarop een regel rust

Een regel rust op de formuleringen die zijn uitvoer en zijn voorwaarden dragen (skill, *Waarop een regel rust*):
- de Afleidingsregel-markering, als die er is;
- anders de formulering van het afgeleide begrip. Een beslisregel over een recht of bevoegdheid rust op de
  Rechtsbetrekking met haar voorwaarden, een tijdstip op de Tijdsaanduiding die het beschrijft.

Een regel zonder enige grondslag weigert de api, zoals een begrip sinds #1760. Een contextbron is niet geannoteerd en
draagt dus geen regel; dat is een signaal om haar te analyseren.

### 3. Eén regel per uitvoer, altijd als beslistabel

Per afgeleid begrip is er één regel. Een regel heeft één of meer **gevallen**; een regel met één geval heeft één rij.
Er is geen aparte vorm voor een "losse" regel.
- Elk geval heeft een label ("lid 5"), voorwaarden en een uitkomst. De gevallen sluiten elkaar uit; een eventuele
  voorrang staat erbij (R7: rij 2 gaat voor).
- De api toetst of twee regels met dezelfde uitvoer elkaar uitsluiten (R2 en R4 via R1). Doen ze dat niet, dan is dat
  een signaal en geen fout.

### 4. Begrippen in de regel

- **Regelbegrip**: "bepalen <uitvoer>", een gewoon begrip op de passage van de grondslag.
- **Uitvoer**: precies één begrip. **Invoer**: begrippen op volgorde, elk met de rol `invoer` of `parameter`.
- **Tussenresultaat**: een eigen regel met een eigen uitvoerbegrip, dat op de afleidingsregel rust met de koppelrol
  `afgeleid` (#1760).
- **Operator**: een operatorbegrip op een gemarkeerde formulering, daarna generiek hergebruikt (ADR-006). De lijst met
  namen in de skill (B5, #1766) is alleen een voorstel voor de naam. Het taalpatroon is geen begrip.
- **Tijd**: een duur bij een tijdstip ("zes weken na", "telkens een maand later") is een Tijdsaanduiding. De regel
  noemt die bewerking in het taalpatroon.
- **Parameter**: de regel noemt het parameterbegrip. De waarde is een parameterwaarde met een eigen begrip, een tijdvak
  (geldig vanaf en tot, leeg is onbekend), een vindplaats en de getoetste toestand.

### 5. De regeltekst wordt afgeleid

De regeltekst is niet vrij te typen. De code leidt haar af uit de delen, zodat dezelfde delen dezelfde tekst geven. De
toelichting is vrij. De taalpatronen (M02 §3.5.2b en het praktijkvoorbeeld; de vormen voor tijdstip en beslistabel
zijn een projectkeuze) zijn:
- *rekenregel*: "De <uitvoer> moet berekend worden als <invoer> <operator> <invoer> …";
- *tijdstip*: "De <uitvoer> moet bepaald worden als <tijdsaanduiding> <invoer>";
- *beslisregel*: "<Wie of wat> <is/heeft> <uitvoer> indien aan alle volgende voorwaarden is voldaan:", met de variant
  "aan één van de volgende voorwaarden", genest tot elke diepte;
- *specialisatie*: "Een <rechtssubject of rechtsobject> is een <uitvoer> indien …";
- *met gevallen*: "De <uitvoer> moet bepaald worden volgens het geval dat geldt:", en per geval "indien …" met de
  uitkomst;
- een ontkenning staat in de regel als *niet*, nooit in het begrip.

In de weergave zijn begrippen herkenbaar en operatoren vet, naar de schrijfwijze van het boek. De kopieertekst en het
rapport geven gevallen en voorwaarden als lijsten, niet als tabellen.

### 6. Open punten en interpretatiekeuzes

Eén object voor alle open punten van een werkgebied (L-X-1 uit de lessen; de vorm uit de skill, *Wat open blijft*):
- de soort: interpretatiekeuze, ontbrekend uitvoeringsbeleid, onderzoekspunt of gat in de annotatie;
- waar het aan hangt: een of meer regels, gevallen, markeringen of begrippen. Een keuze kan meer regels raken; lezing C
  van art. 72 Mbw raakt er twee;
- bij een interpretatiekeuze: de lezingen met hun grondslag, de gekozen lezing, wie koos, de **methode**
  (teleologisch, wetshistorisch, systematisch, grammaticaal) en wat nog getoetst moet worden.

Lex signaleert en legt lezingen voor. Lex kiest niet.

### 7. Voorbeelden horen bij het beoordelen

Een regel heeft voorbeelden: invoerwaarden, de uitkomst en het oordeel of die juridisch juist is (M01 h.3 stap 4a).
Ze staan op de regelkaart in dezelfde vorm als de voorbeelden van een begrip. Lex stelt ze voor; het oordeel is van de
jurist. De volledige voorbeeldreeks van activiteit 4b valt buiten dit besluit.

### 8. Status en poort

- Statussen:
  - `concept`;
  - `in_beoordeling`;
  - `geaccordeerd`;
  - `geaccordeerd_als_beleidsregel`, als de grondslag een beleidsregel is;
  - `afgewezen`, met reden;
  - `vervangen`, door een opvolger;
  - `herbeoordelen`.
- De api geeft per regel een lijst van wat er nog openstaat voor accorderen, en de kaart toont die. Wat er in de poort
  zit, staat in besluit 2 hieronder.
- Herbeoordeling volgt het mechanisme van de begrippen:
  - een dragende passage verandert;
  - een laag gaat weer open;
  - een invoerbegrip krijgt een opvolger;
  - een interpretatiekeuze wijzigt.

### 9. Het artefact: de regelkaart in de keten

- Twee artefactsoorten in dezelfde paneelschil (`PaneelKop`, `VersieKiezer`, één exportknop), als tabs naast elkaar:
  - `regel` is één regel, met de opbouw van de begripskaart;
  - `regels` is de keten van het werkgebied: de afleidingshiërarchie als lijst en diagram, met de stand per regel.
- De kaart toont deze delen:
  - *Beoordeling*;
  - *Regel*: regelbegrip, regeltekst en de gevallen als lijst;
  - *Invoer en uitvoer*: met de regel die elke invoer levert;
  - *Formuleringen*: de dragers met JAS-klasse en beoordeling, waarbij een skeletgat een open punt is;
  - *Voorbeelden*, *In de keten* (volgt op, gebruikt door, zelfde uitvoer), *Interpretatiekeuzes*, *Open punten* en
    *Historie*.
- Op de kaart staat geen knop die Lex start, geen zoekveld en geen letter-sneltoets. Voorstellen van Lex staan per veld
  in geel (`KaartVoorstelKaart`).
- De werkgebiedpagina raadpleegt: het artefact *Afleidingsregels*, met *Vraag Lex* per rij. De begripskaart toont
  *Afgeleid door* en *Gebruikt in*. Het regelskelet in de annotatie toont op welke regel het rust.
- De mock-up `media/afleidingsregels-voorstel.html` is de referentie voor de vorm.

### 10. Lex

- Een taakagent `regels` (ADR-005, ADR-016), zonder profiel; zie besluit 7.3 van de gebruiker en
  [bijlage A](adr-018-bijlage-agentische-laag.md).
- In code: inventariseren (van de analysevraag terug naar de regels en de keten), de volledigheidstoets op het skelet,
  een conceptregel opstellen uit skelet en begrippen, en uitsluiting toetsen.
- Een strikte modelstap alleen waar de code niet kan beslissen, en pas na een meting:
  - de soort bij twijfel;
  - het label van een geval;
  - een ontbrekend regelbegrip, via de begrippen-agent;
  - het signaleren van een interpretatiekeuze met lezingen;
  - voorbeelden voorstellen.
- De route: Lex begint bij de analysevraag, zoekt terug welke regels nodig zijn en stelt ze dan van onder naar boven
  op, één per beurt. De stand per regel staat bij de api en de code kiest de volgende, zoals bij de bronselectie per
  deelvraag. Een interpretatiekeuze is een open punt op de regelkaart, met de keuzekaart van ADR-016 §A4 in het gesprek
  (besluit 7.13).

### 11. Projectie en rapport

- De api projecteert geaccordeerde regels in de named graph van het werkgebied, naast het begrippenkader. Dat gebeurt
  met een klein eigen vocabulaire:
  - `wa:Afleidingsregel` met `wa:regelbegrip`, `wa:uitvoer`, `wa:invoer` (geordend) en `wa:geval`;
  - `wa:rustOp` naar de annotaties;
  - `prov:wasDerivedFrom` naar de jci-bronreferentie.

  Een vervangen regel krijgt `dct:isReplacedBy`. Er komt geen RegelSpraak en geen feittype.
- Het rapport (ADR-009) krijgt het hoofdstuk *Afleidingsregels*, met interpretatiekeuzes en te signaleren beleid.

### 12. De grens met RegelSpraak

Een regel in 3b is implementatieonafhankelijk en hoeft niet uitvoerbaar te zijn. Hij moet wel zo precies zijn dat een
jurist hem met voorbeelden kan toetsen. Het feitmodel, de typen, de relaties "van een … over een …", een vaste syntaxis
en uitvoerbaarheid horen bij activiteit 6 en vallen buiten Lex.

## Datamodel (api, Postgres)

- `regels`: `id`, `werkgebied_id`, `regelbegrip_id`, `soort`, `uitvoer_begrip_id`, `status`, `revisie`,
  `toelichting`, `herkomst` (lex, jurist, import), `opvolger_van`, `brontype` (afgeleid uit de dragers), aanmaker en
  tijden. Revisies in `regel_revisies`, de audit in `werkgebied_audit`.
- `regel_gevallen`: `regel_id`, `volgorde`, `label`, `voorrang`, `voorwaarden` (een boom van "alle" en "één van", met
  per blad een omschrijving en de markeringen) en `uitkomst` (invoer en operatoren op volgorde, of de waarde van de
  uitvoer).
- `regel_invoer`: `regel_id`, `geval_id` (leeg is de hele regel), `begrip_id`, `volgorde` en `rol`.
- `regel_dragers`: `regel_id`, `geval_id`, `element_id` of `relatie_id`, `rol`, `teksthash` en de bewijsstand, zoals
  `begrip_koppelingen`.
- `parameter_waarden`: het begrip van de parameterwaarde, het parameterbegrip, `waarde`, `eenheid`, `geldig_vanaf`, `geldig_tot`, het dragende element en de
  getoetste toestand.
- `regel_voorbeelden`: `regel_id`, `geval_id`, de invoerwaarden, de uitkomst, het oordeel en de herkomst.
- `open_punten`: het object van L-X-1, met koppelingen naar regels, gevallen, markeringen en begrippen.
- `regel_voortgang`: de stand per regel voor de route van Lex.
- `artefact_versies` krijgt de soorten `regel` en `regels`.

De hiërarchie wordt niet opgeslagen maar afgeleid: een regel volgt op een andere als zijn invoer de uitvoer van die
ander is.

## Gevolgen

- De scope van het platform wordt "activiteit 1 tot en met 3b". De skill zegt dat al met #1766; PLAN heeft spoor V.
- Het hele 3b-resultaat van Termijnen moet in dit model passen, zonder vrije tekst voor skelet, parameters of keuzes.
  Dat is de eerste maat (R1 in het bouwplan).
- De kwaliteit van een conceptregel van Lex hangt aan het skelet. De bouw van Lex volgt daarom pas na lessenbundel 3.
- Interpretatiekeuzes en ontbrekend beleid worden zichtbaar in de werkplek en het rapport, en niet meer alleen in een
  logboek.
- Dit is een nieuw artefact en een nieuwe agent met een nieuw profiel: het bronpakket, het profielregister en de
  catalogus volgen.

## Overwogen en afgewezen

- **De beslistabel als enige weergave** (richting B): de methode schrijft een regel als zin met een lijst voorwaarden.
  Een tabel past slecht op een telefoon en niet in kopieertekst. De gevallen blijven, als lijst.
- **De keten als enige artefact** (richting C): te ver van de regel die je beoordeelt. De keten blijft als tweede tab
  en als pagina van het werkgebied.
- **De regel in de annotatie** (richting D): een regel over drie leden past niet in de weergave van één lid, en de
  grens tussen activiteit 2 en 3 vervaagt. De annotatie toont alleen op welke regel het skelet rust.
- **Een regel per lid**: dan krijgt één gegeven drie identiteiten (de les van het team).
- **Vrij getypte regeltekst**: die veroudert stil als de delen veranderen, en is niet te toetsen.
- **Operatoren als begrippen zonder formulering, of een catalogus zonder begrip**: geen van beide volgt de methode
  (#1766).
- **R8 afwijzen omdat het een bevoegdheid is**: volgens de methode is het een beslisregel (M-3b-0).

## Besluiten van de gebruiker (19 nov 2026)

De gebruiker nam de richting en de voorstellen bij alle open keuzes over:

1. **De richting**: de regelkaart in de keten.
2. **De poort bij accorderen** vraagt:
   - beoordeelde begrippen voor uitvoer en invoer;
   - genomen interpretatiekeuzes op de regel;
   - minstens één beoordeeld voorbeeld per geval.

   Het skelet is een signaal en blokkeert niet.

   **Aanvulling (besluit gebruiker 20 nov 2026).** Op de vraag of een open onderzoekspunt (zoals O1 in Termijnen) het
   accorderen moet blokkeren, besliste de gebruiker: "Ja, blokkeren". Daarom houdt elk open punt dat aan de regel of
   aan een van zijn gevallen hangt de poort tegen, welke soort het ook is: interpretatiekeuze, ontbrekend
   uitvoeringsbeleid, onderzoekspunt of gat in de annotatie. De reden noemt het punt. Een punt telt niet meer mee als
   het besloten is (*gekozen* of *getoetst*), als *gesignaleerd* (het beleid ontbreekt), of als het is omgehangen naar
   iets buiten de regel. Tot die datum was alleen een keuze blokkerend en een onderzoekspunt of gat een signaal.
3. **Interpretatiekeuzes** horen bij het werkgebied en worden gekoppeld aan regels, gevallen, markeringen en begrippen.
4. **Beleidsregels** staan in dezelfde lijst, met het brontype zichtbaar en de status `geaccordeerd_als_beleidsregel`.
5. **De soort van een begrip** (bedrag, aantal, datum, ja of nee) komt later, na een besluit over P15. De
   eenduidigheidstoets wacht daarop.
6. **Termijnen als eerste bestand**: R1–R8 worden op acceptatie geïmporteerd na R1 en R3 van het bouwplan, met R8 als
   beslisregel en het termijnregime als tussenregel als de jurist dat wil. De wijziging op acceptatie zelf vraagt
   op het moment van uitvoeren nog een akkoord.

Al beslist door de methode (#1760, #1766): operatoren, tussenresultaten, de grondslag en R8.

### De agentische laag (19 nov 2026)

7. **De dertien keuzes van [bijlage A](adr-018-bijlage-agentische-laag.md) §10.** De gebruiker nam ze alle over:
   1. Een regel van Lex is een conceptregel met `herkomst: "lex"`, als `Voorstel` op de kaart. Accorderen blijft bij de
      jurist.
   2. Lex wijzigt alleen een eigen concept dat niemand anders wijzigde. Bij elke andere regel stelt Lex per veld voor
      (`KaartVoorstelKaart`), na R5.
   3. De regels-agent is een taakagent zonder profiel (`register.AGENTS`, `overdracht.TAAKAGENTS`, de tool
      `taakagent`). Een leesprofiel `regels_lezen` (niet kiesbaar) komt met R7, met `lees_regels` onder VASTE ROUTES.
   4. 3b is één fase van "werk dit werkgebied uit", regel voor regel. Opstellen doet geen subagent.
   5. Er komt een methoderol `regels`. Elke modelstap van 3b is een `llm_stap.Rol` met die methoderol, te kiezen onder
      *Aanpassingen › Agents*, en gemeten zodra een model hem krijgt.
   6. De volledigheidstoets staat in de api, als uitbreiding van `regelskelet.gaten`. De gaten komen uit de skill
      (gegenereerd, met een drifttest).
   7. De eerste modelstap is het signaleren van interpretatiekeuzes.
   8. Voorbeelden van Lex: de invoer per geval altijd, de uitkomst alleen bij een rekenregel met bekende waarden, en het
      oordeel altijd `open`.
   9. Een ontbrekend begrip (een regelbegrip "bepalen <uitvoer>" of een tussenresultaat met `afgeleid`) vraagt de
      regels-agent aan de begrippen-agent, op de passage. De regel wacht in de poort.
   10. "Goed genoeg" zijn de drempels van bijlage A §7.4: eerst de ontwikkelset, dan blind. Een stap die ze niet haalt,
       blijft uit.
   11. Subagents onderbouwen de lezingen van een open punt (R6b, na de meting van R6). Het plan komt uit `te_toetsen`,
       in code. Er is een bevestigingskaart en een plafond van hoogstens drie per open punt. Lex kiest niets.
   12. De stand is één generieke `werkvoortgang`, met regels als eerste gebruiker. De bronselectie verhuist later.
   13. De jurist besluit op het artefact (het open punt op de regelkaart). In het gesprek staat de keuzekaart van
       ADR-016 §A4. Beide schrijven naar de ene besluitroute van het open-puntobject; er komt geen nieuwe modus van de
       vraagkaart.

## Fasering

Het bouwplan R0–R7 staat in [plan-afleidingsregels-in-lex.md](plan-afleidingsregels-in-lex.md) §13. Dit ADR is R0.

De agentische laag (de regels-agent, zijn tools, de skills, de route, de meting en de keuzes, R5, R6 en R6b) staat in
[bijlage A](adr-018-bijlage-agentische-laag.md), aangenomen op 19 nov 2026. R3 en verder beginnen pas als de gebruiker
daar apart voor kiest.
