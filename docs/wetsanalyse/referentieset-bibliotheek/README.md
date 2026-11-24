# Referentieset bibliotheek (begrippen en afleidingsregels)

Soort: *meting* (referentie, lokaal) · Hoort bij: [plan lessen Termijnen-bibliotheek](../../architectuur/plan-lessen-termijnen-bibliotheek.md), V1

Gevalideerd praktijkwerk van een uitvoeringsorganisatie als meetlat voor activiteit 3: een begrippenbibliotheek, een
afleidingsregelbibliotheek en de wetsanalyse met het werkbestand dat formuleringen aan begrippen koppelt. **Het
materiaal zelf staat niet in deze repo**: het is van derden. Hier staat alleen het manifest (`manifest.json`): per deel
het aantal pagina's en een hash, zonder namen, zodat een meting zegt op welke export ze draaide.

| set | deel | pagina's |
|---|---|---|
| `termijnen-bibliotheek-2026-11` | begrippenbibliotheek (zes trajecten) | 177 |
| | afleidingsregelbibliotheek | 36 |
| | wetsanalyse met werkbestand | 13 |

## Meten

De code staat in `tools/graph-qa/eval/extern_bibliotheek.py` en kent geen pad, geen regeling en geen afkorting. De
export is onvertrouwde invoer: alleen lezen, en met `python -I`. Alles wat eruit komt (de referentie in het neutrale
schema, het rapport) blijft lokaal, in `docs/acceptatie/lokaal/` of buiten de repo.

1. Inlezen, alleen het traject van de analyse:

   ```bash
   cd tools/graph-qa && uv run python -I eval/extern_bibliotheek.py lees --begrippen <map> --regels <map> --werkbestand <html> --traject <naam> --uit <referentie.json>
   ```

2. Het werkgebied lezen via de acceptatie-MCP (alleen lezen): `werkgebied_lezen` met `volledig: true`, `begrip_lezen`
   zonder begrip, en per actieve regel `GET /api/werkgebieden/{id}/regels/{regel}` (één JSON per regel in een map).
3. Een bestand met de afkortingen uit het werkbestand naar hun BWB-id (`{"IW": "BWBR…"}`), lokaal.
4. Vergelijken:

   ```bash
   cd tools/graph-qa && uv run python -I eval/extern_bibliotheek.py vergelijk --referentie <referentie.json> --werkgebied <werkgebied.json> --begrippen <begrippen.json> --regels <map> --afkortingen <afkortingen.json> --uit <rapport.json>
   ```

5. Een nieuwe export: `manifest --naam <set> <map …> --uit manifest.json`, en de meting in het
   [meetlogboek](../../architectuur/metingen/README.md) met alleen de getallen en de naam van de set.

## Wat de uitkomsten betekenen

Per begrip uit de referentie, gekoppeld via de formuleringen in het werkbestand (vindplaats plus tekst) en de
koppelingen van het werkgebied:

| uitkomst | betekenis |
|---|---|
| `gedekt` | precies één begrip in het werkgebied draagt deze formuleringen, en geen formuleringen van een ander referentiebegrip |
| `anders_gesneden` | de formuleringen liggen bij meer begrippen, of het begrip draagt ook die van een ander referentiebegrip (vaak: één breder begrip waar de referentie er meer heeft) |
| `zonder_begrip` | de formulering is gemarkeerd, maar er rust geen begrip op |
| `niet_gemarkeerd` | op die plek is geen element met die tekst |
| `alleen_op_naam` / `ontbreekt` | het begrip heeft geen formulering in het werkbestand (vaak een tussenresultaat); gevonden op naam, of niet |

Per regel: `gevonden` (een regel met dezelfde uitvoer op naam), `anders_gesneden` (alleen via het begrip dat de meeste
formuleringen van de uitvoer draagt: een aanwijzing, geen bewijs), `ontbreekt`. Regelbegrippen ("bepalen …") tellen
bij de begrippen niet mee.

De referentie is één analyse, geen gouden standaard, met een eigen analysevraag en eigen gaten. Een verschil is pas een
fout van Lex als een jurist dat zegt ([adjudicatieprotocol](../referentieset/adjudicatieprotocol.md)). En het is een
**ontwikkelset**: wie de keten ermee verbetert, meet daarna op iets anders.
