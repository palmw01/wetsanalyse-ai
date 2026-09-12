# Onderzoek en ontwerp: JAS met JRM 2-verrijking

Versie 2.1 — onderzoek 11 september 2026; implementatie 12 september 2026.
Status: geïmplementeerde conceptmethode, nog geen empirisch bewezen kwaliteitsverbetering.

## Uitkomst

De belangrijkste zwakte van de bestaande invoer was dat juridische analyse werd teruggebracht
tot het vinden van losse tekstfragmenten met een label. De nieuwe methode maakt de samenhang,
bronnen en onzekerheden expliciet. Een betekenisvolle analyse moet kunnen uitleggen wie
waarop aanspraak heeft, onder welke voorwaarden, door welk feit een toestand verandert en
hoe dat uit de toepasselijke tekst volgt. Grammaticale ontleding ondersteunt dit, maar is
geen vervanging van juridische interpretatie.

De uitvoer is daarom tweeledig: een volledig Markdown-dossier voor de skillworkflow en een
compact annotatieprotocol voor de bestaande platformagent. De API draagt nog steeds dertien
labels. De aanvullende inhoud leeft in het dossier; een groene annotatiekaart is geen
bewijs dat extern bronnenonderzoek of een volledige analyse heeft plaatsgevonden.

## Onderzoeksbasis en bewaarbeleid

Het [bronnen- en beslisregister](../../.claude/skills/wetsanalyse/references/bronnen.md)
legt de gebruikte onderdelen vast. Het [bronmanifest](bronnen/manifest.json) bewaart
herkomst, versies en hashes van lokale exemplaren. De originele interne handleiding,
leidraad en het auteursrechtelijk beschermde boek blijven lokaal; zij worden niet
opnieuw gepubliceerd. Dit document bevat eigen bevindingen en projectbesluiten.

De lokale methodebronnen omvatten de kennisbankplannen, handleiding, leidraad, het
JAS-begrippenkader en de relevante theorie en toepassingen in het boek. De bespreking
van elektronische berichten laat bijvoorbeeld zien waarom een naamwoord als
kennisgeving niet automatisch als object kan worden geclassificeerd: de antecedent en
juridische context bepalen welke functie bedoeld is. De handleiding verbindt markeren
en classificeren met het zichtbaar maken van samenhang; de huidige runtime gebruikte
vooral de klassedefinities. Zie M01–M04 in het register.

Bronnen worden op hun specifieke bijdrage beoordeeld. Een praktijkvoorbeeld bewijst geen
universele classificatieregel. Een schrijfaanwijzing verklaart conventioneel taalgebruik,
maar sluit afwijkende historische formuleringen niet uit. Een onderzoek naar een andere
jurisdictie ondersteunt het ontwerp van annotatie en evaluatie, niet automatisch de
inhoudelijke uitkomst van een Nederlandse wetsanalyse.

## JAS en de gevonden doorontwikkeling

De relevante publicatie noemt de doorontwikkeling **JRM 2**, Juridisch Referentiemodel,
en is expliciet een werkversie. Zij voegt onder meer rechtsgevolgen en juridisch relevante
feiten toe en geeft scenario's een centrale rol. De overgang is inhoudelijk: relaties en
toestanden krijgen een explicietere plaats. Het is geen simpele hernoeming van labels.
Ons projectprofiel behoudt JAS en voegt deze informatie toe in het dossier. Het onderscheid
met de bronmethode is bewust vastgelegd; het dossier is geen volledige implementatie van
alle door JRM beoogde formele modellen. [M06: Bulles en Van der Hoven, 2024](https://regels.overheid.nl/publicaties/doorontwikkelingen-en-voortschrijdend-inzicht-in-wetsanalyse/download)

De lokale WetsTaal-werkversie bevat bruikbare patronen, maar ook onvoltooide hoofdstukken.
Daarom wordt zij niet integraal als zekere instructie aan een agent gegeven. Hetzelfde
geldt voor verschillen tussen de bronnen in subtypen: de methode registreert bronvariant
en onderbouwing, in plaats van een ontbrekend subtype stilzwijgend te verwijderen.
[M05: WetsTaal](https://regels.overheid.nl/standaarden/wetstaal)

## Tekstanalyse: wat moet de agent daadwerkelijk doen?

### Eerst de structuur, daarna de betekenis van fragmenten

Een zin, normeenheid en annotatie zijn verschillende dingen. Een lid kan meerdere
normen bevatten; een norm kan een aanhef en meerdere onderdelen nodig hebben. De agent
maakt daarom eerst een structuurkaart. Vervolgens worden voor iedere norm de dragende
uitspraak, actor, object en beperkingen gezocht. Fragmenten blijven exact; analytische
reconstructies worden afzonderlijk vastgelegd.

De werkwijze voorkomt twee tegenovergestelde fouten: alleen een woord zoals bedraagt
markeren en daarmee de rekenregel verliezen, of een volledig lid één label geven en
betekenisvolle onderdelen niet meer onderscheiden. Overlap is geoorloofd waar elementen
verschillende functies dragen. Concurrerende interpretaties horen bij alternatieven.
Een hiërarchische tekening levert geen algemene prioriteitsregel op.

### Grammaticale controles met juridische gevolgen

De expliciete controles omvatten passief en ellips, modaliteit, negatie, kwantoren,
bijzinnen, opsommingen, coreferentie, vergelijkingen en tijd. Ze beantwoorden concrete
vragen: wie handelt, wat is de voorwaarde, waarop werkt niet, welk antecedent bedoelt
deze, en deelt deze uitzondering de aanhef van alle onderdelen?

De Aanwijzingen bieden onder meer aanknopingspunten voor het onderscheid tussen indien
en voor zover, voor ficties versus vermoedens en voor het lezen van opsommingen. Ook de
motivering en doelen van regelgeving horen in de toelichting thuis. Deze aanwijzingen
worden als contextgevoelige controlevragen toegepast. Het wetsdoel wordt aan de juiste
versie en wijziging verbonden; het wordt niet uit een plausibel verhaal van het model
afgeleid. [M07: Aanwijzingen 3.10–3.12, 4.43 en 4.47](https://www.kcbr.nl/print-instrument/12640)

### Signaalwoorden zijn geen beslisboom

Annotatieonderzoek beschrijft problemen met de interpretatie van modale werkwoorden,
nesteling van lijsten en minder expliciete uitzonderingen. Dat ondersteunt onze keuze
om herkenningswoorden als zoekhulp te gebruiken en daarna hun functie in context te
toetsen. De concrete Nederlandse classificatie blijft gebaseerd op de betreffende wet
en JAS-definities; buitenlandse labels worden niet automatisch overgenomen.
[M08: Nazarenko, Lévy en Wyner, 2018](https://aclanthology.org/L18-1177/)

## Brononderzoek en juridische interpretatie

De dossierworkflow kan noodzakelijke officiële bronnen volgen. Iedere verwijzing krijgt
een functie en uitkomst. Definities, delegatie, uitzonderingen en tijdswerking kunnen
meerdere stappen vereisen; een vaste diepte van één is daarom geen volledigheidscriterium.
Wel is er een operationeel startbudget van twintig nieuwe passages. Dat is een expliciete
projectkeuze om onderzoek beheersbaar te houden. Bij uitputting blijven de wachtrij en
beïnvloede conclusies zichtbaar.

De analyse houdt de primaire wetstekst gescheiden van historische toelichting, rechtspraak,
beleid en eigen reconstructie. Grammaticale, systematische, historische en doelgerichte
argumenten worden alleen gebruikt waar ze bijdragen aan een materiële interpretatievraag.
Geen van deze methoden krijgt een universele automatische voorrang. Ontbrekende informatie
wordt niet omgezet in een negatieve conclusie: een niet gevonden sanctie bewijst niet dat
geen sanctie bestaat, en een onbekende waarde is niet nul.

Het dossier bewaart bronversie, peildatum en raadpleegdatum afzonderlijk. Exacte citaten
met context en positie sluiten aan bij het W3C-annotatiemodel; de bestaande platformankers
blijven bruikbaar. Een hash borgt tekstidentiteit, maar bewijst geen juridische geldigheid.
[M10: Web Annotation Data Model, selectors](https://www.w3.org/TR/2017/REC-annotation-model-20170223/)

## Kwaliteit aantonen

Een agent mag zijn eigen onzekerheid niet wegpoetsen om een groen rapport te produceren.
Onderzoek naar annotatie van EU-regelgeving laat zien dat de gemeten overeenstemming
samenhangt met taak, meetwijze en beoordelingsronde. Daarom scheiden we technische
brongetrouwheid, inhoudelijke juistheid en menselijke beoordeling. Een betwistbare
duiding kan een aanvaardbaar alternatief zijn; adjudicatie wordt met reden vastgelegd.
[M09: Van Dijck, Aguilera en Chakravarthy](https://link.springer.com/article/10.1007/s10506-024-09423-9)

De nieuwe rubriek beoordeelt bronintegriteit, grammatica, classificatie, samenhang,
interpretatie, dekking, scenario's en reviewbaarheid. Kritieke fouten blokkeren de
betrokken analyse; een gemiddelde score mag ze niet verbergen. De conceptset bevat
24 gevallen, gesplitst op wetsfamilie. Zij bevat nog open vragen en is geen goldstandaard.
De vier ontwikkelfamilies en twee toetsfamilies blijven gescheiden van promptvoorbeelden.

De bestaande evaluator meet al exacte genormaliseerde fragmenten en klassen en heeft
fijnmaziger diagnostiek. Het probleem is niet dat hij uitsluitend woorden telt, maar
dat de oude ankerset niet alle normen, relaties en juridische beslissingen beschrijft.
Die set mag niet als volledig deskundig referentiemodel worden gepresenteerd. Bij nieuwe
referentiegrenzen moeten zowel oude als nieuwe modeluitkomsten opnieuw worden beoordeeld.

## Technische vertaling en beperkingen

De generator neemt nu naast de klassedefinities een versieerbaar protocol op. De
gecombineerde annotator, kandidaatgenerator, classificator, reviewer en herziener krijgen
de toepasselijke secties. De classificator mag voorlopige grenzen herzien, maar de
bestaande broncontrole blijft elk resultaat toetsen aan het aangeboden corpus.

De critic krijgt niet langer de instructie een herhaald bezwaar uitsluitend wegens
herhaling af te zwakken. Bestaande bescherming van menselijke annotaties en de begrensde
correctieketen blijven gehandhaafd. Deze wijziging is een methodische verbetering van
de instructie, geen bewijs dat het model altijd het gewenste gedrag vertoont.

Er zijn geen nieuwe API-velden, databasewijzigingen, zoektools voor de annotator of
UI-schermen toegevoegd. Het volledige document is een skillproduct. De technische tests,
open inhoudelijke vragen en nog niet uitgevoerde metingen staan in het
[evaluatierapport](evaluatie-methode.md).
