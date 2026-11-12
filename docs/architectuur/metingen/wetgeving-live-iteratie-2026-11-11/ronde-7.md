# Wetgeving buiten de kennisgraaf: gerichte meting na de fixes voor I30, I14 en I28 – 12 november 2026

- **Soort:** *meting*.
- **Code:** master `a120e579` (bundel 55, met #1272).
- **Straat:** acceptatie.
- **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** dezelfde bronstand als ronde 5 en 6. De drie vragen van de fixes (I30, I14, I28) en vijf andere
  modelvragen (I01, I02, I12, I13, I20), elk één run in een eigen gesprek.

De ruwe gegevens staan in [`ronde-7-runs.jsonl`](ronde-7-runs.jsonl). Tokens zijn invoer, uitvoer, cache lezen en cache
schrijven samen, uit het `meting`-event.

## Uitkomst

**5 goed, 3 deels, 0 fout.** Dezelfde acht vragen in ronde 6: 5 goed, 3 deels (I14, I28, I30).

**Tokens:** samen **775.859**, tegen 808.326 voor dezelfde acht in ronde 6.

**Correctierondes:** één, bij I02. Daar werd het sjabloon twee keer gevuld.

| vraag | oordeel (r6 → r7) | tokens (r6 → r7) | `sjabloon` |
|---|---|---|---|
| I30 | deels → **deels** | 48.170 → 48.172 | omgezet, gevuld |
| I14 | deels → **goed** | 46.505 → 46.359 | omgezet, gevuld |
| I28 | deels → **deels** | 163.467 → 135.195 | geweigerd `duiding.vul` 2, gemist |
| I01 | goed → **goed** | 67.779 → 67.835 | omgezet, gevuld |
| I02 | goed → **goed** | 55.174 → 86.631 | gevuld 2× (correctieronde) |
| I12 | goed → **goed** | 132.594 → 130.414 | geweigerd `extern.vul` 1, gemist |
| I13 | goed → **goed** | 125.579 → 168.438 | geweigerd `duiding.vul` + `extern.blokken`, gemist |
| I20 | goed → **deels** | 169.058 → 92.815 | lijst aangenomen, gemist |

## Wat de fixes deden

- **I14 (opgelost).**
  - In ronde 6 stonden de 7 artikelen als "**19a**" in een tabel, en de code herkende er maar 2 van.
  - Nu herkent de code ze alle zeven aan de kern van hun label. Ze staan met link in de lijst, en de tabel is weg.
- **I30 (half).**
  - **Wat werkt:** de lopende tekst telt niet meer mee. "Van artikel 1 tot en met artikel 86" zet dus geen "Artikel 1"
    meer onder de telling.
  - **Wat nog misging:** het begin van "- **4** nog niet in werking" was gelijk aan de kern van "Artikel 4". De telling
    werd zo een lijst van één stuk, en die regel viel uit de tekst.
  - **Opgelost in deze PR:** een korte kale kern ("4", "19a") telt aan het begin van een opsomming alleen nog in twee
    gevallen:
    - de regel is precies dat nummer, zoals een tabelcel;
    - de regel draagt ook het voorvoegsel van het label ("§ 22a …", "Artikel 19a …").
  - Een kern met meer dan een nummer ("2010, 176") blijft onderscheidend genoeg.
  - Toets: `test_een_telling_in_een_opsomming_is_geen_stuk`.
- **I28 (half).**
  - **Wat werkt:** er staat geen eigen kanttekening meer als blokcitaat.
  - **Wat niet werkt:** de twee weigeringen van `duiding.vul` bleven. De tekst noemt artikel 36 Iw, dat niet gelezen is
    (`onbevestigd`). Waarschijnlijk is het de weigering "je noemt artikel 36 zonder passage": het model hield vast aan
    een artikel uit eigen kennis.
  - Die weigering was al gericht. Dat het model haar negeert, is geen fout in de code, wel een grens van het mechanisme.
- **I01:** de omzetting werkt (Besluit en Regeling lz met link). Wel bleef de inleidende zin "Daarnaast zijn er
  verwante regelingen, zoals:" staan, zonder lijst erachter. Dat is cosmetisch, maar het valt op.
- **I20 (nieuw *deels*).**
  - **Beter:** er komt geen herhaalverzoek meer, want een opsomming van adviezen is gewone tekst. De run kost 93k in
    plaats van 169k.
  - **Wat niet goed is:** de stellige bewering "staat niet in het Basiswettenbestand" komt nergens vandaan. In ronde 6
    stond er "met de tools niet te vinden". Dit is modelgedrag; de beweringentoets vangt het niet.

## Open, benoemd

- **De inleidende zin bij een lijst die de code verplaatst** (I01, "zoals:"). Te herstellen door een zin die op ":"
  eindigt direct vóór de verwijderde lijstregels mee te nemen.
- **Een artikel uit eigen kennis dat het model blijft noemen** (I28). Na twee weigeringen komt het als `onbevestigd` in
  tekst.
- **Een stellige bewering over wat een bron niet bevat** (I20). Dat hoort bij de beweringentoets (Rechtspraak).
