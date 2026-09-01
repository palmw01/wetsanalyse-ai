---
name: wetsanalyse
description: >-
  Voert Wetsanalyse uit op Nederlandse wet- en regelgeving volgens de methode
  Wetsanalyse (Ausems, Bulles & Lokin) en het Juridisch Analyseschema (JAS):
  activiteit 2 (wetsformuleringen markeren en classificeren in JAS-klassen). Dit is de
  inhoudelijke methodebeschrijving; het draaiende platform voert de analyse uit in de
  werkplek. Gebruik deze skill zodra de gebruiker een wetsartikel of regeling juridisch
  wil analyseren, structureren, ontleden of "wetsanalyse" wil doen – ook bij vragen als
  "classificeer dit artikel", "welke rechtssubjecten/rechtsbetrekkingen/voorwaarden zitten
  hierin", "ontleed deze bepaling juridisch", of wanneer een bepaling brongetrouw en
  uitlegbaar moet worden vastgelegd voor uitvoering (bijvoorbeeld bij de Belastingdienst).
  Trigger ook bij twijfel: dit is de aangewezen werkwijze voor het gestructureerd duiden
  van de betekenis van wetgeving.
---

# Wetsanalyse — activiteit 2: markeren en classificeren

Wetsanalyse maakt de betekenis van wetgeving expliciet, traceerbaar en uitlegbaar, zodat besluiten
in de uitvoering te verantwoorden zijn. Deze skill dekt **activiteit 2**: relevante
wetsformuleringen *markeren* (2a) en elke markering een *klasse* uit het Juridisch Analyseschema
geven (2b).

**De eenheid van analyse is de formulering, niet het artikel of het lid.** Eén lid levert vrijwel
altijd meerdere markeringen op.

**Dit is een hulpmiddel, geen vervanger van de analist.** Lever een onderbouwd, eerlijk concept:
classificeer wat helder is, en benoem twijfel, aannames en open normen als zodanig. Een analyse die
haar eigen onzekerheden benoemt is waardevoller dan een gladde die ze verbergt.

## Brongetrouwheid is niet onderhandelbaar

- **Werk alleen met letterlijk opgehaalde wettekst.** Verzin nooit tekst, leden of artikelnummers.
- **Elk gemarkeerd fragment staat letterlijk in de bron** — teken voor teken, aaneengesloten. Kun
  je een element niet met een letterlijk fragment onderbouwen, neem het dan niet op als markering;
  benoem het in de toelichting.
- **Houd alles herleidbaar**: elke markering verwijst naar artikel + lid en, waar beschikbaar, de
  `bronreferentie` (jci-uri).
- **Gebruik uitsluitend de dertien JAS-klassen** hieronder. Verzin geen eigen klassen.

## De dertien klassen

De officiële JAS-tabel (`docs/wetsanalyse/wa-table.png`) nummert zestien rijen; onze labelset
voegt drie paren samen. De korte definities hieronder komen uit die tabel.

| Klasse | Wat het is | Herken aan |
| --- | --- | --- |
| **Rechtssubject** | Drager van rechten en plichten. Natuurlijke persoon of rechtspersoon. Partij in een rechtsbetrekking of bij een rechtsfeit. | Zelfstandig naamwoord voor persoon/entiteit; ‘hij’, ‘zij’, ‘iemand’, ‘een ieder’, ‘degene’ |
| **Rechtsobject** | Voorwerp van een rechtsbetrekking of rechtsfeit, fysiek of niet-fysiek. | Zelfstandig naamwoord (een woning, medische zorg); ‘dat’, ‘hetgeen’, ‘welk(e)’ |
| **Rechtsbetrekking** | Juridische relatie tussen twee rechtssubjecten: de een rechthebbend, de ander plichthebbend. | Werkwoord(combinatie): ‘heeft recht op’, ‘kan verzoeken’ (recht); ‘stelt vast’, ‘is verplicht’, ‘dient te’ (plicht) |
| **Rechtsfeit** | Handeling, gebeurtenis of tijdsverloop dat een wijziging in de juridische toestand teweegbrengt. | Actieve werkwoordsvorm, vaak genominaliseerd: ‘indienen van een bezwaarschrift’ |
| **Voorwaarde** | Conditie bij een rechtssubject, rechtsobject, rechtsbetrekking, rechtsfeit of afleidingsregel. | ‘indien’, ‘als’, ‘mits’, ‘tenzij’, ‘met uitzondering van’; ook een bijwoord: ‘schriftelijk’ |
| **Afleidingsregel** | Regel die op basis van bestaande feiten of waarden nieuwe feiten of waarden creëert. | ‘verminderd met’, ‘bedraagt’, ‘wordt gesteld op’, ‘het gezamenlijke bedrag van’ |
| **Variabele en variabelewaarde** | Waarde die per rechtssubject, rechtsobject, rechtsbetrekking of rechtsfeit kan verschillen (+ die waarde). | Getal, datum, tekst, enumeratie (limitatieve opsomming), booleaans (ja/nee) |
| **Parameter en parameterwaarde** | Waarde die over een (bepaalde of onbepaalde) periode gelijk is voor allen (+ die waarde). | Tarief, percentage, (drempel)bedrag, vrijstelling |
| **Operator** | Bewerking, vergelijking of logische verbinding. | ‘de som van’, ‘vermeerderd met’; ‘groter dan’, ‘is gelijk aan’; ‘en’, ‘of’, ‘niet’, ‘ten minste’ |
| **Tijdsaanduiding** | Aanduiding van een tijdstip of tijdvak. | Concrete datum, ‘kalenderjaar’, ‘maand’, ‘week’ |
| **Plaatsaanduiding** | Aanduiding van een plaats of gebied. | ‘Nederland’, ‘de gemeente Amsterdam’, ‘een lidstaat van de EU’ |
| **Delegatiebevoegdheid en delegatie-invulling** | Bevoegdheid om in lagere regelgeving nadere regels te stellen (+ de regeling die dat invult). | ‘bij (of krachtens) amvb / ministeriële regeling worden regels gesteld’ (verplicht); ‘kunnen regels worden gesteld’ (facultatief) |
| **Brondefinitie** | In de wetgeving opgenomen definitie. | Definitieartikel met aanhef en onderdelen, vaak vooraan de regeling |

Voor de volledige omschrijving, de herkenningsvragen en de uitdrukkingswijze per klasse: zie
`references/jas-klassen-referentie.md`. Raadpleeg dat bestand bij twijfel of samenloop.

## Werkwijze

Gebruik de **herkenningsvraag** per klasse als grammaticale ontleedvraag op de tekst, zoals bij
zinsontleding.

1. **Anker aan een centrale klasse.** Zoek eerst de *rechtsbetrekking*, het *rechtsfeit*, de
   *afleidingsregel* of de *voorwaarde* die de bepaling draagt.
2. **Hang de rest daaraan op**: wie is rechthebbende, wie plichthebbende, wat is het rechtsobject,
   onder welke voorwaarden geldt het.
3. **Ga daarna de diepte in**: bij elke voorwaarde de variabelen waaraan getoetst wordt; daarna
   operatoren, parameters, tijds- en plaatsaanduidingen, delegaties en brondefinities.
4. Bij een bepaling die iets berekent: begin bij de formulering die de **uiteindelijke waarde**
   vaststelt en werk terug naar de invoervariabelen.

**Fragmentgrenzen.** Markeer precies zoveel tekst als nodig is om de betekenis van het element
volledig te dragen. De klasse bepaalt de omvang: bij een *variabele* geen werkwoord en geen
voorwaarden, bij een *afleidingsregel* juist wel, bij een *voorwaarde* de hele zin of het hele
zinsdeel. Neem het lidwoord mee, en een verwijzing als die de betekenis draagt.

**Markeringen mogen overlappen** — dat is de verwachte uitkomst, niet een fout. Een voorwaarde
bevat vrijwel altijd variabelen; een rechtsbetrekking bevat haar subjecten en object.

Volledige markeerregels — opsommingen, verwijzende voornaamwoorden, homoniemen, en wat je juist
*niet* markeert — staan in `references/markeren-fragmentgrenzen.md`.

## Samenloop: de meest specifieke klasse wint

De bron geeft één expliciete prioriteitsregel, tweemaal (`H2-JAS.md:107` en `:116`):

> Een formulering kan zowel tot de klasse tijdsaanduiding [resp. plaatsaanduiding] als tot de
> klasse parameter of variabele behoren. Als dat zich voordoet, kiezen we bij de analyse voor de
> meest specifieke klasse.

Dus: **tijdsaanduiding en plaatsaanduiding winnen van variabele en parameter.** De reden is dat een
tijdsaanduiding de duur van een rechtsbetrekking of het moment van een tijdsverloop bepaalt, en dat
belang rechtvaardigt een eigen klasse.

Bij andere samenloop geeft de taxonomie uit `H3-Kader.md` de richting — hoe dieper in de boom, hoe
specifieker: voorwaarde ⊃ afleidingsregel ⊃ {operator, variabele ⊃ {variabelewaarde,
tijdsaanduiding, plaatsaanduiding}, parameter ⊃ parameterwaarde}.

**Twijfel je nog?** Kies de best passende klasse en noteer het alternatief expliciet als
alternatief, met een korte motivatie. Forceer geen zekerheid die er niet is.

## Voorbeeld

De zin uit artikel 9, eerste lid, Invorderingswet 1990 zoals de eval-set hem draagt
(`tools/graph-qa/eval/`):

> Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.

| fragment | klasse | waarom |
| --- | --- | --- |
| `Een belastingaanslag` | Rechtsobject | Waar gaat de invorderbaarheid over? Zelfstandig naamwoord met lidwoord. |
| `Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet` | Rechtsbetrekking | De formulering die de juridische toestand draagt: vanaf wanneer mag worden ingevorderd. |
| `zes weken na de dagtekening van het aanslagbiljet` | Tijdsaanduiding | Vanaf welk moment? Tijdvak vanaf een gebeurtenis — wint van variabele/parameter. |

Let op wat hier gebeurt: drie markeringen op één zin, deels overlappend. De ontvanger als tweede
partij in de rechtsbetrekking staat **niet** in deze zin — die noem je in de toelichting, je
markeert hem niet.

## Buiten de huidige scope

Benoem deze wel als je ze tegenkomt, maar lever ze niet als markering:

- **Deelactiviteit 2c** (een structuurdiagram rond een centrale klasse) — de methode kent hem, dit
  platform levert hem niet.
- **Activiteit 3** (begrippen en begripsdefinities maken bij de markeringen) en de
  RegelSpraak-formalisering.
- **Subklassen** van rechtsbetrekking (aanspraak/bevoegdheid/immuniteit/vrijheid) en van rechtsfeit.
  Het annotatiecontract draagt alleen de dertien klassen; een subtype heeft nergens een veld.

## Kwaliteitscheck voordat je oplevert

- Staat elk gemarkeerd fragment **letterlijk** in de opgehaalde tekst?
- Is elke markering herleidbaar naar artikel + lid (en bronreferentie)?
- Zijn alle klassen uit de dertien, en geen verzonnen klassen?
- Heb je fijnmazig genoeg gewerkt — meerdere markeringen per lid, overlap waar die hoort?
- Is bij samenloop de meest specifieke klasse gekozen, en staat het alternatief genoteerd?
- Zijn interpretatiekeuzes en twijfel expliciet benoemd in plaats van weggepoetst?
- Heeft een mens het resultaat beoordeeld voordat het als vastgesteld geldt?

## Verder lezen

- `references/jas-klassen-referentie.md` — de dertien klassen volledig, uit de bron, met
  regelverwijzingen.
- `references/markeren-fragmentgrenzen.md` — hoe je markeert: grenzen, overlap, opsommingen,
  verwijzingen, homoniemen.
- `references/verwijzingen-volgen.md` — het volg-beleid voor kruisverwijzingen. Hoort bij het
  afbakenen van een werkgebied over meerdere bronnen, niet bij het annoteren van één bepaling.
