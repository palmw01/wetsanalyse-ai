# Staatsblad en Staatscourant, iteratieve verbeterrondes – eindverslag (11 november 2026)

Opdracht: iteratieve verbeterrondes per connector (de hoofdsessie, 11 nov 2026), voor de connector `bekendmakingen`.
Er waren eerst vier rondes; de hoofdsessie voegde er twee toe (ronde 5 en 6, 12 nov 2026), met de id-controle in
`tool_execution` als punt van deze sessie. Per ronde: 30 vragen op acceptatie, beoordelen, generiek verbeteren met een test per punt, één PR
per ronde. De vragen staan in
[`bekendmakingen_vragenset.json`](../../../../tools/graph-qa/tests/data/bekendmakingen_vragenset.json), de runs in
[`runs.jsonl`](runs.jsonl).

## Score en tokens per ronde

| ronde | code | goed | deels | fout | tokens | zonder model |
|---|---|---|---|---|---|---|
| [1](ronde-1.md) | `bb6b46a5` (bundel 40) | 21 | 8 | 1 | 1.518.494 | 9 |
| [2](ronde-2.md) | `73569621` (bundel 42) | 26 | 4 | 0 | 1.626.011 | 10 |
| [3](ronde-3.md) | `80ca14f4` (bundel 43) | 27 | 3 | 0 | 1.435.498 | 13 |
| [4](ronde-4.md) | `a0eeb8de` (bundel 45) | 27 | 3 | 0 | 1.153.439 | 13 |
| [5](ronde-5.md) | `e7e2ab8a` (bundels 49–51) | 28 | 2 | 0 | 1.422.232 | 12 |
| [6](ronde-6.md) | `66e73f75` (bundels 52–53) | 28 | 1 | 1 | 1.042.354 | 12 |

Van ronde 1 naar ronde 6:
- het aantal goede antwoorden ging van 21 naar 28;
- de tokens daalden met 31% (1.518.494 → 1.042.354), de laagste stand van de zes;
- het aantal correctierondes (`meting.sjabloon.geweigerd`) ging in ronde 5 en 6 van vier naar één;
- twaalf vragen gaan zonder model, waar dat er negen waren;
- de enige fout van ronde 6 (B18) is nieuw. Een versmalling van de bronstand per vraag (#1261) zette Kamerstukken uit,
  en Lex zei tegen de jurist dat die bron "in dit gesprek uit" stond.

Ronde 5 was duurder dan ronde 4: een gelezen stuk kostte ongeveer 8k meer per beurt, en B18 verloor de lijstroute
(184k). In ronde 6 was beide weg.

**De id-controle** (#1253, ronde 5): een id in een toolaanroep van het model moet uit het gesprek komen. Een BWB-id mag
ook als de graaf de regeling bevestigt. Van de zes id-vragen in ronde 5 weigerde de controle twee keer terecht: een
dossiernummer en een ECLI uit eigen kennis. Daarna zocht Lex eerst. In 66 runs weigerde ze nergens ten onrechte.

Ronde 2 was duurder dan ronde 1. G2 vraagt één keer om het sjabloon als het model een lijst als tekst gaf. Dat levert het
blok met links en totaal op, maar kost een ronde.

In geen enkele run was het antwoord ongegrond of het citaat niet letterlijk, en er stond nergens een naam van een
particulier.

## Wat er veranderde, per ronde

- **Na ronde 1** (#1225, met G1 en G2 als gedeelde code van deze sessie):
  - de versies van een stuk (B25 fout → goed);
  - "wetten" als soort, waardoor B20 een lijstvraag werd;
  - de grens bij personen in de beschrijving;
  - één weigering voor alle fouten in `extern` (G1);
  - één keer om het sjabloon vragen bij een lijst als tekst (G2).
- **Na ronde 2** (#1230):
  - K15: een lange reeks splitst de code zelf;
  - de versies in de toelichting (B12 → goed);
  - G2 ook na een gelezen stuk (B22 kreeg het sjabloon).

  Van Kamerstukken kwamen in dezelfde bundel (#1227) het oude Sdu-formaat (B27 → goed) en een stuk zonder tekst
  zonder model (B07 en B13 voor 0 tokens).
- **Na ronde 3** (#1234):
  - de voorlezing leest een kort genoemd stuk helemaal (B21: 328k → 155k, zonder bladerrondes);
  - het sjabloon heeft geen grens meer op het aantal aanwijzingen (B16: 187k → 73k, met alle regelingen).

- **Na ronde 4** (#1253): de id-controle in `tool_execution` (`agent/id_herkomst.py`), declaratief per parameter, voor
  elke connector; en de toelichting bij een artikel zegt dat de BWB per artikel koppelt (B24 deels → goed).
- **Na ronde 5** (#1260):
  - "horen bij" zonder regeling breekt de lijstvraag niet meer af (`bron_lijst._bij_regeling`);
  - een zoekvraag bij alleen een regeling noemt de regeling, zonder lege plek (`extern._bepaling_in_woorden`).

## Wat open blijft

Ronde 6 is de laatste. De punten hieronder zijn benoemd en niet opgelost.

- **B18, de versmalde bronstand** (#1261, gedeeld; ronde 6). Een connector die per vraag niet wordt aangeboden, heet
  tegenover de jurist "uit", en de connector die het filter van de vraag draagt (het dossier) valt weg.
- **Tellingen in de eigen toelichting** (B03 in ronde 5, B26 in ronde 5 en 6). De lijsten kloppen, het getal in de zin
  niet. De beweringentoets toetst geen aantallen.
- **Rechtspraak, I04 in ronde 5:** zes keer `get_uitspraak` op hetzelfde ECLI (508k), en losse Awb-artikelen in de bronnen.

Uit ronde 4, ter vergelijking: twee vervolgstappen in gedeelde code zijn na ronde 4 gebouwd, in dezelfde PR als dit verslag, op
besluit van de hoofdsessie. Ze zijn niet meer gemeten: de andere connectors meten ze in hun volgende ronde.

1. **Afkappen in plaats van weigeren bij meer dan 48 alinea's** (B21, B22: twee sjabloonrondes). *Gebouwd:*
   `extern.blokken` kapt af in de volgorde van het antwoord, en een `Leemte` achter de blokken zegt welke alinea's van
   welk stuk niet geciteerd zijn.
2. **Eén spoorregel voor de voorlezing** in plaats van "deels gelezen" per pagina. *Gebouwd:* voor elke connector
   `spoorbronnen.voorleesregel`, "stcrt-2025-22266 gelezen, 7 pagina’s". Elke pagina blijft een `tool_execution`.
3. **"Zelf afgeleide nummers"** ("nieuw artikel 25.2.10"): in ronde 5 bleek dit geen fout. Onderdeel D van Stcrt. 2025,
   22266 noemt 25.2.10 letterlijk. Het oordeel van de rondes 2–4 was hier te streng.
4. **Bij andere eigenaren gemeld:**
   - de dubbele "alleen als PDF" (`_zonder_tekst`, Kamerstukken). Die was al opgelost in #1237, en in ronde 4 kwam hij
     niet meer voor (B07);
   - stukken uit voetnoten in de bronnen zonder dat ze gelezen zijn (B12, sinds bundel 44 of 45).
5. **Spreiding.** B15 en B24 wisselden tussen goed en deels, en B23 en B26 tussen 88k en 140k, zonder codewijziging. Eén
   run per vraag is genoeg om grote oorzaken te vinden, maar niet om kleine verschillen aan een fix toe te schrijven.

## Wat de meting niet zegt

- Elke ronde draaide elke vraag één keer.
- Ronde 5 en 6 draaiden met alle vier de connectors aan; in ronde 6 strandden twee starts op het accounttoken en zijn
  ze opnieuw gedraaid.
- Ronde 4 viel deels samen met een storing van KOOP (23:20–23:29 UTC). De runs tijdens de storing zijn herhaald en niet
  meegeteld; zie [ronde 4](ronde-4.md).
- Niet elke toelichting is zin voor zin tegen de bron gelegd. Feiten met een id, datum of nummer wel, waar het oordeel
  ervan afhing.
