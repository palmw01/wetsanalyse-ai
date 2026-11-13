"""De live-proef van de bronconnector Kennisgroepstandpunten: het contract met de REST API van de Belastingdienst.

De suite draait tegen nepbronnen en echte opnames (`test_kennisgroepen_lezer.py`, `test_kennisgroepen_tools.py`). Een
opname bevestigt niet wat de connector van de echte dienst aanneemt: dat de lijst `X-WP-Total` en `X-WP-TotalPages`
draagt, dat `_embed` de namen van de taxonomieën geeft (de taxonomie-endpoints zelf geven 401), dat elke titel een kenmerk
draagt dat de lezer leest, dat `?search=` een kenmerk vindt en dat een publicatie per id te lezen is. Deze proef toetst
dat, zonder graaf, model of secrets, met hoogstens vijf verzoeken.

Hij draait niet in de poort; dagelijks in `.github/workflows/bronnenwacht.yml`, lokaal met
`BRONNEN_LIVE=1 uv run pytest -m live tests/test_kennisgroepen_live.py`. Is de dienst onbereikbaar, dan begint de melding
met `DIENST ONBEREIKBAAR`.
"""
from __future__ import annotations

import os

import httpx
import pytest

from agent.adapters.kennisgroepen_bron import USER_AGENT, KennisgroepenBron, KennisgroepenFout
from agent.tools.kennisgroep_tools import stuk_van
from bronmodel import kennisgroepen as kg

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("BRONNEN_LIVE"), reason="live: zet BRONNEN_LIVE=1"),
]

#: Een standpunt dat een ouder standpunt intrekt (13 nov 2026), en dat ouder kenmerk.
VOORBEELD = "kg:013:2026:4"


def _get(url: str) -> httpx.Response:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except httpx.HTTPError as exc:
        pytest.fail(f"DIENST ONBEREIKBAAR: {url}: {type(exc).__name__}")
    if r.status_code >= 500:
        pytest.fail(f"DIENST ONBEREIKBAAR: {url}: HTTP {r.status_code}")
    return r


def test_de_lijst_draagt_het_totaal_en_de_termen():
    r = _get(kg.lijst_url(1, per_pagina=10))
    assert r.status_code == 200, r.text[:200]
    totaal, paginas = int(r.headers["X-WP-Total"]), int(r.headers["X-WP-TotalPages"])
    assert totaal >= 1000 and paginas == -(-totaal // 10)
    items = r.json()
    assert len(items) == 10
    for item in items:
        s = kg.lees_publicatie(item)
        assert s.id, f"geen kenmerk in {item['title']['rendered']!r}"
        assert s.rijen and s.metadata["orgaan"].startswith("KG "), s.metadata
        assert s.metadata["soort"] in ("Standpunt", "Informatie")
        assert {"belastingsoort", "rubriek", "subrubriek", "cmd_vaststellingsdatum"} <= set(item["meta"])


def test_zoeken_op_kenmerk_en_lezen_per_id():
    bron = KennisgroepenBron()
    try:
        gelezen = bron.publicatie(None, VOORBEELD)
    except KennisgroepenFout as exc:
        if exc.code in ("onbereikbaar", "bezet"):
            pytest.fail(f"DIENST ONBEREIKBAAR: {exc}")
        raise
    s = gelezen.standpunt
    assert (s.id, s.status) == (VOORBEELD, "geldend")
    assert "kg:013:2018:173" in s.vervangt
    assert any("Antwoord" in r.kop for r in s.rijen)
    stuk = stuk_van(gelezen)
    assert {"id", "label", "link", "bron_hash", "datum", "orgaan"} <= set(stuk)


def test_de_taxonomieen_zijn_niet_openbaar():
    """Staat dit ooit open, dan kan de index de namen ook zonder `_embed` lezen; tot dan leunt hij erop."""
    r = _get(f"{kg.API}/wt_publication_tag?per_page=1")
    assert r.status_code in (200, 401)
