# Connectors en externe bronnen voor Lex: analyse en aanbeveling

> Onderzoek, 7 nov 2026. Alleen lezend; er is niets gebouwd. Basis voor een eventuele ADR-013.


## Context

De vraag is of het platform tools en connectors kan integreren zoals Claude dat doet, en welke externe bronnen dat de
moeite waard maken. De lat is de brongetrouwheid: bronnen en citaten komen alleen uit toolresultaten, met een vindplaats.
ADR-010 kiest code boven model. ADR-007 laat open wat er naar het model mag. Binnen die grenzen moet het antwoord
passen.

**De kern in één zin.** Het platform moet externe bronnen toevoegen als getypeerde bron-tools met een eigen
vindplaatstype. Een vrije MCP-koppeling die het model zelf bedient, past hier niet. Begin met de Kamerstukken
(memorie van toelichting) via de SRU van KOOP, en zet de koppelingen tussen uitspraken en artikelen in de graaf.

---

## 1. Wat er nu is

- **Lex is al een MCP-client.** `agent/mcp_client.py` praat via Streamable HTTP met de MCP-server die in GraphDB is
  ingebouwd (`sparql_query`, `similarity_search`). De client weigert updates, doet de handshake per verbinding en
  herhaalt die bij een 404. Het model ziet die MCP niet. Het ziet alleen de getypeerde toollaag erboven.
- **De getypeerde toollaag** (`agent/tools/__init__.py`) heeft 27 tools in `TOOLS`: 21 graaftools, 4 tools voor
  annotaties en 2 voor begrippen. `anthropic_schemas(only=)` levert per specialist een deel daarvan, en `dispatch()`
  voert ze uit. Elke graaftool levert het **resultaatcontract** (`agent/resultaat.py`): `{status, volledig, aantal,
  vervolg?, resultaten}`, binnen een budget, op natuurlijke grenzen en zonder afknippen. Tests bewaken de toolverdeling,
  de predicaten en de FTS-velden, en of de annotatielagen buiten de bronnen blijven.
- **Brongetrouwheid.** `provenance.iter_refs` herkent vindplaatsen in toolresultaten: BWB-IRI's, jci-strings en
  BWB-id's. `collect_sources` maakt daaruit de bronnenlijst, en `grounding.check_grounding` toetst citaten letterlijk
  tegen trace en bronregister. **Alleen BWB-vindplaatsen tellen.** Een andere identifier, zoals een ECLI of een
  Kamerstuknummer, wordt nu niet als bron herkend.
- **Naar buiten** zijn er vier MCP-servers: `graph-qa-mcp` (stdio, precies `TOOLS`/`dispatch`), de acceptatie-MCP
  (via de BFF met een accounttoken), de admin-MCP (`/v1/admin/*`) en de GraphDB-proxy op acceptatie (alleen `/mcp`,
  met bearer-token). Alle vier ontsluiten het platform. Geen van de vier haalt iets binnen.
- **De BWB-importer** haalt wettekst bij KOOP en valideert die tegen de XSD. Met WTI komen de citeertitels,
  rechtsgebieden, grondslagen, de verantwoordelijke organisatie en relaties tussen regelingen mee. TOOI is er al: een
  CC0-snapshot met ministeries (`tools/bwb-import/app/tooi.py`, `api/app/tooi.py`). Herimporteren is idempotent
  (named-graph `PUT`).
- **De ADR's.** Volgens ADR-005 heeft een agent één strikte stap en is een suggestie deterministisch. Volgens ADR-008
  vult de code de feiten in het antwoordsjabloon en wijst het model alleen aan. Een sjabloontool staat los van `TOOLS`.
  ADR-010 heeft vier lagen: routering in code, vaste workflows, taakagents met een contract van zeven punten, en één
  open laag. Managed Agents en de Agent SDK zijn daar bewust afgewezen, want "de brongetrouwheid hoort in onze code".
  ADR-007 (concept) zegt dat er geen casusinformatie in het gesprek hoort zolang het besluit over de verwerker er niet
  is.

## 2. Hoe connectors in Claude werken

- **MCP 2026-07-28** is de huidige specificatie. Het protocol is stateless: de `initialize`-handshake en het
  `Mcp-Session-Id` zijn weg, en er is `server/discover`. Lijsten zijn cachebaar via `ttlMs`/`cacheScope`, en een server
  hoort tools in een vaste volgorde te geven, wat helpt bij de prompt-cache. Een extensie zoals tasks staat buiten de
  kern. Roots, Sampling en Logging zijn deprecated. Voor autorisatie gebruikt de server OAuth 2.1 met Protected Resource
  Metadata (RFC 9728). Een client registreert zich via een Client ID Metadata Document; Dynamic Client Registration is
  deprecated. De client moet `iss` valideren (RFC 9207). Enterprise-Managed Authorization is stabiel.
  - **Gevolg voor ons:** de handshake-logica in `mcp_client.py` hoort bij de oude versie (2025-11-25). Zolang GraphDB
    die versie spreekt, werkt hij. Bij een upgrade van GraphDB moet dit opnieuw getoetst worden.
- **De drie primitieven.** *Tools* worden door het model aangeroepen. *Resources* zijn door de applicatie gekozen
  context, opvraagbaar op URI. *Prompts* zijn sjablonen die de gebruiker kiest. In de Messages API ondersteunt de
  MCP-connector (`mcp_servers` met `mcp_toolset`) alleen tools van remote servers, met een allow- of denylist per tool.
  De OAuth-flow en het verversen van tokens liggen bij de aanroeper. De connector is beta, ook op Microsoft Foundry, en
  komt niet in aanmerking voor ZDR. Resources en prompts vragen een eigen client.
- **Hoe een host connectors aanbiedt** (claude.ai). Een beheerder zet een connector aan voor de organisatie; op
  Enterprise kan dat per groep. Daarna authenticeert **elke gebruiker zelf** bij de dienst, zodat de rechten van die
  dienst per persoon gelden. Een custom connector is een remote MCP-URL die vanuit de cloud van Anthropic wordt
  aangeroepen, niet vanaf het toestel van de gebruiker.
- **Wat het zou betekenen als Lex zelf MCP-client wordt**, met servers die je per werkgebied of per gebruiker
  aankoppelt in de beheertab:
  - Technisch kan het. Het patroon bestaat al: modelprofielen (`/v1/admin/profiles`), sleutels versleuteld met Fernet
    (`llm-config-secret`), een append-only verbruiksjournaal en een audit.
  - **Wat er dan wegvalt.** Tools van een vreemde server leveren geen resultaatcontract (geen `volledig`/`vervolg`),
    geen vindplaats die `provenance` herkent en geen tests op stille onvolledigheid. Hun beschrijvingen gaan
    ongefilterd het model in, met risico op *tool poisoning* en *rug pulls*. Elk extra schema vergroot ook de vaste
    prefix, terwijl ADR-010 die juist klein wil houden: nu ±10k tokens.
  - **Per gebruiker inloggen** botst met het gedeelde karakter van annotatielagen en werkgebieden. Een bron die alleen
    analist A kan zien, maakt het dossier van analist B onnavolgbaar.
  - **Conclusie:** generieke MCP-koppelingen voor het model botsen met ADR-008/010 en met de brongetrouwheid. MCP is
    wél een goede **transportlaag** onder een getypeerde bron-tool: de code roept de externe server aan, normaliseert
    het resultaat naar het contract en het model ziet alleen de eigen tool. Zo werkt de GraphDB-MCP nu ook.

## 3. Bronnen voor wetsanalyse

De beoordeling kijkt naar *bron* (letterlijk citeerbaar, met een eigen vindplaats in grounding) en naar *context* (hulp
bij interpretatie, nooit een vindplaats van wettekst).

| Bron | Wat het oplevert voor de methode | API / formaat | Licentie | Citeerbaar (identifier) | Oordeel |
|---|---|---|---|---|---|
| **wetten.overheid.nl / BWB + WTI** | de wettekst zelf, de grondslagen en de relaties | repository-XML, XSD, WTI | CC0 | jci, BWB-id | is er al, de kern |
| **Officiële bekendmakingen: Stb, Stcrt, Kamerstukken** | wetsgeschiedenis: MvT, nota's, amendementen, het nader rapport; onmisbaar voor duiding, begrippen en de bedoeling van de wetgever (activiteit 2/3) | SRU 2.0 (KOOP, collectie `officielepublicaties`; Staten-Generaal Digitaal voor oudere stukken), XML/HTML/PDF per publicatie | CC0 | stabiel: `kst-<dossier>-<nr>`, `stb-<jaar>-<nr>`, `stcrt-…`, met paginering in het document | **hoge waarde** |
| **Raad van State: adviezen** | wetgevingsadvies over de bedoeling en de knelpunten | eigen website. Een advies over een wetsvoorstel staat ook als Kamerstuk ("advies RvS en nader rapport") in de bekendmakingen | openbaar (Woo, sinds 2022 zelf gepubliceerd); geen open API gevonden | via het Kamerstuknummer wel | **via de Kamerstukken**, geen eigen connector |
| **Rechtspraak open data (ECLI)** | hoe een bepaling in de praktijk wordt uitgelegd; ondersteunt duiding en begripsbetekenis | REST: eerst de ECLI-index op metadata, dan het document per ECLI. Geen vrije tekst, maximaal 10 verzoeken per seconde. ~800k uitspraken met tekst | dataset als publiek domein/CC0 gemeld; **toetsen**, want secundaire bronnen spreken dat tegen | ECLI, sterk | middel-hoog |
| **Linked Data Overheid (LiDO)** | de verwijzingen tussen uitspraken, Kamerstukken en wetsartikelen (LinkExtractor, Juriconnect), juist de ingang "welke uitspraken gaan over art. X" | RDF/SPARQL op `linkeddata.overheid.nl`; code onder EUPL (2025). **De huidige endpoints zijn niet bevestigd** | open | jci ↔ ECLI | **hoge waarde, als ingang** |
| **EUR-Lex / CELLAR (ELI)** | het EU-recht bij implementatiewetgeving (richtlijn ↔ Nederlandse bepaling), het conformiteitsdenken | CELLAR SPARQL + REST, ELI; webservice voor geregistreerde gebruikers | hergebruik toegestaan met bronvermelding | CELEX, ELI, sterk | middel; alleen voor werkgebieden met een EU-herkomst |
| **TOOI** | vaste URI's voor organisaties en documenttypen | SKOS/RDF, CC0 | CC0 | URI | is er (ministeries); uitbreiden naar documentsoorten als de Kamerstukken komen |
| **Begrippenkaders** (Stelselcatalogus Omgevingswet, begrippenkaders van organisaties in NL-SBB) | bestaande definities hergebruiken en vergelijken (activiteit 3, ADR-003/006) | Stelselcatalogus: REST "Catalogus opvragen", volgens een oud document met API-key; andere kaders als SKOS/NL-SBB-download of SPARQL | per kader verschillend | concept-URI | **context**, laag-middel; per domein |
| **Juriconnect / jci** | de standaard voor verwijzingen naar wetgeving | specificatie, geen dienst | open | – | al in gebruik (`bronmodel.vindplaats`); de basis voor elke nieuwe koppeling |
| **Regelbeheer / RegelSpraak** | formalisering (een latere fase) | specificaties (lokaal, gitignored) | – | – | **later**, buiten deze afweging |
| **Interne bronnen** (Confluence, SharePoint, documenten) | beleid, werkinstructies en eerdere analyses van de organisatie | bestaande MCP-connectors (Atlassian, Microsoft) met OAuth per gebruiker | vertrouwelijk | geen jci; hoogstens een document-URL plus versie | **context**, en pas na ADR-007 |

**Kwaliteit in het kort.** De KOOP-bronnen zijn officieel en stabiel. Rechtspraak is officieel, maar de selectie van
gepubliceerde uitspraken is onvolledig. Bij LiDO hangt de dekking af van automatische linkextractie, met fout-positieven
en gemiste koppelingen. EUR-Lex is gezaghebbend. Interne wiki's zijn niet officieel en hebben vaak een onduidelijke
versie.

## 4. Architectuur

**4.1 Getypeerde bron-tools in plaats van vrije toegang.** Elke externe bron krijgt een eigen, kleine set tools in
`agent/tools/` (bijvoorbeeld `zoek_kamerstukken`, `get_kamerstuk`, `uitspraken_bij_bepaling`, `get_uitspraak`). De
regels zijn dezelfde als voor de graaftools:

- elke tool levert het resultaatcontract en begrenst op een natuurlijke eenheid, zoals een paragraaf van de MvT of een
  rechtsoverweging;
- de tool bouwt zijn query zelf, niet het model;
- hij is toegewezen aan een specialist en heeft een beschrijving en een smoke-controle (`test_toolverdeling`);
- een eventuele MCP-client of HTTP-adapter zit achter een port (zoals `GraphPort`), met een fake voor de tests.

**4.2 Vindplaats en grounding.** `bronmodel.vindplaats` krijgt een `soort` per brontype: `wettekst` (jci, zoals nu),
`kamerstuk` (kst-id plus onderdeel), `uitspraak` (ECLI plus overweging) en `eu` (CELEX/ELI plus artikel).

- `provenance.iter_refs` herkent die identifiers;
- `grounding.check_grounding` toetst citaten letterlijk tegen de trace, zoals nu;
- het antwoordsjabloon (ADR-008) laat per blok zien uit welk soort bron het komt (`door` krijgt dus een brontype);
- **een uitspraak of een MvT onderbouwt nooit wat de wet zegt.** Een uitspraak onderbouwt een uitleg, en het sjabloon
  houdt die twee uit elkaar.

**4.3 Bron of context.** Een *bron* heeft een officiële, stabiele identifier en een letterlijke tekst. Dat geldt voor
alles in de tabel behalve de begrippenkaders en de interne documenten. *Context* (een begrippenkader, een wiki,
werkgebiednotities) mag het model sturen, maar komt nooit in de bronnenlijst en wordt in de werkplek gemarkeerd als
"context, geen vindplaats". Dat sluit aan op de bestaande rollen *analyseren/context* in de bronselectie.

**4.4 In de graaf of live?**

- **In de graaf, via de importer.** Wat stabiel, gestructureerd en relationeel is en waarop je wilt zoeken of rangschikken:
  - de koppelingen jci ↔ ECLI uit LiDO;
  - de verwijzingen bepaling ↔ Kamerstuk (totstandkoming; mogelijk al deels in de WTI, dat moet onderzocht worden);
  - EU-implementatierelaties;
  - de TOOI-documentsoorten;
  - de metadata van Kamerstukken bij een regeling, zonder volledige tekst.

  Het idempotente patroon met een named graph per bron past daarop, en de graafwacht dekt het verlies van de graaf.
- **Live, via een tool met een cache.** De volledige teksten: een uitspraak, een MvT, een EU-artikel. Er zijn er te
  veel om alles te importeren, de licentie of het rate-limit laat een volledige download vaak niet toe (bij Rechtspraak
  expliciet), en een analist heeft er per werkgebied maar een paar nodig.
  - Er komt een cache per identifier met een hash (zoals de teksthash in `bronmodel`), zodat een citaat later
    herleidbaar blijft.
  - Wat in een bronselectie wordt opgenomen, bevriest de api als snapshot, zodat het dossier reproduceerbaar is.
- **Dus:** de graaf weet *dat* en *waar*, de tool haalt *wat*.

**4.5 De vertrouwensgrens.**

- **Injectie.** Externe tekst (uitspraken, Kamerstukken, en zeker wiki's) is data. Ze gaat alleen als toolresultaat naar
  het model, nooit in de systeemtekst. Geen bron-tool schrijft, en schrijfacties blijven bij de taakagents met
  bevestiging.
- **Toolbeschrijvingen zijn van ons, niet van de server.** Dat sluit tool poisoning en rug pulls uit, en het is een
  belangrijk voordeel van getypeerde tools boven een vrije MCP-koppeling.
- **AVG.** Gepubliceerde uitspraken zijn geanonimiseerd, maar niet altijd volledig. Kamerstukken zijn openbaar. Interne
  bronnen kunnen persoonsgegevens of casusgegevens bevatten, en die gaan zonder besluit over de verwerker (ADR-007)
  niet naar het model.
- **Uitgaand verkeer.** Een vaste allowlist van hosts per adapter in de configuratie, geen URL's die het model kiest.
  Telemetrie per aanroep (`tool_execution`-events bestaan al).

**4.6 Beheer, als connectors komen.**

- Een register `/v1/admin/bronnen` naar het model van de modelprofielen: per bron aan of uit per straat, aan of uit per
  werkgebied, een rate-limit en de credentials versleuteld met Fernet (alleen nodig voor de EUR-Lex-webservice of de
  Stelselcatalogus).
- **Openbare bronnen zijn organisatiebreed, zonder login per gebruiker.** Dat past bij het gedeelde werkgebied.
- Gebruik per bron gaat in het bestaande journaal; externe aanroepen tellen als aanroepen, de modeltokens zoals nu.
- Interne connectors met OAuth per gebruiker zijn pas aan de orde na ADR-007, en dan als *context* per gebruiker die
  niet in een gedeeld dossier landt.

## 5. Aanbeveling

**Top vijf, gerangschikt op de verhouding tussen waarde en moeite:**

1. **Kamerstukken en de MvT via de SRU van KOOP.**
   - *Waarde:* hoog, want wetsgeschiedenis is de hoofdbron voor duiding en begripsbetekenis, en het advies van de RvS
     komt mee.
   - *Moeite:* middel. KOOP en de XML ken je al van de importer, en de licentie is CC0.
   - *Vorm:* live tools met een cache, plus de verwijzing regeling ↔ dossier in de graaf.
2. **LiDO-koppelingen tussen bepaling en uitspraak in de graaf.**
   - *Waarde:* hoog als ingang ("welke uitspraken gaan over art. 9 Iw").
   - *Moeite:* laag tot middel, als het endpoint bruikbaar blijkt: een importstap met een named graph.
   - *Eerst:* het endpoint en de dekking bevestigen.
3. **Uitspraken per ECLI (Rechtspraak open data).**
   - *Waarde:* middel-hoog.
   - *Moeite:* laag zodra punt 2 de ECLI's levert, want ophalen per ECLI is eenvoudig.
   - *Eerst:* de licentie toetsen, en het rate-limit respecteren.
4. **EUR-Lex/CELLAR voor de implementatierelaties.**
   - *Waarde:* middel, alleen voor werkgebieden met een EU-herkomst.
   - *Moeite:* middel-hoog (een ander datamodel, de webservice vraagt registratie).
5. **Externe begrippenkaders als context voor de begrippen-agent.**
   - *Waarde:* middel, per domein.
   - *Moeite:* middel. Het NL-SBB-contract (ADR-003) ligt er al, de import per kader niet.

**Eerste stap.** Schrijf ADR-013 *Externe bronnen* (het brontype in de vindplaats, bron of context, graaf of live, de
vertrouwensgrens). Doe daarna één verkenning op Kamerstukken, alleen lezend en achter een vlag:

- tools `zoek_kamerstukken` en `get_kamerstuk` met het resultaatcontract;
- het soort `kamerstuk` in `bronmodel.vindplaats`, `provenance` en `grounding`;
- een paar cases in de kwaliteitsset (bijvoorbeeld de MvT bij een bepaling uit de Invorderingswet);
- meten zoals ADR-010 vraagt: tokens, duur en het aandeel gegronde citaten, in drie runs.

LiDO-endpoint en de licentie van Rechtspraak bevestigen kan parallel, zonder code.

**Wat we bewust niet doen:**

- Geen vrije MCP-koppeling waarbij het model zelf vreemde tools aanroept. Dat geldt ook voor de `mcp_servers`-connector
  van de Messages API: die is beta, valt buiten ZDR, levert geen resultaatcontract en geen vindplaats, en vergroot de
  prefix.
- Geen connectors die gebruikers zelf toevoegen in de beheertab.
- Geen interne bronnen (Confluence of SharePoint) zolang ADR-007 open staat.
- Geen bulkimport van de volledige teksten van uitspraken of Kamerstukken.
- Geen aparte connector voor de RvS (die loopt via de Kamerstukken).
- Geen RegelSpraak nu.
- Geen upgrade naar MCP 2026-07-28 zolang GraphDB de vorige versie spreekt.

**Vraagt dit een ADR?** Ja. Een nieuw vindplaatstype verandert het gedeelde contract in `packages/bronmodel` (api én
graph-qa), de grounding en de antwoordsjablonen (ADR-008). Het legt ook vast wat bron en wat context is. ADR-010 vraagt
per nieuwe taakagent of workflow toch al een contract.

## Te kiezen door de gebruiker

- A. Alleen deze analyse in de repo zetten (`docs/architectuur/onderzoek-connectors-en-bronnen-2026-11.md`) en stoppen.
- B. Daarna ADR-013 uitschrijven (concept).
- C. Daarna de verkenning op Kamerstukken plannen, met de PR-indeling.
- D. Eerst het LiDO-endpoint en de licentie van Rechtspraak laten toetsen (alleen lezen).

## Verificatie

- Analyse: bevat geen hostnamen of IP's van de omgeving (`geen-omgevingsgegevens.yml` draait op de PR), alleen
  publieke URL's van de bronnen.
- Nog niet bevestigd en daarom in de tekst gemarkeerd: de huidige LiDO-endpoints, de exacte licentie van Rechtspraak,
  de toegang tot de API van de Stelselcatalogus, en of de WTI de Kamerstukken bij de totstandkoming al noemt.

## Bronnen (geraadpleegd 7 nov 2026)

- MCP-specificatie 2026-07-28, changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- MCP-autorisatie: https://modelcontextprotocol.io/specification/latest/basic/authorization
- Claude MCP-connector (Messages API): https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
- Connectors in Claude: https://support.claude.com/en/articles/11176164-use-connectors
- Rechtspraak open data: https://www.rechtspraak.nl/uitspraken/open-data , https://data.overheid.nl/dataset/uitspraken-rechtspraak-nl
- Officiële bekendmakingen (SRU, CC0): https://data.overheid.nl/dataset/officiele-bekendmakingen
- EUR-Lex hergebruik: https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html
- Linked Data Overheid onder EUPL: https://interoperable-europe.ec.europa.eu/collection/open-source-observatory-osor/news/code-linked-data-overheid-available-under-eupl
- Raad van State publiceert adviezen: https://njb.nl/nieuws/raad-van-state-maakt-sinds-1-mei-zelf-zijn-adviezen-openbaar-1
- Stelselcatalogus Omgevingswet: https://iplo.nl/digitaal-stelsel/stelselcatalogus-omgevingswet/lokale-software-aansluiten/
- MCP tool poisoning: https://hidekazu-konishi.com/entry/mcp_tool_poisoning_defense_guide.html
