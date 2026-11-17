import json
from dataclasses import replace, asdict
from signalen import Knoppen, meet, gemiddeld
BASIS = Knoppen(w_kop=2.0, w_anker=1.0, beta=0.3, cap=5, vertaling="gebeurtenis", w_wet=2.0)
NS = (10, 20, 30, 40, 60)
basis = meet(BASIS, NS)
def regel(label, res):
    slechter10 = sum(res[s]["r@10"] < basis[s]["r@10"] - 1e-9 for s in res)
    beter10 = sum(res[s]["r@10"] > basis[s]["r@10"] + 1e-9 for s in res)
    slechter30 = sum(res[s]["r@30"] < basis[s]["r@30"] - 1e-9 for s in res)
    beter30 = sum(res[s]["r@30"] > basis[s]["r@30"] + 1e-9 for s in res)
    print(f"{label:28s} r@10 {gemiddeld(res,'r@10'):.2f} r@30 {gemiddeld(res,'r@30'):.2f} nDCG {gemiddeld(res,'ndcg@10'):.2f} | @10 +{beter10}/-{slechter10} | @30 +{beter30}/-{slechter30}")
uit = {"basis": {"knoppen": asdict(BASIS), "sets": basis}}
print("BASIS:"); regel("basis", basis)
print("kandidaten (recall nodig bij N, gemiddeld):", {n: round(gemiddeld(basis, f"r@{n}"), 2) for n in NS})
for knop, waarden in [("w_kop", [0, 1, 2, 3, 5]), ("w_anker", [0, 0.5, 1, 2, 3]), ("beta", [0, 0.1, 0.2, 0.3, 0.5, 1.0]),
                      ("w_wet", [1, 1.5, 2, 3, 5]), ("cap", [0, 3, 5, 10])]:
    print(f"\n# {knop}")
    for w in waarden:
        kn = replace(BASIS, **{knop: w})
        res = meet(kn, NS)
        uit[f"{knop}={w}"] = {"knoppen": asdict(kn), "sets": res}
        regel(f"{knop}={w}", res)
json.dump(uit, open("resultaten-stap4.json", "w"), ensure_ascii=False, indent=1)
