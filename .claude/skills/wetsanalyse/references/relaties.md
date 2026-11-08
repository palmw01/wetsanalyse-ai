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
5. **Een impliciete partij is alleen een rechtssubject, en alleen de jurist legt haar vast.** Noemt de tekst de
   wederpartij niet, verzin dan geen anker. Koppel eerst aan een markering elders waar de partij wél letterlijk
   staat. Lukt dat niet, maak dan een impliciete partij met een toelichting die zegt waaruit ze volgt.
6. **Tekstuele relaties alleen waar de tekst ze uitdrukt.** `uitzondering_op` ("in afwijking van", "met
   uitzondering van") en `toepassing` ("is van toepassing", "vindt toepassing") leg je alleen als die
   woorden er staan. Ze zijn geen regelstructuur.

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
- Specialisatie van een begrip. Dat is de begripsrelatie *soort van* (activiteit 3).
- Rechtsgevolg en juridisch relevant feit als eigen element. Die komen uit de JRM 2-werkversie en horen
  in het dossier (P07).
- Feittypen, objecttypen, datatypen en de syntaxis van RegelSpraak (3b en 6).
