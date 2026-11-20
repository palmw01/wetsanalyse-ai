"""Het importscript van R4 (`scripts/importeer_regels_termijnen.py`): elk verzoek past in het contract van de api, de
id's uit het verslag worden opgelost of de import stopt, en een tweede run maakt niets."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from app.begrip_contracts import BegripInvoer
from app.open_punt_contracts import Besluit, OpenPuntAanmaak
from app.regel_contracts import ParameterWaardeInvoer, RegelAanmaak

_PAD = Path(__file__).resolve().parent.parent / "scripts" / "importeer_regels_termijnen.py"
_spec = importlib.util.spec_from_file_location("importeer_regels_termijnen", _PAD)
imp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = imp     # een dataclass zoekt zijn module op
_spec.loader.exec_module(imp)

WID = "wg-termijnen"


def _korte_ids() -> tuple[set[str], set[str]]:
    tekst = repr((imp.REGELS, imp.OPEN_PUNTEN, imp.PARAMETERWAARDEN))
    return set(re.findall(r"'b:([0-9a-f]{8})'", tekst)), set(re.findall(r"'e:([0-9a-f]{12})'", tekst))


class NepBff:
    """De BFF-routes die het script gebruikt, in het geheugen."""

    def __init__(self, begrippen: list[str] | None = None, elementen: list[str] | None = None):
        b, e = _korte_ids()
        self.begrippen = [{"id": f"{k}-0000-4000-8000-000000000000", "inhoud": {"naam": k}, "status": "geaccordeerd"}
                          for k in (begrippen if begrippen is not None else sorted(b))]
        self.elementen = [{"id": f"{k}00000000000000000000"} for k in (elementen if elementen is not None else sorted(e))]
        self.regels: list[dict] = []
        self.punten: list[dict] = []
        self.waarden: list[dict] = []
        self.schrijven: list[tuple[str, str]] = []

    def __call__(self, methode: str, pad: str, body=None):
        wg = f"/api/werkgebieden/{WID}"
        if methode == "GET":
            return 200, {
                f"{wg}/begrippen": {"begrippen": self.begrippen},
                f"{wg}/elementen": {"elementen": self.elementen},
                f"{wg}/regels": {"regels": self.regels},
                f"{wg}/open-punten": {"open_punten": self.punten},
                f"{wg}/parameterwaarden": {"parameterwaarden": self.waarden},
            }[pad]
        self.schrijven.append((methode, pad))
        if pad == f"{wg}/begrippen":
            BegripInvoer.model_validate(body)
            nieuw = {"id": f"nieuw-begrip-{len(self.begrippen)}", "inhoud": body["inhoud"], "status": "concept"}
            self.begrippen.append(nieuw)
            return 201, nieuw
        if pad == f"{wg}/regels":
            RegelAanmaak.model_validate(body)
            nieuw = {"id": f"regel-{len(self.regels)}", **body}
            self.regels.append(nieuw)
            return 201, nieuw
        if pad == f"{wg}/open-punten":
            OpenPuntAanmaak.model_validate(body)
            ids = {r["id"] for r in self.regels}
            assert all(a["id"] in ids for a in body["inhoud"]["hangt_aan"]), "een aanhaking wijst naar een gemaakte regel"
            nieuw = {"id": f"punt-{len(self.punten)}", "status": "open", "revisie": 1, **body}
            self.punten.append(nieuw)
            return 201, nieuw
        if pad.endswith("/besluit"):
            Besluit.model_validate(body)
            punt = next(p for p in self.punten if pad == f"{wg}/open-punten/{p['id']}/besluit")
            assert body["gekozen"] in {x["label"] for x in punt["inhoud"]["lezingen"]}
            punt["status"] = "gekozen"
            return 200, punt
        if pad == f"{wg}/parameterwaarden":
            ParameterWaardeInvoer.model_validate(body)
            self.waarden.append(body)
            return 201, body
        raise AssertionError(f"onverwacht: {methode} {pad}")


def test_de_import_maakt_alles_een_keer():
    bff = NepBff()
    v = imp.importeer(bff, WID, uitvoeren=True, log=lambda _: None)
    assert len(bff.regels) == 8 and len(v.gemaakt["regel"]) == 8
    assert all(r["herkomst"] == "import" for r in bff.regels)
    assert len(bff.punten) == len(imp.OPEN_PUNTEN)
    keuzes = [p for p in imp.OPEN_PUNTEN if "keuze" in p]
    assert len(keuzes) == 7 and len(v.gemaakt["keuze"]) == 7
    assert all(p["herkomst"] == "import" for p in bff.punten)
    assert len(bff.waarden) == 3
    assert v.gemaakt["regelbegrip"] == [imp.REGELS[7]["regelbegrip"]]


def test_een_tweede_run_maakt_niets():
    bff = NepBff()
    imp.importeer(bff, WID, uitvoeren=True, log=lambda _: None)
    eerst = len(bff.schrijven)
    v = imp.importeer(bff, WID, uitvoeren=True, log=lambda _: None)
    assert len(bff.schrijven) == eerst
    assert not any(v.gemaakt.values())
    assert len(v.bestond["regel"]) == 8 and len(v.bestond["keuze"]) == 7


def test_droog_schrijft_niets():
    bff = NepBff()
    v = imp.importeer(bff, WID, uitvoeren=False, log=lambda _: None)
    assert bff.schrijven == [] and len(v.gemaakt["regel"]) == 8


def test_een_onbekend_id_stopt_de_import_voor_er_iets_geschreven_is():
    b, e = _korte_ids()
    bff = NepBff(elementen=sorted(e - {"f9e23c7cf2d6"}))
    with pytest.raises(imp.ImportFout, match="f9e23c7cf2d6"):
        imp.importeer(bff, WID, uitvoeren=True, log=lambda _: None)
    assert bff.schrijven == []


def test_een_dubbelzinnig_id_stopt_de_import():
    b, _ = _korte_ids()
    bff = NepBff()
    bff.begrippen.append({"id": "de1bae54-ffff-4000-8000-000000000000", "inhoud": {"naam": "x"}, "status": "concept"})
    with pytest.raises(imp.ImportFout, match="2 treffers"):
        imp.importeer(bff, WID, uitvoeren=True, log=lambda _: None)
    assert bff.schrijven == []


def test_r8_is_een_beslisregel_op_de_rechtsbetrekking():
    r8 = imp.regel_aanmaak(imp.REGELS[7])
    assert r8["inhoud"]["soort"] == "beslisregel"
    assert r8["dragers"][0] == {"element_id": "e:0f01cda739e9", "rol": "grondslag", "geval": ""}
    assert r8["inhoud"]["uitvoer_begrip_id"] == "b:fb9f3866"


def test_de_regels_dragen_hun_sleutel_en_herkomst():
    for r in imp.REGELS:
        toelichting = imp.regel_aanmaak(r)["inhoud"]["toelichting"]
        assert imp.heeft_sleutel(toelichting, r["sleutel"])
        assert imp.BRON in toelichting


def test_geen_omgevingsgegevens_in_het_script():
    tekst = _PAD.read_text(encoding="utf-8")
    assert "wa_pat_" not in tekst.replace("`wa_pat_…`", "")
    assert not re.search(r"https://[a-z0-9.-]+\.[a-z]{2,}", tekst)
