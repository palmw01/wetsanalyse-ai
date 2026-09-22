# Bronnen en herleidbaarheid — methode 2.1

Dit register hoort bij de skill. M-ID's verwijzen naar oorspronkelijke methodebronnen;
P-ID's hieronder zijn **projectbesluiten**, geen citaten of wetenschappelijke claims.
Bewaarlocaties, versies en hashes: [manifest](../../../../docs/wetsanalyse/bronnen/manifest.json).
De oorspronkelijke bronbestanden worden niet aangepast bij een wijziging van de skill.

## Methodebronnen

| ID | Bron en specifieke vindplaats | Waarvoor gebruikt / beperking |
|---|---|---|
| M01 | Ausems, Bulles & Lokin (2021), lokaal boek, h.3 werkwijze, h.4 klassen, h.6 en7 toepassingen | Juridische functies, interpretatie, fragmenten en grammaticale reconstructie. Voorbeelden hebben hun eigen historische context. |
| M02 | Handleiding 1.0 (2023), activiteit 2; PDF p.33–35 (gedrukt p.32–34) | Fragmentgrenzen en centrale klasse met samenhang; diagrammen controleren naast tekstextractie. |
| M03 | Leidraad 1.0 (2023), tabellen activiteiten/producten, p.17–22 | Afbakening afhankelijk van doel en samenwerking van disciplines. |
| M04 | [Rijksspecificatie](https://minbzk.github.io/wetsanalyse/), lokaal H2 per klasse; H3 begrippenkader | Bronvelden van dertien gecombineerde labels. H2 Tijdsaanduiding/Plaatsaanduiding bevat expliciete prioriteit; geen algemene voorrang afleiden uit H3. |
| M05 | [WetsTaal 1](https://regels.overheid.nl/standaarden/wetstaal), lokale werkversie 2024-10-18, §4 en §§5–13 | Patronen van rechtsbetrekkingen; onvoltooide onderdelen en voorbeeldinconsistenties niet tot harde regels verheffen. |
| M06 | [Bulles & Van der Hoven](https://regels.overheid.nl/publicaties/doorontwikkelingen-en-voortschrijdend-inzicht-in-wetsanalyse/download), 2024-11-18, §1.4–1.5, §2, §3 | JRM 2, scenario's, expliciete gevolgen/relevante feiten. Werkversie; [lokale PDF](../../../../docs/wetsanalyse/bronnen/jrm2-2024-11-18.pdf) en [doorzoekbare tekst](../../../../docs/wetsanalyse/bronnen/jrm2-2024-11-18.pages.md), via PNA bewaard; zie manifest. |
| M07 | [Aanwijzingen voor de regelgeving](https://www.kcbr.nl/print-instrument/12640), 3.2, 3.10–3.12, 3.35, 3.60, 4.43, 4.47 | Formulering, ficties/vermoedens, bereik en wetstoelichting. Schrijfrichtlijnen zijn geen mechanische interpretatiemachine. |
| M08 | [An Annotation Language for Semantic Search of Legal Sources](https://aclanthology.org/L18-1177/), 2018, annotatieschema en evaluatie, p.1096–1100 | Onderscheid talige signalen en juridische betekenis; annotatievragen contextueel beoordelen. |
| M09 | [Deciphering disagreement in the annotation of EU legislation](https://link.springer.com/article/10.1007/s10506-024-09423-9), annotatieproces, disagreement en discussion | Gescheiden beoordeling, adjudicatie, interpretatieruimte en beperkingen van agreement-metingen. |
| M10 | [W3C Web Annotation Data Model](https://www.w3.org/TR/2017/REC-annotation-model-20170223/), §4.2.4 Text Quote Selector en §4.2.5 Text Position Selector | Exact citaat/context/positie; posities zijn versiegevoelig. Geen reden om de bestaande ankers te vervangen. |

## Beslisregister: van bron naar instructie

| Regel | Skillonderdeel | Basis | Eigen keuze / afwijking |
|---|---|---|---|
| P01 | Analyseprotocol §1 | M01 h.3; M03 producten | Vast Markdown-contract, B/N/E/R-ID's en expliciete peildatum. |
| P02 | Analyseprotocol §2 | M01 h.7, bespreking Awb 2:9 en2:10; M07; M08 | Grammatica als expliciete voorafgaande controle; geen nieuwe parser vereist. |
| P03 | Analyseprotocol §3; verwijzingen | M01 interpretatiemethoden; M07 4.43/4.47 | Materiële keuzes en onzekerheid in een afzonderlijk beslisregister. |
| P04 | Fragmentgrenzen | M02 activiteit 2; M01 h.4/7 | Normeenheid, letterlijk fragment en semantisch element apart vastleggen; geen contextloze woordregels. |
| P05 | Samenloop | M04 H2 tijd/plaats; M02 samenhang | Eerdere veralgemening van H3 ingetrokken; overlap en alternatieven apart behandelen. |
| P06 | Verwijzingen volgen | M01 werkgebied; M04 delegatie/definities | Relevantiegestuurde wachtrij; startbudget 20 passages; geen vaste dieptecap. Budget is niet uit een bron afkomstig. |
| P07 | JRM-verrijking | M06 §§2–3; M01 h.4 | Dertien JAS-labels behouden; JRM-inhoud in dossier. Immuniteit niet stilzwijgend verwijderen. |
| P08 | Scenario's en dekking | M06 §1.4/2.1; M02 | Scenario's toetsen corpusanalyse; geen claim van zuivere JRM-methode of uitputtende scenarioruimte. |
| P09 | Kwaliteit en review | M09; M08 | Rubriek, blokkerende kritieke fouten, 24 casussen, familie-split en drie herhalingen zijn projectkeuzes. |
| P10 | Bronverankering | M10; bestaand Anker-contract | Bestaande offsets/context/hash behouden; versie apart in document vastleggen. |
| P11 | Runtimeprotocol | P02–P05/P09; huidige beperkte API | Compacte secties genereren naar prompts; ontbrekende context melden, geen brononderzoek veinzen. |
| P12 | Agentimport | P01–P11 | Selectie per bestaande rol, stabiele sectie-ID’s, generatie, hashes en technische logging; geen uitbreiding van tools of uitvoercontracten. |

## Onderhoud

Bij iedere inhoudelijke wijziging: pas de betrokken P-regel aan, vermeld bron + sectie
of markeer het als projectkeuze, verhoog de methodeversie bij betekeniswijziging en
regenereer het runtimeprotocol. Controleer de regressies en beoordeel geraakte voorbeelden
opnieuw. Een SHA-wijziging vereist controle van het nieuwe bronexemplaar; gebruik geen
stil bijgewerkte webpagina onder een oude versieaanduiding.

## Bijstelling 2.1 na eerste modelproef

Op 2026-09-12 liet de proef met protocol 2.0 nog losse gezegden en dubbele
tijdsduur/parameterduidingen zien. P04/P05 zijn daarom explicieter gemaakt voor
enkelvoudige normzinnen en dezelfde temporele functie. Dit is een operationele
verduidelijking van de projectregels, geen nieuw voorschrift uit JRM. De eerste
uitkomsten blijven ongewijzigd in modelvergelijking.json; de gerichte hertoets
wordt afzonderlijk opgeslagen.
