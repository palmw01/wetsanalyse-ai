# Plan — wetsanalyse-ai

Soort: *plan* (zie [`README.md`](README.md)) · Bijgewerkt: 5 oktober 2026

Dit is het **enige plan** van het project. Het vervangt de losse plannen voor de workbench, het
herkomstspoor, werkgebieden en begrippen en de kennisbank. Hier staat wat er openstaat, niet wat er
al gebeurd is. Is een onderdeel af? Haal het dan hier weg en laat een verwijzing achter naar de PR
of de specificatie die het nu beschrijft. Ontwerpbesluiten die blijven gelden horen in een
ADR of specificatie, niet in dit bestand.

## Leidende principes

- **De AI stelt voor, de mens beslist.** Agent-gedreven annotatie met menselijke review is het
  product. Handmatig annoteren bestaat alleen als correctie tijdens de review. Een voorstel is nooit
  definitief zonder menselijke beslissing, en een goedkeuring op het ene niveau (begrip) geeft niet
  stilzwijgend goedkeuring op een ander niveau (annotatie).
- **Brongetrouwheid.** Elk element is herleidbaar naar bronnode, anker en bronhash. Citaten komen uit
  de tool-trace, nooit uit de prozatekst van het model (`provenance.iter_refs`,
  `grounding.check_grounding`). Een nieuwe bronsoort krijgt dezelfde controle of hij komt er niet in.
- **De api is system of record.** PostgreSQL is de waarheid. De graaf is een herbouwbare projectie
  die alleen de api schrijft. Het model krijgt geen directe graafmutaties.
- **Normhiërarchie.** De wet is de norm, beleid en handleidingen zijn toepassing. Bij tegenspraak
  prevaleert de wet en benoemt Lex het verschil.
- **Geen schijnzekerheid.** Er komt geen rauwe modelconfidence in beeld, wel een aandacht-niveau op
  basis van echte signalen. Kwaliteit laat zich zien in indicatoren, niet in één cijfer.
  Stabiliteit, technische validiteit en consensus zijn geen maat voor juridische juistheid.

## Wat er staat

Kort en alleen als wegwijzer; de inhoud staat in de genoemde documenten.

- **Annotatiedomein, contract 2**: een laag per bronnode, lokale ankers, review en audit, directe
  projectie naar `urn:jas:graph:v2:<laag-id>`, leestools voor Lex →
  [`architectuur/annotatie-bronnodes.md`](architectuur/annotatie-bronnodes.md),
  [`wetsanalyse-workbench/jas-annotatie-ontologie.md`](wetsanalyse-workbench/jas-annotatie-ontologie.md).
- **Hybride annotatieketen `hybrid_v1`**: detectoren → kandidaten → kleine classifier → gerichte
  review; sinds PR 18 de enige route →
  [`architectuur/adr-001-hybride-jas-pijplijn.md`](architectuur/adr-001-hybride-jas-pijplijn.md),
  [`architectuur/adr-002-taalprovider.md`](architectuur/adr-002-taalprovider.md).
- **Herkomstspoor, eerste helft**: graafcontrole (#517), SSE-fasen met duur en dekking (#518),
  JAS-vocabulairegraaf en leesbare trace-codes (#519), rijke annotatiegraaf schema 3 (#520),
  Critic-restanten weg (#521), JAS-subtype machineleesbaar (#523). Dat zijn PR 1–4 van spoor B;
  PR 0 is af: productie draait `v1.7.0` (1 okt) en projecteert; de api logt elke tien minuten
  `annotatie_graafcontrole` met 0 afwijkingen (geverifieerd 5 okt via `azure-infra` → `telemetrie`).
- **Herkomst en dekking in de werkplek** (spoor B PR 5a, 5b, 6; op productie sinds `v1.8.0`, 5 okt):
  de Waarom-uitklap op de reviewkaart en in de graafinspector met leesbare namen uit de vocabulaire
  (#570); revisiehistorie per laag, alleen-lezend (`GET lagen/{id}/revisies`, #572); ongedekte
  zinsdelen onderstreept in het documentpaneel, zelf markeren vanaf zo'n zinsdeel en een
  dimensie-overzicht (#573); de laag *Dekking* in de 3D-graaf (6b) →
  [`frontend/CLAUDE.md`](../frontend/CLAUDE.md), [`architectuur/annotatie-bronnodes.md`](architectuur/annotatie-bronnodes.md).
- **Exports en technisch detail** (spoor B PR 7a #576, 7b): CSV met herkomstkolommen, PDF met
  herkomstzin, beurtmeting en dekking, JSON v3 met schema (`GET export-schema`), TriG via
  `bouw_graaf` (`api/app/annotatie_export.py`); in de werkplek per markering de RDF en de
  graafcontrole van haar laag (`GET elementen/{id}/graaf`, `graafcontrole.controleer_laag`).
- **Grenskeuze** (spoor B PR 8): de grensopties van de keten als chips op de reviewkaart; de
  beslissing `grens` laat de api het anker uit de bron rekenen.
- **Herkomst in de 3D-graaf** (spoor B PR 10): markeringsknopen dragen herkomst, aandacht, subtype,
  beslist_door en twijfel; *Lagen* heeft een markeringsfilter, de inspector toont herkomst en aandacht.
- **Zoekfilters op herkomst** (spoor B PR 9): `search_annotaties` en `POST zoeken` filteren op
  herkomst, aandacht, subtype, beslist_door en twijfel; in SPARQL én opnieuw tegen Postgres.
- **Citatie-chips** (spoor B PR 5c): een vindplaats in het antwoord van Lex die éénduidig bij een
  bron hoort, opent een bronkaart (`frontend/lib/citaties.ts`, `CitatieChip`).
- **Samenhangsgraaf** (#540–#546): `GET /v1/annotatie/samenhang` (`api/app/samenhang.py`,
  capability `samenhang`) en een 3D-krachtgraaf (`components/graaf/SamenhangGraaf.tsx`,
  `lib/samenhang.ts`). Die staat als tab *3D-graaf* in het annotatiepaneel en opent ook via
  "Bekijk samenhang in 3D" onder chatbronnen. Hij toont de bronstructuur, markeringen met hun
  JAS-klasse en de letterlijke verwijzingen één stap in en uit. Randknopen zijn bij te laden, en er
  zijn zoeken, lagen, een inspector met *Open brontekst* / *Vraag Lex hierover* en live bijwerken na
  een mutatie. Afstand en positie hebben geen juridische betekenis. Browsertest:
  `frontend/scripts/test-samenhang.mjs`.
- **Annoteren per lid of subbepaling** (#550–#553): één artikel per vraag (meer artikelen = een
  werkgebied, spoor D), een keuzekaart met de stand per lid, meerdere leden als één run met een
  laag per lid (`agent/reeks.py`), een blok per lid in het gesprek en bladeren door de reeks in het
  paneel → [`architectuur/annotatieketen.md`](architectuur/annotatieketen.md) (*Afbakening*,
  *Keuze van de bronnode*, *Reeks*).
- **Validatie-infrastructuur V1–V6**: referentieset v1, adjudicatieprotocol, blind formulier,
  fouttaxonomie v2, beslisregister, contractfouten en reviewload gesplitst, en een rapport per laag
  (#525–#530) → [`architectuur/onderzoek-empirische-validatie.md`](architectuur/onderzoek-empirische-validatie.md) §16.
- **Actuele nulmeting** →
  [`architectuur/metingen/hybrid-v1-baseline-2026-09-29/`](architectuur/metingen/hybrid-v1-baseline-2026-09-29/README.md).
  Deze vervangt de freeze van 27 september als vertrekpunt.

## Open sporen

| Spoor | Onderwerp | Stand |
|---|---|---|
| A | Juridische validatie van `hybrid_v1` (V7) | Wacht op mensenwerk: 0 casussen `adjudicated` |
| B | Herkomst zichtbaar in werkplek en exports | Af: alle PR's gebouwd; 5a–6a op productie in `v1.8.0`, de rest gaat mee in `v1.9.0` |
| C | Leerlus en knowledge-check | Te herijken |
| D | Activiteit 3: werkgebieden en begrippen | Ontwerp klaar, niets gebouwd |
| E | Kennisbank (tweede corpus) | Ontwerp klaar, niets gebouwd |

---

### A. Validatie `hybrid_v1`: V7, en dan stoppen

**Doel.** Vaststellen of de keten juridisch juist annoteert. Alle huidige kwaliteitscijfers
(F1 39% → 49%, ankerdekking 47% → 84%) zijn ankerdekking op *provisional* referenties, geen recall.

**V7 — baseline op de adjudicated set.**
1. Het protocol en formulier uit V1–V2 uitvoeren met echte beoordelaars. De PR landt pas als
   **≥ 20 casussen `adjudicated`** zijn die alle 13 klassen en de constructiematrix (§10.3) dekken.
2. Meten met ≥ 3 runs (stabiliteit: 5), een vastgelegd manifest (commit-SHA, image-digest,
   detectorversies, `agent_versie`) en held-out eenmalig.
3. Rapport in `architectuur/metingen/`.

**Daarna stoppen.** Er komt een nieuw onderzoeksdocument met de dominante foutcategorieën,
juridisch tegenover technisch, klassespecifieke problemen en kandidaat-, span-, relationele en
contractproblemen. Pas dan gelden de beslispoorten (§15 van het onderzoek).

**Tot V7 af is:** geen nieuwe semantiek of architectuur in de keten. De stopcriteria staan in het
onderzoek §18. Blijvend verboden zijn promptpatches als primaire oplossing, nieuwe agentrollen, een
Critic, model voting, confidence-percentages en grotere modelvrijheid.

**Uitzondering (6 okt 2026): vier aantoonbare detectorfouten in art. 9 lid 5.** De gebruiker
besloot ze nu te herstellen, robuust en gemeten, in plaats van tot na V7 te wachten. De scope is
beperkt tot de detectoren:

- **C**: precieze functiespans;
- **B**: een rechtsgevolg als hoofdzin;
- **A**: een document of handeling is geen rechtssubject;
- **D**: de context van een nominalisatie.

Er is geen promptwijziging, geen nieuwe agentrol en geen tegenbewijs-semantiek (dat is kandidaat
1). Elke fix heeft een criterium dat vóór de nulmeting is vastgelegd. De meting claimt op v1
uitsluitend "geen regressie". De winst geldt alleen voor de diagnostische conceptcasus `IW05`
(onderzoek §18.6). Kandidaten 2, 3 en 10 blijven ná V7. Meting en criteria:
[`metingen/hybrid-v1-iw05-fixes-2026-10/`](architectuur/metingen/hybrid-v1-iw05-fixes-2026-10/README.md).

**Kandidaten na V7** (alleen met de V7-baseline als vergelijkingspunt; zie ook de
bekende beperkingen in [`architectuur/annotatieketen.md`](architectuur/annotatieketen.md)):
1. Candidate- en EvidenceHypothesis: ondersteuning en tegenbewijs per klasse.
2. Generieke NP uitsluitend als syntactisch bewijs.
3. Een minimaal NormFrame (predicaat, clause, voice, drager/object).
4. Een ComparisonFrame en een DerivationFrame (operanden, invoer/uitvoer).
5. Regelgebonden bewijssterkte en een expliciete routingpolicy.
6. Contextuele disambiguatie van connectieven (vergelijking, hoedanigheid, ellips).
7. Een specialistische JAS-classifier, getoetst op contractfouten.
8. De geplande regels `tijd.voorzetselgroep`, `delegatie.grondslag_wti`, `waarde.numeriek`,
   `feit.gebeurtenisbijzin`, en een eigen route voor Delegatie-invulling.

9. **Relaties tussen elementen** als additieve laag in de projectie: voorwaarde → gevolg,
   vervalmoment, invoer en uitkomst van een afleiding. Bewijs: art. 9 lid 5 (concept `IW05`).
10. Een **deterministische nestingregel** (validatie, géén Critic): een genest element moet een andere
    juridische functie hebben dan het element waarin het ligt.

Kandidaten 2, 3, 4 en 6 hebben in art. 9 lid 5 een concreet voorbeeld: zie de casus onder *Bekende
beperkingen* in [`architectuur/annotatieketen.md`](architectuur/annotatieketen.md) en de
conceptcasus [`IW05`](wetsanalyse/referentieset/concept/IW05.json). Die concepten gaan pas mee in
een meting als een jurist ze heeft beoordeeld.

Open vragen die V7 moet beantwoorden staan in het onderzoek §17.

---

### B. Herkomst zichtbaar in werkplek en exports

**Doel.** De rijkdom van `trace` en run-meting (bewijs, detectoren, regels, twijfel, resolutie,
dekking) moet zichtbaar worden voor de jurist, en aantoonbaar correct in de graaf en in exports.
De samenhangsgraaf is de plek waar die herkomst ook ruimtelijk zichtbaar wordt, naast de tekst.

**Besluiten van de gebruiker:**
- regel-id's worden getoond als leesbare naam, met het id in een tooltip;
- vrij selecteren blijft bestaan naast voorgestelde grenzen;
- de exacte modelvraag komt in de JSON-export;
- beoordelingen komen in de graaf **zonder personen**;
- de 3D-samenhangsgraaf is dé graaftab van het paneel. De Turtle van een markering en de
  graafcontrole-status komen onder "technisch detail" in de graafinspector en in de export.

**UI-richting.** De huidige opzet blijft: een gespreksvenster met de annotatie als zijpaneel. Die
volgt zo dicht mogelijk de patronen van Claude:
- een ingeklapt stappenblok met fasen en duur;
- het antwoord als proza met citatie-chips die een bronkaart openen;
- een artefact-kaartje dat het zijpaneel opent, met revisiekiezer en de tabs *Tekst / Dekking /
  3D-graaf*;
- bij tekstselectie een zwevende balk *Markeer als… / Vraag Lex*, die een citaat-chip in de invoer
  zet.

Er staat al: de tabs *Tekst* en *3D-graaf*, *Vraag Lex* in `SelectiePopover`, en *Open brontekst* /
*Vraag Lex hierover* in de graafinspector. Nog te bouwen: de tab *Dekking*, het stappenblok met duur,
het artefact-kaartje met revisiekiezer, de citatie-chips met bronkaart en de citaat-chip in de
invoer.

De huisstijl (lintblauw, Fira, JAS-kleuren) blijft.

**Werkwijze.** Per PR: branch → PR → `poort` → squash-merge. Contracten blijven additief, beide
SSE-wegen blijven gelijk en drift-tests gaan mee. Elke PR die graph-qa raakt draait ook zónder spaCy
(`uv run --isolated --extra dev pytest -q`).

Alle PR's van dit spoor zijn geleverd; zie *Wat er staat*. Wat hieronder over werkwijze en
verificatie staat, blijft gelden voor vervolgwerk aan de herkomst.

**Verificatie.** Per PR: api `uv run pytest`, graph-qa met en zonder spaCy, frontend
`npm test`/typecheck/`npm run test:browser` (met `test-samenhang.mjs`) en `poort`. Acceptatie live:
één bepaling annoteren en beoordelen, dan geeft `graafcontrole` 0 afwijkingen en is SHACL conform.
Daarna op productie. De werkplek doorlopen in Chrome: uitklap, chips, dekking, de 3D-graaftab
(inspector, dekkingslaag, technisch detail) en export in 4 formaten.

---

### C. Leerlus en knowledge-check — te herijken

Uit de oorspronkelijke workbench-fase 2 staan nog open:
- **lessons-learned** (`{pattern, trigger, resolution}` per JAS-klasse);
- een **pre-flight** vóór het annoteren (vergelijkbare artikelen en eerdere fouten ophalen);
- een **knowledge-check** vóór publicatie (consistentie met graaf en bestaande annotaties).

Die zijn ontworpen voor de generatieve keten met Critic, en die keten is met ADR-001 PR 18
verdwenen. Een few-shot-lus op eerdere beslissingen botst bovendien met het principe dat kennis in
regels en tests hoort en niet in prompts, en met de stopcriteria van spoor A.

**Eerst beslissen, niet bouwen:** blijft de leerlus een doel? Zo ja, in welke vorm? Te denken valt
aan beslissingen als regressiefixtures of als detectorregel-kandidaten in plaats van promptcontext.
En wordt de knowledge-check onderdeel van spoor D (ontdubbeling over een werkgebied)? Niet vóór V7.

---

### D. Activiteit 3: werkgebieden en begrippen

**Doel.** De analist brengt bepalingen samen in een werkgebied en formuleert daarop begrippen,
steeds verbonden met de geannoteerde bronpassages. Lex stelt groeperingen en begrippen voor, de
analist beoordeelt, formuleert en corrigeert; beginnen vanuit een eigen elementselectie kan ook.
Nu draagt het platform `scope: "act2"`; bij levering 1 gaat die afbakening in `CLAUDE.md` mee.

Bronnen:
- *Handleiding Wetsanalyse in de praktijk* §3.5 (pp. 35–44);
- *Leidraad voor Wetsanalyse op maat*, "Ad 3";
- het boek, hoofdstuk 3, stap 3.

Alle drie zijn lokaal-only. Daarnaast is gebruikt:
[NL-SBB 10 okt 2024](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/).

**Methodische uitgangspunten.**
1. Verschillende formuleringen kunnen één begrip aanduiden, ook over artikelen en regelingen heen.
2. Dezelfde formulering kan verschillende betekenissen hebben. Tekstgelijkheid is aanleiding tot
   vergelijking, geen bewijs.
3. De juridische context bepaalt de betekenis mee, bijvoorbeeld een definitie, uitzondering of
   verwijzing elders.
4. Een begripsdefinitie is geen rekenregel. Definitie, letterlijke brondefinitie en toelichting op
   de interpretatie blijven onderscheiden.
5. Voorbeelden, ook grensgevallen en tegenvoorbeelden, toetsen de afbakening.
6. Begrippenvorming kan activiteit 2 corrigeren of het werkgebied uitbreiden; het proces is
   iteratief.

Afleidingsregels, scenario's en RegelSpraak vallen **buiten** deze reeks. Een begrip kan wel alvast
voor een afleidingsregel worden vastgelegd.

**Uitgangssituatie.** Het werkgebied is nu een vrij tekstveld, in v2 leeg. Er zijn geen opgeslagen
betekenisgroepen en geen analysebegrippen; de JAS-begrippen in de vocabulaire zijn classificaties.
`tools/nl-sbb-begrip` is een los hulpmiddel. Samenhang zit in `api/app/samenhang.py` en
`frontend/lib/samenhang.ts`: een 3D-samenhangsgraaf per bepaling (`/v1/annotatie/samenhang`), die
de tab *Samenhang* en de werkgebiedgraaf als basis kunnen hergebruiken. De runstore overleeft een procesuitval nog niet. De keten `hybrid_v1`
hoeft niet te veranderen.

#### Werkgebied als node

Een werkgebied heeft een stabiel ID, naam, analysevraag, afbakening, gewenste peildatum, status en
revisie. Het heeft een eigen begrippenkader en bronselecties.

- **Bronselectie** is een eigen object met gekozen bereik, rol, reden en bronstand. In de GUI
  verschijnt het als één lijn werkgebied → artikel.
- Een artikel kan in meerdere werkgebieden staan. De bronnode en annotaties worden gedeeld, de
  begripskoppelingen zijn contextgebonden. Een werkgebied is **nooit** `parent_iri` van een artikel.
- Een selectie is expliciet: deze node, of deze node met onderliggende onderdelen (standaard het
  hele artikel, vooraf getoond).
- Een selectie heeft een rol: **analyseren** of **contextbron**. Een contextbron ondersteunt
  bijvoorbeeld een definitie, maar zet haar annotaties niet in de werkvoorraad.
- Bij overlap telt elk element één keer. Een element dat gedeeltelijk buiten de selectie valt krijgt
  een melding en wordt niet stil verbreed.
- Een verwijzing naar een niet-opgenomen bepaling verschijnt als suggestie. Een niet-beschikbare bron
  blijft een open punt.
- Peildatum en technische snapshot zijn gescheiden. Is de historische stand niet leverbaar of niet
  geverifieerd, dan toont de werkplek dat.
- IRI's zijn gebaseerd op UUID's: `urn:wa:werkgebied:<uuid>`, `urn:wa:begrip:<uuid>`. Voor de
  projectie komt er een named graph `urn:wa:graph:werkgebied:<uuid>`. Voor publiceerbare HTTP-URI's
  moet later een eigen domein gekozen worden.

#### Elementen, groepen en begrippen

| Object | Betekenis |
|---|---|
| Annotatie-element | Geclassificeerde passage op een concrete bronstand (bestaat al) |
| Betekenisgroep | Voorstel dat elementen hetzelfde begrip aanduiden; werkmiddel en herkomst van het voorstel |
| Begrip | Vastgelegde betekenis: naam, definitie, voorbeelden, eigenschappen |
| Begripskoppeling | Beslissing dat een element een begrip aanduidt of een definitie ondersteunt |
| Begripsrelatie | Inhoudelijke relatie tussen begrippen, met eigen onderbouwing |

- Een filter op JAS-klasse levert geen synoniemen op. Subject + object + voorwaarde van één
  rechtsbetrekking vormen geen begrip, maar krijgen relaties.
- Beslissingen per groep: nieuw begrip, koppelen aan bestaand begrip, splitsen, combineren,
  element eruit halen, parkeren met reden. Geen van die beslissingen wijzigt de annotaties.
- Een groep mag uit één element bestaan. Een aparte groepsgoedkeuring vóór het begrip is niet
  verplicht.
- Een element kan in meerdere kandidaatgroepen staan. Als duiding heeft het binnen één werkgebied en
  geldigheidscontext in beginsel één **primair** begrip. Andere rollen worden apart vastgelegd.
- Verschillende JAS-klassen in één groep zijn een controlesignaal, geen verbod.

#### Werkwijze voor de gebruiker

1. **Werkgebied maken**: naam, vraag, afbakening; bronnen toevoegen vanuit zoeken, een annotatie of
   de graaf.
2. **Elementen inventariseren**: alle actuele, niet verworpen elementen in scope. Onbeoordeelde
   elementen mogen als input dienen, met zichtbaar voorbehoud.
3. **"Stel begrippen voor"** (hoofdactie) op het hele werkgebied of een selectie.
4. **Bronnen vergelijken**: alle passages naast de definitie; elementen toevoegen, verwijderen,
   splitsen of koppelen.
5. **Begrip uitwerken**: vanaf een lege kaart of met hulp van Lex.
6. **Beoordelen** van inhoud én koppelingen. Onbeoordeelde dragende annotaties worden apart
   beoordeeld.
7. **Bijhouden**: nieuwe bronnen leveren nieuwe voorstellen op, wijzigingen leiden tot gerichte
   herbeoordeling.

**Accorderen kan** als naam, definitie, context, dragende koppelingen, voorbeelden en de vereiste
annotatiebeoordelingen compleet zijn en er geen onopgelost betekenisconflict is. Eigenschappen
verschillen per klasse. "Minimaal één passend voorbeeld" is een kwaliteitskeuze, geen bewijs. De
voortgang (geannoteerd / beoordeeld / gekoppeld) zegt niets over juridische dekking.

#### GUI

Er komt een navigatie-item **Werkgebieden** met de tabs **Bronnen · Elementen · Begrippen ·
Samenhang**. Zolang Lex vanuit een werkgebied werkt, blijft de naam van dat werkgebied zichtbaar.

- **Begrippenscherm**, drie kolommen:
  - links voorstellen, geaccordeerde begrippen en herbeoordelingen (naam, aantallen, concreet
    aandachtspunt zoals "zelfde term, andere context");
  - midden de begripskaart;
  - rechts de bronpassages, elk apart aanklikbaar. Een samenvatting vervangt de passages nooit.
- **Begripskaart**:
  - naam en alternatieve termen, context, JAS-duiding en geldigheid;
  - definitie, uitleg en onderbouwing;
  - de herkomst van de definitie: letterlijk, samengesteld of geformuleerd;
  - voorbeelden met verwacht oordeel (wel / niet / onzeker);
  - eigenschappen per klasse;
  - relaties, koppelingen, open vragen, status en historie.
- **Splitsen** gaat met selectievakjes. **Combineren** toont eerst een vergelijking; de analist
  kiest welke identiteit blijft, en de oude begrippen blijven vindbaar als vervangen.
- Op kleine schermen kan de analist wisselen tussen Begrip en Bronnen. Alles werkt met het
  toetsenbord; slepen is hooguit aanvullend. IRI's en hashes staan alleen in de details.
- **Lex naast de kaart** met acties als "Verklaar het betekenisverschil", "Zoek de brondefinitie" en
  "Stel een scherpere definitie voor". Een chatantwoord wordt pas opgeslagen als voorstel via de api.
- **Graaf**: compact met werkgebied, bronnen en begrippen; annotaties op verzoek. Een lijn betekent
  alleen wat het relatietype zegt, en voorstellen en geaccordeerde relaties zijn te onderscheiden.
  Bouwt voort op de samenhangsgraaf (lagen, inspector, bijladen), met het werkgebied als cluster.

#### Datamodel

De verdeling over tabellen en JSON-velden wordt bij de implementatie bepaald.

| Object | Kerngegevens |
|---|---|
| `Werkgebied` | ID/IRI, naam, analysevraag, afbakening, peildatum, status, revisie, maker, tijdstippen |
| `Bronselectie` | werkgebied, canonieke bron-IRI, node/subtree, analyse/context, reden, snapshot, geverifieerde bronstand |
| `Begrippenkader` | ID/IRI, werkgebied, naam, revisie; eerst één per werkgebied |
| `Analysemanifest` | onwijzigbare run-input: scope-revisie, bronstanden, element-ID's en -hashes, laagrevisies, context |
| `Betekenisgroep` | manifest/run, kandidaatleden, motivatie, aandachtspunten, voorgesteld begrip, status |
| `Begrip` + `BegripRevisie` | stabiele identiteit; versies van naam, definitie, uitleg, voorbeelden, context, klasse/subtype, eigenschappen, geldigheid, beoordeling |
| `Begripskoppeling` | werkgebied, begrip/revisie, element-ID, rol, bewaarde bewijsstand, motivatie, reviewstatus |
| `Begripsrelatie` | twee begrippen, relatietype, bewijs, geldigheid, beoordeling |
| `Begripsbeslissing` / audit | actor, actie, tijd, reden, wijziging; ook voor groepsleden en selecties |
| `BegrippenRun` | manifest, model/methodeversie, status, afgeronde batches, resultaten, fouten |

Koppelingen bewaren zowel een verwijzing naar het levende element als de bewaarde bewijsstand.
Als een annotatie verdwijnt, cascadeert dat **niet**: de koppeling wordt gemarkeerd als niet langer
actueel onderbouwd. Werkgebieden zijn eerst gedeeld tussen geauthenticeerde analisten, net als de
annotaties, en iedere mutatie is geautoriseerd en geaudit. Een werkgebied-ID geeft op zichzelf nooit
toegang. Inhoud, beoordeling en actualiteit worden apart bewaard. Een betekeniswijziging levert een
nieuw begrip op met een opvolgingsrelatie; een tekstuele verbetering blijft een revisie.

#### API, agent en graaf

| Route (`/v1/werkgebieden…`) | Verantwoordelijkheid |
|---|---|
| `/` en `/{id}` | aanmaken, lijst, detail, wijzigen met revisiecontrole |
| `/{id}/bronnen`, `/{id}/elementen` | scope onderhouden; volledige, gepagineerde inventaris |
| `/{id}/begrippen-runs` | starten met manifest, status, stoppen, gerichte herstart |
| `/{id}/groepen` | voorstellen lezen; leden wijzigen, splitsen, combineren |
| `/{id}/begrippen` | zoeken, concepten, revisies, beoordelingen |
| `/{id}/koppelingen`, `/{id}/relaties` | bronduiding en relaties met eigen bewijs |
| `/{id}/samenhang`, `/{id}/export` | begrensde graafweergave; export van een benoemde stand |

Alle mutaties controleren de verwachte revisie en zijn idempotent op een sleutel. Een inhoudelijk
andere herhaling geeft een conflict met een bruikbare vergelijking.

**Verwerking.**
1. De api materialiseert een consistent manifest uit PostgreSQL. Een achterlopende projectie mag
   geen elementen laten verdwijnen.
2. Kandidaatverwantschap wordt gezocht op formulering, normalisatie, klasse/subtype, verwijzingen en
   context. Normalisatie bepaalt nooit zelf de identiteit van een begrip.
3. Per groep worden de volledige passages, bovenliggende context, brondefinities en bestaande
   begrippen opgehaald.
4. Het model levert getypeerde voorstellen en voert geen element-ID's of vindplaatsen in die niet
   bestaan.
5. Deterministische controles op ID's, bereik, hashes en verplichte velden. Inhoudelijke signalen
   zijn onder meer tegengestelde contexten, circulaire definities en voorbeelden die niet bij de
   definitie passen. De mens beslist.
6. De api bewaart per afgeronde batch en SSE meldt echte voortgang. Na herladen zijn de voorstellen
   er nog.

Grote werkgebieden gaan in begrensde batches, gevolgd door een vergelijking tussen batches. Een
gedeeltelijk resultaat wordt als gedeeltelijk gemeld, met het behandelde bereik. **Nieuw nodig:**
persistente batches/checkpoints en herstart op hetzelfde manifest.

**Projectie** na commit, zoals bij annotaties: `skos:Concept`/`prefLabel`/`definition`/`inScheme`,
`skos:ConceptScheme` voor het kader, bronverwijzingen volgens het NL-SBB-profiel, en werkgebied,
selectie en review als eigen uitbreidingen. Dit is een beoogde mapping, nog geen claim van
conformiteit. JAS-classificatie en begripsrelaties krijgen eigen predicaten. Een JAS-label maakt een
begrip geen `skos:narrower` van het methodebegrip. Juridische relaties worden niet platgeslagen tot
`skos:related`. Later krijgt Lex getypeerde begripsleestools (filters: werkgebied, status,
geldigheid). Begrippen zijn analyse-uitkomsten en nooit wettelijke definities.

#### Wijzigingen, historie en dekking

- Een scopewijziging maakt een nieuwe revisie. Lopende runs blijven bij hun manifest en worden niet
  ongemerkt geaccordeerd tegen de nieuwe scope.
- Bij bron- of annotatiewijzigingen worden de werkelijk gebruikte fragmenten vergeleken. Een nieuwe
  snapshot-ID alleen is een signaal, geen ongeldigverklaring.
- Uitbreiding van de scope wordt gemarkeerd als nog te verwerken, met nieuwe kandidaten en gevolgen
  voor bestaande begrippen.
- Een selectie verwijderen laat bron, annotaties en historische koppelingen intact.
- Bij herannotatie volgt geen automatische herkoppeling, maar een voorstel dat ankers, klasse en
  context vergelijkt.
- Een inhoudelijke begripswijziging markeert afhankelijke begrippen voor herbeoordeling.
- Dekking telt elk element één keer: te verwerken / voorstel / geaccordeerd gekoppeld / bewust
  buiten behandeling.

#### Leveringen

| Levering | Resultaat | Acceptatie |
|---|---|---|
| 1. Werkgebied en scope | node, bronselecties, api-opslag, tabs Bronnen/Elementen, eenvoudige samenhang | hetzelfde artikel in twee werkgebieden; een wijziging in de ene selectie raakt de andere niet |
| 2. Begrippenwerkplek | begripskaart, elementselectie, koppelingen, beoordeling, historie, JSON/CSV-export | uit meerdere annotaties één begrip maken en elke passage terugvinden |
| 3. Voorstellen van Lex | groeperen, formuleren, bestaand begrip zoeken, splitsen/combineren, hervatbare batches | verschillende formuleringen met gelijke betekenis gekoppeld; gelijke woorden met andere betekenis gescheiden |
| 4. Onderhoud en uitwisseling | gerichte herbeoordeling, relaties, begrippengraaf, RDF-export, Lex leest begrippen | een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand blijft |

**Eerste bouwopdracht:** levering 1 en 2 als één werkend pad met twee artikelen uit verschillende
regelingen, bestaande annotaties en één beoordeeld begrip met meerdere koppelingen. Buiten deze reeks
vallen een regelmodel-editor, een scenario-editor, een organisatiebrede begrippenbibliotheek en
automatische samenvoeging tussen werkgebieden.

**Verificatie.**
- **API**: node/subtree, overlap, grensoverschrijdende ankers, contextbronnen, revisieconflicten,
  idempotentie, autorisatie, verwijderen met behoud van bewijs.
- **Begrippen**: synoniem en homoniem, meerdere interpretaties, samenhang zonder synoniem,
  opvolging.
- **Actualiteit**: gebruikte tekst tegenover elders gewijzigd, scopewijziging tijdens een run,
  herannotatie.
- **Agent**: geen gefingeerde ID's, incomplete input zichtbaar, deelresultaten, herstart zonder
  duplicaten.
- **GUI**: de volledige doorloop, ook na herladen en met het toetsenbord.
- **Projectie**: reconstrueerbaar uit PostgreSQL.
- **Proefset**: dezelfde term in een andere context, andere termen met dezelfde betekenis, een
  definitie buiten de scope, en subject/object/voorwaarde. Juristen beoordelen groepering én
  definitie.

---

### E. Kennisbank — een tweede corpus naast de wetsgraaf

**Doel.** Beheerders uploaden beleidsstukken en handleidingen, en Lex bevraagt die samen met de
wettekst. Vastgesteld op 17 aug 2026: geen persoonsgegevens, wet en interne kennis mogen in één
antwoord, en de eerste omvang is ~100 documenten.

**De kern is grounding, niet de vector-opslag.** Een handleiding heeft geen `bwbId`. Er komt een
**tweede referentievorm** (`document + versie + pagina/sectie + chunk`), die precies dezelfde
behandeling krijgt: uit de tool-trace, letterlijk geciteerd, verifieerbaar. Documenten toelaten
zonder `grounding` uit te breiden maakt de garantie voor het hele platform ongemerkt zachter. Dat
mag niet.

**Normhiërarchie in prompt en UI.** De wet is de norm en beleid is toepassing. Bij tegenspraak wint
de wet en wordt het verschil benoemd. Een handleidingpassage wordt nooit als wettekst gepresenteerd.
De bronnenlijst is gesplitst in *Wet- en regelgeving* en *Beleid en handleidingen*. Versie en datum
staan altijd in beeld.

| # | Besluit | Waarom |
|---|---|---|
| D1 | Bestaande PostgreSQL met **pgvector** | Geen nieuwe stateful dienst; rechten, audit en back-up lopen mee. Een aparte vector-DB is overkill, GraphDB is zwak in documentbeheer |
| D2 | Azure `text-embedding-3-small` (1536 dim) | Geen AVG-beletsel, verwaarloosbare kosten. Geen LocalAI: te traag op 2 vCPU en schijnvertrouwelijkheid zolang generatie via Azure loopt |
| D3 | Geen ANN-index in v1, exacte cosine-scan | Bij 2–3k chunks sneller en exacter. HNSW is later één DDL-statement |
| D4 | Hybride retrieval: Dutch FTS + vector met RRF | Spiegelt `search_wetgeving` / `semantic_search` |
| D5 | De api bezit de kennisbank; graph-qa zoekt via `GET /v1/kennis/zoek` | Geen tweede DB-verbinding; embedding-config op één plek |
| D6 | Beheerder uploadt, elke analist leest (platform-breed) | Gedeeld corpus, past op `/v1/admin/*` |
| D7 | v1: PDF met tekstlaag, Markdown, TXT; geen OCR, DOCX later | Extractie is waar dit misgaat; een scan zonder tekstlaag wordt geweigerd met uitleg |
| D8 | Nieuwe upload = nieuwe versie; de oude wordt ingetrokken, niet gewist | Eerdere citaten blijven verklaarbaar |

**Datamodel.**

```
kennis_documenten   id, titel, bestandsnaam, mimetype, versie, datum, geldig_tot?,
                    soort (beleid|handleiding|overig), status (actief|ingetrokken),
                    sha256, paginas, geupload_door, geupload_op, ingetrokken_op?
kennis_chunks       id, document_id, ordinal, tekst, pagina?, kop?, tokens,
                    embedding vector(1536), tsv (generated, Dutch FTS)
kennis_audit        append-only: geupload / opnieuw-geindexeerd / ingetrokken / verwijderd
```

`sha256` herkent een dubbele upload vóór er kosten gemaakt worden. Een ander embedding-model
betekent herindexeren, en dat is een expliciete beheeractie. `vector` is een extensie en geen
additieve kolom, dus dit vraagt een bewuste migratie (Azure Flexible Server, `main.bicep`).

**Waar het landt.**
- **api**: `app/kennis/` (contracts, store, extractie/chunking), `routers/kennis.py`, admin-routes
  `POST/DELETE /v1/admin/kennis/documenten`, en `embed()` naast `complete()` achter dezelfde poort
  en throttle.
- **graph-qa**: drie tools achter een `KennisPort`:
  - `zoek_kennis`;
  - `haal_kennis_passage`, verplicht, want één chunk is te smal om te citeren;
  - `lijst_kennisdocumenten`.

  Deze tools komen bij de specialisten `duiding` en `algemeen`, niet bij `definitie`. `provenance`
  en `grounding` leren de tweede referentievorm, en de prompt krijgt de normhiërarchie.
- **frontend**: een beheertab *Kennisbank* (`components/admin/KennisPanel.tsx`) en een gesplitste
  bronnenlijst.

**Geen nieuwe agent.** Er draait één QA-specialist per beurt (`parse_supervisor`). Een aparte
`beleid`-specialist zou wet en beleid dus juist splitsen. Die komt er pas als de eval aantoont dat
één prompt de bronsoorten niet uit elkaar houdt, en dat vraagt dan een specialist per worker in de
supervisor. "Vergelijk wet met handleiding" kan via de bestaande decompositie
(`ENABLE_DECOMPOSITION`). Er komt geen aparte Critic: `verify_node` is de plek. De annotatie-worker
blijft bij de wettekst.

| Fase | Inhoud | Verificatie |
|---|---|---|
| 1 | Upload → extractie met pagina's → chunking (~500 tokens, overlap, kop-bewust) → embedding → `GET /v1/kennis/zoek` (vector-only) → drie tools → grounding → prompt → beheertab en gesplitste bronnen | Een citaat dat niet letterlijk in de chunk staat wordt geweigerd; een gemengde vraag geeft beide bronsoorten gelabeld; kennis-cases in `eval/golden.jsonl` |
| 2 | Hybride retrieval (RRF), DOCX, herindexeren na modelwissel, versiebeheer in de UI, eventueel herrank | — |
| 3 | Document of chunk koppelen aan een bepaling ("welk beleid hoort bij art. 36 IW") via het geaudite schrijfpad van de api | — |

**Risico's.**
- *Extractie-drift*: alleen PDF's met tekstlaag, en de ruwe tekst wordt bewaard.
- *Verouderd beleid als waarheid*: versie en datum verplicht, `geldig_tot`, intrekken.
- *Scope-creep naar documentanalyse*: het gaat om retrieval, niet om JAS-annotatie van documenten.
- *Modelwissel*: vraagt volledig herindexeren.

---

## Volgorde en samenhang

- **A** loopt los van de rest en is vooral werk voor beoordelaars. Het blokkeert alleen semantisch
  werk aan de annotatieketen, niet B, D of E.
- **B**: 7, 8, 9, 10 en 5c staan los van elkaar; alle afhankelijkheden zijn geleverd. PR 6, 7 en 9 kunnen parallel.
- **D** en **E** zijn onafhankelijk. D-levering 4 (Lex leest begrippen) en E-fase 3 (koppelen aan
  bepalingen) gebruiken allebei het projectie- en schrijfpad van de api. Ontwerp ze samen als ze
  tegelijk aan de orde komen.
- **C** eerst herijken. Een eventuele knowledge-check past het best bij D (ontdubbeling over een
  werkgebied).

## Open keuzes

1. **D — bediening**: Lex stelt standaard voor (voorstel van dit plan), de analist begint vanuit een
   eigen selectie, of beide even prominent.
2. **D — toegang**: gedeelde werkgebieden zoals de annotaties (voorstel), of afgeschermde dossiers
   met leden en rollen. Dat laatste moet vóór levering 1 besloten zijn.
3. **D — kaders**: één begrippenkader per werkgebied als start (voorstel), met later expliciet
   hergebruik tussen kaders.
4. **C**: blijft de leerlus een doel, en in welke vorm?
5. **B — PR 9 en 10**: wel of niet bouwen.
6. **A — scope**: horen relaties (operand, afleiding) en beleidsregels met rekenvoorbeelden bij
   activiteit 2? Zie het onderzoek §17, punten 7 en 9.
