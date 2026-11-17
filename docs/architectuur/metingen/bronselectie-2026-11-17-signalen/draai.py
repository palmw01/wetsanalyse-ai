"""Draait stap 2–4 en schrijft resultaten.json."""
import json
from dataclasses import replace, asdict
from signalen import Knoppen, meet, toon, gemiddeld

uit = {}


def run(label, kn):
    res = meet(kn)
    uit[label] = {"knoppen": asdict(kn), "sets": res}
    toon(label, res)
    return res


# stap 2: signalen een voor een
C0 = Knoppen()
C1 = replace(C0, w_kop=2.0)
C2 = replace(C1, w_anker=1.0)
C3 = replace(C2, beta=0.3)
C4 = replace(C3, cap=5)
for lab, kn in [("C0 tekst", C0), ("C1 + kop", C1), ("C2 + verwijzende zin", C2), ("C3 + belang verwijzingen", C3),
                ("C4 + spreiding", C4)]:
    run(lab, kn)
# los: elk signaal alleen bij de tekst
run("los: tekst + verwijzende zin", replace(C0, w_anker=1.0))
run("los: tekst + belang verwijzingen", replace(C0, beta=0.3))

# stap 3: vertalen
run("V1 gebeurtenis als wetsterm", replace(C4, vertaling="gebeurtenis"))
run("V2 orakel (bovengrens)", replace(C4, vertaling="orakel"))

json.dump(uit, open("resultaten-stap2-3.json", "w"), ensure_ascii=False, indent=1)
