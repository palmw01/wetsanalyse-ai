"""B-2 uit de E2E-test Rekeningafspraken (16 nov 2026; plan centrale agent na A6, PR E): het zoeken per deelvraag
miste de kern. Lex vond Uitv.reg. Iw art. 40ca lid 1, dat naar Iw 7a verwijst, maar niet 7a zelf; en de kandidaten per
deelvraag verschilden nauwelijks. Twee vlaggen in `Zoekprofiel`, beide standaard uit tot de meting:
`verwijzingen` en `onderscheidend`. Dezelfde nepgraaf als `test_bronnen_vinden.py`."""
from __future__ import annotations

from dataclasses import replace

from agent import deelvraag_zoeken as dz
from test_bronnen_vinden import DOSSIER, IW, IWB, L1, BepalingGraaf, _opties, _tsv

DOEL = f"{IW}:artikel:7a:lid:1"
BUITEN = "urn:bwb:BWBR0002320:artikel:4:89"


class VerwijsGraaf(BepalingGraaf):
    """Lid 1 van het eerste resultaat verwijst naar artikel 7a lid 1 (binnen het bereik) en naar een regeling
    daarbuiten."""

    def _antwoord(self, q: str) -> str:
        if "bwb:heeftVerwijzing" in q and "?vanuit" in q:
            return _tsv(["vanuit", "naar"], [[L1, DOEL], [L1, BUITEN], [L1, L1]])
        return super()._antwoord(q)


def _profiel(**vlaggen):
    return replace(dz.STANDAARD_PROFIEL, **vlaggen)


def test_verwijzingen_staat_aan_en_onderscheidend_uit():
    """`verwijzingen` staat aan sinds stap 8 van het plan Termijnen (16 nov 2026); `onderscheidend` blijft uit."""
    assert dz.STANDAARD_PROFIEL.verwijzingen is True and dz.STANDAARD_PROFIEL.onderscheidend is False
    uit = _profiel(verwijzingen=False)
    assert [o["bron_iri"] for o in _opties(VerwijsGraaf(), profiel=uit)] == [o["bron_iri"] for o in _opties(profiel=uit)]


def test_met_verwijzingen_komt_het_verwezen_artikel_mee_binnen_het_bereik():
    uit = _opties(VerwijsGraaf(), profiel=_profiel(verwijzingen=True))
    extra = [o for o in uit if o.get("verwezen_vanuit")]
    assert [o["bron_iri"] for o in extra] == [DOEL], "binnen het bereik, niet zichzelf en niet erbuiten"
    assert extra[0]["omschrijving"].startswith("verwezen vanuit ")
    assert len(uit) == len(_opties(profiel=_profiel(verwijzingen=False))) + 1


def test_een_haperende_graaf_kost_alleen_de_aanvulling():
    class Kapot(VerwijsGraaf):
        def _antwoord(self, q: str) -> str:
            if "bwb:heeftVerwijzing" in q:
                raise RuntimeError("graaf hapert")
            return super()._antwoord(q)

    assert [o["bron_iri"] for o in _opties(Kapot(), profiel=_profiel(verwijzingen=True))] == \
        [o["bron_iri"] for o in _opties(profiel=_profiel(verwijzingen=False))]


def test_een_term_uit_elke_deelvraag_rangschikt_alleen():
    deelvragen = ["Wanneer is een belastingaanslag invorderbaar?",
                  "Wanneer is een belastingaanslag direct invorderbaar?",
                  "Wie betaalt de belastingaanslag na de termijn?"]
    termen = ["belastingaanslag", "invorderbaar"]
    assert dz.gedeelde_termen(termen, deelvragen) == ["belastingaanslag"]
    # Alles gedeeld: dan zoekt de deelvraag gewoon op haar termen.
    assert dz.gedeelde_termen(["belastingaanslag"], deelvragen) == []
    assert dz.gedeelde_termen(termen, deelvragen[:1]) == [], "zonder twee deelvragen geen onderscheid"

    args = {"regelingen": [IWB], "deelvraag": deelvragen[0], "dossier": {**DOSSIER, "deelvragen": deelvragen}}
    pool = dz.kandidatenpool(BepalingGraaf(), **args, profiel=_profiel(onderscheidend=True))
    assert "belastingaanslag" not in pool["termen"] and "belastingaanslag" in pool["dossiertermen"]
    assert "belastingaanslag" in dz.kandidatenpool(BepalingGraaf(), **args)["termen"], "standaard uit"
