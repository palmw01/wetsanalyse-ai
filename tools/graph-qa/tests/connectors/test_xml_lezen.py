"""XML van buiten: één ingang die entiteiten weigert en de echte stukken leest (`agent/xml_lezen.py`).

Ruff S314 (kwaliteitsmeting, PR #1801): de adapters lazen de antwoorden van KOOP, de Rechtspraak en de SRU-diensten met
`ET.fromstring`. Nu langs `lees_xml`, en een weigering is een gewone `ParseError`, zodat elke aanroeper haar afhandelt als
onleesbare XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from agent.adapters.sru_koop import KoopFout, lees_records
from agent.tools.op_xml import _cals
from agent.xml_lezen import lees_xml

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>
<x>&b;</x>"""

XXE = b"""<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY geheim SYSTEM "file:///etc/passwd">]>
<x>&geheim;</x>"""


@pytest.mark.parametrize("xml", [BILLION_LAUGHS, XXE], ids=["entiteiten", "extern"])
def test_een_entiteitdeclaratie_is_onleesbare_xml(xml):
    with pytest.raises(ET.ParseError, match="XML geweigerd"):
        lees_xml(xml)


def test_elke_opgenomen_xml_blijft_leesbaar():
    """De opnames van KOOP dragen een DOCTYPE met een externe DTD; die blijft gewoon leesbaar."""
    paden = sorted(FIXTURES.rglob("*.xml"))
    assert paden, "geen opnames gevonden"
    met_doctype = 0
    for pad in paden:
        data = pad.read_bytes()
        met_doctype += b"<!DOCTYPE" in data
        assert lees_xml(data) is not None, pad
    assert met_doctype, "de set moet een stuk met een DOCTYPE bevatten, anders toetst ze de DTD niet"


def test_een_sru_antwoord_met_entiteiten_is_een_weigering_van_de_bron():
    with pytest.raises(KoopFout) as fout:
        lees_records(BILLION_LAUGHS)
    assert fout.value.code == "geweigerd"


def test_een_cals_tabel_telt_kop_en_rijen_en_samengevoegde_cellen():
    """`_cals` las een rij in een closure binnen de lus (B023); nu in `_cals_rij`. Zelfde uitkomst, ook over twee groepen."""
    tabel = ET.fromstring("""<table><tgroup cols="2">
      <colspec colname="c1"/><colspec colname="c2"/>
      <thead><row><entry>Jaar</entry><entry>Bedrag</entry></row></thead>
      <tbody><row><entry namest="c1" nameend="c2">samen</entry></row>
             <row><entry>2025</entry><entry morerows="1">10</entry></row>
             <row><entry></entry><entry></entry></row></tbody></tgroup>
      <tgroup cols="2"><colspec colname="a"/><colspec colname="b"/>
      <thead><row><entry>Anders</entry><entry>Kop</entry></row></thead>
      <tbody><row><entry>x</entry><entry>y</entry></row></tbody></tgroup></table>""")
    kolommen, rijen, samen = _cals(tabel, [])
    assert kolommen == ["Jaar", "Bedrag"], "de kop van de eerste groep"
    assert rijen == [["samen", ""], ["2025", "10"], ["x", "y"]], "een lege rij valt weg"
    assert samen == 2
