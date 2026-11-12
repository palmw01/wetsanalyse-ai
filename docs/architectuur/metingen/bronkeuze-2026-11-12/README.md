# Bronkeuze per vraag (#1261) – meting tegen ronde 5 (12 november 2026)

Soort: *meting* · Code: master `66e73f75` (bundels 52–53, met #1261: elke beurt krijgt alleen de connectortools die de
vraag of het gesprek noemt) · Straat: acceptatie, **alle vier de connectors aan** · Model: `claude-sonnet-4-6` · Uitvoering:
de acceptatie-MCP, één run per vraag in een eigen gesprek ("Ronde 6 bronkeuze – …"); de vervolgvragen K21–K22, K23–K24,
B21–B22 en B16–B26 elk in één gesprek. Vergeleken met ronde 5 van de iteraties van Kamerstukken
([`../kamerstukken-iteratie-2026-11-11/ronde-5.md`](../kamerstukken-iteratie-2026-11-11/ronde-5.md)) en van Staatsblad en
Staatscourant ([`../bekendmakingen-iteratie-2026-11-11/ronde-5.md`](../bekendmakingen-iteratie-2026-11-11/ronde-5.md)), die
ook met alle vier aan liepen, op code `e7e2ab8a`. Tokens = invoer + uitvoer + cache lezen + cache schrijven uit het
`meting`-event. Ruwe gegevens per vraag in [`runs.jsonl`](runs.jsonl), met de cijfers van ronde 5 ernaast. Na K12 was het
tokenbudget op; na een reset is de ronde in dezelfde gesprekken verder gegaan (K13–K16 zonder het user-bericht opnieuw).

## Uitkomst

| | tokens r5 → r6 | modelrondes | per modelronde |
|---|---|---|---|
| Kamerstukken (30) | 1.948.517 → 2.155.167 (+11 %) | 59 → 73 | 33.026 → 29.523 (−11 %) |
| Kamerstukken zonder K07 (29) | 1.718.424 → 1.584.234 (−8 %) | 52 → 56 | 33.047 → 28.290 (−14 %) |
| Staatsblad en Staatscourant (30) | 1.422.232 → 1.082.729 (−24 %) | 51 → 45 | 27.887 → 24.061 (−14 %) |
| samen, zonder K07 (59) | 3.140.656 → 2.666.963 (−15 %) | 103 → 101 | 30.492 → 26.406 (−13 %) |

- **Beperkt tot de genoemde bron** (12 vragen met een model bij Kamerstukken, 14 bij Staatsblad): per modelronde −13 % en
  −23 %. Een beurt die één stuk leest in één ronde, kost 25,8k in plaats van 34,5k (Kamerstukken, n=2) en 23,6k in plaats
  van 31,7k (Staatsblad, n=8): **~8k minder per beurt**, de toolschema's van de drie andere connectors en hun regel in
  BRONNEN IN DEZE BEURT.
- **Niets genoemd, alle vier aan** (K10, K20, B03, B04, B23, B24): per modelronde −2 %, zoals verwacht.
- **K07 is spreiding van het model, geen effect van #1261**: 17 rondes en 571k (ronde 1–5: 19/10/16/11/7 rondes). Alleen
  Kamerstukken was aangeboden, de eerste ronde kostte 19k; het antwoord is goed (dossier 30322, art. 36 en 36b, gegrond).
  Bij één run per vraag is het aantal rondes de grootste ruis; de maat per modelronde is betrouwbaarder dan het totaal.

## Oordelen

Gelezen zijn K07, K10, K16, K18, K20, K22, K24, B15 en B18. Bij de andere vragen zijn route, aantal rondes, bronstand,
grounding en `meting.sjabloon` nagelopen; die zijn gelijk aan ronde 5 (geen ongegrond, geen correctieronde, het sjabloon
gevuld waar het in ronde 5 gevuld werd), en het oordeel van ronde 5 is overgenomen.

- **Eén regressie, B18 (goed → fout)**: "Welke publicaties horen bij Kamerdossier 36602?" noemt het Staatsblad
  ("publicaties"), dus de bronkeuze hield alleen die bron aan. De lijstroute koos in code `zoek_kamerstukken {dossier}`; die
  aanroep liep tegen de beperkte stand aan (`connector_uit`) en Lex zei ten onrechte dat Kamerstukken in dit gesprek uit
  staan. Opgelost in #1270 (`bronkeuze.van_route`: de connector van een route in code hoort altijd bij de keuze).
- **Gelijk aan ronde 5**: K10 deels (de amendementen als tekst, "ruim 85" naast 94), K16 deels (het duiding-sjabloon twee
  keer geweigerd; Rechtspraak niet meer aangeboden, maar de vraag gaat over de wetgever, dus Kamerstukken past), K18, K20,
  K22, K24 en B15 goed.
- Kamerstukken: 28 goed, 2 deels, 0 fout (als ronde 5). Staatsblad en Staatscourant: 27 goed, 2 deels, 1 fout (ronde 5:
  28, 2, 0); zonder B18 gelijk.

## Andere bevindingen

1. **De bronkeuze ziet een soort stuk niet als signaal**: "amendement" (K10) en "motie" (K20) staan in de beschrijving als
   `soorten`, niet als signaal, dus daar bleef alles aan. "publicatie" in het enkelvoud (B24) is geen signaal, "publicaties"
   wel. Een soort als signaal tellen is niet zonder meer goed: "wet", "verslag" en "brief" zijn te algemeen.
2. **Een vervolgvraag mist de cache** (B26, los van #1261): drie rondes lezen alleen het vaste deel (17,9k) uit de cache en
   schrijven elk ~14,5k opnieuw. B16 zelf (zelfde gesprek, eerste beurt) heeft dat niet.
3. **`tekst_ernaast`** (tekst naast een sjabloonaanroep, #1257): 5.293 tekens over 23 beurten, het meest bij K22 (810).

## Wat deze meting niet zegt

Eén run per vraag; het aantal rondes spreidt sterk (K07, K15, B23, B24). De meting van B18 na #1270 volgt na de uitrol.
