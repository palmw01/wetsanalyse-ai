"""Het plan bronselectie bij Termijnen (`docs/architectuur/onderzoek-bronselectie-termijnen-2026-11.md`): elke stap is een
vlag in `Zoekprofiel` (of naast de pool), standaard uit, met zijn eigen toets. Dezelfde nepgraaf als
`test_bronnen_vinden.py`."""
from __future__ import annotations

import re
from dataclasses import replace

from agent import deelvraag_zoeken as dz
from test_bronnen_vinden import DOSSIER, IWB, BepalingGraaf, _tsv


def _profiel(**vlaggen):
    return replace(dz.STANDAARD_PROFIEL, **vlaggen)


# --- stap 1a: zoektermen op onderscheidend vermogen (O6) ---------------------------------------------------------

#: Een deelvraag met meer inhoudswoorden dan `MAX_TERMEN`, het onderscheidende achteraan, en een vulwoord vooraan.
VRAAG = ("Hoe werkt de verrekening van een negatieve voorlopige aanslag door in de bedragen van reeds geregistreerde "
         "betalingstermijnen?")
#: Hoe vaak elke term in de regelingen staat (de telquery van de nepgraaf).
AANTAL = {"werkt": 400, "verrekening": 40, "negatieve": 30, "voorlopige": 60, "aanslag": 900, "bedragen": 500,
          "reeds": 300, "geregistreerde": 0, "betalingstermijnen": 6}


class TelGraaf(BepalingGraaf):
    """Beantwoordt de telquery met `AANTAL` op de term in de Lucene-query; de rest zoals `BepalingGraaf`."""

    def __init__(self, kapot: bool = False):
        super().__init__()
        self.tellingen: list[str] = []
        self.kapot = kapot

    def _antwoord(self, q: str) -> str:
        if "COUNT(DISTINCT ?node) AS ?aantal" in q:
            if self.kapot:
                raise RuntimeError("graaf hapert")
            term = re.search(r'tekst:\(?\(?([a-zà-ÿ]+)', q).group(1)
            self.tellingen.append(term)
            return _tsv(["aantal"], [[str(AANTAL.get(term, 0))]])
        return super()._antwoord(q)


def _termen(graaf, **vlaggen) -> list[str]:
    pool = dz.kandidatenpool(graaf, regelingen=[IWB], deelvraag=VRAAG, dossier=DOSSIER, profiel=_profiel(**vlaggen))
    return pool["termen"]


def test_standaard_staat_termen_idf_uit_en_telt_niets():
    graaf = TelGraaf()
    assert dz.STANDAARD_PROFIEL.termen_idf is False
    assert _termen(graaf) == ["werkt", "verrekening", "negatieve", "voorlopige", "aanslag", "bedragen"]
    assert graaf.tellingen == [], "zonder vlag geen telquery: het verzoek blijft gelijk"


def test_de_zeldzaamste_termen_zoeken_in_de_volgorde_van_de_vraag():
    graaf = TelGraaf()
    termen = _termen(graaf, termen_idf=True)
    assert "betalingstermijnen" in termen, "het onderscheidende woord achteraan krijgt een plaats"
    assert "aanslag" not in termen and "bedragen" not in termen, "de gewoonste woorden wijken"
    assert "geregistreerde" not in termen, "een term die nergens staat vindt niets en gaat achteraan"
    assert len(termen) == dz.MAX_TERMEN
    plek = {w: VRAAG.casefold().index(w) for w in termen}
    assert termen == sorted(termen, key=plek.__getitem__), "de volgorde van de vraag blijft"


def test_een_vulwoord_zoekt_niet():
    vraag = "Welke termijnen gelden bijvoorbeeld voor een voorlopige aanslag?"
    args = {"regelingen": [IWB], "deelvraag": vraag, "dossier": DOSSIER}
    assert "bijvoorbeeld" in dz.kandidatenpool(TelGraaf(), **args)["termen"], "zonder vlag ongewijzigd"
    assert "bijvoorbeeld" not in dz.kandidatenpool(TelGraaf(), **args, profiel=_profiel(termen_idf=True))["termen"]


def test_een_korte_vraag_telt_niets():
    graaf = TelGraaf()
    dz.kandidatenpool(graaf, regelingen=[IWB], deelvraag="Wanneer is een belastingaanslag invorderbaar?",
                      dossier=DOSSIER, profiel=_profiel(termen_idf=True))
    assert graaf.tellingen == [], "binnen MAX_TERMEN valt er niets te kiezen"


def test_een_haperende_telling_kost_alleen_de_keuze():
    assert _termen(TelGraaf(kapot=True), termen_idf=True) == \
        ["werkt", "verrekening", "negatieve", "voorlopige", "aanslag", "bedragen"]


# --- stap 1b: om de beurt alleen tussen regelingen met een sterke treffer (O7) --------------------------------------

def _k(iri: str, bwb: str) -> dict:
    return {"iri": iri, "bwb_id": bwb}


def test_om_de_beurt_sterk_laat_een_zwakke_regeling_wachten():
    a1, a2, a3 = _k("a1", "A"), _k("a2", "A"), _k("a3", "A")
    b1, c1 = _k("b1", "B"), _k("c1", "C")
    score = {"a1": 1.0, "a2": 0.9, "a3": 0.8, "b1": 0.6, "c1": 0.2}
    volgorde = [a1, a2, a3, b1, c1]
    # Zonder de grens krijgt C (0,2) de derde plaats, vóór a2.
    assert [k["iri"] for k in dz.om_de_beurt(volgorde, {}, ["A", "B", "C"])] == ["a1", "b1", "c1", "a2", "a3"]
    # Met de grens (de helft van 1,0) doen A en B om de beurt mee, en C komt erna.
    assert [k["iri"] for k in dz.om_de_beurt_sterk(volgorde, score, {}, ["A", "B", "C"])] == \
        ["a1", "b1", "a2", "a3", "c1"]


def test_om_de_beurt_sterk_met_gelijke_regelingen_is_om_de_beurt():
    volgorde = [_k("a1", "A"), _k("b1", "B"), _k("a2", "A")]
    score = {"a1": 1.0, "b1": 0.9, "a2": 0.8}
    assert dz.om_de_beurt_sterk(volgorde, score, {}, ["A", "B"]) == dz.om_de_beurt(volgorde, {}, ["A", "B"])


def test_beurt_sterk_staat_standaard_uit():
    assert dz.STANDAARD_PROFIEL.beurt_sterk is False and dz.AANDEEL_STERK == 0.5


# --- stap 1: de woordenroute naast een brede pool (O1) -----------------------------------------------------------

from agent import zoekvragen as zv  # noqa: E402


def _pool(iri: str, geraakt: list[str], brug: dict | None = None) -> dict:
    return {"bron_iri": iri, "geraakt": geraakt, "zoekvraag": "d", "signaal": "beleidsregel",
            **({"brug": brug} if brug else {})}


def _woord(iri: str, buiten: bool = False) -> dict:
    return {"bron_iri": iri, "geraakt": ["verrekening"], "buiten": buiten, "label": iri}


POOL = [_pool("p1", ["verrekening"]), _pool("p2", ["termijnen"], brug={"termijnen": "winstaandeel"}), _pool("p3", [])]
WOORDEN = [_woord("w1"), _woord("p1"), _woord("w2"), _woord("w3", buiten=True)]


def test_zwak_in_pool_is_alleen_brug_of_bonus():
    assert [zv.zwak_in_pool(o) for o in POOL] == [False, True, True]


def test_standaard_gaat_de_pool_voor_zoals_vroeger():
    uit = zv.samen_met_woorden(POOL, WOORDEN, limit=4)
    assert [o["bron_iri"] for o in uit] == ["p1", "p2", "p3", "w1", "w3"], "buiten komt er altijd achter"
    assert [o["bron"] for o in uit] == ["pool", "pool", "pool", "woorden", "woorden"]


def test_met_de_vlag_wijkt_een_zwakke_poolkandidaat_voor_een_woordtreffer():
    uit = zv.samen_met_woorden(POOL, WOORDEN, limit=4, woorden_voor_pool=True)
    assert [o["bron_iri"] for o in uit] == ["p1", "w1", "w2", "p2", "w3"]


def test_woorden_voor_pool_staat_standaard_uit():
    assert dz.STANDAARD_PROFIEL.woorden_voor_pool is False
