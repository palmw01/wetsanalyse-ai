# Testen op acceptatie met het account van de gebruiker

Runbook bij Lex Bench §20.5 stap 5 (keten 3, voorstel 3 uit het testplan keten-e2e; bevinding O-1).

risico: R19

## Het besluit

Er komt geen apart testaccount. Tests op acceptatie draaien op het account van de gebruiker, met hetzelfde accounttoken
(`wa_pat_…`) waarmee de acceptatie-MCP inlogt (besluit gebruiker, 16 nov 2026).

**Dat account is echt.** Er staan eigen gesprekken en metingen op, en op 10 nov 2026 wiste een bulkverwijdering er een
meting en een gesprek. Daarom gelden er drie regels voor elke test, elk scenario en elke agent:

1. **Maak alleen eigen objecten, met een herkenbaar voorvoegsel.**
   - `lex-bench-keten · <run>` voor het ketenscenario in CI;
   - `acc-test-<onderwerp>-<datum>` voor de E2E;
   - `Bench <naam>` voor Lex Bench.

   Het voorvoegsel staat in de naam van het werkgebied en in de titel van elk los gesprek. Een gesprek in zo'n werkgebied
   of onder zo'n gesprek hoort er vanzelf bij.
2. **Ruim alleen die op.** Je verwijdert niets wat de test niet zelf maakte, ook niet als het er "oud" uitziet.
3. **Verwijder nooit in bulk.** Geen `/api/gesprekken/verwijderen`, geen `/groep/…`, en niets wat gedeeld is (een
   annotatielaag, een generiek begrip, het beheer).

De code dwingt dat af, en tests bewaken het:

- de vangrail en `opruimen` in de acceptatie-MCP (`src/runruimte.ts`, `src/runruimte.test.ts`);
- het ketenscenario (`src/keten.ts`, `src/keten.test.ts`): het telt wat er vóór het scenario stond, en faalt als daar
  na het opruimen iets van ontbreekt;
- de workflow (`tests/poort/test_acceptatie_keten.py`).

## Lokaal en via de MCP

Gebruik de bestaande acceptatie-MCP met het token dat al machine-lokaal in `.claude/settings.local.json` staat. Je leest
of kopieert het token nergens heen.

Optioneel zet je daar `WETSANALYSE_ACC_ACCOUNT` op de userid van het account. Dan meldt `wie_ben_ik` in
`account_verwacht` of het token bij dat account hoort.

## In CI: `acceptatie-keten`

De workflow `.github/workflows/acceptatie-keten.yml` draait na elke geslaagde publish van api, frontend of graph-qa, of
met de hand, en nooit op een pull request. Het scenario werkt zonder model, dus er gaan geen tokens op. Het doet dit:

1. inloggen met het accounttoken;
2. een werkgebied en een gesprek maken, met het voorvoegsel `lex-bench-keten · gh-<run-id>-<poging>`;
3. ze teruglezen;
4. de vangrail toetsen op een gesprek van de gebruiker en op de bulkroute (alleen een oordeel, er gaat geen DELETE uit);
5. precies die twee objecten opruimen;
6. nagaan dat er verder niets verdwenen is.

**Wat de gebruiker zet:** het environment-secret **`WA_ACC_TOKEN`** in de GitHub-environment `acceptatie`, met het
accounttoken. Meer is niet nodig. De URL komt uit Azure (de ingress van `<APP_NAME>-frontend`) en wordt in de log
gemaskeerd.

**Zonder dat secret** meldt de job `voorwaarde` dat in een regel, en wordt de job `keten` overgeslagen: grijs, niet groen.
Een ontbrekende Azure-credential laat de job falen.

**Na 90 dagen** verloopt het token. Maak dan een nieuw via instellingen → **Beheer** → **API-tokens**, en zet het zowel
machine-lokaal als in `WA_ACC_TOKEN`.

## Opruimen na een eigen run

```
opruimen { voorvoegsel: "acc-test-verrekening-2026-11-16" }                 → alleen de lijst
opruimen { voorvoegsel: "acc-test-verrekening-2026-11-16", bevestig: true } → wissen
```

- Zonder bevestiging geeft de tool alleen de lijst van werkgebieden en gesprekken.
- Met bevestiging wist hij eerst de gesprekken (deelgesprekken vóór hun ouder) en dan de werkgebieden, elk met zijn
  revisie en elk opnieuw langs de vangrail. Wat geweigerd wordt, staat in `geweigerd`.
- Een meetrun waarvan het resultaat bewijs is (`docs/architectuur/metingen/`), ruim je niet op: het verslag verwijst ernaar.
- Annotaties en begrippen in een gedeelde laag blijven altijd staan.
