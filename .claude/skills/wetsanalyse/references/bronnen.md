# Bronnen en herleidbaarheid — methode 3.0

Dit register hoort bij de skill. M-ID's verwijzen naar oorspronkelijke methodebronnen;
P-ID's hieronder zijn **projectbesluiten**, geen citaten of wetenschappelijke claims.
Bewaarlocaties, versies en hashes: [manifest](../../../../docs/wetsanalyse/bronnen/manifest.json).
De oorspronkelijke bronbestanden worden niet aangepast bij een wijziging van de skill.

## Methodebronnen

| ID | Bron en specifieke vindplaats | Waarvoor gebruikt / beperking |
|---|---|---|
| M01 | Ausems, Bulles & Lokin (2021), *Wetsanalyse*, lokaal boek: h.3 de aanpak (stap 1 werkgebied, stap 2 structuur, stap 3 betekenis en interpretatie, stap 4 valideren, stap 5 uitvoeringsbeleid), h.4 het analyseschema (per klasse: omschrijving, vraag, uitdrukkingswijze, subklassen, relatie met eigen en andere klassen), h.6 en 7 toepassingen | Juridische functies, interpretatie, fragmenten en grammaticale reconstructie. Voorbeelden hebben hun eigen historische context. |
| M02 | Handleiding 1.0 (2023): §3.3 activiteit 1 (deelactiviteiten 1a–1g), §3.4 activiteit 2 (deelactiviteiten a–c; PDF p.33–36, gedrukt p.31–35), §3.5 activiteit 3, §3.6 activiteit 4 | Het werkgebied, de markeerregels en de centrale klasse met samenhang, het valideren; diagrammen controleren naast tekstextractie. Alleen in eigen woorden; niet herpubliceren. |
| M03 | Leidraad 1.0 (2023), tabellen activiteiten/producten, p.17–22 | Afbakening afhankelijk van doel en samenwerking van disciplines. |
| M04 | [Rijksspecificatie](https://minbzk.github.io/wetsanalyse/), publicatieversie 1.0.10 (2024-11-29, commit 5ae93cc; zie `docs/wetsanalyse/wetsanalyse-rijk/BRON.md` en ADR-001 §1), lokaal H2 per klasse; H3 begrippenkader | Bronvelden van dertien gecombineerde labels. H2 Tijdsaanduiding/Plaatsaanduiding bevat expliciete prioriteit; geen algemene voorrang afleiden uit H3. |
| M05 | [WetsTaal 1](https://regels.overheid.nl/standaarden/wetstaal), lokale werkversie 2024-10-18, §4 en §§5–13 | Patronen van rechtsbetrekkingen; onvoltooide onderdelen en voorbeeldinconsistenties niet tot harde regels verheffen. |
| M06 | [Bulles & Van der Hoven](https://regels.overheid.nl/publicaties/doorontwikkelingen-en-voortschrijdend-inzicht-in-wetsanalyse/download), 2024-11-18, §1.4–1.5, §2, §3 | Onderbouwt JAS-keuzes waar de werkversie het analyseschema toelicht (de soorten rechtsbetrekkingen, de plaats van voorwaarden); wat zij aan het JAS toevoegt, staat in de skill wetsuitvoering. Werkversie; [lokale PDF](../../../../docs/wetsanalyse/bronnen/jrm2-2024-11-18.pdf) en [doorzoekbare tekst](../../../../docs/wetsanalyse/bronnen/jrm2-2024-11-18.pages.md), via PNA bewaard; zie manifest. |
| M07 | [Aanwijzingen voor de regelgeving](https://www.kcbr.nl/print-instrument/12640), 3.2, 3.10–3.12, 3.35, 3.60, 4.43, 4.47 | Formulering, ficties/vermoedens, bereik en wetstoelichting. Schrijfrichtlijnen zijn geen mechanische interpretatiemachine. |
| M08 | [An Annotation Language for Semantic Search of Legal Sources](https://aclanthology.org/L18-1177/), 2018, annotatieschema en evaluatie, p.1096–1100 | Onderscheid talige signalen en juridische betekenis; annotatievragen contextueel beoordelen. |
| M09 | [Deciphering disagreement in the annotation of EU legislation](https://link.springer.com/article/10.1007/s10506-024-09423-9), annotatieproces, disagreement en discussion | Gescheiden beoordeling, adjudicatie, interpretatieruimte en beperkingen van agreement-metingen. |
| M10 | [W3C Web Annotation Data Model](https://www.w3.org/TR/2017/REC-annotation-model-20170223/), §4.2.4 Text Quote Selector en §4.2.5 Text Position Selector | Exact citaat/context/positie; posities zijn versiegevoelig. Geen reden om de bestaande ankers te vervangen. |
| M11 | [NL-SBB 1.0](https://docs.geostandaarden.nl/nl-sbb/nl-sbb/), §§ Definitie, Uitleg, Toelichting, Voorbeeld; Forum Standaardisatie: pas-toe-of-leg-uit sinds 1 jan 2026 | Rol van definitie (`skos:definition`), uitleg in eenvoudige taal (`rdfs:comment`), toelichting (`skos:scopeNote`), voorbeeld (`skos:example`) en bron (`dct:source`). |
| M12 | [Schrijven op B1-niveau – Rijksoverheid/Direct Duidelijk](https://www.communicatierijk.nl/vakkennis/rijkswebsites/aanbevolen-richtlijnen/taalniveau-b1) | Korte zinnen, actieve vorm, bekende woorden, vaktermen uitleggen, voorbeelden. Richtlijn, geen meetbare norm: de drempels zijn projectkeuzes. |
| M13 | [TOOI – Thesauri en Ontologieën voor Overheidsinformatie](https://standaarden.overheid.nl/tooi), waardelijsten rwc_ministeries_compleet (versie 6) en scw_toplijst (versie 1), CC0 | Vaste URI's voor ministeries en thema's; snapshots in `tools/bwb-import/app/tooi_ministeries.json` en `api/app/tooi_themas.json`, met bron en datum. |
| M14 | Expertisecentrum BRM Belastingdienst, tabel *soorten zoekvragen* bij de bronselectie (intern, lokaal bewaard, zie manifest) | Vier zoekvragen vanuit een gebeurtenis: bestaansrecht, rechtsgeldigheid, rechtsgevolgen en nadere invulling. Alleen in eigen woorden in de skill; niet herpubliceren. |

## Beslisregister: van bron naar instructie

| Regel | Skillonderdeel | Basis | Eigen keuze / afwijking |
|---|---|---|---|
| P01 | Analyseprotocol §1 | M01 h.3 stap 1 en stap 2; M03 tabellen activiteiten/producten (p.17–22) | Vast Markdown-contract, B/N/E/R-ID's en expliciete peildatum. |
| P02 | Analyseprotocol §2 | M01 h.7, bespreking Awb 2:9 en2:10; M07; M08 | Grammatica als expliciete voorafgaande controle; geen nieuwe parser vereist. |
| P03 | Analyseprotocol §3; verwijzingen | M01 h.3 stap 3, onderdelen c (interpretatie) en d (jurisprudentie); M07 4.43/4.47 | Materiële keuzes en onzekerheid in een afzonderlijk beslisregister. |
| P04 | Fragmentgrenzen | M02 §3.4 activiteit 2, deelactiviteit a; M01 h.4 (uitdrukkingswijze per klasse) en h.7 | Normeenheid, letterlijk fragment en semantisch element apart vastleggen; geen contextloze woordregels. |
| P05 | Samenloop | M04 H2:107 en H2:116 (voorrang van tijd en plaats); M02 §3.4 activiteit 2, deelactiviteit b (overlappende markeringen) | Eerdere veralgemening van H3 ingetrokken; overlap en alternatieven apart behandelen. |
| P06 | Verwijzingen volgen | M01 h.3 stap 1 (werkgebied); M04 H2:125 (delegatie) en H2:134 (brondefinities) | Relevantiegestuurde wachtrij; startbudget 20 passages; geen vaste dieptecap. Budget is niet uit een bron afkomstig. |
| P07 | Zorgvuldig duiden van rechtsbetrekking en rechtsfeit ([relaties](relaties.md)) | M01 h.4, rechtsbetrekking en rechtsfeit (subklassen); M06 §3 | De dertien JAS-labels blijven. Een onderbouwde immuniteit blijft staan; één passage zonder sanctie maakt een verplichting niet zwak; niet elke handeling is een rechtshandeling. Tot 13 nov 2026 heette deze regel *JRM-verrijking*; wat over het JRM ging, staat nu in de skill wetsuitvoering (JP05). |
| P08 | Toetsen met praktijkvoorbeelden ([analyseprotocol §5](analyseprotocol.md)) | M01 h.3 stap 4 (review, concrete voorbeelden) en stap 5 (ontbrekend beleid signaleren); M02 §3.6 activiteit 4, deelactiviteit b (voorbeeldreeksen) en §3.7 | Een review, praktijkvoorbeelden en bij een afleidingsregel een voorbeeldreeks; minstens een normaal geval en een grensgeval, herkenbaar als hypothetisch; de uitkomst herleid tot normen en bronnen. Ontbrekend beleid is een eigen soort open punt. Geen dekkingsclaim over alle denkbare gevallen. Het juridische scenario met aktes en toestanden staat in de skill wetsuitvoering (JP06). |
| P09 | Kwaliteit en review | M09; M08; verder projectkeuze | Rubriek, blokkerende kritieke fouten, 24 casussen, familie-split en drie herhalingen zijn projectkeuzes. |
| P10 | Bronverankering | M10 §4.2.4 en §4.2.5; bestaand Anker-contract (projectkeuze) | Bestaande offsets/context/hash behouden; versie apart in document vastleggen. |
| P11 | Runtimeprotocol | P02–P05, P09; projectkeuze (de huidige beperkte API) | Compacte secties genereren naar prompts; ontbrekende context melden, geen brononderzoek veinzen. |
| P12 | Agentimport | P01–P11; projectkeuze | Selectie per bestaande rol, stabiele sectie-ID’s, generatie, hashes en technische logging; geen uitbreiding van tools of uitvoercontracten. |
| P13 | Werkgebied samenstellen in het gesprek (graph-qa, PLAN spoor F) | M03 (Leidraad 1.0) §2.2 startactiviteit a en §2.4 activiteit 1 (p.5–11); M02 (Handleiding 1.0) §3.3 deelactiviteiten 1a–1g | Volgorde naam → aanleiding, context, doel → analysevraag → praktijkvoorbeeld → deelvragen → wat erbuiten valt → bronnen (1f: bronnen pas na vraag en deelvragen). De vaste lijsten van aanleidingen en doelen staan in eigen woorden in de code. Het juridische scenario van 1c en 1e werkt de skill wetsuitvoering uit (besluit 13 nov 2026); hier de "deelvragen eerst"-variant die de Leidraad toestaat, met de gebeurtenis als eigen veld. Startactiviteit b–d bewust niet. |
| P14 | Deelvragen en bronnen (graph-qa, deelvragen-agent en intake, PLAN spoor F3) | M02 (Handleiding 1.0) §3.3 deelactiviteiten 1d–1g; M03 §2.4 activiteit 1 | Wat een goede deelvraag is, splitsen en samenvoegen, van deelvraag naar bronnen (lidniveau, verwijzingen één stap) en dekking, in eigen woorden. Dekking = een bron om te analyseren (1g). Begrippen horen bij het werkgebied, niet bij een deelvraag (M04 H3: het begrippenkader gaat over het hele scenario); sinds spoor K telt een begrip niet meer mee in de dekking per deelvraag. |
| P15 | Begrippen (graph-qa, begrippen-agent, PLAN spoor D/F3) | M04 H3 begrippenkader; M01 h.3 stap 3, onderdeel a; NL-SBB 1.0; ADR-003, ADR-004 | Begrip = analyse-uitkomst; herkomst letterlijk > samengesteld > geformuleerd; voorbeelden pas na een overgenomen definitie; relaties met type en richting. De drempels en de volgorde zijn projectkeuzes van de begrippenketen. **Afwijking van M01:** het boek legt bij een begrip ook de soort en een verdieping van de klasse vast (het type rechtsbetrekking of rechtsfeit). Hier krijgt een begrip geen JAS-klasse en geen begripstype: het begrip volgt het slanke NL-SBB-profiel (ADR-003), en de klasse blijft bij de markeringen waarop het rust. Besluit 13 nov 2026. |
| P17 | Zoekvragen bij de bronselectie ([zoekvragen-bronselectie](zoekvragen-bronselectie.md), graph-qa bronnenrun, PLAN spoor F) | M14; M02 deelactiviteit 1f; P06 | De gebeurtenis in de term van de wet als vertrekpunt, de vier zoekvragen als keten vanaf de grondslag, één zoekvraag per kandidaat als label. Projectkeuzes: het platform herkent de zoekvragen zonder model, met tekstsignalen en verwijzingen in de graaf (een voorstel, geen kwalificatie); de koppeling zoekvraag → rol is een vuistregel; de analist kiest de gebeurtenis. |
| P19 | Opbouw van de skill (sinds skillversie 3.0) | Aanbevelingen voor Claude-skills (progressive disclosure, werkstromen met checklists, voorbeelden); P11–P12; projectkeuze | `SKILL.md` kiest de werkstroom per activiteit; de protocollen en voorbeelden staan in references; de runtime-secties blijven byte-gelijk tot een meting een wijziging onderbouwt. De voorbeelden zijn een illustratie van de werkwijze, geen referentieset. |
| P16 | NL-SBB-velden en uitleg in B1 (graph-qa, begrippen-agent, PLAN spoor I) | M11; M12; ADR-003 | Een slank begrip (term, definitie, uitleg, toelichting, voorbeelden). De uitleg op B1 met toetsen in code (`begrip_b1`): ≤ 20 woorden per zin, ≤ 5 zinnen, lijdende vorm, moeilijk woord (eigen lijst), onverklaarde vakterm, herhaalde definitie. Drempels en woordenlijst zijn projectkeuzes; een treffer is een aandachtspunt, geen weigering. |
| P18 | Relaties tussen markeringen ([relaties](relaties.md), catalogus `relaties.json`, ADR-011) | M01 h.4 per klasse; M02 deelactiviteit 2c; M04 H2; M05; M06 | Relaties horen bij activiteit 2 (2c). De rollen en verbanden komen uit de methode; codes, leesvormen, richting en drager zijn projectkeuzes. `onderdeel`, `uitzondering_op` en `toepassing` zijn projecttypen, de laatste twee alleen waar de tekst ze uitdrukt. Een impliciete partij is alleen een Rechtssubject en alleen door de jurist; relaties tussen afleidingsregels en waarden op een lijn horen bij activiteit 3b. |
| P20 | De prompts van de annotatieketen (graph-qa `agent/jas_pipeline/classificatie.py` en `review.py`) | M04 H2:53 (een rechtsfeit heeft een rechtsgevolg), H2:107 en H2:116 (voorrang van tijd en plaats); ADR-001; projectkeuze | De systeemprompts van classifier en reviewer staan in code, niet in deze skill. Ze dragen een paar methoderegels uit de bron en noemen de publicatieversie van het JAS (1.0.10, zie M04). De klasseduiding zelf komt wel uit deze skill (`agent/jas_klassen.py`). Een wijziging van die prompts is een wijziging van de annotatieketen en vraagt een annotatiemeting. |

## Hoe je dit register leest

- Elke reference in deze skill begint met een regel *Grondslag* die naar codes in dit register wijst.
- Een P-regel noemt in de kolom *Basis* de bron met de plek erin (hoofdstuk, stap, paragraaf, activiteit of regel),
  of zegt dat het een projectkeuze is. `tools/graph-qa/tests/test_methodebronnen.py` toetst beide.
- Het boek (M01), de readers (M02, M03, M14) en de werkversie (M06) staan niet in deze repo; ze staan hier alleen in
  eigen woorden.

## Onderhoud

Bij iedere inhoudelijke wijziging: pas de betrokken P-regel aan, vermeld bron + sectie
of markeer het als projectkeuze, verhoog de methodeversie bij betekeniswijziging en
regenereer het runtimeprotocol. Controleer de regressies en beoordeel geraakte voorbeelden
opnieuw. Een SHA-wijziging vereist controle van het nieuwe bronexemplaar; gebruik geen
stil bijgewerkte webpagina onder een oude versieaanduiding.

## Historie

**Methodeversie 3.0, derde stap (G1b): een lijdende vorm noemt de handelende partij niet.** De meting van G1 liet zien
dat Lex bij een passieve zin ("De motivering wordt vermeld …") de handelende partij als genoemd behandelde, soms zelfs
tussen aanhalingstekens. De sectie `duiding` zegt nu dat een partij alleen genoemd is als haar woord letterlijk in de
tekst staat, en dat een lijdende vorm de handelende partij niet noemt (M01 h.4 §4.2.2 en §4.3.1). Dit verandert de
vingerafdruk van `duiding` en `agent`; gemeten met G1 als nulpunt.

**Methodeversie 3.0, tweede stap (13 nov 2026): `duiding` maakt de partij die de tekst niet noemt expliciet.** De
sectie vraagt Lex de andere partij van een rechtsbetrekking te zoeken en te benoemen als interpretatie met haar
vindplaats, of te zeggen dat zij onbekend is, en de soort rechtsbetrekking of rechtsfeit te noemen waar de tekst haar
draagt (M01 h.4 §3, §4, §4.2.2 en §4.3.1; P18). Dit verandert de vingerafdruk van `duiding` en `agent`; gemeten met
de vorige stap als nulpunt.

**Methodeversie 3.0 (13 nov 2026): de methodetekst zonder JRM.** De sectie `duiding` beschrijft de rechtsbetrekking
volgens het JAS (partijen, voorwerp, voorwaarden, en het rechtsfeit dat haar creëert, wijzigt of beëindigt) in plaats
van "volgens JRM 2"; de slotzin over de JRM-verrijking vervalt. De sectie `supervisor` belooft geen "JAS/JRM-dossier"
meer maar een analysedossier. M06 is geen grondslag van `duiding` meer; wat over het JRM ging, staat in de skill
wetsuitvoering. Dit verandert de vingerafdruk van de rollen
`duiding`, `agent` en `supervisor`, en de kop van elke systeemprompt met methodetekst; gemeten volgens P19 (zie
`docs/architectuur/metingen/README.md`).

**Skillversie 4.0 (13 nov 2026): wetsanalyse en wetsuitvoering gescheiden.** Alles wat uit het JRM komt (het
juridische scenario met aktes, het rechtsgevolg als eigen element, het juridisch relevante feit, de juridische toestand)
staat nu in de skill wetsuitvoering. Deze skill houdt de dertien JAS-klassen, de relaties en de begrippen, en heet
"Wetsanalyse: JAS". `references/jrm-verrijking.md` is vervallen; P07 en P08 zijn herschreven tot hun JAS-kern. De
methodetekst per rol is in deze stap niet gewijzigd: dat is een eigen stap met een meting.

**Skillversie 3.0 (12 nov 2026).** De skill is opnieuw opgezet volgens de eisen voor Claude-skills: een router per
activiteit, werkstromen met checklists, een markeringslijst als uitvoerformaat, uitgewerkte voorbeelden, de
beheerdersinformatie apart ([platform](platform.md)) en testgevallen in `evals/`. De methodetekst per rol (de secties
in [agentrollen](agentrollen.md), [deelvragen en bronnen](deelvragen-en-bronnen.md) en [NL-SBB en B1](nl-sbb-en-b1.md))
is bewust ongewijzigd: een wijziging daarvan vraagt een meting (P19).

**Bijstelling 2.1 na eerste modelproef.**

Op 2026-09-12 liet de proef met protocol 2.0 nog losse gezegden en dubbele
tijdsduur/parameterduidingen zien. P04/P05 zijn daarom explicieter gemaakt voor
enkelvoudige normzinnen en dezelfde temporele functie. Dit is een operationele
verduidelijking van de projectregels, geen nieuw voorschrift uit een bron. De eerste
uitkomsten blijven ongewijzigd in modelvergelijking.json; de gerichte hertoets
wordt afzonderlijk opgeslagen.
