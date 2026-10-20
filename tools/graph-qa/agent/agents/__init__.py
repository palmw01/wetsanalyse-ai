"""De agents onder de supervisor (spoor F, F3c; ADR-005): deelvragen en begrippen, en de
werkgebied-taak van de annotatie-agent.

Elke agent is een Python-module met dezelfde vorm:

- een vaste lijst `Taak` (een `StrEnum`);
- per agent één Pydantic-`Invoer` (taak + id's) en de gedeelde `Uitkomst`;
- `async def voer_uit(invoer, ctx) -> Uitkomst`: een keten van gewone functies.

Een model komt alleen in een stap die een oordeel of formulering vraagt, en dan als één `strict` tool met
validatie in code – zoals de JAS-classifier. Er is geen vrije tool-lus: zoeken, koppelen, dekking,
rangschikken en opslaan is code. Wat een taak oplevert, landt bij de api als **voorstel** of
**kandidaat**: Lex stelt voor, de analist beslist.

De tekst van een uitkomst komt uit code, niet van een model. De node `agent_taak`
(`nodes/agent_taak.py`) zet de uitkomst om in events; de beurt-driver legt het bericht vast met het
artefact en de bevestiging.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "bevestiging", "geweigerd", "fout"]


class Uitkomst(BaseModel):
    """Wat één taak opleverde. `tekst` is de samenvatting voor het gesprek, uit code.

    - `ok`: gedaan; `voorstellen` noemt de id's van wat er bij de api als voorstel of kandidaat landde.
    - `bevestiging`: duur werk, nog niet gestart; `bevestiging` draagt wat de werkplek als knop toont.
    - `geweigerd`: de taak past niet, of het object ontbreekt; `reden` zegt wat Lex nodig heeft.
    - `fout`: een storing (api, graaf, model); `reden` is een vaste tekst, de oorzaak staat in het log.
    """

    taak: str
    status: Status = "ok"
    reden: str = ""
    voorstellen: list[str] = Field(default_factory=list)
    # In de vorm van `api/app/gesprek_contracts.Artefact`: {soort, titel, ref}.
    artefact: dict[str, Any] | None = None
    # In de vorm van `api/app/gesprek_contracts.Bevestiging`.
    bevestiging: dict[str, Any] | None = None
    tekst: str = ""
    # Per stap wat er gebeurde: duur, aantal, volledig, en of er een model aan te pas kwam.
    meting: dict[str, Any] = Field(default_factory=dict)

    @property
    def gesprekstekst(self) -> str:
        """Wat Lex zegt: de samenvatting, en anders de reden."""
        return self.tekst or self.reden


@dataclass
class Context:
    """Wat een agent nodig heeft buiten zijn invoer. De api-client hoort bij de event loop van de beurt
    en wordt daar gemaakt (`nodes/agent_taak.py`); tests geven nepversies mee.

    `llm` is het model van de beurt: zijn meter telt mee in het verbruik dat de beurt-driver boekt.
    Taken die een eigen run bij de api hebben (de kaartacties, de verdieping) boeken zelf, zoals hun
    endpoints dat al deden."""

    api: Any
    settings: Any
    user_id: str = ""
    run_id: str = ""
    gesprek_id: str = ""
    graph: Any = None
    llm: Any = None
    # Een statusregel naar het gesprek ("Lex · …"); de node maakt er een `status`-event van.
    melding: Callable[[str], None] = lambda _bericht: None
    gestopt: Callable[[], bool] = lambda: False
    # Voor tests: een eigen taalprovider (de begrippenketen), een eigen model per run, een budgetpoort.
    provider: Any = None
    maak_llm: Callable[[Any], Any] | None = None
    budget_toegestaan: Callable[[], Awaitable[bool]] | None = None
    # Wat de node verder meegeeft (de getypte vraag, voor het herkennen van een term).
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def run(self) -> Any:
        """Een run-achtig object voor de bestaande stromen (`run_id`, `stop_gevraagd`)."""
        ctx = self

        class _Run:
            run_id = ctx.run_id

            @property
            def stop_gevraagd(self) -> bool:
                return ctx.gestopt()

        return _Run()


def geweigerd(taak: str, reden: str) -> Uitkomst:
    return Uitkomst(taak=taak, status="geweigerd", reden=reden)


def fout(taak: str, reden: str) -> Uitkomst:
    return Uitkomst(taak=taak, status="fout", reden=reden)
