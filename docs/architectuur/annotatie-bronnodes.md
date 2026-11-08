# Annotaties op bronnodes

Een verzoek om artikel 9 lid 1 toont en annoteert uitsluitend die bestaande bronnode en haar kinderen. De API en graph-qa gebruiken `packages/bronmodel` om dezelfde bronboom, teksthashes en lokale posities af te leiden. Er is geen terugval naar het hele artikel als een lid ontbreekt. De oorspronkelijke BWB-graaf blijft ongewijzigd.

## Eigenaarschap en tekst

Een laag hoort bij één canonieke bron-IRI. Een element heeft één stabiel ID en één of meer geordende, niet-overlappende ankers. Elk anker bevat de bron-IRI, de SHA256 van de exacte UTF-8-tekst, het letterlijke fragment en start/eind als Unicode-codepoints. De frontend vertaalt DOM-posities in UTF-16 naar die codepoints. De eigenaar is de diepste gezamenlijke bestaande voorouder van alle ankers. Bij verplaatsing blijft het element-ID behouden.

Een element kan een **herkomstspoor** dragen (`trace`, sinds ADR-001 PR 15, additief). Bij de
hybride annotatieketen staan daarin de kandidaat met zijn bewijs (detector, regel, UD-relatie), de
beslissing (regel, model of specificiteit, met reden), de exacte regel die het model over die
kandidaat zag, en de validatie-, twijfel- en resolutieregels. Bij de legacy-keten is het leeg.
Het spoor wordt ongewijzigd bewaard en geëxporteerd (JSON volledig, CSV in de provenance-kolom). Het
is herkomst, geen juridische autoriteit.

Een weergave omvat alleen de gekozen subtree. Elementen met ankers die deels buiten de selectie vallen verschijnen als verwijzing naar hun eigenaar; ze tellen niet mee als lokaal beoordeelbare elementen. Er is geen knop die ongemerkt de selectie tot het artikel verbreedt. JSON-, CSV- en PDF-export gebruiken dezelfde selectie.

Snapshots bevatten de hele canonieke bronboom. De snapshot-ID hangt niet van de geselecteerde node af. Dekking wordt op de structuur en hashes van het betreffende bereik gecontroleerd: een wijziging in een ander lid maakt ongewijzigde dekking niet ongeldig. Een succesvol voltooid leeg resultaat is wel dekking; een afgebroken run niet. Los behandelde kinderen bewijzen niet dat de context van hun ouder beoordeeld is.

## Opslag en projectie

PostgreSQL is de bron voor lagen, elementen, snapshots, beoordelingen, dekking en audit. Batches zijn idempotent op batch-ID plus payload/actor; gewijzigde herhaling geeft conflict. De verwachte revisies beschermen tegen overschrijven. Elke geslaagde schrijftransactie sluit af met één auditregel `revisie` per laag die ze raakte (kolom `laag_id`, detail `{revisie, acties}`); `GET /v1/annotatie/lagen/{laag_id}/revisies` geeft die historie, nieuwste eerst. Het is een logboek van wie wat wanneer deed, geen terugblik: de inhoud van een laag in een eerdere revisie wordt niet bewaard. Een database-slot serialiseert schrijftransacties over API-processen heen; een batch of eigenaarverplaatsing wordt volledig gecommit of teruggedraaid. Besluiten op één laag kunnen samen in één transactie en één revisie (`POST /v1/annotatie/lagen/{laag_id}/beslissingen`), alles of niets.

De API projecteert iedere laag in `urn:jas:graph:v2:<laag-id>`, direct na elke geslaagde schrijftransactie (op de achtergrond, best-effort) – net als v1. De achtergrondtaak (`JAS_PROJECTIE_INTERVAL`, standaard 60 s) is het vangnet: mislukt de directe projectie, dan blijft de laag vuil en neemt die hem mee. Register `urn:jas:graph:register:v2` en de graph zelf dragen de laagrevisie. `geprojecteerd_revisie` is de transactionele achterstandsmarkering; de achtergrondtaak probeert achterstallige lagen opnieuw en herstelt een verdwenen projectie. De projectie houdt tijdens het schrijven naar GraphDB geen rijslot of databaseverbinding vast: ze leest de laag, schrijft de graph, en legt de revisie pas daarna vast, en alleen als de laag intussen niet veranderde. Anders begint ze opnieuw. Een oudere projector overschrijft een nieuwere laag zo hooguit even; valt hij daarna uit, dan ziet de achtergrondtaak de oude revisie in het register. Achtergebleven geregistreerde v2-graphs worden alleen verwijderd na een hercontrole onder het schrijfslot; bestaande lagen en andere graphs blijven behouden. De oorspronkelijke brongraphs worden nooit als annotatieopslag gebruikt.

Een batch is aanvullend: een voorstel dat er al lag (zelfde id, of zelfde klasse en ankers) blijft staan, met zijn besluiten. **Een ronde opnieuw ruimt op.** Draagt de batch `run.modus == "opnieuw"` en een voltooide dekking, dan is hij de nieuwe uitkomst voor zijn bereik: elk element met de eigenaar in dat bereik dat van de agent komt, nog actueel is, geen oordeel draagt (geen besluit, geen opmerking) en niet opnieuw in de batch zit (ids volgen uit de kandidaat), krijgt de lifecycle `vervangen`, met `vervangen_in: {batch_id, tijd}` en een auditregel `element-vervangen`. Het wordt niet gewist: de rij, de herkomst en de audit blijven. Een eigen markering, een beoordeeld of vergrendeld element, een verouderd element en een afgeronde laag blijven onaangeroerd; een gestopte of mislukte ronde (dekking niet voltooid) en een gewone ronde ruimen niets op. De respons draagt `vervangen` (de ids), waaruit Lex in zijn samenvatting noemt hoeveel. Maakt een latere ronde een vervangen voorstel weer (zelfde id), dan leeft het op als `voorgesteld` (`element-hersteld`). `vervangen` is niet actueel (`NIET_ACTUEEL` in `annotatie_v2_contracts`): het staat niet in de elementen van de weergave, de inventaris, het manifest, de werkvoorraad, de zoekresultaten, de statistiek en de projectie, houdt afronden niet tegen en is alleen-lezen (409). Terug te vinden is het in `vervangen` van de weergave en van de inventaris (zoals `afgewezen`), en via `GET elementen/{id}`. Een begripskoppeling op een vervangen element is `gewijzigd`, net als bij een verouderd element.

Verwijderen (`POST /v1/annotatie/weergave/verwijder`, elke gebruiker) haalt alle lagen in het bereik van de bepaling in beeld weg, met hun elementen en de dekkingsrijen van die bronnodes; een dekkingsrij van een ruimere bepaling verliest die bronnodes uit haar bereik en is daarna niet meer voltooid. Elementen van een voorouderlaag blijven staan. De audit krijgt per laag `laag-verwijderd` en blijft verder ongewijzigd; de weergave leest daaruit `verwijderd`. Na de commit gaan de graph en de registerregels van die lagen direct weg; lukt dat niet, dan ruimt de achtergrondtaak ze op als wees. Een nieuwe annotatie op dezelfde bepaling krijgt een nieuwe laag-id en botst dus nooit met een achtergebleven projectie.

## Relaties tussen markeringen (ADR-011)

Het besluit staat in [ADR-011](adr-011-relaties-tussen-markeringen.md), de typen in de catalogus van de skill
(`relaties.json`, gegenereerd naar `api/app/jas_relaties.py`). De opslag staat in `annotatie_v2_relaties.py`.

- **Een relatie** (`annotatie_v2_relaties`, JSON-inhoud per rij) verbindt `van` en `naar`. Elk eindpunt is
  `{soort: element|impliciet, id}`, en een element mag in een andere laag liggen.
- **Wat een relatie draagt:** `type`, `volgorde` (alleen bij `invoer` en `operand`, uniek per eindpunt `naar`),
  `toelichting`, `herkomst`, `lifecycle` en `beslissingen`, en de stand van beide eindpunten (`stand_van`/`stand_naar`:
  `begrip_store.element_hash`).
- **Het id is `R` + hash(van, naar, type, volgorde).** Dezelfde relatie nog eens is een 409 `al_vastgelegd`.
- **De drager.** De relatie hoort bij de laag van de kant die de catalogus aanwijst (`drager_kant`). Leggen,
  beoordelen en wissen raken die laag: schrijfslot, `verwachte_revisies` (412), status (409, heropen eerst), revisie,
  auditregel (`relatie-gelegd`, `relatie-beoordeeld`, `relatie-gewist`) en projectie.
- **De api toetst:**
  - het type bestaat;
  - het klassenpaar past (`toegestaan`, bij `waarde` met subtype);
  - geen relatie naar zichzelf;
  - de eindpunten bestaan en zijn actueel (niet verworpen, verouderd of vervangen).

  Elke weigering is een 422 met `fout` en `melding`. Juridische juistheid toetst de api niet.
- **Oordeel.**
  - Een relatie van de jurist is meteen `human_approved`, met een regel `markering`, zoals een eigen markering.
  - `approve`, `reject`, `heropen` en `comment` volgen de lifecycle van elementen. Na `reject` kan alleen `heropen` of
    `comment`.
  - `approve` legt de stand van nu vast en toetst het klassenpaar opnieuw.
- **Doorwerking.** Wijkt een eindpunt af van zijn stand, of is het niet meer actueel, dan draagt de relatie in de
  weergave `veranderd: true`.
- **Wissen.**
  - Een eigen relatie kan worden gewist. Een voorstel van Lex wijs je af; dat blijft als historie staan.
  - Een gewist element (`verwijder`) of een verwijderde bepaling (`verwijder_weergave`) neemt de relaties mee, met
    een auditregel. Een dragerlaag die blijft, krijgt een revisie.
- **Impliciete partij** (`annotatie_v2_impliciet`): een rechtssubject dat de tekst niet noemt, alleen van de jurist,
  met een verplichte toelichting en optioneel `vindplaats` en `zelfde_als`.
  - Ze hoort bij de laag van de bepaling in beeld.
  - Ze is geen markering: geen ankers, geen dekking, en ze telt niet in de inventaris, de statistiek of de afronding.
  - Wissen kan alleen door wie haar maakte, en haar relaties gaan mee.
- **Lezen.** `GET weergave` draagt `relaties` (met `leesvorm`, de eindpunten met klasse en tekst, en `veranderd`) en
  `impliciet`. Daarin staat elke relatie met een eindpunt in beeld of de drager in een van de lagen.
- **Routes onder `/v1/annotatie`:**
  - `POST relaties`;
  - `POST relaties/{id}/beslissing`;
  - `POST relaties/{id}/wis`;
  - `POST impliciet`;
  - `POST impliciet/{id}/wis`.

  De BFF laat `relaties` en `impliciet` door.
- **Nog niet:** de projectie naar de graaf (3D) en voorstellen uit de keten (4C).

## Echte leestoegang en uitvoeringsspoor

Lex en MCP registreren dezelfde drie tools:

| Tool | Gedrag |
| --- | --- |
| `search_annotaties` | Getypeerde SPARQL tegen geregistreerde annotatiegraphs, daarna verificatie tegen PostgreSQL en actuele bronankers. |
| `get_annotatie` | Detail van een opgeslagen element, met eigenaar en bronankers. |
| `get_annotatiedekking` | Dekking en laagrevisies voor een concrete bronselectie. |

Zoekfilters ondersteunen tekst (bevat of exact, citaat/toelichting/beide), JAS-klassen, lifecycle, laagstatus, regeling, node/subtree en expliciete historie. Filters combineren met AND, waarden binnen een lijst met OR. Standaard worden verworpen en verouderde elementen uitgesloten; vervangen elementen altijd. Deduplicatie gaat vóór paginering (standaard 25, maximaal 100). Cursors horen bij dezelfde filters en manifestrevisie. Een wijziging vereist opnieuw beginnen. Meer dan 10.000 graafkandidaten geeft expliciet `partial`; er wordt dan geen volledige zoekdekking beweerd.

Resultaten onderscheiden `ok`, `partial`, `unavailable` en `invalid_request`. Een storing of achterlopende projectie is nooit een leeg succesvol zoekresultaat. Zoekvragen worden uitvoerbaar naar een leesroute gestuurd; die route kan geen annotaties schrijven of via willekeurige SPARQL de annotatietools omzeilen. Annotatieresultaten worden als opgeslagen interpretaties gegrond, afzonderlijk van letterlijke wettekst.

De `tool_execution`-events tonen werkelijke start en afronding, filters, resultaatstatus, aantal, paginering, duur en actualiteit. Ze worden bij de run en het gesprek bewaard en bij replay op run-ID/call-ID samengevoegd. Dit is een uitvoeringsspoor, geen weergave van interne modelgedachten.

De HTTP-worker gebruikt de geauthenticeerde rungebruiker. CLI/MCP vereist daarnaast `ANNOTATIE_READ_USER_ID` uit vertrouwde configuratie; toolargumenten kunnen de actor niet bepalen. API-URL en servicetoken blijven vereist. Zonder gebruikerscontext weigert de adapter de leesactie.

## Vastgelegd in tests

- **De werkplek gebruikt het vertrouwde annotatiepaneel.** `NodeAnnotatiePaneel` is een dunne schil
  om `ArtefactInhoud`, met `lib/annotatieNodeAdapter.ts` als vertaling tussen codepoints per bronnode
  en UTF-16 in de samengestelde bron. Een eigen paneel verliest alle opmaak en bediening.
- **Een afgeronde bepaling stopt de beurt vóór de modelronde.** De api bevriest een afgeronde laag
  (409); Lex controleert dat vóór de modelaanroepen, niet pas bij het opslaan.
- **De projectie is direct, de lus is vangnet.** Anders staat een annotatie tot een minuut later in
  de graaf.
- **Het chatbericht draagt `annotatie_doel` en `tool_executions`.** Zonder die velden wijst een
  bericht na het heropenen van een gesprek nergens meer naar, en verdwijnen de chip, de
  hergebruikmelding en het toolspoor.
- **De leesroute zoekt zelf.** `annotaties_zoeken` voert vóór de eerste LLM-call zelf
  `search_annotaties` uit; aan de toolkeuze van het model overgelaten levert het soms een
  non-antwoord op.

## Verificatie

- API: `uv sync --extra dev`; `uv run pytest -q` vanuit `api`.
- Echte concurrentie: zet `ANNOTATIE_TEST_DSN=postgresql+asyncpg://test:test@localhost:5432/test`. Tests maken en verwijderen alleen hun eigen schema's.
- Projectorprotocol: dezelfde PostgreSQL-variabele activeert tests met een HTTP-transport dat de SPARQL tegen RDFLib uitvoert. Voor een echte GraphDB-engine zet je daarnaast `ANNOTATIE_TEST_GRAPHDB_URL`; GraphDB 11.4 vereist daarvoor een geldige licentie. De lokale engineproef kon zonder licentie niet schrijven.
- Agent: `uv sync --extra dev --extra mcp`; `uv run pytest -q` vanuit `tools/graph-qa`. Voor de gedeelde run-store: `RUNSTORE_TEST_DSN=postgresql://test:test@localhost:5432/test`.
- Frontend: `npm ci`, `npm test`, `npm run lint`, `npm run typecheck`.
- Browser: `npx playwright install chromium`; start Next met `AUTH_SECRET=annotatie-browser-test-only-secret AUTH_TRUST_HOST=true npm run dev -- --hostname 127.0.0.1 --port 3109`; daarna `npm run test:browser`. Optioneel `CHROMIUM_PATH` voor een lokale Chromium. Deze test gebruikt de echte Next-UI met gecontroleerde BFF-antwoorden.
- API en graph-qa Docker-builds gebruiken de projectroot als buildcontext, zodat het gedeelde bronmodel beschikbaar is.
