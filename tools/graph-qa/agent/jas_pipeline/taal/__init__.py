"""Linguïstische analyselaag (ADR-001 PR 3): UD-model, verwisselbare providers, afgeleide constituenten."""
from .afgeleid import Constituent, bijzinnen, naamwoordgroepen, predicaten, spanopties
from .model import LinguisticAnalysis, Niveau, Token, Zin
from .provider import NullProvider, SpacyProvider, StanzaProvider, TaalProvider, maak_provider

__all__ = [
    "Constituent", "LinguisticAnalysis", "Niveau", "NullProvider", "SpacyProvider",
    "StanzaProvider", "TaalProvider", "Token", "Zin", "bijzinnen", "maak_provider",
    "naamwoordgroepen", "predicaten", "spanopties",
]
