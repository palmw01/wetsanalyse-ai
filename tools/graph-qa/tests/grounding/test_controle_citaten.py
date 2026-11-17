"""Twee valse meldingen van de controle uit de hermeting na #1614 (16 nov 2026, S01; meetverslag
`centrale-agent-2026-11-16-hermeting-c2`).

1. Een citaat is tekst van de bron, geen duiding van Lex. De Hoge Raad verwijst in een geciteerde rechtsoverweging naar
   eerdere arresten ("vgl. HR 31 maart 2017, ECLI:NL:HR:2017:530 …"). De controle las dat als een samenvatting van een
   stuk dat niet gelezen was: drie meldingen "samenvatting van … zonder gelezen tekst".
2. Een ontkenning is geen claim: "hoofdstukken 6 en 7 zijn niet volledig gelezen" gaf "volledig gelezen, maar 10
   stukken zijn maar deels gelezen"."""
from __future__ import annotations

import pytest

import json

from agent.gelezen import ongelezen_samengevat, volledig_geclaimd, zonder_citaten
from agent.grounding import check_grounding

pytestmark = pytest.mark.risico("R15")

GELEZEN = "ECLI:NL:HR:2019:576"
VERWEZEN = "ECLI:NL:HR:2017:530"
ZOEK = ("zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "aantal": 2, "resultaten": [
    {"id": GELEZEN, "label": "HR 12 april 2019"}, {"id": VERWEZEN, "label": "HR 31 maart 2017"}]}))
PASSAGE = ("Indien deze afweging leidt tot het besluit om belastingschulden niet te betalen, kan die afweging slechts "
           "dan worden aangemerkt als kennelijk onbehoorlijk bestuur indien geen redelijk denkend bestuurder dezelfde "
           f"afweging had gemaakt (vgl. HR 31 maart 2017, {VERWEZEN}, rechtsoverweging 3.2.2).")


def _lees(volledig: bool = True):
    return ("get_uitspraak", json.dumps({"status": "ok", "volledig": volledig, "aantal": 1,
                                         "stuk": {"id": GELEZEN, "label": "HR 12 april 2019"},
                                         "resultaten": [{"nr": 1, "tekst": PASSAGE}]}))


ANTWOORD = (f"**HR 12 april 2019** ({GELEZEN})\nDe Hoge Raad legt de maatstaf voor kennelijk onbehoorlijk bestuur uit: "
            "een bestuurder mag kiezen welke schuldeisers hij betaalt, tenzij geen redelijk denkend bestuurder dat zou "
            f'doen.\n\n> "{PASSAGE}" (r.o. 3.5.1)')


def test_een_verwijzing_in_een_citaat_is_geen_samenvatting_van_het_verwezen_stuk():
    trace = [ZOEK, _lees()]
    assert ongelezen_samengevat(zonder_citaten(ANTWOORD), trace) == []
    assert not any(VERWEZEN in b for b in check_grounding(ANTWOORD, trace).beweringen)
    # Schrijft Lex zelf over het verwezen stuk wat erin staat, dan blijft het een bewering.
    eigen = ANTWOORD + (f"\n\nIn {VERWEZEN} oordeelde de Hoge Raad dat de bestuurder persoonlijk een ernstig verwijt "
                        "moet treffen voor elke onbetaalde belastingschuld van de vennootschap.")
    assert any(VERWEZEN in b for b in check_grounding(eigen, trace).beweringen)


def test_het_citaat_zelf_blijft_getoetst_op_letterlijkheid():
    """`zonder_citaten` geldt alleen voor de duidingtoetsen: een citaat dat niet in de bron staat, blijft niet letterlijk."""
    vals = ANTWOORD.replace("geen redelijk denkend bestuurder", "elke redelijk denkende bestuurder")
    assert check_grounding(vals, [ZOEK, _lees()]).niet_letterlijk


def test_een_ontkenning_is_geen_claim_dat_alles_gelezen_is():
    deels = [ZOEK, _lees(volledig=False)]
    assert volledig_geclaimd("Gelezen: hoofdstukken 6 en 7 zijn niet volledig gelezen.", deels) == []
    assert volledig_geclaimd("Ik heb de uitspraken niet helemaal doorgelezen.", deels) == []
    assert volledig_geclaimd("Ik heb alle uitspraken volledig gelezen.", deels), "een echte claim blijft een bewering"
    # Een ontkenning en een claim in één tekst: de claim telt.
    assert volledig_geclaimd("Niet alles is volledig gelezen. De arresten las ik wel volledig door.", deels)
