Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 49% |
|   min–max over rondes | 46–51% |
| micro-precisie | 35% |
| ankerdekking | 79% |
| macro-F1 | 57% |
| precisie, alleen onbetwist | 35% |
| ankerdekking, alleen onbetwist | 79% |
| exacte span | 83% |
| partieel, zelfde klasse | 45% |
| detectie stabiel | 92% |
| span exact over runs | 100% |
| klasse unaniem over runs | 95% |
| kandidaatbeslisstabiliteit | 91% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 6.19 |
| seconden per run | 7.96 |
| elementen per run | 11.27 |
| beslissingen zonder model | 8% |
| human review | 0% |
| geel aandeel | 0% |
|   min–max over rondes | 0–0% |
|   waarvan juridisch | 0 |
|   waarvan technisch | 0 |
| contractfouten classifier | 0% |
|   leakage | 0 |
|   leakage uit specificiteit | 0 |
| contractfouten reviewer | 0% |

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 300, 'DETECTOR_ERROR': 33, 'DETECTOR_SPAN_ERROR': 22, 'CANDIDATE_MISSED': 16}
Per soort: hybrid_v1: {'juridisch': 338, 'technisch': 33}
