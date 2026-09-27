# hybrid_v1 — voorstel BASELINE FREEZE

**Voorstel: bevries codecommit `3b5118670790a360f3f2e35f0536cd4d1141a2ed` en onderstaande
configuratie. Sluit de detectoriteratie af en start V7 — juridisch geadjudiceerde baseline.**

Datum: **27 september 2026**, vastgelegd om 22:46 CEST. Basis is actuele master
`9de992226e18514f40d96dd29ed98498e747ffe6` (V6). De wijzigingen staan op
`audit/hybrid-v1-baseline-freeze`. Dit document bevriest een expliciete codebasis en
configuratie; het verklaart geen referenties tot gold en verandert geen deployment.
De SHA verwijst naar de laatste code/testcommit vóór deze documentatiecommit, zodat de
freeze geen zelfverwijzende commit-hash nodig heeft.

Het [auditrapport](hybrid-v1-detector-audit.md) bevat de 15-detectorenmatrix, H1–H11,
spanpolicy, geplande regels, probleemtaxonomie en generic-NP-analyse. Het
[fixvoorstel](hybrid-v1-fixvoorstel.md) legt bewijs, risico en regressies per fix vast.
Het [machineleesbare manifest](metingen/hybrid-v1-freeze/manifest.json) is de volledige
inventaris van versies, configuratie en SHA-256's.

## Uitgevoerde wijzigingen en nameting

| fix | verandering | grond |
|---|---|---|
| F01 | duuruitbreiding stopt vóór `en elk/ieder van …`; startgebeurtenis blijft onderdeel van de kandidaat | bestaande T3-trace gereproduceerd, profielconforme grens |
| F02 | syntactische als-bijzin vereist verbale predicatie; nominale vergelijking/hoedanigheid wordt niet meer zo aangemerkt | bestaande T4-trace en negatieve profielvoorbeelden gereproduceerd |
| F03 | oorspronkelijke detector-/regelbijdragen blijven bewaard in het beslisregister, ook bij afwijzing | uitsluitend traceerbaarheid; geen gewijzigde beslisinput |
| F04 | de infinitieftak van nominalisatiedetectie vereist `VerbForm=Inf` | drie bestaande devgevallen hadden aantoonbaar `Part` |

Voor iedere fix is eerst een falende regressie aangetoond. Implementatiecommits:
`d35aa90` (F01/F02), `0945ec3` (F03), `b0bdc92` (F04); `3b51186` voegt de
PostgreSQL-roundtripcontrole toe. Nulmeting en harnas: `d5185d5`.

| ontwikkelsplit: 16 cases, 81 provisional ankers | vóór | na |
|---|---:|---:|
| ruwe detectoruitkomsten | 296 | 293 |
| fused kandidaten | 265 | 262 |
| kernankerdekking | 73/81 (90,12%) | 73/81 (90,12%) |
| inclusief spanopties | 75/81 (92,59%) | 75/81 (92,59%) |
| kernankers met aangeboden klasse | 73/81 | 73/81 |
| gemiddelde possible_classes | 2,400 | 2,393 |
| deterministische voorstellen | 19 | 19 |
| classifierkandidaten | 246 | 243 |
| universele classifierbatches | 16 | 16 |

De drie verdwenen devkandidaten zijn uitsluitend ‘het bepaalde in de volgende leden’ (IW02),
‘het bepaalde’ (IW03) en ‘het bepaalde in het vijfde lid’ (WZT04). Er verdwijnt **geen gedekt
provisional anker**, ook geen klassegedekt anker. Deze drie bronnen krijgen wel andere
classifierinvoer; de gevolgen voor modelkeuzes zijn niet opnieuw gemeten.

Op IW-D2 blijft het aantal kandidaten 39. Eén te brede termijnspan wordt vervangen door
‘één maand na de dagtekening van het aanslagbiljet’, met een nieuwe stabiele span-ID.
De specificiteitsverklaring bij de geneste kern ‘één maand’ verwijst daardoor naar de kortere
winnaar; klassen en route blijven gelijk. Deze wijziging betreft een deterministisch voorstel
en verandert de classifierinvoer daar niet. Op LI-D3 daalt het aantal kandidaten van 45 naar
44 doordat ‘als dat van de dagtekening’ vervalt; classifierlabels schuiven en de invoer wijzigt.

F03 is afzonderlijk vergeleken met de toestand na F01/F02: kandidaten, routing, parserresultaat
en classifierinvoer zijn identiek voor alle 18 onderzochte bronnen. De extra metadata heeft
geen semantische besliswerking en wordt niet in prompts opgenomen.

| tegenfeitelijk scenario ná fixes | juridische/spankandidaten | ankers kern / opties | kern met klasse | gem. klassen | deterministisch | classifier / batches | zonder hypothese |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 productie | 262 | 73/81 / 75/81 | 73/81 | 2,393 | 19 | 243 / 16 | 0 |
| S1 diagnostisch neutrale NP | 262 | 73/81 / 75/81 | 67/81 | 1,034 | 19 | 126 / 16 | 117 |
| S2 uitsluitend bestaande onafhankelijke hypotheses | 145 | 67/81 / 68/81 | 67/81 | 1,869 | 22 | 123 / 16 | buiten juridische ruimte |

S1/S2 zijn **uitsluitend metingen**. De 117 generic-only spans verdwijnen in S2 niet uit de
syntactische inventaris. Een nog te ontwerpen contextgenerator is niet gesimuleerd. Minder
routeerbare kandidaten betekent geen bewezen verbetering. Er zijn nul verse modelruns;
juridische precision/F1, reviewerload en modelbeslisstabiliteit zijn hier niet opnieuw gemeten.

## Bevroren versies en configuratie

| onderdeel | vastgelegde waarde |
|---|---|
| Python | `3.14.3` |
| spaCy | `3.8.16` |
| taalmodel | `nl_core_news_md 3.8.0` |
| taalprovider | `spacy:nl_core_news_md`; echte parse vereist voor vergelijkbare baseline |
| agentpakket | `graph-qa 0.1.0`; code-identiteit is de volledige freeze-SHA |
| JAS | `1.0.10`, bron `minbzk/wetsanalyse 5ae93cc` |
| methodeversie in AgentRun | `4fda12e4bc9a` |
| methodepakket | `2.1`, SHA-256 `8ed090655579c6f5b94fd7c0de40edbbbd4a723975ea6c570e4a3f0b64aa1aca` |
| profielenbundel | SHA-256 `3ab5ab0888d359ef4f3ec0c3fa985aeeaa1e8d1b15e56050e0a4f37e8b7504ab` |
| detectorregels inclusief lijsten/maskers | SHA-256 `85babde63edd68630154b1e6893648f7c7df7bd7977cd92baeab19c17a07c942` |
| classifier-promptversie | `97ae4ea7f557` |
| classifier systeemprompt SHA-256 | `9cd5a7d2e1325b1ed21365643f4edb7c4a2782f29579d50517c98ff4532f9d8a` |
| classifier systeem + alle officiële klassen SHA-256 | `de66c0f455c713de7fa890da6ad21b0b259ec809986cba9c27d0b8d8237b9482` |
| reviewer systeemprompt SHA-256 | `688aedac74a2636275e246c3cbebd5cb455f217159acda134b1982c42b41f94f` |
| deterministisch accepteren | `true` |
| classifiergranulariteit | `universeel` |
| classifier-spankeuze | `false` |
| classifiertemperatuur | `null` — providerdefault |
| gerichte review | `true` |
| model/providerconfiguratie | `claude-sonnet-4-6` / `anthropic_via_azure_foundry` |
| gegenereerde vocabulaireversie | `4089e3ffd8c1` |

De profielen hebben geen eigen handmatig versienummer: de bundelhash is de versie.
De hashprocedure en iedere bestandshash staan in het manifest, inclusief de dependencylocks,
beide promptbronbestanden en alle declaratieve regel-ID's met versies. De korte bestaande
classifier-promptversie bevat niet het dynamische klassenblok; daarom zijn hierboven ook de
volledige systeemprompt en alle officiële klasseomschrijvingen gehasht. Per casus staat de hash
van de concrete classifierinvoer in de nameting.

| detector | versie |
|---|---|
| afleiding | `1.1.1` |
| delegatie | `1` |
| numeriek | `1.1.1` |
| operator | `1.1.1` |
| plaats | `1.1` |
| subject | `1` |
| tijd | `1.2.1.1.1.1.1` |
| voorwaarde | `1.1.1.1` |
| definitie | `1` |
| betekenis | `1` |
| norm | `1` |
| naamwoordgroep | `1` |
| bijzin | `2` |
| nominalisatie | `2` |
| logisch | `2` |

Voor een deterministisch voorstel blijven precies één mogelijke klasse en uitsluitend sterke
bewijscodes vereist; PRIORITY_APPLIED is administratief. De sterke codes zijn ARITHMETIC,
COMPARISON, DEFINITION_ITEM, DEFINITION_SENTENCE, DELEGATION_FORMULA, LOCATION_DESCRIPTION,
LOCATION_NAME, TEMPORAL_DATE, TEMPORAL_DURATION, TEMPORAL_MOMENT, TEMPORAL_PERIOD_OF en
TEMPORAL_RELATIVE_PERIOD. Afwijzing door specificiteit blijft een aparte deterministische route.
Er is geen bewijssterkte uit profielmetadata afgeleid en geen whitelist aangepast.

Voor V7 moet iedere daadwerkelijke run deze code/configuratie, bronhashes, referentiesetversie
en model/provideridentiteit vastleggen. Zet `AGENT_VERSION` op de freeze-SHA om dezelfde
pakketversie te onderscheiden van oudere code. De vaste modelnaam is geen garantie op
bit-identieke provideruitvoer; die variatie hoort in de baseline te worden gemeten.

## Verificatie en beschermde inhoud

De [verificatiegegevens](metingen/hybrid-v1-freeze/verificatie.json) bevatten resultaten per
stap en de gebruikte commando's. Laatste controles:

- Detector-/syntactische-/profieltests plus nieuwe detectorregressies: **188 geslaagd**.
- Volledige graph-qa-suite met tijdelijke PostgreSQL: **1.093 geslaagd, 2 overgeslagen**.
  De 17 Postgres-integratietests zijn uitgevoerd. De twee skips betreffen een door RDFLib niet
  ondersteunde GraphDB-query en een niet aanwezige API-router in de graph-qa-omgeving;
  ze zijn geen detector- of parser-skips. Bestaande RDFLib-deprecationwarnings blijven gemeld.
- Volledige API-suite: **432 geslaagd, 7 overgeslagen** wegens ontbrekende Postgres-DSN in
  die run. Die 7 zijn aansluitend samen met de nieuwe trace-roundtriptest uitgevoerd tegen
  tijdelijke PostgreSQL: **8 geslaagd, 0 overgeslagen**. De projector gebruikt de bestaande
  RDFLib HTTP/SPARQL-testadapter; er is geen live GraphDB-deployment getest of gewijzigd.
- 732 ruwe/fused kandidaatspans uit dev en diagnostiek gecontroleerd op letterlijke tekst,
  geldige offsets en stabiele ID. Geen gedegradeerde parserresultaten, geen devankerverlies.
- Oude registers en afwijzingen blijven leesbaar; nieuwe detectiebijdragen overleven de
  API-batch en PostgreSQL-opslag/export. Er is geen schema- of datamigratie nodig.
- Diff en SHA-256-controle van 53 beschermde bestanden bevestigen ongewijzigde
  classifier/reviewerprompts, JAS-definities/herkenningsvragen, profielen in de nameting,
  methodebronnen, provisional/gold/adjudicatiegegevens en GraphDB-projectielogica.

De enige gewijzigde RDF-vocabulairegegevens zijn **de versie van jas.tijd.duur (1→2)** en
de daaruit gegenereerde vocabulairehash. De bijbehorende JSON wijzigt alleen die hash.
Dit is expliciete provenance, geen wijziging van klassen, definities of projectieregels.

Voor lokale herhaling vanuit `tools/graph-qa`:

```bash
uv sync --frozen --extra dev --extra nlp --extra mcp
.venv/bin/python -m pytest tests/test_detectoren.py tests/test_syntactische_detectoren.py tests/test_detectieprofielen.py tests/test_detector_freeze_regressies.py -q
.venv/bin/python -m eval.detector_audit --json /tmp/hybrid-v1-herhaling.json --vergelijk ../../docs/architectuur/metingen/hybrid-v1-freeze/na.json
```

Gebruik voor de volledige integratiesuite een lege, tijdelijke PostgreSQL volgens de
testmodule-instructies, met `RUNSTORE_TEST_DSN` respectievelijk `ANNOTATIE_TEST_DSN`.
De auditbestanden liggen in de documentatiecommit; de runtimecode blijft de genoemde freeze-SHA.

## Bekende beperkingen en POST-BASELINE EXPERIMENTS

Bewust behouden beperkingen:

- Generic NP toetst geen normatief predicaat, voice of juridische actor/objectrelatie;
  de huidige regelnamen suggereren meer context dan de implementatie gebruikt.
- NORMATIVE_PREDICATE biedt ook Rechtsfeit; -ing+nmod bewijst geen handeling met rechtsgevolg.
  ‘Dagtekening’ is niet generiek uitgesloten en vereist juridische context.
- Fusie en classifier gebruiken nog een vlakke klassenunie. Sterk bewijs kan door zwak
  bewijs worden geblokkeerd; plaatsbewijs is sterker gerouteerd dan profiel `middel` suggereert.
- Spanopties zijn diagnostisch, niet kiesbaar. Brede clause-/nominalisatiespans en andere
  conjunctiegrenzen blijven parser-/contextafhankelijk. F01 is geen algemene spanparser.
- Vergelijkend als met eigen werkwoord, elliptische voorwaarden en foutieve clause-attachment
  zijn niet algemeen opgelost. Sommige conditionele als-gevallen in LI-D3 worden nog gemist.
- Operators/afleidingen dragen geen operanden of input/outputrelaties.
- Gepland maar niet ingevoerd: tijd.voorzetselgroep, delegatie.grondslag_wti, waarde.numeriek,
  feit.gebeurtenisbijzin. Delegatie-invulling heeft nog geen eigen detectorroute.
- Provisional ankers zijn geen gold; Rechtsfeit en Plaatsaanduiding hebben geen devankers.
  Juridische impact, werkelijke foutpercentages en reviewerload vereisen V7.

**POST-BASELINE EXPERIMENTS**, pas met een vastgelegde V7-baseline als vergelijkingspunt:

1. CandidateHypothesis / EvidenceHypothesis: klassegebonden ondersteuning en tegenbewijs.
2. Generic NP uitsluitend als syntactisch bewijs, met contextueel gevormde hypotheses.
3. Minimal NormFrame met predicaat, clause, voice en drager/objectrelaties.
4. ComparisonFrame met vergelijkingsoperator en operanden.
5. DerivationFrame met uitvoer, invoer en bewerking.
6. Regelgebonden bewijssterkte en expliciete routingpolicy naast profielmetadata.
7. Contextuele connectiefdisambiguatie, inclusief vergelijking, hoedanigheid en ellips.
8. Specialistische JAS-classifier, getoetst op contractfouten en juridische beslissingen.
9. Gerichte evaluatie van de vier geplande regels en van core/context-spanbeleid.

Er resteren binnen deze audit geen open P0/P1-detectorproblemen met een onderbouwde minimale
fix. De relevante tests zijn groen; de meetinfrastructuur bewaart oorspronkelijke bijdragen.
Resterende verbeteringen vragen semantische keuzes of adjudicated gegevens. Daarmee is het
stopcriterium bereikt: **stel hybrid_v1 nu vast als bevroren uitgangspunt en voer V7 uit.**
