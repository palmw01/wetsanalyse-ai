# Plan: de afleidingsregels in Lex (activiteit 3b)

Status: **richting gekozen (gebruiker, 19 nov 2026: de regelkaart in de keten, §12.3); bouwplan in §13; nog niets gebouwd** · Datum: 2026-11-19 ·
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
  annotatie* vanzelf. De grondslag van een regel (skill `references/afleidingsregels.md`, PR #1766): de
  Afleidingsregel-markering als die er is, en anders de formulering van het afgeleide begrip. Een beslisregel over een
  recht of bevoegdheid rust op de formulering van dat recht, een Rechtsbetrekking, en hoeft niet als Afleidingsregel
  gemarkeerd te zijn. Een regel zonder enige grondslag kan niet bestaan (#1760).
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
- **Operatoren** (bijgesteld 19 nov 2026, na `plan-lessen-e2e-termijnen.md` §0 en M-3a-1): volgens de methode is een
  operator een **operatorbegrip op een gemarkeerde formulering**, dat elke formulering met dezelfde bewerking
  hergebruikt ("gelijke" in "gelijke termijnen" staat wél in de tekst van Termijnen). Een duur bij een tijdstip
  ("zes weken na", "telkens een maand later") is een Tijdsaanduiding en geen operator; de regel noemt die bewerking in
  het taalpatroon (skill, PR #1766). Een vaste lijst met
  namen (`operatoren.json` in de skill, gegenereerd naar api en frontend zoals de relatiecatalogus) dient alleen als
  voorstel voor de naam. Wat in het taalpatroon zelf staat ("moet berekend worden als", "indien aan alle volgende
  voorwaarden is voldaan"), is regelvorm en geen begrip. Ontbreekt de formulering echt, dan is dat een open punt
  (*skeletgat*), geen begrip zonder grondslag. Open keuze 4 is daarmee beslist, tenzij de gebruiker anders kiest.
- **Tussenresultaten**: een tussenresultaat van een berekening krijgt een eigen regel met een eigen uitvoerbegrip (rol
  `afgeleid`, PR #1760), dat rust op de afleidingsregel-markering waaruit het volgt. Zo kunnen het *termijnregime* en het
  *maandnummer van de dagtekening* uit de proef op papier begrippen zijn.
- **Parameterwaarden per tijdvak**: R2 (zes weken) en R6 (€ 49) hebben een waarde die per tijdvak kan verschillen.
  De parameterwaarde is een eigen formulering met een **eigen begrip**, gerelateerd aan het parameterbegrip (M01 h.6;
  skill, PR #1766). **`parameter_waarden`** legt per parameterwaardebegrip vast: het parameterbegrip, `waarde`,
  `eenheid`, `geldig_vanaf`, `geldig_tot` (leeg is onbekend) en het element waarop de waarde rust. De regel gebruikt het
  parameterbegrip, niet de waarde; een waarde staat nooit in de definitie van het parameterbegrip.

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
  `afgewezen` (met reden), `vervangen` (door een opvolger).
- **R8** (art. 24 lid 2): het team wees hem af als "een bevoegdheid, geen afleiding"; volgens de
  methode is een regel die bepaalt of een recht of bevoegdheid bestaat juist een **beslisregel** (M-3b-0 in
  `plan-lessen-e2e-termijnen.md`), met als uitvoer het bestaande begrip *bevoegdheid tot verrekening vóór het verstrijken
  van de betalingstermijn* (fb9f3866). De grondslag van een regel is de afleidingsregel-markering als die er is, en anders
  de formulering van het afgeleide begrip, ook een rechtsbetrekking.
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

Een taakagent in de vorm van ADR-005 en ADR-016: `tools/graph-qa/agent/agents/regels.py`, met een methodesectie
`regels` in de skill. Herzien op 19 nov 2026: zonder profiel in `.claude/lex-agents/` ([ADR-018, bijlage A](adr-018-bijlage-agentische-laag.md)). Eén taak per beurt;
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
- **De afwijkingen van de proef**: één beslistabel per uitvoer en "een niet geannoteerde bron draagt geen regel" worden
  regels in de agent. Drie werkregels van het team waren strenger dan de methode en worden dat niet: een tussenresultaat
  krijgt wel een begrip, een operator met een formulering wel een operatorbegrip, en een bevoegdheid onder voorwaarden
  (R8) is een beslisregel (M-3b-0).
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

(Uitgewerkt en gevalideerd in §12; de gekozen combinatie staat in §12.3.) **A met de hiërarchie van C op de artefactpagina.** De regelkaart past het best op wat er is (de begripskaart), en de
keten hoort op de pagina *Afleidingsregels* van het werkgebied, waar je raadpleegt. De beslistabel van B is dan de
weergave van de gevallen op de kaart, als lijst op een smal scherm. D's diagram per lid blijft wat het is (het skelet in
de annotatie) en verwijst naar de regel. De keuze is aan de gebruiker.

## 10. Keuzes voor de gebruiker

1. **De richting**: A, B, C, D, of een combinatie. Voorstel na de validatie: *de regelkaart in de keten* (§12.3).
2. **Een regel is altijd een beslistabel** (één of meer gevallen): akkoord, of toch een aparte vorm voor een regel met één
   geval?
3. **De poort bij accorderen**: beoordeelde begrippen voor uitvoer en invoer verplicht, het skelet als signaal (voorstel);
   of ook een volledig beoordeeld skelet?
4. **Operatoren**: *beslist door de methode* (PR #1766). Een operatorbegrip ontstaat bij de eerste gemarkeerde
   formulering en is daarna generiek; de lijst in de skill is alleen een voorstel voor de naam. "Zes weken na" is een
   Tijdsaanduiding, geen operator.
5. **Interpretatiekeuzes als eigen object op werkgebiedniveau** (voorstel), of als open punt per regel?
6. **Beleidsregels** (R3, R6): in dezelfde lijst met het brontype zichtbaar (voorstel), of apart?
7. **R8** (art. 24 lid 2): *beslist door de methode* (PR #1766, M-3b-0). Het is een beslisregel met uitvoer
   *bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn*, en hij rust op de Rechtsbetrekking. Een
   regel die later toch wordt afgewezen, blijft bewaard met de reden.
8. **De soort van een begrip** (D5, bedrag, aantal, datum, ja/nee): nu meenemen voor de eenduidigheidstoets, of later?
9. **De import van R1–R8** uit het logboek van het team als eerste bestand in Termijnen: ja of nee?
10. **Scope** (M1 uit het onderzoek): de skill, `CLAUDE.md` en PLAN zeggen nu "het begin van activiteit 3"; met dit plan
    wordt het "activiteit 1 tot en met 3b".

## 11. De PR-volgorde

*Vervangen door het bouwplan van §13 (19 nov 2026); hieronder de eerste versie.*

Elke PR levert iets bruikbaars op; na elke fase kan het stoppen. Fase 1 van het onderzoek (A1, het skelet betrouwbaar)
gaat ervóór of loopt ernaast.

1. **ADR-018 Afleidingsregels** (docs): het datamodel van §3, de grens met RegelSpraak, de gekozen richting; de scope in
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

## 12. Validatie van de vier richtingen, en de gekozen combinatie

Op verzoek van de gebruiker (19 nov 2026) zijn de vier richtingen langs drie maten gelegd: de methode (hoe je volgens
de bronnen een afleidingsregel opstelt), de uitgangspunten van Lex en het gebruik. Daarna zijn ze gecombineerd tot één
richting, met een eigen mock-up die zo dicht mogelijk bij de werkplek van nu ligt:
[`media/afleidingsregels-voorstel.html`](media/afleidingsregels-voorstel.html), met schermafbeeldingen
`media/afleidingsregels-voorstel-regel.png`, `-keten.png` en `-geaccordeerd.png` (na de beslisstap).

### 12.1 Wat de methode vraagt

In eigen woorden, met vindplaats (M01 het boek, M02 de Handleiding, M03 de Leidraad; zie `references/bronnen.md`):

1. **Eerst een begrip voor de regel, dan de regel met begrippen.** Voor een geclassificeerde afleidingsregel maak je een
   begrip dat de aard en functie noemt ("bepalen …"), en daarna stel je de regel op met de begrippen die er al zijn
   (M01 h.3 stap 3b; M02 §3.5.2b).
2. **De opbouw van een regel**: de uitvoer; de wijze van afleiden met de invoer en de bewerking; de voorwaarden, met wat
   vergeleken wordt en hoe (M01 h.3 stap 6, de onderdelen van een afleidingsregel). Een operator krijgt een begrip
   ("min", "plus") dat elke formulering met dezelfde bewerking deelt (M01 h.6, het voorbeeld van de Zvw).
3. **Een vast taalpatroon**: "… moet berekend worden als …" en "… is … indien aan alle (of één) van de volgende
   voorwaarden is voldaan", met de voorwaarden als lijst, ook genest (M02 §3.5.5, het praktijkvoorbeeld van de
   zorgtoeslag). In de schrijfwijze van het boek zijn begrippen herkenbaar en operatoren vet (M01, de kleurconventie).
4. **Een overzicht met het afgeleide begrip**: naam van de regel, de regel, en het begrip dat hij afleidt; het afgeleide
   begrip wordt in de volgende regel hergebruikt. Zo ontstaat de afleidingshiërarchie (M02 §3.5.5; M01 h.4 §6).
5. **Werkrichting**: bij een berekening begin je bij de bepaling die de uiteindelijk benodigde waarde geeft, en zoek je
   van daaruit de bepalingen die de invoer afleiden (M01 h.6, de aanpak van de Zvw).
6. **Per formulering, in één adem**: rond een centrale klasse krijgt elke formulering in het diagram een begrip en waar
   het speelt een afleidingsregel, en direct daarna volgen valideren en het signaleren van beleid (M02 §3.4; M03, de
   iteraties).
7. **Interpretatie expliciet**: classificeren, begrippen en regels vragen interpretatie (teleologisch, wetshistorisch,
   systematisch, grammaticaal), en elke interpretatie wordt vastgelegd voor de beleidsverantwoordelijken (M01 h.3 stap
   3c; M02 §3.5.3; M03, activiteit 5).
8. **Valideren met concrete voorbeelden**: per regel invoerwaarden, de uitkomst en de vraag of die juridisch juist is,
   inclusief nul, negatief en onbekend; dat toetst ook of de regels volledig zijn (M01 h.3 stap 4a; M02 activiteit 4b).
9. **Herleidbaar**: elk begrip en elke regel rust rechtstreeks op wet- en regelgeving of beleidsregels, via de
   gemarkeerde formuleringen (M03 nr. 17; M02 §3.5.2d).
10. **Multidisciplinaire review**: jurist, uitvoeringsdeskundige, informatieanalist en ontwikkelaar lopen de resultaten
    na (M01 h.3 stap 4). Het team op acceptatie deed dat met jurist, gegevensspecialist en regelspecialist; de
    gegevensspecialist vond het teken van het termijnbedrag (R5).

### 12.2 De vier richtingen langs de drie maten

**A. Regelkaart**
- *Methode*: dekt 1, 2, 3, 9 goed (de kaart heeft regelbegrip, uitvoer, invoer, bewerking, dragers). Mist 4 en 5:
  de hiërarchie staat elders. Voorbeelden (8) passen vanzelf, want de begripskaart heeft ze al.
- *Uitgangspunten*: het best. Dezelfde paneelschil en componenten als het begrip; voorstel per veld; geen Lex-knop.
- *Gebruik*: vertrouwd, want een jurist die begrippen beoordeelde, kent de kaart al. Het nadeel is dat je zonder de
  keten niet ziet waar een invoer vandaan komt, en dat een beslistabel van drie gevallen krap is.

**B. Beslistabel**
- *Methode*: sterk op 2 en 8 (gevallen, voorwaarden, en de stap naar voorbeeldreeksen). Wijkt af van 3: de methode
  schrijft een regel als zin met een lijst voorwaarden, niet als tabel. De beslistabel is RegelSpraak (activiteit 6).
- *Uitgangspunten*: vraagt een nieuw tabelcomponent, en kopieertekst en rapport moeten toch lijsten zijn.
- *Gebruik*: overzichtelijk op een groot scherm, slecht op een telefoon; zwaar voor een regel met één geval.
- *Wat blijft*: het idee **gevallen per uitvoer die elkaar uitsluiten**, getoond als lijst van gevallen in het
  taalpatroon.

**C. Regelketen**
- *Methode*: het sterkst op 4 en 5: het overzicht met afgeleid begrip, hergebruik in de volgende regel, en werken vanaf
  de uiteindelijke waarde.
- *Uitgangspunten*: past bij de bronselectie per deelvraag (stand bij de api, de code kiest de volgende). Het diagram
  moet het bestaande graafcomponent hergebruiken.
- *Gebruik*: goed voor overzicht en voortgang. Als enige artefact te ver van de regel zelf: beoordelen zit een klik
  dieper.
- *Wat blijft*: **de keten als overzicht** (een eigen tab in het paneel en de pagina van het werkgebied), en **op elke
  regel de buren**: waar de invoer vandaan komt en wie de uitvoer gebruikt.

**D. Skelet naar regel**
- *Methode*: het sterkst op 6 en 9: de regel ontstaat bij de formulering, en het skelet dwingt herleidbaarheid af.
  Botst met 4 en met het besluit van het team: één regel per uitvoer, over drie leden heen.
- *Uitgangspunten*: vervaagt de grens tussen activiteit 2 (annotatie) en 3 (regel) in de UI.
- *Gebruik*: prettig om een gat te dichten met de wettekst ernaast; je kunt er een regel niet als geheel beoordelen.
- *Wat blijft*: **het skeletgat wordt een open punt op de regel met een link naar de bepaling**, en het herstel gebeurt
  in de annotatie, die er al is. De annotatie toont welke regel op de afleidingsregel rust.

**Wat geen enkele richting goed deed**
- *Interpretatie* (7): alleen B en D lieten een keuze zien, en geen van beide legde de interpretatiemethode en de toets
  vast.
- *Voorbeelden* (8): stonden alleen als later werk. De methode noemt ze juist het middel om een regel te valideren, en
  in Termijnen laat één voorbeeld het open punt van Leidraad 9.1 zien (de laatste termijn op 31 december).
- *Werkrichting* (5): het team werkte van onder naar boven. De methode zoekt van boven naar beneden. Beide zijn nodig.

### 12.3 De gekozen richting: de regelkaart in de keten

Eén zin: **een afleidingsregel is een kaart zoals een begrip, die opent naast het gesprek en altijd laat zien waar hij in
de keten staat. De gevallen staan als lijst in het taalpatroon, de interpretatiekeuzes en de voorbeelden staan op de
kaart, en Lex leidt het gesprek van de analysevraag naar de regels en dan regel voor regel.**

- **Het gesprek**:
  - Lex begint bij de analysevraag en zoekt van boven naar beneden welke waarden ervoor nodig zijn (methode 5). Het
    resultaat is de keten.
  - Daarna stelt Lex de regels van onder naar boven op, één per beurt, zoals bij de bronselectie per deelvraag. De
    stand per regel staat bij de api.
  - Een interpretatiekeuze komt als vraagkaart in de dock, de bestaande `VragenKaart`. Lex legt de lezingen voor, met
    de passages en de interpretatiemethode; de jurist kiest.
- **Het paneel**: twee soorten artefacten in dezelfde paneelschil, als tabs naast elkaar zoals nu.
  - `regels`: de keten van het werkgebied (uit C), als lijst in de volgorde van de keten met status, plus een compact
    diagram;
  - `regel`: één regel, met dezelfde opbouw als de begripskaart (uit A). Daarop staan:
    - *Regel*: de afgeleide regeltekst in het taalpatroon, met de gevallen als lijst (uit B);
    - *Invoer en uitvoer*: de begrippen met hun status, en per invoer de regel die hem levert;
    - *Formuleringen*: de dragende markeringen met hun JAS-klasse en beoordeling, en een skeletgat als open punt dat de
      bepaling opent (uit D);
    - *Voorbeelden*: invoer, uitkomst en het oordeel "juridisch juist?" (methode 8), met de voorstellen van Lex per
      voorbeeld zoals bij een begrip;
    - in de rechterkolom *Beoordeling* (met wat er nog openstaat voor accorderen), *In de keten* (volgt op, gebruikt
      door), *Interpretatiekeuzes* (lezing, methode, getoetst), *Open punten* en *Historie*.
- **De werkgebiedpagina**: het artefact *Afleidingsregels* toont de keten, met *Vraag Lex* per regel. Lex start er niet.
- **De annotatie**: blijft zoals hij is. Het regelskelet in de annotatie krijgt één regel extra: "rust op regel R4".

Wat dit betekent voor §3 tot en met §11:
- het datamodel blijft;
- §3.6 krijgt bij een interpretatiekeuze het veld `methode` (teleologisch, wetshistorisch, systematisch, grammaticaal);
- de voorbeelden (D3) schuiven naar voren, naar PR 4 en 6, omdat ze bij het beoordelen horen;
- de operatoren volgen de methode: een operatorbegrip op een gemarkeerde formulering, met de namenlijst als voorstel
  (§3.3, bijgesteld na `plan-lessen-e2e-termijnen.md`).

### 12.4 Hoe de mock-up de drie maten laat zien

De mock-up toont R4 *Bepalen vervaldagen van de termijnen* uit Termijnen, in de werkplek zoals die nu is (zijbalk,
gesprekskop, dock, paneel met tabs, begripskaartopbouw), gebouwd met de klassen van de huidige frontend:
- *methode*: regelbegrip, uitvoer, invoer met herkomst, gevallen als lijst in het taalpatroon, de keten, de dragende
  formuleringen, een interpretatiekeuze met methode, en een voorbeeld dat de keuze zichtbaar maakt (31 januari, dan
  28 februari, dan 31 maart of 28 maart);
- *uitgangspunten*: het artefact naast het gesprek, besluiten op het artefact, de keuze via het gesprek, geen Lex-knop
  op de kaart, voorstellen in geel;
- *gebruik*: de vraagkaart beantwoorden werkt de regel, het voorbeeld en de beoordeling bij; daarna kan *Accorderen*.
  De tab *Afleidingsregels* toont de keten met R4 erin.

## 13. Bouwplan

**Besluit (gebruiker, 19 nov 2026):** akkoord met de regelkaart in de keten (§12.3). Dit bouwplan vervangt de
PR-volgorde van §11 en sluit aan op de bundels van `plan-lessen-e2e-termijnen.md` (PR #1764, §9), zodat niets twee keer
gebouwd wordt. Werkwijze zoals altijd:
- elke stap begint met een eigen korte toets of dit de beste verbetering is;
- PR's worden per bundel verzameld, één keer getest en één keer uitgerold; de hoofdsessie voert de regie;
- gedrag van Lex wordt licht gemeten: één run, een gerichte set.

### 13.1 Wat er eerst moet liggen

Uit `plan-lessen-e2e-termijnen.md`, en niet opnieuw in dit plan:
- **#1760** (geen begrip zonder grondslag; een tussenresultaat krijgt een begrip dat op de afleidingsregel rust, met
  de koppelrol `afgeleid`): besloten door de gebruiker;
- **#1766** (lessenbundel 1): de skill volgt de methode bij 3b, met `references/afleidingsregels.md` en de
  operatorbegrippen. R0 neemt die reference over en schrijft hem niet opnieuw;
- **lessenbundel 2**: de leesvorm `weergave?vorm=skelet` (L-3b-2), met het skelet uit `werkgebied_rapport.regelskelet_regels`. De
  regels-agent en het paneel lezen het skelet daaruit;
- **lessenbundel 3**: de keten legt het skelet goed (L-2-1, L-2-2: geen rechtsobject als invoer, invoer op volgorde,
  `uitzondering_op` en `toepassing`). Zonder betrouwbaar skelet is een conceptregel van Lex niet beter dan het skelet;
- **lessenbundel 4**: de open punten (L-X-1). Dat is hetzelfde object als de interpretatiekeuzes en open punten van §3.6:
  één bouw, niet twee.

Bundel R0 hieronder gaat samen met lessenbundel 1 in één docs-PR.

### 13.2 De bundels

**R0. Besluit en methode** (docs, skill; geen code) — *in uitvoering: [ADR-018](adr-018-afleidingsregels.md)*
- [ADR-018](adr-018-afleidingsregels.md) *Afleidingsregels* (R0, in uitvoering): het datamodel van §3 met de bijstellingen van 19 nov 2026, de regelkaart in de keten,
  de grens met RegelSpraak, en de open punten van M-3b-2 met het veld `methode`.
- De skill (`references/afleidingsregels.md`, werkstroom F en de grens "activiteit 1 tot en met 3b") ligt er met #1766.
  R0 voegt alleen toe wat de bouw nodig heeft: de taalpatronen als vaste lijst voor `regeltekst.py`, en de namenlijst
  van operatoren als bestand met generator en drift-test, voor zover #1766 die niet al levert.
- PLAN heeft spoor V.
- Vraagt de besluiten van §10 punt 2, 3, 5, 6, 8 en 9; punt 4 en 7 zijn door de methode beslist.
- Klaar als: de ADR is aangenomen en `genereer_jas_klassen.py --check` groen is.

**R1. De regel als object** (api; lessen L-3b-1)
- Tabellen in `api/app/db.py`, idempotent zoals de rest (`create_all` plus `reconcile_schema`):
  - `regels`, `regel_gevallen`, `regel_invoer`, `regel_dragers` en `parameter_waarden`;
  - revisies zoals `begrip_revisies`, en de audit in `werkgebied_audit`.
- Nieuwe modules, met de begrippen als voorbeeld:
  - `regel_contracts.py` en `regel_store.py`;
  - router `regels.py` onder `/v1/werkgebieden/{id}/regels`, met de hiërarchie op `/regels/hierarchie`;
  - `regeltekst.py`: de afgeleide regeltekst in het taalpatroon, deterministisch, met tests per soort en per vorm van
    voorwaarden (alle, één van, genest);
  - `regel_poort.py`: wat er openstaat voor accorderen (begrippen beoordeeld, keuzes genomen, voorbeelden beoordeeld),
    als lijst die het paneel toont.
- `artefact_versies.SOORTEN` krijgt `regel` en `regels`; `gesprek_contracts.Artefact` de soort `regel`.
- De poort van de api: een regel zonder grondslag (geen dragende markering) wordt geweigerd, zoals een begrip sinds #1760.
- Tests: Termijnen R1–R8 als vaste set. Alles moet in het object passen, zonder vrije tekst voor skelet of parameters;
  dat is de maat van L-3b-1. Plus het routecontract in `tests/poort/`.
- Klaar als: de set past, de poort-tests en `scripts/kruistests.sh` groen zijn.

**R2. Het artefact en de kaart** (frontend, BFF; na R1)
- `lib/artefact.ts`: de soorten `regel` (verplicht `werkgebied_id` en `regel_id`) en `regels` (verplicht
  `werkgebied_id`), met labels.
- BFF-routes onder `app/api/werkgebieden/[id]/regels/**`, met `metTrace()` en alle query-parameters doorgestuurd.
- De kaart en de keten:
  - `components/werkgebieden/RegelPagina.tsx` bouwt de kaart uit dezelfde delen als `BegripPagina`: sectiekaart,
    `StatusLabel`, `Lijst`, `KaartVoorstelKaart` voor voorstellen per veld, `VersieKiezer` en `ExportKnop`;
  - `RegelKeten.tsx` is de tab *Afleidingsregels*: de lijst in de volgorde van de keten, met het diagram uit
    `components/graaf` in een eigen modus en geen tweede graafweergave.
- `WerkgebiedArtefactPaneel` opent beide; ze staan als tabs naast elkaar, zoals nu.
- Werkgebied:
  - `ARTEFACT_SOORTEN` krijgt `regels`, met de pagina's `/werkgebieden/[id]/artefacten/regels` en
    `/regels/[regelId]`;
  - *Vraag Lex* per rij, en geen Lex-knoppen op de kaart.
- Op de begripskaart (U4): *Afgeleid door* en *Gebruikt in*. In het regelskelet van de annotatie: "rust op regel R4".
- Export: *Kopieer als Markdown* (lijsten, geen tabellen) en JSON.
- Tests:
  - vitest voor de regeltekst en de poortweergave;
  - Playwright met de mock-up als referentie (`docs/architectuur/media/afleidingsregels-voorstel.html`);
  - `knoppen.test.ts` en de bestaande generieke-componententests blijven groen.
- Klaar als: R4 uit de set ziet eruit als de mock-up, op desktop en op 390 px.

De agentische laag is uitgewerkt en aangenomen in [ADR-018, bijlage A](adr-018-bijlage-agentische-laag.md) (19 nov 2026,
alle dertien keuzes). R3 tot en met R7 hieronder volgen die bijlage. R1 is #1768 en R2 is #1770. R3 en verder beginnen
pas als de gebruiker daar apart voor kiest.

**R3. Open punten op de regel** (frontend en api; na lessenbundel 4)
- Het open-puntobject bouwt lessenbundel 4, niet deze bundel. Het heeft:
  - de vier soorten uit de skill;
  - `hangt_aan` met regel en geval;
  - lezingen, gekozen lezing, methode en `te_toetsen`;
  - één besluitroute van de jurist.

  R3 wijzigt dat object niet.
- De regelkaart toont de open punten bij hun regel en geval. De jurist kiest daar een lezing, met methode en reden
  (besluit 7.13).
- In het gesprek staat de keuzekaart van ADR-016 §A4, die naar dezelfde besluitroute schrijft. Er komt geen nieuwe modus
  van de vraagkaart.
- De poort van een regel neemt de genomen keuzes mee (ADR-018 besluit 2).
- Klaar als: de keuzes en beleidspunten van Termijnen er zonder vrije tekst in passen.

**R4. Termijnen als eerste bestand** (script; op acceptatie, na akkoord)
- `api/scripts/importeer_regels_termijnen.py` zet R1–R8 met hun keuzes en open punten in Termijnen, met herkomst
  `import`.
- R8 volgt het besluit van §10 punt 7.
- Dit is de referentie voor de meting van R5. De wijziging op acceptatie vraagt een akkoord op het moment van uitvoeren.

**R5. Lex stelt regels voor, zonder model** (graph-qa en api; lessen L-3b-3)
- De regels-agent is een taakagent zonder profiel (besluit 7.3). Hij staat in `agents/regels.py`, `agents/register.py`
  en `overdracht.TAAKAGENTS`.
- Taken in code (bijlage A §2.2): `inventariseren`, `volledigheidstoets`, `opstellen`, `uitsluiting_toetsen` en
  `voorbeelden`.
  - De inventaris volgt alle drie de soorten dragers van de methode.
  - `opstellen` volgt relaties over bepalingen heen.
- De gaten komen uit de skill, als uitbreiding van `regelskelet.gaten`: gegenereerd, met een drifttest.
- **`werkvoortgang`**: één generieke stand per werkgebied, met soort, onderwerp, stand en wie (besluit 7.12). Regels is
  de eerste gebruiker. De bronselectie verhuist later in een eigen PR (PLAN.md, spoor V).
- 3b is een fase van "werk dit werkgebied uit". De fase start met de knop voor de volgende fase, en een getypte opdracht
  gaat via `taakagent`. De poort naar de fase is ADR-018 besluit 2.
- Ook in deze bundel:
  - de catalogus (de agent en de workflow);
  - de `/`-commando's;
  - de routeringsset en de golden set van de centrale agent;
  - een compact blok regels in `werkgebied_context` (ADR-015).
- Elke nieuwe aanroep naar de api krijgt een plek in `agent_toegang.TOEGESTAAN`, met de begrenzing erbij.
- Meten volgens bijlage A §7: op Termijnen tegen R4, de gaten tegen die van de regelspecialist, en daarna blind.

**R6. De eerste modelstappen** (graph-qa; na de meting van R5)
- Elke modelstap is een `llm_stap.Rol` met de methoderol `regels` (besluit 7.5), te kiezen onder
  *Aanpassingen › Agents*.
- Eerst `keuzes_signaleren` (`Rol.REGEL_KEUZES`): een open punt met lezingen, fragmenten en `te_toetsen`. De stap kiest
  niet.
- Daarna de soort bij twijfel (`REGEL_SOORT`) en het praktijkvoorbeeld bij de voorbeelden (`REGEL_VOORBEELD`).
- Meten: licht, één run, met de keuzes van Termijnen als set.

**R6b. Subagents onderbouwen de lezingen** (graph-qa; na de meting van R6)
- Het plan komt uit `te_toetsen` van het open punt, in code. Elke bronsoort wijst een kiesbaar profiel aan:
  `wetsgeschiedenis_lezen`, `rechtspraak_lezen`, of `algemeen` met een connector.
- Het is een delegatie met een plan uit code, met een bevestigingskaart en hoogstens drie subagents per open punt
  (besluit 7.11).
- Het rapport staat per lezing bij het open punt, in de vorm van `DefinitieOnderbouwing`. Lex kiest niets.
- Meten: zijn de lezingen terecht en onderbouwd, en wat kost het (als delta van het verbruik).

**R7. Rapport, graaf, lezen en onderhoud** (api en graph-qa)
- Het rapport (ADR-009) krijgt het hoofdstuk *Afleidingsregels*, met daarin interpretatiekeuzes en te signaleren beleid;
  de schema-versie gaat omhoog. Stem dit af met het hoofdstuk over open punten van lessenbundel 4.
- `regel_projectie.py` naast `begrip_projectie.py`: de regels in de named graph van het werkgebied, met het kleine
  vocabulaire van §7.
- De leesroute `lees_regels` met het profiel `regels_lezen` (niet kiesbaar), onder VASTE ROUTES in `centraal.md`.
- Herbeoordeling: `begrip_onderhoud` ziet ook regels. Een veranderde drager, een heropende laag, een opvolger van een
  invoerbegrip of een gewijzigde keuze zet de regel op *opnieuw bekijken* in de `werkvoortgang`.

**Later, buiten dit plan:** de volledige voorbeeldreeks van activiteit 4b, de soort van een begrip (P15/D5), het feitmodel
en RegelSpraak.

### 13.3 Volgorde en wat parallel kan

- R0, R1 (#1768) en R2 (#1770) liggen er.
- R3 volgt op lessenbundel 4. Die bundel bouwt het open-puntobject; R3 toont het op de regel. De twee raken
  verschillende bestanden, en dat is afgestemd met de sessie van de lessen.
- R4 komt na R1 en R3, en vraagt een akkoord voor de wijziging op acceptatie.
- R5 komt na lessenbundel 3 (een betrouwbaar skelet) en R4.
- R6 komt na de meting van R5, en R6b na de meting van R6.
- R7 kan na R2, in delen. Het rapport en de projectie zijn onafhankelijk van de agent.
- Wat zonder de agent al waarde heeft, kan eerder: de gaten uit de skill en de uitsluitingstoets, als signaal op de
  regelkaart.
- R3 en verder beginnen pas als de gebruiker daar apart voor kiest.

Parallel kunnen R3 en R7 rapport, en R7 rapport en R7 projectie. Een sessie per bundel, in een eigen worktree;
twee schrijvers raken nooit dezelfde bestanden.
