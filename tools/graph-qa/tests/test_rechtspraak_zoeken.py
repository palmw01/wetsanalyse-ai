"""Zoeken zonder artikel: de zoekfeed van de Rechtspraak (ADR-013, de tweede ingang van `zoek_uitspraken`).

De feed filtert op instantie, rechtsgebied, soort en periode, maar sorteert alleen op wijzigingsdatum en geeft hoogstens
1000 treffers per verzoek. "De tien nieuwste uitspraken van de Hoge Raad" vraagt dus een datumvenster dat de code kiest:
groot genoeg voor tien, klein genoeg voor één pagina. De nep hieronder geeft de treffers met opzet in een andere volgorde
dan de datum, zoals de echte feed.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

import pytest

from agent import tools
from agent.adapters import lido_rechtspraak as L
from agent.adapters.lido_rechtspraak import Feed, Instantie, Rechtsgebied, RechtspraakFout, Treffer
from agent.bron_lijst import lees as lijstvraag
from tests.fakes import make_settings

AAN = make_settings(connector_rechtspraak=True)
HR = "http://standaarden.overheid.nl/owms/terms/Hoge_Raad_der_Nederlanden"
RBGEL = "http://standaarden.overheid.nl/owms/terms/Rechtbank_Gelderland"
RBAMS = "http://standaarden.overheid.nl/owms/terms/Rechtbank_Amsterdam"
BELASTING = "http://psi.rechtspraak.nl/rechtsgebied#bestuursrecht_belastingrecht"
INSTANTIES = (Instantie(HR, "Hoge Raad", "HR", "TypeHr", True), Instantie(RBGEL, "Rechtbank Gelderland", "RBGEL", "Rechtbank", True),
              Instantie(RBAMS, "Rechtbank Amsterdam", "RBAMS", "Rechtbank", True),
              Instantie("http://psi.rechtspraak.nl/rbarn", "Rechtbank Arnhem", "RBARN", "Rechtbank", False),
              Instantie("http://standaarden.overheid.nl/owms/terms/Centrale_Raad_van_Beroep", "Centrale Raad van Beroep",
                        "CRVB", "TypeCRvB", True))


@dataclass
class Uitspraak:
    ecli: str
    datum: str
    creator: str
    subject: str = BELASTING
    type: str = "Uitspraak"


@dataclass
class NepFeed:
    uitspraken: list[Uitspraak]
    storing: bool = False
    vragen: list[dict] = field(default_factory=list)

    def zoek(self, *, instanties=(), rechtsgebieden=(), soort="", vanaf="", tot="", maximum=1000) -> Feed:
        self.vragen.append({"instanties": instanties, "rechtsgebieden": rechtsgebieden, "soort": soort, "vanaf": vanaf,
                            "tot": tot})
        hit = [u for u in self.uitspraken
               if (not instanties or u.creator in instanties) and (not rechtsgebieden or u.subject in rechtsgebieden)
               and (not soort or u.type == soort) and (not vanaf or u.datum >= vanaf) and (not tot or u.datum <= tot)]
        hit.sort(key=lambda u: u.ecli[::-1])  # niet op datum, zoals de echte feed (die ordent op wijziging)
        naam = {i.uri: i.naam for i in INSTANTIES}
        return Feed(tuple(Treffer(u.ecli, f"{u.ecli}, {naam[u.creator]}, {u.datum[8:]}-{u.datum[5:7]}-{u.datum[:4]}, 26/1",
                                  "HR verklaart het beroep ongegrond.") for u in hit[:maximum]), len(hit))

    def instanties(self):
        if self.storing:
            raise RechtspraakFout("data.rechtspraak.nl is niet bereikbaar")
        return INSTANTIES

    def rechtsgebieden(self):
        return (Rechtsgebied(BELASTING, "Belastingrecht", "Bestuursrecht"),
                Rechtsgebied("http://psi.rechtspraak.nl/rechtsgebied#bestuursrecht", "Bestuursrecht"))

    def koppelingen(self, *a, **k):
        raise AssertionError("zonder artikel geen LiDO")

    def document(self, ecli):
        raise AssertionError("zoeken leest geen uitspraak")


def _veel(code: str, creator: str, n: int, eind: dt.date = dt.date(2026, 11, 9)) -> list[Uitspraak]:
    """`n` uitspraken, drie per dag, teruglopend vanaf `eind`."""
    return [Uitspraak(f"ECLI:NL:{code}:{(eind - dt.timedelta(days=i // 3)).year}:{i + 1}",
                      (eind - dt.timedelta(days=i // 3)).isoformat(), creator) for i in range(n)]


def _zoek(bron, **args) -> dict:
    return json.loads(tools.dispatch("zoek_uitspraken", None, args, AAN, rechtspraak=bron))


def test_de_nieuwste_uitspraken_van_een_instantie_in_een_venster_op_datum():
    bron = NepFeed(_veel("HR", HR, 3000) + _veel("RBGEL", RBGEL, 600))
    uit = _zoek(bron, instantie="Hoge Raad", aantal=10)
    assert uit["status"] == "ok" and uit["aantal"] == 10
    datums = [r["datum"] for r in uit["resultaten"]]
    assert datums == sorted(datums, reverse=True) and datums[0] == "2026-11-09", "de nieuwste eerst, op uitspraakdatum"
    assert all(r["id"].startswith("ECLI:NL:HR:") for r in uit["resultaten"])
    assert uit["totaal"] == 3000, "het totaal over de hele periode, niet over het venster"
    assert uit["resultaten"][0]["samenvatting"] and uit["resultaten"][0]["orgaan"] == "Hoge Raad"
    assert all(v["instanties"] == (HR,) for v in bron.vragen)
    assert len(bron.vragen) <= 6, f"te veel verzoeken voor één lijst: {len(bron.vragen)}"
    assert uit["volledig"] is False and uit["vervolg"]["args"]["offset"] == 10


def test_de_oudste_vanaf_een_datum_en_het_vervolg_sluit_aan():
    bron = NepFeed(_veel("HR", HR, 3000))
    een = _zoek(bron, instantie="HR", volgorde="oudste", vanaf="2025-01-01", aantal=5)
    twee = _zoek(bron, **een["vervolg"]["args"])
    datums = [r["datum"] for r in een["resultaten"] + twee["resultaten"]]
    assert datums == sorted(datums) and datums[0] >= "2025-01-01"
    assert len({r["id"] for r in een["resultaten"] + twee["resultaten"]}) == 10


def test_een_kleine_lijst_kost_één_verzoek():
    bron = NepFeed(_veel("RBGEL", RBGEL, 12))
    uit = _zoek(bron, instantie="Rechtbank Gelderland")
    assert uit["status"] == "ok" and uit["aantal"] == 10 and uit["totaal"] == 12 and len(bron.vragen) == 1


def test_een_soort_gerecht_zijn_alle_gerechten_van_nu_en_een_rechtsgebied_een_uri():
    bron = NepFeed(_veel("RBGEL", RBGEL, 5) + _veel("RBAMS", RBAMS, 5))
    uit = _zoek(bron, instantie="rechtbank", rechtsgebied="belastingrecht")
    assert uit["totaal"] == 10
    assert set(bron.vragen[0]["instanties"]) == {RBGEL, RBAMS}, "een opgeheven rechtbank telt niet mee"
    assert bron.vragen[0]["rechtsgebieden"] == (BELASTING,)
    assert "rechtsgebied belastingrecht" in json.dumps(uit["zoekvraag"], ensure_ascii=False).replace('": "', " ")


@pytest.mark.parametrize("args,woord", [
    ({"instantie": "Rechtbank Atlantis"}, "Rechtbank Gelderland"),
    ({"rechtsgebied": "sterrenkunde"}, "belastingrecht"),
    ({"bwb_id": "BWBR0004770"}, "artikel"),
    ({"bwb_id": "BWBR0004770", "artikel": "36", "rechtsgebied": "belastingrecht"}, "zonder artikel"),
    ({"instantie": "Europees Hof voor de Rechten van de Mens"}, "bij een artikel"),
])
def test_een_invoerfout_noemt_een_voorbeeld(args, woord):
    uit = _zoek(NepFeed([]), **args)
    assert uit["status"] == "error" and uit["reden"] == "ongeldige_argumenten" and woord in uit["melding"], uit


def test_een_waardelijst_die_niet_te_lezen_is_is_een_storing_geen_onbekend_gerecht():
    uit = _zoek(NepFeed([], storing=True), instantie="Rechtbank Gelderland")
    assert uit["status"] == "error" and uit["reden"] == "bron_onbereikbaar"


def test_een_dag_met_meer_dan_een_pagina_zegt_dat_de_lijst_een_deel_is(monkeypatch):
    monkeypatch.setattr(L, "FEED_MAX", 5)
    bron = NepFeed([Uitspraak(f"ECLI:NL:HR:2026:{i}", "2026-11-09", HR) for i in range(1, 9)])
    orig = bron.zoek
    bron.zoek = lambda **k: orig(**{**k, "maximum": 5})  # type: ignore[method-assign]
    uit = _zoek(bron, instantie="HR", aantal=7)
    assert uit["status"] == "ok" and "deel" in uit["toelichting"]


@pytest.mark.parametrize("vraag,args", [
    ("Geef de 10 nieuwste uitspraken van de Hoge Raad in het belastingrecht",
     {"volgorde": "nieuwste", "aantal": 10, "soort": "uitspraak", "instantie": "Hoge Raad", "rechtsgebied": "belastingrecht"}),
    ("de laatste uitspraak van Rechtbank Gelderland",
     {"volgorde": "nieuwste", "aantal": 1, "soort": "uitspraak", "instantie": "Rechtbank Gelderland"}),
    ("de nieuwste uitspraken van de CRvB sinds 2026",
     {"volgorde": "nieuwste", "aantal": 10, "soort": "uitspraak", "instantie": "CRvB", "vanaf": "2026"}),
    ("de nieuwste jurisprudentie van de Raad van State", {"volgorde": "nieuwste", "aantal": 10, "instantie": "Raad van State"}),
])
def test_de_lijstvraag_leest_een_uitspraakvraag_zonder_model(vraag, args):
    v = lijstvraag(vraag, frozenset({"rechtspraak", "kamerstukken"}))
    assert v is not None and v.connector == "rechtspraak" and v.tool == "zoek_uitspraken" and v.args == args


@pytest.mark.parametrize("vraag", ["de laatste uitspraak op bezwaar", "wat staat er in de laatste uitspraak van de Hoge Raad"])
def test_geen_lijstvraag(vraag):
    assert lijstvraag(vraag, frozenset({"rechtspraak"})) is None
