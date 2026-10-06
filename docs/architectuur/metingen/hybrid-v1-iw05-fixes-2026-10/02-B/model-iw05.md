Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall. **Diagnostisch** (conceptcasus): telt niet mee in een v1-totaal.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 35% |
|   min–max over rondes | 35–35% |
| micro-precisie | 26% |
| ankerdekking | 53% |
| macro-F1 | 48% |
| precisie, alleen onbetwist | 26% |
| ankerdekking, alleen onbetwist | 53% |
| exacte span | 65% |
| partieel, zelfde klasse | 62% |
| detectie stabiel | 94% |
| span exact over runs | 100% |
| klasse unaniem over runs | 88% |
| kandidaatbeslisstabiliteit | 86% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 12.0 |
| seconden per run | 17.92 |
| elementen per run | 34.0 |
| beslissingen zonder model | 10% |
| human review | 0% |
| geel aandeel | 0% |
|   min–max over rondes | 0–0% |
|   waarvan juridisch | 0 |
|   waarvan technisch | 0 |
| contractfouten classifier | 0% |
|   leakage | 0 |
|   leakage uit specificiteit | 0 |
| contractfouten reviewer | – |

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 105, 'DETECTOR_SPAN_ERROR': 15, 'CANDIDATE_MISSED': 5, 'DETECTOR_ERROR': 5}
Per soort: hybrid_v1: {'juridisch': 125, 'technisch': 5}
