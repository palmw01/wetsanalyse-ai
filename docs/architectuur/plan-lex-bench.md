# Plan: Lex Bench, een onafhankelijke kwaliteitslaag naast Lex

Soort: *plan* (16 nov 2026). **Er is nog niets gebouwd.** Bouwen gebeurt pas na akkoord van de gebruiker op dit plan en
op de open keuzes onderaan. Getoetst op master `01067e70`.

Lex Bench meet hoe goed Lex juridisch werk doet, naast Lex en buiten zijn code om. Hij begint klein, bij de
**bronselectie**, en groeit daarna naar annotaties, begrippen en afleidingsregels. Een onafhankelijk team van Claude
Code-agents analyseert dezelfde casus als Lex, eerst blind. Daarna worden de selecties vergeleken. Een mens stelt vast
wat juist is.

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

## 10. Open keuzes voor de gebruiker

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
