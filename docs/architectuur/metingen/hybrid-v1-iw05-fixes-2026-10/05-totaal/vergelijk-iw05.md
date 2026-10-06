Voor `858a1de` → na `3f8842f`, casussen `concept:IW05`.

| maat | voor | na | delta | |
|---|---:|---:|---:|---|
| micro_f1 | 29% | 37% | 8% | **buiten spreiding** |
| micro_precision | 23% | 28% | 6% | **buiten spreiding** |
| micro_ankerdekking | 41% | 53% | 12% | **buiten spreiding** |
| macro_f1 | 37% | 50% | 13% | **buiten spreiding** |
| onbetwist_precision | 23% | 28% | 6% | **buiten spreiding** |
| onbetwist_ankerdekking | 41% | 53% | 12% | **buiten spreiding** |
| exact_span | 47% | 65% | 18% | **buiten spreiding** |
| geel_aandeel | 0% | 0% | 0% | binnen spreiding |

| klasse | F1 voor | F1 na | | ankerdekking voor | na | |
|---|---|---|---|---|---|---|
| Afleidingsregel | 0–0% | 67–67% | **buiten spreiding** | 0–0% | 100–100% | **buiten spreiding** |
| Operator | 100–100% | 100–100% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Parameter en parameterwaarde | – | – | – | 0–0% | 0–0% | binnen spreiding |
| Rechtsbetrekking | – | 50–50% | – | 0–0% | 33–33% | **buiten spreiding** |
| Rechtsfeit | – | – | – | – | – | – |
| Rechtsobject | 14–18% | 14–15% | binnen spreiding | 25–25% | 25–25% | binnen spreiding |
| Rechtssubject | – | – | – | – | – | – |
| Tijdsaanduiding | 50–57% | 50–50% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Variabele en variabelewaarde | 15–22% | 22–22% | binnen spreiding | 50–50% | 50–50% | binnen spreiding |
| Voorwaarde | 33–40% | 40–50% | binnen spreiding | 50–50% | 50–50% | binnen spreiding |

| plek | tekst | voor | na |
|---|---|---|---|
| IW05:0-433 | In afwijking van het eerste lid is een voorlopige aanslag in | {'klassen': {'Afleidingsregel': 5}, 'geel': 0} | {'klassen': {'Rechtsbetrekking': 5}, 'geel': 0} |
| IW05:158-179 | de inkomstenbelasting | {'klassen': {'Variabele en variabelewaarde': 3, 'Rechtsobject': 2}, 'geel': 0} | {'klassen': {'Rechtsobject': 5}, 'geel': 0} |
| IW05:189-206 | het aanslagbiljet | {'klassen': {'Rechtssubject': 5}, 'geel': 0} | {'klassen': {'Rechtsobject': 5}, 'geel': 0} |
| IW05:280-292 | invorderbaar | {'klassen': {'Variabele en variabelewaarde': 5}, 'geel': 0} | – |
| IW05:296-433 | zoveel gelijke termijnen als er na de maand, die in de dagte | – | {'klassen': {'Afleidingsregel': 5}, 'geel': 0} |
| IW05:348-384 | de dagtekening van het aanslagbiljet | {'klassen': {'Voorwaarde': 4, 'Rechtsobject': 1}, 'geel': 0} | {'klassen': {'Voorwaarde': 3, 'Rechtsobject': 2}, 'geel': 0} |
| IW05:413-421 | het jaar | {'klassen': {'Tijdsaanduiding': 4}, 'geel': 0} | {'klassen': {'Tijdsaanduiding': 5}, 'geel': 0} |
| IW05:435-567 | De eerste termijn vervalt één maand na de dagtekening van he | – | {'klassen': {'Rechtsfeit': 5}, 'geel': 0} |
| IW05:474-488 | de dagtekening | {'klassen': {'Variabele en variabelewaarde': 1}, 'geel': 0} | {'klassen': {'Variabele en variabelewaarde': 5}, 'geel': 0} |
| IW05:474-510 | de dagtekening van het aanslagbiljet | {'klassen': {'Rechtsobject': 4, 'Rechtsfeit': 1}, 'geel': 0} | – |
| IW05:522-543 | de volgende termijnen | {'klassen': {'Rechtsobject': 5}, 'geel': 0} | – |
| IW05:576-610 | de toepassing van de eerste volzin | {'klassen': {'Voorwaarde': 5}, 'geel': 0} | {'klassen': {'Rechtsfeit': 4}, 'geel': 0} |
| IW05:61-82 | de inkomstenbelasting | {'klassen': {'Variabele en variabelewaarde': 3, 'Rechtsobject': 2}, 'geel': 0} | {'klassen': {'Rechtsobject': 5}, 'geel': 0} |
| IW05:648-679 | vindt het eerste lid toepassing | – | {'klassen': {'Afleidingsregel': 5}, 'geel': 0} |
| IW05:89-114 | de vennootschapsbelasting | {'klassen': {'Variabele en variabelewaarde': 3, 'Rechtsobject': 2}, 'geel': 0} | {'klassen': {'Rechtsobject': 5}, 'geel': 0} |
