"""De samenvatting na een annotatie: hoogstens vier zinnen, alles uit de voorstellen zelf."""
from __future__ import annotations

import re

import pytest

from agent.nodes.annotatie_samenvatting import MAX_ZINNEN, samenvatting, vindplaats

DOEL = {"artikel": "9", "lid": "1", "type": "Lid", "citeertitel": "Invorderingswet 1990"}


def v(klasse: str, door: str = "model", aandacht: str = "") -> dict:
    return {"klasse": klasse, "aandacht": aandacht, "trace": {"beslissing": {"door": door}}}


def zinnen(tekst: str) -> list[str]:
    return [z for z in re.split(r"(?<=[.?!])\s+", tekst.strip()) if z]


def test_voorbeeld_uit_het_ontwerp():
    t = samenvatting([v("Tijdsaanduiding", "regel"), v("Tijdsaanduiding", "regel"),
                      v("Rechtsbetrekking", "model", "geel"), v("Rechtsbetrekking")], DOEL)
    assert t == ("Ik heb artikel 9 lid 1 van de Invorderingswet 1990 geanalyseerd en vier JAS-elementen gevonden. "
                 "De markeringen zijn vooral Tijdsaanduiding en Rechtsbetrekking. "
                 "Eén voorstel heeft een plausibel alternatief en verdient daarom extra aandacht. "
                 "Twee voorstellen volgen rechtstreeks uit vaste regels, twee koos het model.")


@pytest.mark.parametrize("voorstellen", [
    [],
    [v("Rechtsobject")],
    [v("Rechtsobject", aandacht="geel") for _ in range(30)],
    [v(k, d, a) for k in ("Voorwaarde", "Rechtsobject", "Operator") for d in ("regel", "model", "terugval")
     for a in ("", "geel")],
])
def test_nooit_meer_dan_vier_zinnen_en_geen_uitroep_of_emoji(voorstellen):
    t = samenvatting(voorstellen, DOEL)
    assert 1 <= len(zinnen(t)) <= MAX_ZINNEN
    assert "!" not in t and all(ord(c) < 0x2600 for c in t)


def test_geen_elementen_is_één_zin():
    assert samenvatting([], DOEL) == "Ik heb artikel 9 lid 1 van de Invorderingswet 1990 geanalyseerd en geen JAS-elementen gevonden."


def test_enkelvoud_en_geen_keuze():
    t = samenvatting([v("Rechtsobject", "regel")], {"artikel": "9"})
    assert t.startswith("Ik heb artikel 9 geanalyseerd en één JAS-element gevonden.")
    assert "Geen voorstel vraagt om een keuze van jou." in t
    assert t.endswith("Alle voorstellen volgen rechtstreeks uit vaste regels.")


def test_een_terugval_is_een_aandachtspunt_en_geen_keuze_van_het_model():
    t = samenvatting([v("Rechtsobject", "terugval"), v("Rechtsobject", "regel"), v("Voorwaarde", "regel")], DOEL)
    assert "Eén voorstel heeft een plausibel alternatief" in t
    assert t.endswith("Twee voorstellen volgen rechtstreeks uit vaste regels.")


def test_zonder_beslisinfo_valt_de_laatste_zin_weg():
    t = samenvatting([{"klasse": "Rechtsobject"}, {"klasse": "Voorwaarde"}], DOEL)
    assert len(zinnen(t)) == 2


def test_een_divisie_is_een_bepaling_en_geen_artikel():
    assert vindplaats({"nummer": "25.1", "type": "Divisie"}) == "bepaling 25.1"
    assert vindplaats({"artikel": "9", "lid": "5"}) == "artikel 9 lid 5"
