"""Het overzicht van een onderwerp: herkenning, afbakening, samenstelling en vaste volgorde.

De rijen volgen de vorm van de echte graaf op 8 okt 2026 (`Welke artikelen gaan over invordering?`):
Iw H II/V/VII als delen, art. 31 en 63 binnen H V en H VII (Lex schreef dat ze erbuiten vielen), art. 4
in H I, en paragraaf 4.4.4.2 binnen afdeling 4.4.4.
"""
from __future__ import annotations

import json

import pytest

from agent import overzicht
from agent.resultaat import BUDGET, is_contract
from fakes import FakeGraph

IW, AWB, LEIDRAAD = "urn:bwb:BWBR0004770", "urn:bwb:BWBR0005537", "urn:bwb:BWBR0024096"
H2, H5, H7, H1 = (f"{IW}:hoofdstuk:{h}" for h in ("II", "V", "VII", "I"))
AFD = f"{AWB}:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.4"
PAR = f"{AFD}:paragraaf:4.4.4.2"
L28 = f"{LEIDRAAD}:artikel:28"


def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


DELEN = _tsv(["node", "score", "soort", "label", "nummer", "jci", "bwbId", "citeertitel", "bronlabel"], [
    [L28, "2.7", "Divisie", "Invorderingsrente", "28", "", "BWBR0024096", "Leidraad Invordering 2008", "Artikel 28"],
    [H5, "2.7", "Hoofdstuk", "Hoofdstuk V – Invorderingsrente", "V", "", "BWBR0004770", "Invorderingswet 1990", "Hoofdstuk"],
    [H2, "3.0", "Hoofdstuk", "Hoofdstuk II – Invordering in eerste aanleg", "II", "", "BWBR0004770", "Invorderingswet 1990", "Hoofdstuk"],
    [PAR, "3.4", "Paragraaf", "Paragraaf 4.4.4.2 – Invordering bij dwangbevel", "4.4.4.2", "", "BWBR0005537", "Algemene wet bestuursrecht", "Paragraaf"],
    [AFD, "3.0", "Afdeling", "Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel", "4.4.4", "", "BWBR0005537", "Algemene wet bestuursrecht", "Afdeling"],
    [H7, "2.7", "Hoofdstuk", "Hoofdstuk VII – Verplichtingen ten behoeve van de invordering", "VII", "", "BWBR0004770", "Invorderingswet 1990", "Hoofdstuk"],
])
IN_DELEN = _tsv(["deel", "bepaling", "nummer", "label", "bronlabel"], [
    [H2, f"{IW}:artikel:10", "10", "Artikel 10", "Artikel 10"], [H2, f"{IW}:artikel:8", "8", "Artikel 8", "Artikel 8"],
    [H2, f"{IW}:artikel:9", "9", "Artikel 9", "Artikel 9"],
    [H5, f"{IW}:artikel:31", "31", "Artikel 31", "Artikel 31"], [H5, f"{IW}:artikel:27quinquies", "27quinquies", "Artikel 27quinquies", "Artikel 27quinquies"],
    [H5, f"{IW}:artikel:27a", "27a", "Artikel 27a", "Artikel 27a"],
    [H7, f"{IW}:artikel:63", "63", "Artikel 63", "Artikel 63"],
    [AFD, f"{AWB}:artikel:4%3A124", "4:124", "Artikel 4:124", "Artikel 4:124"], [AFD, f"{AWB}:artikel:4%3A112", "4:112", "Artikel 4:112", "Artikel 4:112"],
    [L28, f"{LEIDRAAD}:artikel:28.3a", "28.3a", "Vermindering", "Artikel 28.3a"], [L28, f"{LEIDRAAD}:id:x28.1", "28.1", "Cheque", "28.1"],
])
TREFFERS = _tsv(["bepaling", "beste", "label", "nummer", "jci", "bwbId", "citeertitel"], [
    [f"{IW}:artikel:31", "2.0", "Artikel 31", "31", "", "BWBR0004770", "Invorderingswet 1990"],
    [f"{IW}:artikel:63", "1.9", "Artikel 63", "63", "", "BWBR0004770", "Invorderingswet 1990"],
    [f"{IW}:artikel:4", "1.8", "Artikel 4", "4", "", "BWBR0004770", "Invorderingswet 1990"],
    [f"{AWB}:artikel:4%3A124", "1.7", "Artikel 4:124", "4:124", "", "BWBR0005537", "Algemene wet bestuursrecht"],
    [f"{AWB}:artikel:4%3A94a", "1.6", "Artikel 4:94a", "4:94a", "", "BWBR0005537", "Algemene wet bestuursrecht"],
    [L28, "1.5", "Invorderingsrente", "28", "", "BWBR0024096", "Leidraad Invordering 2008"],
])
PLAATS = _tsv(["bepaling", "deel", "soort", "label"], [
    [PAR, AFD, "Afdeling", "Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel"],
    [f"{IW}:artikel:31", H5, "Hoofdstuk", "Hoofdstuk V – Invorderingsrente"],
    [f"{IW}:artikel:63", H7, "Hoofdstuk", "Hoofdstuk VII – Verplichtingen ten behoeve van de invordering"],
    [f"{IW}:artikel:4", H1, "Hoofdstuk", "Hoofdstuk I – Algemene bepalingen"],
    [f"{AWB}:artikel:4%3A124", AFD, "Afdeling", "Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel"],
    [f"{AWB}:artikel:4%3A94a", f"{AWB}:hoofdstuk:4", "Hoofdstuk", "Hoofdstuk 4"],
    [f"{AWB}:artikel:4%3A94a", f"{AWB}:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.1", "Afdeling", "Afdeling 4.4.1 – Vaststelling"],
])
DEFINITIES = _tsv(["node", "begrip", "label", "tekst", "jci", "bwbId", "citeertitel"], [
    [f"{IW}:artikel:2:lid:2:o:e", "invorderen van rijksbelastingen", "Onderdeel e.", "invorderen: …", "", "BWBR0004770", "Invorderingswet 1990"],
])
TREFWOORDEN = _tsv(["concept", "label", "regeling", "bwbId", "citeertitel"], [
    ["urn:bwb:begrip:invorderingsrecht", "Invorderingsrecht", IW, "BWBR0004770", "Invorderingswet 1990"],
])
REGELINGEN = _tsv(["regeling", "citeertitel", "soort", "afkortingen"], [
    [IW, "Invorderingswet 1990", "wet", "IW 1990 | Iw"],
    [AWB, "Algemene wet bestuursrecht", "wet", "Awb"],
    [LEIDRAAD, "Leidraad Invordering 2008", "beleidsregel", "Leidr. Inv."],
])


class Graaf(FakeGraph):
    """Antwoordt per soort query; `leeg_bij` laat een zoekterm niets opleveren (voor de terugval)."""

    def __init__(self, leeg_bij: tuple[str, ...] = ()) -> None:
        super().__init__(results=self._antwoord)
        self.leeg_bij = leeg_bij

    def _antwoord(self, q: str) -> str:
        if any(w in q for w in self.leeg_bij):
            return "?node\n"
        if "?afkortingen" in q:
            return REGELINGEN
        if "dct:subject" in q:
            return TREFWOORDEN
        if "definieertBegrip:(" in q:
            return DEFINITIES
        if "VALUES ?deel" in q:
            return IN_DELEN
        if "VALUES ?bepaling" in q:
            return PLAATS
        if "tekst:(" in q:
            return TREFFERS
        if "titel:(" in q:
            return DELEN
        if "bwb:opschrift" in q:            # regelingnamen in finalize
            return "?r\t?citeertitel\t?opschrift\n"
        raise AssertionError(f"onverwachte query: {q[:200]}")


@pytest.fixture(autouse=True)
def _verse_cache():
    overzicht._REGELINGEN_CACHE.clear()
    yield
    overzicht._REGELINGEN_CACHE.clear()


# --- Herkennen -------------------------------------------------------------------------------------

@pytest.mark.parametrize(("vraag", "onderwerp"), [
    ("Welke artikelen gaan over invordering?", "invordering"),
    ("welke bepalingen gaan over de aansprakelijkheid van bestuurders", "aansprakelijkheid van bestuurders"),
    ("Welke artikelen in de Invorderingswet gaan over aansprakelijkheid?", "aansprakelijkheid"),
    ("Welke hoofdstukken hebben betrekking op kwijtschelding?", "kwijtschelding"),
    ("Welke artikelen regelen het uitstel van betaling?", "uitstel van betaling"),
    ("Waar is de invordering geregeld?", "invordering"),
    ("Waar wordt kwijtschelding geregeld in de Awb?", "kwijtschelding"),
    ("Geef een overzicht van de bepalingen over invordering", "invordering"),
    ("Overzicht van invorderingsrente", "invorderingsrente"),
])
def test_herkent_een_overzichtsvraag(vraag: str, onderwerp: str):
    assert overzicht.is_overzichtsvraag(vraag)
    assert overzicht.onderwerp_uit(vraag) == onderwerp


@pytest.mark.parametrize("vraag", [
    "Wat regelt artikel 9 van de Invorderingswet?",
    "Wat is invordering?",
    "Annoteer artikel 25 lid 1 van de Invorderingswet",
    "Welke rechtssubjecten kennen we al in de annotaties?",
    "Welke artikelen gaan over",
    "Hoe werkt een dwangbevel?",
])
def test_herkent_geen_andere_vraag(vraag: str):
    assert not overzicht.is_overzichtsvraag(vraag)


# --- Samenstellen ----------------------------------------------------------------------------------

def _per_regeling(ov: dict) -> dict:
    return {r["bwb_id"]: r for r in ov["regelingen"]}


def test_een_bepaling_binnen_een_gevonden_deel_staat_niet_los():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    iw = _per_regeling(ov)["BWBR0004770"]
    los = [b["nummer"] for b in iw["ook_genoemd"]]
    assert "31" not in los and "63" not in los, "art. 31 en 63 vallen binnen H V en H VII"
    assert los == ["4"]
    assert iw["ook_genoemd"][0]["in_deel"] == {"iri": H1, "label": "Hoofdstuk I – Algemene bepalingen"}
    # Een gevonden deel als teksttreffer (Leidraad 28) staat ook niet los.
    assert _per_regeling(ov)["BWBR0024096"]["ook_genoemd"] == []


def test_ook_genoemd_krijgt_het_meest_specifieke_deel():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    awb = _per_regeling(ov)["BWBR0005537"]
    [b] = awb["ook_genoemd"]
    assert b["nummer"] == "4:94a" and b["in_deel"]["label"] == "Afdeling 4.4.1 – Vaststelling"


def test_een_genest_deel_hoort_bij_zijn_ouder():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    [afd] = _per_regeling(ov)["BWBR0005537"]["delen"]
    assert afd["iri"] == AFD
    assert afd["subdelen"] == [{"iri": PAR, "label": "Paragraaf 4.4.4.2 – Invordering bij dwangbevel"}]


def test_vaste_volgorde_rang_documentvolgorde_en_alle_nummers():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    assert [r["bwb_id"] for r in ov["regelingen"]] == ["BWBR0004770", "BWBR0005537", "BWBR0024096"], \
        "wetten vóór de beleidsregel, en binnen de wetten wie de meeste bepalingen in delen heeft"
    iw = _per_regeling(ov)["BWBR0004770"]
    assert [d["iri"] for d in iw["delen"]] == [H2, H5, H7], "documentvolgorde, niet de zoekscore"
    assert [b["nummer"] for b in iw["delen"][0]["bepalingen"]] == ["8", "9", "10"]
    assert [b["nummer"] for b in iw["delen"][1]["bepalingen"]] == ["27a", "27quinquies", "31"]
    leidraad = _per_regeling(ov)["BWBR0024096"]
    assert [b["nummer"] for b in leidraad["delen"][0]["bepalingen"]] == ["28.1", "28.3a"], "geen bereik: 28.3a staat erin"


def test_definitie_en_trefwoord():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    assert ov["definities"][0]["begrip"] == "invorderen van rijksbelastingen"
    assert ov["trefwoorden"] == [{"trefwoord": "Invorderingsrecht",
                                  "regelingen": [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}]}]


def test_dezelfde_vraag_geeft_hetzelfde_overzicht():
    a = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    b = overzicht.bouw_overzicht(Graaf(), "Waar is de invordering geregeld?")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_een_genoemde_regeling_bakent_af_en_is_geen_zoekwoord():
    g = Graaf()
    ov = overzicht.bouw_overzicht(g, "Welke artikelen in de Invorderingswet gaan over invordering?")
    assert ov["scope"] == ["BWBR0004770"]
    assert [r["bwb_id"] for r in ov["regelingen"]] == ["BWBR0004770"]
    assert ov["gevraagd"] == "invordering"


def test_opbouw_en_tekst_vallen_elk_apart_terug():
    # Geen opschrift met "belasting": de delen komen van "invordering", de tekst van het hele onderwerp.
    g = Graaf(leeg_bij=("titel:((invordering OR *invorder*) AND",))
    ov = overzicht.bouw_overzicht(g, "Welke bepalingen gaan over invordering van belastingen?")
    assert ov["onderwerp_opbouw"] == "invordering"
    assert ov["onderwerp_tekst"] == "invordering belastingen"
    assert ov["regelingen"][0]["delen"], "de kern blijft"


def test_voor_model_is_een_contract_binnen_de_begroting_zonder_nummerlijsten():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    tekst = overzicht.voor_model(ov)
    data = is_contract(tekst)
    assert data and len(tekst) <= BUDGET
    assert "27quinquies" not in tekst, "de nummers toont de werkplek; het model typt ze niet over"
    assert data["volledig"] and data["resultaten"][0] == {
        "regeling": "Invorderingswet 1990", "bwb_id": "BWBR0004770",
        "deel": "Hoofdstuk II – Invordering in eerste aanleg", "iri": H2, "bepalingen": 3}
    ook = next(r for r in data["resultaten"] if r.get("ook_genoemd") and r["bwb_id"] == "BWBR0004770")
    assert ook["vooral_in"] == ["Hoofdstuk I – Algemene bepalingen"]


def test_bronrijen_noemen_elke_vindplaats_van_het_overzicht():
    from agent.provenance import collect_sources

    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    uris = {s.uri for s in collect_sources([("overzicht", overzicht.bronrijen(ov))])}
    assert {H2, H5, H7, AFD, L28, f"{IW}:artikel:4", f"{AWB}:artikel:4%3A94a", f"{IW}:artikel:2:lid:2:o:e"} <= uris
    assert f"{IW}:artikel:31" not in uris, "een bepaling binnen een deel is geen aparte bron"


# --- In de keten -----------------------------------------------------------------------------------

def _beurt(vraag: str, *antwoorden: str):
    import asyncio

    from agent.agent import answer_stream
    from fakes import FakeLLM, make_settings, response, text_block

    llm = FakeLLM([response([text_block(a)], "end_turn") for a in antwoorden])

    async def run():
        return [e async for e in answer_stream(vraag, settings=make_settings(enable_decomposition=False),
                                               llm=llm, graph=Graaf())]
    return asyncio.run(run()), llm


def _een(events, soort):
    return next(e for e in events if e["type"] == soort)


def _tekst(events) -> str:
    return "".join(e["content"] for e in events if e["type"] == "token")


def test_de_route_bouwt_het_overzicht_zonder_model():
    events, llm = _beurt("Welke artikelen gaan over invordering?")
    assert len(llm.calls) == 0, "geen supervisor-call, geen tool-keuze en geen duiding door het model"
    ov = _een(events, "overzicht")["overzicht"]
    assert [r["bwb_id"] for r in ov["regelingen"]] == ["BWBR0004770", "BWBR0005537", "BWBR0024096"]
    assert _tekst(events) == overzicht.samenvatting(ov)
    uitvoering = [e for e in events if e["type"] == "tool_execution" and e["tool"] == "overzicht_onderwerp"]
    assert {e["phase"] for e in uitvoering} == {"start", "end"}
    bronnen = {b["uri"] for b in _een(events, "sources")["sources"]}
    assert {H2, H5, H7, AFD, f"{IW}:artikel:4"} <= bronnen
    assert _een(events, "grounding")["niveau"] == "gegrond", "de koppen in de tekst zijn getoetst"


def test_mislukt_het_bouwen_dan_zegt_het_model_dat():
    import asyncio

    from agent.agent import answer_stream
    from fakes import FakeLLM, make_settings, response, text_block

    class Kapot(Graaf):
        def _antwoord(self, q: str) -> str:
            if "titel:(" in q:
                raise RuntimeError("graaf weg")
            return super()._antwoord(q)

    llm = FakeLLM([response([text_block("Het overzicht kon niet uit de graaf worden opgebouwd.")], "end_turn")])

    async def run():
        return [e async for e in answer_stream("Welke artikelen gaan over invordering?",
                                               settings=make_settings(enable_decomposition=False), llm=llm, graph=Kapot())]
    events = asyncio.run(run())
    assert not [e for e in events if e["type"] == "overzicht"], "geen half overzicht"
    assert len(llm.calls) == 1 and "overzicht_niet_opgebouwd" in json.dumps(llm.calls[0]["messages"])
    assert _tekst(events) == "Het overzicht kon niet uit de graaf worden opgebouwd."


def test_andere_formulering_zelfde_overzicht_tekst_en_bronnen():
    a, _ = _beurt("Welke artikelen gaan over invordering?")
    b, _ = _beurt("Waar is de invordering geregeld?")
    assert _een(a, "overzicht") == _een(b, "overzicht")
    assert _tekst(a) == _tekst(b)
    assert _een(a, "sources") == _een(b, "sources")


def test_een_gewone_vraag_krijgt_geen_overzicht():
    from agent.overzicht import is_overzichtsvraag
    assert not is_overzichtsvraag("Wat regelt artikel 9?")


def test_de_eval_scoort_het_overzicht_zelf():
    from eval.scoring import overzicht_ok

    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    assert overzicht_ok(ov, {"delen": [H2, H5], "niet_los": [f"{IW}:artikel:31"]})
    assert not overzicht_ok(ov, {"delen": [f"{IW}:hoofdstuk:IX"]}), "een verwacht deel ontbreekt"
    assert not overzicht_ok(ov, {"niet_los": [f"{IW}:artikel:4"]}), "art. 4 staat wél los"
    assert not overzicht_ok(None, {"delen": [H2]}), "geen overzicht waar er een hoort"
    assert overzicht_ok(None, None), "een gewone vraag heeft geen eis"


def test_namen_staan_in_de_data():
    """Eén plek voor hoe een deel en een bepaling heten: het blok en de samenvatting lezen ze, en de
    werkplek leidt niets meer af uit de IRI-vorm."""
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    per = _per_regeling(ov)
    leidraad = per["BWBR0024096"]["delen"][0]
    assert leidraad["kop"] == "28 – Invorderingsrente"
    assert [b["naam"] for b in leidraad["bepalingen"]] == ["28.1", "art. 28.3a"], "zoals de bron ze noemt, ook waar die wisselt"
    assert leidraad["soortwoord"] == "artikel" and per["BWBR0004770"]["delen"][0]["soortwoord"] == "hoofdstuk"
    assert per["BWBR0004770"]["delen"][0]["kop"] == "Hoofdstuk II – Invordering in eerste aanleg"
    assert [b["naam"] for b in per["BWBR0004770"]["delen"][0]["bepalingen"]] == ["art. 8", "art. 9", "art. 10"]
    assert per["BWBR0005537"]["ook_genoemd"][0]["naam"] == "art. 4:94a"
    assert ov["definities"][0]["vindplaats"] == "Artikel 2, lid 2, onderdeel e"


def test_de_samenvatting_komt_uit_de_data_en_doorstaat_de_controle():
    from agent.grounding import check_grounding

    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    tekst = overzicht.samenvatting(ov)
    assert tekst.startswith("„Invordering” staat vooral in de **Invorderingswet 1990**: 3 hoofdstukken met 7 artikelen "
                            "(Hoofdstuk II – Invordering in eerste aanleg; Hoofdstuk V – Invorderingsrente; "
                            "Hoofdstuk VII – Verplichtingen ten behoeve van de invordering).")
    assert "Verder in de Algemene wet bestuursrecht (Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel) " \
           "en de Leidraad Invordering 2008 (28 – Invorderingsrente)." in tekst
    assert "De Invorderingswet 1990 definieert „invorderen van rijksbelastingen” in artikel 2, lid 2, onderdeel e." in tekst
    assert overzicht.samenvatting(ov) == tekst, "dezelfde data, dezelfde tekst"
    rapport = check_grounding(tekst, [("overzicht_onderwerp", overzicht.bronrijen(ov))], overzicht=ov)
    assert rapport.niveau == "gegrond" and "Hoofdstuk II" in rapport.cited and "afdeling 4.4.4" in [c.casefold() for c in rapport.cited]


def test_de_controle_toetst_ook_delen():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    assert overzicht.vermeldingen_buiten("Zie Hoofdstuk V en afdeling 4.4.4.", ov) == []
    assert overzicht.vermeldingen_buiten("Zie Hoofdstuk I, waar art. 4 staat.", ov) == [], "het deel van 'ook genoemd'"
    assert overzicht.vermeldingen_buiten("Zie Hoofdstuk XII en Titel 5.4.", ov) == ["Hoofdstuk XII", "Titel 5.4"]


def test_samenvatting_zonder_delen_en_met_afbakening():
    ov = overzicht.bouw_overzicht(Graaf(), "Welke artikelen gaan over invordering?")
    zonder = {**ov, "regelingen": [{**r, "delen": []} for r in ov["regelingen"]]}
    tekst = overzicht.samenvatting(zonder)
    assert tekst.startswith("Geen hoofdstuk, afdeling, paragraaf of divisie draagt „invordering” in zijn opschrift.")
    assert "Het onderwerp staat wel in de tekst van 2 bepalingen in 2 regelingen" in tekst
    binnen = overzicht.bouw_overzicht(Graaf(), "Welke artikelen in de Awb gaan over invordering?")
    assert overzicht.samenvatting(binnen).startswith(
        "Binnen de Algemene wet bestuursrecht staat „invordering” vooral in Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel: 2 artikelen.")
    leeg = {**ov, "regelingen": []}
    assert overzicht.samenvatting(leeg) == "In de kennisgraaf staat geen deel of bepaling over „invordering”."


def test_de_telling_spreekt_de_taal_van_de_bron():
    from agent.overzicht import _bepalingen_geteld, _delen_geteld

    deel = lambda woord, *namen: {"soortwoord": woord, "bepalingen": [{"naam": n} for n in namen]}
    assert _delen_geteld([deel("hoofdstuk")] * 4 + [deel("afdeling")]) == "4 hoofdstukken en 1 afdeling"
    assert _delen_geteld([deel("artikel")] * 8) == "8 artikelen"
    assert _delen_geteld([deel("paragraaf")]) == "1 paragraaf"
    from agent.overzicht import soortwoord
    assert soortwoord("Divisie", "Artikel 28") == "artikel"
    assert soortwoord("Divisie", "26.5") == "artikel", "een divisie met alleen een nummer telt als artikel"
    assert soortwoord("Hoofdstuk", "Hoofdstuk") == "hoofdstuk"
    assert _bepalingen_geteld([deel("hoofdstuk", "art. 8", "art. 9")]) == "2 artikelen"
    assert _bepalingen_geteld([deel("artikel", "28.1", "art. 28.3a")]) == "2 bepalingen", "de Leidraad wisselt"
