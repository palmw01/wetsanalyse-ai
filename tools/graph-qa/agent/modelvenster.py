"""Het contextvenster per model (plan contextweergave, *Telwijze* 6).

Lex praat met het model via Azure AI Foundry, en daar is het venster niet op te vragen: de Models API ontbreekt, en
graph-qa schaalt naar nul, dus een cache in het proces is vaak leeg. Vandaar een klein register, per model-id.

Een model dat hier niet staat, krijgt `STANDAARD`: de kleinste gangbare waarde, zodat de contextweergave het aandeel
eerder te hoog dan te laag toont. `tests/test_contextopbouw.py` eist een vermelding voor elk model dat in de config of
de uitrol kan staan, zodat een nieuw model geen stille fout wordt.

Het venster is een weergavegetal: Lex begrenst zijn verzoeken er niet mee (`berichten._historievenster` doet dat, en
het venster van Lex komt nooit in de buurt van de grens, ADR-015).
"""
from __future__ import annotations

#: Tokens per model-id, volgens de documentatie van de provider.
VENSTERS: dict[str, int] = {
    "claude-sonnet-4-6": 1_000_000,
}

STANDAARD = 200_000


def modelvenster(model: str) -> int:
    return VENSTERS.get(model or "", STANDAARD)
