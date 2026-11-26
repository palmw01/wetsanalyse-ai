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


def test_alleen_een_passage_uit_de_kennisgraaf_draagt_een_bevinding():
    # Besluit 26 nov 2026: de contenttoets baseert zich alleen op de kennisgraaf, geen connector en geen live wettekst.
    live = {"bepaling": "bwb:BWBR0002320:2026-01-01:artikel:3", "van": "een looptijd van maximaal", "tot": "twaalf maanden"}
    with pytest.raises(Onvulbaar, match="niet in de kennisgraaf"):
        vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [live])), trace())


def test_een_passage_van_buiten_de_graaf_valt_weg_naast_een_uit_de_graaf():
    standpunt = {"bepaling": "kg:KG:204:2026:5", "van": "De ontvanger", "tot": "verlenen"}
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [standpunt, TWAALF])), trace())
    assert [br.vindplaats.iri for br in rapport(a).bevindingen[0].bronnen] == [STANDAARD]


def test_het_profiel_heeft_geen_connectors():
    from agent.profielen import PROFIELEN
    assert PROFIELEN["contenttoets"].connectors == ()


def test_een_regel_voor_de_redacteur_bij_een_weggevallen_bevinding_valt_mee_weg():
    # Meting C5 (standaardregeling): de citaatcontrole liet bevinding 4 vallen, en "[4]" wees daarna naar bevinding 5.
    weg = bevinding("dit staat er niet", "mogelijk_onjuist", "J1", [TWAALF])
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF]), weg,
                         bevinding("minimaal € 20 per maand", "juist", "J1", [TWINTIG]),
                         voor_redacteur=["[1] Maak er 12 maanden van.", "[2] Schrap dit.", "[3] Laat staan.",
                                         "Lees de hele tekst nog eens na."]), trace())
    assert rapport(a).voor_redacteur == ["[1] Maak er 12 maanden van.", "[2] Laat staan.",
                                         "Lees de hele tekst nog eens na."]


def test_de_verwijzing_volgt_de_volgorde_van_de_content():
    # Het model zette de bevindingen niet in de volgorde van de content: het rapport nummert om, de regels ook.
    a = vul(NAAM, invoer(bevinding("4 maanden kort uitstel", "niet_in_de_bron"),
                         bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF]),
                         voor_redacteur=["[2] Maak er 12 maanden van.", "[1] Waar komt dit vandaan?"]), trace())
    r = rapport(a)
    assert [b.citaat for b in r.bevindingen] == ["maximaal 24 maanden", "4 maanden kort uitstel"]
    assert r.voor_redacteur == ["[1] Maak er 12 maanden van.", "[2] Waar komt dit vandaan?"]


def test_een_spatie_na_het_eurosteken_is_opmaak():
    # Run 1104571876 (C5): het citaat over € 20 viel weg; de graaf schrijft "€ 20", het model "€20" of omgekeerd.
    content = CONTENT.replace("€ 20", "€ 20")
    zonder = {"bepaling": STANDAARD, "van": "termijnen van ten minste €20.", "tot": "€20."}
    a = vul(NAAM, invoer(bevinding("minimaal €20 per maand", "juist", "J1", [zonder])), trace(content))
    b = rapport(a).bevindingen[0]
    assert b.citaat == "minimaal € 20 per maand" and b.bronnen[0].tekst.endswith("ten minste € 20.")
    assert plek_in("€ 20", "kost €20") == (5, 8)


TOESLAG = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.7"
TEKST_TOESLAG = ("De standaardbetalingsregeling gaat uit van een af te lossen bedrag van € 20 per maand voor iedere "
                 "terugvordering afzonderlijk. De belanghebbende lost de toeslagschuld af door maandelijks het "
                 "termijnbedrag over te maken. Wanneer een belanghebbende niet aan zijn aflossingsverplichtingen voldoet "
                 "wordt de betalingsregeling beëindigd.")


def _na_te_lopen(a: Antwoord) -> list[str]:
    """Wat de controlestap vond: sinds C5b punten onder Ontbreekt, met de tekst uit de code en de zinnen als citaat."""
    return [o.tekst + " " + " ".join(f"“{b.tekst}”" for b in o.bronnen) for o in rapport(a).ontbreekt
            if o.tekst.startswith("Uit de controle")]


def test_de_controle_per_bepaling_noemt_een_gevolg_dat_rapport_en_tekst_missen():
    # Meting C5, 79.7: de beëindiging bij niet nakomen stond in de gelezen bepaling, het rapport noemde haar niet.
    content = "U betaalt € 25 per maand per terugvordering."
    tr = [(CONTENT_TOOL, content_resultaat(content)), ("get_bepaling", json.dumps({
        "status": "ok", "volledig": True, "aantal": 0, "resultaten": [],
        "bepaling": {"iri": TOESLAG, "nummer": "79.7", "tekst": TEKST_TOESLAG, "label": "Toeslagschuld"}}, ensure_ascii=False))]
    a = vul(NAAM, invoer(bevinding("€ 25 per maand", "mogelijk_onjuist", "J1",
                                   [{"bepaling": TOESLAG, "van": "De standaardbetalingsregeling", "tot": "afzonderlijk."}])), tr)
    [melding] = _na_te_lopen(a)
    assert "“Wanneer een belanghebbende niet aan zijn aflossingsverplichtingen voldoet wordt de betalingsregeling beëindigd.”" in melding
    assert "termijnbedrag" not in melding  # geen voorwaarde, gevolg of uitzondering
    assert "€ 20 per maand" not in melding  # dat citeert het rapport al


def test_wat_de_content_al_noemt_hoeft_niet_nagelopen():
    content = "U betaalt € 25 per maand. Betaalt u niet, dan wordt de betalingsregeling beëindigd."
    tr = [(CONTENT_TOOL, content_resultaat(content)), ("get_bepaling", json.dumps({
        "status": "ok", "volledig": True, "aantal": 0, "resultaten": [],
        "bepaling": {"iri": TOESLAG, "nummer": "79.7", "tekst": TEKST_TOESLAG}}, ensure_ascii=False))]
    a = vul(NAAM, invoer(bevinding("€ 25 per maand", "mogelijk_onjuist", "J1",
                                   [{"bepaling": TOESLAG, "van": "De standaardbetalingsregeling", "tot": "afzonderlijk."}])), tr)
    assert not _na_te_lopen(a)


def test_een_onderdeel_van_de_opsomming_wordt_nagelopen():
    # Meting C5, 25.3a.1: de uitzondering stond in onderdeel 3 van de opsomming.
    o3 = f"{STANDAARD}%2FTekst%2FOnderdeel._3"
    tr = [*trace(), ("get_bepaling", json.dumps({
        "status": "ok", "volledig": True, "aantal": 1, "bepaling": {"iri": STANDAARD, "tekst": TEKST_STANDAARD},
        "resultaten": [{"onderdeel": o3, "nummer": "–", "tekst": "aanslagen waartegen bezwaar in behandeling is."}]},
        ensure_ascii=False))]
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF])), tr)
    assert any("“aanslagen waartegen bezwaar in behandeling is.”" in m for m in _na_te_lopen(a))


ONDERNEMERS = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.6%2FCirculaire.divisie25.6.2d"


def test_juist_op_een_bepaling_voor_een_andere_doelgroep_krijgt_een_kanttekening():
    # Meting C5: "dan krijgt u kort uitstel" (een tekst voor particulieren) werd gestaafd met de ondernemersbepaling
    # 25.6.2d, terwijl de bepaling voor particulieren "kan … worden getroffen" zegt.
    content = "Bent u particulier? Dan krijgt u 4 maanden kort uitstel."
    rij = {"iri": ONDERNEMERS, "label": "Kort uitstel ondernemers",
           "tekst": "Ondernemers kunnen een kort uitstel van betaling krijgen van ten hoogste vier maanden."}
    tr = [(CONTENT_TOOL, content_resultaat(content)),
          ("get_bepaling", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [], "bepaling": rij},
                                      ensure_ascii=False))]
    bron = {"bepaling": ONDERNEMERS, "van": "Ondernemers kunnen", "tot": "vier maanden."}
    b = rapport(vul(NAAM, invoer(bevinding("Dan krijgt u 4 maanden kort uitstel.", "juist", "J1", [bron])), tr)).bevindingen[0]
    assert b.oordeel == "juist"
    assert "ruimte (“kunnen”)" in b.twijfel and "ondernemers" in b.twijfel and "J4" in b.twijfel


def test_juist_met_dezelfde_ruimte_en_doelgroep_krijgt_geen_kanttekening():
    content = "Dan kunt u kort uitstel krijgen."
    rij = {"iri": ONDERNEMERS, "label": "Kort uitstel", "tekst": "Er kan kort uitstel van betaling worden verleend."}
    tr = [(CONTENT_TOOL, content_resultaat(content)),
          ("get_bepaling", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [], "bepaling": rij},
                                      ensure_ascii=False))]
    bron = {"bepaling": ONDERNEMERS, "van": "Er kan", "tot": "verleend."}
    b = rapport(vul(NAAM, invoer(bevinding("Dan kunt u kort uitstel krijgen.", "juist", "J4", [bron])), tr)).bevindingen[0]
    assert b.twijfel == ""


# Meting C5b (kort uitstel): de vorm van 25.5.3 en 25.6.2d, met hun onderdelen zoals `get_bepaling` ze geeft.
_ONDERDELEN_KORT = {
    "a": "De totale openstaande schuld van de belastingschuldige bedraagt minder dan € 20.000.",
    "b": "Vervallen.",
    "c": "Aan de belastingschuldige is niet voor dezelfde belastingaanslag of voor andere belastingaanslagen uitstel van "
         "betaling in verband met betalingsproblemen verleend.",
    "d": "Het verzoek betreft niet een voorlopige aanslag als bedoeld in artikel 9, vijfde lid, van de wet die in meerdere "
         "termijnen betaald mag worden.",
    "e": "De belastingschuldige heeft geen belastingschuld openstaan waarvoor een dwangbevel is betekend.",
}
_ONDERDELEN_ONDERNEMERS = {
    "b": "Er staan ten name van de belastingschuldige geen belastingaanslagen open waarvoor dwangbevelen zijn betekend.",
    "c": "Aan de belastingschuldige is niet voor dezelfde belastingaanslag of voor andere aanslagen uitstel van betaling "
         "in verband met betalingsproblemen of uitstel in verband met een te verwachten uit te betalen bedrag verleend.",
    "d": _ONDERDELEN_KORT["d"],
}
CONTENT_KORT = ("Bel ons, dan krijgt u kort uitstel. Dit kan als uw totale schuld lager is dan € 25.000. Heeft u al een "
                "dwangbevel gekregen? Dan kunt u geen kort uitstel krijgen.")


def _kort_uitstel() -> list[tuple[str, str]]:
    def lezing(iri, label, tekst, onderdelen):
        return "get_bepaling", json.dumps({
            "status": "ok", "volledig": True, "aantal": len(onderdelen),
            "bepaling": {"iri": iri, "label": label, "tekst": tekst},
            "resultaten": [{"onderdeel": f"{iri}%2FTekst%2FOnderdeel{n}", "nummer": n, "tekst": t}
                           for n, t in onderdelen.items()]}, ensure_ascii=False)
    return [(CONTENT_TOOL, content_resultaat(CONTENT_KORT)),
            lezing(KORT, "Kort uitstel particulieren", TEKST_KORT, _ONDERDELEN_KORT),
            lezing(ONDERNEMERS, "Kort uitstel van betaling voor ondernemers",
                   "Ondernemers kunnen zonder nader onderzoek kort uitstel van betaling krijgen.", _ONDERDELEN_ONDERNEMERS)]


def _kort_rapport(**rest):
    grens = {"bepaling": f"{KORT}%2FTekst%2FOnderdeela", "van": "", "tot": ""}
    eerder = {"bepaling": f"{KORT}%2FTekst%2FOnderdeelc", "van": "", "tot": ""}
    return vul(NAAM, invoer(bevinding("Dit kan als uw totale schuld lager is dan € 25.000.", "mogelijk_onjuist", "J1",
                                      [grens]),
                            bevinding("Heeft u al een dwangbevel gekregen?", "onvolledig", "V1", [eerder]), **rest),
               _kort_uitstel())


def test_de_controle_noemt_geen_vervallen_onderdeel_en_geen_onderwerp_van_een_bewering():
    punten = " ".join(_na_te_lopen(_kort_rapport()))
    assert "Vervallen." not in punten
    # 25.5.3 onder e en 25.6.2d onder b gaan over het dwangbevel, en daar gaat een bewering over.
    assert "dwangbevel" not in punten
    # 25.6.2d onder c is 25.5.3 onder c, die het rapport al citeert, met een staart erbij.
    assert "te verwachten uit te betalen bedrag" not in punten
    # Wat overblijft is wezenlijk: de voorlopige aanslag in termijnen, één keer, ook al staat ze in beide bepalingen.
    assert punten.count("voorlopige aanslag") == 1


def test_wat_de_controle_vindt_staat_onder_ontbreekt_en_niet_in_een_melding():
    # Meting C5b (reguliere regeling): de kwijtschelding stond alleen in de melding Na te lopen, niet in het rapport en
    # niet in de export.
    a = _kort_rapport()
    [o] = [o for o in rapport(a).ontbreekt if o.tekst.startswith("Uit de controle")]
    assert "Kort uitstel particulieren" in o.tekst
    assert o.bronnen[0].tekst == _ONDERDELEN_KORT["d"]
    assert o.bronnen[0].vindplaats.iri == f"{KORT}%2FTekst%2FOnderdeeld"
    assert not [b for b in a.blokken if b.soort == "leemte" and "Na te lopen" in b.tekst]
    assert "Uit de controle" in antwoord_tekst(a)


def test_voor_de_redacteur_staat_op_nummervolgorde():
    # Meting C5b (kort uitstel): [3], [2], [4].
    a = vul(NAAM, invoer(bevinding("maximaal 24 maanden", "mogelijk_onjuist", "J1", [TWAALF]),
                         bevinding("minimaal € 20 per maand", "juist", "J1", [TWINTIG]),
                         bevinding("4 maanden kort uitstel", "niet_in_de_bron"),
                         voor_redacteur=["[3] Waar komt dit vandaan?", "Lees alles na.", "[1] Maak er 12 maanden van."]),
            trace())
    assert rapport(a).voor_redacteur == ["[1] Maak er 12 maanden van.", "[3] Waar komt dit vandaan?", "Lees alles na."]
