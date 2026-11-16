# Plan: Lex Bench, een onafhankelijke kwaliteitslaag naast Lex

Soort: *plan* (16 nov 2026). **Er is nog niets gebouwd.** Bouwen gebeurt pas na akkoord van de gebruiker op dit plan en
op de open keuzes onderaan. Getoetst op master `01067e70`.

Lex Bench meet hoe goed Lex juridisch werk doet, naast Lex en buiten zijn code om. Hij begint klein, bij de
**bronselectie**, en groeit daarna naar annotaties, begrippen en afleidingsregels. Een onafhankelijk team van Claude
Code-agents analyseert dezelfde casus als Lex, eerst blind. Daarna worden de selecties vergeleken. Een mens stelt vast
wat juist is.

Deel A (§1–§9) is de benchmark zelf. Deel B (§11–§15) brengt alle testsets over het gedrag van Lex terug tot één
geordende set per meetas, waar de benchmark uit leest, en beoordeelt de componenttests. Deel C (§16–§21) legt de lat voor het testen in alle lagen: een testpiramide, een
risicomatrix met de foutpaden, agentspecifiek testen, de kwaliteit van de tests en een traceerbaarheidsmatrix. De open
keuzes staan in §22.

# Deel A: de benchmark

## 1. Doel en grenzen

**Doel.** Per versie van Lex laten zien waar de bronselectie staat: wat Lex vindt, wat hij mist en wat hij ten onrechte
kiest, op twintig vaste casussen, met elke run herleidbaar naar code, image, zoekcode, model en graaf. Zo wordt een
verbetering zichtbaar of blijkt dat ze er niet is. Hetzelfde geldt voor een verslechtering.

**Grenzen.**

- **De score is een hulpmiddel, geen einddoel.** Er is geen drempel die een PR, een uitrol of een release tegenhoudt
  of doorlaat. De poort toetst alleen de vorm van de casussen, niet de score.
- **Geen automatische juridische goedkeuring.** Een verwachting is `concept` tot een mens haar vaststelt. Zolang dat niet
  is gebeurd, heten de cijfers een *trendmeting*, net als in het [meetlogboek](metingen/README.md). Het agententeam stelt
  voor, en de mens beslist.
- **Het team is geen gold.** Waar Lex en het team verschillen, kan het team ongelijk hebben. Daarom is er de categorie
  *team mist* (§5).
- **Eerlijk over de stand.** Elke run zegt hoeveel casussen vastgesteld zijn, hoeveel blind, en wat er nog niet gemeten
  wordt. Een stap die niet af is, staat als niet af.
- **Licht meten** ([meetregime](metingen/README.md)): één run, met akkoord, binnen een plafond. Meetbestanden zijn bewijs
  en worden achteraf niet gewijzigd.
- **Publieke repo.** Geen hostnamen, tokens of materiaal van derden. Casussen staan in eigen woorden, wettekst alleen als
  verwijzing (jci-uri of `urn:bwb:`-IRI). Personen zijn codes (`jur-01`), zoals in het
  [adjudicatieprotocol](../wetsanalyse/referentieset/adjudicatieprotocol.md).
- **Generiek.** Bench meet. Wat hij vindt, wordt opgelost in het algemene mechanisme, nooit met maatwerk voor één casus.
- **Acceptatie, nooit productie.** Op acceptatie verwijdert Bench niets: het account is gedeeld.

## 2. Wat er al is, en wat Bench ermee doet

Bench bouwt op wat er staat. Hij maakt geen tweede kopie van een set, een scorer of een team.

| Wat er is | Waar | Wat Bench ermee doet |
|---|---|---|
| De bronselectie-eval: `bepaling_opties` per deelvraag tegen de verwachte bepalingen, met recall, recall nodig, recall exact, precisie, uitgesloten en recall van de pool; offline tegen een opname van de graaf | `tools/graph-qa/eval/bronselectie_eval.py` (`--intake`, `--b2`, `--zoekvragen`, `--opnemen`, `--aanvullen`) | **Hergebruik.** Dit is de Lex-arm offline (§4, arm L1). De relatie `in_selectie` (gelijk, erbinnen of omvattend) en `recall_exact` blijven de definitie van een treffer. Bench voegt alleen de overlap en de driedeling toe (§5) |
| Het setschema 3: dossier, deelvragen, `verwacht[]` met `rol`, `zoekvraag`, `motivering` en `herkomst`, `buiten_graaf` en `uitgesloten[]` | `docs/wetsanalyse/referentieset-bronselectie/<set>/set.json` | **Hergebruik als basis.** Het casusschema (§3) is schema 3 plus een paar velden. Nieuwe ontwikkelcasussen komen in dezelfde map, zodat de eval ze zonder wijziging leest |
| Zes ontwikkelsets met opname: Termijnen, Rekeningafspraken, Bestuurdersaansprakelijkheid, Bezwaar/ontvankelijkheid, Invorderbaarheid (deelvragen), Kwijtschelding | idem, met `graafantwoorden.json` | **Opnemen als ontwikkelcasus**, door ernaar te wijzen vanuit het manifest (§3.3). Bench wijzigt de sets niet. Ze waren alle zes ooit blind en zijn door gebruik ontwikkelset geworden |
| `invorderbaarheid-concept` (schema 1, zonder deelvragen) | idem | Niet opnemen: geen deelvragen, dus niet vergelijkbaar met de rest |
| De held-out set Verrekening, voorgesteld als blinde set voor het plan Termijnen | `verrekening-concept/` en [het onderzoek Termijnen](onderzoek-bronselectie-termijnen-2026-11.md), stap 8 | **Niet opnemen en niet draaien.** Die set hoort bij een lopende sessie en wacht op akkoord. Daarna kan het manifest ernaar wijzen (open keuze 6). Bench raakt de vlaggen in `Zoekprofiel` en de stappen van dat plan niet |
| De zoekversie (`ZOEKVERSIE`, een hash over de zoekcode) | `tools/graph-qa/agent/bronnen_run.py` | **Hergebruik** in het runrecord (§6) |
| Het meetlogboek en de vaste mapvorm per meting | `docs/architectuur/metingen/` | **Hergebruik.** Elke Bench-run krijgt een eigen map en een regel in het logboek |
| De meetset en het meetscript van de centrale agent, met het plafond (`BUDGET_OP`) en het verbruik uit het `meting`-event | `tools/graph-qa/eval/golden_centrale_agent*.jsonl`, `eval/centrale_agent_meting.mjs` | **Hergebruik van het patroon** voor het plafond van de live arm (§7). Bench raakt die set en de lopende meting van F02 niet |
| De acceptatie-MCP: `lex_start`/`lex_wacht`, `bff`, `werkgebied_lezen`, `bron_lezen` (de officiële bron), `graaf_lezen` (alleen-lezen SPARQL), en het logboek dat alleen kan aanvullen | `tools/wetsanalyse-acceptatie-mcp/` | **Hergebruik.** Het team leest er de bron en de graaf mee. De live Lex-arm bedient er Lex mee |
| Het team agent-jurist en agent-gegevensspecialist, met de briefing en het scenario E2E | `.claude/agents/`, `docs/acceptatie/briefing-team.md`, `wetsanalyse-e2e.md` | **Voortbouwen, niet hergebruiken als blind team.** Die agents bedienen Lex en zien dus zijn voorstellen. Bench krijgt een eigen agent (§4.2) die de methode en de werkwijze met bronnen van de agent-jurist overneemt, maar de tools van Lex niet heeft |
| De juridische referentieset (JAS), de familiesplitsing en het adjudicatieprotocol (A en B onafhankelijk, C adjudiceert, het systeem is nooit annotator, codes in plaats van namen) | `docs/wetsanalyse/referentieset/`, `eval/adjudicatie.py`, `scripts/blind_formulier.py` | **Hergebruik van de werkwijze** voor de vaststelling (§4.3), en de set zelf in fase 2 (annotaties, §8) |
| De golden sets van annotaties en begrippen, met de scorers (ankerdekking, BCubed, `samengevoegd_verschillend`) | `eval/golden_annotatie*.jsonl`, `eval/begrippen_eval.py`, `docs/wetsanalyse/referentieset-begrippen/` | **Hergebruik** in fase 2 en 3 (§8) |
| ADR-010 (de kwaliteitsmeting: bewaarde runs die opnieuw te scoren zijn, deterministische scorers) en ADR-016 §A6 (meetset met plafond) | `docs/architectuur/adr-010-…`, `adr-016-…` | **Volgen.** Bench bewaart elke run zo dat hij gratis opnieuw te scoren is |

**Wat nieuw is:** het manifest met twintig casussen, niveau en gebruik; vijf blinde casussen met een hash in de repo en
de inhoud erbuiten; vier velden in het casusschema; een blind analistprofiel voor het team; de vergelijking in drie
categorieën met de overlap; het runrecord; een handmatige workflow; een los dashboard in de stijl van Lex (§6); en de ketentest vanaf fase 2.

## 3. De casus

### 3.1 Schema

Een casus is een set in schema 3, met in **schema 4** deze aanvullingen. Bestaande sets blijven schema 3. Wat Bench er
extra van wil weten, staat in het manifest.

- `casus_id`: vast en kort, bijvoorbeeld `LB-07`. Hij blijft gelijk over versies.
- `niveau`: `makkelijk`, `gemiddeld` of `moeilijk` (§3.2).
- `gebruik`: `ontwikkeling` of `blind`.
- `verwachting`: wie de verwachting opstelde en vaststelde.
  - `opgesteld_door`: de teamrun (`run_id`) en de codes van de analisten.
  - `vastgesteld_door`: de code van de jurist, of `null`.
  - `status`: `concept` of `vastgesteld`.
  - `datum`.
- Per verwachte bepaling, naast `bron_iri`, `rol` (`kern`, `afhankelijkheid`, `aanverwant`), `zoekvraag` (a–d),
  `motivering` en `herkomst`: het veld `nagekomen` (§5). Een bepaling die pas na de vergelijking is toegevoegd, telt
  apart. Zo blijft de score op de bevroren verwachting eerlijk.

Het dossier blijft zoals in schema 3: naam, aanleiding, doel, analysevraag, praktijkvoorbeeld, context, buiten,
gebeurtenis, regelingen (het zoekbereik) en deelvragen. Alles in eigen woorden. `uitgesloten[]` noemt bepalingen die er
in de buurt liggen maar niet horen, met een reden. `buiten_graaf` noemt wat nodig is maar niet in de graaf staat. Dat
telt niet in de noemer.

### 3.2 Niveau

Het niveau zegt waarom een casus moeilijk is, niet hoe goed Lex het doet. Het wordt vastgelegd **voordat** Lex erop
draait.

- **Makkelijk.** De kern staat in één regeling. De vraag gebruikt het woord van de wet. Hoogstens drie deelvragen, en
  weinig verwijzingen.
- **Gemiddeld.** De kern ligt verspreid over twee of meer regelingen, of één verwijzing moet gevolgd worden. Beleid (de
  Leidraad) en wet liggen naast elkaar.
- **Moeilijk.** Er is een woordenkloof (de vraag zegt het woord van de wet niet). Of de kern volgt uit een keten van
  verwijzingen, de gebeurtenis is breed (oorzaak O1 uit het onderzoek Termijnen), of een deel valt buiten de graaf.

Een voorlopige indeling van de zes bestaande sets, ter vaststelling: Termijnen en Kwijtschelding *moeilijk*;
Bestuurdersaansprakelijkheid, Bezwaar/ontvankelijkheid, Invorderbaarheid en Rekeningafspraken *gemiddeld*.

### 3.3 Manifest en versies

`docs/lex-bench/bronselectie/manifest.json` is de bron van waarheid voor de casusset.

- Per casus: `casus_id`, `niveau`, `gebruik`, `pad` (de setmap, voor ontwikkelcasussen) of alleen een `sha256` (voor
  blinde casussen), de status van de verwachting en de opname van de graaf.
- Een versie (`bench-bronselectie-v1`, …) met een hash over alle casussen, en een changelog. Een wijziging aan een casus
  is een nieuwe versie, en een vrijgegeven versie verandert niet (de regel van `eval/referentieset.py`).
- Een git-tag per vrijgegeven versie: `lex-bench/bronselectie-v1`.

## 4. Werkwijze: eerst blind, dan vergelijken

Per casus zijn er drie armen. De volgorde is vast.

### 4.1 Twintig casussen samenstellen

- **Zes bestaande ontwikkelsets**, door ernaar te wijzen (§2).
- **Negen nieuwe ontwikkelcasussen.**
- **Vijf nieuwe blinde casussen.**

De verdeling is ongeveer 6 makkelijk, 8 gemiddeld en 6 moeilijk, en onder de blinde 1, 2 en 2. De bestaande zes zijn
gemiddeld tot moeilijk, dus de nieuwe ontwikkelcasussen beginnen bij makkelijk.

De graaf heeft acht regelingen: AWR, Awb, Invorderingswet 1990, Awir, de Leidraad Invordering 2008, de Mijnbouwwet en
twee uitvoeringsregelingen. Alle bestaande sets gaan over invordering. Nieuwe casussen kiezen daarom bewust andere
onderwerpen: toeslagen (Awir), het bestuursrecht los van de belasting (Awb), de heffing (AWR) en het winstaandeel
(Mijnbouwwet). Een blinde casus kiest een onderwerp dat geen ontwikkelcasus heeft. In een graaf van acht regelingen kan
de stof elkaar wel overlappen; het rapport zegt dat.

Een casusdossier wordt geschreven door een **casusauteur** (open keuze 3). Dat is iemand die de code van de
bronselectie niet afstemt. Het dossier bevat geen verwachte bepalingen: die komen van het team.

### 4.2 Arm T: het team, blind

Een nieuw Claude Code-agentprofiel, `.claude/agents/bench-analist.md`, neemt de methode en de werkwijze met bronnen van
de agent-jurist over. Het is **blind door constructie**: het profiel krijgt een allowlist van tools in plaats van een
verbodslijst.

- **Wel:** `bron_lezen`, `graaf_lezen`, `logboek_aanvullen` en `logboek_lezen` van de acceptatie-MCP, en de skill
  wetsanalyse (de methode, met `references/zoekvragen-bronselectie.md` en `verwijzingen-volgen.md`).
- **Niet:** de tools waarmee je Lex bedient of zijn werk leest (`lex_*`, `bff`, `werkgebied_lezen`, `annotatie_lezen`,
  `weergave_lezen`, `begrip_lezen`). Ook geen bestanden uit de repo: anders leest het team de verwachting van een
  ontwikkelset of de code van Lex.

Per casus werken **twee analisten (A en B) los van elkaar**, zoals in het adjudicatieprotocol. Elk krijgt alleen het
dossier en levert per deelvraag een bronselectie in een vast formulier: bepaling, rol, zoekvraag, motivering, en per
bepaling het bewijs (de tekst bij de bron, opgehaald met `bron_lezen`). Daarna voegt een derde stap A en B samen: waar
ze het eens zijn, waar niet, met beide argumenten. Dat is de **teamverwachting** (`status: concept`).

De teamverwachting wordt **bevroren voordat iemand naar Lex kijkt**: als bestand in de meetmap met een hash in het
runrecord. Pas daarna draait of leest de Lex-arm.

### 4.3 Vaststelling door een mens

Een jurist (code `jur-xx`) leest de teamverwachting tegen de bron en stelt haar vast, past haar aan of laat haar staan,
met een reden. Het systeem is nooit annotator: de jurist ziet de voorstellen van Lex niet bij de vaststelling. Zolang er
geen jurist is, blijft de verwachting `concept` en de cijfers een trendmeting (open keuze 2).

### 4.4 Arm L: Lex

- **L1 offline, zonder model.** `bronselectie_eval --intake` op de casus, tegen de opname van de graaf. Dat kost 0
  tokens, is herhaalbaar en draait ook in een workflow (§6). Dit is de standaardarm.
- **L2 live op acceptatie, met akkoord.** Via de acceptatie-MCP wordt een werkgebied gemaakt met het dossier van de
  casus, en Lex doet de bronselectie per deelvraag. Bench leest wat Lex in het paneel voorstelt, maar neemt geen
  besluiten. L2 meet wat L1 niet ziet: de echte stand van de graaf en het echte gesprek. Een werkgebied krijgt de naam
  `Bench <casus_id> <run>`, en blijft staan, want op acceptatie wordt niets verwijderd.

**Wat telt als keuze van Lex:** de lijst per deelvraag die het paneel als voorstel toont, in de volgorde van de werkplek.
Dat is dezelfde lijst die `--intake` meet.

### 4.5 Blind houden

- **Buiten de repo.** De inhoud van een blinde casus staat niet in deze publieke repo. Het manifest legt per blinde casus
  alleen `casus_id`, `niveau`, de datum en een `sha256` over het bestand vast. Daarmee is achteraf te bewijzen dat de
  casus niet is aangepast. Waar de inhoud wel staat, is open keuze 1.
- **Niet in een prompt, niet bij het afstemmen.** Een sessie die zoekcode, prompts, skills of profielen wijzigt, krijgt
  geen toegang tot de blinde casussen. Alleen een validatierun opent ze, op een bevroren commit.
- **Een poorttest** (`tests/poort/test_lex_bench.py`) bewaakt de vorm: het manifest klopt, een blinde casus heeft geen
  `pad` in de repo, en geen bestand onder `tools/graph-qa/agent/`, `.claude/skills/` of `.claude/lex-agents/` noemt een
  `casus_id`. De inhoud van een blinde casus kan die test niet kennen. Het proces is de echte bescherming.
- **Eenmalig.** Een blinde casus wordt één keer gebruikt. Na de validatierun wordt ze ontwikkelcasus (zoals eerder met
  Kwijtschelding en Bestuurdersaansprakelijkheid), en komt er een nieuwe blinde voor in de plaats.
- **Wat blind niet doet.** Het voorkomt dat de code op de casus wordt afgestemd. Het maakt het model niet onwetend over
  de wet: het kan de wet uit zijn training kennen. Dat geldt voor Lex en het team allebei.

## 5. Scorekaart en het oordeel over een verschil

**Eenheid:** een bepaling op lidniveau, met de treffer van `in_selectie`. Heel artikel 8 omvat lid 1, maar telt niet als
exacte treffer (`recall_exact`).

Per casus, per niveau en over alles, en altijd **ontwikkeling en blind apart**:

- **Recall**: welk deel van de verwachte bepalingen Lex vindt. Er zijn twee varianten: *nodig* (kern en afhankelijkheid)
  en *alles* (ook aanverwant).
- **Precisie**: welk deel van de keuze van Lex in de verwachting staat.
- **Overlap**: de Jaccard-index tussen de keuze van Lex en de verwachting (∣L ∩ V∣ / ∣L ∪ V∣), en apart tussen Lex en de
  teamverwachting vóór de vaststelling. Zo zie je hoeveel de vaststelling verandert.
- **Ter diagnose** (geen hoofdmaat): recall van de pool (zoekt Lex verkeerd, of rangschikt hij verkeerd?), het aantal
  uitgesloten bepalingen in de keuze, en of de rol juist is.

Elke maat staat met de **aantallen** erbij (bijv. 7/12), niet alleen als fractie: op twintig casussen zegt een fractie
zonder noemer weinig. Er is geen totaalcijfer en geen drempel.

**Elk verschil krijgt een categorie.** Een reviewer (een agent met de bron, de motivering van beide kanten en de tekst)
stelt die voor. De jurist beslist:

- **Lex mist**: de bepaling staat in de verwachting, Lex noemt haar niet.
- **Lex onterecht**: Lex kiest een bepaling die er niet hoort, of die in `uitgesloten[]` staat.
- **Team mist**: Lex vond een bepaling die er wél hoort. Ze komt in de volgende versie van de casus met
  `nagekomen: true`. De score op de bevroren verwachting blijft zoals ze was; de score met de nagekomen bepalingen staat
  ernaast.
- **Twijfel**: er is geen uitspraak zonder de jurist. Dit staat open in het rapport en wordt niet weggestreept.

Per categorie noteert de reviewer de **plek waar het misgaat** als die zichtbaar is: niet in de pool, wel in de pool maar
laag gerangschikt, of een verkeerde rol. Dat is de brug naar een generieke fix.

## 6. Vaste runs en versies

**Het runrecord** (`run.json` in de meetmap) legt vast:

- de commit van master en de **image-digests** van graph-qa en api die op acceptatie draaien (het OCI-label
  `org.opencontainers.image.revision` moet bij die commit horen, zoals in `promote.yml`);
- de `ZOEKVERSIE`;
- het **modelprofiel en de model-id** van Lex (L2) en van het team;
- de **graaftoestand**: de datum van de import en de hash van de opname (L1);
- de versie en de hash van de casusset;
- de hash van de bevroren teamverwachting per casus;
- het verbruik per arm, en de plafonds.

**Opslag.** Elke run krijgt een map `docs/architectuur/metingen/lex-bench-<datum>-<naam>/` met het runrecord, de
rapporten per casus en een README met de uitkomst, plus een regel in het meetlogboek. Voor blinde casussen staan alleen
de scores en de categorieën in de repo, niet de bepalingen of het dossier.

**De voortgang** staat op één plek, `docs/lex-bench/README.md`: per meetas (bronselectie, annotaties, begrippen,
afleidingsregels) wat er is, hoeveel casussen vastgesteld zijn, de laatste run, en wat er nog niet is.

**Het dashboard.** Lex Bench krijgt een eigen, losse pagina, en wordt niet in Lex geïntegreerd (besluit van de
gebruiker, 16 nov 2026). Het is een statische HTML-pagina in `tools/lex-bench/`, met nette benchmarkgrafieken in de
stijl van Lex. Er is geen backend en geen koppeling met de app of de api.

- **Wat hij toont.** De scorekaart en het verloop per versie van Lex:
  - recall (nodig en alles), precisie en overlap, per casus en per niveau;
  - blind en ontwikkeling altijd apart, nooit in één lijn;
  - per run de versie uit het runrecord (commit, zoekversie, model);
  - de verdeling over *Lex mist*, *Lex onterecht*, *team mist* en *twijfel*;
  - hoeveel verwachtingen `vastgesteld` zijn.

  Boven elke grafiek staat de status (*trendmeting* zolang een verwachting `concept` is). Er is geen totaalcijfer en
  geen groen of rood oordeel.
- **Waar de gegevens vandaan komen.** Uit de vastgelegde runs in de repo: de `run.json` en de rapporten in de
  meetmappen. Een script (`eval/lex_bench.py --dashboard`) leest die mappen en schrijft één gegevensbestand
  `tools/lex-bench/data.js` (`window.LEX_BENCH = {…}`). De pagina laadt dat met een gewone `<script>`, zodat ze ook als
  lokaal bestand opent (`file://` mag geen JSON ophalen). Het dashboard leest de meetbestanden alleen en verandert
  ze nooit. Van blinde casussen bevat het alleen de scores en de categorieën.
- **De stijl van Lex:**
  - de tokens en kleuren uit `frontend/app/globals.css`: paper, surface, ink, lintblauw, muted, line, en succes, gold en
    fout voor de categorieën;
  - het lettertype Fira (Sans voor tekst, Mono voor cijfers), met een systeemlettertype als terugval zonder netwerk;
  - het beeldmerk uit `frontend/merk/` (`lex-merk.svg`), met *Bench* ernaast.

  De tokens worden overgenomen, niet geïmporteerd: de pagina hangt niet aan de build van de frontend. Een kleine test
  bewaakt dat de overgenomen waarden gelijk blijven aan `globals.css`, net als de drift-test van de JAS-kleuren.
- **De grafieken** zijn met de hand getekend in inline SVG, zonder externe bibliotheek. Zo werken ze zonder netwerk en
  als artifact. Elke grafiek heeft een tabel met de getallen ernaast of eronder.
- **Delen.** De pagina is lokaal te openen. Later kan ze als artifact gedeeld worden, maar alleen met de gegevens van de
  ontwikkelcasussen en de scores van de blinde.

**GitHub.**

- Een poorttest op de vorm (§4.5), zonder model en zonder score.
- Een workflow `lex-bench.yml`, alleen handmatig te starten (`workflow_dispatch`). Die draait arm L1 op de
  ontwikkelcasussen en hangt het rapport als artefact aan de run. Hij gebruikt geen model en geen geheimen, en blokkeert
  niets.
- Arm L2, de teamruns en de blinde validatie draaien vanuit een Claude Code-sessie, met akkoord van de gebruiker. Nooit
  automatisch, nooit op een schema.

## 7. Tokenbudget per run

De schattingen hieronder zijn voorlopig. De pilot (stap LB3) meet ze; daarna liggen de plafonds vast.

- **L1 offline:** 0 tokens.
- **L2 live:** de bronselectie per deelvraag is grotendeels code zonder model. Het E2E-verslag Rekeningafspraken noemt
  ongeveer 15k tokens context per besluit. We nemen in L2 geen besluiten, dus schatting ≤ 50k per casus. **Plafond 100k
  per casus en 1,5M per run van twintig**, met de stopregel uit het meetscript van de centrale agent (`BUDGET_OP`). Het
  verbruik komt uit `/api/account/verbruik` vóór en na (delta), zoals in de E2E.
- **Team (Claude Code, niet uit het budget van Lex):** per analist per casus schatting 100–200k, door het lezen van
  bronnen (`bron_lezen` kapt af op 40.000 tekens). **Plafond 250k per analist per casus.** Twee analisten, de
  samenvoeging en de review samen: ongeveer 0,5–0,7M per casus, en voor twintig casussen ruim 10M. Daarom draait het
  team één keer per casusversie, niet per versie van Lex. Lex verandert; de verwachting blijft staan.

## 8. Uitbreiding: annotaties, begrippen, afleidingsregels, en de ketentest

Elke fase komt pas als de vorige draait. Elke fase hergebruikt de scorer die er al is.

- **Fase 2, annotaties.** Op de bepalingen die de bronselectie van een casus vaststelde, annoteert het team blind in
  het formulier van het adjudicatieprotocol. Lex annoteert via de annotatieketen. Scoren gebeurt met de bestaande
  ankerdekking en klasse-overeenkomst (`eval/scoring.py`, `metrieken.py`), met dezelfde drie categorieën. De
  juridische referentieset (V7) blijft de plek voor vastgestelde JAS-casussen. Bench verwijst ernaar en kopieert niets.
- **Fase 3, begrippen.** Op de vastgestelde annotaties stelt het team begrippen en groepen voor. Scoren met de
  BCubed-maten en `samengevoegd_verschillend` uit `begrippen_eval.py`. Definities beoordeelt alleen een mens.
- **Fase 4, afleidingsregels.** Die horen nog niet tot de functionaliteit van Lex. Bench legt dan alleen het formulier
  vast, en meet pas als Lex ze maakt.

**De ketentest** laat zien waar een fout ontstaat. Elke stap k (bronnen → annotaties → begrippen → regels) draait twee
keer:

- op **de eigen invoer**: de uitvoer van Lex uit stap k−1;
- op **de vastgestelde invoer**: de verwachting van stap k−1.

Wat dat zegt:

- Faalt stap k al op de vastgestelde invoer, dan **ontstaat de fout in stap k**.
- Gaat stap k goed op de vastgestelde invoer en fout op de eigen invoer, dan is het **een fout uit de overdracht**: een
  gemiste bron in stap 1 wordt een gemiste annotatie in stap 2.
- Het verschil tussen beide scores is **het verlies door de overdracht** per stap. Het rapport toont dat als een rij per
  stap.

Dat vraagt per casus een vastgestelde verwachting voor elke stap. Daarom begint de ketentest bij de casussen die het
verst zijn, en niet bij alle twintig tegelijk.

## 9. Stappen

Elke stap is een eigen PR, en de hoofdsessie bundelt ze. Stappen met een model draaien pas na akkoord.

- **LB0 – dit plan.** Alleen docs.
- **LB1 – casusschema, manifest en scorekaart, zonder model.** Schema 4 en het manifest met de zes bestaande sets. Een
  script `eval/lex_bench.py` dat `bronselectie_eval` aanroept, de overlap en de categorieën toevoegt, en het rapport per
  niveau en gebruik schrijft. De poorttest. De eerste run van L1 op de zes, als nulpunt in het meetlogboek. 0 tokens.
- **LB2 – het team.** Het profiel `bench-analist` met de allowlist, het formulier, de briefing
  (`docs/lex-bench/briefing-analist.md`), de stap die A en B samenvoegt, en de reviewer. Nog geen run.
- **LB3 – pilot, met akkoord.** Drie nieuwe ontwikkelcasussen, één per niveau: team blind, vaststelling (of concept), L1,
  en L2 op één casus. Dit meet de tokens en toetst of het formulier werkt. Daarna liggen de plafonds van §7 vast.
- **LB4 – de overige zes ontwikkelcasussen**, en de teamverwachting voor de zes bestaande sets. Die geeft een tweede,
  onafhankelijke blik op hun verwachting, zonder de sets te wijzigen: verschillen gaan als voorstel naar hun eigenaar.
- **LB5 – vijf blinde casussen en de eerste validatierun**, op een bevroren commit. Daarna gaan ze naar ontwikkeling,
  en komen er vijf nieuwe blinde.
- **LB6 – het dashboard in `tools/lex-bench/`** (statisch, in de stijl van Lex, met de drift-test op de tokens), **de
  workflow `lex-bench.yml` en de voortgangspagina.** De eerste versie van het dashboard kan al na LB1 komen, op het
  nulpunt van de zes bestaande sets.
- **LB7 en verder – fase 2 tot en met 4 en de ketentest**, elk met een eigen plan.

# Deel B: één testset voor het gedrag van Lex

*Aanvulling van 16 nov 2026, op verzoek van de gebruiker.* Er zijn veel testsets, en ze zijn in losse sporen ontstaan.
De gebruiker wil één goede, geordende testset voor het gedrag van Lex, los van de componenttests, met de benchmark eraan
gekoppeld. Testsets die los rondzweven, vallen weg. Ook hier geldt: **er wordt niets gebouwd, verplaatst of verwijderd
zonder akkoord.** De sessies die nu aan de sets van de bronselectie en van de restpunten na A6 werken, behouden hun sets;
dit deel stelt alleen voor wat er later met hun akkoord gebeurt.

**Gedrag of component.** Een testset over het *gedrag* meet wat Lex de jurist oplevert: met een model of tegen de echte
graaf, met een verwachting die een mens kan beoordelen. Een *componenttest* toetst een stuk code met fakes, draait in
de poort, en is groen of rood. Bench gaat over het eerste. Het tweede blijft in `tests/`.

## 11. Inventaris

Getoetst op master `01067e70`. Het aantal is het aantal casussen of regels zonder commentaar. *Laatste gebruik* is de
laatste vermelding in het [meetlogboek](metingen/README.md), of de laatste commit als er geen vermelding is. Een
*eigenaar* is het spoor of de ADR waar de set bij hoort: er is geen set met een persoon als eigenaar. Geen enkele set
hieronder is door een jurist vastgesteld.

### 11.1 Bronselectie

- **`docs/wetsanalyse/referentieset-bronselectie/`**: zeven sets in schema 3 (Termijnen, Rekeningafspraken,
  Bestuurdersaansprakelijkheid, Bezwaar/ontvankelijkheid, Invorderbaarheid (deelvragen), Kwijtschelding en Verrekening),
  plus `invorderbaarheid-concept` in schema 1.
  - Doel: de bronselectie per deelvraag (`eval/bronselectie_eval.py`).
  - Eigenaar: spoor F/J en het plan Termijnen.
  - Laatste gebruik: 16 nov 2026.
  - Kwaliteit: 7–24 verwachte bepalingen per set, concept. Zes zijn ooit blind gemeten en sindsdien ontwikkelset. De
    held-out set Verrekening is nooit gedraaid, maar staat publiek. Offline herhaalbaar via de opnames.
  - Overlap: alle sets gaan over invordering. Invorderbaarheid staat er twee keer in, in schema 1 en schema 3.

### 11.2 Annotatie (JAS)

- **`docs/wetsanalyse/referentieset/v1/`**: 24 conceptgevallen in zes wetsfamilies, met een manifest en een hash.
  - Doel: de JAS-annotatieketen. Eigenaar: spoor A (V7).
  - Kwaliteit: alle 24 `provisional`, 0 `adjudicated`. Er is een familiesplitsing: BW6 en de Omgevingswet worden apart
    getoetst en mogen niet in een prompt. Er is een adjudicatieprotocol en een blind formulier, maar die zijn nooit met
    echte beoordelaars gebruikt.
- **`docs/wetsanalyse/referentieset/concept/`** (IW05, UBT01–07): voorstellen buiten `v1`, alleen voor diagnose.
- **`eval/golden_annotatie.jsonl`** (10) en **`golden_annotatie_concept.jsonl`** (14), met `eval/bronteksten.json` (19
  bronteksten).
  - Doel: de annotatie-harnas van `run_eval --annotatie`. Laatste gebruik: 21 okt 2026.
  - Overlap: deels met `referentieset/v1` (dezelfde invorderingsbepalingen); de omvang daarvan is niet nagegaan.
- **Het onderzoeksgereedschap van de annotatieketen**: `compare_pipelines`, `vergelijk_rapporten`, `kandidaat_eval`,
  `detector_audit`, `beslisstabiliteit`, `stabiliteit_analyse`, `fouttaxonomie`, `laagrapport` en `taal_benchmark`. Het
  hoort bij ADR-001, ADR-002 en het validatieplan V1–V6.
- **De bevroren invorderingsproef**: `invordering_proef`, `invordering_parallel`, `invordering_rapport`,
  `invordering_snapshotherstel`, `invordering_bronnen`, `onderzoek_invordering`, `baseline_proef` en
  `baseline_deelmeting`. Laatste commit 29 sep 2026. Dit was een eenmalige proef; de uitkomst staat in het meetlogboek.

### 11.3 Begrippen

- **`docs/wetsanalyse/referentieset-begrippen/`**: `v1`, `heldout-v1` en `heldout-v2`, elk met bronnen, cases en een
  manifest.
  - Doel: de begrippenketen (`begrippen_eval.py`, BCubed en `samengevoegd_verschillend`). Eigenaar: ADR-004.
  - Kwaliteit: provisional. De held-out sets zijn bedoeld voor één blinde meting; na gebruik zijn ze
    ontwikkelset, en nieuwe regels vragen een nieuwe held-out set.
- **`eval/betekenisonderzoek_casus.json`**: spoor M, laatste gebruik 28 okt 2026.
- **`eval/kaartacties_brondefinitie.json`** (*Zoek de brondefinitie*): spoor D fase E, laatste gebruik 16 okt 2026.
- **`eval/uitleg_eval.py`** (B1-uitleg): spoor I. Nooit gemeten: "kost geld", staat open in `PLAN.md`.

### 11.4 Antwoord en agentgedrag

- **`eval/golden.jsonl`** (22, de QA-set): bronnen, citaten, weigering en vraagtype (`run_eval`).
- **`golden_gesprek.jsonl`** (18): vervolgvragen.
- **`golden_duiding.jsonl`** (6), **`golden_duiding_partijen.jsonl`** (10) en **`golden_klasse_twijfel.jsonl`** (5):
  de methodesectie `duiding`. Laatste gebruik 13–14 nov 2026.
  - Samen heten deze sets in het meetlogboek *de kwaliteitsset*. Laatste gebruik 13 nov 2026, eigenaar ADR-010 Q0/Q1
    en het plan methodes scheiden.
- **`golden_routering.jsonl`** (50) en **`golden_routering_centraal.jsonl`** (17): de route per vraag. De routering is
  code zonder model, dus dit is in feite een componenttest; ze staan niet als meting in het logboek.
- **`golden_centrale_agent.jsonl`** (31, de agentset van M0/A6) met de varianten `_breed` (4), `_delegatie` (5) en
  `_vervolgc` (3), het meetscript (`centrale_agent_meting.mjs`, `_sets.py`, `_vat.py`), en `stukcontrole_set.py`.
  - Eigenaar: ADR-016 en het plan restpunten na A6. Er wordt nu op gemeten (F02).
  - Kwaliteit: de verwachting beschrijft het doel van ADR-016, niet een juridisch oordeel.
  - Overlap: de vier bestanden zijn één set in delen.
- **`docs/acceptatie/connectors-meting.md`** en **`kennisgroepen-meting.md`** (20 vragen): meetplannen met vragen en
  criteria vooraf. De vragen staan in Markdown, niet in een machineleesbare set. Laatste gebruik 14 nov 2026.

### 11.5 Keten

- **`docs/acceptatie/wetsanalyse-e2e.md`**, met de briefing, de twee teamagents en het verslag Rekeningafspraken (16 nov
  2026): de enige meting van begin tot eind. Het dossier staat lokaal (`docs/acceptatie/lokaal/`), niet in de repo.
- **`eval/extern_dossier.py`**: een bestaande wetsanalyse als referentie voor een E2E. Nooit in het meetlogboek.
- **`eval/keten_fixture.py`**: een vaste bronpassage met vastgelegde modelcalls, voor ketenmetingen.

### 11.6 Skill-evals

- **`.claude/skills/wetsanalyse/evals/`** (8) en **`wetsuitvoering/evals/`** (3): in de vorm van `claude plugin eval`.
  Ze toetsen de skill als Claude-skill, niet Lex, en `tests/test_skill_evals.py` bewaakt alleen hun vorm. Er is geen
  meting van in het logboek.

### 11.7 Componenttests die als meting begonnen

- **`tests/test_a4_vervolg.py`**, **`test_a6_*.py`** (acht bestanden), **`test_a7_ingang.py`**,
  **`test_b3_na_subagent.py`** en **`test_d01_*.py`** (zes bestanden): samen 17 bestanden en ongeveer 130 tests.
  - Elk bestand legt de gevallen uit één meting of bundel vast, met fakes, als regressie.
  - Het zijn componenttests, en goed dat ze er zijn. Maar ze heten naar een meetmoment (`run2`, `bundel123`), niet naar
    het gedrag dat ze bewaken.

### 11.8 Scripts en infrastructuur

- **`scripts/`** (`kruistests.sh`, `browsertests.mjs`, `pytest_shard.py`): infrastructuur van de poort, geen testsets.
- **`tools/graph-qa/scripts/`**: de generators van de afgeleide methodebestanden, met hun drift-tests; daarnaast
  `blind_formulier` en `render_jas_referentieset` voor de adjudicatie.
- **`eval/`**: daarnaast de gedeelde bouwstenen `scoring`, `metrieken`, `kwaliteit`, `opname`, `manifest`, `casusbron`,
  `criteria`, `referentieset`, `vraagtypen` en `retrieval_smoke`.

## 12. Doelstructuur: één set per meetas, één casusvorm

**Eén wortel**: `docs/lex-bench/`, met per meetas een map en een manifest.

```text
docs/lex-bench/
  README.md                  de voortgang per meetas (§6)
  casusvorm.md               het schema (één kop, een blok per meetas)
  bronselectie/manifest.json + <casus_id>/casus.json
  annotatie/manifest.json    + <casus_id>/casus.json (+ bronnen.json)
  begrippen/manifest.json    + …
  afleidingsregels/          gereserveerd
  antwoord/manifest.json     + …
  keten/manifest.json        + …
tools/lex-bench/             het dashboard (§6)
```

**Eén casusvorm.** Elke casus heeft dezelfde kop:

- `casus_id`, `meetas`, `versie`, `niveau` en `gebruik`;
- het dossier of de vraag, in eigen woorden;
- de bron als verwijzing (IRI met `bron_hash`);
- `verwachting` met opgesteld, vastgesteld en status;
- `herkomst`, als een casus uit een eerdere set komt;
- `tags`.

Daaronder staat één blok per meetas:

- bronselectie: `verwacht[]` en `uitgesloten[]` (schema 3);
- annotatie: de markeringen met anker en klasse (de vorm van `referentieset/v1`);
- begrippen: formuleringen en paren met relatie (de vorm van `referentieset-begrippen`);
- antwoord: wat er verwacht wordt (bronnen, sjabloon, weigering, route of subagents), in de vorm van de agentset;
- keten: een verwijzing naar casussen van de andere assen, plus de praktijkvoorbeelden als toetsgevallen.

Zo kan een keten-casus de bronselectie-, annotatie- en begrippen-casus van hetzelfde werkgebied aan elkaar rijgen. Dat
is wat de ketentest (§8) nodig heeft.

**Eén lader.** `eval/casusbron.py` wordt de enige ingang. Elke eval leest haar casussen via de lader, met een filter op
meetas, gebruik en status. De scorers blijven waar ze zijn (`bronselectie_eval`, `scoring`, `metrieken`,
`begrippen_eval`, `kwaliteit`, `centrale_agent_sets`); ze krijgen een casus in de nieuwe vorm.

**Blind gescheiden.** Dit werkt per meetas zoals in §4.5:

- blinde casussen staan buiten de repo;
- het manifest legt alleen hun hash en niveau vast;
- de lader weigert `gebruik: blind`, behalve in een validatierun met een runrecord;
- na gebruik wordt een blinde casus ontwikkeling.

De bestaande held-out sets (Verrekening, begrippen `heldout-v1` en `-v2`, de BW6- en Omgevingswet-families) staan
publiek. Ze kunnen in de nieuwe set alleen *ontwikkeling* zijn, of *blind voor het afstemmen*. Zo staat het er ook bij.

## 13. Opruimplan

**Eerst de regel voor bewijs.** De maps in `docs/architectuur/metingen/` blijven ongewijzigd: dat is de historie. Een
set waar een meting naar verwijst, blijft op zijn pad bevroren staan, met in zijn README *opgevolgd door
`docs/lex-bench/<meetas>/` (versie …)*. Verplaatsen zou de links in het bewijs breken. Er komen geen nieuwe versies meer
op het oude pad, dus er blijft één levende set.

| Wat | Wordt | Hoe |
|---|---|---|
| De sets onder `referentieset-bronselectie/` (behalve Verrekening) | **gaan op** in `lex-bench/bronselectie` | casus per set, met `herkomst`; het oude pad bevroren. Pas na akkoord van de sessie Termijnen |
| `verrekening-concept` | **beslist de sessie Termijnen** | open keuze 6 |
| `invorderbaarheid-concept` (schema 1) | **vervalt als levende set** | een dubbel van de versie met deelvragen; het bewijs blijft |
| `referentieset/v1` en `concept/` | **gaan op** in `lex-bench/annotatie` | de adjudicatie (spoor A, V7) loopt via de nieuwe set; `v1` blijft bevroren |
| `golden_annotatie*.jsonl` en `bronteksten.json` | **gaan op** in `lex-bench/annotatie` | na een vergelijking met `v1`: wat dubbel is, telt één keer |
| `referentieset-begrippen/*`, `betekenisonderzoek_casus.json`, `kaartacties_brondefinitie.json` | **gaan op** in `lex-bench/begrippen` | de held-out sets als ontwikkeling |
| `golden.jsonl`, `golden_gesprek`, `golden_duiding*` en `golden_klasse_twijfel` | **gaan op** in `lex-bench/antwoord` | één set met tags in plaats van vijf bestanden |
| `golden_centrale_agent*.jsonl`, `stukcontrole_set` | **gaan op** in `lex-bench/antwoord`, **na** de restpunten | nu niet aanraken: daar wordt op gemeten |
| De vragen in `connectors-meting.md` en `kennisgroepen-meting.md` | **gaan op** in `lex-bench/antwoord` | uit Markdown naar casussen; de meetplannen blijven als bewijs |
| `wetsanalyse-e2e.md`, de briefing en de teamagents | **blijven**, met de casussen in `lex-bench/keten` | het scenario is de werkwijze; de casus wordt het dossier in eigen woorden |
| `golden_routering*.jsonl` | **blijft componenttest** | de routering is code zonder model; `test_routering` draait er al op |
| `test_a4/a6/a7/b3/d01_*` | **blijft componenttest**, gegroepeerd naar gedrag (§14.2) | het oorspronkelijke geval komt ook als casus in `lex-bench/antwoord`, voor de meting met het echte model |
| De bevroren invorderingsproef (acht modules, sep 2026) | **vervalt als code** | na een controle dat geen test, workflow of script ze nog laadt; de uitkomst blijft in het meetlogboek |
| `taal_benchmark`, `detector_audit`, `extern_dossier` | **beslist de eigenaar** | eenmalig onderzoek of gereedschap voor later; open keuze 11 |
| Skill-evals | **blijven bij de skill** | ze toetsen de skill, niet Lex; in de inventaris van de voortgangspagina |
| `scripts/` en de generators | **blijven** | infrastructuur |
| `scoring`, `metrieken`, `kwaliteit`, `opname`, `manifest`, `casusbron` | **blijven**, als de scorers van Bench | — |

**De volgorde:**

1. eerst de lader en de casusvorm;
2. dan per meetas een PR die de casussen overzet, met een test die bewijst dat de scores op het nulpunt gelijk blijven
   (dezelfde casussen, dezelfde uitkomst);
3. pas daarna het oude pad bevriezen;
4. als laatste de code die vervalt weghalen.

## 14. De kwaliteit van de componenttests, voor zover ze het gedrag van Lex dekken

### 14.1 De volgordefout tussen `test_eval.py` en `test_sjablonen.py`

**Gereproduceerd.** Met `pytest -p no:randomly tests/test_eval.py tests/test_sjablonen.py` faalt
`test_sjablonen.py::test_een_beurt_rondt_af_met_de_wettekst_uit_de_graaf`. Los draait hij groen.

**De oorzaak.** De cache `agent/overzicht.py:_REGELINGEN_CACHE` is procesbreed ("één query per proces").
`test_eval.py::test_offline_eval_run_slaagt` vult hem met de Invorderingswet 1990. Leeg je alleen deze cache tussen de
twee tests, dan is de test weer groen.

De sessie graph-qa vond de diepere oorzaak (`testplan/graph-qa.md` §4.2): **de sjablonentest is alleen groen *omdat* de
cache leeg is.** De GOK-controle van `id_herkomst` herkent een regeling aan de namen uit dezelfde cache. Met een lege
cache laat hij een gegokt BWB-id door. Met de Invorderingswet in de cache weigert hij het, zoals in productie, en dan
is het script van het model op. De test beschrijft dus een beurt die productie weigert. Alleen de cache resetten zou de
test groen houden om de verkeerde reden. Hij moet ook herschreven worden: de vraag noemt de regeling, of de nepgraaf
beantwoordt `list_regelingen` zoals de echte graaf.

**Waarom alleen soms in de poort.** Er is geen willekeurige volgorde (`pytest-randomly` is niet geïnstalleerd), maar de
shards verdelen per bestand op gewicht. Of beide bestanden in dezelfde shard en in deze volgorde landen, hangt dus af
van de indeling.

**Voorstellen:**

- Een autouse-fixture in `tests/conftest.py` die de procesbrede toestand na elke test leegmaakt:
  `overzicht._REGELINGEN_CACHE`, `regelingnamen._CACHE` en `_AFKORTINGEN`, `graph/schema._cache`, en de stand van de
  modelkeuze. Herschrijf daarna de sjablonentest (zie hierboven). Twaalf testbestanden
  doen dat nu elk met de hand.
- Een test die het register van die caches bewaakt, zodat een nieuwe procesbrede cache er ook in moet.
- Een regressietest die beide tests in deze volgorde draait.
- Een vaste extra run van graph-qa in omgekeerde bestandsvolgorde (één job, `-p` met een eigen kleine plugin), om de
  volgende lekken van dit soort te vinden.
- De `FakeLLM` faalt bij een extra ronde nu met een kale `IndexError`. Laat hem zeggen wat er gebeurde: "de keten vroeg
  ronde 3, gescript waren er 2", met de laatste waarschuwing erbij. Dan is de oorzaak in één oogopslag te zien.

### 14.2 Tests die naar een meetmoment heten

De 17 bestanden uit §11.7 bewaken echt gedrag: delegatie, citaten, de controle per uitspraak, hervatten. Maar wie wil
weten welke test de delegatie bewaakt, moet de bundelnummers kennen. Daarnaast toetsen ze vaak de letterlijke zin uit
één meting, en dan neigt een fix naar maatwerk per geval.

**Voorstel:**

- Groepeer ze naar gedrag (`test_delegatie.py`, `test_citaten_uitspraak.py`, `test_stukcontrole.py`,
  `test_hervatten.py`, …), met de herkomst als commentaar.
- Maak waar het kan van één letterlijk geval een eigenschap over varianten (de vorm die `conftest` al gebruikt voor het
  denkproces).

Dat is verplaatsen, geen inhoudelijke wijziging. Elke test blijft bestaan.

### 14.3 Tests die alleen een vorm vastleggen

- **Drift-tests**: `test_methode_drift`, `test_methodepakket`, `test_vocabulaire_drift`, `test_namespace_drift`,
  `test_contract_drift`, `test_deploy_drift`, `test_begrippen_manifest_drift` en de profiel- en bronpakkettests.
- **Vormtests van sets**: `test_golden_centrale_agent`, `test_golden_annotatie` en `test_skill_evals`.

Dat is nodig. Maar het is geen dekking van gedrag, en het telt in de inventaris apart als *vorm*.

### 14.4 Tests die altijd groen zijn of nooit draaien

- 39 testbestanden hebben een `skip` of `skipif`.
- Zeven bestanden hangen aan een live omgeving (`BRONNEN_LIVE`, `GRAPHDB_MCP_URL`). Die worden in de poort
  overgeslagen en draaien alleen in `bronnenwacht.yml`.

**Voorstellen:**

- Laat de poort per suite het aantal overgeslagen tests met de reden afdrukken.
- Maak een lijst van elke skip met de plek waar hij wél draait. Een skip die nergens draait, is een test die niet
  bestaat.

**Altijd groen** is zonder meting niet hard te maken. Voorstel: een proef met mutatietesten (`mutmut`) op twee modules
die het gedrag van de bronselectie dragen, `agent/bronnen_vinden.py` en `agent/deelvraag_zoeken.py`, lokaal en eenmalig.
Een mutant die blijft leven, wijst een test aan die niets bewaakt, of een hiaat.

### 14.5 Hiaten

- **Fakes tonen het modelgedrag niet.** De componenttests met `FakeLLM` bewijzen wat de code doet met een gegeven
  modelantwoord. Wat het model werkelijk antwoordt, toont alleen een meting. Dat is de taak van Bench, en geen gat in de
  tests.
- **De overdracht tussen de stappen is niet getest op echte gegevens.** Dat de annotatie werkt op wat de bronselectie
  echt oplevert, en de begrippen op de annotatie, is per stap met fakes getoetst, maar niet in samenhang. Dat dekt de
  ketentest (§8).
- **Een gemeten casus zonder regressie in de poort.** De blinde metingen van de bronselectie staan als offline
  regressie in `test_bronselectie_eval.py`. Voor de begrippen, de annotatie en de kwaliteitsset bestaat zo'n regressie
  op de opgenomen runs niet. Voorstel: per meetas één regressietest op een bewaarde opname (gratis herscoren, ADR-010),
  zodat een scorerwijziging de oude uitkomst niet stil verandert.

## 15. Stappen voor deel B

Na deel A's LB1. Elke stap is een eigen PR, en de hoofdsessie bundelt.

- **LB-B1 – de volgordefout (§14.1).** Klein en los. Dit kan eerder, als de gebruiker dat wil (open keuze 12).
- **LB-B2 – de lader en de casusvorm**, met de bronselectie als eerste meetas: deel A's LB1 schrijft al naar deze vorm.
- **LB-B3 – het overzetten per meetas**, met de gelijkheidstest op het nulpunt. De volgorde: begrippen, annotatie,
  antwoord (na de restpunten), keten.
- **LB-B4 – opruimen**: oude paden bevriezen en de vervallen code weghalen.
- **LB-B5 – de componenttests**: groeperen (§14.2), de skips afdrukken (§14.4), de regressies op opnames (§14.5), en
  daarna de proef met mutatietesten.

# Deel C: de lat voor het testen van Lex

*Aanvulling van 16 nov 2026, op verzoek van de gebruiker.* Een professionele tester van agentische platforms moet bij
het lezen denken: dit is in alle lagen goed doordacht. Dat vraagt goede testgevallen en scenario's, het goede pad én
de foutpaden, en een dekking die per risico te meten is. Dit deel legt die lat vast.

De nulmeting per laag (§20) wordt in vier parallelle sessies opgesteld, in `docs/architectuur/testplan/`: graph-qa;
api met bronmodel en de importer; de werkplek; keten en E2E. Hun bevindingen komen hier samen. Dit deel bepaalt
waartegen ze meten. Er wordt niets gebouwd zonder akkoord.

## 16. Een testpiramide per laag

Elke laag zegt wat ze dekt en wat **bewust niet**. Wat een laag bewust laat liggen, moet een andere laag dekken. Dat
staat in de risicomatrix (§17).

| Laag | Dekt | Bewust niet | Waar het staat | Draait |
|---|---|---|---|---|
| **1. Unit en component** | logica per module met deterministische nepdiensten (`FakeLLM`, `FakeGraph`, de api met Postgres in een container, vitest); elk foutpad dat in één component te veroorzaken is | wat een echt model doet; samenwerking tussen diensten | `*/tests/`, `frontend/**/*.test.ts(x)`, `packages/bronmodel` | poort, elke PR |
| **2. Contract en kruistests** | dat twee kanten hetzelfde verwachten: routes, schema's, events, de BFF-proxy, de afgeleide methodebestanden (drift) | gedrag achter het contract | `tests/poort/`, `scripts/kruistests.sh`, de drift-tests | poort, elke PR die code raakt |
| **3. Keten en integratie** | graph-qa ↔ api ↔ werkplek en de MCP's samen, met nep alleen aan de rand (model, graaf of overheid.nl): een beurt van begin tot eind, met storingen ertussen | inhoudelijke juistheid | browserregressie (Playwright met mocks), de rooktest na uitrol (`/api/health?keten=1`); **grotendeels nog te bouwen** | poort (mocks), na elke uitrol (rook) |
| **4. E2E-scenario's** | een echte wetsanalyse op acceptatie, via de acceptatie-MCP, met de agent-jurist en de agent-gegevensspecialist: of het platform de methode draagt, en waar het hapert | een herhaalbare score; elk foutpad | `docs/acceptatie/` | handmatig, met akkoord |
| **5. Gedrag en kwaliteit** | wat Lex juridisch oplevert, tegen een vastgestelde verwachting, per meetas; spreiding over runs; regressie na een wijziging aan een prompt of skill | goedkeuring (die is van de mens); componentfouten | Lex Bench (deel A en B) | handmatig of per workflow, met akkoord |

**De vorm van de piramide.** Onderaan veel, snel en deterministisch; bovenaan weinig, duur en met een mens erbij. Een
foutpad hoort zo laag mogelijk getest te worden. Een storing van de graaf is een componenttest (laag 1). Of de
melding de jurist bereikt, is een ketentest (laag 3). Of Lex daarna eerlijk antwoordt in plaats van te verzinnen, is
gedrag (laag 5).

## 17. Risicomatrix en foutpaden

Elk risico heeft:

- een id;
- een impact (hoog, middel of laag);
- de laag die het **primair** vangt, en de laag die het als tweede vangt.

Het foutpad is wat er moet gebeuren: de verwachte afloop, niet alleen "geen crash". Hieronder staat het voorstel. De
nulmeting vult per risico in wat er nu is.

| Id | Risico | Impact | Verwachte afloop | Primair | Tweede |
|---|---|---|---|---|---|
| R01 | **De graaf is weg** (lege repository na een herstart, `Repository inning doesn't exist`) | hoog | Lex zegt wat er speelt en verzint niets; de graafwacht herstelt; het paneel *Graaf weg* toont het | 1 | 3 |
| R02 | **De api geeft een 5xx of is onbereikbaar** | hoog | de beurt faalt met een melding; niets half opgeslagen; opnieuw proberen kan | 1 | 3 |
| R03 | **Een time-out**: model, graaf, connector of api | hoog | een begrensde wachttijd, de beurt stopt netjes, het denkproces zegt waar | 1 | 3 |
| R04 | **Een 400 van het model**, en de strict-grens (een schema dat de API weigert) | hoog | geen stille terugval; een duidelijke fout; het schema is in de poort al getoetst | 1 | 2 |
| R05 | **Het budget is op** (429 bij de start, het plafond in een run) | middel | geen beurt, een heldere melding, geen half werk; meetscripts stoppen met `BUDGET_OP` | 1 | 3 |
| R06 | **Ongeldige invoer**: een verkeerde IRI, een artikelnummer met een dubbele punt, een lege vraag, te groot, verkeerd schema | middel | een 4xx met reden, of een vraag terug; nooit een 500 | 1 | 2 |
| R07 | **Gelijktijdigheid en 412's**: twee juristen op dezelfde laag, een verouderde revisie, twee runs in één gesprek (409) | hoog | de tweede schrijver krijgt een 412 of 409 en niets gaat verloren; de werkplek laat het zien en biedt verversen aan | 1 | 3 |
| R08 | **Afbreken en hervatten**: stoppen midden in een beurt, een herladen pagina, een hervatte subagent | middel | de stand blijft kloppen, er is geen dubbel werk, en het denkproces klopt na hervatten | 1 | 3 |
| R09 | **Een subagent rondt niet af** (rapport `niet_gelukt`, geen rapport, de grens van het aantal rondes bereikt) | hoog | de centrale agent meldt het en verzint geen uitkomst; de vraag gaat naar boven als dat zo hoort | 1 | 5 |
| R10 | **Lege of afgekapte resultaten** (0 treffers, een bepaling zonder eigen tekst, afkapping op 40.000 tekens) | hoog | "niet gevonden" is iets anders dan "bestaat niet"; afkappen wordt gezegd; geen conclusie uit een half resultaat | 1 | 5 |
| R11 | **Verouderde bronnen**: een andere wetsversie, een veranderde dragende passage, een opname die niet meer klopt | hoog | de peildatum is zichtbaar; de herbeoordeling toont toen en nu; een meting op een oude opname zegt dat | 1 | 5 |
| R12 | **Rechten en identiteit**: `X-User-Id`, rol analist of beheerder, gesprekken per gebruiker, het admin-token, 2FA voor beheer | hoog | geen toegang tot andermans gesprek; beheer dicht zonder 2FA; een vervalste header werkt niet buiten de BFF | 1 | 3 |
| R13 | **Prompt-injectie via de inhoud van een bron** (wettekst, een uitspraak of een kamerstuk met een instructie erin) | hoog | de inhoud is gegevens, geen opdracht; de toollaag en de prompt scheiden dat; de agent voert niets uit wat de bron vraagt | 1 | 5 |
| R14 | **Een connector staat uit of is onbekend** | middel | Lex zegt dat de bron niet beschikbaar is en valt niet stil terug op iets anders; het register in de beheertab klopt met wat graph-qa ziet | 1 | 2 |
| R15 | **Brongetrouwheid**: een citaat dat niet letterlijk is, een verkeerd anker, een vindplaats die niet klopt | hoog | de verificatie en het citaat worden gecontroleerd; *ongegrond* wordt gezegd | 1 | 5 |
| R16 | **De verkeerde route, het verkeerde profiel of de verkeerde tools** | middel | de ingang en de centrale agent kiezen zoals de agentset verwacht; verboden tools komen nergens voor | 2 | 5 |
| R17 | **Methodes vermengd** (JRM-taal of JAS-markeringen in de verkeerde methode) | middel | `test_methodes_gescheiden`; de skill-evals | 2 | 5 |
| R18 | **Een uitrol die niet draait** (de revisie crasht, een verkeerde digest, een ontbrekend secret) | hoog | de gate wacht en faalt; de rooktest op de keten | 3 | — |

Een risico kan in de nulmeting gesplitst worden, of er kan er een bij komen. De matrix wordt dan aangepast, met een
reden. Een risico mag niet stil wegvallen.

## 18. Agentspecifiek testen

Wat een agentisch platform extra vraagt, met per punt de laag en wat er al is:

- **De keuze van het profiel en de tools.** De agentset (`golden_centrale_agent`: `route`, `profielen`,
  `tools_verplicht` en `tools_verboden`) is de juiste vorm. Lat: elke route en elk profiel komt minstens één keer voor in
  de set, en elke verboden tool is getoetst (laag 2 op de vorm, laag 5 op het echte model).
- **De grenzen.** Het aantal rondes per beurt en per subagent, de tokens per beurt en per run, de afkapgrenzen. Lat:
  elke grens heeft een componenttest op *precies op de grens* en *er één over* (laag 1), en een meting die zegt hoe
  vaak de grens in de praktijk geraakt wordt (laag 5).
- **Grounding en brongetrouwheid.** Elk citaat is letterlijk in de bron, en een uitspraak zonder bron heet zo (R15).
  Lat: elk sjabloon heeft een test met een citaat dat er *net niet* in staat (laag 1), en elke meting rapporteert
  faithfulness en het aantal letterlijke citaten (laag 5).
- **Het denkproces klopt.** De regels zijn heel (`narratie.STRIKT` in elke test) en zeggen wat er gebeurde, ook bij een
  fout, een weigering en hervatten. Lat: per foutpad uit §17 een test op de regel die de jurist dan ziet (laag 1 en 3).
- **Stabiliteit over runs.** Een modelstap geeft per run een ander antwoord: het aandeel geel in de annotatie van
  dezelfde bepaling wisselt sterk tussen runs (`eval/stabiliteit_analyse.py`, `beslisstabiliteit.py`). Lat: waar een beslissing van één run afhangt, wordt met **3 of meer runs** gemeten, en het
  rapport toont de spreiding (minimum, maximum, en hoeveel runs het eens zijn), niet alleen het gemiddelde. Een casus
  die tussen runs wisselt, krijgt het label *instabiel* op het dashboard.
- **Regressie bij elke wijziging aan een prompt of skill.**
  - Een wijziging aan een skill of profiel verandert `bronpakket.json`; aan de modeltekst `prompts.py` of de
    methodemarkers (ADR-010, P19).
  - Lat: zo'n PR noemt een Bench-run met die hash, op de geraakte meetas (de lichte vorm: één run, gerichte set). De
    poort kan toetsen *dat* er een run is, niet *wat* de score is. De score blijft een hulpmiddel. Of de poort dat
    afdwingt, is open keuze 14.

## 19. De kwaliteit van de tests zelf

De lat, met per punt hoe het meetbaar wordt:

- **Geen test die altijd groen is.** Gemeten met mutatietesten op de modules die een risico uit §17 dragen (een proef
  in §14.4). Een mutant die blijft leven, krijgt een test of een reden.
- **Geen test die alleen een vorm vastlegt en voor gedrag doorgaat.** Elke test krijgt een soort: *gedrag*, *foutpad*,
  *contract* of *vorm*. Alleen de eerste twee tellen als dekking van een risico.
- **Onafhankelijk van de volgorde.** Een vaste job in omgekeerde volgorde en één met een vaste willekeurige volgorde.
  Procesbrede caches worden per test geleegd (§14.1).
- **Deterministische nepdiensten.**
  - Een nepmodel of nepgraaf antwoordt op wat er gevraagd wordt, niet op de volgorde waarin het gevraagd wordt, waar
    dat kan.
  - Een onverwachte vraag faalt met een duidelijke melding, niet met een `IndexError`.
  - Geen klok, geen netwerk en geen willekeur zonder een vaste waarde.
- **Geen overgeslagen test zonder een plek waar hij wél draait.** De poort drukt per suite het aantal overgeslagen tests
  en de reden af (§14.4).
- **Wisselvallige tests worden geteld, niet stil herhaald.** Een test die bij herhaling soms faalt, komt op een lijst met
  een eigenaar en wordt opgelost of verwijderd.
- **Dekking per risico, niet alleen per regel.** De regeldekking (coverage) wordt wel gemeten, maar de maat is §17: per
  risico, per laag, of er een test op het foutpad is die rood wordt als het foutpad breekt.

## 20. Nulmeting per laag

*Samengevoegd op 16 nov 2026* uit vier parallelle sessies, elk met een eigen document en een eigen PR (alleen docs).
Elk document bevat de inventaris, de risicomatrix van zijn laag, de kwaliteit van de tests en de voorstellen op
prioriteit. Hieronder staan de stand per laag, de dekking per risico uit §17 en de gaten die samen het zwaarst wegen.

| Laag | Detail | PR |
|---|---|---|
| graph-qa | `docs/architectuur/testplan/graph-qa.md` | #1640 |
| api, bronmodel en importer | `docs/architectuur/testplan/api.md` | #1636 |
| de werkplek | `docs/architectuur/testplan/werkplek.md` | #1638 |
| keten en E2E | `docs/architectuur/testplan/keten-e2e.md` | #1635 |

### 20.1 De stand per laag

- **Laag 1, graph-qa.**
  - De omvang: 267 bestanden, 3.179 testfuncties (6.394 met parametrisering), zonder netwerk en zonder model, 3–7 min
    in de poort.
  - Het meeste toetst gedrag, via de echte LangGraph met een gescript model.
  - De foutpaden zijn goed gedekt *waar ze ooit misgingen*: de graaf weg, een api-5xx, afbreken, hervatten, een subagent
    zonder rapport, afkappen, een connector uit, de rondegrenzen.
  - Dun of geen: een time-out van de graaf of een connector, een beurt waarin de API een strict schema weigert, en
    **prompt-injectie via de inhoud van een bron** (geen enkele test).
  - De nepdiensten zijn te toegeeflijk: `FakeGraph(result=…)` geeft op elke query hetzelfde antwoord, en `FakeLLM` toetst
    niet of een tool was aangeboden.
  - 21 bestanden (164 tests) heten naar een meting of bundel.
- **Laag 1, api, met bronmodel en de importer.**
  - De omvang: 84 bestanden en ±1.100 testfuncties in de api, op Postgres in drie shards, plus 218 tests in de importer.
    `bronmodel` heeft geen eigen testmap.
  - Sterk: echte races op Postgres voor annotaties, begrippen, werkgebieden en beheerders, de migratietest en de
    wislijst-guard.
  - Zwak:
    - de projectie is **nooit tegen een echte GraphDB** getest (alleen rdflib);
    - de PDF-tests slaan in CI altijd over;
    - gelijktijdigheid bij bronselectie per deelvraag, deelvragen, delegaties, werkplaats en verbruik is alleen op SQLite
      getest, en dat bewijst geen slot;
    - er is **geen rechtentabel** over de 232 routes;
    - de twee SPARQL-injectietests zijn altijd groen;
    - één mutatie heeft geen test (`parkeren`).
- **Laag 1, de werkplek.**
  - De omvang: ±1.100 logica-tests en ~82 tests van BFF en auth in vitest, ~140 vormtests, en 46 browserscripts. In 50
    poortruns faalde niets.
  - Sterk: de beurt en de SSE-stroom op logicaniveau.
  - Zwak:
    - er zijn **geen componenttests** (geen DOM in vitest), en `useBeurt` en `useOnbewaardBewaker` hebben geen eigen test;
    - de mocks hebben geen contract op hun vorm, en 29 van de 46 scripts beantwoorden een onbekend pad stil met 200;
    - de `sse()`-mock lijkt niet op de echte stroom, dus breken en hervatten wordt nooit in de browser getoetst;
    - één browserscript draait nergens;
    - de eigenaarscontrole bij het starten van een run, de allowlist van de annotatie-catch-all, de `jwt`-callback en
      `lib/trace.ts` hebben geen test.
- **Laag 2, contract en kruistests.** Statisch goed: het routecontract, de kruistests en een dertigtal guards maken
  drift rood, ook als alleen de andere kant wijzigt. Het contract bewaakt pad en methode, **niet de vorm** van het
  antwoord, en geen query-parameters.
- **Laag 3, keten en integratie.** **Er is geen dynamische ketentest.** Geen enkele test laat in CI een beurt lopen van
  browser via BFF, api en graph-qa naar GraphDB en terug. De rooktest na een uitrol raakt GraphDB en het model niet.
- **Laag 4, E2E.** Eén waardevolle run (Rekeningafspraken: 13 bevindingen, 3 hoog), maar als handwerk, op een gedeeld
  beheerdersaccount en zonder verwachting per stap. Ze is niet afgemaakt: DV2–DV5, de logs, de browser en de rechten van
  een analist zijn niet getest.
- **Laag 5, gedrag en kwaliteit.**
  - **Geen enkele set is door een jurist vastgesteld.** Geen set in `eval/` is blind.
  - De held-out uitkomsten van de bronselectie zijn als pin in de unitsuite vastgelegd (`test_bronselectie_eval`). Wie
    de code afstemt, ziet ze dus rood worden, en zo zijn ze niet meer blind bij het afstemmen.
  - De overdracht tussen de stappen wordt nergens gemeten: de evals per stap gebruiken andere casussen.
  - Spreiding over runs wordt alleen live gemeten, en alleen door de agentset.

### 20.2 Dekking per risico

*Goed*: het foutpad is getoetst waar het optreedt, met het randgeval. *Deels*: een deel, of alleen op SQLite of rdflib.
*Geen*: geen test. *—*: niet van toepassing op die laag. Kolom L1 noemt per component (g = graph-qa, a = api,
w = werkplek) de dekking op het foutpad.

| Id | Risico | L1 | L2 | L3 keten | L4 E2E | L5 |
|---|---|---|---|---|---|---|
| R01 | graaf weg | g goed · a deels | — | geen (K1) | niet gedaan | — |
| R02 | api 5xx | g goed · w BFF goed, browser deels | — | geen | — | — |
| R03 | time-out | g model dun, graaf en connector geen · a resolver deels · w BFF goed | — | geen (K6) | — | — |
| R04 | model-400, strict-grens | g 400 goed, strict deels | strict statisch goed | geen (K3) | — | — |
| R05 | budget op | g deels · w logica goed, browser geen | — | geen (K5) | niet gedaan | plafond in de meetscripts |
| R06 | ongeldige invoer | a domeinregels goed, schema niet systematisch | — | — | — | — |
| R07 | gelijktijdigheid, 409/412 | a goed voor 4 domeinen, zwak (SQLite) voor 5 · w 412 goed, 409 bij start geen | — | geen (K4, K7) | twee keer misgegaan | — |
| R08 | afbreken en hervatten | g goed · w logica goed, browser geen | — | geen (K2) | — | — |
| R09 | subagent rondt niet af | g goed | — | geen (K2) | — | — |
| R10 | leeg of afgekapt | g goed (resultaatcontract) | — | — | — | — |
| R11 | verouderde bronnen | a bronstand-409 goed | — | geen | — | opnames zonder versiecontrole |
| R12 | rechten en identiteit | a deels, geen rechtentabel · w deels (`jwt`, eigenaarscontrole geen) | — | geen (K8, K10) | analist niet getest | — |
| R13 | injectie via een bron | g geen · a SPARQL altijd groen | — | geen | — | geen kanarie in de bron |
| R14 | connector uit of onbekend | g goed · w goed | register goed | uitval tijdens een beurt geen (K6) | — | — |
| R15 | brongetrouwheid | g goed op het mechanisme | — | — | handmatig | geen vastgestelde verwachting |
| R16 | route, profiel en tools | — | routeringssets goed | — | — | agentset, live |
| R17 | methodes vermengd | — | `test_methodes_gescheiden` goed | — | — | — |
| R18 | uitrol draait niet | — | — | rooktest deels (geen graaf of model) | rollback nooit geoefend | — |

Uit de vier lagen kwamen risico's die §17 niet had. Ze komen erbij:

| Id | Risico | Impact | Primair | Tweede | Nu |
|---|---|---|---|---|---|
| R19 | **Een gedeeld account**: verbruik en besluiten van twee sessies door elkaar, een bulkactie die andermans werk raakt | hoog | 3 | 4 | geen; twee keer misgegaan in nov 2026 (K4) |
| R20 | **De projectie in de graaf wijkt af van Postgres** | hoog | 1 (echte GraphDB) | 3 | deels: alleen rdflib |
| R21 | **Een nepdienst die niet op de echte dienst lijkt** (vorm van een antwoord, de SSE-framing, één antwoord op elke query) | hoog | 2 | 1 | geen: de oorzaak van de volgordefout en van eerdere stille fouten |
| R22 | **Toegankelijkheid en touch** | middel | 1 (browser) | 4 | deels: axe op 8 van 46 schermen, geen `Tab`, geen touch |
| R23 | **Een controle die fail-open is** (de GOK-controle van `id_herkomst` staat uit met een lege namenlijst, bijvoorbeeld vlak na een herstart van GraphDB) | middel | 1 | — | geen; een vraag aan de eigenaar van `id_herkomst` |

**De telling bij de nulmeting**, over de 23 risico's op hun primaire laag:

- 9 goed: R02, R08, R09, R10, R14, R16 en R17, en op laag 1 ook R01 en R04 (voor graph-qa);
- 9 deels: R03, R05, R06, R07, R11, R12, R15, R18 en R20;
- 5 geen: R13, R19, R21, R22 (alleen deels in de browser) en R23.

Voor de **tweede laag** is het beeld scherper: voor geen enkel risico bestaat een dynamische ketentest (laag 3).

### 20.3 De gaten die het zwaarst wegen, over de lagen heen

1. **Geen dynamische ketentest** (laag 3). Elke laag mockt de buren, dus een fout in de samenwerking ziet pas de jurist.
   Voorstel uit keten-E2E: een diepere rooktest zonder model, en een naadtoets in de poort op één vaste minicasus.
2. **Prompt-injectie via de inhoud van een bron** (R13). Er is geen test in graph-qa, en de SPARQL-injectietests van de
   api zijn altijd groen.
3. **Nepdiensten zonder contract** (R21). Zo ontstond de volgordefout. De nep-api's in de browser beantwoorden een
   onbekend pad met 200, en de SSE-mock wijkt af van de echte stroom.
4. **Rechten niet als geheel getoetst** (R12). Er is geen rechtentabel in de api, de eigenaarscontrole van een run en de
   `jwt`-callback hebben geen test, en een analist is nooit end-to-end getest.
5. **Sloten die alleen op SQLite getoetst zijn** (R07). Daaronder valt de bronselectie per deelvraag, precies wat Lex
   Bench meet.
6. **De projectie nooit tegen GraphDB** (R20).
7. **Geen vastgestelde verwachting en geen blinde set** (laag 5). De pinnen op de held-out uitkomst staan in de
   unitsuite.
8. **Componenttests ontbreken in de werkplek.**
9. **De E2E is handwerk op een gedeeld account** (R19). Er is geen vast testaccount en geen eigen ruimte op acceptatie.
10. **Flakiness wordt niet gemeten.** Er zijn geen herhaalde pogingen, maar ook geen telling.

### 20.4 Wat dit voor de rest van het plan betekent

- **§4.5 en §13: de pinnen op de held-out uitkomst** gaan uit `test_bronselectie_eval` naar het rapport van Bench. De
  test houdt het pad zonder model en de vorm. Daarmee wordt een held-out set weer blind voor wie afstemt (open keuze 17).
- **§12: antwoord en agentgedrag zijn twee assen**, die niet tot één score worden opgeteld:
  - *antwoord*: `golden`, `golden_duiding*` en `golden_klasse_twijfel`, één set met `vraagtype`;
  - *agentgedrag*: de vier `golden_centrale_agent*`-sets en `golden_gesprek`, één set met groepen en met de spreiding
    over runs.

  `stukcontrole_set` en de route en de argumenten van de connectorvragensets (`tests/data/`) blijven een test. De
  live-ronde van de connectorvragen kan een as *connectors* worden.
- **§4.4 en arm L2:** Bench leest de voorstellijst per deelvraag uit de api. Zonder een contract op de volgorde van die
  lijst (api V8) en zonder races op Postgres voor de bronselectie (api V4), kan een meetverschil uit de api komen in
  plaats van uit Lex. Die twee gaan vóór de pilot LB3.
- **§8, de ketentest:** keten-E2E §3 werkt hem uit per naad:
  - werkgebied → bronselectie → annotatie → begrippen → graaf → export;
  - met een keten-casusformaat dat schema 4 uitbreidt (bronnen, annotaties en begrippen op dezelfde IRI's);
  - met een deterministische adapter per naad;
  - en met een naadtoets zonder model in de poort.

  De api kan de keten selectie → werkvoorraad → batch → inventaris → begrip → export zonder model trekken.
- **§14.1, de volgordefout:** graph-qa vond de diepere oorzaak; zie daar.
- **§21, de matrix:** keten-E2E stelt dezelfde matrix voor. Er komt er één, uit markers in de code, zoals §21 zegt.

### 20.5 De volgorde van de verbeteringen

Elke laag heeft zijn voorstellen op prioriteit in zijn eigen document. Over de lagen heen stelt dit plan deze volgorde
voor, met eerst alles zonder model:

1. **Nu, klein:**
   - de cachereset en een herschreven sjablonentest (graph-qa P0-1);
   - de eigenaarscontrole van `run/route.ts` en `server-only` in `lib/config.ts` (werkplek 1 en 5);
   - `pdftotext` op de runner (api V2);
   - het losse browserscript weer in `test:browser` (werkplek 3).
2. **De nepdiensten streng** (R21):
   - een strengere `FakeLLM` (graph-qa P0-4);
   - een strikte nep-api als standaard (werkplek 2);
   - een gedeelde `sse()` die in delen schrijft met `\r\n` (werkplek 4).
3. **De zware risico's:**
   - de injectietest via de bron (graph-qa P0-3) en echte SPARQL-injectietests (api V5);
   - de rechtentabel (api V3);
   - races op Postgres (api V4);
   - de projectie tegen GraphDB (api V1).
4. **Bench klaarmaken:**
   - het contract op de volgorde van de voorstellijst (api V8);
   - de pinnen van de held-out sets naar Bench;
   - de risicomarkers en de matrix (§21).
5. **De keten:**
   - een diepere rooktest en de naadtoets (keten 1 en 2);
   - een vast testaccount (keten 3);
   - de foutpaden K1–K10 als scenario's (keten 5).
6. **Herschrijven zonder gedragswijziging:**
   - groeperen per mechanisme (graph-qa P1-6);
   - één `conftest` in de api (V7);
   - componenttests met een DOM in de werkplek (werkplek 6).

## 21. Traceerbaarheidsmatrix

Van eis of risico, naar testgeval, naar laag, naar de laatste uitkomst.

- **De bron is de code zelf, niet een spreadsheet.** Een test noemt het risico dat hij dekt:
  - in pytest met `@pytest.mark.risico("R07")`;
  - in vitest met `[R07]` in de testnaam;
  - in een Bench-casus en in een E2E-scenario met `tags: ["R07"]`.

  Een eis (bijvoorbeeld "werk alleen met letterlijk opgehaalde wettekst" uit `CLAUDE.md`) krijgt een id `E01` en wordt
  naar zijn risico's verwezen.
- **Het register** `docs/lex-bench/risico's.json` bevat de risico's en eisen uit §17, met impact en de primaire en
  tweede laag.
- **Een script** (`eval/lex_bench.py --matrix`) verzamelt de markers (via `pytest --collect-only` en een
  vitest-lijst), de casussen en de laatste uitkomsten. Die komen uit de JUnit-rapporten van de poort, de laatste
  Bench-run en het laatste E2E-verslag. Het schrijft één `matrix.json`.
- **Een poorttest** bewaakt dat elk risico met impact *hoog* minstens één test van de soort *foutpad* op zijn primaire
  laag heeft, of een reden waarom niet (`bewust_niet`). Hij toetst de dekking, niet de uitkomst.
- **Het dashboard** (§6) toont de matrix: risico's als rijen, lagen als kolommen, en per cel het aantal tests en de
  laatste uitkomst (groen, rood, niet gedraaid of niet gedekt), met een klik naar de testnamen. Dezelfde pagina toont de
  nulmeting en het verloop: hoeveel risico's gedekt waren bij de nulmeting en hoeveel nu.

## 22. Open keuzes voor de gebruiker

1. **Waar staan de blinde casussen?** Voorstel: in een **privé GitHub-repo** (versiebeheer, toegang per persoon), met
   alleen de hash in deze repo. Alternatief: lokaal in een gitignored map, zoals `docs/acceptatie/lokaal/`. Dat is
   eenvoudiger, maar dan bestaat er geen gedeelde versie.
2. **Wie stelt de verwachting vast?** Een jurist met een code, de gebruiker zelf, of voorlopig niemand. In dat laatste
   geval blijft alles concept en heet elke uitkomst een trendmeting.
3. **Wie schrijft de nieuwe casusdossiers?** De gebruiker of een jurist (het beste voor blind), of een aparte
   Claude-sessie die de bronselectie niet afstemt. Mogen dossiers uit de lokale E2E-map dienen als ruwe grondstof, in
   eigen woorden herschreven?
4. **Twee analisten per casus, of één met een reviewer?** Twee is onafhankelijker en kost ongeveer twee keer zoveel.
   Voorstel: twee voor blind en moeilijk, één voor makkelijk.
5. **Arm L2 (live op acceptatie): ja of nee, en vanaf welke stap?** Voorstel: alleen in de pilot op één casus en bij de
   blinde validatie, en verder L1.
6. **De set Verrekening:** opnemen als blinde casus zodra de sessie Termijnen er klaar mee is, of bij dat plan laten?
   Ze staat al publiek in de repo, dus ze is alleen blind voor het afstemmen, niet voor de lezer.
7. **Akkoord op LB1** (zonder model, 0 tokens), en later apart op de pilot LB3 met de plafonds uit §7.
8. **Waar staat de ene testset?** Voorstel: `docs/lex-bench/<meetas>/`, met de oude paden bevroren als historie.
   Alternatief: de bestaande map `docs/wetsanalyse/` als wortel houden, zodat er minder verhuist.
9. **Hoort de routering bij de componenttests** (voorstel, want het is code zonder model), of als meetas bij
   *antwoord*?
10. **Mag de bevroren invorderingsproef (acht modules uit sep 2026) als code vervallen,** na de controle dat niets ze
    nog laadt? De uitkomst blijft in het meetlogboek.
11. **`taal_benchmark`, `detector_audit` en `extern_dossier`: bewaren of laten vervallen?**
12. **Mag de fix van de volgordefout (§14.1) nu al als losse kleine PR,** vóór de rest? Het is een fix aan de tests,
    zonder model.
13. **De componenttests groeperen naar gedrag (§14.2): ja of nee?** Het is veel verplaatsen voor ongeveer 130 tests, en
    elke open PR die ze raakt, krijgt een conflict.
14. **Moet de poort bij een wijziging aan een prompt, skill of profiel eisen dat er een Bench-run is (§18)?** Dat toetst
    dat er gemeten is, niet de score. Het alternatief is een waarschuwing in de PR.
15. **Moeten de risicomarkers en de dekkingstoets (§21) bindend zijn voor impact *hoog*,** of eerst alleen zichtbaar op
    het dashboard tot de nulmeting af is?
16. **Mogen de risico's R01–R23 (§17 en §20.2) de basis zijn,** of wil je er risico's bij of af?
17. **Mogen de pinnen op de held-out uitkomst uit `test_bronselectie_eval` naar het rapport van Bench (§20.4)?** De test
    houdt dan alleen het pad zonder model en de vorm.
18. **Mag de volgorde van de verbeteringen in §20.5 gelden,** met stap 1 (klein, zonder model) als eerste bouwopdracht?
19. **Wie neemt de vraag over de GOK-controle (R23) aan?** Die controle is fail-open bij een lege namenlijst. Dat is een
    vraag over de code, niet over de tests.
