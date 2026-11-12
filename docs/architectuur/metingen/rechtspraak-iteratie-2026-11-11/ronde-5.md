# Rechtspraak, iteratie – ronde 5 – 12 november 2026

Soort: *meting*, de laatste ronde · Code: acceptatie op master `b5b53696` (bundel 54, met #1268) · Straat: acceptatie, alle
vier connectors aan · Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 4](ronde-4.md), één run per vraag · Vragen:
dezelfde 30 in 32 beurten, plus dezelfde vijf extra vragen.

De ruwe gegevens per run staan in [`runs-5.jsonl`](runs-5.jsonl), met de tellers uit `meting.sjabloon`. De ronde liep in twee
delen: de laptop viel weg na 9 beurten, en daarna liepen alleen de beurten zonder `meting`-event opnieuw.

Tokens uit het `meting`-event:
- de 30 vragen: **1.225.839** (ronde 4: 1.816.452, ronde 3: 1.997.147); 17 van de 32 beurten zonder model;
- de vijf extra: 513.494 (ronde 4: 893.321).

LiDO gaf geen fout. De duur van `zoek_uitspraken` bij een artikel: 20 tot 108 s bij een koude cache (R26, de Leidraad als
geheel: 108 s), daarna enkele milliseconden.

## Score

**De 30 vragen: 30 goed** (ronde 4: 28/1/3, ronde 3: 31/1/0).

| # | vraag (kort) | ronde 4 | ronde 5 | wat veranderde |
|---|---|---|---|---|
| R06 | gerechtshoven bij art. 67f AWR | deels | goed | 487 zoals in ronde 3, via de lijstroute, zonder model (ronde 4: 358, de keten van versies brak af) |
| R08 | art. 26 Awir | fout | goed | 471; de tijdelijke 400 van LiDO is geen geweigerde vraag meer |
| R09 | art. 3.111 Wet IB 2001 | fout | goed | 627, met 36 van de Hoge Raad en 68 conclusies, zoals in ronde 3 |
| R26 | de Leidraad Invordering 2008 | fout | goed | 204 bij de Leidraad als geheel |

De andere 26 zijn goed, net als in ronde 4. De tellingen zijn gelijk aan die van ronde 3 en 4: R10 168, R17 470 en 623, R18 14,
R20 184 en 12, R22 623 met 75, 91, 222, 232, 2 en 1, R30 223.

**De vijf extra: 5 goed** (ronde 4: 3 goed, 2 deels).

| # | oordeel | opmerking |
|---|---|---|
| X1-K16 | goed | `get_uitspraak` las de uitspraak in drie pagina's |
| X2-K16 | goed | beide uitspraken gelezen, in één ronde |
| X3-pct | goed | "12% (75 uitspraken)" en "ruim 26%" met het Parket erbij, zonder correctieronde (ronde 4: het aandeel weggelaten) |
| X4-som | goed | 166 = 75 + 91, met de tekststand per instantie, zonder correctieronde en zonder signaal |
| X5-kst | goed | dossier 20588 uit de graaf; de MvT valt buiten de zoekdienst (vanaf 1994-1995), dus geen datum. Een correctieronde, daarna een vals signaal "20588 valt" (zie *Bevindingen*) |

## De correctieronde

- **3 van de 37 beurten**: R09, R15 en X5. Geen enkele op een afgeleid getal (ronde 4: 2 van 3).
- **R15** (ECLI:EU:C:2019:123): na de correctie staat "Hof van Justitie van de EU" als onbevestigd. Het antwoord verwijst naar
  curia.europa.eu; dat is een verwijzing, geen feit uit eigen kennis, maar de toets kan dat niet onderscheiden.
- **R09** kreeg een correctieronde op een feit dat de events niet noemen. Het antwoord daarna klopt.
- **X5**: na de correctie bleef "20588 valt" staan. Dat is een nummer met een werkwoord erachter, geen telling. Opgelost
  in de PR bij deze meting.

## De tellers uit `meting.sjabloon`

Over alle 37 beurten:
- gevuld: `antwoord_extern` 16, `antwoord_duiding` 1;
- geweigerd: `antwoord_bepaling:bepaling.vul` 3, `antwoord_extern:extern.vul` 3, `antwoord_extern:extern.lijsten` 1;
- gevraagd (het herhaalverzoek) 3, gemist 4;
- `tekst_ernaast` 3.800 tekens (ronde 4: 4.234).

## Bevindingen

1. **Een groot getal met een werkwoord erachter telde als telling** (X5, "20588 valt"). De toets op aantallen (ronde 5)
   eist dat een telling een aantal uit de trace is, en een dossiernummer is dat niet. **Opgelost**: een getal van vier cijfers
   of meer dat in de bron staat, telt als bekend.
2. **De toets ving "dossier 20588, 1988-1989" niet** (Kamerstukken ronde 6, K16). Het getal vóór een komma en het jaar met
   een streepje vielen er allebei buiten, ook zonder bron. **Opgelost**: een getal vóór een komma telt (alleen ",\d" is een
   decimaal), een vergaderjaar is een eigen bewering in één vorm ("1987/88" = "1987-1988"), een dossier met zijn vergaderjaar
   in één zin moet samen in één toolresultaat staan, "20 588" is één getal, en een citeervorm van een connector
   ("Stb. 2009, 610") heeft de toets van een id. Terugmeting zonder model op de antwoorden van ronde 3 en 4: geen nieuwe
   treffers buiten de getallen die alleen in de volledige trace staan.
3. **Een instantie in een verwijzing** (R15) telt als bewering. Niet aangepakt: één geval, en het signaal is niet fout, alleen
   overbodig.

## Wat deze ronde niet zegt

- Eén run per vraag.
- De fixes van punt 1 en 2 zijn lokaal getoetst, niet op acceptatie.

Voor deze ronde zijn 37 gesprekken aangemaakt. Er is niets gewijzigd of gewist.
