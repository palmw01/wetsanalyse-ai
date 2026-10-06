"""Het manifest van een meting: welke code, welke referentie en welke instellingen hoorden erbij.

Eén vorm voor alle meetscripts, zodat `eval.vergelijk_rapporten` kan weigeren wat niet vergelijkbaar
is (een andere referentie, een ander model, een andere casusset). Meetbestanden worden achteraf niet
gewijzigd (`docs/architectuur/metingen/README.md`): het manifest is wat een meting later nog
herleidbaar maakt.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import subprocess
from pathlib import Path
from typing import Any

from eval import casusbron

ROOT = Path(__file__).resolve().parents[3]
PIJPLIJN = ROOT / "tools/graph-qa/agent/jas_pipeline"
SCHEMA_VERSIE = 1


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def codehashes(extra: list[Path] | None = None) -> dict[str, str]:
    """Hashes van de keten (Python en regel-YAML), de lockfile en eventuele extra invoer."""
    bestanden = [*PIJPLIJN.rglob("*.py"), *PIJPLIJN.rglob("*.yaml"), ROOT / "tools/graph-qa/uv.lock", *(extra or [])]
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(set(bestanden))}


def detectorversies() -> dict[str, str]:
    from agent.jas_pipeline.detectoren import standaard_detectoren
    from agent.jas_pipeline.fusie import VERSIE as FUSIE
    return {**{d.naam: d.versie for d in standaard_detectoren()}, "fusie": FUSIE}


def maak(casussen: str, *, settings: Any = None, extra: list[Path] | None = None) -> dict[str, Any]:
    """Het manifest. Met `settings` (een modelrun) komen model, provider, prompt en ketenvlaggen erbij."""
    uit: dict[str, Any] = {
        "schema_versie": SCHEMA_VERSIE,
        "git_sha": _git("rev-parse", "HEAD"),
        "werkkopie_schoon": _git("status", "--porcelain", "--", "tools/graph-qa", "docs/wetsanalyse/referentieset") == "",
        "python": platform.python_version(),
        "spacy": _versie("spacy"),
        "casussen": casussen,
        "diagnostisch": casussen != casusbron.STANDAARD,
        "referentie": casusbron.hashes(casussen),
        "detectoren": detectorversies(),
        "code": codehashes(extra),
    }
    if settings is not None:
        from agent.jas_pipeline.classificatie import promptversie
        uit["run"] = {
            "model": settings.llm_model, "provider": settings.llm_provider, "agent_versie": settings.agent_versie,
            "prompt_hash": promptversie(bool(getattr(settings, "classifier_spankeuze", False))),
            **{k: getattr(settings, k, None) for k in (
                "classifier_granulariteit", "classifier_spankeuze", "classifier_temperature",
                "deterministisch_accepteren", "gerichte_review", "broncontext", "taal_provider")},
        }
    return uit


def _versie(pakket: str) -> str:
    try:
        return importlib.metadata.version(pakket)
    except importlib.metadata.PackageNotFoundError:
        return ""


# Wat gelijk moet zijn om twee metingen te mogen vergelijken. Code en git_sha mogen juist verschillen:
# dat is wat er gemeten wordt.
VERGELIJKBAAR = ("casussen", "referentie", "run.model", "run.provider", "run.classifier_granulariteit",
                 "run.deterministisch_accepteren", "run.gerichte_review", "run.classifier_spankeuze")


def verschillen(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """De velden uit `VERGELIJKBAAR` waarop twee manifesten verschillen."""
    def pak(m, pad):
        for deel in pad.split("."):
            m = (m or {}).get(deel)
        return m
    return [v for v in VERGELIJKBAAR if pak(a, v) != pak(b, v)]
