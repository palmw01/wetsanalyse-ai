# Wetgeving buiten de kennisgraaf: iteratie, ronde 6 en eindverslag – 12 november 2026

- **Soort:** *meting*.
- **Code:** master `66e73f75`, met bundel 52 en bundel 53:
  - #1262 een lijst in tekst wordt het sjabloon zonder modelronde;
  - #1259 en #1260 de lijstroute en de zoekvraag;
  - #1261 per vraag alleen de connectortools die de vraag of het gesprek noemt.
- **Straat:** acceptatie.
- **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** zoals ronde 5 ([`ronde-5.md`](ronde-5.md)): dezelfde 30 vragen en dezelfde bronstand, plus dezelfde vier
  lijstvragen.

De ruwe gegevens staan in [`ronde-6-runs.jsonl`](ronde-6-runs.jsonl). Tokens zijn invoer, uitvoer, cache lezen en cache
schrijven samen, uit het `meting`-event.

## Score

**27 goed, 3 deels, 0 fout.** Ronde 5 had ook 27 goed, 3 deels en 0 fout, maar met andere vragen op *deels*.

**Tokens:** samen **1.025.793**, tegen 1.331.629 in ronde 5 (−23 %).

**Correctierondes:** het `meting`-event telt correctierondes niet apart.
- Bij de 30 vragen is er geen te zien.
- Bij L-K1 werd het sjabloon twee keer gevuld. Dat wijst op één correctieronde, waarschijnlijk van de beweringentoets.

| vraag | soort | oordeel (r5 → r6) | tokens (r5 → r6) | `sjabloon` |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | goed → **goed** | 91.768 → 67.779 | tekst zonder lijst |
| I02 | combinatie Rechtspraak | deels → **goed** | 236.123 → 55.174 | gevuld |
| I03 | lezen | goed → **goed** | 968 → 940 | – |
| I04 | artikel lezen | goed → **goed** | 2.902 → 2.871 | – |
| I05 | BW-lid lezen | goed → **goed** | 366 → 395 | – |
| I06 | combinatie Staatsblad | goed → **goed** | 190.206 → 155.805 | gevuld |
| I07 | niet bestaand | goed → **goed** | 0 → 0 | – |
| I08 | artikel lezen | goed → **goed** | 896 → 899 | – |
| I09 | onderdeel lezen | goed → **goed** | 333 → 324 | – |
| I10 | AMvB lezen | goed → **goed** | 517 → 514 | – |
| I11 | ministeriële regeling lezen | goed → **goed** | 806 → 793 | – |
| I12 | beleidsregel opbouw | deels → **goed** | 212.623 → 132.594 | geweigerd `extern.vul` 1, gemist |
| I13 | opbouw | goed → **goed** | 96.323 → 125.579 | geweigerd `extern.vul` 1, gemist |
| I14 | zoeken in de tekst | goed → **deels** | 69.840 → 46.505 | **omgezet**, gevuld |
| I15 | eerdere tekst, in de graaf | goed → **goed** | 1.816 → 1.820 | – |
| I16 | eerdere tekst, buiten de graaf | goed → **goed** | 689 → 684 | – |
| I17 | toekomstige datum | goed → **goed** | 938 → 902 | – |
| I18 | vervallen artikel | goed → **goed** | 313 → 342 | – |
| I19 | nog niet in werking | goed → **goed** | 532 → 514 | – |
| I20 | vervallen regeling | deels → **goed** | 185.192 → 169.058 | gevraagd 1, geweigerd `extern.vul` 1, gemist |
| I21 | de graaf gaat voor | goed → **goed** | 1.707 → 1.703 | – |
| I22 | dubbelzinnige afkorting | goed → **goed** | 0 → 0 | – |
| I23 | combinatie Kamerstukken | goed → **goed** | 0 → 0 | – (lijstroute) |
| I24 | BW-uitleg | goed → **goed** | 42.011 → 42.198 | geweigerd `bepaling.vul` 1, gevuld |
| I25 | vervolgvraag | goed → **goed** | 6.755 → 6.763 | – |
| I26 | opnemen buiten de graaf | goed → **goed** | 0 → 0 | – |
| I27 | toevoegen buiten de graaf | goed → **goed** | 0 → 0 | – |
| I28 | graaf en overheid.nl samen | goed → **deels** | 114.514 → 163.467 | geweigerd `duiding.vul` 2, gemist |
| I29 | connector uit | goed → **goed** | 0 → 0 | – |
| I30 | telling en volledigheid | goed → **deels** | 73.491 → 48.170 | **omgezet**, gevuld |

**Lijstvragen:**

| vraag | r5 → r6 tokens | `sjabloon` | oordeel |
|---|---|---|---|
| L-R1 (HR, art. 33 Iw) | 293.426 → 346.175 | geweigerd `duiding.vul` 2, gemist | gegrond (6 citaten); inhoud niet beoordeeld |
| L-R2 (art. 36 Iw) | 323.810 → 367.912 | geweigerd `extern.blokken` 1, gevuld | gegrond (14 citaten); inhoud niet beoordeeld |
| L-K1 (invorderingsrente) | 99.441 → 242.981 | gevuld 2× (correctieronde) | gegrond (2 citaten); inhoud niet beoordeeld |
| L-K2 (MvT bestuurdersaansprakelijkheid) | 0 → 0 | – (lijstroute) | deels → **goed**: 7 MvT's, met de zoekvraag erbij (#1259, #1260) |

## De tellers van `meting.sjabloon` (de 30 vragen)

| teller | r5 | r6 |
|---|---|---|
| `gevraagd` (herhaalverzoek) | 5 | **1** (I20) |
| `omgezet` (lijst in code naar het sjabloon) | – | 2 (I14, I30) |
| `tekst_zonder_lijst` | 1 | 1 |
| `gemist` | 2 | 4 (I12, I13, I20, I28: telkens tekst na een weigering) |
| weigeringen | 10 | **7** (`extern.vul` 3, `duiding.vul` 2, `bepaling.vul` 1, `extern.blokken` 0) |
| `tekst_ernaast` | ~1.200 tekens | 738 tekens |

## Wat ronde 6 oploste

- **Het herhaalverzoek is bijna weg.** Het komt nog 1 keer voor, tegen 5 in ronde 5.
  - **I02** rondt direct af met het sjabloon: 717 uitspraken van de CRvB, de 14 nieuwste met link, en de grens van LiDO
    benoemd. Dat kost 55k in plaats van 236k en 3 rondes in plaats van 9, en het oordeel gaat van *deels* naar *goed*.
  - **I01** antwoordt kort in tekst zonder lijst (68k in plaats van 92k).
- **I12:** na één weigering antwoordt het model in tekst. De opbouw in vijf hoofdstukken met hun paragrafen komt uit de
  bron, zonder ongevraagde stukkenlijst en zonder interne taal. Dat kost 133k in plaats van 213k, en het oordeel gaat van
  *deels* naar *goed*.
- **I20:** de bronnenlijst noemt de regelingen uit `list_regelingen` niet meer. Er is geen geraden id en geen eigen
  kennis over de intrekking: *deels* → *goed*.
- **L-K2:** een woordgroep die nergens staat, geeft nu de stukken met elk van de woorden, en de zoekvraag zegt dat.

## Wat ronde 6 niet goed deed

1. **De omzetting zoekt stukken in de hele tekst, niet alleen in de lijst** (I30, *deels*).
   - De tekst zei "van artikel 1 tot en met artikel 86" in de lopende tekst, en een opsomming van statussen telde als
     lijst.
   - Daardoor kwam er een lijst "Artikel 1 · 1 van de 174 stukken" onder de telling.
   - Het probleem zit in `genoemde_stukken`: die zou alleen de lijstregels moeten lezen.
2. **De omzetting herkent geen kaal nummer in een tabel** (I14, *deels*).
   - Het model zette de 7 artikelen in een markdown-tabel als "**19a**", niet als "Artikel 19a". Alleen 22a en 53a werden
     herkend, omdat de lopende tekst ze noemde.
   - De tabel bleef staan, met "2 van de 7 stukken" eronder.
   - Een label vergelijken op het nummer ("19a" bij "Artikel 19a") zou dit vangen.
3. **Tekst na twee weigeringen verliest de vorm van de duiding** (I28, *deels*).
   - De citaten en de vergelijking kloppen.
   - Maar een eigen kanttekening staat als blokcitaat ("> Let op: …", `onbevestigd`), met een verwijzing naar "een andere
     bepaling" uit eigen kennis.
   - In ronde 5 leverde het sjabloon hetzelfde gegrond op.
   - Hier komt de grens van `TEKST_NU` scherp naar voren: de weigeringen van `duiding.vul` waren te herstellen.
4. **De combinatievragen met Rechtspraak en Kamerstukken werden duurder** (L-R1 346k, L-R2 368k, L-K1 243k).
   - Ze lezen meer stukken. Bij L-K1 kwam er een correctieronde bij.
   - Dit ligt buiten de wetgeving_live-connector.

Er komen geen nieuwe fixes meer; de punten hierboven zijn alleen benoemd.

## Eindverslag over de zes rondes

| ronde | code | goed | deels | fout | tokens |
|---|---|---|---|---|---|
| 1 | `1ba00b8f` (bundel 41) | 15 | 13 | 2 | 3.011.170 |
| 2 | `80ca14f4` (bundel 43) | 22 | 7 | 0 | 1.747.246 |
| 3 | `a0eeb8de` (bundel 45) | 24 | 6 | 0 | 1.836.261 |
| 4 | `a995b0c0` (bundel 46) | 26 (+2 apart) | 2 | 0 | 1.192.260 |
| 5 | `e7e2ab8a` (bundels 49–51) | 27 | 3 | 0 | 1.331.629 |
| 6 | `66e73f75` (bundels 52–53) | 27 | 3 | 0 | 1.025.793 |

- **Kwaliteit:** van 15 naar 27 goed, en sinds ronde 2 geen fout meer.
  - De drie *deels* van ronde 6 komen voort uit de nieuwe omzetting (I14, I30) en uit de terugval op tekst (I28).
  - Alle drie zijn generiek en klein te herstellen:
    - de omzetting alleen laten kijken naar de lijstregels;
    - een label op zijn nummer vergelijken;
    - bij een weigering die te herstellen is (`duiding.vul`) nog één poging toelaten.
- **Kosten:** van ronde 1 naar ronde 6 daalden de tokens met 66 %.
  - **Workflowvragen** (een genoemd artikel, lid of onderdeel) kosten 300 à 3.000 tokens.
  - **Meldingen** (niet bestaand, dubbelzinnig, connector uit, opnemen) kosten 0.
  - **Lijstvragen via de lijstroute** kosten 0.
  - **Een modelantwoord** kost 45k à 170k.
- **Meetbaarheid:** sinds ronde 5 laat het veld `sjabloon` in het `meting`-event per beurt zien hoeveel herhaalverzoeken,
  omzettingen, weigeringen (per redencode) en gemiste sjablonen er waren. Elke meetronde is zo zonder Grafana te
  verklaren.
- **Wat open blijft (benoemd, niet gebouwd):**
  - de drie punten hierboven;
  - correctierondes apart tellen in het `meting`-event;
  - eigen kennis in een blokcitaat (I28) en in de toelichting, die de beweringentoets niet vangt.
