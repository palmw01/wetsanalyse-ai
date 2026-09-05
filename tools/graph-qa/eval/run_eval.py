"""
Eval-harnas voor graph-qa.

Draait een gouden Q&A-set door de agent en scoort citaat-faithfulness, bron-recall,
contains- en refusal-checks. Twee modi:

  live (default) : echte providers (vereist een gevulde .env + bereikbare graaf).
      .venv/bin/python eval/run_eval.py

  offline        : gescripte fakes, geen netwerk/kosten – bewijst de harnas + scorers.
      .venv/bin/python eval/run_eval.py --offline

Exit-code ≠ 0 als niet alle cases slagen (CI-klaar).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import answer_stream  # noqa: E402
from agent.config import Settings  # noqa: E402
from agent.models import Verbruiksmeter  # noqa: E402
from eval.scoring import AnnotatieResult, CaseResult, score_annotatie, score_case  # noqa: E402

GOLDEN = Path(__file__).parent / "golden.jsonl"
GOLDEN_ANNOTATIE = Path(__file__).parent / "golden_annotatie.jsonl"


def load_golden(path: Path = GOLDEN) -> list[dict[str, Any]]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cases.append(json.loads(line))
    return cases


async def run_case(case: dict[str, Any], *, settings: Settings, llm=None, graph=None) -> CaseResult:
    parts: list[str] = []
    sources: list[dict[str, Any]] = []
    grounding: dict[str, Any] = {"grounded": True, "cited": 0, "unsupported": []}
    error: str | None = None

    async for ev in answer_stream(case["question"], settings=settings, llm=llm, graph=graph):
        t = ev.get("type")
        if t == "token":
            parts.append(ev["content"])
        elif t == "sources":
            sources = ev["sources"]
        elif t == "grounding":
            grounding = ev
        elif t == "error":
            error = ev["message"]

    return score_case(case, "".join(parts), sources, grounding, error)


async def run_suite(cases: list[dict[str, Any]], *, settings: Settings, llm=None, graph=None) -> list[CaseResult]:
    return [await run_case(c, settings=settings, llm=llm, graph=graph) for c in cases]


async def run_annotatie_case(
    case: dict[str, Any], *, settings: Settings, llm=None, graph=None, meter=None
) -> AnnotatieResult:
    """Draai één annotatie-opdracht en scoor de markeringen die eruit komen.

    Meet de hele keten (ophaal → annoteer → Critic → herziening), niet één node: dat is wat de jurist
    ook krijgt. Het corpus komt uit het `doel`-event – dezelfde tekst waartegen de agent zelf grondde,
    zodat "staat dit letterlijk in de bron" hier hetzelfde betekent als daar.

    Verworpen fragmenten worden apart bijgehouden via `verworpen_p100`, gevoed door het
    `verworpen`-event dat `emit_node` sinds fase 1B uitzendt. Ze uit de aandacht-velden afleiden
    kan niet: een fragment dat op "niet letterlijk" sneuvelde wordt nooit een element, dus er is
    achteraf niets meer te reconstrueren. Blijft het event uit, dan telt de maat 0 – en dat betekent
    "niets verworpen", niet "niet gemeten".
    """
    elementen: list[dict[str, Any]] = []
    verworpen: list[dict[str, Any]] = []
    kandidaten: list[dict[str, Any]] = []
    corpus = ""
    antwoord: list[str] = []
    error: str | None = None
    fout_soort: str | None = None

    async for ev in answer_stream(
        case["prompt"], settings=settings, llm=llm, graph=graph, meter=meter
    ):
        soort = ev.get("type")
        if soort == "element":
            elementen.append(ev["element"])
        elif soort == "verworpen":
            verworpen.extend(ev.get("items") or [])
        elif soort == "kandidaten_v2a":
            # fase 2A: gefilterde kandidaten vóór classificatie – voor candidate_recall meting
            kandidaten.extend(ev.get("items") or [])
        elif soort == "doel":
            leden = (ev.get("doel") or {}).get("leden_teksten") or []
            corpus = "\n\n".join(ld.get("tekst", "") for ld in leden)
        elif soort == "token":
            antwoord.append(ev.get("content", ""))
        elif soort == "error":
            error = ev["message"]
            # De exception-naam, niet de gesaniteerde melding: alleen daarmee is een overbelaste
            # provider te onderscheiden van een inhoudelijke fout (zie scoring.is_infrastructuurfout).
            fout_soort = ev.get("soort")

    # In V1 (geen kandidaatgenerator) zijn kandidaten leeg; score_annotatie gebruikt
    # dan de definitieve elementen als proxy voor candidate_recall.
    return score_annotatie(
        case, elementen, corpus, "".join(antwoord), error,
        verworpen=verworpen,
        kandidaten=kandidaten if kandidaten else None,
        fout_soort=fout_soort,
    )


# Vangrails voor één suite. Ze zijn er niet om zuinig te zijn maar om een meting te laten eindigen
# met een leesbaar rapport in plaats van door een job-timeout te worden afgekapt. Op 5 sep 2026 liep
# de eval twee uur (provider overbelast, elke call in zijn timeout) en werd hij gekapt; van de zes
# suites waren er vier af en het begin van de log was toen al uit het venster verdwenen.
#
# Overschrijden is géén "gezakt": de gemeten cases houden hun uitkomst en de rest heet `overgeslagen`.
SUITE_MINUTEN = 20.0
SUITE_TOKENS = 1_500_000


def _kort(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


async def run_annotatie_suite(
    cases: list[dict[str, Any]],
    *,
    settings: Settings,
    llm=None,
    graph=None,
    minuten: float = SUITE_MINUTEN,
    tokens: int = SUITE_TOKENS,
    stil: bool = False,
) -> list[AnnotatieResult]:
    """Draai de cases op volgorde, met voortgang naar stdout en een tijd-/tokenplafond.

    **De voortgangsregel is functioneel, geen versiering.** De job draait in een container en de
    enige manier om te zien wáár een run is, is de log — die tot nu toe pas aan het eind iets
    zei. Eén geflushte regel per case maakt een vastlopende run herkenbaar terwijl hij loopt.

    Het budget wordt ná elke case getoetst, niet tijdens: een halve annotatie afbreken levert een
    onbruikbare meting op, en de winst zit toch in het niet-starten van de volgende.
    """
    resultaten: list[AnnotatieResult] = []
    meter = Verbruiksmeter()
    begin = time.monotonic()

    def melden(regel: str) -> None:
        if not stil:
            print(regel, flush=True)  # flush: anders komt de log pas aan het eind vrij

    for i, case in enumerate(cases, 1):
        verstreken = (time.monotonic() - begin) / 60
        if i > 1 and (verstreken >= minuten or meter.totaal >= tokens):
            reden = "tijdbudget" if verstreken >= minuten else "tokenbudget"
            melden(f"[{i}/{len(cases)}] {reden} bereikt na {verstreken:.1f} min / "
                   f"{_kort(meter.totaal)} tokens – rest overgeslagen")
            for rest in cases[i - 1:]:
                resultaten.append(score_annotatie(
                    rest, [], "", "", f"overgeslagen: {reden} bereikt", fout_soort="Budget"))
            break

        t0 = time.monotonic()
        voor = meter.totaal
        r = await run_annotatie_case(case, settings=settings, llm=llm, graph=graph, meter=meter)
        resultaten.append(r)
        vlag = "niet gemeten" if r.niet_gemeten else ("ok" if r.passed else "GEZAKT")
        melden(f"[{i}/{len(cases)}] {case.get('bron') or 'guard':22} "
               f"{r.aantal:3} markeringen · {time.monotonic() - t0:5.1f}s · "
               f"{_kort(meter.totaal - voor):>7} tokens · {vlag}"
               + (f" · {r.error[:60]}" if r.error else ""))

    melden(f"— suite klaar: {(time.monotonic() - begin) / 60:.1f} min · "
           f"{_kort(meter.totaal)} tokens · {meter.calls} calls")
    return resultaten


def print_report(results: list[CaseResult]) -> bool:
    print(f"\n{'faith':>6} {'recall':>6} {'cont':>4} {'refu':>4} {'schoon':>6}  vraag")
    print("-" * 80)
    for r in results:
        flag = "OK " if r.passed else "XX "
        extra = f"  ! {r.error}" if r.error else ""
        print(
            f"{r.faithfulness:6.2f} {r.source_recall:6.2f} "
            f"{'ja' if r.contains_ok else 'nee':>4} {'ja' if r.refusal_ok else 'nee':>4} "
            f"{'ja' if r.zonder_verboden_ok else 'NEE':>6}  "
            f"{flag}{r.question[:44]}{extra}"
        )
    passed = sum(r.passed for r in results)
    print("-" * 80)
    print(f"{passed}/{len(results)} geslaagd")
    return passed == len(results)


def print_annotatie_report(results: list[AnnotatieResult]) -> bool:
    """Druk de annotatie-scorekaart af.

    Twee secties:
    - Per-case tabel: compact overzicht van alle cases met de meest kritische metrics.
    - Aggregate scorekaart: gemiddelden over alle cases, gegroepeerd per meetcategorie.
      Dit is de baseline die na elke architectuurwijziging (fase 2A, 2B) vergeleken wordt.
    """
    # --- per-case tabel ---
    print(f"\n{'lett':>5} {'klas':>5} {'prec':>5} {'rec':>5} {'span':>5} {'iou':>5} "
          f"{'cacc':>5} {'vw/100':>6} {'n':>3} {'scope':>5} {'inj':>4}  opdracht")
    print("-" * 100)
    for r in results:
        vlag = "-- " if r.niet_gemeten else ("OK " if r.passed else "XX ")
        extra = f"  ! {r.error}" if r.error else ""
        cacc_s = f"{r.class_acc:5.2f}" if r.class_acc is not None else "  n/a"
        print(
            f"{r.letterlijk:5.2f} {r.klassen:5.2f} {r.precisie:5.2f} {r.recall:5.2f} "
            f"{r.span_exact:5.2f} {r.span_iou_gem:5.2f} {cacc_s} {r.verworpen_p100:6.1f} "
            f"{r.aantal:3d} {'ja' if r.binnen_bereik else 'NEE':>5} "
            f"{'ja' if r.injectie_ok else 'NEE':>4}  "
            f"{vlag}{r.prompt[:32]}{extra}"
        )
    ok = sum(r.passed for r in results)
    ongemeten = [r for r in results if r.niet_gemeten]
    gemeten = len(results) - len(ongemeten)
    print("-" * 100)
    # Drie bakken, geen twee. Een case die op een overbelaste provider sneuvelt is NIET gezakt: er
    # is niets gemeten. Op 5 sep 2026 las zo'n storing als "9/10 geslaagd" — een kwaliteitsoordeel
    # dat nergens op sloeg. De noemer is daarom het aantal gemeten cases.
    print(f"{ok}/{gemeten} geslaagd van de gemeten cases "
          f"(precisie/recall zijn een trendmeting, geen slaagcriterium)")
    if ongemeten:
        print(f"{len(ongemeten)} niet gemeten – geen oordeel over de analyse:")
        for r in ongemeten:
            print(f"    · {r.prompt[:52]:52} {r.fout_soort or '?'}: {(r.error or '')[:60]}")

    # --- aggregate scorekaart ---
    n = len(results)
    if n == 0:
        return ok == 0

    def _gem(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    # Alleen cases mét ankers tellen mee voor precisie en recall. Zonder verwachtingen geeft
    # `precisie_en_recall` gratis (1.0, 1.0) (scoring.py:172), en drie van de acht cases hebben dat
    # bewust – die trokken het gemiddelde omhoog zonder iets te meten.
    met_ankers = [r for r in results if r.ankers > 0]
    prec_vals  = [r.precisie for r in met_ankers]
    rec_vals   = [r.recall for r in met_ankers]
    span_vals  = [r.span_exact for r in results]
    iou_vals   = [r.span_iou_gem for r in results]
    cacc_vals  = [r.class_acc for r in results if r.class_acc is not None]
    cand_vals  = [r.cand_recall for r in results]
    vw_vals    = [r.verworpen_p100 for r in results]
    lett_vals  = [r.letterlijk for r in results]
    klas_vals  = [r.klassen for r in results]

    cacc_s = f"{_gem(cacc_vals):.1%}" if cacc_vals else "n/a"

    print(f"""
JAS Annotation Evaluation – baseline
{"─" * 44}
Cases                         {n}

Garanties (code-afgedwongen, hoort 1.0)
  Letterlijkheid              {_gem(lett_vals):.1%}
  Klassen geldig              {_gem(klas_vals):.1%}

Ankers (trendmeting, over {len(met_ankers)} van {n} cases)
  Recall                      {_gem(rec_vals):.1%}   <- de bruikbare maat
  Precisie                    {_gem(prec_vals):.1%}   <- begrensd door het aantal ankers

Spans
  Exact match                 {_gem(span_vals):.1%}
  Token IoU (gem)             {_gem(iou_vals):.1%}

Classificatie
  Accuracy (over exact spans) {cacc_s}

Kandidaten (V1: = elementen)
  Recall                      {_gem(cand_vals):.1%}

Verworpen
  Per 100 voorstellen         {_gem(vw_vals):.1f}
{"─" * 44}
Notitie: dit is een ANKERSET, geen examenmodel. Recall zegt hoeveel van de vastgelegde ankers de
agent vond. Precisie deelt door alles wat hij voorstelde – terecht meer dan er ankers zijn – en is
dus geen kwaliteitsoordeel; gebruik hem alleen om versies onderling te vergelijken.
verworpen_p100 is 0 als er geen verworpen fragmenten zijn.
Alleen niet-nul als het model een niet-letterlijk of ongeldig fragment voorstel.""")

    # De exitcode gaat over de ANALYSE, niet over de dag. Cases die niet gemeten konden worden
    # (provider overbelast, budget bereikt) tellen niet mee: anders maakt een storing de run rood en
    # is niet meer te zien of er iets met de agent mis is. Zijn ALLE cases ongemeten, dan is er niets
    # gemeten en is groen ook geen eerlijk antwoord.
    gemeten = [r for r in results if not r.niet_gemeten]
    if not gemeten:
        print("\nGEEN ENKELE CASE GEMETEN – dit is geen uitspraak over de kwaliteit.")
        return False
    return all(r.passed for r in gemeten)


def _offline_annotatie_scenario():
    """Eén gescripte annotatie + fakes: bewijst de harnas, niet het model.

    Wat hier wél getest wordt is de meting zelf – dat een fragment uit een ander lid als
    buiten-bereik telt en dat een injectie in de wettekst wordt opgemerkt. Of het écht model daar
    intrapt, meet alleen de live-run.

    De verwachte set bevat één exact-match (Rechtsobject) en één span-mismatch
    (Tijdsaanduiding – agent geeft een kortere variant terug). Zo exerceren we alle
    matching-passen in de offline-run.
    """
    import json as _json

    from tests.fakes import FakeGraph, FakeLLM, response, text_block, tool_block

    lid_tsv = _json.dumps(
        '?nummer\t?tekst\n"1"\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."'
    )
    elementen = _json.dumps({"elementen": [
        {"klasse": "Rechtsobject", "tekst": "Een belastingaanslag", "lid": "1",
         "toelichting": "waarover het gaat", "alternatieven": []},
        {"klasse": "Tijdsaanduiding", "tekst": "zes weken na de dagtekening", "lid": "1",
         "toelichting": "wanneer", "alternatieven": []},
    ]})
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block('{"bwbId":"BWBR0004770","artikel":"9","lid":"1","citeertitel":"IW 1990"}')], "end_turn"),
        response([text_block(elementen)], "end_turn"),
        response([text_block(_json.dumps({"oordelen": [], "ontbrekend": []}))], "end_turn"),
    ])
    case = {
        "prompt": "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        "verwacht": [
            {"klasse": "Rechtsobject", "tekst": "Een belastingaanslag"},
            # Gold heeft de volledige tijdsspan; agent geeft een kortere variant – IoU > 0, exact = 0
            {"klasse": "Tijdsaanduiding", "tekst": "zes weken na de dagtekening van het aanslagbiljet"},
        ],
        "verboden": ["uitstel van betaling"],
        "kanaries": ["GEHACKT"],
    }
    return [case], llm, FakeGraph(result=lid_tsv)


def _offline_scenario():
    """Eén gescripte case + fakes die de harnas end-to-end aantonen (geen netwerk)."""
    from tests.fakes import FakeGraph, FakeLLM, response, text_block, tool_block

    graph = FakeGraph(result='<urn:bwb:BWBR0004770> bwb:citeertitel "Invorderingswet 1990" .')
    llm = FakeLLM([
        response([text_block("Ik raadpleeg list_regelingen.")], "end_turn"),          # plan-node (create)
        response([tool_block("t1", "list_regelingen", {})], "tool_use"),              # agent-turn 1 (stream)
        response([text_block("De Invorderingswet 1990 (BWBR0004770) staat in de graaf.")], "end_turn"),  # agent-turn 2
    ])
    case = {
        "question": "Welke regelingen zitten er in de kennisgraaf?",
        "expected_sources": ["BWBR0004770"],
        "expected_contains": ["Invorderingswet 1990"],
        "should_refuse": False,
    }
    return [case], llm, graph


def _laad_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="graph-qa eval-harnas")
    ap.add_argument("--offline", action="store_true", help="draai met fakes (geen netwerk/kosten)")
    ap.add_argument("--golden", type=Path, default=GOLDEN, help="pad naar de golden set (jsonl)")
    ap.add_argument("--annotatie", action="store_true",
                    help="draai de annotatie-set (JAS-markeringen) in plaats van de QA-set")
    ap.add_argument("--retrieval-smoke", action="store_true",
                    help="raak elke graaftool één keer tegen de ECHTE graaf en meld lege uitkomsten")
    args = ap.parse_args()

    if args.retrieval_smoke:
        # Bewust geen --offline-variant: een fake-graaf geeft altijd antwoord, en dan meet je de
        # fake. Dit is de enige controle in het harnas die over de graafinhoud gaat.
        from eval.retrieval_smoke import draai, rapporteer

        _laad_env()
        uitkomsten, geslaagd = draai(Settings.from_env())
        rapporteer(uitkomsten, geslaagd)
        sys.exit(0 if geslaagd else 1)

    if args.annotatie:
        if args.offline:
            cases, llm, graph = _offline_annotatie_scenario()
            resultaten = asyncio.run(run_annotatie_suite(
                cases, settings=Settings(checkpoint_db_path=None), llm=llm, graph=graph,
            ))
        else:
            _laad_env()
            resultaten = asyncio.run(run_annotatie_suite(
                load_golden(GOLDEN_ANNOTATIE), settings=Settings.from_env(),
            ))
        sys.exit(0 if print_annotatie_report(resultaten) else 1)

    if args.offline:
        cases, llm, graph = _offline_scenario()
        results = asyncio.run(run_suite(cases, settings=Settings(checkpoint_db_path=None), llm=llm, graph=graph))
    else:
        _laad_env()
        settings = Settings.from_env()
        cases = load_golden(args.golden)
        if not settings.similarity_index:
            # semantic_search-cases overslaan tot de similarity-index bestaat.
            cases = [c for c in cases if c.get("requires") != "semantic"]
        results = asyncio.run(run_suite(cases, settings=settings))

    ok = print_report(results)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
