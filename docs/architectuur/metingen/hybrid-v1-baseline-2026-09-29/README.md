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

## Ruwe runbestanden

`modelruns/` (volledige verzoeken, reacties, tokens en uitvoer per poging) staat niet in git.
Het wordt als gecomprimeerd archief bewaard; naam en SHA-256 staan hieronder zodra de proef
klaar is. `model-vergelijking.json` bevat de SHA-256 van ieder runbestand.
