# Lex Bench

Soort: *meting* (referentie) · Plan: [`../architectuur/plan-lex-bench.md`](../architectuur/plan-lex-bench.md)

Lex Bench is de kwaliteitslaag naast Lex: per meetas een geordende set, met een mens die de verwachting vaststelt. De
score is een hulpmiddel, geen poort. Zolang geen jurist een verwachting vaststelt, heet elke uitkomst een trendmeting
(besluit 2, §22).

## Wat er nu staat

- **Bronselectie: het manifest en de scorekaart van arm L1 (LB1)** — [`bronselectie/manifest.json`](bronselectie/manifest.json)
  (`bench-bronselectie-v1`: de zes bestaande ontwikkelsets, niveau voorlopig, verwachting `concept`, nog niemand
  vastgesteld) en [`bronselectie/casus-schema-4.json`](bronselectie/casus-schema-4.json). Een run zonder model:
  `cd tools/graph-qa && uv run python -m eval.lex_bench --l1 <naam>`; hij gaat als meetmap naar
  `docs/architectuur/metingen/lex-bench-<datum>-<naam>/`. Het nulpunt: [`lex-bench-2026-11-17-nulpunt`](../architectuur/metingen/lex-bench-2026-11-17-nulpunt/).
  De poort toetst de vorm (`tests/poort/test_lex_bench.py`), nooit de score.
- **Het dashboard** — [`../../tools/lex-bench/`](../../tools/lex-bench/): een statische pagina in de stijl van Lex, met de
  scorekaart, het verloop per versie, de verschillen per categorie en de risicomatrix. Bijwerken met
  `uv run python -m eval.lex_bench --dashboard`. De workflow `lex-bench.yml` en de voortgangspagina (de rest van LB6)
  volgen later.

- **Het team, arm T (LB2)** — het profiel [`bench-analist`](../../.claude/agents/bench-analist.md) met een allowlist
  (`bron_lezen`, `graaf_lezen`, het eigen logboek en de skill; geen Lex en geen repo), de
  [briefing](briefing-analist.md) en het [formulier](bronselectie/formulier-analist.json). De opdracht van een analist en
  de controle van zijn formulier, en het samenvoegen van A en B tot de bevroren teamverwachting:
  `uv run python -m eval.lex_bench_team opdracht|controleer|samenvoegen`. Er draait nog geen analist:
  dat is de pilot LB3, met een eigen akkoord. De poort toetst de allowlist (`tests/poort/test_lex_bench_team.py`).

- **Bronselectie: de uitkomst op de (vroegere) blinde sets** — [`bronselectie/held-out.json`](bronselectie/held-out.json).
  Per set de uitkomst bij haar ene blinde meting, met de regel in het meetlogboek. Vergelijken met de code van nu, offline
  en zonder model: `cd tools/graph-qa && uv run python -m eval.lex_bench`. Het script faalt niet op een verschil. Deze
  uitkomsten stonden eerder als pin in `tests/evals/test_bronselectie_eval.py`; daar toetst de suite nu alleen het pad en de vorm
  (plan §4.5, §20.4).

## Wat er nog niet staat

- de twintig casussen (er staan er nu zes);
- de reviewer (rest van LB2) en de pilot (LB3);
- de risicomarkers en de traceerbaarheidsmatrix (§21);
- de workflow `lex-bench.yml` en de voortgangspagina (§6, LB6);
- de meetassen annotatie, begrippen en afleidingsregels (§8).
