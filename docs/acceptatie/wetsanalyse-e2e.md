# Scenario: een wetsanalyse van begin tot eind

Doorloopt met `tools/wetsanalyse-acceptatie-mcp` een echte wetsanalyse op acceptatie, en beoordeelt wat eruit
komt. Het dossier komt uit `docs/acceptatie/lokaal/` (gitignored): zulke dossiers noemen interne teams en
systemen, en deze repo is publiek. Staat het bestand er niet, vraag het dan aan de gebruiker.

Echte beurten kosten echte tokens. Annoteer daarom onder één deelvraag, tenzij de opdracht anders zegt.

## Vooraf

1. `wie_ben_ik` toont het testaccount met de rol `analist`.
2. Noteer het tokenverbruik: `bff` GET `/api/account/verbruik`.

## Stappen

**1. Werkgebied.** Maak een gesprek (`bff` POST `/api/gesprekken`) en begin met "Ik wil een wetsanalyse
uitvoeren". Beantwoord elke vraagkaart met de `intake_actie` die de kaart aanbiedt.

- Neem uit het dossier letterlijk over wat erin staat. Kies bij aanleiding en doel de opties die erbij horen.
- Vul de rest zelf aan: naam (`acc-test-<onderwerp>-<datum>`), deelvragen, wat erbuiten valt, regelingen en
  gebeurtenis. Kijk eerst wat Lex voorstelt, en noteer per veld wat van jou komt.
- Een praktijkvoorbeeld verzin je niet.

Bewijs: `werkgebied_lezen` toont de velden uit het dossier letterlijk, en de audit toont de aanmaak.

**2. Bronselectie.** Vraag Lex de bronnen te bepalen en werk de deelvragen één voor één af: opnemen of
uitsluiten, *Klaar*, afronden.

Bewijs: de stand per deelvraag komt van de api, niet uit het gesprek. Elke bron is herleidbaar tot een
bepaling, en de dekking toont alle deelvragen.

**3. Annoteren.** Vraag de annotatie van de bronnen onder één deelvraag. Bevestig pas nadat Lex het aantal
noemt, en stuur dat aantal mee (`bevestigd`).

Bewijs: de elementen staan in de inventaris, en `annotatie_lezen` toont ze ook in de graaf.

**4. Begrippen.** Laat Lex begrippen voorstellen en werk er één uit.

Bewijs: `begrip_lezen` toont de kaart met koppelingen naar passages, en de revisies.

**5. Uitlezen en beoordelen.** Zie hieronder.

**6. Bewijzen in de logs.** `logs_zoek` op een `trace_id` en een `run_id` uit de stappen. Telemetrie loopt
enkele minuten achter. Controleer ook of de foutenlijst niets nieuws toont.

**7. Opruimen.** Verwijder het werkgebied en het gesprek, tenzij de gebruiker ze wil bekijken.

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
zekerheid. Dit is een tweede lezing en geen juridisch oordeel: accordeer niets namens een jurist. Eén
beslissing en één accordering op het testaccount testen alleen die route, en die staan apart in het rapport.

Toets op eigenschappen en niet op exacte tekst: annotatieruns verschillen sterk. Dit is ook geen blinde meting
van de zoekkwaliteit als het onderwerp al in de ontwikkelsets zit.

## Rapport

Publiceer per run een privé-artifact, niet in de repo:

- per stap het bewijs, met `trace_id` en `run_id`;
- wat er zelf is aangevuld;
- de bevindingen, gesplitst in vastliggende controles en inhoudelijk oordeel;
- het tokenverbruik;
- wat niet getest is, in elk geval de rendering.
