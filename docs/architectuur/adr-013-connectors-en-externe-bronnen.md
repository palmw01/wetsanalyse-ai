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
| **1a** | het soort vindplaats in `packages/bronmodel` (`extern.py`) + `provenance`/`grounding`/werkplek (PR 1); het sjabloon (`door` met brontype) komt met de eerste tool die externe tekst levert; bronconnector **Kamerstukken** (`zoek_kamerstukken`, `get_kamerstuk`) achter een vlag | dit ADR |
| **1b** | register `/v1/admin/connectors` + beheertab; het menu *Bronnen en tools* per gesprek, de standaard per werkgebied, de stand op het gesprek | 1a |
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
