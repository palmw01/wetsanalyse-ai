"""Compatibiliteitslaag — het run-register woont in `agent/runstore/`.

`Run`, `RunBestaatAl` en het `RunStore`-protocol staan in `agent.runstore`; de implementaties
ernaast. Deze module blijft bestaan omdat `RunRegister` een ingeburgerde naam is; hij wijst naar de
geheugen-implementatie.
"""
from __future__ import annotations

from .runstore import (  # noqa: F401 – re-export
    BEWAAR_NA_AFLOOP_S,
    MAX_EVENTS,
    VLUCHTIGE_TYPES,
    Run,
    RunBestaatAl,
    RunStore,
)
from .runstore.geheugen import GeheugenStore

# De oorspronkelijke naam; nieuw werk gebruikt GeheugenStore of het RunStore-protocol.
RunRegister = GeheugenStore
