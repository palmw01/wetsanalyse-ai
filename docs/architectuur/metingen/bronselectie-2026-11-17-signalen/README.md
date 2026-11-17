# Bronselectie – signalen van een zoekmachine, een voor een (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Aanleiding: het voorstel voor een transparante bronselectie (vraag van de
gebruiker: "een transparant selectieproces … met een paar parameters om te tunen … en neem het proces van Google mee") ·
Akkoord gebruiker: "Ja, voer het uit" (stap 1 tot en met 4, zonder model)

Dit is een onderzoek, geen wijziging van Lex. Het meet een eenvoudig ontwerp naast de code: één ranglijst per deelvraag over
alle bepalingen in het zoekbereik, met een handvol benoemde signalen. Het meet welke signalen helpen en hoe gevoelig elke knop
is. Alles offline, zonder model (0 tokens), op de tien ontwikkelsets. De verwachtingen zijn `concept`, dus dit is een
trendmeting.

## Wat er gemeten is

**Stap 1 – opname** (`opname.py`). Voor de zeven regelingen van de sets: elke eenheid (lid, artikel zonder leden, divisie)
met haar tekst (met onderdelen), de koppen erboven (en de titel van een divisie), en de inkomende verwijzingen met hun
ankertekst en de tekst van de verwijzende bepaling. Alleen lezend, via de MCP-server op de graaf van acceptatie. Elke query
is tegen een `COUNT` getoetst: de MCP kapt grote antwoorden stil af (eerste poging: 466 van 710 verwijzingen naar de
Invorderingswet). De opname zelf staat niet in de repo; ze is uit de graaf opnieuw te maken.

| regeling | eenheden | inkomende verwijzingen |
|---|---|---|
| AWR | 557 | 332 |
| Uitvoeringsregeling Invorderingswet 1990 | 208 | 146 |
| Invorderingswet 1990 | 430 | 710 |
| Awb | 1347 | 710 |
| Awir | 250 | 140 |
| Uitvoeringsregeling Awir | 56 | 4 |
| Leidraad Invordering 2008 | 813 | 374 |

**Het model van de meting** (`signalen.py`). BM25F (k1 = 1,2, b = 0,75) over drie velden: tekst, kop en de *verwijzende zin*
(tot 120 tekens vóór het anker plus het anker, uit elke andere bepaling die naar de eenheid of haar artikel verwijst). Een
term raakt een woord zoals in de code (`_stamdeel`, het begin van de stam als deel van het woord). De termen zijn de
inhoudswoorden van de deelvraag (`termen_van_deelvraag`), met gewicht 1. De knoppen:

- `w_kop`, `w_anker`: het gewicht van de kop en van de verwijzende zin tegenover de tekst (1);
- `beta`: het belang van verwijzingen, `beta · log(1+n) / log(1+max)` bij een score boven 0, met n het aantal andere bepalingen
  dat naar het artikel verwijst (zelfde artikel telt niet);
- `w_wet`: het gewicht van een wetsterm uit de vertaling tegenover een eigen woord;
- `vertaling`: `geen`, `gebeurtenis` (de gebeurtenis van het werkgebied als wetsterm) of `orakel` (de woorden uit de diepste kop
  boven de verwachte kernbepalingen van de deelvraag: een bovengrens die de verwachting kent, geen route);
- `cap`: hoogstens zoveel plaatsen per regeling bovenaan.

**Maten.** Recall nodig in de top N (kern en afhankelijkheid, treffer zoals `in_selectie`), per set als telling, en nDCG@10
met winst 2 voor kern en 1 voor afhankelijkheid. Het gemiddelde over de sets staat erbij als indicatie, niet als oordeel.

## Uitkomst

**Stap 2 – signalen een voor een** (`draai.py`), gemiddeld over de tien sets:

| stap | recall nodig @10 | @30 | nDCG@10 |
|---|---|---|---|
| C0 alleen tekst | 0,17 | 0,28 | 0,13 |
| C1 + kop (2) | 0,21 | 0,34 | 0,15 |
| C2 + verwijzende zin (1) | 0,21 | 0,33 | 0,15 |
| C3 + belang verwijzingen (0,3) | 0,20 | 0,39 | 0,16 |
| C4 + spreiding (5 per regeling) | 0,19 | 0,39 | 0,16 |

**Stap 3 – vertalen**, op C4:

| vertaling | recall nodig @10 | @30 | nDCG@10 |
|---|---|---|---|
| geen | 0,19 | 0,39 | 0,16 |
| de gebeurtenis als wetsterm | 0,27 | 0,59 | 0,24 |
| orakel (bovengrens) | 0,41 | 0,68 | 0,39 |

**Stap 4 – gevoeligheid per knop** (`gevoeligheid.py`), rond de basis `w_kop` 2, `w_anker` 1, `beta` 0,3, `w_wet` 2, `cap` 5,
vertaling gebeurtenis. Per waarde het gemiddelde en hoeveel sets beter (+) of slechter (−) zijn dan de basis:

- `w_kop`: 0 → 0,27/0,57 (@10/@30), 3 → 0,30/0,58 (@10 +3/−0). Helpt bovenaan, 2–3 is stabiel.
- `w_anker`: 0 → 0,27/0,58, 2 → 0,29/0,60 (@30 +3/−1). Klein maar positief.
- `beta`: 0 → 0,27/0,52 (@30 −5 sets), 0,2–0,5 → 0,28–0,29/0,59, 1,0 → 0,30/0,47 (@30 −8 sets). De sterkste knop na de
  vertaling, en gevoelig: te zwaar verdringt het de inhoud.
- `w_wet`: 1 → 0,26/0,52 (@30 −7 sets), 2 → 0,27/0,59, 3–5 lager op @30. 2 is het optimum.
- `cap`: geen duidelijk effect (0: 0,31/0,56; 5: 0,27/0,59; 10: 0,31/0,56). Een knop die de recall niet verklaart.
- Kandidaten naar het model: recall nodig @20 0,45, @30 0,59, @40 0,65, @60 0,74.

**De keuze uit stap 4** (`w_kop` 3, `w_anker` 2, `beta` 0,3, `w_wet` 2, geen `cap`, vertaling gebeurtenis;
`resultaten-keuze.json`):

| set | @10 | @40 | nDCG@10 |
|---|---|---|---|
| bestuurdersaansprakelijkheid | 10/18 | 15/18 | 0,42 |
| bezwaar-ontvankelijkheid | 1/15 | 7/15 | 0,10 |
| invorderbaarheid-deelvragen | 5/11 | 8/11 | 0,42 |
| kwijtschelding | 5/21 | 7/21 | 0,21 |
| rekeningafspraken | 3/7 | 4/7 | 0,27 |
| termijnen | 6/16 | 10/16 | 0,23 |
| verrekening | 9/18 | 18/18 | 0,44 |
| LB-07 | 4/20 | 15/20 | 0,24 |
| LB-08 | 5/30 | 13/30 | 0,24 |
| LB-09 | 3/16 | 8/16 | 0,14 |
| gemiddeld | 0,32 | 0,62 | 0,27 |

Ter vergelijking (andere route, top 8, `bronselectie-2026-11-17-model`): de rangschikking in code haalde gemiddeld 0,25, de
keuze door het model 0,42.

## Wat dit zegt

1. **Vertalen naar de wetsterm is de grootste knop.** Alleen de gebeurtenis als wetsterm meenemen tilt de recall in de top 30
   van 0,39 naar 0,59. Een vertaling per deelvraag (de bovengrens) haalt 0,68, en bovenaan 0,41 in plaats van 0,27. Dat
   bevestigt de methode: eerst de term van de wet, dan de woorden van de analist.
2. **Het belang van verwijzingen werkt, licht gedoseerd.** Op 0,2–0,5 is het de sterkste knop na de vertaling; op 1 kost het
   op acht sets. Nodige artikelen liggen in hun regeling meestal in het bovenste kwart van de verwijzingen, maar een op de vijf
   heeft er geen.
3. **De kop helpt bovenaan, de verwijzende zin een beetje.** Strikt genomen (het venster rond het anker) brengt de verwijzende
   zin weinig nieuwe woorden: bij 3 van de 172 nodige bepalingen staat een woord van de deelvraag alleen daar. Met de hele
   tekst van de verwijzende bepaling zijn het er meer, maar die tekst gaat ook over andere dingen.
4. **Spreiding over regelingen verklaart de recall niet.** Ze kan als weergaveregel blijven, niet als knop.
5. **Een eenvoudig ontwerp haalt zonder model al meer dan de huidige rangschikking in code**, en levert in de top 40 een
   kandidatenlijst die gemiddeld 0,62 van wat nodig is bevat. Wat het model daaruit haalt, is de volgende meting (stap 5).
6. **Bezwaar blijft laag** (de gebeurtenis "bezwaar" staat overal in Awb en AWR), en **LB-08 en LB-09** blijven laag zonder
   vertaling per deelvraag: daar beschrijft de deelvraag het onderwerp in eigen woorden.

## Grenzen

- Eén set knoppen, gekozen op dezelfde tien sets waarop gemeten is. Verschillen van 0,01–0,03 zijn één of twee bepalingen.
  Alleen de grote lijnen (1, 2 en 5) zijn stevig. Een blinde set moet de keuze bevestigen.
- Het orakel kent de verwachting. Het is een bovengrens voor wat een goede vertaling kan opleveren, geen route.
- De meting gebruikt alleen de gebeurtenis als vertaling. De vertaling per deelvraag door een model is niet gemeten.
- Geen keten a–d (grondslag, verwijzingen vanuit de kern) en geen afbakening: dit meet alleen de ranglijst per deelvraag.
- Concept-verwachtingen, door Claude opgesteld; geen jurist heeft ze vastgesteld.

## Opnieuw draaien

Vanuit deze map, met de MCP-server `graphdb` machine-lokaal geregistreerd:

```bash
python3 opname.py BWBR0002320 BWBR0004766 BWBR0004770 BWBR0005537 BWBR0018472 BWBR0019237 BWBR0024096
python3 draai.py
python3 gevoeligheid.py
```

De opname komt in `opname/` (niet in de repo).
