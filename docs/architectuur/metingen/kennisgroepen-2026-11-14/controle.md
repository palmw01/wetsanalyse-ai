# Kennisgroepstandpunten, controle van B13 en B15 – 14 november 2026

- **Soort:** *controle*, geen derde ronde: alleen de vier vragen die in ronde 2 matig of fout waren (8, 11, 13, 15), één
  run, centraal.
- **Code:** master `d2c1f585` (bundel 109), op acceptatie; budget gereset om 02:28 UTC. Daarin de fixes B13 en B15 uit
  [#1468](https://github.com/palmw01/wetsanalyse-ai/pull/1468), **en ook #1464** (de centrale agent krijgt de afrondregel van
  duiding). Die loopt mee: wat hieronder verandert, is niet te scheiden tussen de twee. Vraag 13 en 15 gaan via de route
  `duiding`, waar #1464 niets aan verandert; vraag 8 en 11 via de centrale agent, waar het wel kan meespelen.
- **Uitvoering:** als ronde 2 ([`ronde-2.md`](ronde-2.md)), elk in een nieuw gesprek.

## Uitkomst

| # | ronde 2 | nu | wat er gebeurde |
|---|---|---|---|
| 8 | matig | **goed** | totaal 93 en 13 ingetrokken of vervallen apart; de verdeling per belastingsoort precies uit de index (IB 37, AWR 24, VPB 13, LB 7, …), zonder reeksen; 2 rondes, 42k tokens. Gesprek `0a9be642d1f14b69`, run `d4e3056b…` |
| 11 | matig | *matig* | de status juist (beleid, bindt de inspecteur, niet de rechter), maar weer zonder vindplaats; het vertrouwensbeginsel komt uit eigen kennis en "artikel 4:84 Awb" wordt genoemd zonder het te lezen (grounding: `onbevestigd`). B8 blijft open. Gesprek `b6b3344611494994` |
| 13 | fout | **goed** | "het artikel is gewijzigd na dit standpunt, maar of het zeventiende lid zelf anders luidt, staat daar niet bij", met de raad het lid op twee peildata te vergelijken. Geen onjuiste uitspraak meer; het lid vergelijkt Lex niet zelf. Gesprek `a02f8757dc904f4a` |
| 15 | matig | *matig* | de stukken en pagina's juist, maar nr. 9 opnieuw "nota van wijziging"; volgens officielebekendmakingen.nl is kst-31930-9 de *nota naar aanleiding van het verslag* (gecontroleerd 14 nov 2026). B14 blijft open. Gesprek `6cf7baac56964e1e` |

Tokens samen 131.511 (8: 41.508; 11: 40.528; 13: 24.293; 15: 25.182).

## Eindstand

**18 goed, 2 matig, 0 fout van 20** (ronde 1: 12/2/6, ronde 2: 16/3/1), garanties 20/20 in elke ronde. Het doel uit plan
§4 (≥ 17 goed, 0 fout) is gehaald. Twee kanttekeningen: de eindstand combineert ronde 2 (zestien vragen) met deze controle
(vier), en #1464 loopt mee in de controle.

## Open

- **B8** (vraag 11): de status van een kennisgroepstandpunt zonder vindplaats, en eigen kennis over beleidsregels. Wat
  ontbreekt is een tekst van de bron zelf die de status uitlegt, als vindplaats.
- **B14** (vraag 15): het soort van een Kamerstuk dat een standpunt alleen citeert, leidt het model af uit een citaat ("in
  de nota van wijziging voor") in plaats van het op te zoeken bij Kamerstukken.
- **B10**: `?search=` vindt een kenmerk met voorloopnullen in de titel niet (alleen de terugvalweg zonder index).
- **B11** (vraag 3): een regeling buiten de graaf staat in de zoekvraag als BWB-id, niet met haar naam.
- **B12** (vraag 6): de toelichting herhaalt de gevonden lijst in lopende tekst.
- Vraag 13: Lex zegt eerlijk dat de tekststand niets over het lid zegt, maar vergelijkt het lid niet zelf op beide data.

Voor deze controle zijn vier gesprekken aangemaakt. Er is niets gewijzigd of gewist.
