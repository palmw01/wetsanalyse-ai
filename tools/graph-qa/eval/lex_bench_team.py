"""Lex Bench, arm T: het team dat blind de bronselectie van een casus bepaalt (plan-lex-bench §4.2, LB2).

De analist (`.claude/agents/bench-analist.md`) ziet Lex niet en leest geen bestanden uit de repo: hij krijgt alles in
één opdracht. Dit script maakt die opdracht (de briefing, de twee uitwerkingen uit de skill, het dossier zonder
verwachting en het formulier) en controleert het formulier dat terugkomt. Er draait hier geen model: de coördinator
start de analist zelf, pas met het akkoord voor een run (LB3).

    python -m eval.lex_bench_team opdracht --casus LB-03 --analist A --run lb-03-2026-11-20-a
    python -m eval.lex_bench_team opdracht --dossier <pad buiten de repo> --casus LB-21 --analist B --run ...
    python -m eval.lex_bench_team controleer formulier-a.json --casus LB-03
    python -m eval.lex_bench_team samenvoegen formulier-a.json formulier-b.json --casus LB-03 --run lb-03-... --uit <map>

De controle leest de vorm uit `docs/lex-bench/bronselectie/formulier-analist.json` (één bron voor de afspraak) en
toetst daarna wat een schema niet kan zien: elke deelvraag precies één keer, en een bepaling per deelvraag op één plek.

**Samenvoegen en bevriezen** (§4.2): de derde stap legt A en B naast elkaar. Wat beide opnemen, staat in `verwacht`
(bij een verschil in rol de zwaarste, met het verschil in `onenig`); wat er één opneemt, staat alleen in `onenig`, met
het standpunt van beide; wat beide uitsluiten, in `uitgesloten`. Dat is de teamverwachting in schema 4, `status:
concept`. Bevriezen schrijft haar met de formulieren in een map, met hun sha256 in `bevroren.json`, en weigert een map
die al bestaat. Een blinde casus bevriest buiten de repo (§4.5, besluit 1): alleen de hashes gaan erin.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from eval.wortel import WORTEL as WORTEL_REPO

WORTEL = WORTEL_REPO
BENCH = WORTEL / "docs" / "lex-bench"
MANIFEST = BENCH / "bronselectie" / "manifest.json"
FORMULIER = BENCH / "bronselectie" / "formulier-analist.json"
BRIEFING = BENCH / "briefing-analist.md"
SKILL = WORTEL / ".claude" / "skills" / "wetsanalyse" / "references"
UITWERKINGEN = ("zoekvragen-bronselectie.md", "verwijzingen-volgen.md")

# Wat een werkgebied draagt (activiteit 1) en Lex ook krijgt. Niet: `verwacht`, `uitgesloten`, `buiten_graaf`,
# `toelichting` en de status: dat is de verwachting, of een beschrijving ervan.
DOSSIERVELDEN = ("naam", "aanleiding", "doel", "analysevraag", "praktijkvoorbeeld", "context", "buiten", "gebeurtenis",
                 "regelingen", "deelvragen")


def dossier_van(s: dict[str, Any]) -> dict[str, Any]:
    """Het dossier van een set, zonder verwachting. Een veld dat ontbreekt, blijft weg."""
    return {k: s[k] for k in DOSSIERVELDEN if k in s}


def laad_casus(casus_id: str, manifest: Path = MANIFEST) -> dict[str, Any]:
    """De casus uit het manifest. Een blinde casus staat niet in de repo: die komt met `--dossier`."""
    m = json.loads(manifest.read_text(encoding="utf-8"))
    for c in m["casussen"]:
        if c["casus_id"] == casus_id:
            if not c.get("pad"):
                raise SystemExit(f"{casus_id} staat niet in de repo; geef het dossier met --dossier.")
            return c
    raise SystemExit(f"{casus_id} staat niet in het manifest {m['versie']}.")


def dossier_uit(casus_id: str, pad: Path | None = None) -> dict[str, Any]:
    if pad is None:
        pad = WORTEL / laad_casus(casus_id)["pad"] / "set.json"
    return dossier_van(json.loads(pad.read_text(encoding="utf-8")))


def opdracht(dossier: dict[str, Any], casus_id: str, analist: str, run: str) -> str:
    """De hele opdracht van één analist, als tekst. Alles wat hij mag weten, en niets meer."""
    if analist not in ("A", "B"):
        raise ValueError("De analist is A of B.")
    delen = [
        f"# Lex Bench, casus {casus_id}: de bronselectie van analist {analist}",
        f"Je logboek is de run `{run}`, met rol `analist`. Je formulier draagt `\"casus_id\": \"{casus_id}\"`, "
        f"`\"analist\": \"{analist}\"` en `\"run\": \"{run}\"`.",
        BRIEFING.read_text(encoding="utf-8").split("## Voor de coördinator")[0].rstrip(),
        *(f"# Uit de skill wetsanalyse: {n}\n\n" + (SKILL / n).read_text(encoding="utf-8").strip() for n in UITWERKINGEN),
        "# Het dossier\n\n```json\n" + json.dumps(dossier, ensure_ascii=False, indent=2) + "\n```",
        "# Het formulier (JSON Schema)\n\n```json\n" + FORMULIER.read_text(encoding="utf-8").strip() + "\n```",
    ]
    return "\n\n".join(delen) + "\n"


def _is(waarde: Any, soort: str) -> bool:
    if soort == "null":
        return waarde is None
    if soort == "boolean":
        return isinstance(waarde, bool)
    typen = {"object": dict, "array": list, "string": str, "integer": int}
    return isinstance(waarde, typen[soort]) and not (soort == "integer" and isinstance(waarde, bool))


def schemafouten(waarde: Any, schema: dict[str, Any], pad: str = "$") -> list[str]:
    """Het deel van JSON Schema dat het formulier gebruikt; alleen de standaardbibliotheek, zoals de poort."""
    fouten: list[str] = []
    if "const" in schema and waarde != schema["const"]:
        return [f"{pad}: moet {schema['const']!r} zijn"]
    if "enum" in schema and waarde not in schema["enum"]:
        return [f"{pad}: {waarde!r} is niet een van {schema['enum']}"]
    soorten = schema.get("type")
    soorten = [soorten] if isinstance(soorten, str) else soorten
    if soorten and not any(_is(waarde, s) for s in soorten):
        return [f"{pad}: verwacht {' of '.join(soorten)}"]
    if isinstance(waarde, str):
        if len(waarde.strip()) < schema.get("minLength", 0):
            fouten.append(f"{pad}: leeg")
        if "pattern" in schema and not re.search(schema["pattern"], waarde):
            fouten.append(f"{pad}: {waarde!r} heeft niet de vorm {schema['pattern']}")
    if isinstance(waarde, int) and "minimum" in schema and waarde < schema["minimum"]:
        fouten.append(f"{pad}: kleiner dan {schema['minimum']}")
    if isinstance(waarde, dict):
        props = schema.get("properties", {})
        fouten += [f"{pad}: {k} ontbreekt" for k in schema.get("required", []) if k not in waarde]
        if schema.get("additionalProperties") is False:
            fouten += [f"{pad}: onbekend veld {k}" for k in waarde if k not in props]
        for k, v in waarde.items():
            if k in props:
                fouten += schemafouten(v, props[k], f"{pad}.{k}")
    if isinstance(waarde, list) and "items" in schema:
        for i, v in enumerate(waarde):
            fouten += schemafouten(v, schema["items"], f"{pad}[{i}]")
    return fouten


def controleer(formulier: Any, dossier: dict[str, Any], casus_id: str | None = None) -> list[str]:
    """Alle fouten in een formulier; leeg als het klopt."""
    fouten = schemafouten(formulier, json.loads(FORMULIER.read_text(encoding="utf-8")))
    if fouten:
        return fouten
    if casus_id and formulier["casus_id"] != casus_id:
        fouten.append(f"casus_id is {formulier['casus_id']}, verwacht {casus_id}")
    nummers = [d["deelvraag"] for d in formulier["deelvragen"]]
    verwacht = list(range(len(dossier.get("deelvragen", []))))
    if sorted(nummers) != verwacht:
        fouten.append(f"de deelvragen zijn {sorted(nummers)}, verwacht precies {verwacht}")
    for d in formulier["deelvragen"]:
        plekken: dict[str, list[str]] = {}
        for plek in ("bepalingen", "uitgesloten", "twijfel"):
            for b in d[plek]:
                plekken.setdefault(b["bron_iri"], []).append(plek)
        for iri, waar in sorted(plekken.items()):
            if len(waar) > 1:
                fouten.append(f"deelvraag {d['deelvraag']}: {iri} staat {len(waar)} keer ({', '.join(waar)})")
    for b in formulier.get("buiten_graaf", []):
        if "deelvraag" in b and b["deelvraag"] not in verwacht:
            fouten.append(f"buiten_graaf: deelvraag {b['deelvraag']} bestaat niet")
    return fouten


ROLGEWICHT = {"kern": 0, "afhankelijkheid": 1, "aanverwant": 2}


def _standpunten(f: dict[str, Any], i: int) -> dict[str, dict[str, Any]]:
    """Per bron_iri wat één analist in deelvraag i vond."""
    d = next(d for d in f["deelvragen"] if d["deelvraag"] == i)
    uit: dict[str, dict[str, Any]] = {}
    for b in d["bepalingen"]:
        uit[b["bron_iri"]] = {"plek": "opgenomen", "rol": b["rol"], "zoekvraag": b["zoekvraag"],
                              "motivering": b["motivering"], "citaat": b["bewijs"]["citaat"]}
    for b in d["uitgesloten"]:
        uit[b["bron_iri"]] = {"plek": "uitgesloten", "motivering": b["motivering"]}
    for b in d["twijfel"]:
        uit[b["bron_iri"]] = {"plek": "twijfel", "motivering": b["reden"]}
    return uit


def voeg_samen(formulieren: list[dict[str, Any]], dossier: dict[str, Any], casus: dict[str, Any], run: str,
               datum: str | None = None, tegenlezing: dict[str, Any] | None = None) -> dict[str, Any]:
    """De teamverwachting uit één of twee gecontroleerde formulieren. Geen model, geen keuze: alleen naast elkaar.

    Met `tegenlezing` (één analist, besluit 4; `lex_bench_review`, modus tegenlezen) gaat een bepaling waartegen de
    tegenlezer bezwaar maakt van `verwacht` naar `onenig`, en een bepaling die volgens hem ontbreekt ook."""
    for f in formulieren:
        fouten = controleer(f, dossier, casus["casus_id"])
        if fouten:
            raise ValueError(f"formulier {f.get('analist')}: " + "; ".join(fouten))
    analisten = [f["analist"] for f in formulieren]
    if len(formulieren) not in (1, 2) or len(set(analisten)) != len(analisten):
        raise ValueError("Eén of twee formulieren, van verschillende analisten.")
    verwacht, onenig, uitgesloten = [], [], []
    for i in range(len(dossier["deelvragen"])):
        per = {f["analist"]: _standpunten(f, i) for f in formulieren}
        for iri in sorted(set().union(*per.values())):
            st = {a: per[a].get(iri, {"plek": "niet genoemd"}) for a in analisten}
            plekken = {s["plek"] for s in st.values()}
            opgenomen = [a for a in analisten if st[a]["plek"] == "opgenomen"]
            if plekken == {"uitgesloten"}:
                uitgesloten.append({"deelvraag": i, "bron_iri": iri,
                                    "motivering": " / ".join(f"{a}: {st[a]['motivering']}" for a in analisten)})
            elif len(opgenomen) == len(analisten):
                rollen = {st[a]["rol"] for a in analisten}
                rol = min(rollen, key=ROLGEWICHT.__getitem__)
                verwacht.append({"deelvraag": i, "bron_iri": iri, "rol": rol, "zoekvraag": st[analisten[0]]["zoekvraag"],
                                 "motivering": " / ".join(f"{a}: {st[a]['motivering']}" for a in analisten),
                                 "herkomst": "team: " + " en ".join(analisten)})
                if len(rollen) > 1:
                    onenig.append({"deelvraag": i, "bron_iri": iri, "soort": "rol", "argumenten": st})
            elif opgenomen:
                onenig.append({"deelvraag": i, "bron_iri": iri, "soort": f"alleen_{opgenomen[0]}", "argumenten": st})
            elif "twijfel" in plekken:
                onenig.append({"deelvraag": i, "bron_iri": iri, "soort": "twijfel", "argumenten": st})
            # Uitgesloten door de één en niet genoemd door de ander: niemand neemt haar op, en er is geen geschil.
            elif "uitgesloten" in plekken:
                a = next(a for a in analisten if st[a]["plek"] == "uitgesloten")
                uitgesloten.append({"deelvraag": i, "bron_iri": iri, "motivering": f"{a}: {st[a]['motivering']}"})
    if tegenlezing is not None:
        verwacht, onenig = _met_tegenlezing(formulieren, tegenlezing, casus["casus_id"], verwacht, onenig)
    return {
        "schema_versie": 4, "casus_id": casus["casus_id"], "niveau": casus["niveau"], "gebruik": casus["gebruik"],
        "verwachting": {"opgesteld_door": {"run_id": run, "analisten": analisten}, "vastgesteld_door": None,
                        "status": "concept", "datum": datum or dt.date.today().isoformat()},
        "verwacht": verwacht, "onenig": onenig, "uitgesloten": uitgesloten,
        "buiten_graaf": [dict(b, analist=f["analist"]) for f in formulieren for b in f.get("buiten_graaf", [])],
        "open_punten": [f"{f['analist']}: {p}" for f in formulieren for p in f.get("open_punten", [])],
    }


def _met_tegenlezing(formulieren: list[dict[str, Any]], lezing: dict[str, Any], casus_id: str,
                     verwacht: list[dict[str, Any]], onenig: list[dict[str, Any]]) -> tuple[list, list]:
    from eval import lex_bench_review

    if len(formulieren) != 1:
        raise ValueError("Een tegenlezing hoort bij één analist; bij twee is de ander de tegenlezer.")
    (f,) = formulieren
    fouten = lex_bench_review.controleer(lezing, "tegenlezen", casus_id, formulier=f)
    if fouten:
        raise ValueError("tegenlezing: " + "; ".join(fouten))
    bezwaar = {(o["deelvraag"], o["bron_iri"]): o for o in lezing["oordelen"] if o["categorie"] != "eens"}
    blijft = [v for v in verwacht if (v["deelvraag"], v["bron_iri"]) not in bezwaar]
    erbij = []
    for (i, iri), o in sorted(bezwaar.items()):
        analist = _standpunten(f, i).get(iri, {"plek": "niet genoemd"})
        tegen = {"plek": o["categorie"], "motivering": o["reden"], **({"citaat": o["bewijs"]["citaat"]} if "bewijs" in o else {})}
        al = next((x for x in onenig if (x["deelvraag"], x["bron_iri"]) == (i, iri)), None)
        if al:
            al["argumenten"]["tegenlezer"] = tegen
        else:
            erbij.append({"deelvraag": i, "bron_iri": iri, "soort": "tegenlezer",
                          "argumenten": {f["analist"]: analist, "tegenlezer": tegen}})
    return blijft, onenig + erbij


RUN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def lokaal_map(wortel: Path = WORTEL) -> Path:
    """De map van het logboek van de acceptatie-MCP (`standaardMap`): die van de checkout, ook vanuit een worktree.
    Gitignored; de opdracht en de inleveringen van een agent staan hier, buiten de context van de coördinator."""
    return Path(re.sub(r"[/\\]\.claude[/\\]worktrees[/\\][^/\\]+[/\\]?$", "", str(wortel))) / "docs" / "acceptatie" / "lokaal"


def runmap(run: str, map_: Path | None = None) -> Path:
    if not RUN.match(run):
        raise ValueError("Een run heet bijvoorbeeld lb-10-2026-11-20-a.")
    return (map_ or lokaal_map()) / run


def naar_run(run: str, tekst: str, controle: dict[str, Any], map_: Path | None = None) -> Path:
    """Leg de opdracht in de runmap: `opdracht.md` voor de agent (`bench_opdracht_lezen`) en `opdracht.json` voor de
    controle van wat hij inlevert (`eval.lex_bench_inleveren`). Een runmap met een opdracht blijft zoals ze is."""
    doel = runmap(run, map_)
    doel.mkdir(parents=True, exist_ok=True)
    if (doel / "opdracht.md").exists():
        raise FileExistsError(f"{doel} heeft al een opdracht: een nieuwe run krijgt een nieuwe naam.")
    (doel / "opdracht.json").write_text(json.dumps(controle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (doel / "opdracht.md").write_text(tekst, encoding="utf-8")
    return doel


def schrijf_uit(tekst: str, run: str, naar: bool, controle: dict[str, Any]) -> None:
    """De opdracht naar stdout, of met `--naar-run` in de runmap met alleen een regel op stdout."""
    if naar:
        doel = naar_run(run, tekst, controle)
        print(f"De opdracht staat in {doel} ({len(tekst)} tekens). De agent leest haar met bench_opdracht_lezen.")
    else:
        sys.stdout.write(tekst)


def _pad(waarde: Path | None) -> str | None:
    return str(waarde.resolve()) if waarde else None


def _json(waarde: Any) -> bytes:
    return (json.dumps(waarde, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def bevries(team: dict[str, Any], formulieren: list[dict[str, Any]], map_: Path) -> dict[str, Any]:
    """Schrijf de teamverwachting en de formulieren weg, met hun hash. Een bestaande map blijft zoals ze is."""
    if team["gebruik"] == "blind" and map_.resolve().is_relative_to(WORTEL):
        raise ValueError("Een blinde casus bevriest buiten de repo; alleen de hash gaat erin.")
    map_.mkdir(parents=True, exist_ok=False)
    bestanden = {"teamverwachting.json": _json(team),
                 **{f"formulier-{f['analist'].lower()}.json": _json(f) for f in formulieren}}
    for naam, inhoud in bestanden.items():
        (map_ / naam).write_bytes(inhoud)
    bevroren = {"casus_id": team["casus_id"], "run_id": team["verwachting"]["opgesteld_door"]["run_id"],
                "bevroren": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "sha256": {naam: hashlib.sha256(inhoud).hexdigest() for naam, inhoud in bestanden.items()}}
    (map_ / "bevroren.json").write_bytes(_json(bevroren))
    return bevroren


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="actie", required=True)
    o = sub.add_parser("opdracht", help="de opdracht van één analist, naar stdout")
    o.add_argument("--casus", required=True)
    o.add_argument("--analist", required=True, choices=("A", "B"))
    o.add_argument("--run", required=True)
    o.add_argument("--dossier", type=Path, help="een set.json buiten de repo (een blinde casus)")
    o.add_argument("--naar-run", action="store_true", help="schrijf de opdracht in de runmap (bench_opdracht_lezen)")
    c = sub.add_parser("controleer", help="toets een formulier; exit 1 bij een fout")
    c.add_argument("formulier", type=Path)
    c.add_argument("--casus", required=True)
    c.add_argument("--dossier", type=Path)
    v = sub.add_parser("samenvoegen", help="voeg één of twee formulieren samen en bevries de teamverwachting")
    v.add_argument("formulieren", type=Path, nargs="+")
    v.add_argument("--casus", required=True)
    v.add_argument("--run", required=True)
    v.add_argument("--uit", type=Path, required=True, help="een nieuwe map; voor een blinde casus buiten de repo")
    v.add_argument("--dossier", type=Path)
    v.add_argument("--niveau", choices=("makkelijk", "gemiddeld", "moeilijk"), help="bij --dossier")
    v.add_argument("--gebruik", choices=("ontwikkeling", "blind"), help="bij --dossier")
    v.add_argument("--tegenlezing", type=Path, help="de review van de tegenlezer (één analist, makkelijk)")
    args = p.parse_args(argv)
    dossier = dossier_uit(args.casus, args.dossier)
    if args.actie == "opdracht":
        schrijf_uit(opdracht(dossier, args.casus, args.analist, args.run), args.run, args.naar_run,
                    {"soort": "analist", "casus": args.casus, "dossier": _pad(args.dossier)})
        return 0
    if args.actie == "samenvoegen":
        casus = ({"casus_id": args.casus, "niveau": args.niveau, "gebruik": args.gebruik} if args.dossier
                 else laad_casus(args.casus))
        if not casus["niveau"] or not casus["gebruik"]:
            raise SystemExit("Geef bij --dossier ook --niveau en --gebruik.")
        formulieren = [json.loads(f.read_text(encoding="utf-8")) for f in args.formulieren]
        lezing = json.loads(args.tegenlezing.read_text(encoding="utf-8")) if args.tegenlezing else None
        team = voeg_samen(formulieren, dossier, casus, args.run, tegenlezing=lezing)
        print(json.dumps(bevries(team, formulieren, args.uit), ensure_ascii=False, indent=2))
        return 0
    fouten = controleer(json.loads(args.formulier.read_text(encoding="utf-8")), dossier, args.casus)
    print("\n".join(fouten) if fouten else "Het formulier klopt.")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
