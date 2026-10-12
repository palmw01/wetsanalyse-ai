# Hulpmiddelen voor Wetsanalyse activiteit 2 en 3

Beoordeling van alle 102 vermeldingen op de INT-pagina **Hulpmiddelen**, met TermWerk als 103e, aanvullende vermelding. Tedi en TermStar staan ieder tweemaal op de INT-pagina: na deze twee expliciete dubbeltellingen resteren 100 productidentiteiten uit die lijst. Gelijknamige LookUp-producten zijn afzonderlijk gehouden.

De beoordeling betreft openbare documentatie op 8 oktober 2026. Er zijn geen producten geïnstalleerd, accounts aangemaakt, corpora geüpload of API-proeven uitgevoerd. Een proefkandidaat is daarom een voorstel voor vergelijking, geen bewezen geschikte toepassing. Nederlandse tekstopslag, een Nederlandse interface en Nederlandstalige taalanalyse zijn afzonderlijke eigenschappen.

De veldnamen *functie*, *omgeving* en *toegang* vatten de aangehaalde documentatie samen. *Betekenis voor Wetsanalyse* en *oordeel* zijn eigen onderzoeksconclusies. Waar primaire informatie ontbrak, staat dat expliciet. Een geblokkeerde opvraag bewijst geen beëindiging van een product.

Lees het [onderzoek en projectadvies](README.md) voor de samenhang en de [verdieping van de belangrijkste toepassingen](verdieping.md) voor concrete vergelijkingsvragen. Dezelfde fiches staan in [CSV](hulpmiddelen.csv). Het [bronnenregister](bronnen.json) bewaart per bron de leesstatus, opvraag en vindplaatsen.

| INT-rubriek | Vermeldingen |
|---|---:|
| Alignering | 5 |
| Corpusanalyse | 8 |
| Online concordantie | 7 |
| Termextractie | 25 |
| Terminologiebeheer – onafhankelijke applicaties | 27 |
| Terminologiebeheer – onafhankelijke applicaties geschikt voor kennisbeheer met grafische relatieweergave | 8 |
| Vertaalgeheugens met geïntegreerde terminologiemodule | 11 |
| Vertaalprojectbeheer met geïntegreerde terminologiemodule | 6 |
| Zoekapplicaties | 5 |
| Aanvulling TermWerk | 1 |

## Alignering

### H001 AlignAssist Translation File AlignmentTool

**Oordeel:** Onvoldoende bewijs. **Functie:** Tweetalige segmentalignering.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Historische desktoptool; actuele uitvoerformaten niet bevestigd |
| Licentie of toegang | Actuele voorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Alleen nuttig bij het vergelijken van meertalige bronpassages; een segmentpaar bewijst geen gelijke juridische betekenis.

**Beperking:** INT verwijst naar een downloadaggregator; deze blokkeert de opvraag. Geen verifieerbare actuele makersdocumentatie gevonden.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-2). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H001](https://alignassist.software.informer.com/1.5/). Vindplaats: Alignering / AlignAssist.

### H002 AlignFactory en AlignFactory (Light)

**Oordeel:** Later. **Functie:** Documentparen automatisch uitlijnen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Tekstalignering; geen Nederlandse begripsanalyse aangetoond |
| Omgeving en uitwisseling | Desktop; bitexten; documentkoppeling en segmentfilters |
| Licentie of toegang | Commerciële abonnementen op productpagina |

**Betekenis voor Wetsanalyse:** Leer van het afzonderlijk bewaren van documentpaar en segmentkoppeling. Gebruik dit pas bij meertalig brononderzoek, met behoud van bronversie en afzonderlijke beoordeling.

**Beperking:** De oude INT-link komt uit op AlignFactory Desktop; de oude Light-aanduiding en tariefinformatie zijn geen actuele productspecificatie.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-3). Bronnen: [H002](https://terminotix.com/index.asp?content=item&item=11&lang=en). Vindplaats: AlignFactory Desktop / Alignement de documents.

### H003 HunAlign

**Oordeel:** Later. **Functie:** Zinnen in twee talen uitlijnen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalonafhankelijke aanpak; Nederlandse kwaliteit niet gemeten |
| Omgeving en uitwisseling | C++ lokaal; vooraf gesegmenteerde en getokeniseerde teksten naar zinsparen |
| Licentie of toegang | LGPLv3 of later volgens README |

**Betekenis voor Wetsanalyse:** Een reproduceerbare aligneringsstap kan vertaalde regelingen doorzoekbaar verbinden. Bewaar koppelingen als suggesties en toets ze afzonderlijk van begripsidentiteit.

**Beperking:** Geen kruisende aligneringen: verplaatste passages kunnen verkeerd uitlijnen. De oorspronkelijke MOKK-link was onbereikbaar; auteursrepository wel gelezen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-4). Bronnen: [H003B](https://github.com/danielvarga/hunalign). Vindplaats: README / Introduction; License.

### H004 Twente Word Alignment

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Woord- en zinsalignering.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet voor het huidige product geverifieerd |
| Omgeving en uitwisseling | Twente Word Alignment / NATools; historische verwijzing |
| Licentie of toegang | Actuele distributievoorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Het onderscheid tussen woordkoppelingen, zinskoppelingen en conceptkoppelingen is bruikbaar bij bronvergelijking.

**Beperking:** Archieflink toont toegangscontrole; NATools-bronpagina kon niet inhoudelijk worden gelezen. De gemelde opvolgingslijn komt uit INT.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-5). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H004](https://archive.is/CcSD), [H004B](https://sourceforge.net/projects/natools/). Vindplaats: Alignering / Twente Word Alignment.

### H005 YouAlign

**Oordeel:** Afgevallen. **Functie:** Online documentalignering.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet meer relevant voor inzet van deze dienst |
| Omgeving en uitwisseling | Voormalige webdienst; maker verwijst naar AlignFactory Desktop |
| Licentie of toegang | Dienst volgens eigen website niet meer beschikbaar |

**Betekenis voor Wetsanalyse:** Het patroon van een eenvoudige upload naar controleerbare segmentparen blijft bruikbaar voor een toekomstige vergelijkingsfunctie.

**Beperking:** De eigen homepage meldt beëindiging. De INT-vermelding van gratis dagelijkse aligneringen is achterhaald.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-6). Bronnen: [H005B](https://youalign.com/). Vindplaats: Homepage / YouAlign is no longer available.

## Corpusanalyse

### H006 Corsis

**Oordeel:** Onvoldoende bewijs. **Functie:** Corpusonderzoek met frequenties.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Historische opensourceverwijzing op SourceForge |
| Licentie of toegang | Actuele licentie en onderhoud niet bevestigd |

**Betekenis voor Wetsanalyse:** Een afgebakend corpus en herhaalbare woordtellingen kunnen een baseline voor termselectie leveren.

**Beperking:** De opgehaalde bron bevat geen leesbare productdocumentatie. Geen installatieadvies op basis van de INT-omschrijving alleen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-8). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H006](https://corsis.sourceforge.net/index.php/Main_Page). Vindplaats: Corpusanalyse / Corsis.

### H007 DIMAP

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Woordenboek en betekenissen beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse analyse niet bevestigd |
| Omgeving en uitwisseling | DIMAP desktop; actuele gegevensuitwisseling niet gecontroleerd |
| Licentie of toegang | Demoaanbod gevonden; actuele licentie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Meerdere betekenissen onder één woord maken zichtbaar waarom een woordenboekstructuur verschilt van het beoogde begrippenmodel.

**Beperking:** Directe makerspagina blokkeert toegang. Een gevonden registratiepagina bevestigt hoogstens een demoaanbod, geen actuele geschiktheid.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-9). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H007](https://www.clres.com/DIMAP.html). Vindplaats: Corpusanalyse / DIMAP.

### H008 FastR

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Termen en varianten herkennen.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Engels en Frans; Nederlands niet bevestigd |
| Omgeving en uitwisseling | Historische FastR-parser; bronlink geeft 404 |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Variantenherkenning is nuttig als zoekuitbreiding voor activiteit 2 en als aanwijzing voor vergelijking in activiteit 3.

**Beperking:** De doorgestuurde makerspagina ontbreekt. Normalisatie mag de oorspronkelijke formulering en het tekstanker niet vervangen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-10). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H008](https://www.limsi.fr/Individu/jacquemi/FASTR/). Vindplaats: Corpusanalyse / FastR.

### H009 Open Parallel Corpus

**Oordeel:** Contextbron. **Functie:** Parallelle corpora ontsluiten.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlands op corpusniveau nader selecteren |
| Omgeving en uitwisseling | OPUS-webapp; concrete corpusversie en licentie per dataset vaststellen |
| Licentie of toegang | Afhankelijk van het gekozen corpus |

**Betekenis voor Wetsanalyse:** Gebruik parallelle corpora alleen voor vergelijkingsonderzoek en voor taalvarianten; selecteer juridische teksten per rechtsstelsel en periode.

**Beperking:** De hoofdpagina is een JavaScript-app. Er is geen corpus gedownload en geen geldige Nederlandse rechtsbron uit afgeleid.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-11). Bronnen: [H009](https://opus.nlpl.eu/), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: Corpusanalyse / Open Parallel Corpus.

### H010 Plug Word Aligner

**Oordeel:** Onvoldoende bewijs. **Functie:** Tweetalige woorden en zinnen koppelen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet bevestigd |
| Omgeving en uitwisseling | Historische PLUG Word Aligner |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een onderzoeksvoorbeeld van alignering; geen reden om binnen de huidige Nederlandstalige annotatieketen een aparte koppellaag toe te voegen.

**Beperking:** De oorspronkelijke universiteitsbron reageerde niet binnen de opvraagtermijn. Onderhoud en downloadbaarheid blijven onbekend.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-12). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H010](https://stp.ling.uu.se/plug/pwa/). Vindplaats: Corpusanalyse / Plug Word Aligner.

### H011 WebReaper

**Oordeel:** Afgevallen voor dit traject. **Functie:** Webpagina's voor een corpus verzamelen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Geen Nederlandse NLP aangetoond |
| Omgeving en uitwisseling | Historische Windows-crawler |
| Licentie of toegang | Niet bij maker geverifieerd |

**Betekenis voor Wetsanalyse:** Corpusverwerving vereist een expliciete bronselectie en versieregistratie. De bestaande BWB-import is daarvoor al een gerichte basis.

**Beperking:** INT verwijst naar een geblokkeerde downloadsite. Een algemene webcrawler voegt voor wettelijke bronteksten geen noodzakelijke functie toe.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-13). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H011](https://www.softpedia.com/get/Internet/Offline-Browsers/WebReaper.shtml), [P02](../../../README.md). Vindplaats: Corpusanalyse / WebReaper; project README.

### H012 WordNet

**Oordeel:** Contextbron. **Functie:** Lexicale betekenissen en relaties ontsluiten.

| Aspect | Bevinding |
|---|---|
| Nederlands | Engelstalige lexicale bron |
| Omgeving en uitwisseling | WordNet; gebruiksvoorwaarden op makerssite |
| Licentie of toegang | Makerssite blokkeert directe opvraag |

**Betekenis voor Wetsanalyse:** Synsets illustreren het verschil tussen woordvorm en betekenis. Gebruik lexicale verwantschap hoogstens om kandidaten te vinden.

**Beperking:** Geen Nederlandse juridische begrippenbank; een synset is geen bewijs dat twee wetsformuleringen hetzelfde betekenen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-14). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H012](https://wordnet.princeton.edu/license-and-commercial-use), [H012B](https://wordnet.princeton.edu/). Vindplaats: Corpusanalyse / WordNet.

### H013 WordSmith Tools

**Oordeel:** Alternatieve proefkandidaat. **Functie:** Concordanties en woordstatistiek.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse tekstverwerking te beproeven; geen juridische NLP |
| Omgeving en uitwisseling | Windows; Concord, KeyWords, WordList |
| Licentie of toegang | Commerciële licentie; voorwaarden bij leverancier |

**Betekenis voor Wetsanalyse:** Kan een handmatig controleerbare baseline leveren voor contextzoeken en onderscheidende woorden, vóór inzet van AI.

**Beperking:** De actuele pagina noemt WordSmith 9 en Windows 10 of hoger. Voor dit Linux-project zijn platformoverdracht en export een extra stap.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-15). Bronnen: [H013](https://lexically.net/wordsmith/). Vindplaats: Homepage / System Requirements; Concord; KeyWords; WordList.

## Online concordantie

### H014 2Lingual

**Oordeel:** Later. **Functie:** Gelijktijdig in twee talen zoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlands staat in de taalkeuze |
| Omgeving en uitwisseling | Webzoekinterface; geen gestructureerde termexport vastgesteld |
| Licentie of toegang | Geen integratievoorwaarden vastgesteld |

**Betekenis voor Wetsanalyse:** Interessant als zoekinterface bij meertalige verkenning; elke gevonden passage moet daarna als afzonderlijke bron worden beoordeeld.

**Beperking:** Zoekresultaten zijn geen afgebakend corpus en bieden geen juridische herkomstgarantie. De feitelijke zoekwerking is niet getest.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-17). Bronnen: [H014](https://www.2lingual.com/). Vindplaats: Homepage / language selectors.

### H015 KwicFinder

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Zoekwoorden in webcontext tonen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Historisch KWiCFinder; makerssite onbereikbaar |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** KWIC is direct relevant: vergelijk voorkomens van een formulering naast elkaar en open de volledige broncontext.

**Beperking:** De productimplementatie is niet geverifieerd. Voor dit patroon zijn wel leesbare AntConc- en TextSTAT-bronnen beschikbaar.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-18). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H015](https://www.kwicfinder.com/KWiCFinder.html), [H015B](https://www.kwicfinder.com/). Vindplaats: Online concordantie / KwicFinder.

### H016 Linguee

**Oordeel:** Contextbron. **Functie:** Tweetalige woorden en contexten opzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlands in interface en taalparen |
| Omgeving en uitwisseling | Webwoordenboek en contextzoeker |
| Licentie of toegang | Publiek raadpleegbaar; hergebruik/API niet vastgesteld |

**Betekenis voor Wetsanalyse:** Kan alternatieve formuleringen aanreiken voor gericht bronnenonderzoek bij activiteit 3.

**Beperking:** Een vertaalvoorbeeld is geen Nederlandse wettelijke definitie. Domein, rechtsstelsel en juridische geldigheid moeten bij de oorspronkelijke tekst worden vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-19). Bronnen: [H016](https://www.linguee.nl/). Vindplaats: Homepage / woordenboek en taalparen.

### H017 MyMemory

**Oordeel:** Later. **Functie:** Vertaalde tekstsegmenten terugvinden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Dutch staat in taalkeuze |
| Omgeving en uitwisseling | Webdienst; INT noemt API |
| Licentie of toegang | API-voorwaarden en datagebruik niet onderzocht |

**Betekenis voor Wetsanalyse:** Vergelijkbare segmenten kunnen een onderzoeksvraag opleveren over termgebruik; houd het gevonden segment en zijn herkomst apart van de analyse.

**Beperking:** De grote verzameling is niet automatisch een betrouwbaar juridisch corpus. Geen tekst ingestuurd en geen API uitgevoerd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-20). Bronnen: [H017](https://mymemory.translated.net/), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: Homepage; Online concordantie / MyMemory.

### H018 TradooIT

**Oordeel:** Later. **Functie:** Tweetalige concordanties en terminologie zoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Eigen interface toont Frans, Engels en Spaans |
| Omgeving en uitwisseling | Web; geheugen, aligneren, bitextexport en Termidoo |
| Licentie of toegang | Accountfuncties niet getest |

**Betekenis voor Wetsanalyse:** Het naast elkaar tonen van bronzin en tegenhanger is een bruikbaar presentatiepatroon voor vergelijking.

**Beperking:** Geen Nederlandse ondersteuning aangetoond. Ook een vertaalgeheugenmatch mag geen begripskoppeling automatisch goedkeuren.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-21). Bronnen: [H018](https://www.tradooit.com/). Vindplaats: Homepage / Concordancier bilingue; Mémoire; Termidoo.

### H019 TransSearch

**Oordeel:** Onvoldoende bewijs. **Functie:** Vertaalzinnen doorzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Engels, Frans en Spaans |
| Omgeving en uitwisseling | TransSearch webdienst; directe TLS-fout |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Het concordantieprincipe is bruikbaar, maar biedt geen aanleiding voor inzet binnen het Nederlandse traject.

**Beperking:** Het certificaat past niet bij de opgegeven host. Actuele beschikbaarheid en productcontinuïteit zijn niet vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-22). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H019](https://tsrali3.com/). Vindplaats: Online concordantie / TransSearch.

### H020 WebCorp

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Het web als corpus doorzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Nederlands; niet functioneel bevestigd |
| Omgeving en uitwisseling | WebCorp; TLS- en verbindingsproblemen bij opvraag |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een contextoverzicht over meerdere bronnen kan Lex helpen zoekvragen te richten, mits de analist bronsoort en versie kan filteren.

**Beperking:** Het open web geeft geen vaste corpusstand. De dienst is niet operationeel getest; gebruik voor wetsanalyse een vooraf geselecteerd broncorpus.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-23). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H020](https://www.webcorp.org.uk/live/guide.jsp), [H020B](https://www.webcorp.org.uk/). Vindplaats: Online concordantie / WebCorp.

## Termextractie

### H021 Anchovy

**Oordeel:** Proefkandidaat voor uitwisseling. **Functie:** Woordenlijsten bewerken, extraheren en converteren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalcodes en meertalige gegevens; Nederlandse extractiekwaliteit onbekend |
| Omgeving en uitwisseling | Desktop; GlossML, CSV, Excel, TBX, TMX, HTML en XLIFF-gerelateerde extractie |
| Licentie of toegang | Makerspagina onderscheidt broncode en betaalde gebruiksklare distributie |

**Betekenis voor Wetsanalyse:** Gebruik als mogelijke conversieproef voor kleine termenlijsten. Vergelijk na export de conceptgroepering, labels, bronnen en reviewstatus.

**Beperking:** De INT-beschrijving als gratis plug-in dekt het huidige aanbod niet. Een tabelconversie bewaart niet vanzelf juridische koppelingen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-25). Bronnen: [H021](https://www.maxprograms.com/products/anchovy.html), [H021B](https://maxprograms.com/support/anchovy/anchovy.html). Vindplaats: Overview / What you can do; Subscription Benefits.

### H022 AntConc

**Oordeel:** Proefkandidaat activiteit 2. **Functie:** Concordanties, clusters en corpusvergelijking.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse teksten mogelijk; tagging en lemma's afzonderlijk toetsen |
| Omgeving en uitwisseling | Desktop Windows, macOS en Linux; KWIC, file view, n-grams en keywordlijsten |
| Licentie of toegang | Freeware volgens maker |

**Betekenis voor Wetsanalyse:** Gebruik als externe controle op de vindbaarheid van formuleringen. Open vanuit een concordantieregel de volledige bepaling en beoordeel uitzonderingen en antecedenten.

**Beperking:** De handleiding beschrijft corpusfuncties, geen juridische classificatie. Frequentie en collocatie mogen de JAS-uitkomst niet bepalen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-26). Bronnen: [H022](https://www.laurenceanthony.net/software/antconc/), [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf). Vindplaats: AntConc downloads; help / Overview of Tools.

### H023 BibClassify

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Documenten automatisch met trefwoorden indexeren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet bevestigd |
| Omgeving en uitwisseling | BibClassify; documentniveau |
| Licentie of toegang | Geen actuele inzetvoorwaarden vastgesteld |

**Betekenis voor Wetsanalyse:** Onderscheid documentonderwerp van fragmentfunctie: een trefwoord kan bronnen helpen vinden, maar identificeert geen rechtssubject, voorwaarde of rechtsgevolg.

**Beperking:** De CERN-bron toont een botcontrole ondanks HTTP 200. De productdetails zijn daarom niet onafhankelijk uit die pagina bevestigd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-27). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H023](https://cds.cern.ch/help/admin/bibclassify-admin-guide?ln=it). Vindplaats: Termextractie / BibClassify.

### H024 Dandelion API

**Oordeel:** Afgevallen voor directe inzet. **Functie:** Entiteiten, onderwerpen en tekstgelijkenis bepalen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Eigen homepage noemt zes talen zonder Nederlands |
| Omgeving en uitwisseling | Web-API voor semantische tekstanalyse |
| Licentie of toegang | Dienst met account en prijsinformatie |

**Betekenis voor Wetsanalyse:** Laat zien dat entiteitherkenning, tekstrelevantie en begripsvorming verschillende taken zijn. Een herkende persoon is niet automatisch een juridisch rechtssubject.

**Beperking:** Geen Nederlandse ondersteuning op de gelezen homepage; algemene entiteitskoppeling mist de juridische context van een regeling.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-28). Bronnen: [H024](https://dandelion.eu/). Vindplaats: Homepage / Semantic Text Analytics; Entity Extraction.

### H025 ExtPhr32

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Termkandidaten en collocaties vinden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Historische ExtPhr32-desktoptool |
| Licentie of toegang | Actuele voorwaarden onbekend |

**Betekenis voor Wetsanalyse:** Minimale frequentie en stopwoorden zijn zinvolle baselineparameters, maar mogen zeldzame wettelijke definities niet wegfilteren.

**Beperking:** INT vermeldt dat onderhoud is gestopt; een primaire actuele bron ontbreekt. Niet installeren op basis van een downloadaggregator.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-29). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H025](https://extphr32.software.informer.com/). Vindplaats: Termextractie / ExtPhr32.

### H026 Extractor

**Oordeel:** Onvoldoende bewijs. **Functie:** Sleuteltermen uit teksten afleiden.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT-talenlijst bevat geen Nederlands |
| Omgeving en uitwisseling | Historische Extractor-dienst; TLS-hostnaamprobleem |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** De oude productbelofte van onbevooroordeelde extractie mag niet als kwaliteitsbewijs gelden. Meet afzonderlijk of juridisch relevante formuleringen worden gemist.

**Beperking:** Actuele productidentiteit en beschikbaarheid zijn niet bevestigd. Geen aanbeveling voor de annotatieketen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-30). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H026](https://extractor.com/). Vindplaats: Termextractie / Extractor.

### H027 fivefilters

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Relevante woorden uit tekst of URL halen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse verwerking niet bevestigd |
| Omgeving en uitwisseling | Webextractor; maker positioneert uitkomst voor tagging |
| Licentie of toegang | Dienstpagina verwijst naar extractor; voorwaarden nader vaststellen |

**Betekenis voor Wetsanalyse:** Een eenvoudige tekst-naar-kandidatenstap is bruikbaar als baseline naast juridische detectoren.

**Beperking:** De gelezen productpagina bevat geen bewijs voor begripsonderscheiding, Nederlandse lemmatisering of bronankers. Alleen gebruiken in een afgescheiden proef.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-31). Bronnen: [H027](https://fivefilters.org/term-extraction/). Vindplaats: Term Extraction.

### H028 Lexical extractor for terminology and translation

**Oordeel:** Onvoldoende bewijs voor bedoelde extractor. **Functie:** Lexicografie en terminologie beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet vastgesteld |
| Omgeving en uitwisseling | Python-server, webclient en TBX-gerelateerde repositoryprojecten |
| Licentie of toegang | Per repository controleren |

**Betekenis voor Wetsanalyse:** Maak productidentiteit controleerbaar voordat een tool wordt vergeleken: gelijknamige software kan een andere functie hebben.

**Beperking:** De INT-link naar LexTerm leidt naar een organisatie met LexTermServer, LexTermClient en CRITI. Daarmee is de beschreven statistische extractor niet aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-32). Bronnen: [H028](https://github.com/LexTerm), [H028B](https://github.com/LexTerm/LexTermServer), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: GitHub organisatie en LexTermServer README.

### H029 LogiTerm

**Oordeel:** Later. **Functie:** Vertaalarchieven en terminologie gezamenlijk ontsluiten.

| Aspect | Bevinding |
|---|---|
| Nederlands | Unicode en Nederlandse geschiktheid nog testen |
| Omgeving en uitwisseling | LogiTerm Light, Pro en Web; archief- en terminologiezoekfunctie |
| Licentie of toegang | Light als gratis aanbod vermeld; Pro/Web commercieel |

**Betekenis voor Wetsanalyse:** Een zoekinterface over zowel tekstcontext als terminologische records is bruikbaar voor de werkplek van activiteit 3.

**Beperking:** Het betreft een vertaalomgeving. Bronstand, bronanker en begripsbeslissing moeten in Wetsanalyse eigen objecten blijven.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-33). Bronnen: [H029](https://www.terminotix.com/index.asp?content=brand&brand=2&lang=en). Vindplaats: Traduction / LogiTerm-producten.

### H030 maui-indexer

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Trefwoorden en onderwerpen automatisch toekennen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Afhankelijk van taalresources; Nederlands niet bevestigd |
| Omgeving en uitwisseling | Maui; lokale code en gecontroleerde vocabulaire als mogelijke invoer |
| Licentie of toegang | GPL volgens repository |

**Betekenis voor Wetsanalyse:** Een gecontroleerde woordenschat kan zoekresultaten ordenen. De vergelijkingsproef moet documentindexering scheiden van het classificeren van wetsfragmenten.

**Beperking:** De Google Code-link is een archief. De gelezen repository noemt deels verouderde documentatie; actuele productondersteuning is niet aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-34). Bronnen: [H030B](https://github.com/zelandiya/maui). Vindplaats: README / Summary; tasks.

### H031 MultiTerm Extract

**Oordeel:** Onvoldoende bewijs. **Functie:** Termkandidaten voor een MultiTerm-omgeving verzamelen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet geverifieerd voor dit onderdeel |
| Omgeving en uitwisseling | INT linkt een algemene MultiTerm-handleiding |
| Licentie of toegang | Productlicentie en afzonderlijke verkrijgbaarheid onbekend |

**Betekenis voor Wetsanalyse:** Relevant als voorbeeld van een kandidaatfase vóór opname in een termenbank.

**Beperking:** De opgegeven URL en de huidige productpagina bevestigen geen afzonderlijk actueel MultiTerm Extract-product. Geen functionaliteit van MultiTerm stilzwijgend eraan toeschrijven.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-35). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H031](https://docs.rws.com/1117394/261588/multiterm-2022-sr2/welcome-to-------------multiterm-2022-sr2), [H055B](https://www.trados.com/product/multiterm/). Vindplaats: Termextractie / MultiTerm Extract.

### H032 Olifant

**Oordeel:** Later. **Functie:** Vertaalgeheugens bewerken en filteren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Unicodeverwerking volgens INT; geen Nederlandse analyse bevestigd |
| Omgeving en uitwisseling | Olifant; TMX-bewerking |
| Licentie of toegang | Actuele voorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een schoon broncorpus voorkomt dat dubbele of onvolledige segmenten termstatistiek vertekenen.

**Beperking:** Een TMX-editor is geen directe begrippenextractor. De makersdocumentatie kon niet worden gelezen; huidige compatibiliteit blijft onzeker.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-36). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H032](https://okapi.sourceforge.net/Release/Olifant/Help/). Vindplaats: Termextractie / Olifant.

### H033 OneClick Terms

**Oordeel:** Alternatieve proefkandidaat. **Functie:** Termextractie via een eenvoudige webinterface.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Nederlands; niet functioneel getest |
| Omgeving en uitwisseling | OneClickTerms JavaScript-app; concrete export niet uitgevoerd |
| Licentie of toegang | Actuele prijs/toegang niet bevestigd |

**Betekenis voor Wetsanalyse:** Een compacte upload-naar-kandidatenworkflow kan de instap verlagen. Gebruik hetzelfde corpus en dezelfde beoordelingsset als bij andere extractoren.

**Beperking:** De app laadt, maar er is geen extractie uitgevoerd. De oorspronkelijke uitspraak gratis is niet als actueel tarief overgenomen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-37). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H033](https://terms.sketchengine.eu/), [H035](https://www.sketchengine.eu/guide/keywords-and-term-extraction/#toggle-id-5-closed). Vindplaats: Termextractie / OneClick Terms; Sketch Engine guide.

### H034 Prospector (bèta)

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Termkandidaten tegen een referentiecorpus rangschikken.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Engels en COCA |
| Omgeving en uitwisseling | Prospector in JavaScript-cloudportaal |
| Licentie of toegang | Actuele moduletoegang niet vastgesteld |

**Betekenis voor Wetsanalyse:** De keuze van referentiecorpus beïnvloedt welke termen opvallen; maak die keuze en versie expliciet in iedere proef.

**Beperking:** Het portaal leverde geen leesbare modulebeschrijving. Een Engels referentiecorpus is geen verantwoorde standaard voor Nederlandse wetgeving.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-38). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H034](https://cloud.logrusglobal.com/#prospector). Vindplaats: Termextractie / Prospector.

### H035 Sketch Engine

**Oordeel:** Proefkandidaat activiteit 2 en 3. **Functie:** Keywords en meerwoordtermen via corpusvergelijking extraheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalgrammatica vereist; Nederlandse configuratie per proef controleren |
| Omgeving en uitwisseling | Webcorpora; focus- en referentiecorpus; lemma's en contextregels |
| Licentie of toegang | Commerciële dienst; concrete voorwaarden niet onderzocht |

**Betekenis voor Wetsanalyse:** Vergelijk frequentie met taalkundig gefilterde termkandidaten. Test expliciet of kwalificaties, verbale normen en zeldzame definities behouden blijven.

**Beperking:** Keyness is statistische opvallendheid en geen juridische betekenis of modelconfidence. De makersdefinitie van term als meerwoordeenheid is toolspecifiek.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-39). Bronnen: [H035](https://www.sketchengine.eu/guide/keywords-and-term-extraction/#toggle-id-5-closed). Vindplaats: Guide / Keywords and terms; Requirements; Simple maths.

### H036 SynchroTerm

**Oordeel:** Later. **Functie:** Termen en equivalenten uit vertaalde documentparen halen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlands expliciet in makerslijst |
| Omgeving en uitwisseling | Desktop; documenten, bitexten, SDLXLIFF, XLIFF en TMX |
| Licentie of toegang | Commerciële abonnementen |

**Betekenis voor Wetsanalyse:** Een voorstel met beide termen én hun contexten is beter toetsbaar dan een kale lijst met synoniemen.

**Beperking:** Tweetalige equivalentie is niet hetzelfde als gelijkheid tussen begrippen uit verschillende rechtsstelsels. Geen eerste prioriteit voor eentalige activiteit 2.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-40). Bronnen: [H036](https://www.terminotix.com/index.asp?name=SynchroTerm&content=item&brand=4&item=7&lang=en). Vindplaats: SynchroTerm / Extraction; talenlijst.

### H037 TermFinder

**Oordeel:** Onvoldoende bewijs. **Functie:** Terminologie-extractie als API aanbieden.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt Frans, Engels en Italiaans |
| Omgeving en uitwisseling | RapidAPI-vermelding; nauwelijks leesbare documentatie |
| Licentie of toegang | Actuele API-toegang en prijs niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een getypeerde extractie-API is een mogelijk koppelpatroon, mits bronposities en kandidaatstatus onderdeel van het contract zijn.

**Beperking:** De vermelding bevestigt geen bruikbare actuele Nederlandse extractiedienst. Geen proef of integratie uitgevoerd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-41). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H037](https://rapidapi.com/translated/api/terminology-extraction). Vindplaats: Termextractie / TermFinder.

### H038 TerMine

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Meerwoordtermen en acroniemen herkennen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse NLP niet aangetoond; demo vraagt ASCII |
| Omgeving en uitwisseling | Webdemo; tekst, bestand of URL; C-value en POS-tagging |
| Licentie of toegang | Publieke demo; productievoorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Vergelijk statistische termhood met juridische relevantie; acroniemen horen aan de uitgeschreven vorm en context gekoppeld te worden.

**Beperking:** De makersdemo beperkt tekst tot ASCII en bestanden tot 2 MB. Dat corrigeert de brede INT-vermelding van Unicode-talen; een Nederlandse proef vereist expliciete taalondersteuning.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-42). Bronnen: [H038](https://www.nactem.ac.uk/software/termine/). Vindplaats: TerMine / Usage; Limitations; Background.

### H039 TermoStat Web 3.0

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Termkandidaten uit een gespecialiseerd corpus selecteren.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt vijf talen zonder Nederlands |
| Omgeving en uitwisseling | TermoStat; huidige URL levert een JavaScript-app |
| Licentie of toegang | Toegang en actuele versie niet vastgesteld |

**Betekenis voor Wetsanalyse:** De verhouding tussen vakcorpus en algemeen corpus is een bruikbaar selectieprincipe, mits ook laagfrequente juridische elementen worden beoordeeld.

**Beperking:** De oude documentatie-URL geeft geen leesbare handleiding meer. De aanduiding versie 3.0 is niet als actuele productversie bevestigd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-43). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H039](https://termostat.ling.umontreal.ca/doc_termostat/doc_termostat_en.html), [H039B](https://termostat.ling.umontreal.ca/). Vindplaats: Termextractie / TermoStat.

### H040 TermTreffer

**Oordeel:** Opvolger onderzoeken. **Functie:** Nederlandstalige termextractie.

| Aspect | Bevinding |
|---|---|
| Nederlands | Ja, volgens INT |
| Omgeving en uitwisseling | Historische TermTreffer; verdiept via TermWerk |
| Licentie of toegang | Voor huidige toegang: TermWerk |

**Betekenis voor Wetsanalyse:** De relevante ontwikkellijn loopt van termextractie naar beschrijving en beheer binnen één workflow. Gebruik TermWerk als actuele vergelijkingskandidaat.

**Beperking:** De INT-toolrij verwijst alleen naar de INT-homepage. Behandel TermTreffer niet als een zelfstandig geverifieerde actuele dienst.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-44). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [INT15](https://ivdnt.org/actueel/nieuws/terminologietool-termwerk/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf). Vindplaats: TermTreffer; TermWerk nieuws en handleiding.

### H041 TexLexAn

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Tekst classificeren en samenvatten.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt geen Nederlands |
| Omgeving en uitwisseling | Historische TexLexAn-verwijzing |
| Licentie of toegang | Actuele voorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Samenvatting kan leeswerk ondersteunen, maar de geannoteerde wetsformulering moet letterlijk bewaard blijven.

**Beperking:** INT noemt gestopte ontwikkeling; de SourceForge-pagina was niet inhoudelijk beschikbaar. Geen huidige inzet aanbevelen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-45). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H041](https://texlexan.sourceforge.net/). Vindplaats: Termextractie / TexLexAn.

### H042 TextSTAT

**Oordeel:** Proefkandidaat activiteit 2. **Functie:** Frequenties en concordanties in eigen teksten onderzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse interface; Unicode; inhoudelijke kwaliteit te testen |
| Omgeving en uitwisseling | Windows, macOS, Linux; tekst, HTML, PDF, Office; CSV-uitvoer |
| Licentie of toegang | Gratis gebruik; herdistributievoorwaarden op makerspagina |

**Betekenis voor Wetsanalyse:** Geschikt als eenvoudige controleerbare baseline voor alle voorkomens van een formulering, met export voor menselijke beoordeling.

**Beperking:** PDF- en Office-extractie kan bronposities veranderen. Koppel resultaten terug naar canonieke brontekst voordat ze annotatievoorstellen worden.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-46). Bronnen: [H042](https://neon.niederlandistik.fu-berlin.de/nl/textstat/). Vindplaats: TextSTAT 3 / beschrijving; download; disclaimer.

### H043 Tilde Terminology

**Oordeel:** Alternatieve proefkandidaat. **Functie:** Termextractie en terminologiediensten.

| Aspect | Bevinding |
|---|---|
| Nederlands | INT noemt EU-talen; Nederlandse werking niet uitgevoerd |
| Omgeving en uitwisseling | Tilde Terminology JavaScript-app; INT noemt API en CAT-plug-ins |
| Licentie of toegang | Actuele toegang en licentie onbekend |

**Betekenis voor Wetsanalyse:** Interessant bij een toekomstige meertalige extractieproef; beoordeel per taal dezelfde fouttypen en behoud van context.

**Beperking:** Een geladen app bewijst geen beschikbare API of werkend Nederlands model. Eerst documentatie en proefuitvoer verkrijgen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-47). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H043](https://term.tilde.com/). Vindplaats: Termextractie / Tilde Terminology.

### H044 VocabGrabbler

**Oordeel:** Later. **Functie:** Woordenschat met gebruiksvoorbeelden verkennen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Engels gericht |
| Omgeving en uitwisseling | Web; woordenlijsten en thesaurusweergave |
| Licentie of toegang | Publieke interface; aanvullende voorwaarden niet onderzocht |

**Betekenis voor Wetsanalyse:** Een interactieve woordkaart kan analisten helpen navigeren, maar relaties moeten zichtbaar hun eigen bewijs en betekenis houden.

**Beperking:** Woordenschatonderwijs en algemene thesaurusrelaties bieden geen juridisch begrippenmodel. Geen Nederlandse inzet aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-48). Bronnen: [H044](https://www.visualthesaurus.com/vocabgrabber/). Vindplaats: VocabGrabber / How does Vocabgrabber work.

### H045 Wordle

**Oordeel:** Afgevallen. **Functie:** Historisch woordenwolken maken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet relevant voor huidig aangetroffen aanbod |
| Omgeving en uitwisseling | INT-link toont inmiddels woordspelinhoud |
| Licentie of toegang | Oorspronkelijke toepassing niet geverifieerd |

**Betekenis voor Wetsanalyse:** Een woordenwolk kan frequenties tonen, maar verbergt broncontext, negatie en uitzonderingen en helpt nauwelijks bij juridische beoordeling.

**Beperking:** Het bezochte domein bevat niet de beschreven oorspronkelijke toepassing. De naam niet verwarren met actuele gelijknamige spellen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-49). Bronnen: [H045](https://www.wordle.net/), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: Termextractie / Wordle; waargenomen bestemmingspagina.

## Terminologiebeheer – onafhankelijke applicaties

### H046 Acrolinx

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Terminologiegebruik in teksten controleren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse taalondersteuning niet bevestigd |
| Omgeving en uitwisseling | Schrijfondersteuning en terminologiebeheer; huidige directe toegang geblokkeerd |
| Licentie of toegang | Commercieel; geen prijs vastgesteld |

**Betekenis voor Wetsanalyse:** Maak controles op voorkeurstermen alleen actief op eigen toelichtingen en conceptdefinities. Bronwetten en citaten mogen niet worden geharmoniseerd.

**Beperking:** De makersdocumentatie beschrijft schrijfconsistentie; dat bewijst geen juridische juistheid. De actuele product-/merkovergang is niet volledig onderzocht.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-51). Bronnen: [H046B](https://www.acrolinx.com/translatability/), [H046C](https://support.acrolinx.com/hc/en-us/articles/10211163344018-Configure-Term-Sets-in-the-Language-Configuration-File). Vindplaats: Translatability; Configure Term Sets.

### H047 Anylexic

**Oordeel:** Later. **Functie:** Meertalige woordenlijsten centraal opzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Tekstopslag mogelijk; Nederlandse NLP niet aangetoond |
| Omgeving en uitwisseling | Desktop; TXT, CSV, XLS en eigen AEF-formaat; sneltoetsen |
| Licentie of toegang | Actuele licentie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Het zoeken vanuit de werkplek is nuttig. Laat Lex een beoordeeld begrip met broncontext tonen in plaats van alleen een vervangterm.

**Beperking:** De makerspagina beschrijft woordenlijstbeheer; versieondersteuning en omzetting naar het juridische begrippenmodel zijn niet aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-52). Bronnen: [H047](https://www.anylexic.com/). Vindplaats: Homepage / Main features.

### H048 ApSIC Xbench

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Vertaalterminologie en consistentie controleren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Tekstformaten; geen Nederlandse juridische NLP |
| Omgeving en uitwisseling | Windows; meerdere CAT-formaten, waaronder TMX en XLIFF |
| Licentie of toegang | Commercieel abonnement; proefperiode |

**Betekenis voor Wetsanalyse:** Gebruik expliciete consistentiecontroles, bijvoorbeeld ontbrekende bronnen of uiteenlopende labels, als aandachtssignalen voor review.

**Beperking:** Een formele QA-melding bewijst niet dat de gebruikte term inhoudelijk juist is. Het actuele productadres is xbench.net.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-53). Bronnen: [H048B](https://www.xbench.net/). Vindplaats: Highlights / QA Features; Terminology Features.

### H049 evoTerm

**Oordeel:** Onvoldoende bewijs. **Functie:** Terminologie via een webomgeving beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | evoTerm; hosting en uitvoer niet geverifieerd |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** De INT-beschrijving van rechten per taal is een relevant governancepatroon, maar nog geen vereiste voor de eerste eentalige werkplek.

**Beperking:** De opgegeven website reageerde niet. Actuele beschikbaarheid, licentie en onderhoud blijven onbekend.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-54). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H049](https://www.evoterm.net/Terminologie.aspx). Vindplaats: Terminologiebeheer / evoTerm.

### H050 FAIRterm

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Deelbare terminologische fiches volgens FAIR organiseren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig gegevensbeheer; geen Nederlandse extractie aangetoond |
| Omgeving en uitwisseling | FAIRterm-webomgeving en tutorial |
| Licentie of toegang | Gratis met aangevraagde toegang volgens projectpagina |

**Betekenis voor Wetsanalyse:** Denk naast velden aan vindbaarheid, toegangsvoorwaarden, uitwisselbaarheid en verantwoord hergebruik van begrippen.

**Beperking:** FAIR betekent niet automatisch openbaar of juridisch gevalideerd. De tutorial beschrijft het ontwerp; een ingelogde workflow is niet getest.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-55). Bronnen: [H050](https://yourterm.eu/toolbox/), [H050B](https://yourterm.eu/wp-content/uploads/2022/05/FAIRterm-presentation-update.pdf). Vindplaats: YourTerm ToolBox / FAIRterm Application; tutorial.

### H051 Inter Active Terminology for Europe

**Oordeel:** Contextbron activiteit 3. **Functie:** EU-terminologie opzoeken en beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse EU-terminologie beschikbaar |
| Omgeving en uitwisseling | IATE-webtermenbank; selectie van records en exportvoorwaarden apart beoordelen |
| Licentie of toegang | Publiek zoeken; hergebruikvoorwaarden niet volledig onderzocht |

**Betekenis voor Wetsanalyse:** Gebruik een record als aanknopingspunt voor EU-bronnen, met domein en herkomst. Leg een externe begripsmapping afzonderlijk voor aan de analist.

**Beperking:** Een IATE-record is geen automatische definitie voor een Nederlandse regeling. Geen algemene betrouwbaarheidsscore omzetten naar juridische goedkeuring.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-56). Bronnen: [H051](https://iate.europa.eu/home). Vindplaats: Home / About IATE.

### H052 Kalcium Quickterm

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Collaboratief terminologiebeheer en validatie.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig beheer; Nederlandse taalmodules niet bewezen |
| Omgeving en uitwisseling | Quickterm-webplatform; configureerbaar gegevensmodel en workflow |
| Licentie of toegang | Commercieel; demoaanbod |

**Betekenis voor Wetsanalyse:** Maak verzoek, voorstel, bespreking, beoordeling en publicatie afzonderlijk zichtbaar. De reviewgeschiedenis hoort ook bij afgewezen voorstellen.

**Beperking:** De maker claimt schaalbaarheid en kwaliteit; deze zijn niet gemeten. Geen platformaanschaf nodig om het workflowpatroon over te nemen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-57). Bronnen: [H052](https://kaleidoscope.at/en/products/quickterm/). Vindplaats: Quickterm / At a Glance; platformbeschrijving.

### H053 Lingo 4.0

**Oordeel:** Later. **Functie:** Kleine terminologiebanken op een desktop beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige invoer; geen Nederlandse NLP aangetoond |
| Omgeving en uitwisseling | Lingo 4.0 voor Windows; downloadbare evaluatie |
| Licentie of toegang | Commerciële/evaluatiedistributie |

**Betekenis voor Wetsanalyse:** Een eenvoudig fiche kan een nuttige ondergrens voor gebruiksgemak zijn: naam, definitie, context en vindplaats snel kunnen vergelijken.

**Beperking:** De makerspagina toont een andere build en interfacetalen dan INT. Een aangeboden download bewijst geen onderhoud of geschiktheid voor huidige systemen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-58). Bronnen: [H053](https://www.lexicool.com/soft_lingo2.asp). Vindplaats: Lingo 4.0 / Overview; evaluation.

### H054 MoBiDic

**Oordeel:** Onvoldoende bewijs. **Functie:** Elektronische woordenboeken raadplegen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | MoBiDic/MorphoLogic; actuele productpagina is algemeen |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Contextuele woordenboektoegang is een gebruikerspatroon; het beoogde analysebegrip moet daarnaast werkgebied en juridische onderbouwing dragen.

**Beperking:** De INT-link komt uit op een algemene productpagina en onderbouwt de beschreven MoBiDic-functionaliteit niet voldoende.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-59). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H054](https://www.morphologic.hu/content/view/212/106/lang,en/). Vindplaats: Terminologiebeheer / MoBiDic.

### H055 MultiTerm

**Oordeel:** Later. **Functie:** Terminologiebanken in de Trados-omgeving beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige opslag volgens INT; taalwerking niet uitgevoerd |
| Omgeving en uitwisseling | MultiTerm; directe makerspagina geeft lege challenge-respons |
| Licentie of toegang | Actuele editie en licentie niet geverifieerd |

**Betekenis voor Wetsanalyse:** Vergelijk concept-, taal- en termvelden bij uitwisseling met bestaande terminologiebanken, vooral als gebruikers al MultiTerm gebruiken.

**Beperking:** Geen actuele specifieke productclaim uit de onleesbare pagina afgeleid. MultiTerm Extract en Trados Terminology blijven afzonderlijke vermeldingen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-60). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H055](https://www.sdl.com/solution/language/terminology-management/multiterm/), [H055B](https://www.trados.com/product/multiterm/). Vindplaats: Terminologiebeheer / MultiTerm.

### H056 MultiTes - Thesaurus and Taxonomy Authoring Tools

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Thesauri opbouwen en publiceren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertaligheid niet inhoudelijk getest |
| Omgeving en uitwisseling | MultiTes Pro, WDK en EDK; desktop en webpublicatie |
| Licentie of toegang | Commercieel aanbod; actuele voorwaarden niet gecontroleerd |

**Betekenis voor Wetsanalyse:** Thesaurusbeheer kan generieke, hiërarchische en associatieve relaties helpen ordenen. Beoordeel apart welke relaties juridisch betekenis dragen.

**Beperking:** Productbeschrijving via webtool gelezen; directe URL gaf 404. Thesaurusstructuur is geen bewijs voor een volledige juridische ontologie.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-61). Bronnen: [H056C](https://www.multites.com/products.htm). Vindplaats: Our Products.

### H057 MultiTrans TermBase

**Oordeel:** Later. **Functie:** Terminologie binnen MultiTrans beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | MultiTrans TermBase; INT verwijst naar een appstore-app |
| Licentie of toegang | Actuele modulelicentie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een gedeelde termenbank is bruikbaar voor consistente toelichtingen, mits iedere term naar een beoordeeld begrip met context verwijst.

**Beperking:** De gelinkte JavaScript-pagina levert geen leesbare modulespecificatie. Niet aannemen dat alle suitefuncties in deze module zitten.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-62). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H057](https://appstore.rws.com/plugin/87/). Vindplaats: Terminologiebeheer / MultiTrans TermBase.

### H058 Ontoterminology Editor (Tedi)

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Concepten formeel modelleren en van termen voorzien.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig model; geen Nederlandse juridische analyse |
| Omgeving en uitwisseling | Tedi-desktop; RDF/OWL, SKOS, TBX, OntoLex, CSV en HTML volgens maker |
| Licentie of toegang | Persoonlijk academisch, niet-commercieel gebruik volgens licentie |

**Betekenis voor Wetsanalyse:** Scheid conceptuele kenmerken van taalvormen. Gebruik een relationeel diagram om ontbrekende onderscheidende kenmerken bespreekbaar te maken.

**Beperking:** Een formeel consistente ontologie bewijst geen juiste wetsinterpretatie. De licentie geeft geen algemene toestemming voor operationele overheidsinzet.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-63). Bronnen: [H058B](https://ontoterminology.com/tedi), [H058](https://ontoterminology.com/licence). Vindplaats: Tedi / Conceptual dimension; Personal User Licence.

### H059 QTerm

**Oordeel:** Ontwerpvoorbeeld en uitwisselkandidaat. **Functie:** Flexibele terminologiebanken met rollen en workflow beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige velden; Nederlandse NLP niet bewezen |
| Omgeving en uitwisseling | Qterm/memoQweb; TBX, CSV, MultiTerm XML; gedocumenteerde WS API |
| Licentie of toegang | Onderdeel memoQ-omgeving; concrete licentie niet onderzocht |

**Betekenis voor Wetsanalyse:** De API-documentatie laat zien waarom eigen velden expliciet moeten worden gemapt. Test bronverwijzingen en status bij elke heen-en-terugconversie.

**Beperking:** De oude productlink geeft 404. De gelezen exportdocumentatie gebruikt TBX met productspecifieke metadata; TBX-ondersteuning alleen bewijst geen compatibiliteit met TermWerk.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-64). Bronnen: [H059C](https://docs.memoq.com/current/en/memoQWeb-help/mqw-qterm.html), [H059D](https://docs.memoq.com/11-3/api-docs/wsapi/memoqservices/tbservice.importexport.tbx.html). Vindplaats: Qterm; WS API / Term base in TBX format.

### H060 STAR WebTerm

**Oordeel:** Later. **Functie:** Terminologie via de browser raadplegen en beoordelen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | STAR WebTerm; winkelpagina niet bereikbaar |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Browsertoegang kan verspreide beoordelaars betrekken; beslissingen moeten ook buiten de terminologietool terugvindbaar blijven.

**Beperking:** TLS-probleem op de opgegeven shop. Actuele WebTerm-versie en relatie tot TermStar moeten vóór inzet worden bevestigd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-65). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H060](https://shop.star-group.net/), [H088](https://www.star-group.net/en/products/terminology-management.html). Vindplaats: Terminologiebeheer / STAR WebTerm.

### H061 Term4Client

**Oordeel:** Later. **Functie:** Klantterminologie in een beheerd portaal vastleggen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige benamingen en landspecifiek gebruik |
| Omgeving en uitwisseling | Gehost portaal; lees- en schrijfrechten; configureerbare metadata |
| Licentie of toegang | Commerciële dienstverlening; voorwaarden op aanvraag |

**Betekenis voor Wetsanalyse:** Een aparte aanduiding voor landgebonden termgebruik helpt naamvarianten onderscheiden van verschillende juridische betekenissen.

**Beperking:** De maker beschrijft concepten en benamingen op één niveau; dat moet expliciet worden getoetst aan het gewenste onderscheid tussen begrip en term.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-66). Bronnen: [H061](https://www.e-kern.com/en/technology/term4client/). Vindplaats: term4client / online terminology portal.

### H062 Termbases

**Oordeel:** Onvoldoende bewijs. **Functie:** Publieke en private termenbanken aanbieden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Termbases.eu; login en publieke lijsten zichtbaar |
| Licentie of toegang | Voorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een publieke leesomgeving kan losstaan van het redactieproces. Voor het project blijft een controleerbare publicatiestand nodig.

**Beperking:** De openbare pagina biedt onvoldoende functionele documentatie om model, export, audit of onderhoud te beoordelen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-67). Bronnen: [H062](https://www.termbases.eu/), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: Homepage; Terminologiebeheer / Termbases.

### H063 Terminologue

**Oordeel:** Proefkandidaat activiteit 3. **Functie:** Conceptgerichte termenbanken redigeren en publiceren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige opslag; Nederlandse smart-searchkwaliteit onbekend |
| Omgeving en uitwisseling | Web; eigen installatie mogelijk; TBX en TXT; historie en rollen |
| Licentie of toegang | MIT-broncode; gehoste dienst met eigen voorwaarden |

**Betekenis voor Wetsanalyse:** Vergelijk vooral herbeoordeling na wijziging, conceptfiches en rolverdeling met spoor D. Gebruik als referentie voor review, niet als automatische bron van juridische betekenissen.

**Beperking:** Gedeelde termen kunnen wijzigingen naar andere fiches laten doorwerken. Juridische context en bronankers vereisen een bewuste eigen inrichting.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-68). Bronnen: [H063B](https://www.terminologue.org/docs/intro.en/), [H063C](https://www.terminologue.org/docs/info.en/). Vindplaats: Introduction / Term sharing; Entry status; History log; About.

### H064 TermStar

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Terminologie beheren voor auteurs en vertalers.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige toepassing; Nederlands niet specifiek getest |
| Omgeving en uitwisseling | TermStar; zie afzonderlijke productpagina bij H088 |
| Licentie of toegang | Commercieel; exacte editie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een voorkeursterm helpt eigen analyses consistent formuleren, maar mag citaten uit verschillende regelingen niet overschrijven.

**Beperking:** De INT-link gaat naar algemene taaldiensten. Deze vermelding hoort bij dezelfde productidentiteit als STAR TermStar H088.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-69). Bronnen: [H088](https://www.star-group.net/en/products/terminology-management.html), [H064](https://www.star-group.net/en/services/language-services.html?modAcc=3). Vindplaats: TermStar / Terminology management.

### H065 TermWeb

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Termenbanken met workflow en gebruikersrollen beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalvarianten beschreven; Nederlandse NLP onbekend |
| Omgeving en uitwisseling | TermWeb 4; API-synchronisatie beschreven in handleiding |
| Licentie of toegang | Commercieel; huidige leverbaarheid niet bevestigd |

**Betekenis voor Wetsanalyse:** Een aparte workflow voor beoordeling en gerichte synchronisatie voorkomt dat ongecontroleerde termen zomaar in andere toepassingen landen.

**Beperking:** Directe site blokkeert. Handleiding 1.7.2 van 22 juni 2023 is via webtool deels leesbaar; huidige API-contracten zijn niet getest.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-70). Bronnen: [H065B](https://www.interverbumtech.com/wp-content/uploads/2021/04/TermWeb-4-User-Administrator-Guide-v1.7.pdf). Vindplaats: Guide / Workflow Conditions; User roles; revision history.

### H066 TermWiki Pro

**Oordeel:** Onvoldoende bewijs. **Functie:** Terminologie in een teamomgeving beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | TermWiki Pro; directe website blokkeert |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Het samenwerken aan termen is een nuttig patroon, maar specifieke rechten, bronvelden en wijzigingsgeschiedenis moeten aantoonbaar zijn.

**Beperking:** De openbare productpagina kon niet inhoudelijk worden gelezen. De naam en INT-beschrijving zijn onvoldoende voor een technisch advies.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-71). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H066](https://pro.termwiki.com/terminology-management/). Vindplaats: Terminologiebeheer / TermWiki Pro.

### H067 TermXplorer

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Concept-, taal- en termvelden configureerbaar beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Talen configureerbaar volgens productfiche |
| Omgeving en uitwisseling | Web/intranet; TBX, MultiTerm XML, Excel en Web-API volgens fiche |
| Licentie of toegang | Bedrijfsbrede licentie volgens historische fiche |

**Betekenis voor Wetsanalyse:** Een eigen status op elk beschrijvingsniveau maakt verschil tussen een beoordeeld begrip en een nog onbesliste term zichtbaar.

**Beperking:** Het gelezen fiche is gedateerd november 2018. Het bewijst het ontwerp, niet actuele beschikbaarheid of een ondersteunde huidige API.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-72). Bronnen: [H067B](https://term-solutions.com/wp-content/uploads/2020/08/InfoSheet_termXplorer_TermSolutions.pdf). Vindplaats: InfoSheet termXplorer, november 2018, pp. 1–2.

### H068 TippyTerm

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Voorkeurstermen tijdens schrijven aanbieden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Unicode en uitbreidbare talen volgens maker |
| Omgeving en uitwisseling | Desktopwerkbalk; termdetails en taalkeuze |
| Licentie of toegang | Actuele licentie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Een compacte begripsopzoeker naast de tekst kan de analist helpen consequent te formuleren zonder het bronpaneel te verlaten.

**Beperking:** Automatisch vervangen past alleen bij eigen tekst. De letterlijke wettelijke formulering moet altijd behouden blijven.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-73). Bronnen: [H068](https://www.tippyterm.de/tippyterm/anwendung/). Vindplaats: Anwendung / Funktionsweise; Weitere Funktionalitäten.

### H069 tlTerm Terminology Software

**Oordeel:** Alternatieve proefkandidaat. **Functie:** Terminologie met corpus en teamredactie beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Maker zegt alle talen; Nederlandse kwaliteit niet gemeten |
| Omgeving en uitwisseling | Windows/macOS; termbankeditor; TBX-verwerking en publicatie via TLex Online |
| Licentie of toegang | Commercieel aanbod |

**Betekenis voor Wetsanalyse:** Een corpus naast het fiche ondersteunt het vergelijken van gebruikscontexten. AI-hulp moet herkenbare voorstellen opleveren die de analist kan afwijzen.

**Beperking:** De makersclaim over snelle verwerking van grote IATE-bestanden is geen eigen meting. Geen bewijs voor volledige juridische bronankers.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-74). Bronnen: [H069B](https://tshwanedje.com/terminology/). Vindplaats: tlTerm / productbeschrijving.

### H070 TManager

**Oordeel:** Onvoldoende bewijs. **Functie:** Terminologiebeheer volgens INT.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | TManager; makersdomein niet gevonden via DNS |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** De vermelding is behouden voor volledigheid; er is onvoldoende bewijs om er een concreet ontwerp- of integratieadvies op te baseren.

**Beperking:** De actuele productidentiteit, uitvoerformaten en onderhoudsstatus zijn niet verifieerbaar vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-75). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H070](https://www.rafaelguzman.ie/tools/). Vindplaats: Terminologiebeheer / TManager.

### H071 Trados Terminology

**Oordeel:** Later. **Functie:** Terminologie binnen Trados aanbieden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Trados Terminology; INT verwijst naar algemene prijsinformatie |
| Licentie of toegang | Actuele productafbakening en licentie niet bevestigd |

**Betekenis voor Wetsanalyse:** Relevant wanneer terminologie met een bestaande Trados-organisatie gedeeld moet worden; bepaal dan eerst de concrete editie en eigenaar van de data.

**Beperking:** Een algemene prijspagina is geen productspecificatie. Niet automatisch gelijkstellen aan MultiTerm of MultiTerm Extract.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-76). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H071](https://www.trados.com/pricing/). Vindplaats: Terminologiebeheer / Trados Terminology.

### H072 UniTerm Terminologie Management

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Organisatieterminologie beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig beheer; Nederlandse NLP niet bevestigd |
| Omgeving en uitwisseling | UniTerm; herstelde productpagina gevonden |
| Licentie of toegang | Commercieel; exacte voorwaarden niet onderzocht |

**Betekenis voor Wetsanalyse:** Een expliciet begrippenkader helpt teams dezelfde termen doelgericht gebruiken. Bewaar afwijkende wettelijke formuleringen als brongegevens.

**Beperking:** De oorspronkelijke INT-URL leidt naar een afbeelding. Gebruik de nieuwe productpagina voor oriëntatie en vraag vóór integratie een concrete exportspecificatie.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-77). Bronnen: [H072C](https://acolada.de/produkte/uniterm-terminologieverwaltung/), [H072](https://www.acolada.de/UniTerm.htm). Vindplaats: UniTerm Terminologieverwaltung.

## Terminologiebeheer – onafhankelijke applicaties geschikt voor kennisbeheer met grafische relatieweergave

### H073 Congree TermTiger Terminology System

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Terminologie en schrijfondersteuning combineren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse ondersteuning niet bevestigd |
| Omgeving en uitwisseling | Congree UCC; geïntegreerde editors en SDK volgens maker |
| Licentie of toegang | Commercieel |

**Betekenis voor Wetsanalyse:** Controles op eigen definities en toelichtingen kunnen stijl- en termvarianten signaleren. De beoordelaar moet inhoudelijke uitzonderingen kunnen uitleggen.

**Beperking:** De huidige toolspagina toont een breder platform en bevestigt niet zelfstandig de oude TermTiger-productafbakening.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-79). Bronnen: [H073](https://www.congree.com/en/tools). Vindplaats: Tools / Authoring Assistance; Congree SDK.

### H074 Coreon Multilingual Knowledge System

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Meertalige begrippen en kennisgraaf gezamenlijk beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalonafhankelijke concepten met meertalige termen |
| Omgeving en uitwisseling | Coreon; REST/SPARQL; TBX, SKOS en RDF als genoemde formaten |
| Licentie of toegang | Commercieel; geen offerte gevraagd |

**Betekenis voor Wetsanalyse:** Zet relaties tussen begrippen en taalvarianten op afzonderlijke plaatsen. Laat een gewijzigde voorkeursterm de begripsidentiteit en relaties intact laten.

**Beperking:** Inhoudelijke gelijkheid blijft een juridisch oordeel. Een meertalige kennisgraaf levert geen kant-en-klare mapping naar JAS of de bronankers van het project.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-80). Bronnen: [H074](https://coreon.com/terminology-management/). Vindplaats: Terminology Management / One System, One View; APIs.

### H075 i-Term

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Begrippen met kenmerken en relaties tekenen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig conceptbeheer; geen Nederlandse NLP bewezen |
| Omgeving en uitwisseling | i-Term met i-Model; conceptdiagram en UML-weergave |
| Licentie of toegang | Actuele licentie niet vastgesteld |

**Betekenis voor Wetsanalyse:** Laat de analist per relatie het soort verband en het onderscheidende kenmerk zien. Een boom alleen is onvoldoende voor alle juridische verbanden.

**Beperking:** Documentatie via webtool gelezen; directe opvraag geblokkeerd. Exportsemantiek en beschikbaarheid van de toepassing zijn niet getest.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-81). Bronnen: [H075B](https://www.danterm.dk/products/i-model.html), [H075C](https://www.danterm.dk/products/i-term-main.html). Vindplaats: i-Model; i-Term main.

### H076 LookUp (D.O.G.)

**Oordeel:** Ontwerpvoorbeeld en uitwisselkandidaat. **Functie:** Termen, relaties en review in één omgeving beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig model; Nederlandse NLP niet bewezen |
| Omgeving en uitwisseling | LookUp D.O.G.; API, CSV, TBX, MultiTerm en RDF volgens maker |
| Licentie of toegang | Huur/koop en proefaanbod |

**Betekenis voor Wetsanalyse:** Combineer conceptdiagrammen met broncontext, wijzigingen en rollen. Gebruik het als vergelijkingsmodel voor een begripskaart met navolgbare relaties.

**Beperking:** Formaatnamen bewijzen geen behoud van juridische metadata. Dit product is niet hetzelfde als LookUp op lookup-web.de.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-82). Bronnen: [H076](https://www.dog-gmbh.de/lookup-produkt/). Vindplaats: LookUp Produkt / Hauptmerkmale.

### H077 LookUp-Terminology Management Professional

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Terminologie beheren volgens historische INT-vermelding.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | LookUp Terminology Management Professional; andere maker dan D.O.G. |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Gelijknamige tools moeten op maker en identiteit worden onderscheiden; dit is ook een nuttige illustratie van homonymie voor het begrippenmodel.

**Beperking:** De host heeft een certificaatprobleem. De vermelding wordt niet samengevoegd met H076 en niet als actueel product aanbevolen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-83). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H077](https://www.lookup-web.de/index.php). Vindplaats: Terminologiebeheer met grafische relatieweergave / LookUp.

### H078 Ontoterminology Editor (Tedi)

**Oordeel:** Duplicaat van H058. **Functie:** Concepten formeel modelleren en van termen voorzien.

| Aspect | Bevinding |
|---|---|
| Nederlands | Zie H058 |
| Omgeving en uitwisseling | Tedi; tweede vermelding in een andere rubriek |
| Licentie of toegang | Zie H058 |

**Betekenis voor Wetsanalyse:** De dubbele opname laat zien dat één toepassing meerdere functies kan hebben; rubriektoewijzing en productidentiteit blijven gescheiden.

**Beperking:** Geen tweede product of tweede onafhankelijk bewijs. De inhoudelijke beoordeling staat bij H058.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-84). Bronnen: [H058B](https://ontoterminology.com/tedi), [H058](https://ontoterminology.com/licence). Vindplaats: Tedi / product en licentie.

### H079 Protégé

**Oordeel:** Proefkandidaat voor modelcontrole. **Functie:** OWL-ontologieën modelleren en controleren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalgetagde gegevens; geen Nederlandse termextractie |
| Omgeving en uitwisseling | Desktop en WebProtégé; OWL 2, RDF en uitwisselformaten |
| Licentie of toegang | Gratis opensource volgens maker |

**Betekenis voor Wetsanalyse:** Gebruik een kleine begrippenproef om het onderscheid tussen SKOS-begrippen, OWL-klassen en concrete entiteiten te toetsen.

**Beperking:** Een reasoner valideert formele consequenties van ingevoerde axioma's. Hij stelt niet vast of de wet juist is geïnterpreteerd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-85). Bronnen: [H079B](https://protege.stanford.edu/software). Vindplaats: Software / WebProtégé; Protégé Desktop.

### H080 Synaptica Graphite

**Oordeel:** Ontwerpvoorbeeld activiteit 3. **Functie:** Taxonomieën en ontologieën redigeren en publiceren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige metadata; geen Nederlandse NLP bewezen |
| Omgeving en uitwisseling | Graphite; native RDF; editor- en publicatieomgeving |
| Licentie of toegang | Commercieel; demoaanbod |

**Betekenis voor Wetsanalyse:** Scheid redactie van publicatie en maak de gebruikte begrippenstand expliciet. Gebruik getypeerde relaties en controleer hun herkomst.

**Beperking:** Marketing over kwaliteit en besparing is niet als meetresultaat overgenomen. Geen noodzaak vastgesteld om de bestaande graaf hiermee te vervangen.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-86). Bronnen: [H080](https://www.synaptica.com/synaptica-graphite/). Vindplaats: Synaptica Graphite / benefits; RDF concept modeling.

## Vertaalgeheugens met geïntegreerde terminologiemodule

### H081 Déjà Vu X3

**Oordeel:** Later. **Functie:** Vertalen met hergebruik van geheugen en termen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse vertaalondersteuning niet gecontroleerd |
| Omgeving en uitwisseling | Déjà Vu X3; desktop/teams en terminologiedatabase |
| Licentie of toegang | Commercieel aanbod |

**Betekenis voor Wetsanalyse:** Hergebruik en suggesties kunnen het redigeren versnellen, maar een eerder goedgekeurde formulering moet opnieuw op de huidige rechtscontext worden getoetst.

**Beperking:** De primaire taak is vertalen. Er is geen wettelijke brongraaf, JAS-classificatie of juridisch reviewcontract aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-88). Bronnen: [H081](https://atril.com/). Vindplaats: Homepage / Products; teams.

### H082 ESTeam Translator

**Oordeel:** Onvoldoende bewijs. **Functie:** Vertaalautomatisering volgens INT.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | ESTeam Translator; oude route komt uit op lege homepage-extractie |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** De vermelding blijft in de kaart, maar levert zonder leesbare productdocumentatie geen concreet projectadvies op.

**Beperking:** Het huidige aanbod, terminologiecomponent en onderhoud zijn niet vastgesteld. HTTP 200 is hier geen inhoudelijke bevestiging.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-89). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H082](https://www.esteam.se/solutions/translation-automation.html). Vindplaats: Vertaalgeheugens / ESTeam Translator.

### H083 memoQ Translator Pro

**Oordeel:** Later. **Functie:** Vertalen met geheugen, termen en waarschuwingen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig; Nederlandse termextractiekwaliteit onbekend |
| Omgeving en uitwisseling | Windows; termbases en referentiemateriaal; importfuncties |
| Licentie of toegang | Commercieel abonnement en proefaanbod |

**Betekenis voor Wetsanalyse:** Een waarschuwing bij afwijkend termgebruik kan nuttig zijn voor eigen analyses. Laat de gebruiker steeds de achterliggende definitie en context zien.

**Beperking:** Vertaalgeheugen, termbase en juridisch analysebegrip hebben verschillende doelen. Geen reden voor vervanging van de bestaande werkplek.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-90). Bronnen: [H083](https://www.memoq.com/en/memoq-translator-pro). Vindplaats: memoQ translator pro / Term base; Translation memory.

### H084 MetaTexis

**Oordeel:** Onvoldoende bewijs. **Functie:** Vertaalondersteuning in documenten.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | MetaTexis; Nederlandse URL niet bereikbaar |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Documentgebonden hergebruik is een historische inspiratiebron, maar bronversie en begripsbeslissingen vragen eigen registratie.

**Beperking:** TLS-verbinding mislukte. Actuele systeemvereisten en data-export zijn niet geverifieerd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-91). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H084](https://www.metatexis.net/dutch/index.htm). Vindplaats: Vertaalgeheugens / MetaTexis.

### H085 OmegaT

**Oordeel:** Later of kleine uitwisselproef. **Functie:** Open vertaalomgeving met geheugen en glossaria.

| Aspect | Bevinding |
|---|---|
| Nederlands | Unicode; Nederlandse corpus-/termkwaliteit niet gemeten |
| Omgeving en uitwisseling | Windows, macOS, Linux; diverse tekstformaten en gebruikersglossaria |
| Licentie of toegang | GPLv3 volgens maker |

**Betekenis voor Wetsanalyse:** Bruikbaar om te onderzoeken hoe een beoordeelde begrippenlijst beschikbaar komt tijdens vertaalwerk, als dat later onderdeel van het traject wordt.

**Beperking:** Fuzzy matches en verbogen termherkenning bewijzen geen gelijke wettelijke betekenis. Geen juridische analysefunctie vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-92). Bronnen: [H085B](https://omegat.org/). Vindplaats: Homepage / Professional features; Powerful tools; license.

### H086 OpenTM2

**Oordeel:** Later met verificatie. **Functie:** Vertaalprojecten met open formaten ondersteunen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Maker noemt alle talen; niet getest |
| Omgeving en uitwisseling | OpenTM2; TMX, TBX, XLIFF genoemd |
| Licentie of toegang | Opensourceclaim op site; repository/licentie niet verder geverifieerd |

**Betekenis voor Wetsanalyse:** Open uitwisselformaten kunnen leveranciersafhankelijkheid beperken, mits bronkoppelingen en status apart worden gecontroleerd.

**Beperking:** De website bevat ook niet-productgerelateerde berichten. Actueel onderhoud en betrouwbare distributiebron zijn daarom niet voldoende vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-93). Bronnen: [H086](https://www.opentm2.org/). Vindplaats: Homepage / OpenTM2 description.

### H087 SDL Trados Studio

**Oordeel:** Later. **Functie:** Computerondersteund vertalen met terminologie.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd voor huidige editie |
| Omgeving en uitwisseling | Trados Studio; oude SDL-link en nieuwe productpagina beperkt leesbaar |
| Licentie of toegang | Actuele licentie niet bevestigd |

**Betekenis voor Wetsanalyse:** Een mogelijke afnemer van een gecontroleerde terminologie-export; bepaal eerst welke velden en statussen de betreffende editie kan bewaren.

**Beperking:** Geen bestaande koppeling met Wetsanalyse AI aangetoond. Een suiteaanschaf draagt niet rechtstreeks bij aan activiteit 2.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-94). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H087](https://www.sdl.com/software-and-services/translation-software/sdl-trados-studio/), [H087B](https://www.trados.com/product/studio/). Vindplaats: Vertaalgeheugens / SDL Trados Studio.

### H088 STAR TermStar

**Oordeel:** Duplicaat van H064. **Functie:** Terminologie voor schrijven en vertalen beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig; Nederlands niet functioneel getest |
| Omgeving en uitwisseling | STAR TermStar; productpagina gelezen |
| Licentie of toegang | Commercieel; editievoorwaarden niet vastgesteld |

**Betekenis voor Wetsanalyse:** Dit is de bruikbare productbron voor de twee TermStar-vermeldingen. Voorkeurstermen zijn inzetbaar bij eigen uitleg, met behoud van bronformuleringen.

**Beperking:** De plaatsing onder vertaalgeheugens maakt TermStar nog geen zelfstandig vertaalgeheugen. Productrol en rubriek zijn afzonderlijk beoordeeld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-95). Bronnen: [H088](https://www.star-group.net/en/products/terminology-management.html). Vindplaats: TermStar / Terminology management.

### H089 STAR Transit NXT

**Oordeel:** Later. **Functie:** Vertaalgeheugen voor lokalisatie.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalig aanbod; Nederlands niet getest |
| Omgeving en uitwisseling | STAR Transit; hergebruik van vertaalde segmenten |
| Licentie of toegang | Commercieel; voorwaarden niet onderzocht |

**Betekenis voor Wetsanalyse:** Vergelijk het hergebruikmechanisme met begripshergebruik: beide vragen zichtbaarheid van de oorspronkelijke context en eerdere beoordeling.

**Beperking:** Een vertaalmatch valideert geen juridische betekenis; het product biedt voor de huidige eentalige analyse geen noodzakelijke aanvulling.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-96). Bronnen: [H089](https://www.star-group.net/en/products/translation-localization.html). Vindplaats: Transit / Translation and localization.

### H090 WebWordSystem

**Oordeel:** Later. **Functie:** Vertaalgeheugen vanuit Office gebruiken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse ondersteuning niet bevestigd |
| Omgeving en uitwisseling | WebWordSystem; Word, Excel en PowerPoint-integratie |
| Licentie of toegang | Commercieel aanbod |

**Betekenis voor Wetsanalyse:** Een beperkte, contextuele hulpfunctie in de bestaande werkplek kan bruikbaarder zijn dan een extra volledige applicatie.

**Beperking:** De concrete koppeling met bronankers, JAS en betekenisgroepen ontbreekt in de gelezen productbeschrijving.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-97). Bronnen: [H090](https://www.webwordsystem.com/en/home.aspx). Vindplaats: Homepage / Office integration.

### H091 Wordfast Classic

**Oordeel:** Later. **Functie:** Vertaalgeheugen binnen Word gebruiken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Taalgeschiktheid apart toetsen |
| Omgeving en uitwisseling | Wordfast Classic; Word-integratie; woordenboeken en macros |
| Licentie of toegang | Commerciële distributie; systeemvereisten verifiëren |

**Betekenis voor Wetsanalyse:** Contextuele suggesties tijdens schrijven zijn bruikbaar voor eigen documenten, mits analisten naar het volledige begrip kunnen navigeren.

**Beperking:** De makerspagina bevat brede compatibiliteitsclaims. Deze zijn niet getest; geen inzetadvies voor de huidige Linux-webarchitectuur.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-98). Bronnen: [H091](https://wordfast.com/products/wordfast_classic). Vindplaats: Wordfast Classic / Benefits; Specifications.

## Vertaalprojectbeheer met geïntegreerde terminologiemodule

### H092 Across Language Server

**Oordeel:** Later. **Functie:** Vertaalprojecten, geheugen en terminologie beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse NLP niet aangetoond |
| Omgeving en uitwisseling | Across Language Server; geïntegreerd terminologiesysteem |
| Licentie of toegang | Commercieel |

**Betekenis voor Wetsanalyse:** Taakverdeling, voortgang en expliciete termenverantwoordelijkheid zijn relevante procespatronen voor menselijke beoordeling.

**Beperking:** De organisatie van vertaalwerk is geen vervanging voor de juridische beslis- en auditlaag van Wetsanalyse.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-100). Bronnen: [H092](https://www.across.net/en/across-language-server). Vindplaats: Across Language Server / productbeschrijving.

### H093 GlobalLink

**Oordeel:** Later. **Functie:** Meertalige contentprocessen organiseren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet voor Nederlandse juridische analyse aangetoond |
| Omgeving en uitwisseling | GlobalLink-platform; huidige pagina beschrijft AI- en workflowintegratie |
| Licentie of toegang | Commercieel; modules niet afzonderlijk onderzocht |

**Betekenis voor Wetsanalyse:** Een configureerbare werkverdeling kan als procesvoorbeeld dienen. Houd bronophaling, voorstel en menselijke beslissing afzonderlijk traceerbaar.

**Beperking:** De oude INT-modulelijst is niet als actuele productspecificatie overgenomen. Marketingcijfers zijn niet onafhankelijk gevalideerd.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-101). Bronnen: [H093](https://globallink.translations.com/products#all-products). Vindplaats: The Language Intelligence Platform.

### H094 MultiTrans

**Oordeel:** Later. **Functie:** Vertaalbeheer inclusief terminologie.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | MultiTrans; productpagina beperkt toegankelijk |
| Licentie of toegang | Actuele editie/licentie onbekend |

**Betekenis voor Wetsanalyse:** Terminologie in een grotere werkstroom vraagt expliciete eigenaarschap- en synchronisatieregels.

**Beperking:** De huidige openbare pagina kon niet inhoudelijk worden gelezen. Niet afleiden dat een specifieke TermBase-module nog hetzelfde contract heeft.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-102). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H094](https://www.trados.com/product/multitrans/). Vindplaats: Vertaalprojectbeheer / MultiTrans.

### H095 Star Corporate Language Management

**Oordeel:** Later. **Functie:** Bedrijfsbrede taalprocessen organiseren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet afzonderlijk bevestigd |
| Omgeving en uitwisseling | STAR CLM; geconfigureerde processen met menselijke taken |
| Licentie of toegang | Commercieel aanbod |

**Betekenis voor Wetsanalyse:** Het toewijzen van uitzonderingen aan deskundigen past bij de bestaande gerichte review. Registratie van een besluit is belangrijker dan automatisering van iedere stap.

**Beperking:** De beschreven processen richten zich op vertaling en taalbeheer; juridische volledigheid en geldigheid blijven buiten de aangetoonde functies.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-103). Bronnen: [H095](https://www.star-group.net/en/products/corporate-language-management.html?sKey=Y29ycG9yYXRlIGxhbmd1YWdl). Vindplaats: STAR CLM / Manage language processes.

### H096 Wordbee

**Oordeel:** Later. **Functie:** Lokalisatiewerk en teamprocessen beheren.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet afzonderlijk bevestigd |
| Omgeving en uitwisseling | Wordbee; workflow, opdrachten en kwaliteitscontrole |
| Licentie of toegang | Commercieel platform |

**Betekenis voor Wetsanalyse:** Rolgebonden taken en statusoverzichten zijn bruikbare procesvoorbeelden voor een groeiend analistenteam.

**Beperking:** Vertaalproductiviteit en facturatie dragen niet rechtstreeks bij aan activiteit 2/3. Geen specifieke juridische begripsfunctionaliteit aangetoond.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-104). Bronnen: [H096](https://www.wordbee.com/). Vindplaats: Homepage / platform en workflow.

### H097 XTM Cloud Translation Management System

**Oordeel:** Later. **Functie:** Lokalisatie en taalbeheer samenbrengen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Meertalige platformclaim; Nederlandse juridische kwaliteit onbekend |
| Omgeving en uitwisseling | XTM; oude domein verwijst naar xtm.ai |
| Licentie of toegang | Commercieel platform |

**Betekenis voor Wetsanalyse:** Het expliciet kiezen van losse functies is een bruikbaar afwegingsprincipe: voeg alleen toe wat aantoonbaar de analyse ondersteunt.

**Beperking:** De brede huidige suite en marketingclaims bewijzen geen geschiktheid voor brongetrouwe wetsanalyse.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-105). Bronnen: [H097](https://xtm.cloud/). Vindplaats: Homepage / composable platform.

## Zoekapplicaties

### H098 BabelNet

**Oordeel:** Contextbron voor experiment. **Functie:** Meertalige lexicale concepten via API doorzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlands per record/API te verifiëren |
| Omgeving en uitwisseling | BabelNet; Java, Python en HTTP-API; offline data |
| Licentie of toegang | Niet-commerciële onderzoeksvoorwaarden voor bepaalde downloads; licentie per gebruik toetsen |

**Betekenis voor Wetsanalyse:** Kan zoekuitbreiding en alternatieve betekenissen leveren. Koppel externe lexicale concepten als hypotheses met eigen bron, nooit als juridische identiteit.

**Beperking:** Toegang en hergebruik verschillen per product en gebruik. Geen offline index gedownload en geen algemene geschiktheid voor overheidsproductie vastgesteld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-107). Bronnen: [H098](https://babelnet.org/download), [H098B](https://babelnet.org/license). Vindplaats: Downloads; License.

### H099 IntelliWebSearch

**Oordeel:** Ontwerpvoorbeeld. **Functie:** Meerdere bronnen met één zoekactie benaderen.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | IntelliWebSearch; registratiepagina geeft HTTP 999 |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Federatief zoeken kan bronnenonderzoek versnellen. Bewaar per antwoord de werkelijke vindplaats en onderscheid zoekresultaat van bewijs.

**Beperking:** Actuele werking en ondersteunde databanken zijn niet bevestigd. Geen geautomatiseerde productiezoekroute op basis hiervan adviseren.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-108). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H099](https://www.intelliwebsearch.com/version-5/register/), [H099B](https://www.intelliwebsearch.com/). Vindplaats: Zoekapplicaties / IntelliWebSearch.

### H100 Lexicool

**Oordeel:** Contextbron. **Functie:** Woordenboeken en glossaria per taal vinden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Nederlandse taalparen aanwezig |
| Omgeving en uitwisseling | Lexicool webdirectory |
| Licentie of toegang | Publiek raadpleegbaar; afzonderlijke bronnen hebben eigen voorwaarden |

**Betekenis voor Wetsanalyse:** Bruikbaar voor het vinden van specialistische bronnen bij een onduidelijke term. Beoordeel daarna de geselecteerde oorspronkelijke bron zelf.

**Beperking:** Een directory selecteert bronnen maar valideert hun juridische gezag of actualiteit niet.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-109). Bronnen: [H100](https://www.lexicool.com/). Vindplaats: Homepage / Dictionaries and translation.

### H101 Tb-Scout v.3.0

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Terminologiegegevens op meerdere niveaus doorzoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Tb-Scout; oude winkelpagina geeft 404 |
| Licentie of toegang | Niet vastgesteld |

**Betekenis voor Wetsanalyse:** Zoeken op concept-, taal- en termvelden is relevant voor de begrippenwerkplek, bijvoorbeeld alle onbesliste termen bij beoordeelde begrippen vinden.

**Beperking:** Actuele software, veldondersteuning en licentie zijn niet geverifieerd. De conceptuele les komt uitsluitend uit de INT-beschrijving.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-110). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H101](https://tbscout30.translationist.com/de/store.html). Vindplaats: Zoekapplicaties / Tb-Scout.

### H102 Term-minator

**Oordeel:** Historisch ontwerpvoorbeeld. **Functie:** Gericht op terminologiebronnen zoeken.

| Aspect | Bevinding |
|---|---|
| Nederlands | Niet onafhankelijk bevestigd |
| Omgeving en uitwisseling | Historische Term-minator-webzoeker |
| Licentie of toegang | Actuele dienstvoorwaarden onbekend |

**Betekenis voor Wetsanalyse:** Expliciete zoekprofielen per bronsoort kunnen Lex helpen een betekenisvraag gericht te onderzoeken.

**Beperking:** De oorspronkelijke host heeft een certificaatprobleem. De huidige dienst is niet vastgesteld en mag niet met gelijknamige medische leertools worden verwisseld.

[INT-vermelding](https://ivdnt.org/terminologie/hulpmiddelen/#child-111). Bronnen: [INT08](https://ivdnt.org/terminologie/hulpmiddelen/), [H102](https://www.term-minator.it/index.html). Vindplaats: Zoekapplicaties / Term-minator.

## Aanvulling buiten de hulpmiddelenlijst

### H103 TermWerk

**Oordeel:** Proefkandidaat activiteit 2 en 3. **Functie:** Corpusonderzoek, termextractie en termbeheer verbinden.

| Aspect | Bevinding |
|---|---|
| Nederlands | Specifiek Nederlands voor corpus en extractie |
| Omgeving en uitwisseling | TermWerk-webapp; concept/taal/term; TBX v3 met Core, Min en Basic |
| Licentie of toegang | Homepage en handleiding verschillen in omschrijving van toegestaan gebruik; voor inzet vaststellen |

**Betekenis voor Wetsanalyse:** Vergelijk de volledige gang van voorkomens naar kandidaten en begripsfiches. Test contextbehoud, afzonderlijke statusvelden en behoud van relaties bij uitwisseling.

**Beperking:** Aanvulling uit INT buiten de 102 toolrijen. Geen account gebruikt. TBX-export bevat ook ongeconsolideerde termen; sommige gegevens worden notes en kunnen elders betekenis verliezen.

[INT-vermelding](https://ivdnt.org/actueel/nieuws/terminologietool-termwerk/). Bronnen: [INT15](https://ivdnt.org/actueel/nieuws/terminologietool-termwerk/), [INT16](https://termwerk.ivdnt.org/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf). Vindplaats: Handleiding versie 01/10/2025, pp. 1, 17–24.
