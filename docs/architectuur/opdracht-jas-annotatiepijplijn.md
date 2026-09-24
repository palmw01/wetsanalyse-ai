# Opdracht: herontwerp en implementeer de JAS-annotatiepijplijn van wetsanalyse-ai

Je werkt in de repository:

`palmw01/wetsanalyse-ai`

Je opdracht is een fundamentele kwaliteitsverbetering van de JAS-annotatiearchitectuur.

Dit is nadrukkelijk **geen opdracht om de bestaande annotatieprompt langer te maken** en ook niet om zonder noodzaak meer agents toe te voegen.

Het doel is een annotatiesysteem te bouwen dat:

1. zo volledig mogelijk JAS-elementen vindt;
2. zo correct mogelijk classificeert;
3. bij dezelfde invoer zo reproduceerbaar mogelijk dezelfde uitkomst geeft;
4. juridisch en technisch uitlegbaar is;
5. iedere beslissing kan herleiden tot bron, regel, detector, modelcall en menselijke review;
6. zo veel mogelijk gebruikmaakt van deterministische software;
7. het LLM alleen gebruikt waar echte semantische of juridische taalinterpretatie noodzakelijk blijft;
8. kleine, afgebakende prompts gebruikt;
9. systematisch geëvalueerd kan worden;
10. stapsgewijs via afzonderlijke, reviewbare Pull Requests kan worden ingevoerd.

Voer deze opdracht grondig uit. Kies geen eenvoudiger oplossing alleen omdat die sneller te implementeren is.

---

# 1. Normatieve basis: JAS

Gebruik de officieel gepubliceerde specificatie:

**Wetsanalyse met het juridisch analyseschema 1.0.10**

als inhoudelijke grondslag voor JAS.

Controleer tijdens de repositoryanalyse of het project bewust van een andere JAS-versie uitgaat. Indien dit zo is, documenteer het verschil voordat je gedrag wijzigt.

De JAS-specificatie is leidend voor:

* betekenis van de klassen;
* herkenningsvragen;
* uitdrukkingswijzen;
* onderlinge samenhang;
* specialisatieregels;
* onderscheid tussen klassen.

Maak geen eigen alternatieve definitie van een JAS-klasse.

## Belangrijk methodisch uitgangspunt

JAS beschrijft per klasse herkenningsvragen die vergelijkbaar zijn met vragen uit grammaticale zinsontleding en beschrijft daarnaast hoe zulke elementen in wetgeving kunnen worden uitgedrukt.

Vertaal dit expliciet naar de architectuur.

Dat betekent:

> grammatica, syntaxis, lexicale patronen en juridische formuleringen worden gebruikt om kandidaten te vinden.

Maar:

> een grammaticaal of lexicaal signaal is niet automatisch bewijs dat de betreffende JAS-klasse juridisch van toepassing is.

Maak altijd onderscheid tussen:

```text
detectiesignaal
→ kandidaat
→ juridische classificatie
```

---

# 2. JAS-dekking

De oplossing moet expliciete dekking hebben voor alle JAS-elementgroepen uit de officiële specificatie:

1. Rechtssubject
2. Rechtsobject
3. Rechtsbetrekking
4. Rechtsfeit
5. Voorwaarde
6. Afleidingsregel
7. Variabele en Variabelewaarde
8. Parameter en Parameterwaarde
9. Operator
10. Tijdsaanduiding
11. Plaatsaanduiding
12. Delegatiebevoegdheid en Delegatie-invulling
13. Brondefinitie

Let erop dat sommige paragrafen meerdere afzonderlijke begrippen bevatten, zoals:

* Variabele / Variabelewaarde;
* Parameter / Parameterwaarde;
* Delegatiebevoegdheid / Delegatie-invulling.

Controleer de bestaande interne JAS-taxonomie van de repository en maak de mapping naar de officiële specificatie expliciet.

---

# 3. Vertaal de officiële JAS-herkenningsvragen naar detectiestrategieën

Maak voor iedere JAS-klasse een formeel detectieprofiel.

Neem daarin minimaal op:

```yaml
jas_class:
official_definition:
official_recognition_intent:
official_expression_patterns:
syntactic_signals:
lexical_signals:
semantic_signals:
structural_signals:
candidate_rules:
confusable_classes:
negative_patterns:
required_context:
deterministic_detection_possible:
llm_needed_for:
test_cases:
```

Gebruik de officiële herkenningsvragen inhoudelijk als uitgangspunt.

Samengevat moeten de detectoren onder andere kunnen zoeken naar:

### Rechtssubject

Wie draagt een recht of plicht, bezit een object of hoort bij een waarde?

### Rechtsobject

Waarop heeft het recht of de plicht betrekking, of waarop heeft een waarde betrekking?

### Rechtsbetrekking

Welke juridische verhouding bestaat tussen rechtssubjecten?

### Rechtsfeit

Welke gebeurtenis, handeling of welk tijdsverloop verandert een juridische toestand?

### Voorwaarde

Aan welke eisen of omstandigheden moet zijn voldaan?

### Afleidingsregel

Hoe wordt een waarde, conclusie, rechtssubject of rechtsobject berekend of afgeleid?

### Variabele / Variabelewaarde

Welke veranderlijke eigenschap wordt beschreven en welke concrete waarde kan die hebben?

### Parameter / Parameterwaarde

Welke waarde is voor alle gevallen gedurende een bepaalde periode constant?

### Operator

Welke berekening, vergelijking of logische verbinding wordt toegepast?

### Tijdsaanduiding

Wanneer geldt of gebeurt iets, vanaf wanneer, tot wanneer of gedurende welke periode?

### Plaatsaanduiding

Voor welke plaats of welk gebied geldt de regel?

### Delegatiebevoegdheid / Delegatie-invulling

Wordt opdracht of bevoegdheid gegeven nadere regels te stellen, of wordt zo'n bevoegdheid in lagere regelgeving ingevuld?

### Brondefinitie

Wordt een term expliciet in de regelgeving omschreven?

Gebruik voor implementatiedetails steeds de volledige officiële specificatie en niet alleen bovenstaande samenvatting.

---

# 4. Hoofdprincipe van de architectuur

Gebruik bij iedere ontwerpbeslissing deze beslisregel:

> Kan deze taak betrouwbaar worden opgelost met bronstructuur, grammatica, syntaxis, deterministische regels, dictionaries, juridische patronen, bestaande RDF-kennis of andere vaste software?

Zo ja:

**doe het zonder LLM.**

Zo nee:

**reduceer de resterende vraag tot de kleinst mogelijke LLM-beslissing.**

De gewenste architectuur is dus niet:

```text
wettekst
→ grote prompt
→ volledige annotaties
→ criticus
```

maar:

```text
wettekst
↓
bronstructuur
↓
linguïstische analyse
↓
deterministische JAS-detectoren
↓
candidate generation
↓
candidate fusion
↓
kleine semantische classificatie
↓
deterministische validatie
↓
coverage- en conflictanalyse
↓
gerichte review van alleen twijfelgevallen
↓
resolver
↓
menselijke review
↓
persistente JAS-annotatie
↓
RDF / GraphDB-projectie
```

---

# 5. Analyseer eerst de bestaande repository

Voordat je gedrag wijzigt, inspecteer de actuele repository volledig.

Onderzoek minimaal:

* annotatie-agent;
* huidige annotatieprompt(s);
* Critic;
* supervisor/orchestrator;
* LangGraph- of andere workflow;
* tools;
* GraphDB;
* SPARQL;
* Postgres;
* annotation layer contract;
* bronreferenties;
* spanmodel;
* grounding;
* tool execution trace;
* provenance;
* review lifecycle;
* statusvelden;
* `verouderd`-logica;
* bronhash/lidhash;
* JAS-ontologie;
* SKOS;
* PROV-O;
* Web Annotation;
* ELI;
* GraphDB-projectie;
* API-contracten;
* frontend;
* tests;
* evaluaties;
* fixtures;
* documentatie;
* bestaande methode- en promptversies.

Neem niets uit deze opdracht als bewijs dat iets ontbreekt.

Controleer eerst daadwerkelijk de code.

---

# 6. Maak vóór implementatie een GAP-analyse

Lever eerst een document op met:

```text
CURRENT STATE
TARGET STATE
JAS GAP ANALYSIS
ARCHITECTURAL GAP ANALYSIS
MIGRATION RISKS
EVALUATION BASELINE
PR ROADMAP
```

Maak daarnaast een matrix:

| JAS-klasse | huidige detectie | LLM-verantwoordelijkheid | deterministisch mogelijk | grammaticale signalen | juridische patronen | resterende semantiek | tests | risico false negative | risico false positive | voorstel |
| ---------- | ---------------- | ------------------------ | ------------------------ | --------------------- | ------------------- | -------------------- | ----- | --------------------- | --------------------- | -------- |

Deze matrix moet alle JAS-klassen omvatten.

---

# 7. Canoniek bron- en tekstmodel

Voordat classificatie plaatsvindt, moet iedere analyse werken op één canonieke representatie van de brontekst.

Leg minimaal vast:

```text
source_id
BWB-id
JCI/bronreferentie
bronversie
artikel
lid
onderdeel
tekst
start_offset
end_offset
bronhash
lid_hash
```

De originele brontekst is leidend.

Een LLM mag spans niet onnodig opnieuw genereren.

Gebruik kandidaat-ID's die naar canonieke offsets verwijzen.

Bijvoorbeeld:

```text
candidate_id = C017
start = 128
end = 146
text = "binnen zes weken"
```

De modeluitvoer verwijst vervolgens naar `C017`.

---

# 8. Linguïstische analyselaag

Bouw een modelonafhankelijke linguïstische analyselaag.

Onderzoek voor Nederlandse wetsteksten geschikte technieken en implementaties voor:

* tokenisatie;
* zinssegmentatie;
* lemma's;
* part-of-speech;
* morfologie;
* dependency parsing;
* constituenten of clause detection waar nuttig;
* naamwoordgroepen;
* werkwoordgroepen;
* hoofd- en bijzinnen;
* coördinatie;
* negatie;
* modaliteit;
* tijdsexpressies;
* numerieke expressies;
* juridische verwijzingen;
* eventueel named entities waar nuttig.

Geef sterke voorkeur aan expliciete en gestandaardiseerde representaties, bijvoorbeeld Universal Dependencies, wanneer die voor de gekozen Nederlandse NLP-stack bruikbaar zijn.

Gebruik niet blind de eerste beschikbare NLP-bibliotheek.

Vergelijk serieuze kandidaten op:

```text
kwaliteit op Nederlandse juridische taal
determinisme
stabiliteit
snelheid
onderhoud
licentie
lokale uitvoerbaarheid
modelomvang
Python/API-integratie
```

Maak de provider verwisselbaar.

Bijvoorbeeld:

```python
class LinguisticAnalysis:
    sentences
    tokens
    lemmas
    pos
    morphology
    dependencies
    clauses
    noun_phrases
    verb_phrases
    temporal_expressions
    numeric_expressions
    references
```

JAS-logica mag niet direct afhankelijk worden van één specifieke NLP-leverancier.

---

# 9. Deterministische kandidaatdetectie

Bouw detectoren die **mogelijke** JAS-spans vinden.

Een detector maakt nog geen definitieve juridische annotatie.

Voorbeelden van detectorfamilies:

```text
subject detector
object detector
noun phrase detector
normative verb detector
legal relation detector
event/action detector
conditional clause detector
comparison detector
calculation detector
temporal detector
location detector
numeric/value detector
definition detector
delegation detector
reference detector
enumeration detector
negation detector
coordination detector
```

Iedere detector produceert bewijs.

Bijvoorbeeld:

```json
{
  "candidate_id": "C017",
  "span": {
    "start": 128,
    "end": 146,
    "text": "binnen zes weken"
  },
  "possible_classes": [
    "Tijdsaanduiding"
  ],
  "evidence": [
    {
      "detector": "temporal_expression",
      "rule": "BINNEN_DURATION"
    },
    {
      "detector": "dependency",
      "relation": "obl"
    }
  ]
}
```

---

# 10. Recall heeft voorrang in candidate generation

Het doel van candidate generation is:

> relevante elementen zo min mogelijk missen.

Optimaliseer deze laag daarom primair voor recall.

False positives mogen in een volgende stap worden weggefilterd.

Maar gebruik geen triviale strategie waarbij elk token of ieder willekeurig zinsdeel kandidaat wordt.

Meet kandidaatkwaliteit expliciet.

---

# 11. Candidate fusion

Meerdere detectoren kunnen dezelfde of gedeeltelijk overlappende span vinden.

Bouw één volledig deterministische fusion-laag die:

* identieke kandidaten dedupliceert;
* bewijs combineert;
* overlap registreert;
* nesting behoudt wanneer JAS dat vereist;
* verschillende kandidaatklassen bewaart;
* nooit bronoffsets stilzwijgend verandert.

Voorbeeld:

```json
{
  "candidate_id": "C017",
  "span": "binnen zes weken",
  "possible_classes": [
    "Tijdsaanduiding",
    "Voorwaarde"
  ],
  "evidence": [
    "TEMPORAL_DURATION",
    "PREPOSITIONAL_PHRASE",
    "RULE_BINNEN_DURATION"
  ]
}
```

---

# 12. Respecteer JAS-specificiteitsregels

JAS kent gevallen waarin een formulering meerdere algemene interpretaties zou kunnen krijgen maar een specifiekere JAS-klasse voorrang heeft.

Implementeer zulke regels expliciet wanneer ze normatief uit JAS volgen.

Voorbeeld:

een tijdsaanduiding kan conceptueel tevens als variabele of parameter worden gezien, maar JAS kiest in zo'n geval de specifiekere klasse Tijdsaanduiding.

Hetzelfde principe geldt bij Plaatsaanduiding.

Stop dergelijke regels niet alleen in een prompt.

Maak ze:

```text
expliciet
versioneerbaar
testbaar
traceerbaar naar JAS
```

---

# 13. LLM-classificatie

De standaardprompt mag niet meer luiden:

> Analyseer deze wettelijke bepaling volledig en geef alle JAS-elementen.

Het model ontvangt alleen kandidaten die uit de eerdere pipeline zijn gekomen.

Bijvoorbeeld:

```text
Candidate: C017

Span:
"binnen zes weken"

Context:
"..."

Evidence:
- temporal duration
- syntactic modifier
- pattern BINNEN_DURATION

Allowed decisions:
- Tijdsaanduiding
- Voorwaarde
- Geen annotatie
```

Output:

```json
{
  "candidate_id": "C017",
  "decision": "Tijdsaanduiding"
}
```

Gebruik:

* structured output;
* JSON/schema validation;
* enumeraties;
* vaste candidate IDs;
* minimale vrije tekst.

Het model mag geen nieuwe JAS-klassen bedenken.

---

# 14. Prompts moeten klein blijven

Prompts zijn geen opslagplaats voor alle domeinkennis.

Plaats stabiele kennis waar mogelijk in:

```text
code
regels
schema's
RDF
SKOS
configuratie
retrieval
tests
```

Modelprompts bevatten alleen informatie die nodig is om de huidige beperkte beslissing te nemen.

Voorkom duplicatie van dezelfde JAS-regels in tientallen prompts.

---

# 15. Onderzoek classifier-granulariteit

Onderzoek empirisch welke vorm het meest betrouwbaar is:

### optie A

één kleine universele JAS-classifier;

### optie B

kleine classifier per familie, bijvoorbeeld:

```text
rechtssubject/rechtsobject
rechtsbetrekking/rechtsfeit
voorwaarde/operator
variabele/parameter
tijd/plaats
delegatie
brondefinitie
afleidingsregel
```

Kies op basis van meetbare resultaten.

Maak hiervoor geen afzonderlijke agents wanneer gewone functies/modelcalls volstaan.

---

# 16. Beperk het aantal agents

Gebruik niet automatisch een multi-agentarchitectuur.

Voorkeursmodel:

```text
1 orchestrator
+
deterministische pipeline
+
beperkte classifier
+
optionele reviewer
```

Een nieuwe agent is alleen gerechtvaardigd als:

1. de taak niet betrouwbaar deterministisch kan;
2. een bestaande classifier de taak niet goed kan uitvoeren;
3. evaluatie laat zien dat de extra agent aantoonbare kwaliteitswinst geeft;
4. de extra variatie en complexiteit acceptabel zijn.

---

# 17. Herontwerp de Critic

Onderzoek de huidige Critic grondig.

Voorkom:

```text
annotator
→ volledige annotatieset
→ critic
→ volledige tweede interpretatie
```

Dat introduceert potentieel extra generatieve variatie.

Ontwerp in plaats daarvan:

```text
classifier
↓
deterministische validators
↓
uncertainty/conflict detector
↓
gerichte reviewer
↓
resolver
```

De reviewer krijgt alleen concrete conflicten.

Bijvoorbeeld:

```json
{
  "candidate_id": "C024",
  "current": "Voorwaarde",
  "alternative": "Rechtsfeit",
  "reason_for_review": "CLASS_AMBIGUITY",
  "allowed_actions": [
    "KEEP",
    "CHANGE",
    "HUMAN_REVIEW"
  ]
}
```

De reviewer mag niet zelfstandig de gehele annotatieset herschrijven.

---

# 18. Reviewer en resolver zijn verschillende verantwoordelijkheden

Reviewer:

```text
geeft oordeel over concreet twijfelgeval
```

Resolver:

```text
past vaste beslisregels toe op revieweroutput
```

Voorbeeld:

```text
reviewer confidence hoog + allowed transition
→ wijzig voorstel

conflict blijft bestaan
→ human review

structurele fout
→ reject
```

Alle transities moeten auditbaar zijn.

---

# 19. Onzekerheid

Gebruik geen willekeurige zelfgerapporteerde LLM-confidence als primaire kwaliteitsmaat.

Bepaal onzekerheid waar mogelijk uit observeerbare signalen:

* verschillende kandidaatklassen;
* conflicterende detectoren;
* overlap;
* parser failure;
* ontbrekende context;
* afwijking van bekende patronen;
* classifier/reviewer disagreement;
* onbekend taalpatroon;
* out-of-distribution situatie.

Gebruik modelconfidence hooguit als aanvullend signaal.

---

# 20. Deterministische validatie

Voer na classificatie vaste controles uit op minimaal:

```text
candidate bestaat
offsets kloppen
brontekst klopt
klasse toegestaan
bronversie klopt
bronhash klopt
overlap toegestaan
nesting toegestaan
status geldig
provenance aanwezig
source target geldig
```

Een LLM mag deze controles niet vervangen.

---

# 21. SHACL

Onderzoek en implementeer SHACL voor structurele validatie van de RDF-projectie.

Gebruik SHACL niet als vervanging van juridische review.

Maak expliciet onderscheid tussen:

```text
RDF structureel geldig
JAS-model structureel geldig
juridisch inhoudelijk juist
```

SHACL kan voornamelijk de eerste twee controleren.

Begin met SHACL in:

```text
tests
CI
diagnostics
```

Maak productieblokkades pas later, wanneer duidelijk is dat de shapes correct en compleet zijn.

---

# 22. Coverage: onderscheid drie vormen

Gebruik het woord coverage niet als één generieke maat.

## A. Candidate processing coverage

Iedere gegenereerde kandidaat moet eindigen als:

```text
ACCEPTED
REJECTED
UNCERTAIN
HUMAN_REVIEW
```

`UNHANDLED = 0`

## B. Structural detection coverage

Leg vast welke relevante detectiedimensies zijn uitgevoerd:

```text
actor
object
normatieve relatie
handeling/gebeurtenis
voorwaarde
berekening/afleiding
waarde
operator
tijd
plaats
delegatie
definitie
```

## C. Annotation recall

De vraag:

> hoeveel echte JAS-annotaties zijn daadwerkelijk gevonden?

kan alleen betrouwbaar worden beantwoord tegen door bevoegde mensen gevalideerde referentieannotaties.

Verwar A of B nooit met C.

---

# 23. Geen fictieve golden set

Gebruik de term `gold` uitsluitend voor annotaties waarvan een expliciete menselijke validatieprocedure is vastgelegd.

Gebruik anders bijvoorbeeld:

```text
fixture
synthetic
silver
provisional
review_pending
adjudicated
gold
```

Maak de status machineleesbaar.

---

# 24. Evaluatie

Bouw evaluatie vanaf het begin in.

Meet kandidaatgeneratie:

```text
candidate recall
candidate precision
candidates per true annotation
detector contribution
```

Meet classificatie:

```text
precision per JAS class
recall per JAS class
F1 per JAS class
macro F1
micro F1
confusion matrix
exact span match
partial span overlap
```

Meet consistentie:

voer exact dezelfde analyse meerdere keren uit.

Meet:

```text
candidate agreement
class agreement
span agreement
annotation-set agreement
review disagreement
```

Meet systeemefficiëntie:

```text
LLM calls
input tokens
output tokens
LLM decisions per article
percentage deterministic decisions
review percentage
human-review percentage
latency
cost
```

Maar optimalisatievolgorde is:

```text
1. juridische kwaliteit
2. recall
3. precision
4. reproduceerbaarheid
5. uitlegbaarheid
6. efficiency
7. kosten
```

Optimaliseer niet vroegtijdig op minder tokens wanneer de kwaliteit daardoor daalt.

---

# 25. Fouttaxonomie

Iedere analysefout moet categoriseerbaar worden.

Gebruik bijvoorbeeld:

```text
SOURCE_ERROR
SEGMENTATION_ERROR
PARSER_ERROR
DETECTOR_ERROR
CANDIDATE_MISSED
CANDIDATE_FALSE_POSITIVE
FUSION_ERROR
CLASSIFICATION_ERROR
SPAN_ERROR
CONTEXT_ERROR
VALIDATION_ERROR
REVIEW_ERROR
RESOLUTION_ERROR
PROJECTION_ERROR
```

Iedere regressie moet uiteindelijk tot een concrete foutcategorie kunnen worden herleid.

---

# 26. Geen stille fallback

Wanneer bijvoorbeeld dependency parsing faalt:

doe NIET:

```text
fallback naar volledige LLM-annotatie
```

Doe:

```text
registreer failure
markeer gedegradeerde analyse
gebruik betrouwbare resterende signalen
verhoog onzekerheid
stuur indien nodig naar menselijke review
```

Iedere fallback moet zichtbaar zijn in provenance en metrics.

---

# 27. Provenance end-to-end

Voor iedere uiteindelijke annotatie moet kunnen worden gereconstrueerd:

```text
bron
bronversie
bronhash
segmentatie
linguïstische analyse
detectors
regels
candidates
evidence
classifier
model
modelversie
promptversie
methodeversie
validators
reviewer
resolver
menselijke review
uiteindelijke status
```

Gebruik de bestaande PROV-O-architectuur waar passend.

Behandel modelherkomst nooit als juridische autoriteit.

---

# 28. RDF en standaarden

Behoud de reeds aanwezige sterke keuzes rond:

* RDF;
* SKOS;
* Web Annotation;
* PROV-O;
* ELI waar semantisch passend;
* named graphs;
* canonieke bron-IRI's;
* JAS-vocabulary.

Voeg geen nieuwe standaarden toe zonder concrete use case.

---

# 29. Behoud deterministische SPARQL

De bestaande richting waarbij het model domeintools selecteert en code de daadwerkelijke SPARQL-query bepaalt is gewenst.

Behoud:

```text
LLM bepaalt informatiedoel
→ domeintool
→ deterministische query
→ GraphDB
```

Introduceer geen vrije SPARQL-generatie in de kern van de annotatiepijplijn.

---

# 30. Maak JAS-regels data-driven waar zinvol

Voorkom dat alle detectiekennis verspreid raakt over honderden losse `if`-statements.

Gebruik declaratieve regels wanneer dat de leesbaarheid verbetert.

Bijvoorbeeld:

```yaml
id: jas.condition.indien

jas_class: Voorwaarde

trigger:
  lemma:
    - indien
    - mits
    - tenzij

syntax:
  clause: subordinate

evidence:
  code: CONDITIONAL_CLAUSE
```

Iedere regel bevat:

```text
rule id
JAS class
bron/motivatie
pattern
expected evidence
version
tests
```

Niet alle code hoeft declaratief. Kies gewone code wanneer die duidelijker is.

---

# 31. Tests per regel en detector

Iedere detector of regel krijgt minimaal:

```text
positive case
negative case
edge case
overlap case
```

Voeg voor iedere gevonden productiefout een regressietest toe.

Het doel is dat steeds meer kwaliteitskennis in tests terechtkomt en steeds minder in promptpatches.

---

# 32. Gebruik goedgekeurde annotaties als leerbron

Wanneer menselijke goedgekeurde annotaties beschikbaar komen:

* sla ze gestructureerd op;
* behoud bron en provenance;
* indexeer grammaticale kenmerken;
* indexeer JAS-klasse;
* gebruik ze voor evaluatie;
* gebruik ze als relevante voorbeelden bij twijfel.

Bouw bijvoorbeeld een domeintool:

```text
find_reviewed_examples(
    jas_class,
    syntactic_pattern,
    legal_context
)
```

Stop niet honderden voorbeelden in de systeemprompt.

---

# 33. JRM en JAS scheiden

Wanneer JRM-verrijking in de huidige architectuur aanwezig is:

* behandel JAS als primaire annotatielaag;
* houd JRM-verrijking afzonderlijk;
* laat JRM geen JAS-label vervangen;
* laat JRM de kandidaatdetectie niet ongemerkt veranderen;
* documenteer expliciet op welk moment JRM wordt toegevoegd.

---

# 34. PR-strategie

Voer de verandering gefaseerd door.

Pas na repositoryanalyse indien nodig de precieze PR-grenzen aan, maar behoud de afhankelijkheidsrichting.

## PR 1. Architecture baseline + ADR

Geen gedragswijziging.

Documenteer:

* huidige pipeline;
* JAS-gap;
* doelarchitectuur;
* verantwoordelijkheden;
* fouttaxonomie;
* metrics;
* migratiepad.

## PR 2. Canoniek bron-, segment- en spanmodel

Introduceer of consolideer:

* bronidentiteit;
* bronversie;
* offsets;
* hashes;
* segmenten;
* immutable source spans.

## PR 3. Linguistic analysis abstraction

Introduceer provider-onafhankelijk taalmodel.

Benchmark geschikte Nederlandse NLP-provider(s).

## PR 4. JAS detection profiles

Leg per JAS-klasse vast:

* officiële bedoeling;
* herkenningssignalen;
* uitdrukkingspatronen;
* confusions;
* deterministic/semantic boundary.

## PR 5. Candidate datamodel

Introduceer:

```text
Candidate
Evidence
DetectorResult
CandidateClass
```

Nog zonder productiemigratie.

## PR 6. High-confidence detectors

Begin met relatief deterministische patronen:

* tijd;
* plaats;
* numerieke waarden;
* operatoren;
* expliciete definities;
* expliciete delegatie;
* wettelijke verwijzingen.

## PR 7. Syntactische detectoren

Voeg onder andere toe:

* rechtssubject-kandidaten;
* rechtsobject-kandidaten;
* rechtsbetrekking-kandidaten;
* rechtsfeit-kandidaten;
* conditionele structuren;
* afleidingsconstructies.

## PR 8. Candidate fusion

Deduplicatie, nesting, overlaps en evidence aggregation.

## PR 9. Candidate classifier

Introduceer de kleine semantische classifier.

Laat legacy en nieuw parallel kunnen bestaan.

## PR 10. Coverage accounting

Candidate coverage en structural coverage.

Nog geen ongefundeerde claim over echte recall.

## PR 11. Deterministische validators

Spans, bronnen, enums, overlap, status, provenance.

## PR 12. Critic → targeted reviewer

Verwijder volledige generatieve heranalyse uit de standaardroute.

## PR 13. Resolver

Maak reviewer-output gecontroleerd verwerkbaar.

## PR 14. SHACL

Structurele RDF-validatie.

Eerst non-blocking.

## PR 15. End-to-end provenance

Alle tussenstappen reconstrueerbaar.

## PR 16. Evaluation harness

A/B:

```text
legacy
vs
hybrid pipeline
```

Meet kwaliteit, consistency, recall, precision, errors, latency en kosten.

## PR 17. Tuning op basis van fouten

Geen willekeurige promptwijzigingen.

Verbeter concrete foutcategorieën.

## PR 18. Legacy removal

Verwijder de oude route pas wanneer de nieuwe architectuur aantoonbaar voldoende presteert.

---

# 35. Feature flags

Maak parallel testen mogelijk:

```text
ANNOTATION_PIPELINE=legacy
ANNOTATION_PIPELINE=hybrid_v1
```

Identieke bepalingen moeten door beide routes kunnen worden geanalyseerd.

---

# 36. Acceptatiecriteria voor iedere PR

Iedere PR bevat:

1. doel;
2. probleem;
3. ontwerpbeslissing;
4. scope;
5. wijzigingen;
6. unit tests;
7. integratietests;
8. regressietests;
9. metrics indien relevant;
10. documentatie;
11. backwards compatibility;
12. risico's;
13. rollback;
14. bewijs dat geen onbedoelde JAS-semantiek is gewijzigd.

Geen PR accepteren op basis van alleen:

> de output ziet er beter uit.

---

# 37. Bescherm wat al goed is

Herontwerp geen bestaande onderdelen alleen omdat een nieuw ontwerp architectonisch mooier lijkt.

Behoud waar mogelijk bewezen onderdelen zoals:

* GraphDB;
* Postgres als source of truth indien dat het bestaande contract is;
* annotatielagen;
* brontraceerbaarheid;
* lifecycle;
* reviewhistorie;
* provenance;
* domeintools;
* deterministische SPARQL;
* bestaande API-contracten;
* bestaande frontendfunctionaliteit.

---

# 38. Geen verborgen semantische wijzigingen

Iedere wijziging van JAS-gedrag moet expliciet worden vastgelegd:

```text
JAS class
old behavior
new behavior
official JAS basis
reason
examples
regression tests
migration impact
```

---

# 39. Verboden oplossingsrichtingen

Doe niet:

```text
"maak de annotatieprompt gewoon beter"
```

Doe niet:

```text
"voeg twintig extra voorbeelden aan de prompt toe"
```

Doe niet:

```text
"laat drie agents stemmen"
```

Doe niet:

```text
"laat de Critic de hele analyse nogmaals doen"
```

Doe niet:

```text
"laat het LLM grammaticale informatie bedenken"
```

wanneer een parser dat betrouwbaarder kan leveren.

Doe niet:

```text
"gebruik één confidence-getal als waarheid"
```

Doe niet:

```text
"100% candidate coverage = 100% annotation recall"
```

Doe niet:

```text
"noem ongevalideerde annotaties gold"
```

Doe niet:

```text
"introduceer meer RDF/OWL/agents omdat het technisch kan"
```

---

# 40. Gewenste eindtoestand

Voor iedere annotatie moet uiteindelijk antwoord gegeven kunnen worden op:

```text
Welke tekstspan is geannoteerd?
Waarom werd deze span kandidaat?
Welke detector(en) vonden hem?
Welke grammaticale structuur is gevonden?
Welke JAS-herkenningssignalen waren relevant?
Welke mogelijke klassen waren er?
Was een LLM noodzakelijk?
Zo ja, welke exacte beperkte vraag kreeg het model?
Welke beslissing gaf het model?
Welke validators draaiden?
Was er onzekerheid?
Waarom werd reviewer of mens ingeschakeld?
Welke uiteindelijke beslissing is genomen?
Op basis van welke JAS-versie?
Hoe is dit geprojecteerd naar RDF?
Welke provenance hoort erbij?
```

Een ontwikkelaar, jurist of auditor moet de volledige route kunnen reconstrueren.

---

# 41. Centrale architectuurdoctrine

Gebruik in het hele traject deze volgorde:

```text
STRUCTURE BEFORE LANGUAGE MODEL
RULES BEFORE GENERATION
DETECTION BEFORE CLASSIFICATION
CLASSIFICATION BEFORE REVIEW
VALIDATION BEFORE ACCEPTANCE
EVIDENCE BEFORE CONFIDENCE
HUMAN VALIDATION BEFORE GOLD
```

Het eindproduct moet niet bestaan uit een steeds slimmer wordende prompt.

Het eindproduct moet een:

**robuuste, meetbare, traceerbare en grotendeels deterministische JAS-annotatiemachine**

zijn waarin het taalmodel alleen wordt gebruikt voor de kleine resterende semantische beslissingen waarvoor taalinterpretatie werkelijk noodzakelijk is.

---

# 42. Eerste opdracht aan jou

Begin NIET direct met implementeren.

Voer eerst uitsluitend deze analysefase uit.

## Stap 1. Repository baseline

Analyseer de huidige implementatie end-to-end.

## Stap 2. Officiële JAS-mapping

Controleer per officiële JAS-klasse:

* definitie;
* herkenningsvraag;
* uitdrukkingswijze;
* huidige ondersteuning;
* ontbrekende ondersteuning.

## Stap 3. Responsibility map

Bepaal voor iedere stap:

```text
deterministisch
linguïstisch/NLP
GraphDB/RDF
LLM
reviewer
mens
```

## Stap 4. Gap analysis

Maak concreet zichtbaar:

* waar annotaties gemist kunnen worden;
* waar inconsistentie kan ontstaan;
* waar prompts te veel verantwoordelijkheid dragen;
* waar de Critic extra variatie kan introduceren;
* waar regels impliciet zijn;
* waar coverage onvoldoende meetbaar is.

## Stap 5. Doelarchitectuur

Werk een definitieve architectuur uit die aansluit op de daadwerkelijke huidige repository.

## Stap 6. Definitief PR-plan

Maak vervolgens het PR-plan.

Per PR:

```text
doel
scope
bestanden/modules
contractwijzigingen
tests
acceptatiecriteria
metrics
dependencies
risks
migration
rollback
```

## Stap 7. Validatie van het plan

Voordat je implementatie voorstelt, controleer expliciet:

* worden alle JAS-klassen afgedekt?
* zijn de officiële herkenningsvragen verwerkt?
* zijn de officiële uitdrukkingswijzen verwerkt?
* is grammatica slechts een detectiemiddel en niet blind een classificatieregel?
* is candidate recall meetbaar?
* is echte annotation recall later meetbaar?
* is de modelverantwoordelijkheid kleiner geworden?
* zijn prompts kleiner geworden?
* is de Critic voldoende begrensd?
* blijft deterministische SPARQL behouden?
* blijft provenance intact?
* wordt bestaande goede architectuur gerespecteerd?
* kunnen legacy en nieuwe route objectief worden vergeleken?

## Stap 8. Stop

Implementeer nog niets.

Lever eerst terug:

1. Current-state analyse
2. JAS-conformiteitsanalyse
3. Gap-analyse
4. Doelarchitectuur
5. Responsibility map
6. Definitief PR-plan
7. Teststrategie
8. Evaluatieplan
9. Risicoanalyse
10. Openstaande inhoudelijke beslissingen

Onderbouw iedere conclusie met concrete verwijzingen naar de repository of de officiële JAS-specificatie.

Pas nadat dit fundament klopt, begint de uitvoering met PR 1.
