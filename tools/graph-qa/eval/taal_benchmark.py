"""Benchmark van taalanalyse-providers op wetstekst (ADR-001 PR 3).

De vraag is niet "welke parser is het beste Nederlands", maar: **welke parser levert grenzen
waarop onze detectoren JAS-kandidaten kunnen bouwen?** Er bestaat geen treebank van Nederlandse
wetstekst, dus meten we het tegen de enige gegronde spans die er zijn: de conceptmarkeringen van de
referentieset (status `provisional`, uitsluitend de ontwikkelsplit).

Per provider:

- **tokengrens** – begint en eindigt de span op een tokengrens? Zo niet, dan kan geen enkele
  detector hem exact als kandidaat opleveren.
- **constituent** – is de span (modulo interpunctie aan de rand) exact het bereik van een
  UD-subboom? Dat is de bovengrens voor spanopties die uit de parse komen.
- **voegwoord als mark** – worden 'indien', 'tenzij', 'mits', 'als', 'voor zover' als `mark` van
  een bijzin herkend (de uitdrukkingswijze van Voorwaarde, H2:64)?
- **spanoptie** – zit de span in `spanopties()` (subbomen, kern- en volle naamwoordgroepen,
  bijzinnen, predicaten, zinnen)? Dat is de verzameling waaruit later gekozen wordt; het aantal
  opties per 1000 tekens is de prijs ervan.
- **determinisme** – levert dezelfde tekst twee keer exact dezelfde analyse op?
- **tijd** – milliseconden per 1000 tekens (na het laden).

Dit is geen kwaliteitsoordeel over de JAS-annotatie en de referentiespans zijn geen gold.

    python -m eval.taal_benchmark --providers spacy:nl_core_news_sm spacy:nl_core_news_md \\
        spacy:nl_core_news_lg stanza:nl --md /tmp/taal.md --json /tmp/taal.json
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent.jas_pipeline.taal import LinguisticAnalysis, maak_provider, spanopties

CASES = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset" / "cases.json"
_VOORWAARDE_VOEGWOORDEN = {"indien", "tenzij", "mits", "als", "zover", "wanneer"}


def ontwikkelcasussen(pad: Path = CASES) -> list[dict[str, Any]]:
    """Alleen de ontwikkelsplit: held-out families mogen niet sturen welke parser we kiezen."""
    return [c for c in json.loads(pad.read_text(encoding="utf-8")) if c.get("split") == "ontwikkeling"]


def _kern(tekst: str, start: int, eind: int) -> tuple[int, int]:
    """De span zonder witruimte en interpunctie aan de rand."""
    fragment = tekst[start:eind]
    links = len(fragment) - len(fragment.lstrip(" .,;:\n"))
    rechts = len(fragment) - len(fragment.rstrip(" .,;:\n"))
    return start + links, eind - rechts


def _constituentbereiken(a: LinguisticAnalysis) -> set[tuple[int, int]]:
    bereiken = set()
    for t in a.tokens:
        sub = tuple(i for i in a.subboom(t.i) if a.tokens[i].upos != "PUNCT") or (t.i,)
        s, e = a.bereik(sub)
        bereiken.add(_kern(a.tekst, s, e))
    return bereiken


def _handtekening(a: LinguisticAnalysis) -> tuple:
    return tuple((t.start, t.eind, t.lemma, t.upos, t.head, t.deprel) for t in a.tokens)


def meet(spec: str, casussen: list[dict[str, Any]]) -> dict[str, Any]:
    provider = maak_provider(spec)
    provider.analyseer("Opwarmen.")            # laden telt niet mee in de tijd
    per_klasse: dict[str, list[tuple[bool, bool, bool]]] = defaultdict(list)
    optie_aantal = 0
    voegwoorden = [0, 0]
    tekens, duur, deterministisch, gedegradeerd = 0, 0.0, True, []
    for c in casussen:
        tekst = c["tekst"]
        t0 = time.perf_counter()
        a = provider.analyseer(tekst)
        duur += time.perf_counter() - t0
        tekens += len(tekst)
        if a.gedegradeerd:
            gedegradeerd.append(f"{c['id']}: {a.fout}")
        if _handtekening(provider.analyseer(tekst)) != _handtekening(a):
            deterministisch = False
        grenzen_start = {t.start for t in a.tokens}
        grenzen_eind = {t.eind for t in a.tokens}
        bereiken = _constituentbereiken(a)
        opties = spanopties(a)
        for ann in c["annotaties"]:
            s, e = _kern(tekst, ann["start"], ann["end"])
            per_klasse[ann["klasse"]].append((s in grenzen_start and e in grenzen_eind, (s, e) in bereiken,
                                              (s, e) in opties))
        optie_aantal += len(opties)
        for t in a.tokens:
            if t.tekst.lower() in _VOORWAARDE_VOEGWOORDEN and t.upos in {"SCONJ", "ADP", "ADV", ""}:
                # 'als' in "als bedoeld in" is geen voorwaarde; alleen een bijzin-inleider telt.
                volgend = a.tokens[t.i + 1].tekst.lower() if t.i + 1 < len(a.tokens) else ""
                if t.tekst.lower() == "als" and volgend == "bedoeld":
                    continue
                voegwoorden[1] += 1
                # "voor zover": 'voor' is de inleider; 'zover' hangt er als fixed of advmod bij.
                vorige = a.tokens[t.i - 1] if t.i > 0 else None
                voegwoorden[0] += t.deprel == "mark" or (t.tekst.lower() == "zover" and vorige is not None
                                                        and vorige.tekst.lower() == "voor"
                                                        and vorige.deprel == "mark")
    alle = [x for v in per_klasse.values() for x in v]
    return {
        "provider": spec, "model": provider.model,
        "spans": len(alle),
        "tokengrens": sum(x[0] for x in alle) / len(alle) if alle else None,
        "constituent": sum(x[1] for x in alle) / len(alle) if alle else None,
        "spanoptie": sum(x[2] for x in alle) / len(alle) if alle else None,
        "opties_per_1000_tekens": round(1000 * optie_aantal / tekens, 1) if tekens else None,
        "per_klasse": {k: {"n": len(v), "tokengrens": sum(x[0] for x in v) / len(v),
                           "constituent": sum(x[1] for x in v) / len(v),
                           "spanoptie": sum(x[2] for x in v) / len(v)} for k, v in sorted(per_klasse.items())},
        "voegwoord_als_mark": voegwoorden[0] / voegwoorden[1] if voegwoorden[1] else None,
        "voegwoorden": voegwoorden[1],
        "deterministisch": deterministisch,
        "ms_per_1000_tekens": round(1000 * duur / tekens * 1000, 1) if tekens else None,
        "gedegradeerd": gedegradeerd,
    }


def markdown(resultaten: list[dict[str, Any]]) -> str:
    pct = lambda x: "–" if x is None else f"{100 * x:.0f}%"  # noqa: E731
    regels = ["| provider | model | tokengrens | subboom | spanoptie | opties/1000 tk | voegwoord als mark | "
              "deterministisch | ms/1000 tk |",
              "|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for r in resultaten:
        regels.append(f"| {r['provider']} | {r['model']} | {pct(r['tokengrens'])} | {pct(r['constituent'])} | "
                      f"{pct(r['spanoptie'])} | {r['opties_per_1000_tekens']} | "
                      f"{pct(r['voegwoord_als_mark'])} ({r['voegwoorden']}) | {'ja' if r['deterministisch'] else 'NEE'} | "
                      f"{r['ms_per_1000_tekens']} |")
    klassen = sorted({k for r in resultaten for k in r["per_klasse"]})
    regels += ["", "Spanoptie-dekking per klasse:", "",
               "| klasse | n | " + " | ".join(r["provider"] for r in resultaten) + " |",
               "|---|---:|" + "---:|" * len(resultaten)]
    for k in klassen:
        n = next(r["per_klasse"][k]["n"] for r in resultaten if k in r["per_klasse"])
        regels.append(f"| {k} | {n} | " + " | ".join(
            pct(r["per_klasse"].get(k, {}).get("spanoptie")) for r in resultaten) + " |")
    return "\n".join(regels) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--providers", nargs="+", default=["spacy:nl_core_news_md", "null"])
    p.add_argument("--md")
    p.add_argument("--json")
    args = p.parse_args()
    casussen = ontwikkelcasussen()
    resultaten = [meet(spec, casussen) for spec in args.providers]
    tekst = markdown(resultaten)
    print(tekst)
    if args.md:
        Path(args.md).write_text(tekst, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(resultaten, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
