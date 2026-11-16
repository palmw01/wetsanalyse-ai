"""De voorlezing van een genoemd stuk (`nodes/bron_lezen.py`): een kort stuk leest de code helemaal, voor elke connector.

Iteratie bekendmakingen ronde 2 (B21): bij "wat staat er in" bladerde het model een stuk van 100 alinea's in zes rondes
door, één ronde per pagina. Nu leest de code een stuk van hoogstens `MAX_RIJEN_KORT` rijen in één keer voor, tot
`MAX_PAGINAS` pagina's. Een langer stuk blijft bij de eerste pagina (met `inhoud`), en een gefilterde lezing ook.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.nodes import bron_lezen as bl
from bronmodel.connectors import CONNECTORS

#: Per connectorvorm: de leestool, haar argument en een id.
VORMEN = [(c.leestool, c.lees_argument, c.voorbeeld_id) for c in CONNECTORS.values() if c.leestool and c.voorbeeld_id
          and c.leestool not in bl.HEEL_LEZEN]


def _pagina(tool: str, arg: str, ident: str, offset: int, totaal: int, per: int) -> str:
    rijen = [{"nr": n + 1, "tekst": f"Alinea {n + 1}."} for n in range(offset, min(offset + per, totaal))]
    vervolg = ({"tool": tool, "args": {arg: ident, "offset": offset + per}} if offset + per < totaal else None)
    return json.dumps({"status": "ok", "volledig": vervolg is None, "aantal": len(rijen), "totaal": totaal,
                       "stuk": {"id": ident}, "resultaten": rijen, **({"vervolg": vervolg} if vervolg else {})})


def _lees(tool: str, arg: str, ident: str, totaal: int, per: int = 30, extra: dict | None = None) -> list[str]:
    vragen: list[dict] = []

    def uitvoeren(b, state, writer, aanroep):
        vragen.append(aanroep["input"])
        return _pagina(tool, arg, ident, int(aanroep["input"].get("offset") or 0), totaal, per)

    state = {"bron_lezen": [{"name": tool, "input": {arg: ident, **(extra or {})}}], "source_trace": []}
    with patch.object(bl, "execute_tool", uitvoeren), patch.object(bl, "get_stream_writer", return_value=lambda _: None):
        uit = bl.bron_lezen_node(SimpleNamespace(), state)
    assert [naam for naam, _ in uit["source_trace"]] == [tool] * len(vragen)
    return [json.dumps(v, sort_keys=True) for v in vragen]


def test_er_is_een_vorm_per_connector():
    assert {t for t, _, _ in VORMEN} >= {"get_kamerstuk", "get_bekendmaking", "get_uitspraak"}


@pytest.mark.parametrize("tool,arg,ident", VORMEN)
def test_een_kort_stuk_leest_de_code_helemaal(tool, arg, ident):
    vragen = _lees(tool, arg, ident, totaal=100)
    assert len(vragen) == 4, "100 rijen op pagina's van 30: vier lezingen in code, geen ronde per pagina"


@pytest.mark.parametrize("tool,arg,ident", VORMEN)
def test_een_lang_stuk_blijft_bij_de_eerste_pagina(tool, arg, ident):
    assert len(_lees(tool, arg, ident, totaal=bl.MAX_RIJEN_KORT + 1)) == 1, "lang: de inhoud wijst de weg"


@pytest.mark.parametrize("tool,arg,ident", VORMEN)
def test_de_harde_grens_op_pagina_s(tool, arg, ident):
    assert len(_lees(tool, arg, ident, totaal=bl.MAX_RIJEN_KORT, per=5)) == bl.MAX_PAGINAS, "nooit meer dan MAX_PAGINAS"


def test_een_gefilterde_lezing_leest_de_code_niet_verder():
    assert len(_lees("get_bekendmaking", "id", "stcrt-2026-37344", totaal=100, extra={"regeling": "Leidraad"})) == 1



def test_een_niet_gevonden_stuk_met_opvolger_noemt_die():
    """Meting kennisgroepen 14 nov 2026, vraag 10: "Welk standpunt vervangt KG:013:2018:0173?" kreeg "Controleer het
    id", terwijl de index wist dat KG:013:2026:4 het intrekt."""
    fout = {"status": "error", "reden": "niet_gevonden", "melding": "…", "vervangen_door": ["kg:013:2026:4"]}
    antwoord = bl._zonder_tekst([{"content": json.dumps(fout)}], [], [{"name": "get_standpunt",
                                                                       "input": {"id": "kg:013:2018:173"}}])
    [leemte] = antwoord.blokken
    assert "ingetrokken door Kennisgroepstandpunt KG:013:2026:4" in leemte.tekst
    assert "Controleer het id" not in leemte.tekst
    zonder = dict(fout, vervangen_door=[])
    [kaal] = bl._zonder_tekst([{"content": json.dumps(zonder)}], [], [{"name": "get_standpunt",
                                                                        "input": {"id": "kg:013:2018:173"}}]).blokken
    assert "Controleer het id" in kaal.tekst
