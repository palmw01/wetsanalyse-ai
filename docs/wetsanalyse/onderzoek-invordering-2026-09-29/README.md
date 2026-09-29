# Onderzoek invordering: volledigheid en samenhang

Datum: 29 september 2026. Onderzoeksresultaat en verbeterontwerp; geen wijziging van productiedetectoren, prompts, beslisbeleid of publieke contracten. De inhoudelijke beoordelingen zijn concepten, niet geadjudiceerd.

## Uitkomst

De twee annotaties bij artikel 9 lid 1 geven de aanslag en de termijn weer, maar laten de centrale uitspraak over invorderbaarheid onbeslist buiten de uitvoer. De norm is wel gedetecteerd en aangeboden aan de classifier. De afgewezen beslissing wordt bewaard, maar veroorzaakt geen review. Dat rechtvaardigt onderzoek naar de afwijzing en ontbrekende samenhang; het bewijst niet dat iedere mogelijke extra markering juist is.

De andere drie bepalingen laten zien dat alleen deze afwijzing repareren onvoldoende is. In Leidraad §9.1 ontbreken de twee centrale termijnregels al in de kandidaatruimte. Datums zonder jaartal ontbreken in §9.1 én §9.5. Lid 5 heeft veel markeringen, maar de berekening van het aantal termijnen is niet als Afleidingsregel beschikbaar. Meer kaartjes betekenen dus ook daar geen complete juridische analyse.

De aanbevolen eerste verbeteringen zijn **datums zonder jaartal, herkenning van verschillende woordvolgordes in toewijzingen, samenhangende termijnberekeningen en zichtbare behandeling van een afgewezen centrale norm**. Zie het [concrete ontwerp en de acceptatietests](ontwerp.md). Generieke naamwoordgroepen vervangen of alle normkandidaten automatisch accepteren is niet onderbouwd.

## Leeswijzer en bestanden

- [Vier dossiers](dossiers.md): volledige eigen graafteksten, 60 onderzoeksitems met exacte offsets, alle dertien klassen per bepaling en open beoordelingsvragen. De 60 items omvatten alternatieven, relaties en uitsluitingen; dit is geen doel van 60 annotaties.
- [Eisenmatrix](eisenmatrix.md): methodische bron → eis → huidige ondersteuning → bevinding → voorgestelde toets.
- [Ontwerp](ontwerp.md): geprioriteerde verbeteringen, samenhangsdiagram, scenario's en een afgebakende modelproef.
- [Bronnen](bronnen.json): vier casussen en vijftien geselecteerde contextpassages uit de acceptatiegraaf, inclusief teksthashes en versiegegevens.
- [Concepten](concepten.json): machineleesbare inhoudelijke beoordelingen; geen wijziging van referentieset v1.
- [Historische sporen](historische-sporen.json): geselecteerde bron- en beslisgegevens uit drie exports, zonder gebruikersnamen of auditactoren.
- [Meting](meting.json): actuele ruwe bijdragen, fusie, klasseopties, taalanalyse, routes, classifierinvoer, bereikbaarheid van conceptfragmenten, historische vergelijking en acht synthetische grammaticaproeven.
- [Ontwikkelcontrole](ontwikkelcontrole.json): vergelijking met de bestaande tekststructuurmeting op zestien ontwikkelcasussen; oude meetbestanden ongewijzigd.
- [Verificatie](verificatie.json): uitgevoerde technische controles en hun beperkingen.

## Bronbeleid en afbakening

**Alle analyseteksten komen uitsluitend uit de graaf.** Ze zijn op 29 september alleen-lezen opgehaald via de bestaande acceptatie-MCP-proxy, repository `inning`, met `bronmodel.resolve`. De graaf vermeldt voor beide regelingen de toestand geldig vanaf 1 juli 2026. Dit is een onderzoek van die toestand, geen onbeperkte claim over actueel geldend recht.

De verouderde lokale MCP-URL werkte niet. Daarna is de projectgebonden MCP-proxyconfiguratie gebruikt. Lokale BWB-XML is alleen ter controle vergeleken: de vier canonieke casusteksten zijn identiek. XML of internet leveren geen terugvaltekst aan de meetcode. De vooraf geraadpleegde webresultaten bepalen geen annotatie of scenario-uitkomst.

Drie eigen graafteksten zijn bovendien identiek aan de exports `annotatie (5).json` (lid 1), `(2).json` (lid 5) en `(3).json` (§9.5). §9.1 heeft geen historische modeluitvoer in dit pakket. Bronhashes identificeren tekst; juridische status en toestand staan apart. De graaf levert voor sommige Leidraadnodes geen JCI; dat ontbrekende veld is niet aangevuld met een verzonnen verwijzing.

De parser gebruikt de canonieke node-tekst uit de graaf. Alle offsets zijn halfopen codepointbereiken `[start,eind)` daarin, nooit offsets in XML of een samengeplakt wetscitaat. Voor een replay bouwt de onderzoekscode een kleine afgeleide snapshot met dezelfde node-tekst en oudercontext; haar snapshot-ID pretendeert niet de oorspronkelijke volledige bronboomsnapshot te zijn.

Het contextbudget is 15 van 20 passages. De bronboom is technisch breder opgehaald, maar alleen de vijftien gemotiveerde passages zijn inhoudelijk gebruikt. Met name IW 9 lid 10 is relevant: de Algemene termijnenwet wordt daarin uitgesloten. Een algemene weekendverschuiving mag dus niet ongemotiveerd in de scenario's worden ingebouwd. De volledige uitzonderingsruimte en de concrete aanwijzing van een ontvanger zijn niet afgerond; de resterende bronvragen staan in het bronnenregister.

## Gemeten huidige toestand

Meting met spaCy `nl_core_news_md-3.8.0`, volledige parse, vijftien detectoren, standaardconfiguratie met vaste fragmentgrenzen. Geen betaalde modelaanvragen.

| Casus | Ruwe kandidaten | Na fusie | Regelroute | Modelroute | Historische modeluitvoer |
|---|---:|---:|---:|---:|---|
| IW 9 lid 1 | 7 | 5 | 0 | 5 | 29 september: 2 accepted, 3 rejected, geen review |
| IW 9 lid 5 | 40 | 39 | 3 | 36 | 25 september: 28 accepted, 11 rejected |
| LI §9.1 | 16 | 14 | 0 | 14 | Niet beschikbaar; actuele classificatie niet gemeten |
| LI §9.5 | 54 | 44 | 0 | 44 | 25 september: 31 accepted, 2 rejected, 12 human review, op toen 45 kandidaten |

Alle detecties zijn bij herhaling identiek. De ouderaanhef verandert op deze vier teksten geen kandidaat. Dat zegt niets over het effect van juridische context op een model: het model is hier niet opnieuw aangeroepen. De huidige classifier krijgt bij een afzonderlijke node diens corpus; de overige nodes in een bronboomsnapshot worden niet automatisch context in de prompt.

De meting bewaart daarnaast een **onderzoeksprompt met de vier bepalingen en geselecteerde context**, herkenbaar per bron en bronstatus. Deze variant is alleen opgebouwd, niet naar een model gestuurd. Zij verandert geen lokale kandidaatgrenzen en maakt geen contexttekst tot annotatiedoel.

## Oorzaken door de keten

| ID | Waarneming en bewijs | Waar ontstaat het verlies? | Wat kan de volgende stap herstellen? |
|---|---|---|---|
| I01 | Lid 1 C001 `[0,87)` heeft RB/RF, normbewijs en volledige zin; de actuele export wijst af. Offline replay geeft opnieuw exact 2 voorstellen en 0 reviewgevallen. | Classificatie; `onzekerheid.signaleer` slaat modelafwijzingen over. | Gerichte review kan een bestaande kandidaat herbeoordelen als een controleerbaar signaal haar bereikt. Validatie beoordeelt juridische volledigheid niet. |
| I02 | `jas.tijd.datum` eist vier jaarcijfers. Geen datumkandidaat voor `31 december` in §9.1 of de concrete voorbeelddata in §9.5. Met jaartal ontstaat die in de controleproef wel. | Lexicale tijdsdetectie; H2 eist geen jaartal voor een tijdstipomschrijving. | Classifier/reviewer kunnen geen ontbrekend fragment aanmaken. |
| I03 | §9.1 krijgt 14 kandidaten, maar geen Afleidingsregel of Rechtsbetrekking. `wordt gesteld op …` werkt in de controle; `wordt … op … gesteld` niet. | Afleidingspatroon verlangt aangrenzend `gesteld op`. Normdetector herkent geen centrale norm in deze vorm. | Promptverbetering alleen maakt de niet-aangeboden klasse/zin niet selecteerbaar. |
| I04 | Lid 5: C001 biedt de volledige eerste zin als RB/RF, nooit AR. Het gedeelte `zoveel gelijke termijnen als …` krijgt geen rekenregel. | Detectie van afleidingen en uitkomst/invoer ontbreken voor deze constructie. | Classifier kan de klasse niet toevoegen; context kan de betekenis wel helpen beoordelen zodra een hypothese bestaat. |
| I05 | Lid 1 C003 verenigt tijd, NP en nominalisatie; vijf klassen blijven over. C004 `zes weken` verliest Variabele via specificiteit, maar heeft daarna alleen RO/RS. | Fusie gebruikt dezelfde span; specificiteit verwijdert klassen, maar draagt de temporele hypothese niet over naar de andere grens. | Een keuze voor de bestaande lange tijdspan is mogelijk. Zonder grensopties kan de classifier de korte span niet als tijd kiezen. Er is geen reden beide verplicht te annoteren. |
| I06 | Lid 5 C026 loopt nog van `de dagtekening` door tot de vervolgregel `… een maand later`; het tijdfragment C024 is inmiddels wel gecorrigeerd. | Nominalisatie volgt een ruime dependency-subboom; de eerdere reparatie betrof de tijdsdetector. | Semantische afwijzing mogelijk, grensherstel niet bij `classifier_spankeuze=false`. |
| I07 | §9.5 C034 heeft `de dag die hetzelfde nummer heeft als dat van de dagtekening`, maar alleen VW/RS/RO. `de kalendermaand` heeft geen tijdklasse. | Relatieve bijzin/NP leveren een vormhypothese zonder passende temporele functie. | Ongeldige keuze wordt contractfout, geen nieuwe tijdhypothese. |
| I08 | Alle 99 modelroutekandidaten hebben in deze universele batches extra klassen in het batchschema die per kandidaat niet mogen. Het validatorvangnet weigert ze wel. | Batch-enum is unie, geen overeenkomst per label. | Technische review kan omgaan met de fout, maar niet bepalen of de kandidaatruimte juridisch onvolledig was. |
| I09 | Iedere detectiedimensie is uitgevoerd en `ongedekt` is overal leeg. Als alle modelroutekandidaten worden afgewezen, ontstaat in geen van de vier casussen een twijfelgeval. | Structurele dekking kijkt naar overlap met kandidaten vóór de eindbeslissing; normeenheden en relaties ontbreken. | De huidige uitvoercontrole kan dit niet als juridische onvolledigheid herkennen. |
| I10 | Synthetisch `Volgens artikel 9.1 bedraagt de vergoeding € 1.000.` levert afleidingsspan `1 bedraagt de vergoeding € 1.`. | Afleidingsregex heeft eigen puntgrenzen; de gedeelde beschermde bereiken worden daar nog niet gebruikt. | Brongetrouwheid slaagt op de verkeerde korte uitsnede. Gedeelde grenzen moeten ook deze generator begrenzen. |

RB = Rechtsbetrekking, RF = Rechtsfeit, AR = Afleidingsregel, VW = Voorwaarde, RO = Rechtsobject, RS = Rechtssubject. De ID's verwijzen naar het ontwerp en de eisenmatrix.

### Historische verschillen verklaard

- Lid 1: de vijf grenzen en klasseverzamelingen komen overeen met de nieuwste export. Dit is geen nieuwe grensregressie van de laatste wijziging.
- Lid 5: de historische C024 `[461,567)` eindigt nu bij 510, vóór de volgende termijnregel. Dit is de bestaande F01-reparatie. Er blijven 39 kandidaten. De oude 28 voorstellen zijn geen opnieuw gemeten modeluitvoer.
- §9.5: de historische C037 `als dat van de dagtekening` is verwijderd als zelfstandige voorwaarde door de bestaande F02-reparatie. Daardoor 44 in plaats van 45 kandidaten; labels na die positie verschuiven. Vergelijk daarom op bron + offsets, niet alleen label.
- Oude exports van lid 5 en §9.5 bevatten geen volledige beslisregistratie van de afgewezen kandidaten. Hun ontbrekende beslissingen zijn niet gereconstrueerd. Alleen bewaarde voorstellen worden op grenzen en klassen vergeleken.
- De twaalf historische HUMAN_REVIEW-gevallen in §9.5 zijn volgens hun spoor contractfouten. Dit is geen actuele modelmeting. De huidige code bewaart inmiddels de ruwe ongeldige reviewreactie en rapporteert technische reviewbelasting; die eerdere verbetering mag niet opnieuw als ontbrekend worden voorgesteld.

## Wat de verificatie wel en niet bewijst

De nieuwe tests controleren het graafbronbeleid, onveranderde hashes, geldige lokale conceptgrenzen, beoordeling van alle dertien klassen, onderscheid tussen kern en optie, per-kandidaatvalidatie en de volledige route via classifier, validatie, gerichte review en uitvoer. In iedere casus komt een vooraf gekozen, beschikbare kandidaat met ongewijzigde bronankers aan. Dit bewijst dat transport lukt; niet dat een echt model de juiste kandidaat kiest.

De afzonderlijke ontwikkelcontrole heeft dezelfde 262 kandidaten, 73 van 81 voorlopige kernankers en identieke classifierinvoer als de bewaarde baseline. Geen verloren ontwikkelankers. Dat is een stabiliteitscontrole, geen juridische recallscore. De afgeschermde families BW6 en Omgevingswet zijn niet gebruikt om ontwerpkeuzes te maken.

De juridische ontbrekende elementen blijven hypotheses totdat deskundigen de volledige dossiers beoordelen. Er is geen live voor/na-modelproef gedaan en geen kwaliteitswinst geclaimd. Het ontwerp specificeert de volgende proef en de acceptatievoorwaarden.

## Reproduceren

Vanuit `tools/graph-qa`, zonder netwerk of providercredentials:

```bash
.venv/bin/python -m eval.onderzoek_invordering --output /tmp/invordering-nieuwe-meting.json --dossiers /tmp/invordering-nieuwe-dossiers.md
.venv/bin/python -m pytest tests/test_onderzoek_invordering.py -q
.venv/bin/python -m eval.detector_audit --json /tmp/invordering-nieuwe-devcontrole.json --vergelijk ../../docs/architectuur/metingen/hybrid-v1-tekststructuur-2026-09-29/na.json
```

Een volledige `nl_core_news_md`-parse is vereist voor de meting; bij een ontbrekend model stopt die expliciet. De meetopdracht weigert bestaande uitvoerbestanden te overschrijven. De bron-, concept- en codehashes staan in het meetbestand; een nieuwe codeversie vraagt een nieuw vergelijkingspunt.
