"""Controle: voor een paar artikelen de ECLI's die de live diensten nu geven (route *ref*, zoals de spike en de
connector) naast de ECLI's uit de dump. Alleen lezend, met de pauze en cache van de spike.

Gebruik: python -I vergelijk_live.py <pad naar lido_spike.py-map> <BWB> <dump-ecli.json> <iw.json> <uit.json> <art> …
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
import lido_spike as L  # noqa: E402


def main() -> None:
    bwb, dump_ecli, dump_res, uit = sys.argv[2], json.load(open(sys.argv[3])), json.load(open(sys.argv[4])), sys.argv[5]
    label_van = {tuple(v["nr"]): lab for lab, v in dump_res["per_artikel"].items()}
    cache = pathlib.Path(uit).parent / "cache-live"
    cache.mkdir(exist_ok=True)
    rij = []
    for nr in sys.argv[6:]:
        vs = L.versies(bwb, nr, cache)
        live = {l["doel"].rstrip("/").split("/")[-1] for v in vs for l in L.links(v, cache)
                if l["groep"] == "Jurisprudentie" and l["richting"] == "inkomende"}
        lab = label_van.get((nr,))
        dump = set(dump_ecli.get(lab, []))
        rij.append({"artikel": nr, "label_id": lab, "live_versies": len(vs),
                    "dump_versies": dump_res["per_artikel"].get(lab, {}).get("versies", 0),
                    "live": len(live), "dump": len(dump), "beide": len(live & dump),
                    "alleen_live": sorted(live - dump), "alleen_dump_aantal": len(dump - live)})
        print(json.dumps({k: v for k, v in rij[-1].items() if k != "alleen_live"} | {"alleen_live": len(live - dump)}),
              flush=True)
    json.dump({"stat": L.STAT, "artikelen": rij}, open(uit, "w"), indent=1)
    print(json.dumps(L.STAT))


if __name__ == "__main__":
    main()
