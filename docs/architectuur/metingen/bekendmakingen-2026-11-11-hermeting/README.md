# Staatsblad en Staatscourant, hermeting – 11 november 2026

Soort: *meting* · Code: master `d6dcabb5` (bundel 36, #1209: met #1206) · Straat: acceptatie, connector `bekendmakingen`
aan (`/api/connectors`: `beschikbaarheid: aan`) · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP,
elke run in een nieuw gesprek met `bronnen: ["bekendmakingen"]`, één tegelijk · Akkoord: de hoofdsessie, voor één run per
veranderde vraag, geschat op ~400k (grens 600k).

Een hermeting van de vragen die #1206 raakte, na [de meting van 10 november](../bekendmakingen-2026-11-10/README.md). De
vragen en wat een goed antwoord is, staan in
[`bekendmakingen_vragenset.json`](../../../../tools/graph-qa/tests/data/bekendmakingen_vragenset.json). B12 is sinds #1206
een andere vraag (stcrt-2024-20015-n1 in plaats van een herdruk over onderwijs). De ruwe gegevens per run staan in
[`runs.jsonl`](runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache schrijven, uit het `meting`-event.

## Hoeveel er gemeten is

**8 runs, één per vraag: B03, B04, B05, B08, B10, B11, B12 en B16. Samen 451.885 tokens.** De verbruiksteller van het
account steeg in dezelfde tijd met 749.624 (van 191.458 naar 941.082). Het verschil komt van een andere meting op
hetzelfde account in dezelfde minuten (de gesprekken "Meting rechtspraak-versies 11 nov 2026", 06:24–06:29 UTC), dus de
teller is hier geen controle. De som per run is de maat.

## Uitkomst

| # | route | goed | tokens | vorige meting | opmerking |
|---|---|---|---|---|---|
| B03 | model, 5 rondes, 3 tools | ja | 93k | 90k / 376k / 90k | verzamelwetten via de tekst, gesplitst in wijzigen, inwerkingtreding en alleen noemen; geen enkele pagina gelezen |
| B04 | model, 6 rondes | ja | 114k | 139–141k | 4 juli 2010, Stb. 2009, 610 en Stb. 2010, 176 met de goede rol, gegrond; **Stb. 2010, 176 staat nu in de bronnen** |
| B05 | model, 3 rondes, 1 tool | ja | 43k | 60–62k | Stcrt. 2026, 37344 bovenaan, 16 van 58; geen nul-ronde meer op de soort |
| B08 | genoemd stuk mét artikel + 4 rondes | ja | **86k** | 24k / 24k / 46k | alleen onderdeel A, letterlijk; daarna las het model toch het hele stuk (bevinding 1) |
| B10 | lijstvraag, 0 rondes | ja | 0 | 43k | "12 van de 38 stukken" met de zoekvraag |
| B11 | lijstvraag, 0 rondes | **ja** (was 0/3) | 0 | 0 | 11 verbeterbladen uit 2018; het jaar staat in de zoekvraag |
| B12 | genoemd stuk + 1 ronde | ja, deels | 43k | (andere vraag) | samenvatting A–G met letterlijke passages, label "(versie n1)"; noemt de eerdere versie niet |
| B16 | genoemd stuk + 2 rondes | ja, onvolledig | **72k** | 338k | 12 regelingen uit de inhoud; acht artikelen zonder aanhef in de inhoud, en dat zegt het antwoord (bevinding 2) |

**Garanties:** geen run ongegrond (5 gegrond, 3 onbepaald), 0 niet-letterlijk, elke passage in `extern` komt uit een
gelezen stuk. In B04 staat de bekendmaking waaruit het antwoord citeert in de bronnen.

**Wat #1206 opleverde, per bevinding van 10 november:**
- 1 (jaartal valt weg): opgelost, B11 goed voor 0 tokens.
- 2 (verzamelwet doorbladeren): B16 van 338k naar 72k, B03 zonder doorbladeren (93k). De filter `regeling` gebruikte het
  model in deze runs niet; B03 had hem niet nodig.
- 4 (Invoeringswet): tekstcorrectie, niet gemeten.
- 5 (leemtezin): niet gemeten (B14 viel buiten de hermeting).
- 6 (filters in het spoor): opgelost, elke zoekvraag noemt haar filters in `tool_execution`.
- 7 (bekendmaking niet in de bronnen): opgelost (B04).
- 8 (artikel bij de voorlezing): werkt (3 rijen), maar maakte B08 duurder (bevinding 1 hieronder).
- B10 als lijstvraag: 43k → 0.
- B12 (genoemd stuk buiten het domein): de nieuwe vraag valt binnen het domein; het samenvatten buiten het domein is
  hier niet gemeten.

## Bevindingen

1. **Na een voorlezing met artikel leest het model het hele stuk alsnog** (B08, 86k tegen 24k). De voorlezing gaf de drie
   rijen van onderdeel A, met de toelichting dat er alleen dat deel staat. Het model haalde daarna de eerste pagina van
   het hele stuk op (32 rijen) en zocht artikel 1.1.5 in de BWB (`get_bepaling` → 0 rijen). Het antwoord noemt de
   inwerkingtreding (1 januari 2027) en de ondertekening: die staan niet in de drie rijen. Mogelijke verbetering: de
   voorlezing met artikel draagt ook de rijen met de inwerkingtreding en de dagtekening, of het `stuk` noemt ze. Eerst
   meten met meer runs: één run zegt niets over de spreiding.
2. **De inhoud mist de aanhef als die langer is dan 160 tekens** (B16). `stuk_tekst.inhoud` geeft `begint` alleen bij een
   eerste alinea van hoogstens `MAX_BEGIN` tekens. Bij Stb. 2009, 610 vallen zo acht artikelen weg (IIA, IVA, VII–X, XIIB,
   XIV), want hun aanhef is één lange zin ("Aan artikel 15, eerste lid, van de Wet op belastingen van rechtsverkeer wordt,
   onder vervanging van …"). Lex noemt 12 regelingen in plaats van 17 en zegt welke artikelen hij niet zag. De regeling
   staat bijna altijd aan het begin van de zin. Een begin tot een woordgrens, met de markering dat het is afgekapt,
   lost dit op zonder de hele alinea mee te geven.
3. **Kleine dingen:**
   - De zoekvraagzin zegt "van de Ministerie van Financiën" (B10). Het lidwoord hoort bij het orgaan: "van het".
   - In B04 staat bij Stb. 2010, 176 de twijfel "alleen als PDF beschikbaar bij KOOP", terwijl het stuk `leesbaar: true`
     heeft en de tekst gelezen is. Dat is een fout van het model.
   - B12 noemt de eerdere versie (stcrt-2024-20015, 28 juni 2024) niet. Het model zocht niet naar andere versies,
     en `stuk.versie` ("n1") zegt alleen dát er een eerdere is.
   - B11 zegt niet wat een verbeterblad is: de lijstroute heeft geen toelichting.
   - De bron "Leidraad 1.1.5" in B08 heeft de IRI als label (`get_bepaling` gaf 0 rijen).

## Wat deze meting niet zegt

- Eén run per vraag, dus geen spreiding. Vooral B08 en B16 kunnen bij een tweede run anders uitvallen.
- B01, B02, B06, B07, B09 en B13–B15 zijn niet opnieuw gemeten.
- Het samenvatten van een genoemd stuk buiten het belastingdomein (het besluit bij B12) is niet gemeten: de nieuwe B12
  valt binnen het domein.
- De datums in de toelichtingen zijn niet elk tegen KOOP of de BWB nagetrokken (bijvoorbeeld "24 juni 2024" in B12).

## Controle na de oplossing – 11 november 2026

Code: master `7afd7d15` (bundel 37, #1212, met de oplossing uit #1210). Twee runs, B08 en B16, samen **142.318 tokens**
(grens 150k). Ruwe gegevens onderaan [`runs.jsonl`](runs.jsonl), `r: "controle"`.

| # | rondes | tokens | hermeting | uitkomst |
|---|---|---|---|---|
| B08 | 3, 2 tools | 45k | 86k | goed: onderdeel A en de toelichting erbij, letterlijk, gegrond |
| B16 | 4, 2 tools | 98k | 72k (12 regelingen) | goed: **alle 17 regelingen**, per artikel, gegrond |

- **B08 is weer goedkoop.** Na de voorlezing met artikel las het model alleen de toelichting bij onderdeel A, vanaf de
  offset uit `inhoud_publicatie` (265), en niet het hele stuk of de BWB. Van de 45k was 24k cache schrijven: de eerste
  run na de uitrol had een koude cache. De 24k van de eerste meting was met een warme cache.
- **B16 heeft alle artikelen.** De eerste pagina gaf alle 30 koppen zonder begin, met `inhoud_openen`. Het model vroeg de
  inhoudpagina op (`inhoud: true`, 30 koppen met hun aanhef) en las de tekst niet door. Het noemt de 17 regelingen, en
  zegt wat XX, XXA, XXI en XXII doen. Duurder dan de 72k van de hermeting, maar die miste 5 regelingen. De eerste meting
  vond er 17 voor 338k.
- **Twee kleine dingen:**
  - In B16 citeert het blok `extern` de hele eerste pagina (nr 1–20: de aanhef en artikel I) in plaats van de aanhef per
    artikel. Die aanhef staat alleen in de inhoudpagina, niet als rij met een nr, dus het model kon hem niet als passage
    aanwijzen. Een groot deel van de 98k zit in die uitvoer.
  - Het spoor toont `inhoud: true` niet bij de filters (`tool_execution.FILTERS`).

Eén run per vraag, dus geen spreiding.
