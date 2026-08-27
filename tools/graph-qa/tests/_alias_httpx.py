"""Laat `import httpx` naar httpx2 wijzen, vóórdat pytest iets anders laadt.

Waarom dit een aparte plugin is en geen regel in `conftest.py`: `alias_httpx()` moet draaien
vóórdat welke module dan ook `httpx` of `httpcore` importeert, anders gooit hij
`RuntimeError: httpx was already imported`. Een conftest laadt daar te laat voor – de testmodules
(en `api.main`, die de alias zelf ook aanroept) zijn dan al aan de beurt geweest.

Aangehaakt via `addopts = "-p tests._alias_httpx"` in pyproject.toml; `-p` laadt een plugin vóór de
collectie begint. Dubbel aanroepen is een no-op, dus dat `api/main.py` het óók doet is geen
probleem – die blijft nodig voor de draaiende dienst, waar geen pytest bij komt kijken.
"""

import httpx2

httpx2.alias_httpx()
