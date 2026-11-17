"""Het taalmodel laadt één keer, ook als de opwarmthread en een beurt tegelijk beginnen."""
from __future__ import annotations

import sys
import threading
import time
from types import SimpleNamespace

from agent.jas_pipeline.taal.provider import NullProvider, SpacyProvider


def test_gelijktijdig_laden_laadt_het_model_een_keer(monkeypatch):
    geladen = []

    def load(naam, exclude=()):
        time.sleep(0.2)
        geladen.append(naam)
        return SimpleNamespace(meta={"version": "9.9"})

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(load=load))
    p = SpacyProvider("nep_model")
    draden = [threading.Thread(target=p.warm_op) for _ in range(4)]
    for d in draden:
        d.start()
    for d in draden:
        d.join()
    assert geladen == ["nep_model"]
    assert p.model == "nep_model-9.9"


def test_warm_taalmodel_op_verdraagt_een_provider_zonder_model():
    from agent.jas_pipeline.keten import warm_taalmodel_op

    warm_taalmodel_op("null")  # NullProvider heeft niets op te warmen en mag niet gooien
    assert not hasattr(NullProvider(), "warm_op")
