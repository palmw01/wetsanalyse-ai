import json, sys
from dataclasses import replace
from eval import bronselectie_eval as be
from agent import deelvraag_zoeken as dz
P = dz.STANDAARD_PROFIEL
kand = replace(P, termen_idf=True, verwijzingen=True, brug_omschrijving=True, overzicht_streng=True)
routes = {"standaard woorden": be._met_profiel(P), "kandidaten woorden": be._met_profiel(kand),
          "standaard zoekvragen": be._zoekvragen_route(P), "kandidaten zoekvragen": be._zoekvragen_route(kand)}
for naam in sys.argv[1:]:
    s = be.laad_set(naam)
    pad = be.SETS / naam / "graafantwoorden.json"
    g = be.AanvullendeGraaf(json.loads(pad.read_text()), be._echte_graaf())
    r = be.meet_intake(g, s, routes)
    g.close(); pad.write_text(json.dumps(g.opname, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(naam, " | ".join(f"{k}: {v['recall_nodig']} (prec {v['precisie']}, uitgesl {v['uitgesloten']})" for k, v in r.items()),
          )
