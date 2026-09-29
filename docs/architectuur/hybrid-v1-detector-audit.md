# Detectoraudit vóór de baseline van hybrid_v1

**Implementatievervolg 29 september 2026:** het [invorderingsvervolg](hybrid-v1-invordering-vervolg.md)
implementeert A01–A10 uit het daaropvolgende onderzoeksontwerp: beschermde afleidingsgrenzen,
datums zonder jaartal, termijnfuncties, expliciete tijdkernhypothesen, gerichte toetsing van
centrale afwijzingen en afzonderlijke graafcontext. Anders dan de eerdere technische ronde
bevat dit ook gewijzigde prompts en beslisregels. De [nieuwe meetmap](metingen/hybrid-v1-invordering-vervolg-2026-09-29/README.md)
bewaart de afzonderlijke fasen, alle detectieverschillen en de modelproef. Onderstaande
audit en eerdere onderzoeksuitspraken blijven hun historische betekenis houden.

**Inhoudelijk vervolg 29 september 2026:** het [onderzoek van vier invorderingsbepalingen](../wetsanalyse/onderzoek-invordering-2026-09-29/README.md)
voegt tien bevindingen toe, op uitsluitend graafteksten: afgewezen centrale norm zonder review,
datums zonder jaartal, gemiste passieve datumtoewijzing en termijnberekening, temporele
klasse-/grensgaten, batchcontract en beperkte volledigheidscontrole. Ook afleidingsdetectie
blijkt nog binnen beschermde notaties te splitsen; F05 hieronder betrof norm en terugvalanalyse.
De [dossiers en eisenmatrix](../wetsanalyse/onderzoek-invordering-2026-09-29/eisenmatrix.md)
onderbouwen een afzonderlijk verbeterontwerp. Alleen onderzoeksvoorzieningen zijn toegevoegd;
geen nieuwe productieregels of promptwijzigingen. De freeze en historische metingen blijven intact.

**Aanvulling 29 september 2026:** de oorspronkelijke audit en freeze hieronder blijven het
historische vergelijkingspunt. De [ketenkaart en tekststructuurverbetering](hybrid-v1-annotatieketen.md)
beschrijven het vervolg: gedeelde beschermde tekstgrenzen, opmaak-onafhankelijke onderdelen
en een gecontroleerd detectorresultaatcontract. De nieuwe
[voor](metingen/hybrid-v1-tekststructuur-2026-09-29/voor.json)- en
[nameting](metingen/hybrid-v1-tekststructuur-2026-09-29/na.json) staan afzonderlijk van de freeze.
De eerdere uitspraak onderaan dat geen minimale P1-fix meer bekend was, geldt voor het
toen onderzochte bereik; de drie onderstaande technische acceptatiegevallen zijn aanvullend.

| ID | Aanvullende bevinding | Mechanisme en status | Regressiebewijs |
|---|---|---|---|
| F05 | Norm afgebroken binnen `artikel 3:4`, `artikel 9.1`, `€ 1.000` of `art. 4` | `taal/grenzen.py` en `taal/verwijzingen.py`: bescherming vóór zins-/segmentgrenzen; norm v2 en terugvalprovider aangesloten. GEREPAREERD | `test_tekststructuur.py`: beide woordvolgordes, werkelijke zinseinden, Unicode, afkortingen, nummering, brongetrouwheid en determinisme |
| F06 | Definitie/betekenisonderdelen alleen gevonden bij regelstart | `taal/structuur.py`: eigen aanhef of aparte oudercontext, labels en nodegrenzen, centrale offsetterugvertaling; beide detectoren v2. GEREPAREERD | Eén regel, meerdere regels, kindnodes, gewone dubbele punten en meerledige omschrijvingen; emittertests met nepmodellen |
| F07 | Overgeslagen detector rapporteert hardcoded versie 1 | `detectoren.resultaat`: dezelfde constructie voor alle uitkomsten; `detecteer_alles` controleert identiteit; bijdragen en runmeting blijven herleidbaar. GEREPAREERD | Nul treffers, geen/gedegradeerde parse, identiteitsdrift, fusie/beslisregister en ketenuitvoer |

De nieuwe runmeting legt ook versies van de gedeelde tekstvoorzieningen vast. Ontwikkelset:
262 kandidaten en 73/81 kernankers met klasse blijven gelijk; vier alternatieve zinspans
veranderen, zonder verandering in classifierinvoer of routing. D01–D12 blijven buiten deze
technische wijziging. Er zijn geen nieuwe juridische herkenningsregels, prompts of
beslisregels toegevoegd en er is niet uitgerold.

## Afbakening en bewijs

Start: actuele remote master `9de992226e18514f40d96dd29ed98498e747ffe6` (V6), schone
checkout. Geen andere codebasis, nieuwe agents, prompts of referentieannotaties gebruikt.
De gecontroleerde code staat onder `tools/graph-qa/agent/jas_pipeline`; hieronder zijn paden
naar modules relatief aan die map. Alle detectorbestanden, regel-YAML's en dertien profielen
zijn gelezen, naast kandidaten, fusie, specificiteit, besluit, onzekerheid, keten, classifier,
validator, resolver, beslisregister en de opgegeven tests/evaluatiemodules.

Bewijssoorten: **C** = code/profiel; **R** = lokaal gereproduceerd met echte spaCy-parse;
**T** = historische trace; **A** = tegenfeitelijke meting; **O** = onbekend, geen vastgesteld
juridisch oordeel. `possible_classes` is een toegestane hypotheseruimte, geen geaccepteerde
JAS-classificatie. Alle hier genoemde referentieankers hebben status **provisional**.

Bronnen en reproduceerbaarheid:

- [Nulmeting](metingen/hybrid-v1-freeze/voor.json): 16 ontwikkelcasussen, 81 ankers, vier
  wetsfamilies. BW6 en Omgevingswet blijven buiten de ontwikkeling. De drie Awb-definitiecases
  bevatten deels dezelfde artikeltekst; frequenties zijn dus geen onafhankelijke steekproef.
- [Nameting](metingen/hybrid-v1-freeze/na.json): dezelfde invoer, met vergelijking per kandidaat
  en hashes van classifierinvoer, parserresultaat, code, regels en referentie.
- [Historische meting](metingen/2026-09-25-ab-legacy-hybrid.md) en
  [eerder onderzoek](onderzoek-empirische-validatie.md): context, geen actuele kwaliteitsclaim.
- De oorspronkelijke lokale exports T1–T4 zijn teruggevonden. T3 (`annotatie (2).json`,
  2026-09-25 12:33Z) en T4 (`annotatie (3).json`, 12:52Z export) zijn gebruikt voor reproductie.
  Brontekst, exporthash en relevante oorspronkelijke kandidaatsporen staan in
  `tools/graph-qa/tests/fixtures/detector_audit_diagnostiek.json`. Dit zijn diagnostische
  bronnen **zonder gold**, geen uitbreiding van de referentieset. Oude exports missen
  afgewezen kandidaten; hun modelbeslissingen zijn niet als volledige replay behandeld.
- Uitvoering: vanuit `tools/graph-qa`, `.venv/bin/python -m eval.detector_audit --json
  /tmp/na.json --vergelijk ../../docs/architectuur/metingen/hybrid-v1-freeze/voor.json`.
  Het meetprogramma weigert een gedegradeerde parse en doet nul modelaanroepen.

## Detectormatrix

Klassen: RS=Rechtssubject, RO=Rechtsobject, RB=Rechtsbetrekking, RF=Rechtsfeit,
VW=Voorwaarde, AR=Afleidingsregel, V=Variabele/waarde, P=Parameter/waarde, O=Operator,
T=Tijdsaanduiding, L=Plaatsaanduiding, D=Delegatiebevoegdheid/invulling, B=Brondefinitie.
“Det.” betekent de huidige route bij uitsluitend het genoemde bewijs en één klasse;
fusie kan die route blokkeren. FP/FN zijn waarneembare detectiefouten of expliciet aangeduide
risico's, geen gemeten juridische precision/recall. Status betreft de nameting.

| detector | input | taalkundig/structureel signaal | outputspan | evidence code | possible classes / juridische hypothese | parse? | juridische context vereist? | deterministic mogelijk? | bekende false positives / risico | bekende false negatives / risico | spanrisico | testdekking | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tijd | tekst, lijsten, verwijzingsmaskers | datum, duur, periode, tijdstip, bijwoord | langste regeluitbreiding; kern als optie | TEMPORAL_DATE, DURATION, RELATIVE_PERIOD, PERIOD_NOUN, PERIOD_OF, MOMENT, ADVERB (elk met TEMPORAL_-prefix) | T | nee | startgebeurtenis, toepasselijkheid | ja, behalve PERIOD_NOUN/ADVERB | T3 uitbreiding over vervolgbepaling (F01); contextloze tijdswoorden risico | `Binnen een redelijke termijn`; kale kalenderdagen zonder jaar | uitbreiding stopt doorgaans op interpunctie; F01 begrenst distributieve vervolgzin | vier YAML-testsoorten per regel; volledige T3; behoud samengestelde startgebeurtenis | actief; duur v2 |
| voorwaarde | tekst, masker | conditioneel/causaal voegwoord, vaste inleiding, wijze-bijwoord | tot komma/punt, formule tot punt; bijwoord kern; wegens + beperkte NP | CONDITIONAL_CLAUSE, CONDITIONAL_FORMULA, CONDITIONAL_ADVERB, CAUSAL_PHRASE | VW; bij wegens ook RF | nee | rechtsgevolg en bereik | nee | `schriftelijk` als beschrijving i.p.v. eis (risico) | als via andere detector; `zodra`; samengestelde eisen | komma binnen bijzin kapt af; zonder komma kan hoofdzin meegaan | vier testsoorten per regel en overlap met termijn | actief; contextbeperking |
| operator | tekst, masker | vergelijkings-, reken- en logische lexemen | operatorformule zelf | COMPARISON, ARITHMETIC, LOGICAL | O | nee | operandfunctie en rechtscontext | COMPARISON/ARITHMETIC ja; LOGICAL nee | vergelijkende tekst zonder normatieve functie (risico) | `zoveel … als` in IW-D2; onvolledige lexicale varianten | operatorgrens goed afgebakend, operanden ontbreken | vier testsoorten per regel | actief; relationeel beperkt |
| afleiding | tekst | bedraagt, passieve berekening, fictie/vermoeden | segment of uitgebreide passieve formule | CALCULATION_COPULA, CALCULATION_PASSIVE, LEGAL_FICTION | AR/P bij bedraagt; anders AR | nee | invoer, uitvoer, bewerking | nee | vast bedrag als AR/P bewust ambigu | IW03 weerlegging; IW-D2 zoveel … als; WZT02 meervoudige zinnen niet exact | passieve uitbreiding kan over `;` lopen; hele regel versus deelregel | vier testsoorten per regel | actief; frame uitgesteld |
| numeriek | tekst, masker | eurobedrag, percentage, veelvoud | waarde met eventuele eenheid | MONEY_AMOUNT, PERCENTAGE, MULTIPLIER | P/V; veelvoud O/P | nee | constant versus per geval | nee | waarden in voorbeelden blijven kandidaten (risico) | kaal `42`; andere geldnotaties dan eurotekenpatroon | lexicale notatie beperkt; geen generieke numerieke tokenparser | vier testsoorten per regel; maskernegatieven | actief; numeriek algemeen gepland |
| delegatie | tekst | bij/krachtens regelingsvorm + regels gesteld | volledige formule en onderwerp tot punt/; | DELEGATION_FORMULA | D | nee | gedelegeerd onderwerp; invulling vereist grondslag | ja | zeer ruime formulematch kan onderwerpsbereik meenemen (risico) | datumvaststelling zonder regels; `Gelet op …` / WTI-invulling | gehele bevoegdheidsformule bewust ruim | vier testsoorten, NormDetector sluit delegatie uit | actief; invulling gepland |
| plaats | tekst, gazetteer, masker | gebiedsnaam of lidstaatomschrijving | gebied met optioneel in/binnen/buiten; kernoptie | LOCATION_NAME, LOCATION_DESCRIPTION | L | nee | werkingsgebied versus naam/bestuursorgaan | ja, ondanks profiel `middel` | gebied in eigennaam/wetstitel niet expliciet gemaskeerd (risico) | gebieden buiten lijst; afwijkende hoofdletters | optioneel voorzetsel; maximaal beperkte eigennaam | vier testsoorten, synthetische gebiedscases; geen devankers | actief; contextbeperking |
| subject | tekst, rollexicon, masker | rolwoord/voornaamwoord | rol met beperkte linker/rechteruitbreiding | ROLE_NOUN | RS/RO | nee | drager van recht/plicht | nee | rolvermelding bewijst geen drager (risico) | onbekende rollen en antecedenten | slechts beperkte modifiers | vier testsoorten, overlap met parserrol | actief; kandidaatgenerator |
| definitie | tekst + ouderaanhef | verstaan-onder + term:omschrijving, of definitiezin | term en omschrijving; interpunctiekern als optie | DEFINITION_ITEM, DEFINITION_SENTENCE | B | nee | definitieaanhef noodzakelijk | ja | voorbeeld dat syntactisch op definitie lijkt (risico) | geneste/meerdere regels en varianten buiten patroon | regelgrens kan omschrijving afkappen | onderdeel, oudercontext, zin, niet-definitie, overlap | actief |
| betekenis | tekst + ouderaanhef | betekent: + term | term vóór dubbele punt/betekent | MEANING_TERM | VW/RO | nee | situatie waaronder betekenis geldt | nee | elke betekent-formule is niet automatisch juridische VW (risico) | andere formuleringen, geneste onderdelen | termgrens meestal klein; inhoud niet als relatie gemodelleerd | verkeerslicht, eigen onderwerp, aanhefuitsluiting | actief |
| NormDetector | tekst/lexicon | modaal woord of normatief lexeme | segment tussen . ; :; zin als optie | NORMATIVE_PREDICATE | RB/RF | nee, ondanks modulebenaming | partijen, recht/plicht, handeling met rechtsgevolg | nee | los lexeme of modaliteit zonder norm (risico) | impliciete normen; IW02/WZT01 brede referentiegrenzen | segmentatie op leestekens en afkortingen; modaliteit is geen minimale relatie | modaal, vaste uitdrukking, adjectief, delegatieuitsluiting, geen-parse | actief; context ontbreekt |
| NaamwoordgroepDetector | tokens, lemma, POS, dependencies | NP-kop, rol/eigenschap/parameter, grammaticale positie | eerst aaneengesloten kern; NP en NP+bijzin als opties | PARAMETER_NOUN, PROPERTY_NOUN, PERSON_PRONOUN, ROLE_NOUN, SUBJECT_NP, OBJECT_NP, ENUMERATED_NP | P/V; V/RO; RS; RS/RO; generiek RS/RO/V | ja | predicaat, clause, voice, actor/object | nee | grammatica wordt juridische keuzeruimte; `invorderbaar` bij parataxis blijft parserrisico | niet-aaneengesloten boom; onbekende pronomina; IW02 lange NP | parsergrenzen, kern kan te klein zijn; opties uit bijzin | kern/volledig, verwijzingsmasker, cop-regressie, dekkingvloer; geen volledige juridische-contexttest | actief; H1 mismatch uitgesteld |
| BijzinDetector | dependencyboom | als+mark+clause; relatieve bijzin bij NP | als-subboom; NP+relatieve bijzin | CONDITIONAL_CLAUSE, RESTRICTIVE_RELATIVE | VW; relatief VW/RS/RO | ja | conditionele of beperkende functie | nee | elliptische vergelijking/hoedanigheid gerepareerd (F02); vergelijkingen met werkwoord blijven risico | LI-D3 conditioneel als met parataxis/nsubj; ellipsen zonder werkwoord | subboom aaneengeslotenheid, modifier versus hele NP | conditioneel, bedoeld-in, hoedanigheid, vergelijking, relatieve bijzin, T4 | actief; v2 |
| NominalisatieDetector | POS, features, dependencies | Inf+het of NOUN op -ing met nmod | subboom zonder parataxis/bijzin; randfuncties weg | NOMINALIZED_ACTION | RF/VW/RO | ja | gebeurtenis/handeling én rechtsgevolg | nee | `het bepaalde` gerepareerd (F04); -ing alleen is geen handelingbewijs | actienamen buiten -ing; Inf verkeerd getagd | argumenten/modifiers/conj kunnen te ruim zijn; IW01 parser neemt duur mee | indienen, drie bestaande deelwoordcases, degraded parse | actief; v2 |
| LogischeOperatorDetector | dependencies, POS, morfologie | cc tussen predicaten met eigen zin; negatie bij mark | en/of/niet/geen-token | CLAUSE_COORDINATION, NEGATION_IN_CONDITION | O | ja | wat wordt verbonden/ontkend | nee | voorwaardelijke functie van mark blijft proxy (risico) | negatie bij NP met elders het voegwoord; opgesplitste opsommingen | token klein, bereik/operanden ontbreken | clause positief, objectopsomming negatief, eerdere of-regressie | actief; v2 |

Alle vijftien detectoren zijn actieve generators. Geen detectoruitvoer betekent op zichzelf
“juridisch vastgesteld”. De vier echte parsedetectoren slaan bij ontbrekende parse zichtbaar
over; NormDetector werkt lexicaal. De classifier krijgt de bepaling, vlakke bewijscodes en
toegestane klassen, zonder gestructureerde governor/clause/voice/actorrelaties.

## H1–H11 opnieuw getoetst

| hypothese | actuele beoordeling | bewijs en consequentie |
|---|---|---|
| H1 | bevestigd als profiel/implementatiemismatch | C/R: `_classificeer_signaal` checkt bij generieke NP geen normatief predicaat. Subjectrelaties krijgen RS/RO/V, conj RO/RS/V en **alle overige nominalen** RO/V/RS; OBJECT_NP betekent dus niet alleen grammaticaal object. PROPERTY_NOUN kijkt incidenteel naar `bedragen`, generic NP niet. De volgorde bepaalt bovendien de familiebatch bij configuratie `familie`. Niet zonder adjudicatie herontwerpen. |
| H2 | bevestigd als ontbrekende gestructureerde context | C: head, zin, morphologie en UD-relatie zijn beschikbaar in de taalanalyse. De detector gebruikt lokale dependencyrelaties, maar geen algemene governorpredicaat-, voice- of actor/objectanalyse. nsubj:pass en obl:agent vallen beide onder subjectsignaal. De volledige tekst is wel aan de classifier beschikbaar. |
| H3 | gedeeltelijk bevestigd | C: NormDetector biedt altijd RB/RF. Het RB-profiel noemt RF expliciet als verwarringsklasse; dit is dus geen eenvoudige overtreding van het eigen profiel. NORMATIVE_PREDICATE bewijst zelfstandig geen RF met rechtsgevolg. Een normsegment kan een handeling bevatten: verwijderen van RF is een semantische policywijziging, uitgesteld. |
| H4 | precisierisico bevestigd; één concrete bug gerepareerd | C/R: NOUN op -ing + iedere nmod test geen actie of rechtsgevolg, zelfs niet letterlijk `van`. ‘Dagtekening’ staat juist expliciet in het RF-profiel: geen blacklist. De Inf-tak herkende ten onrechte Part (`het bepaalde`) in IW02/IW03/WZT04; F04 herstelt uitsluitend de grammaticale conditie. |
| H5 | algemene foutclaim niet bevestigd; concrete grensfout wel | C: tijdprofiel verlangt duur mét startgebeurtenis. `classifier_spankeuze=false` maakt die gekozen grens definitief, maar verplicht geen korte kern. T3 C024 overschrijdt de startgebeurtenis aantoonbaar; F01 repareert die vervolgbepaling. Geen algemene omkering van core/optie. |
| H6 | bevestigd; traceverlies verminderd zonder semantische vervanging | C/R: fusie is exact op ID (bron+offsets); alleen dezelfde span krijgt een unie. Overlap/nesting blijft aparte kandidaat. Ook RegelDetector voegt intern samen. F03 bewaart de oorspronkelijke bijdragen; beslisinput blijft de vlakke unie. |
| H7 | mechanisme bevestigd; omvang begrensd gemeten | A: op dev blokkeren generic-NP-bijdragen drie anders deterministische kandidaten in AWB04. IW01 heeft bovendien nominalisatiebewijs: weghalen van generic NP alleen herstelt daar determinisme niet. S1 laat zwak bewijs staan en levert daarom geen extra deterministische besluiten. |
| H8 | driftgevaar bevestigd, geen automatische metadata-afleiding verantwoord | C: plaatsprofiel heeft `middel`, terwijl LOCATION_* in STERK_BEWIJS staat. Voorwaarde en Parameter hebben `hoog`, maar hun codes zijn niet sterk. Klassenniveau ‘detecteerbaar’ is niet hetzelfde als regelbewijs voor één juridische klasse. De assert tussen STERK_BEWIJS en KLASSE_VAN_BEWIJS bewaakt alleen die twee codecollecties. |
| H9 | fout bevestigd en beperkt gerepareerd | T/R: mark+advcl komt voor bij ‘als dat van de dagtekening’ én het bestaande negatieve voorbeeld ‘als bestuurder’. F02 verlangt eigen verbale predicatie. Voorwaardelijk als blijft gevonden, bedoeld-in blijft gemaskeerd. Vergelijkingen met een eigen predicaat worden hiermee niet algemeen opgelost. |
| H10 | bevestigd; expliciet post-baseline | C: operators hebben geen operanden; afleidingen geen output/input/operatorrelaties. Dit is geen technisch ongeldig Candidate-contract. Frames zouden nieuwe juridische semantiek toevoegen. |
| H11 | vier geplande regels bevestigd | C/R: zie inventaris hieronder. Geen aantoonbare volledige JAS-familie die hierdoor ontestbaar wordt; gebrek aan devankers voor RF en L is een referentiebeperking. Geen geplande regel geïmplementeerd. |

## Problemenregister en beslissingen

Elke rij heeft precies één primaire categorie. Prioriteit P3 betekent hier dat de voorgestelde
wijziging een juridische of architecturale keuze vereist; het betekent niet dat het risico gering is.
Een profielmismatch voldoet aan criterium A, maar verplicht niet tot een ingrijpende semantische
correctie vlak vóór V7. Het toevoegen van een nieuwe normcontextgate bij generic NP is zo'n keuze.

| ID | probleem | primaire categorie | prioriteit | besluit |
|---|---|---|---|---|
| F01 | duurspan overschrijdt startgebeurtenis naar distributieve vervolgzin | SPAN_POLICY_ERROR | P1 | FIX_BEFORE_BASELINE — uitgevoerd, A/B |
| F02 | nominale vergelijkings-/hoedanigheidsfrase als conditionele clause | OVERBROAD_DETECTION | P1 | FIX_BEFORE_BASELINE — uitgevoerd, A/B |
| F03 | oorsprong van klassen verdwijnt bij interne merge en fusie | FUSION_DESIGN_LIMITATION | P2 | FIX_BEFORE_BASELINE — diagnostische opslag, D; semantische fusie blijft |
| F04 | Part geaccepteerd door als Inf bedoelde nominalisatietak | IMPLEMENTATION_BUG | P1 | FIX_BEFORE_BASELINE — uitgevoerd, A/B |
| D01 | generic NP-regel noemt normatief predicaat zonder dat te toetsen | PROFILE_IMPLEMENTATION_MISMATCH | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D02 | grammaticale rollen missen juridische governor/voice/dragerrelatie | MISSING_CONTEXT | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D03 | normatief signaal biedt RF zonder bewijs voor rechtsgevolg | EVIDENCE_MAPPING_ERROR | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D04 | -ing+nmod is onvoldoende actieherkenning; voorbeelden regeling/toepassing/dagtekening | OVERBROAD_DETECTION | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D05 | zwak bewijs en extra klassen blokkeren sterk patroonbewijs | DETERMINISTIC_POLICY_LIMITATION | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D06 | centrale sterktelijst heeft geen sluitende relatie met profielmetadata | PROFILE_IMPLEMENTATION_MISMATCH | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D07 | vergelijkend als met werkwoord, ellipsen en indirecte clause-attachment | PARSER_DEPENDENCY | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D08 | operanden, normrollen en afleidingsrelaties ontbreken | RELATION_MODEL_LIMITATION | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D09 | vier geplande regels en lexicale varianten ontbreken | UNDER_DETECTION | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D10 | Rechtsfeit/Plaats zonder devankers; provisional is onvolledig, geen juridische FP-score | EVALUATION_LIMITATION | P2 | DEFER_UNTIL_AFTER_BASELINE — inhoudelijke beoordeling in V7 |
| D11 | overige parserafhankelijke NP-/nominalisatiegrenzen, o.a. T3 parataxis en conjuncten | PARSER_DEPENDENCY | P3 | DEFER_UNTIL_AFTER_BASELINE |
| D12 | werkingsgebied/rol/bijwoord herkennen vereist meer dan lexicon | MISSING_CONTEXT | P3 | DEFER_UNTIL_AFTER_BASELINE |
| N01 | alle uitgebreide duurspans inkorten vanwege spankeuze=false | SPAN_POLICY_ERROR | P3 | DO_NOT_FIX — huidige uitgebreide span is expliciete profielkeuze |
| N02 | ‘dagtekening’ als woord uitsluiten van nominalisatie/RF | EVIDENCE_MAPPING_ERROR | P3 | DO_NOT_FIX — strijdig met expliciete profielvoorbeelden; context eerst |

**FIX BEFORE BASELINE:** F01–F04. Het [voorstel](hybrid-v1-fixvoorstel.md) is vóór iedere fix
vastgelegd, inclusief aanvullend F04 na diens reproductie. Geen P0-outputfout aangetoond.

**DEFER UNTIL AFTER BASELINE:** D01–D12. Generieke NP behouden is geen bevestiging van de
juridische klassen: V7 moet juist beoordelen hoe schadelijk die keuzeruimte is. Kandidaten op
parserafhankelijke brede spans blijven expliciet zichtbaar. Geen verhulde claim dat alle
detectie- of juridische fouten nu weg zijn.

## Generic NP: kwantitatief en tegenfeitelijk

Nulmeting vóór fixes: 296 ruwe detectoruitkomsten → 265 samengevoegde kandidaten.
Gemiddelde klassen: 2,341 vóór fusie, 2,438 na fusie vóór specificiteit, 2,400 erna.

| signaal | aantal | aandeel ruwe kandidaten (n=296) | aandeel fused kandidaten (n=265) |
|---|---:|---:|---:|
| SUBJECT_NP | 17 | 5,74% | 6,42% |
| OBJECT_NP | 98 | 33,11% | 36,98% |
| ENUMERATED_NP | 8 | 2,70% | 3,02% |
| generiek samen | 123 | 41,55% | 46,42% |

Deze drie signalen komen in deze set op verschillende spans voor. Van de 123 zijn 117
generic-only en 6 exact samengevallen met andere detectorbijdragen; 4 daarvan dragen sterk
bewijs. Alleen overlap of nesting veroorzaakt geen fusie. De nameting bevat afzonderlijk
`sterke_overlap_andere_grens` per kandidaat, met `binnen_sterk`, `bevat_sterk` of `overlap`.
In de nameting betreft dit 56 generieke kandidaten: 54 liggen binnen een sterke kandidaat,
2 omvatten er een; er zijn geen gedeeltelijke overlaps in deze groep. Deze aantallen staan
los van de 6 exacte samenvallingen en bewijzen geen ondersteuning voor dezelfde juridische functie.

Zes unieke kernankers berusten uitsluitend op generic NP: IW01/E02 en IW02/E03, E05, E06,
E08, E09. Inclusief opties komt IW02/E10 erbij. Dit zijn provisional ankers, geen gold.
De 16 unieke ankers van de **hele** NaamwoordgroepDetector omvatten ook rol- en
eigenschapsherkenning en mogen niet als generic-NP-bijdrage worden gepresenteerd.

Generic NP voegt vóór specificiteit 366 kandidaat-klassecombinaties toe tegenover dezelfde
spans zonder generic-bijdragen: 351 bij generic-only kandidaten en 15 bij de 6 gedeelde
kandidaten. Na specificiteit zijn dat 356 respectievelijk 11 bij de gedeelde kandidaten.
Dit zijn aantallen **combinaties**, geen 366 verschillende JAS-klassen.

De drie daadwerkelijk door generic NP geblokkeerde deterministische besluiten zijn AWB04:
‘de eerste veertien dagen’, ‘de daaropvolgende veertien dagen’, ‘de overige dagen’.
In IW01 blijft na NP-verwijdering NOMINALIZED_ACTION aanwezig; dat blijft een blokkade.

| scenario vóór fixes | spans/kandidaten | ankers kern | inclusief opties | kern mét klasse | gem. klassen | regelbesluiten | classifierkandidaten / batches | zonder hypothese |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 productie | 265 | 73/81 | 75/81 | 73/81 | 2,400 | 19 | 246 / 16 | 0 |
| S1 diagnostisch neutrale NP | 265 | 73/81 | 75/81 | 67/81 | 1,057 | 19 | 129 / 16 | 117 |
| S2 bestaande onafhankelijke hypotheses | 148 | 67/81 | 68/81 | 67/81 | 1,892 | 22 | 126 / 16 | 0 in juridische ruimte |

S1 behoudt spans, opties en bewijs en haalt alleen de juridische klassenbijdrage van generic NP
weg. Lege klassen zijn uitsluitend diagnostische rijen, geen ongeldige productie-Candidates.
De 117 niet-routeerbare rijen zijn **onopgelost werk**, geen gratis besparing. De bestaande
deterministische policy blijft zwak bewijs blokkeren. Gemiddelde bij S1 telt ook lege rijen.

S2 bewaart dezelfde syntactische spans buiten de juridische kandidaatruimte en gebruikt alleen
al aanwezige onafhankelijke hypotheses. Nieuwe contextuele hypotheses zijn niet gesimuleerd.
De juridische dekking van een toekomstige contextgenerator is onbekend. Dit is een ablatie,
geen bewezen vervanging. De derde tabelkolom meet spandekking, niet juridische juistheid.

Conclusie: generic NP helpt aantoonbaar bij **kandidaatdekking** (6 kernankers), maar daarmee
is niet aangetoond dat generic NP zelfstandig de juiste **juridische classificatie** draagt.
Geen van S1/S2 is productiegedrag geworden.

## Spanpolicy

| signaal | huidige core / opties | toets aan profiel en configuratie | besluit |
|---|---|---|---|
| TEMPORAL_DURATION | langste duur met voor-/na-uitbreiding; korte duur als kernoptie | startgebeurtenis hoort expliciet bij T-profiel; model kan opties niet kiezen | alleen F01; verdere minimale core na V7 onderzoeken |
| CONDITIONAL_CLAUSE | lexicaal tot komma/punt; syntactisch hele aaneengesloten subboom | profiel noemt eis én bereik; clause is betekenisdragende eenheid | F02 corrigeert signaaltoekenning, geen algemene clauseverkorting |
| NOMINALIZED_ACTION | subboom zonder directe bijzinnen/parataxis, meestal zonder opties | handeling plus argumenten is plausibele kern; -ing en parserbewijskracht onvoldoende | F04 grammaticale Inf-controle; overige grenzen/context uitgesteld |
| NORMATIVE_PREDICATE | normsegment; langere zin als optie | segment/clause staat expliciet in implementatie en profiel | behouden; los modaal woord zou context verliezen |
| CALCULATION_* | bedraagt-segment of passieve formule met rechtse uitbreiding; formulekern als optie | uitvoer, bewerking en invoer horen bij de regel; geen verplichting tot één werkwoord | behouden; uitbreiding over meerdere deelzinnen als beperking; geen DerivationFrame |
| DELEGATION_FORMULA | bevoegdheidsformule met onderwerp tot . of ; | reikwijdte gedelegeerd onderwerp expliciet vereist | behouden; niet tot ‘regels gesteld’ inkorten |

Ook de andere detectoren zijn op core/opties gecontroleerd (matrix). Bij definitie staat
slotinterpunctie in de core, bij plaats een eventueel voorzetsel, bij subject beperkte
modifiers. De evaluatie normaliseert alleen randinterpunctie/witruimte; het runtimeanker
wordt daardoor niet veranderd. `candidate_recall_incl_opties` is met spankeuze uit alleen
beschikbare grensinformatie, **geen bereikbare classifier-annotation-recall**.

## Geplande regels

Alle `candidate_rules` zijn doorzocht; precies vier hebben status `gepland`. De code laat zien
welke voorzieningen ontbreken. Een historische productreden voor uitstel is niet voor elke
regel gedocumenteerd; onderstaande technische verklaring is geen verzonnen besluitgeschiedenis.
De synthetische voorbeelden zijn lokaal uitgevoerd, zonder ze aan de referentieset toe te voegen.

| regel | klasse | wat ontbreekt / reden voor terughoudendheid | actuele gemiste voorbeeldcapaciteit | bewijs provisional | FP-risico | vóór baseline? |
|---|---|---|---|---|---|---|
| jas.tijd.voorzetselgroep | T | algemene temporele voorzetselgroep buiten datum/duur/periodepatronen; ‘voor/na’ vereist context | `Binnen een redelijke termijn beslist het bestuursorgaan`: NP, geen T | T-kernankers 9/9 gedekt; LI-D3 kent wel tijdsgaten, maar bewijst niet dat deze geplande regel ze oplost | doel-, rang- of plaatsvoorzetsel als tijd | DEFER_UNTIL_AFTER_BASELINE |
| jas.delegatie.grondslag_wti | D, subtype invulling | broncontext bevat tekst/ouderaanhef, geen WTI-grondslag als detectorinvoer; graafvoorziening niet aangesloten als detector | `Gelet op artikel 3 van de wet worden deze regels vastgesteld`: geen D | delegatie 2/2 betreft bevoegdheid; geen invullingsanker | iedere verwijzing als delegatie-invulling aanmerken | DEFER_UNTIL_AFTER_BASELINE |
| jas.waarde.numeriek | V, mogelijk P | numerieke detector heeft specifieke notaties, geen algemene getalhypothese; semantiek variabele/parameter onbeslist | `Het aantal bedraagt 42`: AR en eigenschaps-NP, geen kandidaat voor `42` | V 7/8; gemist WZT02 betreft lange inkomens-NP, niet kaal getal; P 5/5 | artikelnummers, labels, ranggetallen, voorbeelden | DEFER_UNTIL_AFTER_BASELINE |
| jas.feit.gebeurtenisbijzin | RF | contextuele relatie gebeurtenis→rechtsgevolg ontbreekt | `Zodra de aanvrager overlijdt, vervalt de aanspraak`: geen RF-clause | geen RF-devankers: nul bewijs voor omvang recallgat; nominalisatie is wel actief en synthetisch getest | iedere gebeurtenis als juridisch feit, verwarring met VW/T | DEFER_UNTIL_AFTER_BASELINE |

Geen volledige JAS-familie wordt door deze vier ontbrekende regels ontestbaar. RF heeft
nominalisatietests, plaats heeft regeltests, delegatie heeft bevoegdheidstests. Dit zegt niets
over volledige **subtype**dekking: delegatie-invulling is expliciet nog niet gedekt.

## Bewijs, hypothesen en meetbaarheid na V7

Voor F03 bevatte Candidate bewijs en klassen als losse lijsten; het beslisregister bevatte
codes en detectornamen maar geen ruwe klassenbijdragen per regel. Het register kon daardoor
niet betrouwbaar onderscheiden of bijvoorbeeld RO uit NP of uit nominalisatie kwam.

F03 voegt `DetectieBijdrage` toe aan detectorresultaat en fusieresultaat, buiten Candidate:
kandidaat-ID, detector/versie, eventuele declaratieve regelversie, gezamenlijk aangeboden
klassen, oorspronkelijke evidence en spanopties. Declaratieve regels worden vóór hun interne
merge opgenomen. Structuur-/syntactische resultaten worden vóór fusie opgenomen. Eén bijdrage
met meerdere bewijsstukken betekent **gezamenlijke** ondersteuning, geen verzonnen
één-op-één evidence-classmapping.

Het beslisregister en het additieve API-veld `detectiebijdragen` bewaren dit ook bij afwijzing.
De opslag gebruikt de bestaande batch-audit; geen database- of RDF-migratie. Oude registers
zonder dit veld blijven geldig en krijgen een lege lijst, wat ‘niet vastgelegd’ betekent.
De bestaande bewijsfingerprint en alle classifier-/reviewerfuncties blijven ongewijzigd.
API-roundtrip en end-to-end emitter zijn getest; de P2-vergelijking is voor alle 18 bronnen
identiek qua kandidaten, routing, parserresultaat en classifierinvoer.

Een toekomstig EvidenceHypothesis kan hierop aansluiten met klassegebonden bewijskracht,
relationele context en ondersteunings-/tegenbewijsrelaties. Die semantiek is niet ingevoerd.
V7 kan nu per oorspronkelijke bijdrage fouten adjudiceren, maar contextlabels en juridische
waarheid moeten nog door mensen worden toegevoegd.

## Before/after, controle en stop

De exacte nameting, scenario's na alle fixes, casusverschillen en testresultaten staan in
[het freeze-document](hybrid-v1-baseline-freeze.md) en de meetbestanden. Alle veranderingen
in de ontwikkelset worden veroorzaakt door F04; F01/F02 veranderen alleen de aangetoonde
diagnostische gevallen. F03 heeft geen besliseffect. Modelkwaliteit, juridische precision/F1
en feitelijke reviewerload zijn niet opnieuw gemeten; er zijn geen verse modelcalls gedaan.

Er worden geen P0/P1-problemen open gelaten waarvoor een minimale, onderbouwde detectorfix
is vastgesteld. Resterende problemen vereisen semantische keuzes of adjudicated gegevens.
De expliciete vervolgstap is **V7 — juridisch geadjudiceerde baseline**, niet een volgende
detectoriteratie.
