import json, sys, statistics
from agent.begrippen_pipeline import betekenis, toetsen
from agent.begrippen_pipeline.model import Fragment, Herkomst, Kaart
from eval.betekenisonderzoek_eval import casus, laad
data = laad()
LEDEN = {"A": ("e0",), "B": ("e0", "e1")}; NAAM = {"A": "herziening", "B": "belasting"}
KERN = {"ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE", "RECHTSGEVOLG_IN_DEFINITIE", "AFLEIDING_IN_DEFINITIE", "TEGENBEWIJS_IN_ONDERZOEK"}
def defs(rij):
    uit = []
    k = rij["kaart"]
    if k["definitie"] and k["herkomst"] != "letterlijk":
        uit.append(("kaart", k["definitie"], k["herkomst"], k["fragmenten"], k.get("duiding")))
    for v in rij["scherper"]["voorstellen"]:
        d = v["definitie"]; uit.append(("scherper", d["definitie"], d["herkomst"], d["fragmenten"], v.get("duiding")))
    return uit
rapport = {}
for versie in ("voor", "na"):
    r = json.load(open(f"{sys.argv[1]}/{versie}.json"))
    rij_uit = {"definities": [], "tokens": {"kaart": [], "scherper": [], "voorbeelden": []}, "duur_s": [],
               "voorbeelden": [], "meldingen": []}
    for rij in r["runs"]:
        c = rij["casus"]; m, o = casus(data, c)
        d = betekenis.dossier(m, o, LEDEN[c], [NAAM[c]])
        for bron, tekst, h, frs, duiding in defs(rij):
            kaart = Kaart(groep_id="G0", naam=NAAM[c], definitie=tekst, herkomst=Herkomst(h),
                          fragmenten=tuple(Fragment(**f) for f in frs))
            codes = [x for x in toetsen.signalen(kaart, [], d) if x in KERN]
            rij_uit["definities"].append({"run": rij["run"], "casus": c, "bron": bron, "herkomst": h, "definitie": tekst,
                                          "kern_signalen": codes, "duiding": duiding})
        for a in ("kaart", "scherper", "voorbeelden"):
            rij_uit["tokens"][a].append(rij[a]["tokens"])
        rij_uit["duur_s"].append(sum(rij[a]["s"] for a in ("kaart", "scherper", "voorbeelden")))
        vb = rij["voorbeelden"]["voorstellen"]
        rij_uit["voorbeelden"].append({"casus": c, "aantal": len(vb), "niet": sum(v["oordeel"] == "niet" for v in vb),
                                       "onzeker": sum(v["oordeel"] == "onzeker" for v in vb),
                                       "soorten": [v.get("soort_voorbeeld", "") for v in vb],
                                       "toetst_anders": sum(v.get("toetst", "begrip") != "begrip" for v in vb),
                                       "dubbel": "SEMANTISCH_DUBBEL" in sum((v["aandachtspunten"] for v in vb), [])})
        for a in ("scherper", "voorbeelden"):
            if rij[a]["melding"]:
                rij_uit["meldingen"].append({"casus": c, "actie": a, "melding": rij[a]["melding"]})
        if not rij["kaart"]["definitie"]:
            rij_uit["meldingen"].append({"casus": c, "actie": "kaart", "melding": rij["kaart"]["motivatie"],
                                         "aandachtspunten": rij["kaart"]["aandachtspunten"]})
    defs_ = rij_uit["definities"]
    rij_uit["samen"] = {"definities": len(defs_), "met_kernsignaal": sum(bool(x["kern_signalen"]) for x in defs_),
                        "tokens_mediaan": {a: statistics.median(v) for a, v in rij_uit["tokens"].items()},
                        "duur_mediaan_s": statistics.median(rij_uit["duur_s"])}
    rapport[versie] = rij_uit
json.dump(rapport, open(f"{sys.argv[1]}/score.json", "w"), ensure_ascii=False, indent=1)
for v in ("voor", "na"):
    print("==", v, rapport[v]["samen"])
    for x in rapport[v]["definities"]:
        print(f'  {x["casus"]}{x["run"]} {x["bron"]:8} {x["herkomst"]:12} {x["kern_signalen"]} | {x["definitie"][:150]}' + (f' | duiding {x["duiding"]}' if x["duiding"] else ""))
    for x in rapport[v]["voorbeelden"]:
        print("  vb", x)
    for x in rapport[v]["meldingen"]:
        print("  melding", x["casus"], x["actie"], str(x["melding"])[:160], x.get("aandachtspunten", ""))
