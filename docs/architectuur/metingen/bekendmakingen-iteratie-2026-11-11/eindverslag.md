# Staatsblad en Staatscourant, iteratieve verbeterrondes – eindverslag (11 november 2026)

Opdracht: iteratieve verbeterrondes per connector (de hoofdsessie, 11 nov 2026), voor de connector `bekendmakingen`.
Er waren hoogstens vier rondes: 30 vragen op acceptatie, beoordelen, generiek verbeteren met een test per punt, één PR
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

Van ronde 1 naar ronde 4:
- het aantal goede antwoorden ging van 21 naar 27, en de enige fout (B25) verdween;
- de tokens daalden met 24%;
- dertien vragen gaan nu zonder model, waar dat er negen waren.

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

## Wat open blijft

Ronde 4 is de laatste, dus dit zijn vervolgstappen:

1. **Afkappen in plaats van weigeren bij meer dan 48 alinea's** (B21, B22: twee sjabloonrondes). De code kapt af en zegt
   in het blok dat de bron meer telt. *Gedeeld*, `sjablonen/extern.blokken`.
2. **Eén spoorregel voor de voorlezing** in plaats van "deels gelezen" per pagina. *Gedeeld*, `nodes/bron_lezen.py`.
3. **Zelf afgeleide nummers** ("nieuw artikel 25.2.10"). Een fout van het model die in drie rondes terugkwam. Een
   generieke fix zie ik niet zonder een controle op nummers in de eigen woorden van het model.
4. **Bij andere eigenaren gemeld:**
   - de dubbele "alleen als PDF" (`_zonder_tekst`, Kamerstukken);
   - stukken uit voetnoten in de bronnen zonder dat ze gelezen zijn (B12, sinds bundel 44 of 45).
5. **Spreiding.** B15 en B24 wisselden tussen goed en deels, en B23 en B26 tussen 88k en 140k, zonder codewijziging. Eén
   run per vraag is genoeg om grote oorzaken te vinden, maar niet om kleine verschillen aan een fix toe te schrijven.

## Wat de meting niet zegt

- Elke ronde draaide elke vraag één keer.
- Ronde 4 viel deels samen met een storing van KOOP (23:20–23:29 UTC). De runs tijdens de storing zijn herhaald en niet
  meegeteld; zie [ronde 4](ronde-4.md).
- Niet elke toelichting is zin voor zin tegen de bron gelegd. Feiten met een id, datum of nummer wel, waar het oordeel
  ervan afhing.
