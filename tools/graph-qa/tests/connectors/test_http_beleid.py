"""Het gedeelde herhaalbeleid (`agent/adapters/http_beleid.py`): welke status tijdelijk is, declareert de adapter per
host; blijft een tijdelijke status, dan is het een storing, en alleen een status die de adapter niet als tijdelijk kent
is een geweigerd verzoek (Rechtspraak ronde 4, R08: drie keer een 400 van LiDO heette "weigerde het verzoek")."""
from __future__ import annotations

import logging

import httpx
import pytest

from agent.adapters import http_beleid as H
from agent.adapters import lido_rechtspraak as L
from agent.adapters.sru_bwb import BwbFout, SruBwb
from agent.adapters.sru_kamerstukken import KamerstukFout, SruKamerstukken
from agent.tools import bekendmaking_tools, kamerstuk_tools, wetgeving_tools

LOG = logging.getLogger("test")


@pytest.fixture(autouse=True)
def _geen_wachttijd(monkeypatch):
    monkeypatch.setattr(H, "HERHAAL_S", 0)
    monkeypatch.setattr(L, "HERHAAL_S", 0)
    monkeypatch.setattr(L, "PER_SECONDE", 10**9)


def _reeks(statussen: list[int], body: bytes = b"ok"):
    gezien: list[int] = []
    rest = list(statussen)

    def dienst(_r: httpx.Request) -> httpx.Response:
        status = rest.pop(0) if rest else 200
        gezien.append(status)
        return httpx.Response(status, content=body if status < 400 else b"")
    return dienst, gezien


@pytest.mark.parametrize("beleid,status,code", [
    (H.STANDAARD, 500, "onbereikbaar"), (H.STANDAARD, 503, "onbereikbaar"), (H.STANDAARD, 429, "bezet"),
    (H.STANDAARD, 400, "verzoek_geweigerd"), (H.STANDAARD, 403, "verzoek_geweigerd"), (H.STANDAARD, 404, "niet_gevonden"),
    (H.Statusbeleid(frozenset({400})), 400, "onbereikbaar"), (H.Statusbeleid(frozenset({400})), 403, "verzoek_geweigerd"),
])
def test_de_code_volgt_het_beleid_van_de_bron(beleid, status, code):
    assert beleid.foutcode(status) == code


def test_een_tijdelijke_status_gaat_opnieuw_een_definitieve_niet():
    dienst, gezien = _reeks([503, 503])
    client = httpx.Client(transport=httpx.MockTransport(dienst))
    r = H.met_herhaling(lambda: client.get("https://x/"), beleid=H.STANDAARD, host="x", slaap=lambda _s: None,
                        logger=LOG, gebeurtenis="t")
    assert r.status_code == 200 and gezien == [503, 503, 200]
    dienst, gezien = _reeks([400])
    client = httpx.Client(transport=httpx.MockTransport(dienst))
    r = H.met_herhaling(lambda: client.get("https://x/"), beleid=H.STANDAARD, host="x", slaap=lambda _s: None,
                        logger=LOG, gebeurtenis="t")
    assert r.status_code == 400 and gezien == [400]


def test_elke_adapter_declareert_zijn_tijdelijke_statussen():
    """De vorm, niet een lijst: LiDO kent de 400 als hik; de andere bronnen volgen het standaardbeleid."""
    assert L.BELEID["linkeddata.overheid.nl"].is_tijdelijk(400)
    assert not L.BELEID.get("data.rechtspraak.nl", H.STANDAARD).is_tijdelijk(400)


def test_een_blijvende_400_van_lido_is_een_storing_geen_geweigerde_vraag():
    dienst, gezien = _reeks([400, 400, 400])
    bron = L.LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    with pytest.raises(L.RechtspraakFout) as exc:
        bron._get(f"{L.LIDO_URL}/get-id", **{"juriconnect-ref": "BWBR0004770&artikel=9"})
    assert exc.value.code == "onbereikbaar" and gezien == [400, 400, 400]


def test_een_400_van_de_rechtspraak_blijft_een_geweigerd_verzoek():
    dienst, gezien = _reeks([400])
    bron = L.LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    with pytest.raises(L.RechtspraakFout) as exc:
        bron._get(L.RECHTSPRAAK_URL, id="ECLI:NL:HR:2023:563")
    assert exc.value.code == "verzoek_geweigerd" and gezien == [400]


def test_koop_herhaalt_een_storing_en_noemt_een_4xx_geen_storing():
    """De KOOP-adapter noemde elke 4xx "niet bereikbaar" en herhaalde niets."""
    dienst, gezien = _reeks([503, 503], body=b"<x/>")
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    assert bron._get(bron._url, query="x") == b"<x/>" and gezien == [503, 503, 200]
    dienst, _ = _reeks([400])
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    with pytest.raises(KamerstukFout) as exc:
        bron._get(bron._url, query="x")
    assert exc.value.code == "verzoek_geweigerd"


def test_de_bwb_zoekdienst_volgt_hetzelfde_beleid():
    dienst, gezien = _reeks([502, 502, 502])
    bron = SruBwb(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    with pytest.raises(BwbFout) as exc:
        bron._get(bron._url, params={"query": "x"})
    assert exc.value.code == "onbereikbaar" and gezien == [502, 502, 502]
    dienst, _ = _reeks([403])
    bron = SruBwb(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    with pytest.raises(BwbFout) as exc:
        bron._get(bron._url, params={"query": "x"})
    assert exc.value.code == "verzoek_geweigerd"


@pytest.mark.parametrize("module", [wetgeving_tools, kamerstuk_tools, bekendmaking_tools])
def test_elke_code_van_het_beleid_heeft_een_reden_in_de_tools(module):
    for code in ("onbereikbaar", "bezet", "verzoek_geweigerd", "niet_gevonden"):
        assert code in module.FOUTREDEN, (module.__name__, code)
    assert module.FOUTREDEN["bezet"] == "bron_bezet" and module.FOUTREDEN["verzoek_geweigerd"] == "zoekvraag_geweigerd"
