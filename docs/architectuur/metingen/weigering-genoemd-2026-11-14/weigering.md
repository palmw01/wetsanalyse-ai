# #1457 – de weigering `genoemd_in_tekst` van `antwoord_duiding` (14 nov 2026)

Soort: *meting*, licht regime: één run per vorm, alleen de opdrachten die de stap raakt.

- **Code:** graph-qa op `913500ca` (bundel 106, met #1457), `CENTRALE_AGENT=meten`.
- **Wat #1457 verandert:** noemt de uitleg een artikel dat alleen in de tekst van een opgehaalde bepaling staat, dan zegt
  de weigering niet meer "niet opgehaald, haal het op met get_artikel". Ze noemt het adres van die bepaling en vraagt de
  passage aan te wijzen of de vermelding weg te laten. Dat gebeurt met de nieuwe code `genoemd_in_tekst`.

**Nulpunten:**

- Partijenset: de G1b-meting (`8aa96d09`, twee runs per vorm,
  [`../methodes-g1b-2026-11-13/g1b.md`](../methodes-g1b-2026-11-13/g1b.md)).
- F04 en F05 centraal: de A2-3c-meting (`26736e4f`, drie runs,
  [`../centrale-agent-2026-11-14-a23c/a23c.md`](../centrale-agent-2026-11-14-a23c/a23c.md)).
- **F04 en F05 supervisor: geen nulpunt.** De laatste supervisorrun van F04 en F05 is die van ronde 0 (`808c908e`). Die
  versie is te oud om mee te vergelijken. De cijfers hieronder zijn alleen een stand.

## Kort

- **Minder gemiste sjablonen na een weigering om een genoemd artikel: niet aangetoond.**
  - De nieuwe code vuurt waar ze moet: bij F05 (de Leidraad noemt artikel 29 Wet OB 1968) en bij 4:5 lid 1.
  - Twee van de vier beurten met `genoemd_in_tekst` vullen daarna het sjabloon. Dat zijn beide supervisorbeurten.
  - Bij centraal vallen F05 en 4:5 lid 1 alsnog terug op tekst. Bij F05 was dat na twee weigeringen `genoemd_in_tekst`,
    bij 4:5 na één weigering `genoemd_in_tekst` en twee `passage_niet_te_tonen`.
  - Na `genoemd_onbekend` mist geen enkel sjabloon. Dat gold ook al voor G1b op de partijenset.
- **Brongetrouw: gelijk.** Faithfulness 1,0 en geen *ongegrond*. Alle 103 blokcitaten staan in de officiële tekst.
  - Twee treffers van de controle zijn vals alarm: een streepje (— tegen –) in een Leidraadcitaat, en lopende tekst
    tussen twee aanhalingen.
  - F05 centraal is *onbepaald*, net als in alle drie de runs van A2-3c.
- **Niet duurder: bij de supervisor ja, bij centraal niet aangetoond.**
  - Partijenset per run, gewogen warm: supervisor 231,6k → 195,6k (−16 %), centraal 201,7k → 228,5k (+13 %).
  - Drie vragen zijn bij centraal meer dan 25 % duurder: 3:45 lid 1, 4:5 lid 1 en 7:10 lid 1. De dure beurten komen
    vooral door de weigering `passage_niet_te_tonen`, niet door de weigering om een genoemd artikel.
  - F04 en F05 centraal samen: 108,6k, tegen 80,4k–105,8k per run in A2-3c (+15 % tegen de mediaan).
- **Verbruik:** 2,90M ruw, tegen een schatting van 2,7M.
  - Partijenset: 1,49M.
  - F04 en F05 centraal: 0,53M.
  - F04 en F05 supervisor: 0,88M.

## Wat er gemeten is

| | Commando | Vormen | Runs |
|---|---|---|---|
| Partijenset (10 Awb-bepalingen) | `centrale_agent_meting.mjs vragen partijen 1` | supervisor en centraal, om en om | 1 |
| F04 en F05 (vervolgvragen met hun opzet) | `centrale_agent_meting.mjs run 1 --vorm <v> --extra '{"agentvorm":"<v>"}' F04 F05` | eerst centraal, dan supervisor | 1 |

- F04 en F05 vragen geen werkgebied. Het meetwerkgebied, dat is weggegooid, was daarom niet nodig.
- Gescoord is met `eval.centrale_agent_sets` (partijenset) en `eval/centrale_agent_vat.py` (F04, F05).
- **De partijenset is sinds G1b veranderd.** #1453 zette de verwachting bij 7:11 lid 2 op `["herroept", "verplicht"]`.
  Het aantal geslaagde 7:11-antwoorden is daardoor niet vergelijkbaar met G1b. De sjablonen en kosten zijn het wel.

Gegevens:

- [`partijen-sets.jsonl`](partijen-sets.jsonl): 20 regels.
- [`vervolg-runs.jsonl`](vervolg-runs.jsonl): 4 regels.
- Het nulpunt staat in de mappen van G1b en A2-3c.

## De drempels

### Minder gemiste sjablonen na de weigering – niet aangetoond

**Partijenset**, per beurt (een beurt met een weigering heeft er één of meer):

| | G1b supervisor (20) | #1457 supervisor (10) | G1b centraal (20) | #1457 centraal (10) |
|---|---|---|---|---|
| Beurten met een weigering | 6 | 4 | 7 | 6 |
| … met `genoemd_onbekend` | 5 | 2 | 6 | 3 |
| … met `genoemd_in_tekst` (nieuw) | – | 1 | – | 1 |
| Sjabloon gemist | 0 | 0 | 0 | 1 (4:5 lid 1) |
| Gemist na `genoemd_onbekend` | 0 | 0 | 0 | 0 |
| Gemist na `genoemd_in_tekst` | – | 0 | – | 1 |

**F04 en F05:**

| | Nulpunt centraal (A2-3c, 3 runs) | #1457 centraal | #1457 supervisor (geen nulpunt) |
|---|---|---|---|
| F04 | 2/3 gevuld. Run 1: geen poging, tekst | gemist, zonder poging (geen weigering) | gemist na `passage_niet_te_tonen` en `genoemd_gelezen+onbekend` |
| F05 | 1/3 gevuld. Twee keer gemist na `genoemd_onbekend`, één keer zonder poging | gemist na twee keer `genoemd_in_tekst` | gevuld na één `genoemd_in_tekst` |

**Wat dit zegt:**

- **De code herkent het geval.** Waar A2-3c bij F05 `genoemd_onbekend` gaf, staat nu `genoemd_in_tekst`. Dit is het geval
  waarvoor #1457 bedoeld is.
- **Het model volgt de nieuwe aanwijzing maar half.** De supervisor wijst daarna de passage aan, bij F05 en bij 4:5. De
  centrale agent doet dat bij F05 twee keer niet, en valt na de tweede weigering terug op tekst.
- **De meting kan niet zeggen waarom.** De tekst van de weigering staat niet in de events.
- **F04 centraal mist het sjabloon zonder het te proberen**, net als in A2-3c run 1. Dat raakt #1457 niet.

### Brongetrouw gelijk – gehaald

| | Citaten | Niet in de bron | Oordeel |
|---|---|---|---|
| Partijen, supervisor | 32 | 0 | 10 × *gegrond* |
| Partijen, centraal | 31 | 0 | 9 × *gegrond*, 1 × *onbepaald* (4:5 lid 1, het gemiste sjabloon) |
| F04 en F05, centraal (met opzet) | 10 | 0 | 3 × *gegrond*, 1 × *onbepaald* (F05, net als in A2-3c) |
| F04 en F05, supervisor (met opzet) | 30 | 0 | 4 × *gegrond* |

**Valse treffers.** De controle vond twee citaten niet, en beide zijn vals alarm:

- F04 supervisor: een citaat uit Leidraad 22.9.2.2. Het staat letterlijk in de Leidraad, alleen met — waar de bron –
  heeft.
- 4:35 (supervisor): lopende tekst tussen twee aanhalingen.

Faithfulness is 1,0 in elke beurt. `niet_letterlijk` en `unsupported` zijn 0.

### Niet duurder (gewogen warm) – supervisor ja, centraal niet aangetoond

**Partijenset, per run:**

| | G1b (gemiddelde van 2 runs) | #1457 | Verschil |
|---|---|---|---|
| Supervisor | 231,6k | 195,6k | −16 % |
| Centraal | 201,7k | 228,5k | +13 % |

**De 25 %-regel**, tegen de mediaan van de twee G1b-runs. Er is geen afwijzing in deze set.

| Vraag | Vorm | G1b, runs | #1457 | Verschil | Weigeringen in #1457 |
|---|---|---|---|---|---|
| 3:45 lid 1 | centraal | 11,6 / 15,4k | 28,6k | +112 % | `passage_niet_te_tonen` |
| 4:5 lid 1 | centraal | 41,9 / 34,1k | 57,0k | +50 % | `genoemd_in_tekst`, 2 × `passage_niet_te_tonen`; gemist |
| 7:10 lid 1 | centraal | 13,2 / 15,2k | 21,4k | +51 % | `genoemd_onbekend` |

- Bij de supervisor gaat geen vraag over de 25 %. Drie zijn meer dan 25 % goedkoper (3:47 lid 1, 4:5 lid 1, 7:10
  lid 1).
- **F04 en F05, centraal:**
  - F04: 69,3k, tegen 75,7 / 24,6 / 41,6k in A2-3c;
  - F05: 39,3k, tegen 30,1 / 55,8 / 52,5k.

  Samen 108,6k tegen 105,8 / 80,4 / 94,1k per run. Dat is binnen de spreiding van A2-3c, maar boven de mediaan.
- **F04 en F05, supervisor (geen nulpunt):** F04 153,1k in 14 rondes, F05 56,5k.
- **Koud:** geen koud begin in deze meting. #1457 verandert de systeemprompt niet, alleen de controle achter het sjabloon.

## Keuzes die ik maakte

De gebruiker sliep en vroeg bij een keuze de aanbevolen optie te nemen. Hieronder staat wat ik zelf besliste.

- **F04 en F05 draaien zonder werkgebied,** met de run-opdracht van het script. De set vraagt er geen.
- **"Minder gemist na de weigering" beoordeel ik als *niet aangetoond*, niet als *niet gehaald*.** Het gaat om één run.
  De code doet wat ze moet, en de supervisor volgt de aanwijzing. Alleen de centrale agent doet dat bij F05 niet.
- **De meerkosten bij centraal schrijf ik niet toe aan #1457.** De twee duurste vragen (3:45 en 4:5) kregen vooral
  `passage_niet_te_tonen`, een andere weigering, die #1457 niet raakt. Met één run blijft dat een lezing.

## Open

1. **De centrale agent volgt `genoemd_in_tekst` niet bij F05.** Twee keer dezelfde weigering, en daarna tekst. Te
   bekijken is of de weigering het adres noemt in de vorm die `bepaling` verwacht. Een paar runs F05 centraal laten zien
   of het bij spreiding blijft.
2. **`passage_niet_te_tonen` is bij centraal nu de meest voorkomende weigering**, met 4 van de 8. Bij 3:45 en 4:5 kostte
   ze de meeste rondes. Dat is een kandidaat voor dezelfde aanpak als #1457: zeggen wat wel kan.
3. **F04 centraal probeert het sjabloon niet.** Dat gebeurde nu en in A2-3c run 1.
4. **Een nulpunt voor F04 en F05 bij de supervisor ontbreekt.** Deze meting is er nu een, op `913500ca`.

## Verbruik

| | Ruw |
|---|---|
| Partijenset, beide vormen | 1,49M |
| F04 en F05, centraal (met opzet) | 0,53M |
| F04 en F05, supervisor (met opzet) | 0,88M |
| **Totaal** | **2,90M** (schatting vooraf 2,7M) |

Bron: de delta van het accountverbruik, na de reset van 23:44 UTC.
