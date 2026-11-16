"""Een hele bronnenrun op een set met deelvragen, met en zonder overzicht_streng, tegen de opname (aangevuld)."""
import json, sys
from dataclasses import replace
from eval.bronselectie_eval import SETS, AanvullendeGraaf, _echte_graaf, laad_set, _raakt
from agent import bronnen_vinden as bv, deelvraag_zoeken as dz, overzicht, regelingnamen
naam = sys.argv[1]; s = laad_set(naam); pad = SETS / naam / "graafantwoorden.json"
g = AanvullendeGraaf(json.loads(pad.read_text()), _echte_graaf())
invoer = {"naam": s["naam"], "analysevraag": s["analysevraag"], "context": [], "kern": [],
          "deelvragen": [{"id": f"d{i}", "vraag": v} for i, v in enumerate(s["deelvragen"])],
          "regelingen": list(s["regelingen"]),
          "dossier": {k: s.get(k, "") for k in ("aanleiding", "doel", "praktijkvoorbeeld", "context", "gebeurtenis")}}
for label, prof in (("standaard", dz.STANDAARD_PROFIEL), ("overzicht_streng", replace(dz.STANDAARD_PROFIEL, overzicht_streng=True))):
    regelingnamen._CACHE.clear(); overzicht._REGELINGEN_CACHE.clear()
    uit = bv.vind(g, invoer, profiel=prof)
    ks = uit["kandidaten"]
    zonder = [k for k in ks if not any(b["methode"] == "deelvraag" for b in k["bewijs"])]
    nodig = [v for v in s["verwacht"] if v["rol"] in ("kern", "afhankelijkheid")]
    gevonden = sum(1 for v in {v["bron_iri"] for v in nodig} if any(_raakt(k["bron_iri"], v) for k in ks))
    uitgesloten = sum(1 for k in ks if any(_raakt(k["bron_iri"], u["bron_iri"]) for u in s["uitgesloten"]))
    print(f"{naam} | {label} | kandidaten {len(ks)} | zonder deelvraag {len(zonder)} | kern {sum(k['rol']=='kern' for k in ks)} "
          f"| verwacht nodig gevonden {gevonden}/{len({v['bron_iri'] for v in nodig})} | uitgesloten {uitgesloten} | methoden {sorted(uit['meting'])}")
g.close(); pad.write_text(json.dumps(g.opname, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
