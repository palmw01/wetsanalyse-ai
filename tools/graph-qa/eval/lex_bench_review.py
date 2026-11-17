"""Lex Bench, de reviewer (plan-lex-bench §5, §22 besluit 4, LB2): elk verschil krijgt een categorie, als voorstel.

Twee modi, één profiel (`.claude/agents/bench-reviewer.md`):

- **verschillen**: arm L1 (offline, zonder model) tegen de bevroren teamverwachting. De code telt de maten met teller en
  noemer, nummert de verschillen (`V1`, …) en stelt per verschil een categorie voor (*Lex mist*, *Lex onterecht*). De
  reviewer oordeelt tegen de bron: Lex mist, Lex onterecht, team mist of twijfel, met de plek.
- **tegenlezen**: bij een makkelijke casus leest de reviewer het formulier van de ene analist, zonder Lex, vóór het
  bevriezen. `lex_bench_team.voeg_samen(tegenlezing=)` zet zijn bezwaren in `onenig`.

Dezelfde invoer geeft dezelfde verschillen en nummers, zodat de opdracht en het verwerken los van elkaar draaien. Een
uitkomst blijft een voorstel: de jurist beslist, en aan de casus verandert niets.

    python -m eval.lex_bench_review opdracht --casus LB-03 --team <map>/teamverwachting.json --run lb-03-...-r
    python -m eval.lex_bench_review verwerk review.json --casus LB-03 --team <map>/teamverwachting.json
    python -m eval.lex_bench_review tegenlezen --casus LB-03 --formulier formulier-a.json --run lb-03-...-r
    python -m eval.lex_bench_review opnemen --dossier <pilot>/set.json --uit <meetmap>/graafantwoorden.json
    python -m eval.lex_bench_review l2 keuze-l2.json --casus LB-08 --team <map>/teamverwachting.json --dossier <set.json>

**Voor de pilot (LB3)**: `opnemen` legt de graafantwoorden van L1 vast voor een casus die niet in de referentieset
staat (live tegen de graaf, `GRAPHDB_MCP_URL`, geen model), op het dossier alleen en zonder iets van de keuze van Lex
te tonen; een bestaande opname overschrijft het niet. `l2` meet de lijst die het paneel op acceptatie voorstelde (arm
L2) met dezelfde maten en verschillen als L1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from eval import lex_bench_team as team
from eval.bronselectie_eval import ROUTES, OpnameGraaf, OpnemendeGraaf, _raakt, meet_intake, scoor_deelvraag
from eval.lex_bench import ROUTE_L1, _maat

REVIEW = team.BENCH / "bronselectie" / "formulier-reviewer.json"
BRIEFING = team.BENCH / "briefing-reviewer.md"
CATEGORIEEN = {"verschillen": ("lex_mist", "lex_onterecht", "team_mist", "twijfel"),
               "tegenlezen": ("eens", "hoort_er_niet_bij", "ontbreekt", "twijfel")}
#: Welk oordeel bij welk voorstel van de code past: wat Lex niet koos, kan hij niet onterecht kiezen, en omgekeerd.
PAST = {"lex_mist": {"lex_mist", "twijfel"}, "lex_onterecht": {"lex_onterecht", "team_mist", "twijfel"}}


def _set_met_team(set_: dict[str, Any], tv: dict[str, Any]) -> dict[str, Any]:
    """De set met de teamverwachting in plaats van de eigen verwachting: zo meet L1 tegen het team."""
    return {**set_, "verwacht": tv["verwacht"], "buiten_graaf": [],
            "uitgesloten": [{"bron_iri": u["bron_iri"], "motivering": u["motivering"]} for u in tv["uitgesloten"]]}


def lex_tegen_team(set_: dict[str, Any], tv: dict[str, Any], opname: dict[str, Any]) -> dict[str, Any]:
    """De maten van arm L1 tegen de teamverwachting, en de verschillen met een voorstel van de code."""
    s = _set_met_team(set_, tv)
    per = meet_intake(OpnameGraaf(opname), s, {ROUTE_L1: ROUTES[ROUTE_L1]})[ROUTE_L1]["per_deelvraag"]
    return _kaart(per, tv, ROUTE_L1)


#: Arm L2 (§4.4): de lijst per deelvraag die het paneel op acceptatie als voorstel toont, in de volgorde van de werkplek.
ROUTE_L2 = "L2: het paneel op acceptatie"


def l2_tegen_team(set_: dict[str, Any], tv: dict[str, Any], keuze: dict[str, Any]) -> dict[str, Any]:
    """Dezelfde maten en verschillen als L1, op de lijst die Lex op acceptatie voorstelde. `keuze` is
    `{"deelvragen": [{"deelvraag": i, "opties": [{"bron_iri": ..., "buiten": bool?}, ...]}, ...]}`; een deelvraag
    zonder voorstel telt als een lege lijst, nooit als ontbrekend."""
    s = _set_met_team(set_, tv)
    opties = {d["deelvraag"]: d["opties"] for d in keuze["deelvragen"]}
    onbekend = sorted(set(opties) - set(range(len(s["deelvragen"]))))
    if onbekend:
        raise ValueError(f"de keuze noemt deelvragen die het dossier niet heeft: {onbekend}")
    per = [scoor_deelvraag(s, i, opties.get(i, [])) for i in range(len(s["deelvragen"]))]
    return _kaart(per, tv, ROUTE_L2)


def _kaart(per: list[dict[str, Any]], tv: dict[str, Any], route: str) -> dict[str, Any]:
    som = {k: sum(p[k] for p in per) for k in ("verwacht", "nodig", "aantal", "gevonden", "gevonden_nodig", "raak")}
    verschillen: list[dict[str, Any]] = []
    for i, p in enumerate(per):
        verwacht = {v["bron_iri"]: v for v in tv["verwacht"] if v["deelvraag"] == i}
        for iri in p["gemist"]:
            verschillen.append({"deelvraag": i, "bron_iri": iri, "voorstel": "lex_mist", "lex": {"gekozen": False},
                                "team": {k: verwacht[iri][k] for k in ("rol", "motivering")}})
        for pos, c in enumerate(p["opties"][:p["aantal"]], 1):
            if any(_raakt(c, v) for v in verwacht):
                continue
            uit = [u for u in tv["uitgesloten"] if u["deelvraag"] == i and _raakt(c, u["bron_iri"])]
            geschil = [o for o in tv["onenig"] if o["deelvraag"] == i and _raakt(c, o["bron_iri"])]
            verschillen.append({"deelvraag": i, "bron_iri": c, "voorstel": "lex_onterecht",
                                "lex": {"gekozen": True, "positie": pos},
                                "team": ({"uitgesloten": uit[0]["motivering"]} if uit
                                         else {"onenig": geschil[0]["argumenten"]} if geschil else {"niet genoemd": True})})
    for n, v in enumerate(verschillen, 1):
        v["verschil"] = f"V{n}"
    return {"casus_id": tv["casus_id"], "route": route, "tegen": "teamverwachting, vóór de vaststelling",
            "maten": {"recall_nodig": _maat(som["gevonden_nodig"], som["nodig"]),
                      "recall": _maat(som["gevonden"], som["verwacht"]),
                      "precisie": _maat(som["raak"], som["aantal"]),
                      "overlap": _maat(som["gevonden"], som["verwacht"] + som["aantal"] - som["raak"])},
            "verschillen": verschillen}


def _blok(titel: str, waarde: Any) -> str:
    return f"# {titel}\n\n```json\n" + json.dumps(waarde, ensure_ascii=False, indent=2) + "\n```"


def _kop(casus_id: str, modus: str, run: str) -> list[str]:
    deel = BRIEFING.read_text(encoding="utf-8").split("## Voor de coördinator")[0].rstrip()
    return [f"# Lex Bench, casus {casus_id}: review, modus {modus}",
            f"Je logboek is de run `{run}`, met rol `reviewer`. Je formulier draagt `\"casus_id\": \"{casus_id}\"`, "
            f"`\"modus\": \"{modus}\"` en `\"run\": \"{run}\"`.", deel]


def opdracht_verschillen(dossier: dict[str, Any], kaart: dict[str, Any], casus_id: str, run: str) -> str:
    return "\n\n".join([*_kop(casus_id, "verschillen", run), _blok("Het dossier", dossier),
                        _blok("De verschillen", kaart["verschillen"]),
                        "# Het formulier (JSON Schema)\n\n```json\n" + REVIEW.read_text(encoding="utf-8").strip() + "\n```"]) + "\n"


def opdracht_tegenlezen(dossier: dict[str, Any], formulier: dict[str, Any], casus_id: str, run: str) -> str:
    """Het formulier van de analist, en niets van Lex: de teamverwachting is nog niet bevroren."""
    return "\n\n".join([*_kop(casus_id, "tegenlezen", run), _blok("Het dossier", dossier),
                        _blok(f"Het formulier van analist {formulier['analist']}", formulier),
                        "# Het formulier (JSON Schema)\n\n```json\n" + REVIEW.read_text(encoding="utf-8").strip() + "\n```"]) + "\n"


def controleer(review: Any, modus: str, casus_id: str, *, kaart: dict[str, Any] | None = None,
               formulier: dict[str, Any] | None = None) -> list[str]:
    """Alle fouten in een review; leeg als hij klopt."""
    fouten = team.schemafouten(review, json.loads(REVIEW.read_text(encoding="utf-8")))
    if fouten:
        return fouten
    if review["modus"] != modus or review["casus_id"] != casus_id:
        return [f"verwacht modus {modus} en casus {casus_id}, kreeg {review['modus']} en {review['casus_id']}"]
    for o in review["oordelen"]:
        if o["categorie"] not in CATEGORIEEN[modus]:
            fouten.append(f"{o['bron_iri']}: {o['categorie']} hoort niet bij de modus {modus}")
    if modus == "verschillen":
        bekend = {v["verschil"]: v for v in (kaart or {"verschillen": []})["verschillen"]}
        gezien = [o.get("verschil") for o in review["oordelen"]]
        for o in review["oordelen"]:
            v = bekend.get(o.get("verschil"))
            if v is None:
                fouten.append(f"{o.get('verschil')}: geen verschil uit de opdracht")
            elif (v["deelvraag"], v["bron_iri"]) != (o["deelvraag"], o["bron_iri"]):
                fouten.append(f"{v['verschil']}: hoort bij {v['bron_iri']} in deelvraag {v['deelvraag']}")
            elif o["categorie"] not in PAST[v["voorstel"]]:
                fouten.append(f"{v['verschil']}: {o['categorie']} kan niet bij een bepaling die Lex "
                              f"{'niet ' if v['voorstel'] == 'lex_mist' else ''}koos")
        fouten += [f"{n}: geen oordeel" for n in bekend if n not in gezien]
        fouten += [f"{n}: twee oordelen" for n in set(gezien) if n and gezien.count(n) > 1]
    else:
        te_lezen = {(d["deelvraag"], b["bron_iri"]) for d in (formulier or {"deelvragen": []})["deelvragen"]
                    for b in d["bepalingen"] + d["twijfel"]}
        gezien = [(o["deelvraag"], o["bron_iri"]) for o in review["oordelen"]]
        for o in review["oordelen"]:
            sleutel = (o["deelvraag"], o["bron_iri"])
            if o["categorie"] == "ontbreekt":
                if sleutel in te_lezen:
                    fouten.append(f"{o['bron_iri']}: staat al in het formulier; ontbreekt kan alleen bij iets nieuws")
                if "bewijs" not in o:
                    fouten.append(f"{o['bron_iri']}: een bepaling die ontbreekt, draagt bewijs")
            elif sleutel not in te_lezen:
                fouten.append(f"{o['bron_iri']}: staat niet bij de opgenomen of twijfelgevallen van deelvraag {o['deelvraag']}")
        fouten += [f"{iri} (deelvraag {i}): geen oordeel" for i, iri in sorted(te_lezen) if (i, iri) not in gezien]
        fouten += [f"{iri}: twee oordelen" for i, iri in set(gezien) if gezien.count((i, iri)) > 1]
    for o in review["oordelen"]:
        if modus == "tegenlezen" and "plek" in o:
            fouten.append(f"{o['bron_iri']}: een plek hoort bij de modus verschillen")
    return fouten


def verwerk(kaart: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """De telling per categorie als voorstel van de reviewer. Team mist is een voorstel voor `nagekomen`, geen wijziging."""
    fouten = controleer(review, "verschillen", kaart["casus_id"], kaart=kaart)
    if fouten:
        raise ValueError("; ".join(fouten))
    per = {o["verschil"]: o for o in review["oordelen"]}
    telling = {c: 0 for c in CATEGORIEEN["verschillen"]}
    plekken: dict[str, int] = {}
    for o in review["oordelen"]:
        telling[o["categorie"]] += 1
        if o["categorie"] in ("lex_mist", "lex_onterecht"):
            plekken[o.get("plek", "onbekend")] = plekken.get(o.get("plek", "onbekend"), 0) + 1
    return {**kaart, "categorieen": {**telling, "status": "voorstel van de reviewer; de jurist beslist"},
            "plekken": plekken,
            "verschillen": [{**v, "oordeel": {k: per[v["verschil"]][k] for k in ("categorie", "plek", "reden", "bewijs")
                                              if k in per[v["verschil"]]}} for v in kaart["verschillen"]],
            "nagekomen_voorstel": [{"deelvraag": v["deelvraag"], "bron_iri": v["bron_iri"], "nagekomen": True,
                                    "motivering": per[v["verschil"]]["reden"]}
                                   for v in kaart["verschillen"] if per[v["verschil"]]["categorie"] == "team_mist"]}


def _set_en_opname(casus_id: str, dossier: Path | None, opname: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if dossier is None:
        pad = team.WORTEL / team.laad_casus(casus_id)["pad"]
        dossier, opname = pad / "set.json", opname or pad / "graafantwoorden.json"
    if opname is None:
        raise SystemExit("Geef bij --dossier ook --opname (de graafantwoorden van de casus).")
    return (json.loads(dossier.read_text(encoding="utf-8")), json.loads(opname.read_text(encoding="utf-8")))


def neem_op(dossier: dict[str, Any], uit: Path, graaf: Any) -> int:
    """De graafantwoorden van arm L1 voor een casus buiten `referentieset-bronselectie/` (de pilot, een blinde casus).
    Het draait de route van L1 op het dossier alleen: de verwachting doet er voor de queries niet toe, en wie opneemt,
    ziet zo geen keuze van Lex. Een bestaande opname is bewijs en wordt niet overschreven. Geeft het aantal queries."""
    if uit.exists():
        raise FileExistsError(f"{uit} bestaat al: een opname is bewijs en wordt niet overschreven.")
    opnemer = OpnemendeGraaf(graaf)
    try:
        meet_intake(opnemer, {**team.dossier_van(dossier), "status": "concept", "verwacht": [], "uitgesloten": []},
                    {ROUTE_L1: ROUTES[ROUTE_L1]})
    finally:
        opnemer.close()
    uit.parent.mkdir(parents=True, exist_ok=True)
    uit.write_text(json.dumps(opnemer.opname, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return len(opnemer.opname["sparql"]) + len(opnemer.opname["semantisch"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="actie", required=True)
    o = sub.add_parser("opdracht", help="de opdracht van de reviewer in de modus verschillen, naar stdout")
    w = sub.add_parser("verwerk", help="toets een review en geef de telling per categorie")
    for q in (o, w):
        q.add_argument("--casus", required=True)
        q.add_argument("--team", type=Path, required=True, help="de bevroren teamverwachting.json")
        q.add_argument("--dossier", type=Path, help="een set.json buiten de repo (een blinde casus)")
        q.add_argument("--opname", type=Path, help="de graafantwoorden bij --dossier")
    o.add_argument("--run", required=True)
    w.add_argument("review", type=Path)
    t = sub.add_parser("tegenlezen", help="de opdracht van de tegenlezer bij een makkelijke casus, naar stdout")
    t.add_argument("--casus", required=True)
    t.add_argument("--formulier", type=Path, required=True)
    t.add_argument("--run", required=True)
    t.add_argument("--dossier", type=Path)
    n = sub.add_parser("opnemen", help="de graafantwoorden van L1 voor een casus buiten de referentieset (live)")
    n.add_argument("--dossier", type=Path, required=True)
    n.add_argument("--uit", type=Path, required=True, help="het nieuwe graafantwoorden.json")
    l2 = sub.add_parser("l2", help="de lijst van het paneel op acceptatie (arm L2) tegen de teamverwachting")
    l2.add_argument("keuze", type=Path)
    l2.add_argument("--casus", required=True)
    l2.add_argument("--team", type=Path, required=True)
    l2.add_argument("--dossier", type=Path, required=True)
    args = p.parse_args(argv)
    if args.actie == "opnemen":
        from eval.bronselectie_eval import _echte_graaf
        aantal = neem_op(json.loads(args.dossier.read_text(encoding="utf-8")), args.uit, _echte_graaf())
        print(f"{aantal} graafantwoorden opgenomen in {args.uit}; sha256 {hashlib.sha256(args.uit.read_bytes()).hexdigest()}")
        return 0
    if args.actie == "l2":
        kaart = l2_tegen_team(json.loads(args.dossier.read_text(encoding="utf-8")),
                              json.loads(args.team.read_text(encoding="utf-8")),
                              json.loads(args.keuze.read_text(encoding="utf-8")))
        print(json.dumps(kaart, ensure_ascii=False, indent=2))
        return 0
    if args.actie == "tegenlezen":
        dossier = team.dossier_uit(args.casus, args.dossier)
        sys.stdout.write(opdracht_tegenlezen(dossier, json.loads(args.formulier.read_text(encoding="utf-8")),
                                             args.casus, args.run))
        return 0
    set_, opname = _set_en_opname(args.casus, args.dossier, args.opname)
    kaart = lex_tegen_team(set_, json.loads(args.team.read_text(encoding="utf-8")), opname)
    if args.actie == "opdracht":
        sys.stdout.write(opdracht_verschillen(team.dossier_van(set_), kaart, args.casus, args.run))
        return 0
    review = json.loads(args.review.read_text(encoding="utf-8"))
    fouten = controleer(review, "verschillen", args.casus, kaart=kaart)
    if fouten:
        print("\n".join(fouten))
        return 1
    print(json.dumps(verwerk(kaart, review), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
