# Begrippen

Hoe Lex bij activiteit 3 met begrippen werkt: wat een begrip in een werkgebied is, wat een goede
definitie is en hoe voorbeelden en relaties erbij horen. Dit is methode-uitleg, geen agentrol: graph-qa laadt deze
tekst niet in een prompt (besluit 7 nov 2026). De begrippenketen draagt deze regels in code en toetsen (ADR-004), en de
modelstappen van de begrippen-agent hebben elk hun eigen strakke opdracht. In eigen woorden, op basis van het
begrippenkader van de Rijksspecificatie (H3), NL-SBB (ADR-003) en de begrippenketen (ADR-004).
Broncodes verwijzen naar [bronnen en beslisregister](bronnen.md).

## Begrippen

Grondslag: M01, M04, P15.

Een begrip is een analyse-uitkomst, geen wettelijke definitie: het brengt de formuleringen samen die in het werkgebied hetzelfde aanduiden, met de passages waarop het rust. Het volgt NL-SBB en draagt alleen een term (naam en alternatieve termen), een definitie, een uitleg, een toelichting (de grenzen of het gebruik) en voorbeelden; een begripstype of JAS-duiding stel je niet voor. Een gelijk woord bewijst geen gelijke betekenis; sterk bewijs is wat de wet zelf vastlegt – een begripsbepaling binnen haar bereik, of een verwijzing. Houd de wettelijke definitie en het vastgelegde begrip uit elkaar.
Een definitie noemt het soortbegrip en het onderscheidende kenmerk, dekt wat de passages aanduiden en niet meer, gebruikt de naam van het begrip niet als eigen soortbegrip en is geen rekenregel. De herkomst telt: letterlijk uit de bron gaat voor samengesteld uit bronfragmenten, en dat gaat voor zelf geformuleerd. Een geformuleerde definitie is altijd een voorstel om te beoordelen, met de fragmenten waarop ze rust.
Lees een begrip in zijn context: de andere leden van het artikel, een definitie of kwalificatie elders, een bepaling waarnaar verwezen wordt. Beginnen bepalingen gelijk en verschillen ze daarna (zoals "bij herziening van … met een positief bedrag tot …"), kies dan een algemene definitie die voor alle varianten geldt, of een specifiek begrip met een eigen naam; een toepassingsgeval is niet de definitie van het algemene begrip. Een definitie geeft de wezenlijke kenmerken en, waar de tekst het zegt, het doel – geen rechtsgevolg, geen voorwaarde uit één lid en geen afleiding: wat de wet met een term berekent of verrekent, is een eigen begrip ("bepalen …"), en een woord dat in één bepaling door een berekening verandert, kan daar twee begrippen dragen. Een kwalificatie van een samenstelling ("geldt als het te betalen bedrag aan belasting") definieert de kale term niet. Is er onvoldoende bewijs, zeg dan wat er ontbreekt in plaats van een definitie te raden, en noem open vragen.
Voorbeelden toetsen een definitie. Ze komen pas als er een overgenomen definitie is, en een grensgeval of tegenvoorbeeld hoort erbij. Elk voorbeeld toetst één kenmerk van de definitie en zegt of het het begrip toetst of iets anders (een scenario, een voorwaarde, een rechtsgevolg); twee voorbeelden die alleen in getallen of namen verschillen, toetsen hetzelfde. Een betekenisverschil leg je uit met de context van beide begrippen, niet met het woord alleen; waar de grens ligt, hoort in de toelichting.
Relaties houden hun type – kwalificatie, inclusie, uitsluiting, soort van, verwant – en hun richting. Een begrip met een andere betekenis wordt een opvolger, het oude wordt vervangen. Het begrippenkader volgt NL-SBB.
Lex stelt voor; de analist neemt over, past aan of wijst af, en alleen de analist accordeert.

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
- Zo min mogelijk afkortingen.

**De omschrijving**

- Zeg wat het begrip is (de wezenlijke kenmerken) en waarvoor het dient (het doel), waar de tekst dat zegt.
- De omschrijving moet het begrip in een zin kunnen vervangen. Lees een zin uit de wet met de omschrijving op de plek
  van de term: klopt de zin nog?
- Gebruik de naam van het begrip niet in zijn eigen omschrijving. Gebruik wel begrippen die al zijn vastgelegd: dan
  werkt een wijziging daarvan vanzelf door.
- Geen berekening of redenering in de omschrijving. Die hoort bij de afleidingsregel.

Twee van deze regels toetst Lex in code (een kringdefinitie, een rekenregel in de definitie); de andere zijn
aandachtspunten voor wie het begrip beoordeelt.

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
