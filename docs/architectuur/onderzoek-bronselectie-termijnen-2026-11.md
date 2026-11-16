# Onderzoek: de bronselectie bij het werkgebied Termijnen (16 nov 2026)

Soort: *onderzoek en plan* · Status: **plan, wacht op het sein om te bouwen** · Hoort bij: [bronselectie per deelvraag](bronselectie-per-deelvraag.md)
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

### O6. Hoogstens zes zoektermen, in de volgorde van de zin (uit de nulmeting)

`kandidatenpool` neemt de eerste `MAX_TERMEN` (6) termen van de deelvraag, in de volgorde waarin ze staan. Bij DV3 zijn
dat "werkt, verrekening, negatieve, voorlopige, aanslag, bedragen". Het onderscheidende "betalingstermijnen" valt
erbuiten, terwijl een vulwoord als "werkt" blijft. `zoektermen` kent de lijst `LEGE_WOORDEN` van de zoekvragen niet. De
zes plaatsen gaan dus naar wat vooraan staat, niet naar wat iets zegt.

### O7. Om de beurt over zes regelingen (uit de nulmeting)

`per_regeling` geeft de plaatsen op het kaartje om de beurt aan de regelingen, de hoogste soort eerst. Dat was een
remedie tegen een beleidsregel die het kaartje vulde, gemeten op werkgebieden met twee of drie regelingen. Met zes
regelingen krijgt elke regeling ongeveer één plaats, ook een regeling zonder sterke treffer. Bij Termijnen kiest de
woordenroute zo per deelvraag Awb 8:80b, AWR 30fa, Iw 16, Awir 30, Uitv.reg. 8 en Leidraad 26.1.9. Haar pool bevat alle
verwachte bepalingen (recall_pool 1,00), en toch komt er bij DV1 en DV2 geen in de top 8.

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

## Plan: alle voorstellen in één traject

Besluit van de gebruiker (16 nov 2026): alle voorstellen in één plan. Elke stap wordt een eigen PR. De stappen zijn klein
en lossen elk één oorzaak op. Vóór het bouwen toetst elke stap of dit de beste ingreep is: welke alternatieven er zijn,
en waarom deze. Elke ingreep komt achter een vlag die standaard uit staat (`Zoekprofiel`, of een constante in
`bronnen_vinden`), zodat de meting hem apart aan- en uitzet. Pas stap 8 zet de vlaggen aan die winnen. Elke stap
verandert de zoekcode en dus `ZOEKVERSIE`, zodat een werkgebied na de uitrol opnieuw zoekt. De hoofdsessie bundelt en
merget.

### Stap 0 – De meetbasis (vóór elke codewijziging)

- Ontwikkelset `termijnen-deelvragen-concept` (schema 3, met gebeurtenis): de drie deelvragen, het zoekbereik, de
  verwachte bepalingen uit dit document met rol en motivering, en de uitgesloten bepalingen. De Mijnbouwwet staat onder
  *buiten de graaf* en telt niet in de noemer.
- `graafantwoorden.json` voor deze set, en `--aanvullen` voor de bestaande sets. Elke stap stelt nieuwe vragen aan de
  graaf, dus een stap neemt bij zijn meting ook de nieuwe vragen op.
- De nulmeting met `--intake` en `--zoekvragen` op alle zes de ontwikkelsets, vastgelegd in het meetlogboek
  (`docs/architectuur/metingen/`). Die staat vóór de eerste codewijziging.
- **Vraagt de gebruiker**: de opname draait live tegen de graaf van acceptatie, met verbindingsgegevens die niet in de
  repo staan.

**Uitkomst (16 nov 2026).** De set, de opnames en de nulmeting staan, zie
[`metingen/bronselectie-2026-11-16-nulmeting/`](metingen/bronselectie-2026-11-16-nulmeting/README.md). Op vijf van de
zes sets vindt de woordenroute vrijwel alles (pool 0,84–1,00), maar haar top 8 haalt daar 0,00–0,53 van. Daarom
komen de stappen 1a en 1b vóór stap 1: plaatsen geven aan een route die slecht rangschikt, helpt niet.

### Stap 1a – Zoektermen op onderscheidend vermogen, niet op zinsvolgorde (O6)

- **Ingreep**: `zoektermen` laat de lege woorden en de woorden van de vraagvorm weg (de lijsten van `zoekvragen`, op één
  plek). Daarna kiest `kandidatenpool` de `MAX_TERMEN` termen met het hoogste onderscheidend vermogen in de regelingen
  van het werkgebied (idf uit één telquery per term, met de index die er al is), in plaats van de eerste zes. Vlag
  `termen_idf`.
- **Toets**: een hogere `MAX_TERMEN` is het alternatief. Dat maakt de OR-query breder en de per-termlijsten talrijker,
  zonder de vulwoorden weg te halen.
- **Meten**: `recall_pool` mag niet dalen, `recall_nodig` hoort te stijgen.

### Stap 1b – Om de beurt alleen tussen regelingen met een sterke treffer (O7)

- **Ingreep**: `om_de_beurt` geeft alleen een plaats aan een regeling waarvan de beste kandidaat een fusiescore haalt van
  minstens een vast deel van de beste score over alle regelingen. Een regeling daaronder doet niet mee. De grens leggen
  we vooraf vast. Vlag `beurt_sterk`.
- **Toets**: `per_regeling` uitzetten is het alternatief. Dan komt het probleem terug waarvoor het bestond: een
  beleidsregel met lange divisies vult het kaartje. Op de sets van november moet het effect behouden blijven.
- **Meten**: precisie en `recall_nodig` op alle sets, en het aandeel bepalingen uit de Leidraad op het kaartje.

### Stap 1 – De woordenroute wijkt niet voor een pool die niet filtert (O1)

- **Ingreep**: in `bronnen_vinden._deelvraag` verdringt een treffer van de woordenroute (`bepaling_opties`) die een eigen
  woord van de deelvraag raakt, een optie uit de pool die dat niet doet. Zo'n poolkandidaat staat er alleen door een
  brugwoord of de bonus van de vraagvorm. Vlag `woorden_voor_pool`.
- **Alternatieven en toets**: (a) vaste plaatsen voor de woordenroute (`PLAATSEN_WOORDEN`) zijn in PR 5 gemeten en waren
  slechter; (b) een grens op de breedte van de omgeving vraagt een drempel die we op geen set kunnen afstemmen; (c) per
  kandidaat verdringen heeft geen drempel en laat een specifieke gebeurtenis ongemoeid, omdat haar pool de deelvraag wel
  raakt. We bouwen (c) en meten (b) ernaast als variant, met de drempel vooraf vastgelegd.
- **Signaal**: omvat de omgeving van de gebeurtenis een groot deel van een regeling, dan zegt Lex dat bij het kaartje
  van de gebeurtenis, met de vraag of het smaller kan ("invordering" omvat bijna de hele wet).
- **Meten**: `recall_nodig` en `recall_pool` per deelvraag. Op de termijnenset moeten Iw 24 lid 2 en AWR 13 lid 2 in de
  top 8 komen. Op de vier sets van PR 5 mag niets dalen.

### Stap 2 – De bonus van de vraagvorm vraagt een eigen woord (O2)

- **Ingreep**: in `zoekvragen.opties_bij_deelvraag` telt `past` alleen als de kandidaat ook een eigen woord van de
  deelvraag raakt, geen brugwoord. Zoekvraag d wordt in de pool twee signalen: `definitie` (een begripsbepaling, en de
  invullingen `verstaan`, `begrepen`, `gelijkgesteld`) en `beleid` (een subdivisie van een beleidsregel). "Wat is …"
  geeft alleen de definitie de bonus. Vlag `vraagvorm_eigen_woord`.
- **Toets**: de skill houdt beide onder d. We veranderen de zoekvraag niet, alleen het gewicht in de rangschikking, en
  het bewijs blijft `zoekvraag: d`.
- **Meten**: `precisie` en `uitgesloten` per deelvraag (Leidraad 79.x hoort uit DV1 te verdwijnen), en `recall_nodig`
  op de sets met een "wat is"-deelvraag.

### Stap 3 – Het overzicht niet naast deelvragen en niet op een kale naam (O5)

- **Ingreep**: in `bronnen_vinden.standaard_voor` draait `overzicht` niet als het werkgebied deelvragen heeft. Zonder
  deelvragen gebruikt `_overzicht` de naam alleen als die meer dan één inhoudswoord heeft of in een kop van de regelingen
  staat. Wat het overzicht vindt, krijgt de rol *aanverwant* (`overzicht_aanverwant`).
- **Toets**: het overzicht was bedoeld voor een werkgebied zonder vertrekpunt (meting 15 okt 2026). Met deelvragen is er
  een vertrekpunt, en op de naam vond het hier alleen ruis. Een alternatief was het overzicht beperken tot treffers die
  een deelvraagwoord raken. Dat doet de woordenroute al.
- **Meten**: het aantal kandidaten zonder deelvraag en `overbodig`. Die horen bijna 0 te worden, zonder verlies aan
  `recall`.

### Stap 4 – Een samenstelling raakt op haar hele stam of haar kern (O3)

- **Ingreep**: `zoektermen._raakt` en de idf-telling in `opties_bij_deelvraag` toetsen een term van meer dan acht letters
  op zijn hele stam ("betalingstermijn"), of op een deel aan het eind van minstens vijf letters dat zelf een woord in de
  index is ("termijn"). Het eerste deel ("betaling") telt niet meer. De index-query (`splitsingen`) blijft breed. Vlag
  `stam_heel`.
- **Toets**: dit raakt elke rangschikking, ook de intake. De samenstellingsvlag van november was voor de index bedoeld,
  niet voor het raken. Het alternatief, de lengte dempen (`lengte`), kostte in november recall; dit pakt de oorzaak.
- **Meten**: op alle zes de sets, `recall_nodig` en `precisie`. Een daling op één set is een reden om de stap niet aan te
  zetten.

### Stap 5 – Brugtermen alleen uit een omschrijving, en de kloof per deelvraag (O4, O6)

- **Ingreep**: `zoekvragen.brugtermen` gebruikt alleen een zin die het woord omschrijft ("X is …", "X betekent …"). Zonder
  omschrijving geen brug. Het bewijs zegt dan dat het woord ontbreekt, en `bronselectie._kloof` meldt het bij de
  deelvraag, ook als er wel iets gevonden is: "‘winstaandeel’ staat niet in de regelingen van dit werkgebied". Staat de
  connector *wetgeving buiten de kennisgraaf* aan, dan biedt het kaartje aan om de regelingen te zoeken die het woord
  wél noemen. Vlag `brug_omschrijving`.
- **Toets**: de brug van Rekeningafspraken kwam uit een omschrijvende zin, dus die blijft werken. Het melden bestaat al
  (PR 6), maar alleen als Lex niets vond.
- **Meten**: Rekeningafspraken (recall gelijk) en termijnen (geen brugwoorden meer in het bewijs bij DV1). De melding toetst
  een unittest.

### Stap 6 – De wet als brug: "wordt aangeduid als" (O4)

- **Ingreep**: de parser (`bronmodel/bwb/parser.py`, gedeeld door importer en api) herkent een vierde definitievorm: "…
  wordt aangeduid als X" en "… hierna: X", aan het eind van een zin en met de term als korte naamwoordgroep. De term komt
  op `bwb:definieertBegrip`. Daarna een brug in `deelvraag_zoeken`: raakt een deelvraagwoord de omschrijving van zo'n
  definitie, dan zoekt de gedefinieerde term mee ("negatieve voorlopige aanslag" → "voorlopige teruggaaf"). Vlag
  `definitie_brug`.
- **Toets**: een wijziging aan `bronmodel` raakt de api, graph-qa en de importer. Een herimport verandert de graaf, dus
  ook de begrippen die het paneel bij een antwoord toont (`samenhang_antwoord`). Vóór het aanzetten tellen we de nieuwe
  definities over alle geïmporteerde regelingen en toetsen we een steekproef met de hand (geen "hierna: de wet" als
  begrip).
- **Meten**: het aantal nieuwe definities, de steekproef, en op de sets `recall_nodig` voor DV1-achtige vragen.

### Stap 7 – De vlaggen van PR E opnieuw meten

Na stap 1 krijgt de woordenroute plaatsen, en dan kunnen `verwijzingen` en `onderscheidend` iets uitmaken. We meten ze
met `--intake --b2` op alle sets, met dezelfde regel als hierboven.

### Stap 8 – Eindmeting en aanzetten

- Een **blinde set uit een ander werkgebied**, opgesteld voordat de meting draait, door iemand anders dan wie de code
  schreef (of door de agent-jurist op acceptatie, met akkoord).
- Eén run per configuratie (licht meten): de standaard, en de standaard met elke winnende vlag. Alleen wat op de
  ontwikkelsets en op de blinde set niet slechter is, gaat standaard aan, in één PR met de meting in het meetlogboek.
- Daarna een nieuwe bronnenrun op het werkgebied Termijnen, met akkoord, als controle in de werkplek.

### Volgorde en afhankelijkheden

Stap 0 gaat voor alles. Daarna 1a en 1b, dan stap 1. Stap 2, 3 en 5 raken elk een eigen functie en kunnen in deze
volgorde na elkaar. Stap 4 komt na stap 2, omdat beide de telling in `opties_bij_deelvraag` raken. Stap 6 staat apart (bronmodel en herimport) en kan
naast 1–5 lopen. Stap 7 komt na 1, en stap 8 als laatste.

### De Mijnbouwwet in de graaf (besluit gebruiker, 16 nov 2026)

De Mijnbouwwet (BWBR0014168) komt in de graaf, na een grondige analyse van de import. Dat gebeurt in een eigen PR,
apart van dit plan. Een lokale import met de echte importer, naast de zeven regelingen van de graaf, vond meteen een fout.
De wet is geldig volgens het XSD, maar de importer weigert haar: *Sub-paragraaf 4.1a.1.1* krijgt dezelfde IRI als
*Paragraaf 4.1a*. Het jci-segment `sub-paragraaf=` valt weg in `_JCI_STRUCTUUR` (`bronmodel/bwb/references.py`).
Het herstel leest een sub-paragraaf als geneste paragraaf, zoals de parser al deed. Dat gebeurt in de importer, in
`bronmodel.vindplaats` en in de frontend, met jci-vectoren. Geen andere regeling van de graaf heeft sub-paragrafen. Het
zoekbereik van het werkgebied Termijnen kiest de gebruiker zelf; de set hierboven houdt het zoekbereik zoals het nu is.

## Open keuzes voor de gebruiker

- Mag de opname van stap 0 gemaakt worden? Die draait live tegen de graaf van acceptatie.
- Wie stelt de blinde set van stap 8 op, en uit welk werkgebied?
- Mag de herimport van stap 6 op acceptatie draaien als de steekproef goed is?
