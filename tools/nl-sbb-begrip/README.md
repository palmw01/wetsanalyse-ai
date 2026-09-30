# nl-sbb-begrip

Een agent-workflow die voor één wettelijk begrip een **NL-SBB-conforme definitie** opstelt en die
wegschrijft als Markdown en Turtle (SKOS). Hij haalt zijn wettekst uit dezelfde BWB-kennisgraaf als
de rest van dit platform.

Dit is een **side project**: het draait niet mee in de dienst, wordt niet meegebouwd in een image en
heeft geen eigen CI. Het staat hier omdat het dezelfde graaf en dezelfde toollaag gebruikt, en dus
mee hoort te bewegen als die veranderen.

## Aanroepen

```js
{ begrip: "belastingschuldige",
  artikelen: ["2 lid 1 IW 1990", "4:89 Awb"],   // informele verwijzingen
  begrippenkader: "Invordering",                 // optioneel, default "Algemeen"
  uitvoermap: "nlsbb-begrippen" }                // optioneel, relatief pad
```

`wetteksten: [...]` mag in plaats van `artikelen`: dan slaat hij het ophalen over en analyseert hij
de meegegeven teksten. Uitvoer: `<Begrip>.md` en `<Begrip>.ttl` in de uitvoermap, plus een
samenvatting met de gebruikte vindplaatsen.

## Hij schrijft geen SPARQL — en dat is het punt

De workflow gebruikt de **getypeerde graaftools** van graph-qa via de MCP-server
`wetsanalyse-graaf` (`tools/graph-qa/agent/mcp_server.py`): `list_regelingen`, `get_artikel`,
`get_lid`, `get_bepaling`, `zoek_definitie`. Dezelfde tools die Lex gebruikt, om dezelfde reden.

Eigen SPARQL loopt in de valkuilen die `tools/graph-qa/agent/graph/queries.py` al oplost:

- een **handgeschreven BWBR-tabel** veroudert en vergist zich: AWR is `BWBR0002320`, en
  `BWBR0019237` is de Uitvoeringsregeling Awir, niet de Leidraad. Een fout nummer geeft geen
  foutmelding maar de tekst van een ándere wet;
- artikelnummers **met een dubbele punt**: `4:89` moet als `artikel:4%3A89` de graaf in;
- `bwb:tekst` als **harde eis** geeft stil nul rijen voor bepalingen die alleen onderdelen hebben,
  zoals een deel van de Leidraad;
- definities alleen zoeken in `soort == "wet"` mist definities in regelingen, zoals artikel 1ca van
  de Uitvoeringsregeling IW ("betalingsvordering", "overheidsvordering").

De regelingenlijst komt daarom uit de graaf zelf (`list_regelingen` geeft citeertitel, soort én de
officiële afkortingen). Staat een genoemde wet niet in de graaf, dan meldt de workflow dat — hij
verzint geen BWB-nummer.

## Opzetten

De MCP-server draait naast de workflow en praat met de graaf:

```bash
cd tools/graph-qa
uv sync --extra mcp
GRAPHDB_MCP_URL=… GRAPHDB_TOKEN=… uv run --extra mcp graph-qa-mcp
```

Registreer hem onder de naam **`wetsanalyse-graaf`** – die naam verwacht de workflow
(`nl-sbb-begrip.js`). Registreren doe je **machine-lokaal** (`claude mcp add`), niet in deze repo — die is publiek, en de
URL en het token van de omgeving horen er niet in.

## Wat hier niet getest is

De workflow draait in een agent-runtime die dit project niet meelevert; er is dus geen
end-to-end-test. Wat wél bewaakt is: de tools en hun queries hebben tests en een retrieval-smoke in
`tools/graph-qa`, en de MCP-server heeft tests die borgen dat hij exact die toollaag doorgeeft. Wat
in `nl-sbb-begrip.js` zelf zit — de prompts, de Turtle-opmaak — is met de hand nagelopen.
