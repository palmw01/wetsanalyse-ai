"""Gedeelde fixture voor ketenmetingen: vaste bronpassage, vastgelegde modelcalls.

De keten (annoteerder → critic → patch/herziening → critic → emit) draait echt, maar de graaf
geeft altijd dezelfde passage terug. Zo meet een script de modelketen en niet de bronophaling.
Agentmodules worden pas binnen de functies geïmporteerd: `compare_methodeketen` zet eerst een
ander agentpad op `sys.path`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / 'docs/wetsanalyse/referentieset/cases.json'


def laad_cases(ids: list[str]) -> list[dict[str, Any]]:
    """De gevraagde referentiecasussen, in de gevraagde volgorde; held-out wordt geweigerd."""
    alle = {c['id']: c for c in json.loads(CASES.read_text())}
    onbekend = [i for i in ids if i not in alle]
    if onbekend:
        raise ValueError(f'onbekende casus: {", ".join(onbekend)}')
    gekozen = [alle[i] for i in ids]
    if any(c['split'] != 'ontwikkeling' for c in gekozen):
        raise ValueError('held-out casussen niet gebruiken voor ontwikkelmetingen')
    return gekozen


def ontwikkelcases() -> list[str]:
    return [c['id'] for c in json.loads(CASES.read_text()) if c['split'] == 'ontwikkeling']


def ketensettings(settings: Any) -> Any:
    """Expliciet-doelketen zonder checkpoint, splitsing of decompositie; twee Critic-rondes."""
    return settings.model_copy(update={
        'checkpoint_db_path': None, 'checkpoint_db_url': None,
        'llm_timeout_seconds': 60, 'llm_max_retries': 0,
        'enable_kandidaat_splitsing': False, 'critic_max_rondes': 2,
        'enable_planning': True, 'enable_decomposition': False,
    })


# Alleen technische fixture-identiteit: elke casustekst staat als lid 1 van art. 9 IW 1990.
# Contract 2 leest de bron als bronboom (`bronmodel.resolve`), dus de graaf levert rijen.
BWB = 'BWBR0004770'
_REG = f'urn:bwb:{BWB}'
_ART = _REG + ':artikel:9'
LID = _ART + ':lid:1'


def fixture_rijen(text: str) -> list[dict[str, str]]:
    return [
        {'node': _REG, 'type': 'Regeling', 'nummer': '', 'tekst': ''},
        {'node': _ART, 'parent': _REG, 'type': 'Artikel', 'nummer': '9', 'tekst': ''},
        {'node': LID, 'parent': _ART, 'type': 'Lid', 'nummer': '1', 'tekst': text},
    ]


def fixture_doel(case: dict[str, Any]) -> dict[str, str]:
    return {'bron_iri': LID}


class FixtureGraph:
    """Graaf die op elke SPARQL-vraag dezelfde bronboom teruggeeft."""

    def __init__(self, text: str):
        self.rows = fixture_rijen(text)

    def initialize(self):
        return {}

    def close(self):
        pass

    def sparql(self, query):
        return self.rows

    def semantic_search(self, query, limit=10):
        raise AssertionError('onverwachte zoekroute')


class LegeAnnotaties:
    """Annotatie-leespoort zonder bestaande lagen: elke run annoteert vers, niets wordt hergebruikt.

    Zo meet elke herhaling de keten zelf, en schrijft de meting niets in de werkvoorraad.
    """

    def __init__(self, text: str):
        from bronmodel import bouw_snapshot
        self.snapshot_id = bouw_snapshot(fixture_rijen(text), bron_iri=LID, bwb_id=BWB)['snapshot_id']

    def zoeken(self, filters):
        return {'status': 'ok', 'resultaten': [], 'volledig': True}

    def element(self, id):
        return {'status': 'niet_gevonden'}

    def dekking(self, doel):
        return {'status': 'ok', 'snapshot_id': self.snapshot_id, 'voltooid': False,
                'parent_context': False, 'bereik': []}

    def weergave(self, doel):
        return {'schema_versie': 2, 'snapshot_id': self.snapshot_id, 'elementen': [], 'lagen': []}


TOKENVELDEN = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')


class Capture:
    """Legt elke modelcall vast; bij `create` ook antwoordtekst en verbruik."""

    def __init__(self, llm: Any):
        self.llm = llm
        self.calls: list[dict[str, Any]] = []

    def create(self, **kw):
        resp = self.llm.create(**kw)
        usage = getattr(resp, 'usage', None)
        # Met prompt-caching telt `input_tokens` alleen het ongecachete deel; de rest staat apart.
        self.calls.append({**kw, 'antwoord': ''.join(b.text for b in resp.content if b.type == 'text'),
                           **{k: getattr(usage, k, 0) or 0 for k in TOKENVELDEN}})
        return resp

    def stream(self, **kw):
        self.calls.append(kw)
        return self.llm.stream(**kw)
