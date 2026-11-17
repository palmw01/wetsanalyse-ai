"""Print de URL van het spaCy-model uit pyproject.toml ([tool.graph-qa] taalmodel).

Het model staat bewust niet in uv.lock (zie de extra `nlp` in pyproject.toml). Installeren:

    uv pip install "$(uv run python scripts/taalmodel.py)"
"""
from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def url() -> str:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["graph-qa"]["taalmodel"]


if __name__ == "__main__":
    print(url())
