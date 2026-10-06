Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 48% |
|   min–max over rondes | 47–49% |
| micro-precisie | 35% |
| ankerdekking | 77% |
| macro-F1 | 57% |
| precisie, alleen onbetwist | 35% |
| ankerdekking, alleen onbetwist | 77% |
| exacte span | 82% |
| partieel, zelfde klasse | 42% |
| detectie stabiel | 96% |
| span exact over runs | 100% |
| klasse unaniem over runs | 96% |
| kandidaatbeslisstabiliteit | 94% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 6.21 |
| seconden per run | 9.14 |
| elementen per run | 11.25 |
| beslissingen zonder model | 8% |
| human review | 0% |
| geel aandeel | 0% |
|   min–max over rondes | 0–1% |
|   waarvan juridisch | 1 |
|   waarvan technisch | 0 |
| contractfouten classifier | 0% |
|   leakage | 0 |
|   leakage uit specificiteit | 0 |
| contractfouten reviewer | 0% |

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 302, 'DETECTOR_ERROR': 33, 'DETECTOR_SPAN_ERROR': 21, 'CANDIDATE_MISSED': 19}
Per soort: hybrid_v1: {'juridisch': 342, 'technisch': 33}
