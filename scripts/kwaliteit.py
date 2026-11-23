"""Het kwaliteitsrapport: statische analyse en testdekking van een wijziging, als rapport en niet als poort.

Meet drie dingen en zet ze naast de basis (in de poort: de doelbranch van de PR):

- **ruff** met de regels uit `ruff.toml`: echte fouten, bugrisico's, beveiligingsrisico's en complexiteit (Python);
- **complexiteit**: de functies boven de grens van mccabe (`C901` uit dezelfde ruff-run);
- **testdekking**: per onderdeel het totaal, en per gewijzigd bestand welke gewijzigde regels geen test raakt.

Het rapport houdt niets tegen. Het is bedoeld om op te pakken: wat in deze wijziging **nieuw** is (een ruff-bevinding die
er in de basis niet was, een gewijzigde regel zonder test) ruimt de auteur van de PR op, mens of agent. De bestaande
schuld staat er ter informatie bij.

Gebruik (vanuit de projectroot; alleen de standaardbibliotheek, plus `ruff` en `coverage` op het pad):

    uv run --no-project --with ruff==0.17.6 --with coverage==7.17.4 python scripts/kwaliteit.py

    --basis REF     waartegen vergeleken wordt (standaard: de merge-base met origin/master)
    --dekking MAP   de dekkingsdata (de poort: de artefacten van de testjobs; zie `_dekkingsbestanden`). Zonder deze
                    optie leest het script wat een lokale run achterliet: `api/.coverage`, `tools/graph-qa/.coverage`
                    en `frontend/coverage/coverage-final.json`
    --uit MAP       schrijft `kwaliteit.md` en `kwaliteit.json` (standaard: alleen de Markdown naar stdout)

Lokaal dekking meten: `cd api && uv run --with pytest-cov pytest --cov --cov-report=` (idem in `tools/graph-qa`), en
`cd frontend && npx vitest run --coverage`.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]

#: Onderdelen op padvoorvoegsel; de eerste die past telt.
ONDERDELEN = (
    ("api", "api/"),
    ("graph-qa", "tools/graph-qa/"),
    ("bwb-import", "tools/bwb-import/"),
    ("bronmodel", "packages/bronmodel/"),
    ("frontend", "frontend/"),
    ("scripts", "scripts/"),
    ("tests", "tests/"),
    ("deploy", "deploy/"),
)
#: De Python-onderdelen met een dekkingsmeting: naam → map (de dekkingsdata heeft paden relatief aan die map).
PYTHON_DEKKING = {"api": "api", "graph-qa": "tools/graph-qa"}
#: Zoveel regels per lijst in de Markdown; de JSON heeft alles.
MAX_REGELS = 40


def onderdeel(pad: str) -> str:
    for naam, voorvoegsel in ONDERDELEN:
        if pad.startswith(voorvoegsel):
            return naam
    return "overig"


# ── git ─────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _git(*args: str, cwd: Path = WORTEL) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def standaardbasis() -> str:
    try:
        return _git("merge-base", "origin/master", "HEAD").strip()
    except subprocess.CalledProcessError:
        return "HEAD"


def lees_diff(tekst: str) -> dict[str, set[int]]:
    """De regelnummers (na de wijziging) die een unified diff met `-U0` toevoegt of wijzigt, per bestand."""
    uit: dict[str, set[int]] = {}
    bestand: str | None = None
    for regel in tekst.splitlines():
        if regel.startswith("+++ "):
            pad = regel[4:].strip()
            bestand = None if pad == "/dev/null" else pad.removeprefix("b/")
            if bestand is not None:
                uit.setdefault(bestand, set())
        elif regel.startswith("@@") and bestand is not None:
            m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", regel)
            if m:
                start, aantal = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
                uit[bestand].update(range(start, start + aantal))
    return uit


def gewijzigde_regels(basis: str) -> dict[str, set[int]]:
    """Wat er ten opzichte van de basis is veranderd: commits én de werkboom (lokaal telt niet-gecommit werk mee)."""
    gewijzigd = lees_diff(_git("diff", "-U0", "--no-color", "--no-ext-diff", basis))
    # Nieuwe bestanden die nog niet in git staan, tellen helemaal mee.
    for pad in _git("ls-files", "--others", "--exclude-standard").splitlines():
        bestand = WORTEL / pad
        if bestand.is_file():
            with bestand.open(encoding="utf-8", errors="replace") as f:
                gewijzigd[pad] = set(range(1, sum(1 for _ in f) + 1))
    return gewijzigd


# ── ruff ────────────────────────────────────────────────────────────────────────────────────────────────────────────


def ruff_bevindingen(map_: Path, config: Path) -> list[dict]:
    uit = subprocess.run(
        ["ruff", "check", "--config", str(config), "--output-format", "json", "--exit-zero", "--no-cache", "."],
        cwd=map_, capture_output=True, text=True, check=True,
    ).stdout
    bevindingen = []
    for b in json.loads(uit or "[]"):
        pad = Path(b["filename"]).resolve()
        try:
            rel = pad.relative_to(map_.resolve()).as_posix()
        except ValueError:
            rel = pad.as_posix()
        bevindingen.append({
            "bestand": rel,
            "regel": b["location"]["row"],
            "code": b["code"] or "syntax",
            "melding": b["message"],
        })
    bevindingen.sort(key=lambda b: (b["bestand"], b["regel"], b["code"]))
    return bevindingen


def ruff_in_basis(basis: str, config: Path) -> list[dict] | None:
    """Dezelfde ruff-run op de basis, in een tijdelijke worktree, met de regels van nu (anders telt een nieuwe regel als
    nieuwe bevinding). None als de basis niet uit te checken is."""
    tmp = Path(tempfile.mkdtemp(prefix="kwaliteit-basis-"))
    doel = tmp / "basis"
    try:
        _git("worktree", "add", "--detach", "--quiet", str(doel), basis)
    except subprocess.CalledProcessError:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    try:
        # Een kopie in de basis zelf: de padpatronen in de config gelden vanaf de map waarin hij staat.
        shutil.copyfile(config, doel / "ruff.toml")
        return ruff_bevindingen(doel, doel / "ruff.toml")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(doel)], cwd=WORTEL, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def nieuwe_bevindingen(nu: list[dict], basis: list[dict], gewijzigd: dict[str, set[int]]) -> list[dict]:
    """De bevindingen die deze wijziging toevoegt.

    Regelnummers schuiven, dus de vergelijking telt per (bestand, code): waar dat aantal steeg, zijn de bevindingen op
    gewijzigde regels nieuw – en ligt er geen op een gewijzigde regel (een verschoven blok), dan alle van die soort.
    Alleen in gewijzigde bestanden: een bestand dat de wijziging niet raakt, kan geen nieuwe bevinding hebben.
    """
    teller_basis = Counter((b["bestand"], b["code"]) for b in basis)
    teller_nu = Counter((b["bestand"], b["code"]) for b in nu)
    gestegen = {k for k, n in teller_nu.items() if k[0] in gewijzigd and n > teller_basis.get(k, 0)}
    uit = []
    for sleutel in sorted(gestegen):
        soort = [b for b in nu if (b["bestand"], b["code"]) == sleutel]
        op_regel = [b for b in soort if b["regel"] in gewijzigd[sleutel[0]]]
        uit.extend(op_regel or soort)
    return sorted(uit, key=lambda b: (b["bestand"], b["regel"], b["code"]))


def complexiteit(bevindingen: list[dict]) -> list[dict]:
    """De `C901`-bevindingen als (bestand, regel, functie, complexiteit), de complexste eerst."""
    uit = []
    for b in bevindingen:
        if b["code"] != "C901":
            continue
        m = re.match(r"`(.+?)` is too complex \((\d+) > \d+\)", b["melding"])
        if m:
            uit.append({"bestand": b["bestand"], "regel": b["regel"], "functie": m.group(1),
                        "complexiteit": int(m.group(2))})
    return sorted(uit, key=lambda c: (-c["complexiteit"], c["bestand"], c["regel"]))


# ── dekking ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _dekkingsbestanden(dekking: Path | None, naam: str, map_: str) -> list[Path]:
    """De datafiles van coverage.py voor één onderdeel: in de poort `<dekking>/<naam>/*.coverage` (één per shard),
    lokaal `<map>/.coverage`."""
    if dekking is not None:
        return sorted((dekking / naam).glob("*.coverage")) if (dekking / naam).is_dir() else []
    lokaal = WORTEL / map_ / ".coverage"
    return [lokaal] if lokaal.is_file() else []


def python_dekking(naam: str, map_: str, bestanden: list[Path]) -> dict | None:
    """Voegt de shards samen en geeft per bestand (pad vanaf de projectroot) de uitvoerbare en de ongedekte regels."""
    if not bestanden or not shutil.which("coverage"):
        return None
    cwd = WORTEL / map_
    with tempfile.TemporaryDirectory(prefix=f"kwaliteit-{naam}-") as tmp:
        samen = Path(tmp) / "samen.coverage"
        rapport = Path(tmp) / "dekking.json"
        subprocess.run(["coverage", "combine", "--keep", "--quiet", f"--data-file={samen}", *map(str, bestanden)],
                       cwd=cwd, check=True, capture_output=True)
        subprocess.run(["coverage", "json", "--quiet", "--ignore-errors", f"--data-file={samen}", "-o", str(rapport)],
                       cwd=cwd, check=True, capture_output=True)
        data = json.loads(rapport.read_text(encoding="utf-8"))
    per_bestand = {}
    for pad, info in data["files"].items():
        regels = set(info["executed_lines"]) | set(info["missing_lines"])
        per_bestand[f"{map_}/{pad}"] = {"regels": regels, "ongedekt": set(info["missing_lines"])}
    t = data["totals"]
    return {"regels": t["num_statements"], "gedekt": t["covered_lines"], "per_bestand": per_bestand}


def frontend_dekking(dekking: Path | None) -> dict | None:
    """De istanbul-uitvoer van vitest (`coverage-final.json`): een regel telt als uitvoerbaar als er een statement
    begint, en als ongedekt als geen enkel statement op die regel draaide."""
    map_ = (dekking / "frontend") if dekking is not None else (WORTEL / "frontend" / "coverage")
    bron = map_ / "coverage-final.json"
    if not bron.is_file():
        return None
    # De paden zijn absoluut, op de machine die mat. In de poort schrijft de frontendjob die wortel mee.
    wortel_bestand = map_ / "wortel.txt"
    wortel = wortel_bestand.read_text(encoding="utf-8").strip() if wortel_bestand.is_file() else str(WORTEL)
    data = json.loads(bron.read_text(encoding="utf-8"))
    per_bestand, totaal, gedekt = {}, 0, 0
    for pad, info in data.items():
        rel = pad[len(wortel):].lstrip("/") if pad.startswith(wortel) else pad
        geraakt: dict[int, bool] = {}
        for sid, plek in info["statementMap"].items():
            regel = plek["start"]["line"]
            geraakt[regel] = geraakt.get(regel, False) or info["s"].get(sid, 0) > 0
        per_bestand[rel] = {"regels": set(geraakt), "ongedekt": {r for r, ja in geraakt.items() if not ja}}
        totaal += len(info["s"])
        gedekt += sum(1 for n in info["s"].values() if n > 0)
    return {"regels": totaal, "gedekt": gedekt, "per_bestand": per_bestand, "eenheid": "statements"}


def ongedekte_wijzigingen(per_bestand: dict, gewijzigd: dict[str, set[int]]) -> list[dict]:
    """Per gewijzigd bestand met dekkingsdata: hoeveel gewijzigde regels uitvoerbaar zijn en welke geen test raakt."""
    uit = []
    for pad in sorted(set(per_bestand) & set(gewijzigd)):
        regels = per_bestand[pad]["regels"] & gewijzigd[pad]
        if not regels:
            continue
        ongedekt = sorted(per_bestand[pad]["ongedekt"] & gewijzigd[pad])
        uit.append({"bestand": pad, "gewijzigd": len(regels), "ongedekt": ongedekt})
    return uit


def bereiken(regels: list[int]) -> str:
    """[3, 4, 5, 9] → '3-5, 9'."""
    delen, i = [], 0
    while i < len(regels):
        j = i
        while j + 1 < len(regels) and regels[j + 1] == regels[j] + 1:
            j += 1
        delen.append(str(regels[i]) if i == j else f"{regels[i]}-{regels[j]}")
        i = j + 1
    return ", ".join(delen)


# ── rapport ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def meet(basis: str, dekking: Path | None) -> dict:
    config = WORTEL / "ruff.toml"
    gewijzigd = gewijzigde_regels(basis)
    rapport: dict = {"basis": basis, "gewijzigde_bestanden": sorted(gewijzigd), "meldingen": []}

    if shutil.which("ruff"):
        nu = ruff_bevindingen(WORTEL, config)
        oud = ruff_in_basis(basis, config)
        if oud is None:
            rapport["meldingen"].append(f"de basis `{basis}` is niet uit te checken: geen vergelijking voor ruff")
        rapport["ruff"] = {
            "totaal": len(nu),
            "totaal_basis": None if oud is None else len(oud),
            "per_code": dict(Counter(b["code"] for b in nu).most_common()),
            "per_onderdeel": dict(Counter(onderdeel(b["bestand"]) for b in nu).most_common()),
            "nieuw": nieuwe_bevindingen(nu, oud or [], gewijzigd) if oud is not None else [],
            "in_gewijzigde_bestanden": [b for b in nu if b["bestand"] in gewijzigd],
        }
        complex_nu = complexiteit(nu)
        rapport["complexiteit"] = {
            "grens": 15,
            "aantal": len(complex_nu),
            "aantal_basis": None if oud is None else len(complexiteit(oud)),
            "hoogste": complex_nu[:10],
            "in_gewijzigde_bestanden": [c for c in complex_nu if c["bestand"] in gewijzigd],
        }
    else:
        rapport["meldingen"].append("ruff niet gevonden: geen statische analyse")

    rapport["dekking"] = {}
    for naam, map_ in PYTHON_DEKKING.items():
        try:
            meting = python_dekking(naam, map_, _dekkingsbestanden(dekking, naam, map_))
        except subprocess.CalledProcessError as fout:
            rapport["meldingen"].append(f"dekking {naam}: coverage faalde ({fout.stderr.decode(errors='replace')[:200]})")
            meting = None
        if meting:
            rapport["dekking"][naam] = meting
    meting = frontend_dekking(dekking)
    if meting:
        rapport["dekking"]["frontend"] = meting
    for meting in rapport["dekking"].values():
        meting["procent"] = round(100 * meting["gedekt"] / meting["regels"], 1) if meting["regels"] else None
        meting["gewijzigd_zonder_test"] = ongedekte_wijzigingen(meting.pop("per_bestand"), gewijzigd)
    return rapport


def _verschil(nu: int, basis: int | None) -> str:
    if basis is None:
        return "–"
    d = nu - basis
    return f"{d:+d}" if d else "0"


def _afkappen(regels: list[str], totaal: int) -> list[str]:
    if totaal > MAX_REGELS:
        regels = regels[:MAX_REGELS] + [f"- … en nog {totaal - MAX_REGELS} (zie `kwaliteit.json`)"]
    return regels


def markdown(rapport: dict) -> str:
    r = ["## Kwaliteitsrapport", "",
         "Alleen een rapport: het houdt niets tegen. Ruim op wat in deze wijziging **nieuw** is; de rest is bestaande "
         f"schuld. Vergeleken met `{rapport['basis'][:12]}`, {len(rapport['gewijzigde_bestanden'])} gewijzigde "
         "bestanden. Regels: `ruff.toml`; uitleg: `scripts/kwaliteit.py`.", ""]
    for melding in rapport["meldingen"]:
        r.append(f"> {melding}")
    if rapport["meldingen"]:
        r.append("")

    r += ["| meting | nu | basis | verschil |", "|---|---:|---:|---:|"]
    ruff, cx = rapport.get("ruff"), rapport.get("complexiteit")
    if ruff:
        basis = ruff["totaal_basis"]
        r.append(f"| ruff-bevindingen | {ruff['totaal']} | {'–' if basis is None else basis} | "
                 f"{_verschil(ruff['totaal'], basis)} |")
        r.append(f"| nieuw in deze wijziging | {len(ruff['nieuw'])} | | |")
    if cx:
        basis = cx["aantal_basis"]
        r.append(f"| functies met complexiteit > {cx['grens']} | {cx['aantal']} | {'–' if basis is None else basis} | "
                 f"{_verschil(cx['aantal'], basis)} |")
    for naam, d in rapport["dekking"].items():
        eenheid = d.get("eenheid", "regels")
        r.append(f"| testdekking {naam} | {d['procent']}% ({d['gedekt']}/{d['regels']} {eenheid}) | | |")
    niet_gemeten = [n for n in (*PYTHON_DEKKING, "frontend") if n not in rapport["dekking"]]
    if niet_gemeten:
        r.append(f"| testdekking niet gemeten | {', '.join(niet_gemeten)} | | |")
    r.append("")

    if ruff and ruff["nieuw"]:
        r += ["### Nieuw in deze wijziging (ruff)", ""]
        regels = [f"- `{b['bestand']}:{b['regel']}` **{b['code']}** {b['melding']}" for b in ruff["nieuw"]]
        r += _afkappen(regels, len(regels)) + [""]

    zonder_test = [(naam, w) for naam, d in rapport["dekking"].items() for w in d["gewijzigd_zonder_test"] if w["ongedekt"]]
    if zonder_test:
        r += ["### Gewijzigde regels zonder test", "",
              "| bestand | uitvoerbaar gewijzigd | zonder test | regels |", "|---|---:|---:|---|"]
        for _, w in zonder_test[:MAX_REGELS]:
            r.append(f"| `{w['bestand']}` | {w['gewijzigd']} | {len(w['ongedekt'])} | {bereiken(w['ongedekt'])} |")
        if len(zonder_test) > MAX_REGELS:
            r.append(f"| … en nog {len(zonder_test) - MAX_REGELS} bestanden | | | |")
        r.append("")

    if cx and cx["in_gewijzigde_bestanden"]:
        r += [f"### Complexiteit > {cx['grens']} in gewijzigde bestanden", ""]
        regels = [f"- `{c['bestand']}:{c['regel']}` `{c['functie']}`: {c['complexiteit']}"
                  for c in cx["in_gewijzigde_bestanden"]]
        r += _afkappen(regels, len(regels)) + [""]

    if ruff:
        r += ["<details><summary>Bestaande schuld per onderdeel en per regel</summary>", "",
              "| onderdeel | ruff |", "|---|---:|"]
        r += [f"| {o} | {n} |" for o, n in ruff["per_onderdeel"].items()]
        r += ["", "| regel | aantal |", "|---|---:|"]
        r += [f"| {c} | {n} |" for c, n in ruff["per_code"].items()]
        if cx and cx["hoogste"]:
            r += ["", "De complexste functies:", ""]
            r += [f"- `{c['bestand']}:{c['regel']}` `{c['functie']}`: {c['complexiteit']}" for c in cx["hoogste"]]
        r += ["", "</details>", ""]
    return "\n".join(r)


def _json_klaar(rapport: dict) -> dict:
    return json.loads(json.dumps(rapport, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis", help="ref om mee te vergelijken (standaard: merge-base met origin/master)")
    p.add_argument("--dekking", type=Path, help="map met de dekkingsdata van de testjobs")
    p.add_argument("--uit", type=Path, help="map voor kwaliteit.md en kwaliteit.json")
    args = p.parse_args(argv)

    basis = _git("rev-parse", args.basis or standaardbasis()).strip()
    rapport = meet(basis, args.dekking)
    tekst = markdown(rapport)
    if args.uit:
        args.uit.mkdir(parents=True, exist_ok=True)
        (args.uit / "kwaliteit.md").write_text(tekst, encoding="utf-8")
        (args.uit / "kwaliteit.json").write_text(json.dumps(_json_klaar(rapport), ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
    print(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
