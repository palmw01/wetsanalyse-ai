"""De JAS-prioriteitsregels gelden voor élke rol die een klasse mag kiezen.

De methode kent twee: bij samenloop wint `Tijdsaanduiding` van `Variabele en variabelewaarde` /
`Parameter en parameterwaarde` (JAS-PRIORITY-001), en `Plaatsaanduiding` van diezelfde twee
(JAS-PRIORITY-002). Ze staan als data in `jas_klassen.REGELS` en voeden twee dingen: de prompttekst
(`_prioriteitsregels_tekst`) en de deterministische validator (`_pas_prioriteitsregels_toe`).

Tot 1 sep 2026 vielen bij de **Critic** beide weg: hij kreeg de regels niet in zijn prompt, en
`pas_critic_toe` liet de validator niet over zijn correcties lopen. Een correct toegewezen
Tijdsaanduiding kon dus met rood+vervang direct naar Variabele worden gezet – rood is de tak zonder
tweede beoordelaar. De annoteerder en de herziener lopen wél door `_verwerk`, waar de validator al
stond; alleen dit pad had het gat.
"""
from __future__ import annotations

import pytest

from agent.annotatie import _pas_prioriteitsregels_toe, pas_critic_toe
from agent.annotatie_prompt import (
    annotatie_systeemprompt,
    critic_systeemprompt,
    herziening_systeemprompt,
)

CORPUS = (
    "De ontvanger verleent uitstel van betaling voor de duur van zes maanden indien de schuldenaar "
    "daarom verzoekt."
)
TIJD = "voor de duur van zes maanden"
VARIABELE = "Variabele en variabelewaarde"


# --- de validator als pure functie ----------------------------------------------------------------

def test_een_alternatief_met_hogere_prioriteit_wint():
    klasse, alts = _pas_prioriteitsregels_toe(
        VARIABELE, [{"klasse": "Tijdsaanduiding", "motivatie": "termijn"}], als_dict=True
    )
    assert klasse == "Tijdsaanduiding"
    # De weggedrukte lezing blijft zichtbaar; stil weggooien zou de twijfel verbergen.
    assert VARIABELE in [a["klasse"] for a in alts]


def test_de_alternatief_vorm_volgt_de_aanroeper():
    """Het annoteerderpad werkt met AnnotatieAlternatief, de patcher met dicts.

    Een dataclass tussen de dicts van `pas_critic_toe` schuiven levert daar verderop een TypeError
    op – dat gebeurde bij de eerste opzet van deze fix, en de test hieronder ving het.
    """
    _k, als_obj = _pas_prioriteitsregels_toe(VARIABELE, [{"klasse": "Tijdsaanduiding", "motivatie": "t"}])
    _k, als_dicts = _pas_prioriteitsregels_toe(
        VARIABELE, [{"klasse": "Tijdsaanduiding", "motivatie": "t"}], als_dict=True
    )
    assert als_obj[0].klasse == VARIABELE          # default: AnnotatieAlternatief
    assert als_dicts[0]["klasse"] == VARIABELE     # als_dict=True: kale dict


def test_de_hoogste_prioriteit_blijft_staan():
    klasse, alts = _pas_prioriteitsregels_toe("Tijdsaanduiding", [{"klasse": VARIABELE, "motivatie": "waarde"}])
    assert klasse == "Tijdsaanduiding"
    assert [a["klasse"] for a in alts] == [VARIABELE]


def test_zonder_prioriteitsrelatie_verandert_er_niets():
    """Twee klassen die in geen enkele regel samen voorkomen: de validator hoort zich er niet mee te bemoeien."""
    klasse, alts = _pas_prioriteitsregels_toe("Voorwaarde", [{"klasse": "Rechtsfeit", "motivatie": "?"}])
    assert (klasse, [a["klasse"] for a in alts]) == ("Voorwaarde", ["Rechtsfeit"])


def test_de_wisselende_klasse_komt_er_niet_dubbel_in():
    klasse, alts = _pas_prioriteitsregels_toe(
        VARIABELE,
        [{"klasse": "Tijdsaanduiding", "motivatie": "termijn"}, {"klasse": VARIABELE, "motivatie": "al aanwezig"}],
    )
    assert klasse == "Tijdsaanduiding"
    assert [a["klasse"] for a in alts].count(VARIABELE) == 1


# --- de validator over het resultaat van de patcher ------------------------------------------------

def test_de_critic_mag_een_prioriteitsregel_niet_terugdraaien():
    """Rood + vervang is de tak die DIRECT wordt uitgevoerd – daar hoort de methode-regel achter."""
    uit, _n, _rest = pas_critic_toe(
        [{"id": "a", "klasse": "Tijdsaanduiding", "tekst": TIJD}],
        [{"id": "a", "aandacht": "rood", "actie": "vervang", "voorstel_klasse": VARIABELE,
          "motivatie": "dit is een waarde"}],
        CORPUS,
    )
    assert uit[0]["klasse"] == "Tijdsaanduiding"
    # De lezing van de Critic gaat niet verloren: hij ligt als alternatief naast de kaart.
    assert VARIABELE in [a["klasse"] for a in (uit[0].get("alternatieven") or [])]


def test_een_geel_voorstel_met_hogere_prioriteit_wordt_alsnog_de_klasse():
    """Zelfde eindtoestand als uit de annoteerder, dus dezelfde uitkomst – ongeacht wie het aandroeg.

    Dit ís geen schending van "geel verandert nooit iets": dat principe houdt een tweede TAALMODEL
    tegen, en dit is een deterministische methode-regel die de andere lezing bovendien laat staan.
    """
    uit, _n, _rest = pas_critic_toe(
        [{"id": "a", "klasse": VARIABELE, "tekst": TIJD}],
        [{"id": "a", "aandacht": "geel", "actie": "vervang", "voorstel_klasse": "Tijdsaanduiding",
          "motivatie": "het is een termijn"}],
        CORPUS,
    )
    assert uit[0]["klasse"] == "Tijdsaanduiding"
    assert VARIABELE in [a["klasse"] for a in (uit[0].get("alternatieven") or [])]


def test_een_markering_van_de_jurist_blijft_ongemoeid():
    """Dezelfde grens als in de rest van de patcher: een mens overrulen we niet, ook niet met een regel."""
    uit, _n, _rest = pas_critic_toe(
        [{"id": "a", "klasse": VARIABELE, "tekst": TIJD, "van_jurist": True,
          "alternatieven": [{"klasse": "Tijdsaanduiding", "motivatie": "termijn"}]}],
        [{"id": "a", "aandacht": "rood", "actie": "vervang", "voorstel_klasse": "Tijdsaanduiding"}],
        CORPUS,
    )
    assert uit[0]["klasse"] == VARIABELE


def test_een_gewone_correctie_wordt_niet_geblokkeerd():
    """De validator mag alleen ingrijpen waar een regel geldt – anders smoort hij legitiem werk."""
    uit, n, _rest = pas_critic_toe(
        [{"id": "a", "klasse": "Voorwaarde", "tekst": "indien de schuldenaar daarom verzoekt"}],
        [{"id": "a", "aandacht": "rood", "actie": "vervang", "voorstel_klasse": "Rechtsfeit"}],
        CORPUS,
    )
    assert (uit[0]["klasse"], n.toegepast) == ("Rechtsfeit", 1)


# --- de regels staan in de prompt van elke classificerende rol -------------------------------------

@pytest.mark.parametrize(
    "naam,prompt",
    [
        ("annoteerder", annotatie_systeemprompt),
        ("critic", critic_systeemprompt),
        ("herziener", herziening_systeemprompt),
    ],
)
def test_elke_classificerende_rol_kent_de_prioriteitsregels(naam, prompt):
    """Wie de dertien klassen krijgt mag kiezen, en hoort dus de regels te kennen die die keuze binden."""
    tekst = prompt()
    assert "JAS-PRIORITY-001" in tekst, f"{naam} kent JAS-PRIORITY-001 niet"
    assert "JAS-PRIORITY-002" in tekst, f"{naam} kent JAS-PRIORITY-002 niet"
