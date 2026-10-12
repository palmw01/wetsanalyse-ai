# Begrippen uit het terminologieonderzoek

Deze 66 werkdefinities zijn een eigen synthese van het INT-materiaal, geselecteerde primaire bronnen en de methode Wetsanalyse. Ze vormen een begrippeninventaris voor onderzoek en projectadvies; het zijn geen wettelijke definities en geen geïmporteerde begrippenbank. De voorbeelden zijn illustratief. *Projectstatus* vergelijkt met de geraadpleegde projectdocumentatie op 8 oktober 2026.

De volledige inventaris staat ook in [CSV](concepten.csv). Bron-ID’s verwijzen naar het [bronnenregister](bronnen.json); de links hieronder openen de onderliggende bron. Beschermde lokale methodebronnen zijn alleen beschikbaar waar ze rechtmatig aanwezig zijn.

## Betekenis en aanduiding

### C001 Begrip

Een afgebakende betekenis binnen een bepaald kennisdomein.

- Activiteit 2: Een JAS-label identificeert nog geen domeinbegrip.
- Activiteit 3: Leg identiteit, definitie en toepassingscontext afzonderlijk vast.
- Voorbeeld: Twee passages kunnen hetzelfde begrip aanduiden.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Gebruik stabiele begripsidentiteiten naast annotatie-identiteiten.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [P01](../../../docs/PLAN.md). Vindplaats: Wat is terminologie; NL-SBB §2.3; spoor D / Elementen groepen en begrippen.

### C002 Term

Een talige aanduiding van een begrip.

- Activiteit 2: Bewaar de aangetroffen formulering.
- Activiteit 3: Verbind alternatieve aanduidingen met een beoordeeld begrip.
- Voorbeeld: Een afkorting en uitgeschreven naam kunnen hetzelfde aanduiden.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Maak termtekst niet tot de unieke sleutel van een begrip.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [E10](https://www.cotsoes.org/sites/default/files/public_files/CEOV_Aanbevelingen_voor_terminologie.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Terminologische gegevens; spoor D / Begripskaart.

### C003 Voorkomen en tekstanker

Een concrete verschijning van tekst op een vastgelegde bronstand.

- Activiteit 2: Bewaar exacte tekst, positie en bronnode.
- Activiteit 3: Onderbouw elke duiding met terugvindbare voorkomens.
- Voorbeeld: Hetzelfde woord op twee plaatsen levert twee ankers op.
- Projectstatus: Bestaand activiteit 2; koppeling voorzien.
- Advies: Behoud de oorspronkelijke passage naast genormaliseerde zoekvormen.

Bronnen: [P03](../../../docs/architectuur/annotatieketen.md), [P01](../../../docs/PLAN.md). Vindplaats: Annotatieketen; spoor D / Begripskoppeling.

### C004 Conceptgerichte beschrijving

Een beschrijving waarin betekenis de termen groepeert.

- Activiteit 2: Termherkenning levert materiaal voor betekenisvergelijking.
- Activiteit 3: Orden de begrippenkaart rond betekenis en context.
- Voorbeeld: Twee synoniemen staan op één kaart na beoordeling.
- Projectstatus: Reeds voorzien; terminologische onderbouwing.
- Advies: Gebruik conceptgerichte fiches als vergelijkingsmodel voor de werkplek.

Bronnen: [H063B](https://www.terminologue.org/docs/intro.en/), [H074](https://coreon.com/terminology-management/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf). Vindplaats: Terminologue entries; Coreon concepten; TermWerk Conceptniveau.

### C005 Woordgerichte beschrijving

Een beschrijving waarin een woord toegang geeft tot meerdere betekenissen.

- Activiteit 2: Zoeken op een woord toont uiteenlopende contexten.
- Activiteit 3: Laat de analist mogelijke betekenissen vergelijken.
- Voorbeeld: Eén zoekterm toont twee verschillende begripskaarten.
- Projectstatus: Aanvullende zoekfunctie.
- Advies: Gebruik woordgerichte toegang zonder betekenissen samen te voegen.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [INT07](https://ivdnt.org/terminologie/historische-termenlijsten/). Vindplaats: Terminologie en lexicografie; historische termenlijsten.

### C006 Vakgebied en werkgebied

De inhoudelijke afbakening waarbinnen betekenis wordt onderzocht.

- Activiteit 2: Bepaal welke bronnen en passages worden betrokken.
- Activiteit 3: Verbind begrippen met analysevraag en afbakening.
- Voorbeeld: Een financieel en een medisch werkgebied gebruiken hetzelfde woord anders.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Neem corpusselectie en analysecontext zichtbaar op.

Bronnen: [E02](https://termnet.eu/wp-content/uploads/2018/03/5-Steps-Action-Plan_Terminology-with-Ease-1.pdf), [P01](../../../docs/PLAN.md). Vindplaats: TermNet / requirements; spoor D / Werkgebied als node.

### C007 Rechtsstelsel en toepassingscontext

De juridische omgeving die mede bepaalt wat een aanduiding betekent.

- Activiteit 2: Toon regeling, verwijzingen en relevante context.
- Activiteit 3: Toets begripsidentiteit binnen de juiste juridische omgeving.
- Voorbeeld: Een Nederlandse en Vlaamse term zijn niet door taal alleen equivalent.
- Projectstatus: Reeds voorzien; nader preciseren.
- Advies: Leg rechtsstelsel expliciet vast wanneer bronnen worden gecombineerd.

Bronnen: [INT12](https://ivdnt.org/terminologie/juriterm-nl-vl/), [INT13](https://ivdnt.org/terminologie/onderwijsterminologie-hotnev/), [P01](../../../docs/PLAN.md). Vindplaats: JuriTerm; HOTNeV; spoor D / Methodische uitgangspunten.

### C008 Geldigheid en bronstand

Het onderscheid tussen toepasselijke tijd en technisch vastgelegde tekstversie.

- Activiteit 2: Annoteer de geselecteerde bronstand.
- Activiteit 3: Beoordeel begripsduiding voor de bedoelde periode.
- Voorbeeld: Een nieuw snapshot kan dezelfde dragende tekst bevatten.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Beoordeel inhoudelijke verschillen voordat herbeoordeling wordt vereist.

Bronnen: [P01](../../../docs/PLAN.md), [P03](../../../docs/architectuur/annotatieketen.md). Vindplaats: Spoor D / Bronselectie en actualiteit; annotatieketen.

### C009 Synonymie

Meerdere aanduidingen voor dezelfde betekenis binnen een context.

- Activiteit 2: Vind alternatieve formuleringen.
- Activiteit 3: Stel samenvoeging voor met bronvergelijking.
- Voorbeeld: Afkorting en volledige naam kunnen synoniem zijn.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Beschouw gelijkenis als zoekaanwijzing; de analist beslist.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [E10](https://www.cotsoes.org/sites/default/files/public_files/CEOV_Aanbevelingen_voor_terminologie.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Terminologische gegevens; spoor D / Verwerking.

### C010 Homonymie en polysemie

Eenzelfde vorm kan verschillende, al dan niet verwante betekenissen hebben.

- Activiteit 2: Toon uiteenlopende gebruikscontexten.
- Activiteit 3: Splits betekenisgroepen waar de context dat vereist.
- Voorbeeld: Dezelfde term in twee regelingen kan twee begrippen opleveren.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Laat tekstgelijkheid nooit automatisch tot één begrip leiden.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [M01](../../../docs/wetsanalyse/wetsanalyse-boek.md), [P01](../../../docs/PLAN.md). Vindplaats: Wat is terminologie; boek h3 en h6; spoor D.

### C011 Termvariant en afkorting

Een andere vorm van een aanduiding met te onderzoeken betekenisrelatie.

- Activiteit 2: Vergroot terugvindbaarheid met varianten.
- Activiteit 3: Bewaar soort variant en context van gebruik.
- Voorbeeld: Een afkorting zonder lokale uitleg blijft dubbelzinnig.
- Projectstatus: Voorzien als alternatieve termen; aanscherping.
- Advies: Scheid spellingvariant, afkorting en inhoudelijk andere formulering.

Bronnen: [H038](https://www.nactem.ac.uk/software/termine/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [P01](../../../docs/PLAN.md). Vindplaats: TerMine acronyms; TermWerk Termniveau; Begripskaart.

### C012 Voorkeursterm en toegestane term

Een redactionele keuze voor het gebruik van een aanduiding.

- Activiteit 2: Wijzig geen letterlijke bronformuleringen.
- Activiteit 3: Maak eigen definities en uitleg consistent.
- Voorbeeld: Een verouderde bronterm blijft zichtbaar naast het gekozen label.
- Projectstatus: Nieuwe explicitering bij spoor D.
- Advies: Beperk schrijfadviezen tot eigen teksten; bewaar historische termen.

Bronnen: [H068](https://www.tippyterm.de/tippyterm/anwendung/), [H088](https://www.star-group.net/en/products/terminology-management.html), [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/). Vindplaats: TippyTerm; TermStar; NL-SBB §2.4.1.1.

### C013 Equivalentie tussen talen of stelsels

Een onderbouwde overeenkomst tussen begrippen uit verschillende contexten.

- Activiteit 2: Verzamel gekoppelde passages als vergelijkingsmateriaal.
- Activiteit 3: Registreer volledige, gedeeltelijke of ontbrekende overeenkomst.
- Voorbeeld: Een vertaalpaar kan een relevante juridische nuance verliezen.
- Projectstatus: Aanvullende kwaliteitsregel; meertaligheid later.
- Advies: Bewaar mappingbeslissingen en hun beperkingen afzonderlijk.

Bronnen: [INT12](https://ivdnt.org/terminologie/juriterm-nl-vl/), [INT13](https://ivdnt.org/terminologie/onderwijsterminologie-hotnev/), [E09](https://www.cotsoes.org/sites/default/files/public_files/KUEDES_Empfehlungen_fuer_die_Terminologiearbeit_Bern_2018.pdf). Vindplaats: JuriTerm; HOTNeV; aanbevelingen / equivalence.

## Definities en afbakening

### C014 Kenmerk

Een eigenschap die helpt een begrip te beschrijven of onderscheiden.

- Activiteit 2: Markeer kwalificerende formuleringen.
- Activiteit 3: Bepaal welke kenmerken betekenisdragend zijn.
- Voorbeeld: Een leeftijdsgrens kan de beschreven groep afbakenen.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Scheid definitiekenmerken van toevallige eigenschappen van voorbeelden.

Bronnen: [E09](https://www.cotsoes.org/sites/default/files/public_files/KUEDES_Empfehlungen_fuer_die_Terminologiearbeit_Bern_2018.pdf), [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Begriffe und Merkmale; handleiding §3.5; Begripskaart.

### C015 Intensie en extensie

De bepalende kenmerken tegenover de gevallen die eronder vallen.

- Activiteit 2: Verzamel formuleringen én toepassingsgevallen.
- Activiteit 3: Toets of definitie en voorbeelden dezelfde afbakening geven.
- Voorbeeld: Een te ruime definitie laat een bedoeld tegenvoorbeeld toe.
- Projectstatus: Aanvullende kwaliteitslens.
- Advies: Gebruik voorbeelden om de beoogde begripsomvang te toetsen.

Bronnen: [E09](https://www.cotsoes.org/sites/default/files/public_files/KUEDES_Empfehlungen_fuer_die_Terminologiearbeit_Bern_2018.pdf), [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf). Vindplaats: Begriffe und Definitionen; NL-SBB §2.3; handleiding §3.5.

### C016 Intensionele definitie

Een afbakening door een algemener begrip en onderscheidende kenmerken.

- Activiteit 2: Vind relevante kwalificaties in de bron.
- Activiteit 3: Formuleer een compacte controleerbare definitie.
- Voorbeeld: Een subtype wordt door een extra kenmerk onderscheiden.
- Projectstatus: Reeds voorzien; nader preciseren.
- Advies: Gebruik dit als hulpmiddel waar passend, niet als star sjabloon voor iedere norm.

Bronnen: [E10](https://www.cotsoes.org/sites/default/files/public_files/CEOV_Aanbevelingen_voor_terminologie.pdf), [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/). Vindplaats: Aanbevelingen / definitie; NL-SBB §5.1.1.

### C017 Extensionele definitie

Een afbakening door de gevallen of deelbegrippen op te sommen.

- Activiteit 2: Behoud opsommingen en verbindingswoorden.
- Activiteit 3: Controleer of de opsomming uitputtend of illustratief is.
- Voorbeeld: Het woord waaronder kan een andere reikwijdte hebben dan uitsluitend.
- Projectstatus: Aanvullende kwaliteitsregel.
- Advies: Neem de status van de opsomming mee in de onderbouwing.

Bronnen: [E09](https://www.cotsoes.org/sites/default/files/public_files/KUEDES_Empfehlungen_fuer_die_Terminologiearbeit_Bern_2018.pdf), [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf). Vindplaats: Definitionsarten; handleiding §3.5.

### C018 Brondefinitie

Een definitiebepaling zoals die in de onderzochte bron staat.

- Activiteit 2: Herken en annoteer de bronformulering.
- Activiteit 3: Bewaar de letterlijke definitie naast de analyse.
- Voorbeeld: Een brondefinitie met lokaal bereik mag niet algemeen worden gemaakt.
- Projectstatus: Bestaand activiteit 2; uitwerking voorzien.
- Advies: Neem bronbereik en toepassingscontext over in de vergelijking.

Bronnen: [M04](../../../docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md), [P01](../../../docs/PLAN.md). Vindplaats: JAS / Brondefinitie; spoor D / Methodische uitgangspunten.

### C019 Analysedefinitie en toelichting

Een geformuleerde betekenisafbakening met afzonderlijke uitleg.

- Activiteit 2: Laat de bronmarkering intact.
- Activiteit 3: Maak zichtbaar wat letterlijk, samengesteld of geïnterpreteerd is.
- Voorbeeld: Een begrijpelijke uitleg is nog geen wettelijke definitie.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Label de herkomst van de definitie en motiveer interpretatiekeuzes.

Bronnen: [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Handleiding §3.5; spoor D / Begripskaart.

### C020 Definitiekwaliteit

De mate waarin een definitie scherp, begrijpelijk en niet circulair afbakent.

- Activiteit 2: Signaleer ontbrekende verwijzingen of context.
- Activiteit 3: Laat circulaire, te brede en te nauwe definities beoordelen.
- Voorbeeld: A verwijst voor zijn betekenis naar B en B alleen naar A.
- Projectstatus: Reeds voorzien; checklist aanscherpen.
- Advies: Gebruik controlesignalen met toelichting, geen automatische inhoudelijke goedkeuring.

Bronnen: [E10](https://www.cotsoes.org/sites/default/files/public_files/CEOV_Aanbevelingen_voor_terminologie.pdf), [E03](https://www.termcat.cat/en/recursos/productes-multimedia/termtest-dictionary-self-assessment-test), [P01](../../../docs/PLAN.md). Vindplaats: Aanbevelingen / definitie; TermTest productbeschrijving; spoor D / Verwerking.

### C021 Voorbeeld en tegenvoorbeeld

Een geval waarmee een voorgestelde begripsgrens wordt getoetst.

- Activiteit 2: Controleer of relevante bronvoorwaarden behouden zijn.
- Activiteit 3: Registreer verwacht oordeel en reden.
- Voorbeeld: Een geval net buiten de grens moet worden uitgesloten.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Neem naast een passend voorbeeld ook grensgevallen op waar nodig.

Bronnen: [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf), [M03](../../../docs/kennisbank/leidraad-voor-wetsanalyse-op-maat-versie-1.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Handleiding §3.5; leidraad Ad 3; Begripskaart.

### C022 Open norm en betekenisconflict

Een begripsgrens die interpretatieruimte of een onbeslist geschil bevat.

- Activiteit 2: Behoud de kwalificerende bronwoorden.
- Activiteit 3: Leg alternatieven en open vragen vast.
- Voorbeeld: Twee redelijke interpretaties blijven zichtbaar naast elkaar.
- Projectstatus: Reeds voorzien; concretiseren in proefset.
- Advies: Forceer geen consensus omdat een termenbank één label verwacht.

Bronnen: [M01](../../../docs/wetsanalyse/wetsanalyse-boek.md), [P01](../../../docs/PLAN.md). Vindplaats: Boek h3; spoor D / accorderen en open vragen.

## Relaties en modellen

### C023 Generieke relatie

Een soortverband waarbij een specifieker begrip onder een algemener valt.

- Activiteit 2: Classificatie kan aanleiding geven tot vergelijking.
- Activiteit 3: Maak de betekenis van het soortverband expliciet.
- Voorbeeld: Subbegrip X heeft de bepalende kenmerken van bovenbegrip Y.
- Projectstatus: Reeds voorzien; relatiekeuze aanscherpen.
- Advies: Verwar een domeintaxonomie niet met JAS-classificatie.

Bronnen: [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [P01](../../../docs/PLAN.md). Vindplaats: NL-SBB §2.4.3.1; spoor D / Projectie.

### C024 Partitieve relatie

Een geheel-deelverband tussen begrippen.

- Activiteit 2: Herken samengestelde objectbeschrijvingen.
- Activiteit 3: Leg deelverbanden apart vast.
- Voorbeeld: Een onderdeel van een document is geen soort document.
- Projectstatus: Aanvullende precisering van relaties.
- Advies: Scheid deel-van en soort-van in beoordeling en uitvoer.

Bronnen: [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [H075B](https://www.danterm.dk/products/i-model.html). Vindplaats: NL-SBB §2.4.3.1; i-Model.

### C025 Associatieve relatie

Een relevant verband zonder generieke of partitieve ordening.

- Activiteit 2: Toon samenhang tussen gemarkeerde elementen.
- Activiteit 3: Benoem het inhoudelijke verband en zijn bron.
- Voorbeeld: Een begrip verwijst naar een verwant proces.
- Projectstatus: Reeds voorzien; nader typeren.
- Advies: Gebruik een algemene relatie alleen waar geen preciezer verband nodig is.

Bronnen: [SKOS](https://www.w3.org/TR/skos-reference/), [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [P01](../../../docs/PLAN.md). Vindplaats: SKOS §8; NL-SBB thesaurus; spoor D / relaties.

### C026 Juridische relatie

Een inhoudelijk juridisch verband met rollen, richting en onderbouwing.

- Activiteit 2: Verbind bijvoorbeeld subject, object en rechtsbetrekking.
- Activiteit 3: Werk relaties uit zonder de betrokken begrippen samen te voegen.
- Voorbeeld: Een actor en een voorwaarde vormen geen synoniemenpaar.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Bewaar juridische predicaten naast algemene terminologische relaties.

Bronnen: [M04](../../../docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md), [P01](../../../docs/PLAN.md). Vindplaats: JAS / Rechtsbetrekking; spoor D / Projectie.

### C027 Begrippenlijst taxonomie thesaurus

Oplopende manieren om begrippen en hun ordening te beschrijven.

- Activiteit 2: Een lijst ondersteunt zoeken en vergelijken.
- Activiteit 3: Kies alleen relaties die de analyse nodig heeft.
- Voorbeeld: Een alfabetische lijst heeft nog geen betekenisvolle hiërarchie.
- Projectstatus: Reeds voorzien via NL-SBB.
- Advies: Begin met onderbouwde fiches; voeg relaties gericht toe.

Bronnen: [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [H056C](https://www.multites.com/products.htm). Vindplaats: NL-SBB §2.4; MultiTes producten.

### C028 Ontologie en axioma

Een formeel model met expliciete typen en samenhangsregels.

- Activiteit 2: JAS-classificatie is input voor interpretatie.
- Activiteit 3: Toets formele consequenties apart van juridische onderbouwing.
- Voorbeeld: Een logisch consistent model kan een onjuiste wetsinterpretatie bevatten.
- Projectstatus: Latere modelcontrole; geen vervanging JAS.
- Advies: Gebruik Protégé of Tedi alleen in een afgebakende modelproef.

Bronnen: [H079B](https://protege.stanford.edu/software), [H058B](https://ontoterminology.com/tedi). Vindplaats: Protégé Software; Tedi / ontoterminology.

### C029 JAS-klasse versus domeinbegrip

Een analysecategorie beschrijft een functie; een domeinbegrip beschrijft betekenis.

- Activiteit 2: Behoud de bestaande JAS-classificatie.
- Activiteit 3: Geef een begrip een duiding zonder het onder een JAS-term te hangen.
- Voorbeeld: Twee rechtssubjecten zijn door hun klasse nog geen synoniemen.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Maak deze scheiding zichtbaar in filters, graaf en export.

Bronnen: [M04](../../../docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md), [P01](../../../docs/PLAN.md). Vindplaats: JAS; spoor D / Elementen en Projectie.

### C030 Mapping tussen begrippenkaders

Een beoordeeld verband tussen zelfstandig beheerde begrippen.

- Activiteit 2: Externe woordenlijsten helpen kandidaten vinden.
- Activiteit 3: Bewaar equivalentie met eigen bewijs en status.
- Voorbeeld: Een IATE-record ondersteunt onderzoek maar wordt geen brondefinitie.
- Projectstatus: Aanvullende kwaliteitsregel.
- Advies: Gebruik exactMatch pas na inhoudelijke toets binnen de beoogde context.

Bronnen: [SKOS](https://www.w3.org/TR/skos-reference/), [H051](https://iate.europa.eu/home), [P01](../../../docs/PLAN.md). Vindplaats: SKOS §10; IATE; spoor D / werkgebieden.

## Corpus en brononderzoek

### C031 Corpus en subcorpus

Een expliciete verzameling teksten met selectiekenmerken.

- Activiteit 2: Maak onderzoek naar formuleringen reproduceerbaar.
- Activiteit 3: Vergelijk gebruik binnen en buiten de afbakening.
- Voorbeeld: Een contextbron kan wel bewijs leveren zonder werkvoorraad te worden.
- Projectstatus: Reeds voorzien als bronselectie.
- Advies: Registreer selectie, rol en bronstand bij iedere extractieproef.

Bronnen: [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf), [P01](../../../docs/PLAN.md). Vindplaats: AntConc corpusfuncties; spoor D / Bronselectie.

### C032 Concordantie en KWIC

Een overzicht van voorkomens met omliggende tekst.

- Activiteit 2: Controleer de spreiding en betekenis van formuleringen.
- Activiteit 3: Vergelijk kandidaatleden vóór groepering.
- Voorbeeld: Een kort contextvenster mist een uitzondering in het volgende lid.
- Projectstatus: Aanvullende werkplekfunctie.
- Advies: Bied altijd toegang tot de volledige bepaling en verwijzingen.

Bronnen: [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf), [H042](https://neon.niederlandistik.fu-berlin.de/nl/textstat/). Vindplaats: AntConc KWIC en File; TextSTAT concordantie.

### C033 Alignering

Een voorgestelde koppeling tussen segmenten van verschillende teksten.

- Activiteit 2: Ondersteun vergelijking van vertalingen of versies.
- Activiteit 3: Onderzoek betekenisovereenkomst op basis van gekoppelde context.
- Voorbeeld: Verplaatste zinnen kunnen een fout segmentpaar opleveren.
- Projectstatus: Latere toepassing.
- Advies: Behandel segmentkoppeling en begripsmapping als twee beslissingen.

Bronnen: [H003B](https://github.com/danielvarga/hunalign), [H036](https://www.terminotix.com/index.asp?name=SynchroTerm&content=item&brand=4&item=7&lang=en). Vindplaats: Hunalign README; SynchroTerm.

### C034 Frequentie

Het aantal voorkomens binnen een gekozen corpus.

- Activiteit 2: Maak terugkerende formuleringen zichtbaar.
- Activiteit 3: Gebruik spreiding als onderzoekshulp.
- Voorbeeld: Een begrip kan juridisch cruciaal zijn en maar eenmaal voorkomen.
- Projectstatus: Aanvullende baseline.
- Advies: Gebruik frequentie voor rangschikking, niet als uitsluitingsgrond.

Bronnen: [H042](https://neon.niederlandistik.fu-berlin.de/nl/textstat/), [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf). Vindplaats: TextSTAT; AntConc Word.

### C035 N-gram cluster en collocatie

Herhaalde woordreeksen of woorden die geregeld samen voorkomen.

- Activiteit 2: Vind meerwoordformuleringen en lokale patronen.
- Activiteit 3: Toets of een combinatie daadwerkelijk een begrip aanduidt.
- Voorbeeld: Een veelvoorkomende frase kan slechts een redactioneel patroon zijn.
- Projectstatus: Aanvullende baseline.
- Advies: Bewaar de oorspronkelijke volgorde en context naast de score.

Bronnen: [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf), [H013](https://lexically.net/wordsmith/). Vindplaats: AntConc Cluster N-Gram Collocate; WordSmith.

### C036 Lemma en normalisatie

Een zoekvorm waarin vormvariatie wordt samengenomen.

- Activiteit 2: Vergroot recall zonder bronankers te wijzigen.
- Activiteit 3: Zoek mogelijke varianten voor beoordeling.
- Voorbeeld: Enkelvoud en meervoud delen een zoekvorm maar behouden eigen passages.
- Projectstatus: Bestaande taalverwerking; begripsfunctie voorzien.
- Advies: Laat normalisatie nooit identiteit of gelijkheid bewijzen.

Bronnen: [P03](../../../docs/architectuur/annotatieketen.md), [P01](../../../docs/PLAN.md), [H035](https://www.sketchengine.eu/guide/keywords-and-term-extraction/#toggle-id-5-closed). Vindplaats: Annotatieketen; spoor D / Verwerking; Sketch Engine guide.

### C037 Woordsoort en taalgrammatica

Een taalkundige indeling waarmee extractiepatronen kunnen worden gevormd.

- Activiteit 2: Ondersteun kandidaatselectie naast juridische detectoren.
- Activiteit 3: Geef taalkundige herkomst van een voorstel weer.
- Voorbeeld: Een nominale extractor mist een verbale normformulering.
- Projectstatus: Bestaande taalprovider; extra proef.
- Advies: Meet ook werkwoorden, operators en kwalificaties buiten naamwoordgroepen.

Bronnen: [H035](https://www.sketchengine.eu/guide/keywords-and-term-extraction/#toggle-id-5-closed), [H038](https://www.nactem.ac.uk/software/termine/), [P03](../../../docs/architectuur/annotatieketen.md). Vindplaats: Sketch Engine requirements; TerMine POS; annotatieketen.

### C038 Referentiecorpus en keyness

Een vergelijking die relatief opvallend taalgebruik zichtbaar maakt.

- Activiteit 2: Vind domeinspecifieke formuleringen.
- Activiteit 3: Onderzoek relevantie zonder statistiek als betekenis te lezen.
- Voorbeeld: Algemene rechtstaal kan verdwijnen tegen een juridisch referentiecorpus.
- Projectstatus: Nieuwe proefdimensie.
- Advies: Vergelijk een algemeen en een juridisch referentiecorpus met gelijke bronselectie.

Bronnen: [H035](https://www.sketchengine.eu/guide/keywords-and-term-extraction/#toggle-id-5-closed), [H039](https://termostat.ling.umontreal.ca/doc_termostat/doc_termostat_en.html), [INT08](https://ivdnt.org/terminologie/hulpmiddelen/). Vindplaats: Sketch Engine guide; TermoStat-vermelding.

## Extractie en AI

### C039 Termkandidaat en termhood

Een vermoedelijke vakterm met nog te beoordelen relevantie.

- Activiteit 2: Voeg een onderzoekssignaal toe naast JAS-voorstellen.
- Activiteit 3: Laat de analist opname of afwijzing motiveren.
- Voorbeeld: Een hoge extractiescore rechtvaardigt nog geen begrip.
- Projectstatus: Reeds voorzien als voorstellen; extra signaal mogelijk.
- Advies: Behoud kandidaatstatus en methodeversie bij overname.

Bronnen: [H038](https://www.nactem.ac.uk/software/termine/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [P01](../../../docs/PLAN.md). Vindplaats: TerMine C-value; TermWerk termextractie; spoor D.

### C040 Stoplijst en uitsluitingsdrempel

Selectieregels die kandidaatresultaten verkleinen.

- Activiteit 2: Maak gemiste zeldzame formuleringen meetbaar.
- Activiteit 3: Voorkom onzichtbare gaten in de begripsinventaris.
- Voorbeeld: Het wegfilteren van niet kan een norm omkeren.
- Projectstatus: Aanvullend kwaliteitscriterium.
- Advies: Controleer expliciet negaties, uitzonderingen en eenmaal voorkomende definities.

Bronnen: [H022B](https://www.laurenceanthony.net/software/antconc/releases/AntConc440/docs/help.pdf), [P03](../../../docs/architectuur/annotatieketen.md), [M04](../../../docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md). Vindplaats: AntConc stoplists; annotatieketen; JAS Operator.

### C041 Entiteitherkenning en entiteitskoppeling

Het herkennen van namen en verbinden daarvan met externe entiteiten.

- Activiteit 2: Kan tekstonderzoek ondersteunen.
- Activiteit 3: Onderscheid concrete entiteit, juridische rol en begrip.
- Voorbeeld: Een persoonsnaam is niet hetzelfde als de rol rechtssubject.
- Projectstatus: Aanvullende afbakening; geen directe integratie.
- Advies: Gebruik externe entiteitslinks als onderzoekshypothese.

Bronnen: [H024](https://dandelion.eu/), [H098](https://babelnet.org/download). Vindplaats: Dandelion Entity Extraction; BabelNet.

### C042 Betekenisonderscheiding

Het kiezen tussen mogelijke betekenissen op basis van context.

- Activiteit 2: Toon ambiguïteit bij dezelfde formulering.
- Activiteit 3: Onderbouw groepstoewijzing met kenmerken en bronnen.
- Voorbeeld: Een overeenkomstige woordvorm krijgt in twee werkgebieden een andere duiding.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Maak alternatieven en onbesliste gevallen zichtbaar.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [P01](../../../docs/PLAN.md). Vindplaats: Wat is terminologie; spoor D / Verwerking.

### C043 Definitie- en relatievoorstel

Een kandidaatbeschrijving afgeleid uit bronpassages.

- Activiteit 2: Herken brondefinities en relevante verwijzingen.
- Activiteit 3: Laat Lex een onderbouwd voorstel doen.
- Voorbeeld: Een model voegt een kenmerk toe dat nergens in de bron staat.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Beoordeel iedere betekenisdragende toevoeging afzonderlijk.

Bronnen: [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Handleiding §3.5; spoor D / API agent en graaf.

### C044 Negatie operator en uitzondering

Elementen die de strekking en reikwijdte van een formulering bepalen.

- Activiteit 2: Behoud hun tekst en JAS-functie.
- Activiteit 3: Controleer hun invloed op de begripsafbakening.
- Voorbeeld: Behalve en uitsluitend veranderen welke gevallen onder een begrip vallen.
- Projectstatus: Bestaand JAS; expliciete extractieproef.
- Advies: Neem deze elementen op in de referentieset voor iedere extractor.

Bronnen: [M04](../../../docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md), [P03](../../../docs/architectuur/annotatieketen.md). Vindplaats: JAS Operator Voorwaarde; annotatieketen.

### C045 Gelijkenis versus identiteit

Een overeenkomst in tekst of vectorruimte is een aanwijzing voor vergelijking.

- Activiteit 2: Vind mogelijk verwante passages.
- Activiteit 3: Laat samenvoeging afhangen van betekenis en context.
- Voorbeeld: Hoge tekstgelijkenis kan samengaan met een tegengestelde uitzondering.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Bewaar de motivatie voor een groep naast de zoekscore.

Bronnen: [P01](../../../docs/PLAN.md), [H024](https://dandelion.eu/). Vindplaats: Spoor D / Verwerking; Dandelion similarity.

### C046 Beoordelingsset en foutanalyse

Vooraf beschreven gevallen waarmee bruikbaarheid wordt getoetst.

- Activiteit 2: Meet gevonden en gemiste juridische elementen.
- Activiteit 3: Meet verkeerde samenvoegingen en splitsingen apart.
- Voorbeeld: Een tool vindt veel termen maar mist alle eenmalige definities.
- Projectstatus: Bestaand validatiekader; uitbreiding voorgesteld.
- Advies: Vergelijk kandidaten op dezelfde bronstand en beoordeelde gevallen.

Bronnen: [P04](../../../docs/architectuur/onderzoek-empirische-validatie.md), [P01](../../../docs/PLAN.md). Vindplaats: Empirische validatie; spoor D / Proefset.

## Beheer en beoordeling

### C047 Concept taal en termniveau

Verschillende niveaus waarop gegevens van een fiche thuishoren.

- Activiteit 2: Herkomst blijft aan de passage verbonden.
- Activiteit 3: Plaats definitie, taalgebonden gegevens en termstatus op het juiste niveau.
- Voorbeeld: Een voorkeursterm kan wijzigen zonder het begrip te veranderen.
- Projectstatus: Nieuwe explicitering binnen bestaande begripskaart.
- Advies: Toets niveaukeuze met TermWerk en termXplorer als voorbeelden.

Bronnen: [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [H067B](https://term-solutions.com/wp-content/uploads/2020/08/InfoSheet_termXplorer_TermSolutions.pdf). Vindplaats: TermWerk beschrijvingsniveaus; termXplorer pp. 1–2.

### C048 Termstatus redactionele status juridische beoordeling

Onafhankelijke uitspraken over taalgebruik, bewerking en inhoudelijke aanvaarding.

- Activiteit 2: Goedkeuring van een term keurt geen annotatie goed.
- Activiteit 3: Bewaar afzonderlijke beslissingen per begrip en koppeling.
- Voorbeeld: Een geredigeerd fiche kan nog juridisch onbeoordeeld zijn.
- Projectstatus: Deels voorzien; statusonderscheid aanscherpen.
- Advies: Maak de statusdimensies expliciet in scherm en export.

Bronnen: [H063B](https://www.terminologue.org/docs/intro.en/), [H067B](https://term-solutions.com/wp-content/uploads/2020/08/InfoSheet_termXplorer_TermSolutions.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Terminologue status; termXplorer; spoor D / accorderen.

### C049 Rollen en verantwoordelijkheden

De verdeling van bewerken, beoordelen en publiceren.

- Activiteit 2: Bestaande analisten beoordelen annotaties.
- Activiteit 3: Leg vast wie begripskeuzes en publicatie beoordeelt.
- Voorbeeld: Een technische importeur wordt niet daardoor inhoudelijk beoordelaar.
- Projectstatus: Deels bestaand; spoor D voorziet audit.
- Advies: Gebruik bevoegdheden en auditacties die bij de taak passen.

Bronnen: [H052](https://kaleidoscope.at/en/products/quickterm/), [H063C](https://www.terminologue.org/docs/info.en/), [P01](../../../docs/PLAN.md). Vindplaats: Quickterm; Terminologue privileges; spoor D.

### C050 Herkomst en bewijs

De bronnen en bewerkingen waarop een uitspraak berust.

- Activiteit 2: Behoud letterlijke passage en technische bronstand.
- Activiteit 3: Onderbouw definitie, koppeling en relatie afzonderlijk.
- Voorbeeld: Een begripsrelatie heeft een andere onderbouwing dan het label.
- Projectstatus: Bestaand activiteit 2; voorzien in D.
- Advies: Bewaar gebruikte bewijsstanden ook wanneer bron of annotatie verandert.

Bronnen: [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [P01](../../../docs/PLAN.md), [P03](../../../docs/architectuur/annotatieketen.md). Vindplaats: NL-SBB §5.2; spoor D / Datamodel; annotatieketen.

### C051 Revisie identiteit en opvolging

Het onderscheid tussen een verbeterde beschrijving en een gewijzigde betekenis.

- Activiteit 2: Bronwijzigingen blijven traceerbaar.
- Activiteit 3: Scheid revisie van nieuw begrip met opvolgingsrelatie.
- Voorbeeld: Spelfoutcorrectie verandert de identiteit niet; betekenisverschuiving mogelijk wel.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Laat de analist het soort wijziging motiveren.

Bronnen: [P01](../../../docs/PLAN.md), [H063B](https://www.terminologue.org/docs/intro.en/). Vindplaats: Spoor D / Datamodel; Terminologue History.

### C052 Samenvoegen splitsen en parkeren

Beslissingen waarmee kandidaatgroepen en begrippen worden afgebakend.

- Activiteit 2: De oorspronkelijke annotaties blijven intact.
- Activiteit 3: Bewaar de reden en historie van de keuze.
- Voorbeeld: Een voorgestelde groep wordt gesplitst wegens verschillend bereik.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Maak terugvinden van vervangen begrippen en verworpen voorstellen mogelijk.

Bronnen: [P01](../../../docs/PLAN.md), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf). Vindplaats: Spoor D / Elementen groepen en begrippen; TermWerk beheer.

### C053 Wijzigingsimpact en herbeoordeling

Het gericht opnieuw beoordelen van afhankelijke gegevens na een verandering.

- Activiteit 2: Controleer of gebruikte passages inhoudelijk veranderen.
- Activiteit 3: Markeer getroffen koppelingen en begrippen.
- Voorbeeld: Een gewijzigde dragende definitie raakt meerdere begrippen.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Volg bewijsafhankelijkheden; een nieuwe datum alleen is onvoldoende.

Bronnen: [P01](../../../docs/PLAN.md), [H063B](https://www.terminologue.org/docs/intro.en/). Vindplaats: Spoor D / Actualiteit; Terminologue status-reset.

### C054 Publicatiestand en redactievoorraad

Een vastgelegde selectie voor gebruik naast materiaal dat nog in bewerking is.

- Activiteit 2: Onbeoordeelde annotaties blijven herkenbaar.
- Activiteit 3: Publiceer alleen volgens een expliciet selectiecriterium.
- Voorbeeld: Een export kan meer records bevatten dan de publieke zoekinterface.
- Projectstatus: Aanvullend acceptatiecriterium.
- Advies: Controleer publicatie- en exportfilters afzonderlijk.

Bronnen: [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [H080](https://www.synaptica.com/synaptica-graphite/), [P01](../../../docs/PLAN.md). Vindplaats: TermWerk export/publicatie; Graphite; spoor D / export.

### C055 Dekking en open punten

Wat behandeld is tegenover wat nog ontbreekt of onzeker is.

- Activiteit 2: Maak ontbrekende of afgewezen elementen zichtbaar.
- Activiteit 3: Tel verwerking los van inhoudelijke volledigheid.
- Voorbeeld: Honderd procent gekoppeld kan nog een verkeerde definitie bevatten.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Rapporteer aantallen en inhoudelijke onzekerheden apart.

Bronnen: [P01](../../../docs/PLAN.md), [P04](../../../docs/architectuur/onderzoek-empirische-validatie.md). Vindplaats: Spoor D / dekking; empirische validatie.

## Uitwisseling en hergebruik

### C056 TBX en dialect

Een terminologisch uitwisselformaat met verschillende toegestane gegevenscategorieën.

- Activiteit 2: Termlijsten kunnen kandidaatmateriaal leveren.
- Activiteit 3: Toets hoe concept-, taal- en termgegevens worden overgedragen.
- Voorbeeld: Een TBX-Basic-export bewaart niet automatisch alle lokale reviewvelden.
- Projectstatus: Latere uitwisseling; nadere proef nodig.
- Advies: Noem versie, dialect, veldmapping en verlies expliciet.

Bronnen: [E07](https://www.tbxinfo.net/tbx-dialects/), [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [H059D](https://docs.memoq.com/11-3/api-docs/wsapi/memoqservices/tbservice.importexport.tbx.html). Vindplaats: TBX Dialects; TermWerk Export; QTerm TBX API.

### C057 SKOS en begrippenkader

Een RDF-model voor begrippen, labels en semantische relaties.

- Activiteit 2: JAS-labels blijven een eigen classificatie.
- Activiteit 3: Publiceer begrippen met herleidbare kader- en bronverwijzingen.
- Voorbeeld: Een URI identificeert een begrip ook als zijn label wijzigt.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Behoud review en juridische relaties als eigen gegevens naast SKOS.

Bronnen: [SKOS](https://www.w3.org/TR/skos-reference/), [P01](../../../docs/PLAN.md). Vindplaats: SKOS §3–4 en §8; spoor D / Projectie.

### C058 NL-SBB profiel

Nederlandse afspraken om begrippen en begrippenkaders te beschrijven.

- Activiteit 2: Bronnen ondersteunen betekenisonderzoek.
- Activiteit 3: Toets de gekozen beschrijving aan het gebruikte profiel.
- Voorbeeld: Een veld met definitietekst alleen bewijst nog geen conformiteit.
- Projectstatus: Reeds voorzien; conformiteit nog niet aangetoond.
- Advies: Gebruik de vastgelegde versie van 10 oktober 2024 als controlebasis.

Bronnen: [SBB](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/), [P01](../../../docs/PLAN.md). Vindplaats: NL-SBB §4–5; spoor D / Projectie.

### C059 SKOS-XL en labelidentiteit

Een uitbreiding waarin labels zelf identificeerbare objecten zijn.

- Activiteit 2: Kan herkomst van een aanduiding expliciteren.
- Activiteit 3: Helpt alleen wanneer metadata over labels nodig is.
- Voorbeeld: Twee labels hebben eigen gebruiksnotities.
- Projectstatus: Latere optie; geen eerste vereiste.
- Advies: Begin niet met extra labelobjecten zonder concrete metadata-behoefte.

Bronnen: [E16](https://www.w3.org/TR/skos-reference/skos-xl.html). Vindplaats: SKOS-XL vocabulary.

### C060 Formaat versus betekenisbehoud

Een geldig bestand kan inhoudelijk belangrijke gegevens verliezen.

- Activiteit 2: Bronposities kunnen bij conversie verdwijnen.
- Activiteit 3: Controleer relaties, context, status en identiteit na overdracht.
- Voorbeeld: Een getypeerde relatie komt terug als vrije notitie.
- Projectstatus: Aanvullend acceptatiecriterium.
- Advies: Vergelijk inhoud vóór export en na import, niet alleen XML-validiteit.

Bronnen: [INT17](https://termwerk.ivdnt.org/images/termwerk_handleiding_1.0.pdf), [H059D](https://docs.memoq.com/11-3/api-docs/wsapi/memoqservices/tbservice.importexport.tbx.html), [H076](https://www.dog-gmbh.de/lookup-produkt/). Vindplaats: TermWerk Export; QTerm TBX; LookUp formats.

### C061 API en projectie

Een toegangsvorm tot gegevens met een eigen verantwoordelijkheidsgrens.

- Activiteit 2: De bestaande API beheert annotatiebeslissingen.
- Activiteit 3: De graaf volgt de vastgelegde begripsgegevens.
- Voorbeeld: Een graafprojectie loopt achter terwijl een beoordeling al is opgeslagen.
- Projectstatus: Reeds voorzien in spoor D.
- Advies: Voeg een externe termtool niet als tweede waarheid toe.

Bronnen: [P01](../../../docs/PLAN.md), [P02](../../../README.md), [H074](https://coreon.com/terminology-management/). Vindplaats: Spoor D / API en Projectie; architectuur; Coreon APIs.

### C062 FAIR en hergebruikvoorwaarden

Vindbaarheid en herbruikbaarheid vragen metadata en duidelijke toegangsvoorwaarden.

- Activiteit 2: Selecteer bronnen met bekende herkomst.
- Activiteit 3: Maak begrippen vindbaar met passende gebruiksvoorwaarden.
- Voorbeeld: Een vindbaar bestand is niet daardoor vrij herbruikbaar.
- Projectstatus: Aanvullende beheerafspraak.
- Advies: Leg licentie en toegangsvoorwaarden per externe bron vast.

Bronnen: [H050B](https://yourterm.eu/wp-content/uploads/2022/05/FAIRterm-presentation-update.pdf), [H098B](https://babelnet.org/license), [E11](https://www.cotsoes.org/sites/default/files/public_files/COTCOES_Terminology_Management_for_Translation_A_Starter_Guide.pdf). Vindplaats: FAIRterm tutorial; BabelNet License; COTCOES Starter Guide.

## Bronnen en gezag

### C063 Terminologische autoriteit versus rechtsbron

Een woordenlijst kan uitleg geven zonder de geldende norm vast te stellen.

- Activiteit 2: Zoek vanuit een term door naar de wettelijke bron.
- Activiteit 3: Weeg herkomst en context van iedere definitie.
- Voorbeeld: Een publieksglossarium vervangt geen definitiebepaling.
- Projectstatus: Reeds voorzien; bronrollen aanscherpen.
- Advies: Gebruik IATE, EuroVoc en Rechtspraak als verschillende soorten contextbron.

Bronnen: [H051](https://iate.europa.eu/home), [E12](https://op.europa.eu/en/web/eu-vocabularies/th-dataset/-/resource/dataset/eurovoc), [E13](https://www.rechtspraak.nl/juridische-begrippen), [P01](../../../docs/PLAN.md). Vindplaats: IATE; EuroVoc; Rechtspraak begrippen; spoor D / Bronselectie.

### C064 Historische terminologie en betekenisverandering

Aanduidingen en betekenissen kunnen door de tijd veranderen.

- Activiteit 2: Zoek oude termen zonder ze stil te moderniseren.
- Activiteit 3: Vergelijk begrippen per periode en broncontext.
- Voorbeeld: Een historisch woord krijgt geen huidige definitie zonder onderbouwing.
- Projectstatus: Reeds voorzien via geldigheid; extra onderzoekslens.
- Advies: Bewaar historische labels met periode en bron.

Bronnen: [INT07](https://ivdnt.org/terminologie/historische-termenlijsten/), [P01](../../../docs/PLAN.md). Vindplaats: Historische termenlijsten; spoor D / geldigheid.

### C065 Descriptief en voorschrijvend terminologiegebruik

Beschrijven van aangetroffen taal verschilt van sturen van eigen taalgebruik.

- Activiteit 2: Registreer wat de wet daadwerkelijk formuleert.
- Activiteit 3: Kies heldere labels voor eigen analyse zonder de bron te herschrijven.
- Voorbeeld: Een onwenselijke term in een bron blijft een letterlijk citaat.
- Projectstatus: Nieuwe explicitering van bestaand brongetrouw beleid.
- Advies: Laat terminologische consistentiecontroles alleen adviseren over eigen teksten.

Bronnen: [INT01](https://ivdnt.org/terminologie/wat-is-terminologie/), [H068](https://www.tippyterm.de/tippyterm/anwendung/), [P02](../../../README.md). Vindplaats: Wat is terminologie; TippyTerm; brongetrouwheid project.

## Methode en iteratie

### C066 Terugkoppeling tussen activiteit 2 en 3

Begripsvorming kan aanleiding geven tot een andere markering of scope.

- Activiteit 2: Heropen de betreffende annotatie als dat nodig is.
- Activiteit 3: Leg de reden voor de terugkoppeling vast.
- Voorbeeld: Een gevonden definitie onthult een gemiste kwalificatie.
- Projectstatus: Expliciet voorzien in spoor D.
- Advies: Voer geen verborgen correctie door vanuit een begripsbeslissing.

Bronnen: [M02](../../../docs/kennisbank/handleiding-wetsanalyse-in-de-praktijk-versie-1%20%281%29.pdf), [M03](../../../docs/kennisbank/leidraad-voor-wetsanalyse-op-maat-versie-1.pdf), [P01](../../../docs/PLAN.md). Vindplaats: Handleiding §3.4–3.5; leidraad Ad 2 en Ad 3; spoor D.
