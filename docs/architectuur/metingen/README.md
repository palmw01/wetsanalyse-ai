# Meetlogboek

Soort: *meting* (zie [`../../README.md`](../../README.md)) · Bijgewerkt: 29 september 2026

Hier staat per datum wat er gemeten is, op welke code, wat eruit kwam en waar de gegevens staan.
Nieuwste bovenaan. De meetbestanden zelf zijn bewijs: **wijzig ze niet achteraf**. Een correctie
of herhaling krijgt een eigen map of rij. Hoe de keten nu werkt, staat in
[`../annotatieketen.md`](../annotatieketen.md), en welke meting er nog moet komen in
[`../../PLAN.md`](../../PLAN.md), spoor A.

> **Nog geen enkele meting hieronder is een juridisch oordeel.** Referentieset v1 is
> *provisional*: er zijn 0 casussen `adjudicated`. "Recall" is hier ankerdekking tegen
> conceptmarkeringen. Stabiliteit, contractfouten en aantallen voorstellen zeggen iets over het
> mechanisme, niet over juistheid. Dat verandert pas met V7.

## Logboek

| Datum | Meting | Code | Uitkomst in één regel | Gegevens |
|---|---|---|---|---|
| 29 sep | **Baseline `hybrid_v1`**, het huidige vertrekpunt. Deelmetingen WP1–WP4b (auditpunten D01, D03–D06) en een modelproef met vijf varianten (84 pogingen, 3 herhalingen) | R0 `e8c1603`, daarna `afdc343`…`8baab53` | Proef 1 afgekeurd (tokenbudget). Proef 2: `klasseverzameling` wordt de default (0 contractfouten tegen 9, 6/8 casussen stabiel, 1,45× kosten); broncontext blijft aan | [`hybrid-v1-baseline-2026-09-29/`](hybrid-v1-baseline-2026-09-29/README.md) |
| 29 sep | **Invorderingsvervolg** A01–A10: datums zonder jaartal, termijnfuncties, tijdkern, centrale afwijzing, broncontext. 8 casussen × 3 varianten × 3 herhalingen (72 pogingen) | `b8117e2` → `b190841`, `4fb25f5`, `a0699a5` | Gemiste datum- en berekeningsfuncties zijn bereikbaar; B/C geven bij IW 9 lid 1 steeds dezelfde drie voorstellen. Geen bewijs van juridische winst | [`hybrid-v1-invordering-vervolg-2026-09-29/`](hybrid-v1-invordering-vervolg-2026-09-29/README.md) |
| 29 sep | **Onderzoek invordering**: vier bepalingen (IW 9 lid 1 en 5, Leidraad §9.1 en §9.5), 60 conceptonderzoeksitems, eisenmatrix | onderzoeksvoorzieningen, geen productiewijziging | De centrale invorderbaarheidsuitspraak wordt gedetecteerd maar afgewezen zonder review; datums zonder jaar en termijnberekening ontbreken | [`../../wetsanalyse/onderzoek-invordering-2026-09-29/`](../../wetsanalyse/onderzoek-invordering-2026-09-29/README.md)¹ |
| 29 sep | **Tekststructuur**: beschermde grenzen, onderdelen op één regel, detectorresultaatcontract (F05–F07). 18 bronnen, 0 modelcalls | voor `32faeae` | Kandidaten, ankers en routing gelijk (262; 73/81); alleen vier alternatieve zinspans veranderen | [`hybrid-v1-tekststructuur-2026-09-29/`](hybrid-v1-tekststructuur-2026-09-29/) |
| 27 sep | **Detectoraudit en freeze**: F01–F04 vóór baseline, 16 cases, 81 provisional ankers, generic-NP-ablatie S0–S2, 0 modelcalls | `9de9922` → freeze `3b51186` | 296 → 293 ruwe uitkomsten, 265 → 262 kandidaten, ankerdekking gelijk (73/81). Generic NP draagt 6 kernankers, maar blokkeerde 3 regelbesluiten | [`hybrid-v1-freeze/`](hybrid-v1-freeze/) (manifest met alle versies en hashes) |
| 25 sep | **A/B legacy tegen `hybrid_v1`**, 16 casussen × 3 herhalingen | #508, fixes PR 17 | F1 39% → 49%, ankerdekking 47% → 84%; de spankeuze van het model was de grootste foutbron en gaat uit | [`2026-09-25-ab-legacy-hybrid.md`](2026-09-25-ab-legacy-hybrid.md) |
| 12 sep | **Methode 2.1** in de legacy-keten: promptvergelijking (24 + 6 aanvragen) en skillimport (8 ketens) | legacy-keten, sindsdien verwijderd | Protocol 2.1 houdt de normzin bij elkaar (IW01 0/3 → 3/3); de dubbele tijd/parameter-duiding is niet opgelost | [`2026-09-12-methode-2.1/`](2026-09-12-methode-2.1/README.md) |

¹ Deze map staat buiten `metingen/`. Testcode en eval-scripts gebruiken het pad
(`test_invordering_verbeteringen.py`, `eval/onderzoek_invordering.py`,
`eval/invordering_proef.py`), en de meetbestanden van het invorderingsvervolg leggen hun hashes op
dat pad vast. Verplaatsen zou dat bewijs breken.

## Meten en reproduceren

Vanuit `tools/graph-qa`:

| Doel | Commando | Modelcalls |
|---|---|---|
| Detectie en fusie tegen een eerdere stand | `.venv/bin/python -m eval.detector_audit --json /tmp/x.json --vergelijk <meting.json>` | 0 |
| Keten tegen referentie, met stabiliteit | `.venv/bin/python -m eval.compare_pipelines --output /tmp/ab.json [--cases …] [--herhalingen 3]`, daarna `--analyseer /tmp/ab.json --md /tmp/ab.md` | betaald; weigert held-out |
| Variantmatrix met een vooraf vastgelegd criterium | `.venv/bin/python -m eval.baseline_proef` (en `rapport`) | betaald |
| Rapport per laag, familie en tekstsoort | `eval/laagrapport.py` op een run-set van `compare_pipelines` | 0 |
| Referentieset controleren | `python -m eval.referentieset --check` / `--dekking` | 0 |

Regels voor een nieuwe meting:
- leg de commit, het image of `AGENT_VERSION`, het model, de provider, de referentiesetversie en de
  bronhashes vast;
- gebruik een echte spaCy-parse;
- legt de meting een keuze vast, bepaal het criterium dan vóór de run;
- geef elke meting een eigen map `<onderwerp>-<datum>/` met een `README.md`, en voeg hier een rij toe.
