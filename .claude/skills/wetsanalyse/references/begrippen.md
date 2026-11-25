# Begrippen

Hoe Lex bij activiteit 3 met begrippen werkt: wat een begrip in een werkgebied is, wat een goede
definitie is en hoe voorbeelden en relaties erbij horen. Dit is methode-uitleg, geen agentrol: graph-qa laadt deze
tekst niet in een prompt (besluit 7 nov 2026). De begrippenketen draagt deze regels in code en toetsen (ADR-004), en de
modelstappen van de begrippen-agent hebben elk hun eigen strakke opdracht. In eigen woorden, op basis van het
begrippenkader van de Rijksspecificatie (H3), NL-SBB (ADR-003) en de begrippenketen (ADR-004).
Broncodes verwijzen naar [bronnen en beslisregister](bronnen.md).

## Begrippen

Grondslag: M01, M04, P15.

Een begrip is een analyse-uitkomst, geen wettelijke definitie: het brengt de formuleringen samen die in het werkgebied hetzelfde aanduiden, met de passages waarop het rust. **Een begrip zonder grondslag in een annotatie bestaat niet.** Het ontstaat uit minstens één gemarkeerde passage en houdt er altijd minstens één: de laatste passage gaat er niet af, en wie het begrip niet meer nodig heeft, verwijdert het. Een tussenresultaat van een berekening of beslissing krijgt wél een begrip, ook als de tekst het niet met een eigen formulering noemt: de uitvoering moet elke stap kunnen uitvoeren en uitleggen, en het oude tussenresultaat blijft bewaard (M01 §2.2.2 en h.6; M02 §1.2). Zo'n begrip rust op de markering van de afleidingsregel die het afleidt, met de rol `afgeleid`; daarna kijk je opnieuw in de tekst of er toch een formulering is die het aanduidt. Een element dat een regel nodig heeft maar dat de tekst open laat, krijgt ook een begrip op de formulering waarvoor het nodig is, en de interpretatie signaleer je als ontbrekend uitvoeringsbeleid (M01 h.7). Het platform dwingt de grondslag af (`api/app/begrip_store.py`: 422 `geen_passage`, 409 `laatste_passage`, 422 `geen_afleidingsregel`). Het volgt NL-SBB en draagt alleen een term (naam en alternatieve termen), een definitie, een uitleg, een toelichting (de grenzen of het gebruik) en voorbeelden. Daarnaast heeft het een klasse en, bij een variabele of parameter, een waardebereik (P15, bijgesteld 24 nov 2026). De klasse stel je niet voor: ze komt uit de markeringen waarop het begrip rust, en de analist verlegt haar alleen met een reden. Een gelijk woord bewijst geen gelijke betekenis; sterk bewijs is wat de wet zelf vastlegt – een begripsbepaling binnen haar bereik, of een verwijzing. Houd de wettelijke definitie en het vastgelegde begrip uit elkaar.
Een definitie noemt het soortbegrip en het onderscheidende kenmerk, dekt wat de passages aanduiden en niet meer, gebruikt de naam van het begrip niet als eigen soortbegrip en is geen rekenregel. De herkomst telt: letterlijk uit de bron gaat voor samengesteld uit bronfragmenten, en dat gaat voor zelf geformuleerd. Een geformuleerde definitie is altijd een voorstel om te beoordelen, met de fragmenten waarop ze rust.
Lees een begrip in zijn context: de andere leden van het artikel, een definitie of kwalificatie elders, een bepaling waarnaar verwezen wordt. Beginnen bepalingen gelijk en verschillen ze daarna (zoals "bij herziening van … met een positief bedrag tot …"), kies dan een algemene definitie die voor alle varianten geldt, of een specifiek begrip met een eigen naam; een toepassingsgeval is niet de definitie van het algemene begrip. Een definitie geeft de wezenlijke kenmerken en, waar de tekst het zegt, het doel – geen rechtsgevolg, geen voorwaarde uit één lid en geen afleiding: wat de wet met een term berekent of verrekent, is een eigen begrip ("bepalen …"), en een woord dat in één bepaling door een berekening verandert, kan daar twee begrippen dragen. Een kwalificatie van een samenstelling ("geldt als het te betalen bedrag aan belasting") definieert de kale term niet. Is er onvoldoende bewijs, zeg dan wat er ontbreekt in plaats van een definitie te raden, en noem open vragen.
Voorbeelden toetsen een definitie. Ze rusten op een overgenomen definitie, of – bij een begrip dat in één keer wordt uitgewerkt – op de voorgestelde definitie, en vervallen als die niet of anders wordt overgenomen; een grensgeval of tegenvoorbeeld hoort erbij. Elk voorbeeld toetst één kenmerk van de definitie en zegt of het het begrip toetst of iets anders (een scenario, een voorwaarde, een rechtsgevolg); twee voorbeelden die alleen in getallen of namen verschillen, toetsen hetzelfde. Een betekenisverschil leg je uit met de context van beide begrippen, niet met het woord alleen; waar de grens ligt, hoort in de toelichting.
Relaties houden hun type – kwalificatie, inclusie, uitsluiting, soort van, verwant – en hun richting. Een begrip met een andere betekenis wordt een opvolger, het oude wordt vervangen. Ligt vast per wanneer de betekenis verandert, geef die datum dan mee: de opvolger geldt vanaf die dag en het oude begrip tot en met de dag ervoor (M01 h.3 stap 3a; M02 §3.5.2a). Die geldigheid is de juridische datum, niet de dag waarop iemand het begrip verving. Het begrippenkader volgt NL-SBB.
Lex stelt voor; de analist neemt over, past aan of wijst af, en alleen de analist accordeert.

## Welke formulering krijgt wat

Grondslag: M01 h.3 stap 3a en 3b, h.4 punt 16, h.6 en h.7; M02 §3.4.2c, §3.5.1 en §3.5.2; M03 hoofdactiviteit 2 en 3; P21. In
eigen woorden. De verwachting per klasse staat ook als data in `../begripverwachting.json`; de dekking van een werkgebied
telt ermee.

Elke formulering die in activiteit 2 is geclassificeerd, krijgt in activiteit 3a een begrip: een nieuw, of een bestaand
met dezelfde betekenis. De uitwerkingen in het boek laten zien dat dat voor bijna elke klasse geldt, ook waar je het niet
verwacht. Per klasse:

- **Rechtssubject**: een begrip, ook voor een organisatie of een bestuursorgaan. Een organisatie is een rechtssubject en
  dus een begrip, ook als ze niet de kern van de analysevraag is.
- **Rechtsobject**: een begrip.
- **Rechtsbetrekking**: een begrip voor de betrekking als geheel, met de handeling of de verplichting vooraan
  ("verschuldigdheid …", "bevoegdheid … tot …"). Het begrip draagt de soort, de rechtkant, de plichtkant en het voorwerp,
  met begrippen als waarde.
- **Rechtsfeit**: een begrip met een werkwoord vooraan ("indienen …").
- **Voorwaarde**: geen begrip. Ze krijgt een omschrijving die met "indien" begint, bij de rechtsbetrekking, het rechtsfeit
  of de afleidingsregel waar ze bij hoort; soms verwerk je haar in het begrip zelf.
- **Afleidingsregel**: eerst een begrip voor de regel ("bepalen …"), dan de regel met de begrippen als in- en uitvoer.
  Ook een tussenresultaat van de regel krijgt een begrip, als de tekst het niet noemt. Hoe je de regel opschrijft, staat
  in [afleidingsregels](afleidingsregels.md).
- **Variabele en variabelewaarde**: een begrip voor de variabele.
- **Parameter en parameterwaarde**: een begrip voor de parameter, en ook voor de waarde in haar tijdvak. Een vaste waarde
  die nooit verandert (zoals nihil) krijgt geen begrip.
- **Operator**: een begrip dat je overal hergebruikt ("plus" voor elke optelling, "min" voor elke aftrekking).
- **Tijdsaanduiding**: een begrip, ook voor een algemene eenheid die de wet niet definieert ("kalenderjaar").
- **Plaatsaanduiding**: het boek werkt geen voorbeeld uit; naar analogie van de tijdsaanduiding een begrip
  (projectkeuze).
- **Delegatiebevoegdheid en delegatie-invulling**: een begrip ("delegatiebevoegdheid … tot …").
- **Brondefinitie**: geen eigen begrip. Ze is de wettelijke definitie van het begrip dat de gedefinieerde term draagt, en
  levert daar de omschrijving.

Twee dingen volgen hieruit voor de beoordeling:

- **Een begrip is geen gegeven.** Begrippen zijn de bouwstenen van het gegevensmodel, het regelmodel én het procesmodel.
  Of iets een eigen gegeven wordt, beslis je pas bij het kennismodel. "Geen eigen gegeven", "te algemeen", "een
  organisatie" of "een kalendereenheid" is dus geen reden om een begrip af te wijzen. Wel een reden: het is hetzelfde als
  een begrip dat er al is (koppel dan), of de formulering hoort niet bij de analyse.
- **Wat er een begrip moet krijgen, is begrensd door de samenhang.** Alleen formuleringen die met een rechtsbetrekking,
  rechtsfeit, afleidingsregel of voorwaarde samenhangen, doen mee. Een losse markering zonder die samenhang is eerst een
  vraag: hoort ze bij de analyse? Zo niet, dan zet de jurist haar buiten behandeling, met een reden.

## Naam en omschrijving: de richtlijnen van de methode

Grondslag: M01 h.3 stap 3, onderdeel a (begrippen maken met eigenschappen); P15. In eigen woorden.

Voor elke geclassificeerde formulering maakt de methode een begrip dat haar betekenis zo precies mogelijk weergeeft,
en dat begrip gebruik je opnieuw voor elke formulering met dezelfde betekenis. Dat levert twee toetsen op:

- **Eén formulering, meer betekenissen** (een homoniem): maak meer begrippen. Hetzelfde woord kan in drie leden iets
  anders aanduiden doordat er telkens een berekening bij komt.
- **Meer formuleringen, één betekenis** (synoniemen): maak één begrip. Of twee termen hetzelfde betekenen, weet je pas
  na het lezen van de andere bepalingen; vraag het een jurist als de tekst het niet beslist.

**De naam**

- Blijf zo dicht mogelijk bij de woorden van de wet.
- Voeg je een aspect toe dat de betekenis verandert (uit een ander lid of een andere regeling), dan is het een nieuw
  begrip met een eigen naam.
- Begin met het zelfstandig naamwoord dat de kern uitdrukt. Gebruik lidwoorden en voorzetsels alleen waar de naam
  anders onleesbaar wordt.
- Geen ontkenning in de naam: in een regel levert dat later een dubbele ontkenning op.
- Zo kort als kan. Schrijf eerst volledig op wat het begrip moet uitdrukken, en kort dan in.
- Dezelfde opbouw voor gelijksoortige begrippen: één basisterm, aangevuld met wat het onderscheidt.
- Een afleiding krijgt een eigen begrip, met een werkwoord vooraan ("bepalen …").
- Zo min mogelijk afkortingen. Staat er toch een in de naam, schrijf haar dan voluit in de omschrijving.
- Nooit een lidwoord of voorzetsel vooraan: in een regel staat het lidwoord al in het taalpatroon (M02 §3.5.2a).
- Kleine letters, tenzij de spelling een hoofdletter vraagt (een eigennaam, een wet).
- Het enkelvoud, ook als de wet het meervoud gebruikt; alleen als het meervoud iets anders betekent of de term alleen
  in het meervoud bestaat, houd je dat.
- Geen Romeins cijfer: het lijkt op letters. En vermijd "voor": het kan "vóór" en "ten behoeve van" betekenen.
- Gebruik in een naam begrippen die er al zijn, zodat een wijziging vanzelf doorwerkt.

**De omschrijving**

- Zeg wat het begrip is (de wezenlijke kenmerken) en waarvoor het dient (het doel), waar de tekst dat zegt.
- De omschrijving moet het begrip in een zin kunnen vervangen. Lees een zin uit de wet met de omschrijving op de plek
  van de term: klopt de zin nog?
- Gebruik de naam van het begrip niet in zijn eigen omschrijving. Gebruik wel begrippen die al zijn vastgelegd: dan
  werkt een wijziging daarvan vanzelf door.
- Geen berekening of redenering in de omschrijving. Die hoort bij de afleidingsregel.
- Geen punt aan het eind: anders staat er een punt midden in de zin als de omschrijving de naam vervangt.
- Geen parameterwaarde in de omschrijving van een parameter ("zes weken", "€ 49"). De waarde is een eigen begrip in
  haar tijdvak, gerelateerd aan de parameter: wijzigt de wetgever de waarde, dan blijft de parameter hetzelfde
  (M01 h.6; M04 H2 *Parameter*).
- Geeft een omschrijving per geval een andere uitkomst ("bij A telt de maand mee, bij B niet"), dan zijn het twee
  begrippen, of één begrip met een kenmerk dat het geval aanwijst. Een begrip dat zijn waarde laat afhangen van iets
  wat het niet noemt, is niet eenduidig.
- Schrijf de omschrijving uit alle passages met deze term in het werkgebied, niet uit de eerste. Anders is het begrip
  te smal voor een passage die erbij hoort, en volgt er later een opvolger.

Een deel van deze regels toetst Lex in code: een kringdefinitie en een rekenregel in de definitie, en als aandachtspunt
op de kaart een lidwoord of voorzetsel vooraan, een hoofdletter vooraan, een Romeins cijfer, een ontkenning of "voor" in
de naam, en een punt aan het eind van de definitie (`api/app/begrip_store.py`, `naamregels`). Op de kaart staan ook twee
controles van activiteit 4 (M02 §3.6.1): een begrip zonder voorbeeld, en een variabele zonder de relatie "is kenmerk
van". Elk aandachtspunt is een signaal, geen weigering. De andere regels zijn voor wie het begrip beoordeelt.

## Wat de praktijk aan een begrip toevoegt

Grondslag: M15 (gevalideerd praktijkwerk), met M01 h.3 stap 3a en h.6; P23. In eigen woorden. Waar dit verder gaat dan
wat het platform nu vastlegt, staat dat erbij.

**De volgorde.** Maak eerst een werklijst: per klasse de gemarkeerde formuleringen met hun vindplaats, en daarnaast de
naam van het begrip. Formuleringen met dezelfde betekenis komen in één rij. Begin met de rechtssubjecten en
rechtsobjecten, dan de variabelen, de parameters en de tijd. Pas als die begrippen er zijn, maak je de regels voor
rechtsfeiten, afleidingsregels, rechtsbetrekkingen en voorwaarden. Een formulering waar je geen begrip bij vindt, is
een open rij, geen stille weglating.

**De klasse kan verschuiven.** De klasse van een markering zegt wat de formulering in de zin doet. Bij het maken van
het begrip kan blijken dat het in de regels iets anders is: wat de tekst als rechtsobject noemt ("een voorlopige
aanslag in de inkomstenbelasting"), is in de regel een ja/nee-kenmerk van een algemener object, afgeleid uit twee
andere kenmerken. Leg dat vast bij het begrip, met de reden; de markering blijft wat ze was. Een markering als parameter
die bij nader inzien een deel van een regel of van een variabele is, vervalt als parameter.

**Een ja/nee-begrip.** Een begrip dat alleen waar of onwaar kan zijn, krijgt:
- een naam zonder voorvoegsel ("is", "indicator") en zonder ontkenning: de woorden van de tekst, zo dicht als kan;
- een omschrijving die de situatie beschrijft waarin het waar is ("situatie waarin …"), niet de regel die het afleidt;
- een regel "bepalen …" die zegt wanneer het waar is (zie [afleidingsregels](afleidingsregels.md), *Ontleden in kleine
  regels*).

**Het waardebereik.** Bij een variabele of parameter hoort wat voor waarde het is: ja/nee, een datum, een bedrag (met
het aantal decimalen en de ondergrens), een aantal, een duur, of een van een vaste lijst waarden. Zonder waardebereik
is een voorbeeld niet te toetsen en een regel niet te bouwen. Het waardebereik heeft een eigen veld op het begrip, niet
in de toelichting, en de api toetst de waarden in een voorbeeldtabel ertegen. De waarde van een parameter hoort hier,
niet in de omschrijving.

**De naam van een kenmerk noemt zijn object.** "Dagtekening" is van een aanslagbiljet, een brief of een beschikking.
Draagt een kenmerk een naam die ook bij een ander object past, zet het object er dan bij. Geldt een begrip alleen in één
domein (de aanslag in de invordering, niet in de heffing), dan hoort dat in de naam van het object, en zo vanzelf in de
namen van zijn kenmerken. Dit weegt het zwaarst bij een begrip dat meer werkgebieden gebruiken. Blijkt een begrip
breder te gelden dan zijn naam zegt, hernoem het dan en leg vast waarom.

**Interpretatie apart.** Voegt het begrip iets toe aan de tekst (een geval dat de wet niet noemt maar dat de uitvoering
eronder brengt), dan staat dat niet in de omschrijving maar als interpretatiekeuze bij het begrip, met de reden en wie
koos.

**Het gesprek hoort erbij.** Een voorstel, een tegenwerping en het besluit, met datum, horen bij het begrip. Wie later
twijfelt, moet kunnen lezen waarom het zo is.

## De vorm van een voorbeeld

Grondslag: M01 h.3 stap 3, onderdeel a, en stap 4, onderdeel a (valideren met concrete voorbeelden).

Een voorbeeld beschrijft één concreet geval, in een vaste vorm: eerst het begrip, dan het rechtssubject met een
verzonnen naam, dan het tijdvak of tijdstip, dan de waarde.

> *De betalingstermijn* van *belastingschuldige* A. de Vries voor de *belastingaanslag* met dagtekening 3 maart 2025
> eindigt op 14 april 2025.

Zo'n zin laat meteen zien met welke andere begrippen het begrip samenhangt (hier: de belastingschuldige en de
belastingaanslag). Neem er een grensgeval bij: een geval waarover je kunt twisten of het onder het begrip valt. Valt het
erbuiten terwijl de omschrijving het toelaat, dan is de omschrijving niet scherp genoeg; pas haar aan en toets
opnieuw. Een verzonnen naam en een verzonnen bedrag zijn herkenbaar als voorbeeld; het is nooit bronbewijs.

Een voorbeeld bij een begrip is een **stelling**: ze is waar of niet waar, en dat is haar oordeel. Neem met opzet ook
stellingen op die niet waar zijn. De toelichting zegt in één zin waarom: welk kenmerk van de definitie het geval
binnen of buiten het begrip zet (M02 §3.5.5b; M03 hoofdactiviteit 3a). Zo'n stelling toetst de naam en de definitie;
de voorbeeldtabel bij een regel toetst de regel (M03 hoofdactiviteit 4b).
