# Conceptanalysedossier — rood voetgangerslicht

Status: concept, niet juridisch vastgesteld. Methode: JAS met JRM 2-verrijking 2.1.
Analist: agent | Datum: 2026-09-12 | Menselijke reviewer: nog niet beoordeeld.

## 1. Opdracht en bronbasis

**Vraag:** welke verschillende gedragsnormen bevat artikel 74 lid 1 onderdeel c van
het oorspronkelijke RVV 1990, en hoe kunnen ontkenning en actorstatus verkeerd worden gelezen?
Doelgroep: analisten die de annotatiemethode beoordelen. Gebruik: historische tekstanalyse,
geen verkeersadvies of oordeel over geldend recht. Territoriale toepasselijkheid en latere
wijzigingen zijn niet onderzocht. Dit is een afgebakende oefening, geen volledige RVV-analyse.

| Bron-ID | Soort | Vindplaats | Versie | Raadpleging |
|---|---|---|---|---|
| B01 = L03 | Oorspronkelijke regeling | [Stb.1990,459](https://zoek.officielebekendmakingen.nl/stb-1990-459.pdf), p.13, art.74/75 | Publicatie1990 | 2026-09-11; pagina visueel gecontroleerd |
| M04 | Methodebron, geen rechtsbron | [Klassenreferentie](../../../.claude/skills/wetsanalyse/references/jas-klassen-referentie.md) | Zie bronmanifest | 2026-09-11 |
| M06 | Methodebron, geen rechtsbron | [JRM-verrijking en bronverantwoording](../../../.claude/skills/wetsanalyse/references/jrm-verrijking.md) | Werkversie2024-11-18 | Zie manifest |

De bronhash staat in het [manifest](../bronnen/manifest.json). De analyse gebruikt de
ongewijzigde analysetekst van RVV03 in [cases.json](cases.json). PDF-regelafbrekingen zijn
samengevoegd. Een juridische peildatum voor actuele toepassing is bewust niet gekozen.
Het bredere beleidsdoel van het RVV is hier niet uit toelichting vastgesteld. De concrete
tekstfunctie — gedrag bij rood regelen — is rechtstreeks in B01 zichtbaar.

## 2. Structuur en grammatica

De gedeelde aanhef luidt: ‘Bij voetgangerslichten betekent:’. Onderdeel c luidt:

> rood licht: voetgangers mogen niet meer beginnen over te steken; reeds overstekende voetgangers moeten zo snel mogelijk doorlopen.

| Norm-ID | Structuur | Grammaticale bevinding |
|---|---|---|
| N01 | Eerste zinsdeel van c, met gedeelde aanhef | Voetgangers is onderwerp; mogen niet meer beginnen over te steken is het gezegde. De negatie betreft beginnen. |
| N02 | Tweede zinsdeel van c, onder dezelfde roodlichtsituatie | Reeds overstekende voetgangers is de afgebakende actor; moeten doorlopen is de plicht. Zo snel mogelijk bepaalt de wijze. |

**Analytische reconstructie, geen citaat:** wie nog moet beginnen, mag bij rood niet
beginnen; wie al oversteekt, moet doorlopen. Deze reconstructie maakt het actorverschil
expliciet. De brontekst bevat geen algemene instructie om midden op de oversteek te stoppen.

## 3. Annotaties en vindplaatsen

Alle fragmenten staan letterlijk in B01, art.74lid1c; de aanhef wordt als context gekoppeld.
De exacte offsets voor de kernmarkeringen staan in RVV03. Dit dossier voegt duidingen toe
voor bespreking; het is geen nieuwe automatisch vastgestelde referentie.

| ID | Norm | Fragment | Klasse | Functie |
|---|---|---|---|---|
| E01 | N01/N02 | rood licht | Voorwaarde | Situatie uit de gedeelde aanhef. |
| E02 | N01 | voetgangers | Rechtssubject | Eerste voorkomen, vóór mogen. |
| E03 | N01 | voetgangers mogen niet meer beginnen over te steken | Rechtsbetrekking | Volledige verbodsformulering. |
| E04 | N02 | reeds overstekende voetgangers | Rechtssubject | Groep die al met oversteken bezig is. |
| E05 | N02 | reeds overstekende voetgangers moeten zo snel mogelijk doorlopen | Rechtsbetrekking | Volledige plichtformulering. |

De ruime rechtsbetrekkingsfragmenten overlappen met hun subjecten. Dat is hier functioneel.
‘Niet’ is in E03 behouden; afzonderlijke operatorannotatie kan nuttig zijn maar verandert
de hoofdduiding niet. ‘Zo snel mogelijk’ is geen exact getal. Een eventuele afzonderlijke
klasse voor deze modaliteit blijft een reviewvraag.

## 4. Samenhang en scenario's

| Relatie | Actor/rol | Inhoud | Voorwaarde | Bronnen/status |
|---|---|---|---|---|
| R01 | Voetganger die nog moet beginnen | Niet beginnen met oversteken | Rood voetgangerslicht | N01/E01–03, concept |
| R02 | Reeds overstekende voetganger | Zo snel mogelijk doorlopen | Rood voetgangerslicht | N02/E01/E04–05, concept |

Een wederpartij en sancties zijn niet uit deze passage vastgesteld. Daarom vullen we
niet automatisch de Staat in en kennen we geen subtype toe op grond van een ontbrekende
sanctie. De actorstatus ‘al aan het oversteken’ is een juridisch relevant scenariofeit.
Rood worden is een hypothetische gebeurtenis in de scenario's; de tekst bevat geen
algemene beschrijving van een volledig procesmodel.

| Scenario | Beginfeiten (hypothetisch) | Gebeurtenis | Verwachte normatieve toestand |
|---|---|---|---|
| S01 | Voetganger staat nog vóór de oversteek | Voetgangerslicht is rood | N01: niet beginnen. |
| S02 | Voetganger is al aan het oversteken | Licht wordt rood | N02: doorlopen zo snel mogelijk. |
| S03 | Onduidelijk of de voetganger al begonnen is | Licht is rood | Welke tak geldt is niet bepaalbaar zonder actorstatus. |
| S04 | Voetganger staat voor groen licht | Nog geen rood | N01/N02 mogen niet uit deze rode tak op groen worden toegepast; lees onderdeel a. |

Iedere uitkomst is beperkt tot deze tekst en veronderstelt dat geen relevante afwijkende
norm of aanwijzing de situatie verandert. De grens tussen nog beginnen en reeds
overstekend is materieel; deze oefening bevat geen definitie die elk randgeval oplost.

## 5. Interpretaties, dekking en review

| Vraag | Conceptkeuze en grond | Open controle |
|---|---|---|
| V01: geldt niet ook voor doorlopen? | Nee: de puntkomma scheidt de uitspraken en N02 bevat een zelfstandige plicht. | Menselijke bevestiging van scope en actorafbakening. |
| V02: wat betekent zo snel mogelijk? | Open wijze van nakoming; geen numerieke snelheid uit de bron. | Zo nodig toepasselijke toelichting/interpretatie onderzoeken. |
| V03: wie is wederpartij? | Niet vastgesteld uit deze passage. | Alleen toevoegen met relevante rechtsbron. |
| V04: zijn dit onvoorwaardelijke actuele regels? | Nee: historische tekst, beperkte opdracht. | Voor concrete toepassing actuele versie en rangorde van normen onderzoeken. |

N01 en N02 zijn behandeld; de gedeelde aanhef is gekoppeld. De overige kleuren en
artikel74lid2 zijn context buiten deze opdracht, geen stilzwijgend geanalyseerde regels.
Artikel75 is op dezelfde pagina gelezen, maar levert geen algemene invulling van R01/R02.

Rubriek: brontekst gecontroleerd; grammatica en samenhang onderbouwd als concept;
externe context beperkt; actuele toepasselijkheid niet beoordeeld; menselijke
classificatiereview en volledige referentieannotatie nog open. **Niet vastgesteld.**
