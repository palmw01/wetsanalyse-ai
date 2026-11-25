"""Wat er tussen twee uitvoeren van `kandidaten.py` verschilt, per soort verschil met hoogstens drie voorbeelden."""
import collections
import json
import sys


def soort(x, y) -> str:
    if x is None:
        return "nieuw:" + ",".join(y[5])
    if y is None:
        return "weg:" + ",".join(c for c in x[5] if c in ("DATE_ASSIGNMENT", "LEGAL_EFFECT_CLAUSE", "TEMPORAL_RECURRENCE"))
    delen = []
    if x[3] != y[3]:
        delen.append(f"klassen {'/'.join(c[:6] for c in x[3])}→{'/'.join(c[:6] for c in y[3])}")
    if ev := set(y[5]) ^ set(x[5]):
        delen.append("bewijs " + ",".join(sorted(ev)))
    if x[4] != y[4]:
        delen.append(f"status {x[4]}→{y[4]}")
    if x[6] != y[6]:
        delen.append(f"besluit {x[6]}→{y[6]}")
    return "; ".join(delen)


def main() -> None:
    with open(sys.argv[1]) as f:
        voor = json.load(f)
    with open(sys.argv[2]) as f:
        na = json.load(f)
    tel, voorbeelden, geraakt = collections.Counter(), collections.defaultdict(list), 0
    for sleutel in voor:
        a = {tuple(x[:2]): x for x in voor[sleutel]["k"]}
        b = {tuple(x[:2]): x for x in na[sleutel]["k"]}
        geraakt += a != b
        for sp in a.keys() | b.keys():
            if a.get(sp) == b.get(sp):
                continue
            s = soort(a.get(sp), b.get(sp))
            tel[s] += 1
            if len(voorbeelden[s]) < 3:
                voorbeelden[s].append((sleutel[-60:], (a.get(sp) or b.get(sp))[2][:90]))
    print("bepalingen:", len(voor), "geraakt:", geraakt)
    for s, c in tel.most_common():
        print(f"{c:4} {s}")
        for e in voorbeelden[s]:
            print("       ", e)


if __name__ == "__main__":
    main()
