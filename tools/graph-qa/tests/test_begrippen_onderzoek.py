"""De onderzoeksstand in de keten (spoor M, M1): model, fragmentruimte en de samengevoegde fragmentkeuze."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.begrippen_pipeline import fragmenten
from agent.begrippen_pipeline.kaartacties import Kant, fragmenten_voor
from agent.begrippen_pipeline.model import (
    Bron, Contextbron, Formulering, Manifest, Onderzoek, Ontbrekend, Reden, Rol, fragment_id,
)
from agent.begrippen_run import onderzoek_uit

CASUS = json.loads((Path(__file__).resolve().parents[1] / "eval" / "betekenisonderzoek_casus.json").read_text())
NODES = {n["bron_iri"]: n for n in CASUS["nodes"]}
A = "urn:bwb:BWBR0002320:artikel:30fb"


def _bron(iri: str) -> dict:
    n = NODES[iri]
    return {"bron_iri": iri, "tekst": n["tekst"], "bron_hash": n["bron_hash"], "label": iri, "aanhef": "",
            "regeling": "BWBR0002320"}


def _manifest(casus: str = "A") -> Manifest:
    fs = CASUS["casus"][casus]["formuleringen"]
    return Manifest(bronnen=tuple(Bron(**_bron(i)) for i in sorted({f["bron_iri"] for f in fs})),
                    formuleringen=tuple(Formulering(element_id=f"e{i}", **f) for i, f in enumerate(fs)))


def _context(iri: str, reden: Reden = Reden.ZELFDE_ARTIKEL) -> Contextbron:
    return Contextbron(**_bron(iri), rol=Rol.ONDERZOEK, reden=reden, voor=("e0",))


def _onderzoek(m: Manifest, *iris: str, **extra) -> Onderzoek:
    return Onderzoek(manifest_id=m.id, bronnen=tuple(_context(i) for i in iris), **extra)


def test_het_onderzoek_hoort_bij_zijn_manifest():
    m = _manifest()
    o = _onderzoek(m, f"{A}:lid:1", f"{A}:lid:5")
    assert o.past_bij(m) is o
    with pytest.raises(ValueError, match="ander manifest"):
        Onderzoek(manifest_id="Manders", bronnen=o.bronnen).past_bij(m)
    with pytest.raises(ValueError, match="ook een manifestbron"):
        _onderzoek(m, f"{A}:lid:4").past_bij(m)
    with pytest.raises(ValidationError, match="dubbel"):
        _onderzoek(m, f"{A}:lid:1", f"{A}:lid:1")
    with pytest.raises(ValidationError):
        Ontbrekend(wat="x", reden="geen_zin")


def test_het_id_volgt_uit_de_inhoud_en_niet_uit_de_volgorde():
    m = _manifest()
    een = _onderzoek(m, f"{A}:lid:1", f"{A}:lid:5")
    twee = _onderzoek(m, f"{A}:lid:5", f"{A}:lid:1")
    assert een.id == twee.id and een.id.startswith("O")
    assert _onderzoek(m, f"{A}:lid:1").id != een.id
    assert Onderzoek(manifest_id=m.id, bronnen=een.bronnen, versie="2").id != een.id


def test_de_fragmentruimte_groeit_met_het_onderzoek_en_houdt_de_oude_ids():
    m = _manifest()
    zonder = fragmenten.alle(m)
    met = fragmenten.alle(m, _onderzoek(m, f"{A}:lid:1"))
    assert set(zonder) < set(met)
    assert all(met[i] == f for i, f in zonder.items())
    nieuw = next(f for f in met.values() if f.bron_iri == f"{A}:lid:1")
    assert nieuw.id == fragment_id(f"{A}:lid:1", nieuw.start, nieuw.eind)


def test_zonder_onderzoek_is_de_fragmentkeuze_bitgelijk():
    m = _manifest()
    kant = Kant(id="b", inhoud={"naam": "herziening"}, leden=("e0",))
    assert fragmenten_voor(m, [kant]) == fragmenten_voor(m, [kant], onderzoek=None)
    assert [f.bron_iri for f in fragmenten_voor(m, [kant])] == [f"{A}:lid:4"] * len(fragmenten_voor(m, [kant]))


def test_de_volgorde_met_onderzoek_definities_eerst_dan_eigen_dan_context():
    m = _manifest()
    definitie = Contextbron(bron_iri="urn:bwb:BWBR0002320:artikel:1", tekst="In deze wet wordt verstaan onder "
                            "herziening: de wijziging van een voorlopige aanslag.", bron_hash="h",
                            regeling="BWBR0002320", rol=Rol.ONDERZOEK, reden=Reden.DEFINITIE_IN_REGELING)
    verwijzing = _context(f"{A}:lid:7", Reden.VERWIJZING)
    o = Onderzoek(manifest_id=m.id, bronnen=(verwijzing, _context(f"{A}:lid:1"), definitie)).past_bij(m)
    kant = Kant(id="b", inhoud={"naam": "herziening"}, leden=("e0",))
    iris = list(dict.fromkeys(f.bron_iri for f in fragmenten_voor(m, [kant], onderzoek=o)))
    assert iris == ["urn:bwb:BWBR0002320:artikel:1", f"{A}:lid:4", f"{A}:lid:1", f"{A}:lid:7"]
    # Het maximum knipt achteraan: de definities en de eigen bron blijven.
    kort = fragmenten_voor(m, [kant], maximum=2, onderzoek=o)
    assert [f.bron_iri for f in kort][0] == "urn:bwb:BWBR0002320:artikel:1"


def test_de_run_leest_het_onderzoek_en_toetst_het():
    m = _manifest()
    o = _onderzoek(m, f"{A}:lid:1")
    assert onderzoek_uit(o.model_dump(mode="json"), m) == o
    assert onderzoek_uit(None, m) is None
    with pytest.raises(ValueError):
        onderzoek_uit({**o.model_dump(mode="json"), "manifest_id": "Manders"}, m)
