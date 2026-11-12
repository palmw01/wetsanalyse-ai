"""Bronnen naast de wet in het antwoord (ADR-008 + ADR-013): het blok `extern`, als subsjabloon en als eigen sjabloon.

De echte leestool (`get_kamerstuk` tegen een nepbron) levert de trace, zodat het contract van een leestool hier
meetelt: `stuk: {id, label, link, bron_hash, gewijzigd?}` en rijen `{nr, tekst, kop?}`. Het model wijst alleen het stuk en de alinea's aan.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from bronmodel.antwoord import Antwoord, antwoord_tekst
from bronmodel.connectors import CONNECTORS

from agent import sjablonen, tools
from agent.agent import answer_stream
from agent.config import Settings
from agent.grounding import check_grounding
from agent.sjablonen import extern
from agent.sjablonen.vullen import Onvulbaar
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_kamerstuk_tools import DOSSIER, NepBron

AAN = Settings(connector_kamerstukken=True)
ID = "kst-99001-3"


def _lees(naam: str, args: dict) -> tuple[str, str]:
    return naam, tools.dispatch(naam, None, args, AAN, kamerstukken=NepBron(DOSSIER))


TRACE = [_lees("zoek_kamerstukken", {"dossier": "99001"}), _lees("get_kamerstuk", {"id": ID})]


def test_de_leestool_houdt_zich_aan_het_contract():
    data = json.loads(TRACE[1][1])
    assert {"id", "label", "link"} <= set(data["stuk"])
    assert all(isinstance(r["nr"], int) and isinstance(r["tekst"], str) for r in data["resultaten"])


def test_het_eigen_sjabloon_neemt_de_tekst_uit_de_bron():
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "De MvT legt het doel uit.",
                                          "extern": [{"id": ID, "van_nr": 1, "tot_nr": 3}], "twijfel": []}, TRACE)
    assert a.sjabloon == "extern"
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert blok.door == "bron" and blok.brontype == "kamerstuk" and blok.kop == "Uit de parlementaire geschiedenis"
    # De voetnoot staat als eigen passage direct na zijn alinea.
    assert [p.tekst for p in blok.passages] == ["Dit voorstel regelt de invorderingsrente opnieuw.", "Zie de nota.",
                                                "Het doel is eenvoud."]
    assert blok.link.endswith(ID) and blok.passages[2].kop == "1. Inleiding › Doel"
    Antwoord.model_validate(a.model_dump())  # het contract dat api en werkplek lezen
    tekst = antwoord_tekst(a)
    assert "**Uit de parlementaire geschiedenis**" in tekst and '> "Het doel is eenvoud."' in tekst
    # De letterlijke tekst haalt de controle: de passages komen uit de bron.
    assert check_grounding(tekst, TRACE).grounded


@pytest.mark.parametrize("aanwijzing,reden", [
    ({"id": "kst-99001-10", "van_nr": 1, "tot_nr": 1}, "niet gelezen"),
    ({"id": ID, "van_nr": 2, "tot_nr": 4}, "niet opgehaald"),
    # Geen grens per aanwijzing meer (K15): een lange reeks splitst de code, en wat niet gelezen is, zegt de weigering.
    ({"id": ID, "van_nr": 1, "tot_nr": 9}, "alinea 4–9 is niet opgehaald"),
    ({"id": ID, "van_nr": 2, "tot_nr": 1}, "van_nr ≤ tot_nr"),
    # Een ECLI heeft sinds de connector Rechtspraak wel een bron; EU-recht (nog) niet.
    ({"id": "CELEX:32016R0679", "van_nr": 1, "tot_nr": 1}, "geen id van een bron"),
])
def test_wat_niet_klopt_gaat_terug_naar_het_model(aanwijzing, reden):
    with pytest.raises(Onvulbaar, match=reden):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [aanwijzing], "twijfel": []}, TRACE)


def test_zonder_aanwijzing_geen_eigen_sjabloon():
    with pytest.raises(Onvulbaar, match="minstens één passage"):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [], "stukken": [], "twijfel": []}, TRACE)


def test_het_subsjabloon_staat_achter_de_uitleg_en_voor_de_twijfel(monkeypatch):
    from bronmodel.antwoord import Toelichting, Twijfel
    nep = sjablonen.Sjabloon(sjablonen.SJABLONEN["antwoord_duiding"].schema,
                             lambda invoer, _t: Antwoord(sjabloon="duiding", blokken=[Toelichting(tekst=invoer["kort_antwoord"]),
                                                                                    Twijfel(punten=["p"])]))
    monkeypatch.setitem(sjablonen.SJABLONEN, "antwoord_duiding", nep)
    a = sjablonen.vul("antwoord_duiding", {"kort_antwoord": "k", "extern": [{"id": ID, "van_nr": 2, "tot_nr": 2}]}, TRACE)
    assert [b.soort for b in a.blokken] == ["toelichting", "extern", "twijfel"]


def test_zonder_connector_zijn_de_schemas_gelijk_aan_voor_adr_013():
    namen = frozenset({"antwoord_bepaling", "antwoord_duiding"})
    zonder = sjablonen.sjabloon_schemas(namen)
    assert all("extern" not in s["input_schema"]["properties"] for s in zonder)
    met = sjablonen.sjabloon_schemas(namen | {sjablonen.EXTERN}, extern=True)
    for s in met:
        invoer = s["input_schema"]
        assert "extern" in invoer["properties"] and "extern" in invoer["required"]
        assert "stukken" in invoer["properties"] and "stukken" in invoer["required"]
        assert invoer["additionalProperties"] is False and s["strict"] is True
    # Het origineel blijft ongemoeid.
    assert sjablonen.sjabloon_schemas(namen) == zonder


def test_het_veld_is_plat():
    """Strict tools (ADR-008): geen union, geen recursie, alleen strings en gehele getallen in het item."""
    item = extern.ITEMS["items"]
    assert {v["type"] for v in item["properties"].values()} <= {"string", "integer"}
    assert set(item["required"]) == set(item["properties"]) and item["additionalProperties"] is False
    assert extern.STUKKEN_ITEMS["items"] == {"type": "string"}, "een lijst ids, niets anders"


def test_een_gevonden_stuk_is_geen_signaal():
    """Acceptatie 9 nov 2026: een lijst opvolgende stukken in lopende tekst gaf 13 keer "alleen gevonden, niet gelezen",
    en het niveau zakte naar onbepaald. Het zoekresultaat draagt label, soort, datum en titel uit de bron: wie een
    gevonden stuk noemt, beweert niets wat er niet staat. Een id dat nergens gevonden is, blijft ongegrond."""
    rapport = check_grounding("Zie kst-99001-10 (Verslag) en het doel in kst-99001-3.", TRACE[:1])
    assert rapport.onbevestigd == [] and rapport.niveau == "gegrond" and not rapport.unsupported
    verzonnen = check_grounding("Zie kst-99001-77.", TRACE[:1])
    assert verzonnen.unsupported and verzonnen.niveau == "ongegrond"


def _schemas_van_de_beurt(settings, bronnen):
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])

    async def loop():
        async for _ in answer_stream("Wat betekent artikel 9?", settings=settings.model_copy(update={"enable_planning": False}),
                                     llm=llm, graph=FakeGraph(result=""), bronnen=bronnen):
            pass

    asyncio.run(loop())
    return {t["name"]: t for t in llm.calls[0]["tools"]}


def test_de_beurt_biedt_het_subsjabloon_alleen_met_een_connector_aan():
    aan = _schemas_van_de_beurt(make_settings(connector_kamerstukken=True), ["kamerstukken"])
    uit = _schemas_van_de_beurt(make_settings(connector_kamerstukken=True), [])
    assert "antwoord_extern" in aan and "extern" in aan["antwoord_bepaling"]["input_schema"]["properties"]
    assert "antwoord_extern" not in uit and "extern" not in uit["antwoord_bepaling"]["input_schema"]["properties"]
    assert uit == _schemas_van_de_beurt(make_settings(), None), "uit is gelijk aan een straat zonder connector"


# ── Eén lezing per blok, met de versie erbij (review ADR-013, punt 3) ────────────────────────────────────────────

from agent.adapters.sru_kamerstukken import Document  # noqa: E402
from test_kamerstuk_tools import XML  # noqa: E402


class Versie(NepBron):
    def __init__(self, xml: bytes, h: str, gewijzigd: str):
        super().__init__(DOSSIER, xml)
        self.h, self.gewijzigd = h, gewijzigd

    def document(self, ident):
        return Document(ident, self.xml, self.h, gewijzigd=self.gewijzigd, documentstatus="Opgemaakt")


OUD = ("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID}, AAN, kamerstukken=Versie(XML, "h1", "2026-01-02")))
# De opgemaakte versie: de tweede alinea is weg.
NIEUW_XML = XML.replace(b"<al>Het doel is   eenvoud.</al>", b"")
NIEUW = ("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID}, AAN,
                                         kamerstukken=Versie(NIEUW_XML, "h2", "2026-02-01")))


def _vul(trace, van, tot):
    return sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [{"id": ID, "van_nr": van, "tot_nr": tot}],
                                             "twijfel": []}, trace)


def test_het_blok_draagt_de_versie_die_lex_las():
    blok = next(b for b in _vul([OUD], 1, 2).blokken if b.soort == "extern")
    assert blok.bron_hash == "h1" and blok.gewijzigd == "2026-01-02"


def test_passages_komen_uit_de_laatste_lezing_en_mengen_niet():
    blok = next(b for b in _vul([OUD, NIEUW], 1, 1).blokken if b.soort == "extern")
    assert blok.bron_hash == "h2" and [p.tekst for p in blok.passages] == ["Dit voorstel regelt de invorderingsrente opnieuw."]
    with pytest.raises(Onvulbaar, match="veranderd sinds alinea 3"):
        _vul([OUD, NIEUW], 1, 3)


def test_een_ouder_bericht_zonder_versie_blijft_geldig():
    oud = {"soort": "extern", "door": "bron", "brontype": "kamerstuk", "id": ID, "label": "x", "kop": "k",
           "passages": [{"nr": 1, "tekst": "t"}]}
    a = Antwoord.model_validate({"sjabloon": "extern", "blokken": [oud]})
    assert a.blokken[0].bron_hash == ""



# ── Een tabel in het blok (plan tabellen en voetnoten, PR 2) ────────────────────────────────────────────────────

from test_kamerstuk_tools import TABELLEN  # noqa: E402


def _tabeltrace(open_: bool):
    bron = NepBron(DOSSIER, TABELLEN)
    trace = [("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID}, AAN, kamerstukken=bron))]
    if open_:
        trace.append(("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID, "tabel": 2}, AAN, kamerstukken=bron)))
    return trace


def test_een_tabel_komt_met_kolommen_en_cellen_in_het_blok():
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [{"id": ID, "van_nr": 2, "tot_nr": 3}],
                                          "twijfel": []}, _tabeltrace(True))
    kop, rij = next(b for b in a.blokken if b.soort == "extern").passages
    assert kop.soort == "tabel" and kop.cellen == ["", "2014", "2015", "struc"], "de kop met de kolommen wint"
    assert rij.soort == "tabelrij" and rij.cellen == ["Totaal", "12", "106", "267"] and rij.tekst == "Totaal | 12 | 106 | 267"


def test_een_passage_over_een_niet_geopende_tabel_toont_de_titel():
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [{"id": ID, "van_nr": 1, "tot_nr": 7}],
                                          "twijfel": []}, _tabeltrace(False))
    passages = next(b for b in a.blokken if b.soort == "extern").passages
    assert [p.soort for p in passages] == ["alinea", "tabel", "alinea"]
    assert passages[1].tekst == "Tabel 1 Opbrengst (€ mln)" and passages[1].cellen is None


def test_een_voetnoot_in_het_blok_draagt_zijn_verwijzing_met_label_en_link():
    from test_kamerstuk_tools import NOTEN

    trace = [("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID}, AAN, kamerstukken=NepBron(DOSSIER, NOTEN)))]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [{"id": ID, "van_nr": 1, "tot_nr": 2}],
                                          "twijfel": []}, trace)
    noot = next(b for b in a.blokken if b.soort == "extern").passages[1]
    assert noot.soort == "voetnoot" and [v.id for v in noot.verwijst_naar] == ["kst-33410-15"]
    assert noot.verwijst_naar[0].label == "Kamerstukken 33410, nr. 15"
    assert noot.verwijst_naar[0].link == "https://zoek.officielebekendmakingen.nl/kst-33410-15"


# ── Een lijst gevonden stukken (het blok `stukken`) ──────────────────────────────────────────────────────────────────
# Gesprek e906567a op acceptatie: 44 Kamerstukken als vrije tekst, 31 keer "alleen gevonden, niet gelezen", en datums uit
# de tekst van het model. Nu wijst het model de ids aan en komt elk feit uit de zoekrijen.

def _zoek(args: dict, bron=None) -> tuple[str, str]:
    return "zoek_kamerstukken", tools.dispatch("zoek_kamerstukken", None, args, AAN, kamerstukken=bron or NepBron(DOSSIER))


def test_de_lijst_neemt_elk_feit_uit_de_zoekrijen():
    trace = [_zoek({"dossier": "99001", "volgorde": "nieuwste", "aantal": 2})]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "Dit zijn de nieuwste stukken.", "extern": [],
                                          "stukken": ["kst-99001-10", "kst-99001-3"], "twijfel": []}, trace)
    blok = next(b for b in a.blokken if b.soort == "stukken")
    rijen = {r["id"]: r for r in json.loads(trace[0][1])["resultaten"]}
    # De volgorde van het zoekresultaat, niet die van het model.
    assert [x.id for x in blok.items] == [i for i in rijen if i in {"kst-99001-10", "kst-99001-3"}]
    assert all(x.datum == rijen[x.id]["datum"] and x.label == rijen[x.id]["label"] for x in blok.items)
    # Het totaal van de dienst (de nepbron telt een bijlage mee, zoals KOOP zijn records telt).
    assert blok.kop == "Gevonden Kamerstukken" and blok.door == "bron" and blok.totaal == 4
    assert blok.zoekvraag == "Gezocht op dossier 99001. Nieuwste eerst."
    Antwoord.model_validate(a.model_dump())
    tekst = antwoord_tekst(a)
    assert "**Gevonden Kamerstukken**" in tekst and "2 van de 4 stukken." in tekst


def test_een_lijst_is_niet_onbevestigd():
    """De ids in een lijst zijn gevonden, niet gelezen; dat is geen signaal, want de lijst zegt niets over de inhoud."""
    from bronmodel.antwoord import NIET_GETOETST

    trace = [_zoek({"dossier": "99001"})]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "Het dossier telt drie stukken.", "extern": [],
                                          "stukken": ["kst-99001-2", "kst-99001-3", "kst-99001-10"], "twijfel": []}, trace)
    rapport = check_grounding(antwoord_tekst(a, zonder=NIET_GETOETST), trace)
    assert not rapport.onbevestigd


def test_een_stuk_dat_niet_gevonden_is_gaat_terug_naar_het_model():
    with pytest.raises(Onvulbaar, match="staat in geen zoekresultaat"):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [], "stukken": ["kst-99001-77"], "twijfel": []},
                      [_zoek({"dossier": "99001"})])
    with pytest.raises(Onvulbaar, match="hoogstens 25"):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [],
                                          "stukken": [f"kst-99001-{i}" for i in range(26)], "twijfel": []}, TRACE)


def test_een_stuk_met_alleen_een_pdf_kan_in_de_lijst():
    from test_kamerstuk_tools import Koop, _koop, _record_xml

    pdf = _record_xml("kst-1278484", dossiers=("32140",), datum="2026-10-16", gepubliceerd="2026-10-16")
    trace = [("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": "kst-32140-342"}, AAN,
                                              kamerstukken=_koop(Koop({}, {("32140", "342"): [pdf]}))))]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "Nr. 342 is nog onopgemaakt.", "extern": [],
                                          "stukken": ["kst-1278484"], "twijfel": []}, trace)
    [x] = next(b for b in a.blokken if b.soort == "stukken").items
    assert x.label == "Kamerstukken 32140, nr. 342" and x.datum == "2026-10-16" and x.leesbaar is False
    assert "(onopgemaakt, alleen PDF)" in antwoord_tekst(a)


def test_het_subsjabloon_zet_de_lijst_voor_de_passages():
    from bronmodel.antwoord import Toelichting, Twijfel

    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [{"id": ID, "van_nr": 1, "tot_nr": 1}],
                                          "stukken": [ID], "twijfel": ["p"]}, TRACE)
    assert [b.soort for b in a.blokken] == ["toelichting", "stukken", "extern", "twijfel"]
    assert isinstance(a.blokken[0], Toelichting) and isinstance(a.blokken[-1], Twijfel)


def test_het_blok_extern_noemt_datum_en_soort_uit_het_stuk():
    from test_kamerstuk_tools import Koop, _koop, _record_xml

    leesbaar = _record_xml("kst-99001-3", nummer="3", xml=True, status="Opgemaakt na onopgemaakt")
    trace = [("get_kamerstuk", tools.dispatch("get_kamerstuk", None, {"id": ID}, AAN,
                                              kamerstukken=_koop(Koop({ID: leesbaar}))))]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [{"id": ID, "van_nr": 1, "tot_nr": 1}],
                                          "stukken": [], "twijfel": []}, trace)
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert (blok.datum, blok.soort_stuk) == ("2026-09-25", "Brief regering")
    assert "(Brief regering, 2026-09-25)" in antwoord_tekst(a)


@pytest.mark.parametrize("zoekvraag,verwacht", [
    ({"volgorde": "nieuwste", "aantal": 10}, "Nieuwste eerst."),
    ({"soort": "motie", "vanaf": "2024-01-01", "tot": "2024-12-31", "volgorde": "oudste"},
     "Gezocht op soort stuk „motie” en van 1 januari 2024 tot en met 31 december 2024. Oudste eerst."),
    ({"woorden": "Invorderingswet", "volgorde": "relevantie"},
     "Gezocht op „Invorderingswet” in de titel. Meest relevante eerst."),
    ({"tekst": '"één bankrekeningnummer"', "volgorde": "relevantie"},
     "Gezocht op „één bankrekeningnummer” in de tekst. Meest relevante eerst."),
    # Acceptatie 9 nov 2026: "Kamer Eerste Kamer". Een waarde die zegt wat ze is, krijgt geen label.
    ({"tekst": "invorderingsrente", "vergaderjaar": "2025-2026", "kamer": "Eerste Kamer", "volgorde": "relevantie"},
     "Gezocht op „invorderingsrente” in de tekst, vergaderjaar 2025-2026 en van de Eerste Kamer. Meest relevante eerst."),
    ({"vanaf": "2011-01-01"}, "Gezocht naar stukken vanaf 1 januari 2011."),
    ({}, ""),
])
def test_de_zoekvraag_in_woorden(zoekvraag, verwacht):
    from bronmodel.connectors import KAMERSTUKKEN

    assert extern.zoekvraag_tekst(KAMERSTUKKEN, zoekvraag) == verwacht


def test_de_velden_noemen_de_voorbeelden_van_de_connectors_die_aanstaan():
    """Geen vaste "kst-…" in het schema: met alleen Kamerstukken alleen dat voorbeeld, met Rechtspraak erbij ook een ECLI."""
    alleen = json.dumps(sjablonen.sjabloon_schemas(frozenset({"antwoord_duiding", sjablonen.EXTERN}), extern=("kamerstukken",)),
                        ensure_ascii=False)
    beide = json.dumps(sjablonen.sjabloon_schemas(frozenset({"antwoord_duiding", sjablonen.EXTERN}),
                                                  extern=("kamerstukken", "rechtspraak")), ensure_ascii=False)
    assert "kst-33755-3" in alleen and "ECLI" not in alleen and "Rechtspraak" not in alleen
    assert "kst-33755-3" in beide and "ECLI:NL:HR:2022:50" in beide and "ECLI:NL:…" in beide
    assert "later" not in beide, "geen belofte over een bron die er al is"


# --- de tekst van het artikel waarbij een uitspraak hoort (review ADR-013, 10 nov 2026) ----------------------------

def _rechtspraak_trace(lezen: bool):
    from test_rechtspraak_tools import DRIE, IW, VERSIELINKS, NepBron, _artikel, _uitspraak

    aan = make_settings(connector_rechtspraak=True)
    bron = NepBron(VERSIELINKS, versies=DRIE, docs={"ECLI:NL:HR:2018:2": _uitspraak()})
    trace = [("zoek_uitspraken", tools.dispatch("zoek_uitspraken", FakeGraph(result=_artikel("2023-01-01")),
                                                {"bwb_id": IW, "artikel": "9", "peildatum": "2017-01-01"}, aan,
                                                rechtspraak=bron))]
    if lezen:
        trace.append(("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2018:2"}, aan,
                                                      rechtspraak=bron)))
    return trace


def test_de_lijst_en_het_blok_noemen_de_tekst_waarbij_de_uitspraak_hoort():
    trace = _rechtspraak_trace(lezen=True)
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [{"id": "ECLI:NL:HR:2018:2", "van_nr": 1,
                                                                             "tot_nr": 1}],
                                          "stukken": ["ECLI:NL:HR:2018:2", "ECLI:NL:HR:2024:1"], "twijfel": []}, trace)
    lijst = next(b for b in a.blokken if b.soort == "stukken")
    oud, nieuw = (next(s for s in lijst.items if s.id == e) for e in ("ECLI:NL:HR:2018:2", "ECLI:NL:HR:2024:1"))
    assert (oud.tekst_vanaf, oud.tekst_tot, oud.tekststand, oud.op_peildatum) == (
        "2016-05-01", "2022-12-31", "eerdere tekst", True)
    assert (nieuw.tekststand, nieuw.tekst_tot, nieuw.op_peildatum) == ("huidige tekst", "", False)
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert (blok.tekst_vanaf, blok.tekst_tot, blok.tekststand) == ("2016-05-01", "2022-12-31", "eerdere tekst")


def test_een_uitspraak_die_alleen_gelezen_is_draagt_geen_tekststand():
    from test_rechtspraak_tools import NepBron, _uitspraak

    aan = make_settings(connector_rechtspraak=True)
    trace = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2018:2"}, aan,
                                              rechtspraak=NepBron([], docs={"ECLI:NL:HR:2018:2": _uitspraak()})))]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [{"id": "ECLI:NL:HR:2018:2", "van_nr": 1,
                                                                             "tot_nr": 1}], "stukken": [], "twijfel": []},
                      trace)
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert (blok.tekststand, blok.op_peildatum) == ("", None), "de leestool kent het artikel niet: geen gok"


def test_de_zoekvraag_noemt_de_peildatum_en_de_tekststand():
    from bronmodel.connectors import RECHTSPRAAK

    tekst = extern.zoekvraag_tekst(RECHTSPRAAK, {"bwb_id": "BWBR0004770", "artikel": "9", "bepaling": "artikel 9 van "
                                                 "Invorderingswet 1990", "peildatum": "2015-01-01",
                                                 "tekststand": "op peildatum", "volgorde": "nieuwste"})
    assert tekst.startswith("Gezocht bij artikel 9 van Invorderingswet 1990, op ")
    assert "peildatum 1 januari 2015" in tekst and "de tekst op de peildatum" in tekst


@pytest.mark.parametrize("naam", [c for c, k in sorted(CONNECTORS.items()) if k.veld("wetsverwijzing") is not None])
def test_een_zoekvraag_bij_een_regeling_zonder_artikel_heeft_geen_lege_plek(naam, monkeypatch):
    """Meting Staatsblad ronde 5, B03: "Gezocht bij artikel  van BWBR0004770". Voor elke connector die stukken aan een
    regeling koppelt: zonder artikel de regeling als geheel, met de naam als het proces die kent, anders het id."""
    from agent import overzicht
    c = CONNECTORS[naam]
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}])
    veld = c.veld("wetsverwijzing")
    regeling = {veld.filters[0]: "BWBR0004770", "volgorde": "nieuwste"}
    assert extern.zoekvraag_tekst(c, regeling).startswith("Gezocht bij Invorderingswet 1990")
    assert extern.zoekvraag_tekst(c, {**regeling, veld.filters[1]: "36"}).startswith(
        "Gezocht bij artikel 36 van Invorderingswet 1990")
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [])
    zin = extern.zoekvraag_tekst(c, regeling)
    assert zin.startswith("Gezocht bij BWBR0004770") and "artikel  " not in zin


@pytest.mark.parametrize("n,totaal,slot", [(3, 3, "3 stukken."), (1, 1, "1 stuk."), (2, 4, "2 van de 4 stukken."),
                                            (2, None, "")])
def test_de_slotzin_noemt_het_totaal_ook_als_alles_getoond_is(n, totaal, slot):
    """K25 (ronde 1 Kamerstukken, 11 nov 2026): "hoeveel stukken zitten er in dossier 33755?" kreeg een lijst zonder getal."""
    from bronmodel.antwoord import Stuk, Stukken
    blok = Stukken(brontype="kamerstuk", kop="Gevonden Kamerstukken", totaal=totaal,
                   items=[Stuk(id=f"kst-99001-{i}", label=f"Kamerstukken 99001, nr. {i}") for i in range(n)])
    tekst = antwoord_tekst(Antwoord(sjabloon="extern", blokken=[blok]))
    assert tekst.endswith(slot) and tekst.count("\n\n") == (2 if slot else 1), "zonder totaal geen slotzin"


# ── Ronde 1 van de iteratie Rechtspraak (11 nov 2026): de zoekvraag, de pagina's en de kanttekening ──────────────────

@pytest.mark.parametrize("naam,verwacht", [
    ("Hoge Raad", "van de Hoge Raad"),
    ("College van Beroep voor het bedrijfsleven", "van het College van Beroep voor het bedrijfsleven"),
    ("Ministerie van Financiën", "van het Ministerie van Financiën"),
    ("Parket bij de Hoge Raad", "van het Parket bij de Hoge Raad"),
    ("Eerste Kamer", "van de Eerste Kamer"),
    ("gerechtshof", "van gerechtshoven"),
    ("gerechtshoven", "van gerechtshoven"),
    ("rechtbank", "van rechtbanken"),
])
def test_het_lidwoord_bij_een_orgaan(naam, verwacht):
    """Metingen Rechtspraak R25 en Staatsblad B10: "van de College", "van de Ministerie"."""
    assert extern.van_orgaan(naam) == verwacht


def test_de_paginas_van_een_zoekvraag_zijn_een_lijst():
    """Kamerstukken K10, Rechtspraak R04/R30: ids uit twee pagina's van dezelfde zoekvraag gaven een blok zonder
    zoekvraag en met totaal null."""
    eerste = _zoek({"dossier": "99001", "volgorde": "nieuwste", "aantal": 2})
    data = json.loads(eerste[1])
    tweede = _zoek(data["vervolg"]["args"])
    ids = [r["id"] for r in data["resultaten"]] + [r["id"] for r in json.loads(tweede[1])["resultaten"]][:1]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "stukken": ids, "twijfel": []},
                      [eerste, tweede])
    blok = next(b for b in a.blokken if b.soort == "stukken")
    assert blok.zoekvraag == "Gezocht op dossier 99001. Nieuwste eerst." and blok.totaal == 4
    assert [x.id for x in blok.items] == ids


def test_twee_zoekvragen_zijn_geen_lijst_met_een_zoekvraag():
    a1 = _zoek({"dossier": "99001", "volgorde": "nieuwste", "aantal": 2})
    d1 = json.loads(a1[1])
    # Een tweede zoekvraag met een andere rij: alleen de tweede rij, met een andere volgorde.
    d2 = {**d1, "resultaten": d1["resultaten"][1:], "zoekvraag": {**d1["zoekvraag"], "volgorde": "oudste"}}
    a1 = (a1[0], json.dumps({**d1, "resultaten": d1["resultaten"][:1]}))
    a2 = (a1[0], json.dumps(d2))
    ids = [d1["resultaten"][0]["id"], d1["resultaten"][1]["id"]]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "stukken": ids, "twijfel": []}, [a1, a2])
    blok = next(b for b in a.blokken if b.soort == "stukken")
    # Geen totaal voor de hele lijst (dat is er niet), wel per zoekvraag een zin met haar totaal (Kamerstukken ronde 3,
    # K17: de jurist zag niet waarop gezocht was).
    assert blok.totaal is None
    assert blok.zoekvraag == ("Gezocht op dossier 99001. Nieuwste eerst. Totaal 4. "
                              "Gezocht op dossier 99001. Oudste eerst. Totaal 4.")


def test_een_gelezen_stuk_blijft_bij_zijn_zoekvraag():
    """Rechtspraak R27: een arrest dat na het zoeken gelezen werd, maakte zoekvraag en totaal van het blok leeg."""
    trace = _rechtspraak_trace(lezen=True)
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "twijfel": [],
                                          "stukken": ["ECLI:NL:HR:2018:2", "ECLI:NL:HR:2024:1"]}, trace)
    blok = next(b for b in a.blokken if b.soort == "stukken")
    assert blok.zoekvraag.startswith("Gezocht bij artikel 9") and isinstance(blok.totaal, int)


def test_de_kanttekening_van_de_tool_staat_bij_de_lijst_en_bij_niets_gevonden():
    """Rechtspraak R07: een onvolledige lijst bleef "geen jurisprudentie gevonden". De kanttekening van de tool komt in
    het blok, en in de leemte zonder volgorde."""
    from bronmodel.connectors import RECHTSPRAAK
    from test_rechtspraak_tools import ARTIKEL, IW, LINKS, V_2016, NepBron

    aan = make_settings(connector_rechtspraak=True)
    bron = NepBron(LINKS, onvolledig=((V_2016, "plafond"),))
    raw = tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL), {"bwb_id": IW, "artikel": "9"}, aan,
                         rechtspraak=bron)
    data = json.loads(raw)
    assert "niet alles binnen" in data["kanttekening"]
    ids = [r["id"] for r in data["resultaten"]][:2]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "stukken": ids, "twijfel": []},
                      [("zoek_uitspraken", raw)])
    blok = next(b for b in a.blokken if b.soort == "stukken")
    assert blok.zoekvraag.endswith(data["kanttekening"])
    leeg = extern.leemte_tekst(RECHTSPRAAK, {**data, "resultaten": []})
    assert leeg.startswith("Bij deze zoekvraag vond ik geen jurisprudentie.") and "niet alles binnen" in leeg
    assert "eerst." not in leeg


def test_een_rechtsgebied_naast_een_artikel_zoekt_zonder_en_zegt_het():
    """Rechtspraak R24: de tool weigerde, het model nam het over en liet het filter stil vallen."""
    from test_rechtspraak_tools import ARTIKEL, IW, LINKS, NepBron

    aan = make_settings(connector_rechtspraak=True)
    data = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL),
                                     {"bwb_id": IW, "artikel": "9", "rechtsgebied": "belastingrecht"}, aan,
                                     rechtspraak=NepBron(LINKS)))
    assert data["status"] == "ok" and data["totaal"] == 4
    assert "niet toegepast" in data["kanttekening"] and "rechtsgebied" not in data["zoekvraag"]


def test_een_maand_en_een_jaar_in_de_zoekvraag():
    """Rechtspraak ronde 2, R04: "van 2025-03 tot en met 2025-03" en "… en in maart 2025"."""
    from bronmodel.connectors import RECHTSPRAAK

    assert extern.zoekvraag_tekst(RECHTSPRAAK, {"instantie": "Centrale Raad van Beroep", "vanaf": "2025-03",
                                                "tot": "2025-03", "volgorde": "nieuwste"}) == (
        "Gezocht naar stukken van de Centrale Raad van Beroep in maart 2025. Nieuwste eerst.")
    assert "van maart 2025 tot en met juni 2025" in extern.zoekvraag_tekst(
        RECHTSPRAAK, {"vanaf": "2025-03", "tot": "2025-06"})


def test_de_grens_van_de_lijst_geldt_per_bron():
    """Rechtspraak ronde 2, R30: 25 uitspraken lieten geen ruimte voor de gezochte Kamerstukken. Elke bron heeft een eigen
    lijst met hoogstens `MAX_LIJST`."""
    trace = [_zoek({"dossier": "99001", "volgorde": "nieuwste", "aantal": 2})]
    kst = [r["id"] for r in json.loads(trace[0][1])["resultaten"]]
    eclis = [f"ECLI:NL:RBZWB:2024:{i}" for i in range(1, extern.MAX_LIJST + 1)]
    uitspraken = json.dumps({"status": "ok", "volledig": True, "aantal": len(eclis), "totaal": len(eclis),
                             "zoekvraag": {"bwb_id": "BWBR0004770", "artikel": "9"},
                             "resultaten": [{"id": e, "label": e, "soort": "Uitspraak", "datum": "2024-03-01"} for e in eclis]})
    trace.append(("zoek_uitspraken", uitspraken))
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "stukken": eclis + kst, "twijfel": []},
                      trace)
    lijsten = [b for b in a.blokken if b.soort == "stukken"]
    assert sorted(len(b.items) for b in lijsten) == sorted([len(kst), extern.MAX_LIJST])
    with pytest.raises(Onvulbaar):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "k", "extern": [], "twijfel": [],
                                          "stukken": eclis + ["ECLI:NL:RBZWB:2024:999"]},
                      [*trace[:1], ("zoek_uitspraken", json.dumps({**json.loads(uitspraken), "resultaten": [
                          *json.loads(uitspraken)["resultaten"], {"id": "ECLI:NL:RBZWB:2024:999", "label": "x"}]}))])


def test_de_schemabeschrijving_noemt_de_bronnen_met_of():
    """Twee functies `_opsomming` overschaduwden elkaar: het schema zei "een kamerstuk, een bekendmaking en een uitspraak"
    waar "of" bedoeld is (Staatsblad, 12 nov 2026). De zoekvraag houdt "en"."""
    from bronmodel.connectors import KAMERSTUKKEN, RECHTSPRAAK

    tekst = json.dumps(extern.items(["kamerstukken", "bekendmakingen", "rechtspraak"]), ensure_ascii=False)
    assert " of een " in tekst and "en een uitspraak" not in tekst
    assert " en " in extern.zoekvraag_tekst(KAMERSTUKKEN, {"tekst": "x", "vergaderjaar": "2025-2026", "kamer": "Eerste Kamer"})
    assert RECHTSPRAAK.brontype == "uitspraak"
