# Verbeterplan JAS: bewijs, context en beoordeelbare samenhang

Soort: *los verbeterplan* · Aangescherpt: 8 oktober 2026 · Status: plan voor een proefimplementatie, nog niet uitgevoerd; PR 1 is op verzoek nog niet gestart. De aanvullingen hieronder verwerken de inhoudelijke reviews en een gerichte controle van de huidige kandidaat-, bewijs-, dekkings- en besliscode.

## 1. Hoofdkeuze en kritische beoordeling

**De voorgestelde richting is bruikbaar, maar ik zou de negen lagen niet als verplichte bouwvolgorde overnemen.** De eerste verbetering moet het model voor kandidaten en bewijs zijn. Daarna volgen gerichte grammaticale frames en juridische relaties. Een omvangrijke grammaticale tussenlaag vooraf bouwen heeft nog onvoldoende onderbouwing.

De [INT-analyse](../wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md) ondersteunt vooral het onderscheiden van **bronvoorkomen, betekenis, context, relatie en beoordeling**. Zij bevat geen praktijkbewijs dat de onderzochte hulpmiddelen de annotatie verbeteren. Ook die analyse blijft dus toetsbaar.

De [metingen van oktober](metingen/hybrid-v1-iw05-fixes-2026-10/README.md) laten concrete problemen zien met kandidaatgrenzen, algemene naamwoordgroepen en concurrerende klassen. De referenties zijn nog niet juridisch vastgesteld. Meer gevonden kandidaten betekenen daarom nog geen betere juridische analyse.

| Onderdeel van jouw voorstel | Kritisch oordeel en besluit |
|---|---|
| **1. Brontekst** | Behouden. Ook nieuw bewijs, frames en relaties moeten naar de juiste bronversie verwijzen. Impliciete partijen krijgen geen verzonnen tekstanker. |
| **2. Linguïstische analyse** | Grotendeels aanwezig: er bestaat al een provideronafhankelijk UD-model. SpaCy vervangen vereist dus geen nieuwe ontkoppelingslaag. |
| **3. GrammaticaalFrame** | Verkleinen tot gerichte predicatie-, vergelijkings- en afleidingsframes. Grammaticale rollen zijn aanwijzingen; onderwerp → Rechtssubject is geen geldige algemene omzetting. |
| **4. Lexicale kennis** | Als optionele bewijsbron onderzoeken. Valentie bepaalt mogelijke aanvullingen bij een woordbetekenis; zij bewijst geen juridische rol en corrigeert een parse niet automatisch. |
| **5. Kandidaatdetectie** | Hier ligt de eerste ingreep: bewijs aan afzonderlijke klassehypothesen koppelen, met de onderliggende waarnemingen en afhankelijkheden. De huidige samenvoeging van klassen en bewijs verliest het klassegebonden onderscheid. Afwezig bewijs is geen tegenbewijs. |
| **6. JAS-relaties** | Opnemen, inclusief beoordeling. Onderscheid grammaticale afhankelijkheden, juridische annotatierelaties en begripsrelaties uit activiteit 3. De voorgestelde relatienamen zijn projectkeuzes, geen vanzelfsprekend officiële JAS-vocabulaire. |
| **7. Coherentie** | Technische fouten hard afwijzen; ontbrekende juridische samenhang meestal als onderzoeksvraag behandelen. Een niet-genoemde partij maakt een rechtsbetrekking niet automatisch ongeldig. |
| **8. Compleetheid** | Structurele dekking en onderzoek naar juridische functies afzonderlijk registreren. Een parser en een daarop gebaseerde detector kunnen hetzelfde missen; hun onderlinge overeenstemming bewijst geen volledigheid. Juridische volledigheid wordt per complete bepaling onafhankelijk beoordeeld. |
| **9. AI-restgevallen** | Behouden met begrensde keuzes, maar voeg expliciet **onbeslist** toe. Onvoldoende context mag niet worden vertaald naar ‘geen annotatie’. |

Een inhoudelijke correctie betreft de afleidingsregel: **de uitvoer is niet noodzakelijk een letterlijk genoemde Variabelewaarde**. De regel kan een uitvoervariabele bepalen, een beslissing beschrijven of een specialisatie afleiden. Annoteren is bovendien nog geen regel uitvoeren. Dat onderscheid volgt uit [H2-JAS](../wetsanalyse/wetsanalyse-rijk/H2-JAS.md).

### 1.1 JAS-classificatie en JRM 2-verrijking

Voor deze pipeline is **JAS 1.0.10** het normatieve annotatiekader, vastgezet op de lokale [bronversie](../wetsanalyse/wetsanalyse-rijk/BRON.md). De dertien platformlabels met subtypen blijven de implementatie van dat kader. De classifier noemt deze versie nu al; het plan maakt haar ook expliciet in regels, beoordeling en exports.

De gepubliceerde JRM-specificatie onderscheidt Rechtsgevolg en Juridisch relevant feit als afzonderlijke hoofdclassificaties. JRM 2 verschilt dus inhoudelijk van JAS en is meer dan een verzameling extra relaties. De geraadpleegde publicatie vermeldt **werkversie 29 november 2024**, geen goedgekeurde consultatieversie. [JRM-specificatie, status en §§ 1, 3–4](https://regels.overheid.nl/standaarden/wetsuitvoering).

De eerste vier PR's implementeren JAS-analyse en projectmatig getypeerde annotatierelaties. JRM-verrijking staat standaard uit. Als die later wordt toegevoegd, krijgt zij een eigen bronversie, profiel, bewijs en beoordeling; haar classificaties komen niet in de JAS-enum of JAS-kwaliteitscijfers. Een projectrelatie is niet alleen door haar naam een JRM-uitspraak. Leg in het runmanifest het classificatieschema, het relatieprofiel en het eventuele verrijkingsprofiel afzonderlijk vast. De lokaal gebruikte JRM-werkversie van 18 november 2024 en de openbare versie worden niet als identiek behandeld zonder vergelijking. Dit sluit aan op de bestaande [afspraak over JRM-verrijking](../../.claude/skills/wetsanalyse/references/jrm-verrijking.md).

## 2. Bouwvolgorde

**Stap A — Beoordelingsbasis vastleggen, gelijktijdig met de proefontwikkeling**

- Bevries de actuele pipeline, bronstanden, instellingen en versies als nulmeting.
- Laat twee juristen onafhankelijk complete bepalingen beoordelen; leg verschillen en adjudicatie vast.
- Gebruik de bestaande opzet van circa 27–30 casussen voor de eerste gecontroleerde proef. Minimaal twintig geadjudiceerde casussen én dekking van alle dertien platformklassen en de constructiematrix zijn een ondergrens voor de eerste beoordeling, geen bewijs van brede juridische kwaliteit of voldoende grond voor productie-invoering; zie §4.1.
- Neem relaties en hun bewijs expliciet mee in de beoordeling. Leg vast wanneer samenhang impliciet, buiten bereik of juridisch onbeslist is.
- Beoordeel JAS-classificatie en juridische samenhang in afzonderlijke beoordelingsonderdelen. Leg naast labels ook de toegestane juridische interpretaties vast: functie, bereik, deelnemers/rollen, relaties en benodigde context. Verschillen tussen beoordelaars blijven zichtbaar vóór adjudicatie.
- Houd ontwikkelgevallen en een ongebruikte eindtoets gescheiden. Controleer eerdere blootstelling voordat bestaande casussen opnieuw ‘held-out’ worden genoemd.

**Stap B — Bewijs per hypothese en behoud van juridische functies**

- Scheid de identiteit van een tekstvoorkomen van de hypothesen over zijn juridische functie.
- Bewaar per klassehypothese ondersteunend bewijs, tegenbewijs, herkomst, regelversie en toepassingscontext. Splits de feitelijke waarneming van de juridische toepassing van een bewijsregel; detectoren mogen dezelfde waarneming hergebruiken.
- Geef waarnemingen een identiteit en leg hun oorsprong vast: tekstpatroon, concrete UD-relatie, lexiconrecord of contextgegeven, met bronanker, invoer-/modelversie en verwijzingen naar voorafgaande waarnemingen. Leg bij de toepassing vast welke regel en methodische grond de hypothese ondersteunen of tegenspreken. Dit zijn gegevens in het bewijsdossier, geen extra publiek hoofdmodel.
- Houd de afhankelijkheidsketen acyclisch en herleidbaar. Drie detectoren die dezelfde parsewaarneming gebruiken leveren geen drie onafhankelijke gronden. Het aantal detectoren of overeenkomende uitkomsten verhoogt de bewijssterkte niet. Ook verschillende herkomsten bewijzen nog geen statistische onafhankelijkheid.
- Onderscheid **ondersteuning**, **tegenbewijs** en **niet vastgesteld**. Een overgeslagen detector, ontbrekende context of ontbrekend positief signaal is op zichzelf geen tegenbewijs. Tegenbewijs vereist een expliciete regel met gecontroleerde toepassingsvoorwaarden.
- Maak iedere bewijsregel toetsbaar met positieve, negatieve, ambigue en context-onvolledige gevallen. Voeg een invariant toe: duplicatie van dezelfde waarneming via een andere detector verandert noch de deterministische beslissing noch de canonieke classifierinvoer. Variatie tussen modelaanroepen wordt afzonderlijk gemeten.
- Voeg alleen hypothesen voor dezelfde functie samen. Verschillende functies op dezelfde span mogen elkaar niet wegdrukken.
- Behandel algemene naamwoordgroepen als taalkundige waarnemingen. Onderzoek met een vergelijking mét en zonder deze signalen wanneer zij zelfstandig juridische kandidaten mogen opleveren; verwijder ze niet blind.
- Laat deterministische acceptatie afhangen van gevalideerd klassespecifiek bewijs. Conflicterend juridisch bewijs blijft zichtbaar en vraagt classificatie of beoordeling.

De huidige code leidt bewijssterkte al af uit regelmetadata in `bewijssterkte.py`; `besluit.py` telt geen detectorstemmen op. De ingreep is daarom het expliciet maken van afhankelijkheden en klassespecifieke toepassingen, niet het vervangen van een aangetoond stemmechanisme. Bestaande `DetectieBijdrage`-records bewaren gezamenlijke steun voor een klasseverzameling. Migreer die als gezamenlijke steun; reconstrueer daaruit geen precieze klasse–bewijsrelatie die nooit is vastgelegd.

**Stap C — Kleine frames en expliciete contextafhankelijkheden**

- Bouw voort op de bestaande constituentendetectie. Begin met predicaat, zinsdeelbereik, actieve/passieve vorm, mogelijke deelnemers, tijdsconstructies en het bereik van operatoren, negatie, modaliteit en uitzonderingen.
- Voeg afzonderlijke vergelijkings- en afleidingsframes toe voor operanden, invoer en uitvoer. Een algemene verzameling velden voor alle Nederlandse grammatica wordt geen voorwaarde voor andere detectoren.
- Neem `OperatorScope` op **binnen `AnalyseFrame`**, niet als vijfde zelfstandig hoofdmodel. Het bevat de brongebonden verbindingsformulering, mogelijke bewerking of koppeling, operanden met hun rollen/volgorde, bereik, doelpredicaat of doelframe, bewijs en alternatieve koppelingen. Ondersteun één operand bij negatie en genest bereik bij samengestelde voorwaarden; een uitzondering is niet automatisch gewone negatie. Onderscheid grammaticale koppeling van de nog te beoordelen juridische functie. Gebruik onderbouwde statussen, geen ongekalibreerd zekerheidspercentage.
- Bewaar onzekere grammaticale koppelingen als alternatieven. Niet-aaneengesloten werkwoordgroepen blijven tokenverzamelingen; hun omspannende bereik wordt niet automatisch een annotatie.
- Laat detectoren zonder parserafhankelijkheid blijven werken bij een ontbrekende of mislukte parse.
- Breid het bronpakket gecontroleerd uit met rechtstreeks aangewezen context: oudertekst en één stap expliciete bronverwijzingen, versiegebonden en binnen de bestaande limiet van twintig contextpassages. Ontbrekende of ambigue verwijzingen blijven expliciet. Context wordt geen extra annotatiedoel.
- Koppel een contextafhankelijkheid aan de getroffen hypothese, relatie of scope: welk gegeven ontbreekt, waarom het nodig is en welke beslissing ervan afhangt. Vereiste ontbrekende context geeft `HUMAN_REVIEW` met reden `CONTEXT_NODIG`; dit is geen extra JAS-klasse. De classifier of resolver mag die blokkade niet omzetten in automatische acceptatie of afwijzing. Niet-afhankelijke beslissingen kunnen doorgaan. Nieuwe context leidt tot een nieuwe herleidbare beoordeling, niet tot overschrijven van menselijke historie.

**Ontwikkelcasus voor tijd en operatorbereik.** Gebruik IW01, artikel 9 lid 1 IW 1990, uit de vastgelegde referentieset: ‘Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.’ De volgende onderscheidingen zijn onderzoeksvragen, geen vooraf goedgekeurde gold-annotaties:

| Formulering | Te onderzoeken functie en samenhang |
|---|---|
| belastingaanslag | Mogelijk Rechtsobject; verbinding met de invorderbaarheid. |
| is invorderbaar | Dragende juridische uitspraak; klasse, eventueel kenmerk en partijen afzonderlijk beoordelen. |
| zes weken | Duur binnen een tijdsconstructie; mogelijke vaste termijnwaarde onderscheiden van de gekozen JAS-klasse. |
| na | Temporele koppeling tussen tijdsreferentie en verschuiving, met bereik over de constructie. Een zelfstandig JAS-Operator-label blijft een afzonderlijke hypothese. |
| dagtekening van het aanslagbiljet | Tijdreferentie met eigen grensvraag; vaststellen hoe de constructie aan het predicaat hangt. |

De JAS-definitie van Operator beschrijft rekenkundige, vergelijkende en logische bewerkingen. Het herkennen van het voorzetsel ‘na’ bewijst dus niet zelfstandig die classificatie. Het frame mag de temporele koppeling vastleggen zonder een Operator-annotatie af te dwingen. De precieze spans, nesting en eventuele nevenfuncties worden juridisch gevalideerd. Er wordt geen concrete invorderingsdatum berekend. IW01 en andere reeds gebruikte IW-gevallen blijven ontwikkel- of regressiecasussen, geen onafhankelijke eindtoets. [Operator en Tijdsaanduiding](../wetsanalyse/wetsanalyse-rijk/H2-JAS.md#operator).

**Stap D — Juridische relaties, diagnose en begrensde classificatie**

- Introduceer eerst relaties voor betrokken partijen/objecten, voorwaarden en uitzonderingen, tijd/plaats, afleidingsinvoer/-uitvoer en waarde–grootheid.
- Leg richting, betekenis, toegestane eindpunten en bewijsvereisten vast in een versieerbare relatiecatalogus. Leid ‘plichthebber’ bijvoorbeeld niet uitsluitend af uit het grammaticale onderwerp.
- Onderscheid de juridische functie van een hypothese van haar rol in een specifieke relatie. Eén Rechtssubject kan in verschillende relaties verschillende rollen vervullen; een rol wordt niet als universele eigenschap of nieuw JAS-label op het element gezet.
- Maak relatievoorstellen tussen hypothesen. Koppel ze bij opslag aan de uiteindelijke element-ID’s; onopgeloste eindpunten blijven onderzoeksvragen.
- Behoud tijd/plaats als specifieke JAS-klasse waar de bestaande voorrangsregels gelden. Bewaar een aanvullende variabele- of parameterfunctie afzonderlijk.
- Registreer structurele dekking en juridische functiedekking afzonderlijk, volgens de uitwerking hieronder. Een herstelregel mag alleen een brongebonden kandidaat met eigen bewijs toevoegen.
- Laat het model kiezen tussen aangeboden hypothesen, bestaande spanopties, geen annotatie of onbeslist. Ambigue relaties gaan in deze eerste versie naar de jurist; er komt geen nieuwe generatieve beoordelaarsketen.

### 2.1 Structurele dekking, functiedekking en interpretatie

**Structurele dekking** registreert welke predicaten, bijzinnen, vergelijkingen, operatorbereiken en temporele koppelingen onderzocht zijn, inclusief overgeslagen of ambigue analyses. Dit bouwt voort op de huidige detectorregistratie, maar een gedraaide detector bewijst niet dat iedere constructie onderzocht is.

**Juridische functiedekking** registreert per volledige bepaling de JAS-herkenningsvragen en hun concrete toepassingen op gevonden constructies. Per toepassing staat vast: hypothese aangeboden, onderbouwd geen kandidaat, impliciete functie nog onopgelost, context nodig of niet onderzocht. Bewaar ook een algemene controle van de bepaling, zodat functies buiten gevonden frames niet buiten de administratie vallen. Het afronden van die controles rechtvaardigt geen claim dat alle functies gevonden zijn.

Een impliciete functie krijgt een signaal met de dragende passage en benodigde context; zij krijgt geen verzonnen span voor niet-aanwezige woorden. Alleen voldoende onderzochte gevallen mogen de uitkomst ‘geen kandidaat’ krijgen. Onbesliste, niet onderzochte en contextafhankelijke functies blijven in het overzicht en in de noemer van de procesrapportage staan.

Meet daadwerkelijke juridische volledigheid tegen de onafhankelijk geadjudiceerde **complete bepaling**, niet tegen de door de pipeline zelf gevonden frames. Meet daarnaast **interpretatiedekking**: is minstens één door juristen toegestane combinatie van klasse/subtype, functie, bereik, rollen en relaties aangeboden? Rapporteer ook het aantal onjuiste alternatieven en de uiteindelijke keuze, zodat steeds meer hypothesen aanbieden niet vanzelf als verbetering telt. Houd deze maat gescheiden van labelherkenning, relatiekwaliteit en onderzoekdekking. Een open contextvraag kan een juiste procesuitkomst zijn, maar telt niet automatisch als een volledig gevonden interpretatie.

### 2.2 Identiteit en samenvoeging van hypothesen

Het bestaande kandidaat-ID op basis van bron-IRI en offsets blijft een technische verwijzing naar een kandidaat, niet de identiteit van een juridische interpretatie. Geef `JasHypothese` een afzonderlijk ID op basis van een canonieke sleutel:

| Onderdeel van de sleutel | Betekenis |
|---|---|
| Bronvoorkomen | Bron-IRI, bronhash en exacte ankerbereiken; identieke woorden elders of in een gewijzigde bron zijn andere voorkomens. |
| Classificatie | JAS-versie, klasse en subtype; onbepaald subtype is niet gelijk aan een vastgesteld subtype. |
| Juridische functie en interpretatie | Functiecode, toepassingsbereik en betekenisdragende bindingen, zoals doelpredicaat en operanden. Dezelfde span en klasse met ander bereik zijn verschillende hypothesen. |
| Context | Een vingerafdruk van de daadwerkelijk gebruikte, versiegebonden context en de nog vereiste contextafhankelijkheden; niet van willekeurige extra passages in het bronpakket. |
| Framebinding, indien betekenisdragend | Een canonieke sleutel van het gebonden frame en zijn bronrollen; geen tijdelijk parser- of runnummer. Een frame dat alleen extra bewijs geeft, verandert de interpretatie-identiteit niet. |

Detector, bewijsvolgorde, toelichting en run-ID maken geen deel uit van deze sleutel. Zij horen in het versiegebonden bewijsdossier. Extra bewijs voor dezelfde interpretatie levert een nieuwe bewijsversie op; een gewijzigde klasse, functie, betekenisdragende binding of benodigde context levert een andere hypothese op, met een expliciete opvolgingsverwijzing.

Automatische fusie is alleen toegestaan bij gelijke, voldoende bepaalde sleutels. Bij ontbrekende interpretatiegegevens blijven voorlopige hypothesen aan hun detectiebijdrage gekoppeld; ‘onbekend’ geldt niet als wildcard voor samenvoeging. Historische kandidaten krijgen geen achteraf verzonnen functie-identiteit. Uitwisselbare alternatieven voor dezelfde beslisvraag komen in een expliciete alternatiefgroep. Verenigbare functies kunnen naast elkaar bestaan, ook op dezelfde span; het enkel delen van een span rechtvaardigt geen alternatiefgroep.

### 2.3 Beslisstrategie en begrenzing van AI-gebruik

Pas de volgende beslisregels toe op de betrokken hypothese of alternatiefgroep. Technische ongeldigheid en noodzakelijke ontbrekende context worden vóór semantische classificatie afgehandeld. Een ontbrekend signaal telt nergens als automatische juridische afwijzing.

| Situatie | Uitkomst |
|---|---|
| Anker, bronversie of bewijsverwijzing technisch ongeldig | Technische afwijzing met auditreden; geen modelaanroep en geen juridische conclusie over de tekst. |
| Voor de beslissing vereiste context ontbreekt | `HUMAN_REVIEW` met `CONTEXT_NODIG`; andere, niet-afhankelijke functies kunnen doorgaan. |
| Gevalideerde uitsluitings- of specificiteitsregel is volledig toepasbaar | Deterministische afwijzing van uitsluitend de getroffen hypothese of redundante functie, met regel en bewijs. Bij strijdig beslissend bewijs volgt menselijke beoordeling. |
| Eén interpretatie heeft beslissend, gevalideerd klassegebonden bewijs; er is geen onopgelost juridisch conflict | `ACCEPTED` als deterministisch annotatievoorstel. Algemene grammaticale signalen zijn op zichzelf geen tegenbewijs. Dit is geen menselijke goedkeuring. |
| Verschillende interpretaties zijn verenigbaar | Behoud ze afzonderlijk en beoordeel elke functie; geen geforceerde winnaar wegens overlap of dezelfde klasse. |
| Er rest een afgebakende semantische keuze met voldoende context en onderbouwde alternatieven | De classifier kiest binnen de aangeboden alternatiefgroep een hypothese-ID, geen annotatie of onbeslist. Alleen bestaande spanopties zijn toegestaan; vrije interpretaties blijven uitgesloten. |
| Alternatieven, juridisch bereik of conflicten zijn onvoldoende afgebakend, of de classifier blijft onbeslist | Menselijke beoordeling met concrete open vraag. Ambigue relaties gaan in deze proef eveneens naar de jurist. |

Een generieke naamwoordgroep zonder klassegebonden grond veroorzaakt niet automatisch een modelaanroep. Bewaar haar als waarneming of gerichte onderzoeksvraag. Ontdubbel bewijs en gelijkwaardige interpretaties vóór routering. Een grote kandidaatverzameling is geen reden om de modelvrijheid of het aantal beoordelaars te vergroten. Bij overschrijding van de bestaande batch- of budgetgrenzen blijven de niet behandelde groepen zichtbaar als onbeslist; zij verdwijnen niet en worden niet als ‘geen annotatie’ geboekt.

Meet naast juridische kwaliteit het aandeel deterministische beslissingen, modelaanroepen en tokens per complete bepaling, de omvang van alternatiefgroepen en de menselijke beoordelingslast. Vergelijk modelgebruik bij gelijkwaardige kwaliteit en dezelfde taak. Verplaatsen van werk naar juristen of wegfilteren van relevante hypothesen geldt niet zelfstandig als verbetering.

## 3. Interfaces, werkplek en opslag

De minimale uitbreiding bestaat uit vier expliciete gegevensvormen:

| Gegevensvorm | Verantwoordelijkheid |
|---|---|
| **JasHypothese** | Bronanker, functiecontext, klasse/subtype, toepassingen van bewijsregels met waarnemingen en afhankelijkheden, beslisstatus en benodigde context. |
| **AnalyseFrame** | Brongebonden grammaticale of regelstructuur, rollen, ingebedde `OperatorScope`, bereik, alternatieven en contextafhankelijkheden. |
| **RelatieVoorstel / JasRelatie** | Getypeerde eindpunten, rollen binnen deze relatie, richting, bewijs, bronstand, relatieprofiel en eigen beoordeling. |
| **AnalyseSignaal** | Ontbrekende samenhang, onopgeloste functie of contextafhankelijkheid, betrokken onderdelen, onderzoeksstatus en reden. |

Behoud de dertien platformlabels met bestaande subtypen. Meerdere rollen bij hetzelfde element worden via relaties vastgelegd; zij veroorzaken niet vanzelf dubbele annotaties.

Breid de bestaande batch- en leescontracten additief uit met relaties en hypothesetraces. Voeg afzonderlijke relatiebeslissingen toe met dezelfde revisiecontrole en auditprincipes als elementbeslissingen. PostgreSQL blijft de bron van waarheid; de graaf blijft een projectie.

De werkplek toont bij een voorstel de volledige bepaling, relevant bewijs, gedeelde bewijsafhankelijkheden, operatorbereik, alternatieven en gerelateerde elementen. Onopgeloste functies en benodigde context zijn ook zichtbaar als er nog geen geclassificeerd element is. Juristen kunnen relaties goedkeuren, afwijzen en corrigeren. Goedkeuring van een element keurt zijn relaties niet impliciet goed. Gewijzigde eindpunten maken betrokken relaties opnieuw beoordelingsplichtig; historie blijft behouden.

Voeg bronvergelijking toe met letterlijke en lemma-gebaseerde concordanties binnen het geselecteerde werkgebied. Gelijke woorden worden daarbij niet automatisch hetzelfde begrip. Begripsvorming en definitiebeheer blijven activiteit 3.

Gebruik een nieuwe exportversie voor relaties en hun beoordelingen. Bestaande exports blijven leesbaar; oude elementexports worden herkenbaar als zodanig aangeboden. Bestaande element-ID’s en menselijke besluiten worden niet vervangen door een nieuwe analyserun.

### 3.1 Contract van hypothese naar beoordeelde annotatie

De overgang kent drie niveaus: **bronwaarneming → juridische hypothese → beoordeelde JAS-annotatie**. Een machinebesluit `ACCEPTED` levert een voorstel met lifecycle `voorgesteld`; alleen een expliciete menselijke beslissing kan het juridisch accorderen.

- Leg bij ieder voorstel de hypothese-ID's, exacte bewijsversies, bronstand en producerende run vast. Bij een beoordeling worden ook actor, besluit, reden en annotatierevisie vastgelegd. Latere bewijsversies wijzigen niet het dossier waarop een eerder besluit berustte.
- Promotie controleert bronankers, actuele revisies, de gekozen interpretatie en eventuele contextblokkades. Benodigde context moet zijn geleverd of met een menselijke motivering als niet noodzakelijk zijn beoordeeld. Relaties krijgen een afzonderlijk besluit; beoordeelde eindpunten maken een relatie niet automatisch vastgesteld.
- Bewaar een expliciete mapping van hypothesen naar annotatie-ID en revisie. Alleen aantoonbaar dezelfde interpretatie mag naar hetzelfde element worden samengevoegd. Ontdubbeling uitsluitend op klasse en ankers is daarvoor onvoldoende. Meerdere relatierollen bij één ongewijzigde interpretatie mogen hetzelfde element gebruiken.
- Een afwijzing blijft met bewijs en reden bewaard, ook als geen annotatie-element ontstaat. Een nieuwe analyserun mag dat besluit niet wissen, heropenen of omzeilen door een nieuw voorstel-ID voor dezelfde interpretatie te maken. Nieuw inhoudelijk bewijs kan een afzonderlijk herbeoordelingsverzoek opleveren.
- Een menselijke wijziging bewaart het oorspronkelijke voorstel en het verschil. Wijzigt de interpretatie, leg dan de nieuwe hypothese/annotatierevisie en de relatie ‘vervangt’ vast. Geraakte relaties worden opnieuw beoordelingsplichtig; onveranderde besluiten blijven behouden.
- Een nieuwe analyse koppelt bij gelijke identiteit aan de bestaande historie. Een andere bronversie of interpretatie krijgt een opvolgingsrelatie, geen stilzwijgend overgenomen goedkeuring. Een oude annotatie die de nieuwe run niet vindt, wordt daardoor niet verwijderd of afgewezen.

Het beslisregister, de API-opslag, weergave en export moeten deze mapping bewaren, ook voor afgewezen en onbesliste hypothesen. Historische annotaties zonder hypothese-ID blijven leesbaar en worden herkenbaar als historisch vastgelegd; ontbrekend bewijs wordt niet gereconstrueerd alsof het destijds bestond.

## 4. Hulpmiddelen en verificatie

**Geen extern lexicon wordt een verplichte afhankelijkheid van de eerste verbetering.** Vergelijk later PAROLE en e-Lex op werkelijk waargenomen valentieproblemen. e-Lex bevat eveneens complementatiepatronen; PAROLE vraagt een ondertekende licentie. Adoptie vereist bruikbare toegang én aantoonbare verbetering op de juridische beoordelingsset. [PAROLE](https://taalmaterialen.ivdnt.org/download/tstc-parole-lexicon/), [e-Lex-documentatie](https://taalmaterialen.ivdnt.org/wp-content/uploads/documentatie/elex_documentatie1.1_nl.pdf).

Lassy en SoNaR dienen als aanvullende diagnostiek. Controleer eerst labelmapping en datasetoverlap: het huidige spaCy-model noemt UD LassySmall als trainingsbron. SoNaR-1 heeft handmatig geverifieerde semantische annotaties, maar daarmee nog geen JAS-gold. [spaCy-modelgegevens](https://raw.githubusercontent.com/explosion/spacy-models/master/meta/nl_core_news_md-3.8.0.json), [SoNaR](https://taalmaterialen.ivdnt.org/download/tstc-sonar-corpus/).

Verificatie omvat:

- **Juridische grensgevallen:** onderwerp zonder Rechtssubjectfunctie, passieve actor, impliciete partij, nominalisatie, definitie in een opsomming, voorwaardelijk versus vergelijkend ‘als’, negatie en uitzonderingen.
- **Samenhang:** termijn bij het juiste predicaat, afleiding zonder genoemde uitkomstwaarde, verschillende functies op dezelfde span, ontbrekende context en ambigue antecedenten.
- **Operatorbereik:** onderscheid `niet (A en B)` van `(niet A) en B`, vergelijk temporele koppelingen aan verschillende predicaten, toets uitzonderingen op de juiste hoofdregel en behoud onbesliste koppelingen. Voeg ook gevallen toe waarin een temporele koppeling terecht géén zelfstandig Operator-label krijgt.
- **Bewijs en context:** duplicatie via meerdere detectoren verandert de deterministische beslissing en canonieke classifierinvoer niet; de afhankelijkheidsgraaf kent geen cycli of ontbrekende verwijzingen; ontbrekend bewijs wordt geen tegenbewijs; noodzakelijke ontbrekende context blijft een gerichte blokkade; onafhankelijke beslissingen blijven mogelijk.
- **Techniek:** exacte Unicode-ankers, bronversies, parseruitval, tegenstrijdig bewijs, afgewezen eindpunten, gelijktijdige correcties en verliesvrije opslag/export.
- **Kwaliteit:** kandidaatrecall, aangeboden juiste klasse, interpretatiedekking met onjuiste alternatieven, exacte grenzen, precisie/recall per klasse, relatieprecisie/-recall, volledigheid per bepaling en benodigde correcties/beoordelingstijd. Beoordeel relaties afzonderlijk op eindpunten, rollen, type, richting en bereik, zowel gegeven correcte elementen als over de hele keten.
- **Methodescheiding:** JRM-verrijking staat standaard uit; eventueel later ingeschakelde verrijking verandert geen JAS-label, goedkeuring of JAS-score. Het bronprofiel reist door opslag, weergave en export mee.
- **Identiteit en promotie:** dezelfde span/klasse met ander bereik of andere context blijft onderscheiden; extra bewijs verandert geen interpretatie-ID; detectorvolgorde verandert de canonieke sleutel niet. Goedkeuring, afwijzing, correctie en een nieuwe run bewaren de mapping en historie. Een nieuwe run die een goedgekeurd element mist, verwijdert het niet.
- **Vergelijking:** iedere wijziging afzonderlijk en gecombineerd meten, met vijf herhalingen voor modelafhankelijke resultaten en een controlegroep met ongewijzigde invoer.

### 4.1 Omvang en uitbreiding van de juridische toetsing

De eerste 27–30 casussen zijn een **pilotset** om het beoordelingsprotocol, de fouttaxonomie en de technische proef te toetsen. Zij onderbouwen geen brede kwaliteitsclaim over alle dertien klassen, complexe relaties of Nederlandse wetgeving. Rapporteer per klasse, constructie en relatietype het aantal onafhankelijke bepalingen, de aantallen beoordeelde gevallen en de onzekerheid; meerdere modelruns op dezelfde bepaling vergroten niet de juridische steekproef.

Breid daarna gericht uit met nieuw geadjudiceerde gevallen rond aangetoonde fouten, grensgevallen, weinig vertegenwoordigde klassen en extra bronfamilies. Die verzameling is ontwikkel- en regressiemateriaal, geen representatieve eindtoets. Neem ook correct verwerkte contrastgevallen op om overcorrectie zichtbaar te maken.

Houd voor de volgende fase een **nieuwe onafhankelijke eindtoets** apart. Leg selectie, omvang, spreiding en de vereiste nauwkeurigheid van de kwaliteitsclaims vast voordat uitvoer op die set wordt bekeken; baseer de omvang op de gewenste uitspraak per klasse/relatietype, niet op een willekeurig totaal aantal casussen. Zodra toetsgevallen voor aanpassing van de pipeline worden gebruikt, worden ze ontwikkelgevallen en is voor een volgende eindclaim een nieuwe toets nodig. Een onvoldoende grote of te eenzijdige toets rechtvaardigt alleen een beperkte conclusie; het betrokken onderdeel blijft experimenteel als de beoogde productieclaim niet is onderbouwd.

## 5. Invoering en acceptatie

Zoals gekozen groeit de nieuwe werking in een **afzonderlijke proefomgeving naast productie**, inclusief de beoordelingsinterface. Dat vervangt het eerdere ontwikkeluitstel voor deze proef; juridische validatie blijft vereist voor productie.

Leg vóór de eerste proefwijziging de meetdefinities, referentieversie, vergelijkingsopzet en acceptatiecriteria vast. Een onderdeel wordt pas ingevoerd wanneer de volgende controles slagen:

| Meetpunt | Acceptatievoorwaarde |
|---|---|
| Exacte bronankers en contracten | 100% van de opgeslagen ankers is technisch correct en versiegebonden. Geen ongeldige eindpunten of bewijsverwijzingen. Afgewezen technische uitvoer blijft afzonderlijk geregistreerd. |
| Menselijke besluiten | Geen verlies of onbedoelde wijziging van besluiten, element-ID's of revisiehistorie; aantonen met voor/na-vergelijking en opslag-/exportcontrole. |
| Klasseherkenning | Precisie en recall per klasse en over de set vergelijken met de nulmeting; geen onverklaarde verslechtering. De beoogde foutcategorie verbetert op geadjudiceerde gevallen uit minstens twee bronfamilies. |
| Relatieherkenning | Eindpunten, rollen, type, richting en bereik afzonderlijk én gezamenlijk toetsen. Winst op labels mag fouten in relaties niet compenseren; de relatiebeoordeling heeft een eigen uitkomst. |
| Interpretatie en juridische volledigheid | Per volledige bepaling vergelijken met de onafhankelijk vastgestelde functies en toegestane interpretaties. Gemiste en onbesliste functies blijven zichtbaar. Extra onjuiste hypothesen apart tellen. |
| Beoordelingslast | Vergelijk dezelfde volledige beoordeltaak, inclusief samenhang, in een tegengebalanceerde proef met juristen. Standaardgrens: de mediane actieve beoordelingstijd neemt niet toe; rapporteer ook spreiding, correcties en onnodige signalen. Een overschrijding houdt de wijziging experimenteel en vereist een vooraf vastgelegde herziening van het criterium voor een volgende proef. |
| Onbesliste gevallen | Alle onbesliste uitkomsten hebben een reden, betrokken bronpassage/functie en waar nodig contextafhankelijkheden. Geen stilzwijgende afwijzing, verdwijning of geforceerde klassekeuze. |
| Hypothese–annotatieovergang | De mapping naar beoordeelde annotaties en revisies blijft volledig herleidbaar, ook na afwijzingen, menselijke correcties en nieuwe runs; geen impliciete goedkeuring of verlies van historische besluiten. |
| AI-afhankelijkheid | Modelaanroepen en tokens per bepaling vergelijken bij dezelfde taak en juridische kwaliteit. Minder modelgebruik door gemiste functies of extra verborgen mensenwerk telt niet als winst. |
| Eindtoets | De vooraf vastgelegde, niet voor ontwikkeling gebruikte eindtoets ondersteunt de verbetering en is toereikend voor de concrete kwaliteitsclaim volgens §4.1. De pilotomvang of een onbesliste vergelijking is geen voldoende reden voor productie-invoering. |

Bij onbesliste resultaten blijft het onderdeel experimenteel en volgt aanvullende onafhankelijke beoordeling. Iedere invoerbare verbetering krijgt een uitschakelbare configuratie en versiegebonden herkomst; er ontstaat geen tweede permanente productiepipeline.

### 5.1 Vier PR's voor de proefimplementatie

Dit is uitsluitend de geplande werkverdeling; **nog geen PR beginnen** is de huidige uitvoeringsafspraak. Bij een latere start lopen de nulmeting, juridische beoordeling en meetinfrastructuur van stap A parallel aan deze PR's. Meetdefinities en het manifest staan vóór PR 1 vast. Iedere PR is afzonderlijk vergelijkbaar; de gecombineerde werking wordt daarna beoordeeld.

| PR | Afbakening op de huidige implementatie | Aantoonbare oplevering |
|---|---|---|
| **1. Bewijsmodel en hypothesen** | Breid `kandidaten.py`, fusie en de bestaande regelmetadata uit met waarnemingsidentiteit, afhankelijkheden, klassegebonden toepassingen en contextblokkades. Implementeer de hypothese-identiteit en beslismatrix uit §2.2–2.3 en leg de herkomstmapping van §3.1 vast bij het voorstel. Behoud bestaande detectorpatronen zoveel mogelijk en markeer niet-toewijsbare historische steun als gezamenlijk. Gebruik `UNCERTAIN`/`HUMAN_REVIEW` en bied de classifier uitsluitend expliciete alternatieven plus onbeslist aan. | Trace en beslisregister bewaren ondersteuning, tegenbewijs en ontbrekende kennis. Duplicatie en herordening van bewijs veranderen de deterministische beslissing en canonieke classifierinvoer niet. Verschillende interpretaties blijven onderscheiden. Historische traces blijven leesbaar. Gedragswijzigingen draaien alleen in de proefroute. |
| **2. Gerichte frames** | Bouw op `taal/model.py` en `taal/afgeleid.py`: predicaten, tijdsconstructies, ingebedde operatorscopes, negatie/uitzonderingen en gerichte contextafhankelijkheden. | IW01 en andere ontwikkelgevallen tonen operanden, bereik en alternatieven; parseruitval en benodigde context blijven zichtbaar. Klassen en gold-spans worden niet uit het voorbeeld afgedwongen. |
| **3. Juridische relatievoorstellen** | Voeg getypeerde relaties en hun bewijs toe aan proefbatch, opslag, revisies en export. Houd juridische functie, relatierol en methodeprofiel gescheiden. | Relaties zijn herleidbaar tot hypothesen en actuele eindpunten. Correcties heropenen getroffen relaties, zonder historie te verliezen. Relatie-evaluatie is beschikbaar vóór de UI-oplevering. |
| **4. Beoordelingsinterface en kwaliteitsdiagnose** | Breid het bestaande annotatiepaneel en de dekkingsweergave uit met bewijsafhankelijkheden, scope, relatiebeslissingen en onopgeloste functies. Sluit aan op de bestaande kandidaat- en structurele dekkingsregistratie. | Juristen kunnen classificatie en samenhang afzonderlijk beoordelen. Correcties, actieve beoordelingstijd en uitkomsten reizen door audit en export mee. Geen automatische productiepromotie. |

**Eerste concrete oplevering:** een geadjudiceerde nulmeting en een werkende proef met bewijs per klassehypothese. Die combinatie bepaalt welke frames en detectorverbeteringen daadwerkelijk nodig zijn.
