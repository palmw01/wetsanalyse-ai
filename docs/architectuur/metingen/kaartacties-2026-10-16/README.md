# Lex naast de kaart: *Zoek de brondefinitie* – 16 oktober 2026

Soort: *meting* · Spoor D, fase E2 · Branch `feat/fase-e2-kaartacties`

## Wat er gemeten is

`agent/begrip_kaart.zoek_brondefinities`, live tegen de graaf van acceptatie, zonder model (0
modelcalls, geen kosten). Per case een werkgebied (selecties) en een begrip; verwacht zijn de
bepalingen die de term definiëren, met de plaats die Lex ze moet geven: in het werkgebied, in een
regeling van het werkgebied, in een regeling waar een begripsbepaling van het werkgebied naar verwijst
(*definitieverwijzing*), of elders.

Set: `tools/graph-qa/eval/kaartacties_brondefinitie.json`, acht cases rond IW 1990 art. 2 en 9, AWR
art. 2 en de Uitvoeringsregeling. **Een ontwikkelset**: opgesteld tijdens de bouw uit de graaf zelf, niet
door een jurist vastgesteld. De uitkomst zegt dat het mechanisme doet wat het moet doen, niet dat het
generaliseert.

```
cd tools/graph-qa
GRAPHDB_MCP_URL=… GRAPHDB_TOKEN=… uv run python -m eval.kaartacties_eval --json <pad>
```

## Uitkomst

| maat | waarde |
|---|---|
| recall (verwachte definities als voorstel) | 1,00 |
| plaats goed | 1,00 (9/9) |
| volgorde sterk → zwak | 1,00 |
| letterlijk in de bron (garantie) | 1,00 |

Gegevens: [`brondefinitie.json`](brondefinitie.json).

## Wat de meting veranderde

De eerste run gaf recall 0,25. Twee oorzaken, allebei in de set en niet in de code:

1. De IRI's in de set waren verminkt: de fish-shell las `$IW:a…` als variabele met modifier. De set wordt
   nu met Python geschreven.
2. IW art. 2 lid 2 ("Deze wet verstaat **mede** onder") stond als verwachte definitie in de set. Dat is
   een uitbreiding, geen definitie (PLAN §D: inclusie is geen synoniem), en `definities.definiens` neemt
   haar terecht niet over. Wel bleef Lex dan stil met een vage melding. Nu zegt hij het
   (`kaartacties.geen_definitie_melding`): "De wet breidt “aanslagbiljet” alleen uit … in Artikel 2, lid 2,
   onderdeel d – Invorderingswet 1990; dat is geen definitie om over te nemen."

## Niet gemeten

De drie model-acties (scherpere definitie, betekenisverschil, voorbeelden). Hun garanties (fragmenten op
id, letterlijkheid, cirkel verworpen, het api-contract) liggen vast in `tests/test_begrip_kaart.py` en
worden door de api opnieuw getoetst; of de voorstellen inhoudelijk deugen, beoordeelt de jurist bij de
acceptatie op acc, na E3.
