"""Lex Bench, meetas bronselectie: de scorekaart van arm L1, en de uitkomst op de (vroegere) blinde sets.

**De scorekaart (LB1, plan §3, §5, §6, §9).** Het manifest (`docs/lex-bench/bronselectie/manifest.json`) noemt de
casussen met niveau en gebruik. Arm L1 is de bronselectie zonder model, met de route die de bronnenrun ook neemt
(`ROUTE_L1`). Per casus: recall (nodig en alles), precisie en overlap, elk met teller en noemer, en de verschillen als
voorstel voor een categorie (*Lex mist*, *Lex onterecht*; *team mist* en *twijfel* vragen de reviewer van LB2). Dan het
rapport per gebruik en niveau, altijd ontwikkeling en blind apart, zonder totaalcijfer. Een run gaat als meetmap naar
`docs/architectuur/metingen/lex-bench-<datum>-<naam>/` (`run.json`, `rapport.json`, `README.md`), en een bestaande map
wordt nooit overschreven: meetbestanden zijn bewijs. `--dashboard` leest die mappen en schrijft
`tools/lex-bench/data.js` voor de pagina in `tools/lex-bench/`.

    python -m eval.lex_bench --manifest             # het manifest opnieuw uit de sets (na een wijziging aan een set)
    python -m eval.lex_bench --l1 nulpunt           # een run van L1 als meetmap
    python -m eval.lex_bench --dashboard            # tools/lex-bench/data.js uit de meetmappen

**De vroegere blinde sets.**

Plan: `docs/architectuur/plan-lex-bench.md` (§4.5, §20.4). Een blinde set wordt één keer gemeten; daarna is hij een
ontwikkelset. Zijn uitkomst hoort niet als pin in de unitsuite: wie de code afstemt, ziet de test dan rood worden, en
de set is niet meer blind voor het afstemmen. Daarom staat die uitkomst hier, in `docs/lex-bench/bronselectie/held-out.json`
(met de meting waar hij vandaan komt), en zegt dit script wat er nu anders is. **Het faalt niet op een verschil**: de score
is een hulpmiddel, geen poort (plan §1). De unitsuite houdt voor deze sets alleen het pad zonder model en de vorm
(`tests/evals/test_bronselectie_eval.py`).

Offline, tegen de opnames van de graaf: geen model, geen graaf, nul tokens.

    python -m eval.lex_bench               # het verschil per set en route, als tabel
    python -m eval.lex_bench --json uit.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from eval.bronselectie_eval import ROUTES, SETS, OpnameGraaf, _raakt, laad_set, meet_intake
from eval.wortel import WORTEL as WORTEL_REPO

WORTEL = WORTEL_REPO
HELD_OUT = WORTEL / "docs" / "lex-bench" / "bronselectie" / "held-out.json"
MANIFEST = WORTEL / "docs" / "lex-bench" / "bronselectie" / "manifest.json"
METINGEN = WORTEL / "docs" / "architectuur" / "metingen"
DASHBOARD_DATA = WORTEL / "tools" / "lex-bench" / "data.js"
#: De route van arm L1: dezelfde als `bronnen_vinden._deelvraag` (zoekvragen vanaf de gebeurtenis samen met de
#: woordenroute; zonder gebeurtenis alleen de woordenroute), met het standaardprofiel.
ROUTE_L1 = "zoekvragen standaard (stap 8)"
VERSIE = "bench-bronselectie-v1"
NIVEAUS = ("makkelijk", "gemiddeld", "moeilijk")
GEBRUIK = ("ontwikkeling", "blind")
#: De zes bestaande sets (plan §3.2, voorlopige indeling ter vaststelling). Verrekening blijft erbuiten.
CASUSSEN = (
    ("LB-01", "termijnen-deelvragen-concept", "moeilijk"),
    ("LB-02", "kwijtschelding-concept", "moeilijk"),
    ("LB-03", "bestuurdersaansprakelijkheid-concept", "gemiddeld"),
    ("LB-04", "bezwaar-ontvankelijkheid-concept", "gemiddeld"),
    ("LB-05", "invorderbaarheid-deelvragen-concept", "gemiddeld"),
    ("LB-06", "rekeningafspraken-deelvragen-concept", "gemiddeld"),
)
#: De maten die de uitkomst draagt; een route die een maat niet heeft, laat haar weg.
MATEN = ("recall", "recall_nodig", "recall_exact", "precisie", "recall_pool", "uitgesloten")


def laad() -> dict[str, Any]:
    return json.loads(HELD_OUT.read_text(encoding="utf-8"))


def meet_set(naam: str, routes: list[str]) -> tuple[dict[str, dict[str, Any]], int]:
    """De maten per route op één set, offline. Geeft ook het aantal query's dat de opname niet kende."""
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text(encoding="utf-8")))
    gekozen = {r: ROUTES[r] for r in routes if r in ROUTES}
    r = meet_intake(graaf, laad_set(naam), gekozen or None)
    uit = {}
    for route in routes:
        if route in r:
            uit[route] = {m: round(r[route][m], 3) if isinstance(r[route][m], float) else r[route][m]
                          for m in MATEN if m in r[route]}
    return uit, graaf.ontbrekend


def vergelijk(register: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Per set, route en maat: de uitkomst bij de blinde meting, nu, en of ze gelijk zijn."""
    register = register or laad()
    rijen = []
    for s in register["sets"]:
        nu, ontbrekend = meet_set(s["set"], list(s["uitkomst"]))
        for route, maten in s["uitkomst"].items():
            for maat, toen in maten.items():
                waarde = (nu.get(route) or {}).get(maat)
                rijen.append({"set": s["set"], "route": route, "maat": maat, "toen": toen, "nu": waarde,
                              "gelijk": waarde == toen, "opname_onvolledig": ontbrekend > 0, "meting": s["meting"]})
    return rijen


def _tabel(rijen: list[dict[str, Any]]) -> str:
    regels = ["| set | route | maat | bij de blinde meting | nu | |", "|---|---|---|---|---|---|"]
    for r in rijen:
        teken = "" if r["gelijk"] else "anders"
        regels.append(f"| {r['set']} | {r['route']} | {r['maat']} | {r['toen']} | {r['nu']} | {teken} |")
    anders = sum(not r["gelijk"] for r in rijen)
    regels.append(f"\n{len(rijen)} maten, {anders} anders dan bij de blinde meting. Een verschil is geen fout: het zegt wat "
                  "de code sindsdien veranderde op een set die nu ontwikkelset is.")
    return "\n".join(regels)


# --- het manifest (plan §3.3) ---------------------------------------------------------------------------------------

def sha256(pad: Path) -> str:
    return hashlib.sha256(pad.read_bytes()).hexdigest()


def versiehash(casussen: list[dict[str, Any]]) -> str:
    """Eén hash over alle casussen: id en de hash van zijn set, op volgorde van id."""
    regels = sorted(f"{c['casus_id']} {c['sha256']}" for c in casussen)
    return hashlib.sha256("\n".join(regels).encode()).hexdigest()


def bouw_manifest() -> dict[str, Any]:
    """Het manifest uit de sets van nu. Een vrijgegeven versie verandert niet: een andere hash is een nieuwe versie."""
    casussen = []
    for casus_id, naam, niveau in CASUSSEN:
        s = laad_set(naam)
        casussen.append({
            "casus_id": casus_id, "naam": s["naam"], "niveau": niveau, "niveau_status": "voorlopig",
            "gebruik": "ontwikkeling", "pad": f"docs/wetsanalyse/referentieset-bronselectie/{naam}",
            "sha256": sha256(SETS / naam / "set.json"), "schema_versie": s.get("schema_versie"),
            "verwachting": {"status": "vastgesteld" if s.get("status") == "vastgesteld" else "concept",
                            "opgesteld_door": None, "vastgesteld_door": None, "datum": s.get("datum")},
            "opname": {"pad": f"docs/wetsanalyse/referentieset-bronselectie/{naam}/graafantwoorden.json",
                       "sha256": sha256(SETS / naam / "graafantwoorden.json"), "graaftoestand": s.get("graaftoestand")},
            "verwacht": len(s["verwacht"]), "deelvragen": len(s.get("deelvragen", [])),
        })
    return {"schema": "lex-bench-manifest-1", "meetas": "bronselectie", "versie": VERSIE, "hash": versiehash(casussen),
            "vrijgegeven": False, "casussen": casussen,
            "changelog": [{"versie": VERSIE, "wijziging": "De zes bestaande ontwikkelsets (LB1); niveau voorlopig, "
                                                          "verwachting concept, nog niemand vastgesteld."}]}


def laad_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# --- de scorekaart (plan §5) ----------------------------------------------------------------------------------------

def _maat(teller: int, noemer: int) -> dict[str, Any]:
    return {"teller": teller, "noemer": noemer, "waarde": round(teller / noemer, 3) if noemer else None}


def scoor_casus(casus: dict[str, Any], route: str = ROUTE_L1) -> dict[str, Any]:
    """De scorekaart van één casus. Van een blinde casus alleen de aantallen en de categorieën, geen bepalingen."""
    naam = Path(casus["pad"]).name
    s = laad_set(naam)
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text(encoding="utf-8")))
    r = meet_intake(graaf, s, {route: ROUTES[route]})[route]
    per = r["per_deelvraag"]
    som = {k: sum(p[k] for p in per) for k in ("verwacht", "nodig", "aantal", "gevonden", "gevonden_nodig", "exact", "raak")}
    rol = {v["bron_iri"]: v["rol"] for v in s["verwacht"]}
    mist = [{"deelvraag": i, "bron_iri": iri, "rol": rol.get(iri), "plek": "onbekend"}
            for i, p in enumerate(per) for iri in p["gemist"]]
    verwacht_per = {i: [v["bron_iri"] for v in s["verwacht"] if v["deelvraag"] == i] for i in range(len(per))}
    onterecht = [{"deelvraag": i, "bron_iri": c, "uitgesloten": c in p["uitgesloten"]}
                 for i, p in enumerate(per) for c in p["opties"][:p["aantal"]]
                 if not any(_raakt(c, v) for v in verwacht_per[i])]
    uit = {
        "casus_id": casus["casus_id"], "naam": casus["naam"], "niveau": casus["niveau"], "gebruik": casus["gebruik"],
        "verwachting": casus["verwachting"]["status"], "route": route,
        "maten": {
            "recall_nodig": _maat(som["gevonden_nodig"], som["nodig"]),
            "recall": _maat(som["gevonden"], som["verwacht"]),
            "recall_exact": _maat(som["exact"], som["verwacht"]),
            "precisie": _maat(som["raak"], som["aantal"]),
            # Jaccard met de treffer van `in_selectie`: de verwachte die Lex raakt, gedeeld door wat er samen staat.
            "overlap": _maat(som["gevonden"], som["verwacht"] + som["aantal"] - som["raak"]),
        },
        "diagnose": {"uitgesloten_in_keuze": r["uitgesloten"], "opname_onvolledig": graaf.ontbrekend},
        "categorieen": {"lex_mist": len(mist), "lex_onterecht": len(onterecht), "team_mist": 0, "twijfel": 0,
                        "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"},
    }
    if casus["gebruik"] == "ontwikkeling":
        uit["verschillen"] = {"lex_mist": mist, "lex_onterecht": onterecht}
    return uit


def rapport_per_niveau(kaarten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per gebruik en niveau de som van de tellers en noemers. Geen rij over gebruik heen, en geen totaal."""
    rijen = []
    for gebruik in GEBRUIK:
        for niveau in NIVEAUS:
            groep = [k for k in kaarten if k["gebruik"] == gebruik and k["niveau"] == niveau]
            if not groep:
                continue
            maten = {}
            for m in groep[0]["maten"]:
                maten[m] = _maat(sum(k["maten"][m]["teller"] for k in groep), sum(k["maten"][m]["noemer"] for k in groep))
            rijen.append({"gebruik": gebruik, "niveau": niveau, "casussen": [k["casus_id"] for k in groep], "maten": maten,
                          "categorieen": {c: sum(k["categorieen"][c] for k in groep)
                                          for c in ("lex_mist", "lex_onterecht", "team_mist", "twijfel")}})
    return rijen


def _commit() -> dict[str, Any]:
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], cwd=WORTEL, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "schoon": git("status", "--porcelain", "--", "tools/graph-qa/agent",
                                                              "tools/graph-qa/eval", "docs/wetsanalyse") == ""}


def runrecord(manifest: dict[str, Any], naam: str, datum: str) -> dict[str, Any]:
    """Het runrecord van plan §6, voor arm L1: geen model, geen team, geen tokens."""
    from agent.bronnen_run import ZOEKVERSIE

    return {"schema": "lex-bench-run-1", "naam": naam, "datum": datum, "arm": "L1", "route": ROUTE_L1,
            "code": _commit(), "zoekversie": ZOEKVERSIE, "images": None, "model": None, "team": None,
            "casusset": {"versie": manifest["versie"], "hash": manifest["hash"]},
            "graaftoestand": {c["casus_id"]: c["opname"] for c in manifest["casussen"]},
            "verwachting": {c["casus_id"]: {"sha256": c["sha256"], "status": c["verwachting"]["status"]}
                            for c in manifest["casussen"]},
            "verbruik": {"L1": 0}, "plafonds": None}


def _readme(run: dict[str, Any], rapport: dict[str, Any]) -> str:
    regels = [f"# Lex Bench, bronselectie – {run['naam']} ({run['datum']})", "",
              f"Arm L1 (zonder model, route `{run['route']}`) op `{run['casusset']['versie']}` "
              f"(hash `{run['casusset']['hash'][:12]}`), commit `{run['code']['commit'][:8]}`, zoekversie "
              f"`{run['zoekversie']}`. 0 tokens. Alle verwachtingen zijn `concept`: dit is een **trendmeting**, geen oordeel "
              "(plan §22, besluit 2). Er is geen totaalcijfer.", "",
              "| casus | niveau | gebruik | recall nodig | recall | precisie | overlap | Lex mist | Lex onterecht |",
              "|---|---|---|---|---|---|---|---|---|"]
    for k in rapport["casussen"]:
        m = k["maten"]
        f = lambda x: f"{x['teller']}/{x['noemer']}"  # noqa: E731
        regels.append(f"| {k['casus_id']} {k['naam']} | {k['niveau']} | {k['gebruik']} | {f(m['recall_nodig'])} | "
                      f"{f(m['recall'])} | {f(m['precisie'])} | {f(m['overlap'])} | {k['categorieen']['lex_mist']} | "
                      f"{k['categorieen']['lex_onterecht']} |")
    regels += ["", "De categorieën zijn een voorstel van de code: *team mist* en *twijfel* vragen de reviewer en de jurist "
                   "(LB2). Per niveau staat het rapport in `rapport.json`.", ""]
    return "\n".join(regels)


def run_l1(naam: str, datum: str | None = None, map_: Path | None = None) -> Path:
    """Een run van L1 als meetmap. Een bestaande map wordt niet overschreven."""
    datum = datum or dt.date.today().isoformat()
    doel = map_ or METINGEN / f"lex-bench-{datum}-{naam}"
    if doel.exists():
        raise SystemExit(f"{doel} bestaat al: een meetmap is bewijs en wordt niet overschreven")
    manifest = laad_manifest()
    if manifest["hash"] != versiehash(manifest["casussen"]):
        raise SystemExit("de hash van het manifest klopt niet met de casussen")
    for c in manifest["casussen"]:
        if c["gebruik"] == "ontwikkeling" and sha256(WORTEL / c["pad"] / "set.json") != c["sha256"]:
            raise SystemExit(f"{c['casus_id']}: de set wijkt af van het manifest; maak eerst een nieuwe versie")
    kaarten = [scoor_casus(c) for c in manifest["casussen"]]
    rapport = {"schema": "lex-bench-rapport-1", "casussen": kaarten, "per_niveau": rapport_per_niveau(kaarten)}
    run = runrecord(manifest, naam, datum)
    doel.mkdir(parents=True)
    (doel / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (doel / "rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (doel / "README.md").write_text(_readme(run, rapport), encoding="utf-8")
    return doel


# --- het dashboard (plan §6) ----------------------------------------------------------------------------------------

def _risicomatrix() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("risicomatrix", WORTEL / "scripts" / "risicomatrix.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None  # noqa: S101 – typevernauwing; eval draait nooit met -O
    spec.loader.exec_module(mod)
    return mod.matrix()


def dashboard_data(metingen: Path = METINGEN) -> dict[str, Any]:
    """Wat de pagina toont, uit de vastgelegde runs. Van een blinde casus alleen de scores en de categorieën."""
    runs = []
    for map_ in sorted(metingen.glob("lex-bench-*")):
        if not (map_ / "run.json").exists():
            continue
        run = json.loads((map_ / "run.json").read_text(encoding="utf-8"))
        rapport = json.loads((map_ / "rapport.json").read_text(encoding="utf-8"))
        for k in rapport["casussen"]:
            if k["gebruik"] == "blind":
                k.pop("verschillen", None)
        runs.append({"map": map_.name, "run": run, "rapport": rapport})
    runs.sort(key=lambda r: (r["run"]["datum"], r["map"]))
    manifest = laad_manifest()
    matrix = _risicomatrix()
    return {"schema": "lex-bench-dashboard-1", "meetas": "bronselectie",
            "manifest": {"versie": manifest["versie"], "hash": manifest["hash"],
                         "vastgesteld": sum(c["verwachting"]["status"] == "vastgesteld" for c in manifest["casussen"]),
                         "casussen": len(manifest["casussen"])},
            "runs": runs, "risicos": matrix}


def schrijf_dashboard(pad: Path = DASHBOARD_DATA) -> Path:
    data = dashboard_data()
    pad.write_text("// Gegenereerd door `python -m eval.lex_bench --dashboard`; niet met de hand bewerken.\n"
                   f"window.LEX_BENCH = {json.dumps(data, ensure_ascii=False, indent=1)};\n", encoding="utf-8")
    return pad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", type=Path, help="het verschil ook als JSON")
    p.add_argument("--manifest", action="store_true", help="schrijf het manifest opnieuw uit de sets")
    p.add_argument("--l1", metavar="NAAM", help="een run van L1 als meetmap lex-bench-<datum>-<NAAM>")
    p.add_argument("--datum", help="de datum van de run (standaard vandaag)")
    p.add_argument("--dashboard", action="store_true", help="schrijf tools/lex-bench/data.js uit de meetmappen")
    args = p.parse_args(argv)
    if args.manifest:
        MANIFEST.write_text(json.dumps(bouw_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(MANIFEST)
        return 0
    if args.l1:
        print(run_l1(args.l1, args.datum))
        return 0
    if args.dashboard:
        print(schrijf_dashboard())
        return 0
    rijen = vergelijk()
    print(_tabel(rijen))
    if args.json:
        args.json.write_text(json.dumps(rijen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
