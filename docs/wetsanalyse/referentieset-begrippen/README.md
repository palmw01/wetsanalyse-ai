# Referentieset begrippen

Soort: *meting* (referentie) · Hoort bij: [ADR-004](../../architectuur/adr-004-begrippenketen.md)

De meetlat voor de begrippenketen: welke formuleringen duiden hetzelfde begrip aan, welke staan
in een andere relatie, en welke lijken op elkaar maar zijn het níét. Per versie een map
`v<N>/` met:

| Bestand | Inhoud |
|---|---|
| `bronnen.json` | letterlijke wettekst per bronnode, met `bron_hash` (sha256) en de aanhef van de houder |
| `cases.json` | formuleringen (ankers in die bronnen) en paren met relatie, categorie en motivatie |
| `manifest.json` | versie, status en een hash over bronnen + cases |

Controle en meten: `cd tools/graph-qa && uv run python -m eval.begrippen_eval --check` en
`--variant lemma|keten`. Zie de docstring van `eval/begrippen_eval.py` voor de maten.

## Sets

| set | regeling | rol | status |
|---|---|---|---|
| `v1` | Invorderingswet 1990 | ontwikkelset (regels erop gebouwd) | provisional |
| `heldout-v1` | Awir | blind gemeten, daarna **ontwikkelset** (reparaties erop gebaseerd) | provisional |
| `heldout-v2` | AWR | held-out, **één keer** blind gemeten na de Awir-reparaties; één gouden paar daarna gecorrigeerd | provisional |

Een set die gebruikt is om regels te verbeteren, zegt daarna niets meer over generalisatie. Wie
regels toevoegt op basis van `heldout-v2`, maakt een nieuwe held-out set. De metingen staan in
[`../../architectuur/metingen/begrippen-heldout-2026-10-14/`](../../architectuur/metingen/begrippen-heldout-2026-10-14/README.md).

## v1 (14 okt 2026) — status `provisional`

25 formuleringen uit art. 2 en 9 Invorderingswet 1990 en 22 paren. De teksten komen uit de
kennisgraaf (acceptatie). Elke `bron_hash` is vergeleken met `SHA256()` in de graaf zelf.

De set is samengesteld rond de gevallen waar "zelfde woord = zelfde begrip" faalt:

- **soorten in een opsommende definitie**: "de aanslag" en "de navorderingsaanslag" zijn soorten
  belastingaanslag (art. 2 lid 1 m), geen synoniemen;
- **uitbreiding**: "verstaat mede onder" (lid 2) breidt een begrip uit, het blijft één begrip;
- **gelijkstelling**: "met een belastingaanslag gelijkgestelde beschikking" is een kwalificatie;
- **afwijking**: lid 3 bepaalt "in afwijking van" de eerste twee leden wat als belastingaanslag
  geldt;
- **homoniem**: "termijnen" in art. 9 lid 5 (betalingstermijnen) en lid 10 (de gestelde termijnen);
- **verwijzing**: "die belastingaanslag" en "bedoeld in onderdeel c" wijzen terug.

**Gaten:** geen uitsluiting ("wordt niet verstaan") en geen synoniemen met een ander woord binnen
deze artikelen. **Opgesteld zonder jurist.** De relaties zijn een eerste duiding. Adjudicatie
volgt het protocol van spoor A; pas daarna mag de set `adjudicated` heten.

Nulmeting (`--variant lemma`, groeperen op de formulering zonder lidwoord): zelfde betekenis
P = R = 0,73, BCubed F 0,89, twee verschillende paren samengevoegd (f01~f22, f18~f19), en geen
relaties.
