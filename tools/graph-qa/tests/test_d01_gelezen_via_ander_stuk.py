"""D01 uit de meting van bundel 120 (14 nov 2026), met nepbronnen in de echte vorm (`zoek_uitspraken` en `get_uitspraak`
door de echte toollaag). De tekst van de stukken is ingekort tot wat de test nodig heeft; de alinea's uit het eindantwoord
staan er letterlijk.

1. HR:2023:1371 werd samengevat zonder dat een kind hem las: de inhoud kwam uit de conclusie PHR:2025:435. De kop noemde
   het stuk met instantie en datum, alleen de eerste zin bij id, en de zes zinnen daarna telden voor geen enkel stuk.
2. De jurist koos 2022–2024; twee van de vier blokken waren stukken uit 2025, en het hervatte deel las niets: het begon op
   70k met de tekst van negen uitspraken uit het eerste deel.
3. De afbakening stond in het rapport, niet in het eindantwoord en niet op de kindregel van het eind-event.
4. "niet-melدende": een Arabische letter midden in een woord."""
from __future__ import annotations

import json

from agent import subagent as sub
from agent import tools
from agent.berichten import HERVATTING, INGEKORT, eerste_deel_ingekort
from agent.gelezen import buiten_periode, gekozen_periode, ongelezen_samengevat, per_stuk, vreemd_schrift
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from test_rechtspraak_tools import AAN, ARTIKEL, IW, V_NU, Link, NepBron
from tests.fakes import FakeGraph

HR1371, PHR435, PHR936, HOF1599 = ("ECLI:NL:HR:2023:1371", "ECLI:NL:PHR:2025:435", "ECLI:NL:PHR:2024:936",
                                   "ECLI:NL:GHARL:2025:1599")
#: (instantie, datum, alinea's). HR:2023:1371 staat alleen in het zoekresultaat: geen kind las hem.
TEKST = {
    PHR435: ("Parket bij de Hoge Raad", "2025-04-11", [
        "In de tussenbeslissing ECLI:NL:HR:2023:1371 (r.o. 3.9) verwierp de Hoge Raad drie middelen. Artikel 36 schrijft "
        "dwingend de bewijsrechtelijke gevolgen voor als niet of niet juist is gemeld; het niet-melden is een vergaande "
        "onzorgvuldigheid, een bewuste keuze van de wetgever. De ontvanger heeft geen discretie om van aansprakelijkstelling "
        "af te zien of haar te matigen. Artikel 36 lid 4 kan als formele wet niet worden getoetst aan artikel 3:4 lid 2 Awb "
        "of het ongeschreven evenredigheidsbeginsel. De Hoge Raad stelde prejudiciële vragen over het Unierechtelijke "
        "evenredigheidsbeginsel.",
        "Na het antwoord van het Hof van Justitie zie ik vijf lichtpuntjes voor de niet-meldende bestuurder, waaronder de "
        "rechtspraak over artikel 6:11 Awb en het toetsingskader uit de Harderwijk-uitspraak."]),
    PHR936: ("Parket bij de Hoge Raad", "2024-09-13", [
        "Uitstel van betaling aan de aansprakelijkgestelde verlengt de verjaringstermijn van de belastingschuld niet. Wordt "
        "uitstel verleend, dan is de belastingschuldige niet (meer) in gebreke en vervalt de grondslag."]),
    HOF1599: ("Gerechtshof Arnhem-Leeuwarden", "2025-03-18", [
        "Na verwijzing gaat het om de vraag of de schending van het verdedigingsbeginsel tot een andere afloop had kunnen "
        "leiden."]),
}


def _xml(ecli: str) -> bytes:
    orgaan, datum, alineas = TEKST[ecli]
    paras = "".join(f"<para>{a}</para>" for a in alineas)
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>{orgaan}</dcterms:creator>
  <dcterms:date>{datum}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Artikel 36 Invorderingswet 1990.</para></inhoudsindicatie>
<uitspraak><section><title>Beoordeling</title>{paras}</section></uitspraak></open-rechtspraak>""".encode()


BRON = NepBron([Link(HR1371, f"{HR1371} - Hoge Raad, 06-10-2023 / 22/01234", "Door computer herkende referentie", V_NU),
                *(Link(e, f"{e} - {TEKST[e][0]}, {'-'.join(reversed(TEKST[e][1].split('-')))} / 2{i}/00{i}",
                       "Door computer herkende referentie", V_NU) for i, e in enumerate(TEKST))],
               docs={e: _xml(e) for e in TEKST})
ZOEK = ("zoek_uitspraken", tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL), {"bwb_id": IW, "artikel": "36"},
                                          AAN, rechtspraak=BRON))
TRACE = [ZOEK, *(("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=BRON))
                 for e in TEKST)]


def _passages(ecli: str) -> str:
    rijen = next(json.loads(t) for n, t in TRACE[1:] if json.loads(t)["stuk"]["id"] == ecli)["resultaten"]
    return " ".join(r["tekst"] for r in rijen)


#: Wat het rapport citeerde (`State.rapport_steun`): de passages van de drie gelezen stukken.
STEUN = {e: _passages(e) for e in TEKST}

#: Uit het eindantwoord van bundel 120, letterlijk (het eerste blok).
ANTWOORD_1371 = (
    "**HR 6 oktober 2023 — tussenbeslissing met prejudiciële vragen**\n"
    "De Hoge Raad (ECLI:NL:HR:2023:1371) verwerpt drie van vier cassatiemiddelen. Over de melding: artikel 36 IW 1990 "
    "schrijft dwingend voor wat de bewijsrechtelijke gevolgen zijn als niet of niet juist is gemeld. Het niet-melden is een "
    "\"vergaande onzorgvuldigheid\" — een bewuste wetgeverskeuze. De ontvanger heeft geen discretie om af te zien van "
    "aansprakelijkstelling of deze te matigen. Artikel 36 lid 4 (formele wet) kan niet worden getoetst aan artikel 3:4 lid "
    "2 Awb of het nationaal ongeschreven evenredigheidsbeginsel. Een bestuurder zonder kennelijk onbehoorlijk bestuur is "
    "toch aansprakelijk als hij niet heeft gemeld. De prejudiciële vragen gaan over de verenigbaarheid van die strikte "
    "regeling met het Unierechtelijke evenredigheidsbeginsel.")
#: Het blok over PHR:2025:435 (ingekort tot de eerste zin met de lichtpuntjes), letterlijk.
ANTWOORD_435 = (
    "**PHR 11 april 2025 — analyse meldingsplicht na HvJ EU-antwoord** *(buiten de periode, maar voortbouwend op HR "
    "2023:1371)*\n"
    "Na het HvJ EU-antwoord — de meldingsregeling is niet strijdig met het Unierechtelijke evenredigheidsbeginsel — "
    "inventariseert A-G Koopman vijf mogelijke \"lichtpuntjes\" voor de niet-melدende bestuurder: (a) ook andere "
    "omstandigheden dan overmacht of een deskundigenadvies kunnen meebrengen dat niet-melden de bestuurder niet valt te "
    "verwijten, maar dit zal in de praktijk zelden voorkomen; (e) al te harde toepassing kan worden gecorrigeerd via het "
    "toetsingskader uit de Harderwijk-uitspraak van de ABRvS.")
ANTWOORD_936 = (
    "**PHR 13 september 2024 — verjaring, niet de melding zelf**\n"
    "A-G Koopman (ECLI:NL:PHR:2024:936) gaat niet over de meldingsplicht zelf, maar over verjaring van de "
    "aansprakelijkstelling. Uitstel van betaling aan de aansprakelijkgestelde verlengt de verjaringstermijn van de "
    "onderliggende belastingschuld niet automatisch. Als uitstel wordt verleend, is de belastingschuldige niet meer in "
    "gebreke en vervalt daarmee de grondslag voor de aansprakelijkstelling.")
ANTWOORD_1599 = (
    "**Hof Arnhem-Leeuwarden 18 maart 2025 — andere-afloop-criterium** *(buiten de periode, voortbouwend op HR 10 "
    "februari 2023)*\n"
    "Na verwijzing staat centraal of schending van het Unierechtelijke verdedigingsbeginsel — niet horen in bezwaar — tot "
    "vermindering leidt. De kern na verwijzing is het \"andere-afloop-criterium\"; over de melding van betalingsonmacht "
    "zelf bevat de eerste pagina geen oordelen.")
ANTWOORDEN = "Uitspraken uit 2022 tot en met 2024.\nAlle instanties; verder geen beperking.\nGeen verdere beperking."


# --- 1. een stuk dat alleen via een ander stuk bekend is ----------------------------------------------------------

def test_de_zinnen_onder_een_kop_met_instantie_en_datum_gaan_over_dat_stuk():
    regels = per_stuk(ANTWOORD_1371, labels={HR1371: "Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371"})
    assert all(ids == [HR1371] for _, ids in regels[1:]), regels
    # Zonder labels uit de trace geeft de eerste zin met een id het onderwerp.
    assert all(ids == [HR1371] for _, ids in per_stuk(ANTWOORD_1371)[1:])
    # Een kop met de datum van een stuk van een andere instantie gaat er niet over: PHR is het Parket, niet de Hoge Raad.
    kop = per_stuk("**PHR 6 oktober 2023**\nEen lange samenvatting van iets.",
                   labels={HR1371: "Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371"})
    assert kop[-1][1] == []


def test_een_ongelezen_stuk_samengevat_uit_een_ander_stuk_is_een_bewering():
    assert ongelezen_samengevat(ANTWOORD_1371, TRACE) == [f"samenvatting van {HR1371} zonder gelezen tekst"]
    fout = check_grounding(ANTWOORD_1371, TRACE, steun=STEUN, bekend=ANTWOORDEN)
    assert f"samenvatting van {HR1371} zonder gelezen tekst" in fout.beweringen and fout.niveau != "gegrond"


def test_wie_zegt_uit_welk_gelezen_stuk_het_komt_rust_op_dat_stuk():
    goed = ANTWOORD_1371.replace("**HR 6 oktober 2023 — tussenbeslissing met prejudiciële vragen**",
                                 "**HR 6 oktober 2023, volgens de conclusie in ECLI:NL:PHR:2025:435 (r.o. 3.9)**")
    assert all(ids == [PHR435] for _, ids in per_stuk(goed, gelezen={PHR435})[1:])
    fout = check_grounding(goed, TRACE, steun=STEUN, bekend=ANTWOORDEN)
    assert not [b for b in fout.beweringen if HR1371 in b or PHR435 in b], fout.beweringen
    # Zonder de passages van de conclusie draagt niets de weergave.
    zonder = check_grounding(goed, TRACE, steun={PHR936: STEUN[PHR936]}, bekend=ANTWOORDEN)
    assert f"duiding van {PHR435} zonder passage van dat stuk in het rapport" in zonder.beweringen


def test_de_correctie_zegt_hoe_het_wel_kan(monkeypatch):
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: lambda _e: None)
    uit = antwoordnodes.correct_node(None, {"beweringen": [f"samenvatting van {HR1371} zonder gelezen tekst"]})
    assert "volgens <het gelezen stuk>" in uit["messages"][0]["content"]


# --- 2. de periode van de jurist ----------------------------------------------------------------------------------

def test_de_periode_uit_de_antwoorden_van_de_jurist():
    assert gekozen_periode(ANTWOORDEN) == (2022, 2024)
    assert gekozen_periode("Over welke periode? 2020–2025\nAntwoord: van 2022 tot 2024") == (2022, 2024)
    assert gekozen_periode("Alle instanties.") is None
    # Bij een subagent: de antwoorden staan in de hervatting, die zijn vraag is; de opdracht telt eerder.
    hervat = {"opdracht": {"doel": "Rechtspraak over de melding, 2015–2020."},
              "question": f"{HERVATTING}de gebruiker)\n- Periode?\n  Antwoord: Uitspraken uit 2022 tot en met 2024."}
    assert antwoordnodes._periode(hervat) == (2022, 2024)
    # De centrale agent: uit de afloop van de subagent; het dossier telt niet mee.
    centraal = {"question": "Geen verdere beperking.", "werkgebied_context": "Belastingjaren 2015-2018.",
                "subagenten": [{"uitkomst": "klaar", "periode": [2022, 2024]}]}
    assert antwoordnodes._periode(centraal) == (2022, 2024)


def test_een_samenvatting_van_buiten_de_periode_is_een_bewering_een_vermelding_niet():
    tekst = f"{ANTWOORD_936}\n\n{ANTWOORD_435}\n\n{ANTWOORD_1599}"
    # De kop van het hof noemt na de eigen datum nog een ander stuk: de eerste datum telt.
    assert buiten_periode(tekst, TRACE, (2022, 2024)) == [
        f"duiding van {PHR435} van buiten de gekozen periode 2022–2024",
        f"duiding van {HOF1599} van buiten de gekozen periode 2022–2024"]
    assert not buiten_periode(tekst, TRACE, None), "zonder gekozen periode geen toets"
    assert not buiten_periode(f"{ANTWOORD_936}\n\nBuiten de periode staat nog {PHR435} (Parket, 11 april 2025).",
                              TRACE, (2022, 2024))
    fout = check_grounding(tekst, TRACE, steun=STEUN, bekend=ANTWOORDEN, periode=(2022, 2024))
    assert f"duiding van {PHR435} van buiten de gekozen periode 2022–2024" in fout.beweringen
    assert not [b for b in fout.beweringen if PHR936 in b], "de duiding binnen de periode rust op haar passages"


def test_het_rapport_zegt_wat_er_binnen_de_periode_gelezen_is():
    kind = {"rapport": {"status": "klaar"}, "answer": "Bevindingen.", "source_trace": TRACE, "periode": [2022, 2024]}
    tekst = sub.rapport_tekst(sub.Afloop(profiel="algemeen", uitkomst="klaar"), kind)
    assert "Gekozen periode (door de gebruiker): 2022–2024. Gelezen binnen de periode: 1." in tekst
    assert f"vat ze niet samen): {PHR435}, {HOF1599}." in tekst
    leeg = sub.periode_tekst({"source_trace": TRACE}, (2010, 2015))
    assert "Binnen de periode is niets gelezen: zeg dat de gebruiker." in leeg
    assert sub.rapport_inhoud(kind)["periode"] == [2022, 2024]


def _rapport(*ids: str) -> dict:
    return {"type": "tool_use", "id": "r1", "name": "rapport",
            "input": {"status": "vraag", "bevindingen": " ".join(f"Over {i}." for i in ids)}}


def test_het_hervatte_deel_ziet_alleen_de_tekst_die_zijn_eerste_rapport_noemt():
    vraag = f"{HERVATTING}de gebruiker)\n- Periode?\n  Antwoord: 2022 tot en met 2024"
    lees = [{"type": "tool_use", "id": f"t{i}", "name": n, "input": {}} for i, (n, _) in enumerate(TRACE)]
    uit = [{"type": "tool_result", "tool_use_id": f"t{i}", "content": t} for i, (_, t) in enumerate(TRACE)]
    messages = [{"role": "user", "content": "Opdracht: rechtspraak over de melding."},
                {"role": "assistant", "content": lees}, {"role": "user", "content": uit},
                {"role": "assistant", "content": [_rapport(PHR936)]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "r1", "content": "ok"}]},
                {"role": "user", "content": vraag}]
    venster = eerste_deel_ingekort(messages, vraag, {"get_uitspraak"})
    inhoud = {json.loads(b["content"]).get("stuk", {}).get("id"): b["content"] for b in venster[2]["content"]
              if b["tool_use_id"] != "t0"}
    assert inhoud[PHR936] == TRACE[2][1], "wat het rapport noemt, blijft heel"
    assert INGEKORT in inhoud[PHR435] and INGEKORT in inhoud[HOF1599]
    assert len(json.dumps(venster)) < len(json.dumps(messages))
    assert venster[2]["content"][0] == messages[2]["content"][0], "een zoekresultaat blijft"
    assert messages[2]["content"][1]["content"] == TRACE[1][1], "de berichten zelf blijven heel (de trace)"
    # Geen hervatting, of geen rapport: alles blijft.
    assert eerste_deel_ingekort(messages, "Opdracht: rechtspraak over de melding.", {"get_uitspraak"}) is messages
    zonder = [m for m in messages if m["role"] != "assistant" or m["content"][0]["name"] != "rapport"]
    assert eerste_deel_ingekort(zonder, vraag, {"get_uitspraak"}) is zonder


# --- 3. de afbakening bereikt de jurist ----------------------------------------------------------------------------

def test_de_afbakening_staat_onder_het_eindantwoord_en_op_de_kindregel():
    state = {"subagenten": [{"uitkomst": "klaar", "afbakening": ["tekst: huidige tekst"]}]}
    regel = antwoordnodes.afbakening_regel(state, ANTWOORD_936)
    assert regel.startswith("De subagent beperkte het zoeken zelf") and "tekst: huidige tekst" in regel
    assert not antwoordnodes.afbakening_regel(state, "Alleen bij de huidige tekst van artikel 36 gezocht.")
    assert not antwoordnodes.afbakening_regel({**state, "opdracht": {"doel": "x"}}, ANTWOORD_936)
    afloop = sub.Afloop(profiel="algemeen", uitkomst="klaar", afbakening=["tekst: huidige tekst"], periode=[2022, 2024])
    assert afloop.als_dict()["afbakening"] == ["tekst: huidige tekst"] and afloop.als_dict()["periode"] == [2022, 2024]
    assert "afbakening" not in sub.Afloop(profiel="algemeen").als_dict()


def test_finalize_zet_de_afbakening_onder_het_antwoord(monkeypatch):
    gezien: list[dict] = []
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: gezien.append)
    state = {"answer": ANTWOORD_936, "subagenten": [{"uitkomst": "klaar", "afbakening": ["tekst: huidige tekst"]}],
             "source_trace": TRACE, "messages": []}
    try:
        antwoordnodes.finalize_node(None, state)
    except Exception:  # noqa: BLE001 – na het token hoeft de rest van finalize hier niet te lukken
        pass
    token = next(e["content"] for e in gezien if e.get("type") == "token")
    assert token.startswith(ANTWOORD_936) and token.endswith("Wil je dat breder, zeg het dan.")


# --- 4. een letter uit een ander schrift ---------------------------------------------------------------------------

def test_een_letter_uit_een_ander_schrift_is_een_spelfout(monkeypatch):
    assert vreemd_schrift(ANTWOORD_435) == ["spelling: 'niet-melدende' bevat een letter uit een ander schrift"]
    assert not vreemd_schrift("café, naïef, œuvre, Ελλάδα en het Unierechtelijke beginsel")
    assert "spelling: 'niet-melدende' bevat een letter uit een ander schrift" in check_grounding(
        ANTWOORD_435, TRACE, bekend=ANTWOORDEN).beweringen
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: lambda _e: None)
    uit = antwoordnodes.correct_node(None, {"beweringen": ["spelling: 'niet-melدende' bevat een letter uit een ander schrift"]})
    tekst = uit["messages"][0]["content"]
    assert "Herstel de spelling: 'niet-melدende'" in tekst and "Je schreef als feit" not in tekst
