"""Lex stelt met de analist een werkgebied samen (startactiviteit a en activiteit 1): herkenning, de
stapmachine, de kaartjes, de voorstellen uit graaf en model met het hele dossier, het gesprek over
meerdere beurten en het aanmaken door de driver."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from agent import werkgebied_intake as wi
from agent.models import ChatRequest
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block
from test_contract_drift import _bericht_velden

IB = "BWBR0011353"
H2 = f"urn:bwb:{IB}:hoofdstuk:2"
AFD = f"urn:bwb:{IB}:hoofdstuk:5:afdeling:5.1"


def _voorstel(naam=(), vraag=(), onderwerp="", aanleiding=(), doel=()):
    blok = SimpleNamespace(type="tool_use", id="v1", name=wi.TOOL,
                           input={"naam": list(naam), "aanleiding": list(aanleiding), "doel": list(doel),
                                  "analysevraag": list(vraag), "onderwerp": onderwerp})
    return response([blok], "tool_use")


def _deelvragen(*vragen):
    blok = SimpleNamespace(type="tool_use", id="d1", name="stel_deelvragen_voor", input={"deelvragen": list(vragen)})
    return response([blok], "tool_use")


DV1 = "Wie is belastingplichtig voor box 3?"
DV2 = "Hoe wordt het voordeel uit sparen berekend?"
OPTIES = [{"label": "Wet inkomstenbelasting 2001", "waarde": IB, "bron": {"bwb_id": IB}},
          {"label": "Algemene wet inzake rijksbelastingen", "waarde": "BWBR0002320", "bron": {"bwb_id": "BWBR0002320"}}]
DELEN = {IB: [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht", "deelvragen": []},
              {"iri": AFD, "kop": "Afdeling 5.1 – Box 3", "deelvragen": [DV1]}]}


@pytest.fixture
def graaf(monkeypatch):
    """De regelingvoorstellen zonder graaf: wat `regeling_opties` krijgt, en wat het teruggeeft."""
    gezocht: list[dict[str, Any]] = []

    def opties(graph, zoek, *, genoemd_in="", deelvragen=(), buiten=()):
        gezocht.append({"zoek": zoek, "genoemd_in": genoemd_in, "deelvragen": list(deelvragen), "buiten": list(buiten)})
        if zoek == "niets":
            return [], {}, [], []
        return list(OPTIES), dict(DELEN), [], []

    monkeypatch.setattr(wi, "regeling_opties", opties)
    return gezocht


# --- Herkenning ------------------------------------------------------------------------------------

@pytest.mark.parametrize("vraag", [
    "Kunnen we een werkgebied samenstellen?", "Ik wil een wetsanalyse uitvoeren", "maak een nieuw werkgebied",
    "Help me een werkgebied te bepalen over box 3", "Laten we beginnen met een wetsanalyse",
    "Start een wetsanalyse", "Ik wil graag een werkgebied aanmaken voor de invordering",
])
def test_startzinnen_worden_herkend(vraag):
    assert wi.is_werkgebiedvraag(vraag)


@pytest.mark.parametrize("vraag", [
    "Annoteer het werkgebied", "Welke bepalingen horen bij het werkgebied?", "Wat is een wetsanalyse?",
    "Wat betekent artikel 3.1 Wet IB 2001?", "Stel begrippen voor in dit werkgebied", "Wat ontbreekt er nog?",
])
def test_andere_vragen_zijn_geen_startzin(vraag):
    assert not wi.is_werkgebiedvraag(vraag)


def test_alleen_een_wetsanalysevraag_krijgt_uitleg():
    assert wi.is_wetsanalysevraag("ik wil een wetsanalyse uitvoeren")
    assert not wi.is_wetsanalysevraag("kunnen we een werkgebied samenstellen?")


def test_inhoud_van_de_startzin():
    assert wi.inhoud("Kunnen we een werkgebied samenstellen?") == []
    assert "box" in wi.inhoud("Ik wil een werkgebied over de box 3-heffing per 2026")


def test_een_startzin_binnen_een_werkgebied_gaat_niet_een_harde_route_in():
    for vraag in ("Kunnen we een werkgebied samenstellen?", "Ik wil een wetsanalyse uitvoeren"):
        r = ChatRequest(question=vraag, werkgebied_id="wg1")
        assert not r.is_werkgebied_annotatie and r.actie is None, vraag


# --- De stapmachine --------------------------------------------------------------------------------

def _klik(intake, stap, **kw):
    return {"intake_id": intake["id"], "stap": stap, "actie": kw.pop("actie", "antwoord"), **kw}


def test_de_volgorde_ligt_vast_en_de_samenvatting_volgt():
    """Startactiviteit a vóór de analysevraag; de bronnen pas na vraag, deelvragen en wat erbuiten valt."""
    i = wi.nieuwe_intake("kunnen we een werkgebied samenstellen?")
    assert i["stap"] == "naam"
    i, u = wi.verwerk(i, _klik(i, "naam", tekst="Box 3"))
    assert (u, i["stap"]) == ("verder", "aanleiding")
    i, _ = wi.verwerk(i, _klik(i, "aanleiding", keuzes=["wetswijziging", "verzonnen"], tekst="Herstel na het Kerstarrest"))
    assert i["stap"] == "context" and i["antwoorden"]["aanleiding"] == {"keuze": "wetswijziging",
                                                                        "tekst": "Herstel na het Kerstarrest"}
    i, _ = wi.verwerk(i, _klik(i, "context", tekst="De aangifte 2026 moet blijven werken."))
    i, _ = wi.verwerk(i, _klik(i, "doel", keuzes=["webservices", "traceerbaar"]))
    assert i["stap"] == "analysevraag"
    i, _ = wi.verwerk(i, _klik(i, "analysevraag", tekst="Wie is belastingplichtig voor box 3?"))
    assert i["stap"] == "praktijkvoorbeeld"
    i, _ = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", tekst="Een spaarder met een tweede huis."))
    assert i["stap"] == "deelvragen"
    i = {**i, "voorstellen": {"deelvragen": wi.tekst_opties([DV1, DV2], "voorstel van Lex")}}
    i, _ = wi.verwerk(i, _klik(i, "deelvragen", keuzes=[DV1], teksten=["Telt een tweede huis mee?", "  "],
                               tekst="wie is belastingplichtig voor box 3"))
    assert i["antwoorden"]["deelvragen"] == [{"vraag": DV1, "herkomst": "lex"},
                                             {"vraag": "Telt een tweede huis mee?", "herkomst": "analist"}]
    assert i["stap"] == "buiten"
    i, _ = wi.verwerk(i, _klik(i, "buiten", tekst="geen overgangsrecht"))
    assert i["stap"] == "regelingen"
    i = {**i, "voorstellen": {"regelingen": OPTIES}, "delen": DELEN}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[IB]))
    assert i["stap"] == "onderdelen" and i["antwoorden"]["regelingen"] == [{"bwb_id": IB, "label": OPTIES[0]["label"]}]
    i = {**i, "voorstellen": {**i["voorstellen"], "onderdelen": wi.onderdeel_opties(i["antwoorden"]["regelingen"], DELEN)}}
    i, _ = wi.verwerk(i, _klik(i, "onderdelen", keuzes=[AFD, wi.HELE + IB]))
    assert i["stap"] == "samenvatting"
    verzoek = wi.aanmaakverzoek(i)
    assert verzoek["werkgebied"] == {
        "naam": "Box 3", "analysevraag": "Wie is belastingplichtig voor box 3?", "intake_id": i["id"],
        "aanleiding": "Een wetswijziging raakt een bestaand proces. Herstel na het Kerstarrest.",
        "context": "De aangifte 2026 moet blijven werken.",
        "doel": "Bruikbaar voor de bouw van webservices; Traceerbaar koppelen aan de bestaande uitvoering.",
        "praktijkvoorbeeld": "Een spaarder met een tweede huis.",
        "deelvragen": [{"vraag": DV1, "herkomst": "lex"}, {"vraag": "Telt een tweede huis mee?", "herkomst": "analist"}],
        "afbakening": ("Regelingen: Wet inkomstenbelasting 2001.\n"
                       "Onderdelen: Afdeling 5.1 – Box 3 en De hele Wet inkomstenbelasting 2001.\n"
                       "Buiten de afbakening: geen overgangsrecht.")}
    # De hele regeling staat in de tekst, maar wordt geen bronselectie; het deel draagt zijn deelvraag mee.
    assert verzoek["bronnen"] == [{"bron_iri": AFD, "label": "Afdeling 5.1 – Box 3", "deelvragen": [DV1]}]
    samen = wi.kaart(i)["samenvatting"]
    assert samen["deelvragen"] == [DV1, "Telt een tweede huis mee?"] and samen["context"].startswith("De aangifte")


def test_weet_ik_niet_slaat_de_onderdelen_over_en_maakt_geen_bron():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"},
         "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[wi.ONBEKEND]))
    assert i["stap"] == "samenvatting"
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: nog te bepalen."
    assert wi.bronnen(i["antwoorden"]) == []
    kaart = wi.kaart({**i, "stap": "regelingen", "voorstellen": {"regelingen": OPTIES}})
    assert kaart["opties"][-1] == {"label": "Weet ik (nog) niet", "waarde": wi.ONBEKEND, "bron": {},
                                   "omschrijving": wi.ONBEKEND_OMSCHRIJVING}


def test_aanleiding_en_doel_komen_uit_de_vaste_lijst_en_deelvragen_mogen_meer_tekst():
    i = wi.nieuwe_intake("x")
    k = wi.kaart({**i, "stap": "aanleiding"})
    assert [o["waarde"] for o in k["opties"]] == list(wi.AANLEIDING) and not k["meerkeuze"]
    k = wi.kaart({**i, "stap": "doel"})
    assert [o["waarde"] for o in k["opties"]] == list(wi.DOEL) and k["meerkeuze"]
    k = wi.kaart({**i, "stap": "deelvragen"})
    assert k["meer_tekst"] and k["meerkeuze"] and k["overslaanbaar"]
    assert not wi.kaart({**i, "stap": "context"})["meer_tekst"]
    # Overslaan laat niets achter dat als antwoord leest.
    j = {**i, "stap": "doel"}
    j, _ = wi.verwerk(j, _klik(j, "doel", actie="overslaan", keuzes=["webservices"]))
    assert wi.doel_tekst(j["antwoorden"]) == "" and j["stap"] == "analysevraag"


def test_ook_bij_onderdelen_kan_weet_ik_niet():
    i = {**wi.nieuwe_intake("x"), "stap": "onderdelen",
         "antwoorden": {"naam": "Box 3", "regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}]}}
    assert wi.kaart(i)["opties"][-1]["waarde"] == wi.ONBEKEND
    i, _ = wi.verwerk(i, _klik(i, "onderdelen", keuzes=[wi.ONBEKEND]))
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: Wet IB 2001.\nOnderdelen: nog te bepalen."


def test_artikelen_in_eigen_tekst_worden_bronnen_bij_een_regeling():
    a = {"regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}], "onderdelen": [],
         "onderdelen_tekst": "artikel 5.2 en 5.3"}
    assert wi.bronnen(a) == [{"bwb_id": IB, "artikel": "5.2", "label": "Wet IB 2001 – art. 5.2", "deelvragen": []},
                             {"bwb_id": IB, "artikel": "5.3", "label": "Wet IB 2001 – art. 5.3", "deelvragen": []}]
    # Bij twee regelingen is niet te zeggen waar de artikelen staan: alleen tekst.
    assert wi.bronnen({**a, "regelingen": a["regelingen"] * 2}) == []


def test_naam_is_verplicht():
    i = wi.nieuwe_intake("x")
    assert wi.verwerk(i, _klik(i, "naam", actie="overslaan"))[1] == "naam_nodig"
    assert wi.verwerk(i, _klik(i, "naam", tekst="   "))[1] == "naam_nodig"
    assert not wi.kaart(i)["overslaanbaar"] and wi.kaart({**i, "stap": "buiten"})["overslaanbaar"]


def test_een_oud_kaartje_verandert_niets():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"}}
    assert wi.verwerk(i, _klik(i, "naam", tekst="Anders")) == (i, "verouderd")
    assert wi.verwerk(i, _klik(i, "samenvatting", actie="aanmaken"))[1] == "verouderd"


def test_eigen_tekst_bij_de_regelingen_is_een_zoekopdracht():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"}}
    i, u = wi.verwerk(i, _klik(i, "regelingen", tekst="Awir"))
    assert (u, i["stap"], i["zoekterm"]) == ("zoek", "regelingen", "Awir")


def test_vanaf_de_samenvatting_aanpassen_aanmaken_en_afbreken():
    i = {**wi.nieuwe_intake("x"), "stap": "samenvatting", "antwoorden": {"naam": "Box 3"}}
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "wijzig", "naar": "buiten"})[0]["stap"] == "buiten"
    klaar, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})
    assert (u, klaar["stap"]) == ("aanmaken", "klaar")
    # Nog eens aanmaken mag (de api is idempotent op de intake-id); na afbreken niet.
    assert wi.verwerk(klaar, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})[1] == "aanmaken"
    weg, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "afbreken"})
    assert u == "afgebroken" and not wi.is_open(weg)
    assert wi.verwerk(weg, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})[1] == "verouderd"


def test_het_kaartje_volgt_het_api_contract():
    """De vraagkaart gaat het bericht in; de api weigert stil niets, maar valideert wel."""
    import importlib.util
    import sys
    from pathlib import Path

    pad = Path(__file__).parents[3] / "api" / "app" / "gesprek_contracts.py"
    spec = importlib.util.spec_from_file_location("gesprek_contracts_intake", pad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    i = {**wi.nieuwe_intake("x"), "voorstellen": {"regelingen": OPTIES}}
    for stap in (*wi.STAPPEN, "samenvatting"):
        mod.Vraagkaart.model_validate(wi.kaart({**i, "stap": stap, "antwoorden": {"naam": "Box 3"}}))
    assert "vraagkaart" in _bericht_velden()


# --- Voorstellen ------------------------------------------------------------------------------------

def test_het_model_stelt_alleen_voor_met_het_hele_dossier_en_een_storing_is_geen_fout():
    llm = FakeLLM([_voorstel(naam=["Box 3", "Box 3"], vraag=["Wie betaalt box 3?", "zonder vraagteken"],
                             onderwerp="box 3", aanleiding=["wetswijziging"], doel=["webservices", "onzin"])])
    i = {**wi.nieuwe_intake("werkgebied over box 3"),
         "antwoorden": {"naam": "Box 3", "context": "Herstel na het Kerstarrest.", "buiten": "overgangsrecht"}}
    vs = wi.stel_voor(llm, "router", i)
    assert vs == {"naam": ["Box 3"], "aanleiding": ["wetswijziging"], "doel": ["webservices"],
                  "analysevraag": ["Wie betaalt box 3?"], "onderwerp": "box 3"}
    inhoud = llm.calls[0]["messages"][0]["content"]
    assert wi.dossier(i) in inhoud and "Context: Herstel na het Kerstarrest." in inhoud
    assert "Buiten de afbakening: overgangsrecht." in inhoud and "- wetswijziging:" in inhoud

    class Kapot:
        def create(self, **_):
            raise RuntimeError("provider weg")
    assert wi.stel_voor(Kapot(), "router", wi.nieuwe_intake("x")) == {
        "naam": [], "aanleiding": [], "doel": [], "analysevraag": [], "onderwerp": ""}


def _nep_overzicht(monkeypatch, per_onderwerp):
    from agent import overzicht as ov

    monkeypatch.setattr(ov, "regelingen_in_vraag", lambda g, v: ["BWBR0002320"] if "awr" in v.lower() else [])
    monkeypatch.setattr(ov, "_regelingen", lambda g: [{"bwb_id": "BWBR0002320", "namen": ["Algemene wet inzake rijksbelastingen", "AWR"]}])
    monkeypatch.setattr(ov, "bouw_overzicht", lambda g, v, onderwerp=None, scope=None: {"regelingen": per_onderwerp.get(onderwerp, [])})


def test_regelingen_komen_uit_het_overzicht_en_genoemde_staan_voorop(monkeypatch):
    _nep_overzicht(monkeypatch, {"belastingplicht": [
        {"bwb_id": IB, "citeertitel": "Wet inkomstenbelasting 2001",
         "delen": [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht"}, {"iri": "", "kop": "zonder iri"}]}]})
    opties, delen, voorop, weg = wi.regeling_opties(FakeGraph(), "belastingplicht", genoemd_in="volgens de AWR")
    assert [o["waarde"] for o in opties] == ["BWBR0002320", IB]
    assert voorop == ["BWBR0002320"] and weg == []
    assert delen == {IB: [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht", "bepalingen": 0, "deelvragen": []}]}
    assert opties[0]["omschrijving"] == "genoemd in je vraag"


def test_regelingen_ook_per_deelvraag_en_zonder_wat_erbuiten_valt(monkeypatch):
    """F2: per deelvraag zoeken, onthouden waar een deel bij hoort, en wat buiten valt zichtbaar weglaten."""
    from agent.werkgebied_context import uitsluitstammen

    _nep_overzicht(monkeypatch, {
        "box 3": [{"bwb_id": IB, "citeertitel": "Wet IB 2001", "delen": [{"iri": AFD, "kop": "Afdeling 5.1 – Box 3"}]}],
        "voordeel uit sparen": [{"bwb_id": IB, "citeertitel": "Wet IB 2001", "delen": [
            {"iri": AFD, "kop": "Afdeling 5.1 – Box 3"},
            {"iri": H2, "kop": "Hoofdstuk 10a – Overgangsrecht box 3"}]}]})
    opties, delen, _, weg = wi.regeling_opties(FakeGraph(), "box 3", deelvragen=[(DV2, "voordeel uit sparen")],
                                               buiten=uitsluitstammen("het overgangsrecht"))
    assert [d["iri"] for d in delen[IB]] == [AFD] and delen[IB][0]["deelvragen"] == [DV2]
    assert weg == ["Hoofdstuk 10a – Overgangsrecht box 3"]
    assert opties[0]["omschrijving"].endswith("bij een deelvraag")
    opties = wi.onderdeel_opties([{"bwb_id": IB, "label": "Wet IB 2001"}], delen, ["Eerste?", DV2])
    assert opties[0]["omschrijving"] == "Wet IB 2001 · deelvraag 2"


# --- Het gesprek ------------------------------------------------------------------------------------

def _beurt(settings, llm, vraag, actie=None, cid="g1"):
    from agent.agent import answer_stream
    from agent.models import IntakeActie

    async def run():
        return [e async for e in answer_stream(vraag, cid, settings=settings, llm=llm, graph=FakeGraph(),
                                               intake_actie=IntakeActie(**actie) if actie else None)]
    return asyncio.run(run())


def _kaart(events) -> dict[str, Any]:
    kaarten = [e["vraagkaart"] for e in events if e["type"] == "vraagkaart"]
    assert len(kaarten) == 1, events
    return kaarten[0]


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


def test_een_heel_gesprek_tot_aanmaken(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(aanleiding=["wetswijziging"]),
                   _voorstel(doel=["webservices"]),
                   _voorstel(vraag=["Wie is belastingplichtig voor box 3?"]),
                   _deelvragen(DV1, DV2),
                   response([text_block("WORKERS: antwoord\nSPECIALIST: algemeen\nPLAN: uitleg")], "end_turn"),
                   response([text_block("Box 3 is het inkomen uit sparen en beleggen.")], "end_turn"),
                   _voorstel(onderwerp="box 3")])

    def klik(k, vraag="x", **kw):
        return _kaart(_beurt(settings, llm, vraag, {"intake_id": k["intake_id"], "stap": k["stap"], **kw}))

    k = _kaart(e := _beurt(settings, llm, "Ik wil een wetsanalyse uitvoeren"))
    assert wi.UITLEG in _tekst(e) and (k["stap"], k["opties"], k["overslaanbaar"]) == ("naam", [], False)
    assert llm.index == 0, "een startzin zonder inhoud kost geen modelaanroep"

    k = klik(k, tekst="Box 3")
    assert k["stap"] == "aanleiding" and k["vooringevuld"] == ["wetswijziging"] and len(k["opties"]) == len(wi.AANLEIDINGEN)
    k = klik(k, keuzes=["wetswijziging"])
    assert k["stap"] == "context" and llm.index == 1, "context is vrije tekst: geen aanroep"
    k = klik(k, tekst="De aangifte 2026 moet blijven werken.")
    assert k["stap"] == "doel" and k["vooringevuld"] == ["webservices"]
    k = klik(k, keuzes=["webservices"])
    assert k["stap"] == "analysevraag" and k["opties"][0]["waarde"] == "Wie is belastingplichtig voor box 3?"
    k = klik(k, keuzes=["Wie is belastingplichtig voor box 3?"])
    assert k["stap"] == "praktijkvoorbeeld"
    k = klik(k, tekst="Een spaarder met een tweede huis.")
    assert k["stap"] == "deelvragen" and [o["waarde"] for o in k["opties"]] == [DV1, DV2] and k["meer_tekst"]

    # Elke voorstelaanroep kreeg alles wat er op dat moment lag.
    def inhoud(n):
        return llm.calls[n]["messages"][0]["content"]
    assert "Aanleiding: Een wetswijziging" in inhoud(2) and "Context: De aangifte 2026" in inhoud(2)
    assert "Doel: Bruikbaar voor de bouw van webservices." in inhoud(2)
    assert "Praktijkvoorbeeld: Een spaarder" in inhoud(3) and "Analysevraag: Wie is belastingplichtig" in inhoud(3)

    # Een tussenvraag: gewoon antwoord, het kaartje blijft open.
    tussen = _beurt(settings, llm, "Wat is box 3 eigenlijk?")
    assert not [x for x in tussen if x["type"] == "vraagkaart"]
    assert "OPEN KAARTJE" in llm.calls[4]["system"]

    k = klik(k, keuzes=[DV1], teksten=["Telt een tweede huis mee?"])
    assert k["stap"] == "buiten"
    k = klik(k, tekst="het overgangsrecht")
    assert k["stap"] == "regelingen" and k["meerkeuze"] and graaf[-1]["zoek"] == "box 3"
    assert "Deelvragen:\n- Wie is belastingplichtig" in inhoud(6) and "Buiten de afbakening: het overgangsrecht." in inhoud(6)
    assert [v for v, _ in graaf[-1]["deelvragen"]] == [DV1, "Telt een tweede huis mee?"]
    assert graaf[-1]["buiten"] == ["overgang"] and "overgangsrecht" not in graaf[-1]["genoemd_in"]
    assert [o["waarde"] for o in k["opties"]] == [IB, "BWBR0002320", wi.ONBEKEND]

    k = klik(k, keuzes=[IB])
    assert k["stap"] == "onderdelen" and [o["waarde"] for o in k["opties"]] == [H2, AFD, wi.HELE + IB, wi.ONBEKEND]
    assert k["opties"][1]["omschrijving"].endswith("deelvraag 1")
    k = klik(k, keuzes=[AFD])
    assert k["soort"] == "samenvatting" and k["samenvatting"]["bronnen"] == ["Afdeling 5.1 – Box 3"]

    e = _beurt(settings, llm, "Maak aan", {"intake_id": k["intake_id"], "stap": "samenvatting", "actie": "aanmaken"})
    [aan] = [x for x in e if x["type"] == "werkgebied_aanmaken"]
    assert aan["werkgebied"]["naam"] == "Box 3" and aan["werkgebied"]["context"] == "De aangifte 2026 moet blijven werken."
    assert aan["werkgebied"]["deelvragen"] == [{"vraag": DV1, "herkomst": "lex"},
                                               {"vraag": "Telt een tweede huis mee?", "herkomst": "analist"}]
    assert aan["bronnen"] == [{"bron_iri": AFD, "label": "Afdeling 5.1 – Box 3", "deelvragen": [DV1]}]
    assert llm.index == 7, "geen modelaanroep voor de klikken zelf"


def test_terugbladeren_zonder_wijziging_kost_niets_met_wijziging_nieuwe_voorstellen(tmp_path, graaf):
    """Het dossier bepaalt de voorstellen: een gewijzigd antwoord maakt ze opnieuw, een ongewijzigd niet."""
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(naam=["Box 3"]), _voorstel(aanleiding=["wetswijziging"]),
                   _voorstel(aanleiding=["digitaliseren"])])
    k = _kaart(_beurt(settings, llm, "Ik wil een werkgebied maken over box 3"))
    k = _kaart(_beurt(settings, llm, "x", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "Box 3"}))
    assert (k["stap"], k["vooringevuld"], llm.index) == ("aanleiding", ["wetswijziging"], 2)

    terug = _kaart(_beurt(settings, llm, "‹", {"intake_id": k["intake_id"], "stap": "aanleiding", "actie": "wijzig",
                                                 "naar": "naam"}))
    k = _kaart(_beurt(settings, llm, "x", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "Box 3"}))
    assert terug["vooringevuld"] == ["Box 3"] and k["stap"] == "aanleiding" and llm.index == 2

    _beurt(settings, llm, "‹", {"intake_id": k["intake_id"], "stap": "aanleiding", "actie": "wijzig", "naar": "naam"})
    k = _kaart(_beurt(settings, llm, "x", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "Digitale aangifte"}))
    assert (k["vooringevuld"], llm.index) == (["digitaliseren"], 3)
    assert "Werkgebied: Digitale aangifte" in llm.calls[2]["messages"][0]["content"]


def test_een_getypt_antwoord_op_het_open_kaartje(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([response([text_block("WORKERS: werkgebied\nPLAN: antwoord op het kaartje")], "end_turn"),
                   _voorstel()])
    _beurt(settings, llm, "Kunnen we een werkgebied samenstellen?")
    k = _kaart(_beurt(settings, llm, "Invordering van de erfbelasting"))
    assert k["stap"] == "aanleiding"


def test_een_kaartje_van_een_oude_intake(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([])
    _beurt(settings, llm, "Kunnen we een werkgebied samenstellen?")
    e = _beurt(settings, llm, "Box 3", {"intake_id": "oud", "stap": "naam", "tekst": "Box 3"})
    assert "niet meer loopt" in _tekst(e) and not [x for x in e if x["type"] == "vraagkaart"]


def test_vooringevuld_uit_de_eerste_zin(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(naam=["Box 3-heffing"], vraag=["Hoe wordt box 3 per 2026 berekend?"], onderwerp="box 3"),
                   _voorstel(aanleiding=["wetswijziging"])])
    k = _kaart(_beurt(settings, llm, "Ik wil een werkgebied maken over de box 3-heffing per 2026"))
    assert k["vooringevuld"] == ["Box 3-heffing"] and k["opties"][0]["waarde"] == "Box 3-heffing"
    k = _kaart(_beurt(settings, llm, "ok", {"intake_id": k["intake_id"], "stap": "naam", "keuzes": ["Box 3-heffing"]}))
    assert k["stap"] == "aanleiding" and k["vooringevuld"] == ["wetswijziging"] and llm.index == 2


def _sla_over(settings, llm, k, tot):
    while k["stap"] != tot:
        k = _kaart(_beurt(settings, llm, "-", {"intake_id": k["intake_id"], "stap": k["stap"], "actie": "overslaan"}))
    return k


def test_niets_gevonden_bij_eigen_zoekterm(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(), _voorstel(), _voorstel(), _voorstel()])
    k = _kaart(_beurt(settings, llm, "Kunnen we een werkgebied samenstellen?"))
    k = _kaart(_beurt(settings, llm, "X", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "X"}))
    k = _sla_over(settings, llm, k, "deelvragen")
    assert "Zonder analysevraag stel ik geen deelvragen voor" in k["toelichting"] and k["opties"] == []
    k = _sla_over(settings, llm, k, "regelingen")
    k = _kaart(e := _beurt(settings, llm, "niets", {"intake_id": k["intake_id"], "stap": "regelingen", "tekst": "niets"}))
    assert k["stap"] == "regelingen" and [o["waarde"] for o in k["opties"]] == [wi.ONBEKEND]
    assert "Ik vond geen regeling bij ‘niets’." in k["toelichting"] and "Weet ik (nog) niet" in _tekst(e)


# --- Aanmaken door de driver -------------------------------------------------------------------------

class NepApi:
    def __init__(self, weiger: set[str] = frozenset(), faal: bool = False):
        self.werkgebieden: dict[str, dict[str, Any]] = {}
        self.bronnen: list[dict[str, Any]] = []
        self.berichten: list[dict[str, Any]] = []
        self.weiger, self.faal = weiger, faal
        self.gekoppeld: list[tuple[str, dict[str, Any]]] = []

    async def maak_werkgebied(self, invoer):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if self.faal:
            raise WetsanalyseApiFout("POST → 503", 503)
        wg = self.werkgebieden.setdefault(invoer["intake_id"], {
            "id": f"wg-{len(self.werkgebieden) + 1}", "revisie": 1, **invoer,
            "deelvragen": [{"id": f"d{n}", "vraag": d["vraag"], "status": "actief", "bronnen": [], "begrippen": []}
                           for n, d in enumerate(invoer.get("deelvragen") or [])]})
        return dict(wg)

    async def voeg_bron_toe(self, wid, bron):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if bron.get("bron_iri") in self.weiger:
            raise WetsanalyseApiFout("POST → 422", 422)
        wg = next(w for w in self.werkgebieden.values() if w["id"] == wid)
        # Zoals de api: dezelfde bron nog eens is dezelfde selectie, zonder revisiesprong.
        if (eerder := next((n for n, b in enumerate(self.bronnen) if b["bron_iri"] == bron.get("bron_iri")), None)) is not None:
            return {"selectie": {"id": f"s-{eerder + 1}"}, "werkgebied": dict(wg)}
        self.bronnen.append(bron)
        wg["revisie"] += 1
        return {"selectie": {"id": f"s-{len(self.bronnen)}"}, "werkgebied": dict(wg)}

    async def koppel_deelvraag(self, wid, did, koppelingen):
        wg = next(w for w in self.werkgebieden.values() if w["id"] == wid)
        assert koppelingen["verwachte_revisie"] == wg["revisie"]
        self.gekoppeld.append((did, koppelingen))
        d = next(d for d in wg["deelvragen"] if d["id"] == did)
        d["bronnen"] = koppelingen["bronnen"]
        wg["revisie"] += 1
        return dict(wg)

    async def voeg_bericht_toe(self, gid, bericht):
        self.berichten.append(bericht)
        return {}

    async def aclose(self):
        pass


def _driver(monkeypatch, nep, events):
    from agent import beurt
    from agent.runs import Run

    monkeypatch.setattr(beurt, "WetsanalyseApi", lambda settings, user: nep)
    settings = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t")

    async def stroom():
        for e in events:
            yield e

    async def run():
        return [e async for e in beurt.voer_beurt_uit(stroom(), settings=settings, run=Run(run_id="r1", conversation_id="g1", user_id="u"),
                                                      gesprek_id="g1", user_id="u")]
    return asyncio.run(run())


VERZOEK = {"type": "werkgebied_aanmaken", "intake_id": "ik1",
           "werkgebied": {"naam": "Box 3", "analysevraag": "Wie?", "afbakening": "", "intake_id": "ik1"},
           "bronnen": [{"bron_iri": AFD, "label": "Afdeling 5.1"}, {"bron_iri": H2, "label": "Hoofdstuk 2"}]}


def test_de_driver_maakt_het_werkgebied_met_bronnen(monkeypatch):
    nep = NepApi(weiger={H2})
    uit = _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert [b["bron_iri"] for b in nep.bronnen] == [AFD]
    assert nep.bronnen[0] | {} == {"bron_iri": AFD, "verwachte_revisie": 1, "rol": "analyseren",
                                   "bereik": "onderliggend", "reden": wi.REDEN}
    [bericht] = nep.berichten
    assert bericht["artefact"] == {"soort": "werkgebied", "titel": "Box 3", "ref": {"werkgebied_id": "wg-1"}}
    assert "met 1 bron" in bericht["tekst"] and "Hoofdstuk 2" in bericht["tekst"] and "deelvragen" in bericht["tekst"]
    [opgeslagen] = [e for e in uit if e["type"] == "opgeslagen"]
    assert opgeslagen["artefact"] == bericht["artefact"] and uit[-1]["type"] == "done"
    # Nog eens: hetzelfde werkgebied, niets dubbel.
    _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert len(nep.werkgebieden) == 1


def test_de_driver_koppelt_een_bron_aan_de_deelvraag_waarbij_lex_hem_vond(monkeypatch):
    """Handleiding 1g: de bron hoort bij de deelvraag; de dekkingscheck ziet het meteen."""
    nep = NepApi()
    verzoek = {**VERZOEK, "werkgebied": {**VERZOEK["werkgebied"], "deelvragen": [
        {"vraag": DV1, "herkomst": "lex"}, {"vraag": "Eigen?", "herkomst": "analist"}]},
        "bronnen": [{"bron_iri": AFD, "label": "Afdeling 5.1", "deelvragen": ["wie is belastingplichtig voor box 3"]},
                    {"bron_iri": H2, "label": "Hoofdstuk 2", "deelvragen": []}]}
    _driver(monkeypatch, nep, [verzoek, {"type": "done"}])
    assert nep.gekoppeld == [("d0", {"verwachte_revisie": 3, "bronnen": ["s-1"], "begrippen": []})]
    assert "2 deelvragen" in nep.berichten[0]["tekst"]
    # Nog eens: al gekoppeld, dus niets dubbel.
    _driver(monkeypatch, nep, [verzoek, {"type": "done"}])
    assert len(nep.gekoppeld) == 1


def test_mislukt_aanmaken_dan_een_fout_en_geen_bericht(monkeypatch):
    nep = NepApi(faal=True)
    uit = _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert [e.get("foutcode") for e in uit if e["type"] == "error"] == ["werkgebied_niet_aangemaakt"]
    assert not nep.berichten and uit[-1]["type"] == "done"


def test_het_kaartje_gaat_mee_in_het_bericht(monkeypatch):
    nep = NepApi()
    kaart = wi.kaart(wi.nieuwe_intake("x"))
    _driver(monkeypatch, nep, [{"type": "token", "content": "Hoe noemen we het?"},
                               {"type": "vraagkaart", "vraagkaart": kaart}, {"type": "done"}])
    assert nep.berichten[0]["vraagkaart"] == kaart and json.dumps(nep.berichten[0])


def test_een_klik_gaat_nooit_een_harde_route_in():
    r = ChatRequest(question="Stel begrippen voor", werkgebied_id="wg1",
                    intake_actie={"intake_id": "ik1", "stap": "naam", "tekst": "Stel begrippen voor"})
    assert r.intake_actie is not None
    with pytest.raises(Exception):
        ChatRequest(question="x", intake_actie={"intake_id": "ik 1", "stap": "naam"})


def test_de_supervisor_kent_de_werkgebied_worker_en_ketent_hem_niet():
    from agent.supervisor import parse_supervisor

    assert parse_supervisor("WORKERS: werkgebied, antwoord\nPLAN: samenstellen") == (["werkgebied"], "samenstellen", False)
    assert parse_supervisor("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: x")[0] == ["duiding"]


def test_artikelnummers_in_eigen_tekst():
    assert wi.artikelen_in("artikel 5.2 en 5.3, art. 7a") == ["5.2", "5.3", "7a"]
    assert wi.artikelen_in("hoofdstuk 5") == []


# --- Terugbladeren (F1: ‹ n van 5 ›) -----------------------------------------------------------------

def _tot_onderdelen():
    i = wi.nieuwe_intake("x")
    i, _ = wi.verwerk(i, _klik(i, "naam", tekst="Box 3"))
    for stap in ("aanleiding", "context", "doel"):
        i, _ = wi.verwerk(i, _klik(i, stap, actie="overslaan"))
    i, _ = wi.verwerk(i, _klik(i, "analysevraag", tekst="Wie?"))
    for stap in ("praktijkvoorbeeld", "deelvragen", "buiten"):
        i, _ = wi.verwerk(i, _klik(i, stap, actie="overslaan"))
    i = {**i, "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[IB]))
    return i


def test_terug_naar_een_eerdere_stap_met_het_antwoord_ingevuld():
    i = _tot_onderdelen()
    assert i["stap"] == "onderdelen"
    terug, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "onderdelen", "actie": "wijzig", "naar": "naam"})
    assert (u, terug["stap"]) == ("verder", "naam")
    k = wi.kaart(terug)
    assert (k["vooringevuld"], k["beantwoord"], k["terug"]) == (["Box 3"], True, False)
    k = wi.kaart({**terug, "stap": "regelingen"})
    assert (k["vooringevuld"], k["beantwoord"], k["terug"]) == ([IB], True, True)
    # Overgeslagen telt als beantwoord: › mag verder.
    assert wi.kaart({**terug, "stap": "context"})["beantwoord"]
    # Vooruit met hetzelfde antwoord: de andere antwoorden blijven staan.
    verder, _ = wi.verwerk(terug, _klik(terug, "naam", tekst="Box 3"))
    assert verder["stap"] == "aanleiding" and verder["antwoorden"]["regelingen"] == [{"bwb_id": IB, "label": OPTIES[0]["label"]}]


def test_terug_mag_niet_naar_een_latere_stap_of_vanaf_een_oud_kaartje():
    i = _tot_onderdelen()
    i = {**i, "stap": "regelingen"}
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "regelingen", "actie": "wijzig", "naar": "onderdelen"})[1] == "verouderd"
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "naam", "actie": "wijzig", "naar": "naam"})[1] == "verouderd"


def test_een_nieuwe_stap_is_nog_niet_beantwoord():
    i = _tot_onderdelen()
    k = wi.kaart(i)
    assert (k["beantwoord"], k["terug"]) == (False, True)
    assert wi.eerder_antwoord({"onderdelen_onbekend": True}, "onderdelen") == [wi.ONBEKEND]


def test_omschrijving_van_een_regeling_en_een_onderdeel_uit_het_overzicht():
    r = {"soort": "wet", "delen": [{}, {}], "ook_genoemd": [{}]}
    assert wi._omschrijving_regeling(r, "box 3") == "wet · 2 delen over ‘box 3’ · 1 bepaling noemt het"
    opties = wi.onderdeel_opties([{"bwb_id": IB, "label": "Wet IB 2001"}],
                                 {IB: [{"iri": AFD, "kop": "Afdeling 5.1", "bepalingen": 12, "deelvragen": []}]})
    assert [o["omschrijving"] for o in opties] == ["Wet IB 2001 · 12 bepalingen", wi.HELE_OMSCHRIJVING]
