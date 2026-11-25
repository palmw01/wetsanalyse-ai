"""De rechtentabel van de api (Lex Bench §20.5 stap 3, risico R12; testplan api V3).

Welke route welke bewaker vraagt, stond nergens als geheel getest: haalde iemand een dependency weg, dan werd alleen een
route rood die toevallig een eigen test op 401/403 had. Deze test leest per route de dependencies uit `app.routes` en
eist twee dingen:

- **vaste regels** die voor elke route gelden (een bearer-token, het admin-token onder `/v1/admin`, 2FA alleen voor een
  beheerder, een actieve gebruiker in elk domein met gegevens van gebruikers, en alleen gezondheid en gereedheid publiek);
- **de tabel** hieronder, route voor route. Een nieuwe route zonder regel in de tabel faalt, en een gewijzigde bewaker
  ook: dan is de wijziging zichtbaar en bespreekbaar, zoals de keuze tussen het admin-token alleen en de 2FA-plicht.

De tabel bijwerken is een bewuste handeling: draai `python -m tests.test_rechtentabel` vanuit `api/` en lees het verschil.
"""
from __future__ import annotations

import pytest

from fastapi.routing import APIRoute

pytestmark = pytest.mark.risico("R12")

#: De bewakers die de tabel bijhoudt (de namen van de dependency-functies).
BEWAKERS = ("require_client", "require_admin", "actieve_userid", "huidige_beheerder", "beheerder_met_2fa",
            "token_login_aan", "rate_limited_client", "rate_limited_admin_test")

#: Zonder token: alleen wat de container-runtime peilt.
PUBLIEK = {"GET /health", "GET /ready"}

#: Domeinen met gegevens van gebruikers: elke route vraagt een actieve gebruiker (`actieve_userid`), of is van het beheer.
GESCOPET = ("annotatie", "artefact-versies", "begrippen", "berichten", "delegaties", "feedback", "gesprekken", "regels",
            "werkgebieden")

#: Routes buiten die domeinen zonder actieve gebruiker, met de reden. Een nieuwe staat hier bewust bij.
ZONDER_GEBRUIKER = {
    "auth": "inloggen, registreren en 2FA gebeuren vóór er een sessie is; de identiteit staat in de body of het token",
    "connectors": "graph-qa leest het register van de beheerder",
    "modelkeuzes": "graph-qa leest de modelkeuzes van de beheerder",
    "verbruik": "graph-qa boekt en controleert het verbruik namens de gebruiker in de body",
    "werkplaats": "graph-qa meldt wat er in zijn image zit (PUT /v1/werkplaats/image)",
}

TABEL: dict[str, tuple[str, ...]] = {
    "DELETE /v1/admin/api-tokens/{token_id}": ('require_admin',),
    "DELETE /v1/admin/berichten/{bericht_id}": ('require_admin',),
    "DELETE /v1/admin/feedback/{feedback_id}": ('require_admin',),
    "DELETE /v1/admin/profiles/{name}": ('require_admin',),
    "DELETE /v1/admin/registraties/{aanvraag_id}": ('require_admin',),
    "DELETE /v1/admin/users/{userid}": ('require_admin',),
    "DELETE /v1/annotatie/elementen/{element_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/gesprekken/{gesprek_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/begrippen/gebruik/{begrip_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/{koppeling_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/bronnen/{selectie_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/dekking/buiten-behandeling/{element_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/parameterwaarden/{waarde_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/dragers/{drager_id}": ('require_client', 'actieve_userid'),
    "DELETE /v1/werkgebieden/{werkgebied_id}/relaties/{relatie_id}": ('require_client', 'actieve_userid'),
    "GET /health": (),
    "GET /ready": (),
    "GET /v1/admin/annotatie-statistiek": ('require_admin',),
    "GET /v1/admin/annotatie/graafcontrole": ('require_admin',),
    "GET /v1/admin/annotatie/prullenbak": ('require_admin',),
    "GET /v1/admin/api-tokens": ('require_admin',),
    "GET /v1/admin/berichten": ('require_admin',),
    "GET /v1/admin/budget": ('require_admin',),
    "GET /v1/admin/connectors": ('require_admin',),
    "GET /v1/admin/connectors/{naam}/audit": ('require_admin',),
    "GET /v1/admin/feedback": ('require_admin',),
    "GET /v1/admin/feedback/ongelezen-aantal": ('require_admin', 'huidige_beheerder'),
    "GET /v1/admin/modelkeuzes": ('require_admin',),
    "GET /v1/admin/modelkeuzes/{sleutel}/audit": ('require_admin',),
    "GET /v1/admin/profiles": ('require_admin',),
    "GET /v1/admin/profiles/{name}": ('require_admin',),
    "GET /v1/admin/registraties": ('require_admin',),
    "GET /v1/admin/users": ('require_admin',),
    "GET /v1/admin/verbruik": ('require_admin',),
    "GET /v1/annotatie/bepaling": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/capabilities": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/dekking": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/diagram": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/diagrammen": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/elementen/{element_id}": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/elementen/{element_id}/graaf": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/export-schema": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/graaf": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/knoop": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/lagen/{laag_id}/revisies": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/node-lagen": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/samenhang": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/samenhang/antwoord": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/samenhang/meer": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/verklaringen": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/weergave": ('require_client', 'actieve_userid'),
    "GET /v1/artefact-versies": ('require_client', 'actieve_userid'),
    "GET /v1/artefact-versies/{versie_id}": ('require_client', 'actieve_userid'),
    "GET /v1/auth/api-token/{token_id}/status": ('require_client', 'token_login_aan'),
    "GET /v1/auth/me": ('require_client',),
    "GET /v1/auth/setup-status": ('require_client',),
    "GET /v1/begrippen": ('require_client', 'actieve_userid'),
    "GET /v1/begrippen/conformiteit": ('require_client', 'actieve_userid'),
    "GET /v1/begrippen/export": ('require_client', 'actieve_userid'),
    "GET /v1/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "GET /v1/begrippen/{begrip_id}/revisies": ('require_client', 'actieve_userid'),
    "GET /v1/begrippen/{begrip_id}/voorstellen": ('require_client', 'actieve_userid'),
    "GET /v1/berichten": ('require_client', 'actieve_userid'),
    "GET /v1/berichten/ongelezen-aantal": ('require_client', 'actieve_userid'),
    "GET /v1/connectors": ('require_client',),
    "GET /v1/delegaties": ('require_client', 'actieve_userid'),
    "GET /v1/delegaties/{delegatie_id}": ('require_client', 'actieve_userid'),
    "GET /v1/gesprekken": ('require_client', 'actieve_userid'),
    "GET /v1/gesprekken/groep/{groep}": ('require_client', 'actieve_userid'),
    "GET /v1/gesprekken/telling": ('require_client', 'actieve_userid'),
    "GET /v1/gesprekken/{gesprek_id}": ('require_client', 'actieve_userid'),
    "GET /v1/gesprekken/{gesprek_id}/contextopbouw": ('require_client', 'actieve_userid'),
    "GET /v1/modelkeuzes": ('require_client',),
    "GET /v1/regels": ('require_client', 'actieve_userid'),
    "GET /v1/verbruik": ('require_client', 'actieve_userid'),
    "GET /v1/verbruik/controle": ('require_client',),
    "GET /v1/werkgebieden": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/export-schema": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/annotatie-werkvoorraad": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/audit": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen-runs/laatste": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/conformiteit": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/export": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/samenhang": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/kaart-runs/{run_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/revisies": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/voorstellen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/bepalingen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/bronnen-runs/laatste": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/bronnen-runs/{run_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/bronselectie": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/deelvragen/dekking": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/deelvragen/{deelvraag_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/dekking": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/elementen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/export": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/groepen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/herbeoordelingen": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/kandidaten": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/open-punten": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}/revisies": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/parameterwaarden": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/hierarchie": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/revisies": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/relaties": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/thema-voorstel": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/toestanden": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/verdieping": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/image/onderdelen/{soort}/{naam}": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/onderdelen": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/onderdelen/{onderdeel_id}": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/onderdelen/{onderdeel_id}/audit": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/onderdelen/{onderdeel_id}/versies/{nummer}": ('require_client', 'actieve_userid'),
    "GET /v1/werkplaats/stand": ('require_client', 'actieve_userid'),
    "PATCH /v1/admin/berichten/{bericht_id}/publicatie": ('require_admin',),
    "PATCH /v1/admin/users/{userid}": ('require_admin',),
    "PATCH /v1/auth/me/rondleiding": ('require_client', 'actieve_userid'),
    "PATCH /v1/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/delegaties/{delegatie_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/gesprekken/{gesprek_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/{koppeling_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/bronnen/{selectie_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/deelvragen/{deelvraag_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}": ('require_client', 'actieve_userid'),
    "PATCH /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/dragers/{drager_id}": ('require_client', 'actieve_userid'),
    "POST /v1/admin/api-tokens": ('require_admin',),
    "POST /v1/admin/berichten": ('require_admin',),
    "POST /v1/admin/budget/proef": ('require_admin',),
    "POST /v1/admin/feedback/markeer-gezien": ('require_admin', 'huidige_beheerder'),
    "POST /v1/admin/profiles/{name}/default": ('require_admin',),
    "POST /v1/admin/profiles/{name}/test": ('require_admin', 'rate_limited_admin_test'),
    "POST /v1/admin/registraties/goedkeuren": ('require_admin',),
    "POST /v1/admin/registraties/{aanvraag_id}/afwijzen": ('require_admin',),
    "POST /v1/admin/registraties/{aanvraag_id}/goedkeuren": ('require_admin',),
    "POST /v1/admin/users": ('require_admin',),
    "POST /v1/admin/users/{userid}/2fa/reset": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "POST /v1/admin/users/{userid}/reset-password": ('require_admin',),
    "POST /v1/admin/users/{userid}/verbruik/reset": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "POST /v1/admin/werkplaats/onderdelen/{onderdeel_id}/intrekken": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "POST /v1/annotatie/elementen": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/elementen/{element_id}/beslissing": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/impliciet": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/impliciet/{impliciet_id}/wis": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/lagen/batch": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/lagen/{laag_id}/beslissingen": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/lagen/{laag_id}/relatiebesluiten": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/lagen/{laag_id}/status": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/plaatsen": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/relaties": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/relaties/{relatie_id}/beslissing": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/relaties/{relatie_id}/wis": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/relaties/{relatie_id}/bevestig": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/weergave/export": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/weergave/verwijder": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/weergave/verwijder-impact": ('require_client', 'actieve_userid'),
    "GET /v1/annotatie/prullenbak/{prullenbak_id}": ('require_client', 'actieve_userid'),
    "POST /v1/annotatie/prullenbak/{prullenbak_id}/terugzetten": ('require_client', 'actieve_userid'),
    "POST /v1/admin/annotatie/prullenbak/legen": ('require_admin',),
    "POST /v1/annotatie/zoeken": ('require_client', 'actieve_userid'),
    "POST /v1/auth/2fa/activate": ('require_client',),
    "POST /v1/auth/2fa/begin": ('require_client',),
    "POST /v1/auth/2fa/disable": ('require_client',),
    "POST /v1/auth/2fa/herstelcodes": ('require_client',),
    "POST /v1/auth/api-token/verify": ('require_client', 'token_login_aan'),
    "POST /v1/auth/change-password": ('require_client',),
    "POST /v1/auth/registratie": ('require_client',),
    "POST /v1/auth/setup": ('require_client',),
    "POST /v1/auth/verify": ('require_client',),
    "POST /v1/begrippen/verifieer": ('require_client', 'actieve_userid'),
    "POST /v1/begrippen/{begrip_id}/accorderen": ('require_client', 'actieve_userid'),
    "POST /v1/begrippen/{begrip_id}/heropenen": ('require_client', 'actieve_userid'),
    "POST /v1/begrippen/{begrip_id}/nieuwe-betekenis": ('require_client', 'actieve_userid'),
    "POST /v1/begrippen/{begrip_id}/voorstellen/{voorstel_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/begrippen/{begrip_id}/voorstellen/{voorstel_id}/overnemen": ('require_client', 'actieve_userid'),
    "POST /v1/berichten/lees-alles": ('require_client', 'actieve_userid'),
    "POST /v1/delegaties": ('require_client', 'actieve_userid'),
    "POST /v1/feedback": ('require_client', 'actieve_userid', 'rate_limited_client'),
    "POST /v1/gesprekken": ('require_client', 'actieve_userid'),
    "POST /v1/gesprekken/archiveren": ('require_client', 'actieve_userid'),
    "POST /v1/gesprekken/verwijderen": ('require_client', 'actieve_userid'),
    "POST /v1/gesprekken/{gesprek_id}/berichten": ('require_client', 'actieve_userid'),
    "POST /v1/verbruik": ('require_client',),
    "POST /v1/werkgebieden": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen-runs": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/loopt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/mislukt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/vragen/{kandidaat_id}": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/gebruik": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/gebruik/{begrip_id}/bevestigen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/gebruik/{begrip_id}/opvolger": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/accorderen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/combineren": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/combineren-generiek": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/generiek-maken": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/heropenen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/kaart-runs": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/kaart-runs/{run_id}/loopt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/kaart-runs/{run_id}/mislukt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/beoordelen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/bevestigen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/{koppeling_id}/bevestigen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/koppelingen/{koppeling_id}/herkoppelen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/nieuwe-betekenis": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/voorstellen/{voorstel_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/voorstellen/{voorstel_id}/overnemen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronnen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronnen-runs": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronnen-runs/{run_id}/loopt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronnen-runs/{run_id}/mislukt": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronselectie/{deelvraag_id}/kandidaten/{kandidaat_id}": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronselectie/{deelvraag_id}/status": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/bronselectie/{deelvraag_id}/voorstellen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/deelvragen/samen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/deelvragen/voorstellen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/dekking/buiten-behandeling": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/groepen/akkoord": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/heropenen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/koppelen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/parkeren": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/open-punten": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}/besluit": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/open-punten/{punt_id}/omhangen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/parameterwaarden": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/accorderen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/dragers": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/heropenen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/voorbeelden/{nr}/oordeel": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/dragers": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/poort": ('require_client', 'actieve_userid'),
    "GET /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/voorbeelden": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/regels/{regel_id}/dragers/{drager_id}/verversen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/relaties": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/relaties/voorstellen/{voorstel_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/relaties/{relatie_id}/bevestigen": ('require_client', 'actieve_userid'),
    "POST /v1/werkgebieden/{werkgebied_id}/relaties/{relatie_id}/afwijzen": ('require_client', 'actieve_userid'),
    "POST /v1/werkplaats/onderdelen": ('require_client', 'actieve_userid'),
    "POST /v1/werkplaats/onderdelen/{onderdeel_id}/intrekken": ('require_client', 'actieve_userid'),
    "POST /v1/werkplaats/onderdelen/{onderdeel_id}/versies": ('require_client', 'actieve_userid'),
    "POST /v1/werkplaats/toets": ('require_client', 'actieve_userid'),
    "PUT /v1/admin/berichten/{bericht_id}": ('require_admin',),
    "PUT /v1/admin/budget": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/admin/budget/rollen/{rol}": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/admin/connectors/{naam}": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/admin/modelkeuzes/{sleutel}": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/admin/profiles/{name}": ('require_admin',),
    "PUT /v1/admin/werkplaats/beleid": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/admin/werkplaats/onderdelen/{onderdeel_id}/delen": ('require_admin', 'huidige_beheerder', 'beheerder_met_2fa'),
    "PUT /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/batches/{batch_id}": ('require_client', 'actieve_userid'),
    "PUT /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/uitkomst": ('require_client', 'actieve_userid'),
    "PUT /v1/werkgebieden/{werkgebied_id}/begrippen-runs/{run_id}/verdieping": ('require_client', 'actieve_userid'),
    "PUT /v1/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}/kaart-runs/{run_id}/uitkomst": ('require_client', 'actieve_userid'),
    "PUT /v1/werkgebieden/{werkgebied_id}/bronnen-runs/{run_id}/uitkomst": ('require_client', 'actieve_userid'),
    "PUT /v1/werkplaats/image": ('require_client',),
}


def _routes(routes, prefix=""):
    """Elke route met haar volle pad. FastAPI koppelt een router lui aan (`_IncludedRouter`), dus we lopen erin."""
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            yield from _routes(r.original_router.routes, prefix + getattr(r.include_context, "prefix", ""))
        elif isinstance(r, APIRoute):
            yield prefix + r.path, r


def _deps(dependant, acc: set[str]) -> set[str]:
    for sub in dependant.dependencies:
        acc.add(getattr(sub.call, "__name__", ""))
        _deps(sub, acc)
    return acc


def huidig() -> dict[str, tuple[str, ...]]:
    from app.main import app
    uit = {}
    for pad, route in _routes(app.routes):
        alle = _deps(route.dependant, set())
        for methode in sorted(route.methods):
            uit[f"{methode} {pad}"] = tuple(b for b in BEWAKERS if b in alle)
    return dict(sorted(uit.items()))


def test_de_tabel_klopt_met_de_routes():
    nu = huidig()
    assert len(nu) > 200, "de routes zijn niet gevonden: dan toetst deze test niets"
    nieuw = sorted(set(nu) - set(TABEL))
    weg = sorted(set(TABEL) - set(nu))
    anders = sorted(f"{k}: tabel {TABEL[k]} → nu {nu[k]}" for k in set(nu) & set(TABEL) if nu[k] != TABEL[k])
    assert not (nieuw or weg or anders), (
        f"de rechtentabel klopt niet (werk hem bewust bij):\n nieuw: {nieuw}\n weg: {weg}\n anders: {anders}")


def test_elke_route_buiten_gezondheid_vraagt_precies_een_token():
    nu = huidig()
    assert {k for k, b in nu.items() if not b} == PUBLIEK
    for k, b in nu.items():
        if k not in PUBLIEK:
            assert ("require_client" in b) != ("require_admin" in b), f"{k}: precies één van webapp- en admin-token"


def test_het_beheer_vraagt_het_admin_token_en_2fa_alleen_een_beheerder():
    for k, b in huidig().items():
        if k.split()[1].startswith("/v1/admin"):
            assert "require_admin" in b, f"{k}: beheer zonder admin-token"
        if "beheerder_met_2fa" in b:
            assert "huidige_beheerder" in b and "require_admin" in b, f"{k}: 2FA zonder beheerder"


def test_elk_domein_met_gebruikersgegevens_vraagt_een_actieve_gebruiker():
    for k, b in huidig().items():
        pad = k.split()[1]
        domein = pad.split("/")[2] if pad.startswith("/v1/") else ""
        if "require_admin" in b or k in PUBLIEK:
            continue
        if domein in GESCOPET:
            assert "actieve_userid" in b, f"{k}: gegevens van een gebruiker zonder actieve gebruiker"
        elif "actieve_userid" not in b:
            assert domein in ZONDER_GEBRUIKER, f"{k}: zonder actieve gebruiker; zet het domein met reden in ZONDER_GEBRUIKER"


if __name__ == "__main__":  # de tabel opnieuw uitschrijven, om het verschil te lezen
    for k, b in huidig().items():
        print(f"    {k!r}: {b!r},")
