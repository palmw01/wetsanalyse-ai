"""CORS is de buitenste middleware (SonarQube S8414): elk antwoord krijgt de CORS-headers, ook een fout uit een
andere middleware, en een preflight komt nergens anders langs."""
from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware

from app.main import app


def test_cors_is_de_buitenste_middleware():
    # `user_middleware` staat van buiten naar binnen: de laatst toegevoegde staat vooraan.
    assert app.user_middleware[0].cls is CORSMiddleware
