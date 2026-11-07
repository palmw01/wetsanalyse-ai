# ADR-010: De agentarchitectuur van Lex in vier lagen

**Status:** aangenomen, 7 nov 2026. Eindbeeld en bouwvolgorde. De eerste stap is de workflow voor de tekst van een bepaling
(D1). Laag 4 (één algemene agent) is een apart besluit, dat pas valt na een meting.

## Context

Op acceptatie is gemeten (7 nov 2026): 21 losse beurten en 4 gesprekken van samen 15 beurten. Wat daaruit bleek:

- **Elke modelronde stuurt ±10k tokens vaste prefix mee**: de systeemtekst en 23–28 toolschema's.
  - De tekst van één lid (Iw art. 9 lid 1, één zin) kost 41,9k tokens en vier modelaanroepen: de supervisor, het
    BWB-id zoeken, het lid ophalen en afronden. De vraag staat daarna drie keer op ±12 tokens na gelijk.
  - Art. 25 Iw kost 92k tokens en 65 s.
  - Een analist heeft 500k tokens per week.
- **De graaf is snel (milliseconden); de tijd zit in de modelronden en de uitvoer.**
- **Het model kiest wat de code al weet.**
  - De supervisor routeert "wat staat er in artikel 25" naar de duidingspecialist.
  - Het model zoekt een BWB-id dat in de vraag staat.
  - Het model wijst IRI's aan die de code al heeft.
- **De kwaliteit lijdt waar het model feiten doorgeeft of zelf een indeling maakt.**
  - In 6 van de 15 gespreksbeurten stond een bewering die niet in de bron staat.
  - Een vraag over een werkgebied negeerde de opgeslagen bronselectie en gebruikte een verkeerd BWB-id.
  - Een vervolgvraag in een bestaand werkgebied startte het samenstellen van een nieuw werkgebied.
- **De specialisten verschillen nauwelijks.** Duiding en algemeen kunnen allebei een bepaling afronden, en elke specialist
  heeft een eigen prefix. De cache valt daardoor uiteen.

De repo kiest al voor code waar het kan:
- ADR-001: de annotatieketen, met het model alleen voor afgebakende keuzes;
- ADR-005: agents met één strikte stap;
- ADR-008: de code vult het antwoord;
- de overzichtsroute, helemaal zonder model.

Die keuze geldt nog niet voor de antwoordroute als geheel. Anthropic beveelt hetzelfde aan (*Building effective agents*,
de skill `claude-api`):
- begin met een workflow, en gebruik een agent alleen voor open verkenning;
- routeer in code waar het kan;
- houd de vaste prefix stabiel en gedeeld;
- geef een taak alleen een eigen context als het lezen omvangrijk is.

## Besluit

### Vier lagen

```
verzoek ─► 1 routering in code ─┬─► 2 vaste workflow       (bepaling, begrip, werkgebied, overzicht)
                                ├─► 3 taakagent             (deelvragen, begrippen, annotatie, …)
                                └─► 4 algemene agent        (duiding, zoeken; de open rest)
```

**1. Routering in code.** Wat herkenbaar is, gaat zonder model naar zijn plek:
- acties en kaartjes;
- een meegegeven doel of onderwerp;
- een vraagvorm die de code eenduidig leest, zoals "wat staat er in artikel X van Y", een overzichtsvraag of een leesvraag.

Een model routeert alleen wat de code niet eenduidig kan lezen. Het herschrijft de vraag alleen als er een gesprek is.
Elke routeringsregel staat in de routeringsset (Q1, `eval/golden_routering.jsonl`). Het deel zonder model draait in CI.

**2. Vaste workflows voor vaste vragen.** De code doet het werk: de bepaling uit de vraag halen, ophalen, het sjabloon
vullen en de controle. Het model doet hoogstens één aanroep zonder tools, met strikte uitvoer, voor een korte toelichting.
- **Dezelfde vraag geeft dezelfde tekst, dezelfde bronnen en dezelfde vindplaats.** Het model wijst niets aan.
- **Kan de code de vraag niet eenduidig lezen** (geen regeling, meer kandidaten), dan vraagt de workflow door met een
  keuzekaart, of geeft hij de vraag aan laag 4. Hij gokt nooit.
- **Eerst vier workflows:**
  - *bepaling*: de tekst van een artikel, lid of onderdeel;
  - *begrip*: de wettelijke definitie met haar bereik;
  - *werkgebied*: de deelvragen, de bronnen per deelvraag en de dekking, uit de api;
  - *overzicht*: bestaat al.

**3. Taakagents met een smal doel.** Deelvragen, begrippen en annotatie bestaan al (ADR-005). Later komen er misschien
bij, zoals afleidingsregels en RegelSpraak. Elke taakagent heeft het contract hieronder.

**4. Eén algemene agent voor de open rest:** duiding, samenhang en zoeken zonder vaste vorm. Hier blijft de toollus,
omdat de weg naar het antwoord niet vooraf vastligt.
- **Of dat één agent wordt** in plaats van de huidige specialisten (duiding, definitie, algemeen, retrieval), beslist een
  meting achter een vlag. Zie *Wat nog open is*.
- **Valt de meting anders uit, dan blijft laag 4 een paar specialisten**, met een gedeelde prefix waar dat kan.

### Gedeelde onderdelen

Elke laag gebruikt dezelfde drie onderdelen. Er komt geen eigen variant per agent.

| Onderdeel | Wat | Waar |
|---|---|---|
| **De modelstap** | Eén aanroep met één strikte tool. De stopreden wordt gelezen, en hij wordt hoogstens één keer herhaald, bij `end_turn`. Per aanroep een logregel `model_aanroep` met rol, model, stopreden, duur en tokens | H5 (`agent/llm_stap.py`) |
| **De contextopbouw** | Het werkgebied, het onderwerp, de focus en wat eerder is opgehaald, begrensd per laag. De werkplek laat zien wat er meegaat | E6, G3 |
| **De kwaliteitsmeting** | Vraagtype per case, bewaarde runs die gratis opnieuw te scoren zijn, deterministische scorers (volgorde, sjabloon, toon), en de routeringsset. De meting per beurt (`meting`-event) geeft per aanroep het verbruik, het deel uit de cache en de duur | Q1, Q0 |

De werkplek volgt een beurt op één manier (E4: de beurtlogica uit `WerkplekClient`), welke laag de beurt ook afhandelt. De
eventtypes blijven het contract (zie `tools/graph-qa/CLAUDE.md`).

### Het contract van een agent of workflow

Elke workflow (laag 2) en elke taakagent (laag 3) legt vast:

1. **Doel**: één zin, met wat er níét bij hoort.
2. **Ingang**: welke routeringsregel of actie hem kiest, met de rijen in de routeringsset.
3. **Benodigde context**: welke onderdelen van de contextopbouw, en de bovengrens ervan.
4. **Tools of queries**: deterministisch waar het kan. Een model alleen in een stap die een oordeel of een formulering
   vraagt, via de gedeelde modelstap, met een strikte tool en validatie in code.
5. **Uitvoer**: een sjabloon (ADR-008) of een artefact. Feiten komen uit code, nooit uit modeltekst.
6. **Wat bij twijfel gebeurt**: doorvragen (een keuzekaart), doorgeven aan laag 4, of een eerlijke `leemte`. Nooit gokken.
7. **Eval**: cases per vraagtype in de kwaliteitsset, met de verwachte route. Een doel in tokens en duur, gemeten met de
   meting per beurt.

### Een nieuwe agent of workflow toevoegen

1. Schrijf het contract (de zeven punten) in de module zelf of in een korte ADR als het groter is.
2. Voeg de routeringsregel en zijn rijen in `eval/golden_routering.jsonl` toe, en de cases per vraagtype in de kwaliteitsset.
3. Gebruik de gedeelde modelstap, contextopbouw en sjablonen. Een eigen variant mag alleen met een reden in het contract.
4. Meet vóór en na: de kwaliteitsset (bewaard, herscoorbaar) en de meting per beurt, drie runs, zoals het meetlogboek vraagt.
5. Een agent die geen meting haalt, landt niet.

## Relatie met eerdere ADR's

- **ADR-001** (hybride JAS-pijplijn): ongewijzigd. De annotatieketen is een taakagent (laag 3) die al werkt zoals deze ADR
  vraagt: deterministisch, met het model alleen voor afgebakende keuzes op vaste kandidaten.
- **ADR-005** (Vraag Lex en de agents): laag 3 is ADR-005, uitgebreid met het contract. De supervisor blijft voor de keuze
  tussen agent en taak bij getypte tekst die de code niet eenduidig leest. Een actie kiest al zonder model, en dat geldt
  nu voor elke herkenbare vraagvorm (laag 1).
- **ADR-008** (antwoordsjablonen): de sjablonen blijven de uitvoer van laag 2 en 4. Nieuw is dat in laag 2 de code ook
  aanwijst wat in het sjabloon komt. Het model wijst geen IRI's meer aan.

## Eerste stap: de workflow voor een bepaling (D1)

**"Wat staat er in artikel X (lid Y) van regeling Z"**, met precies één eenduidige treffer:
- de regeling uit de vraag (`overzicht.regelingen_in_vraag`);
- het artikel en lid (`aanwijzing.lees_aanwijzing`, `bepaling_namen.bepalingen_uit_tekst`);
- het bestaan in de graaf (`bepaling_namen.bepaling_in_graaf`);
- de tekst ophalen in code;
- het sjabloon `bepaling` vullen;
- `verify`;
- hoogstens één modelaanroep voor de toelichting.

Zonder eenduidige treffer gaat de vraag de huidige weg.

**Doel, op acceptatie gemeten in drie runs:**

| Vraag | Tokens | Duur | Nu |
|---|---|---|---|
| Iw art. 9 lid 1 | ≤12k | ≤4 s | 41,9k, ~10 s |
| Iw art. 22 lid 3 | – | – | letterlijk en in de volgorde van de officiële tekst |
| Iw art. 25 (22 leden) | – | – | volledig, zonder doorbladeren door het model |

Haalt D1 dat, dan volgen de workflows voor begrip en werkgebied in dezelfde vorm.

## Wat nog open is

**Laag 4 als één agent (optie C).** Eén agent met één stabiele prefix (alle methodeteksten en tools), die zelf herschrijft
en het sjabloon kiest, in plaats van de supervisor plus specialisten voor de open rest.
- **Winst:** naar verwachting één aanroep per beurt minder, geen misroute tussen specialisten, en één gedeelde cache.
- **Risico:** minder sturing per vraagtype.
- **Besluit pas na een vergelijking:** achter de vlag `EEN_ANTWOORDAGENT`, op acceptatie, met de kwaliteitsset en
  `golden_gesprek`, elk drie runs. Dat is een betaalde eval, alleen na akkoord.

## Waarom niet anders

- **Eén grote agent voor alles, zoals Claude Code.** Dan gaan de garanties verloren die nu in de topologie zitten: advies
  kan niet annoteren, de leesroute kan niet schrijven, en een bepaling is compleet of wordt niet getoond. Een jurist heeft
  bovendien bij een vaste vraag dezelfde uitkomst nodig, en dat geeft een workflow, geen lus.
- **Een LLM-critic per antwoord.** Dat verdubbelt de kosten. De controle hoort in code (`verify`), en uitbreidingen zoals
  de toets op datums en getallen ook.
- **Een subagent per lid of per bron.** De prefix vermenigvuldigt zich. Een beurt per lid bestaat al waar hij nodig is:
  bij annoteren (`reeks.py`).
- **Managed Agents of de Agent SDK.** Die draaien niet op Microsoft Foundry, en de brongetrouwheid hoort in onze code.
- **Een cascade van goedkopere modellen nu.** De cache geldt per model. Eerst verdwijnen de rondes; daarna is de
  modelkeuze een eigen meting.

## Gevolgen

- **Bij een nieuwe vraagvorm** is de eerste vraag: is dit een workflow (laag 2) of open (laag 4)? Een workflow heeft de
  voorkeur zodra de weg vastligt.
- **De routeringsregels in `nodes/supervisie.py` worden één tabel** met rijen in de routeringsset, in plaats van losse
  patronen vóór en na de supervisor-call.
- **Specialisten die laag 2 overbodig maakt, vervallen.** De retrieval-set en het afronden met `antwoord_bepaling` door
  duiding en algemeen gaan pas weg na D1 en de meting.
- **`tools/graph-qa/CLAUDE.md` beschrijft de lagen**, met een verwijzing naar dit document.
