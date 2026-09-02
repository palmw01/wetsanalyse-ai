#!/usr/bin/env python3
"""Reviewstatistiek over een JSON-export uit de werkplek.

    python api/scripts/statistiek.py export1.json export2.json …

Waarom een script naast `GET /v1/admin/annotatie-statistiek`: dat endpoint praat met de database, en
de api draait op Azure met interne ingress. Een export in je downloadmap is vandaag de enige plek
waar de reviewbeslissingen van een echte werkplek te vinden zijn zonder databasetoegang. Beide
ingangen delen dezelfde aggregatie (`app.annotatie_statistiek`), dus ze kunnen niet uiteenlopen.

Lees de cijfers als tellingen, niet als percentages met betekenis: zolang er weinig gereviewd is
zegt "80% goedgekeurd" over vijf elementen niets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.annotatie_contracts import AnnotatieDocument, AnnotatieElement  # noqa: E402
from app.annotatie_statistiek import _naar_element, rapport  # noqa: E402


def _document(pad: Path) -> AnnotatieDocument:
    data = json.loads(pad.read_text(encoding="utf-8"))
    meta = data.get("document") or {}
    return AnnotatieDocument(
        slug=meta.get("slug") or pad.stem,
        bwbId=meta.get("bwbId", ""), artikel=meta.get("artikel", ""), lid=meta.get("lid") or "",
        elementen=[AnnotatieElement.model_validate(_naar_element(e))
                   for e in (data.get("elementen") or [])],
    )


def _tabel(titel: str, rijen: dict, kolommen: list[str]) -> None:
    if not rijen:
        return
    breedte = max(len(k) for k in rijen)
    print(f"\n{titel}")
    print(f"  {'':<{breedte}}  " + "  ".join(f"{k:>11}" for k in kolommen))
    for naam, vak in rijen.items():
        print(f"  {naam:<{breedte}}  " + "  ".join(f"{vak.get(k, 0):>11}" for k in kolommen))


def main(paden: list[str]) -> int:
    if not paden:
        print(__doc__)
        return 2
    st = rapport([_document(Path(p)) for p in paden])

    print(f"{st.documenten} document(en), {st.elementen} elementen "
          f"({st.van_agent} van de agent, {st.van_jurist} van de jurist)")
    print(f"\nReviewuitkomst over de {st.van_agent} agent-voorstellen")
    for label in ("goedgekeurd", "aangepast", "afgewezen", "open"):
        n = getattr(st, label)
        deel = f"{n / st.van_agent:6.1%}" if st.van_agent else "     –"
        print(f"  {label:<12} {n:>5}  {deel}")

    _tabel("Per JAS-klasse", st.per_klasse,
           ["totaal", "goedgekeurd", "aangepast", "afgewezen", "open"])
    _tabel("Per model", st.per_model, ["totaal", "goedgekeurd", "aangepast", "afgewezen", "open"])
    _tabel("Critic-oordeel tegenover de jurist", st.critic, ["beoordeeld", "gecorrigeerd"])

    if st.per_review_reason:
        print("\nReden van de correctie")
        for reden, n in st.per_review_reason.items():
            print(f"  {reden:<24} {n:>5}")
    if st.klasse_verschuivingen:
        print("\nWat de jurist er anders in zag")
        for verschuiving, n in st.klasse_verschuivingen.items():
            print(f"  {verschuiving:<44} {n:>4}x")

    if not any((st.goedgekeurd, st.aangepast, st.afgewezen)):
        print("\nNog geen enkele reviewbeslissing – dit zijn voorlopig alleen voorstellen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
