# wetsanalyse-acceptatie-mcp

Een **stdio-MCP-server** die de webapp op acceptatie bedient zoals een gebruiker dat doet, zodat een
MCP-client (Claude Code) een acceptatietest van begin tot eind kan doen zonder schermen aan te raken.

Alles loopt via de **BFF**. De MCP wisselt een accounttoken in voor een gewone sessie, dus er gelden
dezelfde controles als voor een gebruiker: sessie, rol, eigenaarschap en tokenbudget. De BFF is ook de
enige publieke weg naar graph-qa. De rendering test dit niet: dat doet Playwright op een gemockte BFF.

`src/client.ts` kent geen MCP, zodat scenario's die later ook los kunnen gebruiken; `src/index.ts` is de
dunne laag met de tools.

## Tools

| tool | wat |
|---|---|
| `wie_ben_ik` | het account en de rol |
| `bff` | één aanroep op een BFF-route; elke status komt terug, met een `trace_id` |
| `lex_start`, `lex_wacht`, `lex_stop` | een beurt van Lex starten, volgen en stoppen; een klik is `intake_actie` of `actie` |
| `werkgebied_lezen` | dossier, dekking, elementen en audit van een werkgebied |
| `annotatie_lezen` | één element met klasse, ankers, bron en graaf |
| `begrip_lezen` | een begrip met revisies, of alle begrippen van een werkgebied |
| `logs_zoek` | de keten op `trace_id`, de logregels op `run_id`, of de fouten; alleen vaste queries |

Elke tool behalve `logs_zoek` neemt optioneel `als: "beheerder"`. `lex_wacht` wacht hooguit 110 seconden; bij `klaar: false`
loopt de run door en vraag je opnieuw met de teruggegeven `vanaf`.

Inloggen, tokens maken en wachtwoord of 2FA wijzigen kan hier niet: dat weigert de server voor een sessie
uit een accounttoken ook.

## Activeren

Op de straat moet `API_TOKEN_LOGIN` aanstaan; `azure-infra` zet die alleen op acceptatie aan.

1. Maak in de webapp een account `acc-analist` en eventueel `acc-beheerder`.
2. Genereer per account een token: instellingen → **Beheer** → **API-tokens** → kies bij *Inloggen als*
   het account. Het token is 90 dagen geldig en wordt één keer getoond.
3. Zet machine-lokaal, in `.claude/settings.local.json` (gitignored):

   ```json
   "env": {
     "WETSANALYSE_ACC_URL": "https://…",
     "WETSANALYSE_ACC_TOKEN": "wa_pat_…",
     "WETSANALYSE_ACC_TOKEN_BEHEERDER": "wa_pat_…"
   }
   ```

4. Registreer de server, ook machine-lokaal, want de repo is publiek:

   ```bash
   claude mcp add wetsanalyse-acceptatie -- node tools/wetsanalyse-acceptatie-mcp/dist/index.js
   ```

Voor `logs_zoek` komen daar `WETSANALYSE_ACC_GRAFANA_URL` en `WETSANALYSE_ACC_GRAFANA_WACHTWOORD` bij: de
Grafana van `azure-infra` → `grafana`, met het wachtwoord uit `WA_GRAFANA_ADMIN_PASSWORD`. Die tool leest via
de datasource van acceptatie, zodat er geen Azure-secret op je machine hoeft te staan.

Zonder URL en analist-token weigert de server te starten, en een URL van de productiestraat ook.

## Bouwen en testen

```bash
cd tools/wetsanalyse-acceptatie-mcp
npm install
npm test
npm run build      # → dist/ (gecommit, zodat `node dist/index.js` zonder buildstap werkt)
```
