# Rechtspraak, iteratie – eindverslag over ronde 1 tot en met 5 – 12 november 2026

Soort: *eindverslag*. Het [eerste eindverslag](eindverslag.md) sloot na ronde 3; daarna kwamen er twee rondes bij (opdracht
van de hoofdsessie: een toets op beweringen voor alle connectors, K16, en de punten die ronde 4 opleverde). Vragen:
[`rechtspraak_vragenset_30.json`](../../../../tools/graph-qa/tests/data/rechtspraak_vragenset_30.json), 30 vragen in 32 beurten,
plus vijf extra vragen vanaf ronde 4.

## Per ronde

| ronde | code | goed | deels | fout | zonder model | tokens (30 vragen) | verslag |
|---|---|---|---|---|---|---|---|
| 1 | `bb6b46a5` (bundel 40) | 16 | 11 | 4 (+1 n.b.) | 10 | 2.700.587 | [ronde-1.md](ronde-1.md) |
| 2 | `80ca14f4` (bundel 43) | 26 | 6 | 0 | 16 | 1.934.419 | [ronde-2.md](ronde-2.md) |
| 3 | `a0eeb8de` (bundel 45) | 31 | 1 | 0 | 16 | 1.997.147 | [ronde-3.md](ronde-3.md) |
| 4 | `e7e2ab8a` (bundels 49–51) | 28 | 1 | 3 | 15 | 1.816.452 | [ronde-4.md](ronde-4.md) |
| 5 | `b5b53696` (bundel 54) | 30 | 0 | 0 | 17 | 1.225.839 | [ronde-5.md](ronde-5.md) |

De extra vragen (K16 twee keer, een percentage, een som, een Kamerstukken-feit): ronde 4 3 goed en 2 deels (893.321 tokens),
ronde 5 5 goed (513.494).

Van ronde 1 naar ronde 5 daalden de tokens voor dezelfde 30 vragen met 55%. Daarbij gingen 7 beurten meer zonder model.

## Wat ronde 4 en 5 veranderden

**De toets op beweringen** (`agent/beweringen.py`, voor elke connector en elk sjabloon): een feit in de toelichting dat niet
in het opgehaalde staat, krijgt eerst één correctieronde en daarna het signaal onbevestigd. Als feit telt:
- een datum, termijn of bedrag;
- een getal van drie cijfers of meer;
- een aantal, ook als telwoord, getoetst tegen de aantallen in de trace;
- een instantie bij naam;
- een vergaderjaar, en een dossier met zijn vergaderjaar samen in één bron.

Een som, verschil of percentage van genoemde getallen uit de bron is geen bewering. Na de correctieronde viel het aantal
correctierondes op een afgeleid getal van 2 (ronde 4) naar 0 (ronde 5).

**Bronnen die haperen** (`adapters/http_beleid.py`): één beleid voor welke HTTP-status tijdelijk is, per adapter
gedeclareerd (LiDO: de 400). Een status die tijdelijk blijft, is een storing, geen geweigerde vraag. Een lege tussenstap
(`get-id` zonder id) gaat één keer opnieuw en wordt niet bewaard als "geen". Bij Rechtspraak die de tekst niet geeft, noemt
LiDO de uitspraak (K16).

**Lezen**: de eerste pagina van een lang stuk noemt alle volgende pagina's, voor elke leestool.

**Bronnen**: een zoektreffer of een regeling uit een overzicht is pas een bron als het antwoord haar noemt.

## Wat open blijft

- **Een instantie in een verwijzing** telt als bewering (R15: "Hof van Justitie van de EU" bij een verwijzing naar
  curia.europa.eu). Het signaal is niet fout, wel overbodig.
- **De duur bij LiDO**: een artikel met veel uitspraken kost bij een koude cache 20–108 s, en op een drukke dag meer (ronde 4:
  tot 211 s). Dat ligt bij LiDO.
- **De kosten van lezen**: R27 (vier arresten) kost nog 178k tokens.
- De fixes na ronde 5 (vergaderjaar, de komma, een nummer met een werkwoord) zijn niet meer op acceptatie gemeten.
