# Plan: de afleidingsregels in Lex (activiteit 3b)

Status: **concept, wacht op de keuze van een richting door de gebruiker; nog niets gebouwd** · Datum: 2026-11-19 ·
Hoort bij: [plan-afleidingsregels.md](plan-afleidingsregels.md) (het onderzoek, de gaten D1–D6, A1–A5, U1–U4, R1–R3, M1–M2),
de regels van het team voor Termijnen (`afleidingsregels-termijnen-team.md`, PR #1762), [ADR-011](adr-011-relaties-tussen-markeringen.md)
(het regelskelet), [ADR-005](adr-005-vraag-lex-en-agents.md), [ADR-008](adr-008-antwoordsjablonen.md),
[ADR-009](adr-009-werkgebiedrapport.md), [ADR-016](adr-016-centrale-agent-en-werkplaats.md),
[artefacten-langs-claude.md](artefacten-langs-claude.md) en [bronselectie-per-deelvraag.md](bronselectie-per-deelvraag.md).

**De mock-ups** van de vier richtingen staan in [`media/afleidingsregels-richtingen.html`](media/afleidingsregels-richtingen.html)
(statische kopie, opent in elke browser) met een schermafbeelding per richting ernaast
(`media/afleidingsregels-richting-a.png` tot en met `-d.png`).

## 1. Waar dit plan over gaat

Het onderzoek in [plan-afleidingsregels.md](plan-afleidingsregels.md) stelde vast wát er ontbreekt voor activiteit 3b: een
regel als eigen object, een betrouwbaar skelet, begrippen voor invoer en uitvoer, een regels-agent, een plek in het
werkgebied en het rapport. Op 19 november 2026 stelde een team van agents op acceptatie de regels van Termijnen op, R1 tot
en met R8, met beslistabellen, een afleidingshiërarchie en zeven interpretatiekeuzes. Lex kon die regels niet bewaren; ze
staan in een logboek buiten de werkplek.

Dit plan legt vast **hoe** de regels in Lex landen: het datamodel, de rol van Lex, de route vanuit het gesprek, het
artefact, de plek in het werkgebied en het rapport, en de projectie naar de graaf. Het eindigt met de keuzes voor de
gebruiker en een PR-volgorde. Eén keuze gaat voor alles: de **richting** van het artefact (§9). De vier richtingen staan
als mock-up naast dit plan. Datamodel, agent en projectie zijn voor alle vier gelijk; waar een richting iets anders vraagt,
staat dat erbij.

## 2. De lijn van Lex, doorgetrokken

Lex is in stappen gegroeid, en elke stap legde een patroon vast dat de regels overnemen:

1. **Annoteren (activiteit 2, ADR-001).** De keten stelt markeringen voor, de jurist beoordeelt ze in het paneel naast de
   wettekst. Het patroon: *Lex stelt voor, de jurist besluit*, met een aandachtsniveau (groen, geel) per voorstel.
2. **Relaties (2c, ADR-011).** Een catalogus in de skill, opslag per drager, het diagram per centrale klasse, en het
   **regelskelet** per afleidingsregel als grondstof voor 3b. Het patroon: *de structuur komt uit de markeringen, niet uit
   vrije tekst*.
3. **Werkgebied (activiteit 1, spoor F).** Vraagkaarten in de volgorde van de methode, een samenvatting met *Aanmaken*, en
   daarna het werkgebied in een eigen paneel. Het patroon: *een vaste stapmachine in code; het model stelt alleen voor*.
4. **Bronselectie per deelvraag (spoor J).** Lex werkt de deelvragen één voor één af; de stand per deelvraag staat bij de
   api, niet in het gesprek, en de code kiest de volgende. Het patroon: *een lange taak als reeks van korte beurten, met de
   stand buiten het gesprek*.
5. **Begrippen (3a, ADR-003/004/006, spoor N).** Een begripskaart op minstens één aanduidende passage, voorstellen per veld
   (*Overnemen*, *Aanpassen*, *Afwijzen*), historie, opvolgers, relaties met type, herbeoordeling bij een veranderde
   passage, en de projectie als NL-SBB-begrippenkader. Het patroon: *een levend object met revisies, gedragen door
   annotaties*.
6. **Artefacten langs Claude (4 nov 2026).** Wat een beurt oplevert is een artefact met een chip; het opent naast het
   gesprek; een versiekiezer toont de stand van die beurt; één paneelschil (`PaneelKop`) met één exportknop. Het patroon:
   *op een artefact lees, bewerk en besluit je; maken en zoeken gaan via het gesprek*.
7. **De centrale agent (ADR-016).** Eén agent per gesprek die zelf antwoordt of overdraagt aan een keten of taakagent
   met een profiel uit één register. Het patroon: *routes in code, taakagents met een contract, een model alleen in een
   strikte stap*.

Doorgetrokken naar 3b betekent dat:

- een regel **een levend object** is zoals een begrip: revisies, status, historie, opvolgers en herbeoordeling, en het rust
  op markeringen zoals een begrip op passages;
- de regel **uit het skelet komt**, niet uit vrije tekst: de regeltekst wordt afgeleid uit de delen;
- Lex **regel voor regel** werkt, van onder naar boven in de hiërarchie, met de stand bij de api, zoals de bronselectie per
  deelvraag;
- de jurist **besluit op het artefact**: overnemen, aanpassen, afwijzen, een lezing kiezen. Op het artefact staat geen
  knop die Lex start;
- een interpretatie **expliciet** wordt: een keuze met lezingen, de gekozen lezing, de motivering en of ze getoetst is;
- de werkgebiedpagina **raadpleegt**: een lijst van regels met *Vraag Lex* per rij.

## 3. Het datamodel

Uitgangspunt: hergebruik wat er is (begrippen, koppelingen met bewijsstand, revisies, audit, `artefact_versies`, het
regelskelet uit `werkgebied_export._regelskelet`) en bouw geen parallelle structuur.

### 3.1 De regel

Een regel hoort bij één werkgebied, net als een begrip.

- **`regels`** (api, Postgres): `id`, `werkgebied_id`, `regelbegrip_id`, `soort`, `uitvoer_begrip_id`, `status`,
  `revisie`, `toelichting` (vrij), `herkomst` (lex, jurist, import), `opvolger_van`, `brontype` (wet of beleid,
  afgeleid uit de dragende markeringen), `aangemaakt_door` en tijden.
- **De naam is een begrip.** Het regelbegrip ("bepalen van het termijnbedrag") is een gewoon begrip in het
  begrippenkader, op de aanduidende passage van de afleidingsregel. Daarmee geldt *een begrip rust altijd op een
  annotatie* vanzelf, en een regel zonder gemarkeerde afleidingsregel kan niet bestaan. Zo deed het team het ook
  (R1 tot en met R7 hebben elk een regelbegrip).
- **De soort**: `rekenregel`, `beslisregel` of `specialisatie` (de methode, plan-afleidingsregels §2.3).
- **De uitvoer**: precies één begrip. Twee regels met dezelfde uitvoer zijn alleen toegestaan als hun gevallen elkaar
  uitsluiten (R2 en R4, via R1); de api meldt het anders als signaal, niet als fout.

### 3.2 Een regel is altijd een beslistabel

Het team koos voor één beslistabel per uitvoer, met rijen die elkaar uitsluiten (R1, R4, R5, R7), in plaats van een regel
per lid. Daarmee heeft het gegeven één bron en kan de volgende regel er eenduidig op bouwen. Dit plan maakt dat de enige
vorm: **een regel heeft één of meer gevallen; een regel met één geval heeft één rij.** Er is dus geen aparte structuur
voor een losse regel en een beslistabel.

- **`regel_gevallen`**: `regel_id`, `volgorde`, `label` ("lid 5"), `voorrang` (R7: rij 2 gaat voor), en per geval:
  - **voorwaarden**: een lijst, elk met een omschrijving "indien …" en de markeringen waarop ze rust (de `voorwaarde`-
    relaties uit het skelet), en of alle of één van de voorwaarden moet gelden;
  - **uitkomst**: de bewerking als reeks van invoerbegrippen en operatoren op volgorde (zie §3.3), of bij een beslisregel
    de waarde van de uitvoer ("in één keer").
- **De regeltekst wordt afgeleid**, in de taalpatronen van de methode ("… moet berekend worden als …", "… is … indien aan
  alle volgende voorwaarden is voldaan"). Ze wordt niet vrij getypt; de toelichting wel. Een afleiding in code geeft
  dezelfde tekst bij dezelfde delen (zoals het overzicht van ADR-008).

### 3.3 Invoer, operatoren en parameters

- **`regel_invoer`**: `regel_id`, `begrip_id`, `volgorde`, `rol` (`invoer` of `parameter`), en waar de invoer vandaan
  komt (de `invoer`-relatie in het skelet). Een invoerbegrip dat de uitvoer van een andere regel is, maakt de hiërarchie
  (§3.5).
- **Operatoren**: het team vond geen gemarkeerde formulering voor *tellen van maanden*, *tijdsduur na tijdstip* en
  *gedeeld door*. Een operator wordt daarom **geen begrip zonder formulering**: de bewerking komt uit een vaste,
  generieke catalogus in code (`operatoren.json` in de skill, gegenereerd naar api en frontend zoals de
  relatiecatalogus). Waar wél een gemarkeerde operator is (*ten hoogste*, R6), wijst de regel naar dat element.
  Open keuze 4.
- **Parameterwaarden per tijdvak**: R2 (zes weken) en R6 (€ 49) hebben een waarde die per tijdvak kan verschillen.
  **`parameter_waarden`**: `begrip_id`, `waarde`, `eenheid`, `geldig_vanaf`, `geldig_tot` (leeg = onbekend), en het
  element waarop de waarde rust. De regel noemt het begrip, niet het getal (de methode, §2.4 van het onderzoek).

### 3.4 Herleiding naar markeringen en relaties

- **`regel_dragers`**: `regel_id`, `geval_id` (leeg = de hele regel), `element_id` of `relatie_id`, `rol` (afleidingsregel,
  voorwaarde, invoer, uitvoer, uitzondering, toepassing), `teksthash` van de passage, en een **bewijsstand** zoals
  `begrip_koppelingen`: open, bevestigd, verworpen.
- **Het skelet is de grondstof, niet de opslag.** De regel neemt de delen over uit `_regelskelet`, en houdt de dragers
  vast. Verandert het skelet (een nieuwe relatie, een afgewezen relatie, een heropende laag), dan meldt de regel dat in de
  herbeoordeling (§3.7). Dat lost ook *een regel die op een heropende laag rust* uit de bevindingen van het team op.
- **De invoer, de uitvoer en de voorwaarden moeten naar een element terug te voeren zijn.** Waar dat niet kan (R5 rij lid 7
  heeft geen markering voor het bedrag; R7 rij 2 heeft geen gemarkeerde voorwaarde), krijgt het geval een **open punt** van
  de soort *skeletgat*, dat op de regel zichtbaar is.

### 3.5 De afleidingshiërarchie

Afgeleid, niet opgeslagen (D2): R4 volgt op R1 omdat *aantal termijnen* de uitvoer van R1 en een invoer van R4 is. De api
levert de hiërarchie als graaf (`/v1/werkgebieden/{id}/regels/hierarchie`) voor het diagram, de volgorde van de agent en
het rapport. Signalen: een kring, twee regels met dezelfde uitvoer zonder uitsluitende gevallen, een invoer zonder regel
die geen parameter of basisgegeven is.

### 3.6 Interpretatiekeuzes en open punten

Het team nam zeven interpretatiekeuzes; drie ervan raken meer dan één regel (lezing C van art. 72 Mbw raakt R1 en R8; "eind
van de maand" raakt R3 en R4). Een keuze hoort daarom bij het **werkgebied**, gekoppeld aan regels en markeringen.

- **`interpretatiekeuzes`**: `werkgebied_id`, `vraag`, `lezingen` (elk met omschrijving en de passages waarop ze rust),
  `gekozen`, `motivering`, `getoetst` (niet, memorie van toelichting, rechtspraak, beleid), `door`, en de koppelingen naar
  regels, gevallen en markeringen.
- **Open punten** (D4): een eigen lijst per regel met soort *beleid* (activiteit 5, alleen signaleren), *ontbrekend
  begrip*, *skeletgat* en *niet getoetst*. Het rapport kent al `open_punten` per onderdeel; dit vult dat voor regels.

Zo staat er na dit plan in Lex wat het team nu in een logboek bijhield: *"lezing C, niet getoetst aan de memorie van
toelichting"* staat als keuze bij R1, zichtbaar in het artefact, het werkgebied en het rapport.

### 3.7 Status, beoordeling en herbeoordeling

- **Status**: `concept` (Lex stelde voor), `in_beoordeling`, `geaccordeerd`, `geaccordeerd_als_beleidsregel` (R3, R6),
  `afgewezen` (met reden; R8: "geen afleidingsregel, een rechtsbetrekking met voorwaarden"), `vervangen` (door een
  opvolger).
- **Accorderen** volgt de poort uit open keuze 3: de begrippen van uitvoer en invoer zijn beoordeeld; het skelet is een
  signaal.
- **Herbeoordeling**: hetzelfde mechanisme als bij begrippen (`begrip_onderhoud`). Een dragende passage verandert, een laag
  gaat weer open, een invoerbegrip krijgt een opvolger, of een interpretatiekeuze wijzigt: de regel komt in de
  herbeoordeling met toen naast nu. Een betekeniswijziging levert een opvolger op.

### 3.8 Versies, audit en export

- **Revisies en audit** zoals bij begrippen: elke wijziging een nieuwe revisie, wie wat deed in de audit van het
  werkgebied.
- **Artefactversies**: de soort `regels` (en, afhankelijk van de richting, `regel`) krijgt een momentopname in
  `artefact_versies`, zodat een chip de stand van die beurt toont, met ‹ versie n van m › en *Nu* (`VersieKiezer`).
- **Export** via de ene knop in `PaneelKop`: *Kopieer als Markdown* (lijsten, geen tabellen, voor wat de jurist
  overneemt; een beslistabel als lijst van gevallen), JSON (het contract), en Turtle (§7).

## 4. De rol van Lex

### 4.1 Een regels-agent

Een taakagent in de vorm van ADR-005 en ADR-016: `tools/graph-qa/agent/agents/regels.py`, met een profiel in
`.claude/lex-agents/regels.md` (instructie, tools, sjablonen) en een methodesectie `regels` in de skill. Eén taak per beurt;
een klik op een suggestie (`actie`) kiest de taak zonder model.

### 4.2 De taken, en wat in code en wat met een model

- **Inventariseren** (code): de gemarkeerde afleidingsregels van het werkgebied, met per regel of het skelet compleet is
  en of er begrippen zijn voor uitvoer en invoer. Levert de volgorde van onder naar boven.
- **Skeletgaten tonen** (code): per afleidingsregel wat ontbreekt (geen uitvoer, invoer zonder volgorde, een rechtsobject
  als invoer, een voorwaarde aan de rechtsbetrekking in plaats van aan de regel). Het herstel gebeurt in de annotatie
  (activiteit 2c), niet in de regel.
- **Een regel opstellen** (code): uit het skelet en de begrippen een conceptregel in het taalpatroon, met de gevallen
  per lid samengevoegd tot één beslistabel per uitvoer. Een **strikte modelstap** alleen waar de code niet kan beslissen:
  de soort bij twijfel, het label van een geval, en het voorstel voor een regelbegrip als dat nog niet bestaat, steeds
  met de fragmenten waarop het rust. Een voorgesteld begrip gaat langs de begrippen-agent, op een passage.
- **Interpretatiekeuzes signaleren** (model, strikt): waar een formulering meer lezingen toelaat ("met overeenkomstige
  toepassing", "eind van de maand"), stelt Lex een keuze voor met de lezingen en de passages. **Lex kiest niet**; de
  jurist kiest op een vraagkaart in het gesprek of op het artefact.
- **Uitsluiting toetsen** (code): sluiten de gevallen van een beslistabel elkaar uit, en sluiten twee regels met dezelfde
  uitvoer elkaar uit? Een signaal, geen besluit.
- **Regels lezen** (A5, leesroute): "welke regel bepaalt de vervaldag?" zoekt in de vastgelegde regels en antwoordt met
  een sjabloon (ADR-008), de feiten uit de code.
- **Meedenken met een gegevensspecialist** (later, model): het debat van het team liet zien dat de waarde van een
  tweede blik in de eenduidigheid zit (R5 zonder teken, anders voldoet een negatief termijnbedrag altijd aan "ten hoogste
  € 49"). Een taak *Toets op eenduidigheid* die per regel de typen en tekens van invoer en uitvoer naast elkaar legt,
  eerst in code (soort van een begrip, D5), daarna eventueel met een model. Pas na een meting.

### 4.3 De stand buiten het gesprek

Zoals bij de bronselectie per deelvraag staat de stand per regel bij de api: *niet gestart*, *in behandeling*, *voorgesteld*,
*beoordeeld*. Een tussenvraag, herladen of een ander gesprek breekt niets; de code kiest de volgende regel (de laagste in de
hiërarchie die nog niet beoordeeld is).

## 5. De route vanuit het gesprek

- **Starten**: "Help mij de afleidingsregels van dit werkgebied op te stellen", de suggestie *Stel de afleidingsregels op*
  na het afronden van de begrippen, of *Vraag Lex* bij een rij op de werkgebiedpagina. De ingang kiest de route in code
  (geen modelstap), zoals bij de bronselectie.
- **Eerst de inventaris**: een compact kaartje in het gesprek ("zeven afleidingsregels, drie met een compleet skelet, twee
  met een skeletgat") dat naar het artefact verwijst.
- **Dan regel voor regel**: per regel een kaartje met de soort, de uitvoer en wat er te beslissen is; het artefact naast
  het gesprek toont de regel. Interpretatiekeuzes komen als vraagkaart in het gesprek (lezing A, B, C, met de passages), en
  het antwoord landt op de regel.
- **Afronden**: *Hoe wil je verder?* met de hiërarchie, de open punten en de suggestie het rapport te openen.
- **Commando's**: geen nieuw commando; de suggesties en *Vraag Lex* volstaan. (Een `/regels` kan later, als de andere
  vaste handelingen ook een commando hebben.)
- **Gescheiden methodes**: de route is van wetsanalyse. Een vraag naar een scenario of een akte gaat naar wetsuitvoering
  en maakt geen regel.

## 6. Het artefact, het werkgebied en het rapport

### 6.1 Het artefact

De soort `regels` is gereserveerd in `frontend/lib/artefact.ts` en `gesprek_contracts.Artefact`. Wat erin staat, hangt af
van de richting (§9). In alle richtingen:

- het opent naast het gesprek in `WerkgebiedArtefactPaneel` met `PaneelKop`, de `VersieKiezer` en de exportknop;
- besluiten gaan met dezelfde knoppen als op de begripskaart (*Overnemen*, *Aanpassen*, *Afwijzen* via
  `KaartVoorstelKaart`, en *Accorderen*);
- elk deel van een regel toont waar het op rust (het element, met de JAS-kleur van zijn klasse) en opent de bepaling;
- er staat geen knop die Lex start, geen zoekveld en geen letter-sneltoets.

### 6.2 Het werkgebied

- **Artefact `Afleidingsregels`** in de tab *Artefacten* (`ARTEFACT_SOORTEN` krijgt `regels`), met een eigen pagina: de
  lijst van regels (naam, soort, uitvoer, status), de hiërarchie als diagram, en per regel de gevallen, de dragers, de
  keuzes en de open punten. Geen nieuwe projecttab: de vijf tabs blijven.
- **De werkgebiedpagina raadpleegt** (F3e): *Vraag Lex* per rij opent het gesprek met de regel als onderwerp.
- **Op de begripskaart** (U4): welke regel het begrip afleidt en welke het gebruikt.
- **In de inventaris**: per afleidingsregel-markering of er een regel op rust.

### 6.3 Het rapport (ADR-009)

- Een hoofdstuk *Afleidingsregels* na *Begrippen*: per regel naam, soort, regeltekst, de gevallen als lijst, uitvoer en
  invoer met hun begrippen, de dragende bepalingen, de keuzes en de open punten; daarna de hiërarchie.
- Een deel *Interpretatiekeuzes* en een deel *Te signaleren uitvoeringsbeleid* (activiteit 5, alleen signaleren).
- Het regelskelet per markering blijft, met een verwijzing naar de regel die erop rust.
- Het rapport blijft één JSON-document (schema-versie omhoog) waaruit PDF en Markdown komen; lijsten, geen tabellen.

## 7. De projectie naar de graaf

- In de named graph van het werkgebied (`urn:wa:graph:werkgebied:<id>`), naast het NL-SBB-begrippenkader, zoals
  `begrip_projectie.py` dat nu doet: alleen de api schrijft, direct na een commit, met de achtergrondlus als vangnet.
- Een klein eigen vocabulaire, geen RegelSpraak en geen feittype: `wa:Afleidingsregel` met `wa:regelbegrip`,
  `wa:uitvoer` en `wa:invoer` (met volgorde) naar de `skos:Concept`'s, `wa:geval` met `wa:voorwaarde`, `wa:rustOp` naar
  de W3C-annotaties van de JAS-lagen, en `prov:wasDerivedFrom` naar de jci-bronreferentie.
- Alleen geaccordeerde regels gaan de graaf in; een vervangen regel krijgt `dct:isReplacedBy`.
- Lex leest de regels via de api (bevestigd door Postgres), zoals `search_annotaties` doet; de graaf is de weg voor
  externe lezers en de controle (graafcontrole, diagnostisch).

## 8. Wat uit het werk van het team in Lex terugkomt

- **R1–R8** worden het eerste bestand: na fase 3 kan een import van het logboek ze als regels in Termijnen zetten
  (herkomst `import`, status zoals het team besloot), zodat de eerste meting een referentie heeft.
- **De afwijkingen van de proef** worden regels in de agent: geen tussenbegrip zonder formulering, één beslistabel per
  uitvoer, een bevoegdheid (art. 24 lid 2) is geen afleidingsregel, een niet geannoteerde bron draagt geen regel.
- **De bevindingen bij de keten** (een rechtsobject als invoer, de volgordeplek van een afgewezen relatie, een
  `uitzondering_op` naar een contextbron) horen bij fase 1 van het onderzoek (A1) en gaan vóór dit plan.

## 9. De vier richtingen

Elke richting gebruikt hetzelfde datamodel en dezelfde agent; ze verschillen in wat het artefact is en waar de jurist
besluit. De mock-ups tonen het gesprek, het artefact ernaast en één beslisstap, met de regels uit Termijnen.

### A. Regelkaart

- **Kerngedachte**: een regel is een object zoals een begrip, met een eigen kaart. Het artefact `regel` (één regel)
  naast het gesprek; de verzameling staat op de werkgebiedpagina.
- **Beslisstap in de mock-up**: R5 *Bepalen termijnbedrag* beoordelen, met het voorstel "uitvoer zonder teken" als
  voorstel per veld.
- **Voor**: sluit naadloos aan op de begripskaart (zelfde componenten, zelfde knoppen); het kleinste nieuwe vlak; een
  regel heeft één adres, één historie, één herbeoordeling.
- **Tegen**: de samenhang tussen de regels zie je pas op de werkgebiedpagina; een beslistabel met drie rijen is krap op
  een kaart.
- **Past bij de uitgangspunten**: volledig. Het hergebruikt `KaartVoorstelKaart`, `BegripBlok` en de herbeoordeling.

### B. Beslistabel

- **Kerngedachte**: de vorm van de regel is de beslistabel. Het artefact toont per uitvoer de gevallen als rijen, met per
  rij de voorwaarden en de uitkomst, en per cel de markering waarop ze rust.
- **Beslisstap in de mock-up**: de interpretatiekeuze bij R2 en R4 ("een aanslag van lid 6 met één termijn valt níét
  terug op lid 1") als vraagkaart in het gesprek, met het effect op de rijen in het artefact.
- **Voor**: maakt uitsluiting en ontbrekende gevallen zichtbaar; dicht bij hoe een jurist en een uitvoerder rekenen; de
  sterkste weg naar de voorbeeldreeks (activiteit 4).
- **Tegen**: in het gesprek en het rapport moet de tabel als lijst (kopieertekst); op een smal scherm vraagt een tabel een
  aparte weergave; een beslisregel met één geval voelt zwaar.
- **Past bij de uitgangspunten**: goed, maar het vraagt een nieuw component (de tabel) dat generiek moet blijven voor
  elke regel en elke soort.

### C. Regelketen

- **Kerngedachte**: het artefact `regels` is de hiërarchie van het werkgebied: een diagram van uitvoerbegrippen en regels
  van onder naar boven, en Lex loopt er regel voor regel doorheen zoals de bronselectie per deelvraag. Een knoop opent de
  regel in hetzelfde paneel.
- **Beslisstap in de mock-up**: R6 *Bepalen wijze van uitbetaling* accorderen als beleidsregel, terwijl de keten laat
  zien dat R5 eronder geaccordeerd is en dat er een signaal is (R6 → R7: het tijdstip bij uitbetaling in één keer).
- **Voor**: de samenhang en de voortgang in één beeld; gaten in de keten (een invoer zonder regel) springen eruit; het
  past op de analysevraag (welke regel draagt welk deel).
- **Tegen**: het diagram vraagt de meeste bouw; met twintig regels wordt het druk; de beoordeling van één regel zit één
  klik dieper.
- **Past bij de uitgangspunten**: goed. Het diagram moet het bestaande graafcomponent (`components/graaf`, sigma) of de
  diagrammodus van ADR-011 hergebruiken, geen tweede graafweergave.

### D. Skelet naar regel

- **Kerngedachte**: de regel ontstaat in de bepaling. Het artefact is de annotatie van het lid, met het regelskelet als
  diagram; de jurist vult de gaten, en de regel verschijnt eronder als afgeleide tekst. Pas als alle leden met dezelfde
  uitvoer een skelet hebben, voegt Lex ze samen tot één regel.
- **Beslisstap in de mock-up**: het skeletgat in art. 9 lid 6 IW 1990 dichten (de voorwaarde "die een uit te betalen
  bedrag behelst") en lezing C van art. 72 Mbw kiezen, waarna R1 rij lid 6 compleet is.
- **Voor**: de sterkste herleiding (de regel staat letterlijk naast de wettekst); dwingt een goed skelet af; geen nieuw
  artefact voor de jurist om te leren.
- **Tegen**: een beslistabel over drie leden past niet in de weergave van één lid; de regel als geheel heeft geen eigen
  plek om te beoordelen; de annotatie-UI groeit met iets dat activiteit 3 is.
- **Past bij de uitgangspunten**: deels. Het artefact blijft de annotatie, maar de grens tussen activiteit 2 en 3 vervaagt
  in de UI.

### Advies

**A met de hiërarchie van C op de artefactpagina.** De regelkaart past het best op wat er is (de begripskaart), en de
keten hoort op de pagina *Afleidingsregels* van het werkgebied, waar je raadpleegt. De beslistabel van B is dan de
weergave van de gevallen op de kaart, als lijst op een smal scherm. D's diagram per lid blijft wat het is (het skelet in
de annotatie) en verwijst naar de regel. De keuze is aan de gebruiker.

## 10. Keuzes voor de gebruiker

1. **De richting**: A, B, C, D, of een combinatie (advies: A met de keten van C).
2. **Een regel is altijd een beslistabel** (één of meer gevallen): akkoord, of toch een aparte vorm voor een regel met één
   geval?
3. **De poort bij accorderen**: beoordeelde begrippen voor uitvoer en invoer verplicht, het skelet als signaal (voorstel);
   of ook een volledig beoordeeld skelet?
4. **Operatoren**: een generieke catalogus in code zonder begrip (voorstel), of generieke operatorbegrippen in het
   generieke kader (ADR-006), ook zonder gemarkeerde formulering?
5. **Interpretatiekeuzes als eigen object op werkgebiedniveau** (voorstel), of als open punt per regel?
6. **Beleidsregels** (R3, R6): in dezelfde lijst met het brontype zichtbaar (voorstel), of apart?
7. **Een afgewezen regel** (R8): bewaren met de reden en de verwijzing naar de rechtsbetrekking (voorstel), of niet
   opslaan?
8. **De soort van een begrip** (D5, bedrag, aantal, datum, ja/nee): nu meenemen voor de eenduidigheidstoets, of later?
9. **De import van R1–R8** uit het logboek van het team als eerste bestand in Termijnen: ja of nee?
10. **Scope** (M1 uit het onderzoek): de skill, `CLAUDE.md` en PLAN zeggen nu "het begin van activiteit 3"; met dit plan
    wordt het "activiteit 1 tot en met 3b".

## 11. De PR-volgorde

Elke PR levert iets bruikbaars op; na elke fase kan het stoppen. Fase 1 van het onderzoek (A1, het skelet betrouwbaar)
gaat ervóór of loopt ernaast.

1. **ADR-017 Afleidingsregels** (docs): het datamodel van §3, de grens met RegelSpraak, de gekozen richting; de scope in
   skill, `CLAUDE.md` en PLAN; de reference `afleidingsregels.md` en `operatoren.json` in de skill (met de generator).
2. **Api: de regel als object** — tabellen `regels`, `regel_gevallen`, `regel_invoer`, `regel_dragers`,
   `parameter_waarden`, met contracten, revisies, audit, de afgeleide regeltekst en de hiërarchie; geen UI.
3. **Api: interpretatiekeuzes en open punten** — `interpretatiekeuzes`, de open punten per regel, de koppelingen.
4. **Frontend: het artefact** — de soort `regels` (en `regel` bij richting A) in `artefact.ts`, het paneel in
   `WerkgebiedArtefactPaneel`, `artefact_versies`, de export; de pagina *Afleidingsregels* bij de artefacten van het
   werkgebied. De jurist kan een regel met de hand maken uit een skelet.
5. **Import van R1–R8** in Termijnen op acceptatie (eenmalig script, herkomst `import`).
6. **graph-qa: de regels-agent, deterministisch** — inventariseren, skeletgaten, opstellen, uitsluiting toetsen; de route
   en de stand per regel; meting op Termijnen tegen R1–R8.
7. **graph-qa: interpretatiekeuzes en de modelstap** — de vraagkaart met lezingen; de strikte modelstap pas na een
   meting.
8. **Rapport en projectie** — het hoofdstuk *Afleidingsregels* (ADR-009), de projectie in de graaf, de leesroute (A5).
9. **Herbeoordeling** — regels in `begrip_onderhoud`: veranderde dragers, heropende lagen, opvolgers van invoerbegrippen.
10. **Later**: de voorbeeldreeks (activiteit 4, D3/A4), de eenduidigheidstoets met de soort van een begrip, en daarna pas
    het feitmodel en RegelSpraak (activiteit 6, buiten de scope).

**Meten**: Termijnen (R1–R8) en WA TRM H1 zijn ontwikkelsets. Een blinde set vraagt een werkgebied met een rekenregel en
een beslisregel dat een jurist zelf uitwerkt; licht meten (één run, gerichte set).
