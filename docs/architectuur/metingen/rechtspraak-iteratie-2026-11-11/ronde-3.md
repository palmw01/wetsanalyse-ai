# Rechtspraak, iteratie – ronde 3 – 12 november 2026

Soort: *meting*, de derde van hoogstens vier rondes · Code: acceptatie op master `a0eeb8de` (bundel 45, met #1235) · Straat:
acceptatie, alle vier connectors aan · Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 2](ronde-2.md), R19 in hetzelfde
eigen werkgebied (peildatum 1 januari 2015) · Vragen: dezelfde set.

De ruwe gegevens per run staan in [`runs-3.jsonl`](runs-3.jsonl). Tokens uit het `meting`-event: samen **1.997.147** (ronde 2:
1.934.419). 16 van de 32 beurten gingen zonder model, net als in ronde 2. Geen budgetfout deze keer.

## Score

**31 goed, 1 deels, 0 fout** (ronde 2: 26/6/0, ronde 1: 16/11/4).

Van de zes vragen die in ronde 2 deels waren, zijn er vijf nu goed:

| # | vraag (kort) | ronde 2 | ronde 3 | tokens | wat veranderde |
|---|---|---|---|---|---|
| R11 | wat staat er in HR:2023:1371 | deels | goed | 95.968 | 2 rondes in plaats van 7 (262k); het model leest de pagina's nu in één ronde |
| R15 | ECLI:EU:C:2019:123 | deels | goed | 60.652 | gegrond: de ECLI is een stuk zonder tekst |
| R22 | verdeling per instantie art. 36 Iw | deels | **deels** | 189.141 | de telling klopt, maar het model duidt haar weer ("past bij het civiel- en belastingrechtelijke karakter") |
| R23 | alle bij art. 2 Uitvoeringsregeling Iw | deels | goed | 0 | alle 11 |
| R26 | de Leidraad Invordering 2008 | deels | goed | 94.613 | 204 uitspraken bij de Leidraad als geheel, met de kanttekening |
| R30 | uitspraken en Kamerstukken bij art. 25 lid 2 Iw | deels | goed | 188.372 | de Kamerstukken (2) in een eigen blok naast de uitspraken (23) |

Ook R04, R06, R09 en R10 zijn netter. R04 zegt "van de Centrale Raad van Beroep in maart 2025", R06 "van gerechtshoven", en R09/R10
noemen "Wet op de omzetbelasting 1968" in plaats van het BWB-id. De overige 22 vragen blijven goed.

## Bevindingen

1. **De telling wordt nog geduid** (R22). Het model volgde de regel in de toolbeschrijving niet. Niet verder aangepakt: het is de
   vrije tekst van het model, en een vaste zin in elk resultaat zou elk antwoord met tellingen zwaarder maken. Te volgen.
2. **Een gelezen stuk zonder tekst stond met zijn kale id in de bronnenlijst** (K12, Kamerstukken ronde 3): "kst-1278484" in
   plaats van "Kamerstukken 32140, nr. 342". Sinds ronde 2 blijft een fout mét `stuk` een bron, maar het label kwam alleen uit een
   geslaagd resultaat. **Opgelost** (gedeeld, `provenance._labels`), met een test voor Kamerstukken en Staatsblad.
3. **Gedeelde punten van andere connectors, in deze ronde gebouwd** (eigenaar Rechtspraak):
   - een regeling die alleen in een zoekresultaat staat (`search_wetgeving`, `list_regelingen`, `zoek_uitspraken`), is geen bron;
     een bepaling die een zoektool met tekst gaf, wel (wetgeving_live I03/I20). Daarmee verdwijnt ook "BWBR0011353" uit de
     bronnenlijst van R09;
   - een artikel met een boeknummer ("6:162", uit `boek=6&…&artikel=162`) telt als bekend (wetgeving_live I24/I28);
   - de grens van het blok `stukken` (25) geldt per bron, niet over alle bronnen samen (R30 in ronde 2: 25 uitspraken lieten geen
     ruimte voor de Kamerstukken).

## Wat deze ronde niet zegt

- Eén run per vraag: over de spreiding zegt dit niets. R30 was in ronde 3 goed zonder de fix voor de grens per bron: het model
  koos 23 uitspraken en 2 Kamerstukken, binnen de oude grens.
- De fixes van deze ronde (punt 2 en 3) zijn lokaal getoetst, nog niet op acceptatie.

Voor deze ronde zijn 32 gesprekken aangemaakt. Er is niets gewijzigd of gewist.
