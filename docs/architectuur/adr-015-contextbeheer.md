# ADR-015 – Contextbeheer: een stabiel voorvoegsel, en opruimen alleen waar het moet

Status: aanvaard voor de antwoordlus (12 nov 2026). Meting: `metingen/context-2026-11-12/`.

## Context

Lex stuurt per modelronde de toolschema's, de systeemprompt en het gesprek mee. Prompt-caching is een prefix-match
in de volgorde tools → system → messages. Eén byte verschil maakt alles daarna nieuw, en dat kost 1,25× (5 minuten)
of 2× (een uur), waar lezen 0,1× kost.

De nulmeting (vier beurten in één gesprek) liet zien waar de kosten zitten:
- het koude begin van een beurt is 40–70% van de gewogen kosten;
- de uitvoer en het cache-lezen zijn kleiner;
- de omvang van de historie is niet de dure post: de historie is begrensd en wordt gecachet gelezen.

Het koude begin had drie oorzaken:

1. **Na 5 minuten is de cache weg.** Een jurist die een antwoord leest en dan doorvraagt, betaalde het hele
   voorvoegsel opnieuw (42k tokens in één beurt).
2. **Het deel van de systeemprompt dat per beurt verandert, staat vóór de berichten.** Plan, gesprekscontext,
   werkgebied, onderwerp en BRONNEN IN DEZE BEURT verschillen per beurt, dus de hele historie was elke beurt nieuw.
3. **Het venster op de historie verschoof elke beurt.** De krimp van oude toolresultaten en de voorkant van het
   venster bewogen mee met de lopende beurt. En een lange beurt liet de hele historie in één keer vallen.

## Besluit

- **Het voorvoegsel blijft een uur.** Het cachepunt op een gesplitste systeemprompt (supervisor, antwoordlus) heeft
  een TTL van een uur (`PROMPT_CACHE_TTL`). Het dekt ook de tools. Het punt op de historie houdt 5 minuten. Nameting:
  na een pauze 24,9k tokens gelezen in plaats van geschreven.
- **De systeemprompt van de antwoordlus is vast.** Wat per beurt verandert, staat als eerste blok in de vraag van
  de lopende beurt (`berichten.met_beurtcontext`, kop `BEURTCONTEXT_KOP`), dus ná de historie. Mid-conversation
  system messages bestaan op Sonnet 4.6 niet, vandaar een tekstblok met een kop die zegt van wie het is. Het blok
  gaat niet de checkpoint in. Twee cachepunten op de berichten overbruggen dat:
  - het eind van de historie van deze beurt (schrijven);
  - het eind van de historie van de vorige beurt (lezen).
- **Het venster groeit aan en wordt alleen bij de grens opgeruimd** (`berichten._historievenster`):
  - `MAX_HISTORY_CHARS` begrenst de historie vóór de lopende beurt;
  - de lopende beurt krimpt nooit en telt niet mee;
  - boven het budget blijven van alle beurten behalve de laatste alleen de vraag en het laatste antwoord over, met
    het resultaat dat erbij hoort (`berichten._kern`). De tussenrondes vallen weg als hele paren van aanroep en
    resultaat; het bronregister houdt ze voor de controle. Toen alleen de resultaten werden afgekapt, was een oude
    beurt nog 8–19k tekens, en knipte het venster bijna elke beurt (nameting G5-4/G5-5). Dat hangt af van de hele
    historie, dus het springt niet aan en uit. Per beurt verandert alleen de vorige beurt, en elk toolresultaat
    wordt één keer heel en één keer gekrompen geschreven: het minimum voor een venster dat moet krimpen;
  - de voorkant valt weg op een vast raster van knippunten over de gekrompen historie (een halve begroting). Het
    knippunt hangt alleen af van het gekrompen oude deel zonder de laatste beurt, dus het schuift alleen naar voren.
    De eerste versie hing ook af van de laatste beurt, en daardoor liep de voorkant op acceptatie heen en weer
    (nameting G4-3/G4-4).

  Gesimuleerd met de echte cachepunten: per beurt ~16k tekens opnieuw geschreven (de vorige beurt gekrompen plus de
  nieuwe), tegen 34–36k met het oude venster (`tests/test_trimming.py`).

## Wat niet

- **Server-compaction** (`compact_20260112`) en **context editing** (`clear_tool_uses_20250919`) gebruikt Lex niet.
  - Ze tellen aanroepen en tokens, niet beurten, en kunnen dus de lopende beurt inkorten. Dat breekt de regel dat
    de lopende beurt nooit krimpt, en daarmee de controle die het model op zijn verse resultaat laat bouwen.
  - De documentatie van Anthropic noemt context editing bovendien een middel voor het contextvenster, geen
    besparing: elke wisbeurt herschrijft de gecachte conversatie.
  - Het venster van Lex komt nooit in de buurt van de contextgrens.
- **Een cachepunt op de tools die de specialisten delen**: dat zijn zonder connectortools maar 7 tools (2,4k
  tokens). Met de TTL van een uur blijft het voorvoegsel per specialist toch warm, en het is voor alle juristen
  gelijk.
- **`/compact` of "nieuw gesprek met samenvatting"** levert geen tokens op. Hooguit is het een keuze voor de
  gebruikerservaring.
- **Token counting vooraf**: `usage` meet het al, en een telling kost een extra aanroep.

## Open

- **De toolset per vraag** (bronkeuze, ronde 6) maakt per combinatie van specialist en connectors een eigen
  voorvoegsel. Of een vaste toollijst per gesprek met de keuze als tekst (BRONNEN IN DEZE BEURT) goedkoper is, hangt
  af van hoe vaak de combinatie wisselt. Met de TTL van een uur blijft elke combinatie een uur warm, voor iedereen.
  Gemeten (`metingen/context-2026-11-12/`, G3):
  - een nieuwe combinatie kost ≈ 36k gewogen, één keer per uur;
  - een vaste lijst kost ≈ 4k gewogen per beurt;
  - het omslagpunt ligt bij één wissel per ~9 beurten.

  Hoe vaak het in echte gesprekken wisselt, meet de `tools_hash` in `model_aanroep`. Tot die meting blijft de
  toolset per vraag, mede omdat de bronkeuze beperkt wat het model mag aanroepen. `defer_loading` met tool search
  loont pas boven ~10k tokens aan schema's.
- **Denkstappen.** Gaat de antwoordlus ooit naar een model met denkstappen die tegen bewerking beschermd zijn
  (Opus 5.5), dan is elke bewerking van een eerdere beurt aan de clientkant een breuk. Dat geldt ook voor de krimp
  van de vorige beurt. Dan is compaction of clearing aan de serverkant de veilige vorm, met een drempel en een
  bescherming van de lopende beurt.
