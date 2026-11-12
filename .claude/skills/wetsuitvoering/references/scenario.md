# Juridische scenario's, aktes en rechtsgevolgen

Grondslag: [bronnen](bronnen.md) — J01 H2 en H3, JP01.

## Inhoud

- Wat een juridisch scenario is
- De juridische akte
- Rechtsgevolg
- Werkwijze
- Welke scenario's je kiest
- Methodetekst voor Lex

## Wat een juridisch scenario is

Een juridisch scenario beschrijft hoe een burger of bedrijf een stuk wet- en regelgeving doorloopt **in de
uitvoering**. De specificatie noemt het "als het ware de eenheid van wetsuitvoering" (J01, H2). Het begint als een
praktijkvoorbeeld in gewone tekst, wordt een tijdlijn, en daarna een reeks juridische aktes.

Een scenario bestaat op twee niveaus:
- **instantie**: met concrete partijen, datums en bedragen (*mevrouw A, aanslag van 12 maart, € 1.200*);
- **type**: dezelfde opbouw zonder concrete waarden (*een belastingschuldige, een aanslag, het bedrag van de aanslag*).

Het type is wat de wet regelt; de instantie toetst of je het goed begrepen hebt.

## De juridische akte

Een akte is één stap, zoals een akte in een toneelstuk (geen notariële akte):

| Deel | Wat erin staat |
|---|---|
| Begintoestand | De rechtsbetrekkingen en juridisch relevante feiten die vóór de gebeurtenis gelden (mag leeg zijn) |
| Rechtsfeit | De handeling, gebeurtenis of het tijdsverloop dat de toestand verandert |
| Rechtsgevolgen | Wat daardoor ontstaat, wijzigt of eindigt |
| Eindtoestand | De begintoestand plus de rechtsgevolgen |

De eindtoestand van een akte is de begintoestand van de volgende.

## Rechtsgevolg

Een rechtsgevolg beschrijft het ontstaan van een rechtsbetrekking of juridisch relevant feit, het wijzigen van een of
meer eigenschappen ervan, of het eindigen ervan (J01, H3). Het JRM maakt het een eigen hoofdclassificatie: in het JAS
zat het verstopt in het rechtsfeit. Leg per rechtsgevolg vast:
- wat het raakt (welke rechtsbetrekking of welk feit);
- wat er gebeurt (ontstaat, wijzigt welke eigenschap, eindigt);
- welk rechtsfeit het veroorzaakt;
- de bepaling, of "toevoeging team" als de wet het niet letterlijk zegt.

In de administratie van de uitvoering zijn rechtsgevolgen de opdracht aan applicaties en registers. Een rechtsgevolg
dat je niet kunt herleiden, is een open punt, geen aanname die je stil invult.

## Werkwijze

1. Schrijf het praktijkvoorbeeld in gewone tekst. Vraag de opdrachtgever om een echt geval als dat er niet is.
2. Zet de gebeurtenissen op een tijdlijn.
3. Maak per gebeurtenis een akte met het [sjabloon](../assets/scenario.md).
4. Zoek bij elk element de bepaling. Gebruik daarvoor de skill wetsanalyse: markeer de bepaling, en koppel de
   markeringen aan de akte.
5. Controleer de keten: is elke eindtoestand de begintoestand van de volgende akte?
6. Schrijf het type: dezelfde aktes zonder concrete waarden.
7. Noem welke andere scenario's er zijn, en welke je bewust niet uitwerkt.

## Welke scenario's je kiest

Kies bewust, in plaats van alleen de *happy flow* uit te werken. Denk aan:
- een voorwaarde die niet voldaan is;
- een uitzondering in een ander lid of een andere regeling;
- een herhaling van dezelfde gebeurtenis;
- een gebeurtenis die later wordt teruggedraaid;
- een termijn die precies op de grens valt.

Werk één scenario volledig uit voor je het volgende begint. Zo blijft het voor het hele team te volgen. De
scenario's leveren meteen testgevallen op voor de uitvoering.

## Methodetekst voor Lex

Deze sectie is de korte vorm voor een modelrol in Lex. Ze is nog aan geen rol gekoppeld (JP04).

<!-- methode:jrm-scenario:begin -->
Beschrijf waar het helpt hoe een burger of bedrijf de bepaling doorloopt in de uitvoering, als juridisch scenario volgens JRM 2: per gebeurtenis een akte met begintoestand, rechtsfeit, rechtsgevolgen en eindtoestand, waarbij de eindtoestand de begintoestand van de volgende akte is. Een rechtsgevolg zegt wat ontstaat, wijzigt of eindigt en welk rechtsfeit het veroorzaakt. Herleid elk element tot de bepaling of noem het een aanname; een hypothetisch scenario toetst een lezing en bewijst haar niet. Houd een concreet geval (instantie) apart van de regel (type). Noem welke andere scenario's er zijn naast de happy flow. De dertien JAS-labels blijven het annotatiecontract; rechtsgevolgen en scenario's zijn aanvullende uitleg.
<!-- methode:jrm-scenario:end -->
