"""Analyseer de uitsnede van één regeling uit de LiDO-dump (`filter_dump.py`) per artikel, over alle versies.

Gebruik: python -I analyse_dump.py <BWB-id> <uitsnede.nt.gz> <uit.json> [uitkomst.json van de spike] [run-sleutel]

Schrijft naast <uit.json> ook <uit>-ecli.json en <uit>-ecli-versie.json (de ECLI's per artikel en per versie), alleen
voor de controle tegen de live diensten; die horen niet in de repo.

- Versies: elk onderwerp `…/bwb/id/<BWB>/<label-id>/<geldig>/<zicht>` met `dcterms:type "Artikel"`; alle versies van
  een artikel delen het label-id, dus de vereniging over versies is een groepering op het label – zonder te zoeken.
- Links: de `LinkAct`-knopen (`linktVan`, `linktNaar`, `heeftLinktype`, `geimporteerdDoor`), plus ter vergelijking de
  directe triple `linkt`.
- Uitspraken bij een artikel: inkomende LinkActs van `…/jurisprudentie/id/ECLI…` naar een versie van dat artikel.
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import resource
import sys
import time

T = "http://linkeddata.overheid.nl/terms/"
VERSIE_RE = re.compile(r"^http://linkeddata\.overheid\.nl/terms/bwb/id/(BWBR\d{7})/(\d+)/([0-9-]+)/([0-9-]+)$")
NT_RE = re.compile(r'^<([^>]*)> <([^>]*)> (.*) \.\s*$')


def obj(o: str) -> str:
    if o.startswith("<"):
        return o[1:-1]
    m = re.match(r'^"(.*)"', o)
    return m.group(1) if m else o


def main() -> None:
    bwb, pad, uit = sys.argv[1], sys.argv[2], sys.argv[3]
    spike = json.load(open(sys.argv[4]))[sys.argv[5]] if len(sys.argv) > 5 else None
    t0 = time.monotonic()
    versies: dict[str, dict] = {}            # versie-uri -> eigenschappen
    acts: dict[int, dict] = collections.defaultdict(dict)
    linkt_direct = collections.Counter()      # (van-soort) -> aantal, alleen naar een artikelversie
    for ruw in gzip.open(pad, "rt", encoding="utf-8", errors="replace"):
        m = NT_RE.match(ruw)
        if not m:
            continue
        s, p, o = m.group(1), m.group(2), m.group(3)
        mv = VERSIE_RE.match(s)
        if mv and mv.group(1) == bwb:
            v = versies.setdefault(s, {"label": mv.group(2), "geldig": mv.group(3), "zicht": mv.group(4)})
            kort = p.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if kort in ("type", "heeftOnderdeelNummer", "isGeldigVanaf", "geimporteerdDoor", "wijzigingOmschrijving",
                        "replaces", "isReplacedBy"):
                v.setdefault(kort, set()).add(obj(o))
            continue
        if "/Regellinks/" in s:
            a = acts[hash(s)]
            kort = p.rsplit("/", 1)[-1]
            if kort in ("linktVan", "linktNaar", "heeftLinktype", "geimporteerdDoor", "heeftBron"):
                a.setdefault(kort, set()).add(obj(o))
            continue
        if p == T + "linkt":
            naar = obj(o)
            mn = VERSIE_RE.match(naar)
            if mn and mn.group(1) == bwb:
                soort = "jurisprudentie" if "/jurisprudentie/id/" in s else ("bwb" if "/bwb/id/" in s else "overig")
                linkt_direct[soort] += 1
    # alleen artikelen
    art = {v: d for v, d in versies.items() if "Artikel" in d.get("type", set())}
    per_label: dict[str, list[str]] = collections.defaultdict(list)
    for v, d in art.items():
        per_label[d["label"]].append(v)
    nr_van = {}
    for lab, vs in per_label.items():
        nrs = set().union(*[art[v].get("heeftOnderdeelNummer", set()) for v in vs])
        nr_van[lab] = sorted(nrs)
    # links per versie
    juris = collections.defaultdict(set)   # versie -> {ecli}
    linktypen = collections.Counter()
    imports_links = collections.Counter()
    eerst: dict[tuple[str, str], str] = {}   # (versie, ecli) -> vroegste link-import
    for a in acts.values():
        for naar in a.get("linktNaar", ()):
            if naar not in art:
                continue
            for van in a.get("linktVan", ()):
                groep = ("Jurisprudentie" if "/jurisprudentie/id/" in van else
                         "Wet" if "/bwb/id/" in van else "Officiele overheidspublicatie" if "/oep/id/" in van else "Overig")
                for lt in a.get("heeftLinktype", {"?"}):
                    linktypen[("inkomend", groep, lt.rsplit("/", 1)[-1])] += 1
                if groep == "Jurisprudentie":
                    ecli = van.rsplit("/", 1)[-1]
                    juris[naar].add(ecli)
                    imp = min((i.rsplit("/", 1)[-1] for i in a.get("geimporteerdDoor", ())), default="?")
                    eerst[(naar, ecli)] = min(eerst.get((naar, ecli), "~"), imp)
                for imp in a.get("geimporteerdDoor", ()):
                    imports_links[imp.rsplit("/", 1)[-1][:13]] += 1   # links-JJJJ-MM
        for van in a.get("linktVan", ()):
            if van in art:
                for naar in a.get("linktNaar", ()):
                    groep = ("Jurisprudentie" if "/jurisprudentie/id/" in naar else
                             "Wet" if "/bwb/id/" in naar else "Officiele overheidspublicatie" if "/oep/id/" in naar else "Overig")
                    for lt in a.get("heeftLinktype", {"?"}):
                        linktypen[("uitgaand", groep, lt.rsplit("/", 1)[-1])] += 1
    per_artikel = {}
    alle_ecli = set()
    paren = paren_huidig = 0
    for lab, vs in per_label.items():
        vs.sort(key=lambda v: (art[v]["geldig"], art[v]["zicht"]))
        e_all = set().union(*[juris[v] for v in vs])
        e_huidig = juris[vs[-1]]
        # uitspraken die alleen via een link-import na de peildatum van de spike (2 jul 2026) binnenkwamen
        def vroegst(e):
            return min(eerst.get((v, e), "~") for v in vs)
        e_nieuw = {e for e in e_all if vroegst(e) > "links-2026-07-02"}
        alle_ecli |= e_all
        paren += len(e_all)
        paren_huidig += len(e_huidig)
        per_artikel[lab] = {"nr": nr_van[lab], "versies": len(vs), "uitspraken": len(e_all),
                            "uitspraken_huidig": len(e_huidig),
                            "uitspraken_import_na_2026_07_02": len(e_nieuw), "eerste": art[vs[0]]["geldig"],
                            "laatste": art[vs[-1]]["geldig"],
                            "vervangt_relaties": sum(len(art[v].get("replaces", ())) + len(art[v].get("isReplacedBy", ()))
                                                     for v in vs)}
    imports_bwb = collections.Counter(i.rsplit("/", 1)[-1] for d in art.values() for i in d.get("geimporteerdDoor", ()))
    res = {
        "bwb": bwb,
        "artikelen_label_ids": len(per_label),
        "artikelversies": len(art),
        "paren_alle_versies": paren,
        "paren_huidige_versie": paren_huidig,
        "unieke_ecli": len(alle_ecli),
        "artikelen_met_uitspraak": sum(1 for x in per_artikel.values() if x["uitspraken"]),
        "linkacts_gelezen": len(acts),
        "linkt_direct_naar_artikelversie": dict(linkt_direct),
        "linktypen": {" | ".join(k): v for k, v in linktypen.most_common()},
        "nieuwste_geldig": max((d["geldig"] for d in art.values()), default=""),
        "imports_bwb_laatste": sorted(imports_bwb)[-5:],
        "imports_links_per_maand": dict(sorted(imports_links.items())),
        "seconden": round(time.monotonic() - t0, 1),
        "piek_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "per_artikel": per_artikel,
    }
    if spike:
        vgl = []
        for nr, s in spike["per_artikel"].items():
            d = per_artikel.get(s["label_id"])
            vgl.append({"artikel": nr, "label_id": s["label_id"],
                        "spike_versies": s["versies"], "dump_versies": d["versies"] if d else 0,
                        "spike_uitspraken": s["uitspraken"], "dump_uitspraken": d["uitspraken"] if d else 0,
                        "spike_huidig": s["uitspraken_huidig"], "dump_huidig": d["uitspraken_huidig"] if d else 0,
                        "dump_import_na_2026_07_02": d["uitspraken_import_na_2026_07_02"] if d else 0})
        res["vergelijking_spike"] = vgl
    json.dump(res, open(uit, "w"), ensure_ascii=False, indent=1)
    # de ECLI's per label-id, alleen voor de controle tegen de live diensten (niet voor de repo)
    json.dump({lab: sorted(set().union(*[juris[v] for v in vs])) for lab, vs in per_label.items()},
              open(uit.replace(".json", "-ecli.json"), "w"))
    json.dump({v: sorted(e) for v, e in juris.items()}, open(uit.replace(".json", "-ecli-versie.json"), "w"))
    kort = {k: v for k, v in res.items() if k not in ("per_artikel", "vergelijking_spike")}
    print(json.dumps(kort, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
