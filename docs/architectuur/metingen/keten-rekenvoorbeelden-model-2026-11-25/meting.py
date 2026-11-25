"""Meting keten-rekenvoorbeelden met het model (V8/M2, 25 nov 2026): de keten zelf, zonder schrijfpad.

Draait `jas_pipeline.keten.analyseer` met het echte model op de tekst van een bepaling zoals die op acceptatie staat
(`../keten-rekenvoorbeelden-2026-11-24/acc.json`). Er is geen api in het spel: niets komt in een laag, en de beslissingen
van de jurist blijven waar ze zijn. Vergelijkt de voorstellen met de beslissingen op acceptatie (dezelfde grens).

    cd tools/graph-qa && uv run python ../../docs/architectuur/metingen/keten-rekenvoorbeelden-model-2026-11-25/meting.py \
        --env <pad naar een .env met AZURE_FOUNDRY_*> --uit <uit.json> [--zonder-voorbeeldstap]

Met `--zonder-voorbeeldstap` is het de nulmeting op dezelfde code: de keten slaat de stap uit `voorbeeld.py` over, zodat
het verschil met een gewone run alleen van die stap komt (en niet van wat er sinds de run op acceptatie veranderde).

Het model en de instellingen zijn die van acceptatie op 25 nov 2026: `claude-sonnet-4-6` voor classifier en reviewer
(de modelkeuzes in het beheer), de standaardinstellingen van `Settings` en `RELATIE_VOORSTELLEN=true`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from dotenv import dotenv_values

from agent.adapters.anthropic_llm import AnthropicLLM
from agent.config import Settings
from agent.jas_pipeline import voorbeeld
from agent.jas_pipeline.keten import analyseer
from agent.jas_pipeline.taal import maak_provider
from bronmodel import CorpusMap, tekst_hash, valideer_ankers

HIER = Path(__file__).parent
ACC = HIER.parent / "keten-rekenvoorbeelden-2026-11-24" / "acc.json"
BEPALINGEN = {
    "Leidraad 9.5": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5",
    "IW 9 lid 1": "urn:bwb:BWBR0004770:artikel:9:lid:1",
}
TOKENS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _snapshot(iri: str, tekst: str) -> dict:
    lid = ":lid:" in iri
    node = {"bron_iri": iri, "parent_iri": "", "tekst": tekst, "bron_hash": tekst_hash(tekst),
            "type": "Lid" if lid else "Divisie", "nummer": iri.rsplit(":", 1)[-1] if lid else "9.5", "volgorde": 1}
    return {"schema_versie": 2, "snapshot_id": hashlib.sha256(json.dumps(node, sort_keys=True).encode()).hexdigest(),
            "doel": node, "nodes": [node], "segmenten": [node]}


class Teller:
    """Geeft elke aanroep door aan het echte model en telt het gebruik."""

    def __init__(self, live):
        self.live, self.aanroepen, self.som = live, [], Counter()

    def create(self, **kw):
        t = time.monotonic()
        r = self.live.create(**kw)
        gebruik = {k: getattr(r.usage, k, 0) or 0 for k in TOKENS}
        self.som.update(gebruik)
        self.aanroepen.append({"tool": kw["tools"][0]["name"], "stop": r.stop_reason,
                               "seconden": round(time.monotonic() - t, 1), **gebruik})
        return r


def meet(naam: str, iri: str, laag: dict, settings, live, provider) -> dict:
    tekst = laag["tekst"]
    snap = _snapshot(iri, tekst)
    cm = CorpusMap(snap["segmenten"])
    teller = Teller(live)
    begin = time.monotonic()
    uit = analyseer(snapshot=snap, corpus_segmenten=cm.als_dicts(), corpus=cm.corpus, llm=teller,
                    model=settings.llm_model, settings=settings)
    for v in uit.voorstellen:
        valideer_ankers(snap, v["ankers"])
    spans = [(v.start, v.eind) for v in voorbeeld.herken(iri, tekst, provider.analyseer(tekst))]

    def in_voorbeeld(s, e):
        return any(a <= s and e <= b for a, b in spans)

    codes = Counter(e.code for k in uit.fusie.kandidaten for e in k.evidence
                    if e.code in {"IN_VOORBEELD", "VOORBEELD_WAARDE", "VOORBEELD_GEEN_NORM"})
    voorstellen = [{"klasse": v["klasse"], "tekst": tekst[v["ankers"][0]["start"]:v["ankers"][0]["eind"]],
                    "start": v["ankers"][0]["start"], "eind": v["ankers"][0]["eind"],
                    "in_voorbeeld": in_voorbeeld(v["ankers"][0]["start"], v["ankers"][0]["eind"]),
                    "aandacht": v.get("aandacht", "")} for v in uit.voorstellen]
    grens = {(v["start"], v["eind"]): v for v in voorstellen}
    per_grens_klasse = {(v["start"], v["eind"], v["klasse"]) for v in voorstellen}
    acc = {"geaccordeerd": [], "afgewezen": Counter()}
    for el in laag["elementen"]:
        if el["herkomst"] != "agent":
            continue
        staat = el["lifecycle"]
        zelfde = grens.get((el["start"], el["eind"]))
        if staat in {"human_approved", "edited"}:
            acc["geaccordeerd"].append({"tekst": el["tekst"], "klasse": el["klasse"], "staat": staat,
                                        "nog_voorgesteld": zelfde is not None,
                                        "zelfde_klasse": (el["start"], el["eind"], el["klasse"]) in per_grens_klasse})
        elif staat == "rejected":
            acc["afgewezen"]["nog_voorgesteld" if zelfde else "niet_meer_voorgesteld"] += 1
    return {"bepaling": naam, "iri": iri, "voorbeeldzinnen": len(spans), "voorstellen": len(voorstellen),
            "in_voorbeeld": sum(v["in_voorbeeld"] for v in voorstellen),
            "per_klasse": dict(Counter(v["klasse"] for v in voorstellen)),
            "per_klasse_in_voorbeeld": dict(Counter(v["klasse"] for v in voorstellen if v["in_voorbeeld"])),
            "kenmerken": dict(codes), "voorbeeldmeting": uit.meting.get("voorbeelden"),
            "relaties": len(uit.relaties),
            "acc_geaccordeerd": {"aantal": len(acc["geaccordeerd"]),
                                 "nog_voorgesteld": sum(g["nog_voorgesteld"] for g in acc["geaccordeerd"]),
                                 "zelfde_klasse": sum(g["zelfde_klasse"] for g in acc["geaccordeerd"]),
                                 "weg": [g for g in acc["geaccordeerd"] if not g["nog_voorgesteld"]]},
            "acc_afgewezen": dict(acc["afgewezen"]),
            "modelaanroepen": teller.aanroepen, "tokens": dict(teller.som),
            "tokens_totaal": sum(teller.som.values()), "seconden": round(time.monotonic() - begin, 1),
            "voorstellen_lijst": voorstellen}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--env", type=Path, required=True)
    p.add_argument("--uit", type=Path, required=True)
    p.add_argument("--alleen", choices=list(BEPALINGEN))
    p.add_argument("--zonder-voorbeeldstap", action="store_true",
                   help="de nulmeting: dezelfde code, maar de stap uit voorbeeld.py doet niets")
    a = p.parse_args()
    if a.zonder_voorbeeldstap:
        voorbeeld.op_fusie = lambda fusie, teksten: (fusie, None)
    s = Settings.from_env({**dotenv_values(a.env)}).model_copy(update={
        "llm_model": "claude-sonnet-4-6", "relatie_voorstellen": True, "llm_max_retries": 2})
    live = AnthropicLLM(s)
    provider = maak_provider(s.taal_provider)
    acc = json.loads(ACC.read_text())
    uit = [meet(n, i, acc[i], s, live, provider) for n, i in BEPALINGEN.items() if not a.alleen or n == a.alleen]
    a.uit.write_text(json.dumps(uit, ensure_ascii=False, indent=1))
    for r in uit:
        print(json.dumps({k: v for k, v in r.items() if k not in {"voorstellen_lijst", "modelaanroepen"}},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
