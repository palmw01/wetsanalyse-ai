# Wijzigingen in de ontologieën

Eén versie per ontologie, in `versies.json`. Verandert een bron (T-Box, shapes of vocabulaire), dan verhoog je de
versie daar, schrijf je hieronder een kop `## <ontologie> <versie>` met wat er veranderde, en draai je
`tools/graph-qa/scripts/genereer_ontologie_docs.py`. Zonder die stappen wordt de drift-test rood.

Versienummers: de JAS-versie volgt het projectieschema (`jas:schemaVersie 4`), de WA-versie de schemaversie van de
begrippenprojectie (`wa:schemaVersie 3`). Een nieuwe verplichte eigenschap of een weggehaalde term is een nieuwe
hoofdversie; een nieuwe optionele term of een strengere waardelijst een nieuwe tussenversie; uitleg alleen een
nieuwe patchversie.

## bwb 1.0.0

27 nov 2026. Eerste vastgelegde versie: de T-Box uit `ontology.py` met ELI-aansluiting en de shapes `bwb-graaf.ttl`
(veertien regelingen, droogloop 26 nov 2026).

## jas 4.0.0

27 nov 2026. Projectieschema 4 (ADR-011): relaties tussen markeringen en impliciete partijen, met de shapes
`jas-v2.ttl`.

## wa 3.0.0

27 nov 2026. Schema 3 van de begrippenprojectie: begrippenkader (NL-SBB), koppelingen, begripsrelaties en de
afleidingsregels in de graph van het werkgebied. Eerste declaratie van de eigen termen in `wa-vocabulaire.ttl`
(alleen documentatie).

## kgo 1.0.0

27 nov 2026. Eerste declaratie van de termen van de kennisgroepenindex in `kg-vocabulaire.ttl` (alleen
documentatie). Er zijn geen shapes.
