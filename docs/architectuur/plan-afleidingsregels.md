# Plan: van annotaties en begrippen naar afleidingsregels (activiteit 3b)

Status: **concept, onderzoek en plan; nog niets gebouwd** · Datum: 2026-11-18 · Hoort bij: [ADR-011](adr-011-relaties-tussen-markeringen.md)
(het regelskelet), [ADR-003](adr-003-nl-sbb-begrippencontract.md), [ADR-004](adr-004-begrippenketen.md),
[ADR-006](adr-006-generieke-begrippen.md), [PLAN](../PLAN.md), skill [`references/relaties.md`](../../.claude/skills/wetsanalyse/references/relaties.md)
en [`references/begrippen.md`](../../.claude/skills/wetsanalyse/references/begrippen.md).

**Aanleiding.** In werkgebied *Termijnen* op acceptatie liep de analyse tot en met de begrippen: 14 bronnen, 212
beoordeelde elementen, 9 geaccordeerde begrippen. De gebruiker stelt dat dit niet het eind van de methode is: op basis
van de annotaties stel je **afleidingsregels** op, met begrippen als invoer en één begrip als uitvoer. Dat kan Lex nu
niet. Dit document legt uit wat de methode daarover zegt, toetst het op Termijnen, en stelt een gefaseerde aanpak voor.

**Afbakening tegenover twee andere onderzoeken.** Welke formuleringen een begrip krijgen en waar NL-SBB knelt, is het
onderwerp van een parallel onderzoek (dekking en begrippenketen); de kleuren en het diagram per bepaling in het rapport
van een ander. Dit plan gaat over de stap ná de begrippen, en verwijst naar die twee waar het raakt (§5).

Broncodes volgen [`references/bronnen.md`](../../.claude/skills/wetsanalyse/references/bronnen.md): M01 is het boek, M02
de Handleiding, M03 de Leidraad, M04 de Rijksspecificatie. M01–M03 zijn materiaal van derden en staan hier alleen in eigen
woorden, met vindplaats.

## 1. Kern

1. **Afleidingsregels zijn deelactiviteit 3b, niet RegelSpraak.** De methode kent twee lagen. In activiteit 3 maak je
   per afleidingsregel een begrip ("bepalen X") en schrijf je de regel in natuurlijke taal met de begrippen die er al
   zijn: één uitvoer, de invoer, de bewerking en de voorwaarden (M01 h.3 stap 3b; M02 §3.5.2b; M03 deelactiviteit 3b).
   Pas in activiteit 6 (het kennismodel) komen het feitmodel (feittypen, rollen, beperkingsregels) en het regelmodel
   in RegelSpraak (M01 h.3 stap 6b–c). **De grens van de scope ligt dus tussen 3b en 6**, niet tussen 3a en 3b.
2. **De gebruiker heeft gelijk.** Een begrip is in de methode geen eindproduct maar een bouwsteen: van de regels, het
   gegevensmodel en het proces (M02 §3.5.2a, *het belang van begrippen*). Negen begrippen voor een werkgebied dat over
   rekenen met termijnen en tijdstippen gaat, zonder één begrip voor wat er berekend wordt, is een halve activiteit 3.
3. **De grondstof ligt er grotendeels, maar is niet af.** ADR-011 legde het regelskelet al vast als grondstof voor 3b,
   en het rapport toont het al per afleidingsregel. In Termijnen zijn de afleidingsregels gemarkeerd, maar hun relaties
   zijn alleen onbeoordeelde voorstellen van de keten, de belangrijkste regel heeft er geen, en de begrippen voor invoer
   en uitvoer ontbreken (§4.3).
4. **Wat ontbreekt is een regel als eigen object.** Er is geen plek voor "bepalen X" met zijn uitvoer- en invoerbegrippen,
   zijn voorwaarden, zijn plaats in een keten van regels en zijn voorbeeldreeks. Het artefact `regels` is sinds AF alleen
   gereserveerd.

## 2. De methode in eigen woorden

### 2.1 Waar 3b staat in de reeks

De zes stappen van het boek (M01 h.3 §3.3) zijn: werkgebied, structuur, betekenis, valideren, ontbrekend
uitvoeringsbeleid, kennismodel. De Handleiding en de Leidraad noemen ze activiteiten 1–6 en splitsen activiteit 3 in vier
deelactiviteiten (M02 §3.5.2; M03 tabel analyseresultaten, nr. 14–17):

- **3a** begrippen maken: naam, definitie, voorbeelden, eigenschappen en relaties;
- **3b** afleidingsregels maken: de berekeningen, beslissingen, specialisaties en voorwaarden uit de wet in een vast
  taalpatroon vastleggen, met de begrippen in samenhang;
- **3c** de juridische scenario's aanvullen (in dit platform de skill wetsuitvoering, niet wetsanalyse);
- **3d** begrippen en regels relateren aan de bronnen.

De stappen lopen niet strikt na elkaar. De Handleiding beschrijft een lus per diagram (M02 §3.4, *Iteraties vanaf
activiteit 2 tot en met 6*): je tekent rond een centrale klasse het diagram van gemarkeerde formuleringen (2c), en voor
elke formulering in dat diagram maak je dan het begrip en, waar het speelt, de afleidingsregel die dat begrip afleidt
(3), valideer je (4), signaleer je ontbrekend beleid (5) en neem je het op in het kennismodel (6). Daarna het volgende
diagram. Zo werk je alleen met formuleringen die aan een centrale klasse hangen.

### 2.2 De tussenproducten

In de volgorde waarin ze ontstaan:

1. **De markeringen** met hun klasse (2a–b).
2. **Het diagram per centrale klasse** (2c; M02 §3.4 deelactiviteit c): de brontekst, de markeringen met hun klasse en
   de verbanden ertussen, rond een rechtsbetrekking, rechtsfeit, afleidingsregel of voorwaarde. Het is een
   tussenresultaat. Zodra de begrippen er zijn, kun je hetzelfde diagram tekenen met de begrippen in plaats van de
   formuleringen (M02 §3.4, *Toelichting op het diagram*). Op het platform: de relaties van ADR-011 en de diagrammodus.
3. **Het regelskelet** is een projectkeuze, geen woord uit de methode: het deel van het diagram rond een afleidingsregel
   (uitvoer, invoer op volgorde, operatoren met operanden, voorwaarden, parameters met waarde, tijd, uitzonderingen).
   Het is precies de opbouw die het boek aan een afleidingsregel geeft (M01 h.3 stap 6c; M01 h.4 §6 *Relatie met
   andere klassen*).
4. **De begrippen** (3a), ook voor operatoren (een generiek begrip "min" voor "verminderd met"), voor tussenresultaten
   die een berekening nodig heeft, en een begrip "bepalen X" voor elke afleidingsregel zelf (M01 h.3 stap 3a en 3b;
   M01 h.6, de bijdrage-inkomens in de Zvw; M02 §3.5.2a, *vaste opbouw begripsnaam*: bij een afleidingsregel een
   werkwoord vooraan).
5. **De tabel met afleidingsregels** (3b; M03 nr. 15; M02 §3.5.5, het praktijkvoorbeeld zorgtoeslag): per regel de naam
   ("Bepalen verzekerde zorgtoeslag"), de regel in een vast taalpatroon met de begrippen, en het afgeleide begrip. Een
   afgeleid begrip is in de volgende regel weer invoer: zo ontstaat een **afleidingshiërarchie** (M01 h.4 §6).
6. **De voorbeeldreeksen** (4b; M01 h.3 stap 4a, tabel 3.4; M03 nr. 20): per regel een reeks waarden voor de invoer
   met de uitkomst die de regel geeft, en per geval de vraag of die uitkomst juridisch juist is en zich mag voordoen. Met
   nul, negatief en onbekend erbij. Zo vind je de gevallen die de regel niet dekt; later zijn het testgevallen.
7. **Ontbrekend uitvoeringsbeleid** (5; M01 h.3 stap 5; M03 nr. 21): elke interpretatie of invulling die een regel nodig
   heeft en die nergens is vastgelegd.
8. **Het kennismodel** (6): de begrippen, het **feitmodel** (de begrippen in samenhang: feittypen met rollen, een
   communicatiepatroon, beperkingsregels; Fact Based Modeling), het **regelmodel** (de regels in RegelSpraak, met de
   relaties uit het feitmodel erin: "van een belastingschuldige over een jaar") en het **procesmodel** (rechtsfeiten als
   gebeurtenissen; BPMN). De Handleiding noemt het feitmodel ook gegevensmodel. **Buiten de scope.**

### 2.3 Wat een afleidingsregel is

- **Soort** (M04 H2:71; M01 h.4 §6): een *rekenregel* (hoogte, duur, aantal, een datum), een *beslisregel* (ja of nee:
  bestaat het recht, is iets invorderbaar) of een *specialisatie* (hoort dit subject of object tot een groep; "wordt
  beschouwd als", "zijn"). De Leidraad noemt ook een beperking op grond van kenmerken (M03 nr. 15, 20).
- **Uitvoer**: precies één. Een variabele (bij een rekenregel de uitkomst, bij een beslisregel waar of onwaar), een
  rechtssubject of rechtsobject (bij een specialisatie), en op het platform ook een tijdsaanduiding (een vervaldag;
  ADR-011).
- **Invoer**: variabelen, parameters, subjecten, objecten, tijdsaanduidingen, en de uitvoer van een andere regel.
- **Bewerking**: de operatoren, met de volgorde van de operanden waar die de uitkomst verandert.
- **Voorwaarden**: deel van de regel (M01 h.4 §5 en §6), elk met wat vergeleken wordt en hoe.

**In 3b zijn invoer en uitvoer begrippen, geen formuleringen** (M01 h.3 stap 3b; M02 §3.5.2b). Het boek laat dat zien
op art. 3.110 Wet IB 2001: een begrip voor de regel ("bepalen belastbare inkomsten uit eigen woning"), de uitvoer het
begrip *belastbare inkomsten uit eigen woning*, de invoer de begrippen *voordelen uit eigen woning* en *op die voordelen
drukkende aftrekbare kosten*, en voor "verminderd met" het begrip *min*. De regel luidt dan, in het vaste patroon:
*uitvoer* moet berekend worden als *invoer 1* **min** *invoer 2*. Een beslisregel krijgt het patroon "X is Y indien aan
alle (of één van de) volgende voorwaarden is voldaan", met de voorwaarden als lijst (M02 §3.5.5).

### 2.4 Begrippen, variabelen en parameters tegenover de regel

- Een **variabele** is in activiteit 2 een geclassificeerde formulering; in 3a krijgt zij een begrip; in 3b is dat begrip
  invoer of uitvoer. Of een variabele bepaald of bepalend is, volgt uit de regels: heeft haar begrip een regel die het
  afleidt, dan is het een uitvoer.
- Een **parameter** is invoer met een waarde die voor allen gelijk is over een periode; zijn begrip draagt de eenheid, de
  waarde komt uit de parameterwaarde (vaak in lagere regelgeving). In de regel staat het begrip van de parameter, niet
  het getal.
- Een **operator** krijgt een generiek begrip dat elke formulering met dezelfde bewerking deelt ("min", "plus", "en",
  "of", "groter dan"). Datumrekenen ("een maand na", "aan het eind van de maand") hoort er in deze casus bij.
- Een **voorwaarde** krijgt in de methode meestal geen eigen begrip maar een omschrijving "indien …", die in de regel
  staat (zie het parallelle onderzoek naar begrippen per klasse).
- **Eén formulering kan meer begrippen dragen** als er een berekening bij komt: dezelfde term vóór en ná de bewerking
  zijn verschillende begrippen (M01 h.3 stap 3a, het bijdrage-inkomen in drie leden). Een regel maakt dus soms een
  begrip nodig dat in 3a niet opviel. 3a en 3b lopen daarom samen, niet na elkaar.

### 2.5 Waar RegelSpraak begint

De regel van 3b gebruikt al woorden die op RegelSpraak lijken ("moet berekend worden als", "min"), omdat de methode en
RegelSpraak uit dezelfde traditie komen. Wat RegelSpraak toevoegt, en wat buiten deze scope blijft:

- **het feitmodel**: van wie of wat een waarde is ("de … van een belastingschuldige over een jaar"), feittypen met rollen,
  beperkingsregels (één waarde per jaar);
- **typen**: datatype, domein en eenheid van elk begrip, kenmerk tegenover attribuut;
- **een vaste syntaxis** met resultaatsoorten, regelversies en geldigheid, ingebouwde expressies (datumrekenen,
  aggregatie, afronding) en beslistabellen;
- **uitvoerbaarheid** (een interpreter of codegenerator).

Een regel in 3b is implementatieonafhankelijk en hoeft niet uitvoerbaar te zijn. Zij moet wel zo precies zijn dat een
jurist haar met een voorbeeldreeks kan toetsen.

## 3. Wat er op het platform ligt

- **Activiteit 2c (ADR-011).** De catalogus kent `uitvoer`, `invoer` (met volgorde), `operator_in`, `operand` (met
  volgorde), `voorwaarde`, `waarde`, `kenmerk`, `tijd`, `uitzondering_op` en `toepassing`. Opslag, projectie, review in
  het paneel en de diagrammodus per centrale klasse (`frontend/lib/graaf/weergave.ts`) zijn gebouwd. De graafcontrole
  meldt een afleidingsregel zonder precies één uitvoer of zonder invoer, diagnostisch.
- **De relatievoorstellen** (`tools/graph-qa/agent/jas_pipeline/relaties.py`, proefvlag `RELATIE_VOORSTELLEN`, op
  acceptatie aan): stap 1–4 van ADR-011 (uitvoer en invoer uit de functiedetector, waarde, operator met operanden,
  aanhechting van een voorwaarde). Kenmerk, tijd, rollen, `uitzondering_op` en `toepassing` stelt de keten niet voor.
- **Het regelskelet in het rapport** (`api/app/werkgebied_export.py::_regelskelet`, `werkgebied_rapport.Regelskelet`):
  per afleidingsregel uitvoer, invoer, operatoren, voorwaarden, parameters, tijd, uitzonderingen en toepassing, met wat
  ontbreekt. Het skelet staat per markering, met formuleringen; er is geen overzicht van de regels van het werkgebied.
- **Begrippen (ADR-003/004/006)**: een slank NL-SBB-begrip zonder klasse en zonder soort (P15), betekenisgroepen van
  minstens twee formuleringen, operatoren en parameters uitgesloten (`geen_begrip.yaml`), begripsrelaties met type
  (kwalificatie, inclusie, uitsluiting, hiërarchie, verwant, opvolging). Een begrip "bepalen X" ontstaat niet: een
  afleidingsregel is een zin en doet niet mee aan de groepering.
- **De tab *Samenhang*** toont de begrippengraaf (koppelingen en begripsrelaties); de graaf per bepaling toont de
  relaties tussen markeringen. Geen van beide kent een regel.
- **Het artefact `regels`** is gereserveerd in `gesprek_contracts.Artefact` en heeft geen versie, route of paneel.
- **De skill** zegt in *Grenzen* dat ze activiteit 1 tot het begin van 3 dekt; `relaties.md` noemt het regelskelet de
  grondstof voor 3b en laat relaties tussen regels aan 3b.

## 4. De proef: Termijnen op papier

Gelezen met de acceptatie-MCP, alleen lezend: het werkgebied, de weergave van IW 1990 art. 9 lid 5 en 6, art. 24 lid 1
(slottekst) en lid 2, Leidraad 24.3, en de officiële tekst van art. 9 lid 7. De wettekst hieronder is letterlijk; de regels
zijn een **reconstructie** (een concept van mij, niet beoordeeld). Begrippen in *cursief*; met † gemarkeerd wat nog geen
begrip is in Termijnen.

### 4.1 De afleidingsregels

**AR1 — Bepalen aantal termijnen voorlopige aanslag gedagtekend in het belastingjaar** (rekenregel; art. 9 lid 5, eerste
volzin; via art. 72 Mbw ook voor winstaandeel, een interpretatie die open staat)

- Bron: "invorderbaar in zoveel gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is
  vermeld, nog maanden van het jaar overblijven".
- Uitvoer: *aantal termijnen*†. Invoer: *maand van de dagtekening*† (uit *dagtekening van het aanslagbiljet*), *jaar
  waarover de aanslag is vastgesteld*†.
- Regel: Het *aantal termijnen* van een *voorlopige aanslag* moet berekend worden als het *aantal maanden van een jaar*†
  **min** het *maandnummer van de dagtekening van het aanslagbiljet*†, indien de *dagtekening van het aanslagbiljet* ligt
  in het *jaar waarover de aanslag is vastgesteld*.

**AR2 — Bepalen invorderbaar in termijnen** (beslisregel; art. 9 lid 5, derde volzin)

- Bron: "Indien de toepassing van de eerste volzin niet leidt tot meer dan één termijn, vindt het eerste lid
  toepassing."
- Uitvoer: *invorderbaar in termijnen*† (waar/onwaar). Invoer: de uitvoer van AR1.
- Regel: Een *voorlopige aanslag* is *invorderbaar in termijnen* indien zijn *aantal termijnen* **groter dan** één is;
  anders geldt lid 1. "Vindt het eerste lid toepassing" is geen afleidingsregel maar een relatie `toepassing` naar lid 1.

**AR3 — Bepalen vervaldag termijn** (rekenregel, uitvoer een tijdstip; art. 9 lid 5, tweede volzin)

- Bron: "De eerste termijn vervalt één maand na de dagtekening van het aanslagbiljet en elk van de volgende termijnen
  telkens een maand later."
- Uitvoer: *vervaldag van een termijn*†. Invoer: *dagtekening van het aanslagbiljet*, *volgnummer van de termijn*†.
- Regel: De *vervaldag van een termijn* moet berekend worden als de *dagtekening van het aanslagbiljet* **plus** zoveel
  maanden als het *volgnummer van de termijn*.

**AR4 — Bepalen termijnbedrag** (rekenregel; art. 9 lid 5 en 6, "gelijke termijnen")

- Uitvoer: *termijnbedrag*†. Invoer: *bedrag van de aanslag*†, *aantal termijnen*.
- Regel: Het *termijnbedrag* moet berekend worden als het *bedrag van de aanslag* **gedeeld door** het *aantal
  termijnen*.
- Ontbrekend beleid: de afronding. € 300.000 in zeven termijnen is € 42.857,142…; waar de restcent landt, staat niet in de
  gelezen bronnen.

**AR5 — Bepalen aantal termijnen en vervaldag bij een uit te betalen bedrag** (rekenregels; art. 9 lid 6)

- Bron: "met inbegrip van de maand die in de dagtekening van het aanslagbiljet is vermeld" en "De eerste termijn vervalt
  aan het eind van de maand van de dagtekening".
- AR5a: *aantal termijnen* = *aantal maanden van een jaar* **min** *maandnummer van de dagtekening* **plus** één.
- AR5b: *vervaldag van de eerste termijn* = de **laatste dag van** de *maand van de dagtekening*; elke volgende **plus** een
  maand.
- `uitzondering_op` naar lid 1 en lid 5 ("In afwijking van het eerste en het vijfde lid").

**AR6 — Bepalen uitbetaling in één keer** (beslisregel; Leidraad 9.3, beleid)

- Uitvoer: *uitbetaling in één keer*†. Invoer: *termijnbedrag*, de parameter *grensbedrag termijnuitbetaling*† met
  parameterwaarde € 49, en *beslag door een derde*†.
- Regel: Een voorlopige teruggaaf wordt *in één keer uitbetaald* indien het *termijnbedrag* **ten hoogste** het
  *grensbedrag termijnuitbetaling* is **en** er **geen** *beslag door een derde* ligt.

**AR7 — Bepalen tijdstip van verrekening** (rekenregel met uitzondering; art. 24 lid 1, slottekst)

- Bron, volzin 6: "In afwijking van artikel 4:93, derde lid, van de Algemene wet bestuursrecht geldt als tijdstip van
  verrekening de dagtekening van het aanslagbiljet waaruit van het te betalen bedrag blijkt."
- Bron, volzin 7: "In afwijking van de vorige volzin geldt met betrekking tot een verrekening van een termijn van een
  voorlopige aanslag als bedoeld in artikel 9, zesde en zevende lid, als tijdstip van verrekening het tijdstip waarop de
  desbetreffende termijn vervalt."
- Uitvoer: *tijdstip van verrekening*† (in Termijnen nu opgenomen in de definitie van *verrekening*; de groep is afgewezen
  met die reden). Invoer: *dagtekening van het aanslagbiljet*, en de uitvoer van AR3 of AR5b.
- Regel: Het *tijdstip van verrekening* is de *vervaldag van de termijn* indien het een termijn is van een *voorlopige
  aanslag* als bedoeld in art. 9 lid 6 of 7; anders de *dagtekening van het aanslagbiljet* waaruit het te betalen bedrag
  blijkt.
- **Afleidingshiërarchie**: AR7 heeft de uitvoer van AR3/AR5b nodig, die die van AR1/AR5a nodig heeft. Dat volgt vanzelf
  als dezelfde begrippen (*vervaldag van een termijn*, *aantal termijnen*) uitvoer van de ene en invoer van de andere zijn.

**AR8 — Bepalen verrekening mogelijk** (beslisregel; art. 24 lid 2 en lid 8, Leidraad 24.3)

- Bron (lid 2): "De verrekening is ook mogelijk ingeval de termijn, bedoeld in artikel 9, nog niet is verstreken, met dien
  verstande dat indien het betreft belastingaanslagen als bedoeld in artikel 9, vijfde en zevende lid, verrekening alleen
  mogelijk is met belastingaanslagen die op dezelfde belasting en hetzelfde tijdvak betrekking hebben."
- Uitvoer: *verrekening mogelijk*†. Regel: verrekening van een *belastingaanslag* als bedoeld in art. 9 lid 5 of 7 met een
  ander bedrag is mogelijk indien het andere bedrag betrekking heeft op **dezelfde** *belasting* **en hetzelfde** *tijdvak*.
  Lid 8 voegt toe dat dit ook geldt voor een voorlopige aanslag tot een negatief bedrag.
- Leidraad 24.3 beperkt het beleid: bij zo'n voorlopige aanslag verrekent de ontvanger alleen voor zover de
  betalingstermijnen zijn verstreken, behalve in de situaties van art. 10 lid 1 onderdeel b–d.

Wat **geen** afleidingsregel uit de wet is: hoeveel er per vervaldag wordt verrekend en wat er wordt uitbetaald. De
analyse leidt het af (op elke vervaldag van een negatieve termijn tegen wat er dan van de positieve aanslag vervallen en
open is), maar geen gelezen bepaling formuleert het als regel. Dat is in de methode **ontbrekend uitvoeringsbeleid**
(activiteit 5), en het onderzoekspunt "herberekenen of salderen" uit het rapport van Termijnen is daar het voorbeeld van.

### 4.2 De voorbeeldreeks (activiteit 4b, op papier)

Met het praktijkvoorbeeld als normaal geval en de rest als grensgevallen. "Juist?" is mijn lezing, niet beoordeeld.

- Positieve voorlopige aanslag, dagtekening 15 februari 2025, belastingjaar 2025: AR1 → 12 − 2 = 10 termijnen; AR2 → waar;
  AR3 → 15 maart tot en met 15 december; AR4 → € 100.000. Volgens het rapport van Termijnen schuift de laatste naar 31
  december (Leidraad 9.1); die bepaling zit niet in de bronselectie en is hier niet gelezen.
- Negatieve voorlopige aanslag, dagtekening 20 juni 2025: AR5a → 12 − 6 + 1 = 7; AR5b → 30 juni, dan telkens een maand
  later; AR4 → € 42.857,14 met een restcent die nergens staat; AR7 → het tijdstip van verrekening van elke negatieve
  termijn is zijn vervaldag.
- Dagtekening 10 november 2025 (positief): AR1 → 1; AR2 → onwaar, dus lid 1. Dagtekening in december: AR1 → 0; AR2 →
  onwaar. Klopt met de derde volzin.
- **Dagtekening in december bij een negatieve aanslag**: AR5a → 1 termijn aan het eind van december. Lid 6 kent geen
  "meer dan één"-clausule zoals lid 5; of lid 6 dan nog geldt of terugvalt op lid 1, beslist de tekst niet. Een vraag voor
  de jurist.
- Dagtekening 30 januari 2025 (positief): AR3 → "één maand na" 30 januari valt in februari niet op de 30e. Het
  datumrekenen ligt niet vast in de wet; het rapport noemt Leidraad 9.5 (niet in de selectie). Ontbrekend beleid of een
  ontbrekende bron.
- Dagtekening vóór het belastingjaar: AR1 geldt niet (voorwaarde niet vervuld); dan geldt art. 9 lid 7: zoveel termijnen
  als het jaar maanden heeft, de eerste aan het eind van de eerste maand. **Lid 7 staat niet in de bronselectie**, terwijl
  art. 24 lid 1 (slottekst) en lid 2 ernaar verwijzen. De proef vindt zo een gat in de bronselectie dat de annotatie niet
  vond.
- Negatieve termijn van € 40, geen beslag: AR6 → in één keer. Met beslag: termijnen.
- Bedrag van de aanslag onbekend: AR4 → onbekend, niet nul.

### 4.3 Kan het met wat er in Termijnen ligt?

**Ja als grondstof, nee als product.** Wat wel lukt: elke regel hierboven hangt aan een gemarkeerde, beoordeelde
afleidingsregel, en de formuleringen van invoer en uitvoer zijn grotendeels gemarkeerd. Wat niet lukt:

- **Geen beoordeelde relatie.** Op de gelezen bepalingen staan 25 relaties, alle 25 `voorgesteld` door de keten. De jurist
  rondde de lagen af zonder ze te beoordelen; afronden vraagt het ook niet (ADR-011, *Gevolgen*).
- **De belangrijkste regel heeft geen skelet.** De slotzin van art. 24 lid 1 (AR7, de kern van het antwoord) heeft nul
  relaties: geen uitvoer, geen invoer, geen `uitzondering_op` naar de vorige volzin.
- **De datumregels hebben geen uitvoer.** De vervaldagregels van lid 5 en 6 (AR3, AR5b) krijgen geen `uitvoer`; de keten
  stelt alleen een uitvoer voor waar de functiedetector een variabele ziet.
- **Tekstuele relaties ontbreken.** "In afwijking van" (lid 5, lid 6, beide volzinnen van de slottekst) en "vindt het
  eerste lid toepassing" (lid 5) zijn geen `uitzondering_op` en `toepassing`. Het laatste is zelfs als Afleidingsregel
  gemarkeerd.
- **Voorstellen naar afgewezen elementen.** In lid 5 wijzen operand-voorstellen naar "na" en "de dagtekening van het
  aanslagbiljet", die de jurist als Operator en Variabele afwees. En "niet" en "meer dan" zijn elkaars operand: een kring.
- **De begrippen voor invoer en uitvoer ontbreken.** Van de negen begrippen is alleen *dagtekening van het aanslagbiljet*
  invoer van een regel; *aantal termijnen*, *vervaldag van een termijn*, *termijnbedrag* en *tijdstip van verrekening*
  bestaan niet. De groepen "het jaar", "de maand" en "het tijdvak" zijn afgewezen als kalendereenheid of te algemeen,
  terwijl het precies de invoer van AR1, AR5 en AR8 is. Een begrip "bepalen …" kan nergens ontstaan.
- **Een bron mist.** Art. 9 lid 7 is nodig voor AR7 en AR8 maar is niet geselecteerd.

## 5. De gaten in de keten

### 5.1 Data

- **D1 — Een regel als eigen object** (tabel per werkgebied, zoals begrippen): naam ("bepalen X", als begrip of als veld),
  soort (rekenregel, beslisregel, specialisatie), uitvoer (precies één begrip), invoer (begrippen op volgorde), de bewerking
  (operatorbegrippen op volgorde), voorwaarden (een omschrijving "indien …" plus de markeringen waarop ze rust), de
  dragende markeringen (de afleidingsregel en de elementen van haar skelet, met bewijsstand zoals bij een
  begripskoppeling), status, revisie, audit en herkomst. De regeltekst wordt **afgeleid** uit die delen, niet vrij
  getypt; een toelichting mag vrij.
- **D2 — De afleidingshiërarchie wordt afgeleid, niet opgeslagen**: een regel volgt op een andere als haar invoerbegrip de
  uitvoer van die ander is. Twee regels met dezelfde uitvoer zonder elkaar uitsluitende voorwaarden zijn een signaal.
- **D3 — Voorbeeldreeksen** per regel: rijen met invoerwaarden, de uitkomst en het oordeel (juist, onjuist, mag zich niet
  voordoen), met een verwijzing naar het praktijkvoorbeeld van het werkgebied waar dat geldt.
- **D4 — Ontbrekend beleid** als eigen soort open punt, aan een regel of een markering gekoppeld (afronding, restcent,
  datumrekenen aan het eind van de maand).
- **D5 — De soort van een begrip** (bedrag, aantal, datum, ja/nee, tekst) als optionele eigenschap. Een regel zonder soort
  kan zijn invoer niet toetsen; dit raakt P15 (zie het parallelle onderzoek, dat dezelfde eigenschap om andere redenen
  voorstelt).
- **D6 — Projectie.** Een regel als knoop in de begrippengraaf van het werkgebied, met uitvoer en invoer naar de
  begrippen. Geen RegelSpraak, geen feittype. Pas na D1–D3.

### 5.2 Agent

- **A1 — Een betrouwbaar skelet** (de relatieketen, activiteit 2c): uitvoer naar een tijdsaanduiding bij een datumregel,
  `uitzondering_op` bij "in afwijking van" en `toepassing` bij "vindt toepassing" (tekstueel, dus deterministisch), en geen
  voorstel meer naar een verworpen element of in een kring. ADR-011 stap 5–7 (kenmerk, tijd, rollen) volgen daarna.
- **A2 — Begrippen voor het skelet**: elk eindpunt van een afleidingsregel zonder begrip wordt een begripsvoorstel, ook
  als het één keer voorkomt; een vaste set generieke operatorbegrippen (ADR-006), inclusief datumrekenen; voor elke
  afleidingsregel een voorstel "bepalen <uitvoer>". Dit overlapt met het voorstel "elk element een begrip" van het
  parallelle onderzoek; het moet één mechanisme worden, niet twee.
- **A3 — Een regels-agent** (ADR-005-vorm: één taak per beurt): uit een skelet met begrippen een conceptregel maken,
  **deterministisch** (de taalpatronen van de methode, de delen in de volgorde van het skelet). Een strikte modelstap
  alleen waar de code niet kan beslissen (de naam van een tussenresultaat, de soort bij twijfel), met de fragmenten
  waarop ze rust. Lex stelt voor; de jurist neemt over, past aan of wijst af.
- **A4 — Een voorbeeldreeks voorstellen**: de gevallen deterministisch uit de regel (normaal, elke voorwaarde niet vervuld,
  de grens van elke vergelijking, nul, onbekend) en uit het praktijkvoorbeeld. De uitkomst stelt Lex niet stil vast:
  zonder uitvoerbare regel is elke uitkomst een voorstel met de stappen erbij, en het oordeel is van de jurist.
- **A5 — Lex leest regels** in het gesprek ("welke regel bepaalt de vervaldag?") via de leesroute, op wat is vastgelegd.

### 5.3 UI

- **U1 — Het diagram per afleidingsregel** in de boekvorm: uitvoer bovenaan, invoer en parameters, operatoren met volgorde,
  voorwaarden, uitzonderingen. Dit sluit aan op het diagram per bepaling waar de sessie *annotatieweergave* aan werkt;
  dit plan vraagt daar alleen dat de afleidingsregel een eigen modus houdt en dat het diagram later met begrippen kan
  (M02 §3.4).
- **U2 — Relaties in bulk beoordelen** vanuit dat diagram, met de afronding van een laag als moment om te zeggen: "drie
  afleidingsregels hebben nog geen beoordeeld skelet".
- **U3 — Een tab *Regels*** in het werkgebied: de lijst (naam, regel, afgeleid begrip), de hiërarchie en per regel de
  voorbeeldreeks en de open punten. Het artefact `regels` opent naast het gesprek; de werkgebiedpagina is raadplegen
  (F3e), net als bij begrippen.
- **U4 — Op de begripskaart** zichtbaar welke regel het begrip afleidt en welke het gebruikt.

### 5.4 Rapport

- **R1 — Een hoofdstuk *Afleidingsregels*** (na *Begrippen*): per regel naam, soort, regel, afgeleid begrip, bron, de
  hiërarchie en de voorbeeldreeks. Lijsten, geen tabellen, zoals de rest van het rapport.
- **R2 — Het skelet per markering blijft**, met een verwijzing naar de regel die erop rust.
- **R3 — Ontbrekend beleid** als eigen deel, naast de onderzoekspunten.

### 5.5 Methode en skill

- **M1 — De scope verschuift.** *Grenzen* in `SKILL.md`, PLAN en de projectroot-`CLAUDE.md` zeggen "het begin van
  activiteit 3". Met 3b erbij wordt dat "activiteit 1 tot en met 3b, en 4b en 5 voor zover ze aan een regel hangen";
  RegelSpraak, het feitmodel en het procesmodel blijven buiten.
- **M2 — Een reference `afleidingsregels.md`** in de skill, in eigen woorden uit M01 h.3 stap 3b/4a/6c en M02 §3.5.2b en
  §3.5.5, met een broncode P21 in het beslisregister. Dit is methode-uitleg buiten de runtime-markers; een wijziging van
  de tekst tussen de markers vraagt een meting (P19).

## 6. Gefaseerd voorstel

Elke fase levert iets bruikbaars op en kan na de vorige stoppen. Volgorde op wat de jurist het eerst mist.

- **Fase 0 — Besluit en methode** (docs, skill): de scope (M1), een ADR voor het regelartefact (D1–D4, de grens met
  RegelSpraak), de reference (M2). Geen code.
- **Fase 1 — Het skelet betrouwbaar** (graph-qa, api, frontend): A1, U2, en een signaal per werkgebied "regelskelet
  compleet / incompleet" per afleidingsregel. Meten met de maat *regelskelet-compleet* van ADR-011 op WA TRM H1 en
  Termijnen. Dit is ook zonder 3b winst: het 2c-diagram wordt er pas mee wat de methode bedoelt.
- **Fase 2 — Begrippen voor regels** (graph-qa, api; samen met het spoor "elk element een begrip" uit het parallelle
  onderzoek): A2 en D5.
- **Fase 3 — De regel als object** (api, BFF, frontend): D1, D2, U3, U4, het artefact `regels`, R1, R2. De jurist kan een
  regel met de hand maken uit een skelet; Lex nog niet.
- **Fase 4 — Lex stelt regels voor** (graph-qa): A3, A5. Eerst deterministisch, de modelstap pas na een meting.
- **Fase 5 — Valideren** (api, graph-qa, frontend): D3, D4, A4, R3. De voorbeeldreeks en het ontbrekende beleid.
- **Later, buiten dit plan**: D6, het feitmodel, RegelSpraak, het procesmodel en de koppeling met juridische scenario's
  (skill wetsuitvoering).

Een meting: Termijnen en WA TRM H1 als ontwikkelset (de regels die het WA TRM-team in 3b opstelde, zijn niet
gevalideerd en zijn geen meetlat; zie ADR-011, *Meten*). Een blinde set vraagt een werkgebied met een rekenregel en
een beslisregel dat een jurist zelf uitwerkt.

## 7. Open vragen voor de gebruiker

1. **Scope**: hoort 3b (en de voorbeeldreeks van 4b) bij het platform? Dan verandert *Grenzen* in de skill en in
   `CLAUDE.md`.
2. **Poort**: mag een regel geaccordeerd worden als haar skelet nog voorstellen bevat, of eist accorderen beoordeelde
   relaties en beoordeelde begrippen voor uitvoer en invoer? (Mijn voorstel: beoordeelde begrippen ja, het skelet als
   signaal.)
3. **Voorwaarden**: een omschrijving "indien …" in de regel (de methode), of ook een begrip? (Mijn voorstel: de
   omschrijving, rustend op de markering.)
4. **Soort van een begrip** (D5): een beperkte terugkeer van een eigenschap die P15 op 13 nov 2026 liet vallen?
5. **Beleid als bron van een regel**: AR6 en de beperking in AR8 komen uit de Leidraad. Staan regels uit beleid in
   dezelfde lijst, met hun brontype zichtbaar, of apart? (PLAN open keuze 7, het nog open deel.)
6. **Voorbeeldreeks**: stelt Lex ook de uitkomst voor, of alleen de gevallen?
7. **Datumrekenen**: generieke operatorbegrippen als "plus maanden" en "laatste dag van de maand" in 3b, of is dat al
   RegelSpraak?
8. **Van wie is een waarde** ("van een belastingschuldige over een jaar"): het boek voegt dat pas in stap 6 toe. In 3b
   weglaten, of de relatie `kenmerk` alvast in de regeltekst tonen?
9. **Termijnen zelf**: art. 9 lid 7 opnemen, de relaties van de afleidingsregels beoordelen en de vier ontbrekende
   begrippen maken? Dat is het werk van een jurist op acceptatie, geen bouwwerk.

## 8. Bevindingen voor elders

- De relatieketen stelt operanden voor naar verworpen elementen en legt een kring tussen twee operatoren (IW 9 lid 5).
  Hoort bij fase 1 (A1).
- De bronselectie van Termijnen mist art. 9 lid 7 IW 1990, waarnaar art. 24 lid 1 (slottekst) en lid 2 verwijzen. Een
  signaal voor de zoeker (verwijzingen vanuit opgenomen bepalingen).
- Afronden van een laag kan met alleen onbeoordeelde relaties; de werkplek telt ze, maar het rapport van Termijnen noemt
  ze niet. Een kleine zichtbaarheidsfix.
