# Meting keten-termijnpatroon, na de uitrol (24 nov 2026)

Soort: *meting*. Vervolg op [`keten-termijnpatroon-2026-11-24/`](../keten-termijnpatroon-2026-11-24/README.md). Twee
delen:

1. de meting met het model na de uitrol van #1837 (bundel #1841, `543946e9`, op acceptatie sinds 24 nov 18:06);
2. de wijziging daarna: de Variabele neemt het koppelwerkwoord mee ("is invorderbaar"), op de branch
   `claude/keten-termijnpatroon-na`, zonder model gemeten.

Het lichte regime: één run, dezelfde gerichte set.

## 1. Met het model, na de uitrol van #1837

Live op acceptatie, code `543946e9`, gesprek `acc-test-2026-11-24-termijnpatroon-na`, Awir art. 33 lid 4 (dezelfde
bepaling als de nulmeting; de laag is van deze test). Eerst kwam er tweemaal hergebruik terug (0 tokens): "opnieuw" in de
vraag is niet genoeg. Een nieuwe ronde gaat met `hergebruik: "opnieuw"` in de run, zoals de knop *Annoteer … opnieuw*.

| Run | Tokens | Uitkomst |
|---|---|---|
| `b756c27a` | 15.969 (delta `/api/account/verbruik`, gedeeld account) | 13 voorstellen (was 12). **Nieuw: Variabele "invorderbaar"**, subtype *variabele*, bewijs *Toestand als uitvoer*, gekozen door het model. **Nieuw: relatie `uitvoer`** van de AR naar die Variabele. De AR, de tijdsaanduidingen, "na", de Rechtsbetrekking en de rest zijn gelijk aan de nulmeting. De eerste en derde zin: niets nieuws. |

Vergeleken met de nulmeting (`c18dc070`): Variabele 0 → 1, `uitvoer` 0 → 1, verder geen verschil.

**Een bijwerking**: "invorderbaar" werd ook **operand 1 van "na"** (`REL_OPERAND_WOORDVOLGORDE`). De operandregel neemt
de naaste voorstellen links en rechts binnen de AR, en het woord lag binnen de AR. Volgens de methode zijn de operanden
van "na" de duur en het tijdstip, niet de uitvoer. Deel 2 lost dat op: "is invorderbaar" begint vóór de AR en is dus
geen operand meer (getoetst in `test_de_toestand_met_koppelwerkwoord_is_uitvoer_en_geen_operand`). De duur "zes weken"
blijft als operand ontbreken zolang `ontdubbel_tijd` de kern weglaat (zie de vorige meting).

## 2. De Variabele met het koppelwerkwoord

**Besluit van de jurist (24 nov 2026):** de Variabele is de toestand met het koppelwerkwoord, "is invorderbaar". Zo
staat art. 9 lid 1 nu op acceptatie.

**Wijziging** (gevolgdetector versie 7): staat het koppelwerkwoord (`cop`) direct vóór de toestand, dan loopt de
kandidaat-Variabele vanaf het koppelwerkwoord, met de kale toestand als spanoptie. Staat het verder weg (inversie: "is
een navorderingsaanslag … invorderbaar", IW 9 lid 2) of ontbreekt het, dan blijft het de toestand alleen: een markering
is één aaneengesloten fragment. De `uitkomst` van de datumregel volgt dezelfde span, zodat de `uitvoer` blijft kloppen.

**Meting zonder model** (`meting.py`, een kopie van de vorige die ook "is …" telt; gegevens `na.json`):

| Bepaling | soort | Variabele (`STATE_PROPERTY`) |
|---|---|---|
| IW 9.1 | patroon | "is invorderbaar" (was "invorderbaar") |
| IW 52.1 | patroon | "is invorderbaar" (was "invorderbaar") |
| IW 63b.5 | patroon | "is invorderbaar" (was "invorderbaar") |
| IW 9.2 | patroon | "invorderbaar" (inversie; ongewijzigd). De tweede toestand heeft geen datumregel en dus geen `STATE_PROPERTY` (bekend gat) |
| 7 controles | controle | geen; geen enkele kandidaat veranderd |

Buiten deze span verandert er geen kandidaat, ook niet op de controles.

**Met het model nog niet gemeten**: deze code draait pas na de merge op acceptatie. Doe dan één beurt op Awir 33 lid 4
met `hergebruik: "opnieuw"`. Verwacht: Variabele "is invorderbaar", `uitvoer` erheen, en "is invorderbaar" geen operand
van "na".

## Wat deze meting niet zegt

- Of het model "is invorderbaar" net zo kiest als "invorderbaar": dat is de meting na de volgende uitrol.
- De gaten uit de vorige meting blijven: de kern "zes weken", de tweede toestand in IW 9.2, en de dekking die de
  gevolgdetector niet telt.
