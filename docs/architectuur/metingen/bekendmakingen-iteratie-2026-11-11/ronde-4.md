# Staatsblad en Staatscourant, iteratie – ronde 4 (11 november 2026)

Soort: *meting* · Code: master `a0eeb8de` (bundel 45, #1238, met #1234: de voorlezing van een kort stuk en het sjabloon
zonder grens op het aantal aanwijzingen) · Straat: acceptatie · Model: `claude-sonnet-4-6` · Uitvoering: zoals
[ronde 1](ronde-1.md), dezelfde 30 vragen, elk één keer, vier tegelijk, 23:19–23:38 UTC. Ruwe gegevens in
[`runs.jsonl`](runs.jsonl) (`ronde: 4`). Tokens = invoer + uitvoer + cache lezen + cache schrijven, uit het
`meting`-event. Dit is de laatste ronde. Het overzicht van alle vier staat in het [eindverslag](eindverslag.md).

**Een storing bij KOOP.** Van 23:20 tot 23:29 UTC gaf de repository van KOOP een time-out op het ophalen van een stuk. De
zoekdienst (SRU) werkte wel, en vanaf hier liep een directe aanvraag ook vast. Daardoor:
- konden B06 (twee keer) en B08 hun stuk niet lezen. Lex zei dat eerlijk ("De bron is op dit moment niet bereikbaar"),
  verzon niets en citeerde niets;
- zijn B06 en B08 na het herstel opnieuw gedraaid in hun eigen gesprek;
- tellen hier de runs na het herstel. De runs tijdens de storing (samen 77.239 tokens) en een herhaling van B04 in
  hetzelfde gesprek (31.675 tokens, met de vorige beurt als context) tellen niet mee;
- heeft B04 zijn eerste run behouden: het antwoord klopt, maar Stb. 2010, 176 komt uit de metadata, met de twijfel dat de
  tekst "tijdelijk niet bereikbaar" was.

## Uitkomst

**27 goed, 3 deels, 0 fout** (ronde 3: 27, 3, 0). **Samen 1.153.439 tokens** (ronde 3: 1.435.498). Dertien vragen gaan
zonder model.

| # | oordeel (r3 → r4) | tokens (r3 → r4) | rondes |
|---|---|---|---|
| B04 | goed → goed | 202.476 → 139.486 | 7 |
| B08 | goed → goed | 42.475 → 20.903 | 1 |
| B15 | goed → **deels** | 23.321 → 23.294 | 2 |
| B16 | **deels → goed** | 186.930 → 73.275 | 3 |
| B21 | **deels → goed** | 328.450 → 155.361 | 4 |
| B22 | deels → deels | 39.677 → 77.006 | 3 |
| B23 | goed → goed | 87.641 → 136.527 | 7 |
| B24 | goed → **deels** | 84.582 → 82.227 | 5 |

De overige 22 vragen zijn gelijk gebleven: dezelfde vorm, de tokens binnen 5%.

**Garanties:** geen run ongegrond, 0 niet-letterlijk, geen naam van een particulier (B15, B30).

## Wat de fixes van ronde 3 deden

- **Geen grens meer op het aantal aanwijzingen** (B16). Lex citeert de aanhef van de artikelen, zo'n 28 losse alinea's,
  in één sjabloonronde. Dat is goed, voor 73k in plaats van 187k. Twee artikelen met overgangsrecht (IX en XXA) staan bij
  de wijzigingen.
- **De voorlezing van een kort stuk** (B21). De code las alle 100 rijen in zeven pagina's, zonder één bladerronde (ronde
  3: zes). De kosten gingen van 328k naar 155k. B22 leest in het vervolg ook het hele stuk, en de citaten lopen nu tot en
  met N.

## Bevindingen

1. **De grens van 48 alinea's kost nog twee rondes** (B21, B22). B21 wil het hele besluit citeren (53 rijen). Het
   sjabloon weigert alles boven `MAX_ALINEAS` en het model probeert het tot het er precies 48 zijn. Daardoor zijn
   M en N niet geciteerd, en B22 eindigt op "luidende:". Mogelijke fix: de code kapt zelf af op 48 en zegt in het blok dat
   de bron meer alinea's telt, in plaats van te weigeren. *Gedeeld*, `sjablonen/extern.blokken`. Een vervolgstap, want
   ronde 4 is de laatste.
2. **Het spoor van de voorlezing zegt zes keer "deels gelezen, er is meer dan dit"** (B21, B22). Elke pagina die de code
   zelf ophaalt, meldt zich als deel. Het spoor zou één regel kunnen geven ("gelezen, 7 pagina's"). *Gedeeld*,
   `nodes/bron_lezen.py`.
3. **Zelf afgeleide nummers** (B21, B22): nog steeds "nieuw artikel 25.2.10". Dit is een fout van het model, zoals in
   rondes 2 en 3.
4. **Spreiding van het model** (B15, B24): het oordeel is hier lager dan in ronde 3, zonder dat er iets aan veranderde.
   - B15 zegt dat exploten "aankondigingen over personen in de Staatscourant" zijn, maar niet dat Lex ze niet zoekt.
   - B24 noemt Stb. 2025, 431 en 1 januari 2026 terecht, maar schrijft het hele artikel 67f aan die wet toe, terwijl die
     alleen lid 6 wijzigde. Ronde 3 had dat goed.
5. **De bronnen van B12 tonen nu ook de stukken uit de voetnoten** (Stcrt. 2021, 12238, Stb. 2023, 381 en 408), terwijl
   die niet gelezen zijn. In ronde 3 stonden alleen de twee versies er. Dit komt waarschijnlijk uit een andere wijziging
   in bundel 44 of 45. Ik meld het bij de hoofdsessie.
6. **Bekend, gedeeld:** de dubbele "alleen als PDF (alleen als PDF)" bij B07 (`bron_lezen._zonder_tekst`, Kamerstukken).

## Wat deze ronde niet zegt

Eén run per vraag. De tekst is gelezen bij B04, B08, B09, B15, B16, B21–B24 en B30. Bij de andere vragen zijn alleen de
route, de tokens, de bronnen en de grounding nagelopen.
