# Staatsblad en Staatscourant, iteratie – ronde 5 (12 november 2026)

Soort: *meting* · Code: master `e7e2ab8a` (bundels 49–51: #1251 sjabloon in één ronde, #1252 telvragen, #1253 de
id-controle in `tool_execution`, #1255 de beweringentoets, #1257 geen antwoord in het denkproces) · Straat: acceptatie ·
Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 1](ronde-1.md), dezelfde 30 vragen, elk één keer, vier tegelijk,
09:08–09:40 UTC, plus zes vragen waarbij Lex een id uit eigen kennis zou kunnen gebruiken (I01–I06). Ruwe gegevens in
[`runs.jsonl`](runs.jsonl) (`ronde: 5`). Tokens = invoer + uitvoer + cache lezen + cache schrijven, uit het
`meting`-event.

**Bronstand.** In elke run stonden alle vier de connectors aan: Kamerstukken, Staatsblad en Staatscourant, Rechtspraak
en Wetgeving buiten de kennisgraaf (het `bronstand`-event, reden "aan"; de gesprekken hadden geen eigen keuze). Een
vraag kon dus bij elke connector terechtkomen. Daarom koos de lijstroute bij B18 Kamerstukken en las I04 bij Rechtspraak.

## Uitkomst

**De 30 vragen: 28 goed, 2 deels, 0 fout** (ronde 4: 27, 3, 0). **Samen 1.422.232 tokens** (ronde 4: 1.153.439, +23%).
Twaalf vragen gaan zonder model (ronde 4: dertien; B18 viel terug, zie bevinding 1). **51 modelrondes**.

**De id-vragen: 5 goed, 1 deels.** Samen 1.115.541 tokens, waarvan 508.364 voor I04.

**Garanties:** geen run ongegrond, 0 niet-letterlijk, geen naam van een particulier (B15, B30).

| # | oordeel (r4 → r5) | tokens (r4 → r5) | rondes |
|---|---|---|---|
| B03 | goed → **deels** | 164.757 → 135.225 | 5 |
| B04 | goed → goed | 139.486 → 234.582 | 8 |
| B15 | **deels → goed** | 23.294 → 31.990 | 2 |
| B18 | goed → goed | **0 → 184.237** | 6 |
| B21 | goed → goed | 155.361 → 45.040 | 1 |
| B22 | **deels → goed** | 77.006 → 49.227 | 2 |
| B24 | **deels → goed** | 82.227 → 117.377 | 5 |
| B26 | goed → **deels** | 102.516 → 129.623 | 4 |

Wat een stuk leest in één ronde (B06, B08, B09, B12, B25, B27, B30) kost nu 28–31k, in ronde 4 was dat 21–23k. Dat is
ongeveer 8k per beurt extra. De oorzaak heb ik niet vastgesteld: de uitsplitsing van de tokens kwam niet meer terug uit
de events. Het valt samen met #1255 en #1257, dus het hoort bij de hoofdsessie.

### Correctierondes en `meting.sjabloon`

Opgeteld over de 30 vragen:
- `gevuld`: 16;
- `geweigerd`: 4 (twee keer `duiding.vul` bij B04, één keer `extern.blokken` bij B16, één keer `extern.lijsten` bij
  B18);
- `gemist`: 2 (B15, B30: geen sjabloon nodig, het stuk valt buiten bereik);
- `tekst_ernaast`: 3.328 tekens, bij 10 antwoorden.

Er waren dus vier correctierondes: elke `geweigerd` kost er één. In ronde 4 kostte de grens van 48 alinea's alleen al
twee rondes in B21 en twee in B22. Die zijn weg (#1251).

Over de id-vragen: `gevuld` 4, `geweigerd` 2 (`extern.vul`, bij I03 en I05), `gevraagd` 1, `tekst_zonder_lijst` 1,
`tekst_ernaast` 813.

## De id-controle (#1253)

| # | vraag | wat de controle deed | oordeel | tokens |
|---|---|---|---|---|
| I01 | artikel 2 van de Wet op de zorgtoeslag (buiten de graaf) | niets te doen: de code las de wettekst zelf | goed | 914 |
| I02 | Staatsbladen bij de Wet op de zorgtoeslag | BWBR0018451 doorgelaten: de supervisie had het id zelf uit de vraag gehaald (`buiten_graaf.genoemd`) | goed | 206.805 |
| I03 | de memorie van toelichting bij de Invorderingswet 1990 | **dossiernummer uit eigen kennis geweigerd**, daarna gezocht | goed | 265.730 |
| I04 | het Quint Wellington Redwood-arrest | **ECLI uit eigen kennis geweigerd**, daarna gezocht | deels | 508.364 |
| I05 | het Staatsblad van de Invorderingswet 1990 | Lex zocht zelf eerst: Stb. 1990, 221 | goed | 131.997 |
| I06 | artikel 9 van de Invorderingswet 1990 (in de graaf) | niets te doen: de code las het artikel zelf | goed | 1.731 |

- **De controle weigerde twee keer, beide terecht, en nergens ten onrechte.** Er was geen enkele `id_niet_uit_gesprek`
  in de 30 vragen, en geen extra zoekronde bij een BWB-id van een regeling in de graaf (B04, B23, B24, I03:
  `get_artikel`, `get_regeling_info`, `grondslagen` en `zoek_bekendmakingen` op BWBR0004770). Zo is de regel bedoeld.
- **I03:** het model vroeg `zoek_kamerstukken` met een dossiernummer uit eigen kennis. Na de weigering zocht het op
  woorden. Het antwoord noemt geen verzonnen dossier en zegt dat de oorspronkelijke memorie van toelichting (van vóór
  1995) niet bij de zoekdienst staat. In ronde 4 van Kamerstukken (K17) noemde Lex hier nog een dossier dat KOOP niet
  kent.
- **I04:** de vraag gebruikte een verkeerde naam. Het arrest is Quint/Te Poel. Lex probeerde eerst `get_uitspraak` met
  ECLI:NL:HR:1957:AG2023 uit eigen kennis. Na de weigering zocht het en vond het HR 30 januari 1959,
  ECLI:NL:HR:1959:AI1600. Dat klopt, en Lex verbeterde de naam. Maar de beurt kostte 508k, met zes keer `get_uitspraak`
  op hetzelfde ECLI. Ook toont de bronnenlijst losse Awb-artikelen (8:79, 8:61, 1:7 …) die niets met het arrest te maken
  hebben. Dat hoort bij Rechtspraak, niet bij de id-controle.
- **I02 is geen gat in de controle.** De supervisie herkent een regeling buiten de graaf die de vraag bij naam noemt, en
  zet haar id in de context van de beurt. Een id dat de code daar zette, telt als gesprek.

## Bevindingen

1. **B18 gaat weer naar het model: 0 → 184k** (generiek, gedeeld: `bron_lijst._bij_regeling`, uit #1252). "Welke
   publicaties horen bij Kamerdossier 36602?" bevat "horen bij". Daarmee leest `_bij_regeling` het als "stukken bij een
   regeling". De vraag noemt geen regeling, en dan geeft de functie `()` terug ("niet eenduidig"). Dat breekt de hele
   lijstvraag af, terwijl het dossierfilter de vraag gewoon zou lezen. In ronde 4 deed de code dat ook
   (`zoek_kamerstukken {dossier: 36602}`). De fix: als er geen regeling genoemd wordt, is het dit patroon niet (`None`);
   alleen bij meer dan één regeling is het niet eenduidig. Dit raakt elke connector met een lijstvraag die "horen bij"
   zegt zonder regeling.
2. **De zoekvraag zegt "Gezocht bij artikel  van BWBR0004770"** (B03; generiek, gedeeld: `sjablonen/extern._zoekvraag`).
   Een zoekvraag met alleen `bwb_id` en zonder artikel geeft een lege plek voor het artikel en het kale id in plaats van
   een naam. Dat zie je bij elke connector met een veld `wetsverwijzing` (Rechtspraak en Bekendmakingen).
3. **Tellingen in de eigen tekst van het model** (B03: "vijf wetten" bij vier; B26: "vier aanpassingen" bij vijf). De
   lijsten eronder kloppen, alleen het getal in de toelichting niet. De beweringentoets (#1255) toetst geen aantallen.
   *Gedeeld*, voor de hoofdsessie. Een fix per connector is niet zinvol.
4. **Een stuk lezen kost ongeveer 8k meer per beurt** (zie hierboven). *Gedeeld.*
5. **B04 weigert het duiding-sjabloon twee keer** (`duiding.vul`): 139k → 235k. Het antwoord is goed. *Gedeeld*
   (`sjablonen/duiding`).

## Wat de fixes van ronde 4 deden

- **B24** (de toelichting bij een artikel zegt dat de BWB per artikel koppelt): Lex leest nu de bekendmaking en schrijft
  alleen lid 6 aan Stb. 2025, 431 toe, met de grens erbij als twijfel. Deels → goed. Het kost één leesronde meer
  (82k → 117k).
- **B22**: in ronde 4 telde ik "nieuw artikel 25.2.10" als een nummer dat het model zelf afleidde. Dat was onjuist.
  Onderdeel D van Stcrt. 2025, 22266 zegt letterlijk "Na artikel 25.2.9 wordt een nieuw artikel ingevoegd, luidende:
  25.2.10 …". De rest van het oordeel in ronde 4 (citaten tot "luidende:") is met #1251 opgelost: het blok zegt nu welke
  alinea's niet geciteerd zijn.
- **B15** is weer goed: "zoek en lees ik niet", zonder het antwoord tot invordering en belastingen te beperken.

## Wat deze ronde niet zegt

Eén run per vraag. De tekst is gelezen bij B03–B09, B12, B15, B16, B18, B21–B27, B30 en I01–I06. Bij de andere vragen
zijn alleen de route, de tokens, de bronnen en de grounding nagelopen.

## Fixes voor ronde 6 (deze PR)

- **Bevinding 1** (`bron_lijst._bij_regeling`): noemt de vraag geen regeling bij naam, dan is het het patroon "stukken bij
  een regeling" niet (`None`), en leest de rest van `lees` de vraag. Een naam die de graaf niet kent, blijft over en gaat
  naar het model. Alleen bij meer dan één regeling, of zonder namenlijst, is het "niet eenduidig". De tests staan in
  `tests/test_bron_lijst.py`: "horen bij Kamerdossier" leest het dossierfilter, en een onbekende naam gaat naar het model,
  bij drie connectors.
- **Bevinding 2** (`sjablonen/extern._bepaling_in_woorden`): als de tool geen `bepaling` gaf, maakt de code die zelf. Met
  een artikel wordt dat "artikel 36 van de Invorderingswet 1990". Zonder artikel is het de regeling als geheel: met de naam
  als het proces die kent, anders het id. Er blijft geen lege plek over. De test staat in `tests/test_extern_sjabloon.py`
  en loopt voor elke connector met een veld `wetsverwijzing`.
