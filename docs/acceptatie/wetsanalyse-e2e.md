# Scenario: een wetsanalyse van begin tot eind

Een multidisciplinair team van agents doorloopt met `tools/wetsanalyse-acceptatie-mcp` een echte wetsanalyse op
acceptatie, neemt alle beslissingen zelf en beoordeelt daarna wat eruit komt: de agent-jurist
(`.claude/agents/agent-jurist.md`) en de agent-gegevensspecialist (`.claude/agents/agent-gegevensspecialist.md`).
De sessie die hen start coördineert: zij geeft het dossier door en voegt de rapporten samen. Het dossier komt uit `docs/acceptatie/lokaal/` (gitignored): zulke dossiers noemen interne teams en
systemen, en deze repo is publiek. Staat het bestand er niet, vraag het dan aan de gebruiker.

Echte beurten kosten echte tokens. Annoteer daarom onder één deelvraag, tenzij de opdracht anders zegt.

## Vooraf

1. `wie_ben_ik` toont het testaccount met de rol `analist`.
2. Noteer het tokenverbruik: `bff` GET `/api/account/verbruik`.

## Stappen

**1. Werkgebied (jurist, gegevensspecialist beoordeelt).** Maak een gesprek (`bff` POST `/api/gesprekken`) en begin met "Ik wil een wetsanalyse
uitvoeren". Beantwoord elke vraagkaart met de `intake_actie` die de kaart aanbiedt.

- Neem uit het dossier letterlijk over wat erin staat. Kies bij aanleiding en doel de opties die erbij horen.
- Vul de rest zelf aan: naam (`acc-test-<onderwerp>-<datum>`), deelvragen, wat erbuiten valt, regelingen en
  gebeurtenis. Kijk eerst wat Lex voorstelt, en noteer per veld wat van jou komt.
- Een praktijkvoorbeeld verzin je niet.

Bewijs: `werkgebied_lezen` toont de velden uit het dossier letterlijk, en de audit toont de aanmaak.

**2. Bronselectie (jurist).** Vraag Lex de bronnen te bepalen en werk de deelvragen één voor één af: opnemen of
uitsluiten, *Klaar*, afronden.

Bewijs: de stand per deelvraag komt van de api, niet uit het gesprek. Elke bron is herleidbaar tot een
bepaling, en de dekking toont alle deelvragen.

**3. Annoteren (jurist).** Vraag de annotatie van de bronnen onder één deelvraag. Bevestig pas nadat Lex het aantal
noemt, en stuur dat aantal mee (`bevestigd`).

Bewijs: de elementen staan in de inventaris, en `annotatie_lezen` toont ze ook in de graaf.

**4. Begrippen (gegevensspecialist, jurist beoordeelt).** Laat Lex begrippen voorstellen, werk ze uit en leg de
relaties. Een begrip wordt pas geaccordeerd als beide agents akkoord zijn.

Bewijs: `begrip_lezen` toont de kaart met koppelingen naar passages, de revisies, de conformiteit en de samenhang.
De Turtle-export (`bff` GET `.../begrippen/export?formaat=ttl`) stemt overeen met de graaf.

**5. Beslissen (beide).** Beoordeel de annotaties en begrippen: goedkeuren, aanpassen, afwijzen of zelf markeren,
en accordeer de begrippen die af zijn. Dit zijn echte beslissingen, met een reden.

Bewijs: de beslissing staat in de audit en komt terug in de laag en de graaf.

**6. Valideren en aansluiten (beide).** Toets elk praktijkvoorbeeld als scenario: volgt de uitkomst uit de bronnen,
en is elk feit in de begrippen vast te leggen? De gegevensspecialist maakt een eerste mapping naar het gegevensmodel,
als dat in `docs/acceptatie/lokaal/` staat; anders een lijst met vragen.

**7. Uitlezen en beoordelen (beide).** Zie hieronder.

**8. Bewijzen in de logs.** `logs_zoek` op een `trace_id` en een `run_id` uit de stappen. Telemetrie loopt
enkele minuten achter. Controleer ook of de foutenlijst niets nieuws toont.

**9. Laten staan.** Het werkgebied blijft staan: het is bewijs, en de volgende iteratie vergelijkt ermee. Een
nieuwe iteratie krijgt een eigen werkgebied met een eigen datum.

## Beoordelen

**Controles die vastliggen.** Eén afwijking is een bevinding.

- Het citaat van elk element staat letterlijk in de bron, op de plek van het anker.
- De `bronreferentie` wijst naar de juiste bepaling.
- De klasse is een van de dertien uit `api/app/jas_klassen.py`.
- Elke deelvraag heeft dekking, of een benoemd gat.
- Het dossier bevat niets wat niet is ingevoerd of overgenomen.
- Wat Lex een voorstel noemt, is nog een voorstel: er is niets stil beslist.

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

Schrijf per run een rapport naar `docs/acceptatie/lokaal/` (gitignored), dus niet in de repo en niet online. De
sessie die het team startte schrijft het; de agents leveren de inhoud.

- per stap het bewijs, met `trace_id` en `run_id`;
- wat er zelf is aangevuld;
- de beslissingen die zijn genomen, met reden;
- waar de agents het oneens waren, met beide argumenten;
- per praktijkvoorbeeld de uitkomst en de gaten in de begrippen, en de aansluiting op het gegevensmodel;
- de bevindingen, gesplitst in vastliggende controles en inhoudelijk oordeel, elk met soort en zwaarte;
- wat er is verbeterd sinds de vorige iteratie, en wat niet;
- het tokenverbruik;
- wat niet getest is, in elk geval de rendering.
