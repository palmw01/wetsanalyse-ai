# Annotaties op bronnodes (contract 2)

Een verzoek om artikel 9 lid 1 toont en annoteert uitsluitend die bestaande bronnode en haar kinderen. De API en graph-qa gebruiken `packages/bronmodel` om dezelfde bronboom, teksthashes en lokale posities af te leiden. Er is geen terugval naar het hele artikel als een lid ontbreekt. De oorspronkelijke BWB-graaf blijft ongewijzigd.

## Eigenaarschap en tekst

Een laag hoort bij één canonieke bron-IRI. Een element heeft één stabiel ID en één of meer geordende, niet-overlappende ankers. Elk anker bevat de bron-IRI, de SHA256 van de exacte UTF-8-tekst, het letterlijke fragment en start/eind als Unicode-codepoints. De frontend vertaalt DOM-posities in UTF-16 naar die codepoints. De eigenaar is de diepste gezamenlijke bestaande voorouder van alle ankers. Bij verplaatsing blijft het element-ID behouden.

Een weergave omvat alleen de gekozen subtree. Elementen met ankers die deels buiten de selectie vallen verschijnen als verwijzing naar hun eigenaar; ze tellen niet mee als lokaal beoordeelbare elementen. Er is geen knop die ongemerkt de selectie tot het artikel verbreedt. JSON-, CSV- en PDF-export gebruiken dezelfde selectie.

Snapshots bevatten de hele canonieke bronboom. De snapshot-ID hangt niet van de geselecteerde node af. Dekking wordt op de structuur en hashes van het betreffende bereik gecontroleerd: een wijziging in een ander lid maakt ongewijzigde dekking niet ongeldig. Een succesvol voltooid leeg resultaat is wel dekking; een afgebroken run niet. Los behandelde kinderen bewijzen niet dat de context van hun ouder beoordeeld is.

## Opslag en projectie

PostgreSQL is de bron voor lagen, elementen, snapshots, beoordelingen, dekking en audit. Batches zijn idempotent op batch-ID plus payload/actor; gewijzigde herhaling geeft conflict. De verwachte revisies beschermen tegen overschrijven. Een database-slot serialiseert schrijftransacties over API-processen heen; een batch of eigenaarverplaatsing wordt volledig gecommit of teruggedraaid.

De API projecteert iedere laag in `urn:jas:graph:v2:<laag-id>`. Register `urn:jas:graph:register:v2` en de graph zelf dragen de laagrevisie. `geprojecteerd_revisie` is de transactionele achterstandsmarkering; de achtergrondtaak probeert achterstallige lagen opnieuw en herstelt een verdwenen projectie. Een rowlock voorkomt dat een oudere projector een nieuwere laag overschrijft. Achtergebleven geregistreerde v2-graphs worden alleen verwijderd na een hercontrole onder het schrijfslot; bestaande lagen en andere graphs blijven behouden. De oorspronkelijke brongraphs worden nooit als annotatieopslag gebruikt.

## Echte leestoegang en uitvoeringsspoor

Lex en MCP registreren dezelfde drie tools:

| Tool | Gedrag |
| --- | --- |
| `search_annotaties` | Getypeerde SPARQL tegen geregistreerde annotatiegraphs, daarna verificatie tegen PostgreSQL en actuele bronankers. |
| `get_annotatie` | Detail van een opgeslagen element, met eigenaar en bronankers. |
| `get_annotatiedekking` | Dekking en laagrevisies voor een concrete bronselectie. |

Zoekfilters ondersteunen tekst (bevat of exact, citaat/toelichting/beide), JAS-klassen, lifecycle, laagstatus, regeling, node/subtree en expliciete historie. Filters combineren met AND, waarden binnen een lijst met OR. Standaard worden verworpen en verouderde elementen uitgesloten. Deduplicatie gaat vóór paginering (standaard 25, maximaal 100). Cursors horen bij dezelfde filters en manifestrevisie. Een wijziging vereist opnieuw beginnen. Meer dan 10.000 graafkandidaten geeft expliciet `partial`; er wordt dan geen volledige zoekdekking beweerd.

Resultaten onderscheiden `ok`, `partial`, `unavailable` en `invalid_request`. Een storing of achterlopende projectie is nooit een leeg succesvol zoekresultaat. Zoekvragen worden uitvoerbaar naar een leesroute gestuurd; die route kan geen annotaties schrijven of via willekeurige SPARQL de annotatietools omzeilen. Annotatieresultaten worden als opgeslagen interpretaties gegrond, afzonderlijk van letterlijke wettekst.

De `tool_execution`-events tonen werkelijke start en afronding, filters, resultaatstatus, aantal, paginering, duur en actualiteit. Ze worden bij de run en het gesprek bewaard en bij replay op run-ID/call-ID samengevoegd. Dit is een uitvoeringsspoor, geen weergave van interne modelgedachten.

De HTTP-worker gebruikt de geauthenticeerde rungebruiker. CLI/MCP vereist daarnaast `ANNOTATIE_READ_USER_ID` uit vertrouwde configuratie; toolargumenten kunnen de actor niet bepalen. API-URL en servicetoken blijven vereist. Zonder gebruikerscontext weigert de adapter de leesactie.

## Gecontroleerde omschakeling

`ANNOTATIE_CONTRACT_VERSIE` is expliciet instelbaar; de nieuwe API heeft standaard waarde `2`. Bij waarde `1` zijn de nieuwe annotatieroutes niet actief. `/v1/annotatie/capabilities` rapporteert de actieve versie. Bij versie `2` weigert de API oude artikelbrede schrijfacties en de oude artikelmigratie. Oude lees-/exportpaden blijven beschikbaar; de expliciet toegestane verwijdering van het ene testdocument kan via het oude verwijderpad.

Voor een omgeving met bestaande actieve componenten:

1. Zet de API expliciet op contract `1` vóór de nieuwe API-revisie verkeer krijgt; rol het nieuwe API-image en de aanvullende tabellen uit.
2. Laat bestaande annotatieruns afronden. Rol de nieuwe graph-qa- en frontend-images uit. In deze korte overgang kunnen nieuwe annotatieverzoeken niet worden uitgevoerd; ze mogen niet naar artikelbrede opslag terugvallen.
3. Controleer dat alle actieve revisies de nieuwe contractondersteuning hebben. Schakel de API vervolgens expliciet naar contract `2` en stuur alle verkeer naar die revisie.
4. Controleer artikel 9 lid 1, hergebruik, lokale review, export, de drie leestools en het zichtbare SSE-spoor. Controleer ook dat een oude schrijfaanroep wordt geweigerd.
5. Verwijder uitsluitend het vooraf geïdentificeerde en door de gebruiker vrijgegeven testdocument. Er is geen inhoudmigratie; bronnen, gebruikers en gesprekken blijven behouden.

Na v2-schrijfverkeer mag rollback alleen naar een v2-compatibele versie, of naar tijdelijk onbeschikbare annotaties. Zet oude brede schrijfpaden niet weer open. De afzonderlijke image-publicatieworkflows regelen deze gecoördineerde eerste omschakeling niet automatisch.

## Verificatie

- API: `uv sync --extra dev`; `uv run pytest -q` vanuit `api`.
- Echte concurrentie: zet `ANNOTATIE_TEST_DSN=postgresql+asyncpg://test:test@localhost:5432/test`. Tests maken en verwijderen alleen hun eigen schema's.
- Projectorprotocol: dezelfde PostgreSQL-variabele activeert tests met een HTTP-transport dat de SPARQL tegen RDFLib uitvoert. Voor een echte GraphDB-engine zet je daarnaast `ANNOTATIE_TEST_GRAPHDB_URL`; GraphDB 11.4 vereist daarvoor een geldige licentie. De lokale engineproef kon zonder licentie niet schrijven.
- Agent: `uv sync --extra dev --extra mcp`; `uv run pytest -q` vanuit `tools/graph-qa`. Voor de gedeelde run-store: `RUNSTORE_TEST_DSN=postgresql://test:test@localhost:5432/test`.
- Frontend: `npm ci`, `npm test`, `npm run lint`, `npm run typecheck`.
- Browser: `npx playwright install chromium`; start Next met `AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --hostname 127.0.0.1 --port 3109`; daarna `npm run test:browser`. Optioneel `CHROMIUM_PATH` voor een lokale Chromium. Deze test gebruikt de echte Next-UI met gecontroleerde BFF-antwoorden.
- API en graph-qa Docker-builds gebruiken de projectroot als buildcontext, zodat het gedeelde bronmodel beschikbaar is.
