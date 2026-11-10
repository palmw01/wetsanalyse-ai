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
- grounding: niveau, `niet_letterlijk`, `onbevestigd` (een stuk dat alleen gevonden is, telt sinds 10 nov 2026 niet
  meer als onbevestigd; de logregel `alleen gevonden genoemd` telt het);
- het sjabloon en de blokken (bestaat er een `extern`, met welk id en welke alinea's; staat een lijst gevonden stukken
  in het blok `stukken` of in lopende tekst);
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

## Lezen in een stuk (vervolg, 8 nov 2026)

Run `d35fb681` (bundel 20) las kst-33755-3 in twee pagina's en stopte. Het contract zei terecht `volledig: false`. Wat
er sindsdien veranderde:
- de eigen inhoudsopgave en de tabelcellen zijn geen alinea's meer;
- een tussenkop noemt het artikel;
- de eerste pagina draagt `inhoud`, met per kop de offset (#1132);
- voetnoten zijn rijen met hun verwijzing (#1135);
- een tabel opent met `tabel=` (#1137) en verschijnt als tabel in het antwoord (#1138).

Deze meting toetst of Lex daardoor gericht leest. Zelfde voorwaarden en werkwijze als hierboven:
- `extra: {"bronnen": ["kamerstukken"], "bronnen_herkomst": "gesprek"}`;
- elke vraag in een nieuw gesprek;
- drie runs per vraag.

**Wanneer:**
- **vóór**: op acceptatie met bundel 21 (#1132 erin, #1135–#1138 niet);
- **na**: met de bundel die #1135–#1138 bevat;
- **alleen na akkoord van de gebruiker**.

| # | Vraag | Verwacht na | Vóór? |
|---|---|---|---|
| L1 | Wat is volgens de memorie van toelichting bij Kamerstuk 33755, nr. 3 het doel van het voorstel? | 1 aanroep van `get_kamerstuk`; passages uit "1. Inleiding" | ja |
| L2 | Wat zegt de memorie van toelichting bij Kamerstuk 33755, nr. 3 over artikel 29 van de Invorderingswet 1990? | een sprong met een `offset` uit `inhoud`; een passage met kop "… Artikel II (artikel 29 van de Invorderingswet 1990)"; ≤ 2 aanroepen | ja |
| L3 | Wat is volgens Kamerstuk 33755, nr. 3 de budgettaire opbrengst per jaar? | de tabel geopend (`tabel=`); de cijfers uit een tabelrij in het blok `extern` | nee: kon niet |
| L4 | Naar welk stuk verwijst Kamerstuk 33755, nr. 3 voor het regeerakkoord? | de voetnoot gelezen; `kst-33410-15` genoemd | nee: kon niet |
| L5 | Wat staat er in Kamerstuk 36200-IX, nr. 2 over de Belastingdienst? | een sprong via `inhoud`; ≤ 3 aanroepen; een passage waarvan de kop de Belastingdienst noemt | ja |

**Vastgelegd per run:**
- het aantal aanroepen van `get_kamerstuk`, en hun `offset` en `tabel`;
- **gesprongen**: de eerste `offset` die niet het `vervolg` van de vorige pagina is;
- of er een tabel is geopend en een voetnoot is gelezen;
- de koppen van de passages in het blok `extern`;
- de grounding (niveau, `niet_letterlijk`);
- het sjabloon;
- tokens (delta verbruik) en duur.

**Criteria (vooraf):**
- **Garanties, op 3/3:**
  - geen run ongegrond;
  - geen passage in het blok `extern` die niet in een gelezen pagina staat;
  - een cijfer uit een tabel komt uit een gelezen tabelrij.
- **Slagen, op ≥ 2/3:**
  - L2 en L5 springen, met minder aanroepen dan vóór;
  - L3 opent de tabel;
  - L4 noemt `kst-33410-15`.
- **Trend:** L1 kost niet meer tokens dan vóór (± de spreiding van drie runs).

**Kosten:**
- 24 runs: L1, L2 en L5 vóór en na (3 vragen × 3 runs × 2 = 18), plus L3 en L4 alleen na (2 × 3 = 6).
- Run `d35fb681` kostte ~60k tokens, cache meegeteld. Samen ~1,4M tokens.

De uitkomst komt in `../architectuur/metingen/kamerstuk-lezen-2026-11-…`, met een regel in het meetlogboek. Faalt een
garantie, dan is dat een bevinding met de opname erbij, geen reden om de vraag te wijzigen.

## Staatsblad en Staatscourant (derde connector, 10 nov 2026)

**Wat het meet.** Of Lex het geldingsbereik van een bepaling uit de officiële bekendmakingen haalt: de publicatie die
haar huidige tekst gaf, het besluit waarmee die in werking trad, en wat een wijzigingsbesluit aan één artikel
veranderde. Alles met `bronnen: ["bekendmakingen"]`, op acceptatie, drie runs per vraag.

| # | Vraag | Verwacht na |
|---|---|---|
| B1 | Sinds wanneer geldt artikel 36 van de Invorderingswet 1990 in deze vorm, en waar staat dat? | `zoek_bekendmakingen` met `bwb_id` + `artikel` (of `geldigheid`); Stb. 2009, 610 als laatste wijziging en Stb. 2010, 176 als inwerkingtreding, met de datum uit de BWB |
| B2 | Wat staat er in Stb. 2010, 176? | route `bron_lezen` (citeervorm), zonder supervisorcall; een blok `extern` met letterlijke passages |
| B3 | Welke wijzigingen van de Leidraad Invordering 2008 staan sinds 2024 in de Staatscourant? | één zoekaanroep met `publicatie` en `vanaf`; het blok `stukken` met ids uit het zoekresultaat |
| B4 | Wat veranderde stcrt-2026-37344 aan artikel 1.1.5 van de Leidraad Invordering 2008? | `get_bekendmaking` met `artikel: "1.1.5"`; alleen onderdeel A in het blok `extern` |

**Vastgelegd per run:** route, toolaanroepen met argumenten, sjabloon, grounding (niveau, `niet_letterlijk`), de ids in
het blok `extern`/`stukken`, tokens (delta verbruik) en duur.

**Criteria (vooraf):**
- **Garanties, op 3/3:** geen run ongegrond; geen passage in `extern` die niet gelezen is; geen datum van inwerkingtreding
  die niet uit de BWB of de gelezen tekst komt.
- **Slagen, op ≥ 2/3:** B1 noemt beide publicaties met de goede rol; B2 leest vooraf; B4 citeert alleen onderdeel A.

**Kosten:** 12 runs, naar de nulmeting van Kamerstukken ~40–60k tokens per run: samen ~0,6M tokens. Alleen na akkoord
van de gebruiker. De uitkomst komt in `../architectuur/metingen/bekendmakingen-2026-11-…`, met een regel in het
meetlogboek.
