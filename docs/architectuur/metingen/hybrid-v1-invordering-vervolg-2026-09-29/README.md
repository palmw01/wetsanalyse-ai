# Invordering: afzonderlijk vergelijkingspunt

Deze map bewaart de implementatiemetingen na het
[oorspronkelijke onderzoek](../../../wetsanalyse/onderzoek-invordering-2026-09-29/README.md).
De [ketenspecificatie](../../annotatieketen.md) beschrijft de keten zoals hij nu werkt. De
implementatienotitie A01–A10 (verantwoordelijkheden, acceptatiegevallen, code en beperkingen)
staat in de git-geschiedenis als `docs/architectuur/hybrid-v1-invordering-vervolg.md`. Baseline b8117e2 en
verbeterde meetversie a0699a5 worden afzonderlijk bewaard; de oude metingen zijn niet herschreven.

Begin bij de [inhoudelijke bevindingen](bevindingen.md): het oorspronkelijke voorbeeld,
de andere drie hoofdgevallen, de gevolgen van context en de resterende beoordelingsvragen.

## Bronnen

Uitsluitend de graaf levert doel- en contextteksten voor de modelproef. De oorspronkelijke
vier hoofdgevallen en vijftien contextpassages zijn bevroren in het onderzoeksdossier.
[controlebronnen-graaf.json](controlebronnen-graaf.json) bewaart vier aanvullende controles,
inclusief hashes, graaftoestand en afwijkingen van historische ontwikkelfixtures.
[proef-bronnen.json](proef-bronnen.json) is het volledige bevroren pakket voor alle varianten.

Met toestemming van de gebruiker vervangen Awb 4:17 lid 1 en IW 34 lid 6 de niet in de graaf
aanwezige WZT01 en RVV03. IW02 en AWB04 blijven controles. Acht casussen × drie varianten ×
drie herhalingen blijven **72 primaire runpogingen**. Er wordt geen ontbrekende bron van
internet gehaald of aan de graaf toegevoegd.

| Casus | Doel | Aanvullende passages in C | Contextcodepoints |
|---|---|---:|---:|
| IW-9-1 | IW 9 lid 1 | 18 | 4.878 |
| IW-9-5 | IW 9 lid 5 | 18 | 4.285 |
| LI-9.1 | Leidraad Invordering §9.1 | 18 | 4.557 |
| LI-9.5 | Leidraad Invordering §9.5 | 18 | 3.987 |
| IW02 | IW 36 lid 1 | 0 | 0 |
| AWB04 | Awb 4:17 lid 2 | 1 (lid 1) | 263 |
| AWB-4:17-1 | Awb 4:17 lid 1 | 0 | 0 |
| IW04 | IW 34 lid 6 | 0 | 0 |

Ook zonder aanvullende passage bevat C de expliciete bronmetadata. Het ontbreken van
niet-geselecteerde context wordt niet gelijkgesteld aan aangetoond volledige context.
De hoofdgevallen gebruiken graaftoestand 2026-07-01; de Awb-controles 2026-08-15.

## Deterministische vergelijking

| Casus | Ruwe treffers voor → na | Kandidaten voor → na | Modelkandidaten voor → na | Regelbesluiten voor → na |
|---|---:|---:|---:|---:|
| IW-9-1 | 7 → 7 | 5 → 5 | 5 → 5 | 0 → 0 |
| IW-9-5 | 40 → 43 | 39 → 41 | 36 → 38 | 3 → 3 |
| LI-9.1 | 16 → 22 | 14 → 21 | 14 → 18 | 0 → 3 |
| LI-9.5 | 54 → 70 | 44 → 59 | 44 → 46 | 0 → 13 |

Dit zijn beschikbare kandidaten, geen aantallen juridisch juiste annotaties.
Bij lid 1 verandert vooral de klasse-/beslisruimte; een grotere kandidatenset is daar niet
nodig om de centrale afwijzing te kunnen beoordelen. Bij §9.5 zijn veel nieuwe kandidaten
letterlijke kalenderdatums uit voorbeelden; deze zijn geen nieuwe algemene normen.

Bestanden per stap:

1. [01-grenzen-datums.json](01-grenzen-datums.json): beschermde afleidingsgrenzen en datums zonder jaar.
2. [02-functies-fusie.json](02-functies-fusie.json): termijnfuncties, nominalisatiegrens en tijdkernhypothesen.
3. [03-beslisketen.json](03-beslisketen.json): tussenmeting van de beslisketen, vóór de aanvullende toepassingskeuze.
4. [04-bevroren-keten.json](04-bevroren-keten.json): definitieve offline meting van code a0699a5.
5. [detectieverschillen.md](detectieverschillen.md): verklaring van iedere gewijzigde kandidaat, grens, klasse en route.
6. [conceptbereik-na.md](conceptbereik-na.md): bereik van de oorspronkelijke conceptpunten; hun status blijft ongewijzigd.
7. [ontwikkelcontrole-na.json](ontwikkelcontrole-na.json): vergelijking met de bestaande zestien ontwikkelfixtures plus twee historische diagnostische teksten.

De ontwikkelcontrole houdt 262 kandidaten, 19 regelbesluiten en 243 modelkandidaten.
Kernankers met klasse gaan van 73/81 naar 72/81. WZT01/E11 had een brede span over een
puntkomma en zelfstandige vervolgbepaling heen; die wordt nu functioneel begrensd. Dit verlies
in de ongewijzigde referentie wordt expliciet gerapporteerd, niet weggeschreven. Alle volledige
parses blijven gelijk. De gewijzigde systeemprompt verandert wel alle classifierinvoer.

## Modelproef en beoordeling

A gebruikt de oorspronkelijke code op b8117e2; B gebruikt a0699a5 zonder aanvullende
context; C gebruikt dezelfde code met het hierboven beschreven pakket. De varianten zijn
per casus drie keer uitgevoerd met geroteerde volgorde. De eerste zes pogingen liepen
sequentieel; daarna maximaal drie onafhankelijke casussen tegelijk, met een barrière tussen
de rondes. Latentie is mede afhankelijk van die planning en is geen zuivere snelheidsbenchmark.

Het model is `claude-sonnet-4-6` via Azure Foundry. De exacte verzoeken, reacties, tokens,
aanvraagduur, oorspronkelijke besluiten, bijdragen en eindvoorstellen staan in de
[runmap](modelruns). [manifest.json](modelruns/manifest.json) fixeert code- en bronhashes;
[planner.json](modelruns/planner.json) fixeert de parallelle uitvoering. Bestaande pogingen
worden bij hervatting overgeslagen, ook als ze mislukten. De classifier heeft zijn bestaande
maximaal één herpoging bij ontbrekende tooluitvoer; die telt als extra call binnen dezelfde
primaire poging. SDK-retries staan op nul.

Bij elf controles in ronde 1 bleek de hoogste geselecteerde graafouder nog naar de niet
meegeleverde regelingwortel te verwijzen. Daardoor ontstond `V_ANKER`, ook bij correcte
modelkeuzes. De onderzoekssnapshot wordt nu expliciet lokaal afgesloten, met de echte
externe graafouder apart vastgelegd. Bronteksten, offsets, directe ouders, applicatiecode en
modelverzoeken blijven gelijk. De elf pogingen zijn gereplayed met hun oorspronkelijke
reacties: **nul extra modelaanvragen** en geen resterende ankerfouten. De oude primaire
bestanden blijven staan; [snapshot-herstel](modelruns/snapshot-herstel) bevat de herstelde
uitvoer. [correctie-snapshot.json](modelruns/correctie-snapshot.json) bewaart beide harnashashes;
[de hervatte planner](modelruns/planner-na-snapshotherstel.json) bewaart het tweede checkpoint.
De eindvergelijking telt iedere poging eenmaal en gebruikt de herstelde uitvoer. De elf
oude lege uitkomsten zijn technische proefopbouwfouten, geen juridische afwijzingen.

De [modelvergelijking](model-vergelijking.md) rapporteert aantallen, stabiliteit, contractfouten,
reviewlast, tokens en geraamde kosten. Het [volledige beoordelingsdossier](model-dossier.md)
bevat ook verdwenen en anders geklasseerde voorstellen. Kosten zijn ramingen op basis van
providerverbruik en lijstprijzen, geen factuurbedragen. Een extra voorstel of een tweede
modeloordeel is geen expertvaststelling. De 60 eerdere conceptpunten zijn geen goldset.

## Technische controle en reproductie

Graph-qa: **1.200 tests geslaagd, 19 overgeslagen** in de volledige pre-push-suite,
inclusief de zeven meetharnastests.
De 19 overgeslagen tests betreffen optionele integraties; er is lokaal geen nieuwe volledige
PostgreSQL-integratiemeting gedaan. De volledige API-suite: **432 geslaagd, 8 overgeslagen**,
waaronder de eerder afzonderlijk gedraaide 63 tests voor vocabulaire, export,
annotatievalidatie en v2. Gegenereerde klassen en vocabulaire komen overeen
met hun bronbestanden. De controle op complete runs verifieert alle kandidaat-/optie-/
voorstelspans, context, detectorbijdragen, bron-/codehashes en reproduceerbare detectie.

Commando's vanuit `tools/graph-qa` (nieuwe meetbestanden verplicht; bestaande uitvoer
wordt niet overschreven):

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/genereer_jas_klassen.py --check
.venv/bin/python scripts/genereer_jas_vocabulaire.py --check
.venv/bin/python -m eval.onderzoek_invordering --output /tmp/invordering-nieuwe-meting.json
.venv/bin/python -m eval.detector_audit --json /tmp/invordering-nieuwe-devmeting.json --vergelijk ../../docs/architectuur/metingen/hybrid-v1-tekststructuur-2026-09-29/na.json
```

`eval.invordering_proef --baseline <checkout-b8117e2> --output <nieuwe-map>` voert de
sequentiële modelproef uit. `eval.invordering_parallel --baseline <checkout-b8117e2>` kan
de vastgelegde proef hervatten als er geen andere planner draait. Verander daarvoor geen
bron- of codeversie. Het afbakeningsherstel staat als afzonderlijke, gecontroleerde correctie
vastgelegd; het is geen algemene toestemming om van versie te wisselen.
`eval.invordering_rapport` leest uitsluitend de bewaarde 72 pogingen;
er volgen geen model- of graafaanvragen. De meetbestanden zijn geen productiedata en
worden niet via de annotatie-API opgeslagen.
