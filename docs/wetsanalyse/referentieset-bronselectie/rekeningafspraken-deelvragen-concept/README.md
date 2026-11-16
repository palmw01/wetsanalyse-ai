# Referentieset bronselectie – Rekeningafspraken, per deelvraag

Soort: *meting* (referentie) · Status: **concept, ontwikkelset, niet geadjudiceerd** · Hoort bij: bevinding B-2 van de
E2E-test Rekeningafspraken (16 nov 2026) en [het plan centrale agent na A6](../../../architectuur/plan-centrale-agent-na-a6.md),
PR E

**Een ontwikkelset, geen bewijs.** De verwachte bepalingen komen uit het
[E2E-verslag](../../../acceptatie/verslag-e2e-rekeningafspraak-2026-11-16.md). Daar noemden de agent-jurist en de
agent-gegevensspecialist ze zelf en toetsten ze letterlijk: Iw 1990 art. 7a lid 1, Awir art. 25 lid 1, Awb art. 4:89
lid 1, Uitv.reg. Iw 1990 art. 40ca lid 1 en Uitv.reg. Awir art. 6 lid 1. De twee vlaggen van PR E
(`Zoekprofiel.verwijzingen` en `onderscheidend`) zijn op die bevinding ontworpen. Winst op deze set zegt dus niets
over een ander werkgebied.

De deelvragen staan in de woorden van het verslag, niet letterlijk zoals ze in het werkgebied stonden. Alleen
deelvraag 1 en 2 hebben verwachte bepalingen: in de E2E-test is alleen deelvraag 1 afgewerkt, en deelvraag 2 volgt uit
de praktijkvoorbeelden. De andere deelvragen staan erin, omdat `onderscheidend` alle deelvragen van het werkgebied leest.

**Nog niet te meten.**
- Er is nog geen `graafantwoorden.json`. Een opname vraagt `GRAPHDB_MCP_URL` en `GRAPHDB_TOKEN`, en die staan niet in
  deze repo.
- De vlaggen stellen nieuwe vragen aan de graaf. De opnames van de bestaande sets missen die vragen, en de eval meldt dat
  als een onvolledige methode.
- Het bewijs moet komen van een **blinde set uit een ander werkgebied**, opgesteld voordat de meting draait.

Meten, vanuit `tools/graph-qa`:

```bash
uv run python -m eval.bronselectie_eval --intake --b2 --set rekeningafspraken-deelvragen-concept --opnemen  # live, één keer
uv run python -m eval.bronselectie_eval --intake --b2 --set rekeningafspraken-deelvragen-concept            # offline
```

Met `--b2` staan de routes `met verwijzingen` en `met onderscheidend` naast de standaard in het rapport. Voor een bestaande set vult `--aanvullen --b2` de opname aan met alleen de nieuwe vragen.
