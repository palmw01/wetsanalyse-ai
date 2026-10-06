Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 50% |
|   min–max over rondes | 50–51% |
| micro-precisie | 37% |
| ankerdekking | 78% |
| macro-F1 | 57% |
| precisie, alleen onbetwist | 37% |
| ankerdekking, alleen onbetwist | 78% |
| exacte span | 82% |
| partieel, zelfde klasse | 44% |
| detectie stabiel | 92% |
| span exact over runs | 100% |
| klasse unaniem over runs | 98% |
| kandidaatbeslisstabiliteit | 93% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 6.21 |
| seconden per run | 13.23 |
| elementen per run | 10.62 |
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

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 270, 'DETECTOR_ERROR': 33, 'DETECTOR_SPAN_ERROR': 21, 'CANDIDATE_MISSED': 21}
Per soort: hybrid_v1: {'juridisch': 312, 'technisch': 33}
