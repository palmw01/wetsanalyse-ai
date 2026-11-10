# Staatsblad en Staatscourant op acceptatie – 10 november 2026

Soort: *meting* · Code: master `466a65d2` (bundel 35, #1203: #1202 + #1201) · Straat: acceptatie, `CONNECTOR_BEKENDMAKINGEN`
aan (infra-uitrol run 42899346693), `/api/connectors` gaf `bekendmakingen` met `beschikbaarheid: aan` · Model:
`claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke run in een nieuw gesprek met `bronnen: ["bekendmakingen"]`,
één tegelijk · Akkoord: gegeven door de gebruiker voor 48 runs, geschat op 1,5–2M tokens.

De vragen, de verwachte tool en wat een goed antwoord is, staan in
[`tools/graph-qa/tests/data/bekendmakingen_vragenset.json`](../../../../tools/graph-qa/tests/data/bekendmakingen_vragenset.json),
de criteria in [`docs/acceptatie/connectors-meting.md`](../../../acceptatie/connectors-meting.md) §Staatsblad en Staatscourant.
De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache schrijven, uit
het `meting`-event.

## Hoeveel er gemeten is

**46 van de 48 runs.** B01 tot en met B15 hebben elk drie runs, B16 heeft er één. Na B16 run 1 stond de som op 2.143.283
tokens; volgens de verbruiksteller was het 2.143.389 (van 36.243 naar 2.179.632). Dat is al boven de goedgekeurde schatting.
B16 kostte in run 1 338k. Twee runs erbij zouden ~680k extra kosten, en daarmee kwam het totaal op ~2,8M. Ik heb ze niet
gedraaid. **Ontbreekt: B16 run 2 en 3.** Het account had nog ruimte (43%), maar het akkoord ging over 1,5–2M.

De schatting zat ernaast door twee vragen: B03 run 2 (376k) en B16 run 1 (338k). In beide bladert het model een
verzamelwet van begin tot eind door (bevinding 2). Zonder die twee zou het totaal 1,43M zijn.

## Uitkomst

| # | soort | route | goed | tokens per run | opmerking |
|---|---|---|---|---|---|
| B01 | 10 nieuwste | lijstvraag, 0 rondes | 3/3 | 0 | tien Stcrt van 10 nov, alleen soorten uit de witte lijst |
| B02 | 5 nieuwste beleidsregels | lijstvraag, 0 rondes | 3/3 | 0 | zoekvraagzin erbij, 5 van 3.617 |
| B03 | wijzigingen Iw sinds 2024 | model, 5–11 rondes | 3/3 | 90k / 376k / 90k | grens van de BWB-koppeling 3/3; run 2 citeert de wijzigingsartikelen |
| B04 | inwerkingtreding art. 36 Iw | model, 7 rondes | 3/3 | 139–141k | 4 juli 2010, Stb. 2009, 610 (wijziging) en Stb. 2010, 176 (inwerkingtreding), gegrond |
| B05 | Leidraad in de Stcrt | model, 4 rondes | 3/3 | 60–62k | Stcrt. 2026, 37344 bovenaan |
| B06 | Stb. 2010, 176 lezen | genoemd stuk + 2 rondes | 3/3 | 41k | 5 letterlijke passages, gegrond |
| B07 | alleen een PDF | genoemd stuk + 1 ronde | 3/3 | 19k | link, geen citaat |
| B08 | wat veranderde aan 1.1.5 | genoemd stuk + 2–3 rondes | 3/3 | 24k / 24k / 46k | alleen onderdeel A, letterlijk |
| B09 | Kamerdossier | genoemd stuk + 1 ronde | 3/3 | 20k | "Kamerstuk 33 755" uit de tekst |
| B10 | telling | model, 3 rondes | 3/3 | 43k | 38 = het `totaal` van KOOP (lokaal getoetst); vrije tekst zonder zoekvraag |
| B11 | verbeterbladen 2018 | lijstvraag, 0 rondes | **0/3** | 0 | **het jaar viel weg** (bevinding 1) |
| B12 | herdruk | genoemd stuk + 1 ronde | **0/3** | 20k | Lex weigert: het stuk gaat over onderwijs (bevinding 3) |
| B13 | niet bestaand nummer | genoemd stuk + 1 ronde | 3/3 | 19k | "bestaat niet", niets verzonnen |
| B14 | zonder treffers | lijstvraag, 0 rondes | 3/3 | 0 | leemte met de zoekvraag |
| B15 | deurwaardersexploten | model, 2 rondes, 0 tools | 3/3 | 23k | buiten de bron, geen namen |
| B16 | welke regelingen wijzigt Stb. 2009, 610 | genoemd stuk + 10 rondes | 1/1 | 338k | 17 regelingen uit de tekst, met AWR en Iw; de hele wet doorgebladerd |

**Garanties (3/3 vereist):**
- geen run ongegrond: 46 van 46 (gegrond of onbepaald);
- 0 niet-letterlijk in 46 runs, en elke passage in `extern` komt uit een gelezen stuk;
- geen naam van een particulier (B15 3/3, en B01 bevat alleen soorten uit de witte lijst);
- in de gelezen antwoorden geen datum, soort of nummer van buiten KOOP of de BWB. Eén telfout van het model: in B03 run 3
  staat "zes publicaties in het Staatsblad" bij vijf Staatsbladen en één Staatscourant.

**Slagen (≥ 2/3):**
- de lijstvragen en genoemde stukken gingen zonder model naar de tool: B01, B02, B06, B07, B09, B13, B14 en B16 (eerste
  lezing door de code);
- B11 haalt het niet: de route klopt, maar de zoekvraag mist het jaar;
- B12 haalt het niet: het stuk is gelezen, maar het antwoord is een weigering;
- B04 noemt 3/3 beide publicaties met de goede rol;
- B08 citeert 3/3 alleen onderdeel A;
- B10 noemt 3/3 het totaal.

**Trend:** B03 noemt de grens van de BWB-koppeling 3/3.

## Bevindingen

1. **Een jaartal na "van" valt stil weg uit een lijstvraag** (B11, 0/3). `_JAAR_RE` in `agent/bron_lijst.py` kent *sinds,
   vanaf, na, in, uit, tot, voor*, maar niet *van*. Het overgebleven "2018" telt daarna niet als onverwerkt woord
   (`not w.isdigit()`). Zo gaat de vraag zonder jaar als lijstvraag door, zonder model, met een ander antwoord: 14
   verbeterbladen uit 2025–2026 in plaats van de 11 uit 2018. "uit 2018" werkt wel (lokaal getoetst). Dit geldt voor elke
   connector. Generieke fix: een jaartal dat de code niet plaatst, stuurt de vraag naar het model; daarnaast kan "van
   <jaar>" na een publicatieblad of reeks als *in* gelden.
2. **Wat een verzamelwet aan één regeling verandert, of welke regelingen ze wijzigt, kost een hele wet lezen** (B03 run 2
   376k, B16 run 1 338k). Het model probeerde in B03 drie keer `get_bekendmaking` met `artikel: "Invorderingswet 1990"`
   (geweigerd: `ongeldige_argumenten`) en bladerde daarna 7 tot 8 pagina's door. Het antwoord was in beide gevallen goed
   en letterlijk. Twee generieke opties:
   - een filter `regeling` op `get_bekendmaking`: alleen het wijzigingsartikel waarvan de aanhef de regeling noemt
     ("De Invorderingswet 1990 wordt als volgt gewijzigd:");
   - of een inhoudsopgave van het stuk (kop en eerste alinea per artikel) als eerste pagina.

   De wetsverwijzing uit de BWB (`regelingen_bij`) gebruikte het model in B16 niet. Die noemt ook alleen de regelingen die in
   de graaf staan.
3. **B12 meet de herdruk niet.** stb-2010-185-n1 gaat over onderwijs, en Lex weigert dan een antwoord ("valt buiten mijn
   werkgebied"), terwijl hij het stuk wel las. De vragenset heeft een herdruk uit het belastingdomein nodig. Of Lex een
   officiële publicatie buiten dat domein mag samenvatten, is een vraag voor de afbakening in de prompt, niet voor de
   connector. Het label zegt "Stb. 2010, 185 (versie n1)", niet "herdruk".
4. **stb-1990-222 is de Invoeringswet Invorderingswet 1990, niet de Invorderingswet 1990 zelf.** Lex zei het goed (B07,
   uit de metadata). De vragenset (`goed` bij B07), het docstring van `tests/test_bekendmakingen_live.py` en
   `frontend/scripts/test-bronvenster-bekendmaking.mjs`, en het meetplan zeggen het verkeerd. Dat zijn tekstcorrecties.
5. **De leemtezin luidt "Geen Staatsblad en Staatscourant gevonden die aan de zoekvraag voldoen"** (B14). De groepsnaam
   past daar niet als meervoud. Bij Kamerstukken ("Geen Kamerstukken gevonden") klopt dezelfde zin wel. Generiek: de zin
   gebruikt een verzamelnaam uit de beschrijving ("bekendmakingen"). De zin "dat bewijst niet dat het niet bestaat" uit het
   meetplan staat er niet in.
6. **Het `tool_execution`-event noemt alleen `tekst` en `offset` als filters.** Publicatieblad, soort, jaar, orgaan en
   `woorden` ontbreken, dus het spoor laat niet zien wat er gezocht is. De denkregel en de zoekvraagzin van het blok
   `stukken` laten het wel zien. Twee zoekvragen met 0 treffers zijn zo alleen lokaal te reconstrueren:
   - B05: de Leidraad met soort `beleidsregel` geeft 0, want KOOP noemt hem "ander besluit van algemene strekking";
   - B03: de Iw in de titel van het Staatsblad sinds 2024 geeft 0, want verzamelwetten noemen de wet niet in de titel.

   Beide kosten een modelronde. De logs van acceptatie waren vanaf hier niet te lezen (Grafana-toegang ontbreekt in de MCP).
7. **Een gelezen bekendmaking staat niet altijd in de bronnen.** In B04 (3/3) bevatten de bronnen alleen art. 36 lid 2, terwijl
   het antwoord een blok `extern` uit Stb. 2010, 176 heeft. In B06–B09 en B16 staat het stuk er wel in.
8. **B08 werkt omdat 1.1.5 vooraan staat.** De code leest het genoemde stuk vooraf zonder het `artikel` uit de vraag (33
   rijen, er is meer). Bij een artikel verderop moet het model zelf verder lezen. Het artikel meegeven aan de voorlezing
   is goedkoper.
9. **Kleine dingen:**
   - de kop "Artikel XI › C." met een punt (het `lidnr` in de XML, B03 run 2);
   - systeemtaal in B15: "Volgens de regels van dit gesprek" en "van deze werkplek zoekt en leest Lex";
   - B10 geeft het getal in vrije tekst, zonder de zoekvraag erbij;
   - het eerste gesprek van de meting (20:58) verdween meteen: de hele gesprekkenlijst van het account was leeg en de run
     onbekend. Waarschijnlijk wiste een andere sessie op hetzelfde account gesprekken. De meting begon opnieuw in een
     nieuw gesprek.

## Wat deze meting niet zegt

Het is geen juridisch oordeel over de publicaties. Bij de herhalingen waarvan de vorm gelijk was (zelfde aantal events,
rondes en tools) is alleen route, duur, tokens en grounding gelezen. Dat geldt voor:
- B05 run 3;
- B06 run 2 en 3, B07 run 2 en 3, B09 run 2 en 3;
- B12 run 3, B13 run 2 en 3, B14 run 2 en 3.

Bij B10 run 3 en B08 run 3 is de tekst niet gelezen. De datums in de toelichtingen (bijvoorbeeld "inwerkingtreding 1
januari 2026" in B03 run 2) zijn niet elk tegen KOOP of de BWB nagetrokken. B16 is één run, dus voor B16 is er geen
spreiding.
