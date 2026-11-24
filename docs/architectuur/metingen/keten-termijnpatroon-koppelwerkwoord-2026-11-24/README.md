# Meting keten-termijnpatroon: "is invorderbaar" met het model (24 nov 2026)

Soort: *meting*. Vervolg op [`keten-termijnpatroon-na-2026-11-24/`](../keten-termijnpatroon-na-2026-11-24/README.md).
Code: `c2de1d63` (#1842: de kandidaat-Variabele neemt het koppelwerkwoord mee, gevolgdetector versie 7), op acceptatie
sinds 24 nov 18:32.

## Opzet

- **Vraag:** is "is invorderbaar" de Variabele, is hij de `uitvoer` van de afleidingsregel, en is hij geen operand van
  "na" meer?
- **Set:** Awir art. 33 lid 4, dezelfde bepaling als de nulmeting en de vorige meting; de laag is van deze test.
- **Werkwijze:** gesprek `acc-test-2026-11-24-termijnpatroon-koppelwerkwoord`, per run één beurt met
  `doel: {bron_iri}` en `hergebruik: "opnieuw"`; lezen met `weergave` en uit het `dekking`-event (het beslisregister).
- **Runs:** drie in plaats van één. De eerste run wees de Variabele af, terwijl de vorige meting hem op "invorderbaar"
  wel kreeg. Bij die twijfel vraagt het lichte regime drie runs.
- **Tokens:** 47.892 voor de drie runs samen (delta `/api/account/verbruik`, 2.917.166 → 2.965.058; gedeeld account).
  De laatste run alleen: 14.880 in + 1.084 uit, 11 modelrondes, `claude-sonnet-4-6`.

## Uitkomst

| Run | "is invorderbaar" (`STATE_PROPERTY`, alleen Variabele) | AR | `uitvoer` | operanden van "na" |
|---|---|---|---|---|
| `780ae05c` | **afgewezen** door het model (*Geen annotatie*) | gekozen | geen | alleen "de dagtekening van de beschikking" (2) |
| `85aa0668` | **afgewezen** | gekozen | geen | idem |
| `590b89fc` | **afgewezen** | gekozen | geen | idem |

De andere beslissingen zijn in alle drie gelijk aan de vorige meting: Rechtsbetrekking voor de tweede zin, de
tijdsaanduidingen, "na" als Operator, de kern "zes weken" weg door `ontdubbel_tijd` (`DUBBELE_TIJD_FUNCTIE`). De eerste en
derde zin krijgen niets nieuws. De vorige laag-Variabele "invorderbaar" is vervangen (`vervangen: 1`).

Tegen de drie vragen:

1. **"is invorderbaar" als Variabele: nee.** De kandidaat ligt er, met de goede span, maar het model wijst hem in 3 van 3
   runs af. Op "invorderbaar" (de vorige code) koos het hem in 1 van 1.
2. **`uitvoer`: nee.** Zonder Variabele is er geen uitvoer. De regel zelf klopt (getest).
3. **Geen operand van "na": ja.** De operandfout van de vorige meting is weg. "na" heeft alleen de dagtekening als
   operand. De duur "zes weken" ontbreekt nog als operand, omdat de kern wegvalt.

## Duiding

De span heeft het gedrag van het model veranderd: een woord dat het eerst als kenmerk las, leest het met het
koppelwerkwoord ervoor als gezegde. Dat is een sterk vermoeden, geen bewijs. Het zijn 3 runs tegen 1, op één bepaling.

Wat het model ziet: een batch met alleen deze kandidaat, de keuze tussen Variabele en *Geen annotatie*, de eerste zin
van de omschrijving van Variabele, en het signaal als code (`STATE_PROPERTY`), zonder de verklaring uit
`verklaringen.yaml`.

Mogelijke vervolgstappen, ter keuze van de hoofdsessie. Elk verandert het gedrag van Lex en vraagt dus een eigen meting:

- **De span terug naar de toestand, met "is invorderbaar" als spanoptie.** Het model koos die vorm wel. Het besluit van
  de jurist ligt dan bij de jurist in de werkplek, niet bij de keten. Spankeuze staat standaard uit.
- **Het model de verklaring van het signaal laten zien** (de naam uit `verklaringen.yaml` naast de code). Dat is
  generiek, maar raakt elke kandidaat in elke bepaling.
- **Deterministisch accepteren** kan niet: Variabele heeft determinisme *laag* en daarom geen sterke code.

## Besluit na deze meting

De eigenaar besloot daarna (24 nov 2026), op grond van de bron, dat de variabele het kenmerk **zonder** koppelwerkwoord
is: "invorderbaar". H2-JAS geeft bij de booleaanse waarde "geregistreerd in het donorregister"; het boek markeert bij
art. 23 lid 5 MRB 1994 ("niet is geregistreerd in het kentekenregister") als variabele "geregistreerd in het
kentekenregister", zonder "is" en "niet"; het werkwoord hoort bij de rechtsbetrekking of het rechtsfeit. De regel staat
nu in de skill (`markeren-fragmentgrenzen.md`), de span gaat terug, en de operandfout is generiek hersteld: zie
[`keten-termijnpatroon-kenmerk-2026-11-24/`](../keten-termijnpatroon-kenmerk-2026-11-24/README.md).

## Gegevens

- Run-id's: zie de tabel. De events staan in de runstore van acceptatie; de laag staat op Awir 33 lid 4, met alle
  voorstellen `voorgesteld`.
- Het gesprek `acc-test-2026-11-24-termijnpatroon-koppelwerkwoord` blijft staan tot de opruimronde van de hoofdsessie.
