# Aanvulling bij ronde 3: de kwaliteitsset met de centrale agent – 13 november 2026

- **Soort:** *meting*, het sluitstuk van [`ronde-3.md`](ronde-3.md). Besluit van de gebruiker (13 november 2026): de
  kwaliteitsset erbij.
- **Code:** master `20d17a92` (bundel 88; het gedrag is gelijk aan `171c38f4`, alleen `eval` en docs), `CENTRALE_AGENT=meten`.
- **Wat er gemeten is:** de 22 vragen van `eval/golden.jsonl`, één keer met `agentvorm: "centraal"` (A2-2b: de kernset
  met de overdracht `meer_tools`), gescoord met de scorers van de set. Als controle vijf vragen zonder het veld.
- **Vergelijking:** de kwaliteitsset van [ronde 2](../centrale-agent-2026-11-12-r2/ronde-2.md) op `06556097`, beide
  vormen, één run elk.
- **Gegevens:** [`ronde-3-kwaliteitsset.jsonl`](ronde-3-kwaliteitsset.jsonl). De meetbestanden van ronde 2 en 3 zijn
  niet gewijzigd.

## Uitkomst

| | Supervisor, ronde 2 | Centraal, ronde 2 | Centraal, nu (A2-2b) |
|---|---|---|---|
| Geslaagd | 18 / 22 | 19 / 22 | 19 / 22 |
| Ruw | 2,43M | 2,75M | 2,07M |
| Gewogen warm | 599k | 608k | 551k |
| Modelrondes | 118 | 110 | 101 |
| Mediaan per vraag, gewogen warm | 14,9k | 12,8k | 11,0k |
| Mediaan duur | 19,8 s | 15,2 s | 13,7 s |

- **Niet slechter, en goedkoper dan beide vormen in ronde 2:** ruw −25 % tegen de centrale agent van ronde 2 en −15 %
  tegen de supervisor; gewogen warm −9 % en −8 %. Eén run per vorm: de som is een aanwijzing, een enkele vraag niet.
- **De overdracht viel drie keer, en elke keer terecht:** K13 (wie verwijst naar artikel 36: `verwijst_naar_deze`), K15
  (op welke grondslag berust de Leidraad: `grondslagen`) en K17 (sinds wanneer geldt de huidige tekst:
  `geldigheid`). Elf van de 126 toolaanroepen kwamen uit de brede toolset; in ronde 2 vielen er 17 van de 141 buiten
  wat nu de kernset is. Vragen als "Wie heeft de Invorderingswet 1990 ondertekend?" lopen zonder overdracht, nu
  `get_regeling_info` in de kernset zit.
- **Geen tool buiten het profiel**, in geen van de 22 beurten.
- **Tools naast elkaar:** 72 modelrondes met tools, 32 met meer dan één; 122 aanroepen, 1,7 per ronde.
- **Brongetrouw:** 59 citaten in tien antwoorden, alle letterlijk in de officiële tekst. Geen run ongegrond; 13 keer
  *gegrond*, 8 keer *onbepaald*.
- **Koud:** de eerste beurt na de uitrol schreef geen uurvoorvoegsel; in de hele run van de centrale agent is er geen
  geschreven. In de controle zonder het veld wel één keer (K17, 13,7k tokens).

## Per vraag

Per cel: supervisor ronde 2 / centraal ronde 2 / centraal nu.

| Vraag | Begin van de vraag | Geslaagd, supervisor r2 | Geslaagd, centraal r2 | Geslaagd, nu | Rondes | Ruw | Gewogen warm | Overdracht |
|---|---|---|---|---|---|---|---|---|
| K01 | Wat zijn de invorderingstermijnen bij belastingen? | ja | ja | ja | 8 / 11 / 8 | 185,5k / 316,4k / 156,1k | 53,3k / 76,9k / 41,3k |  |
| K02 | Welke regelingen zitten er in de kennisgraaf? | ja | ja | ja | 3 / 2 / 2 | 36,9k / 35,7k / 26,7k | 7,2k / 6,4k / 5,5k |  |
| K03 | Binnen welke termijn is een naheffingsaanslag invord | nee (contains) | nee (contains) | nee (contains) | 6 / 5 / 5 | 75,2k / 113,0k / 90,7k | 25,8k / 30,1k / 28,3k |  |
| K04 | Welke soort regeling is de Leidraad Invordering 2008 | nee (bronnen) | ja | ja | 7 / 3 / 3 | 77,4k / 53,4k / 39,9k | 17,2k / 8,3k / 6,7k |  |
| K05 | Wie heeft de Invorderingswet 1990 ondertekend? | ja | ja | ja | 4 / 3 / 3 | 54,6k / 53,8k / 40,5k | 9,8k / 9,1k / 7,2k |  |
| K06 | Wat is het weer vandaag? | ja | ja | ja | 1 / 1 / 1 | 2,3k / 17,5k / 13,0k | 504 / 2,7k / 2,3k |  |
| K07 | Wat geldt er als iemand zijn belasting niet op tijd  | ja | ja | ja | 6 / 12 / 8 | 109,9k / 288,5k / 146,4k | 28,8k / 64,9k / 40,8k |  |
| K08 | Kan de ontvanger een betalingsregeling weigeren? | ja | ja | ja | 20 / 21 / 9 | 812,5k / 756,0k / 223,1k | 156,8k / 149,7k / 66,6k |  |
| K09 | Wat is een belastingschuldige en binnen welke termij | nee (contains) | nee (contains) | nee (contains) | 5 / 6 / 4 | 59,4k / 140,2k / 67,9k | 21,9k / 38,6k / 23,2k |  |
| K10 | Welke soort regeling is de Leidraad Invordering 2008 | nee (bronnen) | nee (bronnen) | ja | 5 / 7 / 4 | 51,7k / 141,3k / 55,9k | 15,1k / 27,0k / 11,8k |  |
| K11 | alles over aansprakelijkheid van de bestuurder | ja | ja | ja | 9 / 13 / 14 | 197,1k / 341,9k / 403,1k | 61,2k / 80,3k / 138,2k |  |
| K12 | wat is bekend over het milieu in de milieuwet? | ja | ja | nee (refusal) | 3 / 3 / 2 | 37,2k / 53,4k / 26,4k | 8,0k / 8,7k / 5,1k |  |
| K13 | Welke bepalingen verwijzen naar artikel 36 van de In | ja | ja | ja | 6 / 4 / 5 | 107,6k / 82,6k / 96,8k | 33,1k / 23,5k / 25,8k | ja |
| K14 | Waar definieert de Invorderingswet 1990 het begrip b | ja | ja | ja | 3 / 2 / 2 | 22,9k / 35,4k / 26,5k | 4,9k / 5,7k / 4,9k |  |
| K15 | Op welke wettelijke grondslag berust de Leidraad Inv | ja | ja | ja | 11 / 6 / 18 | 209,1k / 116,1k / 445,3k | 64,5k / 23,2k / 87,4k | ja |
| K16 | Welke hoofdstukken heeft de Invorderingswet 1990? | ja | ja | ja | 4 / 3 / 3 | 55,8k / 55,1k / 42,1k | 12,1k / 11,3k / 10,2k |  |
| K17 | Sinds wanneer geldt de huidige tekst van artikel 36  | ja | ja | ja | 12 / 4 / 6 | 272,6k / 91,4k / 125,5k | 62,5k / 25,9k / 31,9k | ja |
| K18 | Welke hoofdstukken heeft de Invorderingswet 1990 en  | ja | ja | ja | 4 / 3 / 3 | 56,4k / 56,1k / 42,6k | 14,6k / 14,3k / 12,6k |  |
| K19 | Welke artikelen gaan over invordering? | ja | ja | ja | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |  |
| K20 | Welke bepalingen gaan over kwijtschelding? | ja | ja | ja | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |  |
| K21 | Waar is de invordering geregeld in de Awb? | ja | ja | ja | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |  |
| K22 | Wat staat er in artikel 22, derde lid, van de Invord | ja | ja | ja | 1 / 1 / 1 | 937 / 945 / 950 | 1,6k / 1,7k / 1,7k |  |

- **K03 en K09** falen in alle drie op de tekst "14 dagen": het antwoord zegt "veertien dagen", zoals de wet. De
  verwachting in de set is te letterlijk; het antwoord is juist.
- **K12** ("wat is bekend over het milieu in de milieuwet?") faalt nu, en slaagde in ronde 2. De scorer leest een
  antwoord zonder bronnen als een weigering. De centrale agent zoekt één keer, zegt dat er geen regeling met die naam
  in de graaf staat, en somt de regelingen niet meer op uit de graaf. Hij noemt daarbij "de Belastingwet" als
  voorbeeld: een regeling die niet bestaat. Geen citaat en geen bron, wel een naam uit eigen kennis.
- **K10** slaagt nu (in ronde 2 ontbrak de Leidraad in de bronnenlijst); **K04** bleef goed.
- **K15 is duur geworden:** 445k ruw en 18 rondes, tegen 116k en 6 rondes in ronde 2. Na de overdracht roept hij
  `grondslagen` drie keer aan, afgewisseld met zoeken en lezen, en het sjabloon weigert twee keer
  (`genoemd_gelezen`). Hetzelfde patroon als B02 in ronde 3: de grondslagenvraag vindt haar antwoord niet in één keer.
- **K11** ("alles over aansprakelijkheid van de bestuurder") kost 403k en 14 rondes, tegen 342k en 13 in ronde 2:
  een brede vraag waarbij hij veel leest, wel met meer tools per ronde.
- **De winst zit in de lange vragen:** K08 756k → 223k ruw (21 → 9 rondes), K01 316k → 156k, K07 289k → 146k.
- **De afwijzing (K06)** kost 13,0k ruw en 2,3k gewogen warm, tegen 2,3k en 0,5k bij de supervisor: hetzelfde beeld
  als E06 in de agentset.

## De controle op de supervisorweg

De supervisorweg is sinds ronde 2 gewijzigd (de doorvraagroute en de vindplaatsfix). Vijf vragen zonder het veld, één
keer, tegen dezelfde vragen in ronde 2:

| Vraag | Geslaagd, ronde 2 | Geslaagd, nu | Rondes | Ruw | Gewogen warm |
|---|---|---|---|---|---|
| K04 | nee (bronnen) | ja | 7 → 8 | 77,4k → 96,5k | 17,2k → 25,5k |
| K05 | ja | ja | 4 → 4 | 54,6k → 54,4k | 9,8k → 9,7k |
| K10 | nee (bronnen) | nee (refusal, bronnen) | 5 → 5 | 51,7k → 52,5k | 15,1k → 15,4k |
| K13 | ja | ja | 6 → 5 | 107,6k → 82,3k | 33,1k → 23,8k |
| K17 | ja | ja | 12 → 16 | 272,6k → 416,1k | 62,5k → 85,7k |

- **K04 slaagt nu:** de ongeldige vindplaats is weg en de Leidraad staat in de bronnenlijst. In de controle van
  ronde 3 op `171c38f4` droeg dezelfde vraag alleen de Awb als bron; één run per keer.
- **K10 faalt nog:** het antwoord is juist, maar de bronnenlijst is leeg, en de scorer leest dat als een weigering.
- **K17 is duurder:** 416k tegen 273k, 16 rondes tegen 12. Na `geldigheid` gaat de specialist over op `raw_sparql`.
  Spreiding of een gevolg van de wijzigingen: op één run niet te zeggen.
- **K05 en K13** zijn gelijk gebleven.
- Er is geen verschil dat om de hele set in de vorm zonder het veld vraagt. De bronnenlijst bij vragen over de soort
  regeling blijft wisselen; dat staat los van de centrale agent.

## Verbruik

Uit de `meting`-events; gelijk aan het verschil in de accountstand (5.940.704 → 8.711.709).

| Onderdeel | Ruw |
|---|---|
| De kwaliteitsset, centraal | 2.069.237 |
| De controle, vijf vragen zonder het veld | 701.768 |
| **Samen** | **2.771.005** |

Met deze aanvulling kost ronde 3 in totaal 8.711.709 tokens.

## Wat dit toevoegt aan ronde 3

- Op de kwaliteitsset is de centrale agent na A2-2b niet slechter en goedkoper dan de supervisor, ook in de mediaan
  per vraag. Dat beeld is gunstiger dan de tien enkelvoudige opdrachten van de agentset lieten zien.
- Het risico waarvoor de set erbij kwam, doet zich niet voor: de overdracht valt waar ze moet, en geen vraag strandt
  op een tool die de kernset mist.
- Twee dingen blijven staan uit ronde 3: de afwijzing kost het voorvoegsel, en de grondslagenvraag loopt uit de hand.
- Nieuw: bij K12 noemt de centrale agent een regeling die niet bestaat, in een antwoord zonder bronnen.
