"""De reviewload gesplitst in juridisch en technisch (onderzoek-empirische-validatie §6, V5).

"12 ter keuze aan de jurist" zei tot nu toe niet of dat twaalf juridische vragen waren of twaalf
technische storingen. In LI §9.5 waren het er twaalf van de tweede soort: de classifier koos een
klasse buiten de toegestane, en de reviewer daarna ook. Deze splitsing maakt dat zichtbaar.

Alles is afgeleid uit wat er al is (twijfel, classifierreden, resolutieregel), dus er komen geen
modelaanroepen bij en de afhandeling verandert niet. Alleen de rapportage.

Elk geel geval (HUMAN_REVIEW) krijgt precies één **oorsprong**, in deze volgorde:

1. `classifier_contract_failure`: de classifier koos buiten de toegestane beslissingen;
2. `classifier_invalid_output`: geen tool-uitvoer, of het label ontbrak;
3. `reviewer_contract_failure`: de reviewer gaf ongeldige uitvoer (`R-ONGELDIG`);
4. `degraded_parse_review`: geclassificeerd zonder zinsontleding;
5. `substantive_legal_review`: een detectorconflict of dezelfde span, met een geldig oordeel dat
   bij de jurist uitkomt;
6. `technical_other_review`: de rest.

`juridisch` is alleen (5); `technisch` is alles daarvóór en (6). De tellers `detector_conflict_review`
en `span_review` tellen twijfels, niet gele gevallen, en overlappen dus met de rest.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

CONTRACT = ("CLASSIFIER_ONGELDIGE_KLASSE", "CLASSIFIER_ONGELDIGE_OPTIE")
ONGELDIGE_UITVOER = ("CLASSIFIER_GEEN_UITVOER", "CLASSIFIER_OMITTED")
SUBSTANTIEF = frozenset({"R-CONFLICT-KEEP", "R-CONFLICT-HUMAN", "R-SPAN-HUMAN"})
OORSPRONG = ("classifier_contract_failure", "classifier_invalid_output", "reviewer_contract_failure",
             "degraded_parse_review", "substantive_legal_review", "technical_other_review")


def oorsprong(twijfels: list[Any], transities: list[Any]) -> str:
    """De oorsprong van één geel geval, uit zijn twijfels en transities (§6, volgorde hierboven)."""
    details = [t.detail for t in twijfels if t.reden == "CLASSIFIER_ABSTAIN"]
    regels = [t.regel for t in transities]
    if any(d.startswith(CONTRACT) for d in details):
        return "classifier_contract_failure"
    if any(d.startswith(ONGELDIGE_UITVOER) for d in details):
        return "classifier_invalid_output"
    if "R-ONGELDIG" in regels:
        return "reviewer_contract_failure"
    if any(t.reden == "DEGRADED_PARSE" for t in twijfels):
        return "degraded_parse_review"
    if any(r in SUBSTANTIEF or r.startswith("R-PRIORITEIT") for r in regels):
        return "substantive_legal_review"
    return "technical_other_review"


def splits(beslissingen: list[Any], twijfels: list[Any], transities: list[Any]) -> dict[str, Any]:
    geel = [b.label for b in beslissingen if getattr(b.status, "value", b.status) == "HUMAN_REVIEW"]
    per = Counter(oorsprong([t for t in twijfels if t.label == lab], [t for t in transities if t.label == lab])
                  for lab in geel)
    uit: dict[str, Any] = {k: per.get(k, 0) for k in OORSPRONG}
    uit.update(
        human_review=len(geel),
        juridisch=per.get("substantive_legal_review", 0),
        technisch=len(geel) - per.get("substantive_legal_review", 0),
        detector_conflict_review=sum(t.reden == "DETECTOR_CONFLICT" for t in twijfels),
        span_review=sum(t.reden == "ZELFDE_SPAN" for t in twijfels),
        reviewer_ongeldig=sum(t.regel == "R-ONGELDIG" for t in transities),
    )
    return uit
