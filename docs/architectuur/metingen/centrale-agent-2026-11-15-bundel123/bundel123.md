# ADR-016: controlemeting van D01, passages die de samenvatting dragen (bundel 123, 15 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `655ee98f` (bundel 123, #1531), `CENTRALE_AGENT=meten`. Daarin zit **#1530**:
  - een kopregel is geen passage;
  - als de aanwijzing de samenvatting niet draagt, kiest de code zelf passende alinea's;
  - de alineagrens gaat per stuk om de beurt, tot 10 stukken;
  - "niet samengevat" is geen duiding;
  - *Gedaan* en de bronpassages vallen buiten de duidingtoetsen.
- **Nulpunt:** D01 in de meting van #1528 op `31116955`
  ([`../centrale-agent-2026-11-14-bundel122/bundel122.md`](../centrale-agent-2026-11-14-bundel122/bundel122.md)): 653k.
- **Hoe gemeten:** dezelfde vraag en dezelfde drie antwoorden als bij bundel 118–122, in een lokale kopie van de set
  die niet in de repo staat. Het kind stelde drie vragen, dus alle drie de antwoorden zijn gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Totaal:** 628.127 tokens op het account; plafond 1M.

## Kort

| Punt | Uitkomst |
|---|---|
| 1. Kosten en correctierondes | **628k** (−4 % tegen 653k). Kind deel 1 268k (7 aanroepen), kind deel 2 295k (4), centrale agent 65k (2). **Eén correctieronde** in de centrale agent, de tweede aanroep (36k ruw). In de kinderen geen extra ronde: beide rapporten gingen in één keer |
| 2. Blijven de juiste samenvattingen staan? | **Niet te toetsen voor HR:2023:181, :563 en :176:** het kind las ze deze keer niet. **PHR:2024:936 blijft staan** en rust op echte passages (de samenvatting van de A-G, geen kopregels). **HR:2023:1371 blijft niet staan:** het rapport vatte hem juist en volledig samen, maar na de correctieronde zegt het eindantwoord dat "de inhoudelijke rechtsoverwegingen over de meldingsplicht (r.o. 3 e.v.) niet volledig gelezen" zijn. De passages die de code koos, zijn de eerste alinea's (r.o. 1–3.1: procedure en feiten), niet de alinea's die de samenvatting dragen (r.o. 3.3–3.8). Het kiezen door de code schoot dus tekort |
| 3. De controle per stuk | **Draaide niet** (0 tokens): de goedkopere toetsen vonden al iets. Er is geen aanroep met de rol `stukcontrole` |
| 4. Valse treffers | **"Niet samengevat" en *Gedaan* worden niet meer getroffen.** Wel staan er na de correctie nog vijf `onbevestigd` (`die de passages van dat stuk niet dragen`): bij HR:2023:1371 en PHR:2024:936, en bij drie zinnen die alleen zeggen dat niet vast te stellen is wat het gerecht overweegt (GHARL:2024:1513, GHAMS:2023:2936 en RBZWB:2024:6484). Die drie zijn vals. Bij PHR:2024:936 is het ook vals: de samenvatting staat letterlijk in de getoonde passages. **De zin "gedragen door de passages" staat er niet meer**, maar bij GHARL:2024:1513 en GHAMS:2023:2936 toont het antwoord nog kopregels als citaat ("Locatie Arnhem", "nummer ARN-BK 21/117", "uitspraakdatum: 27 februari 2024") |
| 5. Brongetrouw | Alleen gelezen stukken zijn samengevat, en wat er staat klopt. De periode is gevolgd: PHR:2025:435 noemt het antwoord alleen als "buiten de gevraagde periode". 30 van 30 citaten zijn letterlijk. Het antwoord bevat wel weinig: alleen PHR:2024:936 heeft inhoud, en die gaat over verjaring |
| 6. Doorgegeven, delegaties, meetvelden | **Gehaald, zoals bij bundel 122.** Het deelgesprek heeft opdracht en antwoorden als bericht van Lex (`doorgegeven: opdracht` en `doorgegeven: antwoorden`). `delegaties` staat op het kaartbericht en het eindbericht. `/v1/delegaties?gesprek_id=` geeft `klaar`, met `gelezen` (15 stukken), `periode` `[2022, 2024]` en nu ook `afbakening`. De meting: ouder `agentvorm: centraal`; kind `subagent: true`, `ouder_run_id` juist, model `claude-sonnet-4-6`. Geen geweigerde aanroepen |

**Wat naar T1/A1 gaat:**

1. **De juiste samenvatting van HR:2023:1371 haalt het eindantwoord niet.** Het rapport van deel 2 vat het arrest juist
   samen, en elk punt staat in de uitspraak:
   - het doel van de melding en de termijn van twee weken;
   - de bewijslast bij de ontvanger na een juiste melding (lid 3);
   - het vermoeden en de weerlegging bij niet melden (lid 4);
   - de gewezen bestuurder;
   - geen matiging;
   - de verworpen middelen;
   - de prejudiciële vragen;
   - en voor februari 2019 was belanghebbende gewezen bestuurder en slaagde hij in het bewijs.

   Het kind las het arrest in twee delen (vanaf alinea 0 en 23; de stroom zegt "deels gelezen"). De passages die het
   rapport en de code bij het stuk zetten, zijn de procedure en de feiten. De toets ziet dat de samenvatting daar niet
   op rust, en de centrale agent schrapt de inhoud in plaats van de dragende alinea's te tonen. Zo wordt een juiste
   samenvatting "niet volledig gelezen", wat voor de jurist minder waar is dan het rapport.
2. **De toets op dragende passages treft zinnen die niets duiden.** Bij GHARL:2024:1513, GHAMS:2023:2936 en
   RBZWB:2024:6484 zegt het eindantwoord alleen dat de gelezen alinea's geen oordeel over de melding bevatten. Toch
   blijven ze `onbevestigd`. Bij PHR:2024:936 staat de samenvatting woord voor woord in de getoonde passages en blijft
   hij ook `onbevestigd`.
3. **Kopregels als citaat bij twee hofuitspraken.** Na de correctie toont het antwoord bij GHARL:2024:1513 en
   GHAMS:2023:2936 alleen de kop van de uitspraak. Het rapport had bij die stukken wel inhoudelijke alinea's. In
   GHARL:2024:1513 komt "meld" 44 keer voor, dus daar valt wel iets over de melding te lezen.

## Brongetrouw

Vergeleken met de volledige tekst via de open data van de Rechtspraak.

| Uitspraak | Lex zegt | Volgens de tekst | Oordeel |
|---|---|---|---|
| HR:2023:1371 (eindantwoord) | de feiten, € 142.852; de Hoge Raad zet het nationale recht uiteen; de overwegingen over de melding "niet volledig gelezen" | r.o. 2.1–3.1 | **klopt**, maar de juiste inhoud uit het rapport is weggelaten |
| HR:2023:1371 (rapport deel 2) | lid 2–6, geen matiging, middelen, prejudiciële vragen; februari 2019 gewezen bestuurder en geslaagd in het bewijs | r.o. 3.3–3.8, 4.x ("Belanghebbende is volgens het Hof geslaagd in het leveren van dit bewijs") | **klopt** |
| PHR:2024:936 | geen eigen verjaringstermijn; het zorgvuldigheidsbeginsel bij ambtshalve uitstel; niet over de melding | de samenvatting van de A-G | **klopt** |
| GHARL:2024:1513, GHAMS:2023:2936, RBZWB:2024:6484 | alleen de kop gelezen, geen oordeel vast te stellen | in GHARL:2024:1513 komt "meld" 44 keer voor | **eerlijk**, maar dun |

## Per beurt

| Beurt | Wat | Account | Centrale agent | Kind |
|---|---|---|---|---|
| 0 | opdracht → kaart 1 (periode) | 267.541 | 0 modelrondes | deel 1: 7 aanroepen, 14 tools (12× `get_uitspraak`), 268k ruw / 94,2k gewogen warm, `vraag` (3 vragen), begint op 22k |
| 1 | antwoord 1 → kaart 2 (instanties) | 0 | 0 | — |
| 2 | antwoord 2 → kaart 3 (aspect) | 0 | 0 | — |
| 3 | antwoord 3 → hervatten, eindantwoord | 360.586 | 2 modelrondes: 29k en 36k (correctie); 65k ruw / 38,2k gewogen warm | deel 2: 4 aanroepen, 7 tools (6× `get_uitspraak`), 295k ruw / 124,9k gewogen warm, `klaar` met rapport, afbakening `tekst: huidige tekst`, begint op 63k |

## Open punten

- De controle per stuk is in drie metingen niet gelopen. Zolang de goedkopere toetsen in D01 steeds iets vinden, meet
  D01 haar niet.
- HR:2023:181, :563 en :176 las het kind deze keer niet, dus of hun samenvattingen nu blijven staan, is niet gemeten.

## Bestanden

- `b123-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`), met de status en de stukken van beide
  rapporten.
- `b123-kinderen.jsonl`: de twee delen van de kindrun (ouder-run, agentvorm, aanroepen, modellen, ruw, gewogen,
  beginnende context, sjabloon, tools), zonder tekst.
