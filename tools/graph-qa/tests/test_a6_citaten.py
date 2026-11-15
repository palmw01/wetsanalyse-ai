"""De citaten bij uitspraken na de korte meting na A6 (15 nov 2026, bundel 129): onder een samenvatting stonden het
procesverloop en de feiten (S01: "De Hoge Raad heeft partijen in kennis gesteld …", r.o. 2.1 en 2.2; F02: "Het middel
kan niet tot cassatie leiden …"), niet de passages die de samenvatting dragen. Bij een rapport koos de code hoogstens twee
alinea's op de som van alle woorden, en een samenvatting in zeven punten (HR:2023:1371) droegen die niet: de toets meldde
"die de passages van dat stuk niet dragen". En F02 noemde twee van de zes gelezen uitspraken.

Nepbronnen in de echte vorm (`get_uitspraak` door de echte toollaag), zoals `test_d01_bundel122.py`."""
from __future__ import annotations

from agent import tools
from agent.gelezen import niet_genoemd, zonder_steun
from agent.sjablonen import extern
from agent import sjablonen
from agent import subagent as sub
from test_rechtspraak_tools import AAN, V_NU, Link, NepBron

HR = "ECLI:NL:HR:2023:1371"
PROCES = ["De Hoge Raad heeft partijen in kennis gesteld van zijn voornemen het Hof van Justitie van de Europese Unie "
          "prejudiciële vragen te stellen.",
          "Belanghebbende was bestuurder en enig aandeelhouder van een holdingvennootschap die bestuurder was van de "
          "vennootschap.",
          "Aan de vennootschap zijn naheffingsaanslagen in de loonheffingen opgelegd over de tijdvakken van 2013."]
DRAGEND = ["Het doel van de meldingsplicht is dat de ontvanger in een vroeg stadium op de hoogte komt van "
           "betalingsmoeilijkheden, zodat hij zijn invorderingsbeleid kan bepalen.",
           "De melding moet plaatsvinden binnen twee weken nadat de belasting uiterlijk betaald had moeten zijn.",
           "Bij een correcte melding draagt de ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur in de drie "
           "jaren voorafgaand aan de melding.",
           "Bij een niet correcte melding geldt het wettelijk vermoeden dat de niet-betaling aan onbehoorlijk bestuur is "
           "te wijten.",
           "Daarentegen wordt de gewezen bestuurder steeds toegelaten tot het leveren van tegenbewijs tegen het vermoeden.",
           "De wet geeft de rechter noch de ontvanger de bevoegdheid om de aansprakelijkheid te matigen."]


def _xml(paras: list[str]) -> bytes:
    inhoud = "".join(f"<para>{a}</para>" for a in paras)
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{HR}</dcterms:identifier><dcterms:creator>Hoge Raad</dcterms:creator>
  <dcterms:date>2023-10-06</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Artikel 36 IW 1990; melding betalingsonmacht.</para></inhoudsindicatie>
<uitspraak><section><title>Beoordeling</title>{inhoud}</section></uitspraak></open-rechtspraak>""".encode()


BRON = NepBron([Link(HR, f"{HR} - Hoge Raad, 06-10-2023 / 21/03566", "Door computer herkende referentie", V_NU)],
               docs={HR: _xml([*PROCES, *DRAGEND])})
TRACE = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": HR}, AAN, rechtspraak=BRON))]
_nr = {r["tekst"]: r["nr"] for r in __import__("json").loads(TRACE[0][1])["resultaten"]}
NR_PROCES = [_nr[t] for t in PROCES]
NR_DRAGEND = [_nr[t] for t in DRAGEND]

SAMENVATTING = (
    f"**HR 6 oktober 2023 ({HR}) – meldingsplicht betalingsonmacht**\n"
    "- Het doel van de meldingsplicht is dat de ontvanger vroeg op de hoogte komt van betalingsmoeilijkheden, zodat hij "
    "het invorderingsbeleid kan bepalen.\n"
    "- De melding moet plaatsvinden binnen twee weken nadat de belasting uiterlijk betaald had moeten zijn.\n"
    "- Bij een correcte melding draagt de ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur in de drie jaren.\n"
    "- Bij een niet correcte melding geldt een wettelijk vermoeden van onbehoorlijk bestuur.\n"
    "- De gewezen bestuurder wordt steeds toegelaten tot tegenbewijs tegen het vermoeden.\n"
    "- De wet geeft de rechter noch de ontvanger de bevoegdheid de aansprakelijkheid te matigen.")


def test_een_antwoord_dat_het_procesverloop_aanwijst_krijgt_de_dragende_passages():
    """S01: de centrale agent wees r.o. 1 tot 2.2 aan, het procesverloop en de feiten."""
    items = [{"id": HR, "van_nr": NR_PROCES[0], "tot_nr": NR_PROCES[-1]}]
    nieuw = extern.herkies(SAMENVATTING, items, TRACE)
    nrs = {i["van_nr"] for i in nieuw}
    # Geen procesverloop meer, alleen dragende alinea's; een punt dat de gekozen alinea's samen al dragen, krijgt er geen
    # eigen (zoals `zonder_steun` toetst: op alle passages van het stuk samen).
    assert nrs <= set(NR_DRAGEND) and len(nrs) >= 4, nrs
    # Door het hele sjabloon: de passages die getoond worden, dragen de samenvatting.
    antwoord = sjablonen.vul("antwoord_extern", {"kort_antwoord": SAMENVATTING, "extern": items}, TRACE)
    [blok] = [b for b in antwoord.blokken if b.soort == "extern"]
    getoond = {p.tekst for p in blok.passages}
    assert getoond <= set(DRAGEND) and not getoond & set(PROCES)
    assert not zonder_steun(SAMENVATTING, {HR: " ".join(getoond)}, TRACE), "de getoonde passages dragen de samenvatting"


def test_wat_het_aangewezene_al_draagt_blijft_staan():
    items = [{"id": HR, "van_nr": NR_DRAGEND[0], "tot_nr": NR_DRAGEND[-1]}]
    assert extern.herkies(SAMENVATTING, items, TRACE) == items


def test_een_rapport_in_zeven_punten_krijgt_een_passage_per_punt_en_de_toets_meldt_niets():
    """HR:2023:1371 bij het kind van S01: twee alinea's op de som droegen de punten niet."""
    bij, regels = extern.aanvulling(SAMENVATTING, [{"id": HR, "van_nr": NR_PROCES[0], "tot_nr": NR_PROCES[-1]}], TRACE)
    assert {i["van_nr"] for i in bij} <= set(NR_DRAGEND) and len(bij) > 2 and regels
    rapport = sjablonen.vul("rapport", {"status": "klaar", "gedaan": "Gelezen.", "bevindingen": SAMENVATTING,
                                        "open": [], "vragen": [],
                                        "extern": [{"id": HR, "van_nr": NR_PROCES[0], "tot_nr": NR_PROCES[-1]}]}, TRACE)
    steun = sub.steun_van([{"antwoord": rapport.model_dump()}])
    assert not zonder_steun(SAMENVATTING, steun, TRACE)


def test_f02_een_gelezen_uitspraak_die_het_antwoord_niet_noemt():
    steun = {HR: "passage", "ECLI:NL:HR:2015:1826": "passage"}
    assert niet_genoemd(f"Over {HR}: de melding.", {HR: "passage"}, TRACE) == []
    assert niet_genoemd("Over HR:2023:1371: de melding.", {HR: "passage"}, TRACE) == [], "het korte id telt"
    [weg] = niet_genoemd(f"Over {HR}: de melding.", steun, TRACE)
    assert weg.startswith("ECLI:NL:HR:2015:1826 staat in het rapport met passages")
