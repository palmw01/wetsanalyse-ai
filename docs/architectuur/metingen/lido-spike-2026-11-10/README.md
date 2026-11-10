# LiDO-spike: uitspraken per artikel, verenigd over versies (10 nov 2026)

Soort: *meting*. De meting is gedaan op de publieke diensten van LiDO (`linkeddata.overheid.nl/service/`) en Rechtspraak
(`data.rechtspraak.nl`), alleen lezend. Er is geen productcode en er zijn geen modelcalls. De vraag komt uit het advies
"linked-data-diensten van de overheid" (9 nov 2026, hoofdsessie).

## De aanname die getoetst is

LiDO levert voor de artikelen van onze regelingen een bruikbare en betaalbare set uitspraken, als je de versies van een
artikel samenvoegt.

Dat moet getoetst worden, want LiDO hangt een link aan een *versie* van een artikel, niet aan het artikel zelf. Een
uitspraak landt op de versie die gold op haar eigen datum.

## Opzet

- **`lido_spike.py`:**
  - per artikel uit de toestand-XML de LiDO-versies, van nieuw naar oud: de vorige versie is die op de dag vóór de
    begindatum;
  - per versie `get-links` (XML, 50 per pagina);
  - samengevoegd op het artikel;
  - sequentieel, met 0,15 s pauze per aanroep, een cache per URL en een tweede poging bij een ongeldig antwoord;
  - als terugval het RDF-formaat (zie *Bevindingen 3*).
- **Twee manieren om versies te vinden:**
  - `get-id?juriconnect-ref=<BWB>&artikel=<nr>&g=…&z=…` (*ref*);
  - `get-id?juriconnect=<jci 1.3 uit de toestand>` met de datum van een bestaande BWB-toestand (*jci*).
- **`precisie.py`:** 30 willekeurige paren (artikel, ECLI) uit de Iw (seed 20261110). Per paar de tekst bij Rechtspraak
  en de fragmenten waarin het artikel genoemd wordt. Het oordeel komt uit mijn eigen lezing van de fragmenten
  (`precisie-iw.json`). **Dat is geen juridisch oordeel.**
- **Regelingen:**
  - Iw 1990 (BWBR0004770): alle 128 niet-vervallen artikelen;
  - Awb (BWBR0005537): 30 willekeurige artikelen (seed 7);
  - Leidraad Invordering 2008 (BWBR0024096): met de hand gepeild.

## Uitkomst

| | Iw, *ref* | Iw, *jci* | Awb, 30 artikelen, *jci* |
|---|---|---|---|
| artikelen zonder LiDO-id | 2 (7d, 57a) | 2 (7d, 57a) | 1 (art. 2) |
| versies gevonden | **394** | 240 | 53 |
| paren (artikel, uitspraak), alle versies | **5.332** | 4.388 | 26.169 |
| paren, alleen huidige versie | 2.813 (53 %) | 2.813 | 21.939 (84 %) |
| verschillende ECLI's | 3.068 | 2.701 | 24.180 |
| artikelen met ≥ 1 uitspraak | 103 van 128 | 102 | 28 van 30 |
| aanroepen bij een koude cache | ≈ 930 | ≈ 790 | ≈ 650 |
| duur van een live run | ≈ 4–7 min | ≈ 7 min | ≈ 5 min |

- **Linktypen bij de Iw** (alle versies): 4.866 "door computer herkende referentie" (jurisprudentie), 520 redactionele
  referenties van jurisprudentie, en 737/546/143 inkomende redactionele referenties uit wetten, ministeriële regelingen
  en AMvB's. Die laatste komen uit **157 verschillende regelingen**: de Uitvoeringsregeling Iw, de Uitvoeringsregeling
  Belastingdienst, de Awir, de Mijnbouwwet, de Gemeentewet, enzovoort.
- **Kamerstukken:** 0 links tussen een Iw-artikel en een Kamerstuk.
- **Instanties:** conclusies A-G (PHR) 857, HR 432, en de hoven (GHSHE, GHARL, GHAMS) elk ongeveer 400.
- **Spreiding over de jaren:** 2002–2026, met ongeveer 100–280 per jaar.

**Precisie (Iw, 30 paren):**

- **De vermelding klopt in 30 van de 30**: elke uitspraak noemt het artikel echt. Bij 3 paren zag mijn patroon de
  vermelding niet ("artikelen 30, 49 of 62a", "artikel 68 van de Wet", "Inv"); daar heb ik zelf gelezen.
- **Grond of geschilpunt in 25 van de 30**, *terloops* in 4 (een citaat van een andere regel of een opsomming), en 1
  onzeker.
- De steekproef van 9 nov (8 paren, alleen art. 9) gaf 2 van de 8 inhoudelijk: art. 9 staat in de tekst van de
  belastingrente (AWR 30fc/30hb), die rechters citeren. **De precisie verschilt dus sterk per artikel.**

## Bevindingen

1. **Samenvoegen over versies is nodig.** Alleen de huidige versie geeft bij de Iw 53 % van de paren. Bij een artikel dat
   lang niet gewijzigd is, is het verschil groot: art. 9 heeft 196 uitspraken, waarvan 12 op de huidige versie; art. 49
   heeft er 348, waarvan 47 op de huidige.
2. **De versies vinden is het zwakke punt.** De twee ingangen geven verschillende antwoorden, en LiDO heeft geen relatie
   "vorige versie":
   - *ref* vindt bij de Iw 394 versies, maar faalt bij de Awb helemaal (geen enkele id, ook niet voor een artikel zonder
     dubbele punt);
   - *jci* werkt voor beide, maar vindt bij de Iw maar 240 versies, en daarmee 18 % minder paren.

   **Volledigheid is via de services dus niet aan te tonen.** Een lijst is "ten minste", nooit "alle".
3. **`get-links` breekt stil af.** Bij 16 van de 394 Iw-versies (4 %) komt er HTTP 200 terug met een JSON-foutmelding
   midden in de XML, steeds bij dezelfde gekoppelde items en ook met kleinere pagina's. Het RDF-formaat levert die
   versies wel. Zonder die terugval waren er stil 632 van de 5.332 paren (12 %) weggevallen, bij art. 25 en 49 zelfs het
   merendeel. Bij de Awb faalden 2 versies ook in RDF (heel grote artikelen).
4. **Actualiteit.** De toestand van 1 okt 2026 kent LiDO op 10 nov nog niet. Een jci met die datum geeft niets, en art. 7d
   (in werking 1 okt 2026) ontbreekt. Art. 57a ontbreekt om een onbekende reden. De laatste link-import is van
   2 jul 2026.
5. **Leidraad: niet bruikbaar.** LiDO kent alleen de hoofddivisies als "Artikel N", met versies tot 2009, en geen
   decimale divisies (9.4, 26.5). Die zijn juist de eenheden in onze graaf.
6. **Omvang van de Awb.** Art. 8:57 heeft 11.728 uitspraken en 7:2 heeft er 4.009. Dertig artikelen kosten ongeveer
   650 aanroepen. Voor alle 565 is de schatting ongeveer 12.000 aanroepen, 1,5–2 uur en een half miljoen paren. Voor een
   procedureel artikel zegt zo'n lijst weinig.
7. **De koppelsleutel klopt.** `heeftBWBLabelId` van LiDO is in alle gevonden gevallen gelijk aan de `label-id` in onze
   toestand (0 afwijkingen).
8. **Licentie Rechtspraak.** De dataset *uitspraken-rechtspraak-nl* staat op data.overheid.nl onder de Public Domain
   Mark 1.0 (geraadpleegd op 10 nov 2026). De pagina van de Rechtspraak zelf gaf een 403.

## Go/no-go

- **Go, in een andere vorm dan voorgesteld: live per bepaling, niet als bulkimport.** Eén artikel kost bij de Iw
  gemiddeld 7 aanroepen, ongeveer 2–5 s, en zo'n 15 aanroepen voor het zwaarste artikel (art. 36). Dat past bij "de tool
  haalt wat" (ADR-013): een tool `uitspraken_bij_bepaling` in de bronconnector Rechtspraak, met een cache per
  versie-id. De tool zegt:
  - "noemt dit artikel", met instantie en datum;
  - dat de lijst ten minste deze uitspraken bevat;
  - de stand van LiDO.

  De voordelen boven een import:
  - geen wekelijkse vulling van 1,5 uur of meer;
  - geen extra werk voor de graafwacht;
  - geen half miljoen Awb-paren in een niet-persistente graaf;
  - alleen bepalingen waar een jurist om vraagt.
- **No-go voor de bulkimport via de services** (stap 2 van het advies): volledigheid is niet aan te tonen (bevinding 2),
  en de Awb is te groot (bevinding 6).
- **Open:** of de dump (5,7 GB gz, maandelijks, CC0) de versies wél volledig geeft. Dat is alleen nodig als een
  graafimport toch gewenst blijkt. Het is een aparte spike: de dump streamend filteren op onze BWB-id's, en tijd en
  geheugen meten.
- **De Leidraad: niet.**
- **Stap 1 van het advies** (de BWB-brondata per artikel, met het Kamerdossier) hangt hier niet van af en kan door.

## Bestanden

- `lido_spike.py`, `precisie.py`, `samenvat.py`: de scripts zoals ze gedraaid hebben.
- `uitkomst.json`: de aggregaten per run en per artikel (versies, uitspraken, uitspraken op de huidige versie).
- `precisie-iw.json`: de 30 paren met het fragment, het oordeel en de toelichting.

De ruwe antwoorden van LiDO en Rechtspraak (een cache van ongeveer 900 bestanden) zijn niet bewaard. Ze zijn opnieuw op te
halen met de scripts.
