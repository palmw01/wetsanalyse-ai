"""Genereer het blinde annotatieformulier (adjudicatieprotocol v1, §11 stap 2).

Eén zelfstandig HTML-bestand met per casus alleen wat een annotator mag zien: vindplaats, versie,
brontekst en hash, plus de dertien klassen met hun herkenningsvragen. Geen conceptmarkeringen, geen
dossiertoelichting en geen systeemoutput – de casusvelden gaan via een allowlist (`ZICHTBAAR`), niet
via een blocklist, zodat een nieuw veld in de referentieset niet ongemerkt meelekt.

    python scripts/blind_formulier.py --uit blind-formulier-v1.html [--versie v1] [--casus IW01 AWB04]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.jas_klassen import JAS_KLASSEN  # noqa: E402
from agent.jas_pipeline.subtype import REGELS as SUBTYPES  # noqa: E402
from eval.adjudicatie import PROTOCOLVERSIE  # noqa: E402
from eval.referentieset import ACTUELE_VERSIE, casussen  # noqa: E402

SJABLOON = Path(__file__).with_suffix(".html")
ZICHTBAAR = ("id", "vindplaats", "versie", "bron_id", "tekstsoort", "tekst", "tekst_sha256")


def vragen(vraag: str) -> list[str]:
    """De losse herkenningsvragen van een klasse, letterlijk (de validator eist dat)."""
    return [v.strip() for v in re.findall(r"[^?]+\?", vraag)] or [vraag.strip()]


def gegevens(versie: str = ACTUELE_VERSIE, ids: list[str] | None = None) -> dict:
    alle = casussen(versie)
    if ids:
        onbekend = set(ids) - {c["id"] for c in alle}
        if onbekend:
            raise SystemExit(f"onbekende casus: {', '.join(sorted(onbekend))}")
        alle = [c for c in alle if c["id"] in ids]
    return {
        "protocolversie": PROTOCOLVERSIE, "referentie_versie": versie,
        "klassen": [{"naam": k.naam, "vragen": vragen(k.vraag),
                     "subtypes": [s for s, _ in SUBTYPES.get(k.naam, ())]} for k in JAS_KLASSEN],
        "casussen": [{v: c[v] for v in ZICHTBAAR} for c in alle],
    }


def render(data: dict) -> str:
    # "</" in een tekst zou het script-element sluiten; in JSON is "<\/" hetzelfde teken.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return SJABLOON.read_text(encoding="utf-8").replace("/*__DATA__*/", payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uit", required=True)
    ap.add_argument("--versie", default=ACTUELE_VERSIE)
    ap.add_argument("--casus", nargs="+")
    args = ap.parse_args()
    Path(args.uit).write_text(render(gegevens(args.versie, args.casus)), encoding="utf-8")
    print(f"Formulier geschreven: {args.uit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
