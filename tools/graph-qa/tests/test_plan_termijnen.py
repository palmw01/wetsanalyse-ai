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
