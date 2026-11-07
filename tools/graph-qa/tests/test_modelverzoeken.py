"""Elk modelverzoek ligt vast, byte voor byte (H5a).

H5 brengt alle modelaanroepen onder één gedeelde stap (`agent/llm_stap.py`). Die verbouwing mag niets veranderen aan
wat het model krijgt: een ander verzoek is een andere prompt, een andere promptversie, een ongeldige replay in
`eval/invordering_proef.py` en een eval-uitkomst die niet meer vergelijkbaar is. Deze test legt per aanroepplek, voor
vaste invoer, de volledige kwargs vast (model, max_tokens, system, tools, messages, tool_choice, temperature en de
streamvlaggen), en het aantal aanroepen. Hij draait zonder model en zonder graaf.

Wijkt een verzoek af, dan is dat een promptwijziging: bewust, met een meting, in een eigen PR. Alleen dan leg je opnieuw
vast:

    GRAPHQA_VERZOEKEN_VASTLEGGEN=1 uv run --extra dev pytest tests/test_modelverzoeken.py

Decompositie staat er bewust niet in: die keten is hard uit en verdwijnt met H6.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from agent import deelvragen as dv
from agent import werkgebied_intake as wi
from agent.begrippen_pipeline import classificatie as begrip_classificatie
from agent.begrippen_pipeline import kaart as kaart_mod
from agent.begrippen_pipeline import kaartacties as ka
from agent.begrippen_pipeline import keten as begrip_keten
from agent.begrippen_pipeline import verdieping
from agent.begrippen_pipeline.model import Bron, Formulering, Manifest
from agent.jas_pipeline import classificatie as jas_classificatie
from agent.jas_pipeline.taal.provider import NullProvider
from bron_fakes import answer_stream
from fakes import FakeGraph, _FakeStream, make_settings, response, text_block, tool_block

MAP = Path(__file__).parent / "data" / "modelverzoeken"
VASTLEGGEN = os.environ.get("GRAPHQA_VERZOEKEN_VASTLEGGEN") == "1"


class Opnemer:
    """Legt elke aanroep vast zoals hij binnenkomt, en speelt eerst `script` af, daarna `rest(kwargs)`."""

    def __init__(self, script: list[Any] | None = None,
                 rest: Callable[[dict[str, Any]], Any] | None = None) -> None:
        # `_responses` (en niet een eigen naam): `bron_fakes.answer_stream` leest het annotatiedoel daaruit.
        self._responses = list(script or [])
        self._volgende = 0
        self.rest = rest or (lambda _kw: response([text_block("Ik roep geen tool aan.")], "end_turn"))
        self.calls: list[dict[str, Any]] = []

    def _antwoord(self, kw: dict[str, Any]) -> Any:
        if self._volgende < len(self._responses):
            self._volgende += 1
            return self._responses[self._volgende - 1]
        return self.rest(kw)

    def create(self, **kw: Any) -> Any:
        self.calls.append({"methode": "create", "verzoek": kw})
        return self._antwoord(kw)

    def stream(self, **kw: Any) -> _FakeStream:
        self.calls.append({"methode": "stream", "verzoek": kw})
        return _FakeStream(self._antwoord(kw))


def _vorm(waarde: Any) -> Any:
    """JSON-vorm van een verzoek. Een object zonder JSON-vorm faalt: een repr met een adres is niet stabiel."""
    if isinstance(waarde, dict):
        return {str(k): _vorm(v) for k, v in waarde.items()}
    if isinstance(waarde, (list, tuple)):
        return [_vorm(v) for v in waarde]
    if isinstance(waarde, SimpleNamespace):
        return {"__ns__": _vorm(vars(waarde))}
    if waarde is None or isinstance(waarde, (str, int, float, bool)):
        return waarde
    raise TypeError(f"geen vaste vorm voor {type(waarde).__name__} in een modelverzoek")


def _tekst(calls: list[dict[str, Any]]) -> str:
    return json.dumps(_vorm(calls), ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def _vergelijk(naam: str, calls: list[dict[str, Any]]) -> None:
    assert calls, f"{naam}: er is geen enkel model aangeroepen"
    pad = MAP / f"{naam}.json"
    tekst = _tekst(calls)
    if VASTLEGGEN:
        MAP.mkdir(parents=True, exist_ok=True)
        pad.write_text(tekst, encoding="utf-8")
        return
    assert pad.exists(), f"{pad.name} ontbreekt; leg vast met GRAPHQA_VERZOEKEN_VASTLEGGEN=1"
    verwacht = pad.read_text(encoding="utf-8")
    if tekst != verwacht:
        oud, nieuw = json.loads(verwacht), json.loads(tekst)
        assert len(nieuw) == len(oud), f"{naam}: {len(nieuw)} aanroepen in plaats van {len(oud)}"
        for i, (o, n) in enumerate(zip(oud, nieuw)):
            for sleutel in sorted(set(o["verzoek"]) | set(n["verzoek"])):
                assert n["verzoek"].get(sleutel) == o["verzoek"].get(sleutel), \
                    f"{naam}: aanroep {i + 1} wijkt af in '{sleutel}'"
            assert n == o, f"{naam}: aanroep {i + 1} wijkt af"
        pytest.fail(f"{naam}: het verzoek wijkt af in de opmaak")


def _draai(gen) -> list[dict[str, Any]]:
    async def verzamel():
        return [e async for e in gen]
    return asyncio.run(verzamel())


# --- de antwoordroute: supervisor en specialist ------------------------------------------------

ART9 = "urn:bwb:BWBR0004770:artikel:9"


def test_supervisor_en_antwoordlus():
    llm = Opnemer([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: haal artikel 9 op")], "end_turn"),
        response([text_block("Ik haal het artikel op."),
                  tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block("Artikel 9 gaat over uitstel van betaling.")], "end_turn"),
    ])
    graaf = FakeGraph(result=f'?lid\t?tekst\n<{ART9}:lid:1>\t"De ontvanger verleent uitstel."@nl\n')
    _draai(answer_stream("Wat betekent artikel 9 van de Invorderingswet 1990 voor een belastingschuldige?",
                         settings=make_settings(grounding_correct=False),
                         llm=llm, graph=graaf))
    # Supervisor, en twee rondes van de lus: de tweede draagt het toolresultaat in de historie.
    assert [c["methode"] for c in llm.calls] == ["create", "stream", "stream"]
    _vergelijk("antwoord", llm.calls)


# --- de annotatieketen: supervisor, ophaal-agent, classifier en reviewer -----------------------

LID = "De ontvanger verleent binnen zes weken uitstel van betaling, indien de belastingplichtige daarom verzoekt."
LID_TSV = json.dumps(f'?nummer\t?tekst\t?jci\n"1"\t"{LID}"@nl\t"jci"')
DOEL_JSON = '{"bwbId":"BWBR0004770","artikel":"9","lid":"1","nummer":"","citeertitel":"IW 1990"}'


def _aanloop() -> list[Any]:
    return [
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block(DOEL_JSON)], "end_turn"),
    ]


def test_annotatieketen_met_classifier_en_reviewer():
    """Zonder tool-aanroep: twee classifierpogingen en daarna de reviewer, dus alle vier de rollen."""
    llm = Opnemer(_aanloop())
    _draai(answer_stream("annoteer artikel 9 lid 1 van de Invorderingswet 1990",
                         settings=make_settings(taal_provider="null"), llm=llm, graph=FakeGraph(result=LID_TSV)))
    namen = [(c["verzoek"].get("tools") or [{}])[0].get("name") for c in llm.calls]
    assert namen.count(jas_classificatie.TOOL) == 2 and "beoordeel" in namen
    _vergelijk("annotatieketen", llm.calls)


# --- de begrippenketen: twijfelparen en de concept-kaart ---------------------------------------

A = "De ontvanger verzendt de aanslag binnen zes weken. Daarna volgt de betaling."
B = "Tegen de aanslag kan bezwaar worden gemaakt; de inspecteur beslist."
I1, I2 = "urn:bwb:BWBR1:artikel:1", "urn:bwb:BWBR2:artikel:4"


def _h(t: str) -> str:
    import hashlib
    return hashlib.sha256(t.encode()).hexdigest()


def _f(eid: str, iri: str, tekst: str, deel: str, klasse: str = "Rechtsobject") -> Formulering:
    s = tekst.index(deel)
    return Formulering(element_id=eid, bron_iri=iri, start=s, eind=s + len(deel), tekst=deel, jas_klasse=klasse)


BEGRIP_MANIFEST = Manifest(
    bronnen=(Bron(bron_iri=I1, tekst=A, bron_hash=_h(A), label="art. 1 X", regeling="BWBR1"),
             Bron(bron_iri=I2, tekst=B, bron_hash=_h(B), label="art. 4 Y", regeling="BWBR2")),
    formuleringen=(_f("e1", I1, A, "de aanslag"), _f("e2", I2, B, "de aanslag"),
                   _f("e3", I1, A, "De ontvanger", "Rechtssubject")))


def test_begrippen_vergelijk_en_kaart():
    """Het twijfelpaar wordt `zelfde_betekenis`, zodat er een groep is en de kaart het model ook vraagt."""
    def rest(kw):
        naam = kw["tools"][0]["name"]
        if naam == begrip_classificatie.TOOL:
            paar = kw["tools"][0]["input_schema"]["properties"]["oordelen"]["items"]["properties"]["paar"]["enum"][0]
            return response([tool_block("t1", naam, {"oordelen": [
                {"paar": paar, "uitkomst": "zelfde_betekenis", "motivatie": "Zelfde aanslag."}]})], "tool_use")
        return response([text_block("Geen kaart.")], "end_turn")

    llm = Opnemer(rest=rest)
    uitkomst = begrip_keten.analyseer(BEGRIP_MANIFEST, NullProvider())
    verdieping.verdiep(BEGRIP_MANIFEST, uitkomst, llm, "m")
    namen = [c["verzoek"]["tools"][0]["name"] for c in llm.calls]
    assert namen == [begrip_classificatie.TOOL, kaart_mod.TOOL, kaart_mod.TOOL]
    _vergelijk("begrippen_verdieping", llm.calls)


# --- de kaartacties ----------------------------------------------------------------------------

IW = "urn:bwb:BWBR0004770"
KAART_ART9, KAART_DEF = f"{IW}:artikel:9:lid:1", f"{IW}:artikel:2:lid:1:o:m"
KA = "De ontvanger verzendt de belastingaanslag binnen zes weken. Daarna volgt de betaling."
KD = "belastingaanslag: de voorlopige aanslag en de aanslag;"
KAART_MANIFEST = Manifest(
    bronnen=(Bron(bron_iri=KAART_ART9, tekst=KA, bron_hash=_h(KA), label="Artikel 9 · Lid 1 – IW",
                  regeling="BWBR0004770"),
             Bron(bron_iri=KAART_DEF, tekst=KD, bron_hash=_h(KD), label="Artikel 2 · Lid 1 · m – IW",
                  aanhef="Deze wet verstaat onder:", regeling="BWBR0004770")),
    formuleringen=(_f("e1", KAART_ART9, KA, "belastingaanslag"),
                   _f("e2", KAART_ART9, KA, "De ontvanger", "Rechtssubject")))


def _kant(bid: str, naam: str, leden: list[str], **inhoud: Any) -> ka.Kant:
    return ka.kant_uit({"id": bid, "inhoud": {"naam": naam, **inhoud}, "leden": leden}, KAART_MANIFEST)


@pytest.mark.parametrize("actie", ["scherper", "verschil", "voorbeelden", "uitleg"])
def test_kaartacties(actie):
    llm = Opnemer()
    k = _kant("b1", "belastingaanslag", ["e1"], definitie="de voorlopige aanslag en de aanslag")
    if actie == "verschil":
        ka.verschil(llm, "m", KAART_MANIFEST, k, _kant("b2", "ontvanger", ["e2"]), {})
    else:
        getattr(ka, actie)(llm, "m", KAART_MANIFEST, k, {})
    _vergelijk(f"kaartactie_{actie}", llm.calls)


# --- de deelvragen-agent en de intake ----------------------------------------------------------

WERKGEBIED = {
    "id": "w1", "naam": "Uitstel van betaling",
    "analysevraag": "Wanneer krijgt een belastingschuldige uitstel van betaling?",
    "praktijkvoorbeeld": "Een ondernemer vraagt uitstel na een tegenvallend jaar.",
    "deelvragen": [{"id": "d1", "vraag": "Wie beslist over uitstel van betaling?"}],
}


def test_deelvragen_voorstellen():
    llm = Opnemer()
    dv.vraag_model(llm, "m", WERKGEBIED, {})
    _vergelijk("deelvragen_voorstellen", llm.calls)


def test_deelvraag_verbeteren():
    llm = Opnemer()
    dv.verbeter_model(llm, "m", WERKGEBIED, WERKGEBIED["deelvragen"][0], "splits", {})
    _vergelijk("deelvraag_verbeteren", llm.calls)


def test_intake_stelt_voor():
    llm = Opnemer()
    intake = {**wi.nieuwe_intake("ik wil een wetsanalyse over uitstel van betaling"),
              "antwoorden": {"naam": "Uitstel van betaling", "context": "Na de coronaregeling.",
                             "buiten": "betalingsregelingen"}}
    wi.stel_voor(llm, "router", intake)
    _vergelijk("intake", llm.calls)


# --- de hashes die de herkomst dragen -----------------------------------------------------------

def _hashes() -> dict[str, str]:
    uit = {
        "jas_classificatie": jas_classificatie.promptversie(False),
        "jas_classificatie_spankeuze": jas_classificatie.promptversie(True),
        "begrippen_classificatie": begrip_classificatie.promptversie(),
        "begrippen_kaart": kaart_mod.promptversie(),
    }
    for actie in ("scherper", "verschil", "voorbeelden", "uitleg"):
        uit[f"kaartactie_{actie}"] = ka.promptversie(actie)
    return uit


def test_promptversies_liggen_vast():
    pad = MAP / "promptversies.json"
    tekst = json.dumps(_hashes(), indent=1, sort_keys=True) + "\n"
    if VASTLEGGEN:
        MAP.mkdir(parents=True, exist_ok=True)
        pad.write_text(tekst, encoding="utf-8")
        return
    assert json.loads(pad.read_text(encoding="utf-8")) == _hashes()
