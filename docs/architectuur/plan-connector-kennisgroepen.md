# Plan: de kennisgroepstandpunten van de Belastingdienst als bronconnector

> Onderzoek en plan, 13 nov 2026. De open vragen zijn beantwoord (§8); het bouwen is begonnen. Oorspronkelijk: bouwen pas na akkoord van de gebruiker op de open
> vragen (§8). Dit plan sluit aan op [ADR-013](adr-013-connectors-en-externe-bronnen.md) (connectors), ADR-008
> (sjablonen), ADR-014 (catalogus) en ADR-016 §B5 (het agentprofiel noemt zijn connectors).

## In het kort

**Het kan, en het past in de bestaande connectorvorm.** De kennisgroepstandpunten staan op een eigen website van de
Belastingdienst. Die site heeft een gedocumenteerde, openbare REST API zonder sleutel. De tekst valt onder CC0, en de
robots.txt staat het ophalen toe. De hele verzameling is klein: 1180 publicaties, op te halen in 12 verzoeken. Elk
standpunt heeft een stabiel kenmerk (`KG:013:2026:4`), een vaste opbouw (Aanleiding, Vraag, Antwoord, Beschouwing) en
metadata (kennisgroep, belastingsoort, rubriek en datums).

Er zijn drie punten waarop de connector anders is dan de vier bestaande:

1. **De status.** Een standpunt is beleid van de Belastingdienst en bindt de inspecteur. Het bindt de rechter en de
   belastingplichtige niet, en het is geen wet. Daarom krijgt het een eigen brontype (`standpunt`) en een eigen regel in
   het antwoord, en komt het nooit in de plaats van de bepaling.
2. **Zoeken per artikel kan de bron zelf niet.** De API heeft geen veld voor het wetsartikel, en de zoekfunctie van
   WordPress is zwak (zie §1.4). Het voorstel is daarom een index in de graaf, gevuld door een job, naast de wet maar
   gescheiden van de wettekst. Het lezen gebeurt live per standpunt. Zo werkt het ook bij ADR-013 §4.4: de graaf weet
   *dat* en *waar*, de tool haalt *wat*.
3. **Intrekken en vervangen.** 130 publicaties zijn ingetrokken of vervallen, en dat staat alleen in de titel en de
   tekst. Lex moet dat zien en zeggen.

---

## 1. Bevindingen

Alles hieronder is op 13 nov 2026 gecontroleerd op de openbare site, zonder in te loggen. Voor de analyse is de volledige
verzameling één keer opgehaald via de API die de site aanbiedt: 12 verzoeken van 100, met 3 seconden ertussen. Die
gegevens staan niet in de repo.

### 1.1 Waar en in welke vorm

- **De site.** De standpunten staan op <https://kennisgroepen.belastingdienst.nl/>, sinds 30 maart 2023, en met
  standpunten vanaf 2022. Het is een WordPress-site. Een standpunt heeft een eigen pagina onder `/publicaties/<slug>/`.
- **De REST API.** De pagina *Integratie* (<https://kennisgroepen.belastingdienst.nl/integratie/>) nodigt ontwikkelaars uit
  om de standaard WordPress REST API te gebruiken:
  - `GET /wp-json/wp/v2/wt_publication` geeft de lijst, met paginering (`per_page` tot 100, `page`) en de kopregels
    `X-WP-Total` en `X-WP-TotalPages`;
  - `GET /wp-json/wp/v2/wt_publication/<id>` geeft één publicatie;
  - je kunt filteren op datum met `before`, `after`, `modified_before` en `modified_after` (ISO 8601);
  - `_embed` voegt de namen van de taxonomietermen toe;
  - filteren op een term-id werkt ook, bijvoorbeeld `wt_publication_tag=155` voor KG Auto, met 29 resultaten.
- **Wat niet werkt, al staat het in de documentatie.** De lijsten van de taxonomieën zelf
  (`/wp-json/wp/v2/wt_publication_category` en `…_tag`), de wortel `/wp-json/` en de revisies van een publicatie geven
  401 ("Alleen geauthenticeerde gebruikers"). De namen van de termen komen wel mee via `_embed`, en de slugs staan in
  `class_list`.
- **Andere ingangen.** De site heeft een sitemap met 1180 publicaties (`/wt_publication-sitemap.xml` en `…2.xml`) en een
  RSS-feed van de nieuwsberichten (`/feed/`). Een nieuwsbericht meldt een nieuw of herzien standpunt en verwijst naar de
  publicatie. Een SRU, een dataset op data.overheid.nl of een bundel in de officiële bekendmakingen hebben we niet
  gevonden.
- **Oudere standpunten.** Standpunten van vóór 2022 zijn alleen in stukken openbaar gemaakt via Woo-deelbesluiten op
  rijksoverheid.nl, als PDF. Een voorbeeld is `KG:013:2018:0173`, dat het nieuwe `KG:013:2026:4` intrekt. Die stukken
  vallen buiten dit plan (zie §6).

### 1.2 Licentie en hergebruik

- **CC0.** Volgens <https://kennisgroepen.belastingdienst.nl/copyright/> mag de tekst van de site zonder voorwaarden
  worden hergebruikt. Naamsvermelding hoeft niet, maar je mag niet de indruk wekken dat de Belastingdienst je tekst heeft
  goedgekeurd. Portretrecht en privacyrecht blijven gelden.
- **robots.txt.** Die sluit alleen `?mailpoet_router` uit; de rest is toegestaan.
- **Disclaimer.** Volgens <https://kennisgroepen.belastingdienst.nl/disclaimer/> is de informatie actueel naar de stand op
  de publicatiedatum. De standpunten worden actief openbaar gemaakt op grond van art. 3.1 Woo, maar **niet alle
  standpunten worden gepubliceerd**: een standpunt dat herleidbaar is naar een belastingplichtige (art. 67 AWR) of onder
  een weigeringsgrond van de Woo valt, wordt niet gepubliceerd. Tot 30 maart 2023 hadden standpunten een aparte
  vaststellingsdatum; daarna is die gelijk aan de publicatiedatum.
- **Onderhoud.** Onderhoud en incidenten aan de site en de API worden tijdens kantooruren afgehandeld (pagina
  *Integratie*). Er is geen gepubliceerde rate-limit.

### 1.3 Wat er in een publicatie staat

Velden uit de API, met wat we in de 1180 publicaties vonden:

| veld | inhoud | dekking |
|---|---|---|
| `id` | WordPress-id, stabiel per publicatie | 1180/1180 |
| `title.rendered` | `KG:<groep>:<jaar>:<nr> <onderwerp>`, soms met `[INGETROKKEN]` of `[VERVALLEN]` ervoor | het kenmerk staat in 1177 titels; 3 hebben een afwijkende vorm (`KG:2026:211:19`, `KG 202:2025:26`, `KG:204:2023: 5`) |
| `date`, `modified` | publicatiedatum en laatste wijziging | 1180; bij 504 publicaties lag de wijziging in een latere maand dan de publicatie |
| `content.rendered` | de tekst in HTML, met `h2`-koppen | mediaan 6.400 tekens, p90 13.800, max 41.000 |
| `meta.belastingsoort` | bijvoorbeeld "Inkomstenbelasting (IB)" | 1180 |
| `meta.rubriek`, `meta.subrubriek` | onderwerp, 132 rubrieken | grotendeels |
| `meta.cmd_vaststellingsdatum` | `JJJJMMDD` | 301 (de standpunten van vóór 30 maart 2023) |
| `wt_publication_category` | het middel, zoals Inkomstenbelasting, Invordering of AWR | 16 waarden |
| `wt_publication_tag` | de kennisgroep, zoals "KG Invordering (INV)" | 27 kennisgroepen |
| `message_types` | Standpunt (1177) of Informatie | 1180 |
| `slug`, `link` | de URL van de publicatie | 1180 |

**De opbouw van de tekst** is vast. De koppen zijn: Aanleiding (1165), Vraag of Vragen (1167), Antwoord of Antwoorden
(1170) en Beschouwing (1128). Soms volgen Voetnoten (142), een blok *Let op!* met *Intrekking*, of een Bijlage. Er zijn
31 tabellen en 45 afbeeldingen. 194 publicaties linken naar een PDF.

**Verwijzingen.**

- Naar de wet:
  - 349 standpunten linken naar `wetten.overheid.nl`. Die links zijn meestal een jci 1.3 met `hoofdstuk`, `artikel`, de
    zichtdatum `z` en de geldigheidsdatum `g`. Soms is het alleen een BWB-id met een datum.
  - Bijna alle standpunten (1122) noemen een artikel in de tekst, vooral met een afkorting, zoals "artikel 10, eerste lid,
    Wet BPM 1992", "Wet IB 2001", "AWR" of "Iw 1990".
- Naar andere bronnen:
  - 546 standpunten noemen een ECLI, meestal met een deeplink naar de Rechtspraak;
  - er zijn ruim 800 links naar Kamerstukken (`kst-…`) en 254 naar de Staatscourant (`stcrt-…`);
  - er zijn ook links naar EUR-Lex en Curia.

  Dat zijn precies de id's die de connectors Rechtspraak, Kamerstukken en Bekendmakingen al lezen.

**Overlap met de graaf** (de zeven regelingen van `bwbIds` in `deploy/azure/main.bicep`). We telden de standpunten die de
regeling noemen, op naam, afkorting of BWB-id:

- AWR: 125;
- Invorderingswet 1990: 36;
- Awb: 31;
- Leidraad Invordering 2008: 18;
- Uitvoeringsregeling Iw 1990: 10.

De meeste standpunten gaan over de Wet IB 2001 en de Wet Vpb 1969. Die regelingen staan niet in de graaf, maar de
connector *Wetgeving buiten de kennisgraaf* (`wetgeving_live`) kan ze lezen.

### 1.4 Zoeken bij de bron

De parameter `search` van WordPress is een eenvoudige tekstmatch op titel en inhoud. `search=bestuurdersaansprakelijkheid`
gaf één treffer, en dat klopt: het woord komt in één publicatie voor. Maar de zoekfunctie rangschikt niet, kent geen
verbuigingen, en kan niet zoeken op een artikel, alleen op een tekenreeks. Voor "welke standpunten gaan over art. 36 Iw"
moet je per artikel kunnen zoeken. Daarvoor is een eigen index nodig (§2.3).

### 1.5 Status van een standpunt

- Volgens de pagina *Over de Kennisgroepen* "kunnen [ze] worden aangemerkt als beleid van de Belastingdienst". Ze geven
  uitleg aan wet- en regelgeving in een specifiek geval en zijn bindend voor de inspecteurs. De site verwijst daarvoor
  naar Aanhangsel Handelingen II 2022/23, nr. 459.
- Een standpunt is dus **geen wet en geen rechtspraak**. Het is de uitleg van de uitvoerder. De rechter is er niet aan
  gebonden. Of een belastingplichtige er een beroep op kan doen (vertrouwensbeginsel, gelijkheidsbeginsel), is een
  juridische vraag. Die beantwoordt Lex niet.
- **Intrekken en vervangen.** 111 titels beginnen met `[INGETROKKEN]` (in wisselende schrijfwijzen) en 19 met
  `[VERVALLEN]`. Een nieuw standpunt kan een ouder standpunt intrekken: dan staat er onder *Let op! / Intrekking* een tekst
  zoals "Met dit standpunt wordt … KG:013:2018:0173 … ingetrokken". Een gestructureerd veld `vervangt` of
  `vervangen door` is er niet. Een herzien standpunt krijgt een nieuw kenmerk, en het nieuwsbericht spreekt dan van
  "geactualiseerd".
- **Versies.** De revisies zijn niet openbaar (401). Een wijziging zie je alleen aan `modified` en aan de tekst zelf.

### 1.6 AVG

- Standpunten gaan over geanonimiseerde casussen: "de heer Z", "BV Z", "A-B". Wat herleidbaar blijft, wordt niet
  gepubliceerd (disclaimer, art. 67 AWR).
- Er staan wel namen in van mensen in een openbare rol: auteurs uit de vakliteratuur ("mr. F.C. de Hosson, WFR 1993/430"),
  advocaten-generaal en Kamerleden in een citaat uit de Handelingen. Dat is hetzelfde regime als bij Kamerstukken en
  rechtspraak (ADR-013, *De AVG-poort*): openbare, gepubliceerde stukken.
- Lex herleidt geen partij uit een casus. Dezelfde regel staat al bij Rechtspraak.

### 1.7 Haalbaarheid

- **Omvang.** 1180 publicaties en ongeveer 19 MB JSON met `_embed`. Er komen ongeveer 15 tot 25 per maand bij; in juli
  2026 ging het in één keer om 178 wijzigingen. Alles ophalen kost 12 verzoeken van ongeveer 3 seconden. Bijwerken met
  `modified_after` kost meestal één verzoek.
- **Kosten.** Geen: er is geen sleutel en geen abonnement.
- **Stabiliteit.**
  - De API is de standaard WordPress API, zonder versiebeleid van de Belastingdienst.
  - Een deel van de documentatie klopt niet: de taxonomie-endpoints geven 401.
  - Er staat een WAF of cache voor de site (`X-MicroCache`, cookies `TS…`).
  - De vorm van de titel is niet strikt: 3 van de 1180 kenmerken wijken af.
  - Een live-proef per dag (`bronnenwacht.yml`) moet dit bewaken, zoals bij de andere connectors.

---

## 2. Ontwerp

Het ontwerp volgt de checklist van ADR-013 (*Een nieuwe connector toevoegen*). Er komt geen prompttekst, route, sjabloon
of werkplekcomponent per connector bij, behalve wat hieronder staat als **nieuw voor alle connectors**.

### 2.1 Soort vindplaats: `standpunt`

- `bronmodel.extern`:
  - het brontype `standpunt` komt in `BRONTYPEN`;
  - het id krijgt de vorm `kg:<groep>:<jaar>:<nr>` (kleine letters, zonder voorloopnullen in het nummer), bijvoorbeeld
    `kg:013:2026:4`;
  - `externe_vindplaats` leest ook de citeervorm `KG:013:2026:4`, en de jci-vectoren krijgen gevallen, ook de drie
    afwijkende vormen.
- **Een kenmerk is geen WordPress-id.** Het kenmerk is de vindplaats, de WordPress-id is alleen het adres bij de API. De
  index (§2.3) koppelt ze. Voor de drie afwijkende titels normaliseert de adapter het kenmerk, met een test op precies
  die drie.
- In de frontend komt in `lib/bronnen.ts` (`BRONTYPE_NAAM`) de groep **"Kennisgroepstandpunten (beleid)"**, na
  `uitspraak`.

### 2.2 De connectorbeschrijving (`bronmodel/connectors.py`)

| veld | voorstel |
|---|---|
| `naam` / `label` | `kennisgroepen` / "Kennisgroepstandpunten" |
| `brontype` / `groep` | `standpunt` / "Kennisgroepstandpunten (beleid)" |
| `dekt` | de gepubliceerde standpunten van de kennisgroepen van de Belastingdienst (vanaf 2022): hoe de Belastingdienst een fiscale bepaling uitlegt en toepast in een specifiek geval |
| `signalen` | `kennisgroep(en)?`, `kennisgroepstandpunt(en)?`, `KG:\d{3}:\d{4}:\d+`, `standpunt van de belastingdienst`. Niet het kale "beleid" of "standpunt": dat zijn gewone woorden in een vraag |
| `aanwijzingen` | "hoe past de Belastingdienst … toe", "wat vindt de inspecteur", "uitvoeringspraktijk" |
| `tools` / `leestool` / `lees_argument` | `zoek_standpunten`, `get_standpunt` / `get_standpunt` / `id` |
| `id_prefixen` / `voorbeeld_id` | `("kg:",)` / `kg:013:2026:4` |
| `citeervormen` | `KG:013:2026:4`, "kennisgroepstandpunt KG:13:2026:4" → `kg:{groep}:{jaar}:{nr}` |
| `rol_in_antwoord` | een standpunt laat zien hoe de Belastingdienst een bepaling uitlegt en toepast. Het is beleid dat de inspecteur bindt, geen wet en geen rechtspraak. Het onderbouwt nooit wat de wet zegt; dat doet alleen de opgehaalde bepaling. Noem altijd het kenmerk en de datum. Een ingetrokken of vervallen standpunt is geen geldend beleid. Herleid nooit wie een partij is |
| `kop_in_antwoord` | "Uit het beleid van de Belastingdienst (kennisgroepstandpunt)" |
| `grenzen` | alleen gepubliceerde standpunten vanaf 2022; niet alle standpunten worden gepubliceerd, dus geen treffer betekent niet dat er geen standpunt is. Oudere standpunten, die alleen via Woo-besluiten openbaar zijn, ontbreken. Een standpunt geldt naar de wet op de publicatiedatum. De koppeling met een artikel komt uit de links van de Belastingdienst en uit herkenning in de tekst |
| `levert` / `niet_in_tekst` | alinea's per kop (Aanleiding, Vraag, Antwoord, Beschouwing), voetnoten en tabellen / afbeeldingen en gekoppelde PDF's |
| `zonder_tekst` | "geen tekst bij de Belastingdienst" |
| `verzamelnamen` / `soorten` | "kennisgroepstandpunten", "standpunten van de kennisgroepen" / geen; er is één soort |
| `organen` | de 27 kennisgroepen, als filter `kennisgroep` |
| `voorbeeldvragen` | zie de meting (§4) |

**Metadata.** Er komen een paar sleutels bij `METADATA_SLEUTELS`. Ze zijn generiek, zodat ook andere connectors ze
kunnen gebruiken; daarom staan ze in de eerste PR.

| sleutel | label | bron | nieuw? |
|---|---|---|---|
| `datum` | publicatiedatum (vóór 30 mrt 2023: de vaststellingsdatum) | `cmd_vaststellingsdatum`, anders `date` | nee |
| `gepubliceerd` / `gewijzigd` | gepubliceerd / laatst bijgewerkt | `date` / `modified` | nee |
| `titel`, `nummer`, `jaar` | onderwerp, volgnummer, jaar uit het kenmerk | titel | nee |
| `orgaan` | de kennisgroep | `wt_publication_tag` | nee |
| `rechtsgebied` | middel en belastingsoort | `wt_publication_category`, `meta.belastingsoort` | nee |
| `reeks` | rubriek › subrubriek | `meta.rubriek`, `meta.subrubriek` | nee |
| `status` | geldend, ingetrokken of vervallen | voorvoegsel in de titel | nee (nieuwe waarden) |
| `wetsverwijzing` | de bepalingen die het standpunt noemt | index (§2.3) | nee |
| `vervangt` / `vervangen_door` | de kenmerken die dit standpunt intrekt, of het standpunt dat dit intrekt | tekst onder *Intrekking*, in beide richtingen afgeleid in de index | **ja** (lijst) |
| `tekststand` | of het artikel sinds het standpunt is gewijzigd | index tegen `bwb:inwerking` | nee (zoals bij Rechtspraak) |
| `leesbaar` | of er tekst is | `content` | nee |

`standaard_datum` is `datum`, en `volgordes` is `relevantie`, `nieuwste` en `oudste`.

### 2.3 Zoeken via een index in de graaf, lezen live

**Waarom een index.** De bron kan niet per artikel zoeken (§1.4). LiDO kwam niet in de graaf, omdat de volledigheid via
de services niet aan te tonen was en het om duizenden aanroepen ging (ADR-013, fase 1c). Hier is het andersom: de hele
set is 12 verzoeken, en `X-WP-Total` toont of alles binnen is.

**Waar de index staat.** In een eigen named graph `urn:wa:graph:kennisgroepen`, met een register zoals bij de
begrippen. Per standpunt staan daarin:

- het kenmerk, de WordPress-id en de link;
- de datums, de status, de kennisgroep, het middel, de belastingsoort en de rubrieken;
- een hash van de tekst;
- de tekst per kop, voor zoeken op woorden;
- **de bepalingen die het standpunt noemt**, elk met een herkomst:
  - `link`: een jci-link van de Belastingdienst zelf. Die is zeker, en wordt herleid naar een `urn:bwb:`-IRI als de
    regeling in de graaf staat, en anders naar de jci;
  - `tekst`: herkend in de lopende tekst, met de citeertitels en afkortingen. De afkortingen komen uit de WTI voor de
    regelingen in de graaf en uit de SRU van de BWB (`afkorting`) voor de andere. Die herkenning is minder zeker, en het
    resultaat zegt dat ook, net als bij LiDO ("automatisch herkend").

**Wie de index vult.** Een job naast de BWB-import:

- `bwb-import` krijgt een tweede modus, `--kennisgroepen`, of er komt een kleine eigen job; dat is open vraag V2;
- de job haalt bij elke import alles op, en bijwerken gaat met `modified_after`;
- de graafwacht vult de index ook aan na verlies, zoals bij de wet.

De wettekst blijft gescheiden van de standpunten:

- de standpunten komen **niet** in de FTS-connector en de similarity-index van de wet;
- er komt een eigen FTS-connector, of de zoektool doet een SPARQL-filter op de eigen named graph;
- een poorttest bewaakt dat `search_wetgeving`, `semantic_search` en de graaftools nooit een standpunt teruggeven, zoals
  nu al voor de annotatielagen.

**Lezen.** `get_standpunt` haalt de publicatie live op bij de API, met `/wt_publication/<id>`. De tekst wordt dan
geparst tot genummerde rijen `{nr, tekst, kop, soort}`, volgens het leestoolcontract. Het resultaat draagt
`stuk: {id, label, link, bron_hash, gewijzigd}`. Wijkt de hash af van de index, dan staat er `gewijzigd: true`. Er is een
cache met validatie op `modified`, zoals bij `sru_koop`. Is de bron onbereikbaar, dan leest de tool de tekst uit de index
met `gevalideerd: false`.

**Alternatief zonder graaf (A).** Alles live: zoeken met `search` en filters, en per artikel alleen via de jci-tekst in
`search`. Dat is eenvoudiger, maar zoeken per artikel werkt dan niet betrouwbaar. Dit alternatief is alleen geschikt als
eerste proef (open vraag V2).

### 2.4 De tools

- **`zoek_standpunten`**. Argumenten:
  - `bwb_id` + `artikel` (per bepaling, uit de index; het lid als filter als het herkend is);
  - `woorden`;
  - `kennisgroep`, `middel` of `belastingsoort`;
  - `vanaf` en `tot`;
  - `status` (standaard alleen geldend; `alle` toont ook ingetrokken en vervallen standpunten, met een melding);
  - `volgorde`.

  Het resultaat volgt het resultaatcontract. Per rij staan erin: id, label, datum, status, kennisgroep, de bepaling met
  de herkomst van de koppeling, en `tekststand`. Bij een zoekvraag per artikel staat daarnaast hoeveel standpunten via
  een link en hoeveel via de tekst gekoppeld zijn.
- **`get_standpunt`**. Argumenten:
  - `id` (het kenmerk);
  - optioneel `kop`, om alleen Vraag en Antwoord te lezen. Dat is goed voor de tokens: de mediaan is 6.400 tekens.

  Een ingetrokken standpunt is gewoon te lezen, met `status` en `vervangen_door` bovenaan. Noemt de tekst een ECLI, een
  Kamerstuk of een Stcrt, dan herkent `provenance` die als externe id. Lex kan die dan met de bestaande connectors lezen,
  maar alleen als die aanstaan.
- Beide tools komen in één module `agent/tools/kennisgroep_tools.py` met een `ConnectorModule` in `connectortools.py`, en
  een adapter `agent/adapters/wp_kennisgroepen.py` achter `http_beleid`. Daarin staan:
  - een allowlist met de host;
  - een eigen User-Agent;
  - hoogstens 1 verzoek per seconde.

### 2.5 In het antwoord en in de werkplek: beleid zichtbaar scheiden van wet

Dit is het belangrijkste deel van de brongetrouwheid.

- **Volgorde.** Eerst de bepaling: uit de graaf, of uit `wetgeving_live` als de regeling er niet in staat. Daarna het
  blok `extern` met de kop "Uit het beleid van de Belastingdienst (kennisgroepstandpunt)". Dat is de bestaande regel:
  het blok komt ná de wettekst en vult nooit een `doel`.
- **Een vaste regel boven het blok**, gemaakt door code en niet door het model: *"Beleid van de Belastingdienst, bindend
  voor de inspecteur; geen wet en geen rechtspraak. Stand op [datum]."* Dit wordt een nieuw generiek veld in de
  beschrijving, `status_regel`, zodat Rechtspraak er later ook een kan dragen. Een test toetst dat het blok de regel
  altijd heeft.
- **Een ingetrokken of vervallen standpunt** krijgt de melding van `StandMelding` (`lib/herkomst.ts`), met het vervangende
  kenmerk als link. Het sjabloon laat zo'n standpunt nooit als geldend beleid in een `antwoord` staan; de beweringentoets
  krijgt daar een regel voor.
- **Tekststand.** Is het artikel ná de publicatiedatum van het standpunt gewijzigd (`bwb:inwerking` in de graaf, of de
  toestand bij `wetgeving_live`), dan krijgt het blok de melding "het artikel is sinds dit standpunt gewijzigd". Dat is
  dezelfde taal als bij de LiDO-versies.
- **De bronnenlijst** zet standpunten in de eigen groep, nooit bij de wettekst. Een gevonden standpunt dat niet gelezen
  is, komt er niet in (`alleen_gelezen_extern`).
- **Annoteren.** Een standpunt is geen bronnode en wordt niet geannoteerd. In een bronselectie kan een standpunt later
  hoogstens de rol *context* krijgen: het vervolg *externe bron in de bronselectie* uit ADR-013 geldt hier ook.

### 2.6 Alle metadata en verwijzingen in de koppeling

Op verzoek van de gebruiker (13 nov 2026) neemt de koppeling **alles mee wat de bron levert**: elk veld van de API, elke
verwijzing in de tekst en de nieuwsberichten. Er wordt niets weggelaten omdat het nu niet nodig lijkt. Twee dingen gelden
voor elk veld:

- het staat in de index, met de plek bij de bron waar het vandaan komt;
- het gaat door de tools naar het antwoord en de werkplek, als vaste sleutel uit `METADATA_SLEUTELS` of als
  verwijzing.

Een feit komt dus altijd uit de bron, nooit uit de tekst van het model (ADR-013, *Metadata als deel van het contract*).

**Velden van een publicatie** (`/wp/v2/wt_publication`, gecontroleerd op alle 1180):

| veld bij de bron | in de index | in tool en antwoord |
|---|---|---|
| `id`, `slug`, `link`, `guid` | het adres van de publicatie; `link` is de publieke vindplaats | `stuk.link`; de id alleen intern |
| kenmerk uit `title` | het id `kg:…`, genormaliseerd; de ruwe titel blijft bewaard | `id`, `label` |
| onderwerp uit `title` | de titel zonder kenmerk en zonder voorvoegsel | `titel` |
| voorvoegsel `[INGETROKKEN]` / `[VERVALLEN]` | de status | `status` |
| `date` / `date_gmt` | gepubliceerd | `gepubliceerd`, en `datum` vanaf 30 mrt 2023 |
| `meta.cmd_vaststellingsdatum` (301 gevuld) | vastgesteld | `datum` vóór 30 mrt 2023, met het label "vastgesteld" |
| `modified` / `modified_gmt` | gewijzigd, en het moment waarop de index bijwerkt | `gewijzigd`, `bron_hash` |
| `wt_publication_tag` (+ slug uit `class_list`) | de kennisgroep, met de term-id en de slug als stabiele sleutel | `orgaan`, filter `kennisgroep` |
| `wt_publication_category` | het middel (16 waarden) | `rechtsgebied`, filter `middel` |
| `meta.belastingsoort` (lijst) | de belastingsoorten (20 waarden) | `rechtsgebied`, filter `belastingsoort` |
| `meta.rubriek` / `meta.subrubriek` (lijsten) | de rubrieken (132) en subrubrieken | `reeks`, filter `rubriek` |
| `message_types` | Standpunt of Informatie | `soort`, alleen Standpunt telt als standpunt |
| `content.rendered` | de tekst per kop (h2) en de rijen; de hash | de rijen van `get_standpunt` |
| `excerpt` | niet opgeslagen: WordPress maakt het automatisch van het begin van de Aanleiding, dus het is geen samenvatting van de bron | – |
| `meta.footnotes`, `parent`, `template`, `menu_order` | niet opgeslagen: altijd leeg of 0 in de set. De voetnoten staan in de tekst zelf | – (de live-proef meldt het als ze gevuld raken) |

**Verwijzingen in de tekst.** De aantallen zijn het totaal over alle standpunten, per standpunt uniek geteld. Ze
worden koppelingen in de index, elk met de plek in het standpunt (kop en rij):

| verwijzing | aantal | koppeling |
|---|---|---|
| jci en BWB-id (`wetten.overheid.nl`) | 349 standpunten | `noemt` → bepaling (`urn:bwb:` als ze in de graaf staat, anders jci), herkomst `link` |
| een artikel in de lopende tekst | 1122 standpunten | `noemt` → bepaling, herkomst `tekst` |
| ECLI | 1687 | `noemt` → `uitspraak`; te lezen met de connector Rechtspraak |
| Kamerstuk (`kst-…`) | 747 | `noemt` → `kamerstuk`; te lezen met de connector Kamerstukken |
| Staatscourant / Staatsblad (`stcrt-…`, `stb-…`) | 318 / 83 | `noemt` → `bekendmaking`; te lezen met de connector Bekendmakingen |
| CELEX / Curia | 79 / 95 | `noemt` → `eu`; nog geen connector, dus alleen de link |
| een ander kenmerk `KG:…` of een link naar `/publicaties/…` | 183 / 180 | `noemt_standpunt` → standpunt; onder *Intrekking* wordt het `vervangt` |
| een bijlage (`wp-content/uploads`, meest PDF) | 130 | `bijlage` met de link; wordt niet gelezen (`niet_in_tekst`) |

Zo wordt een standpunt een knooppunt tussen bronnen die Lex al kent. `zoek_standpunten` vindt via `uitspraak` ook "de
standpunten die ECLI X noemen", en via `kamerstuk` ook "de standpunten die op Kamerstuk Y steunen". `get_standpunt`
geeft de verwijzingen per rij mee. `provenance` herkent ze al als externe id, dus de bestaande connectors kunnen ze
lezen als ze aanstaan.

**Nieuwsberichten** (`/wp/v2/posts`, 1265, openbaar, met dezelfde kennisgroep en hetzelfde middel). Elk bericht meldt
een gebeurtenis bij een standpunt: gepubliceerd, geactualiseerd of ingetrokken, met een datum en een link naar de
publicatie. In de index worden ze **gebeurtenissen** per standpunt, met soort, datum en link naar het bericht. Een
gebeurtenis "ingetrokken" zonder voorvoegsel in de titel is een signaal voor de live-proef: dan wijken bron en index
van elkaar af.

**Wat niet openbaar is.** De lijsten van de taxonomieën, `media` en `revisions` geven 401. De namen van de termen komen
daarom uit `_embed`, en de bijlagen alleen als link uit de tekst. Een versiegeschiedenis per standpunt is er niet; de
index bewaart zelf de opeenvolgende hashes en datums `modified` die hij heeft gezien.

**Nieuwe generieke sleutels** in `METADATA_SLEUTELS` (PR 1). De andere connectors kunnen ze ook dragen:

- `vervangt` en `vervangen_door` (lijst);
- `vastgesteld` (datum);
- `noemt` (lijst van externe ids en bepalingen, met herkomst);
- `bijlagen` (lijst van links);
- `gebeurtenissen` (lijst van {soort, datum, link}).

### 2.7 Straat, profielen en catalogus

- **Straatvlag.** `connector_kennisgroepen: bool = False` in `Settings` en `CONNECTOR_KENNISGROEPEN` via `connectorEnv`.
  `azure-infra.yml` geeft op acceptatie alle namen uit `bronmodel.connectors` mee. De bestaande guard in `poort.yml`
  geldt vanzelf, en productie blijft uit.
- **Agentprofielen.** In `.claude/lex-agents/` komt de connector in de lijst `connectors` van `centraal`,
  `centraal_breed`, `duiding` en `algemeen`. `definitie` krijgt hem niet: een standpunt definieert geen begrip. Dat is
  open vraag V4. Na die wijziging moet `genereer_agentprofielen.py` en `genereer_bronpakket.py` draaien.
- **Catalogus (ADR-014).** De catalogus leidt de connector af uit de beschrijving, dus er hoeft niets met de hand bij.
  Een poorttest bevestigt dat.
- **Register.** De beheertab kent hem via `GET /v1/bronnen`, met de tekst uit `beheer`: "Gepubliceerde standpunten van de
  kennisgroepen van de Belastingdienst (CC0). Openbaar, zonder sleutel. Beleid, geen wet."

---

## 3. PR-stappen

Elke stap levert een PR die de hoofdsessie bundelt (`claude/alles-samen-N`). Er wordt niets zelf gemerged, en er draait
niets tegelijk met de G1-meting op acceptatie.

1. **Brontype en vindplaats** (`packages/bronmodel`, frontend). Deze PR bevat:
   - `standpunt` in `BRONTYPEN`;
   - het id `kg:…` en de citeervorm, met vectoren in `frontend/lib/jci-vectoren.json`;
   - de nieuwe sleutels `vervangt` en `vervangen_door`;
   - het generieke veld `status_regel`;
   - `BRONTYPE_NAAM`.

   Tests: de vectoren, de drift-test van de brontypen, en `test_connectorbeschrijving.py` (de nep).
2. **Adapter en parser** (`agent/adapters/wp_kennisgroepen.py`). Deze PR bevat:
   - het transport met allowlist, User-Agent, hoogstens 1 verzoek per seconde en een cache met validatie op `modified`;
   - de HTML naar rijen (kop, alinea, voetnoot, tabel);
   - de status uit de titel;
   - het kenmerk genormaliseerd;
   - het blok *Intrekking* naar `vervangt`.

   Tests:
   - fixtures van een handvol echte publicaties: CC0, dus ze mogen in de repo;
   - de drie afwijkende titels;
   - een ingetrokken en een vervallen standpunt;
   - een standpunt met tabel en voetnoten.
3. **De index in de graaf.** Deze PR bevat:
   - de job (§2.3) met de named graph, het register en de herkenning van bepalingen, met herkomst `link` of `tekst`;
   - alle velden en verwijzingen uit §2.6, de nieuwsberichten als gebeurtenissen, en de gezien-hashes;
   - `vervangen_door`, afgeleid in de index;
   - de graafwacht;
   - de scheiding van de wettekst.

   Tests:
   - de volledigheid tegen `X-WP-Total`;
   - de herkenning van bepalingen tegen een handgemaakte set van 40 standpunten;
   - de poorttest "graaftools geven geen standpunt";
   - idempotent herimporteren.
4. **De tools en de beschrijving.** Deze PR bevat:
   - `zoek_standpunten` en `get_standpunt`;
   - de `ConnectorModule`;
   - de beschrijving in `connectors.py`;
   - de straatvlag;
   - een nepbron in `NEPBRONNEN` en `CONNECTOR_ARGS` (`test_resultaatcontract.py`);
   - de live-proef `tests/test_kennisgroepen_live.py`, met marker `live` en in `bronnenwacht.yml`. Die toetst de
     velden, `X-WP-Total`, `_embed` en de vorm van de titel.
5. **Antwoord en werkplek.** Deze PR bevat:
   - `status_regel` in het blok `extern`;
   - de melding bij een ingetrokken of vervallen standpunt en bij de tekststand;
   - de groep in de bronnenlijst;
   - het tabblad in het bronvenster: generiek, dus alleen een test;
   - de regel in de beweringentoets.

   Browsertest: een blok met een geldend en een met een ingetrokken standpunt.
6. **Profielen en aanzetten op acceptatie.** Deze PR zet de connector in de agentprofielen en draait de generatoren. Daarna
   volgt een `azure-infra`-deploy op acceptatie door de gebruiker. Dat gebeurt pas na de G1-meting.
7. **Meting en iteratierondes** (§4).

Stap 1 en 2 kunnen tegelijk. Stap 3 hangt af van 2, en stap 4 van 1, 2 en 3. Stap 5 kan na 1 beginnen.

## 4. Meting: 20 vragen van verschillende soorten

Op verzoek van de gebruiker (13 nov 2026) volgen na de bouw **20 verschillende vragen**. Ze beoordelen of de integratie
lukt en wat er nog beter kan. De opzet volgt
[`../acceptatie/connectors-meting.md`](../acceptatie/connectors-meting.md) en de iteratierondes van de andere connectors:

- elke vraag in een nieuw gesprek, via de acceptatie-MCP, met `bronnen: ["kennisgroepen", "wetgeving_live", …]`;
- elk antwoord wordt beoordeeld tegen de officiële bron: de publicatie op de site en de wettekst;
- per vraag wordt vastgelegd: route, toolaanroepen, grounding, het sjabloon en de blokken, de status-regel, de
  bronnenlijst, de tokens en de duur;
- een afwijking wordt **generiek** opgelost, gevolgd door een PR en een nieuwe ronde, met hoogstens 4 rondes;
- de uitkomst komt in `docs/architectuur/metingen/kennisgroepen-<datum>/`, met een rij in het meetlogboek.

**De vragen**, vooraf vastgelegd. De ids en kenmerken worden vlak voor de meting tegen de live-bron gecontroleerd.

| # | soort | vraag (richting) | verwacht |
|---|---|---|---|
| 1 | genoemd kenmerk | Wat staat er in kennisgroepstandpunt KG:013:2026:4? | leest direct (`bron_lezen`), blok met status-regel en datum |
| 2 | per artikel, in de graaf | Welke kennisgroepstandpunten gaan over artikel 36 van de Invorderingswet 1990? | `zoek_standpunten` per bepaling; herkomst van de koppeling zichtbaar; "ten minste" |
| 3 | per artikel, buiten de graaf | Zijn er standpunten over artikel 3.111 Wet IB 2001? | koppeling via `wetgeving_live`/jci; wettekst uit `wetgeving_live` |
| 4 | wet + beleid | Wat zegt artikel 10 Wet BPM 1992, en hoe past de Belastingdienst het toe bij een lopend RDW-onderzoek? | eerst de bepaling, dan het blok beleid, zichtbaar gescheiden |
| 5 | onderwerp, woorden | Heeft de Belastingdienst een standpunt over de reisbureauregeling? | zoeken op woorden; geldend standpunt gevonden |
| 6 | lijstvraag, nieuwste | Geef de vijf nieuwste standpunten van de kennisgroep Invordering. | lijstroute zonder model, blok `stukken`, ordening op datum |
| 7 | lijstvraag, metadata | Welke standpunten over de rubriek Eigenwoningschuld publiceerde de kennisgroep IB-NW in 2025? | filters kennisgroep + rubriek + periode; elk feit uit de metadata, volledig of met vervolg |
| 8 | telvraag | Hoeveel standpunten zijn er over de AWR, per belastingsoort? | telling uit de index, met wat geteld is (link/tekst, belastingsoort) |
| 9 | ingetrokken | Geldt standpunt [een ingetrokken kenmerk] nog? | status ingetrokken, vervangend kenmerk genoemd, nooit als geldend beleid |
| 10 | vervangen | Welk standpunt vervangt KG:013:2018:0173? | `vervangen_door` uit de index; zegt dat het oude alleen via Woo openbaar is |
| 11 | status/waarde | Is een kennisgroepstandpunt bindend voor de rechter? | geen juridisch advies; noemt de status zoals de bron die geeft (beleid, bindt de inspecteur), met vindplaats |
| 12 | niet gepubliceerd | Is er een standpunt over [een onderwerp zonder treffer]? | "geen gepubliceerd standpunt gevonden", plus de grens: niet alles wordt gepubliceerd |
| 13 | tekststand | Is artikel X sinds standpunt Y gewijzigd? | melding tekststand uit de graaf of `wetgeving_live` |
| 14 | ketting / omgekeerd | Welke standpunten noemen ECLI:NL:HR:2013:64, en wat zegt die uitspraak? | `zoek_standpunten` via de koppeling `uitspraak`, daarna `get_uitspraak` (alleen als Rechtspraak aanstaat) |
| 15 | wetsgeschiedenis | Op welke Kamerstukken baseert standpunt [kenmerk] zich? | ids uit de tekst; leest een Kamerstuk alleen als dat gevraagd wordt |
| 16 | vergelijken | Wat is het verschil tussen de standpunten [A] en [B] over de expatregeling? | beide gelezen, verschillen met citaten |
| 17 | connector uit | vraag 1 met `bronnen: []` | melding zonder model, knop *Zet Kennisgroepstandpunten aan* |
| 18 | AVG | Wie is de heer Z in standpunt [kenmerk]? | herleidt niemand, zegt dat de casus geanonimiseerd is |
| 19 | controle wettekst | Wat staat er in artikel 9 van de Invorderingswet 1990? | route `bepaling_lezen`, geen standpunt, tokens gelijk aan de nulmeting |
| 20 | buiten scope / verwarring | Wat vindt de Belastingdienst van mijn aangifte? | geen casusadvies; hoogstens algemene standpunten, geen persoonsgegevens gevraagd |

**Criteria**, vooraf vastgelegd:

- **Garanties, 3/3 per run en 20/20:**
  - geen standpunt onder een `doel` of als wettekst;
  - elk standpuntblok heeft de status-regel en een datum;
  - een ingetrokken of vervallen standpunt wordt nooit als geldend gepresenteerd;
  - elk citaat staat letterlijk in de gelezen tekst;
  - een uitgezette connector wordt niet gebruikt.
- **Kwaliteit:** goed, matig of fout per vraag, met als doel minstens 17 goed en 0 fout na de laatste ronde.
- **Kosten:** tokens per vraag, naast de vergelijkbare vragen van Rechtspraak en Kamerstukken.

## 5. Tests en bewaking (samenvatting)

- `test_connectorbeschrijving.py`: de beschrijving is volledig, de tools heten `zoek_…` of `get_…`, en elke invoerfout
  heeft een voorbeeld;
- de contractharnas met een nepbron: alle pagina's samen zijn de dataset;
- tests op de parser met CC0-fixtures;
- tests op de index: volledigheid, de herkenning van bepalingen met precisie en recall op 40 handgemaakte gevallen,
  idempotentie, en de scheiding van de wettekst;
- de poort: `CONNECTOR_KENNISGROEPEN` alleen via `connectorEnv`, en standaard uit;
- de live-proef in `bronnenwacht.yml`, dagelijks en nooit in de poort;
- `scripts/kruistests.sh`.

## 6. Risico's en wat niet kan

| risico | gevolg | maatregel |
|---|---|---|
| De API verandert of gaat dicht; de documentatie klopt al niet helemaal (401 op taxonomieën) | zoeken of lezen faalt | de live-proef per dag; de index als terugval bij het lezen (`gevalideerd: false`); open vraag V1 (contact met het ontwikkelteam) |
| Niet alle standpunten zijn gepubliceerd | stilte wordt gelezen als "er is geen standpunt" | de `grenzen` en een vaste zin bij nul treffers |
| Ingetrokken of vervangen standpunten | verouderd beleid als geldend gepresenteerd | status uit de titel, `vervangen_door` in de index, de beweringentoets, vraag 9 en 10 |
| Een stille wijziging na publicatie (504 keer `modified` later) | citaat en bron lopen uiteen | `bron_hash` en `gewijzigd` op het blok; bijwerken met `modified_after` |
| De herkenning van bepalingen in de tekst | een vals of gemist verband | de herkomst `link` tegenover `tekst` zichtbaar; precisie en recall meten (stap 3) |
| Een standpunt over een eerdere wetstekst | uitleg bij een gewijzigde norm | `tekststand` (§2.5) |
| Standpunten in de wet-FTS | beleid verschijnt als wettekst | een eigen named graph en een eigen index; poorttest |
| AVG | herleiden van een partij | regel in `rol_in_antwoord`, vraag 18 |
| De belasting van de site | onbeleefd gebruik | 12 verzoeken per volledige sync, 1 per seconde, een cache, en bijwerken alleen met `modified_after` |

**Wat niet kan:**

- standpunten van vóór 2022, of die alleen via Woo-deelbesluiten (PDF op rijksoverheid.nl) openbaar zijn. Dat kan een
  latere, aparte bron worden;
- de interne motivering of de versiegeschiedenis van een standpunt;
- zeggen of een belastingplichtige zich op een standpunt kan beroepen: dat is juridisch advies;
- afbeeldingen en gekoppelde PDF's lezen.

## 7. Conclusie

De connector is haalbaar, goedkoop en in lijn met ADR-013. De bron is officieel, CC0, stabiel genoeg (met een
live-proef), klein, en heeft een vast kenmerk en een vaste opbouw. Hij is waardevol voor de duiding van fiscale
bepalingen: hij laat zien hoe de uitvoerder een bepaling uitlegt, naast wat de wet zegt, en hij verwijst zelf naar de
rechtspraak en de Kamerstukken die Lex al kan lezen. De voorwaarde is dat het verschil tussen beleid en wet in code is
vastgelegd (§2.5) en niet aan het model wordt overgelaten.

## 8. Besluiten van de gebruiker (13 nov 2026)

Op alle open vragen hieronder volgde de gebruiker het advies:

- **V1:** de gebruiker neemt zelf contact op met de Belastingdienst. Dat is geen voorwaarde om te bouwen.
- **V2:** de index wordt een eigen modus van `bwb-import`, met een eigen named graph. Daarbij gelden twee eisen:
  - de import blijft idempotent per named graph;
  - de graafwacht leest de nieuwe graaf niet als verlies van de wetgraaf.
- **V3:** de volledige tekst per kop gaat in de index, in de eigen named graph, en nooit in de FTS van de wet.
- **V4:** de connector komt in de profielen `centraal`, `centraal_breed`, `duiding` en `algemeen`, niet in `definitie`.
- **V5:** standaard toont Lex alleen geldende standpunten. Ingetrokken of vervallen standpunten alleen op verzoek, of als
  ze bij naam genoemd worden.
- **V6:** de groep heet "Kennisgroepstandpunten (beleid)", met de status-regel uit §2.5.

Het bouwen van stap 1 tot en met 6 mag beginnen. De meting van 20 vragen (stap 7) draait pas op sein van de
hoofdsessie, na de G1-meting op acceptatie. De hoofdsessie merget.

### Open vragen zoals ze voorlagen

- **V1 – Contact met de Belastingdienst.** De pagina *Integratie* nodigt uit om vragen te stellen aan het ontwikkelteam.
  Willen we melden dat Lex de API gebruikt, en vragen naar de 401 op de taxonomieën en naar een veld voor de
  wetsartikelen? Advies: ja, maar dat doet de gebruiker zelf; het is geen voorwaarde om te bouwen.
- **V2 – De plek van de index.** De voorkeur gaat naar de graaf (§2.3), met een job naast de BWB-import. Alternatieven:
  - een eigen kleine job in plaats van een modus van `bwb-import`;
  - alleen live (A), zonder zoeken per artikel.

  Advies: een eigen modus van `bwb-import`, want daar zitten de graafwacht en het idempotente schrijven al.
- **V3 – De tekst in de graaf.** Mag de volledige tekst per kop in de index (CC0, nodig voor zoeken op woorden), of
  alleen de metadata en de koppelingen? Advies: de volledige tekst, in een eigen named graph, nooit in de wet-FTS.
- **V4 – Welke agentprofielen.** Voorstel: `centraal`, `centraal_breed`, `duiding` en `algemeen`, maar niet `definitie`.
  Klopt dat?
- **V5 – Ingetrokken standpunten.** Standaard alleen geldende standpunten in een zoekresultaat, en ingetrokken of
  vervallen standpunten alleen op verzoek, of wanneer ze bij naam genoemd worden. Akkoord?
- **V6 – De naam in de werkplek.** "Kennisgroepstandpunten (beleid)" als groep, en de status-regel zoals in §2.5. Akkoord,
  of wil je andere woorden?

## Bronnen (geraadpleegd 13 nov 2026)

- Kennisgroepen Belastingdienst, home en publicaties: <https://kennisgroepen.belastingdienst.nl/>
- Integratie (de REST API): <https://kennisgroepen.belastingdienst.nl/integratie/>
- Copyright (CC0): <https://kennisgroepen.belastingdienst.nl/copyright/>
- Disclaimer (art. 3.1 Woo, art. 67 AWR, vaststellingsdatum): <https://kennisgroepen.belastingdienst.nl/disclaimer/>
- Over de Kennisgroepen (status als beleid): <https://kennisgroepen.belastingdienst.nl/over-de-kennisgroepen/>
- robots.txt en sitemap: <https://kennisgroepen.belastingdienst.nl/robots.txt>,
  <https://kennisgroepen.belastingdienst.nl/sitemap_index.xml>
- WordPress REST API: <https://developer.wordpress.org/rest-api/>
- Een voorbeeld van een Woo-deelbesluit met oudere standpunten:
  <https://www.rijksoverheid.nl/documenten/2025/11/13/tweede-deelbesluit-op-woo-verzoek-over-beleidsdocumenten-belastingen>
