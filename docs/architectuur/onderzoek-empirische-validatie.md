# Onderzoeksontwerp: empirische juridische validatie van hybrid_v1

Soort: *technisch ontwerpdocument* · Stand: master `508e8ec` (25 sep 2026) · Status: **concept, geen
implementatie** · Vervolg op ADR-001 (§12 fouttaxonomie, §13 metrieken, §15 stand van uitvoering)

> Dit document bouwt geen semantische architectuur. Het legt vast wat we nu **weten**, wat we
> **vermoeden** en hoe we het verschil gaan meten. Stabiliteit, technische validiteit,
> modelconsensus en coverage zijn hier nooit een maat voor juridische juistheid.

---

## 0. Samenvatting

**Waar zit volgens het huidige bewijs de belangrijkste foutbron?** *Vóór* de classifier: in de
**kandidaatruimte** die detectie en fusie aanbieden. Drie mechanismen komen in alle bekeken traces
terug:

1. **Generieke naamwoordgroepen.** Elk nominaal token wordt via `SUBJECT_NP`/`OBJECT_NP`/`ENUMERATED_NP`
   een kandidaat met drie juridische klassen. Er is geen toets op het predicaat, ook al heet de regel
   `…np_bij_normatief_predicaat`.
2. **Fusie zonder bewijs per klasse.** Zwak syntactisch bewijs wordt gelijkwaardig aan sterk
   patroonbewijs. Het blokkeert daarmee de deterministische route.
3. **Een kandidaatruimte die de juiste lezing niet bevat.** "als" in een vergelijking biedt alleen
   Voorwaarde aan; "de dag" en "de kalendermaand" bieden geen Tijdsaanduiding.

Het classifier-contract versterkt dit. **De enum in het toolschema is de unie over de hele batch.**
In de trace van Leidraad Invordering (LI) §9.5 zijn **12 van de 12** HUMAN_REVIEW-gevallen technisch
van aard, en geen enkel geval is juridische twijfel:

- **9 gevallen:** het model koos precies de klasse die de JAS-voorrangsregel op die kandidaat had
  weggehaald (Variabele op "één maand" en "zes weken").
- **3 gevallen:** het model koos Tijdsaanduiding voor een kandidaat die die klasse niet kreeg
  aangeboden.

Ook de gerichte reviewer faalde daarna in alle 12 gevallen (`R-ONGELDIG`). Wat hij antwoordde is niet
bewaard.

**Wat nog niet vaststaat:** of deze fouten *juridisch* domineren. Er bestaat geen enkele
`adjudicated` referentie. De huidige cijfers zeggen iets over mechanismen, niet over juistheid.
Daarom gaan de eerste zeven PR's over validatie (V1–V7) en niet over nieuwe semantiek.

---

## 1. Bewijsbronnen en hun grenzen

| id | bron | wat het is | beperking |
|---|---|---|---|
| **C** | code op `508e8ec` | `tools/graph-qa/agent/jas_pipeline/*`, `eval/*`, api-projectie | mechanisme, geen frequentie |
| **M** | `docs/architectuur/metingen/2026-09-25-ab-legacy-hybrid.md` | 16 ontwikkelcasussen × 3, tegen de `provisional` referentie | referentie niet beoordeeld; recall = *ankerdekking* |
| **T1** | export art. 9 lid 1 IW 1990, run 13:08 | 6 kandidaten, 5 geaccepteerd, alles via het model | vóór #522 |
| **T2** | export art. 9 lid 1 IW 1990, run 14:04 | 6 kandidaten, 5 geaccepteerd | ná #522 |
| **T3** | export art. 9 lid 5 IW 1990, run 12:33Z | 39 kandidaten: 3 regel, 36 model, 28 geaccepteerd, 11 afgewezen, 0 twijfel | één run |
| **T4** | export LI 2008 §9.5, run 12:50Z | 45 kandidaten: 0 regel, 45 model, 31 geaccepteerd, 2 afgewezen, 12 HUMAN_REVIEW | één run |
| **P** | `docs/wetsanalyse/referentieset/cases.json` | 24 conceptgevallen, 116 conceptmarkeringen, 6 wetsfamilies | alles `provisional` |

Voor alle vier de traces geldt dezelfde run-configuratie:

| instelling | waarde |
|---|---|
| model | `claude-sonnet-4-6` via Azure Foundry |
| classifier-granulariteit | `universeel` |
| spankeuze | uit |
| temperatuur | providerdefault |
| gerichte review | aan |
| taalmodel | `nl_core_news_md-3.8.0` |
| `agent_versie` | `0.1.0` (`AGENT_VERSION` niet gezet) |
| `methode_versie` | `4fda12e4bc9a` |
| `prompt_hash` | `97ae4ea7f557` |

**Belangrijke beperking van de traces.** Een export bevat alleen elementen die zijn **geaccepteerd**
of op **HUMAN_REVIEW** staan. Van afgewezen kandidaten ziet de api alleen de telling (`per_status`).
Hun beslissingen gaan in `nodes/annotatie.emit` wel mee in de agent-state
(`analyse.beslissingen`), maar worden niet naar de api doorgestuurd. Twee dingen zijn daardoor op
productiedata **niet te meten**: model-afwijzingen bij sterk bewijs (H6) en beslisstabiliteit per
kandidaat (§13). Dit gat heeft een eigen prioriteit in V4.

Oordelen in dit document zijn één van vier soorten:

- **B:** bewezen uit code of test;
- **W:** waargenomen in een trace (n = 1 run);
- **A:** afgeleid (tegenfeitelijk uit de code);
- **O:** onbekend.

---

## 2. Repository-baseline

### 2.1 Keten zoals hij draait (`keten.analyseer`)

De stappen, in volgorde:

1. **Bronsegmenten:** snapshot met SHA-256 per node.
2. **Taalanalyse:** spaCy `nl_core_news_md`; zonder parse gedegradeerd, en dat staat zichtbaar in de
   meting.
3. **Detectoren**, 15 in totaal:
   - 8 regelfamilies uit YAML: tijd, voorwaarde, operator, afleiding, numeriek, delegatie,
     subject, plaats;
   - 2 structuurdetectoren: definitie en betekenis;
   - 5 syntactische: norm, naamwoordgroep, bijzin, nominalisatie, logisch.
4. **Fusie:** ontdubbelen op (bron, start, eind) en `possible_classes` en `evidence` samenvoegen.
5. **Specificiteit:** JAS-PRIORITY-001/002 over kandidaten heen.
6. **Labelen** in bronvolgorde.
7. **Deterministisch besluit:** alleen bij precies één klasse én bewijs dat volledig ⊆ `STERK_BEWIJS`
   is.
8. **Classifier:** één batch, één aanroep, strict tool.
9. **Toets per kandidaat.**
10. **Voorstellen**, met ontdubbelen op (grens, klasse).
11. **Validatie:** `V_*` en `W_ZELFDE_SPAN`.
12. **Onzekerheid:** vier redenen.
13. **Gerichte reviewer**, op drie van die redenen.
14. **Resolver:** een vaste tabel.
15. **Hervalidatie.**
16. **Meting:** dekking A/B en fasen.
17. **Api:** Postgres, projectie naar RDF/OA/PROV/SKOS, SHACL en graafcontrole.

### 2.2 Laagtabel

| Laag | Verantwoordelijkheid | Bekende risico's | Bestaande tests | Bestaande metrics | Ontbrekende metrics |
|---|---|---|---|---|---|
| Bronmodel | canonieke tekst, hash, ankers per bronnode | beleidsregel met voorbeeldtekst (LI §9.5) wordt geannoteerd als norm | `test_bronmodel*`, ankervalidatie in api | geen | `source_status` per casus |
| Segmentatie | segmenten, CorpusMap, leden/subdivisies | lidprefix, containerbepalingen | `test_artikel`, CorpusMap-tests | geen | segmentfouten per casus |
| Language provider | UD-parse, gedegradeerd zichtbaar | lange zinnen verkeerd geparsed: art. 9 lid 5 heeft ROOT="overblijven" en "invorderbaar"=parataxis | `test_taal*`, `taal_benchmark.py` | gedegradeerd ja/nee | parserfout per gold-element |
| Detectoren (regels) | lexicale/juridische patronen, regel-id, versie, 4 testsoorten | te brede rechtse uitbreiding over een nevenschikking heen (T3 C024) | `test_detectoren.py` (positief/negatief/rand/overlap per regel) | `kandidaat_eval`: ankerdekking | FP-rate per regel, spanfout per regel |
| Detectoren (syntactisch) | NP-, bijzin-, norm-, nominalisatie- en operatorkandidaten | elk nominaal token wordt een kandidaat met 3 klassen; "als" in een vergelijking wordt voorwaarde | `test_syntactische_detectoren.py` | geen | aandeel generieke kandidaten, FP-rate per code |
| Kandidaatmodel | span + `possible_classes` + `evidence`; stabiel id | bewijs niet per klasse | `test_kandidaatmodel.py` | aantal kandidaten | kandidaten per gold-element |
| Fusie | ontdubbelen, relaties `bevat`/`overlapt` | vlakke unie van klassen en bewijs | `test_fusie.py` | geen | klassen-inflatie door fusie |
| Specificiteit | JAS-PRIORITY over kandidaten heen | weggehaalde klasse blijft in de batch-enum staan | `test_fusie.py`/specificiteit | `PRIORITY_APPLIED` in het spoor | conflict tussen regel en model |
| Deterministisch besluit | voorstel zonder model bij eenduidig sterk bewijs | centrale whitelist, geblokkeerd door fusie met zwak bewijs | `test_hybride_keten.py` | `deterministisch` | geblokkeerd-deterministisch |
| Classifier-schema | strict tool, enum op label/beslissing/optie | enum = batch-unie (H11) | `test_hybride_keten.py` (ongeldige klasse → UNCERTAIN) | `llm_calls` | ongeldige keuze, leakage, contractfoutratio |
| Classifier-batching | universeel of per familie | onderlinge beïnvloeding (H9) | granulariteitstest | geen | vergelijking universeel/familie/per-kandidaat |
| Classifier-validatie | toets per kandidaat → UNCERTAIN met reden | contractfout wordt later "twijfel" | idem | reden in het spoor | uitsplitsing per reden |
| Onzekerheid | 4 redenen uit waarneembare signalen | ziet zwakke acceptaties en model-afwijzingen niet (H5, H6) | `test_review_resolver.py` | `twijfels` | gemiste twijfel (tegen gold) |
| Reviewer | KEEP/CHANGE/HUMAN per twijfelgeval | enum = unie over de twijfels; ongeldige uitvoer wordt niet bewaard | `test_review_resolver.py` | `review_calls` | reviewer-contractfouten, KEEP/CHANGE juist |
| Resolver | vaste tabel, voorrangsregel | `R-ONGELDIG` maskeert de oorzaak | `test_review_resolver.py` | `resolutie` | resolutiefout tegen gold |
| Validatie | `V_*`-fouten, `W_ZELFDE_SPAN` | geen | `test_validatie.py` | `validatie` | geen |
| Dekking | A (verwerkt), B (dimensies + ongedekt) | B ≠ recall | `test_dekking.py` | per_status, structureel | geen (bewust) |
| Evaluatie | `compare_pipelines`, `metrieken`, `stabiliteit_analyse` | taxonomie van 3 codes; geen classifier-contract; ref `provisional` | `test_eval_metrieken.py`, `test_stabiliteit_analyse.py` | P/R/F1, IoU, exacte span, stabiliteit | zie §7 |
| Profielen | 13 klassen, H2-verwijzingen, begrippen, `candidate_rules` | koppeling regel → sterkte zit in Python, niet in het profiel | `test_detectieprofielen.py` | geen | geen |
| Verklaringen | leesbare naam per code | geen | `test_verklaringen.py` | geen | geen |
| RDF/PROV/SKOS | projectie schema 3, vocabulaire | geen juridische betekenis | `test_graaf_rijk.py` e.a. | geen | geen |
| SHACL/graafcontrole | structuur, isomorfie, invarianten | SHACL-conform ≠ juridisch juist | `test_graafcontrole.py` | `annotatie_graaf_afwijking` | geen |
| Persistentie | lagen, elementen, audit, dekking | afgewezen beslissingen niet bewaard | api-suite | per_status | beslissing per kandidaat |

---

## 3. Classifier-contract en batchschema

### 3.1 Wat de code doet (B)

In `classificatie.toolschema()`:

```python
beslissingen = sorted({b for k in kandidaten for b in k.toegestane_beslissingen()})
"beslissing": {"type": "string", "enum": beslissingen}
```

De enum op `beslissing` is de **unie over alle kandidaten in de batch**. De docstring zegt dat ook
("de enum is de unie over alle kandidaten, de toets is per kandidaat"). `strict: true` garandeert
dus alleen dat het model een klasse kiest die *ergens in de batch* mag, niet dat hij bij *deze*
kandidaat mag.

Wat er daarna gebeurt:

- `valideer()` maakt van een ongeldige keuze `UNCERTAIN` met `CLASSIFIER_ONGELDIGE_KLASSE:<klasse>`;
- `onzekerheid.signaleer()` vertaalt dat naar de twijfelreden `CLASSIFIER_ABSTAIN`;
- de reviewer krijgt het geval voorgelegd;
- de resolver maakt er `HUMAN_REVIEW` van, met als voorstel de eerste mogelijke klasse.

Een technische contractfout eindigt zo als een gele kaart die de jurist leest als "juridische
twijfel".

De reviewer heeft **hetzelfde patroon**: `review._schema()` gebruikt als enum op `klasse` de unie van
`huidig` en `alternatieven` over alle twijfels. Een CHANGE naar een klasse die voor dít geval niet
in `alternatieven` staat, wordt `geldig=False` en in de resolver `R-ONGELDIG`. `Oordeel.actie` wordt
dan overschreven met `HUMAN_REVIEW`. **Wat de reviewer werkelijk antwoordde, gaat verloren.**

### 3.2 Wat T4 (LI §9.5) laat zien (W)

| label | span | toegestaan (na specificiteit) | model koos | oorsprong van de gekozen klasse |
|---|---|---|---|---|
| C003, C004, C009, C011, C014, C016, C031, C033, C043 | "één maand", "zes weken", "een maand" | Tijdsaanduiding, Rechtsobject, Rechtssubject | **Variabele** | door `JAS-PRIORITY-001` bij deze kandidaat weggehaald; staat nog in de batch-enum via andere NP-kandidaten |
| C029 | "de kalendermaand" | Rechtsobject, Variabele, Rechtssubject | **Tijdsaanduiding** | geen temporeel bewijs op deze span; komt uit de batch-enum |
| C034 | "de dag die hetzelfde nummer heeft als dat van de dagtekening" | Voorwaarde, Rechtssubject, Rechtsobject | **Tijdsaanduiding** | idem |
| C035 | "de dag" | Rechtsobject, Variabele, Rechtssubject | **Tijdsaanduiding** | idem |

Wat eruit volgt:

- **12 van 12 HUMAN_REVIEW-gevallen zijn contractfouten.** Geen enkel geval is een substantieve
  juridische twijfel.
- **Twee oorzaken zitten onder dezelfde foutcode:**
  - **9 gevallen (type A):** conflict tussen een JAS-regel en het model. Het model wil een klasse die
    JAS-PRIORITY-001 hier uitsluit; volgens JAS is Tijdsaanduiding juist. Het batchschema maakt die
    ongeldige keuze mogelijk.
  - **3 gevallen (type B):** de kandidaatruimte ontbreekt. Het model ziet een tijdsaanduiding die
    geen detector aanbood ("de dag", "de kalendermaand"). Dit is eerder een DETECTOR_ERROR /
    POSSIBLE_CLASS_ERROR (H13) die zich als contractfout voordoet.
- **De reviewer faalde 12 van 12 keer** (`R-ONGELDIG`). Of hij geen tool-aanroep deed of per geval
  een klasse buiten de alternatieven koos (dezelfde lekstroom), valt niet te zeggen (O). Het
  mechanisme maakt het tweede aannemelijk (A).
- **Tegenfeitelijk (A):** voor de 9 gevallen van type A had de deterministische route gegolden als
  de fusie geen `OBJECT_NP` had toegevoegd. Het bewijs was dan alleen `TEMPORAL_DURATION` geweest,
  met één klasse. Er was dan geen modelkeuze en geen HUMAN_REVIEW geweest (zie H1/H4).

In T3 (art. 9 lid 5) zijn er 0 ongeldige keuzes, en in T1/T2 ook. **Leakage treedt dus niet overal
op.** Het vraagt een batch waarin de unie een klasse bevat die bij een kandidaat net is weggehaald
of ontbreekt. Hoe vaak dat gebeurt, is onbekend (O) en wordt in V5 gemeten.

### 3.3 Ontwerpruimte (niet besloten; alleen ter meting in V5)

| optie | wat | voordeel | nadeel/risico |
|---|---|---|---|
| a. per-kandidaat-schema | `oneOf`/discriminated union per label met eigen enum | contract sluit leakage uit | schemagrootte groeit lineair; *verbergt* type-A-conflicten, die dan als "gekozen uit toegestaan" verschijnen |
| b. constrained sub-batches | batch per identieke `toegestane_beslissingen` | enum per batch klopt precies | meer aanroepen; batchcontext wisselt |
| c. familie-batches | bestaat al (`familie`) | geen code nodig | familie = eerste klasse; unie blijft binnen de familie |
| d. contractfout apart rapporteren | nieuwe reden `CLASSIFIER_CONTRACT_ERROR` naast `CLASSIFIER_ABSTAIN` | reviewload eerlijk; geen schemawijziging | lost de fout niet op |

Beslispoort (§15): **d** is een meetvoorziening en hoort in V5. **a** en **b** komen pas na de
V7-baseline, en alleen als het contractfoutpercentage daar materieel blijkt.

---

## 4. Toetsing H1–H13

| # | hypothese | oordeel | bewijs (soort) |
|---|---|---|---|
| H1 | same-span-fusie maakt bewijs uit verschillende hypothesen gelijkwaardig | **BEVESTIGD** (mechanisme) | C, W |
| H2 | `possible_classes` onvoldoende gekoppeld aan bewijs per klasse | **BEVESTIGD** (mechanisme) | C, W |
| H3 | generieke SUBJECT/OBJECT_NP levert kandidaten die pas via het predicaat betekenis krijgen | **BEVESTIGD** (mechanisme en volume); juridische schade **O** | C, W |
| H4 | deterministisch besluit te beperkt door centrale whitelist | **BEVESTIGD** | C, W, A |
| H5 | onzekerheid mist beslissingen op alleen zwak bewijs | **BEVESTIGD** (mechanisme); hoeveel daarvan fout is **O** | C, W |
| H6 | model-afwijzing bij sterk bewijs verdwijnt zonder conflictstatus | **GEDEELTELIJK BEVESTIGD**: mechanisme B, frequentie niet meetbaar | C |
| H7 | detector-spanfouten niet apart gemeten | **BEVESTIGD** | C, W |
| H8 | relationele structuren niet first-class | **BEVESTIGD** (structureel); juridische impact **O** | C, W |
| H9 | universele batch beïnvloedt beslissingen tussen kandidaten | **GEDEELTELIJK BEVESTIGD**: leakage is een vorm van beïnvloeding; "herding" niet bewezen | C, W |
| H10 | technisch stabieler/uitlegbaarder zonder aantoonbaar juridisch beter | **BEVESTIGD** (in de zin: *niet aantoonbaar*) | M, P |
| H11 | batchbrede enum veroorzaakt cross-candidate leakage | **BEVESTIGD** (mechanisme B, voorkomen W: 12/45 in T4); frequentie over casussen **O** | C, W |
| H12 | connectieven te oppervlakkig | **BEVESTIGD** voor "als" (W, T4 C037); "of"/"en" **ONVOLDOENDE BEWIJS** | C, W |
| H13 | detector biedt al de verkeerde kandidaatruimte | **BEVESTIGD** | C, W |

### H1: same-span-fusie

- **(B)** `fusie._samen` neemt de unie van `possible_classes` en `evidence`. De volgorde komt uit het
  eerste bewijs. `Evidence` heeft geen klasse- of sterkteveld.
- **(W, T2 C003)** "zes weken na de dagtekening van het aanslagbiljet" draagt `TEMPORAL_DURATION` +
  `OBJECT_NP` + `NOMINALIZED_ACTION` met vijf klassen: Tijd, Robj, Rsubj, Rfeit, Voorwaarde. Het
  patroonbewijs voor één termijn staat gelijk aan twee generieke syntactische signalen.
- **(W, T4)** 10 kandidaten met sterk temporeel bewijs gingen naar het model, doordat de fusie met
  `OBJECT_NP` ze meerdere klassen gaf.

### H2: possible_classes zonder bewijs per klasse

- **(B)** Er bestaat geen koppeling van bewijs naar klasse. Uit `possible_classes` valt niet af te
  leiden wélk bewijs Rechtssubject draagt.
- **(W, T4 C003)** Rechtsobject en Rechtssubject blijven op "één maand" staan, uitsluitend omdat
  `OBJECT_NP` ze meebracht. In de prompt ziet het model ze naast Tijdsaanduiding als gelijkwaardige
  opties.

### H3: generieke NP-kandidaten

- **(B)** `NaamwoordgroepDetector._classificeer_signaal` maakt van elk nominaal token:
  - onderwerp → [Rsubj, Robj, Var];
  - nevenschikking → [Robj, Rsubj, Var];
  - al het overige → [Robj, Var, Rsubj].

  De regel heet `jas.object.np_bij_normatief_predicaat`, maar een normatief predicaat wordt niet
  getoetst.
- **(W)** Aandeel model-acceptaties dat uitsluitend op SUBJECT/OBJECT/ENUMERATED_NP rust:

  | trace | aandeel | uitkomst |
  |---|---|---|
  | T2 | 2/4 | Rechtsobject |
  | T3 | 15/25 | 7 Rechtsobject, 8 Variabele |
  | T4 | 23/31 | 21 Rechtsobject |

  In T4 staan "de betalingstermijn" 6×, "de dagtekening" 6× en "de termijn" 4× als Rechtsobject.
- **(O)** Of dat juridisch fout is, is een adjudicatievraag. In T3 kreeg dezelfde "de dagtekening"
  wél Variabele. Dat wijst op contextgevoeligheid óf op willekeur; alleen gold kan dat scheiden.

### H4: centrale whitelist

- **(B)** `besluit.STERK_BEWIJS` is één frozenset in Python. Een regel is alleen deterministisch als
  **al** zijn codes ⊆ `STERK_BEWIJS` zijn **en** er precies één klasse is. Rule-YAML kent geen veld
  `deterministic` of `evidence_strength`. `onzekerheid.KLASSE_VAN_BEWIJS` moet met een assert gelijk
  lopen met die set.
- **(W)**
  - T4: 0/45 deterministisch, terwijl 10 kandidaten `TEMPORAL_DURATION`/`TEMPORAL_RELATIVE_PERIOD`
    dragen.
  - T3: 3/39.
  - T1/T2: 0/6, terwijl "zes weken na …" `TEMPORAL_DURATION` draagt.
- **(A)** De blokkade komt door de fusie (H1), niet door de regel zelf.

### H5: onzekerheid te smal

- **(B)** `signaleer` markeert een geaccepteerde modelbeslissing alleen bij één van twee dingen:
  1. sterk bewijs voor een *andere* klasse (DETECTOR_CONFLICT);
  2. een gedegradeerde parse.

  Een acceptatie op alleen generiek bewijs komt nooit in aanmerking. REJECTED door het model
  evenmin.
- **(W, T3)** 36 modelbeslissingen, waarvan 15 acceptaties op alleen generiek bewijs, leveren
  0 twijfels op.

### H6: afwijzing bij sterk bewijs

- **(B)** `signaleer` slaat over wat niet ACCEPTED is (`if b.status is not ACCEPTED … continue`).
  Een model dat "Geen annotatie" kiest voor een kandidaat met `TEMPORAL_DATE` of `COMPARISON` levert
  géén twijfel op.
- **(O)** Hoe vaak dat gebeurt, is op productiedata niet te zien: afgewezen beslissingen worden niet
  naar de api gestuurd (§1). Dat komt neer op 11 onbekende afwijzingen in T3 en 2 in T4.

### H7: spanfouten niet apart gemeten

- **(B)** `compare_pipelines._foutcategorie` kent drie uitkomsten:
  - `CLASSIFICATION_ERROR`;
  - `SPAN_ERROR`: overlap met dezelfde klasse, ongeacht of de detector de grens bepaalde of de keuze;
  - `CANDIDATE_MISSED`.

  Er is geen onderscheid tussen te breed en te smal, en geen `DETECTOR_SPAN_ERROR`.
- **(W, T3 C024)** Een deterministisch geaccepteerde Tijdsaanduiding "één maand na de dagtekening van
  het aanslagbiljet en elk van de volgende termijnen" is te breed: de rechtse uitbreiding van de regel
  loopt over "en" heen. Omdat hij deterministisch is, kijkt geen enkele latere stap ernaar.

### H8: relationele structuur

- **(B)** De fusie kent als relaties alleen `bevat`/`overlapt`, zonder betekenis. Er is geen
  operand-, afleidings-, vergelijkings-, norm- of drager-relatie. Een Operator is een losse span.
- **(W, T3)** "invorderbaar in zoveel gelijke termijnen als er na de maand … nog maanden van het jaar
  overblijven" is een afleiding: *aantal termijnen = aantal resterende maanden*. Dat levert op:
  - geen Afleidingsregel-kandidaat;
  - geen operator voor "zoveel … als";
  - losse Variabelen ("zoveel gelijke termijnen", "nog maanden");
  - een Operator "meer dan" zonder operanden;
  - 33 geneste paren zonder functierelatie.
- **(O)** Of de *jurist* deze relaties nodig heeft voor activiteit 2, is een scopevraag. JAS
  activiteit 2 markeert en classificeert; relaties zijn activiteit 3+. Dat moet vóór een eventuele
  DerivationFrame worden beslist (§15).

### H9: batchbeïnvloeding

- **(B/W)** Leakage (H11) is aantoonbaar een vorm van beïnvloeding tussen kandidaten.
- **(W)** Binnen één batch zijn identieke spans uniform:
  - "de dagtekening" is in T4 6/6 Rechtsobject;
  - tussen batches verschilt het: in T3 Variabele.

  Dat past bij batch-herding, maar ook bij contextgevoeligheid. Zonder vergelijking tussen
  universeel, familie en per-kandidaat op dezelfde casussen is dit **O**.

### H10: technisch beter ≠ juridisch beter

- **(M)**
  - Ankerdekking: 47 → 84%.
  - Exacte span: 52 → 88%.
  - Precisie vlak: 34 → 35%.
  - Precisie alleen onbetwist: 48 → 35%, dus *slechter*.
  - Rechtsobject-F1: 21%.

  De referentie is provisional (P) en niet beoordeeld. Juridische superioriteit is **niet
  aantoonbaar**, en ook geen inferioriteit.

### H11: cross-candidate leakage

Zie §3. Het mechanisme is bewezen in `toolschema()` en in `review._schema()`. Het effect is
waargenomen: 12/45 kandidaten in T4, 100% van de HUMAN_REVIEW. De bestaande test
(`test_ongeldige_of_ontbrekende_beslissing_wordt_onzeker_met_reden`) bewaakt de *afvang*, niet de
*frequentie*.

### H12: connectieven

- **(B)** `BijzinDetector` neemt "als" als `mark` onder een bijzin (`advcl` e.a.) en maakt er
  `CONDITIONAL_CLAUSE` met alleen [Voorwaarde] van. Er is geen toets op vergelijking ("hetzelfde … als",
  "zoveel … als", "anders … dan") of hoedanigheid.
- **(W, T4 C037)** "als dat van de dagtekening": spaCy geeft `als`=mark, kop "dat"=advcl. Dit is een
  vergelijking (*hetzelfde nummer als dat van*), maar werd geaccepteerd als Voorwaarde, zonder
  alternatief. De regeldetector voor `voorwaardelijke_bijzin` laat "als" bewust weg (commentaar in
  `voorwaarde.yaml`); het lek zit in de syntactische detector.
- **(O)** Of "en"/"of" als operator overschieten, is niet waargenomen. `LogischeOperatorDetector` v2
  eist sinds PR 17 nevenschikking op clauseniveau. "dan wel" komt uit `jas.operator.logisch`
  (T4 C022 Operator); of dat juist is, is een adjudicatievraag (zie AWB02: "dan wel is niet zonder
  context een exclusieve…").

### H13: verkeerde kandidaatruimte

- **(W)** De detectoren bieden bij deze gevallen niet de juiste lezing aan:
  - **T4 C037:** alleen Voorwaarde aangeboden. De juiste lezing (vergelijking, Operator of geen
    element) kan het model alleen via "Geen annotatie" benaderen.
  - **T4 C029/C035:** geen Tijdsaanduiding aangeboden; het model probeert het toch (contractfout).
  - **T3 C024:** de detector levert een te brede span die deterministisch doorgaat.
  - **T3 C014:** "invorderbaar" wordt weer OBJECT_NP → Variabele, nu via `parataxis`. De fix van
    #522 dekt alleen het geval met een `cop`-kind; in de lange zin hangt `cop` aan "aanslag", en
    "overblijven" is ROOT. Dit is een PARSER_ERROR die een DETECTOR_ERROR voedt.

---

## 5. Voorlopige foutlokalisatie (geen conclusie)

Op basis van de vier traces, n = 1 run per bepaling. **Dit is een hypothesevormend beeld, geen
meting.**

| laag | aanwijzing | traces | juridisch/technisch |
|---|---|---|---|
| parser | lange zin verkeerd geparsed | T3 | technisch → juridisch gevolg |
| detector: generieke NP | volume, 3 klassen zonder predicaattoets | T2, T3, T4 | technisch; juridisch **O** |
| detector: connectief | "als" in een vergelijking wordt voorwaarde | T4 | juridisch gevolg |
| detector: span | te brede uitbreiding | T3 | juridisch gevolg |
| fusie/possible_classes | sterk bewijs verwatert, determinisme geblokkeerd | T2, T4 | technisch |
| classifier-interface | leakage | T4 | technisch (contract) |
| onzekerheid | 0 twijfel bij 36 modelbesluiten | T3 | technisch → verborgen juridisch risico |
| reviewer | 12/12 ongeldig, oorzaak niet bewaard | T4 | technisch |
| relaties | afleiding/operanden ontbreken | T3 | **O** (scope) |
| projectie | geen afwijking gemeten (graafcontrole in orde) | — | — |

---

## 6. Reviewload splitsen

Voorgestelde velden in `meting.reviewload`, afgeleid uit twijfelreden, beslissingsreden en
resolutieregel. De afleiding is deterministisch; er komen geen nieuwe modelaanroepen bij.

| veld | telt | bron |
|---|---|---|
| `substantive_legal_review` | DETECTOR_CONFLICT en ZELFDE_SPAN met een **geldig** reviewer-oordeel HUMAN_REVIEW of KEEP (tabel → HUMAN) | twijfel + resolutie |
| `classifier_contract_failure` | `CLASSIFIER_ONGELDIGE_KLASSE` / `_OPTIE` | beslissing.reden |
| `classifier_invalid_output` | `CLASSIFIER_GEEN_UITVOER` / `_OMITTED` | beslissing.reden |
| `reviewer_contract_failure` | `R-ONGELDIG` | resolutie.regel |
| `detector_conflict_review` | DETECTOR_CONFLICT (alle) | twijfel |
| `degraded_parse_review` | DEGRADED_PARSE | twijfel |
| `span_review` | ZELFDE_SPAN | twijfel |
| `technical_other_review` | rest | — |

Toegepast op T4: substantive = 0, contract_failure = 12, reviewer_contract_failure = 12. De UI toont
nu "12 ter keuze aan de jurist". Dat getal is dus **12 technische storingen, 0 juridische vragen**.

---

## 7. Gap-analyse evaluatie

| wat nodig is | wat er is | gat |
|---|---|---|
| adjudicated referentie | 24 `provisional` + 10 `silver`-ankercases | **geen enkele** adjudicated/gold |
| klassenspreiding | P: 0× Plaatsaanduiding, 2× Delegatie, 3× Brondefinitie, 4× Operator | ondervertegenwoordigd |
| tekstsoorten | wetten, Awb, Wzt, RVV, BW, Ow | geen beleidsregel/circulaire (LI), geen AMvB/regeling |
| fouttaxonomie | ADR §12, 14 codes; in code 3 codes | zie §8 |
| spanfouten | `SPAN_ERROR` (overlap + zelfde klasse) | te breed/te smal, detector vs keuze |
| classifier-contract | alleen afvang getest | frequentie, leakage, reviewer-contract |
| reviewload | één getal HUMAN_REVIEW | uitsplitsing §6 |
| stabiliteit per kandidaat | `stabiliteit_analyse` clustert op IoU van *voorstellen* | afgewezen kandidaten ontbreken; geen per-candidate-id-rapport |
| afgewezen kandidaten in productie | alleen telling | beslissing + bewijs per afgewezen kandidaat |
| run-manifest | model, provider, prompt_hash, methode_versie, instellingen | commit-SHA, image-digest, detectorversies in export; `agent_versie` leeg |
| relationele kwaliteit | niets | alleen meten, niet bouwen (§14) |
| juridisch vs technisch vs evaluatiefout | niet onderscheiden | veld `soort` per fout |

---

## 8. Definitieve fouttaxonomie (v2)

**Regels:**

1. Elke fout krijgt precies één **primaire** categorie: die van de eerste laag waar het misging,
   niet de laag waar het zichtbaar werd.
2. Daarnaast nul of meer **secundaire** categorieën.
3. Elke fout krijgt ook een `soort`:
   - `juridisch`: de uitkomst is juridisch onjuist tegen gold;
   - `technisch`: de pipeline brak een eigen contract, ongeacht de juridische uitkomst;
   - `evaluatie`: de referentie, de matching of het harnas is fout.

| code | laag | primair als… | typische soort | ADR-001 §12 |
|---|---|---|---|---|
| `SOURCE_ERROR` | bron | verkeerde versie, hash, node; of tekst ongeschikt (`source_status=unusable`) | technisch | = |
| `SEGMENTATION_ERROR` | segmentatie | onderdeel aan verkeerd lid, grens verschoven | technisch | = |
| `PARSER_ERROR` | taal | dependency/POS fout en daardoor detectorfout | technisch | = |
| `DETECTOR_ERROR` | detector | regel vuurt ten onrechte of niet, bij een correcte parse | technisch | = |
| `CONNECTIVE_DISAMBIGUATION_ERROR` | detector | signaalwoord in de verkeerde functie gelezen ("als" vergelijkend → voorwaarde) | juridisch | nieuw (subtype van DETECTOR) |
| `CANDIDATE_MISSED` | kandidaat | gold-element zonder kandidaat en zonder spanoptie | juridisch | = |
| `CANDIDATE_FALSE_POSITIVE` | kandidaat | kandidaat die structureel nooit een element kan zijn | technisch | = |
| `DETECTOR_SPAN_ERROR` | kandidaat | juiste plek, verkeerde grens, en geen spanoptie bevat de gold-grens | juridisch | nieuw (uit SPAN_ERROR) |
| `SPAN_TOO_WIDE` / `SPAN_TOO_NARROW` | kandidaat/keuze | secundair bij een spanfout: richting | juridisch | nieuw |
| `FUSION_ERROR` | fusie | bewijs verloren, verkeerde samenvoeging | technisch | = |
| `HYPOTHESIS_ERROR` | fusie/specificiteit | juiste klasse verwijderd of een onmogelijke klasse toegevoegd door voorrang/fusie | technisch | nieuw |
| `POSSIBLE_CLASS_ERROR` | kandidaat | gold-klasse niet in `possible_classes` | juridisch | nieuw |
| `EVIDENCE_CLASS_MAPPING_ERROR` | detector/profiel | bewijscode wijst een klasse aan die het profiel niet steunt | technisch | nieuw |
| `CLASSIFIER_ERROR` | classifier | geldige keuze, juiste span, gold-klasse wel aangeboden, verkeerd gekozen | juridisch | = CLASSIFICATION_ERROR |
| `CLASSIFIER_CONTRACT_ERROR` | classifier | keuze buiten de toegestane beslissingen van deze kandidaat | technisch | nieuw |
| `CLASSIFIER_CROSS_CANDIDATE_LEAKAGE` | classifier | secundair bij een contractfout: de gekozen klasse staat in de batch-unie | technisch | nieuw |
| `CLASSIFIER_ABSTAIN` | classifier | geen tool-uitvoer of label ontbreekt | technisch | nieuw |
| `CONTEXT_ERROR` | classifier-invoer | benodigde aanhef of ander lid ontbrak | technisch | = |
| `RELATION_MISSING` | (geen laag) | gold vraagt een relatie (operand, afleiding, drager) die de pipeline niet kan uitdrukken | juridisch | nieuw; alleen gemeten |
| `FRAME_ERROR` | (toekomstig) | gereserveerd voor Norm-/DerivationFrame; nu ongebruikt | — | nieuw |
| `UNCERTAINTY_ERROR` | onzekerheid | fout geaccepteerd/afgewezen zonder twijfel, terwijl een waarneembaar signaal bestond | technisch | nieuw |
| `REVIEW_ERROR` | reviewer | geldig maar onjuist KEEP/CHANGE | juridisch | = |
| `REVIEW_CONTRACT_ERROR` | reviewer | ongeldige of ontbrekende reviewer-uitvoer (`R-ONGELDIG`) | technisch | nieuw |
| `RESOLUTION_ERROR` | resolver | transitie in strijd met de tabel of met een JAS-regel | technisch | = |
| `VALIDATION_ERROR` | validatie | ongeldig doorgelaten of geldig geweigerd | technisch | = |
| `PROJECTION_ERROR` | api/RDF | graaf wijkt af van Postgres, SHACL-schending | technisch | = |
| `REFERENCE_ERROR` | evaluatie | gold-element fout, of offset/woordgrens (vgl. RVV01–03) | evaluatie | nieuw |
| `MATCHING_ERROR` | evaluatie | harnas telt goed als fout of omgekeerd | evaluatie | nieuw |

Twee randgevallen:

- **Toewijzing bij de 12 van T4.** Type A: primair `CLASSIFIER_CONTRACT_ERROR`, secundair `LEAKAGE`
  en `HYPOTHESIS_ERROR` (de voorrang haalde een klasse weg die het model wilde). Type B: primair
  `POSSIBLE_CLASS_ERROR` of `DETECTOR_ERROR`, secundair `CONTRACT_ERROR`.
- **`debatable` in de adjudicatie (§10) is géén fout.** Het telt apart en nooit als juist of onjuist.

---

## 9. Definitieve metrics

Notatie: G = gold-elementen (adjudicated), K = kandidaten, V = voorstellen (ACCEPTED ∪ HUMAN_REVIEW),
positie = (bron, start, eind) na randtrim (`metrieken.kern`).

Algemene regels:

- Elke metric wordt gerapporteerd met **status van de referentie**, n, het aantal runs en de
  run-manifest-hash.
- Tegen iets anders dan adjudicated heet recall **ankerdekking**, zoals nu.
- Percentages onder n = 20 worden met teller/noemer getoond, niet alleen als percentage.

**Kandidaatlaag**

| metric | definitie |
|---|---|
| candidate_recall | \|{g ∈ G : ∃k, pos(k)=pos(g)}\| / \|G\| |
| candidate_recall_incl_opties | idem, waarbij ook een spanoptie van k telt |
| possible_class_recall | \|{g : ∃k op pos(g) (of optie) met klasse(g) ∈ possible_classes(k)}\| / \|G\| |
| candidate_precision | \|{k : ∃g op pos(k)}\| / \|K\|; diagnostisch, geen kwaliteitsoordeel |
| kandidaten_per_gold | \|K\| / \|G\| per casus |
| detector_contribution | per detector: aandeel van candidate_recall dat alleen via die detector gedekt is |
| detector_fp_rate | per regel-id: kandidaten zonder gold-overlap / kandidaten van die regel |
| generiek_aandeel | kandidaten met alleen {SUBJECT_NP, OBJECT_NP, ENUMERATED_NP} / \|K\| |

**Spanlaag**

| metric | definitie |
|---|---|
| exact_span | V met pos = pos(g) en dezelfde klasse / \|G\| |
| partial_overlap | IoU > 0, zelfde klasse, niet exact (diagnose) |
| mean_IoU | over gematchte paren |
| detector_span_error | g met overlap, maar geen kandidaat en geen optie exact |
| span_too_wide / too_narrow | bij overlap: pred ⊃ gold of pred ⊂ gold |

**Classificatie**: precisie, recall en F1 per klasse, micro en macro, en een confusion matrix met ∅
voor gemist/overbodig (bestaat in `metrieken.classificatie_metrieken`). Nieuw is dat `debatable`
buiten teller én noemer blijft en apart wordt gerapporteerd.

**Stabiliteit** (per casus, over R runs; zie §13): detectie-, span-, accept/reject-, klasse- en
kandidaatbeslisstabiliteit.

**Proces**

| metric | definitie |
|---|---|
| %deterministisch / %classifier | per casus |
| %legal_review / %technical_review | uit §6 |
| geblokkeerd_deterministisch | kandidaten met ≥ 1 code in STERK_BEWIJS die tóch naar het model gingen |
| llm_calls, review_calls, latentie per fase, tokens | bestaand |

**Classifier-contract**

| metric | definitie |
|---|---|
| invalid_class_selections | # `CLASSIFIER_ONGELDIGE_KLASSE` |
| leakage_count | # daarvan waarbij de gekozen klasse in de batch-unie staat |
| leakage_uit_specificiteit | # daarvan waarbij de klasse door `PRIORITY_APPLIED` van deze kandidaat werd weggehaald |
| invalid_tool_outputs | # GEEN_UITVOER + OMITTED |
| contract_error_rate | (invalid_class + invalid_option + invalid_output) / beslissingen door het model |
| reviewer_contract_error_rate | # R-ONGELDIG / # reviewer-gevallen |

**Relationele kwaliteit (alleen meten, niets bouwen)**: tellingen per gold-element met een
relatievraag (§14): missing_norm_relation, missing_variable_owner, missing_comparison_operands,
missing_derivation, missing_temporal_anchor.

---

## 10. Ontwerp van de eerste adjudicated referentieset

### 10.1 Uitgangspunten

- **27 tot 30 bepalingen.** Hergebruik de 24 bestaande provisional dossiers: de bron is al
  vastgelegd met SHA-256 en de familie-split bestaat. Aanvullen met 3 diagnostische gevallen en
  hooguit 3 gatenvullers.
- **Familie-split behouden:** BW6 en Omgevingswet blijven held-out en komen nooit in een prompt,
  regel-YAML of few-shot.
- **Diagnostische startcases zijn niet dominant:** art. 9 lid 1, art. 9 lid 5 en LI §9.5 zijn samen
  3/30, en IW in totaal 6/30.
- **Een gold-set is per bepaling *volledig*,** niet een ankerset. Alleen dan betekenen precisie en
  recall iets.

### 10.2 Samenstelling

| # | casus | bron | tekstsoort | reden van opname |
|---|---|---|---|---|
| 1 | IW01 | IW 1990 art. 9 lid 1 | wet | diagnostisch: naamwoordelijk gezegde, termijn, Rsubj/Robj/Rbetr/Rfeit |
| 2 | IW-D2 *(nieuw)* | IW 1990 art. 9 lid 5 | wet | diagnostisch: lange zin, afleiding, "zoveel … als", nested spans, parserfout |
| 3 | LI-D3 *(nieuw)* | LI 2008 §9.5 | beleidsregel (uitleg met voorbeelden) | diagnostisch: vergelijkend "als", tijdseenheden, `source_status`-vraag (voorbeeldtekst) |
| 4–6 | IW02–IW04 | IW 1990 art. 36 lid 1/4, art. 34 lid 6 | wet | inversie, vermoeden, delegatie (passief) |
| 7–10 | AWB01–04 | Awb 5:2 lid 1, 4:17 lid 2 | wet | definitie, "dan wel", "voor zover", berekening met tijdvakken |
| 11–14 | WZT01–04 | Wzt art. 2 | wet | "minder dan", percentages, "voorzover", relatieve bijzin, delegatie "kunnen" |
| 15–18 | RVV01–04 | RVV 1990 art. 74–75 | AMvB | toestemming, negatie, verkort gezegde |
| 19–22 | BW01–04 *(held-out)* | BW 6:217–221 | wet | "tenzij", "zolang", passief, twee termijnen |
| 23–26 | OW01–04 *(held-out)* | Ow 1.3–1.8 | wet | open normen, epistemisch "weet of kan vermoeden", "in ieder geval" |
| 27 | GAP-PLAATS *(te selecteren)* | nog te kiezen | wet/regeling | **Plaatsaanduiding** ontbreekt nu volledig |
| 28 | GAP-DEF *(te selecteren)* | begripsbepalingenartikel met onderdelen | wet | Brondefinitie met opsomming (nu 3 markeringen) |
| 29 | GAP-OPERATOR *(te selecteren)* | bepaling met "ten minste/ten hoogste" + berekening | regeling | Operator met operanden, bedragen |
| 30 | reserve | — | ministeriële regeling of circulaire | tweede niet-wettelijke tekstsoort |

Selectieregel voor 27–30: de bron eerst via de graaf ophalen en vastleggen met SHA-256. Kies uit een
familie die niet in de detectorregels als voorbeeld voorkomt. **Geen tekst kiezen omdat het systeem
er goed of slecht op scoort.**

### 10.3 Dekkingsmatrix (controle vóór bevriezen)

De set is pas compleet als elke rij minstens twee gold-elementen in minstens twee families heeft.

- **Klassen:** alle 13.
- **Constructies:**
  - actief en passief;
  - naamwoordelijk gezegde;
  - lange samengestelde zin;
  - opsomming;
  - relatieve bijzin;
  - voorwaarde;
  - tenzij en uitzondering;
  - verwijzing;
  - termijn;
  - bedrag en percentage;
  - vergelijking, berekening en afleiding;
  - delegatie;
  - definitie.
- **Scheidingen:**
  - grammaticaal subject ≠ Rechtssubject;
  - grammaticaal object ≠ Rechtsobject.
- **Spans:**
  - nested spans;
  - meerdere functies op dezelfde span.
- **Ambiguë signaalwoorden:**
  - "als" in voorwaarde, vergelijking en hoedanigheid;
  - "of" en "en" exclusief/inclusief;
  - "dan wel";
  - tijdseenheid in niet-temporele context ("€ 23 per dag");
  - zelfstandig naamwoord dat geen juridisch object is.

### 10.4 Dataschema (V1)

Eén bestand per versie (`referentieset/v<N>/cases.json`) plus een manifest.

**Casus**

- `id`, `familie`, `split`, `bron_id`, `vindplaats`, `versie`
- `tekst`, `tekst_sha256`
- `source_status`: `valid` | `ambiguous` | `unusable`
- `tekstsoort`
- `constructies[]` (uit de matrix §10.3)

**Gold-element**

- `gid`
- `start`, `eind`, `tekst` (codepoints, woordgrensgecontroleerd)
- `klasse`, `subtype`
- `context`, `motivatie`
- `herkenningsvraag` (JAS-vraag, letterlijk uit het profiel)
- `h2_ref` (`H2:NN`)
- `annotation_status`: `correct` | `incorrect` | `debatable`
- `relaties[]` (optioneel, alleen voor meting: `{soort, naar_gid}`)
- `adjudicatie`: `verschil` (gelijk, klasse, span, alleen_a, alleen_b) en `besluit` (gelijk, kies_a,
  kies_b, beide, debatable). Wie en wanneer (annotator_a, annotator_b, adjudicator, datum,
  protocolversie) staat één keer op de casus, niet per element.

**Negatief element**: `start`, `eind`, `tekst`, `waarom_geen_element`. Voor bekende valkuilen, bijvoorbeeld
"als dat van de dagtekening" of "invorderbaar".

**Manifest**

- `referentie_versie`, `protocolversie`, `bevroren_op`
- `referentie_status` (per casus; `adjudicated` alleen met een compleet adjudicatierecord)
- `sha256` over alle casussen
- `voorganger` (vorige versie) plus changelog per gid

Coverage-status (`present` / `missed` / `superfluous`) hoort **niet in gold**. Het is een eigenschap
van een *run tegen* gold en wordt door het harnas afgeleid.

---

## 11. Adjudicatieprotocol (v1)

**Rollen:** annotator A en annotator B (juristen die de JAS-methode kennen) en adjudicator C (een
derde, of A en B samen met een schriftelijk besluit). Het systeem is **nooit** annotator.

**Stappen per casus:**

1. **Bron controleren.** Tekst en SHA-256 tegen de graaf of het Staatsblad. Zet `source_status`.
   Bij `unusable` stopt de casus hier.
2. **Blind annoteren.** A en B werken onafhankelijk, zonder systeemoutput, zonder elkaars werk en
   zonder de oude conceptmarkeringen. Per element vullen ze in: exacte span, klasse, subtype,
   motivatie, de beantwoorde herkenningsvraag en de H2-referentie. Relaties zijn optioneel.
   Negatieve elementen noteren ze alleen bij een bewuste keuze.
3. **Vergelijken, automatisch op positie.** Er zijn vier uitkomsten:
   - gelijk: dezelfde span en klasse;
   - klasseverschil;
   - spanverschil;
   - alleen A of alleen B.
4. **Adjudiceren.** Per verschil wordt het besluit één van:
   - kies A;
   - kies B;
   - allebei (verschillende functies);
   - geen van beide;
   - `debatable`.

   Het besluit krijgt een motivatie en een H2-verwijzing. `debatable` alleen als beide lezingen
   methodisch verdedigbaar zijn; de reden staat erbij.
5. **Overeenstemming vastleggen.**
   - Vóór adjudicatie: per casus het aandeel gelijk op positie, en Cohen's κ op de klasse bij
     gelijke positie.
   - Lage overeenstemming is informatie over de methode, geen reden om een casus te schrappen.
6. **Bevriezen.** De manifest-hash gaat in de repo. Vanaf dat moment is de versie `adjudicated`.

**Onveranderlijkheid:**

- Wijzigen kan alleen via een nieuwe versie (`v<N+1>`), met een changelog per gid (reden, oude en
  nieuwe waarde, datum, adjudicator).
- `provisional ≠ adjudicated`, en `adjudicated ≠ immutable`: een fout in gold wordt een nieuwe
  versie, nooit een stille correctie.
- **Verboden:** een gold-element wijzigen *naar aanleiding van systeemoutput* zonder dat A/B/C het
  opnieuw volgens stap 2–4 beoordelen. Systeemoutput mag een vraag oproepen, geen antwoord leveren.

**Tooling (V2):** een reviewer-workflow die per casus alleen de bron en een leeg formulier toont. De
bestaande werkplek is daar niet geschikt voor, want die toont systeemvoorstellen. Het resultaat is
een JSON conform §10.4.

---

## 12. Blind evaluatieprotocol

1. **Goldset bevroren vóór de run** (manifest-hash). De run weigert te starten tegen een niet-bevroren
   set.
2. **Run-manifest per run.** Het manifest bevat:
   - commit-SHA en image-digest;
   - `methode_versie`, `agent_versie` (niet leeg), JAS-versie;
   - detectornamen en -versies (`fusie.detectoren`);
   - taalmodel en versie;
   - LLM-model, provider, `prompt_hash`, `classifier_prompt`, temperatuur;
   - granulariteit, spankeuze, `deterministisch_accepteren`, `gerichte_review`;
   - referentieversie en -hash;
   - aantal herhalingen en seed-beleid.
3. **Herhalingen:** ≥ 5 runs per casus voor stabiliteit, ≥ 3 voor kwaliteitsmetrics.
4. **Held-out** (BW, Ow): alleen draaien voor de eindmeting van een baseline, niet tijdens ontwikkeling.
5. **Geen tuning op de testset.** Een detector- of promptwijziging die naar aanleiding van een
   held-out-fout wordt gemaakt, maakt die casus voor die meting ongeldig. Het rapport meldt dat.
6. **Rapport:** per metric de status, n, runs en manifest. Juridische en technische fouten worden
   apart gerapporteerd. `debatable` apart.

---

## 13. Kandidaatbeslisstabiliteit

**Sleutel:** `candidate_id`. Dat is een hash van (bron, start, eind) en is stabiel zolang de
bronstand gelijk blijft. Als tweede sleutel voor vergelijking over bronversies:
`span_signature = (bron_iri, genormaliseerde tekst, i-de voorkomen)`.

**Vereist (V4):** per run *alle* kandidaten met hun beslissing bewaren, ook REJECTED en UNCERTAIN.
In het harnas kan dat meteen (`Uitkomst.beslissingen`). In productie vraagt het dat `analyse` via de
batch naar de api gaat.

**Rapportrij:**

| candidate_id | span | evidence fingerprint | possible_classes | run 1 … run R | aanwezig | accept-overeenstemming | klasse-overeenstemming \| geaccepteerd | contractfouten |
|---|---|---|---|---|---|---|---|---|

- *evidence fingerprint* = sha256 over de gesorteerde (detector, code, regel).
- Een fingerprint die tussen runs verschilt, wijst op niet-determinisme in de detectie. Dat is een
  bug, want de detectie hoort deterministisch te zijn.
- Per casus komen er aggregaten bij: detectie-, span-, accept- en klassestabiliteit, en de
  kandidaatbeslisstabiliteit (aandeel kandidaten met R/R dezelfde uitkomst).

---

## 14. Relationele foutanalyse (checklist per foutgeval)

Voor elk element dat `incorrect` is of `missed`:

1. Juiste span aanwezig: als kandidaat, als optie, of niet?
2. Juiste clause aanwezig? Staat de bijzin of het segment als kandidaat?
3. Juiste dependency: klopt de parse op het kopwoord en op de relatie met het predicaat?
4. Juiste detector: welke regel had moeten vuren, en vuurde hij?
5. Juiste hypothese: stond de gold-klasse in `possible_classes`?
6. Bewijs voor de gold-klasse: welk bewijs steunde hem, en was het sterk of generiek?
7. Relatie met het predicaat nodig om de klasse te bepalen? (→ kandidaat voor een NormFrame)
8. Afleiding nodig? (output = f(input)) (→ DerivationFrame)
9. Vergelijking nodig? (links, operator, rechts) (→ ComparisonFrame)
10. Classifier-interface: contractfout, leakage, ontbrekende uitvoer?
11. Juridische classifierfout: geldige keuze, gold aangeboden, toch fout?
12. Had de onzekerheid moeten triggeren? Zo ja: welk signaal was waarneembaar?

De antwoorden zijn gestructureerde velden. Zo vormt het tellen van de vragen 7–9 het bewijs vóór of
tegen de frames in §15.

---

## 15. Beslispoorten voor architectuurwijzigingen

Het format per voorstel is steeds: probleem → bewijs (V7) → root cause → minimale wijziging →
verwachte metric → risico → regressietest → besliscriterium. Geen enkel voorstel gaat door zonder
V7.

| voorstel | alleen als (V7, adjudicated, ≥ 3 runs) | verwachte metric | risico |
|---|---|---|---|
| contract-redesign (per-kandidaat of sub-batch) | contract_error_rate ≥ 5% van de modelbeslissingen **of** ≥ 20% van de HUMAN_REVIEW, over ≥ 3 families | contract_error → 0; technical_review omlaag; CLASSIFIER_ERROR niet omhoog | verbergt conflicten tussen regel en model; dus eerst `leakage_uit_specificiteit` apart zichtbaar maken |
| generieke NP degraderen tot bewijs | ≥ 30% van de CLASSIFIER_ERROR op Rsubj/Robj/Var komt van kandidaten met alleen generiek bewijs, **en** candidate_recall zakt < 2 pt in een ablatie | precisie Rsubj/Robj omhoog; recall gelijk | gemiste subjecten/objecten die alleen syntactisch te vinden zijn |
| bewijs per klasse / CandidateHypothesis | ≥ 25% van de CLASSIFIER_ERROR heeft een gold-klasse met *sterk* bewijs naast gekozen zwak bewijs, of blokkeert het determinisme | geblokkeerd_deterministisch omlaag; %deterministisch omhoog met gelijke precisie | modelcomplexiteit; contractdrift |
| determinisme uit regelmetadata | bij geblokkeerd_deterministisch is de gold-klasse ≥ 90% gelijk aan de sterke klasse | idem | ten onrechte automatisch geaccepteerd (zie T3 C024); dus eerst DETECTOR_SPAN_ERROR per regel meten |
| onzekerheid uitbreiden (WEAK_ONLY, MODEL_REJECTED_STRONG, CLASS_FROM_NON_SUPPORTING) | ≥ 50% van de juridische fouten valt in een klasse die een nieuw signaal zou vangen, bij een reviewload-groei ≤ 2× | UNCERTAINTY_ERROR omlaag | alarmmoeheid |
| connectief-disambiguatie ("als") | ≥ 3 CONNECTIVE_DISAMBIGUATION_ERROR over ≥ 2 families | detector_fp_rate `jas.voorwaarde.als_bijzin` omlaag | gemiste voorwaarden |
| NormFrame | ≥ 30% van de Rsubj/Robj/Rbetr/Rfeit-fouten scoort "ja" op checklistvraag 7 | F1 op die vier klassen | grote wijziging; parserafhankelijk |
| DerivationFrame / ComparisonFrame | ≥ 5 gold-afleidingen of -vergelijkingen met RELATION_MISSING **en** een scopebesluit dat relaties bij activiteit 2 horen | missing_derivation omlaag | scope-uitbreiding buiten activiteit 2 |
| familie-classifier | H9-experiment: klassestabiliteit of F1 verschilt aantoonbaar tussen universeel en familie | stabiliteit/F1 | meer aanroepen |
| decision cache | nooit vóór de andere poorten; alleen voor kosten | kosten | fouten bevriezen |

---

## 16. PR-roadmap V1–V7

Algemeen voor elke PR:

- geen wijziging aan detectoren, prompts, classifier, onzekerheid, reviewer of resolver;
- alle nieuwe metingen additief;
- tests zonder spaCy mogelijk, zoals CI.

**V1 – Adjudicated referentieschema en versiebeheer**

- Schema §10.4, manifest met hash en validator (`metrieken.controleer_status` uitbreiden).
- Migratie van de 24 dossiers naar `v1` als `provisional`, dus zonder statuswijziging.
- Toegevoegd: `source_status`, `constructies`, `tekstsoort`, negatieve elementen.
- Test: een adjudicated casus zonder volledig record faalt; manifest-drift faalt.
- *Niet:* gold invullen.
- *Stand:* uitgevoerd. `docs/wetsanalyse/referentieset/v1/` + `tools/graph-qa/eval/referentieset.py`
  (`--check`, `--bijwerken`, `--dekking`). Niet beoordeelde velden zijn leeg (`null`), niet
  ingevuld; adjudicated kan alleen in een bevroren versie.

**V2 – Adjudicatieprotocol en reviewer-workflow**

- Protocol §11 als document.
- Een blind annotatieformulier:
  - standalone HTML of een CLI, die bron plus leeg formulier toont en JSON uitvoert;
  - geen systeemvoorstellen zichtbaar.
- Vergelijkingsscript A/B → verschillenlijst en κ.
- Test: het formulier toont geen systeemoutput; de vergelijking op positie is correct.
- *Stand:* uitgevoerd.
  - Protocol: `docs/wetsanalyse/referentieset/adjudicatieprotocol.md`.
  - Formulier: `scripts/blind_formulier.py`. De casusvelden gaan er via een allowlist in.
  - Vergelijken en adjudiceren: `eval/adjudicatie.py` (`vergelijk`, `besluit`).
  - Bevriezen: `eval.referentieset --bevries`. Dat zet `review_pending` op `adjudicated`.
  - Namen van annotatoren zijn codes, want de repo is publiek.

**V3 – Fouttaxonomie v2**

- Codes §8 in `eval/`: primair, secundair, `soort`.
- `_foutcategorie` vervangen door een classificeerder die de kandidaat-, span- en contractlaag
  gebruikt.
- `debatable` uitgesloten van de telling.
- ADR-001 §12 verwijst hiernaar.
- Test per code met een geconstrueerd geval, waaronder de 12 T4-vormen als fixture.
- *Stand:* uitgevoerd in `eval/fouttaxonomie.py`.
  - Twee soorten invoer:
    - volledig: alle kandidaten, via `uit_uitkomst`;
    - alleen voorstellen: via `uit_elementen`, voor een export of een `element`-event.
  - De oorspronkelijke classifierreden komt uit `trace.twijfel`, omdat de resolver `beslissing.reden`
    overschrijft.
  - Leakage wordt alleen vastgesteld als de batch-unie bekend is, of als ondergrens bij een
    universele batch.
  - Handmatige codes uit de checklist (§14) komen erbij via `correcties`.
  - `compare_pipelines` gebruikt de classificeerder en sluit `debatable` uit.
  - Fixture: de uitgeklede T4-export (`tests/fixtures/t4_li95_spoor.json`). Daarin zijn de 12
    gevallen 9× primair CONTRACT met LEAKAGE en HYPOTHESIS, en 3× primair POSSIBLE_CLASS met
    CONTRACT en LEAKAGE.

**V4 – Kandidaatbeslisstabiliteit**

- Harnas: alle beslissingen per run bewaren.
- Rapport §13.
- Productie: `analyse.beslissingen` (compact: id, label, status, door, reden, klasse,
  bewijsfingerprint) additief in de batch naar de api; bewaard bij de run.
- Contract-drift-test mee.
- Test: afgewezen kandidaten zijn na de batch terug te lezen.
- *Stand:* uitgevoerd.
  - Beslisregister: `agent/jas_pipeline/beslisregister.py`. Velden per kandidaat:
    - id, label, bron, start en eind;
    - mogelijke klassen en de klassen die voorrang weghaalde;
    - bewijscodes en de bewijsfingerprint;
    - status, door, klasse en reden;
    - `classifier_reden` van vóór de resolver.
  - Transport: via het `dekking`-event → `Batch.beslissingen` → de batch-audit in de api. Daarmee
    staat het in de weergave en de export, en niet op de elementen of in het chatbericht.
  - Harnas: `compare_pipelines` bewaart het register per run.
  - Rapport §13: `eval/beslisstabiliteit.py`, met kandidaatbeslisstabiliteit, fingerprint-drift en
    contractfouten per casus.

**V5 – Classifier-contract en reviewload**

- Reden `CLASSIFIER_CONTRACT_ERROR` naast ABSTAIN. Alleen *rapportage*; de afhandeling blijft gelijk.
- Metrics §9 (leakage, leakage_uit_specificiteit).
- Reviewer: ruwe uitvoer en de reden van ongeldigheid bewaren (`Oordeel.ruw`, `ongeldig_omdat`).
- `meting.reviewload` volgens §6.
- Werkplek: technische gevallen herkenbaar als zodanig in de tekst, zonder gedragswijziging.
- Test met de T4-vorm: 12 → contract 12 / legal 0.
- *Stand:* uitgevoerd.
  - De contractfout is geen nieuwe twijfelreden geworden maar een afgeleide `categorie` op
    `CLASSIFIER_ABSTAIN`. De reviewer-prompt toont reden en detail; een nieuwe reden zou dus een
    promptwijziging zijn.
  - Reviewer: `Oordeel.ruw` en `ongeldig_omdat`, en in het spoor `Transitie.oordeel_ruw` en
    `ongeldig_omdat`.
  - `meting.reviewload`: `agent/jas_pipeline/reviewload.py`. Elk geel geval krijgt precies één
    oorsprong.
  - Metrics §9: `metrieken.contract_metrieken`, berekend op het beslisregister. Die komen ook in
    `compare_pipelines`.
  - Werkplek: de gele kaart zegt bij een contractfout "Technische storing, geen juridische twijfel".
  - T4: 12 human review → 12 contract, 0 juridisch. Leakage 12, waarvan 9 uit specificiteit.

**V6 – Rapport per laag**

- Eén rapport per run-set, per laag uit §2.2 en per metric uit §9.
- Juridisch/technisch/evaluatie apart; per familie en per tekstsoort.
- Relationele checklist §14 als invulbare bijlage.
- *Geen* totaalscore.

**V7 – Baseline hybrid_v1 op de adjudicated set**

- Eerst V1–V2 uitvoeren met echte beoordelaars. Dat is mensenwerk; de PR landt pas als ≥ 20
  casussen `adjudicated` zijn.
- Meting: ≥ 3 runs (stabiliteit: 5), manifest vastgelegd, held-out eenmalig.
- Rapport in `docs/architectuur/metingen/`.

**STOP na V7.** Daarna komt een nieuw onderzoeksdocument met:

- de dominante foutcategorieën en de foutverdeling;
- juridisch tegenover technisch;
- klassespecifieke problemen;
- kandidaat-, span-, relationele en contractproblemen.

Pas dan volgen de beslispoorten van §15.

---

## 17. Wat we nog NIET weten

1. **Of hybrid_v1 juridisch juist annoteert.** Er is geen adjudicated referentie; alle kwaliteitscijfers
   zijn ankerdekking.
2. **Of de generieke Rechtsobject-acceptaties fout zijn.** "de betalingstermijn" en "de dagtekening"
   als Rechtsobject (T4: 21×) kunnen fout zijn of verdedigbaar; dat is een adjudicatievraag.
3. **Hoe vaak leakage voorkomt.** Het is waargenomen in 1 van 4 traces (12/45). Het aandeel over de
   families is onbekend.
4. **Wat de reviewer antwoordde** in T4 (12× R-ONGELDIG). Dat is niet bewaard.
5. **Hoe vaak het model sterk bewijs afwijst** (H6). Afgewezen beslissingen worden niet bewaard.
6. **Of de universele batch beslissingen doet overhellen** (H9), los van leakage. Daarvoor is geen
   vergelijkend experiment gedaan.
7. **Of relaties (operand, afleiding) binnen activiteit 2 horen.** Dat is een scopebesluit, geen
   meetvraag.
8. **Of de parserfouten** (art. 9 lid 5) typerend zijn voor lange wetszinnen, of incidenteel. Er is
   geen parser-evaluatie op gold.
9. **Of een beleidsregel met rekenvoorbeelden** (LI §9.5) überhaupt als normtekst geannoteerd moet
   worden. Dat is een `source_status`/scopevraag.
10. **Run-tot-run-stabiliteit op de nieuwe traces.** Er is 1 run per bepaling. T1/T2 zijn twee runs
    maar met een codewijziging ertussen, dus ze zijn niet vergelijkbaar als herhaling.
11. **Hoe goed de `provisional` conceptmarkeringen zelf zijn.** Bij RVV01–03 was er al één offsetfout
    (REFERENCE_ERROR).
12. **Of spaCy `nl_core_news_md` de juiste parser is** voor wetstaal. ADR-002 koos hem op
    beschikbaarheid, niet op gold-parsekwaliteit.

## 18. Stopcriteria

We bouwen **niet** verder aan semantiek of architectuur zolang één van deze punten geldt:

1. Minder dan 20 casussen zijn `adjudicated` volgens §11, of de set dekt niet alle 13 klassen en de
   constructiematrix §10.3.
2. Er is geen run-manifest met commit-SHA, image-digest, detectorversies en een gevulde `agent_versie`.
3. Afgewezen kandidaten zijn niet per run terug te lezen (V4 niet af). Zonder dat is H5/H6 niet te
   toetsen.
4. Reviewload is niet gesplitst in juridisch en technisch (V5 niet af).
5. Een voorstel haalt zijn beslispoort in §15 niet, of het bewijs komt uit minder dan 2 families.
6. Een verbetering is alleen zichtbaar op de diagnostische cases (art. 9, LI §9.5), of alleen op
   ontwikkelcasussen en niet op held-out.
7. Een metric verbetert doordat casussen, gold-elementen of `debatable` uit de noemer verdwijnen.
8. Een wijziging verbetert technische validiteit, SHACL-conformiteit, stabiliteit of consensus, en
   dat wordt gepresenteerd als juridische verbetering.
9. Een gold-element is gewijzigd op basis van systeemoutput zonder een nieuwe adjudicatieversie.

Daarnaast blijft verboden, los van de metingen:

- promptpatches als primaire oplossing;
- nieuwe agentrollen;
- een Critic;
- model voting;
- modelconfidence-percentages;
- grotere modelvrijheid (vrije spans, vrije klassen).
