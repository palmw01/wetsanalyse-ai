"""
Client naar de wetsanalyse-API: hier legt graph-qa de uitkomst van een beurt vast.

Waarom deze richting bestaat. Tot nu toe schreef de **browser** het resultaat weg, ná afloop van de
stream. Dat betekende: wie zijn tabblad sloot voordat de agent klaar was, verloor het werk – ook als
de agent zijn beurt keurig had afgemaakt. Bij een annotatie is dat 60 tot 90 seconden werk. Met deze
client hoeft er aan het eind niemand meer te kijken.

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

# Ruim genoeg voor een PUT met tientallen elementen, krap genoeg dat een hangende api de run niet
# eindeloos ophoudt.
TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)


#: Velden waar de agent en de api een ándere opvatting van "geen waarde" hebben: de agent gebruikt de
#: lege string (`aandacht: str = ""`), de api een enum met `None` (`Aandacht | None`). Zo'n lege
#: string is voor de api geen geldige waarde maar een 422 – en omdat de PUT alles-of-niets is, sleurt
#: één zo'n veld de complete annotatie mee. Dat is op dev gebeurd: agent klaar en gegrond, jurist een
#: leeg document.
#:
#: De vertaling hoort hier, op de grens, en niet bij elke aanroeper: dit is de enige plek waar de
#: agent-representatie het contract van een ánder proces binnengaat. `tests/test_contract_drift.py`
#: bewaakt dat er geen vierde veld bijkomt zonder dat iemand het merkt.
def _leeg_is_niets(waarde: dict[str, Any], veld: str = "aandacht") -> dict[str, Any]:
    return waarde if waarde.get(veld) else {**waarde, veld: None}


def naar_contract(element: dict[str, Any]) -> dict[str, Any]:
    """Eén element in de vorm die `ElementInvoer` accepteert. Zie `_leeg_is_niets`."""
    uit = _leeg_is_niets(element)
    rondes = uit.get("critic_rondes")
    if rondes:
        uit = {**uit, "critic_rondes": [_leeg_is_niets(r) for r in rondes]}
    return uit


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
        #: Hoeveel markeringen de api liet vallen bij de laatste `zet_laag_elementen`. Zie daar.
        self.verworpen = 0
        #: De leden die de api als al geannoteerd en ongewijzigd herkende (en dus niet aanvulde).
        self.hergebruikt: list[str] = []
        self._laatste_headers: dict[str, str] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, pad: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._verstuur("POST", pad, payload)

    async def _put(self, pad: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._verstuur("PUT", pad, payload)

    async def _verstuur(self, methode: str, pad: str, payload: dict[str, Any]) -> dict[str, Any]:
        antwoord = await self._client.request(
            methode, f"{self._basis}{pad}", json=payload, headers=self._headers,
        )
        self._laatste_headers = {k.lower(): v for k, v in antwoord.headers.items()}
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

    async def zet_laag_elementen(
        self,
        *,
        bwb_id: str,
        artikel: str,
        citeertitel: str,
        elementen: list[dict[str, Any]],
        run: dict[str, Any] | None,
        leden: list[dict[str, Any]],
        bron_hash: str,
        modus: str = "auto",
    ) -> dict[str, Any]:
        """De uitkomst van deze beurt in de GEDEELDE laag van het artikel. Geeft de laag terug.

        Eén PUT, en de api maakt de laag aan als hij er nog niet is. Er is dus geen losse stap meer
        die een leeg document kan achterlaten als de tweede mislukt. De merge-semantiek (op id of
        tekst+lid, bevriezen wat de jurist beoordeelde, verouderen bij een gewijzigd lid, nooit
        intrekken) zit aan de api-kant, niet hier.

        `leden` is per geannoteerd lid de hash en de IRI; daaraan ziet de api welk lid veranderde.
        In `modus="auto"` negeert hij voorstellen voor een lid dat al geannoteerd en ongewijzigd is
        – die staan dan in `self.hergebruikt`.
        """
        self.verworpen = 0
        self.hergebruikt = []
        payload: dict[str, Any] = {
            "citeertitel": citeertitel,
            "elementen": [naar_contract(e) for e in elementen],
            "ronde": 0,
            "leden": leden,
            "bron_hash": bron_hash,
            "modus": modus,
        }
        if run:
            # `tijd` is bij ons optioneel en bij de api verplicht mét default. Hem als `None`
            # meesturen is dus géén "laat maar leeg" maar een validatiefout; weglaten wél.
            payload["run"] = {k: v for k, v in run.items() if not (k == "tijd" and v is None)}
        pad = f"/v1/annotatie/lagen/{quote(bwb_id, safe='')}/{quote(artikel, safe='')}/elementen"
        uit = await self._put(pad, payload)
        # De api laat een element dat zijn schema niet haalt vallen in plaats van de hele ronde te
        # weigeren – beter, maar daarmee wordt een lúíde fout een stille. Daarom telt hij ze in
        # `X-Verworpen` en zeggen wij het tegen de jurist.
        self.verworpen = int(self._laatste_headers.get("x-verworpen", 0) or 0)
        self.hergebruikt = [
            lid for lid in (self._laatste_headers.get("x-hergebruikt-leden") or "").split(",") if lid
        ]
        return uit

    async def hergebruik(
        self,
        *,
        bwb_id: str,
        artikel: str,
        citeertitel: str,
        leden: list[dict[str, Any]],
        run: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Leg vast dat deze beurt de laag hergebruikte in plaats van opnieuw te annoteren.

        Verandert niets aan inhoud of oordeel – de api schrijft een auditregel en een run met
        `modus="hergebruik"`, zodat het spoor laat zien dát en wanneer er is hergebruikt.
        """
        payload: dict[str, Any] = {"citeertitel": citeertitel, "leden": leden, "ankers": []}
        if run:
            payload["run"] = {k: v for k, v in run.items() if not (k == "tijd" and v is None)}
        pad = f"/v1/annotatie/lagen/{quote(bwb_id, safe='')}/{quote(artikel, safe='')}/hergebruik"
        return await self._post(pad, payload)

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
