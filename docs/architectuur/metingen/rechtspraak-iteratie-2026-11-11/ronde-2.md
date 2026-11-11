# Rechtspraak, iteratie – ronde 2 – 11 november 2026

Soort: *meting*, de tweede van hoogstens vier rondes · Code: acceptatie op master `80ca14f4` (bundel 43, met #1229) · Straat:
acceptatie, alle vier connectors aan · Model: `claude-sonnet-4-6` · Uitvoering: zoals [ronde 1](ronde-1.md), eerst één keer
ingelogd en dan drie tegelijk · R19 in een eigen werkgebied met peildatum 1 januari 2015 · Vragen: dezelfde set.

De ruwe gegevens per run staan in [`runs-2.jsonl`](runs-2.jsonl). Tokens uit het `meting`-event: samen **1.934.419**, tegen
2.700.587 in ronde 1. **16 van de 32 beurten gingen zonder model** (ronde 1: 10).

Het gedeelde tokenbudget raakte bij R28a op (429 `budget_op`). Na de reset zijn R28a en R28b opnieuw gedraaid, samen in één
gesprek; R26 en R27 liepen al.

## Score

**26 goed, 6 deels, 0 fout** (ronde 1: 16 goed, 11 deels, 4 fout, 1 niet beoordeeld).

| # | vraag (kort) | ronde 1 | ronde 2 | tokens | rondes |
|---|---|---|---|---|---|
| R01 | uitspraken bij art. 9 Iw | goed | goed | 0 | 0 |
| R02 | de 5 nieuwste bij art. 36 Iw | goed | goed | 0 | 0 |
| R03 | nieuwste HR in het belastingrecht | goed | goed | 0 | 0 |
| R04 | CRvB in maart 2025 | deels | goed | 0 | 0 |
| R05 | 10 oudste conclusies bij art. 25 Iw | deels | goed | 0 | 0 |
| R06 | hoven bij art. 67f AWR | deels | goed | 0 | 0 |
| R07 | RvS bij art. 6:7 Awb | fout | goed | 0 | 0 |
| R08 | art. 26 Awir | goed | goed | 0 | 0 |
| R09 | art. 3.111 Wet IB 2001 | fout | goed | 64.918 | 3 |
| R10 | HR bij art. 15 Wet OB 1968 | fout | goed | 64.834 | 3 |
| R11 | wat staat er in HR:2023:1371 | deels | deels | 261.861 | 7 |
| R12 | r.o. 3.1 van HR:2023:1371 | goed | goed | 30.155 | 1 |
| R13 | conclusie PHR:2015:354 | goed | goed | 62.632 | 2 |
| R14 | ECLI:NL:HR:2099:1 | deels | goed | 0 | 0 |
| R15 | ECLI:EU:C:2019:123 | goed | deels | 83.711 | 4 |
| R16 | "ecli nl rbgel 2026 7933" | goed | goed | 134.519 | 4 |
| R17 | huidige tekst art. 36 Iw | deels | goed | 133.850 | 5 |
| R18 | art. 25 Iw op peildatum 2015 | deels | goed | 99.922 | 4 |
| R19 | art. 25 Iw in een werkgebied | – | goed | 0 | 0 |
| R20 | eerdere tekst art. 9 Iw | goed | goed | 160.454 | 6 |
| R21 | hoeveel bij art. 36 Iw | goed | goed | 0 | 0 |
| R22 | verdeling per instantie art. 36 Iw | deels | deels | 122.149 | 5 |
| R23 | alle bij art. 2 Uitvoeringsregeling Iw | deels | deels | 0 | 0 |
| R24 | belastingrecht bij art. 36 Iw | deels | goed | 0 | 0 |
| R25 | CBb bij art. 9 Iw (niets) | goed | goed | 0 | 0 |
| R26 | de Leidraad Invordering 2008 | goed | deels | 163.420 | 6 |
| R27 | art. 36 Iw en de Hoge Raad | goed | goed | 233.620 | 7 |
| R28a | HR bij art. 36 Iw | goed | goed | 0 | 0 |
| R28b | "wat zegt de nieuwste daarvan?" | fout | goed | 76.575 | 3 |
| R29a | 5 nieuwste bij art. 9 Iw | goed | goed | 0 | 0 |
| R29b | "en de volgende 5?" | goed | goed | 102.453 | 4 |
| R30 | uitspraken en Kamerstukken bij art. 25 lid 2 Iw | deels | deels | 139.346 | 5 |

R15 en R26 zakten van goed naar deels: niet doordat ze slechter werden, maar omdat de beoordeling strenger is. R15 kreeg
"ongegrond"; bij R26 is de lijst met willekeurige uitspraken in deze ronde als misleidend beoordeeld.

## Wat de fixes van ronde 1 deden

- **LiDO alleen jurisprudentie** (R07): de Raad van State bij Awb 6:7 geeft 44 uitspraken binnen de 990 die binnenkwamen, en de
  kanttekening noemt de 6.772 die LiDO zelf telt. Ronde 1: 0.
- **Regeling buiten de graaf** (R09, R10): 627 en 168 uitspraken, met de grens dat de tekststand niet vast te stellen is.
- **Tellingen binnen de filters** (R17): de verdeling per instantie telt bij de huidige tekst 469 van de 470, niet meer alle
  623.
- **De lijstroute** (R04, R05, R06, R23, R24): zonder model, waar ronde 1 60–180k tokens per vraag kostte.
- **De leemte, de kanttekening en het blok** (R14, R24, R25, R30): "Bij deze zoekvraag vond ik geen …", "van het College", het
  rechtsgebied dat niet kon, en pagina's van één zoekvraag als één lijst met totaal.
- **Bundel 43, van andere eigenaren**: R28b leest het arrest in plaats van de wettekst, en een zoekresultaat krijgt het sjabloon
  in plaats van een tabel in tekst (R17, R18).

## Bevindingen, oorzaak en wat ermee gebeurt

1. **Een buitenlandse ECLI was "ongegrond"** (R15). `get_uitspraak` gaf `ongeldig_id` met alleen het voorbeeld; de gevraagde ECLI
   stond niet in de trace, dus het antwoord dat haar noemde, faalde de controle. **Opgelost**: een buitenlandse of Europese ECLI
   is `buiten_bereik` met het `stuk` (`leesbaar: false`, `zonder_tekst`). `provenance` slaat een fout met een `stuk` niet over.
2. **"Welke uitspraken noemen de Leidraad Invordering 2008?"** (R26). De tool eiste een artikel, dus zocht het model de zoekfeed
   van het belastingrecht en toonde 18 willekeurige uitspraken. LiDO koppelt een uitspraak die de regeling noemt zonder artikel
   aan de regeling zelf (live: 204 over 40 versies). **Opgelost**: `zoek_uitspraken` met alleen `bwb_id` zoekt die uitspraken,
   met de kanttekening dat een uitspraak die een artikel noemt bij dat artikel staat.
3. **Een regeling buiten de graaf heette "BWBR0011353"** in de zoekvraag (R09, R10). **Opgelost**: de titel uit de
   BWB-zoekdienst (`LidoRechtspraak.titel`, gecachet; een storing is het BWB-id).
4. **De zoekvraag in woorden** (R04, R06): "van 2025-03 tot en met 2025-03", "… en in maart 2025" en "van een gerechtshoven".
   **Opgelost** in `zoekvraag_tekst` (eigenaar Rechtspraak): "van de Centrale Raad van Beroep in maart 2025", "van gerechtshoven".
5. **"Geef alle …" gaf 10 van de 11** (R23). **Opgelost** in `bron_lijst`: "alle" vraagt een volle pagina (25).
6. **Een telling geduid** (R22): "past bij het civielrechtelijke karakter van het artikel". Art. 36 Iw is bestuursrecht; de
   telling zegt dat niet. **Aangepakt** in de beschrijving van de zoektool: een telling duid je niet.
7. **Een samenvatting van een lang arrest leest alle pagina's** (R11: zes pagina's, 262k). **Aangepakt** in de beschrijving van
   de leestool: voor een samenvatting volstaan de inhoudsindicatie, de inhoud en de beslissing. Of het helpt, zegt ronde 3.
8. **De Kamerstukken ontbreken in het antwoord** (R30). Het model zocht ze, en de toelichting kondigt ze aan, maar het wees
   alleen ECLI's aan in het blok. Niet aangepakt: dit is het model in het sjabloon `bepaling`; eerst zien of het terugkomt.

## Wat deze ronde niet zegt

- Eén run per vraag: over de spreiding zegt dit niets.
- De fixes van deze ronde zijn lokaal en live tegen LiDO en de BWB-zoekdienst getoetst, nog niet op acceptatie.

Voor deze ronde zijn 33 gesprekken en één werkgebied aangemaakt ("Meting rechtspraak ronde 2 (uitstel van betaling 2015)").
Er is niets gewijzigd of gewist.
