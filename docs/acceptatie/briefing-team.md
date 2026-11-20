# Briefing voor het team

De ene ingang voor de agent-jurist, de agent-gegevensspecialist en de agent-regelspecialist. Lees bij de start alleen
dit en het dossier; de rest haal je op als een stap erom vraagt (zie *Bronnen op aanvraag*). De vorige run las per agent meer dan
600.000 tokens context in, en het meeste daarvan is nooit gebruikt.

## De opdracht in het kort

Jullie voeren samen op acceptatie een wetsanalyse uit met Lex, nemen de beslissingen zelf en beoordelen daarna het
resultaat en de werkplek. De stappen, wie trekt en waar jullie moeten overleggen staan in
`docs/acceptatie/wetsanalyse-e2e.md`: lees daar de tabel *Wie doet wat* en de stap die aan de beurt is.

Lex dekt activiteit 1, activiteit 2 en het begin van activiteit 3. De methode vraagt meer: afleidingsregels opstellen
(deelactiviteit 3b), valideren en uitvoeringsbeleid signaleren doen jullie zelf in het rapport. Dat de werkplek daar
niets voor heeft, is een bevinding.

## Wie is wie

- **De agent-jurist** is eigenaar van de betekenis: het werkgebied, de bronselectie, de markeringen en de relaties
  ertussen. Hij trekt stap 1 tot en met 3.
- **De agent-gegevensspecialist** is eigenaar van de eenduidigheid en de aansluiting op gegevensmodellen. Hij trekt
  de begrippen (stap 4).
- **De agent-regelspecialist** is eigenaar van de uitvoerbaarheid. Hij zet na de annotatie de stap naar
  afleidingsregels (3b): per regel een regelskelet, de toets of de relaties volledig genoeg zijn om de regel uit te
  voeren, de regel in gestructureerde natuurlijke taal of als beslistabel, en voorbeeldreeksen die hem doorrekenen.
  Een gat in het skelet legt hij bij de jurist, een ontbrekend begrip bij de gegevensspecialist. RegelSpraak hoort
  niet bij het platform en ook niet bij deze test.

Voor de afleidingsregels volgen jullie alle drie de skill (werkstroom F, `references/afleidingsregels.md`). De regels
waar het team het vaakst over valt, kort (bij verschil gaat de reference voor):
- **Geen begrip zonder grondslag.** Elk begrip rust op een passage; de api weigert een begrip zonder. Een
  tussenresultaat zonder eigen formulering krijgt wél een begrip, op de markering van de afleidingsregel die het
  afleidt, met de koppelrol `afgeleid`.
- **Eén regel per uitvoer.** Verschilt de afleiding per geval, dan is het één beslistabel met rijen die elkaar
  uitsluiten. Een formulering die twee waarden oplevert, draagt twee regels en twee markeringen als Afleidingsregel.
- **Waarop een regel rust.** Een beslisregel over een recht rust op de Rechtsbetrekking en hoeft niet als
  Afleidingsregel gemarkeerd te zijn. Op een contextbron rust geen regel.
- **Operatoren en tijd.** Een operatorbegrip ontstaat bij een gemarkeerde formulering en wordt daarna generiek
  hergebruikt; er zijn geen operatorbegrippen vooraf. "Zes weken na" is een Tijdsaanduiding, geen operator.
- **Parameters.** De regel gebruikt de parameter; de parameterwaarde is een eigen begrip in haar tijdvak en staat niet
  in de definitie van de parameter.

## Alleen de methode wetsanalyse

Jullie werken uitsluitend met de methode **wetsanalyse**: het werkgebied, markeren en classificeren in de dertien
JAS-klassen, de samenhang tussen markeringen en de begrippen volgens NL-SBB. De methode **wetsuitvoering** (het
Juridisch Referentiemodel, JRM: juridische scenario's, aktes, de juridische toestand, rechtsgevolgen en juridisch
relevante feiten) gebruiken jullie niet. Lex houdt de twee strikt gescheiden (besluit 13 nov 2026,
`docs/architectuur/plan-methodes-scheiden.md`), en deze acceptatietest toetst alleen wetsanalyse. Laad dus de skill
`wetsuitvoering` niet, vraag Lex niet om een scenario of akte, en beoordeel de werkplek niet op wat het JRM zou vragen.
Een praktijkvoorbeeld toets je als toetsgeval tegen de bronnen en de begrippen, niet als JRM-scenario.

## Lex op 15 nov 2026

Wat er sinds de vorige run veranderde, en wat je in de werkplek tegenkomt:

- **De centrale agent.** Een vraag die geen vaste route pakt, beantwoordt één centrale agent (ADR-016); de supervisor
  en de keuze tussen specialisten zijn weg. Voor groter werk stelt hij **subagents** op met een taakprofiel, onder
  andere `rechtspraak_lezen` (uitspraken bij een bepaling, per uitspraak de kern met een passage),
  `wetsgeschiedenis_lezen` (memorie van toelichting, nota's, amendementen, de bekendmaking) en `bepalingen_duiden`
  (een reeks bepalingen naast elkaar). Elke subagent levert een rapport; wat hij niet zelf kan beslissen komt als
  **vraag naar boven**, gebundeld aan het eind van de beurt met een keuzekaart per vraag (opgeleverd, wacht op jou,
  mislukt of niet aan bod). Beantwoord zo'n kaart met haar actie. Een kind dat op zijn rondegrens stopt, stelt nog
  geen vraag: noteer het als bevinding als stukken ongelezen blijven.
- **Bronnen naast de wet.** Lex leest naast de graaf ook connectors (onder meer rechtspraak, kamerstukken,
  bekendmakingen), aan of uit per gesprek via het bronnenmenu of `/bron`. Een antwoord daaruit is een citaat van die
  bron, geen wettekst: scheid ze in je oordeel.
- **Het denkproces staat bovenaan** elke beurt, ingeklapt, ook bij een annotatie. Daar lees je welke route, agent of
  subagent werkte en welke bron (graaf, connector) iets opleverde. Er is geen apart toolblok meer.
- **Werkplek-commando's.** Een `/` vooraan in het invoerveld opent de commando's: dezelfde vaste handelingen als de
  suggesties (zonder modelstap voor de route), zoals `/deelvragen`, `/bronnen`, `/bepaling`, `/annoteer`,
  `/begrippen`, `/meedenken`, `/dekking`, en bij een begrip `/uitwerken`, `/brondefinitie`, `/uitleg`, `/voorbeelden`,
  `/relaties`. Zonder beurt: `/nieuw`, `/bron`, `/context` en `/help`. Via de MCP stuur je dezelfde `actie` mee.
- **De bronselectie per deelvraag** (`docs/architectuur/bronselectie-per-deelvraag.md`). Lex werkt de deelvragen één
  voor één af: een compact kaartje per fase (de kernbepalingen, wat eraan hangt), het paneel waar je opneemt of
  uitsluit, *Klaar*, afronden en *Hoe wil je verder?*. De stand per deelvraag (niet gestart, in behandeling, voorlopig
  afgerond, beoordeeld) staat bij de api. Een bron is één selectie met een rol per deelvraag; uitsluiten geldt per
  deelvraag.
- **Begrippen volgens NL-SBB.** Een begripskaart met de term en de vier velden (definitie, uitleg op B1, toelichting,
  voorbeeld), gekoppeld aan de
  dragende passages, met revisies, relaties (kwalificatie, inclusie, uitsluiting, soort van, verwant), opvolgers,
  generieke begrippen boven het werkgebied (ADR-006), conformiteit (diagnostisch) en de Turtle-export.
- **Instellingen › Aanpassingen.** Wat Lex gebruikt staat in het instellingenvenster onder *Aanpassingen*: Methodes
  (de skills), Agents (de agentprofielen, met het model), Connectors en Modellen. De pagina *Werkwijze* bestaat niet
  meer; `/werkwijze` verwijst door. Kijk daar welk profiel en welke methode een agent gebruikt als je een antwoord
  beoordeelt.

## Samenwerken

- **Tegelijk, niet na elkaar.** Jullie werken vanaf stap 1 samen; de regelspecialist leest tot de annotatie mee.
  Praat rechtstreeks met `SendMessage`, met de agent-id's die de coördinator je geeft. Heb je niets te doen tot de
  ander reageert, stuur dan je vraag en beëindig je beurt: het antwoord wekt je weer. Vraag niet via de coördinator wat je aan elkaar kunt vragen.
- **Het logboek is het gedeelde geheugen.** Alles wat de ander moet kunnen terugvinden gaat met `logboek_aanvullen`
  in het logboek: beslissingen met reden, id's (`run_id`, `trace_id`, werkgebied, element, begrip), overleg,
  bevindingen en omwegen. Lees bij het begin van een stap met `logboek_lezen`, en geef de teruggekregen `vanaf`
  mee om alleen het nieuwe te lezen. Een bericht verdwijnt; het logboek blijft. Het kan alleen aanvullen: een
  vergissing herstel je met een nieuwe regel.
- **Oneens is geen probleem.** De jurist is eigenaar van de betekenis, de gegevensspecialist van de eenduidigheid en
  de aansluiting, de regelspecialist van de uitvoerbaarheid. Geef niet toe om sneller klaar te zijn: leg het vast met
  soort `onenigheid`, dat het argument van elke kant vraagt (`argumenten`, per rol, minstens twee). Lukt het niet, dan beslist de eigenaar en blijft de onenigheid staan voor het rapport.
- **Elk een eigen gesprek.** Een run hoort bij een gesprek en een 409 betekent dat er nog een loopt. Wie een stap trekt
  gebruikt het gesprek van die stap; de ander opent een eigen gesprek voor eigen vragen. De stand van de bronselectie
  staat bij de api, dus dat breekt niets.
- **Jullie delen misschien een account.** Begin daarom de reden van elke beslissing met `[jurist]`,
  `[gegevensspecialist]` of `[regelspecialist]`, zodat de audit laat zien wie wat besloot.

## Lex bedienen

- **Laat Lex eerst voorstellen,** ook als je het antwoord al weet, anders test je jezelf en niet Lex. Beoordeel het
  voorstel daarna kritisch.
- **Gebruik de vaste weg.** Beantwoord een vraagkaart met de `intake_actie` die de kaart aanbiedt en een suggestie met
  haar `actie`, zoals een klik dat doet. Lees de events: vraagkaart, artefact, bevestiging, grounding.
- **Bevestig bewust.** Lex annoteert pas na een bevestiging met het aantal dat je zag (`bevestigd`).
- **Stel goede vragen.** Eén onderwerp per vraag, met `werkgebied_id` en de bepaling erbij. De graaf bevat wet- en
  regelgeving; jurisprudentie en kamerstukken komen alleen via een connector die aan staat, en het denkproces zegt
  welke bron gebruikt is.
- **Gebruik de commando's** waar een vaste handeling bestaat, in plaats van een vrije vraag: dat is goedkoper en
  herhaalbaar. Een vrije vraag gaat naar de centrale agent.
- **Lees het aandachtsniveau.** Groen is geen goedkeuring: steekproef ook bij groen, en lees geel volledig.

## Bewijs tegen de bron

Een bevinding over brontekst rust op de officiële XML, niet op wat Lex zegt en niet op een samenvatting. Een eerdere
bevinding bleek fout omdat ze op de samenvatting van een webpagina stond, die de structuur niet ziet.

- `bron_lezen` geeft de XML en de tekst van één artikel of lid uit de officiële repository, met de toestand en de
  url. Zet die url bij de bevinding. Zonder peildatum krijg je de nieuwste toestand, dezelfde die de importer gebruikt.
- `graaf_lezen` toont met alleen-lezen SPARQL wat er in de graaf staat. Bron tegen graaf vergelijken is beoordelen.
  Vraag wat een gebruiker aan Lex vraagt gewoon aan Lex.
- Weigert de repository (geen XML, een botcontrole), noteer dat en stop daar. Probeer geen andere identificatie,
  geen andere weg en geen WebFetch als vervanger.
- Niet getoetst tegen de XML? Dan heet het zo in je bevinding, en is hij hooguit een vermoeden.

## Zuinig met context

In de run van 16 nov 2026 liepen vier agents vast op hun eigen contextruimte, niet op het budget van Lex: sommige
antwoorden van de api waren te groot (zie het verslag, B-1). Daarvoor bestaan nu compacte vormen, die je zelf kiest:

- **`werkgebied_lezen`** geeft standaard een overzicht: dossier, dekking, tellingen per bepaling, klasse en
  lifecycle, en de nieuwste auditregels. Met `bron_iri` krijg je de elementen van die bepaling in korte vorm;
  `volledig: true` geeft alles en is groot.
- **`weergave_lezen`** (`bron_iri`) geeft de annotatie van één bepaling als lijst, om te beoordelen. Dat is dezelfde
  route als `bff` GET `/api/annotatie/v2/weergave?bron_iri=…&vorm=lijst`.
- **De bronselectie** heeft de vorm `?vorm=deelvraag` op elk besluit, elke status en het overzicht. Daarmee komt
  alleen de geraakte deelvraag volledig terug, en de andere alleen met hun stand. Gebruik `GET …/kandidaten` met
  `?deelvraag_id=`.
- **Een wijziging aan een begrip** (PATCH, accorderen, heropenen, een voorstel overnemen) heeft `?vorm=stand`: dan
  komen de stand en de inhoud terug, niet de hele kaart.
- **Vraag met `bron_lezen` één lid tegelijk** (`lid`), niet een heel artikel.
- **Werk één bepaling tegelijk af:** lezen, toetsen, beslissen, loggen, en dan de volgende. Lees het logboek met
  `vanaf`.
- **Selecteer de leden die je nodig hebt.** Een artikel in de selectie annoteert al zijn leden.

## Routes

De `bff`-routes die het team het meest gebruikt, met voorbeeldbody's, staan in
[`tools/wetsanalyse-acceptatie-mcp/README.md`](../../tools/wetsanalyse-acceptatie-mcp/README.md) §*Routes voor `bff`*.
Lees die tabel vóór je een pad raadt. Schrijfroutes kennen `?vorm=stand` of `kort`: vraag die vorm, anders komt de hele
lijst terug. Een onbekend pad geeft een 404 als JSON.

## Omwegen

Je gebruikt wat een gebruiker kan: een vraagkaart, een suggestie, een bevestiging, of een `bff`-route die een scherm ook
aanroept. Loopt de vaste weg vast en zou je een route zonder scherm nodig hebben, dan **stop je daar eerst**. Noteer
in het logboek met soort `omweg` wat vastliep en welke route je zou nemen, en vraag de coördinator (`to: "main"`) wat je
doet. Gebruik je die route daarna met toestemming, dan blijft het een bevinding: de omweg lost niets op, hij verbergt
alleen wat je moest vinden.

## Grenzen

- Alles alleen op acceptatie. Productie valt erbuiten: geen tag, geen promote.
- Jullie maken geen accounts, halen geen wachtwoorden of tokens op en zetten geen configuratie. Ontbreekt er toegang,
  zoals Grafana of de graaf, dan is die stap niet uitgevoerd en meld je dat. Tokens komen ook niet in het logboek.
- Je wijzigt geen code. Dossierinhoud en interne namen horen alleen in `docs/acceptatie/lokaal/`, want de repo is
  publiek.
- Citeer het boek, de handleiding en de leidraad niet letterlijk: die zijn van derden.

## De dertien klassen

Rechtssubject, Rechtsobject, Rechtsbetrekking, Rechtsfeit, Voorwaarde, Afleidingsregel, Variabele en variabelewaarde,
Parameter en parameterwaarde, Operator, Tijdsaanduiding, Plaatsaanduiding, Delegatiebevoegdheid en
delegatie-invulling, Brondefinitie. Verzin er geen bij.

## Bronnen op aanvraag

Haal op wat de stap nodig heeft, niet alles vooraf. Laad de skill `wetsanalyse` als je gaat markeren of beoordelen. De
`references/` staan in `.claude/skills/wetsanalyse/`.

| als je dit doet | lees dan |
|---|---|
| het werkgebied en de deelvragen bepalen | `references/deelvragen-en-bronnen.md`, `references/analyseprotocol.md` |
| bronnen zoeken en kiezen | `references/zoekvragen-bronselectie.md`, `references/verwijzingen-volgen.md`, `docs/architectuur/bronselectie-per-deelvraag.md` |
| markeringen beoordelen | `references/jas-klassen-referentie.md`, `references/markeren-fragmentgrenzen.md`, `references/relaties.md` |
| twijfelen aan een klasse | `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md`, `H3-Kader.md` |
| begrippen uitwerken | `references/begrippen.md`, `references/nl-sbb-en-b1.md`, `docs/architectuur/adr-003-nl-sbb-begrippencontract.md` |
| betekenisgroepen of generieke begrippen beoordelen | `docs/architectuur/adr-004-begrippenketen.md`, `adr-006-generieke-begrippen.md` |
| afleidingsregels opstellen en doorrekenen | `references/afleidingsregels.md`, `references/relaties.md` (*Het regelskelet*), `references/jas-klassen-referentie.md` §6–§9, `references/analyseprotocol.md` §5, `docs/architectuur/plan-afleidingsregels.md` (§2 de methode, §4 de proef Termijnen; waar die van de skill verschilt, gaat de skill voor) |
| de kwaliteit beoordelen en rapporteren | `references/kwaliteit.md` |
| de methode zelf nazoeken | `docs/wetsanalyse/methode-onderzoek.md`; lokaal ook `wetsanalyse-boek.md`, `handleiding.pages.md`, `leidraad.pages.md` |
| weten wat Lex kan | `tools/graph-qa/CLAUDE.md`, en `ACTIE_TAAK` in `tools/graph-qa/agent/models.py` voor de vaste acties |
| een subagent of zijn profiel beoordelen | `.claude/lex-agents/<naam>.md`, `docs/architectuur/adr-016-centrale-agent-en-werkplaats.md` §A4 (vragen naar boven) |
| de commando's nakijken | `frontend/CLAUDE.md` §*Commando's in het invoerveld*, `frontend/lib/vraagLex.ts` |
| weten wat een scherm doet | `frontend/CLAUDE.md`; of een route een scherm heeft, zie je aan een aanroeper in `frontend/` |
| de tools van de MCP nakijken | `tools/wetsanalyse-acceptatie-mcp/README.md` |
