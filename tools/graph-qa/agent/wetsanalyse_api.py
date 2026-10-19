"""
Client naar de wetsanalyse-API: hier legt graph-qa de uitkomst van een beurt vast.

De agent schrijft zelf weg, niet de browser: een beurt van 60 tot 90 seconden mag niet verloren gaan
omdat iemand zijn tabblad sloot. Aan het eind hoeft er dus niemand meer te kijken.

Drie dingen om te weten:

- **Namens wie.** De API kent twee lagen: een client-bearer (wie ben je, `WETSANALYSE_API_TOKENS`) en
  de header `X-User-Id` (namens wie handel je). graph-qa krijgt een eigen client-id; de userid komt
  per beurt mee in het verzoek. Daarmee is dit token een schrijfprimitief op elk gebruikersgesprek —
  vandaar dat graph-qa intern-only blijft en zijn eigen endpoint een token móét hebben
  (`Settings.require_api`).
- **Idempotent waar het telt.** Het `run_id` reist mee met de chatbeurt; de API weigert een tweede
  bericht met datzelfde id. Zo levert opnieuw proberen geen dubbel antwoord op.
- **Falen mag de beurt niet opeten.** Kan er niet geschreven worden, dan is dat een fout in het log
  en een `error`-event richting de werkplek – nooit een stilzwijgend verlies.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings

logger = logging.getLogger("graph_qa.api")

# Ruim genoeg voor een batch met tientallen elementen, krap genoeg dat een hangende api de run niet
# eindeloos ophoudt.
TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)
# Zelfde grens als de BFF bij het starten van begrippen (`MANIFEST_TIMEOUT_MS`).
MANIFEST_TIMEOUT = httpx.Timeout(connect=5.0, read=90.0, write=30.0, pool=5.0)


#: De agent gebruikt de lege string voor "geen aandacht" (`aandacht: str = ""`), de api `None`. De
#: vertaling hoort hier, op de grens, en niet bij elke aanroeper: dit is de enige plek waar de
#: agent-representatie het contract van een ánder proces binnengaat. `tests/test_contract_drift.py`
#: bewaakt dat er geen veld bijkomt zonder dat iemand het merkt.
def _leeg_is_niets(waarde: dict[str, Any], veld: str = "aandacht") -> dict[str, Any]:
    return waarde if waarde.get(veld) else {**waarde, veld: None}


def naar_contract(element: dict[str, Any]) -> dict[str, Any]:
    """Eén element in de vorm die de api verwacht. Zie `_leeg_is_niets`."""
    return _leeg_is_niets(element)


class WetsanalyseApiFout(Exception):
    """De uitkomst kon niet worden vastgelegd. Expliciet, want stil verliezen is het ergste."""

    def __init__(self, melding: str, status: int = 0, reden: str = "") -> None:
        super().__init__(melding)
        self.status = status
        #: De reden die de api zelf gaf ("Heropen de laag …"), zodat de jurist een eerlijke melding
        #: krijgt in plaats van "probeer opnieuw".
        self.reden = reden


def api_reden(antwoord: httpx.Response) -> str:
    """De foutreden uit een api-antwoord: een korte servertekst of een foutcode, nooit de body.

    `detail` is bij deze api een vaste melding ("Heropen de laag …") of een object met `fout`;
    alles daarbuiten (een lange tekst, een lijst validatiefouten met invoer erin) laten we weg."""
    try:
        detail = antwoord.json().get("detail")
    except (ValueError, AttributeError):
        return ""
    if isinstance(detail, str) and len(detail) <= 200:
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("fout"), str):
        return detail["fout"][:80]
    return ""


class GesprekVerdwenen(WetsanalyseApiFout):
    """Het gesprek bestaat niet meer – meestal omdat de jurist het verwijderde terwijl de beurt liep.

    Geen storing, maar een gevolg van een bewuste handeling. De api weigert terecht: erin schrijven
    zou een verwijderd gesprek half laten herrijzen. De aanroeper hoort hier stil te eindigen in
    plaats van alarm te slaan over iets wat de gebruiker zelf deed."""


class WetsanalyseApi:
    """Dunne HTTP-client. Eén instantie per beurt; sluit hem met `aclose()`."""

    def __init__(self, settings: Settings, user_id: str) -> None:
        self._basis = settings.wetsanalyse_api_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {settings.wetsanalyse_api_token}",
            # Namens wie we schrijven. De api vertrouwt deze header van een geldige client.
            "X-User-Id": user_id,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(timeout=TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, pad: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._verstuur("POST", pad, payload)

    async def _verstuur(self, methode: str, pad: str, payload: dict[str, Any]) -> dict[str, Any]:
        antwoord = await self._client.request(
            methode, f"{self._basis}{pad}", json=payload, headers=self._headers,
        )
        if antwoord.status_code == 404 and "/gesprekken/" in pad:
            raise GesprekVerdwenen(f"{methode} {pad} → 404", 404)
        if antwoord.status_code >= 400:
            # De ruwe body kan gebruikersinhoud bevatten; log de status, het pad en alleen de reden
            # die de api zelf formuleert. Zonder die reden was een 409 achteraf niet te duiden.
            reden = api_reden(antwoord)
            logger.error(
                "api-schrijffout",
                extra={"categorie": "technisch", "http_status": antwoord.status_code, "http_path": pad,
                       "api_reden": reden},
            )
            raise WetsanalyseApiFout(f"{methode} {pad} → {antwoord.status_code}", antwoord.status_code, reden)
        return antwoord.json() if antwoord.content else {}

    # -- annotatie-domein ------------------------------------------------------------------------

    async def zet_bronnode_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = {**payload, "elementen": [naar_contract(e) for e in payload.get("elementen", [])]}
        return await self._post("/v1/annotatie/lagen/batch", data)

    # -- begrippen: voorstellen van Lex (spoor D, levering 3a) --------------------------------------

    def _run_pad(self, werkgebied_id: str, run_id: str) -> str:
        return f"/v1/werkgebieden/{quote(werkgebied_id, safe='')}/begrippen-runs/{quote(run_id, safe='')}"

    def _werkgebied_pad(self, werkgebied_id: str) -> str:
        return f"/v1/werkgebieden/{quote(werkgebied_id, safe='')}"

    async def _haal(self, pad: str, **params: str) -> dict[str, Any]:
        antwoord = await self._client.get(f"{self._basis}{pad}", params=params or None, headers=self._headers)
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"GET {pad} → {antwoord.status_code}", antwoord.status_code, api_reden(antwoord))
        return antwoord.json()

    async def haal_werkgebied(self, werkgebied_id: str) -> dict[str, Any]:
        return await self._haal(self._werkgebied_pad(werkgebied_id))

    async def start_begrippen_run(self, werkgebied_id: str) -> dict[str, Any]:
        """Manifest vastleggen en de run maken, of de bestaande op dezelfde stand (`nieuw: false`).

        Het manifest vraagt per regeling de bronboom uit de graaf; vandaar de ruimere leestijd."""
        antwoord = await self._client.post(f"{self._basis}{self._werkgebied_pad(werkgebied_id)}/begrippen-runs",
                                           json={}, headers=self._headers, timeout=MANIFEST_TIMEOUT)
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"POST begrippen-runs → {antwoord.status_code}", antwoord.status_code,
                                     api_reden(antwoord))
        return antwoord.json()

    async def haal_annotatie_werkvoorraad(self, werkgebied_id: str) -> dict[str, Any]:
        """Wat Lex in het werkgebied nog moet annoteren (fase B). De api vraagt per regeling de
        bronboom uit de graaf; vandaar de ruimere leestijd."""
        pad = f"{self._werkgebied_pad(werkgebied_id)}/annotatie-werkvoorraad"
        antwoord = await self._client.get(f"{self._basis}{pad}", headers=self._headers, timeout=MANIFEST_TIMEOUT)
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"GET {pad} → {antwoord.status_code}", antwoord.status_code, api_reden(antwoord))
        return antwoord.json()

    # -- bronnen vinden met Lex (spoor D, fase A) -----------------------------------------------------

    def _bronnen_pad(self, werkgebied_id: str, run_id: str) -> str:
        return f"{self._werkgebied_pad(werkgebied_id)}/bronnen-runs/{quote(run_id, safe='')}"

    async def start_bronnen_run(self, werkgebied_id: str) -> dict[str, Any]:
        return await self._post(f"{self._werkgebied_pad(werkgebied_id)}/bronnen-runs", {})

    async def haal_bronnen_run(self, werkgebied_id: str, run_id: str) -> dict[str, Any]:
        """De run met zijn invoer: de selectie zoals de api hem vastlegde."""
        return await self._haal(self._bronnen_pad(werkgebied_id, run_id), invoer="true")

    async def meld_bronnen_loopt(self, werkgebied_id: str, run_id: str) -> dict[str, Any]:
        return await self._post(f"{self._bronnen_pad(werkgebied_id, run_id)}/loopt", {})

    async def zet_bronnen_uitkomst(self, werkgebied_id: str, run_id: str, uitkomst: dict[str, Any]) -> dict[str, Any]:
        return await self._verstuur("PUT", f"{self._bronnen_pad(werkgebied_id, run_id)}/uitkomst", uitkomst)

    async def meld_bronnen_mislukt(self, werkgebied_id: str, run_id: str, reden: str) -> dict[str, Any]:
        return await self._post(f"{self._bronnen_pad(werkgebied_id, run_id)}/mislukt", {"reden": reden[:2000]})

    async def haal_kandidaten(self, werkgebied_id: str) -> dict[str, Any]:
        return await self._haal(f"{self._werkgebied_pad(werkgebied_id)}/kandidaten")

    async def haal_groepen(self, werkgebied_id: str) -> dict[str, Any]:
        """De betekenisgroepen van de laatste klare run, met hun besluiten."""
        return await self._haal(f"{self._werkgebied_pad(werkgebied_id)}/groepen")

    async def haal_begrippen_run(self, werkgebied_id: str, run_id: str) -> dict[str, Any]:
        """De run met zijn manifest: de vaste invoer die de api heeft vastgelegd."""
        antwoord = await self._client.get(f"{self._basis}{self._run_pad(werkgebied_id, run_id)}",
                                          params={"manifest": "true"}, headers=self._headers)
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"GET begrippen-run → {antwoord.status_code}", antwoord.status_code,
                                     api_reden(antwoord))
        return antwoord.json()

    async def meld_begrippen_loopt(self, werkgebied_id: str, run_id: str) -> dict[str, Any]:
        return await self._post(f"{self._run_pad(werkgebied_id, run_id)}/loopt", {})

    async def zet_begrippen_uitkomst(self, werkgebied_id: str, run_id: str, uitkomst: dict[str, Any]) -> dict[str, Any]:
        """Idempotent aan de api-kant: dezelfde uitkomst nog eens geeft de run terug."""
        return await self._verstuur("PUT", f"{self._run_pad(werkgebied_id, run_id)}/uitkomst", uitkomst)

    async def meld_begrippen_mislukt(self, werkgebied_id: str, run_id: str, reden: str) -> dict[str, Any]:
        return await self._post(f"{self._run_pad(werkgebied_id, run_id)}/mislukt", {"reden": reden[:2000]})

    # -- Lex naast de kaart: voorstellen per veld op één begrip (fase E) ---------------------------

    def _kaart_pad(self, werkgebied_id: str, begrip_id: str, run_id: str) -> str:
        return (f"{self._werkgebied_pad(werkgebied_id)}/begrippen/{quote(begrip_id, safe='')}"
                f"/kaart-runs/{quote(run_id, safe='')}")

    async def haal_kaartrun(self, werkgebied_id: str, begrip_id: str, run_id: str) -> dict[str, Any]:
        """De run met zijn invoer: het begrip op zijn revisie, de passages en het manifest."""
        antwoord = await self._client.get(f"{self._basis}{self._kaart_pad(werkgebied_id, begrip_id, run_id)}",
                                          params={"invoer": "true"}, headers=self._headers, timeout=MANIFEST_TIMEOUT)
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"GET kaart-run → {antwoord.status_code}", antwoord.status_code,
                                     api_reden(antwoord))
        return antwoord.json()

    async def meld_kaart_loopt(self, werkgebied_id: str, begrip_id: str, run_id: str) -> dict[str, Any]:
        return await self._post(f"{self._kaart_pad(werkgebied_id, begrip_id, run_id)}/loopt", {})

    async def zet_kaart_uitkomst(self, werkgebied_id: str, begrip_id: str, run_id: str,
                                 uitkomst: dict[str, Any]) -> dict[str, Any]:
        """De api toetst de garanties opnieuw (422 bij een gebroken) en bewaart de voorstellen."""
        return await self._verstuur("PUT", f"{self._kaart_pad(werkgebied_id, begrip_id, run_id)}/uitkomst", uitkomst)

    async def meld_kaart_mislukt(self, werkgebied_id: str, begrip_id: str, run_id: str, reden: str) -> dict[str, Any]:
        return await self._post(f"{self._kaart_pad(werkgebied_id, begrip_id, run_id)}/mislukt", {"reden": reden[:2000]})

    async def start_kaart_run(self, werkgebied_id: str, begrip_id: str, actie: str,
                              ander_begrip_id: str | None = None) -> dict[str, Any]:
        """Een kaartactie vanuit het gesprek (fase F4), zoals de knop op de kaart: de api legt de invoer vast,
        of geeft de lopende run (of een klare met open voorstellen) terug (`nieuw: false`). Het manifest
        vraagt de bronboom uit de graaf; vandaar de ruimere leestijd."""
        pad = f"{self._werkgebied_pad(werkgebied_id)}/begrippen/{quote(begrip_id, safe='')}/kaart-runs"
        antwoord = await self._client.post(
            f"{self._basis}{pad}", headers=self._headers, timeout=MANIFEST_TIMEOUT,
            json={"actie": actie, **({"ander_begrip_id": ander_begrip_id} if ander_begrip_id else {})})
        if antwoord.status_code >= 400:
            raise WetsanalyseApiFout(f"POST kaart-runs → {antwoord.status_code}", antwoord.status_code,
                                     api_reden(antwoord))
        return antwoord.json()

    async def haal_kaartrun_stand(self, werkgebied_id: str, begrip_id: str, run_id: str) -> dict[str, Any]:
        """De run zonder invoer: alleen status en melding, om op een lopende run te wachten."""
        return await self._haal(self._kaart_pad(werkgebied_id, begrip_id, run_id))

    # -- begrippen over werkgebieden heen (fase F4) ------------------------------------------------

    async def zoek_begrippen(self, q: str, eerst: str = "", limit: int = 20) -> dict[str, Any]:
        return await self._haal("/v1/begrippen", q=q, limit=str(limit), **({"eerst": eerst} if eerst else {}))

    # -- de verdieping: het model op twijfelparen en kaarten (fase C) ------------------------------

    async def haal_verdieping(self, werkgebied_id: str) -> dict[str, Any]:
        """Werkvoorraad, klare batches, schatting en budget voor de laatste klare run."""
        return await self._haal(f"{self._werkgebied_pad(werkgebied_id)}/verdieping")

    async def zet_begrippen_batch(self, werkgebied_id: str, run_id: str, batch_id: str,
                                  batch: dict[str, Any]) -> dict[str, Any]:
        """Idempotent aan de api-kant; de api toetst de garanties opnieuw (422 bij een gebroken)."""
        return await self._verstuur("PUT", f"{self._run_pad(werkgebied_id, run_id)}/batches/{quote(batch_id, safe='')}",
                                    batch)

    async def zet_verdieping(self, werkgebied_id: str, run_id: str, verdieping: dict[str, Any]) -> dict[str, Any]:
        return await self._verstuur("PUT", f"{self._run_pad(werkgebied_id, run_id)}/verdieping", verdieping)

    # -- gesprekken-domein -----------------------------------------------------------------------

    async def voeg_bericht_toe(self, gesprek_id: str, bericht: dict[str, Any]) -> dict[str, Any]:
        """De assistent-beurt in de chatgeschiedenis. `run_id` in de payload maakt dit idempotent."""
        return await self._post(f"/v1/gesprekken/{gesprek_id}/berichten", bericht)

    async def boek_verbruik(
        self, verbruik: dict[str, int], *, model: str = "", gesprek_id: str = "", run_id: str = "",
    ) -> dict[str, Any]:
        """Meld het tokenverbruik van deze beurt. Idempotent op `run_id` aan de api-kant.

        De api is de boekhouder, niet graph-qa: hier draaien meerdere replica's met eigen
        procesgeheugen, dus een teller die hier zou leven telt per replica.
        """
        return await self._post("/v1/verbruik", {
            "bron": "agent",
            "model": model,
            "invoer": verbruik.get("invoer", 0),
            "uitvoer": verbruik.get("uitvoer", 0),
            "cache_lees": verbruik.get("cache_lees", 0),
            "cache_schrijf": verbruik.get("cache_schrijf", 0),
            "gesprek_id": gesprek_id,
            "run_id": run_id,
        })

    async def budget_toegestaan(self) -> tuple[bool, dict[str, Any]]:
        """Mag deze gebruiker een beurt starten? Geeft (toegestaan, stand).

        **Fail-open**: kan de api niet antwoorden, dan gaat de beurt door. Een haperende
        boekhouding mag het werk niet stilleggen; het verbruik wordt daarna gewoon geboekt.
        """
        try:
            antwoord = await self._client.get(
                f"{self._basis}/v1/verbruik/controle", headers=self._headers,
            )
            antwoord.raise_for_status()
            data = antwoord.json()
        except Exception:  # noqa: BLE001 – zie de fail-open hierboven
            logger.warning("budgetcontrole niet beschikbaar; beurt gaat door", exc_info=True)
            return True, {}
        return bool(data.get("toegestaan", True)), data.get("stand") or {}
