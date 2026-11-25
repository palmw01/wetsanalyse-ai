"""Meting keten-rekenvoorbeelden (V8/M2, 24 nov 2026): wat de stap `voorbeeld.py` doet, zonder model, vóór en na.

Per bepaling detectie en fusie met de echte parser, dan de deterministische besluiten; "vóór" zonder de stap, "na" met.
Daartegen:

1. **de beslissingen op acceptatie** (`acc.json`: de tekst en de elementen van de laag, met hun lifecycle, uit
   `/api/annotatie/v2/weergave`). Per element van Lex de kandidaat met dezelfde grens: valt hij na de stap weg (afgewezen,
   of zijn klasse vervallen), of krijgt hij het kenmerk `IN_VOORBEELD`? Dat geeft het aandeel afwijzingen dat de stap
   wegneemt, en of hij iets wegneemt wat de jurist accordeerde;
2. **de referentie** (optioneel, lokaal, materiaal van derden: `--referentie <referentie.json>` uit
   `eval/extern_bibliotheek.py lees`): per formulering Variabele of Parameter of er een kandidaat is die niet is afgewezen,
   die klasse kan dragen en dezelfde woorden heeft (token-IoU ≥ 0,5, de maat van `extern_bibliotheek`). Dat is
   kandidaat-dekking, geen recall: welke klasse het model kiest, meet dit niet. Alleen aantallen in de uitvoer.

Draai vanuit tools/graph-qa:

    uv run python ../../docs/architectuur/metingen/keten-rekenvoorbeelden-2026-11-24/meting.py \\
        ../../docs/architectuur/metingen/keten-rekenvoorbeelden-2026-11-24/acc.json [--referentie <pad>] > uit.json
"""
from __future__ import annotations

import argparse
import json

from agent.jas_pipeline import voorbeeld
from agent.jas_pipeline.besluit import deterministisch
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.taal import maak_provider
from eval.scoring import _token_iou

VAR, PAR = "Variabele en variabelewaarde", "Parameter en parameterwaarde"
# De vindplaats in de referentie per bron-iri van acceptatie.
VINDPLAATS = {
    "urn:bwb:BWBR0004770:artikel:9:lid:1": ("IW", "9", "1"),
    "urn:bwb:BWBR0004770:artikel:9:lid:5": ("IW", "9", "5"),
    "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1": ("Leidr. Inv.", "9.1", ""),
    "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5": ("Leidr. Inv.", "9.5", ""),
}


def _staat(k) -> tuple[bool, tuple[str, ...], bool]:
    """(afgewezen, mogelijke klassen, in een voorbeeld) van een kandidaat na de besluiten zonder model."""
    b = deterministisch(k)
    afgewezen = k.status is CandidateStatus.REJECTED or (b is not None and b.status is CandidateStatus.REJECTED)
    return afgewezen, k.possible_classes, any(e.code == "IN_VOORBEELD" for e in k.evidence)


def meet(iri: str, laag: dict, provider, referentie: dict | None) -> dict:
    tekst = laag["tekst"]
    analyse = provider.analyseer(tekst)
    voor = fuseer(detecteer_alles(BronTekst.van_tekst(iri, tekst, analyse=analyse))).kandidaten
    vb = voorbeeld.herken(iri, tekst, analyse)
    na = voorbeeld.pas_toe(voor, vb)
    per_span_voor = {(k.span.start, k.span.eind): _staat(k) for k in voor}
    per_span_na = {(k.span.start, k.span.eind): _staat(k) for k in na}

    elementen = {"totaal": 0, "zonder_kandidaat": 0}
    for e in laag["elementen"]:
        if e.get("herkomst") not in (None, "agent") or e.get("bron") != iri:
            continue
        elementen["totaal"] += 1
        sleutel = (e["start"], e["eind"])
        if sleutel not in per_span_voor:
            elementen["zonder_kandidaat"] += 1
            continue
        afg_voor, klassen_voor, _ = per_span_voor[sleutel]
        afg, klassen, in_vb = per_span_na[sleutel]
        if afg_voor or e["klasse"] not in klassen_voor:
            uitkomst = "al_niet_zo"          # ook zonder de stap niet zo voorgesteld (de jurist wijzigde de klasse)
        elif afg or e["klasse"] not in klassen:
            uitkomst = "valt_weg"
        else:
            uitkomst = "kenmerk" if in_vb else "gelijk"
        rij = elementen.setdefault(e["lifecycle"], {})
        rij[uitkomst] = rij.get(uitkomst, 0) + 1
        if uitkomst in ("valt_weg", "kenmerk"):
            elementen.setdefault("per_klasse", {}).setdefault(f'{e["lifecycle"]}:{uitkomst}', {})
            t = elementen["per_klasse"][f'{e["lifecycle"]}:{uitkomst}']
            t[e["klasse"]] = t.get(e["klasse"], 0) + 1

    uit = {"bepaling": laag.get("label", iri), "voorbeelden": [{"signaal": v.signaal, "start": v.start, "eind": v.eind}
                                                              for v in vb],
           "kandidaten": len(voor), "na_afgewezen_door_stap": sum(
               k.status is CandidateStatus.REJECTED and any(e.code in voorbeeld.AFWIJZINGSCODES for e in k.evidence)
               for k in na),
           "na_met_kenmerk": sum(any(e.code == "IN_VOORBEELD" for e in k.evidence) for k in na),
           "elementen_op_acceptatie": elementen}
    if referentie is not None:
        afk, art, lid = VINDPLAATS[iri]
        dekking = {}
        for f in referentie["formuleringen"]:
            klasse = next((c for c in f["klasse"] if c in (VAR, PAR)), None)
            if klasse is None or not any((v["afkorting"], v["artikel"], v["lid"]) == (afk, art, lid)
                                         for v in f["vindplaatsen"]):
                continue
            rij = dekking.setdefault(klasse, {"referentie": 0, "voor": 0, "na": 0})
            rij["referentie"] += 1
            for naam, staat in (("voor", per_span_voor), ("na", per_span_na)):
                if any(not afg and klasse in klassen and _token_iou(tekst[s:e], f["tekst"]) >= 0.5
                       for (s, e), (afg, klassen, _) in staat.items()):
                    rij[naam] += 1
        uit["kandidaatdekking_referentie"] = dekking
    return uit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("acc")
    p.add_argument("--referentie")
    a = p.parse_args()
    acc = json.load(open(a.acc, encoding="utf-8"))
    ref = json.load(open(a.referentie, encoding="utf-8")) if a.referentie else None
    provider = maak_provider("spacy:nl_core_news_md")
    print(json.dumps({"voorbeeld_versie": voorbeeld.VERSIE,
                      "bepalingen": [meet(iri, laag, provider, ref) for iri, laag in acc.items() if iri in VINDPLAATS]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
