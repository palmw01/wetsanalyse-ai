# /// script
# requires-python = ">=3.11"
# dependencies = ["ruff==0.17.6", "coverage==7.17.4"]
# ///
"""Het kwaliteitsrapport: statische analyse en testdekking van een wijziging, als rapport en niet als poort.

Meet drie dingen en zet ze naast de basis (in de poort: de doelbranch van de PR):

- **ruff** met de regels uit `ruff.toml`: echte fouten, bugrisico's, beveiligingsrisico's en complexiteit (Python);
- **complexiteit**: de functies boven de grens van mccabe (`C901` uit dezelfde ruff-run, de grens uit `ruff.toml`);
- **testdekking**: per onderdeel het totaal, en per gewijzigd bestand welke gewijzigde regels geen test raakt.

Het rapport houdt niets tegen. Het is bedoeld om op te pakken: wat in deze wijziging **nieuw** is (een ruff-bevinding die
er in de basis niet was, een gewijzigde regel zonder test) ruimt de auteur van de PR op, mens of agent. De bestaande
schuld staat er ter informatie bij.

Gebruik, vanuit de projectroot (uv leest de versies van ruff en coverage uit de kop van dit script):

    uv run scripts/kwaliteit.py

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
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

from padcontrole import veilig_pad

WORTEL = Path(__file__).resolve().parents[1]
CONFIG = WORTEL / "ruff.toml"

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
#: Alle onderdelen met een dekkingsmeting; de poort bewaart ze als `dekking/<naam>/`.
DEKKING_ONDERDELEN = (*PYTHON_DEKKING, "frontend")
#: Zoveel regels per lijst in de Markdown; de JSON heeft alles.
MAX_REGELS = 40


def onderdeel(pad: str) -> str:
    for naam, voorvoegsel in ONDERDELEN:
        if pad.startswith(voorvoegsel):
            return naam
    return "overig"


def _tool(*args: str, cwd: Path) -> str:
    """ruff of coverage uit dezelfde omgeving als dit script (`uv run` installeert ze volgens de kop)."""
    return subprocess.run([sys.executable, "-m", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


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
    uit = _tool("ruff", "check", "--config", str(config), "--output-format", "json", "--exit-zero", "--no-cache", ".",
                cwd=map_)
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


def ruff_in_basis(basis: str) -> list[dict] | None:
    """Dezelfde ruff-run op de basis, in een tijdelijke worktree, met de regels van nu (anders telt een nieuwe regel als
    nieuwe bevinding). None als de basis niet uit te checken is."""
    with tempfile.TemporaryDirectory(prefix="kwaliteit-basis-") as tmp:
        doel = Path(tmp) / "basis"
        try:
            _git("worktree", "add", "--detach", "--quiet", str(doel), basis)
        except subprocess.CalledProcessError:
            return None
        try:
            # Een kopie in de basis zelf: de padpatronen in de config gelden vanaf de map waarin hij staat.
            (doel / "ruff.toml").write_bytes(CONFIG.read_bytes())
            return ruff_bevindingen(doel, doel / "ruff.toml")
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(doel)], cwd=WORTEL, capture_output=True)


def nieuwe_bevindingen(nu: list[dict], basis: list[dict], gewijzigd: dict[str, set[int]]) -> list[dict]:
    """De bevindingen die deze wijziging toevoegt.

    Regelnummers schuiven, dus de vergelijking telt per (bestand, code): waar dat aantal steeg, zijn de bevindingen op
    gewijzigde regels nieuw – en ligt er geen op een gewijzigde regel (een verschoven blok), dan alle van die soort.
    Alleen in gewijzigde bestanden: een bestand dat de wijziging niet raakt, kan geen nieuwe bevinding hebben.
    """
    teller_basis = Counter((b["bestand"], b["code"]) for b in basis)
    per_soort: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for b in nu:
        if b["bestand"] in gewijzigd:
            per_soort[(b["bestand"], b["code"])].append(b)
    uit = []
    for (bestand, code), soort in per_soort.items():
        if len(soort) > teller_basis.get((bestand, code), 0):
            op_regel = [b for b in soort if b["regel"] in gewijzigd[bestand]]
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
        return sorted((dekking / naam).glob("*.coverage"))
    lokaal = WORTEL / map_ / ".coverage"
    return [lokaal] if lokaal.is_file() else []


def python_dekking(naam: str, map_: str, bestanden: list[Path]) -> dict | None:
    """Voegt de shards samen en geeft per bestand (pad vanaf de projectroot) de uitvoerbare en de ongedekte regels."""
    if not bestanden:
        return None
    cwd = WORTEL / map_
    with tempfile.TemporaryDirectory(prefix=f"kwaliteit-{naam}-") as tmp:
        samen = Path(tmp) / "samen.coverage"
        rapport = Path(tmp) / "dekking.json"
        _tool("coverage", "combine", "--keep", "--quiet", f"--data-file={samen}", *map(str, bestanden), cwd=cwd)
        _tool("coverage", "json", "--quiet", "--ignore-errors", f"--data-file={samen}", "-o", str(rapport), cwd=cwd)
        data = json.loads(rapport.read_text(encoding="utf-8"))
    per_bestand = {}
    for pad, info in data["files"].items():
        regels = set(info["executed_lines"]) | set(info["missing_lines"])
        per_bestand[f"{map_}/{pad}"] = {"regels": regels, "ongedekt": set(info["missing_lines"])}
    t = data["totals"]
    return {"regels": t["num_statements"], "gedekt": t["covered_lines"], "per_bestand": per_bestand}


def frontend_dekking(dekking: Path | None) -> dict | None:
    """De istanbul-uitvoer van vitest (`coverage-final.json`): een regel telt als uitvoerbaar als er een statement
    begint, en als ongedekt als geen enkel statement op die regel draaide. De paden zijn absoluut; de testjob en de
    rapportjob draaien in dezelfde werkmap, dus de projectroot eraf halen volstaat."""
    bron = (dekking / "frontend" if dekking is not None else WORTEL / "frontend" / "coverage") / "coverage-final.json"
    if not bron.is_file():
        return None
    wortel = str(WORTEL) + "/"
    per_bestand, totaal, gedekt = {}, 0, 0
    for pad, info in json.loads(bron.read_text(encoding="utf-8")).items():
        geraakt: dict[int, bool] = {}
        for sid, plek in info["statementMap"].items():
            regel = plek["start"]["line"]
            geraakt[regel] = geraakt.get(regel, False) or info["s"].get(sid, 0) > 0
        per_bestand[pad.removeprefix(wortel)] = {"regels": set(geraakt), "ongedekt": {r for r, ja in geraakt.items() if not ja}}
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
    gewijzigd = gewijzigde_regels(basis)
    rapport: dict = {"basis": basis, "gewijzigde_bestanden": sorted(gewijzigd), "meldingen": []}

    nu = ruff_bevindingen(WORTEL, CONFIG)
    oud = ruff_in_basis(basis)
    if oud is None:
        rapport["meldingen"].append(f"de basis `{basis}` is niet uit te checken: geen vergelijking voor ruff")
    rapport["ruff"] = {
        "totaal": len(nu),
        "totaal_basis": None if oud is None else len(oud),
        "per_code": dict(Counter(b["code"] for b in nu).most_common()),
        "per_onderdeel": dict(Counter(onderdeel(b["bestand"]) for b in nu).most_common()),
        "nieuw": [] if oud is None else nieuwe_bevindingen(nu, oud, gewijzigd),
        "in_gewijzigde_bestanden": [b for b in nu if b["bestand"] in gewijzigd],
    }
    complex_nu = complexiteit(nu)
    rapport["complexiteit"] = {
        "grens": tomllib.loads(CONFIG.read_text(encoding="utf-8"))["lint"]["mccabe"]["max-complexity"],
        "aantal": len(complex_nu),
        "aantal_basis": None if oud is None else len(complexiteit(oud)),
        "hoogste": complex_nu[:10],
        "in_gewijzigde_bestanden": [c for c in complex_nu if c["bestand"] in gewijzigd],
    }

    rapport["dekking"] = {}
    for naam, map_ in PYTHON_DEKKING.items():
        try:
            meting = python_dekking(naam, map_, _dekkingsbestanden(dekking, naam, map_))
        except subprocess.CalledProcessError as fout:
            uitleg = (fout.stderr or fout.stdout or "").strip()[:300]
            rapport["meldingen"].append(f"dekking {naam}: coverage faalde ({uitleg})")
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


def _rij(label: str, nu: int, basis: int | None) -> str:
    if basis is None:
        return f"| {label} | {nu} | – | – |"
    return f"| {label} | {nu} | {basis} | {f'{nu - basis:+d}' if nu != basis else '0'} |"


def _cx(c: dict) -> str:
    return f"- `{c['bestand']}:{c['regel']}` `{c['functie']}`: {c['complexiteit']}"


def _afkappen(regels: list[str]) -> list[str]:
    if len(regels) > MAX_REGELS:
        return regels[:MAX_REGELS] + [f"- … en nog {len(regels) - MAX_REGELS} (zie `kwaliteit.json`)"]
    return regels


def markdown(rapport: dict) -> str:
    r = ["## Kwaliteitsrapport", "",
         "Alleen een rapport: het houdt niets tegen. Ruim op wat in deze wijziging **nieuw** is; de rest is bestaande "
         f"schuld. Vergeleken met `{rapport['basis'][:12]}`, {len(rapport['gewijzigde_bestanden'])} gewijzigde "
         "bestanden. Regels: `ruff.toml`; uitleg: `scripts/kwaliteit.py`.", ""]
    r += [f"> {melding}" for melding in rapport["meldingen"]]
    if rapport["meldingen"]:
        r.append("")

    ruff, cx = rapport["ruff"], rapport["complexiteit"]
    r += ["| meting | nu | basis | verschil |", "|---|---:|---:|---:|",
          _rij("ruff-bevindingen", ruff["totaal"], ruff["totaal_basis"]),
          f"| nieuw in deze wijziging | {len(ruff['nieuw'])} | | |",
          _rij(f"functies met complexiteit > {cx['grens']}", cx["aantal"], cx["aantal_basis"])]
    for naam, d in rapport["dekking"].items():
        r.append(f"| testdekking {naam} | {d['procent']}% ({d['gedekt']}/{d['regels']} {d.get('eenheid', 'regels')}) | | |")
    niet_gemeten = [n for n in DEKKING_ONDERDELEN if n not in rapport["dekking"]]
    if niet_gemeten:
        r.append(f"| testdekking niet gemeten | {', '.join(niet_gemeten)} | | |")
    r.append("")

    if ruff["nieuw"]:
        r += ["### Nieuw in deze wijziging (ruff)", ""]
        r += _afkappen([f"- `{b['bestand']}:{b['regel']}` **{b['code']}** {b['melding']}" for b in ruff["nieuw"]]) + [""]

    zonder_test = [w for d in rapport["dekking"].values() for w in d["gewijzigd_zonder_test"] if w["ongedekt"]]
    if zonder_test:
        r += ["### Gewijzigde regels zonder test", "",
              "| bestand | uitvoerbaar gewijzigd | zonder test | regels |", "|---|---:|---:|---|"]
        r += _afkappen([f"| `{w['bestand']}` | {w['gewijzigd']} | {len(w['ongedekt'])} | {bereiken(w['ongedekt'])} |"
                        for w in zonder_test]) + [""]

    if cx["in_gewijzigde_bestanden"]:
        r += [f"### Complexiteit > {cx['grens']} in gewijzigde bestanden", ""]
        r += _afkappen([_cx(c) for c in cx["in_gewijzigde_bestanden"]]) + [""]

    r += ["<details><summary>Bestaande schuld per onderdeel en per regel</summary>", "",
          "| onderdeel | ruff |", "|---|---:|"]
    r += [f"| {o} | {n} |" for o, n in ruff["per_onderdeel"].items()]
    r += ["", "| regel | aantal |", "|---|---:|"]
    r += [f"| {c} | {n} |" for c, n in ruff["per_code"].items()]
    if cx["hoogste"]:
        r += ["", "De complexste functies:", ""] + [_cx(c) for c in cx["hoogste"]]
    r += ["", "</details>", ""]
    return "\n".join(r)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--basis", help="ref om mee te vergelijken (standaard: merge-base met origin/master)")
    p.add_argument("--dekking", type=Path, help="map met de dekkingsdata van de testjobs")
    p.add_argument("--uit", type=Path, help="map voor kwaliteit.md en kwaliteit.json")
    args = p.parse_args(argv)

    basis = _git("rev-parse", args.basis or standaardbasis()).strip()
    # Absoluut: coverage draait vanuit de map van het onderdeel, niet vanuit de projectroot.
    rapport = meet(basis, args.dekking.resolve() if args.dekking else None)
    tekst = markdown(rapport)
    if args.uit:
        uit = veilig_pad(args.uit)
        uit.mkdir(parents=True, exist_ok=True)
        (uit / "kwaliteit.md").write_text(tekst, encoding="utf-8")
        data = json.dumps(rapport, default=lambda o: sorted(o) if isinstance(o, set) else str(o), ensure_ascii=False,
                          indent=1)
        (uit / "kwaliteit.json").write_text(data + "\n", encoding="utf-8")
    print(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
