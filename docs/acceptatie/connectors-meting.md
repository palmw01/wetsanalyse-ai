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

**Wat het meet.** Of Lex het geldingsbereik van een bepaling uit de officiële bekendmakingen haalt, en of de metadata van
KOOP (datum, soort, blad, ministerie, nummer, Kamerdossier, de regeling die een publicatie wijzigt) het antwoord draagt in
plaats van de tekst van het model. Alles met `bronnen: ["bekendmakingen"]`, op acceptatie, drie runs per vraag.

**De vragenset** staat in `tools/graph-qa/tests/data/bekendmakingen_vragenset.json` en wordt op drie plekken gebruikt:
de adaptertoets tegen opgenomen antwoorden van KOOP (`tests/test_bekendmakingen_vragenset.py`), de browsertoets
(`frontend/scripts/test-bronvenster-bekendmaking.mjs`) en deze meting. Per vraag de route (lijstvraag of genoemd stuk:
de code leest de vraag zelf, zonder model; model: de antwoordlus kiest), de tool met haar argumenten en wat een goed
antwoord is:

| # | Soort | Vraag | Route en tool | Goed antwoord |
|---|---|---|---|---|
| B01 | recentheid | Wat zijn de 10 meest recente publicaties? | lijstvraag: `zoek_bekendmakingen` `{"volgorde": "nieuwste", "aantal": 10}` | Een lijst (blok stukken) van tien publicaties, nieuwste eerst, met blad, soort en datum uit KOOP; uit de Staatscourant alleen regelgeving en beleid, geen aankondigingen over personen. |
| B02 | recentheid per soort | Geef de 5 nieuwste beleidsregels in de Staatscourant | lijstvraag: `zoek_bekendmakingen` `{"volgorde": "nieuwste", "aantal": 5, "soort": "beleidsregel", "publicatie": "Staatscourant"}` | Vijf beleidsregels uit de Staatscourant, nieuwste eerst, met datum en ministerie; de zoekvraag in woorden erboven. |
| B03 | per regeling | Welke wijzigingen van de Invorderingswet 1990 zijn er sinds 2024 gepubliceerd? | model: `zoek_bekendmakingen` `{"woorden": "Invorderingswet 1990", "vanaf": "2024", "volgorde": "nieuwste"}` | De publicaties met de Invorderingswet 1990 in de titel sinds 2024, nieuwste eerst, en de kanttekening dat een verzamelwet (een Belastingplan) de wet kan wijzigen zonder haar in de titel te noemen; eventueel aangevuld met zoek_bekendmakingen per bepaling. |
| B04 | inwerkingtreding | Wanneer trad artikel 36 van de Invorderingswet 1990 in werking en welk besluit regelde dat? | model: `zoek_bekendmakingen` `{"bwb_id": "BWBR0004770", "artikel": "36"}` | De huidige tekst van artikel 36 geldt sinds 4 juli 2010; de wijziging staat in Stb. 2009, 610, de inwerkingtreding in Stb. 2010, 176 – met de grens dat dit de toestand is die Lex leest. |
| B05 | beleid in de Staatscourant | Welke wijzigingen van de Leidraad Invordering 2008 zijn er recent in de Staatscourant gepubliceerd? | model: `zoek_bekendmakingen` `{"publicatie": "Staatscourant", "woorden": "Leidraad Invordering", "volgorde": "nieuwste", "aantal": 5}` | De nieuwste besluiten tot wijziging van de Leidraad Invordering 2008, met Stcrt. 2026, 37344 (30 oktober 2026) bovenaan. |
| B06 | één publicatie lezen | Wat staat er in Stb. 2010, 176? | genoemd stuk: `get_bekendmaking` `{"id": "stb-2010-176"}` | Het inwerkingtredingsbesluit, met letterlijke passages in het blok extern, de datum en het soort uit stuk, en welke regeling het in werking zet. |
| B07 | alleen een PDF | Wat staat er in stb-1990-222? | genoemd stuk: `get_bekendmaking` `{"id": "stb-1990-222"}` | Lex zegt dat Stb. 1990, 222 (de Invorderingswet 1990, 1990) bij KOOP alleen als PDF bestaat, geeft de link en citeert er niet uit. |
| B08 | wat veranderde aan één artikel | Wat veranderde stcrt-2026-37344 aan artikel 1.1.5 van de Leidraad Invordering 2008? | model: `get_bekendmaking` `{"id": "stcrt-2026-37344", "artikel": "1.1.5"}` | Alleen onderdeel A: twee gedachtestreepjes na het eerste in artikel 1.1.5 (bezwaarschriften tegen uitstel van betaling en tegen kwijtschelding), letterlijk geciteerd; 1.1.5b en 1.1.5c niet. |
| B09 | koppeling met Kamerstukken | Bij welk wetsvoorstel hoort Stb. 2013, 568? | genoemd stuk: `get_bekendmaking` `{"id": "stb-2013-568"}` | Het Kamerdossier 33755 (uit w.behandeldDossier), met het aanbod de memorie van toelichting te lezen als Kamerstukken aanstaat. |
| B10 | telling en filter | Hoeveel ministeriële regelingen van het Ministerie van Financiën staan er uit 2025 in de Staatscourant? | model: `zoek_bekendmakingen` `{"publicatie": "Staatscourant", "soort": "ministeriële regeling", "orgaan": "Ministerie van Financiën", "vanaf": "2025", "tot": "2025", "aantal": 5}` | Het aantal uit 'totaal' (KOOP telt), met de zoekvraag erbij; geen getal uit eigen kennis. |
| B11 | rectificatie | Welke verbeterbladen staan er in het Staatsblad van 2018? | model: `zoek_bekendmakingen` `{"publicatie": "Staatsblad", "soort": "verbeterblad", "jaar": "2018"}` | De verbeterbladen van 2018 met hun id (stb-2018-…-n1), en dat een verbeterblad een eerdere publicatie herstelt. |
| B12 | herdruk | Wat staat er in stb-2010-185-n1? | genoemd stuk: `get_bekendmaking` `{"id": "stb-2010-185-n1"}` | De herdruk, met het label en de versie (herdruk) uit KOOP. |
| B13 | niet bestaand nummer | Wat staat er in Stb. 2099, 1? | genoemd stuk: `get_bekendmaking` `{"id": "stb-2099-1"}` | Lex zegt dat Stb. 2099, 1 niet in de officiële publicaties staat, en verzint niets. |
| B14 | zonder treffers | Welke publicaties in de Staatscourant gaan over robotbelasting? | lijstvraag: `zoek_bekendmakingen` `{"publicatie": "Staatscourant", "tekst": "robotbelasting"}` | Een leemte met de zoekvraag in woorden: er is niets gevonden, en dat bewijst niet dat het niet bestaat. |
| B15 | buiten de bron | Wat zijn de nieuwste deurwaardersexploten in de Staatscourant? | model: `zoek_bekendmakingen` `{"publicatie": "Staatscourant", "soort": "deurwaardersexploot", "volgorde": "nieuwste"}` | Lex zegt dat aankondigingen over personen (deurwaardersexploten) buiten de bron vallen; geen namen. |
| B16 | welke regeling een publicatie wijzigt | Welke regelingen wijzigt Stb. 2009, 610? | genoemd stuk: `get_bekendmaking` `{"id": "stb-2009-610"}` | Volgens de BWB wijzigt Stb. 2009, 610 de Invorderingswet 1990 en de AWR (en zet een deel van de AWR in werking), met het aantal bepalingen – voor de toestand die Lex leest. |

**Vastgelegd per run:** route, toolaanroepen met argumenten (gelijk aan of afwijkend van de set), sjabloon, grounding
(niveau, `niet_letterlijk`), de ids in het blok `extern`/`stukken`, tokens (delta verbruik) en duur.

**Criteria (vooraf):**
- **Garanties, op 3/3:** geen run ongegrond; geen passage in `extern` die niet gelezen is; geen datum, soort of nummer
  die niet uit KOOP of de BWB komt; geen naam van een particulier (B15).
- **Slagen, op ≥ 2/3:** de lijstvragen en genoemde stukken (B01, B02, B06, B07, B09, B12, B13, B14, B16) zonder model naar
  de tool; B04 noemt beide publicaties met de goede rol; B08 citeert alleen onderdeel A; B10 noemt het `totaal`.
- **Trend:** B03 vermeldt de grens van de BWB-koppeling.

**Kosten:** 48 runs (16 vragen × 3). Een lijstvraag of genoemd stuk kost weinig (geen supervisor, één formulering); naar de
nulmeting van Kamerstukken ~20–60k tokens per run: samen ~1,5–2M tokens. Alleen na akkoord van de gebruiker. De uitkomst
komt in `../architectuur/metingen/bekendmakingen-2026-11-…`, met een regel in het meetlogboek.
