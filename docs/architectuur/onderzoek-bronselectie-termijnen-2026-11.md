# Onderzoek: de bronselectie bij het werkgebied Termijnen (16 nov 2026)

Soort: *onderzoek* · Status: **voorstel, wacht op akkoord** · Hoort bij: [bronselectie per deelvraag](bronselectie-per-deelvraag.md)
(spoor J), [zoekvragen a–d](../../.claude/skills/wetsanalyse/references/zoekvragen-bronselectie.md), PR E (#1607)

De gebruiker maakte op acceptatie het werkgebied *Termijnen* aan en vond bij de kandidaten van Lex weinig bruikbare
bronnen. Dit document zegt wat er mist, waarom, en wat we voorstellen. Alles is gelezen. Er draaide geen beurt van Lex,
geen bronnenrun en geen eval met een model, en het werkgebied is niet gewijzigd.

## Het werkgebied

- **Analysevraag**: hoe wordt een negatieve voorlopige aanslag winstaandeel verwerkt op een positieve, en hoe werkt die
  door in de termijnbedragen van reeds geregistreerde termijnen?
- **Gebeurtenis**: *invordering*.
- **Zoekbereik**: Awb, AWR, Iw 1990, Awir, Uitv.reg. Iw 1990 en de Leidraad Invordering 2008.
- **Deelvragen**:
  - DV1: wat is een (negatieve) voorlopige aanslag winstaandeel?
  - DV2: hoe wordt de negatieve verrekend met de positieve?
  - DV3: hoe werkt die verrekening door in de reeds geregistreerde betalingstermijnen?
- **Laatste bronnenrun**: zoekversie `z4ec70aab4a55`. Met de methoden `deelvraag` (24, volledig), `grondslag` (5) en
  `overzicht` (40, **onvolledig**: plafond geraakt). Er zijn 59 kandidaten, waarvan 45 bij geen enkele deelvraag horen.

## Wat een jurist verwacht, en wat Lex vond

De kernbepalingen staan letterlijk in de graaf (gecontroleerd met `graaf_lezen` en `bron_lezen`):

- **AWR art. 13 lid 1 en 2**: de voorlopige aanslag. Lid 2 zegt dat een voorlopige aanslag tot een negatief bedrag
  *voorlopige teruggaaf* heet. Dat is de wettelijke naam van wat het dossier "negatieve voorlopige aanslag" noemt.
- **Iw 1990 art. 9 lid 5, 6 en 7**: de termijnen van een voorlopige aanslag. Lid 6 gaat over een aanslag "die een uit te
  betalen bedrag behelst": de negatieve.
- **Iw 1990 art. 24 lid 2**: verrekening ook vóór de termijn verstreken is. Bij een aanslag in termijnen alleen met een
  aanslag over dezelfde belasting en hetzelfde tijdvak. Dat is de kern van DV2.
- **Iw 1990 art. 2 lid 2**: het invorderen omvat ook het betalen van een terug te geven bedrag.
- **Leidraad art. 9.1, 9.2, 9.3 en 24.3**: de vervaldag van de laatste termijn, de termijnen van een voorlopige
  teruggaaf, en dat er niet automatisch verrekend wordt met een aanslag die nog niet invorderbaar is.
- **Het winstaandeel zelf** staat in de Mijnbouwwet. Die regeling zit niet in het zoekbereik en niet in de graaf:
  "winstaandeel" komt in geen enkele wettekst in de graaf voor.

Wat Lex per deelvraag voorstelde (8 plaatsen per deelvraag):

- **DV1**: Iw 9 lid 5 en lid 7 (bruikbaar, al passen ze beter bij DV3), Iw 10 lid 2 (randgeval) en vijf Leidraaddivisies
  over iets anders: 79.3, 79.5 en 79.5a (toeslagschuld), 10.3 (versnelde invordering) en 78.1 (bijstand bij invordering
  in de EU). AWR 13 lid 2 mist.
- **DV2**: Iw 9 lid 5 en 7 en Iw 10 lid 2 (bruikbaar of randgeval), Awir 30 lid 2 en Leidraad 79.3, 79.5 en 79.5a
  (toeslagen, ruis) en Iw 19 lid 1 (ruis). **Iw 24 mist.**
- **DV3**: Iw 16 (raakt het aansluiten van termijnen, maar gaat over beslag), Iw 15 lid 1, 19 lid 9, 28 lid 1 en 28a
  lid 2 (ruis), Awir 30 lid 2 en Leidraad 79.3 en 79.5 (ruis). **Iw 9 lid 6, Leidraad 9.x en Iw 24 lid 2 missen.**
- **Zonder deelvraag**: 40 artikelen uit de Awb (2:21–4:95, Bijlage 2), allemaal met de rol *kern*, plus enkele
  grondslagen. Ze komen uit het overzicht op de naam *Termijnen*: de Awb heeft "Wettelijke termijnen" en
  "Beslistermijn".

## Waarom: vijf oorzaken in de code

### O1. De gebeurtenis is te breed, en de pool neemt alle plaatsen

Met een gekozen gebeurtenis komen de opties per deelvraag uit de pool van de zoekvragen a–d (`zoekvragen.pool`,
`opties_bij_deelvraag`). Het zoeken op de woorden van de deelvraag (`bepaling_opties`) krijgt alleen de plaatsen die de
pool openlaat: `PLAATSEN_WOORDEN = 0` (`bronnen_vinden._deelvraag`). De pool had bij elke deelvraag 8 kandidaten, dus de
woordenroute droeg niets bij.

"Invordering" is de naam van de hele wet. De omgeving van de pool (de delen met "invorder" in de kop) is daarom Iw H II,
III, V, VII en VIIbis, Awb afd. 4.4.4, Uitv.reg. H III en Awir art. 31a, 32 en 34. Van de Leidraad komen de hoofddivisies
10, 78 en 79 mee, waaronder de toeslagschuld. Iw H IV afd. 2 *Verrekening* (art. 24) heeft "invorder" niet in de kop.
AWR art. 13 en Leidraad 9 vallen er om dezelfde reden buiten. Precies de verwachte bronnen komen zo nooit in de pool. Ze
zouden er via de woordenroute wél in kunnen komen ("verrekening", "voorlopige", "termijn" staan in hun tekst), maar die
route krijgt geen plaats.

Generiek: de pool werkt als filter als de gebeurtenis specifiek is ("kwijtschelding"). Bij een gebeurtenis die een
groot deel van de regelingen omvat, filtert hij niets meer, en dan sluit de vaste nul de deelvraag zelf buiten.

### O2. De vraagvorm "Wat is …" geeft elke beleidsdivisie de grootste bonus

`VRAAGVORM` wijst bij "Wat is …" zoekvraag d aan. In de pool draagt elke subdivisie van een beleidsregel zoekvraag d
(`signaal: beleidsregel`). `opties_bij_deelvraag` geeft een kandidaat met de passende zoekvraag de bonus van het
sterkste woord. Hij laat de kandidaat ook toe zonder één woord van de deelvraag (`if not (g or past)`). Zo staan bij DV1
vijf Leidraaddivisies over toeslagen en EU-bijstand. Een "wat is"-vraag vraagt om een begripsbepaling: een beleidsregel
die iets anders invult, past daar niet bij. De skill noemt beide d, maar ze verschillen voor de rangschikking.

### O3. Een samenstelling raakt op haar eerste woord

`_stamdeel` neemt de eerste acht letters van de stam, en `_raakt` toetst daarop. "Betalingstermijnen" raakt dan elke
tekst met "betaling", "belastingjaar" en "belastingschuld" elke tekst met "belasting". Het onderscheidende deel valt
weg: "termijn", "jaar" en "schuld". Dat is het omgekeerde van wat de vlag `samenstelling` in de index bedoelt. De
telling in `opties_bij_deelvraag`, `_raakt` in `bepaling_opties` en het idf-gewicht gebruiken allemaal dezelfde stam. Een
lange tekst met veel gewone woorden wint zo van een kort lid met het precieze woord (Leidraad 79.3 tegen Iw 9 lid 6).

### O4. Brugtermen komen uit de analysevraag, niet uit een omschrijving

"Winstaandeel", "negatieve" en "geregistreerde" staan in geen kandidaat van de pool. `brugtermen` zoekt dan woorden uit
de dossierzinnen die zo'n woord noemen. De enige zinnen zijn de analysevraag, de context (dezelfde tekst) en het
praktijkvoorbeeld. Zij leveren "termijnbedragen", "termijnen", "belastingjaar", "belastingschuld", "dagtekening",
"vastgesteld" en "bedrag". Die woorden staan overal, en via O3 nog vaker. Bij DV1 bestaat het hele bewijs (`raakt`)
daarom uit brugwoorden. De zin die een woord *omschrijft* gaat voor, maar er is er geen. Dan brugt elke zin die het
woord noemt, en dat is ruis.

De echte brug staat in de wet: AWR 13 lid 2 omschrijft "voorlopige aanslag tot een negatief bedrag" als *voorlopige
teruggaaf*. De importer kent die definitie niet: hij herkent "wordt verstaan onder", niet "wordt aangeduid als". Er is
dus geen `bwb:definieertBegrip` voor "voorlopige teruggaaf", en de definitieroute vindt haar niet.

### O5. Het overzicht draait op de naam van het werkgebied

Zonder kern draait de methode `overzicht` (`ZONDER_KERN`). De analysevraag heeft geen overzichtsvorm, dus neemt
`_overzicht` de naam: *Termijnen*. Dat levert 40 Awb-artikelen over beslistermijnen en wettelijke termijnen op, met de
rol *kern* en zonder deelvraag, en het plafond `MAX_OVERZICHT` maakt de run onvolledig. Een naam van één algemeen woord
is geen onderwerp. En het werkgebied heeft deelvragen, die het eigenlijke vertrekpunt zijn.

### De vlaggen van PR E helpen hier niet

`verwijzingen` en `onderscheidend` werken alleen in `bepaling_opties`, dus in de woordenroute. Door O1 krijgt die route
hier geen plaats, en dan maken de vlaggen niets uit. `onderscheidend` zou "negatieve", "voorlopige" en "aanslag"
(gedeeld door alle drie de deelvragen) naar het dossier verplaatsen. Dat is zinnig, maar pas als O1 is opgelost.

## Voorstellen, elk generiek

Geen van de voorstellen kent dit werkgebied, het woord "termijn" of een regeling. Elk verandert één algemeen mechanisme.

1. **De woordenroute krijgt plaatsen als de pool niet filtert (O1).** We meten hoe breed de pool is: het aandeel van de
   bepalingen van een regeling dat in de omgeving valt, of het aantal kandidaten tegen `MAX_OMGEVING`. Boven een grens
   (vooraf vastgelegd, niet afgestemd op deze set) krijgt de woordenroute een vast aantal plaatsen, net als zonder
   gebeurtenis. Een alternatief is per kandidaat: wie in de pool geen eigen deelvraagwoord raakt (alleen een brug of
   een bonus), wijkt voor een treffer van de woordenroute die er wel een raakt. PR 5 mat vaste plaatsen als slechter op
   de vier ontwikkelsets, daarom alleen voorwaardelijk.
2. **De bonus van de vraagvorm vraagt een eigen woord (O2).** `past` telt alleen als de kandidaat ook een woord van de
   deelvraag raakt, geen brugwoord. Daarnaast splitsen we zoekvraag d in *definitie* (begripsbepaling, `verstaan`,
   `aangeduid`) en *beleid* (beleidsregel). "Wat is …" geeft dan alleen de definitie de bonus.
3. **Een samenstelling raakt op haar hele stam of haar kern (O3).** `_raakt` en het idf-gewicht toetsen een term van meer
   dan acht letters op zijn hele stam ("betalingstermijn"), of op zijn laatste deel van minstens vijf letters
   ("termijn"), niet op het eerste. De index-query (`splitsingen`) blijft breed zoeken; alleen het raken en wegen wordt
   precies. Dit raakt elke rangschikking, dus meten op alle sets.
4. **Brugtermen alleen uit een omschrijving, en de wet als brug (O4).** `brugtermen` gebruikt alleen nog een zin die
   het woord omschrijft ("X is …", "X betekent …"). Zonder omschrijving geen brug, en zegt Lex dat het woord in de
   regelingen ontbreekt (`ontbrekende_woorden` bestaat al, maar komt nu niet per deelvraag terug). Daarnaast herkent de
   importer ook "wordt aangeduid als" (en verwante vormen) als `bwb:definieertBegrip`. De definitie wordt een brug: een
   deelvraagwoord in de omschrijving brengt de gedefinieerde term mee als zoekterm ("negatieve voorlopige aanslag" →
   "voorlopige teruggaaf").
5. **Het overzicht niet op een kale naam, niet naast deelvragen (O5).** Met deelvragen draait `overzicht` niet: de
   deelvragen zijn het vertrekpunt. Zonder deelvragen gebruikt hij de naam alleen als die meer dan één inhoudswoord heeft
   of in een kop van de regelingen staat. Wat het overzicht oplevert, krijgt de rol *aanverwant*, niet *kern*.
6. **Een woord dat in het zoekbereik ontbreekt, zeggen (O4, deelvraagniveau).** "Winstaandeel" staat in geen regeling
   van het zoekbereik. Lex hoort dat bij de deelvraag te melden, met het aanbod om buiten het zoekbereik te zoeken (de
   connector *wetgeving buiten de kennisgraaf* vindt de Mijnbouwwet). Dit is een signaal uit code, geen keuze voor de
   jurist.

## Meten

- **Een nieuwe ontwikkelset** `termijnen-deelvragen-concept` in `docs/wetsanalyse/referentieset-bronselectie/`. Daarin de
  drie deelvragen, de gebeurtenis, het zoekbereik en de verwachte bepalingen hierboven, met een rol en een motivering. De
  Leidraaddivisies 79.x, 10.3 en 78.1 en de Awb-beslistermijnen komen erin als uitgesloten. De status blijft *concept*
  tot een jurist de set vaststelt.
- **Offline met `eval/bronselectie_eval.py --intake`** (en `--zoekvragen` voor de pool). Die meet `recall_nodig`,
  `recall_pool`, `precisie` en `uitgesloten` per deelvraag, op deze set en op de bestaande vijf ontwikkelsets. Elk
  voorstel staat als eigen vlag in `Zoekprofiel` (of naast `PLAATSEN_WOORDEN`), standaard uit, zodat de meting ze apart
  aan- en uitzet. Een voorstel gaat pas standaard aan als het hier helpt en op geen bestaande set verslechtert.
- **Een opname is nodig.** `graafantwoorden.json` maken vraagt `--opnemen`, met de verbinding naar de graaf van
  acceptatie. Die gegevens staan niet in de repo, dus dat is een stap van de gebruiker.
- **Voorstel 4 (importer) meten we apart.** We tellen de nieuwe definities over de geïmporteerde regelingen, toetsen een
  steekproef met de hand (geen vals positief "aangeduid als" in een andere zin) en draaien de definitieroute op de sets.
- **Geen winst claimen op deze set alleen.** De oorzaken zijn op dit werkgebied gevonden, dus het is een ontwikkelset.
  Bewijs vraagt een **blinde set uit een ander werkgebied**, opgesteld voordat de meting draait. Voorstel 1 en 3 raken
  elke rangschikking en vragen dat het meest.

## Open keuzes voor de gebruiker

- Hoort de Mijnbouwwet in de graaf (importeren), of blijft het winstaandeel bij de connector buiten de graaf?
- Welke voorstellen eerst? Voorstel 1, 2 en 5 zijn klein en lossen de meeste ruis op. Voorstel 3 en 4 zijn breder.
- Mag een opname van de graafantwoorden voor de nieuwe set gemaakt worden, en wie stelt de blinde set op?
