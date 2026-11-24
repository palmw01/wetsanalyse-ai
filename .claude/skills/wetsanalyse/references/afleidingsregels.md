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

## Ontleden in kleine regels

Grondslag: M01 §2.2.2 en h.6; M02 §1.2; M15 (gevalideerd praktijkwerk); P23.

- **Een voorwaarde die zelf iets afleidt, wordt een eigen regel.** Staat er in een voorwaarde meer dan een vergelijking
  van een begrip met een waarde (zoals "een aanslag van soort X in belasting Y waarvan de dagtekening in het jaar zelf
  ligt"), dan maak je daar een begrip van met een eigen regel. De regel erboven noemt alleen nog dat begrip. Zo staat
  elke toets op één plek, en een tweede regel die dezelfde groep nodig heeft, herhaalt de voorwaarde niet.
- **Een indeling is een regel.** Of een rechtsobject tot een groep hoort (een specialisatie), leid je af uit zijn
  kenmerken: een ja/nee-begrip met een regel op die kenmerken. De kenmerken zelf zijn gewone variabelen, met de
  toegestane waarden als waardebereik (zie [begrippen](begrippen.md)).
- **Klein is de maat.** De meeste regels hebben één uitkomst en een of twee voorwaarden. Een regel met geneste
  voorwaarden is een signaal: zit er een begrip in dat nog geen naam heeft?
- **Een deel van een waarde is een eigen begrip** als een regel het nodig heeft: het jaar of de maand uit een datum, het
  volgnummer van een termijn. De regel die het afleidt, is één regel tekst.
- **Algemene hulpregels maak je één keer.** Een kalenderfeit (de laatste dag van een maand, een schrikkeljaar) heeft de
  uitvoering nodig, ook al regelt de wet het niet. Kijk eerst of het begrip en de regel al bestaan in het generieke
  kader; maak ze anders daar, en laat ze rusten op de formulering in de tekst die erom vraagt.
- **Een regel per element.** Geldt een regel voor elk element van een reeks (elke termijn van een aanslag), zeg dan in
  de regel voor welk begrip hij herhaald wordt en waar de reeks eindigt. De uitkomst van het vorige element mag invoer
  zijn van het volgende (een restbedrag dat doorschuift).
- **Het moment van toepassen is invoer.** Een regel die zegt of iets op een moment zo ís (invorderbaar, verstreken),
  heeft de datum van beoordeling als invoer. Noem die, ook al staat ze niet in de tekst.
- **Een vaste waarde is geen vrije tekst.** Vergelijkt een voorwaarde met een waarde uit een opsomming (een soort
  aanslag, een maand), dan komt die waarde uit het waardebereik van het begrip.
- **Twee momenten zijn twee begrippen.** De laatste dag waarop iets kan (de vervaldag) en de eerste dag waarop iets
  anders mag (de dag erna) verschillen een dag. Geef ze elk een begrip, met een regel die het ene uit het andere afleidt.

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

## Toetsen met een voorbeeldtabel

Grondslag: M01 h.3 stap 4; M02 §3.6; M15; P23. Zie ook het [analyseprotocol](analyseprotocol.md) §5.

Een regel is pas afgestemd als hij met voorbeelden is nagelopen. De vorm die in de praktijk werkt, is een tabel bij de
regel:

- elke kolom is één geval, genummerd;
- de bovenste rijen zijn de invoerbegrippen, elk met een waarde uit zijn waardebereik;
- dan de vraag: **kan deze invoer zich voordoen?** Neem met opzet ook een geval dat niet kan (nul termijnen, een
  datum die niet bestaat). Het antwoord is dan "niet van toepassing", en dat is een uitkomst: de regel hoeft dat geval
  niet te dekken, of er ontbreekt een voorwaarde;
- dan de uitvoer die de regel geeft, als voorspelling;
- dan de vraag: **is deze uitkomst juridisch juist?** Een jurist beantwoordt die, niet de opsteller.

Kies de gevallen bij de regel: elk geval van een beslistabel minstens één keer, de precieze grens van elke vergelijking
(de dag zelf, de dag ervoor, de dag erna), en bij een datum de randen van de kalender (de laatste dag van een maand, 28
en 29 februari, de jaarwisseling). Dit zijn voorbeelden om de regel te begrijpen en af te stemmen; het is geen
testset die elk risico dekt.

Een rekenvoorbeeld dat in de bron zelf staat (een beleidsregel die een termijn voorrekent), hoort als geval in deze
tabel. Wijkt de regel af van wat de bron voorrekent, dan klopt de regel niet of is er een interpretatie gekozen.

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
- `regelbegrip_bepalen_van`: het regelbegrip heet "bepalen van de …" of "bepalen van het …"; de vorm is "bepalen
  <uitvoer>", zonder lidwoord en voorzetsel.
- `parameter_zonder_tijdvak`: een parameter heeft geen waarde met een tijdvak.
- `parameterwaarde_in_definitie`: de definitie van een parameter noemt een waarde.
- `rust_op_contextbron`: de regel rust op een bron met de rol context; misschien wordt het een bron om te analyseren.
- `operator_zonder_begrip`: een operatorformulering in de regel draagt geen operatorbegrip.
- `impliciete_invoer`: een invoer rust op geen formulering en geen regel leidt haar af; signaleer ontbrekend
  uitvoeringsbeleid.
- `voorwaarde_zonder_markering`: een voorwaarde rust op geen markering en verwijst naar geen geval van een andere
  regel; ze is dan niet naar de tekst te herleiden.
- `voorwaarde_zonder_begrip`: een voorwaarde noemt geen invoerbegrip van de regel en verwijst naar geen geval van een
  andere regel; wat ze toetst, is een begrip met een eigen regel, of een invoer die ontbreekt.
- `verwijzing_niet_geldig`: een voorwaarde verwijst naar een regel of geval dat niet meer geldt (afgewezen, vervangen).
- `verwijzing_zonder_invoer`: een voorwaarde verwijst naar een andere regel, maar de uitvoer daarvan is geen invoer;
  neem haar op als invoer, anders ziet de keten het verband niet.
- `uitkomstbegrip_geen_invoer`: een uitkomst noemt een begrip dat geen invoer van de regel is.

In de keten van het werkgebied:
- `zelfde_uitvoer`: meer regels leiden hetzelfde begrip af; hun gevallen moeten elkaar uitsluiten.
- `voorwaarde_herhaald`: dezelfde voorwaarde (dezelfde markeringen) staat in meer regels; maak er één begrip met een eigen
  regel van.
- `regelbegrip_meer_uitvoeren`: één regelbegrip hoort bij regels met verschillende uitvoeren.
