"""De fixes na A6 run 3 deel 1 (15 nov 2026, `docs/architectuur/metingen/centrale-agent-2026-11-15-a6-run3/`), met de
gevallen uit die meting als test.

1. S04: het kind gaf een rapport met status `niet_gelukt` (een paar onderdelen niet gelezen), met bevindingen. De code
   telde dat als "geen rapport" en sloot de beurt af met 26 kale vindplaatsen. `niet_gelukt` was twee dingen: de status
   van een rapport en de terugval zonder rapport (`Afloop.rapport` scheidt ze).
2. De controle per stuk: drie van de vier inhoudelijke meldingen vals. Een verwijzing als "tegen"-stukje telt niet
   (HR:2023:1371), en een tweede lezing met de tekst rond de passage bevestigt alleen hetzelfde onderwerp met het
   omgekeerde (HR:2026:586: het verkeerde beroep; kst-26728-3: een passage die Lex bevestigt). kst-36151-3 blijft.
3. Citaten zonder inhoud: de aanhef van een besluit (S05), procedurezinnen (P02) en trefwoorden (P01) vallen binnen een
   reeks weg als er iets met inhoud overblijft.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from agent import stukcontrole
from agent import subagent as sub
from agent.nodes import antwoord as antwoordnodes
from agent.sjablonen import extern
from fakes import FakeLLM, make_settings, response, tool_block
from test_subagent import ARTIKEL, OPDRACHT, STATE, Api, _kinderen

# 1. S04: een rapport `niet_gelukt` is een rapport ----------------------------------------------------------------------

S04_RAPPORT = {"rapport": {"status": "niet_gelukt", "open": ["22.8.10 kon niet worden opgehaald."]},
               "answer": "Gedaan: 22.1 t/m 22.9 gelezen.\n\nBevindingen: de Leidraad werkt het bodemrecht uit.",
               "source_trace": [ARTIKEL]}


def _afloop(kind: dict, uitkomst: str = "klaar") -> sub.Afloop:
    kinderen, _, _ = _kinderen(kind, uitkomst)
    afloop, _, _ = asyncio.run(sub.voer_uit(STATE, "duiding", OPDRACHT, lambda _e: None, settings=None,
                                            kinderen=kinderen, gestopt=lambda: False, api=Api()))
    return afloop


def test_een_rapport_niet_gelukt_is_een_rapport_en_de_code_sluit_niet_af():
    afloop = _afloop(S04_RAPPORT)
    assert afloop.uitkomst == "niet_gelukt" and afloop.met_rapport() and afloop.als_dict()["rapport"] is True
    assert sub.zonder_rapport([afloop.als_dict()]) == "", "de centrale agent vat het rapport samen"
    state = {"subagenten": [afloop.als_dict()], "specialist": "centraal"}
    assert antwoordnodes.na_subagent(state, "get_artikel") == antwoordnodes.NA_RAPPORT
    assert sub.rapport_tekst(afloop, S04_RAPPORT).startswith(S04_RAPPORT["answer"]), "het rapport, geen reden uit code"


def test_zonder_rapport_blijft_de_afsluiting_uit_code():
    afloop = _afloop({"answer": "Vrije tekst.", "source_trace": [ARTIKEL]})
    assert afloop.uitkomst == "niet_gelukt" and not afloop.met_rapport() and "rapport" not in afloop.als_dict()
    assert sub.zonder_rapport([afloop.als_dict()]).startswith(sub.ZONDER_RAPPORT["niet_gelukt"])
    state = {"subagenten": [afloop.als_dict()], "specialist": "centraal"}
    assert antwoordnodes.na_subagent(state, "get_artikel") == antwoordnodes.NA_SUBAGENT
    # Een kind dat de code afsloot, had geen rapport, ook als het er eerder een schreef.
    assert not _afloop({**S04_RAPPORT, "afgesloten": True}).met_rapport()


def test_na_een_rapport_niet_gelukt_komen_de_rapportcitaten_onder_een_tekstantwoord():
    from bronmodel.antwoord import Citaat, Vindplaats

    citaat = Citaat(tekst="Het bodemrecht geldt voor bodemzaken.", vindplaats=Vindplaats(iri="urn:x", label="22.1"))
    state = {"subagenten": [{"uitkomst": "niet_gelukt", "rapport": True}], "rapport_citaten": [citaat.model_dump()]}
    assert antwoordnodes.met_rapportcitaten(state, "Per onderdeel: …") is not None
    assert antwoordnodes.met_rapportcitaten({**state, "subagenten": [{"uitkomst": "niet_gelukt"}]}, "x") is None


# 2. De controle per stuk -----------------------------------------------------------------------------------------------

HR1371 = "ECLI:NL:HR:2023:1371"
HR1371_PASSAGES = ("Daarentegen wordt de gewezen bestuurder op grond van artikel 36, lid 4, tweede volzin, IW 1990 steeds "
                   "toegelaten tot het leveren van tegenbewijs tegen het vermoeden.")
HR1371_ANTWOORD = (f"**{HR1371}**\nVolgens de Hoge Raad wordt de gewezen bestuurder altijd toegelaten tot weerlegging "
                   "van het wettelijk vermoeden, op grond van de leden 5 en 6 van artikel 36.")

HR586 = "ECLI:NL:HR:2026:586"
HR586_PASSAGES = ("Het principale beroep. De klachten over de navordering falen. De uitkomst hiervan is dat deze klachten "
                  "niet kunnen leiden tot vernietiging. Het incidentele beroep. De klacht over de vergrijpboete slaagt. "
                  "De Hoge Raad vernietigt de uitspraak van het Hof voor zover die de vergrijpboete 2013 betreft.")
HR586_ANTWOORD = (f"**{HR586}**\nDe Hoge Raad vernietigde het oordeel van het Hof over de vergrijpboete voor 2013, omdat "
                  "de klacht in het incidentele beroep slaagde.")


def _llm(oordeel: dict, *bevestiging: dict) -> FakeLLM:
    antwoorden = [response([tool_block("o", "oordelen", {"oordelen": [{"stuk": 1, "zin": 1, **oordeel}]})], "tool_use")]
    if bevestiging:
        antwoorden.append(response([tool_block("b", "bevestiging", {"gevallen": list(bevestiging)})], "tool_use"))
    return FakeLLM(antwoorden)


def test_een_wetsverwijzing_is_geen_tegenspraak_en_vraagt_geen_tweede_lezing():
    """HR:2023:1371 (S01): het "tegen"-stukje was "artikel 36, lid 4, tweede volzin, IW 1990"."""
    llm = _llm({"oordeel": "spreekt_tegen", "deel": "op grond van de leden 5 en 6 van artikel 36",
                "tegen": "artikel 36, lid 4, tweede volzin, IW 1990"})
    assert stukcontrole.controleer(llm, make_settings(), HR1371_ANTWOORD, {HR1371: HR1371_PASSAGES}, []) == []
    assert len(llm.calls) == 1
    assert not stukcontrole.heeft_inhoud("artikel 36, lid 4, tweede volzin, IW 1990")
    assert stukcontrole.heeft_inhoud("de gewezen bestuurder steeds toegelaten")


def test_de_tweede_lezing_ziet_het_onderdeel_rond_de_passage_en_bevestigt_bij_twijfel_niet():
    """HR:2026:586 (M06): de controle wees het principale beroep aan; het incidentele beroep is gegrond."""
    oordeel = {"oordeel": "spreekt_tegen", "deel": "De Hoge Raad vernietigde het oordeel van het Hof",
               "tegen": "De uitkomst hiervan is dat deze klachten niet kunnen leiden tot vernietiging."}
    llm = _llm(oordeel, {"geval": 1, "zelfde_onderwerp": False, "omgekeerd": True})
    assert stukcontrole.controleer(llm, make_settings(), HR586_ANTWOORD, {HR586: HR586_PASSAGES}, []) == []
    tweede = llm.calls[1]
    assert tweede["tool_choice"] == {"type": "tool", "name": "bevestiging"}
    inhoud = tweede["messages"][0]["content"]
    assert "Het principale beroep." in inhoud and "Het incidentele beroep." in inhoud, "de tekst rond de passage gaat mee"
    assert "Bij twijfel is het antwoord false" in stukcontrole.BEVESTIG_SYSTEEM
    # Een onbruikbare of mislukte tweede lezing bevestigt niets.
    assert stukcontrole.controleer(_llm(oordeel), make_settings(), HR586_ANTWOORD, {HR586: HR586_PASSAGES}, []) == []


KST36151 = "kst-36151-3"
KST36151_PASSAGES = ("De bestaande kwijtscheldingsbepalingen in de Awb en de socialezekerheidswetgeving zijn niet "
                     "toereikend om de schulden van burgers in een kwetsbare positie te saneren.")
KST36151_ANTWOORD = (f"**Memorie van toelichting ({KST36151})**\nDe regering vindt de bestaande kwijtscheldingsbepalingen "
                     "in de Invorderingswet en de Awb ontoereikend voor schulden van burgers.")


def test_een_bevestigde_tegenspraak_blijft_een_bewering():
    """kst-36151-3 (P02) was terecht: Lex zette de Invorderingswet in de zin, het stuk noemt de sociale zekerheid."""
    llm = _llm({"oordeel": "spreekt_tegen", "deel": "in de Invorderingswet en de Awb",
                "tegen": "in de Awb en de socialezekerheidswetgeving"},
               {"geval": 1, "zelfde_onderwerp": True, "omgekeerd": True})
    [bewering] = stukcontrole.controleer(llm, make_settings(), KST36151_ANTWOORD, {KST36151: KST36151_PASSAGES}, [])
    assert bewering.startswith(f"duiding van {KST36151} die de passages van dat stuk tegenspreekt")


def test_de_omgeving_staat_op_woordgrenzen_rond_de_passage():
    tekst = "a " * 1000 + "HET STUKJE" + " b" * 1000
    rond = stukcontrole.omgeving("het stukje", tekst)
    assert "HET STUKJE" in rond and rond.startswith("…") and rond.endswith("…")
    assert len(rond) <= 2 * stukcontrole.OMGEVING + len("HET STUKJE") + 4


# 3. Citaten zonder inhoud ----------------------------------------------------------------------------------------------

STB = "stb-2010-176"
STB_RIJEN = [
    {"nr": 1, "tekst": "Wij Beatrix, bij de gratie Gods, Koningin der Nederlanden, Prinses van Oranje-Nassau, enz. enz. enz."},
    {"nr": 2, "tekst": "Op de voordracht van Onze Minister van Financiën van 22 april 2010, nr. DB/2010/83U;"},
    {"nr": 3, "tekst": "Hebben goedgevonden en verstaan:"},
    {"nr": 4, "kop": "Enig artikel", "tekst": "Artikel XVII, onderdeel C, van Overige fiscale maatregelen 2010 treedt in "
                                              "werking met ingang van 4 juli 2010."},
    {"nr": 5, "tekst": "Onze Minister van Financiën is belast met de uitvoering van dit besluit dat in het Staatsblad zal "
                       "worden geplaatst."},
]


def _trace(ident: str, rijen: list[dict]) -> list[tuple[str, str]]:
    return [("get_bekendmaking", json.dumps({"status": "ok", "volledig": True, "stuk": {"id": ident, "label": "Stb. 2010, 176"},
                                             "resultaten": rijen}))]


def test_de_aanhef_van_een_besluit_valt_weg_als_er_inhoud_overblijft():
    """S05: "Wij Beatrix …" en "Hebben goedgevonden en verstaan:" stonden als citaat bij de inwerkingtreding."""
    [blok] = [b for b in extern.blokken([{"id": STB, "van_nr": 1, "tot_nr": 5}], _trace(STB, STB_RIJEN), overgeslagen=[])
              if b.soort == "extern"]
    assert [p.nr for p in blok.passages] == [4]
    # Wie alleen de aanhef aanwijst, krijgt de aanhef.
    [blok] = [b for b in extern.blokken([{"id": STB, "van_nr": 1, "tot_nr": 1}], _trace(STB, STB_RIJEN), overgeslagen=[])
              if b.soort == "extern"]
    assert [p.nr for p in blok.passages] == [1]


@pytest.mark.parametrize("tekst, kop", [
    ("De Staatssecretaris van Financiën heeft een verweerschrift ingediend.", "Uitspraak › 1 Geding in cassatie"),   # P02
    ("Belanghebbende heeft tegen ’s Hofs uitspraak beroep in cassatie ingesteld. Het beroepschrift in cassatie is aan dit "
     "arrest gehecht en maakt daarvan deel uit.", "Uitspraak › 1 Geding in cassatie"),
    ("gewezen op het beroep in cassatie van [X] te [Z] (hierna: belanghebbende) tegen de uitspraak van het Gerechtshof",
     "Uitspraak"),
    ("Ontvanger, huurkoopovereenkomst, meldingsplicht, bodemzaak, executiewaarde, beloop van de betalingsverplichting",
     "Inhoudsindicatie"),                                                                                              # P01
    ("- Successierecht", "Inhoudsindicatie"),
])
def test_formules_en_trefwoorden(tekst, kop):
    assert extern.is_formule(tekst, kop)


@pytest.mark.parametrize("tekst, kop", [
    ("Het Hof heeft de uitspraak van de Rechtbank vernietigd en het beroep gegrond verklaard.", "Uitspraak"),
    ("Faillissementsrecht. Bodemvoorrecht fiscus. Uitoefening van dat recht door curator ex art. 57 lid 3 tweede zin Fw.",
     "Inhoudsindicatie"),
    ("- niet-inwoner van Nederland erft van AB-houder een pakket van minder dan 5 percent aandelen: "
     "bedrijfsopvolgingsfaciliteiten van toepassing?", "Inhoudsindicatie"),
    ("Artikel XVII, onderdeel C, van Overige fiscale maatregelen 2010 treedt in werking met ingang van 4 juli 2010.",
     "Enig artikel"),
])
def test_wat_inhoud_heeft_blijft(tekst, kop):
    assert not extern.is_formule(tekst, kop)
