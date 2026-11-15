"""D01 uit de controlemeting van bundel 123 (15 nov 2026). Nepbronnen in de echte vorm (`get_uitspraak` door de echte
toollaag): een arrest met kopregels, procesverloop, feiten en genummerde rechtsoverwegingen; de zinnen van het rapport en
het eindantwoord zoals ze in de meting stonden (ingekort tot wat de test nodig heeft).

1. Het kind wees hele reeksen aan; de grens van 48 alinea's hield per stuk de eerste alinea's, dus bij HR:2023:1371 het
   procesverloop en de feiten in plaats van de dragende r.o. 3.3–3.8.
2. In het eindantwoord stonden kopregels van een uitspraak als citaat ("Locatie Arnhem", "nummer ARN-BK 21/117").
3. Vier van de vijf onbevestigde zinnen zeiden dat iets uit de gelezen passages niet vast te stellen was.
4. De controle per stuk draaide niet, omdat de goedkopere toetsen telkens iets vonden; na de correctieronde draait ze."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent import sjablonen
from agent import subagent as sub
from agent.gelezen import zonder_steun
from agent.nodes import antwoord as antwoordnodes
from agent import tools
from test_rechtspraak_tools import AAN, V_NU, Link, NepBron

HR1371, GHARL, GHAMS, PHR936 = ("ECLI:NL:HR:2023:1371", "ECLI:NL:GHARL:2024:1513", "ECLI:NL:GHAMS:2023:2936",
                                "ECLI:NL:PHR:2024:936")
ANDERE = [f"ECLI:NL:HR:2023:{n}" for n in (101, 102, 103, 104, 105)]

KOP_ARREST = ["HOGE RAAD DER NEDERLANDEN", "BELASTINGKAMER", "Nummer 21/03566", "Datum 6 oktober 2023", "ARREST"]
PROCES = ["op het beroep in cassatie tegen de uitspraak van het Gerechtshof Den Haag van 1 juni 2021.",
          "Belanghebbende, vertegenwoordigd door een gemachtigde, heeft tegen de uitspraak van het Hof beroep in cassatie "
          "ingesteld.", "De Staatssecretaris heeft een verweerschrift ingediend.",
          "Belanghebbende heeft een conclusie van repliek ingediend."]
FEITEN = {"2.1": "Belanghebbende was bestuurder en enig aandeelhouder van een holdingvennootschap die op haar beurt "
                 "bestuurder was van de vennootschap.",
          "2.2": "Aan de vennootschap zijn naheffingsaanslagen in de loonheffingen opgelegd over de jaren 2016 en 2017.",
          "2.3": "Bij beschikking van 5 juli 2019 heeft de Ontvanger belanghebbende aansprakelijk gesteld.",
          "3.1": "Met het oog op de hierna te formuleren prejudiciële vragen zal de Hoge Raad eerst het nationale recht "
                 "uiteenzetten."}
DRAGEND = {"3.3": "De melding van betalingsonmacht moet schriftelijk plaatsvinden binnen twee weken na het tijdstip "
                  "waarop de belasting uiterlijk betaald had moeten zijn.",
           "3.4": "Is niet tijdig gemeld, dan wordt vermoed dat de niet-betaling aan de bestuurder te wijten is, en kan "
                  "hij dat vermoeden alleen weerleggen met de stelling dat het niet melden hem niet te verwijten is.",
           "3.5": "Bij een correcte melding draagt de ontvanger de bewijslast dat de niet-betaling het gevolg is van "
                  "kennelijk onbehoorlijk bestuur.",
           "3.6": "Een bestuurder die niet heeft gemeld, kan het bewijs van het tegendeel niet leveren met feiten over "
                  "de oorzaak van de niet-betaling.",
           "3.7": "Die bewijsbeperking geldt ook als de bestuurder stelt dat de betalingsonmacht niet aan hem te wijten "
                  "is.",
           "3.8": "De Hoge Raad vraagt het Hof van Justitie of deze bewijsbeperking verenigbaar is met het Unierechtelijke "
                  "evenredigheidsbeginsel."}


def _paragroups(stukken: dict[str, str]) -> str:
    return "".join(f"<paragroup><nr>{nr}</nr><para>{t}</para></paragroup>" for nr, t in stukken.items())


def _xml(ecli: str, inhoud: str, orgaan: str = "Hoge Raad", datum: str = "2023-10-06") -> bytes:
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>{orgaan}</dcterms:creator>
  <dcterms:date>{datum}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Artikel 36 IW 1990; bestuurdersaansprakelijkheid; bewijspositie bestuurder.</para></inhoudsindicatie>
<uitspraak>{inhoud}</uitspraak></open-rechtspraak>""".encode()


def _arrest() -> str:
    kop = "".join(f"<para>{t}</para>" for t in [*KOP_ARREST, PROCES[0]])
    proces = "".join(f"<para>{t}</para>" for t in PROCES[1:])
    return (f"{kop}<section><title><nr>1</nr>Geding in cassatie</title>{proces}</section>"
            f"<section><title><nr>2</nr>Uitgangspunten in cassatie</title>{_paragroups({k: v for k, v in FEITEN.items() if k < '3'})}</section>"
            f"<section><title><nr>3</nr>Het nationale recht</title>{_paragroups({'3.1': FEITEN['3.1']})}"
            f"{_paragroups(DRAGEND)}</section>")


#: De kop van een hofuitspraak zoals in de meting: korte regels zonder inhoud.
KOP_HOF = ["Locatie Arnhem", "nummer ARN-BK 21/117", "uitspraakdatum: 27 februari 2024"]
HOF = ("".join(f"<para>{t}</para>" for t in [*KOP_HOF, "uitspraak van de vierde meervoudige belastingkamer"])
       + "<section><title><nr>1</nr>Ontstaan en loop van het geding</title>"
       + _paragroups({"1.1": "De Ontvanger heeft belanghebbende bij beschikking van 3 december 2018 als bestuurder "
                             "aansprakelijk gesteld voor de loonheffingen van de vennootschap."}) + "</section>")
OVERIG = ("".join(f"<para>{t}</para>" for t in KOP_ARREST)
          + "<section><title><nr>2</nr>Beoordeling</title>"
          + _paragroups({f"2.{i}": f"Overweging {i} over een ander onderwerp dan de melding, met een eigen strekking voor "
                                   f"deze zaak." for i in range(1, 11)}) + "</section>")

DOCS = {HR1371: _xml(HR1371, _arrest()), GHARL: _xml(GHARL, HOF, "Gerechtshof Arnhem-Leeuwarden", "2024-02-27"),
        **{e: _xml(e, OVERIG) for e in ANDERE}}
BRON = NepBron([Link(e, f"{e} - Hoge Raad, 01-01-2023 / 2{i}/00{i}", "Door computer herkende referentie", V_NU)
                for i, e in enumerate(DOCS)], docs=DOCS)
TRACE = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=BRON)) for e in DOCS]


def _rijen(ecli: str) -> list[dict]:
    from agent.tools.stuk_tekst import aangevuld

    return next(aangevuld(d) for _n, r in TRACE if (d := json.loads(r)).get("stuk", {}).get("id") == ecli)


#: Het rapport over HR:2023:1371, zoals het kind het samenvatte: de dragende overwegingen over de melding.
BEVINDINGEN = (
    "**1. Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371 (prejudiciële vragen)** De melding van betalingsonmacht moet "
    "schriftelijk binnen twee weken plaatsvinden. Wie niet tijdig meldt, wordt vermoed schuldig te zijn en kan het "
    "tegendeel niet bewijzen met feiten over de oorzaak van de niet-betaling. Bij een correcte melding draagt de "
    "ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur. De Hoge Raad vraagt het Hof van Justitie of die "
    "bewijsbeperking verenigbaar is met het evenredigheidsbeginsel.\n\n"
    + "\n\n".join(f"**{i}. {e}** Overweging over een ander onderwerp dan de melding, met een eigen strekking voor deze "
                  "zaak." for i, e in enumerate(ANDERE, 2)))
GEDAAN = "Gezocht naar uitspraken over artikel 36 IW 1990 en de gevonden stukken gelezen."
#: Het kind wees bij elk stuk alles aan, vanaf de kop: samen boven de grens van 48 alinea's.
EXTERN = [{"id": e, "van_nr": 1, "tot_nr": len(_rijen(e))} for e in [HR1371, *ANDERE]]


def _rapport():
    return sjablonen.vul("rapport", {"status": "klaar", "gedaan": GEDAAN, "bevindingen": BEVINDINGEN, "open": [],
                                     "vragen": [], "onderbouwing": [], "extern": EXTERN}, TRACE)


def test_de_grens_houdt_per_stuk_de_dragende_rechtsoverwegingen():
    assert sum(len(_rijen(e)) for e in [HR1371, *ANDERE]) > 48, "de test gaat over het afkappen"
    antwoord = _rapport()
    blok = next(b for b in antwoord.blokken if b.soort == "extern" and b.id == HR1371)
    plekken = {p.plek for p in blok.passages}
    assert {f"r.o. {nr}" for nr in DRAGEND} <= plekken, plekken
    assert not {p.tekst for p in blok.passages} & {*PROCES, *KOP_ARREST}, "geen procesverloop of kopregel"
    assert [p.nr for p in blok.passages] == sorted(p.nr for p in blok.passages), "op nummer getoond"
    # Wat wegviel, staat in de melding; de samenvatting rust op de passages.
    assert "Niet geciteerd" in json.dumps(antwoord.model_dump(), ensure_ascii=False)
    steun = sub.steun_van([{"antwoord": antwoord.model_dump()}])
    assert not zonder_steun(BEVINDINGEN.split("\n\n")[0], steun, TRACE)


def test_kopregels_van_een_uitspraak_staan_niet_als_citaat_in_het_antwoord():
    antwoord = sjablonen.vul("antwoord_extern", {
        "kort_antwoord": "Het hof oordeelt over de aansprakelijkstelling van de bestuurder.",
        "extern": [{"id": GHARL, "van_nr": 1, "tot_nr": len(_rijen(GHARL))}], "stukken": [], "twijfel": []}, TRACE)
    blok = next(b for b in antwoord.blokken if b.soort == "extern")
    teksten = [p.tekst for p in blok.passages]
    assert not set(teksten) & set(KOP_HOF), teksten
    assert any("aansprakelijk gesteld" in t for t in teksten)
    assert "kopregel" not in json.dumps(antwoord.model_dump(), ensure_ascii=False), "in een antwoord zonder melding"


def test_een_zin_dat_iets_niet_vast_te_stellen_is_is_geen_duiding():
    """De vier valse onbevestigde zinnen uit de meting, letterlijk: een zin over wat er gelezen is, niet over het stuk."""
    steun = {HR1371: "De melding moet binnen twee weken plaatsvinden."}
    for zin in (f"{GHARL}: Wat het hof over de melding overweegt, is op basis van de gelezen passages niet vast te "
                "stellen, want alleen de kop en het procesverloop zijn gelezen.",
                f"{GHAMS}: Die bevatten geen inhoudelijk oordeel over de meldingsplicht van de bestuurder in deze zaak.",
                f"{PHR936}: De meldingsplicht zelf komt in de gelezen passages niet inhoudelijk aan bod in deze conclusie."):
        assert not zonder_steun(zin, steun, TRACE), zin
    # Een gewone duiding zonder steun blijft een bewering.
    assert zonder_steun(f"{GHARL}: Het hof oordeelt dat de melding te laat was en de bestuurder dus aansprakelijk "
                        "blijft voor de naheffingen.", steun, TRACE)


def test_de_controle_per_stuk_draait_na_de_correctieronde(monkeypatch):
    """Vonden de goedkopere toetsen iets, dan draaide de controle per stuk niet; na de correctieronde draait ze altijd,
    op wat er dan staat."""
    aanroepen = []

    def controleer(llm, settings, tekst, steun, trace, meting=None):
        aanroepen.append(tekst)
        return []

    import agent.stukcontrole as stukcontrole

    monkeypatch.setattr(stukcontrole, "controleer", controleer)
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda *_a, **_k: None))
    antwoord = _rapport()
    b = SimpleNamespace(llm=object(), graph=None, settings=SimpleNamespace(grounding_correct=True))
    # Een feit zonder bron in de toelichting: de goedkopere toets vindt iets.
    state = {"antwoord": antwoord.model_dump(), "source_trace": TRACE, "messages": [], "question": "Wat zegt HR?",
             "run_id": "t"}
    monkeypatch.setattr(antwoordnodes, "check_grounding", lambda *a, **k: _rapportage(["een feit zonder bron"]))
    monkeypatch.setattr(antwoordnodes, "voorbij_laatste", lambda *_a: False)
    antwoordnodes.verify_node(b, state)
    assert not aanroepen, "vóór de correctie wacht ze op de correctieronde"
    antwoordnodes.verify_node(b, {**state, "corrected": True})
    assert len(aanroepen) == 1, "na de correctieronde draait ze"


def _rapportage(beweringen):
    from agent.grounding import GroundingReport

    return GroundingReport(grounded=True, cited=[], unsupported=[], niet_letterlijk=[], onbevestigd=[],
                           beweringen=beweringen, niveau="gegrond")
