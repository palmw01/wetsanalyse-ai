# Kamerstukken, iteratieve verbeterrondes – ronde 1 (11 november 2026)

Soort: *meting* · Code: master `bb6b46a5` (bundel 40, #1222) · Straat: acceptatie, alle connectors aan · Model:
`claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke vraag in een eigen gesprek (de vervolgvragen K21–K22
en K23–K24 in één gesprek), één tegelijk · Vragenset: [`tests/data/kamerstukken_vragenset_30.json`](../../../../tools/graph-qa/tests/data/kamerstukken_vragenset_30.json).

De ruwe gegevens per vraag staan in [`runs.jsonl`](runs.jsonl). De tokens zijn cache lezen + cache schrijven + uitvoer +
invoer uit het `meting`-event van de run. De verbruiksteller zeggen hier niets, want andere sessies gebruiken hetzelfde
account. De feiten zijn nagegaan bij KOOP, met de eigen tools tegen de echte dienst (lokaal, zelfde adapter).

Na K10 was het budget van het account op (429 `budget_op`). De hoofdsessie heeft het gereset, en daarna ging de ronde
verder met K11.

## Uitkomst

**16 goed, 12 deels, 2 fout. Samen 3,62M tokens.** Daarvan komen 2,8M uit vijf vragen (K07, K15, K16, K17, K10).

| vraag | soort | route | rondes | tokens | oordeel |
|---|---|---|---|---|---|
| K01 | lijst | lijstroute | 0 | 0 | goed |
| K02 | lijst | lijstroute | 0 | 0 | goed |
| K03 | lijst | lijstroute | 0 | 0 | goed |
| K04 | lijst | lijstroute | 0 | 0 | deels |
| K05 | onderwerp | lijstroute | 0 | 0 | goed |
| K06 | onderwerp | lijstroute | 0 | 0 | goed |
| K07 | onderwerp | model | 19 | 961k | deels |
| K08 | metadata | lijstroute | 0 | 0 | goed |
| K09 | metadata | lijstroute | 0 | 0 | **fout** |
| K10 | metadata | model | 9 | 315k | deels |
| K11 | genoemd stuk | lezen → model | 4 | 129k | goed |
| K12 | alleen pdf | lezen → model | 1 | 27k | goed |
| K13 | passage | lezen → model | 1 | 30k | goed |
| K14 | passage | bepaling | 1 | 0,4k | **fout** |
| K15 | passage | lezen → model | 11 | 450k | deels |
| K16 | koppeling wet | model | 14 | 510k | deels |
| K17 | koppeling wet | model | 11 | 383k | deels |
| K18 | combinatie | lezen → model | 6 | 196k | deels |
| K19 | herdruk | lezen → model | 2 | 61k | goed |
| K20 | onderwerp | model | 4 | 97k | deels |
| K21 | vervolg | lijstroute | 0 | 0 | deels |
| K22 | vervolg | model | 3 | 65k | goed |
| K23 | vervolg | lijstroute | 0 | 0 | goed |
| K24 | vervolg | model | 4 | 97k | goed |
| K25 | telling | lijstroute | 0 | 0 | deels |
| K26 | telling | model | 4 | 90k | goed |
| K27 | onbekend id | lezen → model | 1 | 27k | deels |
| K28 | tabel | lezen → model | 3 | 94k | goed |
| K29 | voetnoot | lezen → model | 1 | 29k | goed |
| K30 | niets gevonden | model | 3 | 60k | deels |

Wat goed gaat:
- **De lijstroute zonder model**: K01–K03, K05, K06, K08, K23, met de zoekvraag in woorden en het totaal.
- **Een genoemd stuk lezen**: K11, K13, K19 (de herdruk), K28 (de tabel geopend) en K29 (de voetnoot), elk letterlijk.
- **Vervolgvragen**: K22 en K24 begrijpen het stuk uit de vorige beurt.
- **Eerlijk over grenzen**: alleen een PDF (K12), een niet-gelezen tabel, niet alles gelezen.
- **De controle**: 0 niet-letterlijk in 30 vragen.

## Bevindingen, per oorzaak

### A. Eigen code van Kamerstukken (deze ronde opgelost)

1. **Oude Kamerstukken hebben geen koppen** (K07, K16; 1,47M tokens samen).
   - Stukken in het oude schema van KOOP (`kamerwrk`, rond 2005) zetten hun tussenkoppen in `<tuskop>`, niet in
     `<tussenkop>`. Een voorbeeld is kst-30322-3: 93 tuskoppen en 210 alinea's, waarvan geen enkele een kop kreeg.
   - Daardoor geeft `inhoud: true` 0 rijen, en de resultaatregel zegt "heeft geen tekst om te lezen".
   - Het model bladert dan pagina voor pagina (K07), of geeft het Kamerstuk op (K16: geen enkel Kamerstuk in het
     antwoord).
   - Hetzelfde oude schema kent de wortel `staatsbl` en de koppen `<art>`, `<wart>` en `<wlid>`. De hoofdsessie meldt dat
     deze bij Staatsblad en Staatscourant ook voorkomen. Dit is gedeelde code (`tools/op_xml.py`); de hoofdsessie heeft
     het aan deze sessie toegewezen.
2. **Een stuk zonder koppen bij `inhoud: true`** (gedeeld: `tools/stuk_tekst.py`, `spoorbronnen`; toegewezen aan deze
   sessie).
   - Het resultaat is leeg, en de statusregel zegt "geen tekst".
   - Het moet zeggen dat het stuk geen koppen heeft en hoeveel alinea's het telt (lees vanaf offset 0).
   - "Geen tekst" hoort alleen bij `leesbaar: false`.
3. **Het soortfilter vindt ook brieven met het woord in de titel** (K10).
   - "Uitvoeringstoetsen aangenomen amendementen" telde als amendement, en het model telde daarna zelf
     ("89 amendementen en 3 brieven", maar het noemde er 4).
   - Het filter hoort op de rubriek (`w.subrubriek`) te staan. De titel telt alleen bij een stuk zonder eigen rubriek
     (de rubriek "Overig").
4. **`volgorde: nummer` met `aantal` wordt geweigerd** (`ongeldig_aantal`, K07, K17). Het model probeert het en verliest
   er een ronde mee.

### B. Gedeelde code (gemeld bij de hoofdsessie, niet in deze PR)

5. **De bepalingsroute neemt een vraag over die een Kamerstuk noemt** (K14, fout; `supervisie`).
   - "Wat zegt de MvT bij Kamerstuk 33755, nr. 3 over artikel 29 IW?" krijgt alleen de huidige wettekst van art. 29.
   - Een genoemd stuk hoort voor de bepalingsroute te gaan.
6. **Het onderwerp van een lijstvraag neemt een werkwoord mee** (K09, fout; `bron_lijst`, eigenaar Rechtspraak).
   - "… over de inkomstenbelasting zijn er in 2024 verschenen" wordt het zinsdeel "inkomstenbelasting verschenen".
   - Ook "Welke moties gingen over …" (K20) en "Zoek kamerstukken over …" (K30) worden geen lijstvraag.
7. **Het blok stukken uit meer pagina's verliest zoekvraag en totaal** (K10, K20; `sjablonen/extern.py`).
8. **Hoogstens 6 alinea's per aanwijzing kost rondes** (K15: 5 extra rondes, 450k tokens; `sjablonen/extern.py`).
   - Het model splitst na elke weigering één stap verder.
9. **Een foutresultaat telt als gelezen bron** (K27; `grounding.alleen_gelezen_extern`).
   - Het niet-bestaande kst-99999-99 stond in de bronnenlijst, want de foutmelding noemt het id.
10. **Een stuk in citeervorm in de vraag komt niet in de bronnen** (K18; `grounding`).
    - "Stb. 2013, 568" is gelezen, maar het telt niet als genoemd.
11. **Een telvraag noemt het aantal niet** (K25; `bronmodel.antwoord`).
    - De slotzin noemt het totaal alleen als niet alles getoond is, dus "Hoeveel stukken zitten er in dossier 33755?"
      geeft 16 stukken zonder het getal.
12. **Een stuk dat alleen als PDF bestaat, of niet bestaat, gaat langs het model** (K12, K27; `bron_lezen`). Bij Rechtspraak
    geeft een stuk zonder tekst een vaste melding uit code.
13. **Vals alarm in `onbevestigd` bij een tabel** (K28; `hoeveelheden`). De eenheid staat in de tabeltitel ("€ miljoenen")
    en de cellen zijn kale getallen.

Punt 11, 12 en 13 heeft de hoofdsessie na de ronde aan deze sessie toegewezen; ze zitten in de PR van deze ronde. De rest
van B gaat naar de sessie die de code bezit.

## Wat de PR van ronde 1 verandert

1. `op_xml` leest het oude schema: `tuskop` als tussenkop, de wortel `staatsbl`, `art`/`wart` als artikel ("ARTIKEL I"
   wordt "Artikel I"), `wlid` als wijzigingsonderdeel en een `lid` met `nr` als lid, plus `afkondig`, `slotform` en
   `ondertek`. kst-30322-3 geeft live 210 van de 210 alinea's met een kop; stb-2004-700 zijn artikelen, onderdelen en
   leden.
2. `stuk_tekst.inhoudpagina` geeft bij een stuk zonder koppen `zonder_koppen`, het aantal alinea's en `lezen` (offset 0).
   De statusregel zegt dan "heeft geen koppen, 210 alinea’s"; "heeft geen tekst om te lezen" alleen bij `leesbaar: false`.
3. Het soortfilter: `w.subrubriek`, en een stuk zonder rubriek alleen als zijn titel het soort op zijn plek draagt. De
   tool haalt die kandidaten op (`dt.title all … NOT w.subrubriek all …`) en neemt ze op id op. Live gaf
   `w.subrubriek=*` 0, dus "heeft geen rubriek" is niet te vragen. In dossier 36602 zijn dat 88 in plaats van 92.
4. `volgorde: nummer` met `aantal` geeft de eerste zoveel van het dossier, met het totaal.
5. `bron_lezen`: alleen een PDF en niet gevonden krijgen, net als geen tekst, een vaste melding uit code. Dat geldt voor
   elke connector.
6. De slotzin van een lijst noemt het totaal ook als alles getoond is ("16 stukken.").
7. `hoeveelheden.uit_tabellen`: een kaal getal in een tabelcel telt met de eenheid uit de kolomkop of de titel.

### C. Wat het model doet

14. **De gezamenlijke behandeling van dossiers** (K04, K21, K25). Stukken van 33752 met de reeks 33752–33755 heten
    "Kamerstukken 33752, nr. L" in een lijst van dossier 33755, zonder uitleg. De data (`reeks`) staat er wel.
15. **Vrije tekst zonder sjabloon** (K17), en een toelichting die de lijst verkeerd beschrijft ("nieuw naar oud" bij een
    lijst op relevantie, K20).

## Wat deze meting niet zegt

Dit is één run per vraag. De spreiding tussen runs is niet gemeten, en bij de vragen met het model kan die groot zijn.
Het oordeel goed, deels of fout is van deze sessie, tegen de bron. Het is geen juridisch oordeel over de stukken.
