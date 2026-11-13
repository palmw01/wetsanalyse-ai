# Aanvulling bij ronde 3: E10 hangt aan de gegevens van de straat – 13 november 2026

- **Soort:** *meting*, aanvulling bij [`ronde-3.md`](ronde-3.md) en bij ronde 2. Zonder tokens: alleen de ruwe runs
  opnieuw gelezen. De meetbestanden van ronde 2 en 3 zijn niet gewijzigd.
- **Aanleiding:** in ronde 2 en 3 kost E10 ("Welke annotaties zijn er gemaakt bij artikel 36 van de Invorderingswet
  1990?") gewogen warm 12,4k tegen 7,3k in de nulmeting, bij dezelfde ruwe tokens. Ronde 3 schreef dat toe aan de
  cachestand van de specialist. Dat klopt niet.

## Wat er aan de hand is

- **Het voorvoegsel is niet veranderd.** In alle elf metingen van E10 (nulmeting, ronde 1, 2 en 3) heeft de
  specialist `annotaties_lezen` dezelfde `tools_hash` en `system_hash`, tien tools en dezelfde omvang van systeem en
  tools. A1 en A2-2 hebben hem niet geraakt.
- **De gegevens op acceptatie zijn veranderd.** De route in code doet vooraf één zoekopdracht: `search_annotaties` met
  alleen `limit: 25`, zonder de bepaling uit de vraag. Tot en met ronde 2, run 1 (12 november, 22:40 UTC) gaf die 0
  treffers; vanaf run 2 (22:44 UTC) geeft hij er 18. In die minuten annoteerde een andere sessie twee bepalingen op
  acceptatie (de annotatielagen zijn gedeeld). De meting zelf annoteert niet.
- **Het gevolg.** De beurt van het model groeit van 2,4k naar 16,2k tekens. Dat stuk gaat met de korte TTL de cache
  in: 6.253 tokens in de eerste aanroep, tegen 1.098 daarvoor. Het model doet het sindsdien in twee rondes in plaats
  van drie of vier, maar betaalt de 18 treffers. Het antwoord is gelijk gebleven: bij artikel 36 zelf zijn er geen
  annotaties.

| E10 | Treffers van de eerste zoekopdracht | Modelrondes | Cache geschreven, eerste aanroep | Gewogen warm |
|---|---|---|---|---|
| Nulmeting, drie runs | 0 | 3 / 4 / 3 | 9.925 (koud) / 1.098 / 1.098 | 7,3k / 9,7k / 7,1k |
| Ronde 2, run 1 | 0 | 3 | 1.098 | 7,2k |
| Ronde 2, run 2 en 3 | 18 | 2 / 2 | 6.253 / 6.253 | 12,4k / 12,4k |
| Ronde 3, drie runs | 18 | 2 / 2 / 2 | 15.080 (koud) / 6.253 / 6.253 | 12,4k / 12,2k / 12,5k |

## Wat dit betekent voor de drempel

De +70 % van E10 zegt niets over de centrale agent of over A2-2b: het is geen beurt van de centrale agent, en de
vergelijking met de nulmeting is voor deze opdracht niet meer zuiver. De mediaan over de tien enkelvoudige opdrachten
ligt precies tussen E07 en E10 en is er dus door vertekend.

Mediaan per opdracht, gewogen warm, over drie runs:

| Over welke opdrachten | Nulmeting | Ronde 2 | Ronde 3 |
|---|---|---|---|
| Alle tien (zoals in de verslagen) | 8,6k | 11,2k | 11,5k |
| Zonder E10 | 9,6k | 10,6k | 10,7k |
| De vijf die de centrale agent zelf doet (E03, E06, E07, E08, E09) | 32,3k | 35,3k | 27,5k |

- **Zonder E10** blijft de mediaan boven de nulmeting: hij is dan E07 zelf, de enkele definitie (+12 %).
- **Over de opdrachten van de centrale agent zelf** ligt de mediaan in ronde 3 onder de nulmeting (−15 %). De som per
  run over die vijf is 199k / 164k / 253k (nulmeting) tegen 136k / 160k / 154k.
- **Wat hierdoor niet verandert:** de afwijzing (E06) kost nog een factor 4,4 en de definitie (E07) 12 % meer dan bij
  de supervisor. De regel "geen opdracht meer dan 25 % duurder" is voor E06 niet gehaald.

## Afspraak voor de volgende rondes

Met de hoofdsessie afgesproken, op 13 november 2026:

- de drempel *niet duurder* wordt getoetst op de mediaan over de opdrachten die de centrale agent zelf doet;
- E10, E05 en de routes in code (E01, E02, E04) staan apart: ze lopen langs de centrale agent heen;
- het verslag vermeldt beide cijfers, met en zonder E10, en de reden.

## Een bevinding los van ADR-016

De eerste zoekopdracht van de leesroute neemt de bepaling uit de vraag niet mee. De vraag naar annotaties bij artikel 36
haalt eerst annotaties van andere bepalingen op; pas de tweede zoekopdracht, die het model doet, is op artikel 36
gericht. Hoe meer annotaties er op de straat staan, hoe duurder deze vraag wordt, tot de grens van 25 treffers.
