"""Het toetsrapport van de contenttoets (plan contenttoets, C1): het model wijst aan, de code vult en toetst.

De brontekst is letterlijk die van de Leidraad Invordering 2008 (art. 25.3a.1 en 25.5.3, toestand 1 juli 2026); de content
is een zelfgemaakte testtekst met een bewust geplaatste fout.
"""
from __future__ import annotations

import json

import pytest
from bronmodel.antwoord import Antwoord, antwoord_tekst, toets_telling

from agent.sjablonen import SJABLONEN, Onvulbaar, vul
from agent.sjablonen.contenttoets import (CONTENT_TOOL, MAX_BEVINDINGEN, NAAM, SCHEMA, content_resultaat, content_van,
                                          plek_in)

LI = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25"
STANDAARD = f"{LI}%2FCirculaire.divisie25.3a%2FCirculaire.divisie25.3a.1"
KORT = f"{LI}%2FCirculaire.divisie25.5%2FCirculaire.divisie25.5.3"
TEKST_STANDAARD = ("De ontvanger kan op verzoek van de belastingschuldige een standaardbetalingsregeling verlenen met een "
                   "looptijd van maximaal twaalf maanden, gerekend vanaf de datum waarop de ontvanger de "
                   "betalingsregeling bij beschikking verleent. De belastingschuldige betaalt de belastingschuld in "
                   "gelijke maandelijkse termijnen van ten minste € 20.")
TEKST_KORT = ("Op schriftelijk of telefonisch verzoek kan zonder nader onderzoek een betalingsregeling worden getroffen "
              "met een looptijd tot maximaal vier maanden na de laatste vervaldag van de (oudste) aanslag, als aan de "
              "volgende cumulatieve voorwaarden is voldaan:")
CONTENT = ("Standaardbetalingsregeling\n\nU betaalt uw belastingschuld in maximaal 24 maanden, in gelijke termijnen van "
           "minimaal € 20 per maand. Of u krijgt 4 maanden kort uitstel.")


def bepaling() -> tuple[str, str]:
    return "get_bepaling", json.dumps({"status": "ok", "volledig": True, "aantal": 2, "resultaten": [
        {"iri": STANDAARD, "nummer": "25.3a.1", "tekst": TEKST_STANDAARD, "citeertitel": "Leidraad Invordering 2008"},
        {"iri": KORT, "nummer": "25.5.3", "tekst": TEKST_KORT, "citeertitel": "Leidraad Invordering 2008"},
    ]}, ensure_ascii=False)


def trace(content: str = CONTENT, peildatum: str = "2026-11-25") -> list[tuple[str, str]]:
    return [(CONTENT_TOOL, content_resultaat(content, peildatum)), bepaling()]


def bevinding(citaat: str, oordeel: str, criterium: str = "", bron=None, **rest) -> dict:
    return {"citaat": citaat, "oordeel": oordeel, "criterium": criterium, "bron": bron or [], "toelichting": "",
            "twijfel": "", "voorstel": "", **rest}


TWAALF = {"bepaling": STANDAARD, "van": "een looptijd van maximaal", "tot": "twaalf maanden"}
TWINTIG = {"bepaling": STANDAARD, "van": "De belastingschuldige betaalt", "tot": "ten minste € 20."}
VIER = {"bepaling": KORT, "van": "met een looptijd tot", "tot": "de (oudste) aanslag"}


def invoer(*bevindingen, **rest) -> dict:
    return {"kort_antwoord": "Getoetst tegen de Leidraad: de looptijd klopt niet.", "voor_redacteur": [],
            "bevindingen": list(bevindingen), "ontbreekt": [], "niet_getoetst": [], **rest}


def rapport(a: Antwoord):
    return next(b for b in a.blokken if b.soort == "contenttoets")


def test_het_sjabloon_staat_in_het_register_en_is_strict():
    assert SJABLONEN[NAAM].schema is SCHEMA
    assert SCHEMA["strict"] is True
    item = SCHEMA["input_schema"]["properties"]["bevindingen"]["items"]
    assert set(item["required"]) == set(item["properties"]) and item["additionalProperties"] is False


def test_de_code_vult_citaat_plek_en_letterlijke_bron():
    a = vul(NAAM, invoer(
        bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF], toelichting="De Leidraad noemt twaalf.",
                  voorstel="U betaalt uw belastingschuld in maximaal 12 maanden."),
        bevinding("gelijke termijnen van minimaal € 20 per maand", "juist", "", [TWINTIG], voorstel="genegeerd")),
        trace())
    assert a.sjabloon == "contenttoets" and a.blokken[0].soort == "toelichting"
    r = rapport(a)
    eerste, tweede = r.bevindingen
    assert (eerste.nr, eerste.oordeel, eerste.criterium) == (1, "mogelijk_onjuist", "J1")
    assert CONTENT[eerste.begin:eerste.eind] == eerste.citaat == "maximaal 24 maanden"
    assert eerste.bronnen[0].tekst == "een looptijd van maximaal twaalf maanden"
    assert eerste.bronnen[0].vindplaats.iri == STANDAARD
    assert tweede.voorstel == ""                        # een juiste bewering krijgt geen voorstel
    assert r.peildatum == "2026-11-25" and r.content == CONTENT
    assert r.getoetst_tegen == ["Leidraad Invordering 2008"]
    assert [d.iri for d in a.doelen] == [STANDAARD]


def test_de_bevindingen_staan_in_de_volgorde_van_de_content():
    a = vul(NAAM, invoer(bevinding("4 maanden kort uitstel", "onvolledig", "V1", [VIER]),
                         bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF])), trace())
    assert [(b.nr, b.citaat) for b in rapport(a).bevindingen] == [(1, "maximaal 24 maanden"),
                                                                    (2, "4 maanden kort uitstel")]


def test_een_citaat_wordt_gevonden_ongeacht_witruimte_en_typografie():
    content = "Het is “maximaal\n24  maanden” – zegt de tekst."
    assert plek_in('"maximaal 24 maanden" - zegt', content) == (7, content.index("zegt") + 4)
    assert plek_in("maximaal 25 maanden", content) is None


def test_een_citaat_dat_niet_in_de_content_staat_gaat_terug():
    with pytest.raises(Onvulbaar, match="niet letterlijk in de content") as fout:
        vul(NAAM, invoer(bevinding("maximaal 36 maanden", "mogelijk_onjuist", "J1", [TWAALF])), trace())
    assert fout.value.code == "niets_te_tonen"


def test_mogelijk_onjuist_zonder_bronpassage_bestaat_niet():
    with pytest.raises(Onvulbaar, match="niet_in_de_bron"):
        vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [])), trace())


def test_een_bronpassage_die_niet_in_de_bron_staat_gaat_terug():
    vals = {"bepaling": STANDAARD, "van": "een looptijd van maximaal", "tot": "vierentwintig maanden"}
    with pytest.raises(Onvulbaar):
        vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [vals])), trace())


def test_niet_in_de_bron_mag_zonder_passage():
    a = vul(NAAM, invoer(bevinding("4 maanden kort uitstel", "niet_in_de_bron", "", [],
                                   voorstel="Waar komt deze termijn vandaan?")), trace())
    b = rapport(a).bevindingen[0]
    assert b.oordeel == "niet_in_de_bron" and b.bronnen == [] and b.voorstel.startswith("Waar")


@pytest.mark.parametrize("oordeel,criterium", [("mogelijk_onjuist", "V1"), ("mogelijk_onjuist", ""),
                                               ("juist", "V2"), ("onvolledig", "X9")])
def test_het_criterium_past_bij_het_oordeel(oordeel, criterium):
    with pytest.raises(Onvulbaar, match="past niet bij"):
        vul(NAAM, invoer(bevinding("maximaal 24 maanden", oordeel, criterium, [TWAALF])), trace())


def test_wat_niet_te_tonen_is_valt_weg_met_een_leemte_als_er_iets_overblijft():
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF]),
                         bevinding("bestaat niet", "juist", "", [TWINTIG])), trace())
    assert len(rapport(a).bevindingen) == 1
    assert a.blokken[-1].soort == "leemte" and "1 bevinding is niet getoond" in a.blokken[-1].tekst


def test_zonder_content_in_de_trace_geen_rapport():
    with pytest.raises(Onvulbaar) as fout:
        vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF])), [bepaling()])
    assert fout.value.code == "geen_content"


def test_de_laatste_content_in_de_trace_telt():
    t = [(CONTENT_TOOL, content_resultaat("oud")), (CONTENT_TOOL, content_resultaat("nieuw", "2026-01-01"))]
    assert content_van(t) == {**json.loads(content_resultaat("nieuw", "2026-01-01"))}


def test_ontbreekt_rust_op_een_passage():
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF]),
                         ontbreekt=[{"wat": "Kort uitstel telt vanaf de laatste vervaldag.", "bron": [VIER]},
                                    {"wat": "Iets zonder bron.", "bron": []}]), trace())
    r = rapport(a)
    assert [o.tekst for o in r.ontbreekt] == ["Kort uitstel telt vanaf de laatste vervaldag."]
    assert "Leemte" not in toets_telling(r) and toets_telling(r) == "1 bewering: 1 mogelijk onjuist. 1 punt ontbreekt."


def test_het_rapport_als_tekst_heeft_twee_lagen_en_geen_tabel():
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF],
                                   voorstel="U betaalt in maximaal 12 maanden."),
                         voor_redacteur=["[1] Zet de looptijd op 12 maanden."], niet_getoetst=["Het formulier."]),
            trace())
    tekst = antwoord_tekst(a)
    assert "**Voor de redacteur**\n\n- [1] Zet de looptijd op 12 maanden." in tekst
    assert "**[1] Mogelijk onjuist** · J1 Waarde" in tekst
    assert '> "een looptijd van maximaal twaalf maanden"' in tekst
    assert "Voorstel: U betaalt in maximaal 12 maanden." in tekst        # geen citaat: tekst van Lex
    assert "**Niet getoetst**\n\n- Het formulier." in tekst
    assert "|" not in tekst


def test_het_rapport_begrenst_het_aantal_bevindingen():
    veel = [bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF])] * (MAX_BEVINDINGEN + 2)
    a = vul(NAAM, invoer(*veel), trace())
    assert len(rapport(a).bevindingen) == 1                              # dezelfde plek telt één keer
    assert any(b.soort == "leemte" and "eerste 30" in b.tekst for b in a.blokken)
