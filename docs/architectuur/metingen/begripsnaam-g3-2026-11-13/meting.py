"""G3-meting zonder model: per referentieset de kaarten zonder model, en wat de twee nieuwe naamtoetsen doen."""
import json, sys
from collections import Counter
from eval.begrippen_eval import laad, manifest_uit
from agent.begrippen_pipeline import keten, verdieping
from agent.begrippen_pipeline.model import Aandacht

NIEUW = {"NAAM_MET_ONTKENNING", "NAAM_MET_AFKORTING"}
uit = {}
for versie in ("v1", "heldout-v1", "heldout-v2"):
    bronnen, cases, _ = laad(versie)
    m = manifest_uit(bronnen, cases)
    u = keten.analyseer(m)
    kaarten, _ = verdieping.kaartopdrachten(m, u, u.groepen)
    tel = Counter(p for k in kaarten.values() for p in k.aandachtspunten if p in NIEUW)
    geraakt = [{"naam": k.naam, "signalen": sorted(set(k.aandachtspunten) & NIEUW),
                "alleen_daardoor_geel": k.aandacht is Aandacht.GEEL and not (set(k.aandachtspunten) - NIEUW)
                and k.herkomst is not None and k.herkomst.value == "letterlijk"}
               for k in kaarten.values() if set(k.aandachtspunten) & NIEUW]
    uit[versie] = {"kaarten": len(kaarten), "per_code": dict(tel), "geraakt": geraakt,
                   "geel": sum(k.aandacht is Aandacht.GEEL for k in kaarten.values())}
print(json.dumps(uit, ensure_ascii=False, indent=1))
