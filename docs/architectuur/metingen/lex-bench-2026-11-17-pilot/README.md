# Lex Bench, pilot LB3 (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Plan: [`../../plan-lex-bench.md`](../../plan-lex-bench.md) §9 ·
Voorstel: [`../../../lex-bench/pilot-lb3.md`](../../../lex-bench/pilot-lb3.md) · Akkoord gebruiker: "ja eerst klein" (LB-07 A),
daarna "Ja, rest pilot"

De pilot draaide het hele proces één keer op drie nieuwe ontwikkelcasussen, één per niveau:
1. het team blind;
2. de tegenlezer bij makkelijk;
3. samenvoegen en bevriezen;
4. de opname van de graaf ná het bevriezen;
5. arm L1 tegen de teamverwachting;
6. de reviewer per verschil;
7. arm L2 op LB-08.

Alle verwachtingen zijn `concept`, en nog geen jurist heeft ze vastgesteld. De cijfers zijn dus een trendmeting
(besluit 2).

## Uitkomst

L1 tegen de bevroren teamverwachting, met de categorieën zoals de reviewer ze voorstelt (de jurist beslist):

| casus | niveau | recall nodig | recall | precisie | overlap | Lex mist | Lex onterecht | team mist | twijfel |
|---|---|---|---|---|---|---|---|---|---|
| LB-07 Beslistermijn (Awb) | makkelijk | 1/20 | 2/24 | 0/24 | 2/48 | 22 | 23 | 0 | 1 |
| LB-08 Terugvordering toeslag | gemiddeld | 1/30 | 1/31 | 1/24 | 1/54 | 30 | 22 | 0 | 1 |
| LB-09 Achteraf alsnog belasting | moeilijk | 2/16 | 2/19 | 2/32 | 2/49 | 17 | 28 | 0 | 2 |

**L2 op LB-08** (acceptatie, werkgebied *Bench LB-08 lb-08-2026-11-17-l2*): dezelfde maten als L1 (1/30, 1/31, 1/24,
1/54) en 0 tokens van Lex. De lijsten zelf verschillen wel: per deelvraag overlappen L1 en L2 maar 5/11, 6/10 en 7/9
bepalingen, met dezelfde zoekversie `za28985cb2f88`.

## Wat de reviewer zag

- **LB-07:** Lex zoekt op het woord *aanvraag* en komt uit bij de regels voor het indienen (4:1–4:6) en bij de subsidietitel
  (4:60, 4:64, 4:65). De beslistermijn (4:13–4:15) en de dwangsom (4:17–4:20) mist hij helemaal.
- **LB-08:** Lex vindt de goede artikelen soms wel, maar zet ze bij een andere deelvraag:
  - 26 lid 2, 26a en 26b staan bij deelvraag 3 en horen bij 1;
  - 28 lid 1 staat bij 3 en hoort bij 2;
  - 32 lid 1 staat bij 1 en 2 en hoort bij 3.

  Daarnaast kiest hij de uitbetaling van het voorschot in termijnen (art. 22) waar het om terugbetalen in termijnen gaat:
  een woordtreffer.
- **LB-09:** Lex komt via *termijn* en *jaar* bij artikelen over publicatieduur, klachten en schorsing, en via *straf* bij
  het strafrecht (69–74 AWR), dat buiten het werkgebied valt. Navordering (art. 16), belastingrente (30fc) en de
  vergrijpboete (67e, 67n) mist hij.
- *Team mist* kwam in geen enkele casus voor. De reviewer kon de plek bijna nooit zien (`onbekend`): de kaart toont
  geen pool en geen rang van Lex.

## Verbruik

| arm | wie | tokens (Agent-tool, laatste context) | aanroepen |
|---|---|---|---|
| T | LB-07 A | 130.811 | 30 bron_lezen, 12 graaf_lezen |
| T | LB-08 A | 216.076 | 66 bron_lezen, 18 graaf_lezen |
| T | LB-08 B | 229.333 | 72 bron_lezen, 22 graaf_lezen |
| T | LB-09 A | 148.685 | 32 bron_lezen, 6 graaf_lezen |
| T | LB-09 B | 140.565 | 32 bron_lezen, 12 graaf_lezen |
| tegenlezer | LB-07 | 115.591 | 22 bron_lezen, 2 graaf_lezen |
| reviewer | LB-07 | 119.846 | 32 bron_lezen |
| reviewer | LB-08 | 140.850 | 36 bron_lezen |
| reviewer | LB-09 | 163.954 | 62 bron_lezen, 6 graaf_lezen |
| **agents samen** | | **1.405.711** | |
| L1 | code | 0 | |
| L2 | Lex | 0 (verbruik vóór en na 556.079) | 0 modelrondes |

- **Plafonds:** elke agent bleef onder zijn plafond (250k per analist, 200k per reviewer, 150k voor de tegenlezer), en de
  agents samen bleven onder 2,2M.
- **De coördinator** was een lange sessie: aan het eind 743k context, en sinds de start van de pilot 38,8M tokens uit de
  cache gelezen. Dat ligt ver boven de geschatte 200k. Het gevolg voor de weeklimiet is te zien aan het percentage dat de
  hoofdsessie afleest.
- Het getal van de Agent-tool is de context van de laatste ronde. Wat de agent over al zijn rondes uit de cache las, ligt
  5 tot 15 keer hoger; dat staat in `run.json`.

## Bevindingen over het proces

1. **De coördinator kost het meest.** Een verse sessie per casus houdt zijn context klein. De opdrachten zijn 17.000 tot
   30.000 tekens en gaan letterlijk in de prompt; een tool waarmee de agent zijn opdracht zelf leest, scheelt
   uitvoertokens.
2. **Klaar zonder besluit** zet de kandidaten op *niet gekozen*. De stap "wat eraan hangt" komt dan niet. L2 meet zonder
   besluiten dus alleen de kernlijst.
3. **L1 en L2 geven dezelfde score maar andere lijsten.** Dat vraagt een eigen onderzoek: welk deel van de route ziet in
   de werkplek iets anders dan offline?
4. **Het logboek kende de rol `analist` niet**: de MCP-server liep nog op een build van vóór #1677. LB-07 A en LB-08 A
   logden daarom als `jurist`. Na een herstart van de sessie werkte het.
5. **Een formulier met een onbekend veld.** LB-08 A gaf `rol_placeholder: null` mee. Terugsturen had het plafond
   overschreden, dus de coördinator haalde het veld weg. Het origineel staat in `LB-08/formulier-a.origineel.json`.
6. **De reviewer mist een plek voor "verkeerde deelvraag".** Bij LB-08 schreef hij het in de reden, maar de enum kent
   het niet.

## Bestanden

Per casus:
- `formulier-*.json`: het formulier van de analist;
- `tegenlezing.json`: alleen bij LB-07;
- `teamverwachting.json` en `bevroren.json`: de bevroren teamverwachting, met de sha256 van de bestanden;
- `graafantwoorden.json`: de opname, ná het bevriezen, alleen lezend via de MCP-proxy;
- `review-verschillen.json` en `review-telling.json`: de review en de telling;
- bij LB-08 ook `keuze-l2.json` en `kaart-l2.json`: de lijsten van het paneel en hun score.

Over alle casussen heen staan `rapport.json` en `run.json` in de meetmap zelf.

De dossiers staan in [`../../../lex-bench/bronselectie/pilot/`](../../../lex-bench/bronselectie/pilot/). Het werkgebied en
het gesprek van L2 blijven op acceptatie staan als bewijs.
