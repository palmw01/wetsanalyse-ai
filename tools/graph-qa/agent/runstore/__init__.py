"""
Het run-register: een beurt is een object van de server, geen HTTP-request.

Waarom dit bestaat. De werkplek hing een lopende beurt aan de SSE-verbinding van één tabblad: van
gesprek wisselen, naar een andere pagina navigeren of herladen sloot die verbinding en daarmee de
beurt. Het werk stopte daar niet eens van – de LangGraph-nodes zijn synchroon, dus een lopende
LLM-call draait door in de executor – het resultaat werd alleen weggegooid. We betaalden de rekening
en gooiden het antwoord weg.

Hier wordt dat omgedraaid, naar het model van Claude: de **run** draait als achtergrondtaak en houdt
zijn eigen event-log bij; een client *kijkt* mee en kan opnieuw aanhaken. Losraken is dus geen
annuleren – stoppen is een aparte, expliciete handeling (`vraag_stop`).

Aannames die je moet kennen voordat je dit uitbreidt:

- **Eén proces, één replica.** graph-qa draait als één uvicorn-proces zonder `--workers`; het
  register leeft in het geheugen. Komt er ooit een tweede replica, dan moet dit naar een gedeelde
  store – een aanhaker die op de verkeerde instantie landt vindt de run anders niet.
- **Een herstart wist het register.** Dat is bewust: hervatten-vanaf-checkpoint vraagt async nodes en
  een resume-pad dat de agent vandaag niet heeft. Een client die met een onbekend run_id terugkomt
  hoort te horen dát de run weg is, niet eeuwig te blijven wachten.
- **Alleen de run-taak schrijft.** Een abonnee die aanhaakt mag nooit een schrijfactie uitlokken;
  daarmee is aanhaken per definitie veilig en idempotent.

Het contract staat hier, de implementaties ernaast. `GeheugenStore` is het oorspronkelijke gedrag en
de default; `PostgresStore` deelt de runs tussen replica's. Die splitsing is er omdat graph-qa op
Azure op `maxReplicas: 2` staat: landt een aanhaker op de andere replica, dan bestaat de run daar
niet en lijkt de beurt verdwenen.

De interface is **async**, ook waar de geheugenvariant niets hoeft af te wachten. Zonder dat kan een
store die met een database praat er niet achter, en dan is het protocol een fictie.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("graph_qa.runs")

# Hoeveel events er hoogstens in de log blijven staan. Ruim: een lange annotatiebeurt met veel
# narratie moet er integraal in passen.
MAX_EVENTS = 4000

# Hoe lang een afgeronde run nog opvraagbaar blijft. Lang genoeg dat je koffie kunt halen en de
# uitkomst alsnog ziet; kort genoeg dat het geheugen niet volloopt.
BEWAAR_NA_AFLOOP_S = 600.0

# Welke events bij het cappen mogen sneuvelen. Narratie is volume; betekenis is `doel`, `element`,
# `run`, `ontbrekend`, `sources`, `grounding`, `kandidaten`, `done` en `error` – die blijven staan,
# anders levert opnieuw aanhaken een verminkt resultaat op zonder dat iemand het merkt.
VLUCHTIGE_TYPES = frozenset({"token", "reason", "status"})


class RunBestaatAl(Exception):
    """Er loopt al een run voor dit gesprek. Draagt het actieve run_id, zodat de aanroeper kan
    aanhaken in plaats van een tweede run te starten.

    Dit is geen UI-nettigheid maar een gegevensbeschermer: `thread_id == conversation_id`, dus twee
    gelijktijdige lussen zouden door elkaar heen in dezelfde checkpointer-thread schrijven.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Er loopt al een run voor dit gesprek: {run_id}")
        self.run_id = run_id


@dataclass
class Run:
    """Eén beurt, met alles wat een late kijker nodig heeft om hem te begrijpen."""

    run_id: str
    conversation_id: str
    # Namens wie deze beurt draait. Zonder dit is een run een capability: wie het id kent, leest mee
    # en kan hem stoppen. De rest van het platform scopet alles per gebruiker (404 op andermans
    # document); dat hoort hier niet anders te zijn.
    user_id: str = ""
    # De vraag hoort bij de run, niet bij het tabblad: wie halverwege aanhaakt moet de user-bubbel
    # erboven kunnen tonen in plaats van tokens uit het niets.
    vraag: str = ""
    status: str = "loopt"          # loopt | klaar | gestopt | mislukt
    # Elk event draagt zijn EIGEN `seq`, toegekend bij het toevoegen. Eerder werd het volgnummer
    # afgeleid uit de positie in deze lijst (`index = cursor - weggevallen`), en dat klopt alleen als
    # precies de eerste N events verdwijnen. `_cap` snoeit echter selectief – het gooit narratie weg
    # waar die ook staat – dus schoof na het snoeien alles op: een `doel`-event dat seq 0 had kwam
    # terug als seq 1, en een client die opnieuw aanhaakte kreeg juist de betekenisvolle events
    # dubbel. Nu is een seq een identiteit, geen positie.
    events: list[dict[str, Any]] = field(default_factory=list)
    # Hoeveel vluchtige events er in totaal zijn weggegooid. Puur informatief (metriek/logging); het
    # gat dat een kijker moet tonen wordt berekend uit de seq-sprong, niet hieruit.
    weggevallen: int = 0
    # Hoeveel events deze run ooit produceerde = het seq-nummer dat het volgende krijgt.
    geproduceerd: int = 0
    gestart: float = field(default_factory=time.monotonic)
    eind_op: float | None = None
    stop_gevraagd: bool = False
    taak: asyncio.Task[None] | None = None
    _wakker: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def loopt(self) -> bool:
        return self.status == "loopt"

    @property
    def volgende_seq(self) -> int:
        """Het seq-nummer dat het eerstvolgende event krijgt (= aantal ooit geproduceerd)."""
        return self.geproduceerd

    def samenvatting(self) -> dict[str, Any]:
        """Wat een client krijgt als hij vraagt of er nog iets loopt."""
        return {
            "run_id": self.run_id,
            "conversation_id": self.conversation_id,
            "vraag": self.vraag,
            "status": self.status,
            "volgende_seq": self.volgende_seq,
            "weggevallen": self.weggevallen,
        }


@runtime_checkable
class RunStore(Protocol):
    """Waar lopende en recent afgeronde beurten leven."""

    async def get(self, run_id: str, *, user_id: str | None = None) -> Run | None:
        """De run, of niets als hij niet bestaat of niet van deze gebruiker is."""
        ...

    async def actief_voor(self, conversation_id: str, *, user_id: str | None = None) -> Run | None:
        """De lopende run van dit gesprek, als die er is."""
        ...

    async def start(
        self,
        *,
        conversation_id: str,
        vraag: str,
        maak_stroom: Callable[[Run], AsyncIterator[dict[str, Any]]],
        user_id: str = "",
    ) -> Run:
        """Registreer een run en zet hem als achtergrondtaak weg. `RunBestaatAl` als er al één loopt."""
        ...

    async def vraag_stop(self, run: Run) -> None:
        """Vraag om te stoppen. Een verzoek, geen annulering: de run stopt op een nodegrens."""
        ...

    async def stop_gevraagd(self, run: Run) -> bool:
        """Is er om een stop gevraagd? Dit is wat de graaf per node leest.

        Apart van `vraag_stop` omdat het verzoek op een ándere replica kan binnenkomen dan waar de
        run draait; een gedeelde store leest dat hier op.
        """
        ...

    def volg(self, run: Run, vanaf: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Lever de events vanaf `vanaf` en volg daarna live mee. Losraken laat de run ongemoeid."""
        ...
