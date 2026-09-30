"""Classificatiebatches parallel: zelfde uitkomst, zelfde volgorde, opgetelde meting, korter.

Vier batches na elkaar kostten een beurt een minuut (4 × ~15 s). Dit toetst de samenvoeging zelf,
met een nep-`classificeer` – de modelaanroep is niet wat hier getest wordt.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from agent.jas_pipeline import keten


def _nep_classificeer(vertraging: float, gezien: list[str]):
    slot = threading.Lock()

    def classificeer(llm, model, batch, corpus, temperature, meting, *, spankeuze=False, context=""):
        time.sleep(vertraging)
        with slot:
            gezien.append(threading.current_thread().name)
        meting["llm_calls"] = meting.get("llm_calls", 0) + 1
        if batch[0] == "b2":
            meting["afgekapt"] = meting.get("afgekapt", 0) + 1
        return [f"beslissing-{k}" for k in batch]
    return classificeer


def _settings(parallel: int):
    return SimpleNamespace(classifier_parallel=parallel, classifier_temperature=None, classifier_spankeuze=False)


BATCHES = [["b1", "b1x"], ["b2"], ["b3"], ["b4"]]


def test_parallel_en_na_elkaar_geven_dezelfde_beslissingen_in_batchvolgorde(monkeypatch):
    uitkomsten = {}
    for parallel in (1, 4):
        monkeypatch.setattr(keten, "classificeer", _nep_classificeer(0.01, []))
        meting = {"llm_calls": 0}
        uitkomsten[parallel] = (keten._classificeer_batches(BATCHES, None, "nep", "corpus", _settings(parallel), meting, ""),
                                meting)
    assert uitkomsten[1][0] == uitkomsten[4][0] == [
        "beslissing-b1", "beslissing-b1x", "beslissing-b2", "beslissing-b3", "beslissing-b4"]
    for parallel, (_, meting) in uitkomsten.items():
        assert meting["llm_calls"] == 4 and meting["afgekapt"] == 1
        assert meting["classifier_parallel"] == parallel


def test_parallel_is_sneller_en_draait_echt_op_meerdere_threads(monkeypatch):
    gezien: list[str] = []
    monkeypatch.setattr(keten, "classificeer", _nep_classificeer(0.3, gezien))
    begin = time.monotonic()
    keten._classificeer_batches(BATCHES, None, "nep", "corpus", _settings(4), {"llm_calls": 0}, "")
    duur = time.monotonic() - begin
    assert duur < 0.9, f"vier batches van 0,3 s duurden {duur:.2f} s – dat is na elkaar"
    assert len(set(gezien)) > 1


def test_niet_meer_threads_dan_batches_en_minstens_een(monkeypatch):
    monkeypatch.setattr(keten, "classificeer", _nep_classificeer(0, []))
    meting = {"llm_calls": 0}
    keten._classificeer_batches([["b1"]], None, "nep", "", _settings(4), meting, "")
    assert meting["classifier_parallel"] == 1
    meting = {"llm_calls": 0}
    assert keten._classificeer_batches([], None, "nep", "", _settings(4), meting, "") == []
    assert meting["classifier_parallel"] == 1


def test_instelling_komt_uit_de_omgeving():
    from agent.config import Settings

    assert Settings().classifier_parallel == 4
    assert Settings.from_env({"CLASSIFIER_PARALLEL": "1"}).classifier_parallel == 1
