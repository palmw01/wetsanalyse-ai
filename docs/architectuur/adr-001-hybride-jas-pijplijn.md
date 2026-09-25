# ADR-001 — Hybride JAS-annotatiepijplijn

Status: **voorgesteld** · Datum: 2026-09-24 · Soort: *plan* (zie `docs/README.md`) · JAS-versie: 1.0.10

Opdracht: [`opdracht-jas-annotatiepijplijn.md`](opdracht-jas-annotatiepijplijn.md). Dit document is
de oplevering van de analysefase (§42 van de opdracht, stap 1–8): current state, JAS-conformiteit,
gap-analyse, doelarchitectuur, verantwoordelijkheidskaart, PR-plan, test- en evaluatieplan,
risico's en open beslissingen. Het wijzigt geen gedrag. De geldende specificatie blijft
[`annotatie-bronnodes.md`](annotatie-bronnodes.md) totdat een PR uit §6 iets anders vastlegt.

---

## 0. Context

De huidige annotatieketen in `tools/graph-qa` laat een LLM de volledige JAS-analyse genereren.
Een tweede LLM (de Critic) herbeoordeelt die volledige set en een derde (de herziener) kan de set
opnieuw uitschrijven. De keten is al sterk verbeterd: patches worden in code uitgevoerd, er zijn
prioriteitsregels, `bronmodel`-ankers en provenance-vingerafdrukken. De kern blijft echter
generatief. De stabiliteitsmeting van 24-09 (`docs/wetsanalyse/evaluatie-methode.md` §Stabiliteit)
en de proef op IW01 (dubbel tijd/parameter-label in 1 of 2 van de 3 runs) laten zien dat dezelfde
invoer verschillende uitkomsten geeft.

Het doel is een grotendeels deterministische detectie- en validatiemachine, met het LLM alleen
voor afgebakende semantische keuzes op vaste kandidaat-ID's. Die machine wordt parallel aan de
legacy-route ingevoerd achter een vlag en objectief vergeleken.

---

## 1. Current-state analyse (repository-baseline)

### 1.1 Normatieve basis
- `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md` is een ongewijzigde spiegel van minbzk/wetsanalyse
  commit `5ae93cc` (BRON.md). **Geverifieerd:** `js/config.js` van die commit meldt
  `publishVersion: "1.0.10"`, `publishDate: 2024-11-29`, en dat is ook de HEAD van main. De repo
  gebruikt dus exact de officiële **1.0.10**. Er is geen versieverschil.
- **Bewuste afwijking in de taxonomie:** de officiële tabel kent 16 rijen, het platform 13 labels.
  Variabele/Variabelewaarde, Parameter/Parameterwaarde en Delegatiebevoegdheid/Delegatie-invulling
  zijn samengevoegd (`.claude/skills/wetsanalyse/references/jas-klassen-referentie.md:17-31`,
  `api/app/jas_klassen.py:19-33`). De helft staat alleen in de vrije `toelichting`. Het
  subonderscheid is daardoor niet machineleesbaar. Dat raakt de dekking die in §2 wordt gevraagd.
- De methode staat in de skill (markdown). `tools/graph-qa/agent/jas_klassen.py` wordt daaruit
  gegenereerd (`scripts/genereer_jas_klassen.py`, bewaakt door `tests/test_methode_drift.py`).
  Het protocol (`annotatieprotocol.md`) wordt via `agentrollen.json` → `methodepakket.py` in de
  prompts geïnjecteerd.

### 1.2 Pijplijn zoals hij nu draait (`agent/orchestrator.py`, `agent/nodes/annotatie.py`)
```
doel → lees_bron (bronmodel.resolve → snapshot) → controleer_hergebruik (api-dekking/weergave)
→ annoteer (LLM: volledige set, ~14,5k tekens klassenreferentie + protocol)
   [alt. ENABLE_KANDIDAAT_SPLITSING: LLM-kandidaten → LLM-klasseer]  (default UIT, config.py:105-109)
→ _verwerk (letterlijkheid, klasse-enum, prioriteitsregels, dedup op sleutel_van, ankers)
→ critic₁ (LLM: oordeel over ELK element + generatief 'ontbrekend')
→ patch (code: rood+vervang uitvoeren, geel → alternatief; prioriteitsvalidator)
→ [herzie (LLM: geeft HELE lijst opnieuw)] → [critic₂] → emit → api PUT (contract 2)
```
- **Bron- en spanmodel:** `packages/bronmodel` is al canoniek. Het levert een snapshot van de hele
  bronboom (`snapshot_id` = SHA256 van de canonieke JSON), een SHA256 per node (`tekst_hash`) en
  offsets in Unicode-codepoints per bronnode. `valideer_ankers` controleert bestaan, bereik, hash,
  letterlijkheid, volgorde en overlap, en `eigenaar` bepaalt de diepste gemeenschappelijke ouder.
  Daarnaast bestaat nog een **tweede, legacy ankerpad**: `annotatie._maak_anker` met FNV-1a over
  het samengestelde corpus, `lid_hashes` en `herankeer`.
- **Offsets komen deels van het model:** `bron_annotatie.bron_instructie` (r.132-144) vraagt het
  LLM om per element `{bron_iri, tekst, start, eind}`. `verwerk_bron` (r.147-207) corrigeert
  verkeerde offsets met een tekstzoektocht en verwerpt ambigue fragmenten.
- **Regels:** `jas_klassen.REGELS` (r.393-429) is een declaratief `JASRule`-model met `RegelType`
  (PRIORITEIT/CONFLICT/EXCLUSIE/SPAN/CONSISTENTIE). Er zijn maar **twee** regels
  (JAS-PRIORITY-001/002: tijd/plaats boven variabele/parameter). De regels worden in de prompt
  gezet én in code afgedwongen (`annotatie._pas_prioriteitsregels_toe`, r.363), maar alleen
  tussen klasse en alternatieven van **hetzelfde** element.
- **LLM-aanroep:** er is geen `temperature` (overal de providerdefault; de eval legt dat zelf vast)
  en geen structured output. JSON wordt uit vrije tekst gevist (`_balanced_objecten`, r.840).
  `max_tokens` is 8192.
- **Critic** (`annotatie_prompt.critic_systeemprompt`, `pas_critic_toe` r.541): het verbeterpunt
  "patches in code" is al gerealiseerd. De Critic krijgt nog wel de volledige set en de volledige
  klassenreferentie, en levert generatief `ontbrekend`. De herziener levert de **volledige**
  elementenlijst opnieuw. Beide zijn bronnen van generatieve variatie.
- **Leesroute en SPARQL:** alle graafbevraging loopt via getypeerde tools en `graph/queries.py`
  (`raw_sparql` is afgeschermd). Annotaties worden via de api gelezen en tegen Postgres
  geverifieerd. Dit is de gewenste deterministische SPARQL-richting.
- **API en opslag:** Postgres is de source of truth (contract 2, `api/app/annotatie_v2*.py`).
  `Element` heeft `extra="allow"` (`annotatie_v2_contracts.py:22-29`) en `Batch.run: dict` (r.53).
  Extra provenance kan dus meereizen zonder contractbreuk. Lifecycle: `voorgesteld,
  critic_checked, human_approved, edited, rejected, published, reused`
  (`annotatie_contracts.py:28-35`). Beslissingen en audit zijn append-only.
- **RDF:** de v2-projectie (`graaf_projectie_v2.py`, `jas-annotatie-ontologie.md`) is bewust
  **plat**: Web Annotation (oa:), `jas:klasseNaam` als string, geen SKOS-concept en **geen
  PROV-O**. PROV en SKOS bestaan alleen in het v1-model (`jas_ontologie.py`, `jas-ontologie.ttl`)
  en in de fixture. Invariant: de wettekst blijft schoon (geen `urn:bwb:`-subject, geen
  domain/range, rdfsplus-inferentie). **SHACL ontbreekt volledig.**
- **Provenance per beurt:** het `run`-event bevat model, provider, agent_versie, `prompt_hash`,
  `methode_versie`, modus, leden en instellingen. Per element zijn er `critic_rondes` met
  `toegepast`. Er is geen trace per element van detector → kandidaat → beslissing.
- **Eval:** `eval/scoring.py` heeft al `candidate_recall` (r.343), `span_exact_match`, `span_iou`,
  `classification_accuracy` en `verworpen_per_100`. `eval/stabiliteit*.py` meet
  detectie-, span- en klassestabiliteit per fase. `golden_annotatie.jsonl` is expliciet een
  **ankerset**, en `docs/wetsanalyse/referentieset/` bevat 24 **concept**casussen (6 families,
  split dev/held-out) met SHA256 en offsets. Er is **nergens gold**. Dat staat ook eerlijk
  gedocumenteerd.
- **JRM:** komt alleen voor in de skill- en dossierlaag (`references/jrm-verrijking.md`), niet in
  de runtimeketen. Dat is al gescheiden; alleen vastleggen.
- **NLP:** er is geen enkele linguïstische bibliotheek. De "grammaticale ontleding" staat als
  instructie in de prompt (`annotatieprotocol.md` §Gedeeld: "Bepaal onderwerp, volledig gezegde,
  passieve actor, modaliteit…"). **Het LLM doet nu zelf de zinsontleding.**

### 1.3 Bescherm-lijst (niet herontwerpen)
`bronmodel`-snapshots en -ankers; contract 2 en de Postgres-waarheid; de api als enige
graafschrijver; de directe projectie met reconcile-lus; getypeerde tools en `queries.py`;
hergebruik vóór annoteren; bevroren juristmarkeringen; `pas_critic_toe`-semantiek (geel verandert
nooit iets); de SSE-eventcontracten; `sleutel_van`-ontdubbeling (drie implementaties, één regel);
drift-tests skill → code; de eval-garanties.

---

## 2. JAS-conformiteitsanalyse (per officiële klasse, H2-JAS.md 1.0.10)

Alle 13 paragrafen (16 begrippen) staan letterlijk in `jas_klassen.JAS_KLASSEN`. Definitie,
vraag en uitdrukkingswijze komen **alleen in prompts** terecht. Geen enkele herkenningsvraag of
uitdrukkingswijze is operationeel als detectiesignaal gecodeerd, met uitzondering van de
specificiteitsregel (H2:107, H2:116). Die is als JAS-PRIORITY-001/002 gecodeerd.

| Klasse (H2-regel) | Officiële uitdrukkingswijze → detectiesignaal | Huidige ondersteuning | Ontbreekt |
|---|---|---|---|
| Rechtssubject (26-28) | znw voor persoon/entiteit; pers./onbep./betr. vnw ('hij', 'degene', 'een ieder') | prompt | NP-/vnw-detectie, antecedent (coreferentie) |
| Rechtsobject (35-37) | znw voorwerp; aanw./betr. vnw ('dat', 'hetgeen', 'welk(e)') | prompt | NP-obj-detectie |
| Rechtsbetrekking (44-46) | hulpww+hoofdww ('kan verzoeken', 'moet informeren'); samengesteld ('heeft recht op', 'draagt de last om') | prompt + protocolregel "volledige normzin" | modaliteit-/predicaatdetectie, clausegrens |
| Rechtsfeit (53-55) | actieve werkwoordsvorm ± znw ('indienen van een bezwaarschrift') | prompt | nominalisatie- en gebeurtenisdetectie |
| Voorwaarde (62-64) | voorwaardelijke bijzin (indien/als/tenzij/mits, 'met dien verstande dat', 'met uitzondering van'); bijwoord ('schriftelijk'); cumulatief/alternatief | prompt | bijzin- en voegwoorddetectie, negatieve patronen ('als bedoeld in') |
| Afleidingsregel (71-73) | 'is (…) verminderd met', 'bedraagt (…) vermeerderd met', 'wordt gesteld op', 'is het gezamenlijke bedrag van', 'en' | prompt | berekeningsconstructies |
| Variabele / Variabelewaarde (80-82) | getal/datum, tekst, enumeratie (limitatieve opsomming), boolean | prompt, **samengevoegd label** | subtype en enumeratiedetectie |
| Parameter / Parameterwaarde (89-91) | tarief, (drempel)bedrag, vrijstelling; bedrag, percentage, datum | prompt, **samengevoegd label** | numerieke en monetaire detectie, subtype |
| Operator (98-100) | rekenkundig ('de som van', 'vermeerderd met'), vergelijking ('groter dan', 'meer bedraagt dan'), logisch ('en', 'of', 'niet', 'ten minste') | prompt | lexicon + coördinatiebereik |
| Tijdsaanduiding (107-109) | concrete datum, datumomschrijving, periodewoorden (jaar/maand/week/dag, kalenderjaar); **voorrang boven var/par** | prompt + PRIORITY-001 | temporele expressieparser; voorrang over overlappende spans |
| Plaatsaanduiding (116-118) | algemene gebiedsomschrijving (lidstaat EU); gebiedsnaam; **voorrang boven var/par** | prompt + PRIORITY-002 | gazetteer |
| Delegatiebevoegdheid / -invulling (125-127) | 'bij (of krachtens) amvb/ministeriële regeling worden regels gesteld', 'kunnen regels worden gesteld'; invulling: verwijzing naar bovenliggende wet | prompt, **samengevoegd label** | delegatiepatroon; invulling via graaf (WTI-grondslagen) |
| Brondefinitie (134-136) | begripsbepalingenartikel: aanhef + onderdelen, vaak aan het begin | prompt | structurele detectie (aanhef 'wordt verstaan onder') |

Samenhangregels uit JAS (H2:62 voorwaarde bevat operanden en operatoren; H2:71 afleidingsregel met
invoer, uitvoer en parameter; H2:125 delegatie aan een rechtssubject) zijn nergens als
consistentieregel gecodeerd. `RegelType.CONSISTENTIE` bestaat wel, maar is leeg.

---

## 3. Gap-analyse

**A. Waar annotaties gemist kunnen worden**
1. Recall hangt volledig af van één generatieve call. Er is geen structurele controle of elke
   bijzin, NP, getal of datum is overwogen. De `ontbrekend`-lijst van de Critic is opnieuw
   generatief.
2. De dekkingstabel in de protocoltekst ("Review iedere normeenheid") is een promptinstructie,
   geen meting.
3. De cap op het aantal elementen en het tokenplafond van de Critic (historisch 27 → 15
   beoordeeld) laten een plafond zien. Bij grote leden daalt de dekking stil.
4. Ambigue ankers (`ambigu_anker_geef_bronnode_en_posities`) worden verworpen. Dat is terecht,
   maar een correct element valt zo weg alleen omdat het model de offsets niet goed teruggaf.

**B. Waar inconsistentie ontstaat**
1. Geen vaste temperatuur en geen structured output.
2. Het model kiest zelf de spangrenzen en rekent zelf offsets uit.
3. Critic en herziener leveren een tweede en derde volledige interpretatie
   (`herziening_systeemprompt`: "geeft de hele lijst").
4. De specificiteitsregel werkt alleen binnen één element. Een los Parameter-element op "zes weken"
   naast een Tijdsaanduiding op "zes weken na de dagtekening" blijft staan (IW01-proef).

**C. Waar prompts te veel verantwoordelijkheid dragen**
Zinsontleding, coreferentie, modaliteit, bijzinbereik, spangrenzen, offsets, dekking,
prioriteitsregels (dubbel met code) en volledigheid liggen allemaal bij het model. De volledige
klassenreferentie (~14,5k tekens) gaat mee in 5 rollen.

**D. Waar de Critic variatie introduceert**
Oordeel over alle elementen, generatief `ontbrekend`, `vervang` met vrije `voorstel_tekst`, en een
herziener die de volledige lijst herschrijft. Rood+vervang wordt zonder tweede beoordelaar
uitgevoerd op basis van één modeloordeel.

**E. Waar regels impliciet zijn**
Negatieve patronen ("als bedoeld in" is geen voorwaarde; ordinaal "derde lid" is geen parameter;
"en" binnen een NP is geen operator) staan alleen in de protocoltekst of in commits. Grenzen per
klasse staan in `markeren-fragmentgrenzen.md` als proza. Het delegatie-subtype en het
variabele/-waarde-subtype worden niet vastgelegd.

**F. Waar dekking onvoldoende meetbaar is**
Er is geen candidate processing coverage (geen kandidaatobjecten), geen structural coverage (geen
detectiedimensies) en geen annotation recall (geen gold). `candidate_recall` bestaat in
`scoring.py`, maar alleen tegen de ankerset.

**G. Provenance-gaten**
Per element is niet te reconstrueren welke detector, regel, kandidaat of exacte modelvraag eraan
voorafging. De v2-RDF bevat geen PROV. De `run` staat per batch, niet per beslissing.

---

## 4. Doelarchitectuur (aansluitend op de repo)

Nieuwe package `tools/graph-qa/agent/jas_pipeline/`. Die is puur, zonder LangGraph-afhankelijkheid,
en wordt aangeroepen vanuit bestaande nodes. Eén orchestrator (de bestaande LangGraph) en geen
nieuwe agents.

```
bronmodel.resolve → snapshot (bestaand)
 └ jas_pipeline.bron: SourceSegment/Span (immutable, codepoints, sha256) + CorpusMap
 └ jas_pipeline.taal: LinguisticAnalysis (provider-onafhankelijk, UD-gebaseerd) ── faalt → degraded=True
 └ jas_pipeline.detectoren: families (temporeel, plaats, numeriek, operator, definitie, delegatie,
      verwijzing, conditioneel, normatief-predicaat, NP-subject/object, gebeurtenis, berekening,
      opsomming, negatie, coördinatie); regels declaratief (YAML) waar leesbaar
 └ jas_pipeline.kandidaten: Candidate{id, span, possible_classes, evidence[], span_options[]}
 └ jas_pipeline.fusie: dedup/merge evidence/overlap-graaf/nesting; offsets nooit gewijzigd
 └ jas_pipeline.specificiteit: JAS-PRIORITY-* over overlappende spans + CONSISTENTIE-regels
 └ jas_pipeline.besluit: deterministisch besluiten waar mogelijk (één klasse, sterk bewijs,
      geen conflict) → ACCEPTED; anders → classifier
 └ jas_pipeline.classificatie: kleine LLM-call(s) op candidate-ID's; enum-schema; temperature 0;
      keuze uit allowed_classes ∪ {GEEN}; span alleen via span_options-ID's
 └ jas_pipeline.validatie: offsets/hash/snapshot/enum/overlap/nesting/status/provenance (bronmodel)
 └ jas_pipeline.dekking: A (candidate processing, UNHANDLED=0), B (structurele dimensies)
 └ jas_pipeline.onzekerheid: observeerbare signalen → review_reason codes
 └ jas_pipeline.review: gerichte reviewer, alleen conflictitems, acties KEEP|CHANGE|HUMAN_REVIEW
 └ jas_pipeline.resolver: vaste transitietabel → voorstel / alternatief / human review / reject
 └ jas_pipeline.trace: per element de volledige route (compact, JSON) → Element.extra + Batch.run
→ bestaande _verwerk-/emit-/api-route (contract 2) → projectie (+ later PROV/SHACL)
```

Kernkeuzes:
- **Het LLM ziet nooit een vrije taak.** Invoer is een lijst `{candidate_id, span, context-venster,
  evidence-codes, allowed_decisions, span_options}`. Uitvoer is een `{candidate_id, decision,
  span_option_id?}`-lijst via een geforceerde tool-call met enum-schema (Foundry-ondersteuning
  controleren in PR 9; anders JSON-schema-validatie met één herhaalpoging en daarna UNCERTAIN).
- **Spangrenzen zijn deterministisch.** Detectoren leveren span-opties (kern, NP, NP+PP, clause).
  Het model kiest een optie-ID en typt geen tekst. Offsets worden nooit door een model berekend.
- **Kennis staat in data, niet in de prompt.** Detectieprofielen (YAML per klasse, §3 van de
  opdracht) staan in `jas_pipeline/profielen/`, met `bron: H2:NN` op elk officieel veld en een
  drift-test tegen `JAS_KLASSEN`. Het classifier-prompt krijgt per kandidaat alleen de
  profielfragmenten van de `allowed_classes` (confusable-paar), niet alle 13 klassen.
- **Subtype zonder labelbreuk:** een optioneel machineleesbaar veld `jas_subtype`
  (`variabele|variabelewaarde`, `parameter|parameterwaarde`,
  `delegatiebevoegdheid|delegatie-invulling`) via `Element.extra`. De 13 labels blijven. Dit is een
  **open beslissing** (§10.1).
- **Geen stille fallback:** faalt de NLP-provider, dan `degraded=True` in de trace, alleen
  lexicale en structurele detectoren, alle kandidaten minimaal `UNCERTAIN`, en een metric. Nooit
  terugvallen op volledige LLM-annotatie binnen `hybrid_v1`.
- **Recall-vangnet:** geen generatief `ontbrekend`. De dekkingsanalyse levert "niet-gedekte
  constituenten" (clauses, NP's en numerieke expressies zonder kandidaat). Die gaan als gewone
  kandidaten met `possible_classes = profielgestuurde set` naar de classifier. Wat daarna nog
  ongedekt is, komt als dekkingsmelding in de werkplek.
- **Critic → gerichte reviewer:** alleen items met review_reason (CLASS_AMBIGUITY,
  DETECTOR_CONFLICT, SPAN_AMBIGUITY, DEGRADED_PARSE, OOD_PATTERN, CLASSIFIER_ABSTAIN).
  De reviewer kan niets toevoegen of verwijderen buiten zijn item.
- **Resolver-transities** (tabel in code, getest):
  `KEEP → accepted(voorstel)`,
  `CHANGE ∧ toegestaan ∧ niet tegen PRIORITY → voorstel met oude klasse als alternatief`,
  `CHANGE tegen regel → alternatief + HUMAN_REVIEW`,
  `onenigheid classifier/reviewer → HUMAN_REVIEW (geel)`,
  `structureel ongeldig → REJECTED (met foutcode)`.
  Rood wordt nooit meer automatisch uitgevoerd op één modeloordeel.
- **Aandacht-mapping** (werkplek ongewijzigd): ACCEPTED zonder review → groen; HUMAN_REVIEW → geel
  + alternatieven; REJECTED-maar-getoond → rood. De lifecycle blijft `voorgesteld` en de mens
  beslist.
- **JRM:** ongewijzigd buiten de runtime. De pipeline leest of schrijft geen JRM-velden.
  Vastgelegd in de ADR.
- **SPARQL:** de pipeline doet alleen bestaande getypeerde reads (`bronmodel.bron_query`,
  api-leestools). Delegatie-invulling gebruikt een nieuwe getypeerde bouwer in `queries.py`
  (WTI-grondslag), geen vrije SPARQL.

### 4.1 Verantwoordelijkheidskaart (responsibility map)

| Stap | Deterministisch | NLP | GraphDB/RDF | LLM | Reviewer (LLM) | Mens |
|---|---|---|---|---|---|---|
| Bron, snapshot, hashes, segmenten | ● | | ● (getypeerde query) | | | |
| Tokens, zinnen, lemma, POS, dependencies, clauses | | ● | | | | |
| Tijd, plaats, getal, bedrag, percentage, verwijzing | ● (regels, gazetteer) | ○ (POS-steun) | | | | |
| Definitie- en delegatiepatroon | ● | ○ | ● (invulling via WTI) | | | |
| Subject-, object-, predicaat-, bijzin- en gebeurteniskandidaten | ○ (patronen) | ● | | | | |
| Fusie, nesting, specificiteit | ● | | | | | |
| Klasse bij eenduidig sterk bewijs | ● | | | | | |
| Klasse bij concurrerende klassen / semantiek | | | | ● (enum) | | |
| Spankeuze tussen opties | ○ (default) | | | ● (optie-ID) | | |
| Validatie (offsets/hash/enum/overlap/provenance) | ● | | | | | |
| Onzekerheid | ● (signalen) | | | ○ (hulpsignaal) | | |
| Conflictbeoordeling | | | | | ● | |
| Resolutie | ● (transitietabel) | | | | | |
| Acceptatie, gold | | | | | | ● |
| Projectie + SHACL | ● | | ● | | | |

---

## 5. Klassematrix (gap × voorstel)

Legenda deterministisch mogelijk: H = hoog, M = middel, L = laag.

| JAS-klasse | huidige detectie | LLM-verantw. nu | det. mogelijk | grammaticale signalen | juridische patronen | resterende semantiek | tests nu | FN-risico | FP-risico | voorstel |
|---|---|---|---|---|---|---|---|---|---|---|
| Rechtssubject | LLM | volledig | M | nsubj/obl:agent, NP-head persoon/org, vnw hij/degene/een ieder | lexicon rollen (belastingplichtige, inspecteur, Onze Minister, bestuursorgaan) | drager recht/plicht vs. grammaticaal onderwerp; impliciete actor | golden-ankers | M | H (elk onderwerp) | NP-detector + rol-lexicon → kandidaat; LLM: subject vs. object vs. geen |
| Rechtsobject | LLM | volledig | L-M | obj/nmod bij normatief predicaat; vnw dat/hetgeen | 'ter zake van', 'terzake', 'verschuldigd' | voorwerp vs. variabele of subject | golden | H | H | NP-obj-detector; LLM-paar subject/object/variabele |
| Rechtsbetrekking | LLM + protocol "hele normzin" | volledig | M | modale aux (kan/mag/moet/dient), 'is verplicht', 'heeft recht op', 'is bevoegd', 'is aansprakelijk' + clause | normatieve predicaatlijst | relatie tussen twee subjecten; recht vs. plicht | golden (IW01) | M | M | predicaat- en clausedetector, span-optie = hele normclause; LLM: betrekking/rechtsfeit/geen |
| Rechtsfeit | LLM | volledig | L | nominalisatie ('indienen van'), ww-clause, 'na', 'door' | 'verstrijken van', 'overlijden', 'dagtekening' | teweegbrengen rechtsgevolg | geen anker (CLAUDE.md: "Rechtsfeit heeft nog geen anker") | H | M | gebeurtenisdetector; LLM-paar rechtsfeit/voorwaarde/tijd |
| Voorwaarde | LLM | volledig | M-H | advcl/mark (indien, als, tenzij, mits, voor zover), 'met dien verstande dat', 'met uitzondering van'; bijwoord 'schriftelijk' | uitzonderingsformules | bereik, cumulatief/alternatief; bijwoord-voorwaarde | golden | L-M | M ('als bedoeld in') | conditionele detector + negatief patroon; LLM alleen bij bijwoord/overlap |
| Afleidingsregel | LLM + protocol | volledig | M | kopula + berekening, 'wordt gesteld op', 'bedraagt' | rekenformules | invoer, uitvoer, grens van de regel | golden + AWB04-proef | M | M ('bedraagt' los) | berekeningsdetector, span-opties (clause/zin); LLM: afleiding vs. parameterwaarde |
| Variabele(waarde) | LLM, samengevoegd | volledig | L (var) / H (waarde-getal) | NP + eigenschap ('hoogte van', 'bedrag van'); enumeratie | limitatieve opsomming | var vs. par; boolean-var | golden | H | M | numeriek + enumeratie → waarde-kandidaat; LLM-paar var/par; subtype-veld |
| Parameter(waarde) | LLM, samengevoegd | volledig | H (waarde) / M (beschrijving) | NUM, SYM €, %, 'tarief', 'drempel', 'vrijstelling' | bedragen en percentages | constant voor iedereen vs. variabel; ordinaal in verwijzing | golden (4:17/2) | L | H (lid-/artikelnummers) | numerieke detector + verwijzingsmasker (negatief); LLM-paar var/par |
| Operator | LLM | volledig | H (lexicaal) | cc/advmod-negatie, vergelijkende constructies | 'ten minste', 'meer bedraagt dan', 'vermeerderd met' | 'en' in NP vs. logisch/rekenkundig | golden | L | H | lexicon + dependency-bereik (cc tussen clauses/berekening); LLM alleen bij NP-coördinatie |
| Tijdsaanduiding | LLM + PRIORITY-001 | groot deel | H | datum, duur, 'binnen/na/vóór/met ingang van', periodewoorden | termijnformules | startgebeurtenis in span; tijd vs. rechtsfeit | golden (IW01) + prioriteitstests | L | L-M | temporele parser → sterk bewijs, deterministisch ACCEPTED zonder conflict; PRIORITY over overlap |
| Plaatsaanduiding | LLM + PRIORITY-002 | groot deel | M-H | NER LOC, 'in/binnen Nederland' | gazetteer (NL, gemeenten, provincies, EU, BES) | werkingsgebied vs. toevallige plaatsnaam | weinig | M | L | gazetteer + PP-detectie; LLM bij twijfel over werkingsgebied |
| Delegatie | LLM, samengevoegd | volledig | H (bevoegdheid) / M (invulling via graaf) | passief 'worden regels gesteld' + 'bij/krachtens amvb/ministeriële regeling' | vaste formules (H2:127) | reikwijdte gedelegeerd onderwerp | geen | L | L | patroondetector + WTI-graaftool; subtype-veld; invulling structureel |
| Brondefinitie | LLM | volledig | H | 'wordt verstaan onder', 'In deze wet … wordt verstaan' + onderdeelstructuur | begripsbepalingenartikel | welke term, grens van de definitie | golden (5:2/1) | L | L | structurele detector (aanhef + onderdelen via bronmodel) |

---

## 6. Definitief PR-plan

Aanpassingen ten opzichte van de opdracht (de afhankelijkheidsrichting blijft gelijk):
- **PR 0** (voorwerk): `feat/stabiliteitsbenchmark` eerst mergen. Dat is de meetinstrumentatie
  voor de baseline.
- De evaluatiebasis komt eerder (PR 5b), zodat elke detector-PR candidate recall rapporteert.
- PR 2 is klein, omdat `bronmodel` al canoniek is.

Elke PR bevat de 14 acceptatiepunten uit §36. Elke PR na PR 1 draagt een sectie
"JAS-semantiek gewijzigd: nee/ja (§38-tabel)". Tot PR 12 blijft `legacy` de default in productie.

| PR | Doel | Scope en modules | Contract | Tests | Acceptatie en metrics | Deps | Risico / rollback |
|---|---|---|---|---|---|---|---|
| **1 ADR + baseline** | Vastleggen zonder gedragswijziging | `docs/architectuur/adr-001-hybride-jas-pijplijn.md` (dit plan), `opdracht-jas-annotatiepijplijn.md`, fouttaxonomie, metriekdefinities, `docs/README.md`-verwijzing; baseline-rapport legacy (stabiliteit + ankerset) | geen | docs-links | review; baseline-getallen bewaard | 0 | nul / revert |
| **2 Bron/span-consolidatie** | Eén immutable Span- en CorpusMap-type | `packages/bronmodel`: `Span`, `CorpusMap` (corpus ↔ node-offset, nu gedupliceerd in `bron_annotatie.corpus_segmenten` en `annotatie._lid_segmenten`); graph-qa gebruikt het. Legacy FNV-pad ongemoeid | geen | property-tests (roundtrip offsets, codepoints/emoji, `\n\n`-grenzen) | bestaande suite groen, geen outputdiff op fixtures | 1 | laag / revert |
| **3 Linguïstische abstractie + benchmark** | `LinguisticAnalysis` (UD-vorm) + providers | `jas_pipeline/taal/{model.py,provider.py,spacy_nl.py,stanza_nl.py,null.py}`; benchmarkscript op de 16 dev-casussen + bronteksten.json (clause-, NP- en POS-steekproef handmatig beoordeeld) | geen | providercontract-tests; determinisme (2× zelfde output); degraded-pad | beslisdocument providerkeuze (kwaliteit, licentie, image-omvang, latentie) | 1 | image groeit → optionele extra `nlp`; provider=null |
| **4 Detectieprofielen** | Per klasse het YAML-profiel (§3-velden) | `jas_pipeline/profielen/*.yaml` + loader + drift-test tegen `JAS_KLASSEN` (officiële velden letterlijk, met `H2:NN`) | geen | schema-, drift- en volledigheidstest (13 klassen / 16 begrippen) | jurist-review van confusables en negatieve patronen | 1 | nul |
| **5 Candidate-datamodel** | `Candidate`, `Evidence`, `DetectorResult`, `SpanOption`, `CandidateStatus` | `jas_pipeline/kandidaten.py` (pydantic, frozen) | geen | serialisatie, ID-stabiliteit (id = hash(bron_iri,start,eind)) | — | 2 | nul |
| **5b Eval-basis** | Candidate-metrics + statusveld referenties | `eval/scoring.py` uitbreiden (candidate precision, cand/true, detectorbijdrage, confusion matrix, per-klasse P/R/F1, macro/micro); `referentie_status` in `cases.json`/golden (`fixture/synthetic/silver/provisional/review_pending/adjudicated/gold`); guard: "gold" alleen met adjudicatierecord | eval-formaat | scorer-unit-tests | rapport labelt de referentiestatus | 5 | laag |
| **6 High-confidence detectors** | tijd, plaats, numeriek, operator-lexicon, definitie, delegatie, verwijzing (negatief masker) | `jas_pipeline/detectoren/*` + `regels/*.yaml`; getypeerde WTI-bouwer voor delegatie-invulling in `graph/queries.py` | geen | per regel: positief, negatief, randgeval, overlap (§31); SPARQL-syntax-test | candidate recall per klasse op ankerset + provisional set gerapporteerd | 3,4,5,5b | FP → alleen kandidaten, geen gedrag |
| **7 Syntactische detectors** | subject/object-NP, normatief predicaat, conditionele bijzin, gebeurtenis/nominalisatie, berekening, opsomming, negatie, coördinatie | idem | geen | idem + degraded-parse-tests | candidate recall ≥ gemeten doel (vast te stellen na PR 6); kandidaten per true annotatie | 6 | idem |
| **8 Fusion + specificiteit** | dedup, bewijsaggregatie, overlapgraaf, nesting, PRIORITY-001/002 over overlappende spans, CONSISTENTIE-regels | `jas_pipeline/fusie.py`, `specificiteit.py`; `REGELS` uitbreiden (herbruikt `JASRule`) | geen | offsets nooit gewijzigd (property); IW01-regressie (geen los Parameter binnen Tijdsaanduiding met dezelfde functie) | fusion-foutcode = 0 op fixtures | 6,7 | — |
| **9 Classifier + vlag** | kleine semantische classifier, parallelle route | `jas_pipeline/classificatie.py`, `besluit.py`; `Settings.annotation_pipeline: legacy\|hybrid_v1` (`ANNOTATION_PIPELINE`, supersedeert `ENABLE_KANDIDAAT_SPLITSING` → `legacy_split`); nieuwe node(s) in `annotatieketen()` alleen in de hybrid-tak; temperature 0, enum-toolschema; experiment A (universeel) vs. B (per familie) | `run`-event + `pipeline` | `test_graafopbouw` per tak; schema-afdwinging; model mag geen nieuwe klasse maken | A/B-granulariteit gemeten → keuze vastgelegd | 8,5b | vlag uit = legacy byte-gelijk |
| **10 Coverage accounting** | A: UNHANDLED=0; B: 12 dimensies uitgevoerd/overgeslagen/degraded | `jas_pipeline/dekking.py`; `waarschuwing`/status-event bij ongedekte constituenten | nieuw optioneel eventveld | invariant-tests | geen recallclaim in UI-tekst | 9 | — |
| **11 Validators** | offsets/hash/snapshot/enum/overlap/nesting/status/provenance aanwezig/target geldig | `jas_pipeline/validatie.py` (hergebruikt `bronmodel.valideer_ankers`) | geen | één test per validator + mutatietests | VALIDATION_ERROR zichtbaar in de trace | 9 | — |
| **12 Critic → gerichte reviewer** | alleen conflictitems; geen `ontbrekend`, geen herziener in hybrid | `jas_pipeline/onzekerheid.py`, `review.py`; legacy-Critic ongewijzigd | geen | reviewer kan buiten zijn item niets wijzigen | review% en disagreement gemeten | 10,11 | — |
| **13 Resolver** | transitietabel | `jas_pipeline/resolver.py`; mapping naar aandacht, alternatieven en lifecycle | geen | tabelgedreven tests, elke transitie auditbaar | — | 12 | — |
| **14 SHACL (non-blocking)** | structurele shapes voor de v2-projectie | `api/app/shapes/jas-v2.ttl`, `pyshacl` in api-dev-extra; test op de projectiefixture + diagnostics-endpoint/log | geen | geldige en ongeldige fixture | "RDF geldig / JAS-model geldig / juridisch juist" gescheiden gerapporteerd | 1 | pyshacl alleen dev/CI |
| **15 E2E provenance** | trace per element → Postgres (Element.extra `trace`, Batch.run `pipeline`); optioneel PROV-O in de v2-projectie (Activity/SoftwareAgent, geen personen, geen domain/range) | api: expliciet `trace`-veld in het contract i.p.v. alleen extra; `graaf_projectie_v2` achter vlag | **contractwijziging (additief)** | contract-drift-test, `test_annotatielaag_isolatie`, invarianten "wettekst schoon" | de 16 §40-vragen per element beantwoordbaar (checklisttest) | 11-13 | vlag uit |
| **16 Evaluation harness A/B** | legacy vs. hybrid_v1 op identieke bron | `eval/compare_pipelines.py` (hergebruikt `keten_fixture`, `stabiliteit_analyse`); eval-job-actie; kosten en latentie | — | offline scenario | rapport: kwaliteit, recall, precisie, consistentie, fouttaxonomie, tokens, latentie | 9-15 | — |
| **17 Tuning op fouten** | per foutcategorie gerichte regel-, profiel- of detectorwijziging + regressietest | detectors/profielen, niet de prompt | — | regressietest per fout | geen promptpatch zonder foutcode | 16 | — |
| **18 Legacy removal** | alleen na aangetoonde gelijkwaardigheid op adjudicated set | legacy-nodes, grote prompts | vlag weg | graafopbouw | beslisdocument | 16-17 + mens | — |

---

## 7. Teststrategie
- **Per regel en detector:** positief, negatief, randgeval en overlap (datagedreven:
  testcases in de regel-YAML, één parametrized pytest).
- **Property-tests** (hypothesis, als dev-dep): offsets zijn na fusie nooit gewijzigd;
  `span.tekst == node.tekst[start:eind]`; CorpusMap-roundtrip.
- **Contracttests:** bestaande `test_contract_drift`, `test_graafopbouw` (hybrid-tak apart),
  `test_ontdubbelsleutel`, `test_annotatielaag_isolatie` en `test_methode_drift`, uitgebreid met
  een profiel-drift-test.
- **Determinisme:** de deterministische pijplijn geeft 2× bitgelijke kandidaten. De
  classifier-route wordt met FakeLLM getest. Echte variatie meet PR 16.
- **Regressie:** elke productiefout krijgt een casus met een foutcode uit de taxonomie
  (SOURCE_ERROR … PROJECTION_ERROR) in `tests/fixtures/regressie/`.
- **Legacy-bescherming:** met vlag `legacy` blijft de bestaande suite ongewijzigd groen en is de
  graafvorm identiek.

## 8. Evaluatieplan
1. **Baseline** (PR 1, stabiliteitsbranch): legacy op 16 dev-casussen × 5, en de ankerset × 3.
2. **Kandidaatlaag** (PR 6-8): candidate recall en precisie per klasse, kandidaten per true
   annotatie, detectorbijdrage (leave-one-detector-out), tegen de ankerset (status `silver`) en
   de referentieset (`provisional`). Altijd met het statuslabel erbij.
3. **Classificatie** (PR 9, 16): P/R/F1 per klasse, macro/micro, confusion matrix, exact span en
   partial overlap. Granulariteit A vs. B op dezelfde kandidaten.
4. **Consistentie:** candidate-, class-, span- en set-agreement plus reviewer-disagreement over
   N=5 runs (`stabiliteit_analyse` hergebruiken, fase "hybrid").
5. **Efficiëntie:** calls, in/out/cache-tokens, % deterministische beslissingen, review%,
   human-review%, latentie en kosten.
6. **Annotation recall:** alleen tegen `adjudicated`/`gold`. Dat blokkeert PR 18 en vraagt
   menselijke adjudicatie van de 24 casussen (§10.4).
7. **Beslisvolgorde:** juridische kwaliteit > recall > precisie > reproduceerbaarheid >
   uitlegbaarheid > efficiëntie > kosten.
8. De held-out families (BW6, Omgevingswet) worden nooit gebruikt voor regel- of detectortuning.
   Guard: de detector-testfixtures weigeren deze bronnen.

## 9. Risicoanalyse
| Risico | Impact | Mitigatie |
|---|---|---|
| NLP-kwaliteit op wetstaal (lange zinnen, opsommingen over onderdelen heen) | FN in syntactische detectors | benchmark in PR 3; clause per bronnode; degraded-pad; lexicale detectors blijven onafhankelijk |
| Image-omvang en licentie van het NLP-model | deploy, Trivy, kosten | optionele extra; modelkeuze met licentiecheck; pinned modelversie in provenance |
| Kandidaatexplosie (recall-first) | kosten, reviewlast | meet kandidaten per true annotatie; batch per bronnode; deterministische ACCEPT voor sterk bewijs |
| Classifier mist context (alleen venster) | classificatiefouten | context = hele bronnode + aanhef-ouder; CONTEXT_ERROR als foutcode |
| Spanopties dekken de gewenste grens niet | SPAN_ERROR | "geen passende optie" → HUMAN_REVIEW, nooit vrije tekst; optie-generatoren tunen in PR 17 |
| Verlies van de recall die de Critic nu via "ontbrekend" levert | FN | dekkingsanalyse + ongedekte constituenten als kandidaten; A/B meet dit expliciet |
| Structured output niet ondersteund via Foundry | parsefouten | schema-validatie + één herhaalpoging → UNCERTAIN; gemeten |
| Geen gold → geen bewijs van verbetering | legacy-verwijdering onmogelijk | PR 18 hangt aan adjudicatie; tot dan parallel |
| Contract- en projectiewijziging (PR 15) raakt de rdfsplus-invarianten | vervuilde wettekst | additief; bestaande isolatietests; PROV achter vlag |
| Drie ontdubbel-implementaties | driftende identiteit | kandidaat-ID (offsets) staat los van `sleutel_van`; emit gebruikt ongewijzigd `sleutel_van` |

## 10. Openstaande inhoudelijke beslissingen (voor de gebruiker/jurist)
1. **16 vs. 13:** blijven de samengevoegde labels, met een machineleesbaar `jas_subtype` erbij
   (aanbevolen, additief)? Of worden de officiële 16 begrippen eigen labels (contract-, frontend-
   en kleurwijziging)?
2. **Delegatie-invulling:** mag die structureel uit de WTI-grondslagen in de graaf worden
   afgeleid (deterministisch)? Of blijft het een tekstuele annotatie?
3. **NLP-runtime in het graph-qa-image:** acceptabel (±50-500 MB, afhankelijk van de provider)?
   Of een aparte NLP-sidecar?
4. **Adjudicatie:** wie beoordeelt de 24 referentiecasussen, en met welke procedure (1 of 2
   beoordelaars, adjudicatierecord)? Zonder die stap blijft annotation recall onmeetbaar en kan
   PR 18 niet.
5. **Deterministisch ACCEPTED zonder LLM** (bijvoorbeeld een concrete datum → Tijdsaanduiding):
   mag dat als "voorgesteld/groen" naar de jurist? Of moet elke klasse minimaal één
   classifier-bevestiging hebben?
6. **Automatische rode correcties:** rood+vervang wordt in hybrid niet meer automatisch
   uitgevoerd (dat wordt HUMAN_REVIEW). Is die gedragswijziging akkoord?
7. **Temperatuur 0** ook voor de legacy-route (los meetbare kleine winst in reproduceerbaarheid)?
   Of legacy onaangeroerd laten als zuivere baseline? Aanbevolen: onaangeroerd.

## 11. Validatie van het plan (§42 stap 7)
- Alle JAS-klassen: 13 paragrafen en 16 begrippen in profielen en matrix (§2, §5); het subtype
  lost het verlies van de officiële 16 op.
- Herkenningsvragen en uitdrukkingswijzen: letterlijk in de profielen met `H2:NN`, vertaald naar
  signalen (§2-tabel) en gedrift-test.
- Grammatica als detectiemiddel: detectors maken alleen kandidaten met `possible_classes`;
  de classificatie is een aparte stap (§4).
- Candidate recall meetbaar (PR 5b/6); annotation recall later meetbaar (statusmodel,
  adjudicatie §10.4).
- Modelverantwoordelijkheid kleiner: geen ontleding, offsets, spans, dekking of regels meer; alleen
  enum-keuzes op ID's. Prompts kleiner: per kandidaat alleen het confusable-profiel.
- Critic begrensd: alleen conflictitems, vaste acties, resolver in code.
- Deterministische SPARQL blijft: alleen getypeerde bouwers.
- Provenance intact en uitgebreid (PR 15); bestaande `run`/`prompt_hash`/`methode_versie` blijven.
- Bestaande architectuur gerespecteerd (§1.3).
- Legacy en nieuw objectief vergelijkbaar: vlag en PR 16 op identieke fixture.

---

## 12. Fouttaxonomie

Elke analysefout en elke regressie krijgt precies één primaire categorie. De categorie hoort bij
de eerste stap waar het misging, niet bij de stap waar het zichtbaar werd.

| Code | Stap | Voorbeeld |
|---|---|---|
| `SOURCE_ERROR` | bron/snapshot | verkeerde bronversie, hash klopt niet, node ontbreekt |
| `SEGMENTATION_ERROR` | segmenten/CorpusMap | onderdeel aan verkeerd lid, `\n\n`-grens verschoven |
| `PARSER_ERROR` | linguïstische analyse | bijzin niet herkend, verkeerde dependency-kop |
| `DETECTOR_ERROR` | detector/regel | regel matcht niet op een bedoeld patroon, of juist wel op een negatief patroon |
| `CANDIDATE_MISSED` | kandidaatgeneratie | echt element zonder enige kandidaat |
| `CANDIDATE_FALSE_POSITIVE` | kandidaatgeneratie | kandidaat die structureel nooit een element kan zijn (bv. lidnummer) |
| `FUSION_ERROR` | fusie/specificiteit | bewijs verloren, nesting weggevallen, verkeerde voorrang |
| `CLASSIFICATION_ERROR` | classifier/besluit | juiste span, verkeerde klasse |
| `SPAN_ERROR` | spanopties/keuze | juiste klasse, verkeerde grens |
| `CONTEXT_ERROR` | classifier-invoer | benodigde aanhef of ander lid ontbrak in de context |
| `VALIDATION_ERROR` | validators | ongeldig element doorgelaten, of geldig element geweigerd |
| `REVIEW_ERROR` | gerichte reviewer | onjuist KEEP/CHANGE op een conflictitem |
| `RESOLUTION_ERROR` | resolver | transitie in strijd met de tabel of met een JAS-regel |
| `PROJECTION_ERROR` | api/RDF | projectie wijkt af van Postgres, SHACL-schending |

Voor de legacy-route bestaan niet alle stappen. Daar vallen fouten onder `CLASSIFICATION_ERROR`,
`SPAN_ERROR`, `CANDIDATE_MISSED` (het element ontbreekt) of `REVIEW_ERROR` (de Critic). Dat
verschil is zelf een bevinding: de legacy-route kan een fout niet verder herleiden.

## 13. Metriekdefinities

Drie dekkingsbegrippen die nooit door elkaar gebruikt worden (opdracht §22):

- **Candidate processing coverage (A):** aandeel gegenereerde kandidaten met eindstatus
  `ACCEPTED | REJECTED | UNCERTAIN | HUMAN_REVIEW`. Doel is 100 %: `UNHANDLED = 0` is een
  invariant, geen streefwaarde.
- **Structural detection coverage (B):** per bronnode welke van de twaalf detectiedimensies
  (actor, object, normatieve relatie, handeling/gebeurtenis, voorwaarde, berekening/afleiding,
  waarde, operator, tijd, plaats, delegatie, definitie) zijn uitgevoerd, overgeslagen of
  gedegradeerd.
- **Annotation recall (C):** aandeel referentie-annotaties dat is gevonden, uitsluitend gemeten
  tegen referenties met status `adjudicated` of `gold`. Tegen `silver`/`provisional` heet dezelfde
  berekening **ankerdekking** en wordt ze altijd met die status gerapporteerd.

Matching: een **exacte match** betekent dezelfde bron-IRI, dezelfde offsets en dezelfde klasse.
Een **partiële match** betekent span-IoU > 0 met dezelfde klasse; dat is diagnose, geen correcte
annotatie. Per klasse worden precisie, recall en F1 gerapporteerd, plus het macro- en
micro-gemiddelde en een confusion matrix. Precisie tegen een ankerset is geen kwaliteitsoordeel
(zie `tools/graph-qa/CLAUDE.md` §Tests & eval).

Referentiestatus, machineleesbaar: `fixture` (technische testdata), `synthetic` (geconstrueerd),
`silver` (conceptankers, bv. `golden_annotatie.jsonl`), `provisional` (conceptdossier, bv.
`referentieset/cases.json`), `review_pending`, `adjudicated` (menselijke adjudicatie vastgelegd),
`gold` (adjudicated plus een vastgelegde validatieprocedure). Op 24-09-2026 heeft geen enkele
referentie in deze repo de status `adjudicated` of `gold`.

## 14. Baseline

De legacy-baseline wordt gemeten met de instrumentatie van `feat/stabiliteitsbenchmark`
(`eval/stabiliteit.py`, 16 ontwikkelcasussen × 5) en met de eval-job (`run_eval --annotatie`,
3 runs). Die meting kost modelaanroepen en is op de datum van dit document **nog niet
uitgevoerd**. De uitkomst komt als bijlage bij dit ADR, met model, temperatuur (providerdefault),
`prompt_hash` en `methode_versie` erbij.

**Gemeten op 25 sep 2026:** zie [metingen/2026-09-25-ab-legacy-hybrid.md](metingen/2026-09-25-ab-legacy-hybrid.md)
(legacy tegen hybrid_v1, vóór en ná PR 17).
