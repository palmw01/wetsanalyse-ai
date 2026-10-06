Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall. **Diagnostisch** (conceptcasus): telt niet mee in een v1-totaal.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 29% |
|   min–max over rondes | 29–30% |
| micro-precisie | 23% |
| ankerdekking | 41% |
| macro-F1 | 37% |
| precisie, alleen onbetwist | 23% |
| ankerdekking, alleen onbetwist | 41% |
| exacte span | 47% |
| partieel, zelfde klasse | 60% |
| detectie stabiel | 94% |
| span exact over runs | 100% |
| klasse unaniem over runs | 84% |
| kandidaatbeslisstabiliteit | 82% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 11.0 |
| seconden per run | 9.73 |
| elementen per run | 31.0 |
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

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 100, 'DETECTOR_SPAN_ERROR': 20, 'CANDIDATE_MISSED': 15, 'DETECTOR_ERROR': 5}
Per soort: hybrid_v1: {'juridisch': 135, 'technisch': 5}
