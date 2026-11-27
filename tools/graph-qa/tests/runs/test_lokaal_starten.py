"""`uv run graph-qa` luistert standaard alleen op deze machine (SonarQube S8392); `HOST` en `PORT` sturen het."""
from __future__ import annotations

import sys
import types

import pytest

from api import main


@pytest.fixture
def uvicorn_run(monkeypatch):
    aanroepen = []
    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=lambda *a, **kw: aanroepen.append(kw)))
    return aanroepen


def test_standaard_alleen_localhost(monkeypatch, uvicorn_run):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    main.run()
    assert (uvicorn_run[0]["host"], uvicorn_run[0]["port"]) == ("127.0.0.1", 8080)


def test_host_en_port_uit_de_omgeving(monkeypatch, uvicorn_run):
    monkeypatch.setenv("HOST", "0.0.0.0")  # noqa: S104 – de test zet het zelf
    monkeypatch.setenv("PORT", "9000")
    main.run()
    assert (uvicorn_run[0]["host"], uvicorn_run[0]["port"]) == ("0.0.0.0", 9000)  # noqa: S104
