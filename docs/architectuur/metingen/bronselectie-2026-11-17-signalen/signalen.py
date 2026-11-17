"""Stap 2–4: signalen een voor een, de bovengrens van het vertalen, en de gevoeligheid per knop. Offline op de
opname (opname/<bwb>.json), zonder model. Eén ranglijst per deelvraag over alle eenheden van het zoekbereik."""
from __future__ import annotations

import glob, json, math, re, statistics, sys
from collections import defaultdict
from dataclasses import dataclass, replace

import graaf  # noqa: F401  (zet het pad naar graph-qa)
from agent.zoekvragen import termen_van_deelvraag
from agent.zoektermen import _stamdeel, zoektermen

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[4]) + "/"
K1, B = 1.2, 0.75
WOORD = re.compile(r"[a-zà-ÿ0-9]+")
KOPRUIS = {"artikel", "lid", "hoofdstuk", "afdeling", "paragraaf", "titel", "titeldeel", "onderdeel", "algemeen",
           "algemene", "bepalingen", "bepaling", "overige", "slotbepalingen", "inleidende", "begripsbepalingen"}


@dataclass(frozen=True)
class Knoppen:
    w_tekst: float = 1.0
    w_kop: float = 0.0
    w_anker: float = 0.0
    beta: float = 0.0          # belang van verwijzingen
    w_wet: float = 2.0         # gewicht van een wetsterm tegenover een eigen woord
    cap: int = 0               # hoogstens zoveel per regeling in de top N (0 = geen grens)
    vertaling: str = "geen"    # geen | gebeurtenis | orakel


# --- de opname ------------------------------------------------------------------------------------------------------

def _binnen(iri, ander):
    return iri == ander or iri.startswith(ander + ":") or (":id:" in ander and iri.startswith(ander + "%2F"))


def raakt(a, b):
    return _binnen(a, b) or _binnen(b, a)


def _artikel(iri):
    m = re.match(r"(urn:bwb:BWBR\d+:artikel:[^:]+)", iri)
    return m.group(1) if m else iri


def tokens(t):
    return WOORD.findall((t or "").casefold())


def laad_regeling(r):
    d = json.load(open(f"opname/{r}.json"))
    e = d["eenheden"]
    anker = defaultdict(list)
    bronnen = defaultdict(set)
    for x in d["inkomend"]:
        doel, bron, t, a = x["doel"], x["bron"], x.get("t") or "", x.get("anker") or ""
        doelen = [u for u in e if raakt(u, doel)] if doel not in e else [doel]
        if doel not in e:
            doelen = [u for u in e if _binnen(u, doel) or _binnen(doel, u)]
        plek = t.find(a) if a else -1
        venster = (t[max(0, plek - 120):plek + len(a)] if plek >= 0 else t[:200])
        for u in doelen:
            if _artikel(bron) == _artikel(u):
                continue
            if bron not in bronnen[u]:
                bronnen[u].add(bron)
                anker[u].append(venster)
    uit = {}
    for u, v in e.items():
        kop = " ".join(v["kop"] + [v.get("label") or ""])
        uit[u] = {"bwb": r, "tekst": tokens(v["tekst"]), "kop": tokens(kop), "anker": tokens(" ".join(anker[u])),
                  "indeg": len(bronnen[u]), "kop_ruw": v["kop"], "label": v.get("label") or ""}
    return uit


REG = {}


def regeling(r):
    if r not in REG:
        REG[r] = laad_regeling(r)
    return REG[r]


# --- de sets ---------------------------------------------------------------------------------------------------------

def sets():
    uit = []
    for f in sorted(glob.glob(ROOT + "docs/wetsanalyse/referentieset-bronselectie/*/set.json")):
        d = json.load(open(f))
        if d.get("deelvragen"):
            uit.append((f.split("/")[-2], d, d["verwacht"]))
    for c, n in [("LB-07", "lb-07-beslistermijn"), ("LB-08", "lb-08-terugvordering-toeslag"),
                 ("LB-09", "lb-09-achteraf-belasting")]:
        d = json.load(open(ROOT + f"docs/lex-bench/bronselectie/pilot/{n}/set.json"))
        t = json.load(open(ROOT + f"docs/architectuur/metingen/lex-bench-2026-11-17-pilot/{c}/teamverwachting.json"))
        uit.append((c, d, t["verwacht"]))
    return uit


def vraag_van(d, i):
    x = d["deelvragen"][i]
    return x if isinstance(x, str) else x.get("vraag", "")


# --- zoeken ---------------------------------------------------------------------------------------------------------

class Index:
    def __init__(self, regelingen):
        self.ids, self.e = [], []
        for r in regelingen:
            for u, v in regeling(r).items():
                self.ids.append(u)
                self.e.append(v)
        self.n = len(self.ids)
        self.gem = {f: (sum(len(v[f]) for v in self.e) / self.n) or 1 for f in ("tekst", "kop", "anker")}
        self.maxdeg = max((v["indeg"] for v in self.e), default=0)
        self._df = {}

    def tf(self, v, f, stam):
        return sum(1 for w in v[f] if stam in w)

    def df(self, stam, kn):
        sleutel = (stam, kn.w_kop > 0, kn.w_anker > 0)
        if sleutel not in self._df:
            velden = ["tekst"] + (["kop"] if kn.w_kop else []) + (["anker"] if kn.w_anker else [])
            self._df[sleutel] = sum(1 for v in self.e if any(stam in w for f in velden for w in v[f]))
        return self._df[sleutel]

    def zoek(self, termen: dict[str, float], kn: Knoppen):
        """termen: stam → gewicht. BM25F (velden met gewicht en eigen lengtenormalisatie), plus het belang van
        verwijzingen als log(1+indeg), genormaliseerd."""
        scores = []
        for i, v in enumerate(self.e):
            s = 0.0
            for stam, g in termen.items():
                tf = 0.0
                for f, w in (("tekst", kn.w_tekst), ("kop", kn.w_kop), ("anker", kn.w_anker)):
                    if w:
                        n = self.tf(v, f, stam)
                        if n:
                            tf += w * n / (1 - B + B * len(v[f]) / self.gem[f])
                if tf:
                    df = self.df(stam, kn)
                    idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
                    s += g * idf * tf / (K1 + tf)
            scores.append(s)
        top = max(scores) or 1
        if kn.beta and self.maxdeg:
            ld = math.log1p(self.maxdeg)
            scores = [s / top + (kn.beta * math.log1p(v["indeg"]) / ld if s > 0 else 0) for s, v in zip(scores, self.e)]
        volgorde = sorted((i for i in range(self.n) if scores[i] > 0), key=lambda i: (-scores[i], self.ids[i]))
        return [self.ids[i] for i in volgorde], {self.ids[i]: self.e[i] for i in volgorde}


def spreid(lijst, info, cap, n):
    if not cap:
        return lijst
    per, top, rest = defaultdict(int), [], []
    for u in lijst:
        if len(top) < n and per[info[u]["bwb"]] < cap:
            top.append(u)
            per[info[u]["bwb"]] += 1
        else:
            rest.append(u)
    return top + rest


def orakeltermen(verwacht_dv, idx_info):
    """Bovengrens van het vertalen: de woorden uit de diepste kop boven de verwachte kernbepalingen."""
    woorden = []
    for v in verwacht_dv:
        if v.get("rol") != "kern":
            continue
        info = idx_info.get(v["bron_iri"])
        if not info:
            # verwacht op een hoger niveau dan een eenheid: neem een eenheid daarbinnen
            info = next((x for u, x in idx_info.items() if _binnen(u, v["bron_iri"])), None)
        if not info:
            continue
        koppen = [k for k in info["kop_ruw"] if not re.match(r"^(Artikel|Lid)\b", k)]
        if info["label"] and not re.match(r"^(Artikel|Lid)\b", info["label"]):
            koppen.append(info["label"])
        if koppen:
            diepst = koppen[-1]
            woorden += [w for w in zoektermen(re.sub(r"^[^–]*–", "", diepst)) if w not in KOPRUIS]
    return list(dict.fromkeys(woorden))


def termen_voor(d, i, kn, verwacht_dv, alle_info):
    eigen = {_stamdeel(w): 1.0 for w in termen_van_deelvraag(vraag_van(d, i))}
    wet = []
    if kn.vertaling == "gebeurtenis":
        wet = zoektermen((d.get("gebeurtenis") or ""))
    elif kn.vertaling == "orakel":
        wet = orakeltermen(verwacht_dv, alle_info)
    for w in wet:
        eigen[_stamdeel(w)] = max(eigen.get(_stamdeel(w), 0), kn.w_wet)
    return eigen


# --- meten ---------------------------------------------------------------------------------------------------------

def meet(kn: Knoppen, ns=(10, 30)):
    uit = {}
    for naam, d, verwacht in sets():
        idx = Index(d.get("regelingen") or [])
        alle_info = dict(zip(idx.ids, idx.e))
        per_n = {n: [0, 0] for n in ns}
        ndcg = []
        buiten = 0
        for i in range(len(d["deelvragen"])):
            vdv = [v for v in verwacht if v.get("deelvraag") == i]
            nodig = [v for v in vdv if v.get("rol") in ("kern", "afhankelijkheid")]
            if not nodig:
                continue
            termen = termen_voor(d, i, kn, vdv, alle_info)
            lijst, info = idx.zoek(termen, kn)
            lijst = spreid(lijst, info, kn.cap, max(ns))
            for v in nodig:
                if not any(_binnen(u, v["bron_iri"]) or _binnen(v["bron_iri"], u) for u in idx.ids):
                    buiten += 1
            for n in ns:
                top = lijst[:n]
                per_n[n][0] += sum(1 for v in nodig if any(raakt(u, v["bron_iri"]) for u in top))
                per_n[n][1] += len(nodig)
            # nDCG@10: winst kern 2, afhankelijkheid 1; elke verwachte bepaling telt één keer
            gain = {v["bron_iri"]: (2 if v["rol"] == "kern" else 1) for v in nodig}
            gezien, dcg = set(), 0.0
            for r, u in enumerate(lijst[:10]):
                g = 0
                for iri, w in gain.items():
                    if iri not in gezien and raakt(u, iri):
                        gezien.add(iri)
                        g = max(g, w)
                dcg += g / math.log2(r + 2)
            ideaal = sorted(gain.values(), reverse=True)[:10]
            idcg = sum(g / math.log2(r + 2) for r, g in enumerate(ideaal))
            ndcg.append(dcg / idcg if idcg else 0)
        uit[naam] = {**{f"r@{n}": per_n[n][0] / per_n[n][1] for n in ns},
                     **{f"t@{n}": f"{per_n[n][0]}/{per_n[n][1]}" for n in ns},
                     "ndcg@10": statistics.mean(ndcg), "buiten_bereik": buiten}
    return uit


def gemiddeld(res, m):
    return statistics.mean(v[m] for v in res.values())


def toon(label, res, ns=(10, 30)):
    print(f"\n## {label}")
    print("set | " + " | ".join(f"recall nodig @{n}" for n in ns) + " | nDCG@10")
    for k, v in res.items():
        print(k, *[f"{v[f'r@{n}']:.2f} ({v[f't@{n}']})" for n in ns], f"{v['ndcg@10']:.2f}", sep=" | ")
    print("gemiddeld over sets", *[f"{gemiddeld(res, f'r@{n}'):.2f}" for n in ns], f"{gemiddeld(res, 'ndcg@10'):.2f}", sep=" | ")
