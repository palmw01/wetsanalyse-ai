# Lex Bench

Soort: *meting* (referentie) · Plan: [`../architectuur/plan-lex-bench.md`](../architectuur/plan-lex-bench.md)

Lex Bench is de kwaliteitslaag naast Lex: per meetas een geordende set, met een mens die de verwachting vaststelt. De
score is een hulpmiddel, geen poort. Zolang geen jurist een verwachting vaststelt, heet elke uitkomst een trendmeting
(besluit 2, §22).

## Wat er nu staat

- **Bronselectie: de uitkomst op de (vroegere) blinde sets** — [`bronselectie/held-out.json`](bronselectie/held-out.json).
  Per set de uitkomst bij haar ene blinde meting, met de regel in het meetlogboek. Vergelijken met de code van nu, offline
  en zonder model: `cd tools/graph-qa && uv run python -m eval.lex_bench`. Het script faalt niet op een verschil. Deze
  uitkomsten stonden eerder als pin in `tests/test_bronselectie_eval.py`; daar toetst de suite nu alleen het pad en de vorm
  (plan §4.5, §20.4).

## Wat er nog niet staat

- het manifest en het casusschema van LB1, en de twintig casussen;
- het blinde agententeam (LB2) en de pilot (LB3);
- de risicomarkers en de traceerbaarheidsmatrix (§21);
- het dashboard in `tools/lex-bench/` (§6);
- de meetassen annotatie, begrippen en afleidingsregels (§8).
