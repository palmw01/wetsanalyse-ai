# Controle na #1211 – 11 november 2026

Soort: *controle*, een aanvulling op de [meting van vandaag](README.md); die blijft ongewijzigd · Code: master `7afd7d15`
(bundel 37, #1212 met #1211) · Straat: acceptatie, dezelfde bronnen aan · Model: `claude-sonnet-4-6` · Uitvoering: de
acceptatie-MCP, vraag 5 en vraag 3 opnieuw, één run elk, in een nieuw gesprek · Akkoord: de hoofdsessie, samen onder 150k.

De ruwe gegevens staan in [`controle-runs.jsonl`](controle-runs.jsonl). Tokens uit het `meting`-event: samen **140.087**.

## Uitkomst

| # | vraag | tokens | toen | nu |
|---|---|---|---|---|
| 5 | Uitspraken over art. 25 Iw, in het werkgebied met peildatum 1 januari 2015 | 0 | 10/10 `huidige tekst`, `op_peildatum: null`, zoekvraag zonder peildatum | 10/10 `huidige tekst`, `op_peildatum: false`; de zoekvraag zegt "op peildatum 1 januari 2015" |
| 3 | Uitspraken bij art. 25 Iw op peildatum 1 januari 2015 | 140.087 | 14 rijen met alleen het jaar en orgaan "rechtbank"/"gerechtshof" | 14 rijen met dag en gerecht ("Rechtbank Oost-Brabant 2 december 2015"); `titel` leeg |

- **Bevinding 1 is opgelost.** De vaste lijstroute geeft de peildatum van het werkgebied mee (`filters: {peildatum: 2015-01-01}`
  in de tool-trace). De lijst blijft de nieuwste tien, maar elke rij zegt nu dat ze niet bij de tekst op de peildatum hoort, en
  de zoekvraag noemt de peildatum.
- **Bevinding 3 is opgelost voor datum en gerecht.** Het label en de sortering op de dag kloppen. Het veld `titel` blijft
  leeg: de metadata van de Rechtspraak heeft voor deze oudere uitspraken kennelijk geen titel. Het label draagt dezelfde
  gegevens, dus de werkplek mist niets.
- Vraag 3 is verder gelijk aan de meting: dezelfde 14 uitspraken, dezelfde periode (1 januari 2014 tot 31 december 2015),
  `gegrond`, 0 ongegrond, en de LiDO-grens bij twijfel. Tokens: 140.087 tegen 137.130.

## Opvallend

- **De duur wisselde.** Vraag 5 duurde 33 s (toen 0,4 s), vraag 3 had de zoektool 3,5 s nodig (toen 30,9 s). Vraag 5 haalde
  de metadata op voor rijen die nog niet bewaard waren. Of de 33 s daarvan komt of van een trage LiDO, zegt één run niet.
  Bij een volgende meting is dat het punt om te volgen.

Voor deze controle zijn twee gesprekken aangemaakt. Er is niets anders gewijzigd of gewist.
