# Begrippenketen – eerste meting van de deterministische kern (14 okt 2026)

Soort: *meting* · Code: `55ae08f` (keten `6e9fb14`, ADR-004 PR 2–7) · Referentie:
[`referentieset-begrippen/v1`](../../../wetsanalyse/referentieset-begrippen/README.md), sha256
`a04035a02eec…`, status **provisional** · Python 3.14.3, spaCy 3.8.16, `nl_core_news_md` 3.8.0 ·
0 modelcalls.

## Wat er gemeten is

Drie varianten op dezelfde 25 formuleringen en 22 paren uit art. 2 en 9 Invorderingswet 1990
(`python -m eval.begrippen_eval --variant <v>`, offline, elk twee keer gedraaid voor de
determinismecontrole):

| variant | wat | zelfde betekenis P / R | hiërarchie R | kwalificatie R | inclusie R | BCubed F | verschillend samengevoegd | groen / geel |
|---|---|---|---|---|---|---:|---:|---|
| `lemma` | nulmeting: groeperen op de tekst zonder lidwoord | 0,73 / 0,73 | 0 | 0 | 0 | 0,89 | 2 (f01~f22, f18~f19) | 6 / 0 |
| `keten` | de begrippenketen met spaCy | 1,0 / 1,0 | 1,0 | 1,0 | 1,0 | 1,0 | 0 | 13 / 2 |
| `keten_zonder_parse` | idem, null-provider | 0,95 / 0,95 | 0,8 | 1,0 | 1,0 | 0,96 | 0 | 13 / 1 |

Alle drie zijn deterministisch. De rapporten staan naast dit bestand (`<variant>.md` en `.json`).

## Hoe dit te lezen

**Dit is een ontwikkelmeting, geen kwaliteitsoordeel.** Twee redenen, en ze wegen allebei:

1. **De set is provisional.** Ze is opgesteld zonder jurist. Vooral de grensgevallen ("de
   aanslag" als soort, lid 3 als afwijkende kwalificatie) zijn een eerste duiding.
2. **De regels zijn op deze set ontwikkeld.** De keten is gebouwd terwijl deze paren bekend waren.
   Een score van 1,0 laat dus zien dat de regels doen wat ze beogen, niet dat ze generaliseren.
   Zonder een held-out set uit een andere regeling zegt dit getal daar niets over.

Wat de meting wél laat zien:

- **Het verschil met de nulmeting zit precies in de bedoelde gevallen.** "Zelfde woord = zelfde
  begrip" voegt de homoniem "termijnen" en de afwijkende kwalificatie van lid 3 samen, en mist de
  verwijzingen ("die belastingaanslag", "bedoeld in onderdeel c") en alle relaties. De keten
  houdt de eerste twee apart en vindt de andere via definities en verwijzingen, zonder model.
- **Geel is waar het hoort.** Twee voorstellen vragen de jurist: de homoniem "termijnen" (alleen
  zwak bewijs, rij `Z-ANDERS`) en "een belastingaanslag die een uit te betalen bedrag behelst" als
  mogelijke soort (middel bewijs, rij `R-MIDDEL`). De kopsignalen van samenstellingen (twaalf,
  allemaal zwak en in deze wet allemaal onjuist) leveren terecht geen voorstel op (`R-TE-ZWAK`).
- **Zonder parser blijft de keten bruikbaar.** De twee missers: de nevenschikking in "beschikking
  of uitspraak" (de term wordt dan één woord) en de beperking "die … behelst" (zonder parse niet
  te zien). Er wordt dan niets ten onrechte samengevoegd.

## Wat hierna nodig is

1. **Een held-out set** uit een regeling waarop niet is ontwikkeld, met minstens een uitsluiting
   ("wordt niet verstaan") en synoniemen met een ander woord. Die ontbreken in v1. Pas die meting
   zegt iets over generalisatie. Het ligt voor de hand: de definities en de opsommingen van de
   Algemene wet inzake rijksbelastingen, of hoofdstuk 5 Awb.
2. **Adjudicatie van v1** door een jurist, volgens het protocol van spoor A.
3. Pas daarna de **classifier voor possible link** (ADR-004, later): meten of hij de gele vragen
   beter maakt dan de jurist ze zonder hulp beantwoordt.
