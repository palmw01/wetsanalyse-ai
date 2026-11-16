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

## Stap 3 – `overzicht_streng` (O5)

Gemeten op een hele bronnenrun zoals de api haar start: deelvragen, dossier met gebeurtenis en zoekbereik, zonder kern
(`stap3/run_meting.py`, `bronnen_vinden.vind(profiel=)`, tegen de aangevulde opname).

- Termijnen, standaard: 59 kandidaten, waarvan 44 zonder deelvraag; verwacht (kern/afhankelijkheid) 2 van 12 gevonden; 8
  uitgesloten bepalingen. Dat is wat acceptatie op 16 nov 2026 toonde.
- Termijnen, met de vlag: 19 kandidaten, waarvan 4 zonder deelvraag (de grondslagen); verwacht 2 van 12; 6 uitgesloten.
- Rekeningafspraken: gelijk (25 kandidaten, 1 zonder deelvraag, 1 van 5): het overzicht vond daar al niets.

**Oordeel: haalt de ruis weg zonder iets te kosten.** 40 kandidaten uit het overzicht op de naam *Termijnen* vallen weg
(Awb-artikelen over beslistermijnen, met de rol kern). Geen verwachte bepaling gaat verloren. Een kandidaat van het overzicht
heeft met de vlag de rol *aanverwant*. Dat raakt de werkgebieden zonder deelvragen, en die meet deze run niet: de set
`invorderbaarheid-concept` heeft een kern, dus het overzicht draait daar niet. De vlag is een kandidaat om in stap 8 aan te
zetten.

## Stap 4 – `stam_heel` (O3)

Recall nodig, eerst de standaard, dan met de vlag. Op de zoekvragenroute (de bronnenrun met een gebeurtenis):

- Termijnen: 0,06 → **0,19**; uitgesloten 12 → 9
- Rekeningafspraken: 0,29 → 0,29
- Bestuurdersaansprakelijkheid: 0,44 → 0,44
- Bezwaar/ontvankelijkheid: 0,40 → **0,27**
- Invorderbaarheid (deelvragen): 0,46 → 0,46
- Kwijtschelding: 0,33 → **0,29**

Op de woordenroute: Bestuurdersaansprakelijkheid 0,22 → 0,28, Bezwaar 0,53 → 0,47, de rest gelijk.

**Oordeel: de eerste winst bij Termijnen, maar ten koste van twee sets.** Waar het verlies vandaan komt:

- **Kwijtschelding.** "belastingschuld" raakte drie verwachte artikelen van de Uitv.reg. Iw (art. 10, 11, 18) alleen op
  zijn eerste acht letters, "belastin". Met de vlag staat het woord er niet meer in. Dat is juist geteld, maar die artikelen
  verliezen er een treffer door.
- **Bezwaar.** Hier verliest geen verwachte bepaling een treffer; AWR 22j wint er zelfs een ("belastingaanslag" via de kern
  "aanslag"). Het verlies komt uit de gewichten. Een term die via zijn kern veel meer kandidaten raakt, krijgt een lager
  idf-gewicht, en de volgorde verschuift.

De vlag blijft uit. Voor stap 8: in de pool telt de kern als treffer, maar niet voor de documentfrequentie. Dat volgt uit dit
mechanisme, en is nog niet gemeten.

De rapporten staan in [`stap4/`](stap4/).

## Stap 5 – `brug_omschrijving` (O4)

Op de zoekvragenroute, recall nodig, eerst de standaard, dan met de vlag: op alle zes sets gelijk (Termijnen 0,06,
Rekeningafspraken 0,29, Bestuurdersaansprakelijkheid 0,44, Bezwaar 0,40, Invorderbaarheid 0,46, Kwijtschelding 0,33). Bij
Termijnen daalt de gewone recall van 0,11 naar 0,06: de brugwoorden uit de analysevraag ("termijnbedragen", "termijnen")
brachten één aanverwante bepaling binnen.

**De melding** (wat de eval niet meet). Staat een kloofwoord niet in het zoekbereik maar wel elders in de graaf, dan noemt
Lex die regeling (`zoekvragen.regelingen_met_woord`). Op de graaf van acceptatie staat "winstaandeel" op 11 plekken, alle
in de Mijnbouwwet. Bij Termijnen zou Lex dus zeggen: "‘winstaandeel’ staat niet in de regelingen van dit werkgebied, wel in
Mijnbouwwet. Hoort die regeling erbij, neem haar dan op in het zoekbereik." Nu zegt hij dat het vermoedelijk een begrip uit
de uitvoering is, en zoekt hij met de woorden van de analysevraag.

**Oordeel: geen winst in de cijfers, wel een juistere melding.** Een kandidaat voor stap 8, vanwege de melding.

De rapporten staan in [`stap5/`](stap5/).

## Stap 6 – route 4 van de definities en `definitie_brug` (O4)

**De parser** (`bronmodel/bwb/parser.py`, route 4, achter de instelling `BWB_DEFINITIE_AANDUIDING` van de importer,
standaard uit): "… wordt aangeduid als X" en "(hierna: X)". De telling over de acht regelingen van de graaf, met de lokale
bron-XML's (`stap6/definities_tel.py`):

- AWR: 25 → 26 definities: *voorlopige teruggaaf* (art. 13 lid 2). Juist.
- De andere zeven regelingen: gelijk (0 erbij). Geen vals positief.
- De Leidraad heeft 14 van zulke zinnen ("aangeduid als bodemzaken", "(hierna: illiquide vermogen)", "(hierna: de
  douane-ontvanger)"). Een divisie van een beleidsregel draagt in het model geen begrippen, dus de parser leest ze niet. Ze
  toevoegen raakt het model, de verzameling en de schrijver van de importer: een **vervolg**, buiten deze stap.

**Het zoeken** (`definitie_brug`): een definitie waarvan de tekst minstens twee termen van de deelvraag raakt, brengt de
woorden van haar begrip mee als zoekterm. Op de graaf van nu (nog zonder route 4) is de recall nodig op alle zes sets
gelijk. Bij Termijnen daalt het aantal uitgesloten bepalingen op de woordenroute van 3 naar 1, door definities die er al
zijn.

**Nog te meten.** Het eigenlijke effect, *voorlopige teruggaaf* als brug bij "negatieve voorlopige aanslag", komt pas na
een herimport met `BWB_DEFINITIE_AANDUIDING=true`. Dat is een wijziging van de graaf van acceptatie, en vraagt akkoord
(stap 8).

## Stap 7 – de vlaggen van PR E opnieuw (`verwijzingen`, `onderscheidend`)

Recall nodig, eerst de standaard, dan met de vlag. Op de **woordenroute**:

- `verwijzingen`: Termijnen 0,00 → 0,19; Rekeningafspraken 0,14 → 0,43; Bestuurdersaansprakelijkheid 0,22 → 0,28; Bezwaar
  0,53 → 0,60; Invorderbaarheid en Kwijtschelding gelijk. Er komen 2 tot 12 opties bij, zodat de precisie bij Kwijtschelding
  daalt (0,06 → 0,04).
- `onderscheidend`: alleen Termijnen verandert (0,00 → 0,12), met een veel kleinere pool (1,00 → 0,22).

Op de **zoekvragenroute** (wat de bronnenrun met een gekozen gebeurtenis doet) hebben beide vlaggen geen effect, ook niet
samen met `woorden_voor_pool`. De verwezen bepalingen staan achteraan de opties van de woordenroute, en vallen buiten de
acht plaatsen (`samen_met_woorden`).

**Oordeel.** `verwijzingen` is de sterkste vlag op de woordenroute. Die route draait als een werkgebied geen gebeurtenis
heeft: in de intake en de bronnenrun zonder gebeurtenis. Met een gebeurtenis bereikt de vlag de kandidaten niet. Een
kandidaat voor stap 8 alleen voor de route zonder gebeurtenis. `onderscheidend` blijft uit.

## Stap 8 – voorstel (nog niet uitgevoerd)

**De combinatie die op geen ontwikkelset slechter is**: `termen_idf`, `verwijzingen`, `brug_omschrijving` en
`overzicht_streng` (`stap8/combinatie.py`, aangevulde opnames). Recall nodig, eerst de standaard, dan met de combinatie:

- Woordenroute (zonder gebeurtenis): Termijnen 0,00 → 0,13; Rekeningafspraken 0,14 → 0,43; Bestuurdersaansprakelijkheid
  0,22 → 0,28; Bezwaar 0,53 → 0,60; Invorderbaarheid 0,36 → 0,36; Kwijtschelding 0,10 → 0,14. De precisie is gelijk of
  beter.
- Zoekvragenroute (met gebeurtenis): gelijk op alle zes; Termijnen precisie 0,08 → 0,04.
- Op een hele run (stap 3): bij Termijnen 40 kandidaten minder zonder deelvraag, geen verwachte bepaling kwijt.

**Wat dit betekent voor Termijnen.** Het werkgebied heeft een gebeurtenis, en daar verandert de combinatie de recall niet.
Wel verdwijnt de ruis van het overzicht, en Lex zegt dat het winstaandeel in de Mijnbouwwet staat. De enige stap die de
recall bij Termijnen op de zoekvragenroute verhoogde, `stam_heel` (0,06 → 0,19), kost op twee andere sets. Die gaat dus niet
aan.

**Niet aanzetten**: `beurt_sterk` (geen effect), `woorden_voor_pool`, `vraagvorm_eigen_woord` en `stam_heel` (slechter op een
andere set). Voor de laatste twee staat in hun stap een variant die uit hetzelfde mechanisme volgt, maar nog niet gemeten is.

**Voordat er iets aan gaat**:

1. **De blinde set.** `verrekening-concept` is de held-out set van 4 nov 2026, opgesteld vóór deze code en nooit gedraaid. De
   meting vraagt een opname: alleen lezen in de graaf, geen model. Daarnaast eventueel een tweede blinde set uit een ander
   werkgebied, opgesteld door de agent-jurist op acceptatie. Dat vraagt een model.
2. **Route 4 van de definities**: `BWB_DEFINITIE_AANDUIDING=true` op acceptatie, een herimport (`vul-graaf`), en dan
   `definitie_brug` meten. Dat wijzigt de graaf van acceptatie.
3. **Aanzetten** in één PR met de meting in dit logboek, en daarna, met akkoord, een nieuwe bronnenrun op Termijnen als
   controle in de werkplek.

**Bevindingen voor een volgend plan** (niet gebouwd):

- de fusie telt het aantal geraakte deelvraagtermen niet apart, dus bij gelijke dekking wint een lange bepaling (stap 1b);
- "negatieve" raakt "negatief" niet (wildcard en stemmer, stap 1b);
- de begrippen in de divisies van een beleidsregel leest de parser niet (stap 6);
- een gebeurtenis die bijna een hele wet omvat, laat de pool alles nemen (O1). Een melding bij het kaartje van de gebeurtenis
  staat in het plan (stap 1), maar is niet gebouwd.
