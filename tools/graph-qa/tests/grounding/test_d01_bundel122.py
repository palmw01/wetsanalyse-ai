"""D01 uit de controlemeting van bundel 122 (14 nov 2026): de controles waren te streng. Nepbronnen in de echte vorm
(`get_uitspraak` door de echte toollaag), met de kopregels van een arrest; de bevindingen staan er letterlijk (ingekort
tot de stukken die de test nodig heeft), en de aanwijzingen zoals het kind ze gaf.

1. Het kind wees hele reeksen aan (alinea 1–35 en 1–59); de grens van 48 alinea's was op bij de eerste twee stukken, de
   citaten waren vooral kopregels, en HR:2023:563 en :176 hielden geen passage. HR:2023:181 en PHR:2024:936 vielen boven
   de grens van vier stukken. De centrale agent haalde daarna vier juiste samenvattingen weg.
2. De zin die zegt dat ze niet samengevat zijn, telde daarna nog als duiding zonder passage.
3. De woordtoets trof een opsomming onder *Gedaan*."""
from __future__ import annotations

import json

from agent import sjablonen
from agent import subagent as sub
from agent.gelezen import vraag_niet_in_stuk, zonder_steun
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from agent import tools
from test_rechtspraak_tools import AAN, V_NU, Link, NepBron

HR1371, PHR435, HR563, HR176, HR181, PHR936 = (
    "ECLI:NL:HR:2023:1371", "ECLI:NL:PHR:2025:435", "ECLI:NL:HR:2023:563", "ECLI:NL:HR:2023:176",
    "ECLI:NL:HR:2023:181", "ECLI:NL:PHR:2024:936")
KOP = ["HOGE RAAD DER NEDERLANDEN", "BELASTINGKAMER", "Nummer 21/03566", "ARREST", "in de zaak van", "tegen",
       "de STAATSSECRETARIS VAN FINANCIËN"]
INHOUD = {
    HR1371: ["De melding moet plaatsvinden binnen twee weken nadat de belasting uiterlijk betaald had moeten zijn.",
             "Bij een correcte melding draagt de ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur."],
    PHR435: ["Het HvJ EU antwoordt dat de Nederlandse meldingsregeling niet in strijd is met het Unierechtelijke "
             "evenredigheidsbeginsel.", "Ik, A-G Koopman, bespreek vijf lichtpuntjes om de hardheid van de regeling te "
             "verzachten."],
    HR563: ["Na het faillissement heeft de curator met de bestuurder een schikking getroffen wegens onbehoorlijk bestuur.",
            "Het Hof heeft de aansprakelijkstelling vernietigd op grond van artikel 36.1 van de Leidraad Invordering 2008."],
    HR176: ["Het gaat om de vraag of schending van het Unierechtelijke verdedigingsbeginsel tot vernietiging leidt.",
            "Het Hof had het betoog van de ontvanger dat het horen niet tot een andere afloop had kunnen leiden niet mogen "
            "passeren."],
    HR181: ["Voor twee tijdvakken heeft de BV tijdig en rechtsgeldig mededeling gedaan van haar onvermogen tot betaling.",
            "Het Hof had moeten onderzoeken of de begunstigde schuldeisers gelieerd waren en of de bestuurder een "
            "persoonlijk belang had bij de betalingen."],
    PHR936: ["De vraag is of uitstel van betaling voor de aansprakelijkheidsschuld ook de verjaringstermijn van de "
             "onderliggende belastingschuld verlengt.", "Die vraag beantwoord ik ontkennend."],
}
DATUM = {HR1371: "2023-10-06", PHR435: "2025-04-11", HR563: "2023-04-14", HR176: "2023-02-10", HR181: "2023-02-10",
         PHR936: "2024-09-13"}


def _xml(ecli: str) -> bytes:
    orgaan = "Parket bij de Hoge Raad" if ":PHR:" in ecli else "Hoge Raad"
    paras = "".join(f"<para>{a}</para>" for a in [*KOP, *INHOUD[ecli]])
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>{orgaan}</dcterms:creator>
  <dcterms:date>{DATUM[ecli]}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Artikel 36 IW 1990; bestuurdersaansprakelijkheid.</para></inhoudsindicatie>
<uitspraak><section><title>Beoordeling</title>{paras}</section></uitspraak></open-rechtspraak>""".encode()


BRON = NepBron([Link(e, f"{e} - Hoge Raad, 01-01-2023 / 2{i}/00{i}", "Door computer herkende referentie", V_NU)
                for i, e in enumerate(INHOUD)], docs={e: _xml(e) for e in INHOUD})
TRACE = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=BRON)) for e in INHOUD]
RIJEN = {e: len(KOP) + len(INHOUD[e]) + 1 for e in INHOUD}

#: Uit het tweede rapport, letterlijk (de alinea's over de zes stukken, ingekort).
BEVINDINGEN = (
    "**1. Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371 (tussenbeslissing; prejudiciële vragen aan HvJ EU)** De melding "
    "moet plaatsvinden binnen twee weken nadat de belasting uiterlijk betaald had moeten zijn. Bij correcte melding draagt "
    "de ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur.\n\n"
    "**2. Conclusie A-G Koopman 11 april 2025, ECLI:NL:PHR:2025:435** Het HvJ EU antwoordt dat de Nederlandse "
    "meldingsregeling niet in strijd is met het Unierechtelijke evenredigheidsbeginsel. A-G Koopman bespreekt vijf "
    "lichtpuntjes om de hardheid van de regeling te verzachten.\n\n"
    "**3. Hoge Raad 14 april 2023, ECLI:NL:HR:2023:563 (schikking curator / Leidraad Invordering 2008)** Het Hof had de "
    "aansprakelijkstelling vernietigd op grond van art. 36.1 Leidraad Invordering 2008 na een schikking tussen bestuurder "
    "en curator.\n\n"
    "**4. Hoge Raad 10 februari 2023, ECLI:NL:HR:2023:176 (Unierechtelijk verdedigingsbeginsel / andere-afloopcriterium)** "
    "De Hoge Raad casseert: het Hof had het gemotiveerde betoog van de ontvanger dat het horen niet tot een andere afloop "
    "had kunnen leiden, niet mogen passeren.\n\n"
    "**5. Hoge Raad 10 februari 2023, ECLI:NL:HR:2023:181 (kennelijk onbehoorlijk bestuur na rechtsgeldige melding)** De BV "
    "had voor twee tijdvakken tijdig en rechtsgeldig gemeld. De Hoge Raad casseert het Hof omdat het niet heeft onderzocht "
    "of de begunstigde schuldeisers gelieerd waren en of de bestuurder een persoonlijk belang had.\n\n"
    "**6. Conclusie A-G Koopman 13 september 2024, ECLI:NL:PHR:2024:936 (verjaring aansprakelijkstelling)** Gaat over de "
    "vraag of uitstel van betaling voor de aansprakelijkheidsschuld ook de verjaringstermijn van de onderliggende "
    "belastingschuld verlengt. A-G Koopman beantwoordt dit ontkennend.")
GEDAAN = ("Gezocht naar alle uitspraken over artikel 36 IW 1990 uit 2022-2024, de inhoudsindicaties en eerste pagina's "
          "gelezen van de meest relevante stukken over de melding van betalingsonmacht: ECLI:NL:HR:2023:1371, "
          "ECLI:NL:PHR:2025:435, ECLI:NL:HR:2023:563, ECLI:NL:HR:2023:176, ECLI:NL:HR:2023:181 en ECLI:NL:PHR:2024:936.")
#: De aanwijzingen zoals het kind ze gaf: hele reeksen vanaf de kop.
EXTERN = [{"id": HR1371, "van_nr": 1, "tot_nr": RIJEN[HR1371]}, {"id": PHR435, "van_nr": 1, "tot_nr": RIJEN[PHR435]},
          {"id": HR563, "van_nr": 1, "tot_nr": RIJEN[HR563]}, {"id": HR176, "van_nr": 1, "tot_nr": RIJEN[HR176]},
          {"id": HR181, "van_nr": 1, "tot_nr": 3}, {"id": PHR936, "van_nr": 1, "tot_nr": 2}]
VRAAG = ("Zoek de rechtspraak over de melding van betalingsonmacht bij artikel 36 van de Invorderingswet 1990 uit de "
         "periode van mijn dossier, en vat per uitspraak samen wat de rechter over de melding zegt.")


def _rapport(extern=EXTERN):
    return sjablonen.vul("rapport", {"status": "klaar", "gedaan": GEDAAN, "bevindingen": BEVINDINGEN, "open": [],
                                     "vragen": [], "onderbouwing": [], "extern": extern}, TRACE)


def test_elk_samengevat_stuk_draagt_een_passage_met_inhoud_en_geen_kopregel():
    antwoord = _rapport()
    blokken = {b.id: b for b in antwoord.blokken if b.soort == "extern"}
    assert set(blokken) == set(INHOUD), "geen stuk boven de grens weg (de grens van het rapport is ruimer)"
    for ident, blok in blokken.items():
        assert blok.passages, f"{ident} heeft een passage"
        assert not any(p.tekst in KOP for p in blok.passages), f"{ident}: een kopregel telt niet als passage"
    # De passages dragen de samenvattingen: de centrale agent haalt ze niet weg.
    steun = sub.steun_van([{"antwoord": antwoord.model_dump()}])
    assert not zonder_steun(BEVINDINGEN, steun, TRACE)
    assert "kopregel zonder inhoud" in json.dumps(antwoord.model_dump(), ensure_ascii=False)


def test_zonder_passage_kiest_de_code_de_alineas_die_bij_de_samenvatting_passen():
    """Wijst het kind bij een stuk alleen de kop aan, of niets, dan kiest de code de alinea's van dat stuk die het meest
    delen met wat erover gezegd wordt: geen extra ronde, en de passage is letterlijk uit het stuk."""
    alleen_kop = [{"id": e, "van_nr": 2, "tot_nr": 4} for e in INHOUD]
    blokken = {b.id: b for b in _rapport(alleen_kop).blokken if b.soort == "extern"}
    assert set(blokken) == set(INHOUD)
    assert any("schikking" in p.tekst for p in blokken[HR563].passages)
    assert any("verdedigingsbeginsel" in p.tekst or "andere afloop" in p.tekst for p in blokken[HR176].passages)
    zonder = {b.id for b in _rapport([]).blokken if b.soort == "extern"}
    assert zonder == set(INHOUD), "ook zonder 'extern'"


def test_een_zin_die_zegt_dat_iets_niet_samengevat_is_is_geen_duiding():
    tekst = (f"**Niet samengevat**\nDe volgende stukken zijn niet samengevat, omdat het rapport er geen passage van "
             f"citeerde: {HR181}, {HR563}, {HR176} en {PHR936}.")
    assert not zonder_steun(tekst, {}, TRACE)
    assert not zonder_steun(f"{HR181} en {PHR936} zijn niet inhoudelijk besproken in dit antwoord, omdat ze buiten "
                            "de kern van de vraag vallen.", {}, TRACE)


def test_gedaan_is_procestekst_en_valt_buiten_de_woordtoets():
    assert vraag_niet_in_stuk(GEDAAN, TRACE, VRAAG), "op de hele tekst zou de opsomming treffen"
    antwoord = _rapport()
    state = {"antwoord": antwoord.model_dump(), "opdracht": {"doel": VRAAG}}
    tekst = antwoordnodes._zonder_gedaan(state)
    assert tekst is not None and "eerste pagina's gelezen" not in tekst and "kennelijk onbehoorlijk" in tekst
    # Op de hele tekst treft 'betalingsonmacht' de opsomming onder Gedaan; zonder Gedaan niet meer.
    assert [b for b in check_grounding(GEDAAN + "\n\n" + BEVINDINGEN, TRACE, vraag=VRAAG).beweringen
            if "'betalingsonmacht'" in b]
    fout = check_grounding(GEDAAN + "\n\n" + BEVINDINGEN, TRACE, vraag=VRAAG, duiding_tekst=tekst)
    assert not [b for b in fout.beweringen if "'betalingsonmacht'" in b]
    assert antwoordnodes._zonder_gedaan({"antwoord": {}}) is None


def test_kopregels_dragen_geen_samenvatting():
    """Punt 3: het eindantwoord zei "gedragen door de passages", en die passages waren de kop van het arrest. Een
    kopregel telt in de steun niet mee, dus de toets ziet dat er niets is waarop de samenvatting rust."""
    kop = [{"tekst": t} for t in KOP]
    assert sub.passagetekst(kop) == ""
    steun = sub.steun_van([{"antwoord": {"blokken": [{"soort": "extern", "id": HR1371, "passages": kop}]}}])
    assert steun == {HR1371: ""}
    tekst = BEVINDINGEN.split("\n\n")[0]
    assert zonder_steun(tekst, steun, TRACE) == [f"duiding van {HR1371} zonder passage van dat stuk in het rapport"]
