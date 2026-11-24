# Uitgewerkte voorbeelden

Grondslag: [bronnen en beslisregister](bronnen.md) — P04, P05, P18, P19.

Vier bepalingen uit de Invorderingswet 1990 en de Algemene wet bestuursrecht, letterlijk uit de officiële bron
(wettekst is vrij van auteursrecht). De duiding is een **voorbeeld van de werkwijze**, geen gouden standaard: een jurist kan op punten
anders kiezen, en dat is precies waarom alternatieven zichtbaar blijven.

## Inhoud

- Voorbeeld 1: één enkelvoudige normzin (art. 9, eerste lid)
- Voorbeeld 2: een uitzondering met een opsomming (art. 9, elfde lid, aanhef en onderdeel a)
- Voorbeeld 3: een plicht zonder genoemde partij (Awb art. 4:13, eerste lid)
- Voorbeeld 4: een rekenregel (art. 28, tweede lid, eerste volzin)
- Voorbeeld 5: een regel ontleden in kleine regels (art. 9, vijfde lid, eerste volzin)
- Wat de voorbeelden laten zien

## Voorbeeld 1: één enkelvoudige normzin

**Bron.** Invorderingswet 1990, artikel 9, eerste lid:

> Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.

**Ontleding.** Eén normeenheid (N01). Onderwerp: *een belastingaanslag*. Gezegde: *is invorderbaar* (naamwoordelijk:
een toestand, geen handeling). Geen actor, geen modaliteit, geen ontkenning. De tijdsbepaling *zes weken na de
dagtekening van het aanslagbiljet* bepaalt wanneer de toestand intreedt. Let op: lid 11 maakt hierop een uitzondering
(zie voorbeeld 2). Wie alleen lid 1 leest, mist dat.

**Markeringslijst.**

| ID | Letterlijk fragment | Klasse | Toelichting | Alternatief |
|---|---|---|---|---|
| E01 | Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet. | Rechtsfeit | Dragende normzin: het verstrijken van de termijn brengt de invorderbaarheid teweeg (tijdsverloop als rechtsfeit). | Rechtsbetrekking, als je invorderbaarheid leest als de bevoegdheid van de ontvanger om in te vorderen; ter beoordeling. |
| E02 | Een belastingaanslag | Rechtsobject | Het voorwerp waarover de norm gaat. | — |
| E03 | invorderbaar | Variabele en variabelewaarde | Booleaanse eigenschap van de aanslag (wel of niet invorderbaar). | — |
| E04 | zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding | Subtype *verbijzondert parameter*: de termijn van zes weken is voor iedereen gelijk, maar de functie is temporeel, dus geen tweede markering Parameter. | — |
| E05 | de dagtekening | Tijdsaanduiding | Subtype *verbijzondert variabele*: een datum die per aanslagbiljet verschilt, het startmoment van de termijn. Tijd gaat voor variabele (H2:107), dus geen markering Variabele; als variabele is zij wel kenmerk van het aanslagbiljet (M01 h.4 §12). | Variabele en variabelewaarde, zoals vóór 24 nov 2026; dat laat de tijdsfunctie weg. |
| E06 | het aanslagbiljet | Rechtsobject | Het stuk waarop de dagtekening staat. | — |

E02 tot en met E06 liggen binnen E01: dat is overlap met verschillende functies, geen dubbeling.

**Samenhang** (zie [relaties](relaties.md); de kolom Type is de code uit de catalogus).

| ID | Van | Type | Naar | Toelichting |
|---|---|---|---|---|
| R01 | E01 (rechtsfeit) | voorwerp | E02 | Het rechtsfeit raakt de aanslag. |
| R02 | E03 (variabele) | kenmerk | E02 | Invorderbaar is een eigenschap van de aanslag. |
| R03 | E01 | tijd | E04 | Wanneer het rechtsfeit intreedt. |
| R04 | E05 (tijdsaanduiding, verbijzondert variabele) | kenmerk | E06 | De dagtekening is een eigenschap van het aanslagbiljet; een tijdsaanduiding neemt die relatie over van de variabele die zij verbijzondert. |

**De partij die lid 1 niet noemt.** Wie vordert in? Lid 1 zegt het niet. Zoek eerst waar de regeling haar wel noemt
(de definities, de bepaling die de bevoegdheid toekent) en koppel daaraan. Vind je haar daar, noem haar dan als
interpretatie met die vindplaats; vind je haar niet, noteer "onbekend, niet in deze bepaling" als open punt. Raad haar
niet.

## Voorbeeld 2: een uitzondering met een opsomming

**Bron.** Invorderingswet 1990, artikel 9, elfde lid, aanhef en onderdeel a:

> In afwijking van het eerste lid is een belastingaanslag die een uit te betalen bedrag behelst niet invorderbaar:
>
> a. zolang over de juistheid van het adresgegeven van de belastingschuldige gerede twijfel bestaat of zolang dit
> gegeven ontbreekt;

**Ontleding.** De aanhef geldt voor elk onderdeel; lees onderdeel a dus samen met de aanhef. *In afwijking van het
eerste lid* maakt dit een uitzondering op voorbeeld 1. *die een uit te betalen bedrag behelst* beperkt welke
aanslagen het betreft (beperkende bijzin). *niet* keert de invorderbaarheid om. In onderdeel a staan twee
alternatieve voorwaarden, verbonden door *of*.

**Markeringslijst (selectie).**

| ID | Letterlijk fragment | Klasse | Toelichting |
|---|---|---|---|
| E07 | In afwijking van het eerste lid | Voorwaarde | Uitzondering op N01 (de tekst zegt het letterlijk). |
| E08 | een belastingaanslag die een uit te betalen bedrag behelst | Rechtsobject | De bijzin beperkt de groep aanslagen; neem hem mee in het fragment. |
| E09 | zolang over de juistheid van het adresgegeven van de belastingschuldige gerede twijfel bestaat | Voorwaarde | Eerste alternatief van onderdeel a. |
| E10 | zolang dit gegeven ontbreekt | Voorwaarde | Tweede alternatief; *dit gegeven* verwijst naar het adresgegeven. |
| E11 | of | Operator | Logische of tussen E09 en E10, binnen onderdeel a. |
| E12 | de belastingschuldige | Rechtssubject | De partij wiens adres het betreft. |

**Een relatie die niet past.** Je wilt E07 met `uitzondering_op` aan E01 koppelen. De catalogus staat dat type
alleen toe naar een Rechtsbetrekking of Afleidingsregel, en E01 is een Rechtsfeit. Dan leg je **geen** relatie:
het verband staat in de toelichting van E07. Kiest de jurist voor het alternatief van E01 (Rechtsbetrekking), dan
past het type wel. Zo laat de catalogus zien dat twee keuzes samenhangen.

**Wat je níét doet.** Onderdeel a niet markeren zonder de aanhef; *niet invorderbaar* niet los als nieuwe klasse
markeren (het is dezelfde variabele als E03, met de waarde *nee*); *gerede twijfel* geen exacte drempel geven die de
wet niet geeft.

## Voorbeeld 3: een plicht zonder genoemde partij

**Bron.** Algemene wet bestuursrecht, artikel 4:13, eerste lid:

> Een beschikking dient te worden gegeven binnen de bij wettelijk voorschrift bepaalde termijn of, bij het ontbreken
> van zulk een termijn, binnen een redelijke termijn na ontvangst van de aanvraag.

**Ontleding.** Eén normeenheid (N03). Het gezegde *dient te worden gegeven* staat in de lijdende vorm: er is een
plicht, maar de zin zegt niet van wie. Twee termijnen, verbonden door *of*; de tweede geldt alleen *bij het ontbreken
van zulk een termijn*. *Een redelijke termijn* is een open norm.

**Markeringslijst.**

| ID | Letterlijk fragment | Klasse | Toelichting | Alternatief |
|---|---|---|---|---|
| E13 | Een beschikking dient te worden gegeven binnen de bij wettelijk voorschrift bepaalde termijn of, bij het ontbreken van zulk een termijn, binnen een redelijke termijn na ontvangst van de aanvraag. | Rechtsbetrekking | Dragende normzin: een plicht om tijdig te beslissen. Soort: aanspraak tegenover verplichting. Of nakoming is af te dwingen, staat niet in dit lid. | — |
| E14 | Een beschikking | Rechtsobject | Het voorwerp van de plicht. | — |
| E15 | binnen de bij wettelijk voorschrift bepaalde termijn | Tijdsaanduiding | De termijn zelf staat elders; daarom geen subtype. De verwijzing naar het wettelijk voorschrift gaat mee in het fragment. | — |
| E16 | bij het ontbreken van zulk een termijn | Voorwaarde | Bepaalt wanneer de tweede termijn geldt. | — |
| E17 | binnen een redelijke termijn na ontvangst van de aanvraag | Tijdsaanduiding | Open norm; de startgebeurtenis (*ontvangst van de aanvraag*) hoort bij de tijdsaanduiding. | Rechtsfeit voor *ontvangst van de aanvraag*, als je de ontvangst leest als de gebeurtenis die de plicht doet ontstaan. |
| E18 | of | Operator | Logische of tussen de twee termijnen. | — |

**Samenhang.**

| ID | Van | Type | Naar | Toelichting |
|---|---|---|---|---|
| R04 | E13 (rechtsbetrekking) | voorwerp | E14 | De plicht gaat over de beschikking. |
| R05 | E13 | tijd | E15 | De eerste termijn. |
| R06 | E13 | tijd | E17 | De tweede termijn. |
| R07 | E13 | voorwaarde | E16 | De tweede termijn geldt alleen onder deze voorwaarde. |

**De partijen die het lid niet noemt.** De zin noemt geen plichthebbende en geen rechthebbende. Een rechtsbetrekking
zonder partijen is niet af, dus je maakt ze expliciet, in deze volgorde:

1. Zoek waar de wet ze wel noemt. De definities van *beschikking* en *aanvraag* staan in artikel 1:3 van dezelfde wet;
   die lees je erbij.
2. Volgt daaruit wie de beschikking geeft en wie de aanvraag doet, noem ze dan als interpretatie: "plichthebbende: het
   bestuursorgaan; rechthebbende: de aanvrager; op grond van de definities in artikel 1:3 Awb". Geen
   aanhalingstekens, geen tekstanker in dit lid: het staat er niet.
3. Heb je artikel 1:3 niet gelezen, schrijf dan "onbekend, artikel 1:3 nog te lezen" als open punt.

**Wat je níét doet.** *Een redelijke termijn* een aantal weken geven; het tweede lid van het artikel zegt daar iets
over, en dat lees je, je raadt het niet. En de partij invullen zonder de vindplaats.

## Voorbeeld 4: een rekenregel

**Bron.** Invorderingswet 1990, artikel 28, tweede lid, eerste volzin:

> De invorderingsrente wordt enkelvoudig berekend over het tijdvak dat aanvangt op de dag waarop de belastingaanslag
> invorderbaar is ingevolge artikel 9 en eindigt op de dag voorafgaand aan die van de betaling.

**Ontleding.** Eén normeenheid (N04): een regel die zegt hóe iets wordt berekend. Uitkomst: *de invorderingsrente*.
Wat de zin zelf aan invoer geeft: het tijdvak, met een begin en een eind. Wat er níét staat: het percentage en het
bedrag waarover wordt gerekend. De tweede volzin van het lid is hier niet meegenomen.

**Markeringslijst.**

| ID | Letterlijk fragment | Klasse | Toelichting | Alternatief |
|---|---|---|---|---|
| E19 | De invorderingsrente wordt enkelvoudig berekend over het tijdvak dat aanvangt op de dag waarop de belastingaanslag invorderbaar is ingevolge artikel 9 en eindigt op de dag voorafgaand aan die van de betaling. | Afleidingsregel | Een rekenregel, gemarkeerd met werkwoord, verwijzing en zinseinde. | — |
| E20 | De invorderingsrente | Variabele en variabelewaarde | De uitkomst van de regel: een bedrag dat per aanslag verschilt. Subtype variabele. | Rechtsobject, als voorwerp van de plicht om rente te betalen (die plicht staat in het eerste lid). |
| E21 | enkelvoudig | Operator | Zegt hoe gerekend wordt: geen rente over rente. | Voorwaarde: een bijwoord bij het werkwoord kan een voorwaarde dragen (H2:64). |
| E22 | het tijdvak dat aanvangt op de dag waarop de belastingaanslag invorderbaar is ingevolge artikel 9 en eindigt op de dag voorafgaand aan die van de betaling | Tijdsaanduiding | Eén tijdvak; de verwijzing *ingevolge artikel 9* gaat mee. Het verschilt per aanslag, dus het verbijzondert hier een variabele. | — |
| E23 | de belastingaanslag | Rechtsobject | Waar de rente bij hoort. | — |

**Samenhang.**

| ID | Van | Type | Naar | Toelichting |
|---|---|---|---|---|
| R08 | E19 (afleidingsregel) | uitvoer | E20 | Precies één uitvoer. |
| R09 | E22 | invoer | E19 | Volgnummer 1: het tijdvak waarover gerekend wordt. |
| R10 | E21 | operator_in | E19 | De wijze van rekenen. |
| R11 | E20 (variabele) | kenmerk | E23 | De rente is een kenmerk van de aanslag. |

**Wat de samenhang laat zien.** De regel heeft een uitvoer en één invoer, maar een rente reken je niet uit zonder
percentage en bedrag. Die staan in andere bepalingen: het bedrag in het eerste lid, het begin van het tijdvak in
artikel 9, het percentage elders. De invoer van deze regel is dus voor een deel de uitkomst van een andere bepaling.
Leg dat vast met `invoer` naar een markering in die bepaling zodra je haar gelezen hebt, en noem het tot dan als open
punt. De keten van regels zelf werk je uit bij het opstellen van regels (activiteit 3b).

**Toetsen met een voorbeeldreeks.** Geef het begin en het eind van het tijdvak een paar waarden, en vraag per geval
of de uitkomst juridisch juist is:

- betaling drie weken na de dag van invorderbaarheid: een tijdvak van enkele weken (het normale geval);
- betaling op de dag van invorderbaarheid zelf: het eind ligt dan vóór het begin. Is het tijdvak dan leeg? De zin
  zegt het niet uitdrukkelijk: een grensgeval, en een reviewvraag;
- de dag van betaling is onbekend: de uitkomst is niet bepaalbaar.

## Voorbeeld 5: een regel ontleden in kleine regels

**Bron.** Invorderingswet 1990, artikel 9, vijfde lid, eerste volzin (hier samengevat, niet geciteerd): een voorlopige
aanslag in een van de genoemde belastingen, waarvan het aanslagbiljet is gedagtekend in het jaar waarover de aanslag is
vastgesteld, is invorderbaar in zoveel gelijke termijnen als er na de maand van de dagtekening nog maanden van het jaar
overblijven.

**Eén grote regel.** Je kunt dit als één regel schrijven: *bepalen aantal termijnen*, met als voorwaarden de soort
aanslag, de belasting en de ligging van de dagtekening. Dat klopt, maar de voorwaarden zijn dan zinsdelen. Een tweede
regel (het bedrag per termijn, de vervaldag per termijn) moet ze herhalen.

**Ontleed.** Elke voorwaarde die iets afleidt, wordt een begrip met een eigen regel:

| begrip | waardebereik | regel |
|---|---|---|
| soort van de aanslag; belasting van de aanslag | een van een vaste lijst | geen: invoer |
| jaar van de dagtekening; maand van de dagtekening | jaartal; maand | het jaar, de maand uit de dagtekening |
| de dagtekening ligt in het jaar van de aanslag | ja/nee | waar als het jaar van de dagtekening gelijk is aan het jaar waarover de aanslag is vastgesteld |
| de aanslag is een voorlopige aanslag in belasting X | ja/nee | waar als de soort "voorlopige aanslag" is en de belasting X (één regel per genoemde belasting) |
| de aanslag valt onder de termijnregeling | ja/nee | waar als de dagtekening in het jaar ligt en de aanslag een van de genoemde voorlopige aanslagen is |
| aantal termijnen | geheel getal, minstens 1 | twaalf min het nummer van de maand van de dagtekening, als de aanslag onder de termijnregeling valt; in de andere gevallen één |

De bovenste regel leest nu als een opsomming van uitkomsten van de regels eronder. De namen in de tabel zijn
omschrijvingen; de echte naam kies je met de [richtlijnen](begrippen.md).

**Wat de tekst open laat.** Is de dagtekening in de laatste maand, dan blijft er geen maand over. De derde volzin van
het lid zegt dat dan de hoofdregel geldt; in de regel is dat een eigen geval. Of het bedrag per termijn wordt afgerond
en waar het restant landt, zegt de tekst niet: dat is een open punt (ontbrekend uitvoeringsbeleid), geen stille keuze.

**Voorbeeldtabel** bij *aantal termijnen* (verzonnen gevallen):

| | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| valt onder de termijnregeling | ja | ja | nee | ja |
| maand van de dagtekening | april | december | april | (geen) |
| kan deze invoer zich voordoen? | ja | ja | ja | nee |
| aantal termijnen (voorspelling) | 8 | 1 | 1 | n.v.t. |
| juridisch juist? | door de jurist | door de jurist | door de jurist | n.v.t. |

## Wat de voorbeelden laten zien

- De hele normzin draagt de functie; de onderdelen krijgen daarnaast hun eigen markering.
- Een termijn is één Tijdsaanduiding, niet ook een Parameter.
- Een uitzondering in een ander lid hoort bij de analyse van het eerste lid.
- Een alternatief schrijf je op met reden; je kiest niet stil.
- Een partij die de tekst niet noemt, maak je expliciet met de bepaling waaruit zij volgt, of je noemt haar onbekend.
- Een rekenregel heeft precies één uitvoer; ontbreekt er invoer, dan staat die vaak in een andere bepaling.
- Een voorbeeldreeks vindt het geval dat de tekst niet uitdrukkelijk regelt.
- Een voorwaarde die zelf iets afleidt, is een begrip met een eigen regel; de regel erboven noemt alleen dat begrip.
- Een voorbeeldtabel bevat ook een geval dat niet kan.
