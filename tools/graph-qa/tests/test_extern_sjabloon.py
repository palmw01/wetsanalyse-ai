"""Bronnen naast de wet in het antwoord (ADR-008 + ADR-013): het blok `extern`, als subsjabloon en als eigen sjabloon.

De echte leestool (`get_kamerstuk` tegen een nepbron) levert de trace, zodat het contract van een leestool hier
meetelt: `stuk: {id, label, link, bron_hash, gewijzigd?}` en rijen `{nr, tekst, kop?}`. Het model wijst alleen het stuk en de alinea's aan.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from bronmodel.antwoord import Antwoord, antwoord_tekst

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
                                          "extern": [{"id": ID, "van_nr": 1, "tot_nr": 2}], "twijfel": []}, TRACE)
    assert a.sjabloon == "extern"
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert blok.door == "bron" and blok.brontype == "kamerstuk" and blok.kop == "Uit de parlementaire geschiedenis"
    assert [p.tekst for p in blok.passages] == ["Dit voorstel regelt de invorderingsrente opnieuw.", "Het doel is eenvoud."]
    assert blok.link.endswith(ID) and blok.passages[1].kop == "1. Inleiding › Doel"
    Antwoord.model_validate(a.model_dump())  # het contract dat api en werkplek lezen
    tekst = antwoord_tekst(a)
    assert "**Uit de parlementaire geschiedenis**" in tekst and '> "Het doel is eenvoud."' in tekst
    # De letterlijke tekst haalt de controle: de passages komen uit de bron.
    assert check_grounding(tekst, TRACE).grounded


@pytest.mark.parametrize("aanwijzing,reden", [
    ({"id": "kst-99001-10", "van_nr": 1, "tot_nr": 1}, "niet gelezen"),
    ({"id": ID, "van_nr": 2, "tot_nr": 4}, "niet opgehaald"),
    ({"id": ID, "van_nr": 1, "tot_nr": 9}, "hoogstens 6"),
    ({"id": ID, "van_nr": 2, "tot_nr": 1}, "van_nr ≤ tot_nr"),
    ({"id": "ECLI:NL:HR:2020:1", "van_nr": 1, "tot_nr": 1}, "geen id van een bron"),
])
def test_wat_niet_klopt_gaat_terug_naar_het_model(aanwijzing, reden):
    with pytest.raises(Onvulbaar, match=reden):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [aanwijzing], "twijfel": []}, TRACE)


def test_zonder_aanwijzing_geen_eigen_sjabloon():
    with pytest.raises(Onvulbaar, match="minstens één passage"):
        sjablonen.vul("antwoord_extern", {"kort_antwoord": "x", "extern": [], "twijfel": []}, TRACE)


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
        assert invoer["additionalProperties"] is False and s["strict"] is True
    # Het origineel blijft ongemoeid.
    assert sjablonen.sjabloon_schemas(namen) == zonder


def test_het_veld_is_plat():
    """Strict tools (ADR-008): geen union, geen recursie, alleen strings en gehele getallen in het item."""
    item = extern.ITEMS["items"]
    assert {v["type"] for v in item["properties"].values()} <= {"string", "integer"}
    assert set(item["required"]) == set(item["properties"]) and item["additionalProperties"] is False


def test_een_stuk_dat_alleen_gevonden_is_is_onbevestigd():
    rapport = check_grounding("Zie Kamerstukken kst-99001-10 over het verslag.", TRACE[:1])
    assert any("alleen gevonden, niet gelezen" in o for o in rapport.onbevestigd)
    assert not any("niet gelezen" in o for o in check_grounding(f"Zie {ID}.", TRACE).onbevestigd)


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
    with pytest.raises(Onvulbaar, match="veranderd sinds alinea 2"):
        _vul([OUD, NIEUW], 1, 2)


def test_een_ouder_bericht_zonder_versie_blijft_geldig():
    oud = {"soort": "extern", "door": "bron", "brontype": "kamerstuk", "id": ID, "label": "x", "kop": "k",
           "passages": [{"nr": 1, "tekst": "t"}]}
    a = Antwoord.model_validate({"sjabloon": "extern", "blokken": [oud]})
    assert a.blokken[0].bron_hash == ""
