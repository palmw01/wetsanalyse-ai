"""Tokenverbruik: de meter telt wat de provider terugmeldt, en de beurt boekt het.

De meter zit in de LLM-adapter en het boeken in de beurt-driver. Wat hier wordt vastgelegd:
elke call telt mee (ook de retry zonder caching), streams tellen via `final_message()`, en een
beurt die mislukt boekt zijn verbruik alsnog — die tokens zijn wél verbruikt.
"""
from __future__ import annotations

import asyncio
import functools
from types import SimpleNamespace

import pytest

from agent.models import Verbruiksmeter


def asyncio_test(fn):
    """Huispatroon in deze suite: async tests draaien via asyncio.run (geen pytest-asyncio)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


def _usage(invoer=0, uitvoer=0, cache_lees=0, cache_schrijf=0):
    return SimpleNamespace(
        input_tokens=invoer,
        output_tokens=uitvoer,
        cache_read_input_tokens=cache_lees,
        cache_creation_input_tokens=cache_schrijf,
    )


# --- de meter -------------------------------------------------------------------

def test_meter_telt_alle_vier_de_soorten():
    m = Verbruiksmeter()
    m.tel_response(SimpleNamespace(usage=_usage(100, 50, 200, 25)))
    assert (m.invoer, m.uitvoer, m.cache_lees, m.cache_schrijf) == (100, 50, 200, 25)
    # Het budget rekent met het volle promptvolume: caching verlaagt de factuur, niet het gebruik.
    assert m.totaal == 375
    assert m.calls == 1


def test_meter_telt_meerdere_calls_op():
    m = Verbruiksmeter()
    for _ in range(3):
        m.tel_response(SimpleNamespace(usage=_usage(10, 5)))
    assert m.totaal == 45 and m.calls == 3


def test_meter_negeert_antwoord_zonder_usage():
    """De test-fakes geven een response zonder `usage`; dat mag niet omvallen."""
    m = Verbruiksmeter()
    m.tel_response(SimpleNamespace(content=[], stop_reason="end_turn"))
    assert m.totaal == 0 and m.calls == 0


def test_meter_negeert_ontbrekende_velden():
    m = Verbruiksmeter()
    m.tel_response(SimpleNamespace(usage=SimpleNamespace(input_tokens=7)))
    assert m.invoer == 7 and m.uitvoer == 0 and m.totaal == 7


def test_als_dict_is_het_api_contract():
    m = Verbruiksmeter()
    m.tel_response(SimpleNamespace(usage=_usage(1, 2, 3, 4)))
    assert m.als_dict() == {
        "invoer": 1, "uitvoer": 2, "cache_lees": 3, "cache_schrijf": 4, "calls": 1,
    }


# --- de adapter telt bij elke call ---------------------------------------------

class _NepMessages:
    """Minimale nabootsing van `client.messages`, inclusief de streamende variant."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.aantal_creates = 0

    def create(self, **_kw):
        self.aantal_creates += 1
        return self._responses.pop(0)

    def stream(self, **_kw):
        resp = self._responses.pop(0)

        class _Ctx:
            def __enter__(self):
                return SimpleNamespace(
                    text_stream=iter(["hoi"]),
                    get_final_message=lambda: resp,
                )

            def __exit__(self, *_a):
                return False

        return _Ctx()


def _adapter(responses):
    from agent.adapters.anthropic_llm import AnthropicLLM
    from tests.fakes import make_settings

    llm = AnthropicLLM.__new__(AnthropicLLM)  # geen echte client/API-key nodig
    llm._caching = False
    llm.meter = Verbruiksmeter()
    llm._client = SimpleNamespace(messages=_NepMessages(responses))
    assert make_settings is not None
    return llm


def test_adapter_telt_bij_create():
    llm = _adapter([SimpleNamespace(usage=_usage(30, 10), content=[], stop_reason="end_turn")])
    llm.create(model="m", max_tokens=10, system="s", tools=[], messages=[])
    assert llm.meter.totaal == 40


def test_adapter_telt_bij_stream():
    """Bij een stream komt het usage-blok pas met `final_message()` binnen."""
    llm = _adapter([SimpleNamespace(usage=_usage(20, 5), content=[], stop_reason="end_turn")])
    with llm.stream(model="m", max_tokens=10, system="s", tools=[], messages=[]) as stream:
        list(stream.text_deltas)
        stream.final_message()
    assert llm.meter.totaal == 25


# --- boeken bij de api ----------------------------------------------------------

class _NepApi:
    def __init__(self):
        self.geboekt: list[dict] = []
        self.gesloten = False

    async def boek_verbruik(self, verbruik, *, model="", gesprek_id="", run_id=""):
        self.geboekt.append(
            {"verbruik": verbruik, "model": model, "gesprek_id": gesprek_id, "run_id": run_id}
        )
        return {"geboekt": True}

    async def aclose(self):
        self.gesloten = True


@pytest.fixture
def nep_api(monkeypatch):
    api = _NepApi()
    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *a, **kw: api)
    return api


def _settings():
    from tests.fakes import make_settings

    return make_settings(
        wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", llm_model="claude-test",
    )


async def _stroom(events):
    for e in events:
        yield e


@asyncio_test
async def test_beurt_boekt_het_verbruik(nep_api):
    from agent.beurt import voer_beurt_uit

    meter = Verbruiksmeter()
    meter.tel_response(SimpleNamespace(usage=_usage(100, 50)))
    run = SimpleNamespace(run_id="run-1", stop_gevraagd=False)

    events = [e async for e in voer_beurt_uit(
        _stroom([{"type": "token", "content": "hoi"}, {"type": "done"}]),
        settings=_settings(), run=run, gesprek_id="g1", user_id="u1", meter=meter,
    )]

    assert any(e["type"] == "token" for e in events)
    assert len(nep_api.geboekt) == 1
    geboekt = nep_api.geboekt[0]
    assert geboekt["verbruik"]["invoer"] == 100 and geboekt["verbruik"]["uitvoer"] == 50
    assert geboekt["run_id"] == "run-1" and geboekt["gesprek_id"] == "g1"
    assert nep_api.gesloten


@asyncio_test
async def test_beurt_boekt_ook_na_een_fout(nep_api):
    """De tokens zijn verbruikt, ook als de beurt halverwege stukloopt."""
    from agent.beurt import voer_beurt_uit

    meter = Verbruiksmeter()
    meter.tel_response(SimpleNamespace(usage=_usage(70, 30)))
    run = SimpleNamespace(run_id="run-2", stop_gevraagd=False)

    async def _knalt():
        yield {"type": "token", "content": "half"}
        raise RuntimeError("stuk")

    with pytest.raises(RuntimeError):
        async for _ in voer_beurt_uit(
            _knalt(), settings=_settings(), run=run, gesprek_id="g", user_id="u", meter=meter,
        ):
            pass

    assert len(nep_api.geboekt) == 1
    assert nep_api.geboekt[0]["verbruik"]["invoer"] == 70


@asyncio_test
async def test_lege_meter_boekt_niets(nep_api):
    from agent.beurt import voer_beurt_uit

    run = SimpleNamespace(run_id="run-3", stop_gevraagd=False)
    async for _ in voer_beurt_uit(
        _stroom([{"type": "done"}]),
        settings=_settings(), run=run, gesprek_id="g", user_id="u", meter=Verbruiksmeter(),
    ):
        pass
    assert nep_api.geboekt == []


@asyncio_test
async def test_zonder_gebruiker_boekt_niets(nep_api):
    """Zonder identiteit valt er niemand te belasten – dat is het `/v1/chat`-pad."""
    from agent.beurt import voer_beurt_uit

    meter = Verbruiksmeter()
    meter.tel_response(SimpleNamespace(usage=_usage(10, 10)))
    run = SimpleNamespace(run_id="run-4", stop_gevraagd=False)
    async for _ in voer_beurt_uit(
        _stroom([{"type": "done"}]),
        settings=_settings(), run=run, gesprek_id="g", user_id="", meter=meter,
    ):
        pass
    assert nep_api.geboekt == []


@asyncio_test
async def test_boekfout_laat_de_beurt_staan(monkeypatch):
    """Een hapering in de boekhouding mag geen fout opleveren die de jurist niets zegt."""
    from agent.beurt import voer_beurt_uit

    class _StukkeApi:
        async def boek_verbruik(self, *a, **kw):
            raise RuntimeError("api plat")

        async def aclose(self):
            pass

    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *a, **kw: _StukkeApi())
    meter = Verbruiksmeter()
    meter.tel_response(SimpleNamespace(usage=_usage(5, 5)))
    run = SimpleNamespace(run_id="run-5", stop_gevraagd=False)

    events = [e async for e in voer_beurt_uit(
        _stroom([{"type": "token", "content": "x"}, {"type": "done"}]),
        settings=_settings(), run=run, gesprek_id="g", user_id="u", meter=meter,
    )]
    assert any(e["type"] == "token" for e in events)
