# ADR-013 — Connectors en externe bronnen

Status: **concept, wacht op akkoord**. Fase 2 wacht ook op het besluit over ADR-007. · Datum: 2026-11-07 · Onderbouwing:
[onderzoek connectors en externe bronnen](onderzoek-connectors-en-bronnen-2026-11.md) · Hangt samen met:
[ADR-007](adr-007-llm-pad-en-verwerker.md), [ADR-008](adr-008-antwoordsjablonen.md), [ADR-010](adr-010-agentarchitectuur.md)

## Context

De gebruiker wil dat connectors werken zoals in Claude:
- in de instellingen toevoegen;
- per gesprek aan- of uitzetten;
- toestemming geven voor een handeling.

Lex haalt nu alleen uit de BWB-graaf. Een vindplaats is altijd een jci of een BWB-id. Tools van een vreemde
MCP-server rechtstreeks aan het model geven, zoals de `mcp_servers`-connector van de Messages API doet, levert geen
resultaatcontract, geen vindplaats en geen eigen toolbeschrijving. Dat botst met de brongetrouwheid en met ADR-008 en
ADR-010. Dit ADR neemt de bediening van Claude over en houdt de garanties van het platform.

## Besluit

### Twee soorten connectors

| | **Bronconnector** | **Contextconnector** |
|---|---|---|
| Voorbeelden | Kamerstukken (SRU van KOOP), rechtspraak (ECLI), EUR-Lex/CELLAR, LiDO-koppelingen | een eigen MCP-server: Confluence, SharePoint, documenten van de organisatie |
| Wie voegt toe | de beheerder, in de beheertab | de gebruiker, in de eigen instellingen, alleen als de beheerder dat toestaat |
| Vorm | getypeerde tools in `agent/tools/`, in onze code, met het resultaatcontract; transport via HTTP of MCP achter een port | een remote MCP-URL plus OAuth aan het eigen account; tools komen van de server, achter een omhulsel van ons |
| Vindplaats | een eigen soort (`bronmodel.extern`, veld `brontype`): `kamerstuk`, `bekendmaking` (Stb., Stcrt.), `uitspraak`, `eu` (naast `wettekst`) | geen; hoogstens een document-URL plus versie als herkomst |
| Citeren | ja; `grounding` toetst letterlijk, zoals bij wettekst | nooit als bron. Het antwoord markeert zichtbaar "context, geen vindplaats" |
| Credentials | per straat, door de beheerder, versleuteld met Fernet (`secrets_crypto`) | per gebruiker (OAuth-token), versleuteld met Fernet, nooit gedeeld |
| Zichtbaar voor | iedereen in een werkgebied (gedeeld dossier) | alleen de gebruiker; komt niet in een gedeeld dossier, tenzij de gebruiker het bewust overneemt als notitie |

**Een uitspraak of een MvT is een bron, maar geen wettekst.** Het sjabloon (ADR-008) houdt de soorten uit elkaar
(`door` krijgt een brontype). Een uitspraak onderbouwt een uitleg, nooit wat de wet zegt.

### Aan of uit per gesprek (*Bronnen en tools*)

- Boven het invoerveld staat een regel met de actieve bronnen: *Wetgeving ✓ · Kamerstukken ✓ · Rechtspraak –*, met een
  menu om ze te schakelen. Wetgeving staat altijd aan.
- **De stand gaat mee met de beurt**, als veld `bronnen` op `ChatRequest` (`agent/models.py`). Er is maar één filter:
  - de toollaag biedt alleen de toegestane tools aan (`anthropic_schemas(only=spec.tools ∩ toegestaan)`);
  - `dispatch` weigert een tool die niet aanstaat, ook als een workflow (laag 2) hem in code aanroept;
  - de supervisor en de routering kiezen nooit een route die op een uitgeschakelde bron leunt.
- **Per werkgebied is er een standaardstand** (in de api, bij het werkgebied). Een nieuw gesprek in het werkgebied
  neemt die over.
- **De stand staat op het gesprek** (`/v1/gesprekken/*`), zodat hij na herladen blijft. Een wijziging geldt vanaf de
  volgende beurt en komt in de beurtmeting.
- De beheerder bepaalt wat er in het menu kan staan. Een connector die de beheerder uitzet, verdwijnt overal, ook uit
  bestaande standaardstanden.

### De connectorbeschrijving (8 nov 2026)

Elke bronconnector heeft één beschrijving in `packages/bronmodel/bronmodel/connectors.py`: naam, label, brontype, de
groep in de bronnenlijst, wat hij dekt (voor de router en de scope), signalen om een vraag te herkennen, zijn tools en
de tool die de citeerbare tekst draagt, de vorm van zijn id, de rollen die zijn tools krijgen, waar hij in een antwoord
voor staat en wat hij niet kan. De keten leidt er alles uit af – toollaag, specialisten, de toegestane namen in api en
graph-qa, het register – en niets per connector met de hand. Een nieuwe connector is: een beschrijving, zijn tools in
`agent/tools/` en een straatvlag `CONNECTOR_<NAAM>`. `tools/graph-qa/tests/test_connectorbeschrijving.py` maakt een
onvolledige beschrijving rood.

**In het antwoord** (vervolg op 1a, 8 nov 2026). Een bron naast de wet krijgt binnen ADR-008 een vaste vorm: het blok
`extern` in de gesloten catalogus (`door: bron`, met brontype, id, label, link, de kop uit de beschrijving en de
letterlijke passages). Elk sjabloon krijgt het als subsjabloon, met één plat veld `extern: [{id, van_nr, tot_nr}]`. Een
vraag die alleen over zo'n bron gaat, heeft een eigen sjabloon (`antwoord_extern`) met dezelfde blokken. Allebei staan ze
er alleen als er een connector aanstaat. Het model wijst aan, de code vult uit de rijen van de leestool; het blok komt ná
de wettekst en vult nooit een `doel`.

**Wat de keten eruit afleidt** (PR 1–6 van *connectors consequent*):

| Waar | Wat | Code |
|---|---|---|
| scope | de supervisor kent elke bekende connector als binnen de wetgeving, ook uitgezet | `supervisor._scope_bronnen` |
| routering | een vraag die alleen over een uitgezette bron gaat: een melding zonder model, met reden en wie hem aanzet; AFWIJZEN bij een bronvraag draait de code terug | `nodes/supervisie._bron_uit`, `bronstand` |
| bronstand | per connector aan, of uit door `straat`, `gesprek`, `werkgebied`, `beheerder` of `register_onleesbaar` | `agent/bronstand.py` |
| tools | de rollen uit `specialisten` krijgen de tools; `toegestane_tools` blijft het ene filter | `specialists._met_connectors` |
| prompt | BRONSOORTEN generiek in het stabiele deel; BRONNEN IN DEZE BEURT na het cachepunt | `prompts.py`, `bronstand.prompt_blok` |
| antwoord | het blok `extern` als subsjabloon en het sjabloon `antwoord_extern` | `sjablonen/extern.py` |
| verificatie | een stuk dat alleen gevonden is, is `onbevestigd` | `grounding.check_grounding`, `connectors.leestools` |
| werkplek | het menu toont wat straat én register aanzetten; *Zet … aan* na `bron_uit` | `GET /v1/bronnen`, `connectorsMenu` |
| genoemd stuk | een id in de vraag leest de code vooraf met de leestool, ook een citeervorm ("Kamerstuk 32140, nr. 342", `citeervormen`); een zoekresultaat is geen bron | `nodes/bron_lezen.py`, `grounding.alleen_gelezen_extern` |
| lijstvraag | "het laatste stuk van dossier X", "de 10 nieuwste": de code leest volgorde, aantal en filters (`soorten`, `organen`, de metadata) en zoekt één keer, zonder model | `agent/bron_lijst.py`, `nodes/bron_lijst.py` |
| denkproces | de werkwoorden per tool ("leest Kamerstuk kst-…"), en de algemene stappen noemen de bronnen van de beurt | `narratie._toolregel`, `bronstand.waar` |

**Een nieuwe connector toevoegen (checklist):**

1. een beschrijving in `bronmodel/connectors.py` (alle velden, ook de werkwoorden per tool voor het denkproces en wat
   de leestool levert en niet levert; `brontype` uit `extern.BRONTYPEN`, eventueel een nieuw
   soort id in `extern.py` met vectoren). Daarbij de **metadata** per stuk (`metadata`, `MetadataVeld`): in de vaste
   sleutels van `METADATA_SLEUTELS` (minstens `datum`, `titel` en `leesbaar`), per veld waar het bij de dienst
   vandaan komt, wat het betekent en op welke zoekargumenten het filtert (`filters`), de `standaard_datum` voor
   "nieuwste" en de `volgordes` (uit `VOLGORDES`), die het argument `volgorde` van de zoektool als enum draagt.
   Alleen velden die de dienst echt levert: toets dat met de live-proef;
2. de tools in `tools/graph-qa/agent/tools/`, met het resultaatcontract; de leestool levert `stuk: {id, label, link, bron_hash, gewijzigd?}` en
   rijen `{nr, tekst, kop?, soort?}` (één nummering per stuk; `soort` is `alinea`, `voetnoot`, `tabel` of `tabelrij`, een
   `tabel` draagt `openen` naar de leestool en een `tabelrij` haar `cellen`), en een tak in `dispatch`;
3. de straatvlag: `Settings.connector_<naam>`, `CONNECTOR_<NAAM>` in `config.py` en de bicep (default uit);
4. de groep in `frontend/lib/bronnen.ts` (`BRONTYPE_NAAM`);
5. een nepbron in de contractharnas (`NEPBRONNEN` en `CONNECTOR_ARGS` in `tests/test_resultaatcontract.py`): elke
   pagina haalt het contract, en alle pagina's samen zijn precies de dataset;
6. een live-proef `tools/graph-qa/tests/test_<naam>_live.py` met de marker `live` tegen de echte dienst (indexen,
   recordvorm, versievelden); `bronnenwacht.yml` draait hem dagelijks, nooit in de poort;
7. `tools/graph-qa/tests/test_connectorbeschrijving.py` (ook de naamconventie `zoek_…`/`get_…` en een voorbeeld in elke
   invoerfout) en de kruistests groen; daarna meten zoals
   [`../acceptatie/connectors-meting.md`](../acceptatie/connectors-meting.md).

Verder hoeft er niets bij: geen prompttekst, geen route, geen sjabloon, geen werkplekcomponent per connector.

### Metadata als deel van het contract (9 nov 2026)

Een feit over een stuk (de datum, het soort, het dossier, de status) komt uit de dienst, niet uit de tekst van het model:
in gesprek e906567a op acceptatie noemde Lex het verkeerde "laatste stuk" van een dossier, twee keer, en de datum van een
gelezen motie kwam uit de modeltekst. Daarom beschrijft elke connector zijn metadata in vaste sleutels
(`METADATA_SLEUTELS`), zodat dezelfde code de lijst in een antwoord, de kop van een gelezen stuk en de werkplek vult.
De poorttest eist datum, titel en leesbaar, een sorteerbare `standaard_datum`, en dat elk filter een argument van een
zoektool is. Wat de SRU van KOOP levert en wat niet, is live getoetst (9 nov 2026): `sortBy` in de CQL werkt, de
parameter `sortKeys` wordt stil genegeerd; documentdatum (`dt.date`) en publicatiedatum (`dt.available`) lopen soms
weken uiteen, en "nieuwste" ordent op de documentdatum (besluit gebruiker). Het vervolg (de adapter leest alle velden,
filters en volgorde in de zoektool, een lijstblok in het antwoord, zoeken in de tekst, een vaste route voor lijstvragen)
volgt in aparte PR's. In het antwoord staat een lijst als blok `stukken` (ADR-008): het model wijst de ids aan, de
code neemt elk feit uit de zoekrijen, met de zoekvraag in woorden en het totaal; het blok `extern` noemt de datum en het
soort van het gelezen stuk.

### Review van de Kamerstuk-connector (8 nov 2026)

Een externe review noemde vier punten; alle vier klopten, en de handleiding SRU 2.0 van KOOP maakte er twee zwaarder.
Niet opnieuw ontworpen: elk punt is opgelost in wat er al lag.

| punt | wat er mis was | besluit |
|---|---|---|
| onvolledig dossier | na 300 records `volledig: true`, `totaal` van de lijst; een subdossier zocht op het hoofdnummer en vond niets | geen vlag naast `volledig`: tot 1000 op nummer, daarboven op datum met een exact vervolg (`volgorde`); subdossier in de CQL; de connectortools in de contractharnas |
| uitval van graph-qa | het menu toonde dan het register met schakelaars | één leesmodel in de BFF met `beschikbaarheid` `aan`/`onbekend`; onbekend = geen schakelaar, de beurt houdt de keuze |
| cache en bronhash | 64 items zonder vervaltijd; een stuk verandert na publicatie (onopgemaakt → opgemaakt, herdruk); de hash bereikte het antwoord niet | valideren op `dt.modified`/documentstatus/versie na `VERS_S`, grens in bytes, `gevalideerd: false` bij storing; `bron_hash` en `gewijzigd` op het blok `extern`; passages uit één lezing |
| alleen een nep | de live-test draaide nergens | een live-proef per connector, dagelijks in `bronnenwacht.yml`, niet in de poort |

Uit de connectorarchitectuur van Claude/MCP (specificatie 2025-11-25) komt de buitenkant van de graaf-MCP: per tool
`annotations` (alleen lezen, `openWorldHint` voor een bronconnector), het resultaatcontract als `outputSchema` met
`structuredContent`, en een gelezen stuk als `resource_link` met `lastModified`.

**Vervolg, nog niet gebouwd:**

- **Een snapshot bij de bronselectie.** Wat in een bronselectie wordt opgenomen, bevriest de api (onderzoek §4.4). Een
  externe bron kan nog niet in een bronselectie; als dat komt, draagt de snapshot `bron_hash` en `gewijzigd` uit het
  leestoolcontract.
- **De tweede connector.** Rechtspraak is de beste proef van herbruikbaarheid (dezelfde vorm, een andere id en XML),
  maar wacht op de toets van endpoint en licentie (fase 1c). EUR-Lex is de terugval zonder licentieblokkade. LiDO hoort
  als graafverrijking, niet als connector. Open keuze voor de eigenaar.

### Toestemming per handeling

- **Connectors die alleen lezen** (alle bronconnectors, en de contextconnectors in fase 2a): de schakelaar is de
  toestemming.
- **Connectors die iets wijzigen** (alleen contextconnectors, fase 2b):
  - elke schrijvende tool vraagt toestemming met een keuzekaart (*Deze keer* / *Altijd voor deze tool* / *Weigeren*);
  - *Altijd* geldt per gebruiker en per tool, is in te trekken in de instellingen en staat in de audit;
  - een tool geldt als schrijvend tenzij de beheerder hem als alleen-lezen markeert. Een hint van de server
    (`readOnlyHint`) is geen bewijs.

### Beheer

- **Register `/v1/admin/connectors`**, naar het model van de modelprofielen:
  - soort, naam, aan of uit per straat, rate-limit en credentials;
  - voor contextconnectors: toegestaan ja/nee, een allowlist van hosts en welke tools zijn toegestaan.
- **Audit en kosten.** Elke externe aanroep geeft een `tool_execution`-event (connector, tool, status, duur, aantal),
  zonder inhoud. Het aantal aanroepen per connector en per gebruiker gaat in het verbruiksjournaal, naast de
  modeltokens. Het OAuth-koppelen en -ontkoppelen staat in de audit.
- **Uitgaand verkeer** gaat alleen naar hosts op de allowlist. Het model kiest nooit een URL.

### De vertrouwensgrens

Die geldt voor beide soorten. Voor contextconnectors is hij de voorwaarde.

1. **Toolbeschrijvingen zijn van ons.**
   - Bronconnector: de beschrijving staat in onze code.
   - Contextconnector: de beheerder keurt per tool de beschrijving goed. Die wordt vastgezet met een hash, en een
     wijziging aan de serverkant zet de tool uit tot opnieuw is goedgekeurd. Zo zijn *rug pulls* uitgesloten.
2. **Externe tekst is data.**
   - Ze komt alleen binnen als toolresultaat, in een omhulsel dat de herkomst noemt, en nooit in de systeemtekst.
   - De beurt die een contextresultaat las, mag in dezelfde beurt geen schrijvende tool aanroepen zonder een
     keuzekaart. Er is geen *Altijd* na contextinvoer in dezelfde beurt.
3. **Begrensd.** Resultaten gaan door het resultaatcontract (budget, natuurlijke grenzen). Een contextconnector levert
   hoogstens N resultaten per beurt.
4. **Geen doorgifte.** Tekst uit een contextconnector komt niet in de bronnenlijst, niet in de grounding als
   vindplaats, en niet in een gedeeld dossier, het rapport of de graaf.

### De AVG-poort (ADR-007)

- Een **bronconnector** haalt openbare, gepubliceerde stukken op. Uitspraken zijn geanonimiseerd, maar niet altijd
  volledig. Dat valt onder hetzelfde regime als wettekst.
- Een **contextconnector** kan persoonsgegevens en casusgegevens naar het model brengen. Daarom:
  - fase 2 start pas na het besluit over ADR-007 (verwerker, regio, retentie);
  - de beheerder legt per connector een gegevensclassificatie vast (*openbaar / intern / vertrouwelijk*). Alleen wat
    het ADR-007-besluit toestaat, kan worden aangezet;
  - de gebruiker ziet bij het koppelen en in het menu wat er naar het model gaat.

## Fasering

| Fase | Wat | Voorwaarde |
|---|---|---|
| **1a** | het soort vindplaats in `packages/bronmodel` (`extern.py`) + `provenance`/`grounding`/werkplek (PR 1); de bronconnector Kamerstukken achter `CONNECTOR_KAMERSTUKKEN` (PR 2). Een Kamerstuk komt niet in een sjabloonblok (de rij draagt `id`, geen `iri`); het staat in de uitleg en de bronnenlijst, en `verify` toetst het citaat. `door` met brontype volgt pas als een blok externe tekst draagt; bronconnector **Kamerstukken** (`zoek_kamerstukken`, `get_kamerstuk`) achter een vlag | dit ADR |
| **1b** | register `/v1/admin/connectors` + beheertab; het menu *Bronnen en tools* per gesprek, de standaard per werkgebied, de stand op het gesprek (`Gesprek.connectors`, `standaard_connectors`) – gebouwd in PR 3–5 | 1a |
| **1c** | LiDO-koppelingen jci↔ECLI in de graaf (importer), bronconnector **rechtspraak**; daarna **EUR-Lex** | endpoint en licentie getoetst |
| **2a** | contextconnectors die de gebruiker toevoegt, alleen lezen: MCP-URL + OAuth, goedkeuring per tool, de vertrouwensgrens | **besluit ADR-007** |
| **2b** | contextconnectors die schrijven, met toestemming per handeling | 2a + aparte toets |

Elke fase meet zoals ADR-010 vraagt: de kwaliteitsset, de meting per beurt en drie runs. De prefix groeit alleen met de
tools die aanstaan.

## Waarom niet anders

- **De `mcp_servers`-connector van de Messages API.** Die is beta, valt buiten ZDR, levert geen resultaatcontract en
  geen vindplaats, en neemt de toolbeschrijving van de server over. Bovendien loopt de aanroep buiten onze audit.
- **Elke MCP-server als bron.** Zonder een stabiele, officiële identifier en een letterlijke tekst kan de grounding
  niets toetsen.
- **Contextconnectors nu al.** Dat kan niet zolang ADR-007 niet zegt wat er naar het model mag.
- **Volledige teksten in bulk in de graaf.** De licentie en het rate-limit laten dat vaak niet toe (rechtspraak), en een
  analist heeft er per werkgebied maar een paar nodig. De graaf weet *dat* en *waar*, de tool haalt *wat*.

## Gevolgen

- `packages/bronmodel` raakt api en graph-qa. De jci-vectoren (`frontend/lib/jci-vectoren.json`) krijgen ook gevallen
  voor de nieuwe soorten.
- De toolverdeling (`test_toolverdeling`) toetst ook dat een connectortool achter zijn schakelaar staat.
- `geen-omgevingsgegevens.yml` blijft gelden: alleen de publieke URL's van de bronnen staan in de repo, de credentials
  niet.
