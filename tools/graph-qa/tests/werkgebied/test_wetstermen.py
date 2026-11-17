"""De proef `Zoekprofiel.wetstermen` (de woordenkloof, meting `bronselectie-2026-11-17-drie-rondes`): het model vertaalt
de deelvraag naar zoektermen in de taal van de wet, de code houdt alleen wat in het zoekbereik staat, en de bestaande
index zoekt erop. Zonder echt model en zonder graaf."""
from __future__ import annotations

import re
from dataclasses import replace

from agent import bronnen_vinden, wetstermen as wt, zoekvragen
from agent import deelvraag_zoeken as dz
from fakes import FakeLLM, response, text_block, tool_block
from test_bronnen_vinden import DOSSIER, IWB, BepalingGraaf, _tsv

#: Hoe vaak een term in de regelingen staat (de telquery van de nepgraaf); 0 = staat er niet.
AANTAL = {"navordering": 12, "vergrijpboete": 3, "herziening": 8, "bijvragen": 0, "voorschot": 0}


class TelGraaf(BepalingGraaf):
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


def _model(termen: list[str]) -> FakeLLM:
    return FakeLLM([response([tool_block("w1", "geef_wetstermen", {"termen": termen})], "tool_use")])


VRAAG = "Mag de Belastingdienst later geld bijvragen?"


def test_de_vlag_staat_standaard_uit():
    assert dz.STANDAARD_PROFIEL.wetstermen is False


def test_zonder_vlag_of_zonder_model_geen_vertaling():
    assert bronnen_vinden._MODEL.get() is None
    assert bronnen_vinden._wetstermen(None, VRAAG, [IWB], {}) == []
    teken = bronnen_vinden._PROFIEL.set(replace(dz.STANDAARD_PROFIEL, wetstermen=True))
    try:
        assert bronnen_vinden._wetstermen(None, VRAAG, [IWB], {}) == [], "zonder model in de run zoekt de code zelf"
    finally:
        bronnen_vinden._PROFIEL.reset(teken)


def test_het_model_typt_alleen_zoektermen():
    eigenschappen = wt.schema()["input_schema"]["properties"]
    assert set(eigenschappen) == {"termen"} and eigenschappen["termen"]["items"] == {"type": "string"}
    assert wt.schema()["strict"] is True


def test_de_termen_worden_inhoudswoorden_zonder_de_woorden_van_de_vraag():
    genoemd = ["navordering", "Vergrijpboete", "navordering", "het bijvragen", "herziening van het voorschot", "eisen"]
    assert wt.als_zoektermen(genoemd, VRAAG) == ["navordering", "vergrijpboete", "herziening", "voorschot"]


def test_alleen_wat_in_het_zoekbereik_staat_telt_als_wetsterm():
    graaf = TelGraaf()
    assert wt.in_regelingen(graaf, ["navordering", "voorschot", "vergrijpboete"], [IWB]) == ["navordering", "vergrijpboete"]
    assert wt.in_regelingen(TelGraaf(kapot=True), ["navordering"], [IWB]) == [], "een storing kost de vertaling"
    veel = [f"term{chr(97 + i)}" for i in range(20)]
    AANTAL.update({w: 1 for w in veel})
    try:
        assert len(wt.in_regelingen(TelGraaf(), veel, [IWB])) == wt.MAX_WETSTERMEN
    finally:
        for w in veel:
            AANTAL.pop(w)


def test_de_stap_vertaalt_en_toetst():
    llm = _model(["navordering", "vergrijpboete", "voorschot"])
    meting: dict = {}
    assert wt.wetstermen(TelGraaf(), llm, "m", VRAAG, {"naam": "Achteraf"}, [IWB], meting) == ["navordering",
                                                                                               "vergrijpboete"]
    assert meting["llm_calls"] == 1
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "Deelvraag: " + VRAAG in prompt and "- Invorderingswet 1990" in prompt and "Werkgebied: Achteraf" in prompt


def test_zonder_bruikbaar_antwoord_geen_termen():
    llm = FakeLLM([response([text_block("Geen idee.")], "end_turn")])
    assert wt.wetstermen(TelGraaf(), llm, "m", VRAAG, {}, [IWB]) == []
    assert wt.wetstermen(TelGraaf(), FakeLLM([]), "m", "", {}, [IWB]) == [], "een lege deelvraag vraagt niets"


def test_de_index_zoekt_op_de_wetstermen_naast_de_deelvraag():
    args = {"regelingen": [IWB], "deelvraag": "Wanneer is een belastingaanslag invorderbaar?", "dossier": DOSSIER}
    zonder = dz.kandidatenpool(BepalingGraaf(), **args)
    graaf = BepalingGraaf()
    met = dz.kandidatenpool(graaf, **args, wetstermen=["dwangbevel", "invorderbaar"])
    assert met["termen"] == zonder["termen"] + ["dwangbevel"] and met["wetstermen"] == ["dwangbevel"]
    assert zonder["wetstermen"] == []
    assert any("dwangbevel" in q for q in graaf.queries), "de wetsterm zoekt in de index"


def test_de_pool_rond_de_gebeurtenis_kent_de_wetstermen():
    kand = [{"bron_iri": "urn:bwb:X:artikel:16", "tekst": "De inspecteur kan de navordering vaststellen."},
            {"bron_iri": "urn:bwb:X:artikel:1", "tekst": "Deze wet verstaat onder ontvanger ..."}]
    assert zoekvragen.opties_bij_deelvraag(kand, VRAAG) == []
    uit = zoekvragen.opties_bij_deelvraag(kand, VRAAG, wetstermen=["navordering"])
    assert [o["bron_iri"] for o in uit] == ["urn:bwb:X:artikel:16"] and uit[0]["geraakt"] == ["navordering"]


def test_de_bronnenrun_vraagt_de_termen_een_keer_per_deelvraag(monkeypatch):
    gezien: list = []

    def opties(graph, **kw):
        gezien.append(kw.get("wetstermen"))
        return []

    monkeypatch.setattr(bronnen_vinden, "bepaling_opties", opties)
    monkeypatch.setattr(wt, "wetstermen", lambda graph, llm, model, vraag, *a, **k: ["navordering"] if "geld" in vraag else [])
    invoer = {"naam": "Achteraf", "kern": [], "context": [], "dossier": {},
              "regelingen": [IWB],
              "deelvragen": [{"id": "d1", "vraag": VRAAG}, {"id": "d2", "vraag": "Welke termijn?"}]}
    profiel = replace(dz.STANDAARD_PROFIEL, wetstermen=True, model_kiest=False)
    bronnen_vinden.vind(BepalingGraaf(), invoer, methoden=("deelvraag",), profiel=profiel, llm=FakeLLM([]), model="m")
    assert gezien == [["navordering"], []]
