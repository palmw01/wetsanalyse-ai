"""Tests voor de FastAPI-service: legacy-vorm, batch, fouten, API-key.

``run_import``/``run_imports`` worden gemonkeypatcht – geen netwerk/GraphDB.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

import app.service as service
from app.models import ImportResult, ImportSummary


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("BWB_SERVICE_API_KEY", raising=False)
    with TestClient(service.app) as test_client:
        yield test_client


def _summary(bwb_id: str) -> ImportSummary:
    return ImportSummary(bwb_id=bwb_id, wetten=1, artikelen=2)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_enkele_import_behoudt_legacy_vorm(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(service, "run_import", lambda bwb_id, settings: _summary(bwb_id))
    resp = client.post("/import", json={"bwb_id": "BWBR0000001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["overzicht"]["bwb_id"] == "BWBR0000001"
    assert "resultaten" not in body


def test_enkele_import_fout_geeft_500(client: TestClient, monkeypatch) -> None:
    def faal(bwb_id, settings):
        raise RuntimeError("boem")

    monkeypatch.setattr(service, "run_import", faal)
    resp = client.post("/import", json={"bwb_id": "BWBR0000001"})
    assert resp.status_code == 500
    assert "boem" in resp.json()["detail"]


def test_batch_import_happy_path(client: TestClient, monkeypatch) -> None:
    def batch(bwb_ids, settings):
        return [ImportResult(bwb_id=b, ok=True, overzicht=_summary(b)) for b in bwb_ids]

    monkeypatch.setattr(service, "run_imports", batch)
    resp = client.post("/import", json={"bwb_ids": ["BWBR0000001", "BWBR0000002"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [r["bwb_id"] for r in body["resultaten"]] == ["BWBR0000001", "BWBR0000002"]
    assert all(r["status"] == "ok" for r in body["resultaten"])


def test_batch_import_gedeeltelijke_fout(client: TestClient, monkeypatch) -> None:
    def batch(bwb_ids, settings):
        return [
            ImportResult(bwb_id="BWBR0000001", ok=True, overzicht=_summary("BWBR0000001")),
            ImportResult(bwb_id="BWBR9999999", ok=False, fout="niet gevonden"),
        ]

    monkeypatch.setattr(service, "run_imports", batch)
    resp = client.post("/import", json={"bwb_ids": ["BWBR0000001", "BWBR9999999"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "gedeeltelijk"
    fout = body["resultaten"][1]
    assert fout["status"] == "fout"
    assert fout["fout"] == "niet gevonden"
    assert fout["overzicht"] is None


def test_batch_import_alles_mislukt(client: TestClient, monkeypatch) -> None:
    def batch(bwb_ids, settings):
        return [ImportResult(bwb_id=b, ok=False, fout="x") for b in bwb_ids]

    monkeypatch.setattr(service, "run_imports", batch)
    resp = client.post("/import", json={"bwb_ids": ["BWBR0000001"]})
    assert resp.json()["status"] == "mislukt"


def test_lege_bwb_ids_geeft_422(client: TestClient) -> None:
    assert client.post("/import", json={"bwb_ids": []}).status_code == 422


def test_api_key_vereist_indien_geconfigureerd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BWB_SERVICE_API_KEY", "geheim")
    with TestClient(service.app) as client_met_key:
        assert client_met_key.post("/import", json={"bwb_id": "X"}).status_code == 401
        monkeypatch.setattr(service, "run_import", lambda bwb_id, settings: _summary(bwb_id))
        resp = client_met_key.post("/import", json={"bwb_id": "X"}, headers={"X-API-Key": "geheim"})
        assert resp.status_code == 200


def _nep_fasen(monkeypatch, *, stuk_bij_verzamelen=(), stuk_bij_schrijven=()):
    """Vervang de twee fasen van `run_imports` door fakes, zonder netwerk of GraphDB."""
    import app.main as main_module
    from app.collect import Batch

    monkeypatch.setattr(main_module, "maak_writer", lambda settings: object())
    monkeypatch.setattr(main_module, "prepare", lambda writer: None)

    def nep_verzamel(bwb_id, settings):
        if bwb_id in stuk_bij_verzamelen:
            raise RuntimeError("kapot bij verzamelen")
        return SimpleNamespace(
            wet=SimpleNamespace(bwb_id=bwb_id), wti=None, batch=Batch(),
            summary=_summary(bwb_id), xml_path=None,
        )

    def nep_schrijf(item, writer, index):
        if item.wet.bwb_id in stuk_bij_schrijven:
            raise RuntimeError("kapot bij schrijven")
        return item.summary

    monkeypatch.setattr(main_module, "_verzamel", nep_verzamel)
    monkeypatch.setattr(main_module, "_schrijf", nep_schrijf)
    return main_module


def test_run_imports_loopt_door_na_fout_bij_schrijven(monkeypatch: pytest.MonkeyPatch) -> None:
    """De batch-runner vangt per wet exceptions en gaat verder."""
    main_module = _nep_fasen(monkeypatch, stuk_bij_schrijven={"SLECHT"})
    resultaten = main_module.run_imports(["GOED", "SLECHT", "OOK_GOED"], settings=None)
    assert [r.ok for r in resultaten] == [True, False, True]
    assert resultaten[1].fout == "kapot bij schrijven"


def test_run_imports_loopt_door_na_fout_bij_verzamelen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sinds de fasesplitsing kan een wet ook in fase 1 sneuvelen (download/XSD/parse).

    Die valt dan uit de structuurindex, en de rest van de batch hoort gewoon door te lopen — met
    dezelfde per-wet-foutrapportage als voorheen. Zonder deze test zou een fout in de nieuwe fase
    de hele run kunnen meeslepen zonder dat iets dat opmerkt.
    """
    main_module = _nep_fasen(monkeypatch, stuk_bij_verzamelen={"SLECHT"})
    resultaten = main_module.run_imports(["GOED", "SLECHT", "OOK_GOED"], settings=None)
    assert [r.ok for r in resultaten] == [True, False, True]
    assert resultaten[1].fout == "kapot bij verzamelen"


def test_run_imports_houdt_de_opgegeven_volgorde_aan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fase 2 loopt over de geslaagde verzamelingen; het overzicht volgt de invoervolgorde."""
    main_module = _nep_fasen(monkeypatch, stuk_bij_verzamelen={"B"})
    resultaten = main_module.run_imports(["A", "B", "C"], settings=None)
    assert [r.bwb_id for r in resultaten] == ["A", "B", "C"]
