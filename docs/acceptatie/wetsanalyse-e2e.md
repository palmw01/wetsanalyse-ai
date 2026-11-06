# Scenario: een wetsanalyse van begin tot eind

Een multidisciplinair team van agents doorloopt met `tools/wetsanalyse-acceptatie-mcp` een echte wetsanalyse op
acceptatie, neemt alle beslissingen zelf en beoordeelt daarna wat eruit komt: de agent-jurist
(`.claude/agents/agent-jurist.md`) en de agent-gegevensspecialist (`.claude/agents/agent-gegevensspecialist.md`).
Ze werken vanaf stap 1 samen en overleggen rechtstreeks. De sessie die hen start coördineert: zij start het team,
beantwoordt vragen over omwegen en voegt de rapporten samen. Ze is geen doorgeefluik.

Het dossier komt uit `docs/acceptatie/lokaal/` (gitignored): zulke dossiers noemen interne teams en systemen, en deze
repo is publiek. Staat het bestand er niet, vraag het dan aan de gebruiker. Die map staat alleen in de hoofdcheckout;
draait de sessie in een worktree, geef dan het absolute pad door.

Echte beurten kosten echte tokens. Annoteer daarom onder één deelvraag, tenzij de opdracht anders zegt.

## Vooraf

De coördinator doet dit, vóór het team start. De agents maken geen accounts en halen geen wachtwoorden of tokens op,
ook niet uit een kluis: ontbreekt er iets, dan vraagt de coördinator het de gebruiker.

1. `wie_ben_ik` toont het account dat de gebruiker voor deze run koos. Dat is tot nu toe een gedeeld account met de rol
   `beheerder`, bewust gekozen. Noteer account en rol in het logboek: bij die keuze zijn analist-rechten niet getoetst
   en staat al het verbruik op dat account, dus dat hoort als beperking in het rapport. Een apart analistaccount
   maakt alleen de gebruiker aan.
2. Noteer het tokenverbruik: `bff` GET `/api/account/verbruik`.
3. Probeer de tools die stap 7 en 8 dragen: `logs_zoek` zonder argumenten, `graaf_lezen` met een `ASK`, en `bron_lezen`
   op een bepaling uit het dossier. Weigert `logs_zoek` of `graaf_lezen` omdat de toegang ontbreekt, leg dat dan voor
   aan de gebruiker voordat de run begint: de `WETSANALYSE_ACC_GRAFANA_*`- en `WETSANALYSE_ACC_GRAAF_*`-variabelen staan
   in de README van de MCP. Gaat de run zonder door, dan is die controle niet gedaan en staat dat in het rapport.
4. Kies de naam van de run, bijvoorbeeld `<onderwerp>-<datum>`. Het logboek staat daarna in
   `docs/acceptatie/lokaal/<run>/logboek.md`; open het met `logboek_aanvullen`, met de stand uit punt 1 tot en met 3.

## Het team starten

Start beide agents in één bericht, zodat ze tegelijk beginnen, en geef elk de naam van de run en het dossier. Elke start
geeft een agent-id terug: stuur die daarna met `SendMessage` naar de ander. Vanaf dan praten ze rechtstreeks. Komt
een bericht niet aan, dan loopt het overleg via het logboek en is dat een bevinding over de opzet.

## Wie doet wat

Wie een stap trekt voert hem uit en beslist bij twijfel. De meekijker werkt tegelijk mee aan wat in de kolom staat, in
een eigen gesprek voor vragen aan Lex. Een stap is pas af als het overleg in het logboek staat.

| stap | trekker | meekijker doet | verplicht overleg |
|---|---|---|---|
| 1 werkgebied | jurist | leest deelvragen en voorbeelden op objecten, feiten en gebeurtenissen | **vóór stap 2:** de specialist beoordeelt elke deelvraag op gegevens; de jurist past aan of legt uit waarom niet |
| 2 bronselectie | jurist | zoekt per deelvraag welke bepalingen de gegevens dragen | vóór het afronden van een deelvraag: ontbreekt er een bron voor een gegeven? |
| 3 annoteren | jurist | leest de gegevensdragende klassen, noteert basisformuleringen, homoniemen en synoniemen | vóór stap 4: welke termen worden begrippen, en waar zit dezelfde term met een andere betekenis? |
| 4 begrippen | gegevensspecialist | leest elke definitie tegen de passages en het recht | **tijdens de stap:** per begrip een juridisch akkoord van de jurist vóór accorderen |
| 5 beslissen | jurist de annotaties, specialist de begrippen | steekproef in het werk van de ander | bij elke afwijking in de steekproef |
| 6 valideren | jurist de uitkomst, specialist de feiten | de andere helft van hetzelfde voorbeeld | per praktijkvoorbeeld één gezamenlijke conclusie |
| 7 beoordelen | beide apart | leest daarna het oordeel van de ander | verschillen in oordeel als onenigheid vastleggen |
| 8 logs | gegevensspecialist | levert de `trace_id`'s en `run_id`'s uit het logboek | geen |

Onenigheid staat in het logboek met beide argumenten (soort `onenigheid`). Komen jullie er niet uit, dan beslist de
eigenaar: de jurist over de betekenis, de specialist over eenduidigheid en aansluiting.

## Stappen

**1. Werkgebied.** Maak een gesprek (`bff` POST `/api/gesprekken`) en begin met "Ik wil een wetsanalyse
uitvoeren". Beantwoord elke vraagkaart met de `intake_actie` die de kaart aanbiedt.

- Neem uit het dossier letterlijk over wat erin staat. Kies bij aanleiding en doel de opties die erbij horen.
- Vul de rest zelf aan: naam (`acc-test-<onderwerp>-<datum>`), deelvragen, wat erbuiten valt, regelingen en
  gebeurtenis. Kijk eerst wat Lex voorstelt, en noteer per veld wat van jou komt.
- Een praktijkvoorbeeld verzin je niet.

Bewijs: `werkgebied_lezen` toont de velden uit het dossier letterlijk, en de audit toont de aanmaak. Het oordeel van de
specialist over de deelvragen staat in het logboek.

**2. Bronselectie.** Vraag Lex de bronnen te bepalen en werk de deelvragen één voor één af: opnemen of
uitsluiten, *Klaar*, afronden.

Bewijs: de stand per deelvraag komt van de api, niet uit het gesprek. Elke bron is herleidbaar tot een
bepaling, en de dekking toont alle deelvragen.

**3. Annoteren.** Vraag de annotatie van de bronnen onder één deelvraag. Bevestig pas nadat Lex het aantal
noemt, en stuur dat aantal mee (`bevestigd`).

Bewijs: de elementen staan in de inventaris, en `annotatie_lezen` toont ze ook in de graaf.

**4. Begrippen.** Laat Lex begrippen voorstellen, werk ze uit en leg de relaties. Een begrip wordt pas geaccordeerd
als beide agents akkoord zijn.

Bewijs: `begrip_lezen` toont de kaart met koppelingen naar passages, de revisies, de conformiteit en de samenhang.
De Turtle-export (`bff` GET `.../begrippen/export?formaat=ttl`) stemt overeen met de graaf.

**5. Beslissen.** Beoordeel de annotaties en begrippen: goedkeuren, aanpassen, afwijzen of zelf markeren,
en accordeer de begrippen die af zijn. Dit zijn echte beslissingen, met een reden.

Bewijs: de beslissing staat in de audit en komt terug in de laag en de graaf.

**6. Valideren en aansluiten.** Toets elk praktijkvoorbeeld als scenario: volgt de uitkomst uit de bronnen,
en is elk feit in de begrippen vast te leggen? De gegevensspecialist maakt een eerste mapping naar het gegevensmodel,
als dat in `docs/acceptatie/lokaal/` staat; anders een lijst met vragen.

**7. Uitlezen en beoordelen.** Zie hieronder.

**8. Bewijzen in de logs.** `logs_zoek` op een `trace_id` en een `run_id` uit het logboek. Telemetrie loopt
enkele minuten achter. Controleer ook of de foutenlijst niets nieuws toont. Deze stap vereist Grafana-toegang: die
zet de gebruiker klaar (zie *Vooraf*). Zonder die toegang is de stap niet uitgevoerd. De `trace_id`'s en `run_id`'s
blijven in het logboek staan, zodat hij achteraf kan.

**9. Laten staan.** Het werkgebied blijft staan: het is bewijs, en de volgende iteratie vergelijkt ermee. Een
nieuwe iteratie krijgt een eigen werkgebied met een eigen datum en een eigen logboek.

## Beoordelen

**Controles die vastliggen.** Eén afwijking is een bevinding.

- Het citaat van elk element staat letterlijk in de bron, op de plek van het anker. Toets dat met `bron_lezen`.
- De `bronreferentie` wijst naar de juiste bepaling.
- De klasse is een van de dertien uit `api/app/jas_klassen.py`.
- Elke deelvraag heeft dekking, of een benoemd gat.
- Het dossier bevat niets wat niet is ingevoerd of overgenomen.
- Wat Lex een voorstel noemt, is nog een voorstel: er is niets stil beslist.
- Een bevinding over brontekst noemt de toestand-url uit `bron_lezen`, of heet niet getoetst.
- Elke route zonder scherm staat als `omweg` in het logboek, ook als er daarna toestemming voor kwam.

**Inhoudelijk oordeel.** Beoordeel een steekproef tegen de `wetsanalyse`-skill: klasse en fragmentgrenzen, en
of een definitie op haar passages rust. Geef per bevinding het artikel, het citaat, het argument en je
zekerheid. Beoordeel niet alleen de uitkomst maar ook de weg: waar moest je omlopen, wat ontbrak, wat kostte
onnodig veel beurten of tokens, en wat zou een jurist niet begrijpen.

Toets op eigenschappen en niet op exacte tekst: annotatieruns verschillen sterk. Dit is ook geen blinde meting
van de zoekkwaliteit als het onderwerp al in de ontwikkelsets zit.

## Verbeteren

Elke bevinding krijgt een soort en een zwaarte:

- **Inhoud van deze analyse:** direct herstellen met een beslissing op acceptatie.
- **Fout in Lex of de werkplek:** de oorzaak repareren in de repo, als eigen PR met een test. Volg de regel van
  ADR-001: kennis hoort in regels en tests, niet in prompts.
- **Vraag aan de gebruiker:** een inhoudelijke of productkeuze die niet aan de agent-jurist is.

Daarna draait de volgende iteratie op de nieuwe versie, met hetzelfde dossier en dezelfde deelvragen, en
vergelijkt met de vorige. Spreiding tussen runs is groot: een verbetering van de annotatieketen geldt pas na
minstens drie runs voor en drie na de wijziging. Stop bij het afgesproken aantal iteraties, of als een iteratie
geen nieuwe zware bevinding meer oplevert.

Productie valt buiten deze lus: geen tag, geen promote.

## Rapport

Schrijf per run een rapport naar `docs/acceptatie/lokaal/<run>/` (gitignored), dus niet in de repo en niet online, naast
het logboek. De sessie die het team startte schrijft het; de agents leveren de inhoud. Het logboek draagt de
details, dus het rapport verwijst ernaar in plaats van het te herhalen.

- per stap het bewijs, met `trace_id` en `run_id`;
- wat er zelf is aangevuld;
- de beslissingen die zijn genomen, met reden;
- waar de agents het oneens waren, met beide argumenten;
- de omwegen: wat vastliep, en wat er daarna mocht;
- per praktijkvoorbeeld de uitkomst en de gaten in de begrippen, en de aansluiting op het gegevensmodel;
- de bevindingen, gesplitst in vastliggende controles en inhoudelijk oordeel, elk met soort en zwaarte;
- wat er is verbeterd sinds de vorige iteratie, en wat niet;
- het tokenverbruik;
- wat niet getest is, in elk geval de rendering, en wat ontbrak aan toegang: analist-rechten bij een gedeeld
  beheerdersaccount, en de logs zonder Grafana.
