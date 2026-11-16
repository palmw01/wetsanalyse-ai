"""De volgorde van de voorstellijst per deelvraag als contract (Lex Bench §20.5 stap 4, testplan api V8).

De werkplek toont de voorstellen bij een deelvraag in de volgorde van de api, en Lex Bench meet die lijst (plan §4.4: wat
het paneel als voorstel toont, in de volgorde van de werkplek). Verandert de volgorde stil, dan verandert de meting zonder
dat Lex veranderde. Deze test legt elke sleutel van `bronselectie.voorstel_volgorde` vast, met één geval per sleutel
waar alleen díé sleutel beslist, en door de echte route heen.
"""
from __future__ import annotations

import random

from app.bronselectie import BEWIJS_VOLGORDE, voorstel_volgorde
from app.bronnen_run_contracts import ROL_VOLGORDE
from test_werkgebieden import client, database, graaf  # noqa: F401


def _v(iri: str, rol: str = "kern", soorten=("tekst",), bewijzen: int = 1, label: str = "x") -> dict:
    return {"bron_iri": iri, "rol": rol, "bewijs_soorten": list(soorten), "_bewijzen": bewijzen, "label": label}


# Elke rij wint van de volgende op precies één sleutel, en elke latere sleutel wijst de andere kant op: zo beslist alleen
# die ene sleutel, en valt een sleutel die wegvalt meteen op.
VERWACHT = [
    _v("urn:9", rol="kern", soorten=("grondslag",), bewijzen=1, label="z"),
    _v("urn:8", rol="kern", soorten=("verwijzing",), bewijzen=3, label="y"),    # zwakkere soort bewijs
    _v("urn:7", rol="kern", soorten=("verwijzing",), bewijzen=2, label="a"),    # minder bewijs
    _v("urn:1", rol="kern", soorten=("verwijzing",), bewijzen=2, label="b"),    # later label
    _v("urn:2", rol="kern", soorten=("verwijzing",), bewijzen=2, label="b"),    # latere iri
    _v("urn:05", rol="afhankelijkheid", soorten=("grondslag",), bewijzen=9, label="a"),  # zwakkere rol
    _v("urn:04", rol="aanverwant", soorten=("grondslag",), bewijzen=9, label="a"),
    _v("urn:03", rol="onbekend", soorten=("grondslag",), bewijzen=9, label="a"),
    _v("urn:02", rol="onbekend", soorten=(), bewijzen=10, label="a"),           # zonder bewijs telt als tekst
    _v("urn:01", rol="onbekend", soorten=("gelijkenis",), bewijzen=11, label="a"),
]


def test_elke_sleutel_beslist_in_de_vastgelegde_volgorde():
    for ronde in range(20):
        lijst = [dict(v) for v in VERWACHT]
        random.Random(ronde).shuffle(lijst)
        assert [v["bron_iri"] for v in sorted(lijst, key=voorstel_volgorde)] == [v["bron_iri"] for v in VERWACHT]


def test_de_rangorde_van_rol_en_bewijs_ligt_vast():
    """Een wijziging hierin is een wijziging van het contract: dan verandert de meting van Lex Bench."""
    assert sorted(ROL_VOLGORDE, key=ROL_VOLGORDE.get) == ["kern", "afhankelijkheid", "aanverwant"]
    assert sorted(BEWIJS_VOLGORDE, key=BEWIJS_VOLGORDE.get) == [
        "grondslag", "genoemd", "verwijzing", "definitie", "structuur", "tekst", "gelijkenis"]


async def test_het_overzicht_geeft_de_voorstellen_in_die_volgorde(client):
    """Door de echte route: de lijst van `GET …/bronselectie` is gesorteerd op `voorstel_volgorde`."""
    from test_annotatie_v2 import ART, ONE, TWO
    from test_bronselectie import _dq, _kd, _met_kandidaten, _overzicht, _vier
    from test_werkgebieden import ART2

    wg, ids = await _vier(client)
    await _met_kandidaten(client, wg, [
        _kd(TWO, "aanverwant", deelvragen=[ids[0]]),
        _kd(ONE, "kern", deelvragen=[ids[0]], vanuit=ART2, methode="verwijzing_uit"),
        _kd(ART2, "afhankelijkheid", deelvragen=[ids[0]]),
        _kd(ART, "kern", deelvragen=[ids[0]])])
    lijst = _dq(await _overzicht(client, wg), ids[0])["kandidaten"]
    assert [k["bron_iri"] for k in lijst] == [ONE, ART, ART2, TWO], [(k["rol"], k["bewijs_soorten"]) for k in lijst]
    assert all("_bewijzen" not in k for k in lijst), "de hulpsleutel lekt niet naar de werkplek"
