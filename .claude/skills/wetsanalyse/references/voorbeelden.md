# Uitgewerkte voorbeelden

Twee bepalingen uit de Invorderingswet 1990, letterlijk zoals ze in de kennisgraaf staan (wettekst is vrij van
auteursrecht). De duiding is een **voorbeeld van de werkwijze**, geen gouden standaard: een jurist kan op punten
anders kiezen, en dat is precies waarom alternatieven zichtbaar blijven.

## Inhoud

- Voorbeeld 1: één enkelvoudige normzin (art. 9, eerste lid)
- Voorbeeld 2: een uitzondering met een opsomming (art. 9, elfde lid, aanhef en onderdeel a)
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
| E04 | zes weken na de dagtekening van het aanslagbiljet | Tijdsaanduiding | Subtype *verbijzondert parameter*: de duur is voor iedereen gelijk, maar de functie is temporeel, dus geen tweede markering Parameter. | — |
| E05 | de dagtekening | Variabele en variabelewaarde | Een datum die per aanslagbiljet verschilt: het startmoment van de termijn. | — |
| E06 | het aanslagbiljet | Rechtsobject | Het stuk waarop de dagtekening staat. | — |

E02 tot en met E06 liggen binnen E01: dat is overlap met verschillende functies, geen dubbeling.

**Samenhang** (zie [relaties](relaties.md); de kolom Type is de code uit de catalogus).

| ID | Van | Type | Naar | Toelichting |
|---|---|---|---|---|
| R01 | E01 (rechtsfeit) | voorwerp | E02 | Het rechtsfeit raakt de aanslag. |
| R02 | E03 (variabele) | kenmerk | E02 | Invorderbaar is een eigenschap van de aanslag. |
| R03 | E01 | tijd | E04 | Wanneer het rechtsfeit intreedt. |

**Open punt.** Wie vordert in (de partij in de rechtsbetrekking)? Lid 1 noemt haar niet. Vul geen partij in; noteer
"impliciet, niet in deze bepaling" en volg de definities van de wet als de analysevraag dat vraagt.

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

## Wat de voorbeelden laten zien

- De hele normzin draagt de functie; de onderdelen krijgen daarnaast hun eigen markering.
- Een termijn is één Tijdsaanduiding, niet ook een Parameter.
- Een uitzondering in een ander lid hoort bij de analyse van het eerste lid.
- Een alternatief schrijf je op met reden; je kiest niet stil.
- Een partij die de tekst niet noemt, vul je niet in.
