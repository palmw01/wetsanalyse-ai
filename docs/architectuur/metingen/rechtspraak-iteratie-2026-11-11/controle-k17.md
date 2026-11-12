# Rechtspraak, iteratie – controle van K17 – 12 november 2026

Soort: *controle* · Code: acceptatie op master `229b9063` (bundel 47, met #1244) · Uitvoering: zoals de rondes, twee vragen,
één run elk, elk in een eigen gesprek.

K17 (Kamerstukken ronde 3): een lijst uit meer zoekvragen toonde geen zoekvraag en geen totaal. Sinds #1244 noemt het blok elke
zoekvraag met haar totaal. De ruwe gegevens staan in [`controle-k17-runs.jsonl`](controle-k17-runs.jsonl). Tokens uit het
`meting`-event: samen **321.040**.

## Uitkomst

- **R09** (rechtspraak bij art. 3.111 Wet IB 2001): **goed**. Het model zocht drie keer: alle instanties, de Hoge Raad en het
  Parket. Het wees 25 stukken aan uit de laatste twee zoekvragen, en het blok noemt die twee met hun eigen totaal:
  "Gezocht bij artikel 3.111 van Wet inkomstenbelasting 2001, van de Hoge Raad. Nieuwste eerst. Totaal 36. Gezocht bij
  artikel 3.111 van Wet inkomstenbelasting 2001, van het Parket bij de Hoge Raad. Nieuwste eerst. Totaal 68." Een totaal voor
  het hele blok staat er terecht niet. In ronde 3 was de zoekvraag hier leeg.
- **R22** (verdeling per instantie bij art. 36 Iw): **deels**, maar geen toets van K17. Het model zocht deze keer één keer
  (`aantal: 1`), dus het blok heeft gewoon één zoekvraag en het totaal 623. Het duidt de telling weer ("wijst op de juridische
  complexiteit van dit artikel"): het open punt uit ronde 3.

## Wat deze controle niet zegt

Eén run per vraag. Of het model meer zoekvragen in één lijst zet, kiest het zelf.

Voor deze controle zijn twee gesprekken aangemaakt. Er is niets gewijzigd of gewist.
