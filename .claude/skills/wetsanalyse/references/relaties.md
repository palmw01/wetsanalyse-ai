# Relaties tussen markeringen

Grondslag: [bronnen en beslisregister](bronnen.md): P18, met M01, M02, M04, M05 en M06.
Het besluit staat in ADR-011 (`docs/architectuur/adr-011-relaties-tussen-markeringen.md`).
De catalogus zelf staat in `relaties.json`, naast `SKILL.md`. Dit bestand legt uit hoe je hem gebruikt.

## Waarom relaties bij activiteit 2 horen

Een markering zegt welke juridische functie een formulering heeft. Een relatie zegt hoe twee markeringen
samenhangen. Je hebt ze nodig voor het diagram rond een centrale klasse (deelactiviteit 2c). Er zijn vier
centrale klassen: de rechtsbetrekking, het rechtsfeit, de afleidingsregel en de voorwaarde (M02).

- **De methode noemt de verbanden wel, maar geeft ze geen namen.** Het JAS-schema tekent lijnen zonder type
  (M04 H2). Per klasse beschrijven de omschrijvingen waarmee hij samenhangt.
  - Een rechtsbetrekking heeft een rechthebbende en een plichthebbende, en een voorwerp.
  - Een rechtsfeit creëert, wijzigt of beëindigt een rechtsbetrekking.
  - Een afleidingsregel heeft invoer en precies één uitvoer.
  - Een voorwaarde vergelijkt operanden: wat vergeleken wordt (een variabele, een tijdsaanduiding) is invoer van
    de voorwaarde, ook als er geen aparte operator gemarkeerd is (M04 H2:62).
  - Een variabele is een kenmerk van een subject, object, betrekking of feit.
  - Een voorwaarde en een afleidingsregel bestaan uit operanden en operatoren.

  Dat zijn de rollen in de catalogus (M01 h.4, M05).
- **Code, leesvorm, richting en drager zijn projectkeuzes.** Ze staan zo in de catalogus, met per type een
  bron, en `methodisch` zegt of het verband uit de methode komt.
- **Een rol hoort bij de relatie, niet bij de markering.** Hetzelfde rechtssubject kan in de ene
  rechtsbetrekking plichthebbende zijn en in de andere rechthebbende. Je zet nooit een rol als label op een
  element.

## Hoe je een relatie legt

1. **Begin bij de centrale klasse.** Neem de rechtsbetrekking, het rechtsfeit, de afleidingsregel of de
   voorwaarde, en zoek de markeringen die eraan hangen.
2. **Kies het type uit de catalogus.** Het klassenpaar moet passen (`van`, `naar`; bij `waarde` ook het
   subtype). Past geen type, dan leg je geen relatie. Een waarde of tak hoort in de toelichting, niet in het type.
3. **Een eindpunt mag in een andere bepaling liggen.** Een uitzondering in lid 5 kan naar een regel in lid 1
   wijzen, en een begrip uit een andere regeling kan de invoer zijn.
4. **Volgorde telt bij `invoer` en `operand`.** "A verminderd met B" is iets anders dan "B verminderd met A".
   Geef de operanden van een operator en de invoer van een regel een volgnummer zodra de volgorde de
   uitkomst verandert. Dat volgnummer is uniek per operator of regel.
5. **De partij die de tekst niet noemt, benoem je; alleen de jurist legt haar vast.** Zie *De partij die de tekst
   niet noemt* hieronder.
6. **Tekstuele relaties alleen waar de tekst ze uitdrukt.** `uitzondering_op` ("in afwijking van", "met
   uitzondering van") en `toepassing` ("is van toepassing", "vindt toepassing") leg je alleen als die
   woorden er staan. Ze zijn geen regelstructuur.

## De partij die de tekst niet noemt

De wet noemt vaak maar één van de twee partijen van een rechtsbetrekking: wie een recht heeft, of wie iets moet. De
andere partij volgt dan uit de regeling. Het boek noemt dat de dieptestructuur onder de tekst, en zegt dat je de andere
partij expliciet moet maken om de rechtsbetrekking te kunnen duiden (M01 h.4, §4.2.2 *Rechten en plichten* en §4.3.1).
Een rechtsbetrekking met één partij is dus niet af.

Zo doe je dat, zonder iets te verzinnen:

1. **Zoek eerst waar de partij wel staat.** In een ander lid, in de definities van de regeling, of in de bepaling die
   de bevoegdheid toekent. Staat zij daar letterlijk, koppel de relatie dan aan die markering.
2. **Staat zij nergens letterlijk, benoem haar dan als interpretatie.** Zeg wie het vermoedelijk is en uit welke
   bepaling dat volgt ("de ontvanger, op grond van artikel 3"). Het is een lezing, geen citaat: zet haar nooit tussen
   aanhalingstekens en geef haar geen tekstanker.
3. **Kun je haar niet onderbouwen, schrijf dan "onbekend"** en maak er een open punt van, met de bron die nodig is. Een
   waarschijnlijke partij zonder vindplaats ("de Staat", "de inspecteur") vul je niet in.

In de annotatie van Lex geldt daarnaast: alleen de jurist legt een impliciete partij vast (ADR-011). Lex noemt haar in
een antwoord of toelichting, als interpretatie met de vindplaats, en legt haar niet zelf als relatie vast.

## Het diagram rond een centrale klasse

De samenhang van activiteit 2 is in de methode een diagram per centrale klasse (M02 §3.4 activiteit 2,
deelactiviteit c). Het toont de brontekst, de markeringen met hun klasse, en de verbanden daartussen. Het is een
tussenresultaat: zodra de begrippen er zijn, kan hetzelfde diagram met begrippen in plaats van formuleringen worden
getekend.

Loop per centrale klasse deze verbanden na (zie per klasse *Samenhang* in de [klassenreferentie](jas-klassen-referentie.md)):

- **rechtsbetrekking**: rechthebbende, plichthebbende, voorwerp, voorwaarden, duur;
- **rechtsfeit**: de rechtsbetrekking die het creëert, wijzigt of beëindigt, wie het verricht, het voorwerp, het
  tijdstip;
- **afleidingsregel**: precies één uitvoer, de invoer op volgorde, de operatoren, de voorwaarden;
- **voorwaarde**: waar zij op werkt, wat zij vergelijkt, de operator.

Een verband dat ontbreekt, is een signaal: de tekst noemt het niet, of de markering mist nog.

## Specialisatie en afleidingshiërarchie

Twee verbanden uit het boek die geen relatietype in de catalogus zijn, en waar je ze dan laat:

- **Specialisatie** (M01 h.4 §1 en §2): een rechtssubject of rechtsobject is een bijzondere vorm van een ander. Noteer
  het in de toelichting van de markering. Als begripsrelatie *soort van* krijgt het later een plek bij de begrippen
  (activiteit 3).
- **Afleidingshiërarchie** (M01 h.4 §6): een regel heeft de uitkomst van een andere regel nodig. Signaleer het bij de
  samenhang met de relatie `invoer`, die naar een andere bepaling mag wijzen. De keten van regels zelf (volgorde,
  vertakking) werk je uit bij het opstellen van regels (activiteit 3b).

## Zorgvuldig duiden

Vier dingen die bij het leggen van relaties vaak misgaan (M01 h.4, rechtsbetrekking en rechtsfeit):

- **Forceer geen volledige relatie.** Een verband dat de tekst niet draagt of dat nog niet vaststaat, krijgt die
  status. Een partij die de tekst niet noemt, benoem je met haar vindplaats of als onbekend (zie hierboven).
- **Een immuniteit is een eigen soort rechtsbetrekking.** Laat een onderbouwde immuniteit staan; maak er geen
  bevoegdheid onder een voorwaarde van zonder dat de tekst dat zegt.
- **Eén passage zonder sanctie maakt een verplichting nog niet zwak.** Of nakoming is af te dwingen, staat vaak in een
  andere bepaling.
- **Niet elke handeling is een rechtshandeling.** Controleer of het rechtsgevolg beoogd is en of de wet het eraan
  verbindt.

Markeer een formulering ook niet als afleidingsregel omdat zij een gevolg beschrijft: de klasse volgt uit haar eigen
omschrijving, en het verband leg je vast als relatie.

Een relatietabel is verplicht waar relaties voorkomen; een diagram is aanvullend. De tabel blijft leidend.

## Kardinaliteit is een signaal

Een afleidingsregel heeft precies één uitvoer en minstens één invoer. Een regel zonder uitvoer of zonder
invoer is onvolledig geannoteerd. Dat is een signaal voor de jurist en geen weigering: de graafcontrole
meldt het, het schrijfpad laat het toe. Zo kun je een diagram stap voor stap opbouwen.

## Het regelskelet

De relaties rond een afleidingsregel zijn de grondstof voor activiteit 3b. Met uitvoer, invoer (op volgorde),
operatoren en operanden, voorwaarden, parameters met hun waarde, tijd en uitzonderingen kan een regel later
in natuurlijke taal worden opgesteld. De naam "bepalen X" en de begrippen komen dan uit activiteit 3.
Een regelskelet is compleet als de regel, zijn uitvoer, zijn invoer en zijn voorwaarden gemarkeerd en
verbonden zijn.

## Wat niet in activiteit 2 hoort

- Relaties tussen afleidingsregels: vertakking, volgorde en herhaling. Die ontstaan bij het opstellen van
  regels (3b).
- Een waarde of tak als label op een lijn ("is gesteld op zes weken", "wel of geen schrikkeljaar"). Dat is
  regelinhoud.
- Specialisatie als relatietype. In activiteit 2 staat zij in de toelichting; als begripsrelatie *soort van* hoort
  zij bij activiteit 3.
- Rechtsgevolg en juridisch relevant feit als eigen element. Die horen bij de methode wetsuitvoering (JRM), niet bij
  een wetsanalyse. Dat een rechtsfeit een rechtsbetrekking creëert, wijzigt of beëindigt, leg je hier wel vast: als
  relatie.
- Feittypen, objecttypen, datatypen en de syntaxis van RegelSpraak (3b en 6).
