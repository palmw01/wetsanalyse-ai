# ADR-016 A6: de eindmeting (run 1–3, 15 nov 2026)

Soort: *meting* (ADR-016 §A6), met akkoord van de gebruiker. Dit verslag maakt de eindmeting af. Het bundelt run 3 deel 1
en deel 2 tot één volledige run van de agentset en de kwaliteitsset, en legt die naast M0, run 1 en run 2. Daarna volgt
het oordeel per drempel.

- **Run 3 deel 1:** E01–S05, P01–P03, M01–M06, V01 en V02. Gedraaid op `346a7e28` (bundel 126), plafond 5M,
  4,75M gebruikt. Het verslag staat in [`../centrale-agent-2026-11-15-a6-run3/a6-run3.md`](../centrale-agent-2026-11-15-a6-run3/a6-run3.md);
  de meetbestanden daar blijven ongewijzigd.
- **Run 3 deel 2 (dit verslag):** gedraaid op `022506a3` (bundel 127, #1551, met de fixes van #1549), plafond 6M,
  4,21M gebruikt. De inhoud:
  - V03, V04 en F01–F05: de opdrachten die in deel 1 buiten het plafond vielen;
  - S04 opnieuw, om de fix voor de regressie uit deel 1 te toetsen;
  - de kwaliteitsset K01–K22, één keer, in de vorm `centraal`.
- **Instellingen:** `CENTRALE_AGENT=meten`, alle beurten met `agentvorm: centraal`. Het model is `claude-sonnet-4-6`,
  ook in de kinderen: de straat heeft geen licht model.
- **Nulpunt:**
  - M0 op `808c908e` ([`../centrale-agent-2026-11-12-r0/ronde-0.md`](../centrale-agent-2026-11-12-r0/ronde-0.md)), drie runs;
  - run 1 ([`../centrale-agent-2026-11-15-a6/a6.md`](../centrale-agent-2026-11-15-a6/a6.md)) en run 2
    ([`../centrale-agent-2026-11-15-a6-run2/a6-run2.md`](../centrale-agent-2026-11-15-a6-run2/a6-run2.md));
  - voor de kwaliteitsset: ronde 4, de vorm centraal, op `43ff91a0`
    ([`../centrale-agent-2026-11-13-r4/ronde-4.md`](../centrale-agent-2026-11-13-r4/ronde-4.md)). M0 had geen
    kwaliteitsset.
- **Hoe gemeten:** met het meetscript `eval/centrale_agent_meting.mjs`, zoals in run 2. De kwaliteitsset gaat via
  `vragen kwaliteit` en is gescoord met `score_case` uit `eval/scoring.py`. De bewaking:
  - vóór elke opdracht leest de keten het verbruik van het account;
  - een wachter stopt alles boven 5,95M;
  - er kwam geen `BUDGET_OP`, en de wachter hoefde niet in te grijpen.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen, voor 0 tokens. De graaf was gevuld.
- **Totaal deel 2:** 4.211.592 tokens; het budget was gereset om 14:55 UTC. Daarvan gingen 2,27M naar de agentset en
  1,94M naar de kwaliteitsset.

## Oordeel: A6 haalt de drempels, op één na

| Meetpunt (§A6) | Drempel | Run 3 (deel 1 + 2) | Run 2 | Run 1 | M0 | Oordeel |
|---|---|---|---|---|---|---|
| Gewone vragen niet duurder | mediaan gewogen ≤ M0, op de vijf opdrachten die de centrale agent zelf doet; duur ≤ M0 | **30,6k** gewogen warm; duur over E01–E10 **9,1 s** | 34,4k | 36k | 32,3k; 14 s | **gehaald** |
| Juiste delegatie | ≥ 27/30 | **29/30** (alleen S02) | 28/30 | 19/26 | 16/26 | **gehaald** |
| Juiste profielkeuze | ≥ 13/15 | **19/19** kinderen | 8/8 | 2/2 | – | **gehaald** |
| Brongetrouw en gegrond | geen onjuiste bron of verzonnen citaat | **355 van 356** citaten letterlijk; het ene is de vorige tekst (V04, verklaard). Geen onjuiste bron | 110/112 | 95/97 | 551/551 | **gehaald** |
| Inhoud, enkelvoudig | niet slechter dan M0 | **10/10** | 10/10 | 10/10 | 10/10 | **gehaald** |
| Inhoud, samengesteld (20) | beter dan M0 | **13 goed, 4 deels, 3 fout** | 12/4/2 op 18 | 10/4/2 op 16 | run 1 op 18: 8/3/7 | **gehaald** |
| Vragen naar boven | 4/4, geen subagent die gokt | **2/4** (V01, V02) | 1/4 | 1/4 | 0/4 | **niet gehaald** |
| Grote opdracht in één keer | plan, eerste fase af, bundel, volgende fase na één klik | M02–M05 zoals in run 2; M01, M06 en P01–P03 uitgevoerd | M01/M06 alleen het plan | | M04 fout | **gehaald** |
| Kosten van delegatie | binnen het plafond | geen kind boven 300k; duurste opdracht M06 827k (M0 tot 826k) | | | | **gehaald** |
| Regressie | geen case van goed naar fout zonder verklaring | kwaliteitsset **20/22** tegen 18/22 in ronde 4; geen case van goed naar fout | | | | **gehaald** |

**Mijn oordeel.** Op negen van de tien meetpunten haalt A6 de drempel. Alleen *vragen naar boven* haalt hem niet: V03
leverde geen vraag op en V04 gokt. De drempel "over drie runs" is te lezen als de lijn run 1 → 2 → 3:
- delegatie: 19/26 → 28/30 → 29/30;
- vragen naar boven: 1/4 → 1/4 → 2/4.

De drempels die gehaald zijn, zijn in run 2 en 3 allebei gehaald. Run 1 was onvolledig. Volgens de ADR besluit A7 of
dat genoeg is.

Twee voorbehouden:
- de routeringsset is niet gemeten;
- samengesteld op dezelfde 18 opdrachten als run 2 is run 3 niet beter (11/4/3 tegen 12/4/2), wel duidelijk beter dan
  M0 (8/3/7).

## De samengestelde opdrachten

Run 3 telt S04 uit deel 2: daar zit de fix voor de regressie in. Deel 1 gaf S04 als fout.

| Opdracht | Run 3 | Account | Run 2 | M0 (r1 / r2 / r3) | Toelichting |
|---|---|---|---|---|---|
| S01 | deels | 373k | deels, 352k | 280 / 453 / 611k | goede samenvattingen, geen citaat (deel 1) |
| S02 | goed | 27k | goed | 26k | gaat in code, zonder subagent (zie run 2) |
| S03 | goed | 198k | goed | 66–83k | nu met 19 citaten |
| S04 | **deels** (deel 1: fout) | 229k | goed | 186–428k | het rapport komt nu door, zie hieronder |
| S05 | goed | 227k | deels | 204–439k | |
| M01 | goed | 498k | plan | 361–487k | uitgevoerd, 3 × `duiding` |
| M02–M05 | goed | 0–18k | goed | 0–5k | regie in code |
| M06 | goed | 827k | plan | 160–826k | uitgevoerd, 3 × `algemeen` |
| V01 | goed | 46k | goed | 323–417k | vraagt welke regeling |
| V02 | goed | 0 | fout | 0 | vraagt de jurist (fix #1539) |
| V03 | **fout** | 351k | goed, 690k | 0 | zie hieronder |
| V04 | deels | 193k | deels | 147–245k | kiest zelf de wijziging en zegt dat |
| F01 | goed | 572k | goed | 30–98k | zie hieronder |
| F02 | **fout** | 121k | deels | 5–139k | stelt een nieuwe keuzevraag |
| F03 | fout | 190k | fout | 18–20k | leest de stand, maar zegt iets onjuists |
| F04 | goed | 509k | goed | 6–426k | lease via de Leidraad 22.9.2, niets verzonnen |
| F05 | **deels** | 107k | goed | 122–168k | de onderdelen 24.1–24.6 goed, maar zonder citaat |

Daarnaast P01–P03 (deel 1): P01 deels, P02 en P03 goed. Die hebben geen nulpunt.

- **S04 (deels).** Het rapport van het kind haalt het eindantwoord nu wel: de kern per onderdeel 22.1–22.8.8, met 17
  letterlijke citaten. Lex zegt zelf dat 22.8.9–22.8.12 en 22.9.x niet gelezen zijn ("alleen bekend uit de
  inhoudsopgave"). Dat is eerlijk, maar de set vraagt elk onderdeel gelezen. De regressie is weg.
- **V03 (fout).** Het proces gaat zoals de fix bedoelt:
  - één kind `algemeen`, zonder kaart voor de jurist;
  - de centrale agent blijft op 114k, en het kind stopt op 237k;
  - er zijn geen 17 keer `get_kamerstuk` meer, zoals in run 2.

  Maar het kind las geen memorie van toelichting. Het vond kst-36369-3, kst-36207-3 en kst-36309-3, maar las ze niet
  "wegens rondegrens", en zijn rapport gaat over de wettekst. Het antwoord zegt dat eerlijk en vat niets samen. Ook
  vroeg het kind de centrale agent niets, terwijl de set daar een vraag naar boven verwacht. `stukken_plafond` werd
  niet geraakt, omdat de centrale agent zelf geen stuk las. Run 2 gaf wel inhoud, maar voor 690k.
- **F01 (goed).** De opzet (S01) loopt nu bij de centrale agent met één kind (284k). De vervolgvraag gaat over dezelfde
  uitspraak als de eerste in het overzicht, HR:2023:1371. Lex geeft de bewijslast met r.o. 3.4, 5.2.2 en 5.6.2–5.6.5,
  met zes letterlijke passages. Hij zoekt niet opnieuw (drie tools).
- **F02 (fout).** Op "De Invorderingswet 1990" meldt Lex dat er 243 uitspraken zijn. Hij stelt voor alleen de Hoge Raad
  en het Parket te lezen, en vraagt opnieuw of dat goed is. De set zegt: geen nieuwe keuzevraag.
- **F03 (fout).** De vervolgvraag kost nog maar 36k, en Lex start niets opnieuw. Maar hij zegt dat er "later gewijzigde
  deelgesprekken voor elk van de drie deelvragen" zijn, terwijl er alleen in deelvraag 1 is doorgevraagd.
  `delegatie_stand` wordt niet aangeroepen.
- **F05 (deels).** De Leidraad 24.1–24.6 is goed samengevat, maar zonder één citaat. De set vraagt een letterlijke
  passage.

## Wat de fixes deden (#1539 en #1549)

| Fix | Uitkomst |
|---|---|
| V02: vraag aan de jurist | **Gehaald** (deel 1). |
| V03: één subagent `algemeen`, met `stukken_plafond` | **Het proces is gehaald:** één kind, en de centrale agent blijft binnen de grens (351k tegen 690k). **De inhoud niet:** het kind las geen MvT. |
| S04: het rapport haalt het antwoord | **Gehaald.** |
| De controle per stuk markeert alleen een tegenspraak als het zinsdeel zelf iets weerspreekt | Zie hieronder. |
| Het jaartal telt niet als aantal gelezen stukken | **Gehaald bij F01:** geen "1990 uitspraken gelezen" meer. Maar het rapport van het kind bij V03 heeft nog `onbevestigd` op getallen: "1988", "33004" en "dossier 20588 in 1994-1995". |
| `na_subagent` en de rapportcitaten | **Gehaald** (deel 1: 0 geweigerde aanroepen; S03 en S04 met citaten). |
| E03: BW art. 3:239 | **Gehaald** (deel 1). |

### De controle per stuk, over de hele run 3

- **Deel 1, nog met de oude regel:** vier meldingen `tegenspreekt`. Eén is terecht (kst-36151-3), drie zijn vals
  (HR:2023:1371, HR:2026:586, kst-26728-3).
- **Deel 2, met de nieuwe regel:** de controle draaide één keer, bij de opzet van F01 (6,6k). Ze meldde **geen
  tegenspraak**. **De valse melding op PHR:2025:435 is weg:** dezelfde samenvatting van de A-G staat er, zonder
  markering. Wel markeerde ze twee keer `die de passages van dat stuk niet dragen`:
  - bij HR:2023:1371 is dat vals: de samenvatting klopt met de uitspraak, zoals bij bundel 123 nagelezen;
  - bij HR:2023:563 is het onschuldig: het antwoord zegt zelf dat het arrest niet volledig gelezen is.
- **Telling:** met de nieuwe regel 0 valse en 0 terechte tegenspraken, in één controle. Dat is te weinig om te zeggen
  dat ze nu goed werkt. Wel is de bekende valse melding verdwenen.

## Citaten zonder inhoud

- **Deel 1:** bij P01 (trefwoorden van een conclusie), P02 (procedurezinnen uit arresten) en S05 (de aanhef van een
  Koninklijk Besluit).
- **Deel 2:** op één kopregel na (S04: "In aansluiting op artikel 22 van de wet beschrijft dit artikel het beleid
  over:") geen enkele. Deel 2 had geen lijst van uitspraken buiten F01, en de zes citaten van F01 dragen elk de
  bewijslast. De oorzaak uit deel 1 zit dus waarschijnlijk in hoe de uitspraken en bekendmakingen worden aangewezen;
  deel 2 kon dat niet opnieuw toetsen.

## De kwaliteitsset

De 22 vragen één keer, in de vorm centraal, gescoord met de scorers van de set. Ernaast ronde 4, de vorm centraal.

| | Nu (`022506a3`) | Ronde 4 centraal | Ronde 3 centraal | Ronde 2 centraal |
|---|---|---|---|---|
| Geslaagd | **20/22** | 18/22 | 19/22 | 19/22 |
| Ruw | 1,94M | 1,91M | 2,07M | 2,75M |
| Gewogen warm | 444k | 538k | 551k | 608k |
| Modelrondes | 88 | | 101 | 110 |
| Mediaan per vraag, gewogen warm | 12,4k | 9,8k | 11,0k | 12,8k |

- **K03 en K09** falen, zoals in elke ronde, op de verwachting "14 dagen". Het antwoord zegt "veertien dagen" en is
  juist. Dat ligt aan de set, niet aan Lex. Inhoudelijk zijn alle 22 antwoorden dus goed.
- **K12** (milieuwet) gaat nu goed. Lex zegt dat de graaf geen milieuwet bevat en noemt de zeven regelingen. In ronde 4
  wees de centrale agent de vraag af.
- **K13** gaat nu goed: de Invorderingswet staat weer in de bronnenlijst.
- **Goedkoper:**
  - K11: 65k tegen 124k;
  - K15: 29k tegen 83k;
  - de som gewogen: −17 %.
- **Duurder:** K03 kost 39k gewogen tegen 20k in ronde 4.
- **De mediaan per vraag** is 12,4k tegen 9,8k. Dat is hoger dan in ronde 4, maar gelijk aan ronde 2. Er is geen
  drempel voor de kwaliteitsset buiten de regressie.
- **De overdracht naar de brede toolset** gebeurt bij K13, K15 en K17, zoals in ronde 3 en 4.
- **Brongetrouw:** 35 citaten, alle letterlijk.
- **Een opvallend punt bij K18:** 61 keer `onbevestigd` op de artikelnummers in een overzicht van de hoofdstukken. Dat
  is ruis van de grounding, geen fout in het antwoord.
- **Niet nagegaan bij K17:** Lex zegt dat de huidige toestand van artikel 36 formeel tot 1 oktober 2026 loopt, en
  daarna een nieuwe. Of die nieuwe toestand de tekst van artikel 36 raakt, heb ik niet nagegaan.

## Brongetrouw, over de hele run 3

Getoetst is elk blokcitaat, en elk citaat van vijf woorden of meer in de lopende tekst. De bronnen:
- de volledige toestanden van de Iw 1990, de Awb, de AWR, de Awir en de Leidraad uit de BWB-repository;
- elk stuk dat het antwoord noemt, zoals de officiële bekendmakingen en de Rechtspraak het publiceren.

De uitkomst:
- **Deel 1:** 270 van 270 letterlijk.
- **Deel 2, agentset:** 50 van 51. Het ene is het citaat bij V04, "daarvan mededeling te doen aan de ontvanger": dat is
  de vorige tekst van artikel 36, tweede lid, uit de bron buiten de kennisgraaf, zoals in run 1 en 2.
- **Deel 2, kwaliteitsset:** 35 van 35.
- **Samen:** 355 van 356 letterlijk, en het ene is verklaard. Geen onjuiste bron en geen verzonnen citaat.

In de samenvattingen staat één onjuistheid: P02 (deel 1) noemt de Invorderingswet waar kst-36151-3 de Awb en de
sociale zekerheid bedoelt.

## Kosten

- **Run 3 samen:** 8,96M voor 30 + 3 opdrachten, de herhaling van S04 en de kwaliteitsset. Daarvan:
  - de agentset 30 opdrachten (deel 1 zonder S04, plus deel 2): **5,04M**;
  - P01–P03: 1,79M;
  - de kwaliteitsset: 1,94M.

  Ter vergelijking, voor 30 opdrachten: M0 2,94–4,70M, run 2 4,56M. Run 3 is duurder omdat M01 en M06 nu worden
  uitgevoerd (samen 1,32M); in M0 deed de supervisor dat werk voor 0,62–1,31M.
- **De kinderen:** 19 in de agentset en P01–P03, samen 3,98M, gemiddeld 210k. Geen kind ging boven 300k, en ze
  beginnen op 15–27k context.
- **Gewone vragen:** de vijf opdrachten die de centrale agent zelf doet, kosten gewogen warm:

  | E03 | E06 | E07 | E08 | E09 |
  |---|---|---|---|---|
  | 58,6k | 2,8k | 11,8k | 37,7k | 30,6k |

  De mediaan is 30,6k, tegen 32,3k in M0. De duur van E01–E10 is in de mediaan 9,1 s, tegen 14 s in M0. Per opdracht
  ligt alleen E04 boven M0 (4,7 s tegen 0,3–4,0 s). Dat is een lijst uit code; de som is te klein om iets te zeggen.

## Wat er openstaat

1. **Vragen naar boven (de drempel die niet gehaald is):**
   - bij V03 moet een kind dat niet aan lezen toekomt, vragen in plaats van stoppen;
   - V04 gokt de wijziging in plaats van te vragen welke bedoeld is.
2. **V03 levert geen inhoud.** Het kind loopt tegen de rondegrens aan voordat het een memorie van toelichting leest.
3. **F02 en F03.** Na een antwoord op de keuzekaart volgt een nieuwe keuzevraag (F02). De stand van de deelgesprekken
   wordt verkeerd gelezen, zonder `delegatie_stand` (F03).
4. **De controle per stuk:** met de nieuwe regel maar één keer gemeten. Daarnaast markeert ze `niet dragen` nog vals bij
   HR:2023:1371.
5. **Citaten zonder inhoud bij uitspraken en bekendmakingen** (deel 1). Deel 2 kon dat niet opnieuw toetsen.
6. **De set:** K03 en K09 verwachten "14 dagen", en S02 meet geen delegatie (zie run 2). Dat pas je na A6 aan, niet
   tijdens.

## Bestanden

- `a6d2-runs.jsonl`: de acht opdrachten van deel 2 (`centrale_agent_vat.py`): S04, V03, V04 en F01–F05. Let op:
  `per_rol` en `kindgesprekken` dekken bij een opdracht met meer beurten alleen de laatste beurt; `delta_account` dekt
  de hele opdracht.
- `a6d2-kinderen.jsonl`: de drie kindruns van deel 2 (S04, V03, F01) zonder tekst. De drie kinderen van de regie (F03)
  kostten 0 tokens en staan er niet in.
- `a6d2-kwaliteit.jsonl`: de 22 vragen van de kwaliteitsset, met de score, de reden van falen, de route, de
  modelrondes, de ruwe en gewogen tokens, de duur en `onbevestigd`.
- Deel 1 staat in [`../centrale-agent-2026-11-15-a6-run3/`](../centrale-agent-2026-11-15-a6-run3/).

De ruwe runs (antwoordtekst en events) staan niet in de repo.
