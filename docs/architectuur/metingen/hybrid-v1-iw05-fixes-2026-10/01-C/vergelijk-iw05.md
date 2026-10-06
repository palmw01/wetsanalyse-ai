Voor `858a1de` → na `e341d5b`, casussen `concept:IW05`.

| maat | voor | na | delta | |
|---|---:|---:|---:|---|
| micro_f1 | 29% | 35% | 6% | **buiten spreiding** |
| micro_precision | 23% | 27% | 4% | **buiten spreiding** |
| micro_ankerdekking | 41% | 49% | 8% | **buiten spreiding** |
| macro_f1 | 37% | 53% | 16% | **buiten spreiding** |
| onbetwist_precision | 23% | 27% | 4% | **buiten spreiding** |
| onbetwist_ankerdekking | 41% | 49% | 8% | **buiten spreiding** |
| exact_span | 47% | 49% | 2% | binnen spreiding |
| geel_aandeel | 0% | 0% | 0% | binnen spreiding |

| klasse | F1 voor | F1 na | | ankerdekking voor | na | |
|---|---|---|---|---|---|---|
| Afleidingsregel | 0–0% | 100–100% | **buiten spreiding** | 0–0% | 100–100% | **buiten spreiding** |
| Operator | 100–100% | 100–100% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Parameter en parameterwaarde | – | – | – | 0–0% | 0–0% | binnen spreiding |
| Rechtsbetrekking | – | 50–50% | – | 0–0% | 0–33% | binnen spreiding |
| Rechtsfeit | – | – | – | – | – | – |
| Rechtsobject | 14–18% | 14–20% | binnen spreiding | 25–25% | 25–25% | binnen spreiding |
| Rechtssubject | – | – | – | – | – | – |
| Tijdsaanduiding | 50–57% | 50–50% | binnen spreiding | 100–100% | 100–100% | binnen spreiding |
| Variabele en variabelewaarde | 15–22% | 17–22% | binnen spreiding | 50–50% | 50–50% | binnen spreiding |
| Voorwaarde | 33–40% | 33–33% | binnen spreiding | 50–50% | 50–50% | binnen spreiding |

| plek | tekst | voor | na |
|---|---|---|---|
| IW05:0-433 | In afwijking van het eerste lid is een voorlopige aanslag in | {'klassen': {'Afleidingsregel': 5}, 'geel': 0} | {'klassen': {'Rechtsbetrekking': 2}, 'geel': 0} |
| IW05:296-433 | zoveel gelijke termijnen als er na de maand, die in de dagte | – | {'klassen': {'Afleidingsregel': 5}, 'geel': 0} |
| IW05:348-384 | de dagtekening van het aanslagbiljet | {'klassen': {'Voorwaarde': 4, 'Rechtsobject': 1}, 'geel': 0} | {'klassen': {'Voorwaarde': 5}, 'geel': 0} |
| IW05:413-421 | het jaar | {'klassen': {'Tijdsaanduiding': 4}, 'geel': 0} | {'klassen': {'Tijdsaanduiding': 5}, 'geel': 0} |
| IW05:474-488 | de dagtekening | {'klassen': {'Variabele en variabelewaarde': 1}, 'geel': 0} | – |
| IW05:474-510 | de dagtekening van het aanslagbiljet | {'klassen': {'Rechtsobject': 4, 'Rechtsfeit': 1}, 'geel': 0} | {'klassen': {'Rechtsfeit': 3, 'Rechtsobject': 1}, 'geel': 0} |
