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
L52 = f"urn:bwb:{IB}:artikel:5.2:lid:1"
L53 = f"urn:bwb:{IB}:artikel:5.3:lid:1"
L21 = f"urn:bwb:{IB}:artikel:2.1:lid:1"


def _bep(iri, label, buiten=False):
    return {"bron_iri": iri, "bwb_id": IB, "label": label, "geraakt": [], "buiten": buiten,
            "omschrijving": "valt mogelijk buiten de afbakening" if buiten else f"{label} · raakt: box"}


def _bepaling_optie(o):
    """Een bepaling als optie op het kaartje, zoals de node haar maakt."""
    return {"label": o["label"], "waarde": o["bron_iri"], "bron": {"bwb_id": o["bwb_id"], "iri": o["bron_iri"]},
            "omschrijving": o["omschrijving"]}


#: Wat `bepaling_opties` per deelvraag teruggeeft (None = de analysevraag).
BEPALINGEN = {DV1: [_bep(L21, "Artikel 2.1, lid 1 – Wet IB 2001")],
              "Telt een tweede huis mee?": [_bep(L52, "Artikel 5.2, lid 1 – Wet IB 2001"),
                                            _bep(L53, "Artikel 5.3, lid 1 – Wet IB 2001", buiten=True)],
              None: [_bep(L52, "Artikel 5.2, lid 1 – Wet IB 2001")]}


@pytest.fixture
def graaf(monkeypatch):
    """De voorstellen uit de graaf zonder graaf: wat `regeling_opties` en `bepaling_opties` krijgen, en
    wat ze teruggeven."""
    from agent import bronnen_vinden

    gezocht: list[dict[str, Any]] = []

    def opties(graph, zoek, *, genoemd_in="", deelvragen=(), buiten=()):
        gezocht.append({"zoek": zoek, "genoemd_in": genoemd_in, "deelvragen": list(deelvragen), "buiten": list(buiten)})
        if zoek == "niets":
            return [], [], []
        return list(OPTIES), [], []

    def bepalingen(graph, *, regelingen, deelvraag, dossier, buiten, limit=8):
        gezocht.append({"bepalingen": deelvraag, "regelingen": list(regelingen), "buiten": list(buiten),
                        "analysevraag": dossier.get("analysevraag", "")})
        return list(BEPALINGEN.get(deelvraag, []))

    monkeypatch.setattr(wi, "regeling_opties", opties)
    monkeypatch.setattr(bronnen_vinden, "bepaling_opties", bepalingen)
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
    return {"intake_id": intake["id"], "stap": stap, "deel": intake.get("deel", 0),
            "actie": kw.pop("actie", "antwoord"), **kw}


def _met_bepalingen(i, *opties):
    """De opties van het huidige bepalingen-kaartje, zoals de node ze klaarzet."""
    return {**i, "voorstellen": {**i.get("voorstellen", {}), wi.kaartsleutel(i): [_bepaling_optie(o) for o in opties]}}


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
    i = {**i, "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[IB]))
    assert (i["stap"], i["deel"]) == ("bepalingen", 0)
    assert i["antwoorden"]["regelingen"] == [{"bwb_id": IB, "label": OPTIES[0]["label"]}]
    # Eén kaartje per deelvraag: eerst deelvraag 1, dan 2; dezelfde bepaling mag bij beide.
    k = wi.kaart(i)
    assert (k["nr"], k["totaal"], k["deel"]) == (10, 11, {"index": 0, "totaal": 2, "deelvraag": DV1})
    assert k["vraag"] == "Welke bepalingen horen bij deelvraag 1?"
    i = _met_bepalingen(i, *BEPALINGEN[DV1], BEPALINGEN[None][0])
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", keuzes=[L21, L52]))
    assert (i["stap"], i["deel"]) == ("bepalingen", 1)
    assert wi.kaart(i)["nr"] == 11 and wi.kaart(i)["deel"]["deelvraag"] == "Telt een tweede huis mee?"
    i = _met_bepalingen(i, *BEPALINGEN["Telt een tweede huis mee?"])
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", keuzes=[L52]))
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
                       "Bepalingen: Artikel 2.1, lid 1 – Wet IB 2001 en Artikel 5.2, lid 1 – Wet IB 2001.\n"
                       "Buiten de afbakening: geen overgangsrecht.")}
    # Elke gekozen bepaling is één bron, met de deelvragen op wier kaartje ze gekozen werd.
    assert verzoek["bronnen"] == [
        {"bron_iri": L21, "label": "Artikel 2.1, lid 1 – Wet IB 2001", "deelvragen": [DV1]},
        {"bron_iri": L52, "label": "Artikel 5.2, lid 1 – Wet IB 2001", "deelvragen": [DV1, "Telt een tweede huis mee?"]}]
    samen = wi.kaart(i)["samenvatting"]
    assert samen["deelvragen"] == [DV1, "Telt een tweede huis mee?"] and samen["context"].startswith("De aangifte")
    assert samen["bronnen"] == ["Artikel 2.1, lid 1 – Wet IB 2001 (deelvraag 1)",
                                "Artikel 5.2, lid 1 – Wet IB 2001 (deelvragen 1, 2)"]
    assert wi.kaart(i)["nr"] == wi.kaart(i)["totaal"] == 11


def test_weet_ik_niet_slaat_de_bepalingen_over_en_maakt_geen_bron():
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


def test_ook_bij_de_bepalingen_kan_weet_ik_niet():
    i = {**wi.nieuwe_intake("x"), "stap": "bepalingen",
         "antwoorden": {"naam": "Box 3", "regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}]}}
    k = wi.kaart(i)
    # Zonder deelvragen één kaartje, over de analysevraag.
    assert k["opties"][-1]["waarde"] == wi.ONBEKEND and k["deel"] == {"index": 0, "totaal": 1, "deelvraag": None}
    assert k["vraag"] == "Welke bepalingen horen bij de analysevraag?" and k["totaal"] == 10
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", keuzes=[wi.ONBEKEND]))
    assert i["stap"] == "samenvatting"
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: Wet IB 2001.\nBepalingen: nog te bepalen."
    assert wi.eerder_antwoord(i["antwoorden"], "bepalingen", None) == [wi.ONBEKEND]


def test_artikelen_in_eigen_tekst_worden_bronnen_bij_een_regeling():
    a = {"regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}], "deelvragen": [{"vraag": DV1, "herkomst": "lex"}],
         "bepalingen": {wi.deel_sleutel(DV1): {"bronnen": [], "tekst": "artikel 5.2 en 5.3", "onbekend": False}}}
    assert wi.bronnen(a) == [{"bwb_id": IB, "artikel": "5.2", "label": "Wet IB 2001 – art. 5.2", "deelvragen": [DV1]},
                             {"bwb_id": IB, "artikel": "5.3", "label": "Wet IB 2001 – art. 5.3", "deelvragen": [DV1]}]
    # Bij twee regelingen is niet te zeggen waar de artikelen staan: alleen tekst.
    assert wi.bronnen({**a, "regelingen": a["regelingen"] * 2}) == []
    # Een keuze bij een deelvraag die er niet meer is, telt niet.
    assert wi.bronnen({**a, "deelvragen": [{"vraag": "Iets anders?", "herkomst": "analist"}]}) == []


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
    opties, voorop, weg = wi.regeling_opties(FakeGraph(), "belastingplicht", genoemd_in="volgens de AWR")
    assert [o["waarde"] for o in opties] == ["BWBR0002320", IB]
    assert voorop == ["BWBR0002320"] and weg == []
    assert opties[0]["omschrijving"] == "genoemd in je vraag"


def test_regelingen_ook_per_deelvraag_en_zonder_wat_erbuiten_valt(monkeypatch):
    """F2: per deelvraag zoeken, en wat buiten valt zichtbaar weglaten."""
    from agent.werkgebied_context import uitsluitstammen

    _nep_overzicht(monkeypatch, {
        "box 3": [{"bwb_id": IB, "citeertitel": "Wet IB 2001", "delen": [{"iri": AFD, "kop": "Afdeling 5.1 – Box 3"}]}],
        "voordeel uit sparen": [{"bwb_id": IB, "citeertitel": "Wet IB 2001", "delen": [
            {"iri": AFD, "kop": "Afdeling 5.1 – Box 3"},
            {"iri": H2, "kop": "Hoofdstuk 10a – Overgangsrecht box 3"}]}]})
    opties, _, weg = wi.regeling_opties(FakeGraph(), "box 3", deelvragen=[(DV2, "voordeel uit sparen")],
                                        buiten=uitsluitstammen("het overgangsrecht"))
    assert weg == ["Hoofdstuk 10a – Overgangsrecht box 3"]
    assert opties[0]["omschrijving"].endswith("bij een deelvraag")


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
        deel = {"deel": k["deel"]["index"]} if k.get("deel") else {}
        return _kaart(_beurt(settings, llm, vraag, {"intake_id": k["intake_id"], "stap": k["stap"], **deel, **kw}))

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
    # Per deelvraag een kaartje met de bepalingen uit de gekozen regeling, zonder model.
    assert k["stap"] == "bepalingen" and k["deel"] == {"index": 0, "totaal": 2, "deelvraag": DV1}
    assert [o["waarde"] for o in k["opties"]] == [L21, wi.ONBEKEND] and k["vooringevuld"] == []
    assert graaf[-1] == {"bepalingen": DV1, "regelingen": [IB], "buiten": ["overgang"],
                         "analysevraag": "Wie is belastingplichtig voor box 3?"}
    k = klik(k, keuzes=[L21])
    assert k["deel"]["index"] == 1 and [o["waarde"] for o in k["opties"]] == [L52, L53, wi.ONBEKEND]
    # Wat raakt aan wat erbuiten valt staat onderaan, gemarkeerd, en is niet aangevinkt.
    assert k["opties"][1]["omschrijving"] == "valt mogelijk buiten de afbakening" and k["vooringevuld"] == []
    assert "raakt aan wat buiten het werkgebied valt" in k["toelichting"]
    # Terug naar deelvraag 1: de keuze staat er, en er wordt niet opnieuw gezocht.
    n = len(graaf)
    terug = klik(k, actie="wijzig", naar="bepalingen", naar_deel=0)
    assert terug["deel"]["index"] == 0 and terug["vooringevuld"] == [L21] and terug["beantwoord"] and len(graaf) == n
    k = klik(terug, keuzes=[L21])
    assert k["deel"]["index"] == 1 and len(graaf) == n
    k = klik(k, keuzes=[L52])
    assert k["soort"] == "samenvatting" and k["samenvatting"]["bronnen"] == [
        "Artikel 2.1, lid 1 – Wet IB 2001 (deelvraag 1)", "Artikel 5.2, lid 1 – Wet IB 2001 (deelvraag 2)"]

    e = _beurt(settings, llm, "Maak aan", {"intake_id": k["intake_id"], "stap": "samenvatting", "actie": "aanmaken"})
    [aan] = [x for x in e if x["type"] == "werkgebied_aanmaken"]
    assert aan["werkgebied"]["naam"] == "Box 3" and aan["werkgebied"]["context"] == "De aangifte 2026 moet blijven werken."
    assert aan["werkgebied"]["deelvragen"] == [{"vraag": DV1, "herkomst": "lex"},
                                               {"vraag": "Telt een tweede huis mee?", "herkomst": "analist"}]
    assert aan["bronnen"] == [{"bron_iri": L21, "label": "Artikel 2.1, lid 1 – Wet IB 2001", "deelvragen": [DV1]},
                              {"bron_iri": L52, "label": "Artikel 5.2, lid 1 – Wet IB 2001",
                               "deelvragen": ["Telt een tweede huis mee?"]}]
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
    assert "2 deelvragen; 1 daarvan heeft de bronnen" in nep.berichten[0]["tekst"]
    # Nog eens: al gekoppeld, dus niets dubbel.
    _driver(monkeypatch, nep, [verzoek, {"type": "done"}])
    assert len(nep.gekoppeld) == 1


def test_de_afronding_belooft_alleen_wat_er_gekoppeld_is():
    """Fix 2 (F3f): de zin over koppelingen volgt wat de api werkelijk koppelde."""
    from agent.beurt import werkgebied_tekst

    wg = {"naam": "Box 3", "analysevraag": "Wie?", "deelvragen": [{"vraag": "Een?", "status": "actief"},
                                                                    {"vraag": "Twee?", "status": "actief"}]}
    niets = werkgebied_tekst(wg, [], [], 0)
    assert "als concept, nog zonder bronnen" in niets and "gekoppeld" not in niets and "koos" not in niets
    assert "Het heeft 2 deelvragen, nog zonder bronnen." in niets and "bepalingen zoeken bij de deelvragen" in niets
    deels = werkgebied_tekst(wg, ["Art. 1"], [], 1)
    assert "1 daarvan heeft de bronnen die je erbij koos, de rest nog geen." in deels
    alles = werkgebied_tekst(wg, ["Art. 1", "Art. 2"], [], 2)
    assert "elk heeft de bronnen die je erbij koos." in alles and "Een volgende stap" not in alles


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

def _tot_bepalingen(deelvragen=()):
    i = wi.nieuwe_intake("x")
    i, _ = wi.verwerk(i, _klik(i, "naam", tekst="Box 3"))
    for stap in ("aanleiding", "context", "doel"):
        i, _ = wi.verwerk(i, _klik(i, stap, actie="overslaan"))
    i, _ = wi.verwerk(i, _klik(i, "analysevraag", tekst="Wie?"))
    i, _ = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", actie="overslaan"))
    i, _ = wi.verwerk(i, _klik(i, "deelvragen", teksten=list(deelvragen)) if deelvragen
                      else _klik(i, "deelvragen", actie="overslaan"))
    i, _ = wi.verwerk(i, _klik(i, "buiten", actie="overslaan"))
    i = {**i, "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[IB]))
    return i


def test_terug_naar_een_eerdere_stap_met_het_antwoord_ingevuld():
    i = _tot_bepalingen()
    assert i["stap"] == "bepalingen"
    terug, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "bepalingen", "actie": "wijzig", "naar": "naam"})
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
    i = _tot_bepalingen()
    i = {**i, "stap": "regelingen"}
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "regelingen", "actie": "wijzig", "naar": "bepalingen"})[1] == "verouderd"
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "naam", "actie": "wijzig", "naar": "naam"})[1] == "verouderd"


def test_bladeren_tussen_de_bepalingen_per_deelvraag():
    i = _tot_bepalingen(["Eerste?", "Tweede?", "Derde?"])
    assert (i["stap"], i["deel"]) == ("bepalingen", 0)
    assert [wi.kaart({**i, "deel": n})["nr"] for n in range(3)] == [10, 11, 12] and wi.kaart(i)["totaal"] == 12
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", actie="overslaan"))
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", tekst="artikel 3.1"))
    assert i["deel"] == 2
    # Een klik op het kaartje van een ander deel is een oud kaartje.
    assert wi.verwerk(i, {**_klik(i, "bepalingen", tekst="x"), "deel": 1})[1] == "verouderd"
    # Terug naar een eerder deel mag, naar een later niet.
    terug, u = wi.verwerk(i, {**_klik(i, "bepalingen", actie="wijzig"), "naar": "bepalingen", "naar_deel": 1})
    assert (u, terug["deel"]) == ("verder", 1)
    k = wi.kaart(terug)
    assert k["vooringevuld"] == ["artikel 3.1"] and k["beantwoord"]
    assert wi.verwerk(terug, {**_klik(terug, "bepalingen", actie="wijzig"), "naar": "bepalingen", "naar_deel": 2})[1] == "verouderd"
    # Vanaf de samenvatting naar het laatste deel.
    i, _ = wi.verwerk(i, _klik(i, "bepalingen", actie="overslaan"))
    assert i["stap"] == "samenvatting"
    terug, _ = wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "wijzig", "naar": "bepalingen",
                              "naar_deel": 2})
    assert (terug["stap"], terug["deel"]) == ("bepalingen", 2) and wi.kaart(terug)["beantwoord"]
    # Een overgeslagen deelvraag laat geen regel achter; de artikelen bij één regeling worden een bron.
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: Wet inkomstenbelasting 2001.\nBepalingen: artikel 3.1."
    assert wi.bronnen(i["antwoorden"])[0]["deelvragen"] == ["Tweede?"]


def test_een_nieuwe_stap_is_nog_niet_beantwoord():
    i = _tot_bepalingen()
    k = wi.kaart(i)
    assert (k["beantwoord"], k["terug"]) == (False, True)


def test_omschrijving_van_een_regeling_uit_het_overzicht():
    r = {"soort": "wet", "delen": [{}, {}], "ook_genoemd": [{}]}
    assert wi._omschrijving_regeling(r, "box 3") == "wet · 2 delen over ‘box 3’ · 1 bepaling noemt het"


def test_een_intake_op_een_vervallen_stap_loopt_niet_meer():
    """Het agent-geheugen kan een intake van vóór F3f dragen (stap `onderdelen`): die is niet meer open, dus
    een volgende vraag begint opnieuw in plaats van op een onbekende stap te struikelen."""
    oud = {**wi.nieuwe_intake("x"), "stap": "onderdelen"}
    assert not wi.is_open(oud)
    assert wi.is_open({**oud, "stap": "bepalingen"}) and wi.is_open({**oud, "stap": "samenvatting"})
    assert not wi.is_open({**oud, "stap": "klaar"})


# --- Aanvullen: het dossier van een bestaand werkgebied ----------------------------------------------

WG = {"id": "wg1", "revisie": 4, "naam": "Box 3", "aanleiding": "Een wetswijziging raakt de heffing.", "context": "",
      "doel": "", "analysevraag": "Wie betaalt box 3?", "praktijkvoorbeeld": "",
      "afbakening": "Regelingen: Wet IB 2001.\nBuiten de afbakening: overgangsrecht.",
      "deelvragen": [{"id": "d1", "vraag": DV1, "status": "actief"}],
      "bronnen": [{"id": "s1", "label": "Artikel 5.2 – Wet IB 2001", "bron_iri": L52, "rol": "analyseren"}]}


@pytest.mark.parametrize("vraag,velden", [
    ("kun je praktijkvoorbeeld toevoegen?", ["praktijkvoorbeeld"]),
    ("Voeg een voorbeeld uit de praktijk toe", ["praktijkvoorbeeld"]),
    ("Pas de analysevraag en het doel aan", ["doel", "analysevraag"]),
    ("Wat is de hoofdvraag eigenlijk? Wijzig hem", ["analysevraag"]),
    ("Vul de aanleiding en de context in", ["aanleiding", "context"]),
    ("Wat valt erbuiten? Pas de afbakening aan", ["buiten"]),
    ("Geef het werkgebied een andere naam", ["naam"]),
    ("Vul het dossier aan", []),
    ("Wat ontbreekt er nog in het dossier?", []),
])
def test_welke_velden_de_vraag_noemt(vraag, velden):
    assert wi.dossiervelden_in(vraag) == velden


def test_de_beginstand_komt_uit_het_werkgebied():
    i = wi.aanvul_intake(WG, ["praktijkvoorbeeld", "naam"], "x")
    # Alleen het gevraagde, in de volgorde van het samenstellen; nooit deelvragen of bronnen.
    assert i["stappen"] == ["naam", "praktijkvoorbeeld"] and i["stap"] == "naam"
    assert i["modus"] == "aanvullen" and i["werkgebied_id"] == "wg1" and i["revisie"] == 4
    a = i["antwoorden"]
    # Aanleiding en doel als eigen tekst, de afbakening bij `buiten`: er gaat niets verloren.
    assert a["aanleiding"] == {"keuze": "", "tekst": WG["aanleiding"]} and a["buiten"] == WG["afbakening"]
    assert wi.als_werkgebied(i)["afbakening"] == WG["afbakening"]
    # Het dossier voor Lex draagt het hele werkgebied: ook de deelvragen en de bronnen.
    assert f"- {DV1}" in wi.dossier(i) and "Artikel 5.2 – Wet IB 2001" in wi.dossier(i)
    assert wi.lege_velden(WG) == ["context", "doel", "praktijkvoorbeeld"]
    with pytest.raises(ValueError):
        wi.aanvul_intake(WG, ["deelvragen", "regelingen"], "x")


def test_aanvullen_vraagt_alleen_het_gevraagde_vooringevuld():
    i = wi.aanvul_intake(WG, ["analysevraag", "praktijkvoorbeeld"], "x")
    k = wi.kaart(i)
    assert (k["modus"], k["stap"], k["nr"], k["totaal"], k["terug"]) == ("aanvullen", "analysevraag", 1, 2, False)
    assert k["vooringevuld"] == ["Wie betaalt box 3?"] and k["overslaanbaar"]
    i, uit = wi.verwerk(i, _klik(i, "analysevraag", tekst="Wie betaalt box 3 over 2026?"))
    k = wi.kaart(i)
    assert uit == "verder" and (k["stap"], k["nr"], k["totaal"], k["terug"]) == ("praktijkvoorbeeld", 2, 2, True)
    # Terug: de werkplek vraagt de vorige stap van het samenstellen (de analysevraag) – die is gevraagd.
    terug, uit = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", actie="wijzig", naar="analysevraag"))
    assert uit == "verder" and terug["stap"] == "analysevraag"
    i, _ = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", tekst="Een spaarder met een tweede huis."))
    assert i["stap"] == "samenvatting"
    # Vanaf de samenvatting vraagt de werkplek de bepalingen: dat wordt de laatste gevraagde stap.
    terug, uit = wi.verwerk(i, _klik(i, "samenvatting", actie="wijzig", naar="bepalingen"))
    assert uit == "verder" and terug["stap"] == "praktijkvoorbeeld"
    # Een stap die er niet bij hoort: een oud kaartje.
    assert wi.verwerk(i, _klik(i, "samenvatting", actie="wijzig", naar="naam"))[1] == "verouderd"


def test_overslaan_laat_het_veld_staan():
    i = wi.aanvul_intake(WG, ["naam", "analysevraag"], "x")
    i, uit = wi.verwerk(i, _klik(i, "naam", actie="overslaan"))
    assert uit == "verder" and i["antwoorden"]["naam"] == "Box 3" and i["stap"] == "analysevraag"
    i, _ = wi.verwerk(i, _klik(i, "analysevraag", actie="overslaan"))
    assert i["stap"] == "samenvatting" and wi.wijzigingen(i) == []


def test_de_samenvatting_toont_alleen_wat_verandert():
    i = wi.aanvul_intake(WG, ["aanleiding", "praktijkvoorbeeld"], "x")
    # De aanleiding ongewijzigd laten (de werkplek stuurt de vooringevulde tekst terug) is geen wijziging.
    i, _ = wi.verwerk(i, _klik(i, "aanleiding", tekst=WG["aanleiding"]))
    zonder = wi.kaart({**i, "stap": "samenvatting"})
    assert zonder["samenvatting"] == {"wijzigingen": []} and zonder["toelichting"] == "Er verandert niets."
    # Zonder wijziging valt er niets op te slaan.
    assert wi.verwerk({**i, "stap": "samenvatting"}, _klik({**i, "stap": "samenvatting"}, "samenvatting",
                                                           actie="opslaan"))[1] == "verouderd"
    i, _ = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", tekst="Een spaarder met een tweede huis."))
    k = wi.kaart(i)
    assert k["soort"] == "samenvatting" and k["modus"] == "aanvullen"
    assert k["samenvatting"]["wijzigingen"] == [{"veld": "praktijkvoorbeeld", "label": "Praktijkvoorbeeld",
                                                 "toen": "", "nu": "Een spaarder met een tweede huis."}]
    # Aanmaken hoort bij het samenstellen; opslaan geeft het event met alleen de gewijzigde velden.
    assert wi.verwerk(i, _klik(i, "samenvatting", actie="aanmaken"))[1] == "verouderd"
    klaar, uit = wi.verwerk(i, _klik(i, "samenvatting", actie="opslaan"))
    assert uit == "opslaan" and klaar["stap"] == "klaar"
    verzoek = wi.wijzigverzoek(klaar)
    assert (verzoek["werkgebied_id"], verzoek["verwachte_revisie"]) == ("wg1", 4)
    assert verzoek["wijziging"] == {"praktijkvoorbeeld": "Een spaarder met een tweede huis."}
    # Bij het samenstellen bestaat opslaan niet.
    s = {**wi.nieuwe_intake("x"), "stap": "samenvatting"}
    assert wi.verwerk(s, _klik(s, "samenvatting", actie="opslaan"))[1] == "verouderd"


def test_het_aanvulkaartje_volgt_het_api_contract():
    import importlib.util
    import sys
    from pathlib import Path

    pad = Path(__file__).parents[3] / "api" / "app" / "gesprek_contracts.py"
    spec = importlib.util.spec_from_file_location("gesprek_contracts_aanvullen", pad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    i = wi.aanvul_intake(WG, list(wi.DOSSIERSTAPPEN), "x")
    for stap in (*wi.DOSSIERSTAPPEN, "samenvatting"):
        k = mod.Vraagkaart.model_validate(wi.kaart({**i, "stap": stap}))
        assert k.modus == "aanvullen"
    assert mod.IntakeAntwoord(intake_id="ik1", stap="samenvatting", actie="opslaan").actie == "opslaan"


def test_een_nieuwe_stand_legt_de_antwoorden_ernaast():
    i = wi.aanvul_intake(WG, ["praktijkvoorbeeld"], "x")
    i, _ = wi.verwerk(i, _klik(i, "praktijkvoorbeeld", tekst="Een spaarder."))
    nieuw = wi.op_nieuwe_stand(i, {**WG, "revisie": 6, "context": "Na het Kerstarrest."})
    assert nieuw["id"] != i["id"] and nieuw["revisie"] == 6 and nieuw["stap"] == "samenvatting"
    assert nieuw["antwoorden"]["context"] == "Na het Kerstarrest." and nieuw["antwoorden"]["praktijkvoorbeeld"] == "Een spaarder."
    # Stond het al zo, dan verandert er niets.
    assert wi.wijzigingen(wi.op_nieuwe_stand(i, {**WG, "revisie": 6, "praktijkvoorbeeld": "Een spaarder."})) == []


class AanvulApi:
    """De api voor de node (ophalen) en de driver (PATCH, met de revisietoets)."""

    def __init__(self, wg=None, patch_status=0):
        self.wg = dict(wg or WG)
        self.patch_status = patch_status
        self.gewijzigd: list[dict[str, Any]] = []
        self.berichten: list[dict[str, Any]] = []

    async def haal_werkgebied(self, wid):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if wid != self.wg["id"]:
            raise WetsanalyseApiFout("GET → 404", 404)
        return dict(self.wg)

    async def wijzig_werkgebied(self, wid, wijziging):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if self.patch_status:
            raise WetsanalyseApiFout("PATCH → x", self.patch_status)
        if wijziging["verwachte_revisie"] != self.wg["revisie"]:
            raise WetsanalyseApiFout("PATCH → 412", 412)
        self.gewijzigd.append(wijziging)
        self.wg.update({k: v for k, v in wijziging.items() if k != "verwachte_revisie"}, revisie=self.wg["revisie"] + 1)
        return dict(self.wg)

    async def voeg_bericht_toe(self, gid, bericht):
        self.berichten.append(bericht)
        return {}

    async def aclose(self):
        pass


def _aanvulbeurt(settings, llm, nep, vraag, klik=None, cid="ga", **kw):
    from agent.agent import answer_stream
    from agent.models import IntakeActie

    async def run():
        return [e async for e in answer_stream(vraag, cid, settings=settings, llm=llm, graph=FakeGraph(),
                                               werkgebied_id="wg1", agent_api=lambda s, u: nep, user_id="u",
                                               intake_actie=IntakeActie(**klik) if klik else None, **kw)]
    return asyncio.run(run())


def _aanvulsettings(tmp_path):
    return make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"),
                         wetsanalyse_api_url="http://api", wetsanalyse_api_token="t")


def test_kun_je_praktijkvoorbeeld_toevoegen_vraagt_het_zonder_model(tmp_path):
    """De aanleiding van dit plan: de supervisor kiest het aanvullen, en het praktijkvoorbeeld verzint Lex niet –
    na de supervisor geen enkele modelaanroep."""
    settings = _aanvulsettings(tmp_path)
    nep = AanvulApi()
    llm = FakeLLM([response([text_block("WORKERS: werkgebied\nSPECIALIST: algemeen\nTAAK: aanvullen\nPLAN: dossier")], "end_turn")])
    e = _aanvulbeurt(settings, llm, nep, "kun je praktijkvoorbeeld toevoegen?")
    k = _kaart(e)
    assert (k["modus"], k["stap"], k["totaal"], k["vooringevuld"]) == ("aanvullen", "praktijkvoorbeeld", 1, [])
    assert len(llm.calls) == 1 and "deelvragen" not in json.dumps([x for x in e if x["type"] == "status"])
    assert any("vult het dossier aan" in x.get("message", "") for x in e if x["type"] == "status")
    a = {"intake_id": k["intake_id"], "stap": "praktijkvoorbeeld", "tekst": "Een spaarder met een tweede huis."}
    k = _kaart(_aanvulbeurt(settings, FakeLLM([]), nep, "Een spaarder met een tweede huis.", a))
    assert k["soort"] == "samenvatting" and k["samenvatting"]["wijzigingen"][0]["toen"] == ""
    opslaan = {"intake_id": k["intake_id"], "stap": "samenvatting", "actie": "opslaan"}
    e = _aanvulbeurt(settings, FakeLLM([]), nep, "Sla het op.", opslaan)
    [ev] = [x for x in e if x["type"] == "werkgebied_wijzigen"]
    assert ev["wijziging"] == {"praktijkvoorbeeld": "Een spaarder met een tweede huis."} and ev["verwachte_revisie"] == 4


def test_de_actie_vult_de_lege_velden_aan_en_een_vol_dossier_zegt_dat(tmp_path):
    settings = _aanvulsettings(tmp_path)
    # Zonder genoemd veld de lege velden; de context heeft geen voorstel, dus geen modelaanroep.
    e = _aanvulbeurt(settings, FakeLLM([]), AanvulApi(), "Vul het dossier aan", actie="dossier_aanvullen")
    k = _kaart(e)
    assert (k["stap"], k["totaal"]) == ("context", 3)
    assert "Er ontbreekt nog: context, doel en praktijkvoorbeeld." in _tekst(e)
    vol = {**WG, "context": "c", "doel": "d", "praktijkvoorbeeld": "p"}
    e = _aanvulbeurt(settings, FakeLLM([]), AanvulApi(vol), "Vul het dossier aan", actie="dossier_aanvullen", cid="gv")
    assert not [x for x in e if x["type"] == "vraagkaart"]
    assert "staat alles al ingevuld" in _tekst(e) and "Analysevraag: Wie betaalt box 3?" in _tekst(e)


def test_zonder_werkgebied_of_als_het_weg_is_zegt_lex_het(tmp_path):
    from agent.agent import answer_stream

    settings = _aanvulsettings(tmp_path)
    weg = _aanvulbeurt(settings, FakeLLM([]), AanvulApi({**WG, "id": "ander"}), "Vul het dossier aan",
                       actie="dossier_aanvullen")
    assert "bestaat niet meer" in _tekst(weg)
    from agent.nodes.werkgebied import ZONDER_WERKGEBIED

    async def zonder():
        llm = FakeLLM([response([text_block("WORKERS: werkgebied\nTAAK: aanvullen\nPLAN: x")], "end_turn")])
        return [e async for e in answer_stream("kun je het praktijkvoorbeeld toevoegen?", "gz", settings=settings,
                                               llm=llm, graph=FakeGraph(), agent_api=lambda s, u: AanvulApi())]
    assert _tekst(asyncio.run(zonder())) == ZONDER_WERKGEBIED


def test_opslaan_op_een_gewijzigd_werkgebied_legt_je_antwoord_naast_de_nieuwe_stand(tmp_path):
    settings = _aanvulsettings(tmp_path)
    nep = AanvulApi()
    llm = FakeLLM([response([text_block("WORKERS: werkgebied\nTAAK: aanvullen\nPLAN: x")], "end_turn")])
    k = _kaart(_aanvulbeurt(settings, llm, nep, "Voeg een praktijkvoorbeeld toe"))
    k = _kaart(_aanvulbeurt(settings, FakeLLM([]), nep, "x",
                            {"intake_id": k["intake_id"], "stap": "praktijkvoorbeeld", "tekst": "Een spaarder."}))
    nep.wg.update(revisie=5, context="Iemand anders schreef dit.")
    e = _aanvulbeurt(settings, FakeLLM([]), nep, "Sla het op.",
                     {"intake_id": k["intake_id"], "stap": "samenvatting", "actie": "opslaan"})
    assert not [x for x in e if x["type"] == "werkgebied_wijzigen"] and "intussen gewijzigd" in _tekst(e)
    nieuw = _kaart(e)
    assert nieuw["intake_id"] != k["intake_id"] and nieuw["samenvatting"]["wijzigingen"][0]["nu"] == "Een spaarder."
    e = _aanvulbeurt(settings, FakeLLM([]), nep, "Sla het op.",
                     {"intake_id": nieuw["intake_id"], "stap": "samenvatting", "actie": "opslaan"})
    [ev] = [x for x in e if x["type"] == "werkgebied_wijzigen"]
    assert ev["verwachte_revisie"] == 5


VERZOEK_WIJZIG = {"type": "werkgebied_wijzigen", "werkgebied_id": "wg1", "verwachte_revisie": 4,
                  "wijziging": {"praktijkvoorbeeld": "Een spaarder."},
                  "wijzigingen": [{"veld": "praktijkvoorbeeld", "label": "Praktijkvoorbeeld", "toen": "",
                                   "nu": "Een spaarder."}],
                  "kaart": {"intake_id": "ik1", "stap": "samenvatting", "soort": "samenvatting", "modus": "aanvullen"}}


def test_de_driver_wijzigt_het_werkgebied_na_opslaan(monkeypatch):
    nep = AanvulApi()
    uit = _driver(monkeypatch, nep, [dict(VERZOEK_WIJZIG), {"type": "done"}])
    assert nep.gewijzigd == [{"verwachte_revisie": 4, "praktijkvoorbeeld": "Een spaarder."}]
    [bericht] = nep.berichten
    assert bericht["artefact"] == {"soort": "werkgebied", "titel": "Box 3", "ref": {"werkgebied_id": "wg1"}}
    assert "praktijkvoorbeeld ingevuld" in bericht["tekst"]
    assert [e for e in uit if e["type"] == "opgeslagen"][0]["artefact"] == bericht["artefact"]


def test_de_driver_bij_412_en_404_niets_opgeslagen_en_zegt_waarom(monkeypatch):
    nep = AanvulApi({**WG, "revisie": 5})
    uit = _driver(monkeypatch, nep, [dict(VERZOEK_WIJZIG), {"type": "done"}])
    [bericht] = nep.berichten
    assert not nep.gewijzigd and "Iemand anders wijzigde het werkgebied net" in bericht["tekst"]
    # Het samenvattingskaartje komt terug, zodat opnieuw opslaan kan.
    assert bericht["vraagkaart"] == VERZOEK_WIJZIG["kaart"] and "artefact" not in bericht
    assert [e["vraagkaart"] for e in uit if e["type"] == "vraagkaart"] == [VERZOEK_WIJZIG["kaart"]]
    nep = AanvulApi(patch_status=404)
    _driver(monkeypatch, nep, [dict(VERZOEK_WIJZIG), {"type": "done"}])
    assert "bestaat niet meer" in nep.berichten[0]["tekst"]


def test_de_driver_een_andere_fout_is_zichtbaar(monkeypatch):
    nep = AanvulApi(patch_status=503)
    uit = _driver(monkeypatch, nep, [dict(VERZOEK_WIJZIG), {"type": "done"}])
    assert [e.get("foutcode") for e in uit if e["type"] == "error"] == ["werkgebied_niet_gewijzigd"]
    assert not nep.berichten and uit[-1]["type"] == "done"


def test_dossier_aanvullen_is_een_actie_zonder_agent():
    from agent.models import ACTIE_TAAK, INTAKE_ACTIES

    r = ChatRequest(question="Vul het praktijkvoorbeeld aan", actie="dossier_aanvullen",
                    onderwerp={"soort": "werkgebied", "werkgebied_id": "wg1"})
    assert r.werkgebied_id == "wg1" and r.modus == "auto" and "dossier_aanvullen" in INTAKE_ACTIES
    assert "dossier_aanvullen" not in ACTIE_TAAK
    with pytest.raises(Exception, match="werkgebied_id"):
        ChatRequest(question="x", actie="dossier_aanvullen")
