# Verdieping van terminologische hulpmiddelen voor Wetsanalyse

De [catalogus](hulpmiddelen.md) behandelt alle 102 vermeldingen van de INT-hulpmiddelenpagina en aanvullend TermWerk. Hieronder staan de toepassingen die de meest concrete vergelijkingsvragen opleveren voor activiteit 2 en 3. Producteigenschappen komen uit de aangehaalde documentatie. De paragrafen *Toepassing op Wetsanalyse* en de proefvragen zijn eigen onderzoeksadviezen.

## Drie verschillende werkzaamheden

Een **corpusinstrument** laat zien waar en hoe een formulering voorkomt. Een **termextractor** selecteert vermoedelijk relevante aanduidingen. Een **terminologiebeheerder** helpt de onderzochte betekenis beschrijven en onderhouden. Een geïntegreerde toepassing kan deze functies combineren; geen van de drie functies bewijst op zichzelf dat een juridische interpretatie klopt.

Voor activiteit 2 is de primaire vraag of het hulpmiddel relevante formuleringen beter vindbaar maakt zonder brongetrouwheid te verliezen. Voor activiteit 3 is de vraag of het vergelijken, afbakenen en beoordelen van betekenissen beter wordt ondersteund. Vergelijk dus de bijdrage aan deze werkzaamheden, niet het aantal functies of het aantal gevonden termen.

## TermWerk

**Aangetroffen documentatie.** Het INT beschrijft een Nederlandstalige omgeving voor corpusonderzoek, extractie en beheer. De handleiding onderscheidt concept-, taal- en termgegevens. Bij TBX-uitvoer worden sommige gegevens in notities ondergebracht; export kan ook ongeconsolideerde termen bevatten. De omschrijving van toegestaan gebruik verschilt tussen homepage en handleiding en vraagt vóór daadwerkelijke inzet verduidelijking. [Homepage](https://termwerk.ivdnt.org/), [handleiding versie 1.0](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), met name het inleidende hoofdstuk en pp. 17–24.

**Toepassing op Wetsanalyse.** Dit is de eerste vergelijkingskandidaat voor de overgang van tekstonderzoek naar begripsbeschrijving. Laat een analist dezelfde geselecteerde passages in een corpusoverzicht en op de beoogde begripskaart vergelijken. Onderzoek of alle dragende kwalificaties behouden blijven wanneer een gevonden term een label krijgt. Een bruikbare kandidaat kan uit meer bestaan dan een naamwoordgroep: ook de normatieve formulering en haar uitzonderingen moeten terugvindbaar blijven.

De belangrijkste proefvraag is wat een overgedragen fiche nog bewijst. Zijn de bronverwijzing, context, relatietypen en verschillende beoordelingen na export en herimport nog te onderscheiden? Een geldig bestand is onvoldoende als de ontvangende toepassing een getypeerde relatie alleen als tekst toont. Deze vraag sluit direct aan op de beoogde export van een benoemde stand in spoor D.

De INT-lijst noemt nog **TermTreffer** met een algemene link. Het onderzoek behandelt die historische vermelding afzonderlijk en gebruikt TermWerk als aanvullende actuele vergelijkingsingang. Er is geen ingelogde werking getest.

## AntConc en TextSTAT

**Aangetroffen documentatie.** AntConc biedt onder meer concordanties, woordlijsten, clusters en corpusvergelijking. TextSTAT biedt een eenvoudiger route naar frequenties en contextregels, met CSV-uitvoer. Beide hebben desktopdistributies. Dit zegt nog niets over juridische analysekracht. [AntConc-handleiding](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf), [TextSTAT](https://neon.niederlandistik.fu-berlin.de/nl/textstat/).

**Toepassing op Wetsanalyse.** Deze instrumenten zijn bruikbaar als onafhankelijke zoekcontrole naast de bestaande annotatieketen. Neem een klein, vastgelegd corpus en onderzoek alle voorkomens van een gekozen formulering. Vergelijk de gevonden passages met de annotatievoorstellen. Een gemist voorkomen vraagt vervolgens een inhoudelijk oordeel: het kan een gemiste annotatie zijn, maar ook terecht buiten de beoogde functie vallen.

Houd twee vragen uit elkaar: werd het woord gevonden en werd zijn juridische functie goed geduid? Beoordeel ook de tekstoverdracht. Extractie uit een PDF kan andere witruimte, afbrekingen of posities opleveren dan de canonieke bronnode. Corpusresultaten moeten daarom eerst met de bewaarde brontekst worden verbonden voordat ze annotaties kunnen ondersteunen.

**Proefvraag:** kan een analist vanuit iedere contextregel de volledige bepaling en relevante verwijzingen terugvinden, inclusief een uitzondering buiten het zichtbare venster?

## Sketch Engine en de overige extractoren

**Aangetroffen documentatie.** Sketch Engine vergelijkt een focuscorpus met een referentiecorpus en onderscheidt keywords en taalkundig geselecteerde termen. TerMine beschrijft een aanpak met woordsoorten en C-value; zijn demo vermeldt ASCII en een bestandslimiet, wat de brede taalclaim in de INT-lijst nuanceert. [Sketch Engine](https://www.sketchengine.eu/guide/keywords-and-term-extraction/), [TerMine](https://www.nactem.ac.uk/software/termine/).

**Toepassing op Wetsanalyse.** Gebruik statistische opvallendheid voor onderzoek naar kandidaten. Zij zegt niet dat een begrip belangrijk, correct gedefinieerd of juridisch goedgekeurd is. Een andere referentieverzameling kan de rangorde veranderen zonder dat de wet verandert. Neem daarom minstens één zeldzame definitie, een verbale norm, een ontkenning en een uitzondering op in de proef.

Voor OneClick Terms, Tilde Terminology en TermoStat was de openbare appinformatie onvoldoende voor een complete functionele beoordeling. De catalogus benoemt per toepassing wat uit INT komt en wat onafhankelijk bevestigd kon worden. Bij een vervolgproef moeten taalconfiguratie, uitvoer en toegang eerst concreet zijn. Een geladen webapp is nog geen werkende Nederlandse extractor.

**Proefvraag:** levert de extractor aanvullende juridisch relevante kandidaten op die de bestaande keten mist, en hoeveel extra beoordeling kost dat? Een lange lijst met algemene woorden is geen verbetering als zij de analist vooral meer werk geeft.

## Terminologue

**Aangetroffen documentatie.** Terminologue is conceptgericht, biedt historie, rollen en bewerkingsstatussen en kan termen tussen fiches delen. De software heeft een MIT-licentie en kan zelf worden gehost; de aangeboden online dienst heeft eigen voorwaarden. [Introductie](https://www.terminologue.org/docs/intro.en/), [software en dienst](https://www.terminologue.org/docs/info.en/).

**Toepassing op Wetsanalyse.** Dit is een goede referentie voor het dagelijkse werk aan een begripskaart: snel context en definitie vergelijken, wijzigingen terugvinden en een onbeslist fiche herkenbaar houden. Het is vooral interessant als toets op gebruiksgemak en review, zonder meteen een tweede systeem in te voeren.

Het delen van termgegevens vraagt extra aandacht bij juridische contexten. Een spellingcorrectie kan gedeeld zijn, terwijl een wijziging in de betekenisomschrijving een andere afweging vraagt. Een bewerkingsstatus hoort evenmin de inhoudelijke goedkeuring van een annotatie of bronkoppeling te vervangen.

**Proefvraag:** kan één term in twee juridische contexten worden onderzocht zonder dat een wijziging in de ene context stilzwijgend een eerder beoordeelde duiding in de andere verandert?

## Coreon en LookUp van D.O.G.

**Aangetroffen documentatie.** Coreon verbindt concepten met meertalige termen en noemt REST, SPARQL en terminologische/RDF-formaten. LookUp van D.O.G. beschrijft begripsrelaties, wijzigingsbeheer, rollen en meerdere uitwisselformaten. [Coreon](https://coreon.com/terminology-management/), [LookUp D.O.G.](https://www.dog-gmbh.de/lookup-produkt/).

**Toepassing op Wetsanalyse.** De nuttigste les is de scheiding tussen betekenis, talige weergave en relaties. Een wijziging van het voorkeurslabel moet een beoordeelde relatie niet ongemerkt veranderen. Een diagram is pas bruikbaar wanneer een analist kan zien wat de lijn betekent, op welke bron die berust en of zij nog een voorstel is.

De beschikbare formaatnamen zijn aanleiding voor een uitwisselproef, geen bewijs voor behoud van de projectgegevens. De eigen bronankers, werkgebieden en beoordelingen moeten expliciet in een mapping terugkomen. Er is geen onderbouwing gevonden om hiervoor een nieuwe centrale gegevensbron naast de bestaande projectarchitectuur in te voeren.

**Proefvraag:** kan de analist twee bijna gelijke begrippen naast elkaar zetten en het onderscheidende kenmerk met bewijs aanwijzen? Het oude **LookUp op lookup-web.de** is een andere vermelding en is niet met het D.O.G.-product samengevoegd.

## Tedi en i-Term met i-Model

**Aangetroffen documentatie.** Tedi scheidt formele conceptbeschrijving van termen in verschillende talen. Het noemt onder meer RDF/OWL, SKOS en TBX als uitvoer. De gelezen licentie is persoonlijk, academisch en niet-commercieel. i-Model beschrijft visuele conceptmodellen met kenmerken en relaties. [Tedi](https://ontoterminology.com/tedi), [licentie](https://ontoterminology.com/licence), [i-Model](https://www.danterm.dk/products/i-model.html).

**Toepassing op Wetsanalyse.** Deze toepassingen helpen de vraag stellen wat een begrip onderscheidt van zijn buren. Een getekende boom dekt echter niet alle juridische relaties. Het verband tussen actor en bevoegdheid heeft bijvoorbeeld een andere betekenis dan een soortverband; het onderdeel van een bron is weer een andere relatie.

Gebruik een kleine handmatig beoordeelde selectie om het onderscheid tussen kenmerken, labels en verbanden zichtbaar te maken. Het doel is scherpere gesprekken over betekenis, niet het automatisch afleiden van een juridisch juiste indeling uit een logisch model.

**Proefvraag:** blijven soort-van, deel-van en juridische rollen apart benoemd wanneer het model wordt weergegeven en geëxporteerd? Een formele controle kan een inconsistentie blootleggen, maar valideert de gebruikte wetsinterpretatie niet.

## Protégé en Synaptica Graphite

**Aangetroffen documentatie.** Protégé biedt een open omgeving voor OWL-ontologieën. Graphite beschrijft redactie en publicatie van begrippenmodellen op basis van RDF. [Protégé](https://protege.stanford.edu/software/), [Graphite](https://www.synaptica.com/synaptica-graphite/).

**Toepassing op Wetsanalyse.** Protégé is bruikbaar voor een beperkte controle van een voorgenomen formele modellering. Begin met de vraag of iets een SKOS-begrip, een formele klasse, een concrete entiteit of een JAS-duiding is. Het zonder onderscheid als klasse modelleren van alle kaartjes kan onbedoelde consequenties introduceren.

Graphite is vooral een procesvoorbeeld voor het scheiden van redactie en beschikbaarstelling. Dat sluit aan op de behoefte aan een herkenbare, beoordeelde begrippenstand. Voor het huidige project volgt daar geen noodzaak uit om de graafopslag te vervangen.

**Proefvraag:** levert een expliciete mapping voorspelbare uitvoer op, met behoud van eigen juridische relaties en reviewgegevens? Technische geldigheid en inhoudelijke aanvaarding moeten afzonderlijk zichtbaar blijven.

## Qterm Anchovy en termXplorer

**Aangetroffen documentatie.** Qterm heeft documentatie voor terminologiebeheer en een beschreven TBX-interface. Anchovy noemt meerdere import- en exportformaten. Het geraadpleegde termXplorer-fiche beschrijft configureerbare gegevens op concept-, taal- en termniveau, maar dateert uit november 2018. [Qterm](https://docs.memoq.com/current/en/memoQWeb-help/mqw-qterm.html), [TBX-interface](https://docs.memoq.com/11-3/api-docs/wsapi/memoqservices/tbservice.importexport.tbx.html), [Anchovy](https://www.maxprograms.com/products/anchovy.html), [termXplorer-fiche](https://term-solutions.com/wp-content/uploads/2020/08/InfoSheet_termXplorer_TermSolutions.pdf).

**Toepassing op Wetsanalyse.** Deze bronnen maken de uitwisselvraag concreter: in welk veld komt welke uitspraak terecht, en begrijpt de ontvangende toepassing dat veld hetzelfde? Een label en een definitie passen vaak eenvoudig in een tabel; de redenen voor een koppeling, het bereik van een begrip en een onafhankelijke beoordeling vragen meer aandacht.

Maak vóór een productvergelijking een klein bestand met één homoniem, twee synoniemen, een brondefinitie, een geformuleerde definitie, een onbesliste relatie en een vervangen begrip. Vergelijk na overdracht per gegeven of het ongewijzigd, tekstueel verplaatst of verdwenen is. Het gebruik van TBX vraagt bovendien een expliciete keuze van versie en dialect. [TBX-dialecten](https://www.tbxinfo.net/tbx-dialects/).

**Proefvraag:** kan de oorspronkelijke betekenis van ieder relevant veld worden gereconstrueerd? Historische productspecificaties bieden ontwerpvoorbeelden, maar geen garantie voor actuele levering of compatibiliteit.

## Quickterm TermWeb en schrijfondersteuning

**Aangetroffen documentatie.** Quickterm beschrijft samenwerking en configureerbare validatie. De deels toegankelijke TermWeb-handleiding behandelt workflow en rollen. TippyTerm en TermStar richten zich mede op consequent termgebruik tijdens schrijven en vertalen. [Quickterm](https://kaleidoscope.at/en/products/quickterm/), [TermWeb-handleiding](https://www.interverbumtech.com/wp-content/uploads/2021/04/TermWeb-4-User-Administrator-Guide-v1.7.pdf), [TippyTerm](https://www.tippyterm.de/tippyterm/anwendung/), [TermStar](https://www.star-group.net/en/products/terminology-management.html).

**Toepassing op Wetsanalyse.** De procesles is nuttig: een voorstel, inhoudelijke bespreking, juridische beoordeling en publicatie zijn verschillende gebeurtenissen. De bestaande auditlaag is de plek waar die beslissingen moeten blijven samenkomen. Vermijd een algemeen vinkje dat verschillende beoordelingen onzichtbaar samenneemt.

Schrijfondersteuning kan eigen toelichtingen en analysedefinities consistenter maken. In de bronweergave moet juist de werkelijk aangetroffen formulering blijven staan. Een verouderde of ongewenste term in een wet is nog steeds bewijs van wat die bron zegt.

**Proefvraag:** blijft de gebruiker zien of een melding over stijl, termvoorkeur, ontbrekende metadata of juridische inhoud gaat? Een schrijfcontrole hoort geen broncitaat te wijzigen.

## Zoekbronnen vertaalmiddelen en overige vermeldingen

IATE, EuroVoc, Rechtspraak en lexicale zoekdiensten hebben verschillende rollen. Zij kunnen een betekenisvraag helpen verkennen, een extern begrippenkader ontsluiten of uitleg bieden. De gekozen rechtsbron en toepassingscontext blijven bepalend voor de analyse. Leg een externe koppeling daarom als afzonderlijke hypothese vast. [IATE](https://iate.europa.eu/home), [EuroVoc](https://op.europa.eu/en/web/eu-vocabularies/th-dataset/-/resource/dataset/eurovoc), [Rechtspraak](https://www.rechtspraak.nl/juridische-begrippen).

Alignering en vertaalgeheugens zijn pas rechtstreeks nuttig wanneer vertalingen of meertalige bronvergelijking onderdeel van de analysevraag worden. Hun onderscheid tussen documenten, segmenten, termen en vertaalvoorstellen is wel leerzaam. Een goed uitgelijnd segmentpaar levert nog geen oordeel over juridische equivalentie. [Hunalign](https://github.com/danielvarga/hunalign), [SynchroTerm](https://www.terminotix.com/index.asp?name=SynchroTerm&content=item&brand=4&item=7&lang=en).

Voor alle overige tools bevat de [catalogus](hulpmiddelen.md) een eigen beoordeling. Verouderde of ontoegankelijke verwijzingen zijn behouden met hun beperking, zodat duidelijk blijft wat wel en niet vastgesteld is. De catalogus doet geen aanschaf- of installatieadvies op basis van alleen een oude INT-omschrijving.

## Vergelijkingsproef voor activiteit 2 en 3

Dit is een **voorgestelde vervolgproef**, geen uitgevoerde meting of extra bouwplanning. Sluit aan bij de bestaande [empirische validatie](../../architectuur/onderzoek-empirische-validatie.md) en de proefset van spoor D. Gebruik een kleine vaste selectie openbare Nederlandse wetsbronnen, met bronstand, selectiecriteria en door juristen beoordeelde gevallen.

1. **Leg de bronselectie vast.** Neem volledige bepalingen en noodzakelijke contextbronnen op. Bewaar de canonieke tekst en bronankers.
2. **Maak een vergelijkingsbasis.** Gebruik bestaande activiteit-2-uitvoer en beoordeel daarnaast passages die nog geen voorstel opleverden. Anders blijven gemiste elementen buiten beeld.
3. **Vergelijk corpusfuncties.** Onderzoek dezelfde formuleringen met AntConc of TextSTAT; registreer configuratie en terugvindbaarheid.
4. **Vergelijk termkandidaten.** Gebruik TermWerk en eventueel een tweede extractor, nadat toegang en gebruiksvoorwaarden zijn vastgesteld. Neem zowel geaccepteerde als afgewezen kandidaten op.
5. **Beoordeel begripsvorming.** Laat juristen betekenisgroepen, definities en koppelingen afzonderlijk beoordelen. Vergelijk foutieve samenvoeging en onnodige splitsing.
6. **Onderzoek gegevensoverdracht.** Vergelijk een klein beoordeeld gegevenspakket vóór en na export/import. Noteer per veld behoud, verandering of verlies.
7. **Beoordeel de netto bijdrage.** Rapporteer kwaliteit én beoordelingswerk. Maak pas daarna een keuze voor een functie of toepassing.

| Geval | Verwacht gedrag |
|---|---|
| Eén woordvorm met twee juridische betekenissen | Twee begrippen of een zichtbaar onbeslist betekenisconflict |
| Twee formuleringen voor dezelfde betekenis | Gemotiveerde kandidaatkoppeling; menselijke beslissing |
| Twee elementen met dezelfde JAS-klasse | Geen samenvoeging op klasse alleen |
| Definitie buiten de eerste bronselectie | Verwijzing en uitbreidingsvoorstel; ontbrekende context zichtbaar |
| Eenmalige wettelijke definitie | Niet uitgesloten wegens lage frequentie |
| Ontkenning of uitzondering buiten het KWIC-venster | Volledige context beschikbaar en invloed beoordeeld |
| Brondefinitie naast eigen uitleg | Herkomst en functie van beide teksten onderscheiden |
| Gelijke Nederlandse termen uit twee rechtsstelsels | Equivalentie afzonderlijk onderzocht |
| Beoordeeld begrip met onbeoordeelde bronkoppeling | Geen impliciete goedkeuring van de koppeling |
| Wijziging in een dragende bronpassage | Gerichte herbeoordeling met behoud van eerdere bewijsstand |
| Getypeerde relatie na export | Type en betekenis behouden of gegevensverlies expliciet gemeld |
| Export met onbesliste records | Status behouden en afzonderlijk publicatiebeleid toegepast |

Meet bij activiteit 2 het aandeel gevonden relevante voorkomens en het aantal onterechte kandidaten, uitgesplitst naar juridische functie. Meet bij activiteit 3 foutieve samenvoegingen, onnodige splitsingen, niet-onderbouwde definitiekenmerken en ontbrekende context. Registreer ook benodigde correcties en beoordelingstijd. Deze maten leveren verschillende inzichten; vat ze niet samen als één algemene score voor juridische kwaliteit.

Een toepassing verdient pas een volgende stap als zij op de gekozen gevallen een aantoonbaar nuttige bijdrage levert zonder brongetrouwheid of beoordelingsstatus te verliezen. De huidige documentatieverkenning bepaalt welke vragen daarvoor nodig zijn, niet welk product die proef al heeft gewonnen.
