"""Lex Bench, arm T: het team dat blind de bronselectie van een casus bepaalt (plan-lex-bench §4.2, LB2).

De analist (`.claude/agents/bench-analist.md`) ziet Lex niet en leest geen bestanden uit de repo: hij krijgt alles in
één opdracht. Dit script maakt die opdracht (de briefing, de twee uitwerkingen uit de skill, het dossier zonder
verwachting en het formulier) en controleert het formulier dat terugkomt. Er draait hier geen model: de coördinator
start de analist zelf, pas met het akkoord voor een run (LB3).

    python -m eval.lex_bench_team opdracht --casus LB-03 --analist A --run lb-03-2026-11-20-a
    python -m eval.lex_bench_team opdracht --dossier <pad buiten de repo> --casus LB-21 --analist B --run ...
    python -m eval.lex_bench_team controleer formulier-a.json --casus LB-03

De controle leest de vorm uit `docs/lex-bench/bronselectie/formulier-analist.json` (één bron voor de afspraak) en
toetst daarna wat een schema niet kan zien: elke deelvraag precies één keer, en een bepaling per deelvraag op één plek.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WORTEL = Path(__file__).resolve().parents[3]
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


def schemafouten(waarde: Any, schema: dict[str, Any], pad: str = "$") -> list[str]:
    """Het deel van JSON Schema dat het formulier gebruikt; alleen de standaardbibliotheek, zoals de poort."""
    fouten: list[str] = []
    if "const" in schema and waarde != schema["const"]:
        return [f"{pad}: moet {schema['const']!r} zijn"]
    if "enum" in schema and waarde not in schema["enum"]:
        return [f"{pad}: {waarde!r} is niet een van {schema['enum']}"]
    soort = schema.get("type")
    typen = {"object": dict, "array": list, "string": str, "integer": int}
    if soort and not (isinstance(waarde, typen[soort]) and not (soort == "integer" and isinstance(waarde, bool))):
        return [f"{pad}: verwacht {soort}"]
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="actie", required=True)
    o = sub.add_parser("opdracht", help="de opdracht van één analist, naar stdout")
    o.add_argument("--casus", required=True)
    o.add_argument("--analist", required=True, choices=("A", "B"))
    o.add_argument("--run", required=True)
    o.add_argument("--dossier", type=Path, help="een set.json buiten de repo (een blinde casus)")
    c = sub.add_parser("controleer", help="toets een formulier; exit 1 bij een fout")
    c.add_argument("formulier", type=Path)
    c.add_argument("--casus", required=True)
    c.add_argument("--dossier", type=Path)
    args = p.parse_args(argv)
    dossier = dossier_uit(args.casus, args.dossier)
    if args.actie == "opdracht":
        sys.stdout.write(opdracht(dossier, args.casus, args.analist, args.run))
        return 0
    fouten = controleer(json.loads(args.formulier.read_text(encoding="utf-8")), dossier, args.casus)
    print("\n".join(fouten) if fouten else "Het formulier klopt.")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
