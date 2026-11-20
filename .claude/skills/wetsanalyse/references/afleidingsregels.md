# Afleidingsregels maken (deelactiviteit 3b)

Grondslag: [bronnen en beslisregister](bronnen.md), P22, met M01, M02, M03 en M04. Het boek en de BRM-readers (M01–M03)
staan hier in eigen woorden. De lessen uit de eerste volledige proef (Termijnen, 19 nov 2026) staan in
`docs/architectuur/plan-lessen-e2e-termijnen.md` §0.

Een afleidingsregel leg je vast met begrippen. Hij komt dus na de begrippen (activiteit 3a) en rust op de markeringen
en relaties uit activiteit 2 (zie [relaties](relaties.md)). RegelSpraak, het feitmodel en het gegevensmodel vallen
buiten deze skill.

## Wat een afleidingsregel is

- Een afleidingsregel maakt een nieuwe waarde of een nieuw feit uit bestaande waarden of feiten (M04 H2
  *Afleidingsregel*). Er zijn drie soorten:
  - een **rekenregel** bepaalt een hoogte, een aantal, een duur of een datum;
  - een **beslisregel** bepaalt of iets zo is, met ja of nee als uitkomst. Dat kan ook gaan over de vraag of een
    recht, plicht of bevoegdheid in een geval bestaat;
  - een **specialisatie** bepaalt of een rechtssubject of rechtsobject tot een bepaalde groep hoort.
- Een regel heeft precies één **uitvoer**: het begrip dat hij afleidt. De begrippen waaruit hij afleidt, zijn de
  **invoer**. De bewerking verbindt de invoer met operatoren, en voorwaarden zeggen wanneer de regel geldt (M01 h.3
  stap 3b).
- Elke regel krijgt een begrip met een naam "bepalen <uitvoer>". Daarna schrijf je de regel op met de begrippen, in een
  vast taalpatroon (M01 h.3 stap 3b; M02 §3.5.2b).

## Waarop een regel rust

- Elke regel en elk begrip moet via gemarkeerde formuleringen terug te voeren zijn op wetgeving of beleidsregels
  (M03, analyseresultaat 17). Een regel zonder grondslag in de tekst bestaat niet.
- **Een regel rust op de formuleringen die zijn uitvoer en zijn voorwaarden dragen.**
  - Is de formulering in activiteit 2 als Afleidingsregel gemarkeerd, dan rust de regel op die markering.
  - Bij een beslisregel over een recht of bevoegdheid rust de regel op de formulering van dat recht (een
    Rechtsbetrekking) met haar voorwaarden. Je hoeft die formulering niet ook als Afleidingsregel te markeren. Voor elk
    geclassificeerd begrip maak je, waar dat aan de orde is, de regels die het afleiden (M03 hoofdactiviteit 3; het
    voorbeeld *bepalen recht op zorgtoeslag* in M02 §3.5.2b).
  - Een tijdstip dat een Tijdsaanduiding beschrijft ("zes weken na de dagtekening"), leidt een regel af die op die
    Tijdsaanduiding rust.
- Een **contextbron** heb je niet geannoteerd. Daar kan dus geen regel op rusten. Draagt ze toch een regel die je nodig
  hebt, dan is dat een signaal: wordt zij een bron om te analyseren?

## Eén regel per uitvoer

- Per afgeleid begrip is er één regel. Leidt de wet hetzelfde begrip in verschillende gevallen anders af (zoals in drie
  leden), dan wordt dat **één beslistabel** met een rij per geval. De voorwaarden van de rijen sluiten elkaar uit. Drie
  regels met drie regelbegrippen voor dezelfde uitvoer geven drie identiteiten voor één gegeven, en een volgende regel
  weet dan niet op welke hij rust.
- Een formulering die twee waarden oplevert ("zoveel gelijke termijnen als …" levert het aantal én het bedrag per
  termijn), draagt twee regels. In activiteit 2 zijn dat twee markeringen als Afleidingsregel, elk op het kleinste stuk
  tekst dat de eigen afleiding draagt. Die markeringen mogen overlappen.

## Tussenresultaten en wat de tekst open laat

- **Een tussenresultaat krijgt een begrip**, ook als de wet het niet met een eigen formulering noemt. De uitvoering moet
  elke stap kunnen uitvoeren, uitleggen en controleren, en het oude tussenresultaat blijft bewaard (M01 §2.2.2 en h.6;
  M02 §1.2). Het begrip rust op de markering van de afleidingsregel die het afleidt (koppelrol `afgeleid`, zie
  [begrippen](begrippen.md)). Daarna kijk je opnieuw in de tekst of er toch een formulering is die het aanduidt.
- **Een invoer die de tekst niet noemt**, zoek je eerst elders: een eindpunt mag in een andere bepaling liggen (zie
  [relaties](relaties.md)). Staat hij nergens, dan krijgt het element dat de regel nodig heeft een begrip. Je gebruikt
  het als impliciete invoer en signaleert de interpretatie als ontbrekend uitvoeringsbeleid (M01 h.7, stap 5).

## Operatoren, tijd en parameters

- Een **operatorbegrip** maak je bij een formulering die een bewerking, vergelijking of logische verbinding uitdrukt
  ("het gezamenlijke bedrag van", "verminderd met", "meer bedraagt dan", "en", "of", "niet"). Daarna hergebruik je het
  voor elke formulering met dezelfde betekenis (M01 h.3 stap 3b, h.6; M04 H2 *Operator*). Een ontkenning laat je uit
  het begrip en zet je in de regel als *niet*.
- Het **taalpatroon** van de regel ("moet berekend worden als", "is", "indien aan alle volgende voorwaarden is
  voldaan") is geen begrip.
- Een **duur bij een tijdstip** ("zes weken na de dagtekening", "telkens een maand later") is een Tijdsaanduiding, geen
  operator: de tijdsaanduiding gaat als meest specifieke klasse voor (M04 H2 *Tijdsaanduiding*). Het tijdstip dat zo
  ontstaat, krijgt een begrip, en de regel die het afleidt noemt de bewerking in het taalpatroon.
- Een **parameter** is de omschrijving van een waarde, de **parameterwaarde** de waarde in een periode (M04 H2). De
  parameterwaarde is een eigen formulering met een eigen begrip, gerelateerd aan de parameter. De regel gebruikt de
  parameter, niet de waarde. Wijzigt de wetgever de waarde, dan verandert alleen de parameterwaarde (M01 h.6). Zet een
  waarde dus niet in de definitie van het parameterbegrip.

## Wat open blijft

Leg elk open punt vast met:
- de soort: interpretatiekeuze, ontbrekend uitvoeringsbeleid, onderzoekspunt of gat in de annotatie;
- waar het aan hangt: een regel, een rij, een markering of een begrip;
- de lezingen met hun grondslag, de keuze en wie die maakte;
- wat nog getoetst moet worden (bijvoorbeeld "niet getoetst aan de memorie van toelichting").

Interpretaties die nog niet in uitvoeringsbeleid staan, signaleer je (M01 stap 5). Denk aan de afronding van een
bedrag, een vervaldag die op een dag valt die in de volgende maand niet bestaat, of het tijdvak waarin een drempel
geldt. Kies niet stil.

## Wat een regel mist

Toets elke regel op deze gaten, zonder het accorderen ervan af te laten hangen (een gat is een signaal). De codes staan
in `regelgaten.json`; het platform rekent ze uit en toont ze op de regelkaart en in het skelet.

In het skelet van de Afleidingsregel-markering:
- `uitvoer_ontbreekt`: er is geen uitvoer.
- `meer_uitvoeren`: de formulering heeft meer uitvoeren; ze draagt dan meer regels.
- `invoer_ontbreekt`: er is geen invoer.
- `invoer_zonder_volgorde`: bij meer invoeren heeft een invoer geen volgorde.
- `rechtsobject_als_invoer`: de enige invoer is een rechtsobject, geen waarde.
- `voorwaarde_bij_andere_drager`: een voorwaarde in de bepaling hangt aan een andere drager, niet aan de regel.
- `afwijking_zonder_uitzondering`: "in afwijking van" zonder relatie `uitzondering_op`.

Bij het regelobject:
- `uitvoer_zonder_begrip`: de uitvoerformulering draagt geen begrip.
- `regelbegrip_zonder_bepalen`: het regelbegrip heet niet "bepalen <uitvoer>".
- `parameter_zonder_tijdvak`: een parameter heeft geen waarde met een tijdvak.
- `parameterwaarde_in_definitie`: de definitie van een parameter noemt een waarde.
- `rust_op_contextbron`: de regel rust op een bron met de rol context; misschien wordt het een bron om te analyseren.
- `operator_zonder_begrip`: een operatorformulering in de regel draagt geen operatorbegrip.
- `impliciete_invoer`: een invoer rust op geen formulering en geen regel leidt haar af; signaleer ontbrekend
  uitvoeringsbeleid.
- `voorwaarde_zonder_markering`: een voorwaarde rust op geen markering en verwijst naar geen geval van een andere
  regel; ze is dan niet naar de tekst te herleiden.
- `verwijzing_niet_geldig`: een voorwaarde verwijst naar een regel of geval dat niet meer geldt (afgewezen, vervangen).
- `verwijzing_zonder_invoer`: een voorwaarde verwijst naar een andere regel, maar de uitvoer daarvan is geen invoer;
  neem haar op als invoer, anders ziet de keten het verband niet.
- `uitkomstbegrip_geen_invoer`: een uitkomst noemt een begrip dat geen invoer van de regel is.

In de keten van het werkgebied:
- `zelfde_uitvoer`: meer regels leiden hetzelfde begrip af; hun gevallen moeten elkaar uitsluiten.
- `regelbegrip_meer_uitvoeren`: één regelbegrip hoort bij regels met verschillende uitvoeren.
