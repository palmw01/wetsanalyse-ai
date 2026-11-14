# #1464 – de centrale agent volgt een sjabloonweigering zoals *duiding* (14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen de opdrachten die de stap raakt.

- **Code:** graph-qa op `d2c1f585` (bundel 109, met #1464), `CENTRALE_AGENT=meten`.
- **Nulpunt:** de meting van #1457 op `913500ca`, centraal
  ([`../weigering-genoemd-2026-11-14/weigering.md`](../weigering-genoemd-2026-11-14/weigering.md)). Voor de spreiding
  kijk ik ook naar G1b (twee runs) en A2-3c (drie runs).
- **Wat #1464 verandert:**
  - de profielen `centraal` en `centraal_breed` krijgen de afrondregel van `duiding`: geen antwoord in tekst, en na een
    weigering de aanroep verbeteren en opnieuw aanroepen;
  - de weigering `genoemd_in_tekst` geeft per plek letterlijk het begin en einde van de zin uit de bron (`van`, `tot`).
    Dat geldt in beide vormen.

  De `system_hash` van `centraal` veranderde van `99b714fb4813` in `81f5b2912c16`. De `tools_hash` bleef `214c1905e10f`.

## Verstoring

- **De Kennisgroepen-connector staat sinds bundel 107 aan, met fixes in 108 en 109.** Hij hoort niet bij de vragen van
  deze meting. In geen enkele beurt is hij aangeroepen.
- **De connector-sessie mat tegelijk vier connectorvragen, met hetzelfde account.** Het accountverbruik is daardoor geen
  zuivere maat. Tijdens de partijenset liep het account 117.146 tokens meer op dan de beurten zelf meldden. De kosten
  hieronder komen daarom uit het `meting`-event van elke beurt, niet uit de delta van het account. Bij F04 en F05 vallen
  ze samen.

## Kort

- **Na een weigering vult centraal het sjabloon vaker: gehaald.**
  - Partijenset: 5 van de 5 beurten met een weigering vullen het sjabloon. In #1463 was dat 5 van de 6, met 4:5 lid 1
    gemist.
  - F04: nu gevuld, waar in #1463 het sjabloon zonder poging gemist werd. Het antwoord heeft wel 233 tekens tekst naast
    het sjabloon.
  - F05: gevuld na één weigering. In #1463 viel F05 na twee keer `genoemd_in_tekst` terug op tekst. In A2-3c vulde
    alleen 1 van de 3 runs het sjabloon.
  - Het geval van #1463 (`genoemd_in_tekst`) kwam nu één keer voor, bij 3:47 lid 1. Daarna is het sjabloon gevuld.
- **`passage_niet_te_tonen` kost minder: gehaald.**
  - Ze kwam één keer voor (F05), tegen vier keer in drie beurten in #1463 (3:46, 3:45 lid 1, 2× 4:5 lid 1).
  - Die drie vragen zijn nu 31 %, 58 % en 30 % goedkoper.
  - F05 vult na deze weigering het sjabloon, in 6 rondes, net als in #1463.
- **Brongetrouw gelijk: gehaald, en F05 beter.**
  - Alle 47 blokcitaten staan in de officiële tekst. Eén treffer van de controle is vals alarm: lopende tekst tussen twee
    aanhalingen bij 4:35 lid 1.
  - Alle veertien beurten zijn *gegrond*, de opzet van F04 en F05 meegeteld. In #1463 waren 4:5 lid 1 en F05 *onbepaald*. F05 was dat in alle drie de runs
    van A2-3c.
  - De partijenset slaagt 10 van de 10 keer. In #1463 was dat 9 van de 10.
- **Niet duurder (gewogen warm): gehaald.**
  - Partijenset per run: 228,5k → 196,5k (−14 %). Dat is ook onder G1b (201,7k).
  - F04 en F05 samen: 108,6k → 103,0k (−5 %).
  - Eén vraag gaat over de 25 %: 3:47 lid 1, van 14,0k naar 18,0k (+29 %). Dat ligt binnen de spreiding van G1b
    (13,8k–23,7k).
- **Verbruik:** 1,25M ruw volgens de beurten zelf, 1,37M op het account (zie §*Verbruik*).

## Wat er gemeten is

| | Commando | Vorm | Runs |
|---|---|---|---|
| Partijenset (10 Awb-bepalingen) | `centrale_agent_meting.mjs vragen partijen 1 … --vormen '{"centraal":{"agentvorm":"centraal"}}'` | centraal | 1 |
| F04 en F05 (vervolgvragen met hun opzet) | `centrale_agent_meting.mjs run 1 … --vorm centraal --extra '{"agentvorm":"centraal"}' F04 F05` | centraal | 1 |

- Gescoord is met `eval.centrale_agent_sets` (partijenset) en `eval/centrale_agent_vat.py` (F04, F05).
- De blokcitaten zijn vergeleken met de volledige officiële tekst van de Awb, de Iw 1990 en de Leidraad Invordering 2008.
- F04 en F05 vragen geen werkgebied; het meetwerkgebied was niet nodig.

Gegevens:

- [`partijen-sets.jsonl`](partijen-sets.jsonl): 10 regels.
- [`vervolg-runs.jsonl`](vervolg-runs.jsonl): 2 regels.

## De drempels

### Na een weigering vaker het sjabloon – gehaald

**Partijenset, centraal**, per beurt:

| | #1463 (10) | #1464 (10) |
|---|---|---|
| Beurten met een weigering | 6 | 5 |
| … met `genoemd_onbekend` | 3 | 4 |
| … met `genoemd_in_tekst` | 1 | 1 |
| … met `passage_niet_te_tonen` | 3 | 0 |
| Sjabloon gemist | 1 (4:5 lid 1) | 0 |

**Per vraag met een weigering in #1464:**

| Vraag | Weigering | Daarna |
|---|---|---|
| 3:47 lid 1 | `genoemd_in_tekst` | gevuld |
| 3:41 lid 1 | `genoemd_onbekend` | gevuld |
| 4:5 lid 1 | `genoemd_onbekend` | gevuld (twee keer aangeroepen) |
| 4:48 lid 1 | `genoemd_onbekend` | gevuld |
| 7:10 lid 1 | `genoemd_onbekend` | gevuld |

Bij 3:45 lid 1 kwam de sjabloonaanroep als tekst en zette de code haar om (`als_tekst`). Het sjabloon is gevuld.

**F04 en F05, centraal:**

| | A2-3c (3 runs) | #1463 | #1464 |
|---|---|---|---|
| F04 | 2/3 gevuld; run 1 zonder poging | gemist, zonder poging | **gevuld**, 233 tekens tekst ernaast |
| F05 | 1/3 gevuld | gemist na 2× `genoemd_in_tekst` | **gevuld** na 1× `passage_niet_te_tonen` |

**Wat dit zegt:**

- De afrondregel doet wat hij moet: centraal vult na elke weigering in deze meting het sjabloon, en F04 probeert het nu
  wel.
- Of de nieuwe tekst van `genoemd_in_tekst` daarbij helpt, toont deze meting maar één keer (3:47 lid 1). Bij F05 kwam die
  weigering niet meer voor: het gevulde sjabloon citeert de Leidraadpassage die artikel 29 Wet OB 1968 noemt.

### `passage_niet_te_tonen` kost minder – gehaald

| Vraag | #1463 | #1464 |
|---|---|---|
| 3:46 | 23,2k, 5 rondes, 1× | 16,0k, 4 rondes, geen |
| 3:45 lid 1 | 28,6k, 5 rondes, 1× | 12,1k, 3 rondes, geen |
| 4:5 lid 1 | 57,0k, 8 rondes, 2× (gemist) | 39,9k, 6 rondes, geen |
| F05 | – | 40,7k, 6 rondes, 1× (gevuld) |

#1464 past de melding `passage_niet_te_tonen` zelf niet aan. Dat ze minder vaak voorkomt, komt dus door het eerste
sjabloon, of door spreiding: met één run is dat niet te scheiden.

### Brongetrouw gelijk – gehaald

| | Citaten | Niet in de bron | Oordeel |
|---|---|---|---|
| Partijenset | 31 | 0 (één vals alarm) | 10 × *gegrond* |
| F04 (opzet en vraag) | 9 | 0 | 2 × *gegrond* |
| F05 (opzet en vraag) | 7 | 0 | 2 × *gegrond* |
| *#1463, partijenset en F04/F05* | *41* | *0* | *12 × gegrond, 2 × onbepaald* |

- **Het valse alarm** staat bij 4:35 lid 1: de controle las de lopende tekst tussen "gegronde reden" en "in ieder geval"
  als één citaat. Beide stukken staan letterlijk in de Awb.
- Faithfulness is 1,0 in elke beurt. `unsupported` en `niet_letterlijk` zijn 0.

### Niet duurder (gewogen warm) – gehaald

| Vraag | #1463 | #1464 | Verschil |
|---|---|---|---|
| 3:46 | 23,2k | 16,0k | −31 % |
| 3:45 lid 1 | 28,6k | 12,1k | −58 % |
| 3:47 lid 1 | 14,0k | 18,0k | +29 % |
| 3:41 lid 1 | 15,9k | 19,6k | +24 % |
| 7:12 lid 1 | 12,7k | 11,6k | −8 % |
| 4:5 lid 1 | 57,0k | 39,9k | −30 % |
| 4:35 lid 1 | 16,9k | 16,8k | −1 % |
| 4:48 lid 1 | 27,5k | 28,6k | +4 % |
| 7:10 lid 1 | 21,4k | 22,2k | +4 % |
| 7:11 lid 2 | 11,4k | 11,7k | +3 % |
| **Partijenset** | **228,5k** | **196,5k** | **−14 %** |
| F04 (zonder opzet) | 69,3k | 62,3k | −10 % |
| F05 (zonder opzet) | 39,3k | 40,7k | +4 % |
| **F04 en F05** | **108,6k** | **103,0k** | **−5 %** |

- **De 25 %-regel**, tegen #1463. Er is geen afwijzing (K06) in deze set, dus er is geen cijfer voor de afwijzing.
  - Alleen 3:47 lid 1 gaat erover (+29 %), met een weigering `genoemd_in_tekst` en één ronde meer.
  - De G1b-runs lagen bij centraal op 13,8k–23,7k, dus 18,0k ligt binnen de spreiding.
- **F04 en F05** liggen binnen de spreiding van A2-3c (80,4k–105,8k per run). F04 duurde 10 rondes in plaats van 7,
  maar is goedkoper.
- **Koud:** de systeemprompt van `centraal` is nieuw, dus de eerste beurt (3:46) begon koud. Die beurt schreef 14.365
  tokens in de uurcache en kostte 43,3k gewogen, tegen 16,0k warm. Daarna was elke beurt warm.

## Keuzes die ik maakte

De gebruiker sliep en vroeg bij een keuze de aanbevolen optie te nemen. Hieronder staat wat ik zelf besliste.

- **De kosten tel ik uit het `meting`-event van elke beurt, niet uit de delta van het account.** De connector-sessie mat
  tegelijk op hetzelfde account; tijdens de partijenset gaf de delta 117k meer dan de beurten.
- **"Vaker het sjabloon" beoordeel ik als *gehaald*.** Het is één run, maar elk geval van #1463 is nu goed: F04 met
  poging, F05 gevuld, 4:5 lid 1 gevuld. Drie runs zijn alleen nodig bij twijfel, en die is er niet.
- **Ik schrijf de daling van `passage_niet_te_tonen` niet hard aan #1464 toe.** De stap raakt die melding niet; met één
  run blijft het een waarneming.
- **De 233 tekens naast het sjabloon bij F04 tel ik niet als gemist.** Het sjabloon is gevuld, en de meting telt de
  tekst ernaast apart (`tekst_ernaast`).

## Open

1. **De nieuwe tekst van `genoemd_in_tekst` is één keer gezien** (3:47 lid 1, gevuld). Of hij bij centraal standhoudt,
   kan alleen een vraag laten zien die die weigering vaker oproept.
2. **De supervisor is niet gemeten.** Hij krijgt de nieuwe weigeringstekst ook. #1464 stelde een run van de partijenset
   voor (ongeveer 0,75M); dat valt buiten deze opdracht.
3. **F04 zet tekst naast het sjabloon** (233 tekens). Dat is te bekijken als het vaker gebeurt.

## Verbruik

| | Ruw (beurten) | Account |
|---|---|---|
| Partijenset, centraal | 697.208 | 814.354 |
| F04 en F05, centraal (met opzet) | 552.136 | 552.136 |
| **Totaal** | **1,25M** | **1,37M** |

- Het account begon op 0, na de reset van 02:28 UTC.
- Het verschil van 117.146 tokens bij de partijenset komt van de connector-sessie, die tegelijk op hetzelfde account mat.
- #1464 schatte het centrale deel van de meting op ongeveer 1,0M.
