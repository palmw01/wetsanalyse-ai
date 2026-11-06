# Briefing voor het team

De ene ingang voor de agent-jurist en de agent-gegevensspecialist. Lees bij de start alleen dit en het dossier;
de rest haal je op als een stap erom vraagt (zie *Bronnen op aanvraag*). De vorige run las per agent meer dan
600.000 tokens context in, en het meeste daarvan is nooit gebruikt.

## De opdracht in het kort

Jullie voeren samen op acceptatie een wetsanalyse uit met Lex, nemen de beslissingen zelf en beoordelen daarna het
resultaat en de werkplek. De stappen, wie trekt en waar jullie moeten overleggen staan in
`docs/acceptatie/wetsanalyse-e2e.md`: lees daar de tabel *Wie doet wat* en de stap die aan de beurt is.

Lex dekt activiteit 1, activiteit 2 en het begin van activiteit 3. De methode vraagt meer: valideren en
uitvoeringsbeleid signaleren doe je zelf in je rapport. Dat de werkplek daar niets voor heeft, is een bevinding.

## Samenwerken

- **Tegelijk, niet na elkaar.** Jullie werken vanaf stap 1 samen. Praat rechtstreeks met `SendMessage`, met het
  agent-id dat de coördinator je geeft. Heb je niets te doen tot de ander reageert, stuur dan je vraag en beëindig je
  beurt: het antwoord wekt je weer. Vraag niet via de coördinator wat je aan elkaar kunt vragen.
- **Het logboek is het gedeelde geheugen.** Alles wat de ander moet kunnen terugvinden gaat met `logboek_aanvullen`
  in het logboek: beslissingen met reden, id's (`run_id`, `trace_id`, werkgebied, element, begrip), overleg,
  bevindingen en omwegen. Lees bij het begin van een stap met `logboek_lezen`, en geef de teruggekregen `vanaf`
  mee om alleen het nieuwe te lezen. Een bericht verdwijnt; het logboek blijft. Het kan alleen aanvullen: een
  vergissing herstel je met een nieuwe regel.
- **Oneens is geen probleem.** De jurist is eigenaar van de betekenis, de gegevensspecialist van de eenduidigheid en
  de aansluiting. Geef niet toe om sneller klaar te zijn: leg het vast met soort `onenigheid`, dat beide argumenten
  vraagt. Lukt het niet, dan beslist de eigenaar en blijft de onenigheid staan voor het rapport.
- **Elk een eigen gesprek.** Een run hoort bij een gesprek en een 409 betekent dat er nog een loopt. Wie een stap trekt
  gebruikt het gesprek van die stap; de ander opent een eigen gesprek voor eigen vragen. De stand van de bronselectie
  staat bij de api, dus dat breekt niets.
- **Jullie delen misschien een account.** Begin daarom de reden van elke beslissing met `[jurist]` of
  `[gegevensspecialist]`, zodat de audit laat zien wie wat besloot.

## Lex bedienen

- **Laat Lex eerst voorstellen,** ook als je het antwoord al weet, anders test je jezelf en niet Lex. Beoordeel het
  voorstel daarna kritisch.
- **Gebruik de vaste weg.** Beantwoord een vraagkaart met de `intake_actie` die de kaart aanbiedt en een suggestie met
  haar `actie`, zoals een klik dat doet. Lees de events: vraagkaart, artefact, bevestiging, grounding.
- **Bevestig bewust.** Lex annoteert pas na een bevestiging met het aantal dat je zag (`bevestigd`).
- **Stel goede vragen.** Eén onderwerp per vraag, met `werkgebied_id` en de bepaling erbij. Lex antwoordt alleen uit
  de graaf; die bevat wet- en regelgeving, geen jurisprudentie of kamerstukken.
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
| markeringen beoordelen | `references/jas-klassen-referentie.md`, `references/markeren-fragmentgrenzen.md`, `references/jrm-verrijking.md` |
| twijfelen aan een klasse | `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md`, `H3-Kader.md` |
| begrippen uitwerken | `references/begrippen.md`, `references/nl-sbb-en-b1.md`, `docs/architectuur/adr-003-nl-sbb-begrippencontract.md` |
| betekenisgroepen of generieke begrippen beoordelen | `docs/architectuur/adr-004-begrippenketen.md`, `adr-006-generieke-begrippen.md` |
| de kwaliteit beoordelen en rapporteren | `references/kwaliteit.md` |
| de methode zelf nazoeken | `docs/wetsanalyse/methode-onderzoek.md`; lokaal ook `wetsanalyse-boek.md`, `handleiding.pages.md`, `leidraad.pages.md` |
| weten wat Lex kan | `tools/graph-qa/CLAUDE.md`, en `ACTIE_TAAK` in `tools/graph-qa/agent/models.py` voor de vaste acties |
| weten wat een scherm doet | `frontend/CLAUDE.md`; of een route een scherm heeft, zie je aan een aanroeper in `frontend/` |
| de tools van de MCP nakijken | `tools/wetsanalyse-acceptatie-mcp/README.md` |
