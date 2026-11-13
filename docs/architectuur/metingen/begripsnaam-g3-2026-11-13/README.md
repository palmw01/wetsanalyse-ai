# G3: twee toetsen op de naam van een begrip, zonder model (13 nov 2026)

Plan `docs/architectuur/plan-methodes-scheiden.md`, deel 2, stap G3. De begrippenketen krijgt twee signalen op de naam
van een begrip: `NAAM_MET_ONTKENNING` en `NAAM_MET_AFKORTING` (`agent/begrippen_pipeline/toetsen.py`), niet bij een
letterlijke definitie. Een signaal maakt een kaart geel; het weigert niets.

**Hoe gemeten.** `meting.py` (in deze map): per referentieset (`v1`, `heldout-v1`, `heldout-v2` in
`docs/wetsanalyse/referentieset-begrippen/`) de keten en per groep de kaart zonder model
(`verdieping.kaartopdrachten`), daarna de aandachtspunten tellen. Geen model, geen graaf. Gedraaid in
`tools/graph-qa` met `uv run python ../../docs/architectuur/metingen/begripsnaam-g3-2026-11-13/meting.py`.

**Uitkomst** (`uitkomst.json`):

- v1: 6 kaarten, 5 geel; geen nieuw signaal.
- heldout-v1: 4 kaarten, 0 geel; geen nieuw signaal.
- heldout-v2: 4 kaarten, 2 geel; geen nieuw signaal.

**Oordeel.** De drempel uit het plan ("geen signaal op een begrip dat de referentie goed noemt, behalve waar de naam
werkelijk een ontkenning of afkorting draagt") is gehaald: geen enkele kaart krijgt een nieuw signaal, en het aantal gele
kaarten is gelijk aan vóór G3 (de nieuwe codes zijn de enige wijziging). **Wat dit niet meet:** of de toetsen een echte
ontkenning of afkorting vinden. Geen naam in de drie sets draagt er een. Dat dekken de eenheidstests
(`tools/graph-qa/tests/test_begripsnaam.py`), niet deze meting.

Een meting met model (de kaarten na de verdieping) is niet gedaan: de toetsen draaien na het model, op wat het model
voorstelde, en dat verandert hier niet.
