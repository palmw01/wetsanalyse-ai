Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall. **Diagnostisch** (conceptcasus): telt niet mee in een v1-totaal.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 37% |
|   min–max over rondes | 37–38% |
| micro-precisie | 28% |
| ankerdekking | 53% |
| macro-F1 | 50% |
| precisie, alleen onbetwist | 28% |
| ankerdekking, alleen onbetwist | 53% |
| exacte span | 65% |
| partieel, zelfde klasse | 50% |
| detectie stabiel | 97% |
| span exact over runs | 100% |
| klasse unaniem over runs | 97% |
| kandidaatbeslisstabiliteit | 95% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 14.0 |
| seconden per run | 12.73 |
| elementen per run | 31.8 |
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

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 99, 'DETECTOR_SPAN_ERROR': 10, 'CANDIDATE_MISSED': 10, 'DETECTOR_ERROR': 5}
Per soort: hybrid_v1: {'juridisch': 119, 'technisch': 5}
