# Staatsblad en Staatscourant, iteratie – ronde 1 (11 november 2026)

Soort: *meting* · Code: master `bb6b46a5` (bundel 40, met #1210 en #1214) · Straat: acceptatie, connector `bekendmakingen`
aan · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke vraag in een eigen gesprek met
`bronnen: ["bekendmakingen"]`; de vervolgvragen B22 en B26 in het gesprek van B21 en B16. Drie runs liepen tegelijk.
Opdracht: iteratieve verbeterrondes per connector (de hoofdsessie, 11 nov 2026).

De vragen, de verwachte route, tool en argumenten, en wat een goed antwoord is, staan in
[`bekendmakingen_vragenset.json`](../../../../tools/graph-qa/tests/data/bekendmakingen_vragenset.json) (30 vragen, B17–B30
nieuw in deze ronde). De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl) (`ronde: 1`). Tokens = invoer +
uitvoer + cache lezen + cache schrijven, uit het `meting`-event. De verbruiksteller van het account is tijdens de ronde
gereset (15:28 UTC), dus de som per run is de maat.

## Uitkomst

**21 goed, 8 deels, 1 fout. Samen 1.518.494 tokens.** Negen vragen gaan zonder model (0 tokens).

| # | route | rondes | tokens | duur | oordeel |
|---|---|---|---|---|---|
| B01 | lijstroute | 0 | 0 | 0,6 s | goed |
| B02 | lijstroute | 0 | 0 | 0,5 s | goed |
| B03 | model | 5 | 105.457 | 43,9 s | deels |
| B04 | model | 8 | 165.540 | 45,3 s | goed |
| B05 | model | 4 | 72.921 | 24,6 s | deels |
| B06 | genoemd stuk | 2 | 41.942 | 14,8 s | goed |
| B07 | genoemd stuk | 1 | 19.377 | 4,8 s | goed |
| B08 | genoemd stuk met artikel | 3 | 44.772 | 17,9 s | goed |
| B09 | genoemd stuk | 1 | 21.043 | 7,8 s | goed |
| B10 | lijstroute | 0 | 0 | 0,6 s | goed |
| B11 | lijstroute | 0 | 0 | 0,4 s | goed |
| B12 | genoemd stuk | 3 | 66.960 | 24,7 s | deels |
| B13 | genoemd stuk | 1 | 19.078 | 9,2 s | goed |
| B14 | lijstroute | 0 | 0 | 0,4 s | goed |
| B15 | model | 2 | 23.243 | 7,8 s | goed |
| B16 | genoemd stuk | 7 | 184.674 | 66,2 s | goed |
| B17 | lijstroute | 0 | 0 | 0,4 s | goed |
| B18 | model | 3 | 44.667 | 12,3 s | deels |
| B19 | lijstroute | 0 | 0 | 0,6 s | goed |
| B20 | model | 3 | 44.604 | 7,9 s | deels |
| B21 | genoemd stuk | 9 | 286.700 | 87,6 s | deels |
| B22 | vervolg op B21 | 2 | 35.738 | 21,9 s | deels |
| B23 | model | 5 | 87.501 | 40,1 s | goed |
| B24 | model | 5 | 88.955 | 28,9 s | goed |
| B25 | genoemd stuk | 1 | 21.710 | 10,8 s | **fout** |
| B26 | vervolg op B16 | 4 | 105.279 | 49,4 s | goed |
| B27 | genoemd stuk | 1 | 19.104 | 5,3 s | deels |
| B28 | lijstroute | 0 | 0 | 0,7 s | goed |
| B29 | lijstroute | 0 | 0 | 0,6 s | goed |
| B30 | genoemd stuk | 1 | 19.229 | 6,4 s | goed |

**Garanties:** geen run ongegrond (gegrond of onbepaald), 0 niet-letterlijk, elke passage in `extern` komt uit een gelezen
stuk, geen naam van een particulier (B15, B30). Feiten nagelopen tegen KOOP en de graaf: B10 (38), B11 (11), B17–B20,
B23 (artikel XII van Stb. 2024, 435), B24 (Stb. 2025, 431, in werking 1 januari 2026, uit de acceptatiegraaf), B25 (er
is een versie n1).

## Bevindingen

Gebundeld per oorzaak. Bij elke bevinding staat of de oorzaak in code van deze connector zit of in code die alle
connectors delen.

1. **Een lijst gevonden stukken komt als vrije tekst, zonder het blok `stukken`** (B03, B05, B18, B20). Het antwoord klopt
   inhoudelijk, maar er staan geen links, geen zoekvraag en geen totaal uit de code bij. B05 zette de lijst in een
   markdown-tabel, met datums uit de zoekrijen. In de hermeting van 10 november kreeg B05 het blok wel. Het model kiest
   dus soms tekst in plaats van het sjabloon, en dat mag (`sjabloon gemist` wordt alleen gelogd). *Gedeeld:*
   `nodes/antwoord.py`, `nodes/sjabloon.py`.
2. **Een geweigerd sjabloon kost per fout een ronde** (B16: vijf rondes van ~850 tokens uitvoer na het lezen, 2/3 van de
   184k; B21: twee; B04: twee korte). `extern.blokken` weigert de hele aanroep bij de eerste fout in één aanwijzing en noemt
   alleen die fout. Een ontbrekende reeks alinea's somt hij nummer voor nummer op. Het model herstelt zo één fout per ronde
   en stuurt telkens het hele antwoord opnieuw. Dit is afgeleid uit de vorm van de rondes; de weigeringen zelf staan
   niet in het event, en de logs zijn vanuit de MCP niet te lezen. *Gedeeld:* `sjablonen/extern.py`.
3. **Andere versies van een stuk zijn onzichtbaar** (B25 fout: "kent geen meerdere versies", terwijl stcrt-2024-20015-n1
   bestaat; B12: noemt de eerdere versie niet). Het `stuk` van `get_bekendmaking` zegt niets over herdrukken, tweede
   versies of verbeterbladen met hetzelfde blad, jaar en nummer. *Deze connector* (`bekendmaking_tools`,
   `sru_bekendmakingen`). Het geldt waarschijnlijk ook voor Kamerstukken (een herdruk krijgt `-n1`).
4. **Het oudere XML-formaat van de Sdu is niet te lezen** (B27). Stb. 1995, 1 staat bij KOOP als XML met de wortel
   `staatsbl` (DTD "staatsblad xml 1.1"). `op_xml.lees` kent die wortel niet en geeft `onleesbaar_document`, "geen stuk in
   het document", zonder metadata of link. Lex gokt dan "waarschijnlijk alleen een PDF" en linkt naar de voorpagina.
   *Gedeeld:* `tools/op_xml.py` (ook gebruikt door Kamerstukken).
5. **De lijstroute mist twee gewone vormen** (B18, B20). "Kamerdossier 36602" is geen dossier voor `_DOSSIER_RE` (die kent
   alleen "dossier", "dossiernummer" en "kamerstukdossier"). En "wetten" is geen soort, want de soorten van de beschrijving
   kennen geen Wet. Beide vragen gaan daardoor naar het model (45k elk) en komen terug zonder blok. *Gedeeld:*
   `agent/bron_lijst.py` (de dossiervorm); *deze connector*: `BEKENDMAKINGEN.soorten` in `bronmodel.connectors`.
6. **Een stuk van 100 rijen lezen kost zeven rondes** (B21, 287k). Bij "wat staat er in" leest het model de pagina's na
   elkaar (30, 24, 12, 12, 9, 9 en 4 rijen), want de alinea's zijn lang en de begroting per pagina is 8.000 tekens. Het
   antwoord is goed. Elke ronde leest de hele context opnieuw (cache). *Gedeeld:* de begroting
   (`resultaat.BUDGET`); voor nu geen fix, eerst meten na bevinding 2.
7. **Kleine dingen:**
   - De zoekvraag zegt "van de Ministerie van Financiën" (B10, ook in de hermeting). *Gedeeld:* `zoekvraag_tekst`.
   - Een leemte zegt "Meest relevante eerst." terwijl er niets is (B14). *Gedeeld:* `nodes/bron_lijst.py`.
   - B15 zegt dat aankondigingen over personen niet in de Staatscourant *staan*. Ze staan er wel, Lex leest ze alleen
     niet. Het model las de grens in de beschrijving ("staan er niet in") als een feit over het blad. *Deze connector.*
   - B22 noemt een nummer dat het zelf afleidde ("25.2.10" voor "na artikel 25.2.9 een nieuw artikel"), en B12 spreekt
     zich tegen over onderdeel F. Dat zijn modelfouten. Er is geen generieke fix zonder meer metingen.
   - Een vervolgvraag over een genoemd stuk leest de code opnieuw vooraf, zonder de regeling uit de vraag (B26, B22).
     Het model leest daarna toch gericht verder. Het kost één lezing (geen modelronde).

## Wat deze ronde niet zegt

- Eén run per vraag, dus geen spreiding.
- Drie runs liepen tegelijk; de duur kan daardoor wat hoger zijn.
- De inhoud van de toelichtingen is niet zin voor zin tegen de bron gelegd. Feiten met een id, datum of nummer wel, waar
  hierboven genoemd. Niet nagetrokken: de percentages in B09 en de overgangszin in B24.
