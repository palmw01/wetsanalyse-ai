# wetsanalyse-acceptatie-mcp

Een **stdio-MCP-server** die de webapp op acceptatie bedient zoals een gebruiker dat doet, zodat een
MCP-client (Claude Code) een acceptatietest van begin tot eind kan doen zonder schermen aan te raken.

De acties van de gebruiker lopen via de **BFF**. De MCP wisselt een accounttoken in voor een gewone sessie, dus er gelden
dezelfde controles als voor een gebruiker: sessie, rol, eigenaarschap en tokenbudget. De BFF is ook de
enige publieke weg naar graph-qa. De rendering test dit niet: dat doet Playwright op een gemockte BFF.

`src/client.ts` kent geen MCP, zodat scenario's die later ook los kunnen gebruiken; `src/index.ts` is de
dunne laag met de tools. `src/bron.ts`, `src/graaf.ts`, `src/logs.ts` (via Grafana) en `src/logboek.ts` staan
buiten de BFF: ze dienen de beoordeling en de samenwerking, en doen niets wat een scherm hoort te doen.

De agent-jurist en de agent-gegevensspecialist (`.claude/agents/`) gebruiken deze MCP om op acceptatie samen een
wetsanalyse uit te voeren, inclusief echte beslissingen; het scenario staat in
[`docs/acceptatie/wetsanalyse-e2e.md`](../../docs/acceptatie/wetsanalyse-e2e.md), de briefing in
[`docs/acceptatie/briefing-team.md`](../../docs/acceptatie/briefing-team.md).

## Tools

| tool | wat |
|---|---|
| `wie_ben_ik` | het account en de rol |
| `bff` | één aanroep op een BFF-route; elke status komt terug, met een `trace_id` |
| `lex_start`, `lex_wacht`, `lex_stop` | een beurt van Lex starten, volgen en stoppen; een klik is `intake_actie` of `actie` |
| `werkgebied_lezen` | dossier, dekking, elementen en audit van een werkgebied |
| `annotatie_lezen` | één element met klasse, ankers, bron en graaf |
| `begrip_lezen` | een begrip met revisies, of alle begrippen van een werkgebied met conformiteit en samenhang |
| `logs_zoek` | de keten op `trace_id`, de logregels op `run_id`, of de fouten; alleen vaste queries |
| `bron_lezen` | de officiële XML en tekst van één artikel of lid, met de toestand en de url |
| `graaf_lezen` | alleen-lezen SPARQL op de kennisgraaf van acceptatie, om te vergelijken met de bron |
| `logboek_aanvullen`, `logboek_lezen` | het gedeelde logboek van een run: alleen aanvullen, en lezen vanaf een stand |

De tools tot en met `begrip_lezen` nemen optioneel `als: "beheerder"`. `lex_wacht` wacht hooguit 110 seconden; bij `klaar: false`
loopt de run door en vraag je opnieuw met de teruggegeven `vanaf`.

Inloggen met een wachtwoord kan hier niet: de client blokkeert dat. Tokens maken en wachtwoord of 2FA wijzigen
kan evenmin: dat weigert de server voor een sessie uit een accounttoken.

## Bron, graaf en logboek

**`bron_lezen`** volgt de weg van de importer: de SRU-zoekdienst noemt de toestanden, de repository
(`repository.officiele-overheidspublicaties.nl`) levert de XML. Het geeft één artikel of lid, omdat een hele wet niet in
de context van een agent hoort; het nummer `artikel` is verplicht. Zonder `peildatum` krijg je de nieuwste toestand,
dezelfde die de importer in de graaf zet. De SRU-dienst geeft HTTP 406 bij een geldig antwoord, dus de inhoud beslist
en niet de status. Er is één eerlijke aanroep: een eigen User-Agent, geen tweede poging en geen redirect. Is het
antwoord geen XML, bijvoorbeeld door een botcontrole, dan komt dat terug als fout om te melden, niet om te omzeilen.

De uitvoer van `bron_lezen` en `graaf_lezen` wordt afgekapt op 40.000 tekens.

**`graaf_lezen`** gaat via de MCP-proxy van acceptatie. Alleen `SELECT`, `ASK`, `CONSTRUCT` en `DESCRIBE`; update-woorden
en `SERVICE` worden geweigerd, en zonder `LIMIT` komt er `LIMIT 200` bij (niet bij `ASK`). De controle staat op de tekst, na het
weghalen van literals, IRI's en commentaar, zodat een wettekst met het woord "delete" gewoon kan. Dat houdt een
vergissing tegen en is geen slot: de proxy is dat wel, met zijn token.

**Het logboek** staat in `docs/acceptatie/lokaal/<run>/logboek.md`. Dit is de enige schrijfweg van de agents: ze hebben
geen `Write`, `Edit` of `Bash`, en dat blijft zo. Een shell zou elk bestand kunnen overschrijven en maakt omwegen om de
BFF makkelijk; de MCP legt het pad vast, opent in append-modus, en houdt de run-naam binnen de map. Het schrijft in de
hoofdcheckout, ook als de sessie in een worktree draait, omdat een worktree wordt opgeruimd en het dossier daar niet
staat. Een onenigheid vraagt beide argumenten, en iets wat op een token lijkt wordt geweigerd.

## Activeren

Op de straat moet `API_TOKEN_LOGIN` aanstaan; `azure-infra` zet die alleen op acceptatie aan.

1. Kies een testaccount. Eén account voor beide agents kan; `WETSANALYSE_ACC_TOKEN_BEHEERDER` is alleen nodig om
   beheerrechten of het verschil tussen rollen te testen.
2. Genereer een token: instellingen → **Beheer** → **API-tokens** → kies bij *Inloggen als*
   het account. Het token is 90 dagen geldig en wordt één keer getoond. Staat `API_TOKEN_LOGIN` uit, dan
   weigert de api het (409).
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

Voor `graaf_lezen` komen daar `WETSANALYSE_ACC_GRAAF_URL` en `WETSANALYSE_ACC_GRAAF_TOKEN` bij: de MCP-proxy van
acceptatie (`azure-infra` → `graphdb_proxy: true`) met het token uit `WA_GRAPHDB_PROXY_TOKEN`. `bron_lezen` en het
logboek hebben geen configuratie nodig. Deze waarden zet de gebruiker: de agents halen geen wachtwoorden of tokens op.

Zonder URL en analist-token weigert de server te starten, en een URL van de productiestraat ook; die
controle kijkt alleen naar `prd` in de hostnaam.

## Bouwen en testen

Vereist Node ≥ 20.3.

```bash
cd tools/wetsanalyse-acceptatie-mcp
npm install
npm test
npm run build      # → dist/ (gecommit, zodat `node dist/index.js` zonder buildstap werkt)
```
