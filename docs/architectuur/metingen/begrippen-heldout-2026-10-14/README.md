# Begrippenketen – held-out metingen (14 okt 2026)

Soort: *meting* · Hoort bij: [ADR-004](../../adr-004-begrippenketen.md),
[eerste meting](../begrippen-kern-2026-10-14/README.md) · 0 modelcalls · Python 3.14.3,
spaCy 3.8.16, `nl_core_news_md` 3.8.0.

De eerste meting gaf 1,0 op de set waarop de regels zijn ontwikkeld. Deze meting toetst of dat
standhoudt op wettekst die bij het ontwikkelen niet bekend was. Alle sets zijn **provisional**
(opgesteld zonder jurist).

## Volgorde (dit is het bewijs, niet alleen de getallen)

| stap | commit | wat |
|---|---|---|
| 1 | `7e435da` | Awir-set (`heldout-v1`) opgesteld zonder de keten te raadplegen; **blind gemeten** op code `48db5d9` → `blind/` |
| 2 | — | foutanalyse op de Awir-set: vijf oorzaken |
| 3 | `62cac44` | AWR-set (`heldout-v2`) opgesteld **vóór** de reparaties; niet gemeten |
| 4 | `e98c5d5` | reparatie van de vijf oorzaken. Formules die alleen in de AWR-set voorkomen bewust níét toegevoegd |
| 5 | `c12bade` | AWR-set **één keer** gemeten → `awr-blind/`; v1 en Awir na reparatie → `na-reparatie/` |
| 6 | dit commit | correctie van één ontbrekend gouden paar in de AWR-set, apart en gemotiveerd → `awr-na-goudcorrectie/` |

Na stap 4 is de Awir-set een ontwikkelset. Alleen de AWR-meting (stap 5) zegt iets over
generalisatie.

## Uitkomsten

| set | variant | zelfde betekenis P / R | relaties gevonden | onterechte relaties | verschillend samengevoegd | BCubed F |
|---|---|---|---|---|---|---:|
| Awir, blind | nulmeting | 1,0 / 0,44 | 0 / 4 | 0 | 0 | 0,86 |
| Awir, blind | **keten** | 1,0 / **0,31** | 0 / 4 | **2** | 0 | 0,82 |
| AWR, blind | nulmeting | 1,0 / 0,83 | 0 / 7 | 0 | 0 | 0,97 |
| AWR, blind | **keten** | 1,0 / 0,83 | **3 / 7** | 1¹ | 0 | 0,97 |
| AWR, gecorrigeerd | **keten** | 1,0 / 0,83 | **4 / 8** | 0 | 0 | 0,97 |
| Awir, na reparatie (ontwikkel) | keten | 1,0 / 0,75 | 3 / 4 | 1 | 0 | 0,96 |
| v1, na reparatie (ontwikkel) | keten | 1,0 / 1,0 | 8 / 8 | 0 | 0 | 1,0 |

¹ De "onterechte" relatie was k16 → k20: "de aanslag" in de opsommende definitie van
belastingaanslag. Dat is een soort belastingaanslag. Het paar ontbrak in de gouden set, in strijd
met de eigen regel uit v1 (f01 → f03) en met de motivatie die er al bij stond. Het is in stap 6
toegevoegd; de blinde uitkomst staat ongewijzigd in `awr-blind/`.

## Wat dit zegt

1. **De eerste versie was overfit.** Blind op de Awir deed de keten het slechter dan "zelfde woord =
   zelfde begrip". De oorzaken waren algemeen, niet Awir-specifiek:
   - een van-complement ("partner van de belanghebbende") telde als beperking;
   - de kern van "degene die …" werd verkeerd bepaald;
   - een definitie zonder dubbele punt werd niet herkend;
   - de mede-formule met een andere woordvolgorde ontbrak;
   - een uitsluiting in de aanhef van een opsomming ontbrak.
2. **Na reparatie, op onbekende wettekst (AWR):**
   - zelfde betekenis zo goed als de nulmeting en nooit fout samengevoegd (precisie 1,0, recall 0,83);
   - daarbovenop de relaties uit opsommende definities (4 van 8, na correctie geen onterechte).
   Het voordeel van de keten zit dus in de **relaties en het niet-samenvoegen**, niet in het
   vinden van meer synoniemen.
3. **Wat hij mist, mist hij omdat hij de formule niet kent**, niet omdat hij iets verkeerds doet:
   - "waar … wordt gesproken van X, is daaronder (mede) begrepen Y": drie inclusies;
   - "als partner wordt aangemerkt: de echtgenoot": een kwalificatie;
   - "Mogendheid" ~ "Mogendheid" zonder definitie: blijft een vraag aan de jurist, zoals ontworpen;
   - de gelijkstelling met een lange tussenzin (Awir art. 3 lid 7): vraagt dependency-analyse.

   De eerste twee zijn bekende wetgevingsformules en logische volgende regels. Toevoegen maakt de
   AWR-set wel een ontwikkelset: wie daarna iets over generalisatie wil zeggen, heeft een derde,
   nieuwe set nodig.
4. **Zonder parser** blijft het precisieprofiel gelijk, met lagere recall (AWR: 0,67).

## Bestanden

- `blind/`: Awir, blind, code `48db5d9`;
- `awr-blind/`: AWR, blind, code `e98c5d5`;
- `awr-na-goudcorrectie/`: idem, na de correctie van één gouden paar;
- `na-reparatie/`: v1 en Awir op code `e98c5d5`.

Elk bestand is de JSON-uitvoer van `python -m eval.begrippen_eval --versie <set> --variant <v> --json`.
