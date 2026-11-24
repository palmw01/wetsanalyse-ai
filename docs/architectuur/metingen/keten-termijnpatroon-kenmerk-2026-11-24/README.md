# Meting keten-termijnpatroon: het kenmerk zonder koppelwerkwoord, en de uitvoer als operand (24 nov 2026)

Soort: *meting*. Code: `c2de1d63` (voor; gevolgdetector v7, relaties v6) en de branch
`claude/keten-termijnpatroon-koppelwerkwoord-meting` (na; gevolgdetector v8, relaties v7). Zonder model. Vervolg op
[`keten-termijnpatroon-koppelwerkwoord-2026-11-24/`](../keten-termijnpatroon-koppelwerkwoord-2026-11-24/README.md), dat
in dezelfde PR staat.

## Besluit en bron

De eigenaar besloot (24 nov 2026), op grond van de bron, dat de variabele het kenmerk **zonder** koppelwerkwoord is:
"invorderbaar", niet "is invorderbaar".
- H2-JAS geeft bij de booleaanse waarde het voorbeeld "geregistreerd in het donorregister".
- Het boek markeert bij art. 23 lid 5 MRB 1994 ("niet is geregistreerd in het kentekenregister") als variabele
  "geregistreerd in het kentekenregister": zonder "is" en zonder "niet" (M01, hoofdstuk Variabele, *Voorbeeld van
  variabele met booleaanse waarde*).
- Het werkwoord hoort bij de rechtsbetrekking of het rechtsfeit (H2-JAS, *Rechtsbetrekking*).

De regel staat nu in de skill: `markeren-fragmentgrenzen.md`, onder "Een variabele markeer je zonder werkwoord". Dat valt
buiten de methodemarkers, dus de methodetekst die Lex leest verandert niet; alleen `bronpakket.json` krijgt een nieuwe
hash.

## Wijziging

1. **Gevolgdetector v8:** de kandidaat-Variabele is weer alleen de toestand ("invorderbaar"), zoals in #1837. Die vorm
   koos het model wel; "is invorderbaar" wees het in 3 van 3 runs af.
2. **Relatievoorstellen v7, de operandfout:**
   - **Oorzaak:** `_operand` kiest de operanden op positie: de naaste voorstellen links en rechts van de operator
     binnen de afleidingsregel. Ligt de uitvoer van die regel binnen de regel, links van de operator, dan wordt de
     uitvoer de linkeroperand.
   - **Herstel, generiek:** de uitvoer van een afleidingsregel (een `uitvoer`-voorstel van `_functie`) is nooit operand
     van een operator in diezelfde regel. Een operator verbindt invoer. Dat geldt voor elke regel met een uitvoer, ook
     een telling (`CALCULATION_QUANTITY`), niet alleen voor de datumregel.

## Meting zonder model

`meting.py`: detectie en fusie met de echte parser, dan een vaste keuze in plaats van het model en daarop
`relaties.stel_voor`. De vaste keuze: elke kandidaat met zijn eerste klasse, een tijdkern weg zoals `ontdubbel_tijd` doet,
een afgewezen kandidaat weg. Dat meet het mechanisme, niet de keuze van het model. Gegevens: `voor.json`, `na.json`.

| Bepaling | soort | Variabele voor → na | `uitvoer` → Variabele | uitvoer ook operand, voor → na |
|---|---|---|---|---|
| IW 9.1 | patroon | "is invorderbaar" → "invorderbaar" | ja → ja | nee → nee |
| IW 9.2 | patroon | "invorderbaar" (inversie) → gelijk | ja → ja | **ja ("invorderbaar", operand 1 van "na") → nee** |
| IW 52.1 | patroon | "is invorderbaar" → "invorderbaar" | ja → ja | nee → nee |
| IW 63b.5 | patroon | "is invorderbaar" → "invorderbaar" | ja → ja | nee → nee |
| Awir 33.4 | patroon | "is invorderbaar" → "invorderbaar" | ja → ja | nee → nee |
| IW 9.5, IW 9.7 (telling) | controle | — | "zoveel gelijke termijnen" → gelijk | nee → nee |
| een rekenregel, geen moment, ontkend, AWR 13.2 | controle | — | — | — |

Per relatie vergeleken: in de vier patroongevallen met koppelwerkwoord wisselt alleen het eindpunt van de `uitvoer` (van
"is invorderbaar" naar "invorderbaar"). In IW 9.2 valt alleen de foute `operand` weg. Op de controles verandert geen
enkele relatie.

Dat IW 9.2 de fout ook vóór deze wijziging liet zien, bevestigt dat het om de operandregel ging en niet om de span: met
de span van #1837 ("invorderbaar") lag de uitvoer in elke datumregel binnen de regel.

## Met het model

Nog niet gemeten: deze code draait pas na de merge op acceptatie. Daarna één beurt op Awir 33 lid 4, met
`hergebruik: "opnieuw"`, in een gesprek `acc-test-…`, en een vervolg-PR met alleen documentatie. Verwacht:
- de Variabele "invorderbaar" (het model koos die vorm in 1 van 1 runs);
- de `uitvoer` naar die Variabele;
- "na" met alleen de dagtekening als operand.

## Wat deze meting niet zegt

- Of het model "invorderbaar" stabiel kiest. Er is één run op die vorm; de modelmeting na de uitrol telt mee.
- De kern "zes weken" ontbreekt nog als operand en als eigen Tijdsaanduiding (`ontdubbel_tijd`); zie
  [`keten-termijnpatroon-2026-11-24/`](../keten-termijnpatroon-2026-11-24/README.md).
