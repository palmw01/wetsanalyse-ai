# Meting contextweergave (stap 6), 12 november 2026

De meting bij `docs/architectuur/plan-contextweergave.md`, §*PR-volgorde* stap 6. Ze toetst of de contextweergave klopt
met wat de API meldt en met wat het budget boekt, en hoe ver de schatting per categorie ernaast zit.

- **Waar**: acceptatie, in eigen gesprekken en één eigen werkgebied, via de acceptatie-MCP.
- **Code**: master `06556097` (bundel 82), model `claude-sonnet-4-6` via Azure AI Foundry.
- **Gekost**: 323.912 tokens (geschat was 0,85M).
- **Cijfers**: `meting.json` in deze map. Tokens komen uit `usage`; tekens zijn de JSON-tekens van
  `verzoekopbouw.samenstelling`.

## Uitkomst in het kort

1. **De som klopt.** In elke beurt is de som van de delen gelijk aan het totaal uit `usage`, en `som` gelijk aan wat het
   budget boekte (beurt 1, de enige die los te meten was: 58.639 in beide).
2. **Het anker werkt.** Bij een koud begin is `cache_schrijf_1u` precies het voorvoegsel (tools + systeem): de aanroepen
   erna lezen hetzelfde getal.
3. **De schatting naar tekens is binnen het voorvoegsel goed** (afwijking tot 4%), en daarbuiten bruikbaar maar grover
   (tot 20% te laag zonder anker). Dat blijft onder de richtlijn van een kwart; tellen met een extra aanroep is niet nodig.
4. **Twee fouten in de weergave**, beide hersteld in een eigen PR (#1357): de boom bij een regie, en de adviestekst bij een
   koud begin met andere tools.

## 1. Vijf beurten in één gesprek

Korte vragen over de Invorderingswet 1990 (art. 4, 11 en 12), alle bronnen aan.

| Beurt | Route | Begin | Context (laatste verzoek) | Verbruik (hele beurt) | Voorvoegsel |
|---|---|---|---|---|---|
| 1 | duiding | koud | 28.178 | 58.639 | 25.009, exact |
| 2 | duiding | warm | 28.866 | 31.893 | 25.164, geschat |
| 3 | duiding | warm | 29.228 | 61.494 | 25.133, geschat |
| 4 | algemeen | koud | 32.004 | 67.069 | 26.905, exact |
| 5 | duiding | warm | 30.656 | 34.550 | 25.139, geschat |

- **Context en verbruik zijn twee getallen.** De context blijft rond 30k (3% van het venster); een beurt kost 32k tot 67k,
  afhankelijk van het aantal rondes en van een koud of warm begin.
- **Koud of warm is in het volume nauwelijks te zien.** Beurt 1 (koud) en beurt 3 (warm) hadden elk twee rondes van de
  lus en kostten ongeveer evenveel (58,6k en 61,5k). Maar beurt 1 schreef 28k waar beurt 3 las. Het budget telt volume,
  dus daar valt het weg; in gewogen kosten (schrijven voor een uur 2×, lezen 0,1×) is het de grootste post. Daarom zegt
  de weergave apart hoe de beurt begon.
- **Beurt 4 begon koud door een ander soort vraag.** De supervisor koos `algemeen` in plaats van `duiding`: andere tools
  (38 tegen 33) en een andere methodetekst, dus een ander voorvoegsel, met dezelfde bronnen aan. De weergave zei daar "de
  bronnen naast de wet wisselden". Dat was fout; zie §4.
- **Het budget**: vóór beurt 1 stond de teller op 829.811, erna op 888.450. Het verschil is 58.639, gelijk aan `som`. Bij
  de latere beurten draaide een ander meetspoor op hetzelfde account; die verschillen zijn niet los te lezen.
- **De meter na herladen**: de `contextopbouw` op het bericht is dezelfde als op het `meting`-event (vergeleken bij de
  eerste beurt na stap 3, veld voor veld gelijk). Bij deze vijf beurten is het bericht niet opnieuw opgehaald.

## 2. De ijking via het anker

Het plan noemde een losse `count_tokens` per categorie. Die is hier niet gedraaid: dat vraagt de sleutel van de provider.
In plaats daarvan zijn drie voorvoegsels exact gemeten en vergeleken.

| Voorvoegsel | Tekens | Tokens (exact) | Tekens per token |
|---|---|---|---|
| A: duiding, alle bronnen | 73.403 | 25.009 | 2,94 |
| B: algemeen, alle bronnen | 78.635 | 26.905 | 2,92 |
| C: duiding, alleen wetgeving | 40.021 | 13.677 | 2,93 |

- **A min C** is wat de bronnen naast de wet toevoegen: de connectortools (27.480 tekens) plus het extra veld in de
  sjablonen (5.902 tekens). Samen 33.382 tekens voor 11.332 tokens: 2,95 tekens per token.
- **B min A** is vooral vijf extra wettools: netto 5.232 tekens voor 1.896 tokens. Rekent men de sjablonen en de methode op
  2,94, dan zitten die wettools op 2,83: 4% dichter dan het gemiddelde.
- **Conclusie voor het voorvoegsel**: de verhouding is over systeem, methode en de drie toolcategorieën vrijwel gelijk. Met
  een anker is de verdeling over die categorieën tot enkele procenten nauwkeurig.

**Na het cachepunt** is de tekst dichter in tokens:

| Verzoek | Tekens na het cachepunt | Tokens (exact) | Tekens per token |
|---|---|---|---|
| eerste beurt na stap 3 | 16.094 | 5.881 | 2,74 |
| beurt 1 | 8.779 | 3.169 | 2,77 |
| ijkbeurt C | 3.100 | 1.358 | 2,28 |

- **Met anker** maakt dat niet uit: het voorvoegsel en de rest worden elk apart verdeeld.
- **Zonder anker** (een warm begin) gaat alles naar tekens in één verhouding. Het voorvoegsel komt dan 0,5% tot 2% te hoog
  uit (25.164 tegen 25.009; 13.954 tegen 13.677), en de delen erna samen 4% tot 20% te laag (ijkbeurt C: 1.081 geschat
  tegen 1.358). Het totaal blijft exact.

**Wat dit wél en niet ijkt**

- Wél: het voorvoegsel als geheel (exact), de connectortools als verschil tussen A en C, en de orde van grootte van de
  wettools.
- Niet: systeem, methode en sjablonen elk apart; en de categorieën na het cachepunt (beurtcontext, historie, beurt,
  toolresultaten) onderling. Daar is alleen hun som exact.
- Niet: wat de API zelf toevoegt bij tool use. Dat zit in het voorvoegsel en is er niet van te scheiden.
- Een echte `count_tokens` per categorie vraagt iemand met de sleutel van de provider.

## 3. Eén regie

Een annotatieregie op een eigen werkgebied zonder deelvragen, met Iw 1990 art. 4 en art. 12 (lid 1 en 2): drie bepalingen
in één deelgesprek. Er zijn geen besluiten genomen; de voorstellen staan als geel in de gedeelde lagen.

- **De leesroute werkt**: `GET /v1/gesprekken/{id}/contextopbouw` gaf het deelgesprek met drie berichten, elk met een
  `contextopbouw`.
- **Verbruik zonder context**, zoals verwacht: de classifier en de reviewer zijn losse stappen, dus `agenten` is leeg en
  `verbruik` heeft een rij per rol. De drie beurten kostten 7.547, 4.761 en 11.125: samen 23.433.
- **Het regiegesprek zelf heeft geen `contextopbouw`**: de regisseur roept geen model aan.
- **`ouder_run_id` is leeg** op de drie beurten. Het zijn de beurten van een reeks (`<run>.<n>`); de kind-run zelf draagt
  de ouder wel, zijn onderdelen niet.
- **De boom tegen het budget** is niet los gemeten: het andere meetspoor liep tegelijk.

## 4. Wat niet klopte, en wat ermee gedaan is

| Bevinding | Gevolg | Gedaan |
|---|---|---|
| Een regiegesprek heeft geen gemeten beurt, en de beurten van een reeks dragen geen ouder | het paneel toonde het deelgesprek niet | #1357: een kind zonder gemeten ouder staat bij de laatste beurt, of op zichzelf; de kaart toont elke beurt |
| Een andere toolset komt ook van een ander soort vraag | de adviestekst wees naar de bronnen naast de wet | #1357: de regel kijkt of de bronnen veranderden |

## Aanbevelingen (niet gebouwd)

- **De reeks geeft de ouder door.** Zet `ouder_run_id` van de kind-run op de beurten van zijn reeks (graph-qa,
  `agent/reeks.py`). De frontend vangt het nu op, maar met de ouder erbij hoort een kind bij de juiste beurt.
- **Een anker bij een warm begin.** In een nieuw gesprek leest de eerste aanroep precies het voorvoegsel (ijkbeurt C:
  13.677). Dat getal is dan even exact als het 1-uursdeel bij een koud begin. In een vervolgbeurt geldt het niet: daar
  leest de eerste aanroep ook historie (beurt 3: 26.145).
- **De boom met een raster per kind** bestaat pas met de subagents van ADR-016: de kinderen van een regie van nu hebben
  geen toollus.
- **Het profiel in het paneel**: de vaste agents dragen sinds A2-1 een profiel, met een hash als versie
  ("duiding, versie b98c251a955c"). Dat is juist, maar zegt een jurist weinig.
