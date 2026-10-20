# Plan — wetsanalyse-ai

Soort: *plan* (zie [`README.md`](README.md)) · Bijgewerkt: 14 oktober 2026

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
- **Uitleg en dekking verdiept** (#605, #606, #614): de toelichting in twee lagen met een reden per
  alternatief, deterministisch uit het bewijs (`agent/jas_pipeline/uitleg.py`); per dimensie ook
  wat er gevonden is (`jas:aantal`); zinsdelen die alleen als geheel geraakt werden
  (`jas:alleenAlsGeheel`). Alles additief in projectie, SHACL en export-schema v3.
- **Vervolgvragen in één gesprek** (#607–#612, #616): gespreksfocus (`agent/focus.py`), een
  supervisor die een vervolgvraag zelfstandig herschrijft, grounding over het gesprek
  (`agent/bronregister.py`), `overzicht_annotaties` en annotatietools voor `duiding`, en het
  letterlijk maken van een bijna-letterlijk citaat (`grounding.herstel_citaten`). Gemeten met de
  gesprekseval (`run_eval.py --gesprek`): 7–9 → 11–12 van 12 vervolgbeurten →
  [`metingen/gesprek-vervolgvragen-2026-10-06/`](architectuur/metingen/gesprek-vervolgvragen-2026-10-06/README.md).
- **Samenhangsgraaf** (#540–#546): `GET /v1/annotatie/samenhang` (`api/app/samenhang.py`,
  capability `samenhang`) en de graaf in de werkplek, sinds okt 2026 een 2D-graaf op sigma.js +
  graphology (`components/graaf/Graaf.tsx`, rekenkern `lib/graaf/`) in plaats van de 3D-krachtgraaf;
  `GET /v1/annotatie/graaf` levert de hele kennisgraaf (schakelaar *Dit antwoord | Hele kennisgraaf*,
  met de nadruk op wat het antwoord noemt; een overzicht opent hem direct). Die staat als tab *Graaf* in het
  annotatiepaneel en opent ook via "Bekijk … in de graaf" onder chatbronnen. Hij toont de bronstructuur, markeringen met hun
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
| B | Herkomst zichtbaar in werkplek en exports | Af: alle PR's gebouwd en op productie (`v1.11.0`) |
| C | Leerlus en knowledge-check | Te herijken |
| D | Activiteit 3: werkgebieden en begrippen | Ontwerp klaar, niets gebouwd |
| E | Kennisbank (tweede corpus) | Ontwerp klaar, niets gebouwd |
| F | Activiteit 1 in het gesprek: werkgebied bepalen | F0 en F1 gebouwd (vraagkaarten zoals Claude → werkgebied); vervolg open |

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
(onderzoek §18.6). Kandidaten 2, 3 en 10 blijven ná V7. **Uitgevoerd**, met alle vier de fouten weg
op IW05. Op v1 gaat geen anker verloren, maar de precisie is 2 procentpunt lager; dat is met drie
rondes niet van run-variatie te scheiden. Meting en criteria:
[`metingen/hybrid-v1-iw05-fixes-2026-10/`](architectuur/metingen/hybrid-v1-iw05-fixes-2026-10/README.md).

Valt eveneens onder deze uitzondering, omdat het een spellingsgat is en geen interpretatiekeuze:
telwoorden als opbouwregel in plaats van een vaste lijst (#613; "eenentwintig dagen" werd geen
Tijdsaanduiding). Ankerdekking gelijk (89%).

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

Kandidaten 1, 3–6 en 9 zijn uitgewerkt in
[`architectuur/verbeterplan-jas-pipeline-2026-10-08.md`](architectuur/verbeterplan-jas-pipeline-2026-10-08.md):
bewijs per hypothese, gerichte frames en relaties, in vier PR's achter een proefvlag. Dat werk start na V7.

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
- de samenhangsgraaf is dé graaftab van het paneel. De Turtle van een markering en de
  graafcontrole-status komen onder "technisch detail" in de graafinspector en in de export.

**UI-richting.** De huidige opzet blijft: een gespreksvenster met de annotatie als zijpaneel. Die
volgt zo dicht mogelijk de patronen van Claude: een ingeklapt stappenblok met fasen en duur, het
antwoord als proza met citatie-chips die een bronkaart openen, een zijpaneel met revisiehistorie en
de tabs *Tekst / Dekking / 3D-graaf*, en bij tekstselectie *Markeer als… / Vraag Lex*.

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
[NL-SBB 10 okt 2024](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), vastgelegd als
begrippencontract in [ADR-003](architectuur/adr-003-nl-sbb-begrippencontract.md). Het onderzoek
naar bronselectie, taalpatronen en retrieval staat in
[`onderzoek-werkgebied-en-begrippen-2026-10.md`](architectuur/onderzoek-werkgebied-en-begrippen-2026-10.md);
het INT-terminologieonderzoek in
[`onderzoek-int-terminologie-2026-10-08/`](wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md).

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
`frontend/lib/graaf/`: een samenhangsgraaf per bepaling (`/v1/annotatie/samenhang`), die
de tab *Samenhang* en de werkgebiedgraaf als basis kunnen hergebruiken. De runstore overleeft een procesuitval nog niet. De keten `hybrid_v1`
hoeft niet te veranderen.

Voor het vinden van bronnen ligt er al het volgende:
- `overzicht_bouwen` (`tools/graph-qa/agent/overzicht.py`) zoekt deterministisch op tekst, opbouw,
  definities en trefwoorden. Hij volgt geen verwijzingen, gebruikt geen semantiek en geeft geen rol
  of bewijs per bepaling.
- De graaf kent verwijzingen (`bwb:verwijstNaar`, gereïficeerd als `bwb:Verwijzing`) met
  `queries.follow_verwijzingen` en `referenced_by`. Ze zijn **niet getypeerd naar functie**:
  `soort` is alleen INTERN, EXTERN of TEKSTUEEL.
- `bwb_similarity` is SemanticVectors op alleen `bwb:tekst`, zonder context.
- De graaf houdt één toestand per regeling. Een peildatum is in de praktijk dus de actuele
  toestand.
- Er is geen retrieval-benchmark: `eval/retrieval_smoke.py` toetst alleen of er iets terugkomt.

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

#### Bronnen vinden voor een werkgebied

Lex stelt bepalingen voor, de analist neemt ze op. Een voorstel is een **kandidaatbepaling**, een
eigen object naast de bronselectie:

- **Herkomst en bewijs per methode**: welke methode vond hem, en waarop (verwijzings-ID,
  definitie, zoekhit). Vinden meerdere methoden dezelfde bepaling, dan is dat één kandidaat met
  meerdere bewijsgronden.
- **Rol**: *kern* (regelt het onderwerp zelf), *afhankelijkheid* (nodig om een kernbepaling te
  begrijpen of toe te passen: definitie, uitzondering, termijn) of *aanverwant* (mogelijk
  relevant, noodzaak niet aangetoond).
- **Status**: voorgesteld, opgenomen (wordt een bronselectie met rol analyseren of contextbron),
  later, of **uitgesloten met reden**. Een uitgesloten kandidaat stelt Lex niet opnieuw voor.

Ontdekmethoden, van sterk naar zwak bewijs, allemaal zonder model:

1. handmatig, vanuit zoeken, een annotatie of de graaf;
2. verwijzingen in en uit (`queries.follow_verwijzingen`, `referenced_by`);
3. definities van termen die in de selectie voorkomen (`bwb:definieertBegrip`);
4. tekst en opbouw: de queries achter `overzicht_bouwen`;
5. `bwb_similarity`, als zwakste signaal. Semantische gelijkenis is geen bewijs van juridische
   toepasselijkheid.

**Verwijzingen gericht volgen**, volgens het beleid in de skill
([`verwijzingen-volgen.md`](../.claude/skills/wetsanalyse/references/verwijzingen-volgen.md)):
diepte 1 vanaf de kernbepalingen, verder alleen langs een concrete afhankelijkheid. Blind
uitbreiden langs de graaf maakt de selectie aantoonbaar slechter (zie het onderzoek). **Nieuw
nodig:** de functie van een verwijzing deterministisch afleiden uit de context van haar anker, bijv.
een anker in een brondefinitie → *definitie*, na "in afwijking van" → *uitzondering*. Dat is een
afleiding in de leeslaag, geen importwijziging. Zolang die er niet is, toont de werkplek "functie
onbekend".

**Analysevraag en deelvragen** (optioneel). De analist kan de analysevraag opdelen in deelvragen
("welke termijn geldt?", "wat is het startmoment?"). Een kandidaat kan een deelvraag dekken. De
**dekkingscheck** toont welke deelvragen, en welke JAS-bouwstenen van de kernbepalingen (subject,
object, rechtsfeit, voorwaarde, tijd, uitzondering), nog zonder bron zijn. Dat is een onderbouwde
volledigheidsindicatie binnen de vraag, geen garantie.

Uitbreiden en afbakenen horen bij elkaar: een selectie van honderd bepalingen waar er twaalf nodig
zijn is onbruikbaar, ook als ze alles bevat.

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
- **Een term is nog geen begrip.** Een termkandidaat (een formulering met lemma en woordgroep) mag
  zonder begrip blijven staan, als "zwevende term" zoals in TermWerk. De begrippenwerkplek heeft
  daarvoor een lijst *Termkandidaten*.
- **Kwalificatie is geen synoniem.** "X geldt als Y" en "X wordt aangemerkt als Y" leveren een
  kwalificatie- of fictierelatie op, nooit automatisch één begrip. "Onder X wordt mede verstaan"
  is een inclusie, "onder X wordt niet verstaan" een uitsluiting en dus negatief bewijs.
- **Bewijs heeft een richting.** Elk signaal bij een kandidaatkoppeling is *steun*, *tegen* of
  *onbeslist*. Er is geen gecombineerde score. De uitkomst van een vergelijking is een van: zelfde
  betekenis, verwant maar ander begrip, betekenisverschil, onbeslist.
- **Begripstype als werkindeling**: entiteit, actor, toestand, gebeurtenis, eigenschap, relatie.
  Dat helpt bij het kiezen van een definitiepatroon en is geen nieuwe JAS-klasse. Een waarde als
  "zes weken" is een tijdsaanduiding of parameterwaarde, geen begrip.

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
| `Kandidaatbepaling` | werkgebied, bron-IRI, methoden met bewijs, rol (kern/afhankelijkheid/aanverwant), gedekte deelvragen, status, reden bij uitsluiten |
| `Deelvraag` | werkgebied, vraag, volgorde, dekkingsstand |
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
| `/{id}/kandidaten`, `/{id}/deelvragen` | kandidaatbepalingen met bewijs; opnemen, uitsluiten met reden; dekkingscheck |
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
4. Een deterministische beslistabel zet de signalen om in voorstellen. Alleen twijfelparen gaan
   naar een klein model, dat kiest op kandidaat-ID en geen element-ID's of vindplaatsen invoert die
   niet bestaan.
5. Deterministische controles op ID's, bereik, hashes en verplichte velden. Inhoudelijke signalen
   zijn onder meer tegengestelde contexten, circulaire definities en voorbeelden die niet bij de
   definitie passen. De mens beslist.
6. De api bewaart per afgeronde batch en SSE meldt echte voortgang. Na herladen zijn de voorstellen
   er nog.

Hoe Lex groepen voorstelt staat in [ADR-004](architectuur/adr-004-begrippenketen.md): een
hybride keten zoals `hybrid_v1`, met signalen met bewijs en richting, een vaste beslistabel en een
model alleen bij twijfel.

Grote werkgebieden gaan in begrensde batches, gevolgd door een vergelijking tussen batches. Een
gedeeltelijk resultaat wordt als gedeeltelijk gemeld, met het behandelde bereik. **Nieuw nodig:**
persistente batches/checkpoints en herstart op hetzelfde manifest.

**Projectie** na commit, zoals bij annotaties: `skos:Concept`/`prefLabel`/`definition`/`inScheme`,
`skos:ConceptScheme` voor het kader, bronverwijzingen volgens het NL-SBB-profiel, en werkgebied,
selectie en review als eigen uitbreidingen. NL-SBB is vanaf levering 2 het datacontract van
begrippen, niet alleen het exportformaat
([ADR-003](architectuur/adr-003-nl-sbb-begrippencontract.md)). Conform heet alleen wat tegen de
SHACL van de vastgepinde versie gevalideerd is. JAS-classificatie en begripsrelaties krijgen eigen predicaten. Een JAS-label maakt een
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

#### Leveringen en fasen

**Gebouwd** (op acceptatie):

| Levering | Resultaat |
|---|---|
| 1. Werkgebied en scope (#659–#661) | node, bronselecties, api-opslag, tabs Bronnen/Elementen/Samenhang, verwijzingen als suggestie, opnemen vanuit graaf en annotatie |
| 2. Begrippenwerkplek (#662–#663) | begripskaart, elementselectie, koppelingen met bewijsstand, beoordeling, poort, historie, JSON/CSV-export |
| 3a. Deterministische voorstellen (#655–#658, #664–#666) | de keten van ADR-004 op het manifest van een werkgebied: groepen, relaties, twijfelvragen; overnemen, splitsen, combineren, koppelen, afwijzen |

**Herzien op 15 okt 2026: een Lex-gedreven stroom.** Na gebruik bleek het vooral handwerk: bronnen,
elementen en begrippen vult de analist zelf, en de voorstellen staan los van de werkplek. Besloten: op
elk punt waar de analist nu handwerk doet, doet Lex een voorstel met bewijs, en de analist beoordeelt
het – in dezelfde vorm als bij annoteren. Wat er staat, blijft het fundament.

```
vraag aan Lex ─► werkgebied: Lex stelt bepalingen voor ─► Lex annoteert wat ontbreekt
             ─► Lex stelt begrippen voor mét concept-kaart ─► review als artefact ─► begrip
             ─► Lex naast de kaart ─► accorderen ─► onderhoud en uitwisseling
```

| Fase | Resultaat | Acceptatie |
|---|---|---|
| AF. Eén artefactmodel – **gebouwd** (AF1 #668, AF2) | `Bericht.artefact {soort: annotatie \| begrippen \| regels, ref, titel}`; chip en artefactpaneel per soort; de werkplek opent vanuit een werkgebied en toont dat; supervisor-route *begrippen*. `regels` (afleidingsregels) wordt alleen gereserveerd | begrippen voorstellen vanuit de chat levert een artefact dat na herladen terugkomt |
| A. Bronnen vinden met Lex – **gebouwd** (#670–#672, meting A4; deelvragen en dekkingscheck volgen) | kandidaatbepalingen (herkomst en bewijs per methode, rol kern/afhankelijkheid/aanverwant, uitsluiten met reden); werkgebied vanuit een overzicht; verwijzingen diepte 1, definities, opbouw, similarity als zwakste; functie van een verwijzing; deelvragen en dekkingscheck | een uitgesloten kandidaat komt niet terug; ablatie per methode op de referentieset bronselectie |
| B. Lex annoteert het werkgebied – **gebouwd** (B1 #674, B2 #675, B3) | werkgebied-annotatierun over de bepalingen van de analysebronnen die nog **nieuw** zijn (per lid, zoals de keuzekaart; plafond 40 per run), met een bevestiging vooraf (aantal, schatting uit de laatste 20 annotatiebeurten, budget, wat niet meegaat) en voortgang als reeksblok; ingangen: tab Elementen (vers gesprek), werkgebiedbalk en de chat | na de run staan de elementen in de inventaris; hergebruik slaat afgeronde bepalingen over; een gewijzigde werkvoorraad start niet stil |
| C. Lex formuleert begrippen (was L3b) – **gebouwd** (C1 #677, C2 #678, C3; meting `metingen/begrippen-model-2026-10-15`) | model voor twijfelparen (alleen *zelfde betekenis* wordt een – gele – groep, ander advies laat de vraag staan); concept-kaart per groep (naam, begripstype, context, definitie met herkomst, dragende passages, voorbeelden) met deterministische toetsen; bestaand begrip zoeken; hervatbare batches | verschillende formuleringen met gelijke betekenis gekoppeld, gelijke woorden met andere betekenis gescheiden; garanties (letterlijkheid, id's) op 100% |
| D. Beoordelen als artefact – **gebouwd** (D1 #681, D2) | reviewlijst zoals bij annoteren (akkoord, aanpassen, afwijzen, splitsen, combineren met vergelijking, toetsenbord), in het artefactpaneel én op de tab Begrippen; akkoord is één transactie (begrip, beoordeelde koppelingen, accorderen als de poort mag), splitsen laat de rest van de groep staan, een onbeoordeelde annotatie keur je ter plekke goed | uit voorstellen een geaccordeerd begrip, zonder leeg formulier |
| E. Lex naast de kaart – **gebouwd** (E1 #683, E2 #684, E3; meting `metingen/kaartacties-2026-10-16`) | vier knoppen op de begripskaart – brondefinitie (zonder model, met plaats: werkgebied, regeling, definitieverwijzing, elders), scherpere definitie, betekenisverschil met een ander begrip, voorbeelden – elk als voorstel onder zijn veld; overnemen, aanpassen of afwijzen; `definitie_door` op het begrip | niets wordt stil overschreven (een veranderde definitie toont toen, nu en voorstel; vervangen is een bewuste keuze); herkomst gaat mee |
| F. Onderhoud en uitwisseling (was L4) – **gebouwd**: F1 (#686, #687), F2 (#688, #689), F3 (#690, #691), F4 (#695 api, #696 graph-qa, F4c werkplek) | in vier deelleveringen: **F1** gerichte herbeoordeling (annotatie én wettekst onder het anker, toen naast nu), voorstel tot herkoppeling (opvolgers na herannotatie, signalen met richting), bevestigen met een tweede bewijsstand, dekking met *buiten behandeling*; **F2** begripsrelaties en opvolging; **F3** NL-SBB-projectie, RDF-export en begrippengraaf; **F4** Lex leest begrippen, overzicht over werkgebieden heen en de chat-ingang voor Lex naast de kaart | een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand blijft |

Volgorde: AF → A → B → C → D → E → F. Voorbeelden op de concept-kaart zijn van C naar E verschoven:
ze hebben geen bronanker en horen als voorstel per veld bij Lex naast de kaart. Afleidingsregels (RegelSpraak) vallen erbuiten; AF legt alleen
hun plek in het artefactmodel vast.

**Besloten voor F (16 okt 2026).** Volgorde F1 → F2 → F3 → F4. Een geaccordeerd begrip met een
gewijzigde dragende passage blijft geaccordeerd en krijgt een vlag; herkoppelen of bevestigen rondt de
herbeoordeling af, zonder statuswijziging. Herkoppelen maakt de oude koppeling historie
(`vervangen_door`), met haar bewijsstand. SHACL bij begrippen is diagnostisch (open keuze 5). F2: *Nieuwe betekenis* kopieert inhoud en passages
(opnieuw open); het oude begrip wordt `vervangen` (alleen-lezen, geen primaire duiding, terug door de
opvolger te verwijderen); combineren van twee begrippen hoort erbij; de analist legt de vier juridische
typen of `verwant` (met toelichting) vast, opvolging alleen via de knoppen. F3: de graaf krijgt **alle**
begrippen met hun status (concept, geaccordeerd, vervangen); de Turtle-export standaard alleen de
geaccordeerde (`inclusief=alle` voor de rest); de NL-SBB-shapes (profiel 1.0.0, CC-BY 4.0) staan
gevendord in `api/app/shapes/` met een hashtoets; de begrippengraaf komt op de tab *Samenhang*, met
data uit Postgres.

**Besloten voor F4 (19 okt 2026).** Lex leest de begrippen van **alle** werkgebieden; opent de werkplek
vanuit een werkgebied, dan staan diens begrippen vooraan. Hij noemt **alle** begrippen met hun status
(concept, geaccordeerd, vervangen met opvolger), geaccordeerd eerst. `search_begrippen` zoekt met SPARQL
in de F3-projectie en laat de kandidaten door de api bevestigen (`POST /v1/begrippen/verifieer`); loopt
de projectie achter, dan is het resultaat onvolledig. Een begrip is afgeleide duiding: geen bron, geen
grounding. Kaartacties vanuit het gesprek ("zoek de brondefinitie van termijn") starten **direct**, net
als de knop, met de budgetpoort van de kaart-run. Het overzicht *Begrippen* in de sidebar is een
leesingang (`GET /v1/begrippen`, uit Postgres); werkgebieden en begrippen komen (nog) niet in de
rondleiding.

**Na F (19 okt 2026).** Wat na fase F openstond, in leveringen G0–G3:

| Levering | Resultaat |
|---|---|
| G0. Reparaties in de werkplek – **gebouwd** (#698) | onbewaarde begripswijzigingen ook bewaakt bij een link in de sidebar en in het artefactpaneel (`useOnbewaardBewaker`); het begrippenpaneel zegt het als de chip naar een eerdere ronde wijst; de beurtsamenvatting onder de annotatiechip komt uit het bericht |
| G1. Deelvragen en dekkingscheck – **gebouwd** (#699 api, #700 graph-qa, #701 werkplek) | deelvragen bij een werkgebied, optioneel; Lex stelt ze voor uit de analysevraag (overnemen of afwijzen met reden); per deelvraag bronnen en begrippen, en de stand *gedekt* / *nog geen geaccordeerd begrip* / *nog geen bron*; bronnen vinden zoekt ook per deelvraag (methode `deelvraag`, nog niet gemeten) |
| G3. Lex meldt herbeoordeling – **gebouwd** (#702) | Lex en het overzicht *Begrippen* noemen een geaccordeerd begrip waarvan een dragende passage veranderde (`herbeoordelen`). Werkgebieden en begrippen komen bewust niet in de rondleiding (besloten 19 okt 2026) |
| G2. Meten en valideren – **open** | de referentieset bronselectie *Invorderbaarheid* door een jurist laten vaststellen (nu een concept), daarna de ablatie opnieuw, ook voor `deelvraag`; een nieuwe held-out begrippenset met dezelfde term in één bepaling, synoniem/homoniem, "geldt als", inclusie/uitsluiting en een definitie buiten het werkgebied |

Nog niet gedaan: de dekking per deelvraag in de werkgebiedbalk van de werkplek. Buiten deze reeks blijven
hergebruik tussen begrippenkaders, publiceerbare HTTP-URI's en afleidingsregels.

**Besloten (14–15 okt 2026).** Werkgebieden zijn gedeeld. Elke analist mag een begrip accorderen (de
audit legt vast wie). De poort vraagt naam, definitie met herkomst, context, minstens één aanduidende
passage, en dragende koppelingen die beoordeeld en actueel zijn en op een door een jurist beoordeelde
annotatie rusten; een voorbeeld is een kwaliteitssignaal, geen voorwaarde. Eén begrippenkader per
werkgebied, impliciet. Bediening: Lex stelt voor en zelf maken blijft mogelijk.

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
  definitie. Ook: kwalificatie tegenover synoniem ("geldt als"), inclusie en uitsluiting, en een
  verwijzing naar een definitie buiten het werkgebied, die als kandidaat moet verschijnen.
- **Bronselectie**: een door een jurist vastgestelde referentieset van werkgebieden, eerst
  *Invorderbaarheid van belastingaanslagen*. Meet recall@k én het aandeel overbodige bepalingen,
  per ontdekmethode apart (ablatie, zie het onderzoek). Een methode die niet aantoonbaar helpt,
  staat niet standaard aan.

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

### F. Activiteit 1 in het gesprek: werkgebied bepalen

**Doel.** Een wetsanalyse begint in het gesprek met Lex, niet met een formulier. "Kunnen we een
werkgebied samenstellen?" of "ik wil een wetsanalyse uitvoeren" start activiteit 1 van de Leidraad
(*werkgebied bepalen*). Lex stelt de vragen zoals Claude dat doet: één per kaartje, met voorstellen
en een eigen antwoord. Na de samenvatting staat het werkgebied bij Werkgebieden, met een eigen paneel
naast het gesprek (zoals een annotatie, maar los ervan).

**F0 – vraagkaarten → werkgebied** (gebouwd, okt 2026; besluiten van de gebruiker op 19 okt 2026):

- De volgorde is vast: naam (verplicht), analysevraag, en de afbakening in drie gerichte vragen –
  regeling(en), onderdelen, wat valt erbuiten – en een samenvatting met *Aanmaken*. Geen
  peildatum-kaartje.
- Een **worker onder de supervisor** (`werkgebied`), met een deterministische stapmachine; het model
  stelt alleen voor (naam, analysevraag, onderwerp). Regelingen en onderdelen komen uit de graaf.
- **Bronnen zijn vaak nog niet bekend**: "Weet ik (nog) niet" staat altijd bij regelingen en
  onderdelen. Alleen een gekozen onderdeel wordt een bronselectie (rol *analyseren*, bereik
  *onderliggend*); *de hele regeling* blijft tekst.
- Een tussenvraag laat de intake open; wat de eerste zin al zegt staat voorgeselecteerd, nooit stil
  aangenomen. Aanmaken is idempotent (`intake_id`).
- PR's: api (#706), graph-qa (#707), werkplek.

**F1 – vraagkaarten zoals Claude** (20 okt 2026): de open vraag onderaan in plaats van het
invoerveld (✕ wegklikken, "● Een vraag stellen ›" in de thread), beantwoorde vragen in één
Vragen-kaart zonder bubbels (`intake_antwoord` op het bericht), opties met een omschrijving uit de
graaf, eigen tekst als laatste regel, pilknoppen, en terugbladeren met ‹ n van 5 ›.

**F2 – startactiviteit a en de volgorde van activiteit 1** (gepland 20 okt 2026; besluiten van de
gebruiker op 20 okt 2026). Getoetst aan Leidraad §2.2 (startactiviteiten) en §2.4, en aan Handleiding
§3.3 (activiteit 1).

- **Waarom.** De startactiviteiten gaan vooraf aan hoofdactiviteit 1–6 (Leidraad §2.2), en
  startactiviteit a – aanleiding, context en doel(en) – ontbrak. De hoofdvraag "bepaalt het doel van
  de Wetsanalyse en de afbakening van het werkgebied" (Handleiding 1a) en volgt dus uit a. En de
  bronnen horen pas te komen "als de hoofdvraag/hoofdopdracht en deelvragen bekend zijn" (1f): F0
  vroeg ze te vroeg, en zocht daardoor op te weinig.
- **Uitgangspunt: alles wat er ligt, is de context van Lex – en die wordt steeds scherper.** Elk
  antwoord en elke toevoeging aan het werkgebied voedt de volgende voorstellen; Lex vraagt nooit iets
  wat hij al weet en stelt niets voor op minder dan wat er ligt. Concreet:
  - *In de intake* bouwt één functie het dossier uit alle antwoorden tot nu toe (startzin, naam,
    aanleiding, context, doel, analysevraag, praktijkvoorbeeld, deelvragen, wat erbuiten valt), en
    **elke** voorstelaanroep en elke zoekopdracht krijgt dat hele dossier – ook de naam en de
    voorselectie van aanleiding en doel. Een test eist dat geen stap minder krijgt.
  - *Terugbladeren* en een eerder antwoord wijzigen maakt de voorstellen van de stappen erna opnieuw;
    wat de analist al koos blijft voorgeselecteerd, nooit stil vervangen.
  - *Na het aanmaken* is het werkgebied zelf het dossier: één `werkgebied_context.context_tekst`
    (alle velden, actieve deelvragen, de afbakening, de bronselecties) uit de api, per beurt vers. Die
    voedt de deelvragenrun en **het gesprek**: met een `werkgebied_id` gaat het als contextblok naar de
    supervisor en de specialisten, naast de focus. Context, geen filter – net als de focus. De
    bronnenrun krijgt het dossier in haar invoer (`dossier`), maar haar methoden gebruiken het pas in
    de iteratie over de bronvoorstellen: een methode wijzigen vraagt eerst een meting.
  - Elke bewaarde wijziging (een veld, een deelvraag, een opgenomen of uitgesloten bron) verhoogt de
    revisie, en de volgende beurt leest de nieuwe stand.
- **Volgorde van de kaartjes:** naam → aanleiding → context → doel → analysevraag → praktijkvoorbeeld
  → deelvragen → wat valt erbuiten → regeling(en) → onderdelen → samenvatting met *Aanmaken*. Alleen
  de naam is verplicht.
- **Aanleiding en doel** zijn elk een kaartje met de vaste lijst uit de Leidraad plus eigen tekst;
  **context** is vrije tekst (de Leidraad: voor de context helpt een lijst niet). De lijsten staan
  **in eigen woorden** in de repo – de Leidraad is BRM-materiaal en lokaal-only – met een verwijzing
  in `references/bronnen.md`. Lex mag uit de startzin voorselecteren, nooit stil aannemen.
- **Analysevraag** = hoofdvraag óf hoofdtaak (1a); Lex stelt haar voor uit aanleiding, context en doel.
- **Praktijkvoorbeeld** (1b), optioneel en vrije tekst: één gangbaar voorbeeld, als voeding voor
  deelvragen en bronzoeken. Geen juridische scenario's en gebeurtenissen (1c/1e): dat is de
  "deelvragen eerst"-variant die de Leidraad toestaat – een bewuste afwijking, zie *Vervolg*.
- **Deelvragen** (1d): Lex stelt er een paar voor uit alles hierboven (de prompt van
  `agent/deelvragen.py`, op `LLM_MODEL`); de analist kiest er één of meer, voegt er zelf één of meer
  toe, of kiest "Geen deelvragen (nu)" (open keuze 4: optioneel). Alleen de vraag, geen soort
  direct/indirect.
- **Wat valt erbuiten** komt na de deelvragen en vóór de bronnen.
- **Regelingen en onderdelen** zoeken met alles wat er dan ligt: de analysevraag en per deelvraag
  (`onderwerp_van_deelvraag`), met wat erbuiten valt als uitsluiting. Een onderdeel dat bij een
  deelvraag werd gevonden, wordt bij het aanmaken aan die deelvraag gekoppeld (1g, de dekkingscheck
  uit G1). Minder en betere bronvoorstellen is een volgende iteratie.
- **Het werkgebied draagt alles**: aanleiding (keuze + toelichting), context, doel (keuze +
  toelichting) en praktijkvoorbeeld als velden met revisie en audit; de deelvragen komen bij het
  aanmaken mee (actief, herkomst `analist` of `lex`, idempotent op `intake_id`). Het werkgebiedpaneel
  naast het gesprek en de werkgebiedpagina tonen alles, de pagina bewerkt het ook.
- **PR's:** api (F2a: velden, deelvragen bij aanmaken, de werkgebiedcontext), graph-qa (F2b: de
  intake met het dossier, de werkgebiedcontext in deelvragenrun, bronnenrun en gesprek), werkplek (F2c).

**F3 – Lex kiest de juiste agent, de werkplek is voor raadplegen** (gepland 20 okt 2026; besluiten
van de gebruiker op 20 okt 2026).

- **Waarom.**
  - De supervisor kent alleen `antwoord`, `annotatie` en `werkgebied`. Bronnen zoeken, begrippen
    voorstellen, meedenken en kaartacties zijn harde routes vóór de supervisor, gekozen op
    tekstpatronen (`_stroom_voor`). Een vraag als "is deelvraag 3 gedekt?" heeft geen agent.
  - Op de werkgebiedpagina starten zes knoppen Lex buiten het gesprek om. De vier kaartacties
    blokkeren elkaar.
  - "Vraag Lex" bestaat alleen voor markeringen (`nodeVraag`, `_advies_context`).
  - De intake biedt regelingen en hoofdstukken aan, nooit artikelen of leden.
    `regeling_opties` gooit de bepalingen weg, en `bepalingen_met_onderwerp` tilt een treffer op naar
    het artikel.
  - Deelvragen en bronnen staan overal in omrande boxen. De stijl van de vraagkaart (rijen met een
    scheidingslijn) is het voorbeeld.
- **Drie plekken, elk met één taak.**
  - **Gesprek:** alle redeneerwerk. De supervisor kiest uit vijf agents: antwoord, annotatie,
    werkgebied, **deelvragen** en **begrippen**.
  - **Zijpaneel:** het resultaat beoordelen (overnemen, aanpassen, afwijzen).
  - **Werkgebiedpagina:** raadplegen en kleine handmatige wijzigingen, zonder Lex-knoppen.

  Vanuit elk object – markering, deelvraag, bron, kandidaat, begrip, werkgebied – leidt één
  generieke **Vraag Lex** naar het gesprek, met suggesties die bij dat object passen. Elk resultaat
  opent als paneel: werkgebied, deelvraag met bronnen, begrip.
- **Nette agents.** Elke agent is een Python-module met:
  - een vaste lijst `Taak`;
  - per taak een Pydantic-`Invoer` en -`Uitkomst` (status, voorstellen, artefact, tekst uit code,
    meting);
  - een keten van gewone functies.

  Een model komt alleen in een stap die een oordeel of formulering vraagt. Die stap is één `strict`
  tool met validatie in code, zoals de classifier. Er is geen vrije tool-lus: zoeken, koppelen,
  dekking, rangschikken en opslaan is code. Een uitlegvraag over een object gaat naar de
  antwoord-worker (`duiding`), met de context van het object en de grounding.
- **Routering.**
  - Getypte tekst gaat altijd langs de supervisor (agent + taak); de tekstpatronen verdwijnen.
  - Een klik op een suggestie stuurt een `actie` mee en gaat zonder model naar de agent en de taak.
  - Wat duur is, vraagt eerst een bevestiging, zoals nu.
  - Lex stelt voor, de analist beslist.
- **Deelvragen-agent:**
  - `voorstellen` en `verbeteren` (herformuleren of splitsen): één modelstap elk;
  - `bronnen_zoeken`: per deelvraag, op lidniveau, met verwijzingen op diepte 1, als kandidaten met
    `deelvraag_id`. Geen model;
  - `dekking`: geen model.

  De methode (wat een goede deelvraag is, van deelvraag naar bronnen, wat dekking betekent) komt als
  agentrol in de skill (`references/deelvragen-en-bronnen.md`, in eigen woorden).
- **Begrippen-agent:**
  - zonder model: `voorstellen` (keten ADR-004), `brondefinitie`, `relaties`;
  - met model: `meedenken` (met bevestiging), `scherper`, `voorbeelden`, `betekenisverschil`, en
    `uitwerken`.

  `uitwerken` doet eerst de brondefinitie, dan een definitievoorstel, en voorbeelden pas op een
  overgenomen definitie. De begrippenkennis komt als agentrol in de skill.
- **Intake.** `onderdelen` wordt `bepalingen`, met één kaart per deelvraag: gerichte artikelen en
  leden binnen de gekozen regelingen.
  - De kandidaten komen zonder model uit:
    - de termen van de deelvraag;
    - de dossiertermen;
    - `fts` op Lid/Artikel;
    - `bepalingen_met_onderwerp` met het lid erbij.
  - Ze zijn vast gerangschikt, hoogstens 8 per kaart, met een letterlijk tekstbegin en het label uit
    de graaf.
  - Een keuze wordt meteen aan die deelvraag gekoppeld.
  - De intake blijft een eigen stapmachine; ze deelt alleen de zoekfunctie met de deelvragen-agent.
  - Twee fixes gaan mee:
    - een uitsluiting filtert niet meer stil: wat geraakt wordt, staat achteraan, gemarkeerd, en
      wordt nooit vooringevuld;
    - de afrondingstekst noemt alleen wat er echt gekoppeld is.
- **Werkgebiedpagina.**
  - Bovenaan dezelfde samenvatting als het zijpaneel.
  - De tabbladen Bronnen, Elementen, Begrippen, Samenhang en Historie in lijststijl.
  - Weg zijn alle Lex-knoppen: deelvragen voorstellen, zoeken/opnieuw zoeken, *Laat Lex annoteren*,
    *Stel begrippen voor*, *Laat Lex meedenken*, en de kaartacties.
  - Elke rij krijgt een Vraag Lex-knop.
  - Handmatige beslissingen blijven: kandidaten opnemen of uitsluiten, groepvoorstellen, en
    kaartvoorstellen overnemen.
- **PR's**, gestapeld:
  - **F3a** frontend: lijststijl (`Lijst`/`LijstRij`/`Sectie`/`StatusLabel`/`Voorstel`) en de
    gedeelde `WerkgebiedSamenvatting` – **gebouwd** (20 okt 2026): in het paneel en bovenaan de pagina,
    en de deelvragen, kandidaten en bronselecties in lijststijl;
  - **F3b**: het Vraag Lex-contract (`onderwerp` + `actie`, `agent/onderwerp.py`). Het
    markeringsadvies blijft byte-gelijk – **gebouwd** (20 okt 2026): `Onderwerp` en `actie` aan beide
    kanten, het contextblok per soort uit de api, de focus voor vervolgvragen, `VraagLexKnop` met
    `?vraag=`, en de handelingen op het werkgebied als suggestie met een actie (die nu de bestaande harde
    routes kiest). `annoteer=`/`meedenk=` blijven tot F3e, met de paginaknoppen die ze gebruiken;
  - **F3c** graph-qa + skill: de twee agents onder de supervisor, de agentrollen, ADR-005, en
    routeringscases in `golden_gesprek.jsonl`, 3× gemeten;
  - **F3d**: suggesties per object, en de artefacten/panelen `deelvraag` en `begrip`;
  - **F3e**: de werkgebiedpagina wordt raadplegen; de ongebruikte BFF-run-routes gaan eruit;
  - **F3f**: de intake met bepalingen per deelvraag en de twee fixes, met een meting op een **nieuwe**
    set.
- **Technisch risico.** De bestaande stromen zijn async; de LangGraph-nodes draaien synchroon. De
  agent draait op de event loop van de beurt. Stopvlag en runstore-sleutels blijven daarbij gelden.
  Een spike-test komt als eerste.
- **Later.**
  - Een toetsstap in de intake: een uitsluiting die de analysevraag tegenspreekt.
  - Een juridische verkenning: heffing op aangifte vs. aanslag, betalings- vs. aanslagtermijn, uit de
    graaf met bronnen.
  - De rest van de app in de lijststijl.

**Vervolg (open, eigen plan):**

- **Lex helpt de bronnen vinden** (nu uitgewerkt in F3) als de analist ze nog niet kent – nu valt dat buiten F0 (de
  bestaande bronnenrun en deelvragen staan klaar als volgende stap na het aanmaken).
- De rest van activiteit 1 uit de Leidraad: juridische scenario's met gebeurtenissen (1c) en die
  verbinden met de deelvragen (1e) – de controle die volgens de Handleiding de afbakening scherp maakt.
- **Minder en betere bronvoorstellen** (de volgende iteratie, volgens de gebruiker): de bronnenrun het
  dossier laten gebruiken – wat erbuiten valt weglaten zoals de intake dat al doet, zoeken met
  aanleiding en praktijkvoorbeeld – met een meting op de referentieset bronselectie ervoor en erna.
- Startactiviteit b (projecttypologie), c (hoofd- en deelactiviteiten) en d (het team): bewust nog niet
  (besloten 20 okt 2026); ze sturen vooral keuzes die het platform nog niet maakt.
- De doorstap naar activiteit 2 (annoteren) en 3 (begrippen) vanuit hetzelfde gesprek.

---

## Volgorde en samenhang

- **A** loopt los van de rest en is vooral werk voor beoordelaars. Het blokkeert alleen semantisch
  werk aan de annotatieketen, niet B, D of E.
- **B** is af; vervolgwerk aan de herkomst volgt de werkwijze en verificatie van dat spoor.
- **D** en **E** zijn onafhankelijk. D-levering 4 (Lex leest begrippen) en E-fase 3 (koppelen aan
  bepalingen) gebruiken allebei het projectie- en schrijfpad van de api. Ontwerp ze samen als ze
  tegelijk aan de orde komen.
- **C** eerst herijken. Een eventuele knowledge-check past het best bij D (ontdubbeling over een
  werkgebied).

## Open keuzes

1. **D — bediening**: *besloten 15 okt 2026* – Lex stelt voor (de Lex-gedreven stroom, zie
   *Leveringen en fasen*); zelf een begrip maken blijft mogelijk.
2. **D — toegang**: *besloten 14 okt 2026* – gedeelde werkgebieden, zoals de annotaties.
3. **D — kaders**: *besloten 15 okt 2026* – één begrippenkader per werkgebied, impliciet: geen eigen
   object, de IRI `urn:wa:kader:<werkgebied>` is afgeleid. Hergebruik tussen kaders komt later en
   vraagt dan wel een eigen object.
4. **D — deelvragen**: *besloten 19 okt 2026* – optioneel; Lex stelt ze voor uit de analysevraag. Zonder
   deelvragen werkt alles zoals daarvoor; de dekkingscheck per deelvraag verschijnt alleen als ze er zijn.
5. **D — SHACL bij accorderen**: *besloten 16 okt 2026* – diagnostisch, zoals bij de JAS-projectie:
   accorderen kan, kaart en export tonen of een begrip NL-SBB-conform is (zie ADR-003, fase F3).
6. **C**: blijft de leerlus een doel, en in welke vorm?
7. **A — scope**: horen relaties (operand, afleiding) en beleidsregels met rekenvoorbeelden bij
   activiteit 2? Zie het onderzoek §17, punten 7 en 9.
8. **A — Rechtsbetrekking zonder genoemde partijen** (jurist): telt een impliciete partij (de
   ontvanger, de belastingschuldige) voor een Rechtsbetrekking (H2:44: een relatie tussen twee
   rechtssubjecten), of is "Een belastingaanslag is invorderbaar …" een rechtsgevolg (Rechtsfeit)?
   Het model wijst de centrale norm hier af, de referentie (IW01, provisional) zegt Rechtsbetrekking.
   Na het oordeel wordt het een deterministische regel (klasse-invariant), met een meting – niet
   eerder, want anders legt de code een methodekeuze vast die nog open is.
9. **GraphDB-licentie**: de Free-sleutel volstaat voor de proeftuin. Voor gebruik in een
   organisatie moet Graphwise de licentievorm bevestigen; Enterprise geeft meer gelijktijdige
   queries, enterprise-authenticatie en clustering. Overstappen naar Jena/Fuseki is geen doel: dan
   vervallen de ingebouwde MCP-server, de Lucene-connector en de similarity-plugin waar graph-qa
   en de importer op leunen.
