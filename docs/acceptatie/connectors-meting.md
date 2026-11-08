# Meting: Lex gebruikt de bronconnectors (ADR-013)

Soort: *meetplan* · Opgesteld: 8 november 2026 · Uitvoering: pas na akkoord van de gebruiker, via de hoofdsessie (de
meting kost tokens). De uitkomst komt als eigen map in [`../architectuur/metingen/`](../architectuur/metingen/README.md),
met een rij in het meetlogboek. Dit plan legt de vragen en de criteria **vooraf** vast, zodat de uitkomst niet achteraf
wordt uitgelegd.

## Waarom

Op acceptatie (8 nov 2026) kende alleen de toollaag de connectors:

- "wat kun je nog vinden in de kamerstukken?" kreeg de scope-weigering;
- de vraag naar de memorie van toelichting bij Kamerstuk 33755, nr. 3 (met `bronnen: ["kamerstukken"]`) kreeg zonder
  toolaanroep "maakt geen deel uit van de kennisgraaf".

De PR-reeks *connectors consequent* (PR 1–6) leidt scope, routering, prompt, tools, sjablonen, verificatie en werkplek
af uit één connectorbeschrijving (`packages/bronmodel/bronmodel/connectors.py`). Deze meting toetst of dat op acceptatie
werkt, vóór (huidige master) en na (de bundel met PR 1–6).

## Voorwaarden

- `CONNECTOR_KAMERSTUKKEN=true` op acceptatie (#1109, na een `azure-infra`-deploy door de gebruiker), en Kamerstukken
  aan in het register (`/v1/admin/connectors`).
- De acceptatie-MCP: `lex_start` geeft `extra` ongewijzigd door aan de beurt. De bronstand gaat dus mee als
  `extra: {"bronnen": [...], "bronnen_herkomst": "gesprek"}`. Wachten met `lex_wacht` (`vanaf=9999` voor alleen de
  afloop); tokens als delta van het verbruik (zie de werkwijze in het geheugen *Lex meten via acceptatie-MCP*).
- Elke vraag in een **nieuw gesprek**, zodat er geen geheugen meetelt.

## De vragen (vast, 8 stuks, elk drie runs)

| # | Vraag | `extra` | Verwacht na |
|---|---|---|---|
| 1 | wat kun je nog vinden in de kamerstukken? | `bronnen: ["kamerstukken"]` | niet afgewezen; zoekt in de Kamerstukken of legt uit wat er te vinden is |
| 2 | Wat staat er in de memorie van toelichting bij Kamerstuk 33755, nummer 3, over de aansprakelijkheid? | `bronnen: ["kamerstukken"]` | `zoek_kamerstukken`/`get_kamerstuk` aangeroepen; het blok `extern` (of `antwoord_extern`) met letterlijke passages van `kst-33755-3` |
| 3 | Welke Kamerstukken horen bij de Invorderingswet 1990? | `bronnen: ["kamerstukken"]` | `zoek_kamerstukken`; stukken met hun id |
| 4 | Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990? | `bronnen: ["kamerstukken"]` | wettekst uit de graaf én een blok `extern`, zichtbaar gescheiden |
| 5 | vraag 2 | `bronnen: [], bronnen_herkomst: "gesprek"` | melding zonder model: "Kamerstukken staat uit in dit gesprek…", knop *Zet Kamerstukken aan* |
| 6 | vraag 2, met Kamerstukken uit in het register | `bronnen: ["kamerstukken"]` | melding zonder model met reden `beheerder`; geen knop |
| 7 | Wat staat er in artikel 9 van de Invorderingswet 1990? | `bronnen: ["kamerstukken"]` | controle: route `bepaling_lezen`, tokens gelijk aan vóór (± de spreiding) |
| 8 | Wat voor weer wordt het morgen? | `bronnen: ["kamerstukken"]` | controle: blijft afgewezen |

Vraag 6 zet de connector even uit in het register en daarna weer aan, met een regel in het logboek; de audit van het
register laat het zien.

## Wat er per run wordt vastgelegd

- route (uit de `status`-regels), afgewezen ja/nee;
- de aanroepen van connectortools (`tool_execution`);
- de bronstand (`bronstand`-event) en, bij uit, het `bron_uit`-event met de reden;
- grounding: niveau, `niet_letterlijk`, `onbevestigd` (ook "alleen gevonden, niet gelezen");
- het sjabloon en de blokken (bestaat er een `extern`, met welk id en welke alinea's);
- de bronnenlijst: staat het Kamerstuk erin met brontype `kamerstuk`;
- tokens (delta verbruik) en duur.

## Criteria (vooraf)

- **Garanties, horen op 3/3:**
  - vraag 1–4 nooit afgewezen;
  - vraag 5 en 6 geen modelaanroep en de juiste reden;
  - vraag 8 afgewezen;
  - elk citaat uit een Kamerstuk letterlijk (`niet_letterlijk` leeg);
  - geen `extern`-blok zonder `get_kamerstuk` van dat id in de beurt.
- **Trend (gerapporteerd, geen slaagcriterium):**
  - vraag 2 en 4 met het blok `extern` (vs. vrije tekst);
  - het aantal rondes en de tokens van vraag 1–4;
  - vraag 7 binnen de spreiding van vóór.
- Faalt een garantie, dan is dat een bevinding met de opname erbij, geen reden om de vraag te wijzigen.
