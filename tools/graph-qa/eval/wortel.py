"""De wortel van de repo, voor evals die bestanden uit `docs/` of `.claude/` lezen.

In de checkout staat een eval op `tools/graph-qa/eval/`, vier mappen onder de wortel. In het image van graph-qa staat hij
op `/app/eval/` en is er geen repo: dan is de wortel de map van het image (`/app`), en vindt een eval die toch een
bestand uit `docs/` leest dat niet. Zo breekt geen eval bij het importeren, ook niet een die in het image draait
(`eval/bronselectie_model_meting.py` haalt zijn sets daarom van GitHub)."""
from __future__ import annotations

from pathlib import Path

_HIER = Path(__file__).resolve()
WORTEL = _HIER.parents[3] if len(_HIER.parents) > 3 else _HIER.parents[1]
