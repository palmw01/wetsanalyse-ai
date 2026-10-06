Voor `d7c6db8` → na `3f8842f`, casussen `concept:IW05`.

| maat | voor | na | delta | |
|---|---:|---:|---:|---|
| micro_f1 | 36% | 37% | 1% | binnen spreiding |
| micro_precision | 27% | 28% | 1% | binnen spreiding |
| micro_ankerdekking | 53% | 53% | 0% | binnen spreiding |
| macro_f1 | 48% | 50% | 2% | **buiten spreiding** |
| onbetwist_precision | 27% | 28% | 1% | binnen spreiding |
| onbetwist_ankerdekking | 53% | 53% | 0% | binnen spreiding |
| exact_span | 65% | 65% | 0% | binnen spreiding |
| geel_aandeel | 0% | 0% | 0% | binnen spreiding |

| klasse | F1 voor | F1 na | | ankerdekking voor | na | |
|---|---|---|---|---|---|---|
| Afleidingsregel | 67–67% | 67–67% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Operator | 100–100% | 100–100% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Parameter en parameterwaarde | – | – | – | 0–0% | 0–0% | binnen spreiding |
| Rechtsbetrekking | 50–50% | 50–50% | binnen spreiding | 33–33% | 33–33% | binnen spreiding |
| Rechtsfeit | – | – | – | – | – | – |
| Rechtsobject | 14–15% | 14–15% | binnen spreiding | 25–25% | 25–25% | binnen spreiding |
| Tijdsaanduiding | 50–50% | 50–50% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Variabele en variabelewaarde | 22–22% | 22–22% | binnen spreiding | 50–50% | 50–50% | binnen spreiding |
| Voorwaarde | 33–33% | 40–50% | **buiten spreiding** | 50–50% | 50–50% | binnen spreiding |

| plek | tekst | voor | na |
|---|---|---|---|
| IW05:348-384 | de dagtekening van het aanslagbiljet | {'klassen': {'Voorwaarde': 5}, 'geel': 0} | {'klassen': {'Voorwaarde': 3, 'Rechtsobject': 2}, 'geel': 0} |
| IW05:474-510 | de dagtekening van het aanslagbiljet | {'klassen': {'Rechtsfeit': 3}, 'geel': 0} | – |
| IW05:522-543 | de volgende termijnen | {'klassen': {'Rechtsobject': 2}, 'geel': 0} | – |
| IW05:576-610 | de toepassing van de eerste volzin | {'klassen': {'Voorwaarde': 5}, 'geel': 0} | {'klassen': {'Rechtsfeit': 4}, 'geel': 0} |
