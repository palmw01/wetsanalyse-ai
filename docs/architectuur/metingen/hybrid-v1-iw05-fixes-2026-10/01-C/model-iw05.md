Referentie: **provisional** – recall heet hier *ankerdekking*, geen annotation recall. **Diagnostisch** (conceptcasus): telt niet mee in een v1-totaal.

| maat | hybrid_v1 |
|---|---:|
| micro-F1 | 35% |
|   min–max over rondes | 33–37% |
| micro-precisie | 27% |
| ankerdekking | 49% |
| macro-F1 | 53% |
| precisie, alleen onbetwist | 27% |
| ankerdekking, alleen onbetwist | 49% |
| exacte span | 49% |
| partieel, zelfde klasse | 58% |
| detectie stabiel | 94% |
| span exact over runs | 100% |
| klasse unaniem over runs | 88% |
| kandidaatbeslisstabiliteit | 88% |
| fingerprint-drift (bug) | 0 |
| modelcalls per run | 11.0 |
| seconden per run | 14.34 |
| elementen per run | 31.2 |
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

Foutcategorieën (fouttaxonomie v2, primair): hybrid_v1: {'CLASSIFIER_ERROR': 97, 'DETECTOR_SPAN_ERROR': 15, 'CANDIDATE_MISSED': 15, 'DETECTOR_ERROR': 5}
Per soort: hybrid_v1: {'juridisch': 127, 'technisch': 5}
