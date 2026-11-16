# Het vaste testaccount op acceptatie

Runbook bij Lex Bench §20.5 stap 5 (keten 3, voorstel 3 uit het testplan keten-e2e; bevinding O-1).

risico: R19

## Waarom

Tot nu toe draaiden de E2E en de metingen op een gedeeld account met de rol `beheerder`. Dat heeft drie gevolgen:

- de rechten van een analist zijn nooit getoetst, want een beheerder mag meer;
- het verbruik en de besluiten van een run staan door elkaar met het werk van de gebruiker;
- een bulkactie raakt andermans werk: op 10 nov 2026 wiste een bulkverwijdering een meting en een gesprek van de gebruiker.

Een vast testaccount met de rol `analist`, plus een vangrail in de acceptatie-MCP, lost dat op. Het gedeelde account
blijft bestaan en wordt niet aangeraakt.

## Wat de gebruiker op acceptatie aanmaakt

Dit doet alleen de gebruiker. Een agent maakt geen account, token of secret aan en wijzigt er geen.

1. **Een account** `acc-test-analist`, rol `analist`, zonder 2FA (een analist heeft die niet nodig). Via instellingen →
   **Beheer** → **Gebruikers**, of door een zelfregistratie goed te keuren. Het e-mailadres mag een adres zijn dat niemand
   leest, zolang het uniek is.
2. **Een accounttoken** (`wa_pat_…`) voor dat account: instellingen → **Beheer** → **API-tokens** → *Inloggen als*
   `acc-test-analist`. Het token is 90 dagen geldig en wordt één keer getoond. `API_TOKEN_LOGIN` staat op acceptatie al aan.
3. **Machine-lokaal** in `.claude/settings.local.json` (gitignored), in plaats van het token van het gedeelde account:

   ```json
   "env": {
     "WETSANALYSE_ACC_TOKEN": "wa_pat_…",
     "WETSANALYSE_ACC_TESTACCOUNT": "acc-test-analist"
   }
   ```

   `WETSANALYSE_ACC_TOKEN_BEHEERDER` blijft alleen nodig voor een scenario dat het verschil tussen de rollen toetst.

Er komt geen secret in GitHub of Azure bij, en geen wijziging aan de bicep. Na 90 dagen maakt de gebruiker een nieuw token;
het oude intrekken gaat in dezelfde tab.

## Controle vóór elke run

`wie_ben_ik` geeft naast het account het veld `testaccount`:

- `ja`: het token hoort bij het testaccount;
- `nee: het token hoort bij …`: er staat een ander token; meld dat aan de gebruiker voordat de run begint;
- `niet ingesteld`: `WETSANALYSE_ACC_TESTACCOUNT` ontbreekt; de run kan, maar dat hoort als beperking in het rapport.

## De naamconventie

Alles wat een run maakt, begint met een **runvoorvoegsel**: `acc-test-<onderwerp>-<datum>` voor de E2E en de
acceptatiescenario's, `Bench <naam>` voor Lex Bench. Dat geldt voor:

- het werkgebied (`naam`);
- elk los gesprek (`titel` bij `bff` POST `/api/gesprekken`).

Een gesprek in zo'n werkgebied of een deelgesprek onder zo'n gesprek hoort er vanzelf bij, ook als Lex de titel later
aanpast.

## De vangrail

Elke verwijderende aanroep via `bff` (een `DELETE`, of een route die op `verwijderen`, `verwijder` of `wis` eindigt)
gaat eerst langs `src/runruimte.ts`:

- **mag**: een gesprek met het voorvoegsel, of in een werkgebied of onder een gesprek van de run; een werkgebied met het
  voorvoegsel dat dit account maakte;
- **weigert altijd**: een bulkroute (`/api/gesprekken/verwijderen`, `/groep/…`), alles wat gedeeld is (een
  annotatielaag, een generiek begrip, het beheer), en alles wat niet te lezen is.

De vangrail is geen slot: de api blijft de rechten bepalen. Hij houdt een vergissing van een agent tegen, zoals die van
10 nov 2026.

## Opruimen na een run

```
opruimen { voorvoegsel: "acc-test-verrekening-2026-11-16" }                 → alleen de lijst
opruimen { voorvoegsel: "acc-test-verrekening-2026-11-16", bevestig: true } → wissen
```

Zonder bevestiging geeft de tool de lijst van werkgebieden en gesprekken. Met bevestiging wist hij eerst de gesprekken
(deelgesprekken vóór hun ouder) en dan de werkgebieden, met hun revisie, elk opnieuw langs de vangrail. Wat geweigerd
wordt, staat in `geweigerd`.

Opruimen is een keuze per run. Een meetrun waarvan het resultaat bewijs is (`docs/architectuur/metingen/`), ruim je niet
op; het verslag verwijst ernaar. Annotaties en begrippen in een gedeelde laag blijven altijd staan.
