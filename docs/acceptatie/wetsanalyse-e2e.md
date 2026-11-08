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

## Vergelijken met een bestaande analyse

Ligt er van hetzelfde onderwerp al een analyse die buiten het platform is gemaakt, bijvoorbeeld een wiki-export
met per bepaling een tabel *Klasse | Formulering uit wettekst | Toelichting*, dan is die een referentie voor
stap 1 tot en met 3. Zo'n analyse is materiaal van derden. Ze staat met alles wat eruit komt in
`docs/acceptatie/lokaal/<naam>/`: de export, de referentie, de transcriptie van de diagrammen en het rapport.
Toets elk bestand met `git check-ignore -v`.

1. **Inlezen** (coördinator): `cd tools/graph-qa && uv run python -m eval.extern_dossier lees --export <map>
   --uit <lokaal>/referentie.json`. Geef met `--bronteksten` de wettekst uit `bron_lezen` mee, anders telt het
   citaat uit de export voor de letterlijkheid. Controleer de aantallen per bepaling met een steekproef tegen
   de pagina.
2. **Diagrammen**, als die er zijn: een plaatje bevat geen machinaal leesbare knopen. Schrijf de knopen
   (klasse, label, letterlijk/nee/impliciet) en de kanten (van, naar, type) één keer over naar
   `<lokaal>/relaties.json`, in de vorm die `lees_relaties` beschrijft, en laat de agent-jurist ze naast de tabel
   controleren. Verschillen tussen diagram en tabel zijn een bevinding over de referentie.
3. **Werkgebied**: de agent-jurist neemt analysevraag, deelvragen, praktijkvoorbeeld en wat erbuiten valt
   letterlijk over uit het dossier; wat er niet in staat (de gebeurtenis), vult hij aan en noteert hij.
4. **Relaties leggen en beoordelen** na stap 3 (ADR-011): de agent-jurist legt in de geannoteerde bepalingen de
   relaties tussen de markeringen, met de typen uit de catalogus (`.claude/skills/wetsanalyse/relaties.json`), en
   een impliciete partij waar de tekst er geen noemt. Hij beoordeelt elke relatie (goedkeuren of afwijzen, met een
   reden). Doe dat zonder naar de diagrammen van de referentie te kijken, anders meet je overschrijven. Bewaar per
   bepaling de weergave (`bff` GET `/api/annotatie/v2/weergave?…`) als `<lokaal>/weergaven/<bepaling>.json`.
5. **Vertaaltabel**, één keer per referentie: het team gebruikt een eigen notatie voor relaties. Leg in
   `<lokaal>/relatie-mapping.json` per teamtype vast welk catalogustype het is:

   ```json
   {"versie": 1, "typen": {
     "<teamtype>": {"type": "<code uit relaties.json>", "omgekeerd": false},
     "<teamtype in de andere richting>": {"type": "<code>", "omgekeerd": true},
     "<teamtype zonder catalogustype>": null,
     "<teamtype dat per klassenpaar verschilt>": {"regels": [
       {"van": "<klasse>", "naar": "<klasse>", "type": "<code>", "omgekeerd": false},
       {"van": "<klasse>", "naar": "<klasse>", "type": null}
     ]}
   }}
   ```

   Met `regels` kies je het catalogustype per klassenpaar van de kant. Een paar zonder regel telt als *niet in de
   tabel*. Twee knopen met dezelfde klasse en hetzelfde label op één bepaling zijn met de tekst niet uit elkaar te
   houden; die tellen als *niet meetbaar*.

   `omgekeerd` draait de richting om, als het team de kant andersom tekent dan de catalogus. `null` betekent geen
   catalogustype: regelinhoud of regelstructuur, die buiten activiteit 2 valt. Die kanten tellen apart
   (*buiten de catalogus*), net als teamtypen die niet in de tabel staan. Een code die de catalogus niet kent, is een
   fout. De tabel volgt de notatie van het team en blijft dus lokaal, naast de referentie.
6. **Vergelijken**: bewaar de uitvoer van `werkgebied_lezen` als `<lokaal>/werkgebied.json`, en draai
   `uv run python -m eval.extern_dossier vergelijk --referentie … --platform <lokaal>/werkgebied.json
   --werkgebied <lokaal>/werkgebied.json [--relaties <lokaal>/relaties.json] --uit <lokaal>/vergelijking.json`.
   Met `--weergaven <lokaal>/weergaven` (een map, of losse bestanden) en `--relatie-mapping
   <lokaal>/relatie-mapping.json` erbij, samen en alleen met `--relaties`, komen de relaties van het platform mee.
   Zonder die twee opties is de uitvoer zoals voorheen.
7. **Beoordelen**: de agent-jurist loopt de lijsten *gemist*, *klasse anders* en *alleen platform* door. Een gemist
   fragment kan anders begrensd maar juist zijn, een klasseverschil kan de export zijn die afwijkt van de skill.
   Bij de relaties loopt hij de kanten met uitkomst *gemist*, de relaties *alleen platform* en de regels die niet
   volledig zijn door. Elk oordeel komt met argument in het logboek.

Wat de vergelijking zegt:

- **Recall per klasse**, strikt over de fragmenten die letterlijk in de bron staan, ruim over alles. Een
  parafrase of los operatorwoord kan Lex niet zo markeren.
- **Bronselectie per deelvraag**, tegen de deelvraagnummers in de bronnentabel.
- **Eindpuntdekking van de relaties**: zijn beide eindpunten van een kant geannoteerd, met de juiste klasse op
  dezelfde plek?
- **Recall per catalogustype** (met weergaven en vertaaltabel): een kant van de referentie is *gevonden* als het
  platform een relatie van hetzelfde type heeft met passende eindpunten: dezelfde klasse en dezelfde plek, of bij een
  impliciete knoop een impliciete partij met dezelfde klasse. Een kant met een parafrase als eindpunt is *niet
  meetbaar* en telt niet mee in de recall. *Alleen platform* zijn de relaties op een bepaling die geen kant van de
  referentie raken, ter informatie.
- **Regelskelet**: per afleidingsregel van de referentie, heeft het platform de regel gemarkeerd, en zijn uitvoer,
  minstens één invoer en elke voorwaarde als relatie gelegd? Uitkomst *volledig*, *deels* of *niet*, met wat
  ontbreekt. Alleen kanten die op de catalogus te vertalen zijn, tellen mee.
- Uitgesplitst naar de status in de export (definitief of concept): een concept is een zwakkere referentie.

Het is één analyse, geen gold, en zit het onderwerp al in de ontwikkelsets, dan is het geen blinde meting. Wil je
de annotatieketen erop meten, maak dan lokaal een set in de vorm van `eval/golden_annotatie.jsonl`, met de
letterlijke fragmenten van de definitieve bepalingen als ankers. Draai die met `run_eval.py --annotatie --golden
<pad>` (kost geld, dus alleen na akkoord).

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
