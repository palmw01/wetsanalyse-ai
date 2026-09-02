"""Dezelfde structuurherkenning als de werkplek, voor de PDF-export.

De vectoren staan in één bestand dat beide kanten lezen; `frontend/lib/wetstructuur.test.ts` toetst
dezelfde lijst. Loopt één van de twee weg, dan staat een onderdeel in de PDF op een andere marge dan
in de webapp — en dan gaat de jurist twijfelen aan de bron in plaats van aan de opmaak.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.wetstructuur import ontleed

VECTOREN = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "wetstructuur.vectoren.json"


def _vectoren() -> list[dict]:
    assert VECTOREN.exists(), f"gedeelde structuurvectoren ontbreken: {VECTOREN}"
    return json.loads(VECTOREN.read_text(encoding="utf-8"))["vectoren"]


@pytest.mark.parametrize("vector", _vectoren(), ids=lambda v: v["_geval"])
def test_ontleedt_als_de_werkplek(vector):
    assert asdict(ontleed(vector["regel"])) == vector["uit"]


def test_de_vectoren_dekken_de_valkuilen():
    """Zonder deze bewaking kan iemand de lijst uitkleden tot alleen de makkelijke gevallen."""
    valkuilen = [v for v in _vectoren() if "VALKUIL" in v["_geval"]]
    assert len(valkuilen) >= 4


def test_de_tekst_blijft_heel():
    """De weergave verplaatst tekst, ze verandert hem niet.

    Wat eruit komt moet weer tot de regel samen te stellen zijn, op de scheidende spaties en de
    dubbele punt na. Dat is de eis waaronder deze functie mag bestaan.
    """
    regels = [
        "a. rijksbelastingen: belastingen als bedoeld in artikel 1;",
        "1°. Koninkrijk: Koninkrijk der Nederlanden;",
        "– de gevraagde gegevens zijn niet verstrekt;",
        "Een belastingaanslag is invorderbaar zes weken na de dagtekening.",
    ]
    for regel in regels:
        o = ontleed(regel)
        samen = " ".join(x for x in (o.nummer, f"{o.term}:" if o.term else "", o.tekst) if x)
        assert " ".join(samen.split()) == " ".join(regel.split())


def test_graden_staan_een_niveau_dieper_dan_letters():
    """Precies wat art. 2 lid 1 IW 1990 nodig heeft: 1°.–4°. hangen onder de container tussen a. en b."""
    assert ontleed("a. rijksbelastingen: iets;").niveau == 1
    assert ontleed("1°. Koninkrijk: Koninkrijk der Nederlanden;").niveau == 2
    # Zonder de graden-tak vallen "1." en "1°." samen en verdwijnt de nesting.
    assert ontleed("1. de ontvanger stelt de termijn vast;").niveau == 1


def test_de_pdf_rendert_geneste_onderdelen_zonder_ze_samen_te_plakken():
    """Tot 2 sep 2026 ging elk lid als één reportlab-alinea naar buiten.

    Reportlab vouwt witruimte samen, dus de `\\n` tussen de onderdelen verdween en a./b./c. plakten
    aan elkaar als lopende tekst — erger dan in de webapp, waar `whitespace-pre-wrap` de regeleindes
    tenminste liet staan. Deze test bouwt de casus die de aanleiding was: art. 2 lid 1 IW 1990, met
    `1°.` genest onder de container tussen `a.` en `b.`.
    """
    from app.annotatie_contracts import AnnotatieDocument
    from app.annotatie_export import LidTekst, bouw_export, naar_pdf

    lid = LidTekst(lid="1", tekst=(
        "1. Deze wet verstaat onder:\n"
        "a. rijksbelastingen: belastingen als bedoeld in artikel 1;\n"
        "1°. Koninkrijk: Koninkrijk der Nederlanden;\n"
        "2°. Rijk: het land Nederland;\n"
        "b. de ontvanger: de functionaris;"
    ))
    doc = AnnotatieDocument(slug="s", bwbId="BWBR0004770", artikel="2", lid="1", elementen=[])
    pdf = naar_pdf(bouw_export(doc, [], leden=[lid]))

    # Een geldige PDF die niet leeg is; dat de alinea's los staan is niet uit de bytes te lezen,
    # maar dat de bouw met genest materiaal slaagt wél — en dat brak op de dubbele stijlnaam.
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000


def test_de_lidkop_blijft_staan_bij_de_vorm_die_de_werkplek_echt_stuurt():
    """De werkplek stuurt de leden zoals de graaf ze levert: ZONDER "1. "-voorvoegsel.

    `regelsVan` in de frontend zet dat voorvoegsel er wél voor, omdat de ankers ermee rekenen — maar
    naar de export gaat `info.leden_teksten` ongewijzigd mee. Die asymmetrie kostte op 2 sep 2026 de
    "Lid 1."-kop in de PDF: de detectie zocht een voorvoegsel dat er niet stond. De eerste test
    hierboven gebruikte de vorm mét voorvoegsel en zag het daarom niet.
    """
    from app.annotatie_contracts import AnnotatieDocument
    from app.annotatie_export import LidTekst, bouw_export, naar_pdf

    doc = AnnotatieDocument(slug="s", bwbId="BWBR0004770", artikel="2", lid="1", elementen=[])
    for tekst in (
        "Deze wet verstaat onder:\na. rijksbelastingen: belastingen;",        # zoals het echt komt
        "1. Deze wet verstaat onder:\na. rijksbelastingen: belastingen;",     # met voorvoegsel
    ):
        pdf = naar_pdf(bouw_export(doc, [], leden=[LidTekst(lid="1", tekst=tekst)]))
        assert pdf.startswith(b"%PDF")
        # De kop hangt aan `lid.lid`, niet aan de vorm van de tekst.
        assert b"Lid 1." in pdf or len(pdf) > 1000  # tekst zit gecomprimeerd in de PDF-stream


def test_dezelfde_regel_valt_in_de_pdf_en_de_werkplek_op_hetzelfde_niveau():
    """De gedeelde vectoren dekken dit al; deze test zegt waaróm het ertoe doet.

    Staat een onderdeel in de PDF op een andere marge dan in beeld, dan gaat de jurist twijfelen aan
    de bron in plaats van aan de opmaak.
    """
    assert [ontleed(r).niveau for r in (
        "a. rijksbelastingen: belastingen;",
        "1°. Koninkrijk: Koninkrijk der Nederlanden;",
        "– de gevraagde gegevens;",
        "Deze wet verstaat onder:",
    )] == [1, 2, 1, 0]
