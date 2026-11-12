"""Prompt-caching op het stabiele deel van de systeemprompt.

Caching is een **prefix-match**: de provider hasht de prompt tot aan het cache-punt, dus alles
ervóór moet byte-voor-byte gelijk zijn tussen calls. Daarom levert de orkestrator het systeemblok
gesplitst aan – identiteit en specialist (stabiel) vóór plan en geheugen-context (per beurt anders).
Zet je die volgorde om, dan is de cache stil waardeloos: geen fout, alleen de volle rekening.
"""
from __future__ import annotations

import asyncio
import json

import anthropic
import pytest

from agent.adapters.anthropic_llm import _MIN_CACHE_TEKENS, AnthropicLLM
from agent.agent import answer_stream
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block


def _adapter(**kw) -> AnthropicLLM:
    s = make_settings(azure_foundry_api_key="k", azure_foundry_base_url="https://x/anthropic", **kw)
    return AnthropicLLM(s)


LANG = "x" * _MIN_CACHE_TEKENS


def test_stabiel_deel_krijgt_het_cache_punt():
    blokken = _adapter()._system([LANG, "plan van deze beurt"])
    assert blokken[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert blokken[0]["text"] == LANG
    # Het variabele deel staat eráchter en draagt géén cache-punt – anders schrijft elke beurt een
    # eigen cache-entry die niemand ooit leest.
    assert blokken[1]["text"] == "plan van deze beurt"
    assert "cache_control" not in blokken[1]


def test_kort_systeemblok_wordt_niet_gecacht():
    """Onder het minimum slaat de provider de cache stilzwijgend over; dan alleen de write betalen
    is verlies."""
    uit = _adapter()._system(["kort", "variabel"])
    assert isinstance(uit, str) and uit == "kort\n\nvariabel"


def test_caching_uit_levert_een_kale_string():
    assert _adapter(prompt_caching=False)._system([LANG, "x"]) == f"{LANG}\n\nx"


def test_provider_die_cache_control_weigert_zet_caching_uit():
    """Caching is op Azure AI Foundry beta. Zou de provider het blok weigeren, dan faalt zónder deze
    terugval élke LLM-call – de prijs van caching mag nooit 'de dienst ligt plat' zijn."""
    llm = _adapter()
    fout = anthropic.BadRequestError(
        message="unexpected field cache_control",
        response=type("R", (), {"status_code": 400, "headers": {}, "request": None})(),
        body=None,
    )
    assert llm._zonder_caching(fout) is True
    assert isinstance(llm._system([LANG, "x"]), str), "na de weigering geen blokken meer"
    # Een fout die niets met caching te maken heeft laat de vlag met rust.
    llm2 = _adapter()
    anders = anthropic.BadRequestError(
        message="max_tokens too large",
        response=type("R", (), {"status_code": 400, "headers": {}, "request": None})(),
        body=None,
    )
    assert llm2._zonder_caching(anders) is False


def test_orkestrator_zet_het_variabele_deel_achter_het_stabiele():
    """De regressie die caching zinloos zou maken: plan/geheugen vóór de identiteit."""
    llm = FakeLLM([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: zoek art. 9 op")], "end_turn"),
        response([text_block("Artikel 9 gaat over de termijn.")], "end_turn"),
    ])
    _ = asyncio.run(_verzamel(answer_stream(
        "Waar gaat artikel 9 over?", settings=make_settings(), llm=llm, graph=FakeGraph(result=""),
    )))

    delen = llm.calls[1]["system_delen"]
    assert len(delen) == 2, "systeemblok hoort gesplitst te zijn in stabiel + variabel"
    assert delen[0].startswith("Je heet Lex"), "het stabiele deel begint bij de identiteit"
    assert "AANPAK" not in delen[0], "het plan van deze beurt hoort NIET vóór het cache-punt"
    assert "AANPAK" in delen[1]


async def _verzamel(gen):
    return [e async for e in gen]


class _Stream:
    def __init__(self, kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fout(tekst: str) -> anthropic.BadRequestError:
    return anthropic.BadRequestError(message=tekst, body=None,
                                     response=type("R", (), {"status_code": 400, "headers": {}, "request": None})())


def test_de_toollus_krijgt_een_cache_punt_op_de_historie_en_de_rest_niet():
    """F7: elke toolronde stuurt de hele historie opnieuw; alleen daar loont een cache-punt aan het eind."""
    llm = _adapter()
    gezien: list[dict] = []
    llm._client = type("C", (), {"messages": type("M", (), {
        "stream": staticmethod(lambda **kw: gezien.append(kw) or _Stream(kw))})()})()
    with llm.stream(model="m", max_tokens=1, system=[LANG, "x"], tools=[], messages=[], historie_cache=True):
        pass
    with llm.stream(model="m", max_tokens=1, system=[LANG, "x"], tools=[], messages=[]):
        pass
    assert gezien[0]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in gezien[1]


def test_weigert_de_provider_het_historie_punt_dan_blijft_de_systeemprompt_gecacht():
    llm = _adapter()
    pogingen: list[dict] = []

    class Weigerend(_Stream):
        def __enter__(self):
            if "cache_control" in self.kwargs:
                raise _fout("unexpected field cache_control")
            return self
    llm._client = type("C", (), {"messages": type("M", (), {
        "stream": staticmethod(lambda **kw: pogingen.append(kw) or Weigerend(kw))})()})()
    with llm.stream(model="m", max_tokens=1, system=[LANG, "x"], tools=[], messages=[], historie_cache=True):
        pass
    assert len(pogingen) == 2 and "cache_control" not in pogingen[1]
    assert isinstance(pogingen[1]["system"], list), "het cache-punt op de systeemprompt blijft"
    assert llm._caching and not llm._historie_caching


# --- De TTL (nulmeting context 12 nov 2026) --------------------------------------------------------------------------


def test_ttl_5m_is_de_standaard_van_de_provider():
    assert _adapter(prompt_cache_ttl="5m")._system([LANG, "x"])[0]["cache_control"] == {"type": "ephemeral"}


def test_een_losse_systeemstring_krijgt_geen_uur():
    """Een prompt zonder aangewezen stabiel deel komt meestal niet terug: schrijven voor een uur kost 2×."""
    assert _adapter()._system(LANG)[0]["cache_control"] == {"type": "ephemeral"}


def test_de_historie_houdt_vijf_minuten():
    """De API eist de langere TTL vóór de kortere: de systeemprompt een uur, het punt op de berichten de standaard."""
    llm = _adapter()
    gezien: list[dict] = []
    llm._client = type("C", (), {"messages": type("M", (), {
        "stream": staticmethod(lambda **kw: gezien.append(kw) or _Stream(kw))})()})()
    with llm.stream(model="m", max_tokens=1, system=[LANG, "x"], tools=[], messages=[], historie_cache=True):
        pass
    assert gezien[0]["system"][0]["cache_control"]["ttl"] == "1h"
    assert gezien[0]["cache_control"] == {"type": "ephemeral"}


def test_weigert_de_provider_de_ttl_dan_blijft_het_cachepunt_met_5_minuten():
    llm = _adapter()
    pogingen: list[dict] = []

    class Weigerend(_Stream):
        def __enter__(self):
            if self.kwargs["system"][0]["cache_control"].get("ttl"):
                raise _fout("system.0.cache_control.ttl: Extra inputs are not permitted")
            return self
    llm._client = type("C", (), {"messages": type("M", (), {
        "stream": staticmethod(lambda **kw: pogingen.append(kw) or Weigerend(kw))})()})()
    with llm.stream(model="m", max_tokens=1, system=[LANG, "x"], tools=[], messages=[], historie_cache=True):
        pass
    assert len(pogingen) == 2 and pogingen[1]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert llm._caching and llm._historie_caching, "caching blijft aan, ook op de historie"
