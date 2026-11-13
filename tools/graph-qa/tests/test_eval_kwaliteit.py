"""De kwaliteitsnulmeting: vraagtypen in de sets, de deterministische scorers, en bewaren → herscoren."""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from eval import run_eval
from eval.gesprek import GOLDEN_GESPREK, herscoor_gesprekken, run_gesprek_suite
from eval.kwaliteit import lopende_tekst, sjabloon_ok, toon, volgorde_ok, zinnen
from eval.opname import bewaar, lees, nieuwe_opname
from eval.scoring import score_opname
from eval.vraagtypen import MIN_CASES, VRAAGTYPEN, dekking, dekking_regel, vraagtype_van
from fakes import make_settings


def _typen() -> list[str]:
    qa = [vraagtype_van(c) for c in run_eval.load_golden(run_eval.GOLDEN)]
    gesprek = [vraagtype_van(c, b) for c in run_eval.load_golden(GOLDEN_GESPREK) for b in c["beurten"]]
    return qa + gesprek


# --- vraagtypen --------------------------------------------------------------------------------------

def test_elke_case_en_beurt_heeft_een_bekend_vraagtype():
    for c in run_eval.load_golden(run_eval.GOLDEN):
        assert vraagtype_van(c) in VRAAGTYPEN, c["question"]
    for c in run_eval.load_golden(GOLDEN_GESPREK):
        for b in c["beurten"]:
            assert vraagtype_van(c, b) in VRAAGTYPEN, (c["id"], b["vraag"])


def test_vraagtype_van_de_beurt_wint_van_het_gesprek():
    assert vraagtype_van({"vraagtype": "vervolg"}, {"vraagtype": "bepaling"}) == "bepaling"
    assert vraagtype_van({"vraagtype": "vervolg"}, {}) == "vervolg"
    assert vraagtype_van({}) == ""


def test_dekkingsoverzicht_noemt_de_dunne_types():
    """Geen harde fout: het overzicht maakt zichtbaar welke types te weinig cases hebben (`pytest -s`)."""
    typen = _typen()
    regel = dekking_regel(typen)
    print("\n" + regel)
    d = dekking(typen)
    assert list(d) == list(VRAAGTYPEN) and sum(d.values()) == len(typen)
    onder = regel.split(f"onder de {MIN_CASES}: ")[1] if "onder de" in regel else ""
    assert set(onder.split(", ")) - {""} == {t for t, n in d.items() if n < MIN_CASES}


# --- volgorde en sjabloon ------------------------------------------------------------------------------

def test_volgorde_ziet_een_slotzin_voor_de_onderdelen():
    goed = "Derden kunnen nimmer verzet doen tegen:\na. de beslaglegging ter zake van X;\nindien de vruchten nog staan."
    fout = "Indien de vruchten nog staan, kunnen derden nimmer verzet doen tegen:\na. de beslaglegging ter zake van X;"
    frag = ["nimmer verzet doen tegen", "de beslaglegging ter zake van", "indien de vruchten"]
    assert volgorde_ok(goed, frag)
    assert not volgorde_ok(fout, frag)
    assert not volgorde_ok(goed, [*frag, "ontbreekt"])
    assert volgorde_ok("wat dan ook", None)


def test_volgorde_zoekt_een_herhaald_fragment_na_het_vorige():
    tekst = "de beslaglegging ter zake van naheffingsaanslagen in X; de beslaglegging ter zake van: a. Y"
    eerst, dan = "de beslaglegging ter zake van naheffingsaanslagen in", "de beslaglegging ter zake van:"
    assert volgorde_ok(tekst, [eerst, dan])
    assert not volgorde_ok(tekst, [dan, eerst])


def test_sjabloon():
    assert sjabloon_ok({"sjabloon": "bepaling"}, "bepaling")
    assert not sjabloon_ok({"sjabloon": "duiding"}, "bepaling")
    assert not sjabloon_ok(None, "bepaling")          # een vrij antwoord gebruikte geen sjabloon
    assert sjabloon_ok(None, None)


def test_score_case_zakt_op_volgorde_en_sjabloon_maar_niet_op_toon():
    from eval.scoring import score_case

    case = {"question": "q", "vraagtype": "bepaling", "sjabloon": "bepaling", "volgorde": ["eerst", "dan"]}
    met_u = {"sjabloon": "bepaling", "blokken": [{"soort": "toelichting", "tekst": "Kunt u dit lezen?"}]}
    goed = score_case(case, "eerst en dan. Kunt u dit lezen?", [{"uri": "x"}], {}, antwoord=met_u)
    assert goed.passed and goed.toon.aantal == 1 and goed.vraagtype == "bepaling"
    assert not score_case(case, "dan en eerst", [{"uri": "x"}], {}, antwoord={"sjabloon": "bepaling"}).passed
    assert not score_case(case, "eerst en dan", [{"uri": "x"}], {}, antwoord={"sjabloon": "duiding"}).passed


# --- toon ----------------------------------------------------------------------------------------------

def test_toon_schoon():
    t = toon("Artikel 9 regelt wanneer een aanslag invorderbaar is.\n\n- **lid 1**: zes weken na de dagtekening.")
    assert t.overtredingen == [] and t.lange_zinnen == 0.0


def test_toon_ziet_elke_overtreding():
    t = toon("# Antwoord\n\nIk zoek dat voor u op 🙂. Zie urn:bwb:BWBR0004770 en get_lid(9); de worker meldt in_review.")
    soorten = " ".join(t.overtredingen)
    for verwacht in ("emoji", "Markdown-kop", "u-vorm", "urn:bwb:", "get_lid(", "worker", "in_review"):
        assert verwacht in soorten, verwacht


def test_toon_onderdeelletter_en_vetgedrukt_zijn_geen_overtreding():
    assert toon("Zie onderdeel u. van het eerste lid, en **vet** mag.").overtredingen == []
    assert toon("Uw termijn loopt.").overtredingen == ["u-vorm 'Uw'"]


def test_toon_telt_lange_zinnen():
    lang = " ".join(["woord"] * 25) + "."
    t = toon(f"Korte zin. {lang}")
    assert t.lange_zinnen == 0.5
    assert zinnen("- eerste punt\n- tweede punt") == ["eerste punt", "tweede punt"]


def test_toon_leest_de_brontekst_niet():
    """Wettekst en citaten zijn brontekst: een lange wetszin of een 'u' daarin is geen fout van Lex."""
    wetszin = " ".join(["wettekst"] * 30) + " door u."
    antwoord = {"sjabloon": "bepaling", "blokken": [
        {"soort": "wettekst", "items": [{"tekst": wetszin}]},
        {"soort": "citaten", "items": [{"tekst": wetszin, "waarom": "Dit lid regelt de termijn."}]},
        {"soort": "toelichting", "kop": "Toelichting", "tekst": "Kort."}]}
    assert lopende_tekst("", antwoord) == "Dit lid regelt de termijn.\n\nKort."
    assert toon(wetszin, antwoord).overtredingen == []
    # Zonder antwoord-event: citaatregels en aanhalingen vallen weg.
    assert toon(f'> "{wetszin}"\n\nDe wet zegt "{wetszin}" hier.').overtredingen == []


# --- bewaren → herscoren ------------------------------------------------------------------------------

def test_bewaren_en_herscoren_geeft_dezelfde_scores(tmp_path):
    cases, llm, graph = run_eval._offline_scenario()
    regels: list = []
    live = asyncio.run(run_eval.run_suite(cases, settings=make_settings(), llm=llm, graph=graph, regels=regels))
    pad = tmp_path / "qa.jsonl"
    bewaar(pad, regels)
    terug = run_eval.herscoor_qa(lees(pad))
    assert [asdict(r) for r in terug] == [asdict(r) for r in live]
    opname = lees(pad)[0]["opname"]
    assert opname["vraagtype"] == "feit" and "list_regelingen" in opname["tools"] and opname["sources"]


def test_gesprek_bewaren_en_herscoren_geeft_dezelfde_scores(tmp_path):
    cases, llm, graph, settings = run_eval._offline_gesprek_scenario(str(tmp_path / "cp.db"))
    regels: list = []
    live = asyncio.run(run_gesprek_suite(cases, settings=settings, llm=llm, graph=graph, stil=True, regels=regels))
    pad = tmp_path / "gesprek.jsonl"
    bewaar(pad, regels)
    terug = herscoor_gesprekken(lees(pad))
    assert [asdict(r) for r in terug] == [asdict(r) for r in live]
    assert [b.vraagtype for b in terug[0].beurten] == ["bepaling", "vervolg"]
    assert all(r["opname"]["status"] for r in lees(pad))


def test_de_duidingset_is_geldig_en_vraagt_het_duidingsjabloon():
    """D5 meet hiermee: elke case is een duiding met sjabloon, een bron en iets wat in het antwoord hoort te staan."""
    from pathlib import Path
    cases = run_eval.load_golden(Path(run_eval.__file__).parent / "golden_duiding.jsonl")
    assert len(cases) >= 5 and len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert vraagtype_van(c) == "duiding" and c["sjabloon"] == "duiding", c["id"]
        assert c["expected_sources"] and c["expected_contains"] and c["should_refuse"] is False, c["id"]


def test_de_meetset_bij_g1_is_geldig_en_raakt_de_voorbeelden_van_de_skill_niet():
    """G1 (plan methodes scheiden, deel 2): tien Awb-bepalingen, vijf met een partij die de tekst niet noemt en vijf met
    een bekende soort bevoegdheid of plicht; geen bepaling uit de voorbeelden van de skill."""
    from pathlib import Path
    cases = run_eval.load_golden(Path(run_eval.__file__).parent / "golden_duiding_partijen.jsonl")
    assert len(cases) == 10 and len({c["id"] for c in cases}) == 10
    assert sorted(c["toets"] for c in cases) == ["partij"] * 5 + ["soort"] * 5
    for c in cases:
        assert vraagtype_van(c) == "duiding" and c["sjabloon"] == "duiding" and c["beoordeling"], c["id"]
        assert c["expected_sources"] == ["BWBR0005537"] and c["expected_contains"] and c["should_refuse"] is False
    assert not any("4:13" in c["question"] for c in cases)


# --- verbruik en weigeringen per case -----------------------------------------------------------------

def test_een_qa_case_meldt_tokens_rondes_duur_en_waarom_het_sjabloon_weigerde(capsys, monkeypatch):
    """De duidingseval van 7 nov 2026 meldde geen kosten, en 14 keer 'sjabloon niet te vullen' zonder reden."""
    from types import SimpleNamespace

    from fakes import FakeGraph, FakeLLM
    from test_sjablonen import HAAL, KIES_DUIDING, TIEN_TSV, _sluit_af

    class GemetenLLM(FakeLLM):
        def _next(self):
            if getattr(self, "meter", None) is not None:
                self.meter.tel_response(SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                                                              cache_read_input_tokens=100)), ms=20)
            return super()._next()

    fout = _sluit_af("t2", van="Dit staat nergens", tot="in de wet.")
    llm = GemetenLLM([KIES_DUIDING, HAAL, fout, _sluit_af("t3")])
    # Live bouwt answer_stream het model zelf en hangt de meter eraan; met een nepmodel doet de test dat.
    from agent.models import Verbruiksmeter
    llm.meter = Verbruiksmeter()
    monkeypatch.setattr(run_eval, "Verbruiksmeter", lambda: llm.meter)
    case = {"id": "d", "question": "Hoe werkt uitstel?", "vraagtype": "duiding", "expected_sources": [], "expected_contains": [],
            "should_refuse": False}
    [r] = asyncio.run(run_eval.run_suite([case], settings=make_settings(enable_planning=True), llm=llm,
                                         graph=FakeGraph(result=TIEN_TSV)))
    assert r.verbruik["modelrondes"] == 4 and r.verbruik["uitvoer"] == 20 and r.verbruik["cache_lees"] == 400
    assert r.verbruik["duur_ms"] >= 0
    [w] = r.weigeringen
    assert "staat niet in" in w
    run_eval.print_report([r])
    uit = capsys.readouterr().out
    assert "weigering: " in uit and "Verbruik over 1 cases: invoer 40, cache_lees 400" in uit.replace(".", "")
    assert "1 weigeringen van het sjabloon" in uit


def test_een_opname_zonder_verbruik_blijft_te_herscoren():
    """Een bewaarde opname van vóór deze velden: het rapport toont een streep, geen fout."""
    opname = nieuwe_opname("v", "feit")
    del opname["verbruik"], opname["weigeringen"]
    r = score_opname({"question": "v", "expected_sources": [], "expected_contains": [], "should_refuse": False}, opname)
    assert r.verbruik is None and r.weigeringen == []
    run_eval.print_report([r])
