# Meting keten-termijnpatroon: het kenmerk zonder koppelwerkwoord, met het model (24 nov 2026)

Soort: *meting*. Code: `e3b4fea0` (bundel #1846 met #1844: gevolgdetector v8, relatievoorstellen v7), op acceptatie
sinds 24 nov 19:57. Vervolg op [`keten-termijnpatroon-kenmerk-2026-11-24/`](../keten-termijnpatroon-kenmerk-2026-11-24/README.md),
die dezelfde wijziging zonder model mat. Het lichte regime: één run, alleen de geraakte vorm.

## Opzet

- **Vraag:** is "invorderbaar" de Variabele, is hij de `uitvoer` van de afleidingsregel, en is hij geen operand van
  "na"?
- **Set:** Awir art. 33 lid 4, dezelfde bepaling als in de vorige metingen; de laag is van deze test.
- **Werkwijze:** gesprek `acc-test-2026-11-24-termijnpatroon-kenmerk`, één beurt met `doel: {bron_iri}` en
  `hergebruik: "opnieuw"`; gelezen uit het `dekking`-event (het beslisregister) en het `relaties`-event van de run.
- **Tokens:** 15.969 (14.879 in + 1.090 uit, 11 modelrondes, `claude-sonnet-4-6`, geen cache), gelijk aan de delta van
  `/api/account/verbruik` (2.965.058 → 2.981.027).

## Uitkomst

| Run | "invorderbaar" (`STATE_PROPERTY`) | AR | `uitvoer` | operanden van "na" |
|---|---|---|---|---|
| `c44b793e` | **gekozen** als Variabele, door het model | gekozen | **AR → "invorderbaar"** | alleen "de dagtekening van de beschikking" (2) |

De andere beslissingen zijn gelijk aan de vorige runs op deze bepaling. Ze verschillen alleen in hun labels:
- de Rechtsbetrekking voor de tweede zin;
- de tijdsaanduidingen;
- "na" als Operator;
- de kern "zes weken", die wegvalt (`DUBBELE_TIJD_FUNCTIE`);
- de eerste en de derde zin.

Lex meldde: 13 elementen, waarvan één nieuw.

Tegen de drie vragen: **alle drie ja.**

## Alle runs op Awir 33 lid 4 naast elkaar

| Code | Span van de Variabele | Variabele gekozen | `uitvoer` | uitvoer ook operand |
|---|---|---|---|---|
| `1c91d2d7` (nulmeting, `c18dc070`) | geen kandidaat | — | nee | — |
| #1837 (`b756c27a`) | "invorderbaar" | 1 van 1 | ja | **ja** (operand 1 van "na") |
| #1842 (`780ae05c`, `85aa0668`, `590b89fc`) | "is invorderbaar" | 0 van 3 | nee | — |
| #1844 (`c44b793e`, deze meting) | "invorderbaar" | 1 van 1 | ja | nee |

## Wat deze meting niet zegt

- Of het model "invorderbaar" stabiel kiest. Op deze vorm zijn er nu 2 van 2 runs, met één run per code. Het lichte regime
  vraagt niet meer.
- De andere bepalingen met het patroon (IW 9.1, 52.1, 63b.5) zijn met het model niet opnieuw gemeten. Alleen zonder
  model (vorige meting).
- De kern "zes weken" ontbreekt nog als eigen Tijdsaanduiding en als operand van "na" (`ontdubbel_tijd`); zie
  [`keten-termijnpatroon-2026-11-24/`](../keten-termijnpatroon-2026-11-24/README.md).
