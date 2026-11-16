# Bronselectie – de stappen van het plan Termijnen (16 nov 2026)

Soort: *meting* · Hoort bij: [onderzoek-bronselectie-termijnen-2026-11.md](../../onderzoek-bronselectie-termijnen-2026-11.md),
nulmeting [`bronselectie-2026-11-16-nulmeting/`](../bronselectie-2026-11-16-nulmeting/README.md)

Per stap van het plan is er een vlag in `Zoekprofiel`, en die staat standaard uit. Elke vlag is offline gemeten met
`eval/bronselectie_eval.py --intake --plan`, op de zes ontwikkelsets, tegen de opnames van acceptatie en zonder model. Nieuwe
vragen aan de graaf zijn met `--aanvullen` live opgehaald en aan de opnames toegevoegd. De cijfers zijn een trendmeting op
ontwikkelsets. Een winst geldt pas na de blinde set van stap 8. De held-out set Verrekening is niet gedraaid.

## Stap 1a – `termen_idf` (O6)

Recall nodig per set, eerst de standaard, dan met de vlag (precisie tussen haakjes):

- Termijnen: 0,00 (0,04) → 0,00 (0,00); recall 0,06 → 0,00; pool 1,00 → 0,94
- Rekeningafspraken: 0,14 (0,03) → 0,14 (0,03)
- Bestuurdersaansprakelijkheid: 0,22 (0,09) → 0,28 (0,12); pool 0,91 → 0,86
- Bezwaar/ontvankelijkheid: 0,53 (0,25) → 0,53 (0,25)
- Invorderbaarheid (deelvragen): 0,36 (0,28) → 0,36 (0,28)
- Kwijtschelding: 0,10 (0,06) → 0,14 (0,12); pool 0,33 → 0,46

**Oordeel: gemengd, en zo verwacht.** De vlag helpt waar het onderscheidende woord buiten de eerste zes termen viel
(Kwijtschelding, Bestuurdersaansprakelijkheid), en verandert niets bij drie sets. Bij Termijnen komt de kern niet in de top
8. Het grootste verlies zit daar in de rangschikking om de beurt over zes regelingen (O7, stap 1b), niet in de termen. De
vlag blijft uit, en de beslissing valt in stap 8, in combinatie met de andere stappen.

De rapporten staan in [`stap1a/`](stap1a/).

## Stap 1b – `beurt_sterk` (O7)

Recall nodig per set, eerst de standaard, dan met de vlag (de grens `AANDEEL_STERK` = 0,5, vooraf vastgelegd):

- Termijnen: 0,00 → 0,00 (gedeeld 0,50 → 0,67)
- Rekeningafspraken: 0,14 → 0,14
- Bestuurdersaansprakelijkheid: 0,22 → 0,22
- Bezwaar/ontvankelijkheid: 0,53 → 0,53
- Invorderbaarheid (deelvragen): 0,36 → 0,36
- Kwijtschelding: 0,10 → 0,10

De vlag samen met `termen_idf` ("met het plan (alles)"): Rekeningafspraken 0,14 → 0,29; de andere sets zoals met
`termen_idf` alleen.

**Oordeel: de grens werkt, de recall verandert niet.** Bij Termijnen DV1 valt de Awb af: haar beste kandidaat haalt 0,033,
tegen de helft van 0,079. Maar de verwachte bepalingen komen er niet bij, want het verlies zit *binnen* een regeling. AWR 13 lid 2 raakt in de
index twee termen van de deelvraag (voorlopige, aanslag), net als AWR 30fa lid 1 en AWR 2 lid 3, en staat daaronder:
bij gelijke dekking beslist de fusie, en een lange bepaling met gewone woorden staat in meer lijsten hoog. Twee **nieuwe
bevindingen** voor stap 8: (1) het aantal geraakte deelvraagtermen telt in de fusie niet apart mee; (2) "negatieve" raakt
"negatief" niet, want de wildcard `*negatiev*` en de stemmer van de index vinden het geen van beide. Zo mist AWR 13 lid 2
("een voorlopige aanslag tot een negatief bedrag") het woord dat haar van de rest onderscheidt. De grens van 0,5 is niet bijgesteld om een uitkomst te halen.

De rapporten staan in [`stap1b/`](stap1b/).

## Stap 1 – `woorden_voor_pool` (O1)

Gemeten op de zoekvragenroute (wat de bronnenrun met een gekozen gebeurtenis doet), recall nodig, eerst de standaard, dan
met de vlag:

- Termijnen: 0,06 → 0,06
- Rekeningafspraken: 0,29 → 0,29
- Bestuurdersaansprakelijkheid: 0,44 → 0,44
- Bezwaar/ontvankelijkheid: 0,40 → 0,40
- Invorderbaarheid (deelvragen): 0,46 → 0,46
- Kwijtschelding: 0,33 → **0,19**

De zoekvragenroute van de eval roept nu dezelfde functie aan als de bronnenrun (`zoekvragen.samen_met_woorden`), en
geeft zonder vlag exact de cijfers van de nulmeting.

**Oordeel: helpt niet, en kost bij Kwijtschelding.** De aanname achter O1 klopt maar half. De pool neemt bij Termijnen alle
plaatsen, maar haar opties raken wel eigen woorden van de deelvraag (voorlopige, aanslag, verrekend). Ze tellen dus niet
als "zwak" en wijken niet. Waar ze wel wijken (Kwijtschelding), rangschikt de woordenroute slechter dan de pool. Zolang de
woordenroute haar eigen pool niet goed rangschikt (stap 1b, bevindingen), maakt meer plaatsen geven het niet beter. De
vlag blijft uit; stap 8 neemt haar niet mee tenzij een latere stap de woordenroute verbetert.

De rapporten staan in [`stap1/`](stap1/).

## Stap 2 – `vraagvorm_eigen_woord` (O2)

Op de zoekvragenroute, recall nodig, eerst de standaard, dan met de vlag:

- Termijnen: 0,06 → 0,06; uitgesloten bepalingen in de top 12 → 9
- Rekeningafspraken: 0,29 → 0,29
- Bestuurdersaansprakelijkheid: 0,44 → 0,44
- Bezwaar/ontvankelijkheid: 0,40 → 0,40
- Invorderbaarheid (deelvragen): 0,46 → 0,46
- Kwijtschelding: 0,33 → **0,19**

Op de woordenroute verandert de vlag niets: de bonus van de vraagvorm bestaat alleen in de pool.

**Oordeel: minder ruis bij Termijnen, verlies bij Kwijtschelding.** Geen van de vier deelvragen van Kwijtschelding heeft de
vorm "Wat is …", dus het verlies komt van de eis van een eigen woord. Dit is de set van de woordenkloof ("laten
vervallen" tegenover *kwijtschelding*). Daar vond de bonus van de vraagvorm de juiste divisies van de Leidraad (art. 26),
zonder één woord van de deelvraag. De bonus is daar de brug over de kloof, en bij Termijnen haalt hij ruis binnen. Een vlag
die het ene herstelt en het andere breekt, gaat niet aan. Voor stap 8: zonder eigen woord alleen een bonus als de
deelvraag een woord heeft dat in de regelingen ontbreekt (de kloof, `ontbrekende_woorden`). Dat volgt uit dit mechanisme,
maar het is nog niet gemeten.

De rapporten staan in [`stap2/`](stap2/).
