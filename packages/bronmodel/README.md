# wetsanalyse-bronmodel

Gedeeld Python-pakket van de [API](../../api/README.md) en [graph-qa](../../tools/graph-qa/README.md):
de canonieke bronboom, snapshot-ID's, teksthashes, lokale tekstankers en het contract van de
antwoordsjablonen. Het staat apart zodat beide
diensten dezelfde bronidentiteit afleiden. Het pakket praat zelf niet met de graaf (de aanroeper geeft
de query-functie mee) en neemt geen modelbeslissingen.

Pakketnaam `wetsanalyse-bronmodel`, import `bronmodel`. Python ≥ 3.11; de enige runtime-afhankelijkheid is `pydantic`.

## Wat erin zit

| Module | Inhoud |
|---|---|
| `bronmodel` (`__init__.py`) | De bronboom: `bron_query`, `parse_rows`, `bouw_snapshot`, `resolve`, `subtree`. De ankers: `eigenaar`, `valideer_ankers`, `tekst_hash`. Annotatie-eenheden: `annotatie_eenheden`, `gedeelde_bepaling`, `onderdelen_om_te_kiezen`. Fouten: `BronFout`, `BronKeuze`. |
| `bronmodel.antwoord` | Het antwoord als sjabloon, het contract tussen agent, api en werkplek ([ADR-008](../../docs/architectuur/adr-008-antwoordsjablonen.md)). |
| `bronmodel.corpus` | Spans over de tekst van meer bronnodes: `CorpusMap`, `CorpusSegment`, `Span`, `SpanFout`, `SCHEIDING`. |
| `bronmodel.vindplaats` | Van graaf-IRI of jci naar de vindplaats: `vindplaats`, `Vindplaats`. |
| `bronmodel.definities` | Het geldingsbereik van een wettelijke definitie: `geldigheid_uit`, `Geldigheid`, `losse_termen`, `term_vindplaats`. |

## Wat je niet mag breken

Een wijziging hier raakt de identiteit van bestaande annotatielagen.

- **Offsets zijn Unicode-codepoints** binnen het exacte tekstliteral van een node. Nummers en labels
  worden niet in die tekst geplakt.
- **`snapshot_id` hasht `PLEK` niet** (`vindplaats`, `bepaling`): de plek mag veranderen zonder dat de
  bronstand verandert.
- **Geen labelopmaak in dit pakket.** Die zou de snapshot-identiteit van bestaande lagen raken; de API
  doet dat zelf.

## Wie het gebruikt

- `api/` en `tools/graph-qa/` als path-dependency. Beide images kopiëren het pakket, en daarom is de
  projectroot hun bouwcontext.
- De frontend spiegelt twee stukken in TypeScript: `vindplaatsVan` in `frontend/lib/samenhang.ts`
  (vectoren in `frontend/lib/jci-vectoren.json`, getoetst door
  `tools/graph-qa/tests/test_vindplaats.py`) en de bronhash (vectoren in
  `frontend/lib/bronHash.vectoren.json`, getoetst door `tools/graph-qa/tests/test_gedeelde_laag.py`).

## Testen

Het pakket heeft geen eigen suite. De tests staan bij de afnemers: `api/tests/test_bronmodel.py`,
`api/tests/test_bronmodel_corpus.py` en de suites van api en graph-qa. Een wijziging hier laat de
poort en de pre-push-hook beide suites draaien en bouwt beide images.

Na een merge die dit pakket raakt, in een bestaande omgeving van graph-qa:

```bash
uv sync --reinstall-package wetsanalyse-bronmodel
```
