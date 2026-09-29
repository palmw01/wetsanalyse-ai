# Baseline hybrid_v1 (29 september 2026)

Deze map legt de nieuwe nulmeting van hybrid_v1 vast. Zij vervangt als vertrekpunt voor het
vervolg de freeze in [hybrid-v1-freeze](../hybrid-v1-freeze) en het invorderingsvervolg in
[hybrid-v1-invordering-vervolg-2026-09-29](../hybrid-v1-invordering-vervolg-2026-09-29); die
metingen blijven ongewijzigd als historisch vergelijkingspunt.

## Wat in deze baseline zit

Uitgangspunt R0 is `e8c1603` (PR #539, lokale tag `meting/r0-invordering-vervolg`). Daarop:

| Stap | Commit | Wijziging | Deelmeting |
|---|---|---|---|
| WP1 | `afdc343` | Contextblok achter flag `broncontext`, dependency-gebaseerde functiedetector, kernbewijs zonder gekopieerde herkomst | [wp1](deelmetingen/wp1-reviewpunten.json) |
| WP2 | `4bc1faa` | D04: nominalisatie alleen bij handeling met van/door-bepaling | [wp2](deelmetingen/wp2-nominalisatie.json) |
| WP3 | `740c4c0` | D03/D01: Rechtsfeit alleen met rechtsgevolg; normcontext getoetst bij generieke NP | [wp3](deelmetingen/wp3-normsignaal.json) |
| WP4a | `f1a8158` | D06: bewijssterkte afgeleid uit de regeldefinities | [wp4a](deelmetingen/wp4a-bewijssterkte.json) |
| WP4b | `8baab53` | D05: sterk patroonbewijs gaat voor een generiek NP-signaal | [wp4b](deelmetingen/wp4b-sterk-boven-generiek.json) |

Iedere deelmeting vergelijkt de ontwikkelset (16 fixtures + 2 diagnostische teksten, 81 provisional
ankers) en de vier invorderingshoofdgevallen met de vorige stap. De `.txt`-bestanden ernaast
noemen iedere gewijzigde kandidaat, klasse, bewijsbijdrage en route.

## Modelproef: opzet en vooraf vastgelegd keuzecriterium

`python -m eval.baseline_proef` (vanuit `tools/graph-qa`) scheidt de factoren die de vorige
A/B/C-proef mengde. Casussen, bronnen en snapshotafbakening zijn die van de vorige proef.

| Variant | Code | Granulariteit | Context |
|---|---|---|---|
| A | master `b8117e2` (productie vóór deze ronde) | universeel | geen |
| U0 | baseline | universeel | uit |
| K0 | baseline | klasseverzameling | uit |
| UC | baseline | universeel | `BronContext.ouders` (productiemechanisme) |
| KC | baseline | klasseverzameling | `BronContext.ouders` |

Het productiemechanisme levert alleen bij de twee Leidraad-casussen een ouderpassage (artikel 9,
78 tekens); de wetsartikelen hebben geen eigen artikeltekst. Voor de overige zes casussen is het
UC/KC-verzoek byte-identiek aan U0/K0: die pogingen worden niet dubbel uitgevoerd maar in het
manifest als `identiek_aan` vastgelegd. Drie herhalingen met geroteerde variantvolgorde: **84
primaire pogingen**, `claude-sonnet-4-6` via Azure Foundry, SDK-retries op nul.

**Keuzecriterium, vastgelegd vóór de run:**

1. `klasseverzameling` wordt de productiedefault alleen als KC ten opzichte van UC (a) minder
   contractfouten heeft (klassekeuzes buiten de toegestane ruimte), (b) op minstens 6 van de 8
   casussen een even hoge of hogere vast/unie-stabiliteit, en (c) hooguit 3× zoveel kosten per run.
   Anders blijft `universeel` de default.
2. Context blijft standaard aan. Is UC op 5 of meer casussen minder stabiel dan U0, dan wordt de
   default pas na bevestiging van de opdrachtgever vastgelegd.

`eval.baseline_proef rapport` past dit criterium mechanisch toe (`beslis`), zonder afstelling achteraf.

## Uitkomst

**Proef 1 is afgekeurd.** Het model stopte vóór de tool-aanroep op het tokenbudget: iedere
reviewaanroep van de nieuwe code en 5 van 27 U0-classificaties. Zie
[proef1-budgetdefect/BEVINDING.md](proef1-budgetdefect/BEVINDING.md). Na herstel (`eb0849e`) is
de proef met dezelfde opzet en hetzelfde criterium herhaald; proef 2 is de baseline.

**Proef 2** ([model-vergelijking.md](model-vergelijking.md)): 84/84 pogingen geslaagd, nul afgekapte
aanroepen in de nieuwe code (A: nog 3 van 28), geraamd $2,94.

| Variant | Contractfouten | Voorstellen (menselijk) | USD/run |
|---|---:|---:|---:|
| A (productie vóór deze ronde) | 22 | 342 (11) | 0,030 |
| U0 | 15 | 424 (5) | 0,027 |
| K0 | 0 | 428 (1) | 0,042 |
| UC (2 casussen) | 9 | 213 (0) | 0,038 |
| KC (2 casussen) | 0 | 210 (0) | 0,055 |

Mechanische toepassing van het criterium: KC heeft minder contractfouten (0 tegen 9), is op
**6/8** casussen minstens zo stabiel als UC (precies op de drempel) en kost **1,45×** per run.
Daarmee wordt **`klasseverzameling` de productiedefault**. Context blijft aan: UC is op één casus
minder stabiel dan U0, ruim onder de drempel van vijf.

Inhoudelijk, zonder juridische score (referentieset v1 is provisional):

- **IW 9 lid 1**: in K0 in alle runs de centrale uitspraak als Rechtsfeit, plus aanslag en
  termijn. In U0 wijst de classifier de norm af en legt de herbeoordeling haar gemotiveerd voor als
  keuze tussen Rechtsfeit en Rechtsbetrekking (`R-CENTRAAL-HUMAN`, 3×; K0 1×). Dat is precies de
  juridische vraag die open staat. Het object 'het aanslagbiljet' komt er in de baseline bij.
- **LI-9.5**: vast/unie van 24/56 (A) naar 52–56/56; U0 en UC zijn in alle runs identiek.
- Stabiliteit is geen juistheid; een voorstel meer is geen expertvaststelling.

## Ruwe runbestanden

`modelruns/` en `modelruns-proef1/` (volledige verzoeken, reacties, tokens en uitvoer per poging)
staan niet los in git maar als gecomprimeerd archief in [archief/](archief):

| Archief | SHA-256 |
|---|---|
| `hybrid-v1-baseline-2026-09-29-modelruns-proef2.tar.zst` | `2727e2b696aeb0ea258956f6e34d795f3aa6b661bca7c9d1d11bcbc0fe4069a5` |
| `hybrid-v1-baseline-2026-09-29-modelruns-proef1.tar.zst` | `8314c02dff2d0e6afd503659aea8b2fbcde0e6033d1cc03b59a49e248a877bc9` |

Uitpakken in deze map (`tar --zstd -xf archief/…`) herstelt `modelruns/`; `eval.baseline_proef
rapport` controleert daarna bronnen, code-hashes, brongetrouwheid en reproduceerbare detectie.
`model-vergelijking.json` bevat de SHA-256 van ieder runbestand.
