"""D01 uit de meting van bundel 119 (14 nov 2026): twee samenvattingen die `verify` *gegrond* noemde, met nepbronnen in
de echte vorm (`get_uitspraak` door de echte toollaag). De tekst van de uitspraken is ingekort tot wat de test nodig heeft;
de samenvattingen staan er letterlijk zoals Lex ze schreef.

1. Bij HR:2023:563 staat "tijdig betalingsonmacht gemeld"; in de uitspraak staat het woord niet.
2. Bij HR:2023:181 en :184 is de bewijslast van lid 3 omgedraaid; het rapport citeerde geen passage van die uitspraken.

Beide stonden onder een kop met het id, en de controle keek alleen naar de kop."""
from __future__ import annotations

import json

import pytest

from agent import subagent as sub
from agent.gelezen import per_stuk, vraag_niet_in_stuk, zelf_afgebakend
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from agent import tools
from test_rechtspraak_tools import AAN, V_NU, Link, NepBron

VRAAG = ("Zoek de rechtspraak over de melding van betalingsonmacht bij artikel 36 van de Invorderingswet 1990 uit de "
         "periode van mijn dossier, en vat per uitspraak samen wat de rechter over de melding zegt.")
HR563, HR181, HR184, HR1371 = ("ECLI:NL:HR:2023:563", "ECLI:NL:HR:2023:181", "ECLI:NL:HR:2023:184",
                               "ECLI:NL:HR:2023:1371")
TEKST = {
    HR563: ("2023-04-14", "Aansprakelijkstelling bestuurder na schikking met de curator; artikel 36.1 Leidraad Invordering "
            "2008.",
            ["Na het faillissement van de vennootschappen heeft de curator met belanghebbende een schikking getroffen "
             "wegens onbehoorlijk bestuur.",
             "Daarna heeft de ontvanger belanghebbende aansprakelijk gesteld op grond van artikel 36 van de Wet.",
             "Het Hof heeft de aansprakelijkstelling vernietigd met een beroep op artikel 36.1 van de Leidraad Invordering "
             "2008."]),
    HR181: ("2023-02-10", "Bestuurdersaansprakelijkheid; kennelijk onbehoorlijk bestuur; selectieve betalingen.",
            ["Voor twee tijdvakken heeft de BV tijdig en rechtsgeldig mededeling gedaan van haar onvermogen tot betaling.",
             "Voor die tijdvakken moet de ontvanger aannemelijk maken dat de niet-betaling het gevolg is van kennelijk "
             "onbehoorlijk bestuur (artikel 36, lid 3, van de Wet).",
             "Het Hof heeft kennelijk onbehoorlijk bestuur aangenomen op grond van betalingen aan gelieerde schuldeisers en "
             "de overdracht van activiteiten zonder vergoeding voor goodwill.",
             "De Hoge Raad verwijst het geding: het Hof had moeten onderzoeken of de begunstigde schuldeisers aan de BV "
             "gelieerd waren, en zo niet, of belanghebbende een persoonlijk belang had bij de selectieve betalingen."]),
    HR184: ("2023-02-10", "Bestuurdersaansprakelijkheid; kennelijk onbehoorlijk bestuur.",
            ["Dezelfde zaak als ECLI:NL:HR:2023:181 voor een ander tijdvak."]),
    HR1371: ("2023-10-06", "Artikel 36 IW 1990; bestuurdersaansprakelijkheid; bewijspositie bestuurder.",
             ["Het lichaam moet betalingsonmacht melden binnen twee weken na het verstrijken van de betalingstermijn.",
              "Wie niet meldt, wordt vermoed aansprakelijk te zijn, tenzij het niet-melden niet aan hem te wijten is."]),
}


def _xml(ecli: str) -> bytes:
    datum, indicatie, alineas = TEKST[ecli]
    paras = "".join(f"<para>{a}</para>" for a in alineas)
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description><dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>Hoge Raad</dcterms:creator>
  <dcterms:date>{datum}</dcterms:date><dcterms:type>Uitspraak</dcterms:type></rdf:Description></rdf:RDF>
<inhoudsindicatie><para>{indicatie}</para></inhoudsindicatie>
<uitspraak><section><title>Beoordeling</title>{paras}</section></uitspraak></open-rechtspraak>""".encode()


BRON = NepBron([Link(e, f"{e} - Hoge Raad, {TEKST[e][0]} / 22/0{i}", "Door computer herkende referentie", V_NU)
                for i, e in enumerate(TEKST)], docs={e: _xml(e) for e in TEKST})
TRACE = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": e}, AAN, rechtspraak=BRON)) for e in TEKST]


def _passages(ecli: str, *woorden: str) -> str:
    rijen = next(json.loads(t) for _, t in TRACE if json.loads(t)["stuk"]["id"] == ecli)["resultaten"]
    return " ".join(r["tekst"] for r in rijen if any(w in r["tekst"] for w in woorden))


#: Wat het rapport van het kind citeerde (`State.rapport_steun`): passages van HR:2023:563 en :1371, niet van :181/:184.
STEUN = {HR563: _passages(HR563, "schikking", "Leidraad"), HR1371: _passages(HR1371, "betalingsonmacht")}

#: Uit het eindantwoord van bundel 119, letterlijk (de alinea's 2 en 4 van de toelichting).
ANTWOORD_563 = (
    "**2. HR 14 april 2023 (ECLI:NL:HR:2023:563) – aansprakelijkstelling na schikking met curator**\n"
    "In deze zaak had de bestuurder tijdig betalingsonmacht gemeld. Na faillissement sloot de curator een schikking met "
    "de bestuurder wegens onbehoorlijk bestuur. Daarna stelde de ontvanger de bestuurder tóch aansprakelijk op grond van "
    "artikel 36. Het hof vernietigde die aansprakelijkstelling op grond van artikel 36.1 van de Leidraad Invordering 2008. "
    "De uitspraak raakt de melding zijdelings: de tijdige melding stond vast en was niet in geschil.")
ANTWOORD_181 = (
    "**4. HR 10 februari 2023 (ECLI:NL:HR:2023:181 en ECLI:NL:HR:2023:184) – kennelijk onbehoorlijk bestuur bij "
    "selectieve betalingen**\n"
    "Voor twee tijdvakken was wél tijdig en rechtsgeldig gemeld; voor de overige tijdvakken was de bewijslast verlegd naar "
    "de ontvanger (artikel 36 lid 3). Het hof nam kennelijk onbehoorlijk bestuur aan op grond van selectieve betalingen en "
    "overdracht van activiteiten zonder vergoeding. De Hoge Raad verwijst terug: het hof had moeten onderzoeken of de "
    "begunstigde schuldeisers aan de BV gelieerd waren, en zo niet, of de bestuurder een persoonlijk belang had bij de "
    "betalingen.")


def test_een_regel_onder_een_kop_gaat_over_het_stuk_uit_de_kop():
    regels = per_stuk(ANTWOORD_181 + "\n\nNiet gelezen: zes conclusies uit 2022.")
    body = [ids for zin, ids in regels if zin.startswith(("Voor twee tijdvakken", "Het hof nam", "De Hoge Raad"))]
    assert body == [[HR181, HR184]] * 3
    assert regels[-1][1] == [], "een nieuwe alinea zonder id gaat over geen stuk"


def test_het_onderwerp_van_de_vraag_toeschrijven_aan_een_stuk_dat_het_niet_noemt():
    fout = check_grounding(ANTWOORD_563, TRACE, steun=STEUN, bekend=VRAAG)
    assert f"duiding van {HR563} met 'betalingsonmacht' uit de vraag, dat niet in dat stuk staat" in fout.beweringen
    assert fout.niveau != "gegrond"
    # Wat het eerste rapport zei, klopte, en mag: een zin met een ontkenning zegt wat er ontbreekt.
    goed = (f"**2. HR 14 april 2023 ({HR563})**\nDe zaak gaat niet primair over de melding van betalingsonmacht. Na het "
            "faillissement trof de curator een schikking met de bestuurder wegens onbehoorlijk bestuur, en het Hof "
            "vernietigde de aansprakelijkstelling met een beroep op artikel 36.1 van de Leidraad Invordering 2008.")
    assert not vraag_niet_in_stuk(goed, TRACE, VRAAG)
    # Een stuk dat het woord wel bevat, mag het: HR:2023:1371 gaat over de melding van betalingsonmacht.
    assert not vraag_niet_in_stuk(f"In {HR1371} moet het lichaam betalingsonmacht melden binnen twee weken.", TRACE, VRAAG)


def test_een_duiding_onder_een_kop_zonder_passage_van_dat_stuk_is_een_bewering():
    fout = check_grounding(ANTWOORD_181, TRACE, steun=STEUN, bekend=VRAAG)
    assert f"duiding van {HR181} zonder passage van dat stuk in het rapport" in fout.beweringen
    assert f"duiding van {HR184} zonder passage van dat stuk in het rapport" in fout.beweringen
    assert fout.niveau != "gegrond"


@pytest.mark.xfail(strict=True, reason="Een omgedraaide bewijslast met de woorden van de passage ziet een toets op "
                                       "woorden niet; daarvoor is een controle per stuk nodig (plan, stap 2).")
def test_met_alle_passages_geciteerd_ziet_de_toets_de_omgedraaide_bewijslast_niet():
    steun = {**STEUN, HR181: _passages(HR181, "Voor", "Het Hof", "De Hoge Raad")}
    # De juiste weergave gaat erdoor, zoals het hoort.
    goed = ANTWOORD_181.replace(
        "Voor twee tijdvakken was wél tijdig en rechtsgeldig gemeld; voor de overige tijdvakken was de bewijslast verlegd "
        "naar de ontvanger (artikel 36 lid 3).",
        "Voor twee tijdvakken deed de BV tijdig en rechtsgeldig mededeling; voor die tijdvakken moet de ontvanger "
        "kennelijk onbehoorlijk bestuur aannemelijk maken (artikel 36, lid 3).")
    assert not check_grounding(goed, TRACE, steun=steun, bekend=VRAAG).beweringen
    # De omgedraaide gebruikt bijna dezelfde woorden, dus ook die gaat erdoor: dit is de grens van een toets op woorden.
    fout = check_grounding(ANTWOORD_181, TRACE, steun=steun, bekend=VRAAG)
    assert any(b.startswith(f"duiding van {HR181}") for b in fout.beweringen)


def test_ook_het_rapport_van_het_kind_rust_op_zijn_eigen_passages():
    """Het tweede rapport duidde zes nieuwe uitspraken zonder er één te citeren (en `stukken` bleef dat van het eerste)."""
    state = {"opdracht": {"doel": VRAAG}, "antwoord": {"blokken": [
        {"soort": "extern", "id": HR1371, "passages": [{"tekst": STEUN[HR1371]}]}]}}
    steun = antwoordnodes.rapport_steun(state)
    assert set(steun) == {HR1371}
    fout = check_grounding(ANTWOORD_181, TRACE, steun=steun, vraag=antwoordnodes._vraag(state))
    assert f"duiding van {HR181} zonder passage van dat stuk in het rapport" in fout.beweringen
    # De opdracht is de vraag van het kind, ook in een hervatte beurt; ze is geen tekst van de jurist (`_bekend`).
    assert "betalingsonmacht" in antwoordnodes._vraag(state) and "betalingsonmacht" not in antwoordnodes._bekend(state)


def test_een_afbakening_die_de_jurist_niet_koos_zegt_de_code():
    zoek = ("zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [],
                                           "zoekvraag": {"bwb_id": "BWBR0004770", "artikel": "36", "instantie": "Hoge Raad",
                                                         "vanaf": "2022-01-01", "tot": "2024-12-31",
                                                         "volgorde": "nieuwste"}}))
    gevraagd = f"{VRAAG}\nAntwoord: Uitspraken uit 2022 tot en met 2024.\nAntwoord: Alle instanties; verder geen beperking."
    assert zelf_afgebakend([zoek], gevraagd) == ["instantie: Hoge Raad"]
    assert zelf_afgebakend([zoek], gevraagd + " Alleen de Hoge Raad.") == []
    # De centrale agent hoort het, in het rapport, en de meting ziet het in het eind-event.
    kind = {"rapport": {"status": "klaar"}, "answer": "Bevindingen.", "source_trace": [zoek, *TRACE],
            "afbakening": ["instantie: Hoge Raad"]}
    tekst = sub.rapport_tekst(sub.Afloop(profiel="algemeen", uitkomst="klaar"), kind)
    assert "Zelf afgebakend door de subagent, niet gevraagd door de gebruiker" in tekst and "instantie: Hoge Raad" in tekst
    inhoud = sub.rapport_inhoud(kind)
    assert inhoud["afbakening"] == ["instantie: Hoge Raad"] and inhoud["gelezen"] == list(TEKST)
