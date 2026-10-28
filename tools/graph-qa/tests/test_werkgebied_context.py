"""Het dossier van een werkgebied als context voor Lex (spoor F, F2): één tekst voor intake, deelvragenrun
en gesprek, en wat de analist buiten het werkgebied liet."""
from __future__ import annotations

import asyncio

from agent import deelvragen
from agent.werkgebied_context import als_blok, context_tekst, uitsluitstammen, valt_buiten
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

WG = {"naam": "Box 3", "aanleiding": "Een wetswijziging raakt een bestaand proces.", "context": "",
      "doel": "Bruikbaar voor de bouw van webservices.", "analysevraag": "Wie is belastingplichtig?",
      "praktijkvoorbeeld": "Een spaarder met een tweede huis.", "afbakening": "Buiten de afbakening: overgangsrecht.",
      "deelvragen": [{"vraag": "Wat telt als vermogen?", "status": "actief"},
                     {"vraag": "Voorstel van Lex?", "status": "voorgesteld"}],
      "bronnen": [{"label": "Afdeling 5.1", "rol": "analyseren"}, {"label": "Artikel 2.1", "rol": "context"}]}


def test_het_dossier_noemt_alleen_wat_er_ligt_in_de_volgorde_van_de_methode():
    tekst = context_tekst(WG)
    assert tekst.splitlines()[:6] == [
        "Werkgebied: Box 3", "Aanleiding: Een wetswijziging raakt een bestaand proces.",
        "Doel: Bruikbaar voor de bouw van webservices.", "Analysevraag: Wie is belastingplichtig?",
        "Praktijkvoorbeeld: Een spaarder met een tweede huis.", "Afbakening: Buiten de afbakening: overgangsrecht."]
    assert "Context:" not in tekst, "een leeg veld staat er niet"
    assert "- Wat telt als vermogen?" in tekst and "Voorstel van Lex?" not in tekst, "alleen actieve deelvragen"
    assert "Bronnen om te analyseren: Afdeling 5.1" in tekst and "Contextbronnen: Artikel 2.1" in tekst
    assert context_tekst({}) == "" and als_blok({}) == ""
    assert als_blok(WG).startswith("\n\nWERKGEBIED") and "geen opdracht" in als_blok(WG)


def test_de_deelvragenrun_krijgt_het_hele_dossier():
    p = deelvragen.prompt(WG)
    assert "Aanleiding: Een wetswijziging" in p and "Praktijkvoorbeeld: Een spaarder" in p
    assert p.count("Wat telt als vermogen?") == 1, "de bestaande deelvragen één keer, onder hun eigen kop"
    assert "- Voorstel van Lex?" in p


def test_wat_buiten_valt_raakt_een_kop_op_het_begin_van_het_woord():
    stammen = uitsluitstammen("Het overgangsrecht en de bestuurdersaansprakelijkheid, niet box 1")
    assert stammen == ["overgang", "bestuurd"]
    assert valt_buiten("Hoofdstuk 10 – Overgangs- en slotbepalingen", stammen) == "overgang"
    assert valt_buiten("Afdeling 5.1 – Box 3", stammen) == ""
    assert uitsluitstammen("") == []


def test_in_een_gesprek_binnen_een_werkgebied_krijgt_lex_het_dossier_mee(monkeypatch, tmp_path):
    """Context, geen filter: het blok staat bij de supervisor en de specialist, de vraag blijft gewoon."""
    from agent import agent as agent_mod
    from agent.agent import answer_stream

    gevraagd: list[str] = []

    async def blok(settings, user_id, werkgebied_id):
        gevraagd.append(werkgebied_id)
        return als_blok(WG)

    monkeypatch.setattr(agent_mod, "_werkgebied_blok", blok)
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([response([text_block("WORKERS: antwoord\nSPECIALIST: algemeen\nPLAN: uitleg")], "end_turn"),
                   response([text_block("Box 3 gaat over sparen en beleggen.")], "end_turn")])

    async def run():
        return [e async for e in answer_stream("Wat is box 3?", "g1", settings=settings, llm=llm, graph=FakeGraph(),
                                               werkgebied_id="wg-1")]
    asyncio.run(run())
    assert gevraagd == ["wg-1"]
    systemen = [str(c["system"]) for c in llm.calls]
    assert all("Praktijkvoorbeeld: Een spaarder met een tweede huis." in s for s in systemen), systemen


def test_zonder_api_geen_werkgebiedblok():
    from agent.agent import _werkgebied_blok

    assert asyncio.run(_werkgebied_blok(make_settings(), "u", "wg-1")) == ""


def test_het_tooi_thema_staat_in_de_context():
    """Spoor I6: een gekozen thema gaat met naam en URI mee; zonder thema geen regel."""
    from agent.werkgebied_context import context_tekst
    uri = "https://identifier.overheid.nl/tooi/def/thes/top/c_25e30d03"
    assert f"Thema (TOOI): belasting <{uri}>" in context_tekst({"naam": "W", "thema": uri, "thema_label": "belasting"})
    assert "Thema" not in context_tekst({"naam": "W", "thema": "", "thema_label": ""})
